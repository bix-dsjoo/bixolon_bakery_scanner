Exit code: 0
Wall time: 0.2 seconds
Output:
# GPU/CPU Dual-Runtime Evaluator EXE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one Windows evaluator EXE that selects a verified GPU path when available and otherwise preserves the exact fail-closed inference contract on the CUDA reference or CPU reference path.

**Architecture:** The Python worker owns runtime selection and emits an explicit runtime mode plus two non-overlapping latency scopes. The existing JSON Lines contract is extended strictly, then Flutter parses and displays the added read-only facts. The installer continues to package one worker payload and is rejected if the new protocol/runtime files are absent from its attested identity.

**Tech Stack:** Python 3.11, PyTorch CUDA/CPU, JSON Lines, Flutter/Dart, Inno Setup, pytest, Flutter test.

## Global Constraints

- Preserve EXIF-transposed RGB as the only canonical coordinate frame.
- Preserve calibrated detector thresholds, direct gate, fusion policy, deterministic order, and fail-closed `Unknown` on every runtime mode.
- Never cap a scan to 3--7 objects; 1--2 and 8+ objects remain valid.
- `gpu_fast_verified` is unavailable unless every accelerated score-affecting component has an accepted output-parity receipt; the current RF-DETR TensorRT export must remain disabled.
- RTX 5080 `100 ms` applies only to warmed `inference_ms` from a canonical RGB frame, not raw JPEG scan-to-result time and not CPU mode.
- Keep `portable_cpu_smoke` and legacy behavior intact.
- Do not add external model, dataset, TensorRT engine, or raw benchmark artifacts to Git.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/bakery_scanner/prototype/camera_runtime.py` | Select runtime mode and produce stable runtime/latency facts. |
| `src/bakery_scanner/prototype/camera_protocol.py` | Strictly validate extended ready/result JSON Lines schemas. |
| `scripts/run_camera_inference_worker.py` | Pass fast-path admission configuration into the long-lived worker. |
| `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart` | Parse immutable runtime facts and latency scopes. |
| `apps/bakery_camera_flutter/lib/src/app/bakery_app.dart` | Project runtime facts into diagnostics state. |
| `apps/bakery_camera_flutter/lib/src/admin/diagnostics_models.dart` | Hold read-only runtime mode and latency data. |
| `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart` | Render device, mode, and CPU fallback neutrally. |
| Installer payload scripts/manifests | Attest the changed worker bytes and retain CPU fallback. |

### Task 1: Strict Python protocol for runtime mode and latency scopes

**Files:**
- Modify: `src/bakery_scanner/prototype/camera_protocol.py`
- Modify: `tests/prototype/test_camera_worker.py`
- Modify: `tests/prototype/test_camera_runtime.py`

**Interfaces:**
- Consumes: existing `result` event with `timings_ms` and `ready.startup_metrics`.
- Produces: `runtime_mode` values `gpu_fast_verified`, `gpu_reference`, `cpu_reference`; top-level result fields `execution_device`, `runtime_mode`, `fallback_reason`, `scan_to_result_ms`, `inference_ms`.

- [ ] **Step 1: Write the failing protocol tests**

```python
def test_result_requires_runtime_scope_fields(valid_result):
    event = valid_result()
    event.pop("runtime_mode")
    with pytest.raises(ValueError, match="runtime result envelope is invalid"):
        validate_result_event(event)

def test_result_rejects_mismatched_runtime_device(valid_result):
    event = valid_result(
        device="cpu", execution_device="cpu", runtime_mode="gpu_reference",
        fallback_reason="rfdetr_engine_parity_missing",
        scan_to_result_ms=400.0, inference_ms=80.0,
    )
    with pytest.raises(ValueError, match="GPU runtime mode requires CUDA device"):
        validate_result_event(event)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/prototype/test_camera_worker.py tests/prototype/test_camera_runtime.py -q`

Expected: FAIL because the strict event validator does not know the added fields.

- [ ] **Step 3: Write minimal protocol implementation**

```python
_RUNTIME_MODES = frozenset({"gpu_fast_verified", "gpu_reference", "cpu_reference"})
_RESULT_FIELDS = frozenset({
    "type", "request_id", "image", "device", "execution_device", "runtime_mode",
    "fallback_reason", "scan_to_result_ms", "inference_ms", "objects", "counts",
    "unknown_count", "presentation", "timings_ms", "diagnostics",
})

