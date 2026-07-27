$ErrorActionPreference = "Stop"
$env:CUDA_VISIBLE_DEVICES = "0"

$DFinePython = ".venvs/dfine/Scripts/python.exe"
$HostPython = "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe"
$ArtifactRoot = "artifacts/box_system/detectors"
$FoldRoot = "artifacts/box_system/folds"
$StagedRoot = "artifacts/box_system/staged"
$StagedAnnotations = Join-Path $StagedRoot "annotations.json"
$GeneratedConfigRoot = "configs/generated/detector-matrix"
$Template = "configs/upstream/dfine_bread.yml"
$Variant = "dfine_n_640"
$Seed = 20260724
$TrainBatchSize = 16
$ValidationBatchSize = 16
$BaseLearningRate = 0.0001
$BackboneLearningRate = 0.00005

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Description (exit $LASTEXITCODE)" }
}

function Write-Utf8NoBom([string]$Path, [string]$Value) {
    [IO.File]::WriteAllText($Path, $Value, (New-Object System.Text.UTF8Encoding($false)))
}

function Convert-ToPosixRelativePath([string]$FromDirectory, [string]$TargetPath) {
    $From = (Resolve-Path -LiteralPath $FromDirectory).Path.TrimEnd("\") + "\"
    $Target = (Resolve-Path -LiteralPath $TargetPath).Path
    $RelativeUri = ([Uri]$From).MakeRelativeUri([Uri]$Target)
    return [Uri]::UnescapeDataString($RelativeUri.ToString())
}

function Convert-ToPosixRepositoryPath([string]$TargetPath) {
    $Repository = (Get-Location).Path.TrimEnd("\") + "\"
    $Target = (Resolve-Path -LiteralPath $TargetPath).Path
    $RelativeUri = ([Uri]$Repository).MakeRelativeUri([Uri]$Target)
    return [Uri]::UnescapeDataString($RelativeUri.ToString())
}

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing required artifact: $Path" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ProcessedValidationIds([string]$ManifestPath, [string]$ProcessedPath) {
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $Processed = Get-Content -LiteralPath $ProcessedPath -Raw | ConvertFrom-Json
    $ExpectedIds = @($Manifest.validation_image_ids | ForEach-Object { [int]$_ } | Sort-Object)
    $ProcessedIds = @($Processed | ForEach-Object { [int]$_ } | Sort-Object)
    if ($ExpectedIds.Count -eq 0 -or $ProcessedIds.Count -ne $ExpectedIds.Count -or @($ProcessedIds | Select-Object -Unique).Count -ne $ProcessedIds.Count -or @(Compare-Object -ReferenceObject $ExpectedIds -DifferenceObject $ProcessedIds).Count -ne 0) {
        throw "Processed validation IDs must exactly match the held-out fold IDs"
    }
}

function Test-CompletedFold([int]$Fold) {
    $RunId = "$Variant-seed$Seed-fold$Fold"
    $RunRoot = Join-Path $ArtifactRoot $RunId
    if (-not (Test-Path -LiteralPath $RunRoot -PathType Container)) { return $false }

    $ReceiptPath = Join-Path $RunRoot "receipt.json"
    $RunConfig = Join-Path $GeneratedConfigRoot "$RunId.yml"
    $ManifestPath = Join-Path (Join-Path $FoldRoot "fold-$Fold") "manifest.json"
    $RawPredictionPath = Join-Path $RunRoot "validation_predictions.raw.json"
    $PredictionPath = Join-Path $RunRoot "validation_predictions.json"
    $ProcessedPath = Join-Path $RunRoot "processed_validation_image_ids.json"
    if (-not (Test-Path -LiteralPath $ReceiptPath -PathType Leaf)) { throw "Existing run directory is not resumable without a receipt: $RunRoot" }
    if (-not (Test-Path -LiteralPath $RawPredictionPath -PathType Leaf)) { throw "Completed run must retain its raw D-FINE prediction export: $RawPredictionPath" }
    $Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
    if ($Receipt.run_id -ne $RunId -or $Receipt.variant -ne $Variant -or [int]$Receipt.seed -ne $Seed -or [int]$Receipt.fold -ne $Fold -or $Receipt.status -ne "completed") {
        throw "Receipt identity or completion status does not match $RunId"
    }
    $ExpectedHashes = [ordered]@{
        fold_manifest_sha256 = Get-Sha256 $ManifestPath
        config_sha256 = Get-Sha256 $RunConfig
        prediction_sha256 = Get-Sha256 $PredictionPath
        processed_images_sha256 = Get-Sha256 $ProcessedPath
    }
    foreach ($Name in $ExpectedHashes.Keys) {
        if ($Receipt.$Name -ne $ExpectedHashes[$Name]) { throw "Receipt hash mismatch for $RunId ($Name)" }
    }
    Assert-ProcessedValidationIds $ManifestPath $ProcessedPath
    return $true
}

function Write-FoldAnnotations([string]$ManifestPath, [string]$TrainPath, [string]$ValidationPath) {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Missing grouped fold manifest: $ManifestPath" }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $Coco = Get-Content -LiteralPath $StagedAnnotations -Raw | ConvertFrom-Json
    $ValidationIds = @($Manifest.validation_image_ids | ForEach-Object { [int]$_ })
    $ValidationSet = @{}
    $ValidationIds | ForEach-Object { $ValidationSet[$_] = $true }
    $TrainImages = @($Coco.images | Where-Object { -not $ValidationSet[[int]$_.id] })
    $ValidationImages = @($Coco.images | Where-Object { $ValidationSet[[int]$_.id] })
    if ($TrainImages.Count -eq 0 -or $ValidationImages.Count -eq 0) { throw "Fold must train on four groups and validate one group" }
    $TrainIds = @{}
    $TrainImages | ForEach-Object { $TrainIds[[int]$_.id] = $true }
    $Train = [ordered]@{ images = $TrainImages; annotations = @($Coco.annotations | Where-Object { $TrainIds[[int]$_.image_id] }); categories = $Coco.categories }
    $Validation = [ordered]@{ images = $ValidationImages; annotations = @($Coco.annotations | Where-Object { $ValidationSet[[int]$_.image_id] }); categories = $Coco.categories }
    Write-Utf8NoBom -Path $TrainPath -Value ($Train | ConvertTo-Json -Depth 8 -Compress)
    Write-Utf8NoBom -Path $ValidationPath -Value ($Validation | ConvertTo-Json -Depth 8 -Compress)
}

if (-not (Test-Path -LiteralPath $StagedAnnotations -PathType Leaf)) { throw "Stage the existing COCO images before detector training: $StagedAnnotations" }
if (-not (Test-Path -LiteralPath $DFinePython -PathType Leaf)) { throw "Missing pinned D-FINE Python: $DFinePython" }
if (-not (Test-Path -LiteralPath $HostPython -PathType Leaf)) { throw "Missing host Python for canonicalization: $HostPython" }
$GpuVerified = $false

foreach ($Fold in 0..4) {
    if (Test-CompletedFold $Fold) {
        Write-Host "Reusing validated completed $Variant fold $Fold"
        continue
    }

    $RunId = "$Variant-seed$Seed-fold$Fold"
    $RunRoot = Join-Path $ArtifactRoot $RunId
    if (Test-Path -LiteralPath $RunRoot) { throw "Refusing to overwrite incomplete run-owned artifacts: $RunRoot" }
    if (-not $GpuVerified) {
        Invoke-Checked { & $DFinePython -c "import torch; assert torch.cuda.is_available() and 'RTX 5080' in torch.cuda.get_device_name(0)" } "require RTX 5080 CUDA for D-FINE"
        $GpuVerified = $true
    }
    $ManifestPath = Join-Path (Join-Path $FoldRoot "fold-$Fold") "manifest.json"
    $FoldDataRoot = Join-Path $RunRoot "fold-data"
    $TrainAnnotations = Join-Path $FoldDataRoot "train.json"
    $ValidationAnnotations = Join-Path $FoldDataRoot "validation.json"
    New-Item -ItemType Directory -Force -Path $FoldDataRoot | Out-Null
    Write-FoldAnnotations $ManifestPath $TrainAnnotations $ValidationAnnotations

    New-Item -ItemType Directory -Force -Path $GeneratedConfigRoot | Out-Null
    $RunConfig = Join-Path $GeneratedConfigRoot "$RunId.yml"
    $TrainConfigPath = Convert-ToPosixRepositoryPath $TrainAnnotations
    $ValidationConfigPath = Convert-ToPosixRepositoryPath $ValidationAnnotations
    $ImagesConfigPath = Convert-ToPosixRepositoryPath (Join-Path $StagedRoot "images")
    $BaseConfigPath = Convert-ToPosixRelativePath $GeneratedConfigRoot "third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml"
    $ConfigText = (Get-Content -LiteralPath $Template -Raw).
        Replace("__INJECTED_TRAIN_ANNOTATIONS__", $TrainConfigPath).
        Replace("__INJECTED_VALIDATION_ANNOTATIONS__", $ValidationConfigPath).
        Replace("__INJECTED_IMAGES_DIR__", $ImagesConfigPath).
        Replace("__INJECTED_DFINE_BASE__", $BaseConfigPath).
        Replace("__INJECTED_INPUT_SIZE__", "640").
        Replace("__INJECTED_SEED__", [string]$Seed).
        Replace("__INJECTED_DFINE_TRAIN_BATCH__", [string]$TrainBatchSize).
        Replace("__INJECTED_DFINE_VAL_BATCH__", [string]$ValidationBatchSize).
        Replace("__INJECTED_DFINE_BASE_LR__", "0.0001").
        Replace("__INJECTED_DFINE_BACKBONE_LR__", "0.00005")
    Write-Utf8NoBom -Path $RunConfig -Value $ConfigText

    $RawPredictionPath = Join-Path $RunRoot "validation_predictions.raw.json"
    $PredictionPath = Join-Path $RunRoot "validation_predictions.json"
    $ProcessedPath = Join-Path $RunRoot "processed_validation_image_ids.json"
    Invoke-Checked { & $DFinePython third_party/D-FINE/train.py -c $RunConfig -d cuda:0 --seed=$Seed --output-dir $RunRoot } "train $RunId"
    $env:DFINE_OOF_PREDICTIONS = $RawPredictionPath
    try {
        $Checkpoint = Join-Path $RunRoot "best_stg2.pth"
        if (-not (Test-Path -LiteralPath $Checkpoint -PathType Leaf)) { $Checkpoint = Join-Path $RunRoot "best_stg1.pth" }
        if (-not (Test-Path -LiteralPath $Checkpoint -PathType Leaf)) { throw "D-FINE did not produce best_stg2.pth or best_stg1.pth for $RunId" }
        Invoke-Checked { & $DFinePython third_party/D-FINE/train.py -c $RunConfig -d cuda:0 --test-only -r $Checkpoint --output-dir $RunRoot } "test $RunId"
    } finally {
        Remove-Item Env:DFINE_OOF_PREDICTIONS -ErrorAction SilentlyContinue
    }
    Invoke-Checked { & $HostPython scripts/canonicalize_validation_predictions.py --backend dfine --source $Variant --input $RawPredictionPath --input-format dfine-coco-json --annotations $ValidationAnnotations --output $PredictionPath --processed-output $ProcessedPath } "canonicalize $RunId"
    Assert-ProcessedValidationIds $ManifestPath $ProcessedPath
    $Receipt = [ordered]@{
        run_id = $RunId
        variant = $Variant
        seed = $Seed
        fold = $Fold
        fold_manifest_sha256 = Get-Sha256 $ManifestPath
        config_sha256 = Get-Sha256 $RunConfig
        prediction_sha256 = Get-Sha256 $PredictionPath
        processed_images_sha256 = Get-Sha256 $ProcessedPath
        status = "completed"
    }
    Write-Utf8NoBom -Path (Join-Path $RunRoot "receipt.json") -Value ($Receipt | ConvertTo-Json -Compress)
}
