[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$repoRoot = Split-Path -Parent $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $output) {
    throw "refusing to overwrite existing ZIP: $output"
}

$outputParent = Split-Path -Parent $output
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw "output parent directory does not exist: $outputParent"
}

$manifestPath = Join-Path $repoRoot 'portable_cpu_smoke\manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$staging = Join-Path $outputParent ('.cpu-smoke-staging-' + [guid]::NewGuid().ToString('N'))

function Copy-PackagePath([string]$relativePath) {
    if ([IO.Path]::IsPathRooted($relativePath) -or $relativePath.Contains('..')) {
        throw "manifest path must be package-relative: $relativePath"
    }
    $source = [IO.Path]::GetFullPath((Join-Path $repoRoot $relativePath))
    $rootPrefix = $repoRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $source.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "manifest path escapes package root: $relativePath"
    }
    if (-not (Test-Path -LiteralPath $source)) {
        throw "manifest source path is missing: $relativePath"
    }
    $destination = Join-Path $staging $relativePath
    if ((Get-Item -LiteralPath $source) -is [IO.DirectoryInfo]) {
        Get-ChildItem -LiteralPath $source -File -Recurse | Where-Object {
            $_.FullName -notmatch '[\\/]__pycache__[\\/]'
        } | ForEach-Object {
            $childRelative = $_.FullName.Substring($source.Length).TrimStart('\', '/')
            $childDestination = Join-Path $destination $childRelative
            New-Item -ItemType Directory -Path (Split-Path -Parent $childDestination) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $childDestination -Force
        }
    }
    else {
        $destinationParent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
    if (-not (Test-Path -LiteralPath $destination)) {
        throw "staged path is missing after copy: $relativePath"
    }
}

try {
    New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null
    foreach ($relativePath in @($manifest.required_paths) + @($manifest.sample_paths)) {
        Copy-PackagePath ([string]$relativePath)
    }

    $fileHashes = [ordered]@{}
    Get-ChildItem -LiteralPath $staging -File -Recurse | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($staging.Length).TrimStart('\', '/') -replace '\\', '/'
        $stagedPath = $_.FullName
        $fileHashes[$relative] = (Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $stageManifest = [ordered]@{
        schema_version = 1
        scope = $manifest.scope
        required_paths = @($manifest.required_paths)
        sample_paths = @($manifest.sample_paths)
        file_sha256 = $fileHashes
    }
    $stageManifest.file_sha256 | Out-Null
    $stageManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $staging 'package-manifest.json') -Encoding utf8

    Compress-Archive -LiteralPath (Get-ChildItem -LiteralPath $staging -Force | Select-Object -ExpandProperty FullName) -DestinationPath $output -ErrorAction Stop
    $archiveHash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output "ZIP SHA-256: $archiveHash"
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
