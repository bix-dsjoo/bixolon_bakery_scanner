# Bakery Scanner Detector + Verifier 설계

- 작성일: 2026-07-24
- 상태: 사용자 승인 완료, 구현 계획 작성 전
- 대상 환경: Windows 11, Intel Core Ultra 9 285K, RAM 64GB, CPU 추론

## 1. 목표와 성공 기준

고정 카메라로 촬영한 트레이 이미지에서 모든 빵의 axis-aligned bounding
box를 출력한다. detector는 빵의 종류를 구분하지 않고 단일 클래스
`bread`만 검출하며, 20종 제품 분류는 후단 classifier가 담당한다.

이 설계에서 “box 검출 100%”는 한 스캔 안에서 다음 조건을 모두 충족하는
것으로 정의한다.

1. 누락된 빵이 없다.
2. 배경이나 방해물을 빵으로 검출하지 않는다.
3. 같은 빵을 중복 검출하지 않는다.
4. 각 실제 빵은 예측 box 하나와만 매칭된다.

최종 판정 지표는 이미지 단위 `Scan Exact Match Rate(SEMR)`이다.

```text
SEMR =
  누락 0, 오검출 0, 중복 0인 이미지 수
  / 전체 이미지 수
```

독립 acceptance set의 모든 필수 시나리오에서 오류 0건을 합격 조건으로
삼는다. 재촬영 또는 결과 거부 없이 항상 box를 출력한다. 따라서 미지의
운영 분포까지 포함한 수학적 100%는 보장하지 않으며, 잠긴 acceptance
set과 지속적인 운영 모니터링으로 정의된 분포에서의 무오류를 검증한다.

## 2. 확정된 운영 조건

- 추론 장비는 이 PC의 CPU이다.
- 처리 지연시간은 초기 모델 선택 기준에 포함하지 않는다.
- 카메라 위치, 촬영 거리, 트레이 영역, 배경, 조명은 고정된다.
- 빵끼리 닿거나 일부 겹칠 수 있다.
- 불확실한 경우에도 재촬영을 요청하지 않는다.
- 초기 배포는 정확도 우선의 OpenVINO FP32를 사용한다.
- FP16, BF16, INT8은 acceptance 결과가 완전히 동일할 때만 채택한다.

## 3. 현재 데이터 현황

Detector 데이터는 COCO 형식으로 정리되어 있다.

| 데이터셋 | 이미지 | Boxes | 원래 클래스 | 장면 그룹 |
|---|---:|---:|---:|---:|
| `group_15class` | 90 | 379 | 15 | 44 |
| `group_20class_batch01` | 103 | 509 | 20 | 74 |
| `group_20class_batch02` | 106 | 522 | 20 | 76 |
| 합계 | 299 | 1,410 | 20 | 약 194 |

이미지당 객체 수는 3~8개이다. 전체 데이터에서 하위 5% box의 상대 크기는
대략 이미지 폭의 18%, 높이의 14%이다. 640 입력에서는 약 `117×87px`,
768 입력에서는 약 `140×105px`이므로 일반적인 작은 객체 문제보다는
접촉·겹침에 의한 병합과 분리가 주요 위험이다.

현재 데이터만으로 운영 무오류를 검증하기에는 부족하다. 다음 데이터를
추가 수집한다.

- 실제 touching/overlap 장면 300장 이상
- 빈 트레이 및 손, 집게, 포장지, 가격표, 부스러기 장면 100장 이상
- 트레이 가장자리에 걸친 빵
- 제품 1개부터 실제 최대 수량까지의 장면
- 모델과 threshold 결정에 사용하지 않을 acceptance 이미지 3,000장 이상

## 4. 검토한 접근법

### 접근법 A: D-FINE-N 768 + Crop Verifier

구성이 단순하고 box localization이 좋지만, 주 detector가 후보를 전혀
생성하지 못한 빵은 verifier도 검사할 수 없다.

