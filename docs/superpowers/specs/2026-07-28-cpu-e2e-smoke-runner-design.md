# CPU E2E Smoke Runner Design

- Date: 2026-07-28
- Status: approved for implementation

## Goal

Provide a deterministic, CPU-only functional smoke runner that executes D-FINE,
MobileNetV4 box assurance, component resolution, RepViT, and conditional
DINOv3 for at most ten images from a supplied image directory. The runner must
be usable on another PC without relying on this workspace's absolute paths.

## Scope and non-goals

The runner exists only to confirm that the detector, MobileNetV4 assurance,
component resolver, classifier, and conditional DINO recheck can be connected
and invoked on CPU. It intentionally does not load ConvNeXt-Tiny because no
ConvNeXt-Tiny assurance checkpoint is available. It is not a release evaluation and must not claim the
locked 299-image accuracy gate, RTX 5080 latency target, or production
readiness.

The runner does not silently substitute cached OOF boxes, synthetic
predictions, or classifier-only replay for detector execution. A required
model, artifact, executable, or CPU-compatible runtime that is unavailable
causes a precise preflight failure. Any MobileNetV4 candidate that would
require ConvNeXt-Tiny recheck becomes `Unknown`; it must not be upgraded to a
registered product without the missing recheck.

## Command interface

The new command is:

```powershell
python scripts/run_e2e_smoke.py --images <image-directory> --limit 10 --device cpu --output <report.json>
```

`--images` is required and must contain at least one supported raster image.
`--limit` defaults to 10 and may not exceed 10. The runner selects the first
`limit` supported files using a stable case-insensitive filename ordering.
`--device` accepts only `cpu`; other values fail before model loading. The
output path is required, and the command refuses to overwrite an existing
report.

All model and runtime locations are resolved relative to the repository root
or through explicit command-line overrides. The report records the resolved
paths, SHA-256 values when configured, runner version, selected input names,
and the execution device.

## Runtime composition

The runner constructs the same logical sequence as the production contract:

```text
Canonical input image
  -> D-FINE-N detector on CPU
  -> MobileNetV4 assurance for every candidate on CPU
  -> recheck-required candidate becomes assurance Unknown
  -> final component resolver
  -> RepViT-M1 classifier on CPU
  -> conditional DINOv3 ViT-S/16 recheck on CPU
  -> final objects and per-SKU aggregate
```

Every input is EXIF-transposed, RGB-normalized, and assigned a deterministic
positive image ID before detector invocation. Final result boxes remain in
that canonical visual image coordinate frame. `Unknown` remains explicit and
is never aggregated as a product.

## Preflight and failure behavior

Before processing any image, preflight validates the input directory, output
path, CPU-only device request, model files, configured checksums, D-FINE
worker command, assurance checkpoints, classifier policy artifacts, and
availability of CPU-capable dependencies. It emits a JSON error report to
stdout and exits nonzero without creating the requested output file when a
requirement is missing or invalid.

Failures while processing an image stop the run, identify the image and
pipeline stage, and preserve no partial success report. This prevents a
partial run from looking like a valid verification result.

## Output

The JSON report contains schema version, explicit `scope` set to
`cpu_functional_smoke_only`, selected input count, per-image final objects,
per-SKU count aggregate, stage timings, conditional ConvNeXt/DINO invocation
counts, and environment provenance. It also includes a limitations field that
states that CPU timings are not comparable with RTX 5080 E2E release metrics,
that ConvNeXt-Tiny recheck is absent, and that this runner provides no accuracy
certification.

## Tests

Unit tests cover stable ten-image selection, rejected limits and devices,
preflight failures, non-overwrite semantics, CPU factory construction through
dependency injection, canonical-image propagation, `Unknown` aggregation,
and report scope/limitations. Tests use lightweight fake runners; they do not
claim that fake execution validates model quality.
