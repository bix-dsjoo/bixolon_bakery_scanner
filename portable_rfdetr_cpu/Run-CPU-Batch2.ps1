[CmdletBinding()]
param(
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$packageRoot = Split-Path -Parent $PSCommandPath
if (-not $Output) {
    $Output = Join-Path $packageRoot ("results\\batch2-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}

& (Join-Path $packageRoot "runtime\\python\\python.exe") `
    (Join-Path $packageRoot "scripts\\run_cpu_rfdetr_fusion.py") `
    --package-root $packageRoot `
    --output $Output
