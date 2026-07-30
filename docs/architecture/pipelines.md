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

## Legacy

The D-FINE-N → MobileNetV4 Box Assurance → conditional ConvNeXt-Tiny →
component resolver → RepViT → conditional DINOv3 GPU flow is frozen historical
behavior. `portable_cpu_smoke/` and its configs/scripts remain in place.
Evaluation and documentation may compare it, but canonical production code
must not route into it implicitly.