### 접근법 B: 이종 detector + 독립 verifier

D-FINE-N 768을 주 detector로 사용하고 RTMDet-Tiny 768을 독립 proposal
detector로 사용한다. 두 구조의 오류를 상호 보완하며, crop 검증과 고정
배경 전경 검증을 결합한다.

### 접근법 C: RTMDet-Tiny 768 + D-FINE-N 640 audit

CPU 배포가 단순할 가능성은 있지만 보조 detector의 해상도가 낮아 겹침
복구 후보 생성력은 접근법 B보다 불리하다.

접근법 B를 채택한다. 단, 실제 최종 모델 조합은 동일 실험 조건에서 네
후보를 평가한 결과로 확정한다.

## 5. 전체 아키텍처

```text
고정 카메라 이미지
  -> 트레이 ROI 정렬 및 색상 보정
  -> D-FINE-N 768 주 후보 생성
  -> RTMDet-Tiny 768 독립 후보 생성
  -> 후보 관계 그래프 및 가설 생성
  -> Crop Verifier
  -> 전경 Coverage Verifier
  -> 필요 시 640 audit 및 고해상도 tile recovery
  -> 전역 Box Solver
  -> 최종 bread boxes + 감사 메타데이터
  -> 후단 20종 classifier
```

### 5.1 입력 정규화

고정된 트레이 ROI를 기준 좌표계로 perspective warp한 뒤 768 정사각 입력을
생성한다. 기준점 위치, 초점, 노출, 색상 분포를 측정하고 이상 여부를
메타데이터에 기록한다. 이상 입력도 거부하지 않고 전체 복구 파이프라인을
실행한다.

### 5.2 D-FINE-N 768

단일 클래스 `bread`의 주 detector이다. 낮은 proposal threshold로 후보를
넉넉히 생성하고 정밀한 좌표를 제공한다.

### 5.3 RTMDet-Tiny 768

단일 클래스 `bread`의 독립 proposal detector이다. D-FINE이 놓친 후보를
복구하고, 하나의 큰 box로 합쳐진 겹침 객체에 분리 가설을 제공한다.
NMS는 높은 IoU 기준 또는 Soft-NMS를 사용해 접촉 객체 후보를 보존한다.

### 5.4 Crop Verifier

후보 box와 주변 문맥 15~20%를 포함한 `256×256` crop을 입력으로 받는
MobileNetV3-Small급 독립 모델이다. 다음 네 상태를 출력한다.

```text
invalid      배경 또는 잘못된 box
exactly_one  한 개의 빵을 온전히 감싼 box
partial      빵 일부가 잘린 box
multiple     두 개 이상의 빵을 합친 box
```

보조 head는 예상 GT IoU, box 보정값 `dx, dy, dw, dh`, 전경 점유율을
출력한다. 이 모델은 제품 종류를 판별하지 않는다.

### 5.5 전경 Coverage Verifier

빈 트레이 기준 이미지와 현재 이미지를 비교해 트레이 내 전경 확률
마스크를 생성한다. 최종 후보가 덮지 못한 전경 영역은 누락 신호로
사용하고, 전경 점유율이 낮은 후보는 오검출 신호로 사용한다.

빵끼리 겹칠 수 있으므로 전경 연결요소의 수를 제품 수로 사용하지 않는다.
Coverage Verifier는 개수 판별기가 아니라 누락된 외곽 영역을 찾는
안전장치이다.

### 5.6 전역 Box Solver

각 후보를 독립적으로 유지·삭제하지 않고 전체 후보 조합을 평가한다.

```text
조합 점수 =
  detector 동의도
  + verifier exactly_one 점수
  + verifier 예상 IoU
  + 전경 coverage
  - 중복 box 패널티
  - partial/multiple 패널티
  - 트레이 밖 영역 패널티
```

실제 객체 겹침을 허용하며, 중심점과 형태가 거의 같고 verifier도 동일
객체로 판단한 경우에만 중복 제거한다.

