# Bixolon Bakery Scanner

스캔 이미지 한 장에서 빵의 **품목, 수량, 위치**를 빠르고 정확하게
추론하는 GPU 기반 비전 파이프라인입니다.

## 목표

Bakery Scanner는 검출, 영역 검증, 제품 분류, 조건부 재확인을 결합하여
최종 판매 대상만 식별합니다.

- 빵을 하나도 놓치지 않습니다.
- 같은 빵을 중복 집계하지 않습니다.
- 집게, 포장지, 라벨, 트레이 등 비대상 물체를 빵으로 판단하지 않습니다.
- 등록 제품을 다른 제품으로 잘못 분류하지 않습니다.
- 확실하지 않은 품목은 억지로 분류하지 않고 `Unknown`으로 반환합니다.

## 추론 파이프라인

```text
스캔 이미지
  → Detector: D-FINE-N
  → Verifier: ConvNeXt-Tiny
  → Classifier: RepViT-M1 (`repvit_m1_15plus5_v1`)
  → 저신뢰·난분류 결과만 DINOv3 ViT-S/16 (`dinov3_vits16_15plus5_v1`) 재확인
  → 품목·수량·위치 결과
```

### 1. Detector

D-FINE-N이 입력 이미지에서 빵의 위치와 후보 박스를 검출합니다.
이 단계의 출력은 최종 결과가 아니라 Verifier가 확인할 후보 집합입니다.

### 2. Verifier

ConvNeXt-Tiny Verifier는 Detector의 후보 박스를 검증하고 필요한 보정과
정리를 수행합니다.
누락된 빵, 하나의 빵을 가리키는 중복 박스, 여러 빵을 합친 박스, 배경이나
비대상 물체의 오검출을 제거하여 빵 하나당 하나의 최종 대상 영역을
확정합니다.

### 3. Classifier

검증된 각 빵 영역은 `repvit_m1_15plus5_v1` RepViT-M1 Classifier로
전달됩니다. Classifier는 제품 종류와 보정된 분류 신뢰도를 산출하며,
신뢰도와 클래스 간 분리도가 모두 충분한 결과만 즉시 확정합니다.

### 4. DINOv3 재확인

DINOv3 ViT-S/16 `dinov3_vits16_15plus5_v1`은 모든 대상에 실행하지
않습니다. 분류 신뢰도가 낮거나 서로 유사한 제품을 구분하기 어려운
경우에만 재확인을 수행합니다.

- 등록 제품임이 충분히 확인되면 해당 품목으로 확정합니다.
- 등록 제품으로 확정할 근거가 부족하면 `Unknown`으로 처리합니다.

이 조건부 경로는 정확도를 보완하면서 평균 추론 시간을 제한합니다.

## 출력

최종 추론 결과는 다음 정보를 제공합니다.

- 각 대상의 제품 식별자 또는 `Unknown`
- 원본 이미지 좌표계 기준 위치
- 각 대상의 판정 신뢰도와 판정 경로
- 품목별 수량
- 전체 제품 수량

개별 위치는 `[x_min, y_min, x_max, y_max]` 형식의 경계 상자로 표현합니다.
판정 경로는 Classifier 직접 확정, DINOv3 재확인, `Unknown`을 구분할 수
있어야 합니다.

## 성공 기준

### 정확성

고정된 운영 조건과 사전에 잠근 승인 평가셋에서 다음 오류가 각각 0건이어야
합니다.

- 오분류
- 누락
- 중복 집계
- 비대상 물체 검출

여기서 오인율 0%는 검증된 운영 범위의 출하 기준입니다. 검증되지 않은
모든 환경과 입력에 대한 절대적 무오류 보장을 의미하지 않습니다.

### 성능

현재 기준 PC의 GPU에서 Detector부터 최종 집계까지 전체 파이프라인의
이미지당 추론 시간 **0.5초 이하**를 목표로 합니다. 정확성 승인 기준을
훼손하는 속도 최적화는 허용하지 않습니다.

## Classifier 보정·승인·벤치마크

Classifier 임계값은 모델 패키지에 내장된 고정값이 아니라 독립적인 개발
증거에서 선택해 버전된 calibration 산출물로 저장합니다. 입력 JSONL은
원본 이미지 경로와 원본 좌표계의 `box_xyxy`를 사용합니다.

- `development_manifest.jsonl`: RepViT 학습 이미지와 겹치지 않는
  `role=development` 표본입니다. 두 모델의 점수를 수집하고 grouped
  cross-fit으로 calibration을 선택하는 용도입니다.
- `locked_acceptance_manifest.jsonl`: 파라미터 선택에 사용하지 않은
  `role=locked_acceptance` 표본입니다. calibration을 고정한 뒤 한 번
  평가하는 출하 승인 용도입니다.
