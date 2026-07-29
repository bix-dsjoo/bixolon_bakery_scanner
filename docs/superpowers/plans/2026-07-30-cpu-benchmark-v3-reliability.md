# CPU Benchmark v3 Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-process CPU benchmark measurement path with two persistent, isolated Windows worker processes and emit reproducible schema-v3 evidence without changing inference policy or promoting a runtime candidate.

**Architecture:** Keep `scripts/benchmark_cpu_rfdetr_299.py` as the user-facing entry point, but move immutable message contracts, worker execution, parent coordination, and report construction into focused `bakery_scanner.e2e` modules. The parent creates one persistent `spawn` worker for `serial_reference` and one for the candidate, waits for both to complete a fixed two-repetition warm-up, then dispatches whole-image passes in alternating AB/BA order. `ClassifierPipeline.infer()` remains the serial decision implementation; optional benchmark-only timing instrumentation and an explicit all-stage preflight add observability without changing decisions.

**Tech Stack:** Python 3.11+, `multiprocessing` with Windows `spawn`, PyTorch CPU/FP32, Pillow, Pydantic configuration models, pytest, existing CPU dataset/regression/paired-bootstrap utilities.

## Global Constraints

- Work on the current `master` branch. Do not create or switch branches unless the user explicitly changes this instruction.
- Preserve every pre-existing dirty-worktree file. Before every commit, compare `git status --short` with the initial dirty set and stage only files named by the current task.
- Do not delete, move, reformat, or stage unrelated files, v2 reports, portable CPU smoke files, or any legacy pipeline file.
- Preserve `ClassifierPipeline.infer()` as the serial decision-policy reference. Optional timing must be a default no-op and must not alter returned decisions, decision ordering, score values, acceptance gates, provenance, or existing `StageTimings`.
- Keep RF-DETR-L on CPU/FP32. Read its calibrated threshold only from `models/rfdetr_large_bakery_v1/manifest.json`.
- Do not change RF-DETR-L, RepViT-M1, DINOv3, weights, manifests, artifact hashes, preprocessing, direct gate, fusion rules, detector threshold, or the fail-closed `Unknown` policy.
- Do not change `configs/cpu_rfdetr_classifier_policy.yaml` in this phase. It must remain `serial_reference`.
- Warm-up is fixed at exactly two repetitions per worker. Each repetition covers one prescribed E, M, and H image and explicitly exercises canonical loading, RF-DETR, the worker's RepViT path, DINO global/local evidence, and fusion. Warm-up rows never enter quality or latency statistics.
- Start measurement only after both workers report compatible `READY` evidence. Never run the two workers simultaneously during a measured pass.
- Full acceptance measurement remains 299 images, 1,406 GT objects, at least three alternating AB/BA passes. Mean and p95 point deltas and one-sided paired-bootstrap 95% CI upper bounds must all be below zero before a speed candidate can pass.
- Quality floors remain Top-1 `>= 1,349`, Top-3 `>= 1,390`, FP `= 0`, FN `<= 5`, Unknown `<= 48`, A-to-B misclassification `<= 4`; all 1,349 currently correct objects must keep the same SKU, and a safe `Unknown` must never become a wrong SKU.
- A failed worker, timeout, protocol mismatch, runtime mismatch, hash mismatch, warm-up failure, invalid timing, missing/duplicate/reordered key, serialization error, or atomic rename failure is a benchmark failure. Do not relax a gate or silently fall back to a single process.
- Use the existing staging-directory/atomic-rename behavior. Never overwrite an existing output directory.
- Do not claim a performance gain from the final serial-reference validation run. This phase validates measurement reliability only.
- At the end of every task, report the changed files, commands and observed results, implementation-versus-plan comparison, commit hash, and whether all user-owned changes remain preserved before starting the next task.

Initial user-owned dirty paths to preserve and never stage:

```text
artifacts/e2e_current_source/classification/policy_fail_closed.json
configs/box_system.yaml
configs/classifier_policy.yaml
configs/e2e_current_source.yaml
datasets/detection/group_20class_batch01/annotations/instances.json
datasets/detection/group_20class_batch02/annotations/instances.json
docs/superpowers/plans/2026-07-28-batch2-cpu-smoke-deployment.md
docs/superpowers/plans/2026-07-29-rfdetr-fusion-nine-image.md
docs/superpowers/specs/2026-07-28-batch2-cpu-smoke-deployment-design.md
models/rfdetr_large_bakery_v1/
src/bakery_scanner/e2e/release_gate.py
tests/classification/test_fusion_policy.py
tests/e2e/test_ground_truth.py
tests/e2e/test_release_gate.py
tests/test_coco.py
tests/test_config.py
tests/test_rfdetr.py
```

## File Structure

New responsibilities:

- Create `src/bakery_scanner/e2e/cpu_benchmark_protocol.py`: immutable spawn-safe commands, messages, row records, runtime/environment metadata, validation, and structured errors.
- Create `src/bakery_scanner/e2e/cpu_benchmark_worker.py`: live dependency loading, fixed warm-up, serial/batch image execution, and the child-process protocol loop.
- Create `src/bakery_scanner/e2e/cpu_benchmark_coordinator.py`: persistent spawned endpoints, READY checks, sequential AB/BA dispatch, timeouts, shutdown, and forced termination.
- Create `src/bakery_scanner/e2e/cpu_benchmark_report.py`: schema-v3 report construction, bilateral profile/DINO summaries, JSON safety, and atomic success/failure publication.
- Create `tests/e2e/test_cpu_benchmark_protocol.py`: contract and validation tests.
- Create `tests/e2e/test_cpu_benchmark_worker.py`: direct worker/warm-up tests with lightweight fakes.
- Create `tests/e2e/test_cpu_benchmark_coordinator.py`: deterministic coordinator unit tests with in-process fake endpoints.
- Create `tests/e2e/test_cpu_benchmark_report.py`: schema-v3 and atomic-write tests.
- Create `tests/e2e/spawn_benchmark_fixture.py`: top-level, importable fake child target for Windows `spawn`.
- Create `tests/e2e/test_cpu_benchmark_spawn.py`: real `spawn` lifecycle integration test.

Modified responsibilities:

- Modify `src/bakery_scanner/classification/runtime.py`: add optional serial timing observation and benchmark all-stage preflight while preserving normal `infer()` behavior.
- Modify `tests/classification/test_runtime.py`: prove timing/preflight behavior and serial result invariance.
- Modify `src/bakery_scanner/e2e/rfdetr_cpu.py`: extend stage summaries with DINO object count/rate and registered/Unknown counts.
- Modify `tests/test_rfdetr_cpu.py`: cover the extended summary validation.
- Modify `scripts/benchmark_cpu_rfdetr_299.py`: retain CLI/options/sample selection, delegate execution/reporting to v3 modules, and stop loading models in the parent.
- Modify `tests/test_benchmark_cpu_rfdetr_299.py`: cover CLI defaults, dependency injection, schema-v3 delegation, and overwrite behavior.