## 6. 데이터 구성과 분할

세 detector 데이터셋의 모든 카테고리를 `bread`, `class_id=1`로
재매핑해 통합한다.

분할 단위는 이미지가 아니라 `(capture_batch, scene_number)` 장면
그룹이다. 같은 번호를 공유하는 E/H/M 이미지는 모두 같은 fold에
배치한다. 이미지 변환이나 verifier 샘플 생성은 장면 분할을 완료한 뒤
각 fold 내부에서 수행한다.

개발 평가는 5-fold 장면 그룹 교차검증으로 진행한다. 최종 모델은 전체
개발 데이터로 재학습하고, 새로 촬영한 잠긴 acceptance set은 마지막에
한 번만 평가한다. Acceptance 결과를 본 뒤 모델, threshold 또는
후처리를 변경하면 새 acceptance set을 구성한다.

## 7. 데이터 증강

고정 카메라 분포를 보존하는 증강만 사용한다.

- 노출, 화이트밸런스, 감마 변화
- 약한 초점 흐림과 모션 블러
- JPEG 압축
- 약 ±5도의 작은 회전
- 실제 범위 안의 위치와 크기 변화
- 실제 빵 마스크 기반 touching/overlap 합성

강한 perspective, 비현실적인 Mosaic 및 운영 범위를 벗어난 회전은
사용하지 않는다. 합성 overlap은 보조 수단으로만 사용하고 실제
touching/overlap 촬영 데이터를 필수로 포함한다.

## 8. Crop Verifier 학습 데이터

Verifier 학습 샘플은 detector의 out-of-fold 예측과 GT에서 생성한다.
Detector가 학습한 이미지의 in-sample 예측을 사용하지 않는다.

- `exactly_one`: 정상 GT와 작은 좌표 jitter
- `partial`: GT 상하좌우를 15~45% 잘라 생성
- `multiple`: 인접한 두 GT의 합집합 및 detector 병합 오류
- `invalid`: 트레이 배경, 빵 사이 공간, detector 오검출
- hard negative: 손, 집게, 포장지, 가격표, 부스러기

Verifier 학습용 합성 샘플도 원본 장면의 fold를 그대로 상속해 데이터
누수를 방지한다.

## 9. 후보 병합과 복구

### 9.1 Proposal 보존

두 detector 모두 낮은 threshold와 최대 30개 후보로 실행한다. 초기
탐색값은 D-FINE 0.05, RTMDet 0.01이지만 최종값은 out-of-fold
예측에서 모든 GT가 후보 하나 이상과 매칭되는 가장 높은 값으로 정한다.

### 9.2 관계 가설

IoU, 중심점 거리, 면적 비율, 전경 일치도를 사용해 다음 관계를 만든다.

- `1 <-> 1`: 두 detector가 같은 객체에 동의
- `1 <-> 0`: 한 detector에만 후보가 존재
- `1 <-> 2`: 병합 가설과 분리 가설이 충돌
- `N <-> N`: 복잡한 중복 또는 겹침

`1 <-> 1`은 verifier의 예상 IoU를 가중치로 사용한 Weighted Box Fusion을
적용한다. `1 <-> 0`은 삭제하지 않고 verifier로 전달한다. `1 <-> 2`는
합친 box와 분리 box들을 모두 전역 solver에 전달한다.

### 9.3 Verifier 처리

- `exactly_one`: 유지
- `partial`: 좌표 보정 후 재검사
- `multiple`: 분리 후보 탐색
- `invalid`: 제거

### 9.4 누락과 병합 복구

`multiple` 또는 uncovered foreground가 발생하면 다음 순서로 복구한다.

1. 두 detector의 threshold 아래 저점수 후보 복구
2. D-FINE-N 640과 RTMDet-Tiny 640 다중 스케일 audit
3. 원본 고해상도 ROI를 겹치는 타일로 나눠 D-FINE-N 768 재실행
4. 전경 내부 경계와 verifier 점수로 분리 가설 비교

