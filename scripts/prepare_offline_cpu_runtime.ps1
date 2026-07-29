[CmdletBinding()]
param(
    [string]$OutputRoot = "artifacts\\offline_cpu_runtime_py311",
    [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $repoRoot $OutputRoot
if (Test-Path -LiteralPath $output) {
    throw "Refusing to overwrite existing runtime: $output"
}

$staging = "$output.staging-$([guid]::NewGuid().ToString('N'))"
$download = Join-Path ([System.IO.Path]::GetTempPath()) "python-$PythonVersion-embed-amd64.zip"
try {
    New-Item -ItemType Directory -Path (Join-Path $staging "python") -Force | Out-Null
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile $download
    Expand-Archive -LiteralPath $download -DestinationPath (Join-Path $staging "python")
    New-Item -ItemType Directory -Path (Join-Path $staging "site-packages") -Force | Out-Null

    $requirements = @(
        "torch==2.8.0",
        "torchvision==0.23.0",
        "rfdetr==1.8.3",
        "timm==1.0.28",
        "numpy>=2.4,<2.5",
        "Pillow==12.2.0",
        "opencv-python>=5.0,<5.1",
        "scipy>=1.17,<1.18",
        "scikit-learn>=1.9,<2",
        "PyYAML>=6.0,<7",
        "pydantic>=2.13,<3"
    )
    python -m pip install --upgrade --target (Join-Path $staging "site-packages") --index-url "https://download.pytorch.org/whl/cpu" "torch==2.8.0" "torchvision==0.23.0"
    python -m pip install --upgrade --target (Join-Path $staging "site-packages") $requirements

    $dinov3Init = (python -c "import dinov3; print(dinov3.__file__)" | Select-Object -Last 1).Trim()
    if (-not $dinov3Init) {
        throw "The build host must provide the vendored dinov3 package"
    }
    Copy-Item -LiteralPath (Split-Path -Parent $dinov3Init) -Destination (Join-Path $staging "site-packages\\dinov3") -Recurse -Force

    $pth = Get-ChildItem -Path (Join-Path $staging "python") -Filter "python*._pth" | Select-Object -First 1
    @("python311.zip", ".", "../site-packages", "../../src", "import site") | Set-Content -LiteralPath $pth.FullName -Encoding ASCII
    Move-Item -LiteralPath $staging -Destination $output
}
finally {
    Remove-Item -LiteralPath $download -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
