[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$pipTemp = Join-Path $root '.pip-tmp'
$pipCache = Join-Path $root '.pip-cache'
New-Item -ItemType Directory -Path $pipTemp, $pipCache -Force | Out-Null
$env:TEMP = $pipTemp
$env:TMP = $pipTemp
$env:PIP_CACHE_DIR = $pipCache

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python launcher "py" is required. Install Python 3.11, then rerun this script.'
}

& py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.11 is required. Install it and make it available as "py -3.11".'
}

$venv = Join-Path $root '.venv'
if (-not (Test-Path -LiteralPath $venv)) {
    & py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "virtual environment creation failed with exit code $LASTEXITCODE"
    }
}

$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "virtual environment creation failed: $python is missing"
}

function Invoke-Checked([string]$description, [string[]]$arguments) {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$description failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked 'pip upgrade' @('-m', 'pip', 'install', '--no-cache-dir', '--upgrade', 'pip')
Invoke-Checked 'CPU PyTorch installation' @('-m', 'pip', 'install', '--no-cache-dir', '--index-url', 'https://download.pytorch.org/whl/cpu', 'torch==2.13.0+cpu', 'torchvision==0.28.0+cpu')

$requirements = Join-Path $PSScriptRoot 'requirements-cpu.txt'
$otherRequirements = Get-Content -LiteralPath $requirements | Where-Object {
    $_ -and -not $_.StartsWith('torch==') -and -not $_.StartsWith('torchvision==')
}
Invoke-Checked 'remaining CPU dependency installation' (@('-m', 'pip', 'install', '--no-cache-dir') + $otherRequirements)
Invoke-Checked 'local project installation' @('-m', 'pip', 'install', '--no-cache-dir', '--no-deps', $root)

Write-Host "CPU smoke runtime installed under $root"