---

### Task 1: Define Spawn-Safe Benchmark Protocol Contracts

**Files:**

- Create: `src/bakery_scanner/e2e/cpu_benchmark_protocol.py`
- Test: `tests/e2e/test_cpu_benchmark_protocol.py`

- [ ] **Step 1: Write failing validation tests**

Add tests that instantiate valid messages, then reject every value that could make a benchmark ambiguous:

```python
from dataclasses import replace

import pytest

from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PrepareCommand,
    ResolvedRuntime,
    RunPassCommand,
    WorkerSpec,
)


def test_worker_spec_is_immutable_and_requires_fixed_warmup():
    spec = _worker_spec()

    assert spec.warmup_repetitions == 2
    with pytest.raises(AttributeError):
        spec.mode = "batch_pytorch"  # type: ignore[misc]
    with pytest.raises(ValueError, match="exactly 2"):
        replace(spec, warmup_repetitions=1)


def test_resolved_runtime_rejects_null_and_non_cpu_values():
    runtime = _resolved_runtime()

    assert runtime.device == "CPU"
    assert runtime.precision == "FP32"
    with pytest.raises(ValueError, match="intra_op_threads"):
        replace(runtime, intra_op_threads=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="CPU/FP32"):
        replace(runtime, device="CUDA:0")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"total_ms": float("nan")}, "finite"),
        ({"detector_ms": -1.0}, "non-negative"),
        ({"dino_object_count": 3}, "DINO"),
        ({"registered_count": 2, "unknown_count": 2}, "decision counts"),
    ],
)
def test_image_row_rejects_invalid_measurement(changes, message):
    with pytest.raises(ValueError, match=message):
        replace(_image_row(), **changes)


def test_run_pass_command_rejects_missing_duplicate_or_empty_keys():
    with pytest.raises(ValueError, match="non-empty"):
        RunPassCommand(pass_index=0, image_keys=())
    with pytest.raises(ValueError, match="unique"):
        RunPassCommand(pass_index=0, image_keys=("a", "a"))
```

The fixture values must use E/M/H profiles, non-empty normalized image keys, non-negative finite timings, `registered_count + unknown_count == len(records)`, and `0 <= dino_object_count <= len(records)`.

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_protocol.py -q
```

Expected: FAIL during collection because `cpu_benchmark_protocol` does not exist.

- [ ] **Step 3: Implement exact immutable contracts**

Define the following public surface with `@dataclass(frozen=True, slots=True)`:

```python
BenchmarkMode = Literal["serial_reference", "batch_pytorch", "batch_pytorch_compile"]
WorkerRole = Literal["reference", "candidate"]
Profile = Literal["E", "M", "H"]


class ProtocolState(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING_PASS = "running_pass"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    role: WorkerRole
    mode: BenchmarkMode
    package_root: Path
    classifier_config: Path
    sample_profile: Literal["all299", "batch2_e3_m3_h3"]
    runtime_overrides: tuple[tuple[str, object], ...]
    expected_artifact_hashes: tuple[tuple[str, str], ...]
    warmup_repetitions: int = 2


@dataclass(frozen=True, slots=True)
class ResolvedRuntime:
    mode: BenchmarkMode
    device: Literal["CPU"]
    precision: Literal["FP32"]
    intra_op_threads: int
    inter_op_threads: int
    cpu_affinity: tuple[int, ...]
    repvit_microbatch_objects: int | Literal["all"]
    dinov3_microbatch_objects: int | Literal["all"]
    compile_models: tuple[Literal["repvit", "dinov3"], ...]


@dataclass(frozen=True, slots=True)
class WorkerEnvironment:
    python_version: str
    pytorch_version: str
    torchvision_version: str
    numpy_version: str
    os_name: str
    os_version: str
    logical_cpu_count: int
    inherited_affinity: tuple[int, ...]
    filesystem_encoding: str
    default_encoding: str
    utf8_mode: int
    gc_enabled: bool


@dataclass(frozen=True, slots=True)
class WarmupStageCounts:
    canonical: int
    detector: int
    repvit: int
    dinov3_global_local: int
    fusion: int


@dataclass(frozen=True, slots=True)
class WarmupImageEvidence:
    key: str
    profile: Profile
    repetition: int
    started_at_utc: str
    completed_at_utc: str
    stage_counts: WarmupStageCounts


@dataclass(frozen=True, slots=True)
class WarmupEvidence:
    repetitions: int
    images: tuple[WarmupImageEvidence, ...]


@dataclass(frozen=True, slots=True)
class WorkerMetadata:
    role: WorkerRole
    pid: int
    resolved_runtime: ResolvedRuntime
    environment: WorkerEnvironment
    detector_metadata: tuple[tuple[str, object], ...]
    artifact_hashes: tuple[tuple[str, str], ...]
    warmup: WarmupEvidence
    stderr_path: Path


@dataclass(frozen=True, slots=True)
class BenchmarkImageRow:
    key: str
    profile: Profile
    object_count: int
    total_ms: float
    records: tuple[ObjectRecord, ...]
    canonical_ms: float
    detector_ms: float
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    dino_object_count: int
    registered_count: int
    unknown_count: int


@dataclass(frozen=True, slots=True)
class PrepareCommand:
    spec: WorkerSpec


@dataclass(frozen=True, slots=True)
class RunPassCommand:
    pass_index: int
    image_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ShutdownCommand:
    pass


@dataclass(frozen=True, slots=True)
class ReadyMessage:
    metadata: WorkerMetadata


@dataclass(frozen=True, slots=True)
class PassResult:
    role: WorkerRole
    worker_pid: int
    pass_index: int
    rows: tuple[BenchmarkImageRow, ...]


@dataclass(frozen=True, slots=True)
class PassResultMessage:
    result: PassResult


@dataclass(frozen=True, slots=True)
class StoppedMessage:
    role: WorkerRole
    pid: int


@dataclass(frozen=True, slots=True)
class WorkerError:
    exception_type: str
    message: str
    role: WorkerRole | None
    pid: int
    protocol_state: ProtocolState
    pass_index: int | None
    stderr_path: Path | None


@dataclass(frozen=True, slots=True)
class ErrorMessage:
    error: WorkerError
```

Normalize sequence fields to tuples in `__post_init__`. Reject booleans where an integer or float is required. Require all timings to be finite and non-negative. Keep messages free of model instances, open files, lambdas, and other non-pickle-safe state.

- [ ] **Step 4: Run protocol tests and confirm GREEN**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_protocol.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add -- src/bakery_scanner/e2e/cpu_benchmark_protocol.py tests/e2e/test_cpu_benchmark_protocol.py
git diff --cached --check
git commit -m "feat: define CPU benchmark worker protocol"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 2: Add No-Op-by-Default Serial Stage Instrumentation

**Files:**

- Modify: `src/bakery_scanner/classification/runtime.py`
- Modify: `tests/classification/test_runtime.py`

- [ ] **Step 1: Write failing tests for instrumentation and invariance**

Import `SerialStageTimings` and add:

```python
def test_serial_timing_sink_records_stages_without_changing_decision():
    observed = []
    plain = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10})),
        dino_loader=lambda: RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10})),
    )
    instrumented = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10})),
        dino_loader=lambda: RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10})),
        stage_timing_sink=observed.append,
    )

    expected = plain.infer(_image(), _box())
    actual = instrumented.infer(_image(), _box())

    assert replace(actual, timings=expected.timings) == expected
    assert len(observed) == 1
    timing = observed[0]
    assert timing.dino_executed is True
    assert timing.total_ms >= timing.crop_ms + timing.repvit_ms
    assert all(
        value >= 0.0
        for value in (
            timing.crop_ms,
            timing.repvit_ms,
            timing.dinov3_ms,
            timing.fusion_ms,
            timing.total_ms,
        )
    )


