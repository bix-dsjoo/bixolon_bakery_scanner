# RTX 5080 15+5 Single-Frame Risk-Controlled Inference 설계

**상태:** 2026-08-03 사용자 승인

**설계 책임:** 현재 15+5 데이터만 사용해 단일 상단 프레임에서 bakery SKU, count와 canonical location을 추론하는 RTX 5080 후보를 정의한다. 검출·분류 오류와 불완전한 장면은 fail-closed로 차단하고, 모든 유효 경로의 warmed p95를 100ms 이하로 제한한다.

**대표 수락 시험:** grouped 5-fold OOF에서 accepted scan critical failure와 wrong auto approval이 각각 0건이고 utility floor를 통과하며, RTX 5080 E/M/H·전체·DINO·retake·Unknown 경로의 warmed p95가 모두 100ms 이하여야 한다.

## 1. 문서 권한과 범위

이 문서는
[2026-08-03-risk-controlled-bakery-inference-v2-design.md](./2026-08-03-risk-controlled-bakery-inference-v2-design.md)의
추상적인 risk-control 구조를 현재 데이터와 RTX 5080 실행 조건에 맞춰
구체화한 versioned GPU 후보 설계다.

- 기존 v2의 capture, scene completeness, selective approval, Unknown,
  immutable receipt와 admission 원칙을 유지한다.
- 입력은 고정 상단 카메라의 단일 프레임으로 고정한다.
- SKU catalog는 기존 15종과 incremental 5종을 합친 동일한 20종이다.
- location은 별도 선반 ID가 아니라 canonical box, 정규화 중심점과
  deterministic object order다.
- 학습·보정·평가는 현재 datasets 아래 데이터만 사용한다.
- pretrained architecture와 외부 checkpoint는 사용할 수 있지만 모든
  checkpoint, engine, support와 policy identity를 hash-bound한다.
- 기존 canonical CPU, portable_cpu_smoke와 legacy GPU 동작은 변경하지 않는다.
- 이 후보는 별도의 pipeline config와 artifact ID를 사용한다.

현재 데이터에는 독립 locked set과 non-target 장면이 없고 accepted scan
2,995개도 없다. 따라서 성공 상태는 development-complete /
production-unverified이며 production risk upper bound나 non-target rejection을
주장하지 않는다.

## 2. 현재 데이터 근거

### 2.1 분류 데이터

| 역할 | SKU | 단독 이미지 |
| --- | --- | ---: |
| base | 1, 2, 3, 5, 7, 8, 10, 11, 12, 13, 14, 17, 18, 19, 20 | SKU별 84장, 총 1,260장 |
| incremental | 4, 6, 9, 15, 16 | SKU별 5장, 총 25장 |

### 2.2 혼합 장면 COCO 데이터

| source | images | boxes | classes |
| --- | ---: | ---: | ---: |
| group_15class | 90 | 379 | 15 |
| group_20class_batch01 | 103 | 506 | 20 |
| group_20class_batch02 | 106 | 521 | 20 |
| 합계 | 299 | 1,406 | 20 |

- E 100장, M 99장, H 100장이다.
- 한 장에는 3~7개 객체가 있고 median은 4~5개다.
- image shape은 3024×4032 또는 4284×5712다.
- incremental 5종은 혼합 장면에서 총 337개 box를 갖는다.
- SKU별 scene box는 최소 57개, 최대 89개다.
- COCO annotation은 image_id, category_id, bbox, area와 iscrowd를 가진다.
- COCO bbox는 xywh이며 runtime과 평가 전에 canonical xyxy로 변환한다.

단독 이미지 5장만 반복 학습하지 않는다. incremental 5종의 training-fold
scene crop을 주된 보강 근거로 사용하고, 단독 이미지는 view anchor와 DINO
support로 사용한다.

## 3. 전체 아키텍처