def _validate_runtime_scope(result: Mapping[str, object]) -> None:
    device, mode, reason = (
        result["execution_device"], result["runtime_mode"], result["fallback_reason"]
    )
    if device != result["device"] or device not in {"cpu", "cuda:0"}:
        raise ValueError("runtime result execution device is invalid")
    if mode not in _RUNTIME_MODES:
        raise ValueError("runtime result mode is invalid")
    if mode == "cpu_reference" and device != "cpu":
        raise ValueError("CPU runtime mode requires CPU device")
    if mode.startswith("gpu_") and device != "cuda:0":
        raise ValueError("GPU runtime mode requires CUDA device")
    if mode == "gpu_fast_verified" and reason is not None:
        raise ValueError("verified GPU runtime cannot have fallback reason")
    if mode != "gpu_fast_verified" and (not isinstance(reason, str) or not reason):
        raise ValueError("reference runtime requires fallback reason")
    for key in ("scan_to_result_ms", "inference_ms"):
        _validate_non_negative_finite(result[key], key)
    if result["scan_to_result_ms"] < result["inference_ms"]:
        raise ValueError("scan-to-result timing must cover inference timing")
```

Call `_validate_runtime_scope(result)` from `validate_result_event` before presentation validation. Keep `timings_ms.total == scan_to_result_ms`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/prototype/test_camera_worker.py tests/prototype/test_camera_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bakery_scanner/prototype/camera_protocol.py tests/prototype/test_camera_worker.py tests/prototype/test_camera_runtime.py
git commit -m "feat(protocol): ?ㅽ뻾 紐⑤뱶? 吏??踰붿쐞瑜?紐낆떆"
```

### Task 2: Deterministic GPU/CPU runtime admission and timing production

**Files:**
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Modify: `scripts/run_camera_inference_worker.py`
- Modify: `tests/prototype/test_camera_runtime.py`
- Modify: `tests/prototype/test_camera_worker_snapshot.py`

**Interfaces:**
- Consumes: `preference` (`auto`, `cuda`, `cpu`), CUDA probe, model artifact verification, and existing `StartupMetrics`.
- Produces: `StartupMetrics.runtime_mode: str`, `CameraInferenceRuntime.runtime_mode: str`, stable reference reasons, and Task 1 result fields.

- [ ] **Step 1: Write the failing runtime-admission tests**

```python
def test_cuda_reference_is_selected_when_fast_admission_is_unavailable(...):
    runtime = CameraInferenceRuntime.initialize(
        root, warmup, preference="auto", cuda_probe=lambda: True,
        backend_loader=loader,
        fast_path_admitter=lambda: "rfdetr_engine_parity_missing",
    )
    assert runtime.device == "cuda:0"
    assert runtime.runtime_mode == "gpu_reference"
    assert runtime.startup_metrics.fallback_reason == "rfdetr_engine_parity_missing"

def test_cpu_reference_is_selected_when_cuda_probe_is_false(...):
    runtime = CameraInferenceRuntime.initialize(
        root, warmup, preference="auto", cuda_probe=lambda: False, backend_loader=loader,
    )
    assert runtime.device == "cpu"
    assert runtime.runtime_mode == "cpu_reference"
    assert runtime.startup_metrics.fallback_reason == "cuda_unavailable"
```

Add a result assertion that `scan_to_result_ms == timings_ms["total"]`, `inference_ms` is the sum of non-decode stages, and CPU never reports a GPU mode.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker_snapshot.py -q`

Expected: FAIL because `fast_path_admitter`, `runtime_mode`, and scope timing fields do not exist.

- [ ] **Step 3: Write minimal runtime implementation**

```python
@dataclass(frozen=True, slots=True)
class RuntimeAdmission:
    mode: Literal["gpu_fast_verified", "gpu_reference", "cpu_reference"]
    fallback_reason: str | None

def _reference_admission(device: str, fast_path_reason: str | None) -> RuntimeAdmission:
    if device == "cuda:0":
        return RuntimeAdmission("gpu_reference", fast_path_reason or "gpu_fast_not_packaged")
    return RuntimeAdmission("cpu_reference", "cuda_unavailable")
