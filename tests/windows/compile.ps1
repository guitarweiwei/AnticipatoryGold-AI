# Real MetaEditor compilation only. Does not launch MT5 or execute the EA.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$MetaEditor,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$IncludeRoot,
    [Parameter(Mandatory=$true)][string]$EvidenceDirectory,
    [string]$SourceTreeRoot = '',
    [ValidateRange(10,600)][int]$TimeoutSeconds = 120
)
$ErrorActionPreference = 'Stop'
$editorPath = (Resolve-Path -LiteralPath $MetaEditor).Path
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$includePath = [IO.Path]::GetFullPath($IncludeRoot)
if ([IO.Path]::GetExtension($sourcePath) -ne '.mq5') { throw 'Expected an .mq5 source file.' }
# Missing vendor headers are recorded, not fabricated. Still invoke the real
# compiler to obtain its diagnostic log; success requires the real library below.
$evidencePath = [IO.Path]::GetFullPath($EvidenceDirectory)
if (Test-Path -LiteralPath $evidencePath) { throw 'Choose a fresh evidence directory; previous evidence will not be overwritten.' }
New-Item -ItemType Directory -Path $evidencePath | Out-Null
$result = [ordered]@{
    status = 'NOT RUN'; source_commit = $env:GITHUB_SHA; source_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash
    compiler_path = $editorPath; compiler_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $editorPath).Hash
    compiler_file_version = (Get-Item -LiteralPath $editorPath).VersionInfo.FileVersion
    compiler_product_version = (Get-Item -LiteralPath $editorPath).VersionInfo.ProductVersion
    started_utc = $null; finished_utc = $null; process_exit_code = $null; errors = $null; warnings = $null
    ex5_sha256 = $null; compiler_result = $null; failure = $null; mt5_backtest = 'NOT RUN'
}
try {
    $signature = Get-AuthenticodeSignature -LiteralPath $editorPath
    if ($signature.Status -ne 'Valid') { throw "Compiler Authenticode signature is not valid: $($signature.Status)" }
    $result.compiler_signer_subject = $signature.SignerCertificate.Subject
    $result.compiler_signer_thumbprint = $signature.SignerCertificate.Thumbprint
    $work = Join-Path $evidencePath 'source'
    New-Item -ItemType Directory -Path $work | Out-Null
    # Copy sibling relative include files as well as the main mq5; never reuse ex5/log.
    $sourceFolder = if ($SourceTreeRoot) { (Resolve-Path -LiteralPath $SourceTreeRoot).Path } else { Split-Path -Parent $sourcePath }
    $relativeSource = [IO.Path]::GetRelativePath($sourceFolder, $sourcePath)
    if ($relativeSource.StartsWith('..') -or [IO.Path]::IsPathRooted($relativeSource)) { throw 'Source must be inside SourceTreeRoot.' }
    Get-ChildItem -LiteralPath $sourceFolder -Recurse -File | Where-Object { $_.Extension -in '.mq5','.mqh' } | ForEach-Object {
        $relative = [IO.Path]::GetRelativePath($sourceFolder, $_.FullName)
        $target = Join-Path $work $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target
    }
    $manifest = @(Get-ChildItem -LiteralPath $work -Recurse -File | ForEach-Object {
        [ordered]@{ path = [IO.Path]::GetRelativePath($work,$_.FullName); sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash }
    })
    ConvertTo-Json -InputObject $manifest -Depth 4 | Set-Content -LiteralPath (Join-Path $evidencePath 'source-manifest.json') -Encoding utf8
    $result.standard_library_present_before = Test-Path -LiteralPath (Join-Path $includePath 'Include/Trade/Trade.mqh')
    $libraryManifest = @(Get-ChildItem -LiteralPath (Join-Path $includePath 'Include') -Recurse -File -Filter '*.mqh' -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{ path = [IO.Path]::GetRelativePath($includePath,$_.FullName); sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash }
    })
    ConvertTo-Json -InputObject $libraryManifest -Depth 4 | Set-Content -LiteralPath (Join-Path $evidencePath 'standard-library-manifest.json') -Encoding utf8
    $compileSource = Join-Path $work $relativeSource
    $nativeLog = [IO.Path]::ChangeExtension($compileSource, '.log')
    $binary = [IO.Path]::ChangeExtension($compileSource, '.ex5')
    $result.started_utc = [DateTime]::UtcNow.ToString('o')
    $result.status = 'RUNNING'
    $arguments = @("/compile:`"$compileSource`"", "/include:`"$includePath`"", '/log', '/portable')
    $process = Start-Process -FilePath $editorPath -ArgumentList $arguments -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw 'MetaEditor timed out; compilation result is unavailable.'
    }
    $process.Refresh()
    $result.process_exit_code = $process.ExitCode
    if (-not (Test-Path -LiteralPath $nativeLog)) { throw 'No fresh compiler log was created.' }
    Copy-Item -LiteralPath $nativeLog -Destination (Join-Path $evidencePath 'metaeditor.log')
    $logText = Get-Content -LiteralPath $nativeLog -Raw
    Write-Output $logText
    $summary = [regex]::Matches($logText, '(?im)^[ \t]*Result:\s*(\d+)\s+errors?,\s*(\d+)\s+warnings?\b[^\r\n]*\r?$')
    if ($summary.Count -ne 1) { throw 'Expected exactly one parseable compiler Result line; inspect the raw log.' }
    $result.errors = [int]$summary[0].Groups[1].Value
    $result.warnings = [int]$summary[0].Groups[2].Value
    $result.compiler_result = $summary[0].Value.Trim()
    if ($result.errors -ne 0 -or $result.warnings -ne 0) { throw 'Compiler reported errors or warnings; review the raw log before proceeding.' }
    if (-not (Test-Path -LiteralPath $binary) -or (Get-Item -LiteralPath $binary).Length -le 0) { throw 'Compiler reported success without a fresh nonempty EX5.' }
    $result.ex5_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash
    if (-not (Test-Path -LiteralPath (Join-Path $includePath 'Include/Trade/Trade.mqh'))) { throw 'Compiler output exists but the installed standard-library path is unverified; inspect evidence.' }
    $libraryManifest = @(Get-ChildItem -LiteralPath (Join-Path $includePath 'Include') -Recurse -File -Filter '*.mqh' | ForEach-Object {
        [ordered]@{ path = [IO.Path]::GetRelativePath($includePath,$_.FullName); sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash }
    })
    ConvertTo-Json -InputObject $libraryManifest -Depth 4 | Set-Content -LiteralPath (Join-Path $evidencePath 'standard-library-manifest.json') -Encoding utf8
    $result.status = 'PASSED'
} catch {
    $result.status = 'FAILED'
    $result.failure = $_.Exception.Message
    throw
} finally {
    $result.finished_utc = [DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidencePath 'compile-result.json') -Encoding utf8
}