~~~mermaid
flowchart TB
    subgraph DATA["15+5 학습 데이터"]
        BASE["기존 15종<br/>각 84장"]
        INC["추가 5종<br/>각 5장"]
        SCENE["혼합 장면 299장<br/>20종 · 1,406 boxes · E/M/H"]
        SPLIT["장면 묶음 기반<br/>5-fold OOF"]

        SCENE --> SPLIT
        SPLIT --> DETDATA["RF-DETR-L 검출 데이터"]
        SPLIT --> CROPS["training-fold GT crop"]
        BASE --> CLSDATA["RepViT 20종 학습"]
        INC --> CLSDATA
        CROPS --> CLSDATA
        BASE --> SUPPORT["DINOv3 support bank"]
        INC --> SUPPORT
        CROPS --> SUPPORT
    end

    subgraph RUNTIME["RTX 5080 단일 프레임 추론"]
        PLACE["사용자가 빵을<br/>트레이에 배치"] --> CAPTURE["단일 프레임 촬영"]
        CAPTURE --> CANON["GPU decode·EXIF transpose<br/>canonical RGB"]
        CANON --> DETECT["RF-DETR-L<br/>bread box 검출"]
        CANON --> FOREGROUND["Tray foreground<br/>coverage evidence"]

        DETECT --> COMPLETE{"Scene completeness<br/>검증 통과?"}
        FOREGROUND --> COMPLETE

        COMPLETE -->|"가림·겹침·잘림<br/>미검출 foreground<br/>촬영 품질 불확실"| RETAKE["needs_retake<br/>부분 결과 확정 금지"]
        RETAKE --> GUIDE["재배치 안내<br/>문제 영역·사유 표시"]
        GUIDE --> REPLACE["사용자 재배치"]
        REPLACE --> CAPTURE

        COMPLETE -->|"통과"| CROP["검증된 모든 box<br/>tight + context GPU crop"]
        CROP --> REP["RepViT-M1<br/>20종 점수"]
        REP --> DIRECT{"Class-wise<br/>직접 승인 Gate"}
        DIRECT -->|"통과"| AUTO1["등록 SKU<br/>direct_approved"]
        DIRECT -->|"거절"| DINO["DINOv3<br/>global + local evidence"]
        DINO --> FUSION{"Immutable fusion<br/>합의 통과?"}
        FUSION -->|"통과"| AUTO2["등록 SKU<br/>consensus_approved"]
        FUSION -->|"실패"| UNKNOWN["Unknown<br/>exact ranked Top3"]
    end

    DETDATA -. "detector artifact" .-> DETECT
    CLSDATA -. "classifier artifact" .-> REP
    SUPPORT -. "prototype/local bank" .-> DINO

    AUTO1 --> RESULT["최종 객체 결과"]
    AUTO2 --> RESULT
    UNKNOWN --> RESULT
    RESULT --> AGG["SKU별 수량<br/>Unknown 별도 수량"]
    AGG --> LOCATION["canonical bbox<br/>정규화 중심점<br/>deterministic order"]
    LOCATION --> RECEIPT["Immutable decision receipt"]
    RECEIPT --> STATUS["development-complete<br/>production-unverified"]
~~~

## 4. 입력과 canonical location

### 4.1 Core worker 경계

100ms 경계는 encoded JPEG bytes가 worker memory에 전달된 순간부터 validated
result payload가 memory에 완성될 때까지다.

포함:

- JPEG decode, EXIF transpose와 RGB canonicalization
- detector, completeness evidence와 box normalization
- GPU crop, RepViT와 conditional DINO
- selective Gate, fusion, Unknown과 exact Top3
- count, location, provenance와 payload validation

제외:

- camera exposure와 frame acquisition
- file-system read/write
- 사용자 재배치와 재촬영 시간
- UI render와 catalog 입력 시간
- engine build, 최초 load와 warm-up

제외 구간도 별도의 scan-to-visible receipt에 기록하며 core timing과 섞지 않는다.

### 4.2 Canonical frame과 box

- EXIF transpose 후 RGB visual image가 유일한 canonical coordinate frame이다.
- detector input resize와 padding transform은 invertible provenance를 남긴다.
- 모든 box는 finite, valid, in-bounds xyxy로 canonical frame에 역변환한다.
- COCO GT xywh도 같은 canonical xyxy로 변환한 뒤 평가한다.
- transform parity를 증명할 수 없으면 scan을 수락하지 않는다.

### 4.3 Location

각 객체는 다음 location을 가진다.

