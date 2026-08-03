[CmdletBinding()]
param(
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'

$release = '1.3.9'
$sourceUrl = 'https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip'
$scriptRoot = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent $scriptRoot
$fontRoot = Join-Path $projectRoot 'assets/fonts'
$temporaryRoot = [System.IO.Path]::GetTempPath()
$temporaryDirectory = Join-Path $temporaryRoot ("pretendard-$release-" + [guid]::NewGuid().ToString('N'))
$temporaryFullPath = [System.IO.Path]::GetFullPath($temporaryDirectory)
$temporaryRootFullPath = [System.IO.Path]::GetFullPath($temporaryRoot)

if (-not $temporaryFullPath.StartsWith($temporaryRootFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use temporary directory outside the system temporary root: $temporaryFullPath"
}

$outputNames = @(
    'OFL.txt',
    'Pretendard-Bold.otf',
    'Pretendard-Medium.otf',
    'Pretendard-Regular.otf',
    'Pretendard-SemiBold.otf'
)

try {
    New-Item -ItemType Directory -Path $temporaryFullPath | Out-Null
    $archivePath = Join-Path $temporaryFullPath 'Pretendard-1.3.9.zip'
    $extractPath = Join-Path $temporaryFullPath 'extract'
    Invoke-WebRequest -Uri $sourceUrl -OutFile $archivePath
    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath

    $stagedFiles = @{}
    foreach ($name in $outputNames) {
        if ($name -eq 'OFL.txt') {
            $source = Get-ChildItem -LiteralPath $extractPath -Recurse -File -Filter 'LICENSE*' | Select-Object -First 1
        }
        else {
            $source = Get-ChildItem -LiteralPath $extractPath -Recurse -File -Filter $name | Select-Object -First 1
        }
        if ($null -eq $source) {
            throw "Release $release does not contain $name"
        }

        $stagedPath = Join-Path $temporaryFullPath $name
        Copy-Item -LiteralPath $source.FullName -Destination $stagedPath
        $stagedFiles[$name] = $stagedPath
    }

    $manifestFiles = @(
        foreach ($name in $outputNames) {
            $stagedPath = $stagedFiles[$name]
            [ordered]@{
                bytes = (Get-Item -LiteralPath $stagedPath).Length
                path = $name
                sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $stagedPath).Hash.ToLowerInvariant()
            }
        }
    )
    $manifest = [ordered]@{
        release = $release
        source_url = $sourceUrl
        license = 'SIL Open Font License 1.1'
        files = $manifestFiles
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 4
    $manifestPath = Join-Path $fontRoot 'pretendard_manifest.json'

    foreach ($name in $outputNames) {
        $destinationPath = Join-Path $fontRoot $name
        if (Test-Path -LiteralPath $destinationPath) {
            $existingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash.ToLowerInvariant()
            $expectedHash = ($manifestFiles | Where-Object { $_.path -eq $name }).sha256
            if ($existingHash -ne $expectedHash -and -not $Replace) {
                throw "Refusing to overwrite non-matching existing asset: $destinationPath. Re-run with -Replace to replace it."
            }
        }
    }
    if (Test-Path -LiteralPath $manifestPath) {
        $existingManifest = Get-Content -Raw -LiteralPath $manifestPath
        if ($existingManifest -ne $manifestJson -and -not $Replace) {
            throw "Refusing to overwrite non-matching existing manifest: $manifestPath. Re-run with -Replace to replace it."
        }
    }

    New-Item -ItemType Directory -Force -Path $fontRoot | Out-Null
    foreach ($name in $outputNames) {
        Copy-Item -LiteralPath $stagedFiles[$name] -Destination (Join-Path $fontRoot $name) -Force
    }
    [System.IO.File]::WriteAllText($manifestPath, $manifestJson, [System.Text.UTF8Encoding]::new($false))
}
finally {
    if ((Test-Path -LiteralPath $temporaryFullPath) -and
        $temporaryFullPath.StartsWith($temporaryRootFullPath, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $temporaryFullPath).StartsWith("pretendard-$release-", [System.StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $temporaryFullPath -Recurse -Force
    }
}
