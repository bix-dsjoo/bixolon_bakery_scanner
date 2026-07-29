# CPU Benchmark v3 Reliability Design

## 목적

현재 CPU 최적화 후보는 같은 299장 품질 결과를 유지하면서 일부 실행에서
평균과 p95 latency를 낮췄지만, 핀된 설정 재측정에서는 p95 paired-bootstrap
단측 95% CI 상한이 `+5.50 ms`로 회귀했다. 실행별 serial reference 평균도
`1,519.29 ms`, `1,377.55 ms`, `1,289.67 ms`로 크게 이동했다.

이번 변경의 목적은 새로운 최적화를 승격하는 것이 아니라, serial reference와
candidate의 CPU 전역 상태, 모델 수명주기, 워밍업과 측정 증거를 분리해 다음
최적화 판단에 사용할 수 있는 재현 가능한 benchmark v3를 만드는 것이다.

## 범위

포함 범위는 다음과 같다.

- serial reference와 candidate를 별도의 장기 실행 worker process에서 실행한다.
- 각 worker는 모델을 한 번만 로드하고 고정된 명시적 워밍업을 수행한다.
- 부모 coordinator가 최소 3회 AB/BA 순서를 제어한다.
- 최종 적용 runtime, 실행 환경, 워밍업 및 양쪽 stage timing을 schema v3
  보고서에 기록한다.
- worker 준비, runtime 검증, pass 실행과 종료를 fail-closed로 처리한다.
- fake worker 단위 테스트와 Windows `spawn` 최소 통합 테스트를 추가한다.

다음은 이번 범위에서 제외한다.

- 모델, weight, threshold, calibration, preprocessing 또는 fusion 정책 변경
- RF-DETR-L, RepViT-M1 또는 DINOv3의 연산 최적화
- thread, affinity 또는 microbatch 후보 재탐색
- compile 인코딩 오류 수정 및 compile 후보 재평가
- 운영 runtime 승격 또는 `configs/cpu_rfdetr_classifier_policy.yaml` 변경
- 기존 schema v2 보고서 수정, 삭제 또는 덮어쓰기
- legacy pipeline 변경

## 불변 계약

- `ClassifierPipeline.infer()`의 결정과 직렬 실행 순서는 기준 구현으로 유지한다.
- RF-DETR-L은 CPU/FP32로 실행하고 score threshold는
  `models/rfdetr_large_bakery_v1/manifest.json`에서만 읽는다.
- RepViT/DINO 모델, 전처리, direct gate와 fusion acceptance 정책은 바꾸지
  않는다.
- 품질 게이트는 Top-1 `>= 1,349`, Top-3 `>= 1,390`, FP `= 0`, FN `<= 5`,
  Unknown `<= 48`, 확인된 A-to-B 오분류 `<= 4`를 유지한다.
- 현재 정답 1,349개는 같은 SKU 정답을 유지하고, 안전한 Unknown은 오답 SKU로
  바뀌지 않아야 한다.
- 속도 통과는 299장, 최소 3회 AB/BA, 평균과 p95 point delta가 모두 음수이며
  paired-bootstrap 단측 95% CI 상한도 모두 음수일 때만 인정한다.
- 기존 파일 또는 보고서를 삭제하거나 덮어쓰지 않는다.

## 아키텍처

### Benchmark coordinator

기존 benchmark CLI의 사용자-facing 진입점은 유지하되, 실제 모델 추론은 부모
process에서 실행하지 않는다. coordinator는 Windows `spawn` context로 두
worker를 생성한다.

```text
BenchmarkCoordinator
  |-- serial_reference worker
  |     |-- apply process-global CPU settings once
  |     |-- load detector and classifiers once
  |     |-- execute fixed warm-up
  |     `-- serve RUN_PASS commands
  |
  `-- candidate worker
        |-- apply process-global CPU settings once
        |-- load detector and classifiers once
        |-- execute fixed warm-up
        `-- serve RUN_PASS commands
```

두 worker는 동시에 측정하지 않는다. 한 worker가 한 pass의 전체 선택 이미지를
완료한 뒤에만 coordinator가 다음 worker에 요청한다. worker process는 모든
pass 동안 유지되어 모델 재로딩, PyTorch threadpool 재생성 및 CPU 설정 변경을
측정 변동에서 제거한다.

두 모델 세트를 동시에 메모리에 유지할 수 없거나 worker 준비 중 OOM이 발생하면
benchmark는 fallback하지 않고 실패 보고서를 남긴다.

### Worker protocol

coordinator와 worker는 전용 `multiprocessing.Pipe`를 사용한다. 전송 payload는
pickle 가능한 immutable dataclass 또는 원시 JSON-compatible 값으로 제한한다.

```text
coordinator -> worker: PREPARE(worker_spec)
worker -> coordinator: READY(worker_metadata)