- box_xyxy: canonical pixel 좌표
- center_normalized: center_x / width, center_y / height
- object_order: center_y_norm, center_x_norm, x_min, y_min의 오름차순

object_order는 SKU나 confidence를 사용하지 않는다. 동일한 box set에서는 항상
동일해야 한다.

## 5. Grouped 5-fold OOF

### 5.1 Group identity

분할 전에 batch와 filename의 capture number로 scene_group_id를 만든다.
같은 source batch에서 E/M/H capture number가 같은 항목은 같은 group으로
취급한다. Metadata와 perceptual hash로 near-duplicate를 검사하고 발견된
group은 합친다.

### 5.2 Fold 생성

- SKU, E/M/H, object count, image shape가 최대한 균형을 이루도록 group 단위
  iterative stratification을 사용한다.
- seed와 fold manifest를 Git에 고정한다.
- 각 회차는 3 train folds, 1 calibration fold, 1 evaluation fold다.
- rotation 후 모든 장면이 정확히 한 번 evaluation 대상이 된다.
- evaluation image와 crop은 model training, support, threshold 또는 policy
  선택에 사용하지 않는다.

단독 이미지는 auxiliary development source다. 모든 fold에서 training과
support에 사용할 수 있지만 scene OOF evaluation에는 포함하지 않는다.
단독 이미지와 scene의 물리적 product-instance 관계를 확인할 metadata가
없다는 제한을 receipt에 기록한다.

### 5.3 기존 artifact 사용 제한

현재 RF-DETR bakery checkpoint와 threshold는 299장 전체를 이미 사용했으므로
새 OOF candidate나 evaluation에 재사용하지 않는다. 동일 split에서 baseline을
재생성하거나 기존 artifact를 비수락 참고값으로만 사용한다.

## 6. 모델과 학습

### 6.1 RF-DETR-L class-agnostic detector

- COCO의 20개 category를 detector training 시 단일 bread category로 remap한다.
- 원래 category_id는 classifier crop label로 보존한다.
- RF-DETR-L은 localization과 bread objectness만 담당한다.
- detector class logits는 최종 SKU 결정에 사용하지 않는다.
- threshold와 box postprocess는 fold calibration에서 고정하고 최종 candidate
  manifest에 기록한다.
- detector는 TensorRT FP16 candidate로 export하고 FP32 reference와 별도
  calibrated candidate로 취급한다.

### 6.2 RepViT-M1 unified 20-way classifier

- active class map은 SKU 1~20의 canonical 순서다.
- training-fold GT box에서 tight crop과 deterministic context crop을 만든다.
- 단독 이미지와 scene crop을 class-balanced, source-balanced sampling한다.
- 모든 crop transform은 canonical RGB에서 수행하고 manifest에 hash-bound한다.
- tight/context Top-1 disagreement는 직접 승인을 금지한다.
- SKU별 confidence, margin, prototype distance와 disagreement limit를 calibration
  fold에서 고정한다.
- 직접 승인 영역을 찾지 못한 SKU는 direct Gate를 비활성화한다.

### 6.3 DINOv3 global/local evidence

- fold별 support는 단독 이미지와 training-fold scene crop만 사용한다.
- class별, source별 global prototype과 local patch 수를 제한한다.
- calibration/evaluation crop은 support bank에 포함하지 않는다.
- 한 번의 DINO backbone pass에서 global token과 local patch token을 모두
  추출한다.
- 거절 crop 전체를 한 batch로 처리하고 object별 forward를 금지한다.

### 6.4 Final artifact

OOF architecture, preprocessing과 policy selection procedure를 고정한 뒤 전체
299장으로 final detector와 classifier를 학습하고 support bank를 다시 만든다.
OOF quality report는 각 evaluation fold에 대응하는 fold-specific calibration
policy만 사용한다. Final train-all policy는 OOF report를 동결한 뒤 pooled
calibration evidence로 한 번 생성하며 OOF 품질 수치 계산에 되먹이지 않는다.
최종 모델과 policy가 OOF fold candidate와 다르므로 locked 또는 production
evidence로 승격하지 않는다.

## 7. Scene completeness와 재배치

