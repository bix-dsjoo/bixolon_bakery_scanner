# Full-development M1 DINOv3-global curve — ten-seed expansion

## Purpose and scope

This is the preregistered seed expansion of the preceding five-seed
[development receipt](20260803-full-development-m1-dinov3-global-curve.md).
The 80-shot point was within three percentage points of the reference on
macro Top-1, so five additional deterministic support seeds were scored before
retaining any screen decision.

The scope remains oracle product crops, forced Top-1, M1 frozen mean
prototypes, and the DINOv3 global branch. This is not a full classification
subsystem or locked result: it excludes M0/M2 completion, DINO local evidence,
the RepViT gate, calibration, immutable fusion, `Unknown`, detection, and
`test2019`.

## Inputs and reproducibility

The original five-seed receipt contributes seeds `101`–`105`. This receipt
adds seeds `106`–`110` using the exact same scorer, source candidate pool,
query cache, support cache, preprocessing, and DINOv3 checkpoint.

| Evidence | External path | SHA-256 |
| --- | --- | --- |
| Original rows (seeds 101–105) | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-m1-div-curve-150.json` | `42b91940037840fc26c9398622af40dcefebc388acfbd75fdbb65c8798a7eda` |
| Added rows (seeds 106–110) | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-m1-global-curve-seeds-106-110.json` | `f2c52791c9e4a405e0e1714a67a39545e4bfe70116ceef102dff44b9870102f0` |
| Development DINOv3 global cache | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-dinov3-global.npz` | `4107223571a7fc6eec17704636148a6fc48eb2305d7b7462021a1e00f109ddf8` |
| 150-shot support feature cache | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\pilot-global-150-features.npz` | `38df59dc5af089b17f9a06708637346b612209dd4e126e507537f4527fd319d6` |
| Shared scorer | `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\score_full_development_m1_curve.py` | `037261dd7d314f3f17a37013355000e6faf2e59b23c4feb17f2a5a5c65e94436` |

The existing scorer was first re-run for seed 101; all 16 frozen
`(selector, shot)` rows matched the original receipt exactly before seeds
106–110 were scheduled.

## Ten-seed results

Values are means across ten support seeds on the complete 36,717-object
development cohort. DIV is the diversity-aware selector. Error is forced
wrong-registered-SKU rate, with no `Unknown` path.

| Supports / SKU | DIV macro Top-1 | DIV wrong registered SKU | RND macro Top-1 | RND wrong registered SKU |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 42.72% | 57.22% | 33.14% | 67.12% |
| 3 | 46.57% | 53.62% | 45.47% | 54.89% |
| 5 | 50.05% | 50.13% | 50.56% | 49.88% |
| 10 | 54.90% | 45.13% | 54.95% | 45.30% |
| 20 | 59.73% | 40.25% | 59.32% | 40.81% |
| 40 | 63.01% | 36.97% | 62.88% | 37.14% |
| 80 | 65.06% | 34.86% | 65.03% | 34.93% |
| 150 | 65.94% | 33.98% | 65.94% | 33.98% |

For DIV, paired `k=80 - k=150` is -0.8755 percentage points in macro Top-1
and **+0.8835 percentage points** in wrong registered SKU. A 100,000-replicate
nonparametric bootstrap over the ten paired support-seed deltas (fixed seed
`20260731`) gives a 95% percentile interval of **+0.5515 to +1.2199%p** for
wrong-SKU difference. It remains wholly above the provisional +0.5%p
wrong-SKU screen guardrail.

## Decision

The additional seeds confirm, rather than reverse, the five-seed screen:
**80 is not eligible as the minimum in this global-branch proxy.** The current
conservative candidate/reference remains 150 supports per SKU. This is not a
final production or cross-domain conclusion; the required full-system and
locked evidence is listed in the experiment design.
