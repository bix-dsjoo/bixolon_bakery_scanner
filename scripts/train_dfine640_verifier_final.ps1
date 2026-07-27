param(
    [string]$Device = "cuda:0",
    [string]$BundleRoot = "artifacts/box_system/final/dfine_n_640-verifier-seed20260724",
    [string]$TrainingRoot = "artifacts/box_system/final-training/dfine_n_640-verifier-seed20260724",
    [string]$DevelopmentReport = "artifacts/box_system/reports/dfine640_verifier_development.json"
)

$ErrorActionPreference = "Stop"

if ($Device -ne "cuda:0") {
    throw "Final detector and verifier training requires device cuda:0"
}

$env:CUDA_VISIBLE_DEVICES = "0"
$env:PYTHONPATH = "src"

$DFinePython = ".venvs/dfine/Scripts/python.exe"
$HostPython = "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe"
$Template = "configs/upstream/dfine_bread.yml"
$StagedRoot = "artifacts/box_system/staged"
$StagedAnnotations = Join-Path $StagedRoot "annotations.json"
$StagedManifest = Join-Path $StagedRoot "staged_manifest.json"
$Images = Join-Path $StagedRoot "images"
$Seed = 20260724
$TrainBatchSize = 16
$ValidationBatchSize = 16
$BaseLearningRate = 0.0001
$BackboneLearningRate = 0.00005

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Failed: $Description (exit $LASTEXITCODE)"
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Value) {
    $Parent = Split-Path -Parent $Path
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    [IO.File]::WriteAllText(
        $Path,
        $Value,
        (New-Object System.Text.UTF8Encoding($false))
    )
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

function New-DFineConfig(
    [string]$Output,
    [string]$TrainAnnotations,
    [string]$ValidationAnnotations
) {
    $ConfigDirectory = Split-Path -Parent $Output
    New-Item -ItemType Directory -Force -Path $ConfigDirectory | Out-Null
    $BaseConfigPath = Convert-ToPosixRelativePath `
        $ConfigDirectory `
        "third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml"
    $ConfigText = (Get-Content -LiteralPath $Template -Raw).
        Replace("__INJECTED_TRAIN_ANNOTATIONS__", (Convert-ToPosixRepositoryPath $TrainAnnotations)).
        Replace("__INJECTED_VALIDATION_ANNOTATIONS__", (Convert-ToPosixRepositoryPath $ValidationAnnotations)).
        Replace("__INJECTED_IMAGES_DIR__", (Convert-ToPosixRepositoryPath $Images)).
        Replace("__INJECTED_DFINE_BASE__", $BaseConfigPath).
        Replace("__INJECTED_INPUT_SIZE__", "640").
        Replace("__INJECTED_SEED__", [string]$Seed).
        Replace("__INJECTED_DFINE_TRAIN_BATCH__", [string]$TrainBatchSize).
        Replace("__INJECTED_DFINE_VAL_BATCH__", [string]$ValidationBatchSize).
        Replace(
            "__INJECTED_DFINE_BASE_LR__",
            $BaseLearningRate.ToString(
                "0.0000",
                [Globalization.CultureInfo]::InvariantCulture
            )
        ).
        Replace(
            "__INJECTED_DFINE_BACKBONE_LR__",
            $BackboneLearningRate.ToString(
                "0.00000",
                [Globalization.CultureInfo]::InvariantCulture
            )
        )
    if ($ConfigText.Contains("__INJECTED_")) {
        throw "Generated final D-FINE config contains unresolved placeholders"
    }
    Write-Utf8NoBom -Path $Output -Value $ConfigText
}

foreach ($Required in @(
    $DFinePython,
    $HostPython,
    $Template,
    $StagedAnnotations,
    $StagedManifest,
    $DevelopmentReport
)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
        throw "Missing required final-training input: $Required"
    }
}
if (-not (Test-Path -LiteralPath $Images -PathType Container)) {
    throw "Missing staged image directory: $Images"
}
if (Test-Path -LiteralPath $BundleRoot) {
    throw "Refusing to overwrite final bundle: $BundleRoot"
}
if (Test-Path -LiteralPath $TrainingRoot) {
    throw "Refusing to overwrite final training work: $TrainingRoot"
}