def test_serial_timing_sink_marks_direct_decision_without_dino():
    observed = []
    pipeline = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20})),
        dino_loader=lambda: pytest.fail("DINO must stay lazy"),
        stage_timing_sink=observed.append,
    )

    result = pipeline.infer(_image(), _box())

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert observed[0].dino_executed is False
    assert observed[0].dinov3_ms == 0.0
    assert observed[0].fusion_ms == 0.0
```

Update `_pipeline(..., stage_timing_sink=None)` so only tests that request observation supply it.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
python -m pytest tests/classification/test_runtime.py -q
```

Expected: FAIL because `SerialStageTimings` and `stage_timing_sink` do not exist.

- [ ] **Step 3: Implement observation without changing the default path**

Add:

```python
@dataclass(frozen=True, slots=True)
class SerialStageTimings:
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    total_ms: float
    dino_executed: bool


class _StageTimingSink(Protocol):
    def __call__(self, timings: SerialStageTimings) -> None: ...
```

Add `stage_timing_sink: _StageTimingSink | None = None` to `ClassifierPipeline.__init__()` and `ClassifierPipeline.load()`, storing it as `self._stage_timing_sink`.

When the sink is `None`, retain the existing timestamp calls, decision branches, lazy DINO loading, `_with_metadata()` values, and return statements exactly. When a sink exists, collect benchmark-only `time.perf_counter()` boundaries around crop creation, RepViT scoring, DINO evidence scoring, and fusion/policy evaluation. Before every existing return, call a private `_observe_serial_timing(...)` once. Sink exceptions must propagate so the benchmark fails closed.

Do not derive or overwrite the returned decision's existing `StageTimings`; the observer is additive only.

- [ ] **Step 4: Verify focused and regression behavior**

Run:

```powershell
python -m pytest tests/classification/test_runtime.py -q
python -m pytest tests/classification/test_fusion_policy.py tests/e2e/test_cpu_regression.py -q
```

Expected: PASS. The second command must not require any test expectation change.

- [ ] **Step 5: Commit only Task 2 files**

```powershell
git add -- src/bakery_scanner/classification/runtime.py tests/classification/test_runtime.py
git diff --cached --check
git commit -m "feat: observe serial classifier stage timings"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 3: Add Explicit All-Stage Benchmark Preflight

**Files:**

- Modify: `src/bakery_scanner/classification/runtime.py`
- Modify: `tests/classification/test_runtime.py`

- [ ] **Step 1: Write failing tests that force DINO and fusion**

Add fakes that record serial and batch RepViT calls plus DINO global/local calls. Test both runtime modes:

```python
@pytest.mark.parametrize(
    "mode, expected_serial, expected_batch",
    [
        ("serial_reference", 3, 0),
        ("batch_pytorch", 0, 1),
    ],
)
def test_benchmark_preflight_exercises_repvit_dino_local_and_fusion(
    mode, expected_serial, expected_batch
):
    recorder = PreflightRecordingRepVit(_repvit_scores({6: 0.80, 5: 0.20}))
    dino = PreflightRecordingDino(_dino_scores({6: 0.70, 5: 0.20}))
    pipeline = _fusion_pipeline(
        mode=mode,
        repvit=recorder,
        dino_loader=lambda: dino,
        local_bank=object(),
    )

    evidence = pipeline.preflight_benchmark(
        _image(),
        (Box(1, 1, 10, 10), Box(12, 1, 10, 10), Box(24, 1, 10, 10)),
        repvit_max_objects=2,
        dino_max_objects=2,
    )

    assert recorder.serial_calls == expected_serial
    assert recorder.batch_calls == expected_batch
    assert dino.global_local_calls == 1
    assert evidence.repvit == 3
    assert evidence.dinov3_global_local == 1
    assert evidence.fusion == 1
```

Use high-margin direct RepViT evidence so the test proves explicit DINO/global-local/fusion preflight is independent of the direct gate. Add validation tests for an empty box sequence and for missing local/fusion artifacts.

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
python -m pytest tests/classification/test_runtime.py -q
```

Expected: FAIL because `preflight_benchmark()` does not exist.

- [ ] **Step 3: Implement the benchmark-only preflight API**

Add:

```python
@dataclass(frozen=True, slots=True)
class BenchmarkPreflightEvidence:
    repvit: int
    dinov3_global_local: int
    fusion: int


def preflight_benchmark(
    self,
    image: Image.Image | CanonicalImage,
    boxes: Sequence[Box],
    *,
    repvit_max_objects: int,
    dino_max_objects: int,
) -> BenchmarkPreflightEvidence:
    """Execute benchmark warm-up work without producing an evaluated decision."""
```

Implementation contract:

1. Canonicalize once, preserve box order, validate every box, and require at least one box.
2. Build actual padded crop and product-box groups for every detector box.
3. If `self.config.runtime.mode == "serial_reference"`, call `score_with_evidence()` once per crop group. Otherwise call `score_many_with_evidence(..., max_objects=repvit_max_objects)` and require aligned results.
4. Obtain DINO and the local bank. Call `score_global_and_local_evidence()` on the first actual crop group even if RepViT would pass the direct gate.
5. Call `_fusion_decision()` with that RepViT/DINO/local evidence and the first box so the immutable fusion path executes.
6. Synchronize the pipeline clock and return exact counts. Do not return or store a final product decision and do not feed preflight data into evaluation.

Keep the existing `preflight_models()` method unchanged for existing callers.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/classification/test_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit only Task 3 files**

