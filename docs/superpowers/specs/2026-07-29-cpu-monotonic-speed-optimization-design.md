# CPU 단조 개선형 속도 최적화 설계

## 목적

현재 확정된 CPU 추론 파이프라인의 정확한 객체 결과를 하한으로 고정하고,
현재 정답 객체를 하나도 훼손하지 않는 범위에서 end-to-end 평균 및 p95
지연을 가능한 만큼 줄인다. 속도가 빨라도 신규 오인, FP, FN, `Unknown`
또는 기존 정답 객체의 회귀가 발생하면 해당 최적화는 채택하지 않는다.

최종 CPU 경로는 다음과 같다.

```text
입력 이미지
  -> EXIF orientation 적용 및 canonical RGB 변환
  -> RF-DETR-L CPU/FP32
  -> calibration threshold와 product box 검증
  -> RepViT-M1 3-padding crop 추론
  -> direct gate
  -> 미확정 객체만 DINOv3 ViT-S/16 global + local evidence
  -> 기존 불변 fusion
  -> SKU 또는 Unknown
```

## 현재 기준선

기준 모델과 정책은 다음 artifact로 고정한다.

- detector: `rfdetr_large_bakery_v1`
- detector score threshold: `0.5691395401954651`
- detector calibration:
  `calibration_corrected_gt_299_fp0_20260729.json`
- detector calibration SHA-256:
  `96eea207e916f51b55ec8170488e19f495e08f049de1a9304d14707d95e7d12d`
- classifier config: `configs/cpu_rfdetr_classifier_policy.yaml`
- RepViT: `repvit_m1_15plus5_v1`
- DINOv3: `dinov3_vits16_15plus5_v1`
- fusion: `fusion_local_or_global_consensus_margin_v1`
- 평가 IoU: `0.50`

현재 workspace의 수정된 299장 annotation은 1,406개 GT 객체를 포함한다.
기존 원시 측정 결과를 이미지 파일명의 E/M/H 토큰으로 다시 집계한 정확도
기준선은 다음과 같다.

| 구간 | 이미지 | GT | Top-1 | Top-3 | FP | FN | Unknown |
|---|---:|---:|---:|---:|---:|---:|---:|
| E | 100 | 410 | 409 | 410 | 0 | 0 | 1 |
| M | 99 | 496 | 477 | 490 | 0 | 4 | 14 |
| H | 100 | 500 | 463 | 490 | 0 | 1 | 33 |
| 전체 | 299 | 1,406 | 1,349 | 1,390 | 0 | 5 | 48 |

오류 상태는 서로 구분해 기록한다.

- Top-3 Candidate `Unknown`: 41건
- Candidate out: 11건
  - Candidate out `Unknown`: 7건
  - 확정 SKU 오인: 4건
- segmentation failure: 5건
- 확정 SKU 오인 매핑:
  - SKU 2 -> SKU 6
  - SKU 6 -> SKU 19
  - SKU 17 -> SKU 16
  - SKU 4 -> SKU 6

현재 단일 원시 측정의 전체 평균은 `1,485.3 ms`, p95는 `2,058.7 ms`다.
평균 단계 시간은 canonical 전처리 `141.2 ms`, RF-DETR `337.3 ms`,
분류 `1,006.8 ms`다. 이 수치는 병목 위치를 보여 주는 참고값이다. 정식
성능 하한은 동일한 측정 harness로 299장을 최소 3회 반복한 결과로 다시
고정한다.

## 정확도 보존 원칙

집계 지표가 우연히 같더라도 현재 정답 객체가 다른 실패로 바뀌면 회귀다.
따라서 최적화 결과는 canonical-frame IoU `0.50` 일대일 매칭 후 객체별로
비교한다. 매칭 후보는 IoU 내림차순, GT image/category/annotation ID,
detector score 내림차순, canonical box 좌표, proposal index 순으로
정렬한다. 동률이나 중복 후보가 있어도 같은 입력은 항상 같은 객체에
매칭되어야 한다.

