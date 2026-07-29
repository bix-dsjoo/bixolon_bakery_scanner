[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [Parameter(Mandatory = $true)]
    [string]$WheelCache,

    [string]$HostPython = 'C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeLock = Join-Path $repoRoot 'deployment\camera_installer\runtime-lock.json'
$requirementsLock = Join-Path $repoRoot 'deployment\camera_installer\runtime-requirements-cu130.lock.txt'
$validator = Join-Path $repoRoot 'scripts\camera_runtime_validation.py'
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputRoot))
$resolvedCache = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $WheelCache))
$stagingRoot = "$resolvedOutput.staging-$PID"

if (Test-Path -LiteralPath $resolvedOutput) {
    throw "OutputRoot already exists: $resolvedOutput"
}
if (Test-Path -LiteralPath $stagingRoot) {
    throw "Staging path already exists: $stagingRoot"
}
if (-not (Test-Path -LiteralPath $HostPython -PathType Leaf)) {
    throw "Host Python not found: $HostPython"
}

$outputParent = Split-Path -Parent $resolvedOutput
$stagingParent = Split-Path -Parent $stagingRoot
if ($outputParent -ne $stagingParent) {
    throw 'Staging directory must be beside OutputRoot.'
}

New-Item -ItemType Directory -Path $resolvedCache -Force | Out-Null
New-Item -ItemType Directory -Path $stagingRoot | Out-Null

try {
    $lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $runtimeLock | ConvertFrom-Json
    if ($lock.python.version -ne '3.11.9') {
        throw "Unsupported Python version in runtime lock: $($lock.python.version)"
    }

    $embedZip = Join-Path $resolvedCache 'python-3.11.9-embed-amd64.zip'
    if (-not (Test-Path -LiteralPath $embedZip -PathType Leaf)) {
        Invoke-WebRequest -UseBasicParsing -Uri $lock.python.url -OutFile $embedZip
    }
    $embedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $embedZip).Hash.ToLowerInvariant()
    if ($embedHash -ne $lock.python.sha256) {
        throw "Embedded Python SHA-256 mismatch: $embedHash"
    }

    $pythonRoot = Join-Path $stagingRoot 'python'
    New-Item -ItemType Directory -Path $pythonRoot | Out-Null
    Expand-Archive -LiteralPath $embedZip -DestinationPath $pythonRoot
    $pathFile = Join-Path $pythonRoot 'python311._pth'
    @(
        'python311.zip'
        '.'
        'Lib\site-packages'
        'import site'
    ) | Set-Content -Encoding ASCII -LiteralPath $pathFile

    & $HostPython -m pip download `
        --requirement $requirementsLock `
        --dest $resolvedCache `
        --only-binary=:all: `
        --extra-index-url 'https://download.pytorch.org/whl/cu130'
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency download failed with exit code $LASTEXITCODE"
    }

    & $HostPython -m pip wheel `
        --no-deps `
        --wheel-dir $resolvedCache `
        $repoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Project wheel build failed with exit code $LASTEXITCODE"
    }

    $sitePackages = Join-Path $pythonRoot 'Lib\site-packages'
    New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
    & $HostPython -m pip install `
        --no-index `
        --find-links $resolvedCache `
        --no-deps `
        --target $sitePackages `
        --requirement $requirementsLock
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE"
    }

    $projectWheel = Get-ChildItem -LiteralPath $resolvedCache `
        -Filter 'bixolon_bakery_scanner-0.1.0-py3-none-any.whl' |
        Select-Object -First 1
    if ($null -eq $projectWheel) {
        throw 'Built bixolon_bakery_scanner wheel was not found.'
    }
    & $HostPython -m pip install `
        --no-index `
        --no-deps `
        --target $sitePackages `
        $projectWheel.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Project wheel installation failed with exit code $LASTEXITCODE"
    }

    $env:PYTHONPATH = $repoRoot
    & $HostPython $validator `
        --runtime-root $stagingRoot `
        --runtime-lock $runtimeLock `
        --execute-cpu-check `
        --write-manifest
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime verification failed with exit code $LASTEXITCODE"
    }

    Move-Item -LiteralPath $stagingRoot -Destination $resolvedOutput
    Write-Host "Prepared camera runtime: $resolvedOutput"
}
catch {
    if (Test-Path -LiteralPath $stagingRoot) {
        $resolvedStaging = [System.IO.Path]::GetFullPath($stagingRoot)
        if ($resolvedStaging -ne $stagingRoot -or
            (Split-Path -Parent $resolvedStaging) -ne $outputParent) {
            throw "Refusing to clean unexpected staging path: $resolvedStaging"
        }
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
    throw
}