```powershell
git add -- src/bakery_scanner/classification/runtime.py tests/classification/test_runtime.py
git diff --cached --check
git commit -m "feat: preflight all CPU classifier stages"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 4: Implement Worker Preparation, Warm-Up, and Measured Passes

**Files:**

- Create: `src/bakery_scanner/e2e/cpu_benchmark_worker.py`
- Create: `tests/e2e/test_cpu_benchmark_worker.py`

- [ ] **Step 1: Write failing direct-worker tests**

Build lightweight fake samples, detector, classifier, environment reader, and monotonic clock. The core tests are:

```python
def test_prepare_loads_once_applies_runtime_once_and_warms_two_e_m_h_repetitions():
    deps = RecordingWorkerDependencies()
    worker = BenchmarkWorker(_worker_spec(), dependencies=deps)

    metadata = worker.prepare()

    assert deps.configure_calls == 1
    assert deps.detector_loads == 1
    assert deps.classifier_loads == 1
    assert tuple(item.profile for item in metadata.warmup.images) == (
        "E", "M", "H", "E", "M", "H"
    )
    assert all(item.stage_counts == WarmupStageCounts(1, 1, item.stage_counts.repvit, 1, 1)
               for item in metadata.warmup.images)
    assert worker.prepare() is metadata


def test_run_pass_uses_requested_order_and_excludes_warmup_rows():
    deps = RecordingWorkerDependencies()
    worker = BenchmarkWorker(_worker_spec(), dependencies=deps)
    metadata = worker.prepare()
    keys = tuple(sample.key for sample in deps.measured_samples)

    result = worker.run_pass(RunPassCommand(pass_index=2, image_keys=keys))

    assert result.pass_index == 2
    assert tuple(row.key for row in result.rows) == keys
    assert not set(row.key for row in result.rows) & {
        warmup.key for warmup in metadata.warmup.images
    }
    assert all(row.total_ms >= row.canonical_ms + row.detector_ms for row in result.rows)


def test_prepare_rejects_manifest_threshold_or_artifact_hash_mismatch():
    deps = RecordingWorkerDependencies(detector_threshold=0.1)

    with pytest.raises(BenchmarkWorkerFailure, match="threshold"):
        BenchmarkWorker(_worker_spec(), dependencies=deps).prepare()


@pytest.mark.parametrize("keys", [("missing",), ("a", "a"), ("b", "a")])
def test_run_pass_rejects_missing_duplicate_or_reordered_keys(keys):
    worker = prepared_worker()

    with pytest.raises(BenchmarkWorkerFailure, match="image key"):
        worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))
```

Add separate assertions that:

- serial mode calls `infer()` and sums one `SerialStageTimings` observation per proposal;
- batch mode calls `infer_many()` once per image and uses its `dino_object_count`;
- `registered_count + unknown_count == len(records)`;
- detector threshold is the manifest value supplied to the detector loader;
- resolved runtime contains config defaults when no CLI override exists;
- worker environment contains no null required field.

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_worker.py -q
```

Expected: FAIL because `cpu_benchmark_worker` does not exist.

- [ ] **Step 3: Implement injectable worker dependencies and preparation**

Define:

```python
@dataclass(frozen=True, slots=True)
class WorkerDependencies:
    load_samples: Callable[[Path], tuple[CpuEvaluationSample, ...]]
    select_samples: Callable[..., tuple[CpuEvaluationSample, ...]]
    detector_metadata: Callable[[Path], dict[str, object]]
    load_detector: Callable[[Path, float], object]
    load_classifier: Callable[[Path, ClassifierRuntimeConfig, object], ClassifierPipeline]
    load_canonical_image: Callable[[Path], CanonicalImage]
    build_regression_record: Callable[..., object]
    configure_cpu_process: Callable[[ClassifierRuntimeConfig], None]
    read_environment: Callable[[], WorkerEnvironment]
    clock: Callable[[], float]


class BenchmarkWorkerFailure(RuntimeError):
    pass


class BenchmarkWorker:
    def __init__(
        self,
        spec: WorkerSpec,
        *,
        dependencies: WorkerDependencies | None = None,
    ) -> None: ...

    def prepare(self) -> WorkerMetadata: ...

    def run_pass(self, command: RunPassCommand) -> PassResult: ...
```

Preparation order must be:

1. Load and validate the fixed 299-image/1,406-object dataset, then select the requested profile.
2. Read the RF-DETR manifest metadata and artifact hashes.
3. Load `ClassifierConfig`, apply only `WorkerSpec.runtime_overrides`, and resolve all runtime fields.
4. Require requested mode, CPU, FP32, expected artifact hashes, and manifest detector threshold to match.
5. Call `configure_cpu_process()` exactly once.
6. Load classifier and detector exactly once.
7. Select the prescribed first E/M/H sample from the immutable selected sequence.
8. Execute two E/M/H warm-up repetitions. For each image, canonicalize, run RF-DETR, require at least one valid proposal, run `preflight_benchmark()`, and record `WarmupImageEvidence`.
9. Return `WorkerMetadata` with the process PID, resolved runtime, environment, detector metadata, verified hashes, warm-up evidence, and stderr path.

Use the current `select_benchmark_samples()` logic temporarily through dependency injection; Task 7 will move the final CLI-facing ownership without duplicating selection rules.

- [ ] **Step 4: Implement measured serial and batch image paths**

Measure from immediately before canonical image loading to immediately after all decisions are complete:

```python
def _run_image(self, sample: CpuEvaluationSample, image_id: int) -> BenchmarkImageRow:
    total_started = self._clock()
    canonical_started = self._clock()
    frame = self._load_canonical_image(sample.image_path)
    canonical_ms = _elapsed(canonical_started, self._clock())

    detector_started = self._clock()
    proposals = self._detector.predict(image_id, frame.image)
    detector_ms = _elapsed(detector_started, self._clock())

    if self._runtime.mode == "serial_reference":
        decisions, classifier_timings, dino_count = self._run_serial(frame, proposals)
    else:
        decisions, classifier_timings, dino_count = self._run_batch(frame, proposals)

    total_ms = _elapsed(total_started, self._clock())
    record = self._build_regression_record(sample, proposals, decisions)
    return self._validated_row(
        sample=sample,
        total_ms=total_ms,
        canonical_ms=canonical_ms,
        detector_ms=detector_ms,
        classifier_timings=classifier_timings,
        dino_object_count=dino_count,
        records=record.objects,
        decisions=decisions,
    )
```

The real implementation must avoid double-reading the clock and must validate:

- proposal boxes are canonical-frame boxes;
- serial timing sink observations equal proposal count;
- batch decisions align with proposal count;
- all stage timings and total are finite/non-negative;
- key/profile/object counts agree with the sample;
- regression records retain detector/decision ordering;
- decision counts and DINO count agree with decisions.

- [ ] **Step 5: Run worker and focused inference tests**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_worker.py tests/classification/test_runtime.py tests/e2e/test_cpu_regression.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit only Task 4 files**