| 현재 객체 상태 | 허용되는 새 상태 |
|---|---|
| 정답 SKU 확정 | 같은 정답 SKU 확정만 허용 |
| Top-3 Candidate `Unknown` | 정답 SKU 확정 또는 정답이 포함된 Top-3 유지 |
| Candidate out `Unknown` | 정답 SKU 확정, Top-3 Candidate 또는 Candidate out `Unknown` 유지 |
| A -> B 확정 오인 | 정답 SKU 확정 또는 fail-closed `Unknown` |
| segmentation failure | 정답 SKU로 검출·확정 또는 검출된 `Unknown` |
| FP 없음 | 계속 FP 0 |

다음 집계 게이트도 모두 만족해야 한다.

- Top-1은 `1,349 / 1,406` 이상이다.
- Top-3는 `1,390 / 1,406` 이상이다.
- FP는 반드시 0이다.
- FN은 5 이하이다.
- `Unknown`은 48 이하이다.
- A -> B 확정 오인은 4 이하이다.
- 현재 정답 객체의 신규 회귀는 0이다.

현재 실패 객체가 정답으로 바뀌는 것은 허용한다. 현재 A -> B 확정 오인이
`Unknown`으로 바뀌는 것도 잘못된 SKU 확정을 막는 안전 개선으로 본다.
반대로 현재 정답을 잃거나 현재의 안전한 `Unknown`을 잘못된 SKU로
확정하는 변화는 전체 Top-1이 증가하더라도 허용하지 않는다.

## 권장 실행 구조

1차 최적화에서는 가중치, 전처리 규칙, detector threshold, direct gate,
fusion 정책을 변경하지 않는다. 이미지 단위 batch-first 실행과 의미를
보존하는 CPU graph/runtime 최적화만 도입한다.

```text
canonical RGB 이미지
  -> RF-DETR-L 한 번 실행
  -> 모든 유효 객체의 3-padding crop 일괄 생성
  -> RepViT [객체 수 x 3] batch 추론
  -> 객체별 기존 direct gate
       -> 통과 객체: 기존 RepViT 결과
       -> 미통과 객체: DINOv3 batch global + local evidence
  -> 객체별 기존 fusion
  -> SKU 또는 Unknown
```

구성요소의 책임은 다음과 같이 나눈다.

- `CropBatchBuilder`: 객체별 세 padding crop, product box와 원본 객체
  인덱스를 생성한다.
- `RepViTBatchScorer`: 설정된 microbatch 크기로 crop을 추론하고 결과를
  객체별 evidence로 복원한다.
- `DinoBatchRechecker`: direct gate 미통과 객체만 모아 설정된
  microbatch 크기로 global 및 local evidence를 생성한다.
- `DecisionAssembler`: 현재 direct/fusion 정책을 객체별로 그대로
  적용한다.
- `BaselineComparator`: 기준 객체와 새 객체를 일대일 매칭하고 허용 상태
  전이 및 집계 게이트를 검사한다.
- `LatencyRecorder`: canonical 전처리, detector, crop, RepViT, DINO,
  fusion 및 전체 시간을 분리해 기록한다.

serial reference와 batch 경로는 같은 결정 코드를 공유한다. batch 경로가
정책을 복제하거나 별도의 acceptance threshold를 만들면 안 된다.

## 단계별 최적화

### 0단계: 기준선 artifact 고정

현재 299장 평가를 정식 재현 가능한 runner로 실행한다. 기존 원시 보고서의
E/M/H 집계 문제를 수정하고 이미지 및 객체별 결과, A -> B 오인, stage
timing, 모델·정책·데이터 SHA-256을 새 경로에 기록한다. 기존 보고서는
삭제하거나 덮어쓰지 않는다.

### 1단계: PyTorch 실행 구조 최적화

변경을 한 책임씩 나눠 다음 순서로 검증한다.

