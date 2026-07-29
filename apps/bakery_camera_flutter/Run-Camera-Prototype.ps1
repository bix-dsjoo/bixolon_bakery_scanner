param(
    [Parameter(Mandatory = $true)]
    [string]$Python
)

$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $appRoot '..\..')).Path
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$exePath = Join-Path $appRoot 'build\windows\x64\runner\Release\bakery_camera_prototype.exe'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python 실행 파일을 찾을 수 없습니다: $pythonPath"
}
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Release EXE를 찾을 수 없습니다. 먼저 flutter build windows --release를 실행하세요: $exePath"
}

$env:BAKERY_INFERENCE_PYTHON = $pythonPath
$env:BAKERY_REPO_ROOT = $repoRoot
& $exePath
exit $LASTEXITCODE