Detector가 출력하지 않은 객체에는 detector confidence가 없다. 따라서 SKU
판정 전에 scene 전체를 별도 검증한다.

### 7.1 Evidence

- tray ROI와 tray boundary
- detector box의 finite/in-bounds 상태
- box별 truncation과 canonical area
- foreground 영역의 predicted-box coverage
- unexplained foreground area
- box overlap, possible split와 possible merge
- blur, exposure와 reflection
- object count profile 3~7

Foreground evidence는 객체를 새로 만들거나 SKU를 결정하지 않는다. Detector
box로 설명되지 않는 foreground가 있으면 retake를 요구하는 보수적 guard다.

### 7.2 Retake reason

- no_target_detected
- object_count_out_of_profile
- uncovered_foreground
- overlap_or_occlusion
- possible_split
- possible_merge
- truncated_object
- capture_quality_unverified
- completeness_risk_exceeded

하나라도 발생하면 scan 전체가 needs_retake다. 일부 box, SKU 또는 count를
확정하지 않는다.

### 7.3 재배치 loop

- 새 촬영은 새 scan_id를 받는다.
- 같은 시도의 연쇄는 retake_chain_id로 연결한다.
- UI는 문제 영역과 machine-readable reason을 표시한다.
- 사용자는 겹친 빵을 분리하고 트레이 안쪽으로 옮긴 뒤 재촬영한다.
- 3회 연속 실패하면 자동 scan을 종료하고 full catalog 수동 입력으로 전환한다.
- 이전 시도의 partial inference는 주문과 자동 정확도에 포함하지 않는다.

## 8. SKU 판정과 fail-closed acceptance

### 8.1 RepViT 직접 승인

다음 조건을 모두 만족할 때만 registered SKU를 direct_approved로 확정한다.

- tight/context crop Top-1 일치
- active catalog에 존재
- SKU별 calibrated confidence 하한 통과
- SKU별 Top-1/Top-2 margin 하한 통과
- prototype distance 상한 통과
- crop disagreement 상한 통과
- calibration이 검증한 difficulty와 box-size envelope 안
- artifact, preprocessing과 policy hash 일치

### 8.2 Conditional DINO와 fusion

Direct Gate에서 거절된 객체만 DINO를 실행한다. Immutable fusion이 선택한 SKU는
다음 중 하나를 만족할 때만 consensus_approved다.

~~~text
fusion SKU == DINO local Top-1
OR
RepViT global Top-1 == DINO global Top-1 == fusion SKU
AND fusion margin >= 0.85
~~~

Evidence가 누락되거나 합의 조건이 실패하면 반드시 Unknown이다. 가장 가까운
prototype이나 arbitrary registered SKU로 대체하지 않는다.

### 8.3 Unknown과 user resolution

- Unknown은 sku_id가 null이고 sku_name은 Unknown이다.
- exact ranked Top3는 길이 3, rank 1~3, 중복 없는 active SKU만 포함한다.
- Top3 miss에는 full catalog search를 제공한다.
- customer_top3와 customer_catalog는 immutable inference와 별도의 audited
  resolution이다.
- user resolution은 자동 정확도나 auto-approval coverage로 재분류하지 않는다.
- resolution persistence 실패 시 주문 반영을 금지한다.

## 9. Output contract

### 9.1 Scan

~~~json
{
  "scan_id": "scan-0142",
  "retake_chain_id": "retake-0041",
  "state": "accepted_scan",
  "object_total": 5,
  "registered_object_total": 4,
  "unknown_total": 1,
  "sku_totals": {"15": 1, "18": 3},
  "objects": [],
  "runtime_profile_id": "rtx5080_trt_fp16_static7_v1",
  "receipt_id": "receipt-0142"
}
~~~

needs_retake에는 final objects와 sku_totals를 생성하지 않고 reasons와 problem
regions만 반환한다.

### 9.2 Object