1. 모델을 프로세스 시작 시 한 번만 로드하고 워밍업한다.
2. inference 전용 실행 모드와 CPU thread/affinity 설정을 탐색하고
   고정한다.
3. crop 생성을 일괄화하고 불필요한 이미지 변환을 제거한다.
4. RepViT를 이미지 내 객체 microbatch로 실행한다.
5. direct gate 미통과 객체만 DINOv3 microbatch로 실행한다.
6. RepViT와 DINOv3에 `torch.compile` CPU FP32를 각각 적용해 eager와
   비교한다.
7. 객체별 기존 fusion 결과를 원래 순서로 복원한다.

현재 측정에서는 DINO 실행률이 100%였으므로, direct gate의 동작을
임의로 완화하지 않는다. 실제 batch runner에서 실행률을 다시 기록하고,
DINO 대상 객체를 일괄 처리해 순차 호출 비용을 줄인다.

CPU batch는 클수록 빠르다고 가정하지 않는다. RepViT와 DINOv3에 대해
microbatch `1`, `2`, `4`, `8`, 이미지 내 전체 객체를 각각 측정한다.
초기 승격 후보는 한 번에 한 이미지만 처리하고 이미지 간 병렬 실행은
금지한다. 각 모델은 자신의 평균뿐 아니라 전체 이미지 p95가 가장 낮은
microbatch를 독립적으로 선택한다.

`torch.compile`은 eager reference와 별도 runtime mode로 측정한다. compile
및 첫 실행 비용은 warm-up에 포함하고 steady-state 측정에서는 제외한다.
compile 실패, graph break, 수치 회귀 또는 p95 악화가 있으면 해당 모델은
eager 실행을 유지한다.

### 2단계: 동일 모델 FP32 백엔드

PyTorch batch 경로가 통과한 뒤 RepViT, DINOv3, RF-DETR 순서로
OpenVINO FP32와 ONNX Runtime FP32를 비교한다. 한 번에 하나의 모델만
변환해 속도와 수치 차이의 원인을 분리한다.

OpenVINO는 CPU `ACCURACY` execution mode, FP32 inference precision,
`LATENCY` performance hint, 단일 inference stream을 기본 후보로 한다.
자동 저정밀 변환과 dynamic quantization은 비활성화한다. ONNX Runtime은
sequential graph execution과 전체 graph optimization부터 측정한다.
XNNPACK을 사용할 때는 ORT intra-op thread를 1로 두고 XNNPACK 자체
threadpool만 물리 core 후보군으로 조정해 두 threadpool의 경합을 막는다.

각 backend는 validation shadow mode에서 기존 PyTorch의 score vector,
순위, margin, 최종 결정을 객체별로 비교한다. 운영 경로가 항상 두
backend를 실행하지 않도록 개발·calibration 데이터에서 policy 경계별
fallback safety band를 정한다. fast backend 출력이 band 안에 있거나
지원되지 않는 연산으로 graph가 분할되면 해당 객체만 PyTorch reference로
보낸다. band 밖에서는 fast backend만 실행한다.

safety band는 SKU acceptance 규칙을 바꾸는 threshold가 아니라 reference
실행 여부만 결정한다. band와 근거 데이터, policy 경계, backend 및
artifact hash를 versioned artifact로 저장한다. locked 데이터에서는 band를
조정하지 않고 검증만 한다. 기존 정답 객체의 backend 불일치가 band
밖에서 발생하면 band를 사후 확장하지 않고 해당 backend 후보를
탈락시킨다.

backend artifact와 변환 옵션은 별도 manifest와 SHA-256으로 고정한다.

RF-DETR 변환은 마지막에 수행한다. 현재 FP 0과 FN 5를 모두 보존하고
현재 정답 객체를 하나라도 잃으면 채택하지 않는다.

### 3단계: 선택적 소형 cascade