- `benchmark_manifest.jsonl`: `sample_id`, `image_path`, `box_xyxy`를
  필수로 갖는 분류기 전용 성능 표본입니다. 선택적으로 `registered`와
  `sku_id`를 함께 기록할 수 있지만 벤치마크는 정답률을 계산하지 않습니다.

개발 증거 수집과 calibration 선택:

```powershell
python scripts/build_dinov3_source_manifest.py --output artifacts/classification/dinov3_source_manifest.json
python scripts/collect_classifier_evidence.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --manifest datasets/classification/development_manifest.jsonl --output artifacts/classification/development_evidence.jsonl
python scripts/calibrate_classifier_policy.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --evidence artifacts/classification/development_evidence.jsonl --output artifacts/classification/policy_v1.json
```

잠긴 승인 증거 수집과 고정 정책 평가:

```powershell
python scripts/collect_classifier_evidence.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --manifest datasets/classification/locked_acceptance_manifest.jsonl --output artifacts/classification/locked_evidence.jsonl
python scripts/evaluate_classifier_policy.py --config configs/classifier_policy.yaml --dino-source-manifest artifacts/classification/dinov3_source_manifest.json --coverage-contract configs/locked_classifier_coverage_v1.json --development-evidence artifacts/classification/development_evidence.jsonl --evidence artifacts/classification/locked_evidence.jsonl --calibration artifacts/classification/policy_v1.json --output artifacts/classification/locked-report.json
```

`build_dinov3_source_manifest.py` defaults to the authoritative support roots
`datasets/classification/base_15class` and
`datasets/classification/incremental_5class_crop`. Its canonical digest must
equal `source_manifest_sha256` in the DINO support artifact; otherwise evidence
collection, calibration, and locked evaluation fail closed. Locked release also
requires all 20 registered SKUs, at least one unregistered crop, and every
scenario in `configs/locked_classifier_coverage_v1.json`; a perfect subset is
not release eligible.

잠긴 보고서는 `auto_precision`, `fallback_top3_recall`,
`assisted_success`가 적용 가능한 구간마다 1.0인지 검사하며, 하나라도
충족하지 못하면 명령이 0이 아닌 종료 코드를 반환합니다. 잠긴 결과를 보고
임계값을 조정했다면 새 잠금 평가셋으로 다시 검증해야 합니다.

분류기 전용 GPU 벤치마크:

```powershell
python scripts/benchmark_classifier_pipeline.py --config configs/classifier_policy.yaml --manifest datasets/classification/benchmark_manifest.jsonl --warmup 20 --output artifacts/classification/benchmark.json
```

측정 전에 manifest의 첫 유효 crop으로 RepViT와 DINOv3를 각각 한 번
명시적으로 실행합니다. 따라서 manifest가 전부 직접 확정 표본이어도
DINOv3 모델 로드, artifact 검증과 첫 GPU kernel 실행이 측정 구간에
들어가지 않습니다. 이 고정 preflight 1회는 `model_preflight_count=1`로
기록하며 사용자가 지정한 `warmup_count`에는 포함하지 않습니다. 이후
`--warmup` 횟수만큼 전체 정책 경로를 추가 실행하고 이 행들도 집계에서
제외합니다.

보고서는 warm-up을 제외한 혼합 전체·RepViT p50/p95, 실제 재확인 행의
DINOv3 p50/p95와 DINOv3 실행률을 기록합니다. 또한 RepViT 직접 확정
경로와 DINOv3 재확인 경로의 측정 표본 수 및 전체 latency p50/p95를
각각 분리합니다. 측정 표본에 한 경로가 없으면 해당 경로 percentile은
`null`입니다. 장치·정밀도 및 실제로 로드·검증한 모델·calibration 해시도
함께 기록합니다.

이 수치는 검증된 crop 이후의 Classifier만 측정하므로 Detector와
Verifier를 포함하는 0.5초 전체 파이프라인 목표의 합격 근거로 사용할 수
없습니다.

현재 모델 패키지 자체만으로 `auto_precision=100%` 또는
`fallback_top3_recall=100%`가 증명되는 것은 아닙니다. 학습과 독립적인
개발 데이터 및 잠긴 승인 데이터의 실제 결과가 있어야
`assisted_success=100%`를 포함한 출하 기준을 판정할 수 있습니다.

## 핵심 원칙

1. 정확성이 속도보다 우선합니다.
2. 불확실한 오분류보다 명시적인 `Unknown`이 안전합니다.
3. 각 모델은 하나의 명확한 책임을 가집니다.
4. 신뢰도 임계값과 모델 선택은 재현 가능한 평가 결과로 결정합니다.
5. 최적화 전후에 동일한 승인 평가 기준을 통과해야 합니다.
