# Classifier Abstention + Top-3 설계

- 작성일: 2026-07-27
- 상태: 사용자 승인 완료
- 범위: 정확히 하나의 빵을 포함한다고 검증된 crop 이후의 품목 판정

## 1. 목표

분류기는 확실한 경우에만 SKU를 자동 확정하고, 확신이 부족한 경우
`Unknown`과 함께 3개의 등록 SKU 후보를 제공한다.

```text
검증된 빵 crop
  → RepViT-M1 (`repvit_m1_15plus5_v1`)
  → 직접 확정 기준 충족 시 SKU
  → 그 외에는 DINOv3 ViT-S/16 (`dinov3_vits16_15plus5_v1`) 재확인
  → 재확인 기준 충족 시 SKU
  → 그 외에는 Unknown + Top-3
```

Detector와 Verifier가 정확한 crop을 전달했다고 가정한다. 이 명세의 분류
지표에는 Detector의 누락, 중복, 병합, 분할 및 crop 좌표 오류를 포함하지
않으며, 전체 파이프라인 출하 평가에서는 해당 오류를 별도로 포함한다.

## 2. 성공 지표

등록 SKU가 정답인 입력에는 다음 지표를 사용한다.

- `auto_precision`: SKU로 자동 확정한 결과 중 정답 비율
- `auto_coverage`: 전체 등록 SKU 입력 중 자동 확정한 비율
- `fallback_top3_recall`: `Unknown` 결과 중 정답 SKU가 Top-3에 포함된 비율
- `assisted_success`: 자동 확정이 정답이거나 `Unknown`의 Top-3에 정답이
  포함된 비율

출하 기준은 잠긴 승인 평가셋 전체와 필수 시나리오별로 다음을 모두
만족하는 것이다.

```text
auto_precision = 100%
fallback_top3_recall = 100%
assisted_success = 100%
```

`auto_coverage`는 높을수록 좋지만 정확성을 희생하는 합격 기준으로 사용하지
않는다. 등록되지 않은 제품에는 정답 SKU가 없으므로 Top-3 recall을 계산하지
않는다. 해당 입력은 반드시 `Unknown`이어야 하며 Top-3는 사용자 확인을 위한
참고 후보일 뿐이다.

이 100% 기준은 잠긴 평가셋과 검증된 운영 범위에 대한 출하 조건이며,
미관측 입력에 대한 절대 보장으로 표현하지 않는다.

## 3. 입력 전처리

원본 검증 박스를 기준으로 5%, 10%, 15% padding을 적용한 RGB crop 세 개를
만든다. padding 이후 좌표는 이미지 범위로 자르고, 모든 crop에 각 모델
패키지 README에 정의된 224×224 resize와 정규화를 적용한다.

- RepViT-M1: 세 crop의 softmax 확률 벡터를 평균한다.
- DINOv3: 세 crop의 L2 정규화 임베딩을 평균한 뒤 다시 L2 정규화하고,
  20개 SKU prototype과 cosine similarity를 계산한다.

crop 순서와 부동소수점 연산 경로를 고정해 동일 입력의 결과가
재현되도록 한다.

## 4. 판정 흐름

### 4.1 RepViT 직접 확정

RepViT-M1의 평균 확률에서 Top-1 확률, Top-2 확률 및 두 값의 margin을
계산한다. 보정된 Top-1 확률과 margin이 모두 버전된 직접 확정 임계값을
통과하면 해당 SKU를 확정한다.

한 조건이라도 통과하지 못하면 RepViT 결과만으로 SKU를 확정하지 않고
DINOv3를 실행한다.

### 4.2 DINOv3 재확인

DINOv3의 prototype similarity를 별도로 보정한다. 다음 조건을 모두
만족하는 경우에만 SKU를 확정한다.

1. RepViT와 DINOv3의 Top-1 SKU가 같다.
2. DINOv3의 보정 점수가 재확인 임계값 이상이다.
3. 결합 점수의 Top-1과 Top-2 margin이 재확인 margin 이상이다.

조건을 하나라도 만족하지 못하면 최종 제품 식별자는 `Unknown`이다.
평가 근거 없이 DINOv3 단독 Top-1로 RepViT 결과를 덮어쓰지 않는다.

### 4.3 Unknown Top-3

두 모델은 각각 20개 SKU 전체에 대한 점수를 제공해야 한다. RepViT 확률과
DINOv3 similarity는 서로 척도가 다르므로 원점수를 직접 평균하지 않는다.

개발용 grouped OOF 예측에서 각 모델 점수를 독립적으로 보정한 뒤 다음
결합 점수를 사용한다.

```text
fused_score(sku) =
  alpha * log(calibrated_repvit_probability(sku))
  + (1 - alpha) * log(calibrated_dino_probability(sku))
```