```powershell
git add -- src/bakery_scanner/e2e/cpu_benchmark_worker.py tests/e2e/test_cpu_benchmark_worker.py
git diff --cached --check
git commit -m "feat: run warmed CPU benchmark workers"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 5: Implement Persistent Spawn Coordinator and Fail-Closed Lifecycle

**Files:**

- Create: `src/bakery_scanner/e2e/cpu_benchmark_coordinator.py`
- Create: `tests/e2e/test_cpu_benchmark_coordinator.py`
- Modify: `src/bakery_scanner/e2e/cpu_benchmark_worker.py`
- Modify: `tests/e2e/test_cpu_benchmark_worker.py`

- [ ] **Step 1: Write failing coordinator tests with fake endpoints**

Use in-process fake endpoints that log every call:

```python
def test_coordinator_prepares_once_and_dispatches_three_alternating_passes():
    log = []
    coordinator = BenchmarkCoordinator(
        endpoint_factory=FakeEndpointFactory(log),
        ready_timeout_s=900.0,
        pass_timeout_s=7200.0,
        shutdown_timeout_s=30.0,
    )

    execution = coordinator.run(
        reference_spec=_worker_spec("reference", "serial_reference"),
        candidate_spec=_worker_spec("candidate", "batch_pytorch"),
        image_keys=("e", "m", "h"),
        passes=3,
        first_order="AB",
    )

    assert [entry for entry in log if entry[0] == "prepare"] == [
        ("prepare", "reference"),
        ("prepare", "candidate"),
    ]
    assert [entry[:3] for entry in log if entry[0] == "run"] == [
        ("run", "reference", 0),
        ("run", "candidate", 0),
        ("run", "candidate", 1),
        ("run", "reference", 1),
        ("run", "reference", 2),
        ("run", "candidate", 2),
    ]
    assert tuple(item.order for item in execution.passes) == ("AB", "BA", "AB")


def test_coordinator_never_has_two_measured_requests_in_flight():
    tracker = ConcurrencyTracker()
    coordinator = BenchmarkCoordinator(endpoint_factory=TrackingFactory(tracker))

    coordinator.run(
        reference_spec=_worker_spec("reference", "serial_reference"),
        candidate_spec=_worker_spec("candidate", "batch_pytorch"),
        image_keys=("e", "m", "h"),
        passes=3,
        first_order="AB",
    )

    assert tracker.maximum_active == 1


@pytest.mark.parametrize(
    "failure",
    ["ready_timeout", "pass_timeout", "worker_error", "broken_pipe", "bad_exit"],
)
def test_coordinator_converts_worker_failure_to_structured_failure(failure):
    coordinator = BenchmarkCoordinator(endpoint_factory=FailingFactory(failure))

    with pytest.raises(BenchmarkCoordinationError) as raised:
        coordinator.run(
            reference_spec=_worker_spec("reference", "serial_reference"),
            candidate_spec=_worker_spec("candidate", "batch_pytorch"),
            image_keys=("e", "m", "h"),
            passes=3,
            first_order="AB",
        )

    assert raised.value.failure.protocol_state is not None
    assert raised.value.failure.exception_type
```

Also test:

- reference and candidate READY mode/role/runtime/threshold/hash/warm-up mismatches are rejected before pass 0;
- every pass has identical ordered keys on both sides;
- both endpoints receive graceful shutdown on success;
- on failure, the coordinator asks both to stop and force-terminates only endpoints still alive;
- `passes < 3` is rejected.

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_coordinator.py -q
```

Expected: FAIL because `cpu_benchmark_coordinator` does not exist.

- [ ] **Step 3: Implement worker process target**

In `cpu_benchmark_worker.py`, add a top-level spawn-importable target:

```python
def worker_process_main(connection: Connection) -> None:
    state = ProtocolState.CREATED
    worker: BenchmarkWorker | None = None
    spec: WorkerSpec | None = None
    active_pass: int | None = None
    try:
        command = connection.recv()
        if not isinstance(command, PrepareCommand):
            raise BenchmarkWorkerFailure("first command must be PREPARE")
        state = ProtocolState.PREPARING
        spec = command.spec
        worker = BenchmarkWorker(spec)
        metadata = worker.prepare()
        connection.send(ReadyMessage(metadata))
        state = ProtocolState.READY

        while True:
            command = connection.recv()
            if isinstance(command, RunPassCommand):
                state = ProtocolState.RUNNING_PASS
                active_pass = command.pass_index
                connection.send(PassResultMessage(worker.run_pass(command)))
                active_pass = None
                state = ProtocolState.READY
            elif isinstance(command, ShutdownCommand):
                state = ProtocolState.STOPPING
                if spec is None:
                    raise BenchmarkWorkerFailure("worker was not prepared")
                connection.send(StoppedMessage(spec.role, os.getpid()))
                state = ProtocolState.STOPPED
                return
            else:
                raise BenchmarkWorkerFailure("unexpected worker command")
    except BaseException as exc:
        connection.send(ErrorMessage(_safe_worker_error(exc, state, active_pass)))
        raise
    finally:
        connection.close()
```

`ShutdownCommand` intentionally carries no spec. Sanitize error messages and never serialize traceback locals or environment-variable values.

- [ ] **Step 4: Implement endpoint and coordinator**

Define:

```python
class WorkerEndpoint(Protocol):
    def prepare(self, timeout_s: float) -> WorkerMetadata: ...
    def run_pass(self, command: RunPassCommand, timeout_s: float) -> PassResult: ...
    def shutdown(self, timeout_s: float) -> None: ...
    def terminate(self) -> None: ...
    @property
    def is_alive(self) -> bool: ...
    @property
    def exit_code(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class CoordinatedPass:
    pass_index: int
    order: Literal["AB", "BA"]
    reference: PassResult
    candidate: PassResult


@dataclass(frozen=True, slots=True)
class BenchmarkExecution:
    reference_worker: WorkerMetadata
    candidate_worker: WorkerMetadata
    passes: tuple[CoordinatedPass, ...]
    started_at_utc: str
    completed_at_utc: str


class BenchmarkCoordinator:
    def __init__(
        self,
        *,
        endpoint_factory: Callable[[WorkerSpec], WorkerEndpoint] | None = None,
        ready_timeout_s: float = 900.0,
        pass_timeout_s: float = 7200.0,
        shutdown_timeout_s: float = 30.0,
    ) -> None: ...

    def run(
        self,
        *,
        reference_spec: WorkerSpec,
        candidate_spec: WorkerSpec,
        image_keys: tuple[str, ...],
        passes: int,
        first_order: Literal["AB", "BA"],
    ) -> BenchmarkExecution: ...
```

The default endpoint factory must use `multiprocessing.get_context("spawn")`, a duplex `Pipe`, and `worker_process_main`. `poll(timeout)` precedes each `recv()`. Any timeout, EOF, unexpected message type, role/pass/key mismatch, or abnormal exit becomes `BenchmarkCoordinationError(WorkerError)`.

Prepare both endpoints before measurement. They may initialize concurrently, but coordinator measurement calls remain strictly synchronous. Validate both READY payloads against their `WorkerSpec` and require their detector metadata/artifact hashes to match. Alternate complete pass order from `first_order`; never interleave images across workers.