$Coco = Get-Content -LiteralPath $StagedAnnotations -Raw | ConvertFrom-Json
$ManifestRows = @(Get-Content -LiteralPath $StagedManifest -Raw | ConvertFrom-Json)
if (
    @($Coco.images).Count -ne 299 -or
    @($Coco.annotations).Count -ne 1410 -or
    $ManifestRows.Count -ne 299
) {
    throw "Final training requires exactly 299 staged images and 1410 boxes"
}

Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle validate-staged-inputs `
        --annotations $StagedAnnotations `
        --staged-manifest $StagedManifest `
        --images $Images
} "validate every staged source image and SHA-256 before final training"

Invoke-Checked {
    & $DFinePython -c (
        "import torch; " +
        "assert torch.cuda.is_available() and torch.cuda.current_device() == 0; " +
        "assert 'RTX 5080' in torch.cuda.get_device_name(0)"
    )
} "require RTX 5080 cuda:0 for final D-FINE training"
Invoke-Checked {
    & $HostPython scripts/require_rtx5080.py
} "require RTX 5080 cuda:0 for final verifier training"

$DetectorBundleRoot = Join-Path $BundleRoot "detector"
$DetectorWorkRoot = Join-Path $TrainingRoot "detector"
$VerifierBundleRoot = Join-Path $BundleRoot "verifier"
$EvidenceRoot = Join-Path $BundleRoot "evidence"
$PolicyRoot = Join-Path $BundleRoot "policy"
$SmokeRoot = Join-Path $BundleRoot "smoke"
$SmokeWorkRoot = Join-Path $TrainingRoot "smoke"
New-Item -ItemType Directory -Force -Path $DetectorBundleRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DetectorWorkRoot | Out-Null
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
New-Item -ItemType Directory -Force -Path $PolicyRoot | Out-Null
New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $SmokeWorkRoot | Out-Null
$TrainingInputSnapshot = Join-Path $EvidenceRoot "training_input_snapshot.json"
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle write-training-snapshot `
        --annotations $StagedAnnotations `
        --staged-manifest $StagedManifest `
        --images $Images `
        --output $TrainingInputSnapshot
} "freeze actual staged PNG training-byte snapshot"

$DetectorConfig = Join-Path $DetectorBundleRoot "dfine_n_640.yml"
New-DFineConfig `
    -Output $DetectorConfig `
    -TrainAnnotations $StagedAnnotations `
    -ValidationAnnotations $StagedAnnotations
Invoke-Checked {
    & $DFinePython third_party/D-FINE/train.py `
        -c $DetectorConfig `
        -d cuda:0 `
        --seed=$Seed `
        --output-dir $DetectorWorkRoot
} "train final full-data D-FINE-N 640"

$TrainedCheckpoint = Join-Path $DetectorWorkRoot "best_stg2.pth"
if (-not (Test-Path -LiteralPath $TrainedCheckpoint -PathType Leaf)) {
    $TrainedCheckpoint = Join-Path $DetectorWorkRoot "best_stg1.pth"
}
if (-not (Test-Path -LiteralPath $TrainedCheckpoint -PathType Leaf)) {
    throw "Final D-FINE training did not produce best_stg2.pth or best_stg1.pth"
}
$DetectorCheckpoint = Join-Path $DetectorBundleRoot "checkpoint.pth"
Copy-Item -LiteralPath $TrainedCheckpoint -Destination $DetectorCheckpoint
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle write-detector-metadata `
        --checkpoint $DetectorCheckpoint `
        --config $DetectorConfig `
        --output (Join-Path $DetectorBundleRoot "detector_metadata.json")
} "record final D-FINE checkpoint/config/runtime metadata"

Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle train-verifier `
        --annotations $StagedAnnotations `
        --staged-manifest $StagedManifest `
        --images $Images `
        --output-dir $VerifierBundleRoot `
        --device cuda:0
} "train final full-data four-state verifier"