coordinator -> worker: RUN_PASS(pass_index, image_keys)
worker -> coordinator: PASS_RESULT(pass_result)

coordinator -> worker: SHUTDOWN
worker -> coordinator: STOPPED

worker -> coordinator: ERROR(error_record)
```

`worker_spec`은 worker role, requested runtime override, config path, package root,
sample profile, warm-up 반복 수와 artifact 기대 hash를 포함한다. worker는
`READY`에서 요청값이 아닌 실제 resolved runtime을 반환한다.

coordinator는 다음 조건을 모두 확인한 후에만 측정을 시작한다.

- role과 runtime mode가 요청과 일치한다.
- device가 CPU이고 precision이 FP32다.
- resolved thread, affinity, microbatch와 compile 설정이 요청 또는 핀된 config와
  일치한다.
- detector threshold가 RF-DETR manifest 값과 일치한다.
- 모든 선언 artifact hash가 검증됐다.
- 고정 워밍업의 모든 stage가 성공했다.

불일치가 하나라도 있으면 worker를 종료하고 측정 row 없이 실패 보고서를 쓴다.

### Process lifecycle and timeout

- worker 준비 timeout 기본값은 `900초`다.
- 한 pass timeout 기본값은 `7,200초`다.
- timeout 값은 CLI override가 가능하지만 보고서에 반드시 기록한다.
- worker exit code, PID와 마지막 성공 protocol state를 실패 보고서에 기록한다.
- coordinator 종료 시 정상 worker에는 `SHUTDOWN`을 보내고, 정해진 종료
  timeout을 넘긴 worker만 명시적으로 terminate한다.

## 워밍업 계약

각 worker는 모델 로드와 artifact 검증 후 다음 고정 워밍업을 정확히 2회
수행한다.

1. 고정 E/M/H 이미지 각 1장에 canonical load와 RF-DETR을 실행한다.
2. 실제 detector crop으로 해당 worker의 RepViT serial 또는 batch API를
   실행한다.
3. direct gate 결과와 무관하게 고정 crop group으로 DINO global/local evidence
   API를 한 번 실행한다.
4. compile mode라면 graph 생성과 최초 compiled call을 워밍업 안에서 완료한다.
5. fusion decision code를 실제 warm-up evidence로 실행하되 결과를 품질 또는
   latency 통계에 포함하지 않는다.

워밍업 횟수는 latency 관측값에 따라 적응적으로 바꾸지 않는다. 각 worker는
이미지 키, 반복 횟수, stage별 호출 수, 시작·종료 시각과 성공 여부를
`WarmupEvidence`로 반환한다.

워밍업에서 임의 SKU를 받아들이거나 gate를 우회하지 않는다. DINO를 명시적으로
호출하는 것은 모델 kernel과 local/global evidence 경로를 준비하기 위한
benchmark preflight이며 최종 객체 decision 정책에는 영향을 주지 않는다.

## 측정 계약

- coordinator는 기존 `first_order`에서 시작해 pass마다 AB/BA를 교대한다.
- 각 pass에서 두 worker에 동일한 image key 순서를 보낸다.
- worker는 시작 시 로드한 immutable sample sequence에서 key를 resolve하며,
  누락·중복·순서 불일치를 거부한다.
- canonical image load 직전부터 최종 객체 decision 완료까지 total latency를
  잰다.
- CPU 연산은 synchronous 결과가 완성된 후 clock을 닫는다.
- 모델 로드, artifact 검증, 워밍업과 Pipe 대기 시간은 이미지 latency에서
  제외한다.
- Python garbage collection 동작은 강제로 변경하지 않고 worker 환경에
  기록한다.
- reference와 candidate는 동시에 실행하지 않는다.

이미지별로 다음 값을 기록한다.

- key, profile, object count와 conditional-DINO object count
- canonical, detector, crop, RepViT, DINO, fusion 및 total milliseconds
- deterministic object regression records
- 최종 registered/Unknown decision count

serial `infer()`의 반환 계약은 변경하지 않는다. benchmark에서 serial stage
timing이 필요할 때는 기본 no-op인 instrumentation sink를 pipeline에 주입한다.
sink는 clock event만 수집하며 decision input, ordering, score 또는 policy에
접근하거나 이를 변경할 수 없다. sink가 없을 때 기존 runtime 동작은 동일하다.

## Schema v3 보고서

새 benchmark는 `schema_version: 3`만 쓴다. 기존 v2 보고서는 읽기 전용 증거로
남기며 변환하거나 덮어쓰지 않는다.

```text
schema_version
created_at_utc
completed_at_utc
dataset
detector
artifacts
coordinator
workers
  reference
    pid
    resolved_runtime
    environment
    warmup
  candidate
    pid
    resolved_runtime
    environment
    warmup