- [ ] **Step 5: Run coordinator and worker tests**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_coordinator.py tests/e2e/test_cpu_benchmark_worker.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit only Task 5 files**

```powershell
git add -- src/bakery_scanner/e2e/cpu_benchmark_coordinator.py src/bakery_scanner/e2e/cpu_benchmark_worker.py tests/e2e/test_cpu_benchmark_coordinator.py tests/e2e/test_cpu_benchmark_worker.py
git diff --cached --check
git commit -m "feat: coordinate isolated CPU benchmark workers"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 6: Build Bilateral Stage/DINO Summaries and Schema-v3 Reports

**Files:**

- Modify: `src/bakery_scanner/e2e/rfdetr_cpu.py`
- Modify: `tests/test_rfdetr_cpu.py`
- Create: `src/bakery_scanner/e2e/cpu_benchmark_report.py`
- Create: `tests/e2e/test_cpu_benchmark_report.py`

- [ ] **Step 1: Write failing profile-summary tests**

Extend the existing stage fixture rows with `dino_object_count`, `registered_count`, and `unknown_count`, then assert:

```python
def test_profile_stage_summary_records_dino_rate_and_decision_counts():
    summary = summarize_profile_stages(_profile_rows())

    assert summary["E"]["objects"] == 5
    assert summary["E"]["dino_objects"] == 2
    assert summary["E"]["dino_execution_rate"] == pytest.approx(0.4)
    assert summary["E"]["registered"] == 4
    assert summary["E"]["unknown"] == 1
```

Reject a DINO count larger than decision/object records, inconsistent registered/Unknown totals, NaN, Infinity, negative counts, and missing E/M/H.

- [ ] **Step 2: Run summary tests and confirm RED**

Run:

```powershell
python -m pytest tests/test_rfdetr_cpu.py -q
```

Expected: FAIL because the new fields are not summarized or validated.

- [ ] **Step 3: Extend the existing summary**

Keep all existing `canonical`, `detector`, `crop`, `repvit`, `dinov3`, `fusion`, and `total` statistics. Add per profile:

```python
{
    "images": int,
    "objects": int,
    "dino_objects": int,
    "dino_execution_rate": float,
    "registered": int,
    "unknown": int,
    "canonical": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "detector": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "crop": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "repvit": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "dinov3": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "fusion": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
    "total": {"mean_ms": float, "p50_ms": float, "p95_ms": float},
}
```

Define rate as `dino_objects / (registered + unknown)` and return `0.0` only when both are zero.

- [ ] **Step 4: Write failing schema-v3 report tests**

Construct a `BenchmarkExecution` with three AB/BA passes and assert:

```python
def test_v3_report_contains_resolved_workers_and_bilateral_profiles():
    report = build_benchmark_report(
        execution=_execution(),
        samples=_samples(),
        detector=_detector_metadata(),
        artifacts=_artifact_hashes(),
        sample_profile="all299",
        bootstrap_seed=20260729,
        coordinator_settings=CoordinatorSettings(900.0, 7200.0, 30.0),
    )

    assert report["schema_version"] == 3
    assert report["workers"]["reference"]["resolved_runtime"]["intra_op_threads"] == 8
    assert report["workers"]["candidate"]["resolved_runtime"]["repvit_microbatch_objects"] == 4
    assert report["profiles"]["reference"]["E"]["dino_execution_rate"] == pytest.approx(0.5)
    assert report["profiles"]["candidate"]["E"]["dino_execution_rate"] == pytest.approx(0.25)
    assert report["created_at_utc"]
    assert report["completed_at_utc"]


def test_v3_report_has_no_null_resolved_runtime_values():
    report = build_benchmark_report(
        execution=_execution(),
        samples=_samples(),
        detector=_detector_metadata(),
        artifacts=_artifact_hashes(),
        sample_profile="all299",
        bootstrap_seed=20260729,
        coordinator_settings=CoordinatorSettings(900.0, 7200.0, 30.0),
    )

    assert all(
        value is not None
        for worker in report["workers"].values()
        for value in worker["resolved_runtime"].values()
    )


def test_publish_refuses_overwrite_and_rejects_non_finite_json(tmp_path):
    output = tmp_path / "report"
    output.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        publish_benchmark_report(output, {"schema_version": 3})
    with pytest.raises(ValueError, match="finite"):
        publish_benchmark_report(tmp_path / "new", {"value": float("nan")})
```

Also verify both sides retain every per-image stage timing in each pass, quality uses first-pass deterministic records but validates all later records are identical, latency uses all paired passes, and existing v2 artifact fixture bytes are unchanged.

- [ ] **Step 5: Run report tests and confirm RED**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_report.py -q
```

Expected: FAIL because `cpu_benchmark_report` does not exist.

- [ ] **Step 6: Implement report construction and publication**

Define:

```python
@dataclass(frozen=True, slots=True)
class CoordinatorSettings:
    ready_timeout_s: float
    pass_timeout_s: float
    shutdown_timeout_s: float


def build_benchmark_report(
    *,
    execution: BenchmarkExecution,
    samples: tuple[CpuEvaluationSample, ...],
    detector: dict[str, object],
    artifacts: dict[str, str],
    sample_profile: Literal["all299", "batch2_e3_m3_h3"],
    bootstrap_seed: int,
    coordinator_settings: CoordinatorSettings,
) -> dict[str, object]: ...


def publish_benchmark_report(output: Path, report: dict[str, object]) -> None: ...


def publish_benchmark_failure(
    output: Path,
    failure: WorkerError,
    *,
    coordinator_settings: CoordinatorSettings,
) -> Path: ...
```

Report construction must:

- build `PairedPass` values from every `CoordinatedPass`;
- call existing `compare_run()` and `compare_paired_latency()`;
- validate deterministic object-record identity across all passes before using first-pass records;
- record `profiles.reference` and `profiles.candidate` from all measured rows, not warm-up;
- serialize every pass's order, image keys, stage timings, DINO count, registered/Unknown counts, and records;
- serialize `ResolvedRuntime` and `WorkerEnvironment` explicitly rather than with raw `__dict__`;
- record the coordinator start/end timestamps and timeout settings;
- use `json.dumps(..., allow_nan=False, sort_keys=True)`;
- write success to a unique sibling staging directory and atomically rename it to `output`;
- on failure, write a sanitized `failure.json` to `<output>.failed.<uuid>`.

- [ ] **Step 7: Run report, summary, quality, and latency tests**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_report.py tests/test_rfdetr_cpu.py tests/e2e/test_cpu_regression.py tests/e2e/test_cpu_latency.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit only Task 6 files**