640 후보는 기본 경로가 아니라 충돌 해결용 audit이다. Tile inference는
부분 객체 후보를 만들 수 있으므로 verifier의 `partial` 판정과 좌표
보정을 반드시 거친다.

### 9.5 재촬영 없는 최종 결정

모호성이 남아도 다음 우선순위로 항상 하나의 조합을 선택한다.

```text
두 detector의 일치
  > verifier exactly_one
  > 전경 coverage를 가장 잘 설명하는 조합
  > calibration된 detector 결합 확률
```

불확실성은 결과를 막는 데 사용하지 않고 감사 로그와 hard-case 수집
우선순위에만 사용한다.

## 10. 학습 순서

1. 세 COCO 데이터셋을 단일 클래스 `bread`로 통합한다.
2. 장면 그룹 5-fold manifest를 만든다.
3. 네 detector 후보를 동일 fold와 seed로 학습한다.
4. 각 후보를 세 개 random seed로 반복한다.
5. 모든 out-of-fold raw prediction을 저장한다.
6. Out-of-fold 오류와 GT로 Crop Verifier 데이터를 생성한다.
7. Crop Verifier를 학습하고 detector/verifier score를 calibration한다.
8. 후보 병합, coverage 및 solver threshold를 fold 결과로 결정한다.
9. Ablation으로 각 안전장치의 효과를 확인한다.
10. 전체 개발 데이터로 최종 detector와 verifier를 재학습한다.
11. 파이프라인을 동결하고 acceptance set을 한 번 평가한다.

## 11. 네 detector 후보의 비교

| 실험 | 모델 | 입력 |
|---|---|---:|
| E1 | D-FINE-N | 640 |
| E2 | D-FINE-N | 768 |
| E3 | RTMDet-Tiny | 640 |
| E4 | RTMDet-Tiny | 768 |

COCO pretrained checkpoint, fold, augmentation, seed, 평가 코드와 원본
annotation을 동일하게 유지한다.

선택 우선순위는 다음과 같다.

1. 낮은 threshold 후보를 포함한 GT recall
2. 이미지 단위 SEMR
3. touching/overlap의 split/merge 오류 수
4. 다른 detector와의 오류 상보성
5. box localization 품질
6. CPU 처리시간과 메모리

초기 기본 조합은 D-FINE-N 768 + RTMDet-Tiny 768이다. 실제 결과에서
640이 동일한 SEMR과 오류 0을 달성하면 더 단순한 640 구성을 채택할 수
있다. COCO mAP만으로 최종 조합을 결정하지 않는다.

## 12. 평가 프로토콜

### 12.1 기본 매칭

각 GT와 prediction을 일대일 최적 매칭한다. 성공 스캔은 GT 수와 예측
수가 같고, 모든 GT가 예측 하나와만 매칭되며, unmatched prediction과
duplicate가 없어야 한다. SEMR과 함께 IoU 0.50, 0.75, 0.90 결과를
별도로 보고해 좌표 품질을 감시한다.

### 12.2 보고 지표

- Scan Exact Match Rate
- GT recall
- False positives per image
- Duplicates per image
- 한 객체를 두 box로 나눈 오류
- 두 객체를 한 box로 합친 오류
- IoU 0.50, 0.75, 0.90
- 제품 개수별 SEMR
- touching/overlap별 SEMR
- 20개 제품별 detector recall
- 빈 트레이 false-positive rate

### 12.3 Acceptance 합격 조건

전체 acceptance set과 다음 모든 구간에서 누락, 오검출, 중복이 각각
0건이어야 한다.

- 빈 트레이
- touching
- overlap
- 트레이 가장자리
- 최대 제품 수
- 20개 각 제품

3,000장의 독립 샘플에서 오류 0건은 대략 95% 신뢰수준에서 실패율의
상한을 약 0.1%로 제한한다. 더 높은 신뢰도를 주장하려면 acceptance
데이터를 수만 장으로 확대한다.

