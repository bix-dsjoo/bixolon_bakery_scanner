# 최소 학습량과 방법 비교 — 현재 결과

## 한 줄 결론

**이 RPC 개발 검증에서는 SKU당 1·3·5장은 충분하지 않았고, 현재 비교 범위에서
가장 보수적인 기준은 150장이다.** 80장은 150장과 정확도 차이가 작아 보이지만
wrong-SKU 차이가 사전 기준(0.5%p)을 넘었다. 따라서 80장을 최소 학습량으로
승인할 근거는 없다.

이 결론은 **DINOv3 전역 특징 + oracle product crop + M1 frozen mean
prototype** 범위의 개발 결과다. 실사용 파이프라인의 최종 최소 수량은 아직
정해지지 않았다.

## 학습 이미지 수 비교

동일한 200개 RPC SKU, development query 36,717개, 지원세트 10개 seed의 평균이다.
`wrong registered SKU`는 강제 Top-1 오분류이며, 이 단계에는 `Unknown`이 없다.

| SKU당 원본 학습 이미지 | DINOv3 전역 macro Top-1 | wrong registered SKU | 150장 대비 Top-1 | 150장 대비 wrong-SKU |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 42.72% | 57.22% | -23.21%p | +23.24%p |
| 3 | 46.57% | 53.62% | -19.37%p | +19.64%p |
| 5 | 50.05% | 50.13% | -15.88%p | +16.15%p |
| 10 | 54.90% | 45.13% | -11.03%p | +11.15%p |
| 20 | 59.73% | 40.25% | -6.21%p | +6.27%p |
| 40 | 63.01% | 36.97% | -2.93%p | +2.99%p |
| 80 | 65.06% | 34.86% | -0.88%p | +0.88%p |
| 150 (balanced reference) | 65.94% | 33.98% | 0.00%p | 0.00%p |

선택 규칙은 DIV(서로 다른 capture stratum을 우선하도록 하는 DINOv3
다양성 선택)이다. 80장의 seed별 wrong-SKU 차이는 +0.04%p부터 +1.89%p까지여서
평균 +0.88%p이다. paired support-seed bootstrap 95% 구간도 +0.55~+1.22%p라
사전 등록한 +0.5%p guardrail을 통과하지 못했다.

## 저샷 방법 비교

아래는 4,000개 development query의 빠른 방법 선별 결과다. 두 수치는
`macro Top-1 / wrong registered SKU`이며 5개 seed 평균이다. M1은 클래스별
정규화 평균 prototype, M2는 클래스 정규화 exemplar cache/kernel이다.

| 특징 / 지원 선택 | 방법 | 1장 | 3장 | 5장 |
| --- | --- | ---: | ---: | ---: |
| DINOv3 전역 / RND | M1 | 33.20% / 66.80% | 44.61% / 55.39% | 48.69% / 51.31% |
| DINOv3 전역 / RND | M2 | 33.20% / 66.80% | 40.04% / 59.96% | 43.33% / 56.67% |
| DINOv3 전역 / DIV | M1 | **42.00% / 58.00%** | **46.95% / 53.06%** | **49.77% / 50.23%** |
| DINOv3 전역 / DIV | M2 | 42.00% / 58.00% | 42.96% / 57.04% | 44.66% / 55.34% |
| RepViT 전역 / RND | M1 | 18.99% / 81.01% | 27.07% / 72.93% | 30.29% / 69.71% |
| RepViT 전역 / DIV | M1 | 18.65% / 81.35% | 26.50% / 73.50% | 30.68% / 69.32% |

현재 범위에서 유지할 방법 후보는 **M1 + DINOv3**다. DIV는 1장 조건에서
뚜렷한 이점이 있었지만, 선택 규칙 자체는 아직 full-system에서 확정하지 않는다.

- 1장에서 DIV는 RND보다 M1 DINOv3 Top-1이 **+8.80%p** 높다.
- 3장과 5장에서도 M1은 같은 선택 규칙의 M2보다 각각 **+3.99%p**, **+5.11%p**
  높다.
- RepViT 전역 단독 점수는 저샷에서 DINOv3 전역보다 크게 낮다. 이것은 RepViT를
  제거한다는 뜻이 아니라, 이후 gate/fusion을 포함해 별도로 검증해야 한다는 뜻이다.
- 10-seed 전체 development 곡선에서는 5장 RND가 DIV보다 0.51%p 높았고,
  80장에서는 둘의 차이가 0.03%p다. 따라서 `DIV가 모든 수량에서 우월`하다고
  주장하지 않는다.

## 실무 적용 판단

| 질문 | 현재 답 |
| --- | --- |
| “SKU당 5장이면 충분한가?” | 아니다. 이 proxy에서는 49.99% Top-1, 50.24% 강제 오분류다. |
| “1~3장에서 무엇을 해야 하나?” | M1 mean prototype을 사용하고, 1장에서는 DIV를 우선한다. 다만 실운영 승인이나 자동 등록에는 사용하지 않는다. |
| “80장으로 줄일 수 있나?” | 현재 기준으로는 아니다. 150장과의 wrong-SKU 차이가 +0.88%p다. |
| “150장이면 충분한가?” | 상대 기준의 balanced reference일 뿐이다. 여전히 33.98% 강제 오분류이므로 최종 품질 기준을 만족한다는 뜻이 아니다. |

## 증거와 범위

- 전체 development curve: `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-m1-div-curve-150.json`
  - SHA-256: `42b91940037840fc26c9398622af40dcefebc388acfbd75fdbb65c8798a7eda`
- 추가 support seed curve: `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-development-m1-global-curve-seeds-106-110.json`
  - SHA-256: `f2c52791c9e4a405e0e1714a67a39545e4bfe70116ceef102dff44b9870102f0`
- 저샷 방법 비교: `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\pilot-global-method-comparison.json`
  - SHA-256: `c9516baff144f1d1d5365153ef8accbf1edb2d088a8d33a1564a721f89a1561a`
- 상세한 입력·모델·캐시 provenance는
  [full-development receipt](receipts/20260803-full-development-m1-dinov3-global-curve.md)에 기록한다.

## 아직 남은 검증

이 문서는 아래를 평가하지 않았으므로 “최소 학습량 확정”이 아니다.

1. M0까지 포함한 모든 Stage-1 방법/5-fold 비교
2. RepViT direct gate, DINOv3 local evidence, calibration, immutable fusion,
   `Unknown`을 포함한 full classification subsystem
3. 150장 reference와 후보의 confidence-bound/old-SKU guardrail
4. 선택을 고정한 뒤의 locked `test2019` 비교
5. 포장상품이 아닌 빵 매장 및 유통매장 도메인으로의 별도 현장 검증