```powershell
git add -- src/bakery_scanner/e2e/rfdetr_cpu.py src/bakery_scanner/e2e/cpu_benchmark_report.py tests/test_rfdetr_cpu.py tests/e2e/test_cpu_benchmark_report.py
git diff --cached --check
git commit -m "feat: report reliable CPU benchmark evidence"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 7: Wire the Existing CLI to Benchmark v3

**Files:**

- Modify: `scripts/benchmark_cpu_rfdetr_299.py`
- Modify: `tests/test_benchmark_cpu_rfdetr_299.py`
- Modify: `src/bakery_scanner/e2e/cpu_benchmark_worker.py`
- Modify: `tests/e2e/test_cpu_benchmark_worker.py`

- [ ] **Step 1: Rewrite CLI tests to fail against the v2 path**

Keep the existing sample-selection and omitted-override tests, then add:

```python
def test_run_benchmark_delegates_to_two_worker_specs_and_emits_v3(tmp_path):
    captured = []
    dependencies = BenchmarkDependencies(
        load_samples=lambda root: tuple(_sample(index) for index in range(299)),
        detector_metadata=lambda root: _detector_metadata(),
        artifact_hashes=lambda root, config, samples: _artifact_hashes(),
        run_coordinator=lambda **kwargs: captured.append(kwargs) or _execution(),
        build_report=lambda **kwargs: {"schema_version": 3},
        publish_report=lambda output, report: (output / "sentinel"),
    )

    report = run_benchmark(_options(tmp_path, tmp_path / "result"), dependencies)

    assert report["schema_version"] == 3
    assert captured[0]["reference_spec"].role == "reference"
    assert captured[0]["reference_spec"].mode == "serial_reference"
    assert captured[0]["candidate_spec"].role == "candidate"
    assert captured[0]["candidate_spec"].mode == "batch_pytorch"
    assert captured[0]["passes"] == 3


def test_cli_defaults_record_fixed_warmup_and_timeouts(monkeypatch, tmp_path):
    received = []
    monkeypatch.setattr(
        "scripts.benchmark_cpu_rfdetr_299.run_benchmark",
        lambda options, dependencies=None: received.append(options) or {},
    )

    assert main([
        "--package-root", str(tmp_path),
        "--classifier-config", str(tmp_path / "policy.yaml"),
        "--candidate-mode", "batch_pytorch",
        "--output", str(tmp_path / "result"),
    ]) == 0

    assert received[0].warmup_repetitions == 2
    assert received[0].ready_timeout_s == 900.0
    assert received[0].pass_timeout_s == 7200.0
    assert received[0].shutdown_timeout_s == 30.0
```

Add tests for `--ready-timeout`, `--pass-timeout`, and `--shutdown-timeout`, and reject non-positive values and fewer than three passes.

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
python -m pytest tests/test_benchmark_cpu_rfdetr_299.py -q
```

Expected: FAIL because the current script emits schema v2 and calls `run_mode` in the parent.

- [ ] **Step 3: Refactor the CLI without changing user-facing mode flags**

Keep `BenchmarkOptions`, `select_benchmark_samples()`, `_validate_full_dataset()`, `_live_samples()`, `_live_detector_metadata()`, `_artifact_hashes()`, and existing mode/microbatch/affinity parsing. Extend options with:

```python
warmup_repetitions: Literal[2] = 2
ready_timeout_s: float = 900.0
pass_timeout_s: float = 7200.0
shutdown_timeout_s: float = 30.0
```

Remove the parent-process `_live_run_mode()` path and the script-local `BenchmarkImageRow`. Build two `WorkerSpec` values:

- reference receives mode `serial_reference` and the resolved reference runtime overrides;
- candidate receives the selected candidate mode and CLI overrides;
- both receive identical package/config/profile/artifact expectations and warm-up repetitions.

Call `BenchmarkCoordinator.run()`, then `build_benchmark_report()` and `publish_benchmark_report()`. On coordination/report failure, call `publish_benchmark_failure()` and re-raise.

Move sample-selection imports used by the child into `cpu_benchmark_worker.py` so spawn workers do not import the script as their application entry point. Keep one canonical selection implementation; the script re-exports it for existing callers/tests.

- [ ] **Step 4: Verify CLI and module tests**

Run:

```powershell
python -m pytest tests/test_benchmark_cpu_rfdetr_299.py tests/e2e/test_cpu_benchmark_worker.py tests/e2e/test_cpu_benchmark_coordinator.py tests/e2e/test_cpu_benchmark_report.py -q
```

Expected: PASS.

- [ ] **Step 5: Verify help starts without loading model artifacts**

Run:

```powershell
python scripts/benchmark_cpu_rfdetr_299.py --help
```

Expected: exit code 0; help includes ready/pass/shutdown timeout options. No model loads and no output directory is created.

- [ ] **Step 6: Commit only Task 7 files**

```powershell
git add -- scripts/benchmark_cpu_rfdetr_299.py tests/test_benchmark_cpu_rfdetr_299.py src/bakery_scanner/e2e/cpu_benchmark_worker.py tests/e2e/test_cpu_benchmark_worker.py
git diff --cached --check
git commit -m "feat: run CPU benchmark CLI with persistent workers"
```

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 8: Prove Real Windows Spawn Lifecycle with Lightweight Workers

**Files:**

- Create: `tests/e2e/spawn_benchmark_fixture.py`
- Create: `tests/e2e/test_cpu_benchmark_spawn.py`

- [ ] **Step 1: Write the failing spawn integration test**

Create a top-level importable fake target in `spawn_benchmark_fixture.py`; it must implement the real message protocol and return deterministic READY/pass/STOPPED messages without importing PyTorch models.

Test:

```python
import multiprocessing

import pytest

from bakery_scanner.e2e.cpu_benchmark_coordinator import BenchmarkCoordinator
from tests.e2e.spawn_benchmark_fixture import fake_worker_process_main


@pytest.mark.skipif(multiprocessing.get_start_method(allow_none=True) == "forkserver",
                    reason="test requires a spawn-capable platform")
def test_two_spawned_workers_remain_persistent_across_ab_ba_passes():
    coordinator = BenchmarkCoordinator(
        endpoint_factory=spawn_fixture_endpoint_factory(fake_worker_process_main),
        ready_timeout_s=10.0,
        pass_timeout_s=10.0,
        shutdown_timeout_s=10.0,
    )

    execution = coordinator.run(
        reference_spec=_spec("reference", "serial_reference"),
        candidate_spec=_spec("candidate", "batch_pytorch"),
        image_keys=("e", "m", "h"),
        passes=3,
        first_order="AB",
    )

    assert execution.reference_worker.pid != execution.candidate_worker.pid
    assert len({item.reference.worker_pid for item in execution.passes}) == 1
    assert len({item.candidate.worker_pid for item in execution.passes}) == 1
    assert tuple(item.order for item in execution.passes) == ("AB", "BA", "AB")
```

The fixture must also expose a controlled crash command used by a second test to prove abnormal child exit is reported and the peer is shut down.

