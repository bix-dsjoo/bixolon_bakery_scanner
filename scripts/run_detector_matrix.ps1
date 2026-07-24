param([string]$Config = "configs/box_system.yaml")
$ErrorActionPreference = "Stop"
$env:CUDA_VISIBLE_DEVICES = "0"
function Invoke-Checked([scriptblock]$Command, [string]$Description) { & $Command; if ($LASTEXITCODE -ne 0) { throw "Failed: $Description (exit $LASTEXITCODE)" } }
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
Invoke-Checked { & .venvs/dfine/Scripts/python.exe -c "import torch; assert torch.cuda.is_available() and 'RTX 5080' in torch.cuda.get_device_name(0)" } "require RTX 5080 CUDA for D-FINE"
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -c "import torch; assert torch.cuda.is_available() and 'RTX 5080' in torch.cuda.get_device_name(0)" } "require RTX 5080 CUDA for RTMDet"

# Uses only the already staged 299-image dataset and its grouped five-fold
# manifests. Each run trains on the other four folds and tests exactly one.
$Variants = @(
    @{ Name = "dfine_n_640"; Backend = "dfine"; Size = 640; Template = "configs/upstream/dfine_bread.yml" },
    @{ Name = "dfine_n_768"; Backend = "dfine"; Size = 768; Template = "configs/upstream/dfine_bread.yml" },
    @{ Name = "rtmdet_tiny_640"; Backend = "rtmdet"; Size = 640; Template = "configs/upstream/rtmdet_tiny_bread.py" },
    @{ Name = "rtmdet_tiny_768"; Backend = "rtmdet"; Size = 768; Template = "configs/upstream/rtmdet_tiny_bread.py" }
)
$Seeds = @(20260724, 20260725, 20260726)
$ArtifactRoot = "artifacts/box_system/detectors"
$StagedRoot = "artifacts/box_system/staged"
$StagedAnnotations = Join-Path $StagedRoot "annotations.json"
$GeneratedConfigRoot = "configs/generated/detector-matrix"
if (-not (Test-Path $StagedAnnotations)) { throw "Stage the existing COCO images before detector training: $StagedAnnotations" }

function Write-FoldAnnotations([string]$ManifestPath, [string]$TrainPath, [string]$ValidationPath) {
    if (-not (Test-Path $ManifestPath)) { throw "Missing grouped fold manifest: $ManifestPath" }
    $manifest = Get-Content -Raw $ManifestPath | ConvertFrom-Json
    $coco = Get-Content -Raw $StagedAnnotations | ConvertFrom-Json
    $validationIds = @($manifest.validation_image_ids | ForEach-Object { [int]$_ })
    $validationSet = @{}; $validationIds | ForEach-Object { $validationSet[$_] = $true }
    $trainImages = @($coco.images | Where-Object { -not $validationSet[[int]$_.id] })
    $validationImages = @($coco.images | Where-Object { $validationSet[[int]$_.id] })
    if ($trainImages.Count -eq 0 -or $validationImages.Count -eq 0) { throw "Fold must train on four groups and validate one group" }
    $trainIds = @{}; $trainImages | ForEach-Object { $trainIds[[int]$_.id] = $true }
    $train = [ordered]@{ images = $trainImages; annotations = @($coco.annotations | Where-Object { $trainIds[[int]$_.image_id] }); categories = $coco.categories }
    $validation = [ordered]@{ images = $validationImages; annotations = @($coco.annotations | Where-Object { $validationSet[[int]$_.image_id] }); categories = $coco.categories }
    Write-Utf8NoBom -Path $TrainPath -Value ($train | ConvertTo-Json -Depth 8 -Compress)
    Write-Utf8NoBom -Path $ValidationPath -Value ($validation | ConvertTo-Json -Depth 8 -Compress)
}

