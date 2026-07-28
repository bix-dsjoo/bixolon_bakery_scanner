# Bixolon Bakery Scanner

## Portable Batch2 CPU smoke

The portable CPU functional smoke ZIP is built with:

```powershell
.\scripts\package_cpu_smoke.ps1 -OutputPath C:\temp\batch2-cpu-smoke.zip
```

After extraction on Windows 10/11 with network access and Python 3.11, run
`portable_cpu_smoke\install_cpu_smoke.ps1`, then
`portable_cpu_smoke\run_batch2_cpu_smoke.ps1`. This is CPU-only; CUDA is not
supported. The fixed bundle has exactly nine Batch2 inputs. Its `report.json`
shows only E/M/H means, while `inference.json` retains audit fields and
`overlays` contains the rendered boxes. This smoke run uses metadata-rebound
policy and a legacy-four-state zero-delta assurance adapter; it is neither a
release gate nor an accuracy certification.

The package includes DINOv3 source at the audited commit recorded in
`dino/COMMIT.txt`; installers do not require Git or download
DINOv3 source/model weights.

The portable lock also includes the complete, exact-pinned runtime closure of
`third_party/D-FINE/requirements.txt`. A failed Python smoke run stops before
the PowerShell launcher reads its output report.

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
  → MobileNetV4 Box Assurance first pass
  → conditional ConvNeXt-Tiny Box Assurance recheck
  → final component resolver
  → Classifier: RepViT-M1 (`repvit_m1_15plus5_v1`)
  → Conditional recheck: DINOv3 ViT-S/16 (`dinov3_vits16_15plus5_v1`)
  → 품목·수량·위치 결과
```

### 1. Detector: D-FINE-N

D-FINE-N이 입력 이미지에서 빵의 위치와 후보 박스를 recall-first로 검출합니다.
이 단계의 출력은 최종 결과가 아니라 Verifier가 확인할 후보 집합입니다.
낮은 점수 후보도 Box Assurance 전에 제거하지 않습니다.

### 2. Box Assurance: MobileNetV4 first pass, conditional ConvNeXt-Tiny

MobileNetV4가 모든 후보를 배치로 평가하여 `INVALID`, `EXACTLY_ONE`,
`PARTIAL`, `MULTIPLE` 상태와 box quality 및 원본 좌표계 box delta를 냅니다.
conditional ConvNeXt-Tiny는 MobileNetV4의 confidence/quality가 부족하거나
`PARTIAL`/`MULTIPLE` 또는 후보 관계 그래프와의 충돌일 때만 재확인합니다.

### 3. Final component resolver

후보 관계 그래프는 중복, 부분, 병합의 가능성을 보여 주지만 hard NMS는 최종
결정이 아닙니다. final component resolver가 중복과 실제 overlap을 구분합니다.
따라서 실제로 겹친 두 빵을 제거하지 않으며, 분리 후보를 복구할 수 없는 병합
구성요소 또는 충분한 근거 없이 충돌한 결과는 `Unknown`으로 남깁니다.
`Unknown`은 빵으로 조용히 집계하지 않습니다.

### 4. Classifier: RepViT-M1

검증된 각 빵 영역은 RepViT-M1 기반 Classifier로만 전달됩니다.
Classifier는 제품 종류와 분류 신뢰도를 산출하며, 신뢰도가 충분하고 혼동
가능성이 낮은 결과는 즉시 사용합니다.

현재 우선 적용하는 Classifier 산출물은
`models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt`입니다.

### 5. Conditional DINOv3 ViT-S/16 재확인

DINOv3는 모든 대상에 실행하지 않습니다. 분류 신뢰도가 낮거나 서로
유사한 제품을 구분하기 어려운 경우에만 재확인을 수행합니다.

- 등록 제품임이 충분히 확인되면 해당 품목으로 확정합니다.
- 등록 제품으로 확정할 근거가 부족하면 `Unknown`으로 처리합니다.

현재 우선 적용하는 재확인 산출물은
`models/dinov3_vits16_15plus5_v1`의 사전학습 가중치와 20품목 prototype
support 파일입니다.

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

잠긴 299장 승인 평가셋에서 IoU 0.50 및 0.75 모두 다음 오류가 각각 0건이어야
합니다.

- 오분류
- 누락
- 중복 집계
- 비대상 물체 검출
- split 오류
- merge 오류

또한 이미지별 최종 박스 수가 GT 빵 수와 일치하고, 최종 박스에 `Unknown`이
없어야 합니다. 이 수치는 실제 empty-tray, overlap, obstruction 데이터가 없는
현재 개발 전용 범위의 결과입니다. 그러므로 이 미관측 조건을 포함한 운영상
100% 보장으로 표현하지 않습니다.

### 성능

현재 RTX 5080 GPU에서 warm-up 후 Detector부터 최종 집계까지 전체 파이프라인의
E2E p95 **0.5초 이하**가 승인 게이트입니다. 정확성 승인 기준을
훼손하는 속도 최적화는 허용하지 않습니다.

## 핵심 원칙

1. 정확성이 속도보다 우선합니다.
2. 불확실한 오분류보다 명시적인 `Unknown`이 안전합니다.
3. 각 모델은 하나의 명확한 책임을 가집니다.
4. 신뢰도 임계값과 모델 선택은 재현 가능한 평가 결과로 결정합니다.
5. 최적화 전후에 동일한 승인 평가 기준을 통과해야 합니다.
