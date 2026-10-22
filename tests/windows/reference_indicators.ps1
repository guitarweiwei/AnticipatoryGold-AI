# No-order native indicator export for a separately labelled Python quote replay.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$RepositoryRoot,
 [Parameter(Mandatory=$true)][string]$InstallationDirectory,
 [Parameter(Mandatory=$true)][string]$M1File,
 [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
 [switch]$ExplicitUserAuthorization
)
$ErrorActionPreference='Stop'
if (-not $ExplicitUserAuthorization) { throw 'Explicit research authorization required.' }
$root=(Resolve-Path -LiteralPath $RepositoryRoot).Path
$installation=(Resolve-Path -LiteralPath $InstallationDirectory).Path
if (-not $env:RUNNER_TEMP -or -not $installation.StartsWith(([IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Disposable runner installation required.' }
$evidence=[IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidence) { throw 'Fresh evidence directory required.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$terminal=Join-Path $installation 'terminal64.exe'
$process=$null
$report=[ordered]@{status='NOT_RUN';account_supplied=$false;orders_authorized=$false;mt5_strategy_tester='NOT_RUN';purpose='NATIVE_INDICATORS_FOR_PYTHON_REFERENCE_REPLAY';source_commit=$env:GITHUB_SHA;firewall_verified=$false;exit_verified=$false;failure=$null}
try {
 foreach ($name in @('terminal64.exe','metaeditor64.exe')) {
  $signature=Get-AuthenticodeSignature -LiteralPath (Join-Path $installation $name)
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne '5A64A7AED24C33DED342D01D01FA5286F06DA6DC') { throw 'Unreviewed signed executable.' }
 }
 if (Test-Path -LiteralPath (Join-Path $installation 'Config/accounts.dat')) { throw 'Account database found.' }
 if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $terminal}).Count -ne 0) { throw 'Existing terminal process found.' }
 $rule=New-NetFirewallRule -DisplayName 'AnticipatoryGold native indicator export offline' -Direction Outbound -Program $terminal -Action Block -Enabled True -Profile Any
 Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
 $profiles=@(Get-NetFirewallProfile -PolicyStore ActiveStore)
 $effective=@(Get-NetFirewallRule -PolicyStore ActiveStore -Name $rule.Name)
 $applications=@($effective | Get-NetFirewallApplicationFilter)
 if ((Get-Service MpsSvc).Status -ne 'Running' -or $profiles.Count -ne 3 -or @($profiles | Where-Object {$_.Enabled -ne 'True'}).Count -ne 0 -or $effective.Count -ne 1 -or $effective[0].Action -ne 'Block' -or $effective[0].Enabled -ne 'True' -or $effective[0].Direction -ne 'Outbound' -or $effective[0].Profile -ne 'Any' -or $applications.Count -ne 1 -or $applications[0].Program -ne $terminal) { throw 'Effective offline firewall validation failed.' }
 $report.firewall_verified=$true
 $compiled=Join-Path $evidence 'compile'
 & (Join-Path $root 'tests/windows/compile.ps1') -MetaEditor (Join-Path $installation 'metaeditor64.exe') -Source (Join-Path $root 'MQL5/Tests/Performance/ExportReferenceIndicators.mq5') -SourceTreeRoot (Join-Path $root 'MQL5') -IncludeRoot (Join-Path $installation 'MQL5') -EvidenceDirectory $compiled
 $compileReport=Get-Content -Raw (Join-Path $compiled 'compile-result.json') | ConvertFrom-Json
 if ($compileReport.status -ne 'PASSED' -or $compileReport.errors -ne 0 -or $compileReport.warnings -ne 0) { throw 'Native indicator compile failed.' }
 $destination=Join-Path $installation 'MQL5/Scripts/AnticipatoryGoldReference/ExportReferenceIndicators.ex5'
 if (Test-Path -LiteralPath $destination) { throw 'Script path already exists.' }
 New-Item -ItemType Directory -Path (Split-Path -Parent $destination) | Out-Null
 Copy-Item -LiteralPath (Join-Path $compiled 'source/Tests/Performance/ExportReferenceIndicators.ex5') -Destination $destination
 $report.deployed_ex5_sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
 if ($report.deployed_ex5_sha256 -ne $compileReport.ex5_sha256) { throw 'Deployed binary mismatch.' }
 $files=Join-Path $installation 'MQL5/Files'
 New-Item -ItemType Directory -Force -Path $files | Out-Null
 if (@(Get-ChildItem -LiteralPath $files -Filter 'AG_REF_*').Count -ne 0) { throw 'Indicator data scope not fresh.' }
 Copy-Item -LiteralPath $M1File -Destination (Join-Path $files 'AG_REF_M1.csv')
 $report.input_m1_sha256=(Get-FileHash -LiteralPath $M1File -Algorithm SHA256).Hash
 $config=Join-Path $evidence 'indicators.ini'
 @'
[Common]
Login=0
KeepPrivate=0
NewsEnable=0
CertInstall=0
[Charts]
MaxBars=10000000
[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
[StartUp]
Expert=
Script=AnticipatoryGoldReference\ExportReferenceIndicators
Symbol=EURUSD
Period=M1
ShutdownTerminal=1
'@ | Set-Content -LiteralPath $config -Encoding Unicode
 $report.started_utc=[DateTime]::UtcNow.ToString('o')
 $process=Start-Process -FilePath $terminal -ArgumentList @('/portable',"/config:`"$config`"") -PassThru
 if (-not $process.WaitForExit(120000)) { throw 'Native indicator script timed out.' }
 $report.terminal_exit_code=$process.ExitCode
 foreach ($file in @('AG_REF_M5.csv','AG_REF_H1.csv','AG_REF_INDICATORS_RESULT.json')) {
  $output=Join-Path $files $file
  if (-not (Test-Path -LiteralPath $output) -or (Get-Item -LiteralPath $output).Length -le 0) { throw "Missing native output $file" }
  Copy-Item -LiteralPath $output -Destination (Join-Path $evidence $file)
  $report[$file+'_sha256']=(Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
 }
 $native=Get-Content -Raw (Join-Path $evidence 'AG_REF_INDICATORS_RESULT.json') | ConvertFrom-Json
 if ($native.passed -isnot [bool] -or -not $native.passed) { throw 'Native data/indicator result did not pass.' }
 $report.status='PASSED'
} catch { $report.status='FAILED';$report.failure=$_.Exception.Message;throw }
finally {
 try {
  if ($process) { $process.Refresh(); if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force };if (-not $process.WaitForExit(5000)) { throw 'Terminal exit verification failed.' } }
  if (@(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $terminal}).Count -ne 0) { throw 'Terminal remains running.' }
  $report.exit_verified=$true
 } catch { $report.status='FAILED';$report.failure=$_.Exception.Message }
 foreach ($logroot in @('logs','MQL5/Logs')) {
  $path=Join-Path $installation $logroot
  if (Test-Path -LiteralPath $path) { $target=Join-Path $evidence $logroot;New-Item -ItemType Directory -Force -Path $target | Out-Null;Get-ChildItem -LiteralPath $path -Filter '*.log' -File | Copy-Item -Destination $target }
 }
 $report.finished_utc=[DateTime]::UtcNow.ToString('o')
 $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidence 'native-indicators-run.json') -Encoding utf8
 if ($report.status -ne 'PASSED') { throw $report.failure }
}
