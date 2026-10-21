# The user approved bounded offline initialization on 2026-10-21. The workflow
# requires a separate explicit activation marker; standalone default is stop.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallationDirectory,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [switch]$ExplicitUserAuthorization
)
$ErrorActionPreference = 'Stop'
if (-not $ExplicitUserAuthorization) { throw 'Separate user approval for offline terminal initialization is required.' }
$installation = (Resolve-Path -LiteralPath $InstallationDirectory).Path
if (-not $env:RUNNER_TEMP -or -not $installation.StartsWith(([IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Only a disposable runner temporary installation is allowed.' }
$terminal = Join-Path $installation 'terminal64.exe'
if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'An instance already exists for this path; initialization is blocked.' }
$signature = Get-AuthenticodeSignature -LiteralPath $terminal
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne '5A64A7AED24C33DED342D01D01FA5286F06DA6DC') { throw 'Terminal is not signed by the reviewed certificate.' }
if (Test-Path -LiteralPath (Join-Path $installation 'Config/accounts.dat')) { throw 'Account database exists; initialization is blocked.' }
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidence) { throw 'Evidence directory must be fresh.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$rule = New-NetFirewallRule -DisplayName 'AnticipatoryGold pending offline initialization block' -Direction Outbound -Program $terminal -Action Block -Enabled True -Profile Any
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
$profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
$effective = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $rule.Name)
if ((Get-Service MpsSvc).Status -ne 'Running' -or $profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne 'True' }).Count -ne 0) { throw 'Active firewall profiles/service verification failed.' }
if ($effective.Count -ne 1 -or $effective[0].Enabled -ne 'True' -or $effective[0].Action -ne 'Block' -or $effective[0].Direction -ne 'Outbound' -or $effective[0].Profile -ne 'Any') { throw 'Effective terminal network block verification failed.' }
$applications = @($effective[0] | Get-NetFirewallApplicationFilter)
if ($applications.Count -ne 1 -or $applications[0].Program -ne $terminal) { throw 'Blocked program path mismatch.' }
$config = Join-Path $evidence 'offline.ini'
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
Script=
'@ | Set-Content -LiteralPath $config -Encoding Unicode
$process = $null
$report = [ordered]@{ status='NOT RUN'; terminal_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $terminal).Hash; firewall_verified=$true; account_supplied=$false; expert_supplied=$false; tester_started=$false; trading_authorized=$false; exit_verified=$false; started_utc=$null; finished_utc=$null; failure=$null }
try {
    $report.started_utc = [DateTime]::UtcNow.ToString('o')
    $process = Start-Process -FilePath $terminal -ArgumentList @('/portable', "/config:`"$config`"") -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while (-not $process.HasExited -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250; $process.Refresh() }
    $report.status = 'OFFLINE INITIALIZATION ATTEMPTED - NOT A COMPILE OR BACKTEST RESULT'
} catch { $report.status='FAILED'; $report.failure=$_.Exception.Message; throw }
finally {
    $cleanupFailure = $null
    try {
        if ($process) {
            $process.Refresh()
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction Stop }
            if (-not $process.WaitForExit(5000)) { throw 'Offline terminal did not exit within cleanup timeout.' }
        }
        if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'A terminal instance remains at the temporary path.' }
        $report.exit_verified = $true
    } catch { $cleanupFailure=$_.Exception.Message; $report.status='FAILED'; $report.failure=$cleanupFailure }
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'offline-bootstrap-result.json') -Encoding utf8
    if ($cleanupFailure) { throw $cleanupFailure }
}
# PROPOSAL ONLY. No workflow invokes this file. Terminal startup needs separate
# user authorization beyond the current MetaEditor-only task. Default is stop.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallationDirectory,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [switch]$ExplicitUserAuthorization
)
$ErrorActionPreference = 'Stop'
if (-not $ExplicitUserAuthorization) { throw 'Separate user approval for offline terminal initialization is required.' }
$installation = (Resolve-Path -LiteralPath $InstallationDirectory).Path
if (-not $env:RUNNER_TEMP -or -not $installation.StartsWith(([IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Only a disposable runner temporary installation is allowed.' }
$terminal = Join-Path $installation 'terminal64.exe'
if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'An instance already exists for this path; initialization is blocked.' }
$signature = Get-AuthenticodeSignature -LiteralPath $terminal
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne '5A64A7AED24C33DED342D01D01FA5286F06DA6DC') { throw 'Terminal is not signed by the reviewed certificate.' }
if (Test-Path -LiteralPath (Join-Path $installation 'Config/accounts.dat')) { throw 'Account database exists; initialization is blocked.' }
$evidence = [IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidence) { throw 'Evidence directory must be fresh.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$rule = New-NetFirewallRule -DisplayName 'AnticipatoryGold pending offline initialization block' -Direction Outbound -Program $terminal -Action Block -Enabled True -Profile Any
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
$profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore)
$effective = @(Get-NetFirewallRule -PolicyStore ActiveStore -Name $rule.Name)
if ((Get-Service MpsSvc).Status -ne 'Running' -or $profiles.Count -ne 3 -or @($profiles | Where-Object { $_.Enabled -ne 'True' }).Count -ne 0) { throw 'Active firewall profiles/service verification failed.' }
if ($effective.Count -ne 1 -or $effective[0].Enabled -ne 'True' -or $effective[0].Action -ne 'Block' -or $effective[0].Direction -ne 'Outbound' -or $effective[0].Profile -ne 'Any') { throw 'Effective terminal network block verification failed.' }
$applications = @($effective[0] | Get-NetFirewallApplicationFilter)
if ($applications.Count -ne 1 -or $applications[0].Program -ne $terminal) { throw 'Blocked program path mismatch.' }
$config = Join-Path $evidence 'offline.ini'
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
Script=
'@ | Set-Content -LiteralPath $config -Encoding Unicode
$process = $null
$report = [ordered]@{ status='NOT RUN'; terminal_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $terminal).Hash; firewall_verified=$true; account_supplied=$false; expert_supplied=$false; tester_started=$false; trading_authorized=$false; started_utc=$null; finished_utc=$null; failure=$null }
try {
    $report.started_utc = [DateTime]::UtcNow.ToString('o')
    $process = Start-Process -FilePath $terminal -ArgumentList @('/portable', "/config:`"$config`"") -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while (-not $process.HasExited -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250; $process.Refresh() }
    $report.status = 'OFFLINE INITIALIZATION ATTEMPTED - NOT A COMPILE OR BACKTEST RESULT'
} catch { $report.status='FAILED'; $report.failure=$_.Exception.Message; throw }
finally {
    $cleanupFailure = $null
    try {
        if ($process) {
            $process.Refresh()
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction Stop }
            if (-not $process.WaitForExit(5000)) { throw 'Offline terminal did not exit within cleanup timeout.' }
        }
        if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $terminal }).Count -ne 0) { throw 'A terminal instance remains at the temporary path.' }
    } catch { $cleanupFailure=$_.Exception.Message; $report.status='FAILED'; $report.failure=$cleanupFailure }
    $report.finished_utc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'offline-bootstrap-result.json') -Encoding utf8
    if ($cleanupFailure) { throw $cleanupFailure }
}
