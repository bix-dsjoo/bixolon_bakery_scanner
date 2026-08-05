[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,

    [Parameter(Mandatory = $true)]
    [string]$IsccPath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [string]$Python = 'C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$payload = [System.IO.Path]::GetFullPath($PayloadRoot)
$compiler = [System.IO.Path]::GetFullPath($IsccPath)
$output = [System.IO.Path]::GetFullPath($OutputDir)
$definition = Join-Path $repoRoot 'deployment\camera_installer\BakeryCameraEvaluator.iss'
$verifier = Join-Path $repoRoot 'scripts\verify_camera_installation.py'

if (-not (Test-Path -LiteralPath $payload -PathType Container)) {
    throw "PayloadRoot is missing: $payload"
}
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "ISCC.exe is missing: $compiler"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Build Python is missing: $Python"
}
if (Test-Path -LiteralPath $output) {
    throw "OutputDir already exists: $output"
}

$compilerVersion = (Get-Item -LiteralPath $compiler).VersionInfo.ProductVersion.Trim()
if ($compilerVersion -eq '0.0.0.0') {
    $toolUninstaller = Join-Path (Split-Path -Parent $compiler) 'unins000.exe'
    if (Test-Path -LiteralPath $toolUninstaller -PathType Leaf) {
        $compilerVersion = (Get-Item -LiteralPath $toolUninstaller).VersionInfo.ProductVersion.Trim()
    }
}
if (-not $compilerVersion.StartsWith('6.4.3')) {
    throw "Inno Setup 6.4.3 is required; got $compilerVersion"
}

$env:PYTHONPATH = $repoRoot
& $Python $verifier --root $payload
if ($LASTEXITCODE -ne 0) {
    throw "Payload verification failed with exit code $LASTEXITCODE"
}

New-Item -ItemType Directory -Path $output | Out-Null
$compilerPayload = $payload
$payloadJunction = $null
if ($payload.Length -gt 80) {
    $payloadJunction = Join-Path $env:TEMP "BixolonPayload-$PID"
    if (Test-Path -LiteralPath $payloadJunction) {
        throw "Temporary payload junction already exists: $payloadJunction"
    }
    New-Item -ItemType Junction -Path $payloadJunction -Target $payload | Out-Null
    $compilerPayload = $payloadJunction
}
try {
    & $compiler `
        "/DAppVersion=$Version" `
        "/DPayloadRoot=$compilerPayload" `
        "/O$output" `
        $definition
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
    }
}
finally {
    if ($null -ne $payloadJunction -and (Test-Path -LiteralPath $payloadJunction)) {
        [System.IO.Directory]::Delete($payloadJunction)
    }
}

$setupName = "BixolonBakeryEvaluator-$Version-win-x64-setup.exe"
$setupPath = Join-Path $output $setupName
if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
    throw "Compiled setup EXE is missing: $setupPath"
}

$setupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $setupPath).Hash.ToLowerInvariant()
"$setupHash  $setupName" | Set-Content -Encoding UTF8 -LiteralPath "$setupPath.sha256"

$manifestPath = Join-Path $payload 'package-manifest.json'
$manifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
$payloadBytes = 0L
foreach ($entry in $manifest.files.PSObject.Properties) {
    $payloadBytes += [long]$entry.Value.bytes
}
$payloadBytes += (Get-Item -LiteralPath $manifestPath).Length
$installerBytes = (Get-Item -LiteralPath $setupPath).Length
$gitCommit = (& git -C $repoRoot rev-parse HEAD).Trim()

$report = [ordered]@{
    schema_version = 1
    app_version = $Version
    architecture = 'windows-x64'
    payload_bytes = $payloadBytes
    installed_bytes = $payloadBytes
    installer_bytes = $installerBytes
    compression_ratio = [math]::Round($installerBytes / $payloadBytes, 6)
    package_manifest_sha256 = $manifestHash
    installer_sha256 = $setupHash
    git_commit = $gitCommit
    build_timestamp_utc = [DateTime]::UtcNow.ToString('o')
    unsigned_internal_test_build = $true
}
$reportPath = Join-Path $output "BixolonBakeryEvaluator-$Version-build-report.json"
$report | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $reportPath

Write-Host "Installer: $setupPath"
Write-Host "SHA-256: $setupHash"
Write-Host "Build report: $reportPath"
