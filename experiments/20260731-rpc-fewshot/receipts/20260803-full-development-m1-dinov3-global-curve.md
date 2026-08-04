# Full-development M1 DINOv3-global learning curve (preliminary)

## Scope and decision

This is a development-only, oracle-product-crop, forced-Top-1 measurement of
the M1 frozen mean-prototype method on the DINOv3 global branch. It is a
learning-curve screen, not a Stage-4 full-subsystem confirmation and not a
locked acceptance result.

The result does **not** evaluate the RepViT direct-decision gate, DINOv3 local
evidence, calibrated immutable fusion policy, `Unknown` behavior, detection,
or the locked `test2019` split. It must not be used as the image requirement
for bakery products or as a production onboarding decision.

Within this narrow screen, the diversity-aware selector (DIV) is the selected
support rule. At 80 supports per SKU, its mean wrong-registered-SKU rate is
0.8394 percentage points higher than the balanced 150-shot reference. This
exceeds the preregistered 0.5 percentage-point wrong-SKU guardrail. Therefore
80 cannot be the provisional minimum on this screen; 150 is the current
conservative reference/candidate only.

## Frozen inputs

| Item | External path or identity | SHA-256 |
| --- | --- | --- |
| Resolved dataset inputs | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\resolved_inputs.json` | `1d8e5f29c74a076947cdebe8d74c36510b6f04a5c05ad8ff01b66a942d244538` |
| Development/calibration role split | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\scene_roles.json` | `2cd9f08bd5adceb555f1265b67b36fd4b159026f7f44956b62a0ab2424bb60f0` |
| DINOv3 checkpoint | `models/dinov3_vits16_15plus5_v1/dinov3_vits16_pretrain_lvd1689m-08c60483.pth` | `08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d` |
| 150-shot support feature cache | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\pilot-global-150-features.npz` | `38df59dc5af089b17f9a06708637346b612209dd4e126e507537f4527fd319d6` |
| Development DINOv3 global cache | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-dinov3-global.npz` | `4107223571a7fc6eec17704636148a6fc48eb2305d7b7462021a1e00f109ddf8` |
| Cache builder | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\build_full_development_dino_cache.py` | `3c668b963348757d6e95a759277dd2eda13e4e1896c379770c8898e4b21017e2` |
| Curve scorer | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\score_full_development_m1_curve.py` | `037261dd7d314f3f17a37013355000e6faf2e59b23c4feb17f2a5a5c65e94436` |

Repository commit at scoring: `ecc2ca246b5cdfe4d0f90b8444840ed0f508062b`.

## Protocol

- Query set: all 36,717 objects in the frozen `val2019` development role.
- Supports: original `train2019` images, nested per-SKU support prefixes.
- Method: M1 frozen, independently L2-normalized DINOv3 embeddings; normalized
  per-SKU mean prototype; cosine forced Top-1.
- Selectors: deterministic RND and DIV; five declared support seeds
  (`101`–`105`).
- Counts: `1, 3, 5, 10, 20, 40, 80, 150` supports per SKU.
- Reference: balanced `k=150`; every class has the same selected 150-shot
  support bank.

## Aggregate results

Values are five-seed means. `macro Top-1` is macro accuracy over the 200 RPC
categories. `wrong registered SKU` is the forced-Top-1 error rate, so it has
no `Unknown` abstention behavior.

| Supports / SKU | DIV macro Top-1 | DIV wrong registered SKU | RND macro Top-1 | RND wrong registered SKU |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 42.72% | 57.22% | 32.24% | 67.88% |
| 3 | 46.08% | 54.14% | 44.67% | 55.59% |
| 5 | 49.99% | 50.24% | 50.13% | 50.25% |
| 10 | 54.98% | 45.08% | 54.55% | 45.59% |
| 20 | 59.81% | 40.16% | 59.23% | 40.79% |
| 40 | 63.09% | 36.93% | 62.83% | 37.11% |
| 80 | 65.09% | 34.82% | 64.92% | 34.96% |
| 150 | 65.94% | 33.98% | 65.94% | 33.98% |

For DIV, `k=80 - k=150` is -0.8496 percentage points in macro Top-1 and
+0.8394 percentage points in wrong registered SKU. The per-seed wrong-SKU
difference ranges from +0.1008 to +1.5878 percentage points. Consequently
the 80-shot condition fails the 0.5-point wrong-SKU screen guardrail even
though its mean macro-Top-1 gap is below two points.

## Evidence output

Raw curve output (external; not committed):
`C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-m1-div-curve-150.json`

SHA-256: `42b91940037840fc26c9398622af40dcefebc388acfbd75fdbb65c8798a7eda`.

## Required next evidence

1. Re-run the selected full-system conditions with the RepViT gate, conditional
   DINOv3 global and local evidence, per-condition calibration, immutable
   fusion, and `Unknown` accounting.
2. Apply the specified confidence-bound and old-SKU guardrails to those results.
3. Freeze the resulting selection certificate, then compare only the frozen
   candidate and 150-shot reference on locked `test2019`.
