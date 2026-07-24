param([string]$Config = "configs/box_system.yaml")
$ErrorActionPreference = "Stop"

# This creates exactly 4 variants x 3 seeds x 5 folds. It only consumes the
# existing staged annotations and never creates physical capture data.
$Variants = @(
    @{ Name = "dfine_n_640"; Backend = "dfine"; Size = 640; Template = "configs/upstream/dfine_bread.yml" },
    @{ Name = "dfine_n_768"; Backend = "dfine"; Size = 768; Template = "configs/upstream/dfine_bread.yml" },
    @{ Name = "rtmdet_tiny_640"; Backend = "rtmdet"; Size = 640; Template = "configs/upstream/rtmdet_tiny_bread.py" },
    @{ Name = "rtmdet_tiny_768"; Backend = "rtmdet"; Size = 768; Template = "configs/upstream/rtmdet_tiny_bread.py" }
)
$Seeds = @(20260724, 20260725, 20260726)
$ArtifactRoot = "artifacts/box_system/detectors"

foreach ($Variant in $Variants) {
    foreach ($Seed in $Seeds) {
        foreach ($Fold in 0..4) {
            $RunId = "$($Variant.Name)-seed$Seed-fold$Fold"
            $RunRoot = Join-Path $ArtifactRoot $RunId
            New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
            $RunConfig = Join-Path $RunRoot "config.$([IO.Path]::GetExtension($Variant.Template).TrimStart('.'))"
            $ConfigText = Get-Content -Raw $Variant.Template
            $ConfigText = $ConfigText.Replace("__INJECTED_INPUT_SIZE__", [string]$Variant.Size).Replace("__INJECTED_SEED__", [string]$Seed)
            $ConfigText = $ConfigText.Replace("__INJECTED_TRAIN_ANNOTATIONS__", "artifacts/box_system/folds/fold-$Fold/train.json").Replace("__INJECTED_VALIDATION_ANNOTATIONS__", "artifacts/box_system/folds/fold-$Fold/validation.json")
            Set-Content -NoNewline -Encoding utf8 -Path $RunConfig -Value $ConfigText
            $PredictionPath = Join-Path $RunRoot "validation_predictions.json"
            if ($Variant.Backend -eq "dfine") {
                & .venvs/dfine/Scripts/python.exe third_party/D-FINE/train.py --config $RunConfig --output_dir $RunRoot
            } else {
                & .venvs/rtmdet/Scripts/python.exe third_party/mmdetection/tools/train.py $RunConfig --work-dir $RunRoot
            }
            if (-not (Test-Path $PredictionPath)) { throw "Missing validation artifact for ${RunId}: $PredictionPath" }
            $Receipt = [ordered]@{ run_id = $RunId; variant = $Variant.Name; seed = $Seed; fold = $Fold; config_sha256 = (Get-FileHash $RunConfig -Algorithm SHA256).Hash.ToLower(); prediction_sha256 = (Get-FileHash $PredictionPath -Algorithm SHA256).Hash.ToLower(); status = "completed" }
            $Receipt | ConvertTo-Json -Compress | Set-Content -NoNewline -Encoding utf8 -Path (Join-Path $RunRoot "receipt.json")
        }
    }
}