Copy-Item -LiteralPath $StagedAnnotations `
    -Destination (Join-Path $EvidenceRoot "annotations.json")
Copy-Item -LiteralPath $StagedManifest `
    -Destination (Join-Path $EvidenceRoot "staged_manifest.json")
Copy-Item -LiteralPath $DevelopmentReport `
    -Destination (Join-Path $EvidenceRoot "development_report.json")
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle write-policy `
        --report $DevelopmentReport `
        --output (Join-Path $PolicyRoot "final_policy.json")
} "freeze final recall-first policy"
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle validate-training-snapshot `
        --snapshot $TrainingInputSnapshot `
        --images $Images
} "revalidate staged PNG bytes before smoke inference"

$SmokeImage = @($Coco.images | Sort-Object { [int]$_.id })[0]
$SmokeImageId = [int]$SmokeImage.id
$SmokeAnnotations = [ordered]@{
    images = @($SmokeImage)
    annotations = @(
        $Coco.annotations |
            Where-Object { [int]$_.image_id -eq $SmokeImageId }
    )
    categories = $Coco.categories
}
$SmokeAnnotationsPath = Join-Path $SmokeWorkRoot "annotations.json"
Write-Utf8NoBom `
    -Path $SmokeAnnotationsPath `
    -Value ($SmokeAnnotations | ConvertTo-Json -Depth 20 -Compress)
$SmokeConfig = Join-Path $SmokeWorkRoot "dfine_n_640_smoke.yml"
New-DFineConfig `
    -Output $SmokeConfig `
    -TrainAnnotations $StagedAnnotations `
    -ValidationAnnotations $SmokeAnnotationsPath
$RawSmokePredictions = Join-Path $SmokeWorkRoot "predictions.raw.json"
$SmokePredictions = Join-Path $SmokeWorkRoot "predictions.json"
$SmokeProcessedIds = Join-Path $SmokeWorkRoot "processed_image_ids.json"
$env:DFINE_OOF_PREDICTIONS = $RawSmokePredictions
try {
    Invoke-Checked {
        & $DFinePython third_party/D-FINE/train.py `
            -c $SmokeConfig `
            -d cuda:0 `
            --test-only `
            -r $DetectorCheckpoint `
            --output-dir $SmokeWorkRoot
    } "run one-image final D-FINE GPU smoke inference"
} finally {
    Remove-Item Env:DFINE_OOF_PREDICTIONS -ErrorAction SilentlyContinue
}
Invoke-Checked {
    & $HostPython scripts/canonicalize_validation_predictions.py `
        --backend dfine `
        --source dfine_n_640 `
        --input $RawSmokePredictions `
        --input-format dfine-coco-json `
        --annotations $SmokeAnnotationsPath `
        --output $SmokePredictions `
        --processed-output $SmokeProcessedIds
} "canonicalize one-image D-FINE smoke predictions"

$ProcessedIds = @(
    Get-Content -LiteralPath $SmokeProcessedIds -Raw |
        ConvertFrom-Json |
        ForEach-Object { [int]$_ }
)
if ($ProcessedIds.Count -ne 1 -or $ProcessedIds[0] -ne $SmokeImageId) {
    throw "One-image D-FINE smoke must process exactly its selected staged image"
}
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle smoke-verifier `
        --checkpoint (Join-Path $VerifierBundleRoot "verifier.pt") `
        --detector-predictions $SmokePredictions `
        --annotations $StagedAnnotations `
        --images $Images `
        --output (Join-Path $SmokeRoot "results.json") `
        --device cuda:0
} "run one-image final verifier GPU smoke inference"

Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle validate-training-snapshot `
        --snapshot $TrainingInputSnapshot `
        --images $Images
} "revalidate staged PNG bytes before final bundle approval"
Invoke-Checked {
    & $HostPython -m bakery_scanner.detectors.bundle write-manifest `
        --bundle-root $BundleRoot
} "write and validate immutable final bundle manifest"

Write-Host "Validated final D-FINE-N 640 plus verifier bundle: $BundleRoot"