### 12.4 Ablation

다음 누적 구성을 동일 fold에서 비교한다.

```text
D-FINE 단독
RTMDet 단독
두 detector 병합
+ Crop Verifier
+ Foreground Coverage
+ 640 audit
+ 고해상도 tile recovery
```

SEMR 또는 필수 시나리오 오류를 개선하지 않는 단계는 제거한다.

## 13. CPU 배포 검증

1. PyTorch FP32 기준 출력을 저장한다.
2. 두 detector와 verifier를 OpenVINO FP32로 변환한다.
3. 동일 이미지에서 box 수, 좌표, score, verifier 상태를 비교한다.
4. 전체 acceptance set에서 PyTorch와 OpenVINO의 최종 SEMR이 같은지
   확인한다.
5. 동일성 검증을 통과한 뒤에만 BF16, FP16 또는 INT8을 평가한다.
6. 양자화로 최종 결과가 한 건이라도 바뀌면 정확도 우선 형식을 유지한다.

## 14. 운영 로그와 재학습

각 스캔은 다음 정보를 기록한다.

```json
{
  "image_id": "traceable-id",
  "detector_versions": {
    "primary": "dfine-n-768-version",
    "secondary": "rtmdet-tiny-768-version"
  },
  "verifier_version": "box-verifier-version",
  "threshold_version": "solver-threshold-version",
  "raw_candidates": [],
  "final_boxes": [],
  "uncovered_foreground_ratio": 0.0,
  "decision_quality": 0.0,
  "conflict_codes": [],
  "inference_ms": 0
}
```

카메라 기준점, 빈 트레이 색상 분포, 초점과 노출을 감시한다. 입력을
거부하지는 않지만 기준에서 벗어난 스캔, detector 충돌, `partial`,
`multiple`, tile recovery 실행 사례는 hard-case 큐에 우선 저장한다.

재학습은 기존 acceptance set을 회귀 테스트로 유지하면서 새로운 잠긴
acceptance set을 추가해 버전 단위로 수행한다. 모델, 데이터 manifest,
threshold 및 OpenVINO artifact 버전을 함께 관리한다.

## 15. 주요 위험과 대응

| 위험 | 대응 |
|---|---|
| 두 detector가 같은 빵을 동시에 누락 | 전경 coverage, 저점수 후보 복구, tile inference |
| 두 빵을 하나로 병합 | verifier `multiple`, 이종 detector 분리 가설, tile inference |
| 한 빵을 두 개로 분리 | 후보 관계 그래프, verifier, 전역 solver |
| 손·집게·포장지 오검출 | 빈 트레이와 방해물 hard negative |
| 유사 장면 데이터 누수 | `(batch, scene)` 그룹 분할 |
| Verifier가 detector 훈련 오류를 암기 | out-of-fold prediction만 사용 |
| 배포 변환 후 결과 변화 | PyTorch/OpenVINO 전체 acceptance 동등성 검사 |
| 카메라·조명 drift | 기준점, 초점, 노출, 배경 분포 모니터링 |
| 절대 100%로 오해 | SEMR, 표본 수, 신뢰한계와 적용 분포를 함께 보고 |

## 16. 외부 근거

- D-FINE 공식 구현 및 모델 표:
  https://github.com/Peterande/D-FINE
- D-FINE 논문:
  https://arxiv.org/abs/2410.13842
- RTMDet 논문:
  https://arxiv.org/abs/2212.07784
- MMDetection RTMDet 설정:
  https://github.com/open-mmlab/mmdetection/tree/main/configs/rtmdet

D-FINE-N의 공식 COCO 결과는 42.8 AP, 약 4M parameters이고,
RTMDet-Tiny는 41.1 AP, 약 4.8M parameters이다. 이 수치는 구조 후보를
선정하는 참고값이며, bakery 데이터의 최종 선택은 본 문서의 동일 조건
실험과 SEMR로 결정한다.
