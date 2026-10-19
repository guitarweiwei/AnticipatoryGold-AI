# Compile locally in MetaEditor. Does not launch MT5, attach an EA, or enable trading.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$MetaEditor,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Log
)
$ErrorActionPreference = 'Stop'
$editorPath = (Resolve-Path -LiteralPath $MetaEditor).Path
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
if ([IO.Path]::GetExtension($sourcePath) -ne '.mq5') { throw 'Expected an .mq5 source file.' }
$logPath = [IO.Path]::GetFullPath($Log)
if (Test-Path -LiteralPath $logPath) { throw 'Choose a new log path; previous evidence will not be overwritten.' }
$parentPath = Split-Path -Parent $logPath
New-Item -ItemType Directory -Force -Path $parentPath | Out-Null
$process = Start-Process -FilePath $editorPath -ArgumentList @("/compile:`"$sourcePath`"", "/log:`"$logPath`"") -Wait -PassThru
if (-not (Test-Path -LiteralPath $logPath)) { throw 'MetaEditor produced no log. Compilation evidence is unavailable.' }
Get-Content -LiteralPath $logPath
Write-Output "MetaEditor process exit code: $($process.ExitCode). Inspect the actual log for error/warning counts."
Write-Output "Source SHA256: $((Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash)"
Write-Output 'MT5 Strategy Tester execution: NOT RUN by this script.'