~~~json
{
  "object_id": "scan-0142:003",
  "sku_id": 15,
  "sku_name": "Sandwich",
  "state": "auto_approved",
  "decision_path": "consensus_approved",
  "location": {
    "box_xyxy": [1698.67, 1221.28, 3578.95, 2661.53],
    "center_normalized": [0.6158, 0.3399],
    "object_order": 3
  },
  "confidence": {
    "detector_calibrated": 0.994,
    "sku_acceptance_calibrated": 0.999,
    "fusion_margin": 0.91
  },
  "provenance": {
    "detector_artifact_id": "rfdetr_l_bread_gpu_fp16_v1",
    "repvit_artifact_id": "repvit_m1_15plus5_gpu_fp16_v1",
    "dinov3_artifact_id": "dinov3_vits16_15plus5_gpu_fp16_v1",
    "fusion_policy_id": "fusion_15plus5_oof_v1",
    "runtime_profile_id": "rtx5080_trt_fp16_static7_v1"
  }
}
~~~

confidence는 raw softmax가 아니라 policy artifact가 정의한 calibrated evidence다.
Unknown은 sku_id null과 exact Top3를 갖고 sku_acceptance_calibrated는 null이다.

### 9.3 Aggregation

~~~text
registered_sku_totals = direct_approved + consensus_approved
unknown_total = Unknown object count
detected_object_total = sum(registered_sku_totals) + unknown_total
~~~

Unknown과 customer resolution은 immutable SKU totals와 자동 주문에 포함하지 않는다.

## 10. RTX 5080 p95 100ms hard contract

### 10.1 Runtime form

- RTX 5080 전용 TensorRT FP16 engine
- RF-DETR-L, RepViT와 DINO static-shape profile
- verified object-count envelope 3~7
- detector input, RepViT batch 14와 DINO batch 7의 고정 buffers
- startup preallocation과 buffer reuse
- GPU crop, padding mask와 score processing
- object별 Python/model call 금지
- CPU/GPU 중간 왕복 금지
- CUDA Graph 적용
- detector와 completeness evidence를 별도 CUDA stream에서 병렬 실행
- DINO global/local evidence를 단일 backbone pass에서 생성
- TensorRT 불가 시 PyTorch/CPU silent fallback 금지

8개 이상 또는 3개 미만 객체는 dynamic profile을 만들지 않고
object_count_out_of_profile로 retake한다.

### 10.2 Stage budget

| stage | p95 budget |
| --- | ---: |
| GPU decode, EXIF와 canonicalization | 10ms |
| RF-DETR-L | 36ms |
| completeness evidence | 6ms, detector와 중첩 |
| GPU crop tensor | 4ms |
| RepViT batch | 12ms |
| direct Gate | 2ms |
| conditional DINO batch | 18ms |
| fusion, aggregate, Top3와 payload | 6ms |
| scheduling와 synchronization headroom | 8ms |
| DINO 포함 worst path | 96ms |
| direct path | 78ms |

Stage budget은 구현의 조기 중단 기준이다. 최종 수락은 stage p95 합이 아니라
sample별 wall-clock total distribution으로 결정한다.

### 10.3 Path-independent acceptance

DINO 실행률이 낮다는 이유로 전체 p95에서 숨기지 않는다. 다음 모두가 각각
warmed p95 100ms 이하여야 한다.

- E
- M
- H
- 전체
- DINO 실행 scan
- needs_retake scan
- Unknown scan

정확도 또는 fail-closed Gate를 느슨하게 해 latency를 맞추지 않는다. Smaller
detector, lower input 또는 더 낮은 precision은 별도 accuracy/calibration candidate다.

## 11. Calibration

각 fold의 calibration data만 사용해 다음을 고정한다.

- detector score threshold와 postprocess
- foreground coverage 하한
- truncation, overlap, split와 merge 위험 기준
- capture quality threshold
- RepViT SKU별 confidence와 margin
- prototype distance와 crop disagreement
- DINO global/local evidence transform
- fusion ranker와 acceptance policy
- retake, auto-approval, Unknown utility floors

GT box 제거, 이동, 병합과 분할로 counterfactual completeness evidence를 만든다.
이는 실제 detector miss가 아니라 contract stress test로 분리 보고한다.

## 12. OOF quality acceptance

### 12.1 Matching

- canonical frame IoU 0.50
- deterministic one-to-one matching
- unmatched GT는 miss
- extra prediction은 duplicate 또는 non-target
- one-to-many와 many-to-one 관계에서 split과 merge를 별도 attribution
- 같은 input, model과 policy에서 동일 ordering과 match를 재현