`alpha`와 보정 파라미터는 개발 데이터에서만 결정하고 버전된 calibration
산출물에 저장한다. 결합 log score에 softmax를 적용한 값을 보고용
`fused_probability`로 사용한다. 결합 점수가 높은 순서대로 서로 다른 SKU
3개를 반환하고, 동점은 SKU ID 오름차순으로 해결한다.

## 5. 임계값과 결합 가중치 선택

모든 보정 파라미터, 직접 확정 임계값, 재확인 임계값, margin 및 `alpha`는
장면 또는 촬영 세션 단위 grouped OOF 예측으로 선택한다. 동일 장면의
이미지가 파라미터 선택과 해당 fold 평가에 동시에 사용되면 안 된다.

선택 우선순위는 다음과 같다.

1. 자동 확정 오답 0건
2. Unknown fallback Top-3 누락 0건
3. assisted failure 0건
4. 위 조건 안에서 최대 `auto_coverage`
5. 위 조건 안에서 최소 DINOv3 실행률

어떤 임계값도 1번을 만족하지 못하면 해당 조건 또는 SKU의 자동 확정을
비활성화한다. 어떤 결합 설정도 2번을 만족하지 못하면 출하하지 않고 데이터,
학습 또는 결합 방식을 개선한다.

잠긴 승인 평가셋은 모델, 임계값, 결합 가중치 또는 confusion pair를
선택하는 데 사용하지 않는다. 승인 평가 결과를 보고 정책을 변경한 경우
새로운 잠금 평가셋으로 다시 평가한다.

## 6. 출력 계약

자동 확정 결과:

```json
{
  "decision": "sku",
  "sku_id": 6,
  "confidence": 0.98,
  "decision_path": "repvit_direct",
  "top3": []
}
```

DINOv3 재확정 결과는 `decision_path`를 `dinov3_confirmed`로 기록한다.
`confidence`는 직접 확정이면 보정된 RepViT Top-1 확률, DINOv3 재확정이면
결합 Top-1 `fused_probability`를 의미한다.

Unknown 결과:

```json
{
  "decision": "unknown",
  "sku_id": null,
  "confidence": 0.41,
  "decision_path": "unknown_top3",
  "top3": [
    {"rank": 1, "sku_id": 6, "score": 0.72},
    {"rank": 2, "sku_id": 5, "score": 0.68},
    {"rank": 3, "sku_id": 19, "score": 0.44}
  ]
}
```

Unknown 결과의 `confidence`와 Top-3 `score`는 결합 Top-1 및 각 후보의
`fused_probability`다. 이는 `Unknown` 자체가 정답일 확률이 아니라 가장
유력한 등록 SKU 후보의 보정 점수다.

모든 결과에는 실제 구현 시 다음 provenance를 함께 기록해야 한다.

- `repvit_m1_15plus5_v1`
- `dinov3_vits16_15plus5_v1`
- class-map 또는 prototype support 해시
- calibration 산출물 버전과 해시
- 전처리 버전

## 7. 평가 시나리오

최소한 다음 구간을 전체 및 개별로 보고한다.

- 20개 SKU 각각
- 기존 15개 SKU와 추가 5개 SKU
- 선언된 유사 품목 조합
- 조명, 회전, 크기 및 padding 변화
- RepViT와 DINOv3 Top-1 일치 및 불일치
- 등록되지 않은 제품과 비제품 crop

각 구간에 대해 자동 확정 정답·오답·보류 수, `auto_precision`,
`auto_coverage`, `fallback_top3_recall`, `assisted_success`, DINOv3 실행률,
단계별 latency와 전체 p50/p95 latency를 기록한다.

## 8. 오류 및 안전 처리

- 모델, class map, prototype support 또는 calibration 버전이 맞지 않으면
  추론을 거부하고 구성 오류를 반환한다.
- NaN, 무한대 또는 20개가 아닌 score vector는 유효한 판정으로 사용하지
  않는다.
- DINOv3 실행 실패 시 RepViT 저신뢰 결과를 SKU로 승격하지 않고
  `Unknown`을 반환한다. 이 경우 Top-3는 RepViT 후보임을 명시한다.
- Top-3는 항상 서로 다른 등록 SKU 3개여야 한다.
- 등록되지 않은 제품을 Top-3 후보 중 하나로 자동 확정하지 않는다.

## 9. 성능 원칙

RepViT 직접 확정 경로에서는 DINOv3를 실행하지 않는다. DINOv3 조건부
실행률과 두 경로의 latency를 별도로 기록한다. GPU 최적화는 동일한 잠긴
평가셋에서 자동 확정과 Top-3 결과가 회귀하지 않음을 확인한 뒤 채택한다.

## 10. 실행 가능한 증거·승인 절차

### 10.1 독립 개발 증거와 calibration

