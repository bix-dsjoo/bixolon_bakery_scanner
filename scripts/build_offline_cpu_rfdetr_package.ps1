[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [string]$RuntimeRoot = "artifacts\\offline_cpu_runtime_py311"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $repoRoot $RuntimeRoot
$output = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
if (Test-Path -LiteralPath $output) {
    throw "Refusing to overwrite existing package: $output"
}
if (-not (Test-Path -LiteralPath (Join-Path $runtime "python\\python.exe") -PathType Leaf)) {
    throw "Prepared embedded Python runtime is missing: $runtime"
}
if (-not (Test-Path -LiteralPath (Join-Path $runtime "site-packages") -PathType Container)) {
    throw "Prepared CPU site-packages are missing: $runtime"
}

$outputParent = Split-Path -Parent $output
New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
$staging = Join-Path $outputParent (".rfdetr-cpu-package-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    $copyPaths = @(
        "src",
        "scripts\\run_cpu_rfdetr_fusion.py",
        "models\\rfdetr_large_bakery_v1",
        "models\\repvit_m1_15plus5_v1",
        "models\\dinov3_vits16_15plus5_v1",
        "artifacts\\e2e_current_source\\classification",
        "configs\\cpu_rfdetr_classifier_policy.yaml",
        "samples\\batch2_e3_m3_h3",
        "portable_rfdetr_cpu\\manifest.json"
    )
    foreach ($relative in $copyPaths) {
        $source = Join-Path $repoRoot $relative
        $destination = Join-Path $staging $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    }
    Copy-Item -LiteralPath $runtime -Destination (Join-Path $staging "runtime") -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "portable_rfdetr_cpu\\README.md") -Destination (Join-Path $staging "README.md")
    Copy-Item -LiteralPath (Join-Path $repoRoot "portable_rfdetr_cpu\\Run-CPU-Batch2.ps1") -Destination (Join-Path $staging "Run-CPU-Batch2.ps1")
    Copy-Item -LiteralPath (Join-Path $repoRoot "portable_rfdetr_cpu\\Verify-Package.ps1") -Destination (Join-Path $staging "Verify-Package.ps1")

    Get-ChildItem -LiteralPath $staging -File -Recurse -Filter "*.pyc" | Remove-Item -Force

    $files = @(Get-ChildItem -LiteralPath $staging -File -Recurse | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($staging.Length).TrimStart("\\").Replace("\\", "/")
            bytes = $_.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        }
    })
    [ordered]@{
        schema_version = 1
        scope = "offline_rfdetr_fusion_cpu_v1"
        files = $files
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $staging "package-manifest.json") -Encoding UTF8
    Compress-Archive -Path (Get-ChildItem -LiteralPath $staging | ForEach-Object FullName) -DestinationPath $output -CompressionLevel Optimal
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