foreach ($Variant in $Variants) { foreach ($Seed in $Seeds) { foreach ($Fold in 0..4) {
    $RunId = "$($Variant.Name)-seed$Seed-fold$Fold"; $RunRoot = Join-Path $ArtifactRoot $RunId
    if ((Test-Path $RunRoot) -and (Get-ChildItem -Force $RunRoot | Select-Object -First 1)) { throw "Refusing stale run-owned artifacts: $RunRoot" }
    $FoldRoot = Join-Path $RunRoot "fold-data"; New-Item -ItemType Directory -Force -Path $FoldRoot | Out-Null
    $ManifestPath = "artifacts/box_system/folds/fold-$Fold/manifest.json"
    $TrainAnnotations = Join-Path $FoldRoot "train.json"; $ValidationAnnotations = Join-Path $FoldRoot "validation.json"
    Write-FoldAnnotations $ManifestPath $TrainAnnotations $ValidationAnnotations
    $RunConfig = Join-Path $GeneratedConfigRoot "$RunId.$([IO.Path]::GetExtension($Variant.Template).TrimStart('.'))"; New-Item -ItemType Directory -Force -Path (Split-Path $RunConfig) | Out-Null
    $ConfigText = Get-Content -Raw $Variant.Template
    if ($Variant.Backend -eq "dfine") {
        $TrainConfigPath = Convert-ToPosixRepositoryPath $TrainAnnotations
        $ValidationConfigPath = Convert-ToPosixRepositoryPath $ValidationAnnotations
        $ImagesConfigPath = Convert-ToPosixRepositoryPath (Join-Path $StagedRoot "images")
        $DFineBaseConfigPath = Convert-ToPosixRelativePath $GeneratedConfigRoot "third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml"
        $ConfigText = $ConfigText.Replace("__INJECTED_TRAIN_ANNOTATIONS__", $TrainConfigPath).Replace("__INJECTED_VALIDATION_ANNOTATIONS__", $ValidationConfigPath).Replace("__INJECTED_IMAGES_DIR__", $ImagesConfigPath).Replace("__INJECTED_DFINE_BASE__", $DFineBaseConfigPath)
    } else {
        $ConfigText = $ConfigText.Replace("__INJECTED_TRAIN_ANNOTATIONS__", (Resolve-Path $TrainAnnotations)).Replace("__INJECTED_VALIDATION_ANNOTATIONS__", (Resolve-Path $ValidationAnnotations)).Replace("__INJECTED_DATA_ROOT__", (Resolve-Path $StagedRoot)).Replace("__INJECTED_IMAGES_DIR__", (Resolve-Path (Join-Path $StagedRoot "images"))).Replace("__INJECTED_MMD_BASE__", (Resolve-Path "third_party/mmdetection/configs/rtmdet/rtmdet_tiny_8xb32-300e_coco.py"))
    }
    $ConfigText = $ConfigText.Replace("__INJECTED_INPUT_SIZE__", [string]$Variant.Size).Replace("__INJECTED_SEED__", [string]$Seed)
    Write-Utf8NoBom -Path $RunConfig -Value $ConfigText
    $RawPredictionPath = Join-Path $RunRoot "validation_predictions.raw.json"; $PredictionPath = Join-Path $RunRoot "validation_predictions.json"
    if ($Variant.Backend -eq "dfine") {
        Invoke-Checked { & .venvs/dfine/Scripts/python.exe third_party/D-FINE/train.py -c $RunConfig -d cuda:0 --seed=$Seed --output-dir $RunRoot } "train $RunId"
        # Official evaluation CLI plus the audited, pinned-source export patch.
        $env:DFINE_OOF_PREDICTIONS = $RawPredictionPath
        try {
            $Checkpoint = Join-Path $RunRoot "best_stg2.pth"; if (-not (Test-Path $Checkpoint)) { $Checkpoint = Join-Path $RunRoot "best_stg1.pth" }
            if (-not (Test-Path $Checkpoint)) { throw "D-FINE did not produce best_stg2.pth or best_stg1.pth for $RunId" }
            Invoke-Checked { & .venvs/dfine/Scripts/python.exe third_party/D-FINE/train.py -c $RunConfig -d cuda:0 --test-only -r $Checkpoint --output-dir $RunRoot } "test $RunId"
        } finally { Remove-Item Env:DFINE_OOF_PREDICTIONS -ErrorAction SilentlyContinue }
    } else {
        Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe scripts/require_rtx5080.py } "require RTX 5080 before RTMDet train $RunId"
        Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe third_party/mmdetection/tools/train.py $RunConfig --work-dir $RunRoot --cfg-options randomness.seed=$Seed } "train $RunId"
        # MMDetection 3.x tools/test.py writes --out as pickle, not JSON.
        $RawPredictionPath = Join-Path $RunRoot "validation_predictions.raw.pkl"
        $Candidates = @(Get-ChildItem -LiteralPath $RunRoot -Filter "best_coco_bbox_mAP_*.pth" -File)
        if ($Candidates.Count -ne 1) { throw "Expected exactly one RTMDet metric best checkpoint for $RunId, got $($Candidates.Count)" }
        Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe scripts/require_rtx5080.py } "require RTX 5080 before RTMDet test $RunId"
        Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe third_party/mmdetection/tools/test.py $RunConfig $Candidates[0].FullName --out $RawPredictionPath } "test $RunId"
    }
    $InputFormat = if ($Variant.Backend -eq "rtmdet") { "mmdet-pickle" } else { "dfine-coco-json" }
    $ProcessedPath = Join-Path $RunRoot "processed_validation_image_ids.json"
    Invoke-Checked { & python scripts/canonicalize_validation_predictions.py --backend $Variant.Backend --source $Variant.Name --input $RawPredictionPath --input-format $InputFormat --output $PredictionPath --processed-output $ProcessedPath } "canonicalize $RunId"
    if (-not (Test-Path $PredictionPath)) { throw "Missing canonical validation artifact for ${RunId}: $PredictionPath" }
    $Receipt = [ordered]@{ run_id = $RunId; variant = $Variant.Name; seed = $Seed; fold = $Fold; fold_manifest_sha256 = (Get-FileHash $ManifestPath -Algorithm SHA256).Hash.ToLower(); config_sha256 = (Get-FileHash $RunConfig -Algorithm SHA256).Hash.ToLower(); prediction_sha256 = (Get-FileHash $PredictionPath -Algorithm SHA256).Hash.ToLower(); processed_images_sha256 = (Get-FileHash $ProcessedPath -Algorithm SHA256).Hash.ToLower(); status = "completed" }
    Write-Utf8NoBom -Path (Join-Path $RunRoot "receipt.json") -Value ($Receipt | ConvertTo-Json -Compress)
} } }

# Validate that all 60 receipts/artifacts form one globally leak-safe OOF set.
Invoke-Checked { & python scripts/collect_oof_evidence.py --detector-root $ArtifactRoot --fold-root "artifacts/box_system/folds" --output (Join-Path $ArtifactRoot "oof_predictions.json") } "collect global OOF evidence"
