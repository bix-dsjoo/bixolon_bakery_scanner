# Batch2 CPU Smoke Deployment Design

- Date: 2026-07-28
- Status: approved design; pending implementation-plan review

## Goal

Create a portable Windows CPU smoke package that installs the required
runtime, runs real end-to-end inference on nine fixed Batch2 images, and
emits an inspectable result report.  This is a functional and latency smoke
test, not a release-accuracy evaluation.

## Fixed sample profile

The bundled `batch2_e3_m3_h3` profile contains exactly these images, copied
from `datasets/detection/group_20class_batch02/images`:

```text
g20_b02_e_0301.jpg  g20_b02_e_0306.jpg  g20_b02_e_0307.jpg
g20_b02_m_0307.jpg  g20_b02_m_0311.jpg  g20_b02_m_0315.jpg
g20_b02_h_0306.jpg  g20_b02_h_0312.jpg  g20_b02_h_0315.jpg
```

The runner may also accept another image directory, but the bundled profile
is the default and must stay deterministic.

## Runtime composition

```text
EXIF-transposed RGB input
  -> D-FINE-N 640 CPU detector
  -> MobileNetV4 CPU Box Assurance
  -> component resolver
  -> RepViT-M1 CPU classifier
  -> conditional DINOv3 ViT-S/16 CPU recheck
  -> JSON result, SKU aggregate, and annotated images
```

The package uses explicitly named D-FINE and MobileNetV4 fold-0 checkpoints
and records their paths and hashes in provenance.  It must not load cached
OOF predictions or classifier-only replay data.

There is no ConvNeXt-Tiny Box Assurance checkpoint in the currently selected
E2E source artifacts.  The CPU runner therefore uses `MobileOnlyE2EPipeline`:
each candidate whose MobileNetV4 outcome requires ConvNeXt-Tiny recheck is
converted to assurance `Unknown`.  It is never classified as a registered
product without that evidence.

The selected D-FINE source is a completed fold artifact, not a frozen
full-data release detector.  Consequently the package must identify itself
as a CPU functional smoke build and must not claim the locked 299-image gate
or production readiness.

## Package and commands

`scripts/package_cpu_smoke.ps1` creates a ZIP with only the needed source,
model artifacts, configuration, D-FINE checkout, locked CPU dependency list,
the nine sample images, and launch scripts.  It refuses to overwrite a ZIP,
creates an explicit temporary staging directory, verifies every manifest
path, records SHA-256 values, and removes only that temporary directory.

After extraction, a Windows user runs:

```powershell
.\install_cpu_smoke.ps1
.\run_batch2_cpu_smoke.ps1
```

The installer requires Python 3.11 and network access to install pinned CPU
dependencies.  The launcher writes a new timestamped result directory and
never overwrites an existing report.

## Runner behavior and output

The CLI accepts CPU only, performs preflight before creating its output, and
fails nonzero with structured diagnostics when a file, checksum, Python
environment, or required CPU dependency is missing.  It launches one warm
D-FINE JSONL worker; detector weights are loaded once, not per image.

One unreported warm-up pass is run before the nine measured passes.
`inference.json` retains the required per-image final objects (`sku_id` or
`null`, visual-frame `box_xyxy`, confidence, decision path, and top
candidates), aggregate counts excluding `Unknown`, artifact/environment
provenance, and invocation counts.

The user-facing `report.json` contains only the mean total E2E milliseconds
for the three groups `E`, `M`, and `H` (three images per group). It does not
include p95, medians, stage timings, SKU counts, or per-image rows. Annotated
PNG outputs remain available beside the two JSON files for visual inspection.

The report must explicitly state that CPU timings are not comparable to RTX
5080 release timings, ConvNeXt-Tiny recheck is absent, the detector is a
fold artifact, and the report provides no accuracy certification.

## Verification

Tests cover the fixed 3/3/3 image profile, CPU-only and non-overwrite
validation, model/preflight diagnostics, canonical EXIF frame propagation,
fail-closed recheck handling, `Unknown` aggregation, stage-timing/report
schema, and package-manifest completeness.  The final verification installs
the package into a clean CPU virtual environment, runs the nine included
images, checks all nine report rows and output overlays, and reports measured
latency without asserting an accuracy claim.
