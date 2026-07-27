param(
    [string]$Device = "cuda:0"
)

$ErrorActionPreference = "Stop"

if ($Device -ne "cuda:0") {
    throw "Verifier training requires device cuda:0"
}

$env:CUDA_VISIBLE_DEVICES = "0"
$env:PYTHONPATH = "src"

$Python = "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe"
$Seed = 20260724
$ModelName = "mobilenetv4_conv_small"
$FoldRoot = "artifacts/box_system/folds"
$DetectorRoot = "artifacts/box_system/detectors"
$VerifierRoot = "artifacts/box_system/verifiers"
$StagedRoot = "artifacts/box_system/staged"
$Annotations = Join-Path $StagedRoot "annotations.json"
$Images = Join-Path $StagedRoot "images"

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing required artifact: $Path"
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-PositiveUniqueIds([object[]]$Values, [string]$Label) {
    $Ids = @($Values | ForEach-Object { [int]$_ })
    if (
        $Ids.Count -eq 0 -or
        @($Ids | Where-Object { $_ -le 0 }).Count -ne 0 -or
        @($Ids | Select-Object -Unique).Count -ne $Ids.Count
    ) {
        throw "$Label must contain unique positive image IDs"
    }
    return $Ids
}

function Assert-SameIds([int[]]$Expected, [int[]]$Observed, [string]$Label) {
    $ExpectedSorted = @($Expected | Sort-Object)
    $ObservedSorted = @($Observed | Sort-Object)
    if (
        $ObservedSorted.Count -ne $ExpectedSorted.Count -or
        @($ObservedSorted | Select-Object -Unique).Count -ne $ObservedSorted.Count -or
        @(Compare-Object -ReferenceObject $ExpectedSorted -DifferenceObject $ObservedSorted).Count -ne 0
    ) {
        throw "$Label must exactly match the held-out fold image IDs"
    }
}

function Get-DetectorFold([int]$Fold) {
    $RunId = "dfine_n_640-seed$Seed-fold$Fold"
    $RunRoot = Join-Path $DetectorRoot $RunId
    $ManifestPath = Join-Path (Join-Path $FoldRoot "fold-$Fold") "manifest.json"
    $ReceiptPath = Join-Path $RunRoot "receipt.json"
    $PredictionPath = Join-Path $RunRoot "validation_predictions.json"
    $ProcessedPath = Join-Path $RunRoot "processed_validation_image_ids.json"
    $Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
    if (
        $Receipt.run_id -ne $RunId -or
        $Receipt.variant -ne "dfine_n_640" -or
        [int]$Receipt.seed -ne $Seed -or
        [int]$Receipt.fold -ne $Fold -or
        $Receipt.status -ne "completed"
    ) {
        throw "Detector receipt identity or completion status does not match $RunId"
    }
    $ExpectedHashes = [ordered]@{
        fold_manifest_sha256 = Get-Sha256 $ManifestPath
        prediction_sha256 = Get-Sha256 $PredictionPath
        processed_images_sha256 = Get-Sha256 $ProcessedPath
    }
    foreach ($Name in $ExpectedHashes.Keys) {
        if ($Receipt.$Name -ne $ExpectedHashes[$Name]) {
            throw "Detector receipt hash mismatch for $RunId ($Name)"
        }
    }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ([int]$Manifest.index -ne $Fold) {
        throw "Fold manifest index does not match fold $Fold"
    }
    $TrainingIds = Get-PositiveUniqueIds $Manifest.training_image_ids "training_image_ids"
    $ValidationIds = Get-PositiveUniqueIds $Manifest.validation_image_ids "validation_image_ids"
    if (@($TrainingIds | Where-Object { $_ -in $ValidationIds }).Count -ne 0) {
        throw "Verifier fold training and validation IDs must be disjoint"
    }
    $ProcessedIds = Get-PositiveUniqueIds (Get-Content -LiteralPath $ProcessedPath -Raw | ConvertFrom-Json) "processed validation IDs"
    Assert-SameIds $ValidationIds $ProcessedIds "Processed detector IDs"
    return [ordered]@{
        ManifestPath = $ManifestPath
        PredictionPath = $PredictionPath
        ValidationIds = $ValidationIds
    }
}

