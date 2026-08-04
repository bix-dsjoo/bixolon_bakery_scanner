[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot,

    [Parameter(Mandatory = $true)]
    [string]$IsccPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [string]$FlutterPath = 'C:\workspace\tools\flutter-3.44.7\bin\flutter.bat',

    [string]$Python = 'C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe',

    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '1.1.0'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][bool]$Directory
    )
    $resolved = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
    if ($Directory -and -not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "$Label directory is missing: $resolved"
    }
    if (-not $Directory -and -not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "$Label file is missing: $resolved"
    }
    return $resolved
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runtime = Resolve-RequiredPath -Path $RuntimeRoot -Label 'RuntimeRoot' -Directory $true
$compiler = Resolve-RequiredPath -Path $IsccPath -Label 'IsccPath' -Directory $false
$flutter = Resolve-RequiredPath -Path $FlutterPath -Label 'FlutterPath' -Directory $false
$buildPython = Resolve-RequiredPath -Path $Python -Label 'Python' -Directory $false
$output = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputRoot))
$releaseDirectory = Join-Path $repoRoot 'apps\bakery_camera_flutter\build\windows\x64\runner\Release'
$payload = Join-Path $output 'portable'
$installer = Join-Path $output 'installer'
$vcRuntimeDirectory = Split-Path -Parent $runtime

if (Test-Path -LiteralPath $output) {
    throw "OutputRoot already exists: $output"
}
foreach ($dll in @('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $vcRuntimeDirectory $dll) -PathType Leaf)) {
        throw "Application-local VC runtime is missing: $(Join-Path $vcRuntimeDirectory $dll)"
    }
}

New-Item -ItemType Directory -Path $output | Out-Null
try {
    Push-Location (Join-Path $repoRoot 'apps\bakery_camera_flutter')
    try {
        & $flutter build windows --release
        if ($LASTEXITCODE -ne 0) {
            throw "Flutter Release build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    $env:PYTHONPATH = $repoRoot
    & $buildPython (Join-Path $repoRoot 'scripts\build_camera_installer_payload.py') `
        --repo-root $repoRoot `
        --release-dir $releaseDirectory `
        --runtime-root $runtime `
        --vc-runtime-dir $vcRuntimeDirectory `
        --output $payload `
        --app-version $Version
    if ($LASTEXITCODE -ne 0) {
        throw "Portable payload build failed with exit code $LASTEXITCODE"
    }

    & $buildPython (Join-Path $repoRoot 'scripts\verify_camera_installation.py') `
        --root $payload `
        --launch-worker-smoke `
        --worker-device auto `
        --analysis-count 0
    if ($LASTEXITCODE -ne 0) {
        throw "Portable payload verification failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $repoRoot 'scripts\build_camera_installer.ps1') `
        -PayloadRoot $payload `
        -IsccPath $compiler `
        -Version $Version `
        -OutputDir $installer `
        -Python $buildPython
    if ($LASTEXITCODE -ne 0) {
        throw "Installer build failed with exit code $LASTEXITCODE"
    }
}
catch {
    if (Test-Path -LiteralPath $output) {
        Write-Warning "Incomplete release output retained for diagnosis: $output"
    }
    throw
}

Write-Host "Portable: $payload"
Write-Host "Installer: $installer"