앞 단계만으로 추가 단축이 부족할 때만 소형 classifier 또는 student
cascade를 검토한다. 소형 모델은 안전한 조기 확정 후보를 생성하고,
불확실한 객체는 항상 현재 원본 파이프라인으로 보낸다. 원본 경로 없이
소형 모델 단독 결과를 기본 SKU로 확정하지 않는다.

모델, threshold 또는 fusion 정책을 변경하는 단계는 calibration에 사용된
현재 299장만으로 채택하지 않는다. 새 locked 데이터에서도 동일한
비회귀 조건을 통과해야 한다.

multiple-exit, dynamic token pruning, INT8/BF16, knowledge distillation은
이 단계의 연구 후보로만 둔다. DINOv3 local evidence가 patch 특징을
사용하므로 token pruning은 local candidate recall을 별도로 검증한다.
집계 accuracy drop만 제한하는 최적화는 객체별 신규 회귀 0을 보장하지
못하므로 승격 조건으로 충분하지 않다.

### 4단계: detector 변경

RF-DETR-L 교체는 마지막 선택지다. 새 detector는 candidate 경로로
추가하고 현재 detector와 동일 입력에서 비교한다. 299장 및 새 locked
데이터의 객체별 검증을 통과하기 전에는 기본 경로로 승격하지 않는다.

## 성능 측정

성능 측정은 같은 PC와 같은 전원 설정에서 수행한다.

- 모델 로딩은 측정 전에 한 번 수행한다.
- 고정된 워밍업을 실행한 뒤 299장을 최소 3회 반복한다.
- canonical 이미지 로딩부터 최종 객체 결정까지 end-to-end로 측정한다.
- 전처리, RF-DETR, crop, RepViT, DINO, fusion 시간을 분리한다.
- E/M/H별 평균, p50, p95와 전체 평균 및 p95를 기록한다.
- DINO 실행률, 이미지당 객체 수, PyTorch/backend 버전, CPU thread 수,
  CPU affinity, 전원 설정, artifact SHA-256을 기록한다.
- 같은 pass에서 기준선과 후보를 `AB/BA` 순서로 교차 실행한다.
- 각 pass는 고정 seed로 같은 이미지 순서를 사용하되 다음 pass에서는
  순서를 바꿔 cache, 발열 및 시간 경과 편향을 상쇄한다.
- 이미지별 paired 차이의 평균과 p95를 bootstrap으로 재표집해 one-sided
  95% 신뢰구간을 계산한다.

정확도 게이트를 먼저 통과한 후보 중 전체 평균과 p95가 모두 기준선보다
낮고 두 paired 개선량의 one-sided 95% 신뢰구간 상한이 모두 0보다 작은
후보만 속도 개선으로 인정한다. 평균만 낮거나 p95만 낮은 후보, 또는
측정 잡음과 구분되지 않는 후보는 기본 경로로 승격하지 않는다.

## 검증

각 단계의 검증 순서는 다음과 같다.

1. batch index, crop 순서와 결과 복원을 단위 테스트한다.
2. serial과 batch의 RepViT/DINO evidence를 비교한다.
3. direct/fusion 결정이 기존 정책을 그대로 사용하는지 검사한다.
4. 같은 입력을 반복해 결정성과 객체 순서를 검사한다.
5. 299장 객체별 단조 개선 및 집계 게이트를 검사한다.
6. 최소 3회 CPU latency를 측정한다.
7. 모델 또는 정책 변경 시 새 locked 데이터에서 다시 검증한다.

실패 보고서는 회귀 객체의 이미지, GT SKU, 기준 결정, 새 결정, box IoU,
score/margin과 실행 backend를 포함한다. 속도 결과와 정확도 결과는 같은
run identifier 및 artifact hash를 공유해야 한다.

## Rollback과 승격

runtime mode는 다음 경로를 유지한다.

```text
runtime_mode: serial_reference | batch_pytorch | batch_pytorch_compile | batch_openvino | batch_onnx
```

