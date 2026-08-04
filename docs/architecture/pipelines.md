# Canonical and legacy pipeline contracts

## Canonical CPU

```text
encoded scan
  -> EXIF-transposed RGB canonical frame
  -> RF-DETR-L CPU/FP32 + manifest threshold
  -> bounded canonical xyxy candidates + provenance
  -> RepViT-M1 immutable direct gate
      accepted -> final registered SKU
      rejected -> DINOv3 global + local evidence
                  -> immutable fusion consensus
                  -> registered SKU or Unknown
  -> aggregate registered SKUs; report Unknown separately
```

The composition is `configs/pipelines/canonical_cpu.yaml`. Every referenced
model, bank, calibration, and policy is hash-bound. The fusion rule accepts only
local Top-1 agreement, or global Top-1 consensus with fusion margin at least
`0.85`. No fallback may manufacture a registered SKU.

## RTX 5080 15+5 candidate

The RTX 5080 candidate is an external-artifact development path, not a
replacement for the canonical CPU composition. Its input boundary is the same
EXIF-transposed RGB frame, then RF-DETR-L, completeness, RepViT direct gate,
and conditional DINOv3 global/local fusion. Static batches of 14 RepViT crops
and 7 DINO crops are chunk capacities, never scan limits: scans with 1-2 and
8+ objects remain valid and are measured as separate performance slices.

The candidate is `production-unverified` until exact train-all artifacts,
runtime/engine manifests, locked OOF quality evidence, and actual warmed RTX
5080 path receipts are registered and admitted. A completion receipt cannot
promote it to production or introduce a fallback to CPU/PyTorch/legacy code.

## Legacy

The D-FINE-N → MobileNetV4 Box Assurance → conditional ConvNeXt-Tiny →
component resolver → RepViT → conditional DINOv3 GPU flow is frozen historical
behavior. `portable_cpu_smoke/` and its configs/scripts remain in place.
Evaluation and documentation may compare it, but canonical production code
must not route into it implicitly.