```

Inject `fast_path_admitter: Callable[[], str | None] | None` into `initialize` for tests. In production return `"rfdetr_engine_parity_missing"` until an artifact-backed parity receipt is loaded and verified. Do not load or route to the draft TensorRT RF-DETR engine. Pass the selected admission through `StartupMetrics` and `CameraInferenceRuntime`.

In `analyze`, calculate:

```python
scan_to_result_ms = timings.total_ms
inference_ms = (
    timings.detector_ms + timings.crop_ms + timings.repvit_ms +
    timings.dinov3_ms + timings.fusion_ms + timings.postprocess_ms
)
```

Attach those fields plus `execution_device=self.device`, `runtime_mode=self.runtime_mode`, and `fallback_reason=self.startup_metrics.fallback_reason` before `validate_result_event`.

- [ ] **Step 4: Extend deployed worker identity coverage**

Add the changed runtime/protocol sources to `deployed_worker_identity_paths()` coverage tests. Assert that changing `camera_runtime.py` changes `compute_deployed_worker_code_identity`.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker_snapshot.py tests/prototype/test_camera_worker.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bakery_scanner/prototype/camera_runtime.py scripts/run_camera_inference_worker.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker_snapshot.py
git commit -m "feat(runtime): 寃利앸맂 GPU? CPU 李몄“ 寃쎈줈瑜?遺꾨━"
```

### Task 3: Flutter parsing, diagnostics, and customer-safe status presentation

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/app/bakery_app.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/admin/diagnostics_models.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Test: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`
- Test: `apps/bakery_camera_flutter/test/inference/inference_worker_client_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/status_strip_test.dart`

**Interfaces:**
- Consumes: Task 1 worker events and Task 2 startup/result fields.
- Produces: immutable Dart `RuntimeMode` and latency properties displayed without a runtime-policy control.

- [ ] **Step 1: Write the failing Dart parsing and widget tests**

```dart
test('parses CUDA reference runtime without treating it as fast verified', () {
  final result = InferenceResult.fromJson(cudaReferenceResultJson());
  expect(result.executionDevice, 'cuda:0');
  expect(result.runtimeMode, RuntimeMode.gpuReference);
  expect(result.fallbackReason, 'rfdetr_engine_parity_missing');
});

