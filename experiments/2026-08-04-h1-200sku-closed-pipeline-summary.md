# H1 200 SKU · SKU당 실제 6장 폐쇄형 분류 평가

## 범위

- 200개 RPC SKU, SKU당 실제 학습 crop 6장(총 1,200장)
- GT box crop만 사용한 분류 실험이다. 검출기 성능은 포함하지 않았다.
- H1: 동결 RepViT 특징 + 가벼운 200-way head + Frozen Feature Augmentation
- RepViT 직접 gate 거절 시에만 DINOv3 전역·지역 증거와 불변 fusion을 실행하고, 보정된 정책이 승인하지 않으면 `Unknown`으로 종료했다.
- 학습(train), threshold 보정(val 36,852 crop), 잠금 평가(test 294,333 crop)를 분리했다.

## 잠금셋 결과

| 실제 이미지/SKU | 총 support | SKU 정답률 | Unknown률 | 승인 SKU 정밀도 | 조건부 DINO 실행률 |
|---:|---:|---:|---:|---:|---:|
| 6장 | 1,200장 | 0.76% | 99.24% | 99.78% | 99.88% |

보정셋에서 직접 gate와 fusion의 오승인 수는 각각 0건이었다. 이 매우 엄격한 zero-error 보정은 잘못된 SKU 승인을 막지만, 200 SKU·6장 조건에서는 대부분을 `Unknown`으로 거절한다. 따라서 이 조건은 현 운영 기준에서 SKU당 6장으로는 부족하다는 근거이며, 정답률 개선을 주장하는 결과가 아니다.

원본 결과 receipt(외부 저장소): `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\h1_closed_pipeline_200sku_6shot_locked.json`