`development_manifest.jsonl`은 RepViT 학습 이미지와 겹치지 않는
`role=development` 표본만 포함한다. 동일 촬영 장면이나 세션은 하나의
`capture_group`으로 묶어 grouped cross-fit 경계를 보존한다.

```powershell
python scripts/collect_classifier_evidence.py --config configs/classifier_policy.yaml --manifest datasets/classification/development_manifest.jsonl --output artifacts/classification/development_evidence.jsonl
python scripts/calibrate_classifier_policy.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --evidence artifacts/classification/development_evidence.jsonl --output artifacts/classification/policy_v1.json
```

증거 수집은 모든 표본에 RepViT와 DINOv3를 모두 실행한다. calibration
명령은 개발 증거만 사용하며, cross-fit 자동 확정 오류, fallback Top-3
누락 또는 assisted failure가 있으면 정책 산출물을 쓰지 않는다.

### 10.2 잠긴 승인 평가

`locked_acceptance_manifest.jsonl`은 모델과 임계값 선택에 사용하지 않은
`role=locked_acceptance` 표본만 포함한다. 먼저 두 모델의 점수를 고정된
증거로 수집한 뒤 기존 calibration을 변경하지 않고 한 번 평가한다.

```powershell
python scripts/collect_classifier_evidence.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --manifest datasets/classification/locked_acceptance_manifest.jsonl --output artifacts/classification/locked_evidence.jsonl
python scripts/evaluate_classifier_policy.py --config configs/classifier_policy.yaml --evidence artifacts/classification/locked_evidence.jsonl --calibration artifacts/classification/policy_v1.json --output artifacts/classification/locked-report.json
```

잠긴 보고서는 전체, SKU별, 기존 15종, 추가 5종, 등록 및 미등록 구간의
`auto_precision`, `fallback_top3_recall`, `assisted_success`와 정확한 실패
표본 ID를 기록한다. 적용 가능한 출하 지표가 모두 1.0이 아니면 평가
명령은 0이 아닌 종료 코드를 반환한다. 이 결과로 파라미터를 바꿨다면 기존
잠금은 해제된 것이므로 새로운 잠금 평가셋이 필요하다.

### 10.3 Classifier 전용 벤치마크

`benchmark_manifest.jsonl`은 `sample_id`, `image_path`, `box_xyxy`를 필수로
갖는다. 정답을 함께 보존하려면 `registered`와 `sku_id`를 둘 다 추가할 수
있지만 벤치마크 명령은 정확성 지표를 계산하지 않는다.

```powershell
python scripts/benchmark_classifier_pipeline.py --config configs/classifier_policy.yaml --manifest datasets/classification/benchmark_manifest.jsonl --warmup 20 --output artifacts/classification/benchmark.json
```

먼저 manifest의 첫 유효 crop으로 RepViT와 DINOv3를 각각 한 번 명시적으로
실행한다. 이 고정 preflight는 all-direct manifest에서도 lazy DINOv3
모델을 실제로 로드하고 가중치와 support를 검증하며 첫 GPU kernel을
실행한다. preflight가 실패하면 측정이나 보고서 쓰기를 시작하지 않는다.
이 1회는 `model_preflight_count=1`로 기록하고 사용자 지정
`warmup_count`와 분리한다. 그 뒤 manifest를 순환하며 `warmup_count`만큼
전체 `ClassifierPipeline` 추론을 수행하고 모든 warm-up 행을 집계에서
제외한다.

`ClassifierPipeline`이 각 측정 단계 시작과 종료 직전에 CUDA를 동기화한
시간을 사용한다. 보고서는 측정 이미지 수, 혼합 전체·RepViT p50/p95,
DINOv3가 실제 실행된 행의 p50/p95와 실행률을 기록한다. RepViT 직접 확정
경로와 DINOv3 재확인 경로는 각각 측정 표본 수와 전체 latency p50/p95를
별도 집계한다. 측정 표본에 한 경로가 없으면 해당 경로 percentile은
`null`이다. 장치, 정밀도, 입력 manifest 해시와 실제로 로드·검증한
모델·support·calibration 해시를 canonical JSON으로 기록한다.

이 벤치마크는 검증된 crop 이후의 Classifier만 측정한다. Detector,
ConvNeXt-Tiny Verifier 및 최종 집계를 포함하지 않으므로 전체 파이프라인
0.5초 목표의 통과 근거로 사용할 수 없다.

현재 `repvit_m1_15plus5_v1`과 `dinov3_vits16_15plus5_v1` 모델 패키지만으로
`auto_precision=100%`, `fallback_top3_recall=100%` 또는
`assisted_success=100%`를 주장할 수 없다. 이 기준은 학습과 독립적인 개발
증거로 calibration을 확정하고, 별도의 잠긴 승인 증거에서 실제로 확인한
경우에만 충족된다.
