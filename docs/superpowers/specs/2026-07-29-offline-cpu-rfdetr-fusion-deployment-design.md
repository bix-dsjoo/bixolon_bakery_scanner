# Offline CPU RF-DETR Fusion Deployment Design

> **Canonical-final CPU notice.** This is a current RF-DETR CPU design alongside the [fusion-consensus design](2026-07-29-rfdetr-fusion-consensus-design.md), [nine-image evaluation design](2026-07-29-rfdetr-desktop-nine-image-evaluation-design.md), and [final CPU documentation design](2026-07-29-cpu-rfdetr-final-documentation-design.md). The canonical final runtime is EXIF-transposed RGB -> CPU/FP32 RF-DETR-L -> RepViT direct gate -> conditional DINOv3 global/local fusion -> SKU or `Unknown`; it replaces the former D-FINE path as the final runtime without deleting that legacy path.

**Goal:** Deliver a Windows ZIP that runs the RF-DETR-L plus fusion classifier on CPU without an existing Python installation or network access, and produces a verified nine-image report.

## Chosen Approach

Bundle the official Windows embedded Python 3.11 runtime, CPU-only Python packages, source tree, model artifacts, and PowerShell entrypoints in one ZIP. The package launcher enables the embedded runtime's local `site-packages` directory and executes the fixed CPU runner without referring to an absolute host path.

The package uses the same direct RF-DETR-L to classifier path as the GPU nine-image evaluation. It deliberately does not use the legacy D-FINE/MobileNet CPU smoke composition because its incomplete assurance model changes the output contract and previously produced invalid component overlays.

## Package Layout

- `runtime/python/`: relocatable embedded CPython 3.11 with local package paths enabled.
- `runtime/site-packages/`: CPU-only PyTorch, RF-DETR, timm, Pillow, NumPy, PyYAML, and their required dependencies.
- `src/bakery_scanner/`: runtime source.
- `models/` and `artifacts/`: RF-DETR-L checkpoint/calibration and the fixed RepViT/DINOv3 classifier assets, each integrity checked before inference.
- `scripts/run_cpu_rfdetr_fusion.py`: canonical RGB loading, CPU inference, IoU-0.50 evaluation, overlays, and report writing.
- `Run-CPU-Batch2.ps1`: end-user launcher with no install/download step.
- `Verify-Package.ps1`: validates every package file against `package-manifest.json`.

## CPU Runtime Contract

The runner forces `device=CPU` and FP32. It loads RF-DETR-L using its packaged calibration threshold and produces canonical visual-coordinate proposal boxes. It evaluates RepViT-M1 first; an immutable direct-decision gate acceptance returns immediately. Only a direct-gate rejection runs DINOv3 global and local evidence plus immutable fusion. That conditional fusion accepts only:

1. Fusion Top-1 equals DINOv3 local Top-1; or
2. Fusion Top-1 equals RepViT Top-1 equals DINOv3 global Top-1 and Fusion Top-1/Top-2 margin is at least 0.85.

Every other detection remains `Unknown`. The report separately records detector FP/FN at one-to-one IoU 0.50 and classifier Top-1/Top-3.

## Validation

1. Unit tests cover CPU config forcing, package path validation, and report metric aggregation.
2. The package build verifies SHA-256 for models and every bundled file.
3. A fresh extraction directory is used on this PC; it runs all nine fixed images with the embedded Python, without `PATH` Python or network.
4. The final report contains E/M/H mean latency plus Top-1, Top-3, FP, and FN.

## Scope and Limits

The offline ZIP will be materially larger than the previous model-only package because it contains CPython and CPU PyTorch. CPU timing is measured on this PC and is hardware-specific. The design does not claim the GPU latency target for CPU execution.
