# Download/signature preflight is the default. Installation needs reviewed consent
# AND exact hashes from a prior preflight. No broker credentials are accepted.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RepositoryRoot,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [switch]$AcceptMetaQuotesEula,
    [string]$ApprovedInstallerSha256 = '',
    [string]$ApprovedSignerThumbprint = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidence) { throw 'Evidence directory must be fresh.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$downloadUrl = 'https://download.terminal.free/cdn/web/metaquotes.ltd/mt5/mt5setup.exe'
$eulaUrl = 'https://www.metaquotes.net/licenses/terminal/mt5'
$report = [ordered]@{ status='NOT RUN'; compile='NOT RUN'; backtest='NOT RUN'; installer_url=$downloadUrl; eula_url=$eulaUrl; eula_accepted=[bool]$AcceptMetaQuotesEula; source_commit=$env:GITHUB_SHA; signer_subject=$null; signer_thumbprint=$null; installer_sha256=$null; failure=$null }
$temporaryRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$installPath = Join-Path $temporaryRoot 'AnticipatoryGold-MetaQuotes'
$firewallName = 'AnticipatoryGold compile-only terminal network block'
try {
    $installer = Join-Path $evidence 'mt5setup.exe'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installer -TimeoutSec 120 -MaximumRedirection 5
    $report.installer_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    $report.signature_status = $signature.Status.ToString()
    if ($signature.SignerCertificate) {
        $report.signer_subject = $signature.SignerCertificate.Subject
        $report.signer_thumbprint = $signature.SignerCertificate.Thumbprint
    }
    if ($signature.Status -ne 'Valid') { throw "Installer Authenticode signature is not valid: $($signature.Status)" }
    if (-not $AcceptMetaQuotesEula) {
        $report.status = 'PREFLIGHT ONLY - INSTALLATION NOT AUTHORIZED'
        Write-Output 'Download/signature preflight complete. Installation, MetaEditor compile and MT5 backtest: NOT RUN.'
        Write-Output ($report | ConvertTo-Json -Depth 4)
        return
    }
    if ($ApprovedInstallerSha256 -notmatch '^[A-Fa-f0-9]{64}$' -or $ApprovedSignerThumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Installation requires the reviewed installer SHA256 and signing-certificate thumbprint from a previous preflight.' }
    if ($report.installer_sha256 -ne $ApprovedInstallerSha256 -or $report.signer_thumbprint -ne $ApprovedSignerThumbprint) { throw 'Installer/signing certificate changed since preflight. Review a new preflight before installation.' }
    if (Test-Path -LiteralPath $installPath) { throw 'Installation directory is not fresh.' }
    # The installer may auto-launch terminal64. Block its network before install;
    # stop that process if spawned. The script never invokes terminal64 itself.
    $terminalPath = Join-Path $installPath 'terminal64.exe'
    $firewallRule = New-NetFirewallRule -DisplayName $firewallName -Direction Outbound -Program $terminalPath -Action Block -Enabled True -Profile Any
    Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
    if ((Get-Service -Name MpsSvc).Status -ne 'Running') { throw 'Windows firewall service is not running; installation is blocked.' }
    $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
    if ($profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne 'True' }).Count -ne 0) { throw 'Windows firewall profiles are not all enabled; installation is blocked.' }
    $effectiveRules = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $firewallRule.Name)
    if ($effectiveRules.Count -ne 1 -or $effectiveRules[0].Enabled -ne 'True' -or $effectiveRules[0].Action -ne 'Block' -or $effectiveRules[0].Direction -ne 'Outbound' -or $effectiveRules[0].Profile -ne 'Any') { throw 'Terminal outbound firewall block is not effective; installation is blocked.' }
    $applications = @($effectiveRules[0] | Get-NetFirewallApplicationFilter)
    if ($applications.Count -ne 1 -or $applications[0].Program -ne $terminalPath) { throw 'Terminal firewall program path mismatch; installation is blocked.' }
    $report.terminal_firewall_profiles_enabled = $true
    $report.terminal_firewall_rule_verified = $true
    $install = Start-Process -FilePath $installer -ArgumentList @('/auto', "/path:`"$installPath`"") -PassThru
    $deadline = [DateTime]::UtcNow.AddMinutes(5)
    while (-not $install.HasExited -and [DateTime]::UtcNow -lt $deadline) {
        Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $installPath 'terminal64.exe') } | Stop-Process -Force
        Start-Sleep -Milliseconds 250
        $install.Refresh()
    }
    if (-not $install.HasExited) { Stop-Process -Id $install.Id -Force -ErrorAction SilentlyContinue; throw 'Official installer timed out.' }
    Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $installPath 'terminal64.exe') } | Stop-Process -Force
    $install.WaitForExit()
    $report.installer_exit_code = $install.ExitCode
    # Record the native installer exit code. Its meaning is not documented here;
    # compilation still requires an actual signed editor and installed includes.
    $installedFiles = @(Get-ChildItem -LiteralPath $installPath -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{ path = [IO.Path]::GetRelativePath($installPath, $_.FullName); bytes = $_.Length }
    })
    ConvertTo-Json -InputObject $installedFiles -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'installation-files.json') -Encoding utf8
    $editor = Join-Path $installPath 'metaeditor64.exe'
    if (-not (Test-Path -LiteralPath $editor)) { throw 'Installer did not produce MetaEditor; no compilation occurred.' }
    $editorSignature = Get-AuthenticodeSignature -LiteralPath $editor
    if ($editorSignature.Status -ne 'Valid' -or $editorSignature.SignerCertificate.Subject -ne $report.signer_subject) { throw 'Installed MetaEditor publisher does not match the reviewed signed installer.' }
    # The installer may put the standard library in the per-user data folder.
    # Match origin.txt to this exact temporary installation; never launch terminal
    # merely to populate files, or borrow headers from an unrelated installation.
    $includeRoot = Join-Path $installPath 'MQL5'
    if (-not (Test-Path -LiteralPath (Join-Path $includeRoot 'Include/Trade/Trade.mqh'))) {
        # Initialize only the signed editor's portable standard library. No EA,
        # terminal, tester or account is supplied to this editor startup.
        $bootstrap = Start-Process -FilePath $editor -ArgumentList '/portable' -PassThru
        try {
            $bootstrapDeadline = [DateTime]::UtcNow.AddSeconds(30)
            while (-not (Test-Path -LiteralPath (Join-Path $includeRoot 'Include/Trade/Trade.mqh')) -and -not $bootstrap.HasExited -and [DateTime]::UtcNow -lt $bootstrapDeadline) {
                Start-Sleep -Milliseconds 250
                $bootstrap.Refresh()
            }
            if (Test-Path -LiteralPath (Join-Path $includeRoot 'Include/Trade/Trade.mqh')) { Start-Sleep -Seconds 5 }
        } finally {
            if (-not $bootstrap.HasExited) { Stop-Process -Id $bootstrap.Id -Force -ErrorAction SilentlyContinue }
            $bootstrap.WaitForExit()
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $includeRoot 'Include/Trade/Trade.mqh'))) {
        $dataRoot = Join-Path $env:APPDATA 'MetaQuotes/Terminal'
        $matches = @(Get-ChildItem -LiteralPath $dataRoot -Directory -ErrorAction SilentlyContinue | Where-Object {
            $originPath = Join-Path $_.FullName 'origin.txt'
            if (Test-Path -LiteralPath $originPath) {
                $origin = (Get-Content -Raw -LiteralPath $originPath).Trim()
                $origin -eq $installPath -and (Test-Path -LiteralPath (Join-Path $_.FullName 'MQL5/Include/Trade/Trade.mqh'))
            }
        })
        if ($matches.Count -ne 1) { throw 'No unique standard-library data folder belongs to this installation.' }
        $includeRoot = Join-Path $matches[0].FullName 'MQL5'
    }
    $report.standard_library_root = $includeRoot
    & (Join-Path $root 'tests/windows/compile.ps1') -MetaEditor $editor -Source (Join-Path $root 'MQL5/Experts/AnticipatoryGold_AI_v1.mq5') -IncludeRoot $includeRoot -EvidenceDirectory (Join-Path $evidence 'compile')
    $report.compile = 'PASSED - SEE REAL COMPILER LOG'
    $report.status = 'COMPILED'
} catch {
    $report.status = 'FAILED'
    $compileReportPath = Join-Path $evidence 'compile/compile-result.json'
    if (Test-Path -LiteralPath $compileReportPath) {
        $compileReport = Get-Content -Raw -LiteralPath $compileReportPath | ConvertFrom-Json
        if ($compileReport.started_utc) { $report.compile = 'FAILED - SEE REAL COMPILER EVIDENCE' }
    }
    $report.failure = $_.Exception.Message
    throw
} finally {
    Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $installPath 'terminal64.exe') } | Stop-Process -Force -ErrorAction SilentlyContinue
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidence 'preflight-result.json') -Encoding utf8
    if ($env:GITHUB_STEP_SUMMARY) {
        @"
## MetaEditor evidence status

- Preflight/installation status: **$($report.status)**
- Actual MetaEditor compilation: **$($report.compile)**
- MT5 backtest: **NOT RUN**
- Installer SHA256: $($report.installer_sha256)
- Installer signing subject: $($report.signer_subject)
- Signing certificate thumbprint: $($report.signer_thumbprint)

A successful preflight job does not mean the EA compiled. Review the JSON and real compiler log when one exists.
"@ | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Encoding utf8
    }
    # Do not upload installer/compiler binaries. Firewall lives only on this disposable runner.
}