### 12.2 Primary Gate

~~~text
accepted_scan_critical_failure =
    box miss
    OR duplicate
    OR split
    OR merge
    OR detected object count mismatch
    OR object-order mismatch
    OR wrong auto-approved SKU
~~~

수락 조건:

- accepted_scan_critical_failure 관측 0건
- wrong auto-approved SKU 관측 0건
- accepted scan의 detected object total과 GT object count 모두 일치
- object order 모두 일치
- Unknown이 SKU totals에 포함된 사례 0건

Unknown은 wrong SKU가 아니다. needs_retake는 primary accepted-scan error에서
제외하되 utility Gate에서 제한한다.

299개 scan에서 오류 0건이어도 단측 95% upper bound는 약 1%다. 1,406개
object에서 오류 0건이어도 약 0.21%다. 이 결과를 0.1% production 주장으로
사용하지 않는다.

### 12.3 Utility Gate

| metric | overall | E/M/H each |
| --- | ---: | ---: |
| normal scan acceptance | ≥80% | ≥70% |
| unnecessary retake | ≤20% | ≤30% |
| auto SKU approval coverage | ≥70% | ≥60% |
| Unknown rate | ≤30% | ≤40% |
| Unknown Top3 recall | ≥95% | ≥90% |

- incremental 5종 전체 auto-approval coverage는 최소 50%다.
- SKU별 coverage와 wrong approval을 별도 보고한다.
- wrong auto approval이 하나라도 있으면 utility와 무관하게 실패다.
- 동일 OOF baseline이 고정 floor보다 높으면 더 높은 baseline 수치를 floor로
  사용한다.

### 12.4 Completeness와 Top3

- counterfactual missing/split/merge/truncation 차단율 100%
- counterfactual 결과를 실제 miss recall로 재해석하지 않음
- OOF Unknown의 exact Top3 schema violation 0건
- Top3 recall overall 95% 이상
- rank 1/2/3 hit와 catalog fallback을 별도 보고

Non-target image가 없으므로 non-target rejection은 unverified다.

## 13. Performance acceptance

RTX 5080에서 실제 final engine과 policy로 측정한다.

| slice/path | minimum warmed observations | acceptance |
| --- | ---: | ---: |
| E | 1,000 | p95 ≤100ms |
| M | 1,000 | p95 ≤100ms |
| H | 1,000 | p95 ≤100ms |
| overall | 3,000 | p95 ≤100ms |
| DINO path | 1,000 | p95 ≤100ms |
| needs_retake path | 1,000 | p95 ≤100ms |
| Unknown path | 1,000 | p95 ≤100ms |

299개 장면을 고정 순서로 반복한다. 경로 표본이 부족하면 실제 해당 경로
scan을 고정 순서로 반복한다. 경로가 전혀 발생하지 않으면 forced-path
performance stress를 별도 실행하고 품질 지표와 섞지 않는다.

필수 보고:

- p50, p90, p95, p99, max와 p95 bootstrap CI
- decode, detector, completeness, crop, RepViT, DINO, fusion와 payload timing
- object count별 latency와 DINO invocation rate
- direct, DINO, retake와 Unknown path별 latency
- GPU memory peak, clock, power, temperature와 thermal throttling
- driver, CUDA, TensorRT, Windows/WDDM와 engine identity
- engine load, warm-up와 startup
- silent fallback 0건

## 14. Artifact와 runtime admission

다음을 SHA-256, byte size, artifact ID, storage class와 expected path로 고정한다.

- fold와 data manifest
- canonical preprocessing와 crop transform
- RF-DETR checkpoint, ONNX와 TensorRT engine
- RepViT checkpoint, prototype와 TensorRT engine
- DINO weights, support, local bank와 TensorRT engine
- calibration과 fusion policy
- class map과 active catalog snapshot
- CUDA, TensorRT, driver와 GPU compatibility profile
- code commit, seed와 build recipe

Admission 실패 시 추론을 시작하지 않는다. Benchmark는 unverified, production은
명시적으로 승인된 last-known-validated mode만 사용할 수 있다. 이 설계의
development candidate는 자동 rollback 대상이 아니며 실행 실패를 명시적으로
반환한다.