function Test-CompletedVerifierFold([int]$Fold, [System.Collections.IDictionary]$DetectorFold) {
    $RunId = "$ModelName-seed$Seed-fold$Fold"
    $RunRoot = Join-Path $VerifierRoot $RunId
    if (-not (Test-Path -LiteralPath $RunRoot -PathType Container)) {
        return $false
    }
    $ReceiptPath = Join-Path $RunRoot "receipt.json"
    $CheckpointPath = Join-Path $RunRoot "verifier.pt"
    $ConfigPath = Join-Path $RunRoot "verifier_config.json"
    $PredictionPath = Join-Path $RunRoot "verifier_predictions.json"
    $Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
    if (
        [int]$Receipt.fold -ne $Fold -or
        [int]$Receipt.seed -ne $Seed -or
        $Receipt.model_name -ne $ModelName -or
        $Receipt.device -ne "cuda:0" -or
        $Receipt.status -ne "completed"
    ) {
        throw "Verifier receipt identity or completion status does not match $RunId"
    }
    if (
        $Receipt.checkpoint_sha256 -ne (Get-Sha256 $CheckpointPath) -or
        $Receipt.config_sha256 -ne (Get-Sha256 $ConfigPath) -or
        $Receipt.fold_manifest_sha256 -ne (Get-Sha256 $DetectorFold.ManifestPath)
    ) {
        throw "Verifier receipt hash mismatch for $RunId"
    }
    if (
        (@($Receipt.class_order) -join ",") -ne "INVALID,EXACTLY_ONE,PARTIAL,MULTIPLE" -or
        $Receipt.preprocessing.color_mode -ne "RGB" -or
        [int]$Receipt.training_examples.seed -ne $Seed -or
        $Receipt.training_examples.algorithm -ne "deterministic_four_state_verifier_crops"
    ) {
        throw "Verifier receipt contract is incomplete for $RunId"
    }
    $ReceiptHash = Get-Sha256 $ReceiptPath
    $ValidationSet = @{}
    $DetectorFold.ValidationIds | ForEach-Object { $ValidationSet[[int]$_] = $true }
    $Rows = @(Get-Content -LiteralPath $PredictionPath -Raw | ConvertFrom-Json)
    foreach ($Row in $Rows) {
        $Probabilities = @($Row.probabilities | ForEach-Object { [double]$_ })
        $ProbabilitySum = ($Probabilities | Measure-Object -Sum).Sum
        if (
            [int]$Row.fold -ne $Fold -or
            -not $ValidationSet.ContainsKey([int]$Row.image_id) -or
            @($Row.bbox).Count -ne 4 -or
            $Probabilities.Count -ne 4 -or
            [Math]::Abs($ProbabilitySum - 1.0) -gt 0.000001 -or
            $Row.verifier_receipt_sha256 -ne $ReceiptHash
        ) {
            throw "Verifier predictions violate the held-out fold contract for $RunId"
        }
    }
    return $true
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Missing Python 3.11 verifier environment: $Python"
}
if (-not (Test-Path -LiteralPath $Annotations -PathType Leaf)) {
    throw "Missing staged annotations: $Annotations"
}
if (-not (Test-Path -LiteralPath $Images -PathType Container)) {
    throw "Missing staged images: $Images"
}

& $Python -c "import torch; assert torch.cuda.is_available() and 'RTX 5080' in torch.cuda.get_device_name(0)"
if ($LASTEXITCODE -ne 0) {
    throw "Verifier training requires RTX 5080 cuda:0"
}

foreach ($Fold in 0..4) {
    $DetectorFold = Get-DetectorFold $Fold
    if (Test-CompletedVerifierFold $Fold $DetectorFold) {
        Write-Host "Reusing validated completed verifier fold $Fold"
        continue
    }

    $RunId = "$ModelName-seed$Seed-fold$Fold"
    $RunRoot = Join-Path $VerifierRoot $RunId
    if (Test-Path -LiteralPath $RunRoot) {
        throw "Refusing to overwrite incomplete verifier artifacts: $RunRoot"
    }
    & $Python -m bakery_scanner.verifier.model `
        --fold-manifest $DetectorFold.ManifestPath `
        --annotations $Annotations `
        --images $Images `
        --detector-predictions $DetectorFold.PredictionPath `
        --output-dir $RunRoot `
        --device $Device
    if ($LASTEXITCODE -ne 0) {
        throw "Failed verifier OOF fold $Fold (exit $LASTEXITCODE)"
    }
    if (-not (Test-CompletedVerifierFold $Fold $DetectorFold)) {
        throw "Verifier fold $Fold did not produce a complete validated artifact"
    }
}
