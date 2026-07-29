[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $PSCommandPath
$manifest = Get-Content -Raw -Encoding UTF8 (Join-Path $packageRoot "package-manifest.json") | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    if ($entry.path -like "*.pyc") {
        continue
    }
    $path = Join-Path $packageRoot $entry.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing packaged file: $($entry.path)"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($actual -ne $entry.sha256) {
        throw "SHA-256 mismatch: $($entry.path)"
    }
}
& (Join-Path $packageRoot "runtime\\python\\python.exe") -c "import torch; from rfdetr import RFDETRLarge; assert torch.version.cuda is None; assert not torch.cuda.is_available(); print('offline CPU runtime import check: OK')"
Write-Output "Package verification succeeded: $($manifest.files.Count) files"