- `serial_reference`: 현재 기준 경로
- `batch_pytorch`: 1차 권장 경로
- `batch_pytorch_compile`: 정확도와 p95 검증을 통과한 compile 경로
- `batch_openvino`: 추가 검증을 통과한 경우에만 사용하는 경로
- `batch_onnx`: 추가 검증을 통과한 경우에만 사용하는 경로

새 경로는 검증 전까지 opt-in이다. 정확도, 결정성, 무결성 또는 latency
게이트 중 하나라도 실패하면 해당 mode를 비활성화하고 직전 통과 경로를
유지한다. 기존 모델, 정책, legacy 코드, serial reference와 기준 보고서는
삭제하거나 덮어쓰지 않는다.

## 완료 기준

작업은 다음 조건을 모두 만족할 때 완료된다.

- 현재 정답 객체의 신규 회귀가 0이다.
- Top-1, Top-3, FP, FN, `Unknown`, A -> B 오인이 모든 하한을 통과한다.
- 전체 평균과 p95가 반복 측정 기준선보다 모두 낮다.
- E/M/H와 stage timing, DINO 실행률이 보고서에 기록된다.
- 결과가 artifact hash와 runtime mode로 재현된다.
- 실패 시 `serial_reference`로 즉시 돌아갈 수 있다.
- 문서, 설정, 테스트와 실제 runtime behavior가 일치한다.

## 연구 및 공식 개발 문서 근거

이 설계는 다음 자료의 원리를 참고하되, 각 자료의 평균 정확도 또는 다른
하드웨어 성능 수치를 이 프로젝트의 성능 주장으로 사용하지 않는다.

- [RF-DETR: Neural Architecture Search for Real-Time Detection Transformers](https://arxiv.org/abs/2511.09554)
  - detector 변경 시 같은 RF-DETR 계열의 accuracy-latency Pareto 후보를
    우선 검토하는 근거다.
- [CF-DETR: Coarse-to-Fine Transformer for Real-Time Object Detection](https://arxiv.org/abs/2505.23317)
  - selective fine inference와 multi-level batch inference 원리를
    batch-first 조건부 재확인 구조에 적용한다.
- [DINOv3](https://arxiv.org/abs/2508.10104)
  - dense feature 품질이 중요한 local evidence 경로를 임의로 pruning하지
    않는 근거다.
- [RepViT: Revisiting Mobile CNN From ViT Perspective](https://arxiv.org/abs/2307.09283)
  - RepViT는 유지하고 실행 graph와 batching을 먼저 최적화하는 근거다.
- [Multiple-Exit Tuning](https://arxiv.org/abs/2409.13999) 및
  [Dynamic Token Pruning](https://arxiv.org/abs/2308.01045)
  - early exit와 token pruning은 가능성이 있지만 별도 학습과 객체별
    회귀 검증이 필요한 연구 단계임을 뒷받침한다.
- [PyTorch CPU Inductor](https://pytorch.org/blog/accelerated-cpu-inference/) 및
  [PyTorch 2.5 release](https://pytorch.org/blog/pytorch2-5/)
  - OpenVINO 변환 전에 `torch.compile` CPU FP32를 독립 후보로 측정하는
    근거다.
- [OpenVINO latency optimization](https://docs.openvino.ai/2026/openvino-workflow/running-inference/optimize-inference/optimizing-latency.html),
  [precision control](https://docs.openvino.ai/2026/openvino-workflow/running-inference/optimize-inference/precision-control.html),
  [post-training quantization](https://docs.openvino.ai/2026/openvino-workflow/model-optimization-guide/quantizing-models-post-training.html)
  - latency mode, FP32 accuracy mode와 quantization의 별도 locked 검증
    원칙을 정하는 근거다.
- [ONNX Runtime threading](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) 및
  [XNNPACK execution provider](https://onnxruntime.ai/docs/execution-providers/Xnnpack-ExecutionProvider.html)
  - graph execution과 threadpool 경합을 모델별로 측정하는 근거다.
