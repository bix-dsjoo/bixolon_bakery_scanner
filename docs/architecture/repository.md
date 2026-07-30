# Repository architecture

## Design goals

This repository separates versioned control-plane material from large
data-plane material. Git contains code, configuration, manifests, policies,
small fixtures, and reviewed result summaries. External storage contains real
images, checkpoints, prototype/support banks, raw predictions, runtimes,
installers, and full experiment outputs.

```text
apps/                 Operator-facing applications
benchmarks/           Protocols, reviewed baselines, locked evidence identities
configs/              Pipeline, data, training, evaluation, deployment control
data/                 Catalogs, manifests, splits, synthetic fixtures
deployment/           Installer/package definitions and runtime locks
docs/                 Architecture, workflows, runbooks, ADRs, research archive
experiments/          Reproducible experiment definitions and compact receipts
models/               Model manifests and documentation; weights are external
policies/             Immutable calibrated decision/fusion policy artifacts
src/bakery_scanner/   Product and research library code
tests/                Hermetic, contract, integration, artifact, GPU suites
tools/                New responsibility-oriented operational entry points
scripts/              Backward-compatible command paths
portable_cpu_smoke/   Immutable legacy portable smoke path
portable_rfdetr_cpu/  Canonical RF-DETR CPU compatibility package path
```

## Runtime boundaries

- `data` owns canonical input and dataset contracts.
- `detection` is the stable namespace for RF-DETR-L; `detectors` remains a
  compatibility namespace for existing and legacy adapters.
- `classification` owns RepViT, conditional DINOv3 evidence, immutable fusion,
  and fail-closed acceptance.
- `pipelines` declares canonical and legacy orchestration identities without
  moving established implementations.
- `evaluation` and `benchmarking` turn immutable outputs into accuracy and
  latency evidence.
- `artifacts` validates repository-wide external artifact identity before a
  pipeline starts.
- `prototype` and `apps` implement the camera evaluation product boundary.

Dependencies flow inward through contracts. Applications and scripts may
compose packages; model adapters must not import application or deployment
code. Legacy paths may depend on compatibility modules but canonical code must
not silently fall back to the legacy pipeline.

## Compatibility policy

Existing imports, root-level configs, scripts, and portable directories remain
valid until an explicit migration is versioned and tested. New work uses the
stable namespaces and grouped configs. Compatibility files are thin facades or
documented entry points, not competing sources of truth.
