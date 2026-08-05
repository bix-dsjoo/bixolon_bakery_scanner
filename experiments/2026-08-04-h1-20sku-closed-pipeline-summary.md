# H1 20-SKU Closed Classification Pipeline Summary

## Scope

This is an oracle-box classification experiment: GT product crops are supplied,
so detector accuracy is not measured. The fixed 20 SKU cohort uses 10 or 50
real `train2019` support images per SKU, selected by the deterministic `div`
prefix with seed `101`.

RepViT frozen features feed the H1 linear head. A direct H1 gate is calibrated
on 4,627 disjoint calibration crops with zero calibration false accepts. Only
direct-gate rejections run DINOv3 global and four-region local evidence. The
immutable fusion policy is also selected on calibration data with zero
calibration false accepts; every other item is `Unknown`.

The 35,179-crop `test2019` locked cohort is not used for support, gate, or
fusion selection.

## Locked results

| Real supports/SKU | Correct SKU rate | Accepted-SKU precision | Unknown rate | Conditional DINO rate |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 26.69% | 99.94% | 73.29% | 82.15% |
| 50 | **53.49%** | **99.94%** | **46.48%** | **56.35%** |

## Conclusion

For a fail-closed deployment target, 50 real images per SKU is preferred over
10: it preserves accepted-SKU precision at about 99.94%, raises correct-SKU
coverage by 26.79 percentage points, and reduces `Unknown` by 26.81 percentage
points. This is not a detector result and should not be used to claim end-to-end
scan-image accuracy.

The external immutable receipt is
`C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\h1_closed_pipeline_20sku_10_50_locked_retry1.json`.
