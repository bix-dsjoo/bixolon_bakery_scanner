[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'CPU runtime is not installed. Run portable_cpu_smoke\install_cpu_smoke.ps1 first.'
}

$results = Join-Path $root 'results'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$output = Join-Path $results $stamp
while (Test-Path -LiteralPath $output) {
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
    $output = Join-Path $results $stamp
}
New-Item -ItemType Directory -Path $results -Force | Out-Null

& $python (Join-Path $root 'scripts\run_e2e_smoke.py') --package-root $root --profile batch2_e3_m3_h3 --output $output --device cpu
if ($LASTEXITCODE -ne 0) {
    throw "CPU smoke runner failed with exit code $LASTEXITCODE"
}

$reportPath = Join-Path $output 'report.json'
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
Write-Host "E average: $($report.E) ms"
Write-Host "M average: $($report.M) ms"
Write-Host "H average: $($report.H) ms"
