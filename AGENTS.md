# AGENTS.md

## Mission

All work in this repository supports a deterministic CPU inference pipeline that
infers bakery SKU, count, and location from a scan image. The canonical final
path is RF-DETR-L detection, RepViT-M1 direct decision, and conditional DINOv3
global and local evidence fusion. Accuracy, reproducibility, and a fail-closed
`Unknown` outcome take precedence over latency.

Priorities are:

1. Prevent misclassification, misses, duplicates, and non-target detections.
2. Produce deterministic, reproducible results.
3. Keep the CPU implementation maintainable and simple.
4. Measure performance as end-to-end CPU latency; do not claim an improvement
   without measured evidence.

## Canonical CPU pipeline

The processing contract is:

```text
Input image
  -> EXIF-transposed RGB canonical frame
  -> RF-DETR-L (CPU/FP32, calibrated threshold)
  -> RepViT-M1 direct-decision gate
  -> conditional DINOv3 global + local evidence
  -> immutable fusion consensus
  -> SKU or Unknown, aggregate and evaluation report
```

### Input and detection

- Apply EXIF transpose and convert to RGB before any model runs. This visual
  image is the canonical coordinate frame.
- RF-DETR-L runs on CPU in FP32. Its calibrated score threshold comes from
  `models/rfdetr_large_bakery_v1/manifest.json`; do not hard-code a competing
  threshold.
- Normalize detection boxes to `[x_min, y_min, x_max, y_max]` in the canonical
  image frame. Boxes must be finite, valid, and within that image's bounds.
- Preserve detector provenance and calibrated score with every candidate.

### Classification and fail-closed acceptance

- Run RepViT-M1 (`repvit_m1_15plus5_v1`) on each accepted RF-DETR-L crop.
  The runtime evaluates the RepViT direct-decision gate before conditional
  DINOv3/fusion. A direct decision is final only when the immutable calibrated
  direct gate accepts it.
- Only direct-gate rejections run DINOv3 ViT-S/16
  (`dinov3_vits16_15plus5_v1`) for both global and local evidence.
- The fusion policy is immutable and must be loaded from the configured
  versioned artifact. A fusion SKU is accepted only when either its ranked
  SKU equals the local Top-1, or both model global Top-1 results equal that
  SKU and the fusion margin is at least `0.85`.
- Every classification result that fails its applicable direct or fusion
  acceptance rule is `Unknown`. Never substitute an arbitrary registered SKU.
  `Unknown` is not silently counted as a bakery SKU; report it explicitly with
  its decision path and ranked evidence where available.
- Use the configured CPU policy and artifacts in
  `configs/cpu_rfdetr_classifier_policy.yaml`. Model weights, manifests,
  prototype/support banks, preprocessing, calibration, and fusion policy must
  pass their declared SHA-256 integrity checks before inference or evaluation.

### Output and aggregation

Each final object must include at least:

- a registered SKU identifier or `Unknown`;
- its canonical-frame bounding box;
- decision confidence;
- decision path (`repvit_direct`, conditional DINOv3/fusion, or `Unknown`);
- enough provenance to identify the fixed model, calibration, and policy
  artifacts used.

Aggregate only final registered-SKU objects. Per-SKU totals must equal the
number of final registered objects; `Unknown` counts remain separate.

## Evaluation and performance contract

- Evaluate canonical-frame boxes with deterministic one-to-one matching at
  IoU `0.50`. Report SKU errors, misses, duplicates, non-target detections,
  splits, merges, `Unknown` count, and final-versus-ground-truth box counts.
- Keep development, calibration, and locked acceptance evidence separate.
  Do not tune models, thresholds, preprocessing, or policies on locked
  acceptance data; if a locked set informs a decision, validate on a newly
  locked set.
- Report end-to-end CPU latency after warm-up, including the detector,
  classifier, and conditional recheck. The required latency summary is the
  mean time for fixed E/M/H image groups, together with per-stage timings and
  conditional-DINO execution rate.
- Do not claim a speed or accuracy gain until the relevant evaluation and CPU
  latency results are recorded. Accuracy is never traded away merely to reduce
  runtime.

## Legacy pipeline preservation

The previous D-FINE-N -> MobileNetV4 Box Assurance -> conditional ConvNeXt-Tiny
-> component resolver -> RepViT -> conditional DINOv3 GPU pipeline remains
legacy (레거시) code and documentation context only. Do not delete, move, or change its
portable CPU smoke files or its existing behavior as part of CPU RF-DETR-L
documentation work.

## Change and verification rules

- Limit each change to one pipeline responsibility when practical. When an
  interface changes, update its producer and consumer tests together.
- Version and record model, calibration, policy, preprocessing, data split,
  seed, and artifact hashes with results. Avoid training/validation leakage.
- Preserve pre-existing user changes and do not mix unrelated refactors.
- Validate the changed contract with relevant unit, integration, regression,
  evaluation, and CPU performance checks. Do not state that a release gate has
  passed without its recorded evidence.

## Completion criteria

Work is complete only when the requested behavior and contracts are implemented,
the relevant automated checks pass, output SKU/count/location/confidence/path
fields are mutually consistent, and documentation/configuration match observed
runtime behavior. The fail-closed `Unknown` policy is part of the contract, not
a successful SKU classification.