testWidgets('CPU reference status is informational, not an error', (tester) async {
  await tester.pumpWidget(statusStripFor(mode: RuntimeMode.cpuReference));
  expect(find.text('CPU ?뺥솗???곗꽑'), findsOneWidget);
  expect(find.byIcon(Icons.error_outline), findsNothing);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/inference/inference_models_test.dart test/inference/inference_worker_client_test.dart test/ui/status_strip_test.dart`

Expected: FAIL because `RuntimeMode`, result scope fields, and CPU status text do not exist.

- [ ] **Step 3: Write minimal Flutter implementation**

```dart
enum RuntimeMode { gpuFastVerified, gpuReference, cpuReference }

RuntimeMode parseRuntimeMode(Object? value) => switch (value) {
  'gpu_fast_verified' => RuntimeMode.gpuFastVerified,
  'gpu_reference' => RuntimeMode.gpuReference,
  'cpu_reference' => RuntimeMode.cpuReference,
  _ => throw const FormatException('unsupported runtime mode'),
};

String runtimeStatusLabel(RuntimeMode mode) => switch (mode) {
  RuntimeMode.gpuFastVerified => 'GPU 寃利?媛??,
  RuntimeMode.gpuReference => 'GPU 李몄“ 紐⑤뱶',
  RuntimeMode.cpuReference => 'CPU ?뺥솗???곗꽑',
};
```

Add `executionDevice`, `runtimeMode`, `fallbackReason`, `scanToResultMs`, and `inferenceMs` to `InferenceResult`. Add `runtimeMode` to `StartupMetrics` and project it through `_diagnosticsLiveState` to `WorkerDiagnosticsState`. Render reference modes with a neutral information icon and the fallback reason; do not expose a runtime-policy control.

- [ ] **Step 4: Run formatting and focused Flutter tests**

Run: `dart format apps/bakery_camera_flutter/lib apps/bakery_camera_flutter/test && flutter test test/inference/inference_models_test.dart test/inference/inference_worker_client_test.dart test/ui/status_strip_test.dart`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bakery_camera_flutter/lib apps/bakery_camera_flutter/test
git commit -m "feat(app): ?ㅽ뻾 ?μ튂? 李몄“ 紐⑤뱶瑜??쒖떆"
```

### Task 4: Offline installer identity and payload regression

**Files:**
- Modify: `scripts/build_camera_installer_payload.py`
- Modify: `deployment/camera_installer/payload-paths.json`
- Modify: `deployment/camera_installer/runtime-lock.json` only when generated payload content changes it
- Test: `tests/deployment/test_camera_installer_payload.py`
- Test: `tests/deployment/test_camera_installer_manifest.py`

**Interfaces:**
- Consumes: Task 2 deployed worker identity paths and Task 3 Flutter executable.
- Produces: one payload whose worker identity covers runtime admission/protocol bytes and whose lock asserts CPU fallback availability.

- [ ] **Step 1: Write the failing installer tests**

```python
def test_payload_identity_covers_dual_runtime_worker_files():
    paths = deployed_worker_identity_paths()
    assert "src/bakery_scanner/prototype/camera_runtime.py" in paths
    assert "src/bakery_scanner/prototype/camera_protocol.py" in paths

def test_payload_keeps_cpu_reference_requirements(lock_payload):
    assert "torch" in lock_payload["runtime_requirements"]
    assert lock_payload["cpu_fallback"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Expected: FAIL until the new worker identity and CPU fallback assertions are represented by the payload builder.

- [ ] **Step 3: Write minimal payload implementation**

Make `build_camera_installer_payload.py` derive worker identity paths from `deployed_worker_identity_paths()` rather than duplicating a path list. Add a manifest boolean `cpu_fallback: true` and validate it in the payload reader. Do not bundle draft engines or measurement artifacts.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py tests/e2e/test_release_gate.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_camera_installer_payload.py deployment/camera_installer/payload-paths.json deployment/camera_installer/runtime-lock.json tests/deployment tests/e2e/test_release_gate.py
git commit -m "fix(package): GPU? CPU 李몄“ ?고??꾩쓣 ?④퍡 蹂댁옣"
```

### Task 5: Cross-boundary verification and package handoff

**Files:**
- Modify: `docs/deployment/windows-installer-test-matrix.md`
- Modify: `docs/releases/1.1.0.md` or a new release note matching the shipped version
- Test: `tests/integration/test_gpu_batch_parity.py`
- Test: `tests/integration/test_rtx5080_15plus5_gpu.py`

**Interfaces:**
- Consumes: completed Python runtime/protocol, Flutter display, and package tasks.
- Produces: evidence that CPU fallback is verified, GPU reference is selected safely, and fast GPU mode remains unavailable without parity.

- [ ] **Step 1: Write the failing GPU-mode safety test**

```python
def test_rfdetr_draft_engine_is_not_admitted_for_automatic_decision(...):
    admission = production_fast_path_admission(artifact_root)
    assert admission.mode == "gpu_reference"
    assert admission.fallback_reason == "rfdetr_engine_parity_missing"
```

Add a CPU integration fixture that asserts registered totals exclude `Unknown` and that device switching does not change object location/order on deterministic fixtures.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_gpu_batch_parity.py tests/integration/test_rtx5080_15plus5_gpu.py -q`

Expected: FAIL until the admission API is wired to integration fixtures.

- [ ] **Step 3: Run complete verification after implementation**

Run: `pytest tests/prototype tests/deployment tests/e2e tests/integration/test_gpu_batch_parity.py -q`

Expected: PASS; unavailable external GPU/artifact suites may SKIP and must be recorded as unverified.

- [ ] **Step 4: Build and inspect the installer in a clean output directory**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_camera_installer.ps1`

Expected: installer build succeeds and payload identity includes changed worker bytes. Do not claim external-PC validation from this local build.

- [ ] **Step 5: Update release documentation and commit**

Record the exact device/runtime mode, the `inference_ms` boundary, CPU fallback behavior, and whether installer/GPU suites passed, skipped, or remain unverified. Do not record exploratory TensorRT microbenchmarks as acceptance receipts.

```bash
git add docs/deployment/windows-installer-test-matrix.md docs/releases
git commit -m "docs(release): ?댁쨷 ?고???寃利?踰붿쐞瑜?湲곕줉"
```

## Self-Review

- Tasks 1--2 enforce common GPU/CPU worker behavior, Task 3 makes it observable in Flutter, Task 4 protects the single offline payload, and Task 5 records strict evidence without enabling the non-parity engine.
- No task introduces an object-count restriction: batching is an implementation detail and every detected object remains in the result contract.
- The plan uses one stable spelling for every cross-boundary field: `execution_device`, `runtime_mode`, `fallback_reason`, `scan_to_result_ms`, and `inference_ms`.