- [ ] **Step 2: Run and confirm RED**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_spawn.py -q
```

Expected: FAIL until the fake spawn target/endpoint injection is complete.

- [ ] **Step 3: Implement the top-level fake target and any minimal endpoint seam**

Keep the fake target under `tests/e2e`; production code must contain only the generic top-level endpoint target injection seam. Always request:

```python
context = multiprocessing.get_context("spawn")
```

Do not use the platform default context. Close the child end of each Pipe in the parent and the parent end in the child. Join every child after STOPPED; terminate and join only after shutdown timeout.

- [ ] **Step 4: Run spawn and coordinator tests repeatedly**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_spawn.py tests/e2e/test_cpu_benchmark_coordinator.py -q
python -m pytest tests/e2e/test_cpu_benchmark_spawn.py -q
python -m pytest tests/e2e/test_cpu_benchmark_spawn.py -q
```

Expected: all three invocations PASS with no hung or orphaned Python worker processes.

- [ ] **Step 5: Commit only Task 8 files**

```powershell
git add -- tests/e2e/spawn_benchmark_fixture.py tests/e2e/test_cpu_benchmark_spawn.py
git diff --cached --check
git commit -m "test: cover CPU benchmark Windows spawn lifecycle"
```

If a minimal production seam changed, stage that exact coordinator file too and report it explicitly.

Record the commit hash and verify the pre-existing dirty set is unchanged.

---

### Task 9: Focused Regression Verification and One Serial Baseline Run

**Files:**

- Modify only if observed behavior requires an in-scope bug fix: files introduced or modified by Tasks 1-8
- Evidence output: a new ignored/untracked directory under `artifacts/evaluations/`; do not commit large benchmark output unless repository policy explicitly requires it

- [ ] **Step 1: Run the complete focused automated suite**

Run:

```powershell
python -m pytest tests/e2e/test_cpu_benchmark_protocol.py tests/e2e/test_cpu_benchmark_worker.py tests/e2e/test_cpu_benchmark_coordinator.py tests/e2e/test_cpu_benchmark_report.py tests/e2e/test_cpu_benchmark_spawn.py tests/test_benchmark_cpu_rfdetr_299.py tests/test_rfdetr_cpu.py tests/e2e/test_cpu_dataset.py tests/e2e/test_cpu_regression.py tests/e2e/test_cpu_latency.py tests/classification/test_runtime.py tests/classification/test_config.py tests/test_rfdetr.py -q
```

Expected: PASS. If a test fails, invoke `superpowers:systematic-debugging`, identify the cause, add a failing regression test, and fix only the in-scope implementation. Do not edit quality or latency gates.

- [ ] **Step 2: Verify production policy and protected file scope**

Run:

```powershell
git diff -- configs/cpu_rfdetr_classifier_policy.yaml
git status --short
git diff --check
```

Expected:

- no diff for `configs/cpu_rfdetr_classifier_policy.yaml`;
- every initial user-owned dirty path is still present with its content preserved;
- no v2 artifact or legacy pipeline file is modified;
- no whitespace errors in the implementation diff.

- [ ] **Step 3: Run one full v3 serial-reference equivalence benchmark**

Use separate serial workers on both sides to validate isolation and result identity without evaluating a new speed candidate:

```powershell
python scripts/benchmark_cpu_rfdetr_299.py `
  --package-root C:\workspace\bixolon_bakery_scanner `
  --classifier-config C:\workspace\bixolon_bakery_scanner\configs\cpu_rfdetr_classifier_policy.yaml `
  --reference-mode serial_reference `
  --candidate-mode serial_reference `
  --sample-profile all299 `
  --passes 3 `
  --first-order AB `
  --bootstrap-seed 20260729 `
  --output C:\workspace\bixolon_bakery_scanner\artifacts\evaluations\cpu-benchmark-v3-serial-equivalence-20260730
```

Before running, confirm that exact output path does not exist. Do not delete or overwrite a prior run.

Expected report contract:

- `schema_version == 3`;
- dataset is 299 images and 1,406 GT objects;
- each worker warm-up contains exactly six entries in E/M/H/E/M/H order;
- each worker PID is stable across three passes and differs from the peer PID;
- pass order is AB/BA/AB and image-key order is identical;
- both workers report CPU/FP32 and non-null resolved runtime values;
- detector threshold equals the RF-DETR manifest value;
- reference and candidate object records are identical on every pass;
- serial quality is Top-1 1,349, Top-3 at least 1,390, FP 0, FN at most 5, Unknown at most 48, A-to-B at most 4;
- both reference and candidate have E/M/H stage profiles and DINO execution rates.

The latency gate may pass or fail due to noise because both sides are intentionally the same implementation. State explicitly that this run is not evidence of a speed improvement.

- [ ] **Step 4: Inspect the report with a read-only assertion command**

Run:

```powershell
@'
import json
from pathlib import Path

path = Path(r"C:\workspace\bixolon_bakery_scanner\artifacts\evaluations\cpu-benchmark-v3-serial-equivalence-20260730\report.json")
report = json.loads(path.read_text(encoding="utf-8"))
assert report["schema_version"] == 3
assert report["dataset"] == {"images": 299, "objects": 1406}
assert tuple(item["order"] for item in report["passes"]) == ("AB", "BA", "AB")
for role in ("reference", "candidate"):
    worker = report["workers"][role]
    assert worker["resolved_runtime"]["device"] == "CPU"
    assert worker["resolved_runtime"]["precision"] == "FP32"
    assert all(value is not None for value in worker["resolved_runtime"].values())
    assert len(worker["warmup"]["images"]) == 6
    assert tuple(worker["warmup"]["images"][i]["profile"] for i in range(6)) == ("E", "M", "H", "E", "M", "H")
    assert tuple(report["profiles"][role]) == ("E", "M", "H")
assert report["workers"]["reference"]["pid"] != report["workers"]["candidate"]["pid"]
assert report["quality_gate"]["passed"] is True
print("schema-v3 serial equivalence evidence: PASS")
'@ | python -
```

Expected: `schema-v3 serial equivalence evidence: PASS`.

- [ ] **Step 5: Run final verification before claiming completion**

Invoke `superpowers:verification-before-completion`, rerun the focused suite from Step 1, and inspect the final `git status --short`.

- [ ] **Step 6: Commit only a required in-scope fix, otherwise make no Task 9 commit**

If Steps 1-5 reveal no code defect, do not create an empty or evidence-only commit. If an in-scope defect is fixed with a regression test:

Stage only the exact in-scope source file and its new regression test, run
`git diff --cached --check`, then commit with
`git commit -m "fix: harden CPU benchmark reliability"`.

Never stage the pre-existing dirty set or the full benchmark output directory.

- [ ] **Step 7: Report completion**

Report:

- every task's changed files;
- every test/benchmark command and observed result;
- deviations from this plan and their technical reason;
- every task commit hash;
- the schema-v3 evidence path;
- quality metrics and the fact that serial-reference equivalence is not a speed claim;
- confirmation that `configs/cpu_rfdetr_classifier_policy.yaml` still uses `serial_reference`;
- confirmation that all initial user changes, v2 reports, and legacy pipeline files remain preserved.