passes
profiles
  reference
    E / M / H
  candidate
    E / M / H
quality_gate
latency_gate
```

`resolved_runtime`에는 mode, device, precision, intra/inter-op threads, 실제
affinity IDs, RepViT/DINO microbatch와 compile model을 기록한다. CLI가 값을
생략했더라도 config에서 resolve된 실제 값을 기록해야 하며 `null`로 대신하지
않는다.

`environment`에는 Python, PyTorch, torchvision, NumPy 버전, OS, logical CPU
수, worker가 상속받은 affinity, filesystem/default encoding, Python UTF-8 mode,
garbage-collection 활성 상태를 포함한다.

`profiles.reference`와 `profiles.candidate`는 각각 E/M/H의 image/object 수,
DINO 실행률 및 total과 모든 stage의 mean, p50, p95를 포함한다.

보고서는 기존과 같이 staging 디렉터리에 완성된 JSON을 쓴 다음 고유 output
디렉터리로 atomic rename한다. 기존 output이 존재하면 실행 전에 거부한다.

## 오류 처리

다음은 모두 fail-closed benchmark failure다.

- worker 준비 또는 pass timeout
- worker crash, broken Pipe 또는 비정상 exit code
- requested/resolved runtime 불일치
- artifact 또는 detector threshold 불일치
- 워밍업 stage 누락·예외·비유한 timing
- 이미지 key 누락·중복·순서 변경
- reference/candidate object identity 불일치
- 비유한·음수 latency
- report serialization 또는 atomic rename 실패

실패 보고서에는 예외 type과 정제된 message, worker role/PID, protocol state,
완료된 pass index와 stderr log 경로를 기록한다. 모델 경로 외부의 민감한 환경
값이나 전체 stack local을 직렬화하지 않는다.

## 테스트 전략

모든 구현은 TDD로 진행한다.

### Coordinator 단위 테스트

- 두 worker가 한 번만 준비되고 3개 pass를 재사용하는지 확인한다.
- `AB`, `BA`, `AB` 요청 순서와 동일 image key 전달을 확인한다.
- worker가 동시에 `RUN_PASS` 상태가 되지 않음을 확인한다.
- runtime, artifact 또는 warm-up evidence 불일치를 거부한다.
- timeout, crash, ERROR와 broken Pipe를 실패 보고서로 변환한다.
- shutdown과 비정상 worker terminate 동작을 검증한다.

### Worker 단위 테스트

- CPU 설정과 모델 loader가 worker당 한 번만 호출되는지 확인한다.
- 워밍업이 E/M/H, detector, RepViT, DINO global/local과 fusion을 정확히
  2회 실행하는지 확인한다.
- 측정 row가 워밍업 row를 포함하지 않는지 확인한다.
- serial instrumentation sink가 decision을 바꾸지 않음을 기존 infer 결과와
  비교한다.
- sample key와 timing validation을 확인한다.

### Report 단위 테스트

- schema v3가 양쪽 resolved runtime과 stage profile을 모두 기록한다.
- config-only 실행에서도 runtime 필드가 `null`이 아님을 확인한다.
- DINO 실행 객체 수와 실행률 계산을 검증한다.
- NaN/Infinity를 거부하고 output overwrite를 거부한다.
- 기존 v2 artifact를 수정하지 않음을 확인한다.

### 통합·회귀 테스트

- 실제 Windows `spawn` context에서 fake lightweight worker 두 개로 최소
  AB/BA 통합 테스트를 실행한다.
- 기존 CPU dataset, regression, latency, classification 및 RF-DETR focused
  suite를 유지한다.
- 구현 완료 후 serial worker 결과가 기존 299장 품질 기준선과 정확히
  일치하는지 1회 확인한다. 이번 변경에서는 runtime 승격 판단을 하지 않는다.

## 완료 기준

다음 조건을 모두 만족하면 이번 측정 신뢰도 개선이 완료된다.

- 두 worker가 분리된 process-global CPU 상태에서 모델을 한 번만 로드한다.
- 고정 워밍업 증거가 양쪽 worker에 기록된다.
- 최소 3회 AB/BA가 동일 worker 수명주기에서 실행된다.
- v3 보고서에 실제 resolved runtime과 양쪽 stage/DINO 통계가 기록된다.
- worker 오류와 불일치가 모두 fail-closed로 보존된다.
- serial 품질 결과가 기존 299장·1,406 GT 기준선과 동일하다.
- focused automated suite와 Windows spawn 통합 테스트가 통과한다.
- 운영 config는 `serial_reference`를 유지한다.
- 기존 user dirty changes, v2 보고서와 legacy pipeline은 보존된다.
