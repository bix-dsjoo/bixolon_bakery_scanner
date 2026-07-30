# AGENTS.md

## Mission and priorities

All work supports a deterministic pipeline that infers bakery SKU, count, and
location from a scan image. Accuracy, reproducibility, provenance, and a
fail-closed `Unknown` outcome take precedence over latency.

Priorities, in order:

1. Prevent misclassification, misses, duplicates, and non-target detections.
2. Preserve deterministic, reproducible behavior and artifact integrity.
3. Keep the CPU implementation and responsibility boundaries maintainable.
4. Measure end-to-end CPU latency before making performance claims.

## Canonical CPU contract

```text
Input image
  -> EXIF-transposed RGB canonical frame
  -> RF-DETR-L (CPU/FP32, calibrated manifest threshold)
  -> RepViT-M1 direct-decision gate
  -> conditional DINOv3 global + local evidence
  -> immutable fusion consensus
  -> registered SKU or Unknown
```

### Input and detection

- Apply EXIF transpose and RGB conversion before any model runs. This visual
  image is the only canonical coordinate frame.
- Load the RF-DETR-L threshold from
  `models/rfdetr_large_bakery_v1/manifest.json`; never hard-code a competing
  threshold.
- Normalize boxes to finite, valid, in-bounds
  `[x_min, y_min, x_max, y_max]` coordinates in the canonical frame.
- Preserve detector artifact identity, calibrated score, and provenance with
  every candidate.

### Classification and fail-closed acceptance

- Run `repvit_m1_15plus5_v1` on each accepted detector crop.
- A direct decision is final only when the immutable calibrated RepViT gate
  accepts it.
- Only direct-gate rejections run `dinov3_vits16_15plus5_v1` global and local
  evidence.
- Load the configured immutable fusion policy. Accept its ranked SKU only when
  it equals local Top-1, or when both model global Top-1 values equal that SKU
  and the fusion margin is at least `0.85`.
- Every other result is `Unknown`. Never replace it with an arbitrary
  registered SKU, and never include it in per-SKU totals.
- Before inference or evaluation, verify every declared model, calibration,
  preprocessing, prototype/support bank, and policy SHA-256.

### Output and aggregation

Each final object includes a registered SKU or `Unknown`, canonical box,
confidence, decision path, and enough model/calibration/policy provenance to
reproduce the decision. Per-SKU totals equal the number of registered final
objects; `Unknown` totals remain separate.

## Evaluation and performance

- Use deterministic one-to-one matching at IoU `0.50` in the canonical frame.
- Report SKU errors, misses, duplicates, non-target detections, splits, merges,
  `Unknown`, and final-versus-ground-truth counts.
- Keep development, calibration, and locked acceptance evidence disjoint. If a
  locked set informs a choice, validate on a newly locked set.
- Measure warmed end-to-end CPU latency for fixed E/M/H groups, with per-stage
  timings and conditional-DINO execution rate.
- Never claim a speed or accuracy improvement without a committed result
  receipt. Never trade accuracy away solely for lower latency.

## Repository responsibility boundaries

- `configs/pipelines/canonical_cpu.yaml` is the canonical composition.
- `data/` owns catalogs, manifests, split identities, and synthetic fixtures.
  Real scans and derived data are external.
- `models/` owns documentation and manifests; weights are external.
- `policies/` owns small immutable calibrated policies tracked by Git.
- `experiments/` records hypotheses, resolved inputs, receipts, and compact
  conclusions; full outputs are external.
- `benchmarks/` owns protocols and reviewed summaries, not raw runs.
- `src/bakery_scanner/artifacts` verifies `artifacts.lock.json`.
- New code uses `bakery_scanner.detection`, `bakery_scanner.pipelines`, and
  `bakery_scanner.benchmarking`. Existing namespaces remain compatibility
  facades until an explicit migration.
- New operational implementations go under responsibility-oriented `tools/`;
  existing `scripts/` paths remain compatible wrappers.

Dependencies flow from apps/tools into library contracts. Model adapters do
not import app or deployment code. Canonical code must not silently fall back
to legacy implementations.

## Artifact, LFS, and public repository rules

- Git contains source, configs, manifests, policies, split identities, tiny
  fixtures, and reviewed compact summaries.
- External storage contains datasets, checkpoints, raw predictions, full
  runs, prototype/support banks, runtimes, wheels, and installers.
- Git LFS is allowed only under `release-assets/models/` and
  `release-assets/prototype-banks/` after redistribution and quota review.
- Do not add a blanket LFS rule for model extensions.
- Every external artifact is versioned by ID, byte size, SHA-256, storage
  class, and expected local path in `artifacts.lock.json` or a stricter
  component manifest.
- Do not commit private, proprietary, or unapproved model/data payloads to the
  public repository.

## Legacy preservation

The D-FINE-N → MobileNetV4 Box Assurance → conditional ConvNeXt-Tiny →
component resolver → RepViT → conditional DINOv3 GPU path is legacy context.
Do not delete, move, or change `portable_cpu_smoke/` files or legacy behavior
while changing the canonical RF-DETR path. Compatibility changes require
focused regression tests and explicit documentation.

## Change workflow

1. State one responsibility and its acceptance test.
2. Write or identify the failing test before behavior changes.
3. Change the smallest producer/consumer surface; update both sides of an
   interface together.
4. Record model, calibration, policy, preprocessing, data/split, seed, code,
   and artifact hashes with results.
5. Run hermetic unit/contract tests. Run artifact, integration, GPU, package,
   and performance suites when their boundary changes.
6. Treat skipped or unavailable suites as unverified, never passed.
7. Preserve unrelated user changes and never delete the only ignored copy of
   an artifact.

## Completion criteria

Work is complete only when requested behavior is implemented, relevant checks
pass, SKU/count/location/confidence/path fields agree, configs and docs match
runtime behavior, and required evidence is recorded. `Unknown` is a correct
fail-closed outcome, not a successful SKU classification.