## 15. Error handling

- frame identity 또는 transform 불일치: request failure
- invalid/non-finite detector box: partial output 없이 scan result 전체 거부
- detector/foreground completeness 부족: needs_retake
- box/crop/evidence count 불일치: result 생성 중단
- score/timing non-finite: result와 receipt 거부
- SKU risk evidence 부족: Unknown
- Top3/catalog schema 불일치: user resolution 차단
- engine/hash/runtime mismatch: admission_failed
- GPU OOM/CUDA/TensorRT 오류: result 생성 중단
- partial object output, silent truncation과 arbitrary SKU: 금지
- user resolution persistence 실패: 주문 반영 금지

## 16. Test strategy

### 16.1 Unit/contract

- COCO xywh에서 canonical xyxy 변환
- EXIF orientation과 RGB parity
- finite/in-bounds box normalization
- foreground coverage와 retake reason
- object count 2와 8의 profile 차단
- tight/context crop ordering과 padding mask
- RepViT direct Gate 경계
- DINO global/local single forward
- fusion local 또는 global consensus와 margin 0.85
- exact Top3와 catalog validation
- registered count와 Unknown 분리
- deterministic object order와 aggregation
- retake_chain_id와 3회 manual escalation
- exact binomial upper bound

### 16.2 OOF and integration

- scene group와 near-duplicate fold isolation
- evaluation crop의 training/support 유입 차단
- fold manifest, seed와 hash reproducibility
- observed detector error와 counterfactual stress 분리
- TensorRT engine binding, shape와 dtype
- max object static buffer와 padding
- corrupt/missing artifact
- CUDA error와 fallback 차단
- FP32 reference와 FP16 candidate의 raw evidence 및 final-decision report

### 16.3 Performance

- E/M/H와 overall minimum observations
- DINO, retake와 Unknown path minimum observations
- wall-clock total distribution
- stage timing, GPU state와 thermal evidence
- cold load/warm-up 별도 보고

### 16.4 Compatibility

- canonical CPU config와 behavior 비변경
- portable_cpu_smoke 파일과 behavior 비변경
- legacy GPU config와 behavior 비변경
- public repository에 dataset, checkpoint, engine와 raw receipt 유입 차단

Skipped 또는 unavailable suite는 passed가 아니라 unverified다.

## 17. Delivery order

1. Data audit, group identity와 immutable 5-fold manifest
2. Output, retake, timing과 receipt contracts
3. Class-agnostic RF-DETR FP32 OOF reference
4. RepViT 20-way OOF training과 direct Gate evidence
5. DINO support/local bank와 immutable fusion
6. Completeness Gate와 counterfactual stress
7. TensorRT FP16 export, GPU batching와 CUDA Graph
8. OOF quality와 utility receipt
9. RTX 5080 performance receipt
10. Final train-all development artifact와 compact conclusion

각 단계에서 artifact, quality 또는 latency Gate가 실패하면 다음 단계 위에
최적화를 쌓지 않는다.

## 18. Completion

~~~text
OOF accepted-scan critical failure == 0
AND wrong auto approval == 0
AND utility floors pass
AND Top3 Gate passes
AND E/M/H/overall/DINO/retake/Unknown p95 <= 100ms
AND artifact and runtime admission pass
AND required tests pass
→ development-complete / production-unverified
~~~

실패 상태는 quality-rejected, utility-rejected, performance-rejected,
artifact-rejected 또는 unverified 중 하나로 명시한다.

## 19. 비목표

- 현재 데이터만으로 production 0.1% risk claim
- non-target 장면 없이 non-target rejection claim
- multi-frame 또는 multi-camera completeness
- 8개 이상 객체를 dynamic allocation으로 처리
- latency를 위해 detector, input size 또는 acceptance accuracy를 조용히 축소
- Unknown을 arbitrary SKU로 대체
- user correction을 자동 정확도로 재분류
- dataset, checkpoint, TensorRT engine 또는 raw receipt를 Git에 커밋
- canonical CPU나 legacy pipeline을 조용히 변경
