# Execute only the reviewed no-order native script in a disposable offline terminal.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RepositoryRoot,
    [Parameter(Mandatory=$true)][string]$InstallationDirectory,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [switch]$ExplicitUserAuthorization
)
$ErrorActionPreference = 'Stop'
if (-not $ExplicitUserAuthorization) { throw 'Native script execution requires explicit authorization.' }
$root = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$installation = (Resolve-Path -LiteralPath $InstallationDirectory).Path
if (-not $env:RUNNER_TEMP -or -not $installation.StartsWith(([IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Disposable runner temporary installation required.' }
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidence) { throw 'Fresh evidence directory required.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$report = [ordered]@{ status='NOT RUN'; source_commit=$env:GITHUB_SHA; native_script='NOT RUN'; backtest='NOT RUN'; account_supplied=$false; production_ea_loaded=$false; trading_authorized=$false; firewall_verified=$false; exit_verified=$false; started_utc=$null; finished_utc=$null; failure=$null }
$process = $null
$terminal = Join-Path $installation 'terminal64.exe'
try {
    foreach ($name in @('terminal64.exe','metaeditor64.exe')) {
        $path = Join-Path $installation $name
        $signature = Get-AuthenticodeSignature -LiteralPath $path
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne '5A64A7AED24C33DED342D01D01FA5286F06DA6DC') { throw "Unreviewed signed executable: $name" }
    }
    $report.terminal_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $terminal).Hash
    if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'Terminal already running at this path.' }
    if (Test-Path -LiteralPath (Join-Path $installation 'Config/accounts.dat')) { throw 'Account database exists; execution blocked.' }
    $rule = New-NetFirewallRule -DisplayName 'AnticipatoryGold native script outbound block' -Direction Outbound -Program $terminal -Action Block -Enabled True -Profile Any
    Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
    $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
    $effective = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $rule.Name)
    if ((Get-Service MpsSvc).Status -ne 'Running' -or $profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne 'True' }).Count -ne 0) { throw 'Firewall profiles/service verification failed.' }
    if ($effective.Count -ne 1 -or $effective[0].Enabled -ne 'True' -or $effective[0].Action -ne 'Block' -or $effective[0].Direction -ne 'Outbound' -or $effective[0].Profile -ne 'Any') { throw 'Effective firewall block verification failed.' }
    $applications = @($effective[0] | Get-NetFirewallApplicationFilter)
    if ($applications.Count -ne 1 -or $applications[0].Program -ne $terminal) { throw 'Firewall program path mismatch.' }
    $report.firewall_verified = $true
    $source = Join-Path $root 'MQL5/Tests/Native/AnticipatoryGold_NativeTests.mq5'
    $compiled = Join-Path $evidence 'compile'
    & (Join-Path $root 'tests/windows/compile.ps1') -MetaEditor (Join-Path $installation 'metaeditor64.exe') -Source $source -SourceTreeRoot (Join-Path $root 'MQL5') -IncludeRoot (Join-Path $installation 'MQL5') -EvidenceDirectory $compiled
    $compileReport = Get-Content -Raw (Join-Path $compiled 'compile-result.json') | ConvertFrom-Json
    if ($compileReport.status -ne 'PASSED' -or $compileReport.errors -ne 0 -or $compileReport.warnings -ne 0) { throw 'Native script compilation did not pass.' }
    $binary = Join-Path $compiled 'source/Tests/Native/AnticipatoryGold_NativeTests.ex5'
    $destination = Join-Path $installation 'MQL5/Scripts/AnticipatoryGoldNative/AnticipatoryGold_NativeTests.ex5'
    if (Test-Path -LiteralPath $destination) { throw 'Script deployment path already exists.' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $binary -Destination $destination
    $report.script_ex5_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash
    if ($report.script_ex5_sha256 -ne $compileReport.ex5_sha256) { throw 'Deployed native script hash mismatch.' }
    $files = Join-Path $installation 'MQL5/Files'
    New-Item -ItemType Directory -Force -Path $files | Out-Null
    if (@(Get-ChildItem -LiteralPath $files -Filter 'AG_NATIVE_*' -File).Count -ne 0) { throw 'Native output scope is not fresh.' }
    $config = Join-Path $evidence 'native.ini'
    @'
[Common]
Login=0
KeepPrivate=0
NewsEnable=0
CertInstall=0
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[StartUp]
Expert=
Script=AnticipatoryGoldNative\AnticipatoryGold_NativeTests
Symbol=EURUSD
Period=M1
ShutdownTerminal=1
'@ | Set-Content -LiteralPath $config -Encoding Unicode
    $report.started_utc = [DateTime]::UtcNow.ToString('o')
    $report.native_script = 'ATTEMPTED'
    $process = Start-Process -FilePath $terminal -ArgumentList @('/portable', "/config:`"$config`"") -PassThru
    if (-not $process.WaitForExit(120000)) { throw 'Native script terminal timed out; missing results cannot pass.' }
    $report.terminal_exit_code = $process.ExitCode
    $outputs = @(Get-ChildItem -LiteralPath $files -Filter 'AG_NATIVE_*.jsonl' -File)
    if ($outputs.Count -ne 1 -or $outputs[0].Length -le 0) { throw 'Expected exactly one fresh nonempty native JSONL result.' }
    Copy-Item -LiteralPath $outputs[0].FullName -Destination (Join-Path $evidence 'native-results.jsonl')
    $report.native_results_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $outputs[0].FullName).Hash
    # Strict schema/case validation is performed below after native output exists.
    $lines = @(Get-Content -LiteralPath $outputs[0].FullName | Where-Object { $_.Trim() -ne '' })
    $records = @($lines | ForEach-Object { $_ | ConvertFrom-Json })
    $expected = Get-Content -Raw (Join-Path $root 'MQL5/Tests/Native/expected_cases.json') | ConvertFrom-Json
    if ($expected.schema_version -ne 1 -or $expected.case_ids.Count -lt 1) { throw 'Unknown or empty native case manifest.' }
    $cases = @($records | Where-Object { $_.type -eq 'case' })
    $summaries = @($records | Where-Object { $_.type -eq 'summary' })
    $ids = @($cases | ForEach-Object { $_.id })
    if ($summaries.Count -ne 1 -or $cases.Count -ne $expected.case_ids.Count -or @($records | Where-Object { $_.type -notin 'case','summary' }).Count -ne 0) { throw 'Native record count/schema mismatch.' }
    if (@($ids | Sort-Object -Unique).Count -ne $ids.Count -or @(Compare-Object ($ids | Sort-Object) ($expected.case_ids | Sort-Object)).Count -ne 0) { throw 'Native case IDs are missing, duplicated or unexpected.' }
    if (@($cases | Where-Object { $_.passed -isnot [bool] -or -not $_.passed }).Count -ne 0) { throw 'A native case failed or lacks a boolean verdict.' }
    if ($summaries[0].schema_version -ne 1 -or $summaries[0].send_attempts -ne 0 -or $summaries[0].denied_file_opens -ne 0 -or $summaries[0].broker_fault_tests -ne 'NOT_RUN' -or $summaries[0].performance_backtest -ne 'NOT_RUN') { throw 'Native containment/evidence boundary mismatch.' }
    foreach ($key in @('schema_version','total','passed','failed','denied_file_opens','send_attempts')) {
        if ($summaries[0].$key -isnot [int] -and $summaries[0].$key -isnot [long]) { throw "Native summary count is not an integer: $key" }
    }
    if ($summaries[0].total -ne $cases.Count -or $summaries[0].passed -ne $cases.Count -or $summaries[0].failed -ne 0) { throw 'Native summary does not match actual cases.' }
    $report.total = $cases.Count
    $report.passed = $cases.Count
    $report.native_script = 'PASSED'
    $report.status = 'PASSED'
} catch {
    $report.status = 'FAILED'
    $report.failure = $_.Exception.Message
    throw
} finally {
    $cleanupFailure = $null
    try {
        if ($process) {
            $process.Refresh()
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction Stop }
            if (-not $process.WaitForExit(5000)) { throw 'Native terminal failed to exit.' }
        }
        if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'Terminal process remains at installation path.' }
        $report.exit_verified = $true
    } catch { $cleanupFailure=$_.Exception.Message; $report.status='FAILED'; $report.failure=$cleanupFailure }
    # Preserve only synthetic case files from the isolated new namespace.
    $fixtureRoot = Join-Path $installation 'MQL5/Files'
    if (Test-Path -LiteralPath $fixtureRoot) {
        $fixtureTarget = Join-Path $evidence 'fixtures'
        New-Item -ItemType Directory -Force -Path $fixtureTarget | Out-Null
        Get-ChildItem -LiteralPath $fixtureRoot -Filter 'AG_NATIVE_*' -File | Copy-Item -Destination $fixtureTarget
    }
    # Logs are generated only in this fresh no-account disposable installation.
    foreach ($logRoot in @('logs','MQL5/Logs')) {
        $path = Join-Path $installation $logRoot
        if (Test-Path -LiteralPath $path) {
            $target = Join-Path $evidence $logRoot
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            Get-ChildItem -LiteralPath $path -Filter '*.log' -File | Copy-Item -Destination $target
        }
    }
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidence 'native-run-result.json') -Encoding utf8
    if ($env:GITHUB_STEP_SUMMARY) { "Native no-order script: **$($report.status)**; historical MT5 backtest: **NOT RUN**. See native result and case records." | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY }
    if ($cleanupFailure) { throw $cleanupFailure }
}
