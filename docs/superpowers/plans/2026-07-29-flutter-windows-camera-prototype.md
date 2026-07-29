# Flutter Windows Camera Evaluation Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-only Flutter evaluation viewer that captures one camera frame, runs the current RF-DETR-L plus RepViT/DINOv3 fusion pipeline through one persistent warmed Python worker, and clearly shows boxes, SKU counts, Unknown Top-3 candidates, device, and POS-facing latency.

**Architecture:** Flutter owns the camera, press-to-result timing, application state, overlay, and evaluation UI. A persistent Python JSON Lines subprocess validates artifacts, selects CUDA with one clean CPU fallback, loads and warms every model once, emits factual stage progress, and returns deterministic canonical-image results. Live captures expose observable inference evidence but never claim ground-truth accuracy.

**Tech Stack:** Flutter 3.44.7, Dart 3.12, `camera 0.12.0+2`, `camera_windows 0.2.6+4`, Python 3.11, PyTorch 2.8, RF-DETR 1.8.3, Pillow, pytest.

## Global Constraints

- Target Windows desktop only under `apps/bakery_camera_flutter`; initial size is `1280x820` and the UI must not overflow at `1024x720`.
- Keep RF-DETR-L, its packaged post-processing and threshold, RepViT-M1, conditional DINOv3, fusion policy, EXIF-transposed RGB preprocessing, and `[x_min, y_min, x_max, y_max]` contracts unchanged.
- Read detector threshold `0.5691395401954651` and artifact paths from `models/rfdetr_large_bakery_v1/manifest.json`; do not hardcode the threshold in runtime code.
- Use the hash-pinned `fusion_local_or_global_consensus_margin_v1` policy on both CUDA and CPU.
- Load RF-DETR-L, RepViT-M1, DINOv3, the RepViT prototype bank, and DINOv3 support/local banks once; warm them before enabling `분석하기`.
- Prefer `cuda:0` only after CUDA availability and allocation checks; after any CUDA load or warm-up failure, dispose the partial attempt and initialize once on CPU.
- Use FP32 on both devices. Do not add FP16, ONNX, TensorRT, quantization, training, resolution changes, or threshold changes.
- Every Unknown must contain three unique ranked registered-product candidates; confirmed objects contain no Top-3 candidates.
- Registered SKU counts exclude Unknown. Counts plus Unknown count must equal the number of returned objects.
- Startup load/warm-up timing, worker inference timing, still-capture timing, and Flutter press-to-rendered-result timing are separate measurements.
- The UI has no operator confirmation, correction, cart, payment, session history, charts, or live accuracy claim.
- Use `dart:io` `Process.start` with absolute paths and argument arrays; never construct a shell command from a captured path.
- Preserve unrelated dirty worktree changes and do not rebuild or overwrite the existing CPU-only ZIP.
- Run repository commands from `C:\workspace\bixolon_bakery_scanner` unless a step explicitly changes directory and restores it.

---

### Task 1: Install pinned Flutter tooling and scaffold the Windows shell

**Files:**
- Create: `apps/bakery_camera_flutter/pubspec.yaml`
- Create: `apps/bakery_camera_flutter/lib/main.dart`
- Create: `apps/bakery_camera_flutter/test/widget_test.dart`
- Modify: `apps/bakery_camera_flutter/windows/runner/main.cpp`

**Interfaces:**
- Consumes: Flutter 3.44.7 and Visual Studio Desktop development with C++.
- Produces: a compilable Windows application named `bakery_camera_prototype`.

- [ ] **Step 1: Install Flutter outside the repository and validate Windows tooling**

```powershell
$flutterRoot = 'C:\workspace\tools\flutter-3.44.7'
git clone --depth 1 --branch 3.44.7 https://github.com/flutter/flutter.git $flutterRoot
$env:Path = "$flutterRoot\bin;$env:Path"
flutter config --enable-windows-desktop
flutter doctor -v
```

Expected: Flutter reports `3.44.7` and Windows desktop tooling is ready. If the doctor reports a missing Visual Studio workload, install `Desktop development with C++`, its Windows SDK, and CMake through Visual Studio Installer, then rerun the doctor before continuing.

- [ ] **Step 2: Scaffold only Windows and pin camera dependencies**

```powershell
flutter create --platforms=windows --org com.bixolon --project-name bakery_camera_prototype apps/bakery_camera_flutter
Push-Location apps/bakery_camera_flutter
flutter pub add camera:0.12.0+2
flutter pub add camera_windows:0.2.6+4
Pop-Location
```

Set `environment.sdk` in `pubspec.yaml` to `">=3.12.0 <4.0.0"`.

- [ ] **Step 3: Set the initial native window size**

Change the generated `windows/runner/main.cpp` `Win32Window::Size` to `1280, 820` without changing the generated runner lifecycle.

- [ ] **Step 4: Verify the untouched shell**

```powershell
flutter analyze
flutter test
flutter build windows --debug
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit the scaffold**

```powershell
git add apps/bakery_camera_flutter
git commit -m "feat: scaffold Windows camera evaluator"
```

---

### Task 2: Define strict worker requests, progress events, and result events

**Files:**
- Create: `src/bakery_scanner/prototype/__init__.py`
- Create: `src/bakery_scanner/prototype/camera_protocol.py`
- Create: `tests/prototype/test_camera_protocol.py`

**Interfaces:**
- Consumes: one UTF-8 JSON object per stdin line.
- Produces: `AnalyzeRequest`, `PingRequest`, `ShutdownRequest`, `WorkerPhase`, `parse_request(line: str) -> Request`, `progress_event(request_id: str, phase: WorkerPhase) -> dict[str, object]`, and `encode_event(event: Mapping[str, object]) -> str`.

- [ ] **Step 1: Write failing strict-request tests**

```python
def test_analyze_requires_unique_fields_absolute_existing_image(tmp_path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    request = parse_request(json.dumps({
        "type": "analyze",
        "request_id": "7",
        "image_path": str(image.resolve()),
    }))
    assert request == AnalyzeRequest("7", image.resolve())


@pytest.mark.parametrize("line", [
    '{"type":"analyze","request_id":"1","image_path":"capture.jpg"}',
    '{"type":"ping","type":"shutdown"}',
    '{"type":"ping","extra":true}',
])
def test_protocol_rejects_ambiguous_input(line):
    with pytest.raises(ValueError):
        parse_request(line)
```

- [ ] **Step 2: Write failing event tests**

```python
def test_progress_event_is_correlated_and_canonical():
    event = progress_event("7", WorkerPhase.DETECTING)
    assert event == {"type": "progress", "request_id": "7", "phase": "detecting"}
    assert encode_event(event) == (
        '{"phase":"detecting","request_id":"7","type":"progress"}\n'
    )
```

Also assert `encode_event` rejects NaN/infinity and appends exactly one newline.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_protocol.py -q`

Expected: collection fails because `bakery_scanner.prototype.camera_protocol` does not exist.

- [ ] **Step 4: Implement immutable requests and duplicate-key rejection**

Use `json.loads(..., object_pairs_hook=...)` to reject duplicate keys. Reject unknown fields, empty request IDs, relative paths, missing files, non-string paths, and unsupported request types. Define phases exactly as:

```python
class WorkerPhase(str, Enum):
    DETECTING = "detecting"
    CLASSIFYING = "classifying"
    RECHECKING = "rechecking"
    AGGREGATING = "aggregating"
```

Use deterministic JSON:

```python
def encode_event(event: Mapping[str, object]) -> str:
    return json.dumps(
        event,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
```

- [ ] **Step 5: Run the focused tests and confirm GREEN**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_protocol.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the protocol**

```powershell
git add src/bakery_scanner/prototype tests/prototype/test_camera_protocol.py
git commit -m "feat: define camera worker protocol"
```

---

### Task 3: Pin a CUDA fusion config and make conditional recheck observable

**Files:**
- Create: `configs/gpu_rfdetr_classifier_policy.yaml`
- Modify: `src/bakery_scanner/classification/runtime.py`
- Modify: `tests/classification/test_runtime.py`
- Create: `tests/prototype/test_camera_classifier_configs.py`

**Interfaces:**
- Consumes: current CPU RF-DETR classifier config and existing hash-pinned fusion artifact.
- Produces: equivalent CUDA and CPU configs plus optional `on_stage(stage: str)` callbacks from `ClassifierPipeline.infer`.

- [ ] **Step 1: Write a failing CUDA/CPU config-equivalence test**

```python
def test_gpu_and_cpu_rfdetr_configs_differ_only_by_device(repo_root):
    cpu = yaml.safe_load(
        (repo_root / "configs/cpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )
    gpu = yaml.safe_load(
        (repo_root / "configs/gpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )
    assert cpu["runtime"] == {"device": "CPU", "precision": "FP32"}
    assert gpu["runtime"] == {"device": "CUDA:0", "precision": "FP32"}
    cpu["runtime"] = gpu["runtime"]
    assert cpu == gpu
    assert gpu["calibration"]["fusion_policy"].endswith(
        "fusion_local_or_global_consensus_margin_v1_reference_rebound.json"
    )
    ClassifierConfig.load(
        repo_root / "configs/gpu_rfdetr_classifier_policy.yaml"
    )
```

- [ ] **Step 2: Write failing classifier-stage callback tests**

Add one direct-decision test asserting `on_stage` receives only `"repvit"` and one conditional test asserting it receives `("repvit", "dinov3")`. Also add a preflight test proving DINOv3 and the local bank are both loaded once.

- [ ] **Step 3: Run tests and confirm RED**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/prototype/test_camera_classifier_configs.py tests/classification/test_runtime.py -q
```

Expected: the GPU config is missing and `ClassifierPipeline.infer` has no `on_stage` parameter.

- [ ] **Step 4: Create the CUDA config without touching the dirty general config**

Create `configs/gpu_rfdetr_classifier_policy.yaml` with every path, ID, hash, preprocess value, calibration artifact, fusion-policy path, and fusion-policy SHA copied exactly from `configs/cpu_rfdetr_classifier_policy.yaml`; change only:

```yaml
runtime:
  device: CUDA:0
  precision: FP32
```

Do not modify `configs/classifier_policy.yaml`.

- [ ] **Step 5: Add backward-compatible stage observation**

Change the classifier signature to:

```python
def infer(
    self,
    image: Image.Image | CanonicalImage,
    box: Box,
    *,
    on_stage: Callable[[str], None] | None = None,
) -> ClassificationDecision:
```

Call `on_stage("repvit")` immediately before RepViT scoring and `on_stage("dinov3")` only after direct classification fails and immediately before conditional DINOv3 work begins. Extend `preflight_models` to load and exercise the configured DINO local bank as well as RepViT and DINO weights. Do not change score vectors, ranking, policy, confidence, or decisions.

- [ ] **Step 6: Run tests and confirm GREEN**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/prototype/test_camera_classifier_configs.py tests/classification/test_runtime.py -q
```

Expected: all tests pass and existing call sites remain compatible.

- [ ] **Step 7: Commit the device config and observation hook**

```powershell
git add configs/gpu_rfdetr_classifier_policy.yaml src/bakery_scanner/classification/runtime.py tests/classification/test_runtime.py tests/prototype/test_camera_classifier_configs.py
git commit -m "feat: prepare warmed CUDA fusion classifier"
```

---

### Task 4: Build the persistent warmed RF-DETR fusion runtime

**Files:**
- Create: `src/bakery_scanner/prototype/camera_runtime.py`
- Create: `tests/prototype/test_camera_runtime.py`

**Interfaces:**
- Consumes: repository root, representative warm-up image, device preference, and progress callback.
- Produces: `CameraInferenceRuntime.initialize(root: Path, warmup_image: Path, preference: str = "auto", on_startup: Callable[[str, str], None] | None = None, *, cuda_probe: Callable[[], bool] | None = None, backend_loader: Callable[[str], RuntimeBackend] | None = None, clock: Callable[[], float] | None = None)`, `.analyze(image_path: Path, request_id: str, on_progress: Callable[[WorkerPhase], None] | None = None) -> dict[str, object]`, `.device`, `.startup_metrics`, and `.close()`. Injection parameters are for deterministic tests; production uses their defaults.

- [ ] **Step 1: Write failing integrity and GPU fallback tests**

```python
def test_initialize_retries_cleanly_on_cpu_after_cuda_warmup_failure(tmp_path):
    attempts = []
    warmup_image = tmp_path / "warm.jpg"
    warmup_image.write_bytes(b"jpeg")

    def loader(device):
        attempts.append(device)
        return FakeBackend(device=device, fail_warmup=device == "cuda:0")

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="auto",
        cuda_probe=lambda: True,
        backend_loader=loader,
    )
    assert attempts == ["cuda:0", "cpu"]
    assert runtime.device == "cpu"
    assert runtime.startup_metrics.fallback_reason == "cuda_warmup_failed"


def test_initialize_rejects_detector_checkpoint_hash_mismatch(repo_fixture):
    repo_fixture.detector_checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checkpoint SHA-256"):
        CameraInferenceRuntime.initialize(
            repo_fixture.root,
            repo_fixture.warmup_image,
            preference="cpu",
        )
```

Also assert CUDA is not attempted when `torch.cuda.is_available()` is false or a small allocation fails.

- [ ] **Step 2: Write failing deterministic result-contract tests**

Use two confirmed fake decisions and one Unknown fake decision. Assert:

```python
assert [row["object_id"] for row in result["objects"]] == [
    "object-1", "object-2", "object-3"
]
assert len(result["objects"][2]["top3"]) == 3
assert result["counts"] == {"6": 1, "10": 1}
assert result["unknown_count"] == 1
assert sum(result["counts"].values()) + result["unknown_count"] == 3
assert set(result["timings_ms"]) == {
    "decode_preprocess", "detector", "repvit",
    "dinov3", "postprocess", "total",
}
```

Assert each Top-3 row includes `rank`, `sku_id`, `sku_name`, and `score`, while confirmed rows have an empty Top-3.

- [ ] **Step 3: Run tests and confirm RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_runtime.py -q`

Expected: import fails because `CameraInferenceRuntime` does not exist.

- [ ] **Step 4: Implement manifest validation and device attempts**

Validate manifest schema, checkpoint SHA, calibration SHA, source label, and threshold before model construction. For `auto`, attempt `cuda:0` only after `torch.cuda.is_available()` and a small `torch.empty(1, device="cuda:0")` succeeds. Map runtime device to RF-DETR's accepted loader device (`"cuda"` or `"cpu"`), and select `configs/gpu_rfdetr_classifier_policy.yaml` or `configs/cpu_rfdetr_classifier_policy.yaml`.

Define the test seam and startup result explicitly:

```python
class RuntimeBackend(Protocol):
    device: str
    detector: RFDetrRunner
    classifier: ClassifierPipeline

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class StartupMetrics:
    device: str
    load_ms: float
    warmup_ms: float
    fallback_reason: str | None
    detector_id: str
    repvit_id: str
    dinov3_id: str
    fusion_policy_id: str
    detector_threshold: float
```

On a failed CUDA load or warm-up, call `.close()` on any constructed backend, drop references, run `gc.collect()`, call `torch.cuda.empty_cache()` when available, and then attempt CPU once. Never switch devices during `analyze`.

- [ ] **Step 5: Implement one-time full warm-up**

Load the canonical warm-up image, run RF-DETR once, require at least one proposal, and call `ClassifierPipeline.preflight_models` on the first proposal. Record separate load and warm-up milliseconds. Mark the runtime ready only after this succeeds. A second warm-up call must raise `RuntimeError("runtime is already warmed")`.

- [ ] **Step 6: Implement measured analysis and progress**

Measure canonical decode/preprocess, RF-DETR predict, aggregated RepViT time, aggregated DINOv3 time, result aggregation, and total. Synchronize CUDA before timing boundaries. Emit each phase at most once and in this legal order:

```text
detecting -> classifying -> [rechecking] -> aggregating
```

Sort objects top-to-bottom then left-to-right, assign deterministic `object-N` IDs, load SKU names from `datasets/classes.json`, and preserve canonical boxes. Do not include startup or warm-up in result timing.

- [ ] **Step 7: Prove model reuse and cleanup**

Analyze twice and assert detector/classifier constructors and warm-up each ran once. Assert `.close()` is idempotent and releases only runtime-owned objects.

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_runtime.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit the runtime**

```powershell
git add src/bakery_scanner/prototype/camera_runtime.py tests/prototype/test_camera_runtime.py
git commit -m "feat: add persistent warmed camera runtime"
```

---

### Task 5: Add the long-lived Python JSON Lines worker

**Files:**
- Create: `src/bakery_scanner/prototype/camera_worker.py`
- Create: `scripts/run_camera_inference_worker.py`
- Create: `tests/prototype/test_camera_worker.py`

**Interfaces:**
- Consumes: stdin requests and CLI arguments `--repo-root`, `--device`, and `--warmup-image`.
- Produces: `loading`, `warming`, `ready`, request-correlated `progress`, `result`, `pong`, recoverable `error`, fatal `fatal`, and `stopped` stdout events.

- [ ] **Step 1: Write failing in-memory worker lifecycle tests**

```python
def test_worker_emits_startup_once_and_keeps_request_correlation(tmp_path):
    stdin = io.StringIO('{"type":"ping"}\n{"type":"shutdown"}\n')
    stdout = io.StringIO()
    serve(stdin, stdout, runtime_factory=lambda emit: FakeRuntime())
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [row["type"] for row in events] == [
        "loading", "warming", "ready", "pong", "stopped"
    ]
```

Add tests that malformed input emits `error` and continues, analyze emits legal progress before its result, duplicate request IDs are rejected, and initialization failure emits exactly one `fatal`.

- [ ] **Step 2: Run tests and confirm RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_worker.py -q`

Expected: import fails because `serve` does not exist.

- [ ] **Step 3: Implement the flushed worker loop**

Write every protocol event through `encode_event` and flush immediately. Write Python tracebacks and library warnings only to stderr. Maintain an in-memory set of handled request IDs. On shutdown, close the exact runtime, emit `stopped`, and exit 0.

- [ ] **Step 4: Add the path-safe CLI**

The entrypoint accepts:

```text
--repo-root C:\workspace\bixolon_bakery_scanner
--device auto|cuda|cpu
--warmup-image C:\workspace\bixolon_bakery_scanner\samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg
```

Resolve all paths, require the warm-up image to remain under the supplied repository root, and call `serve`.

- [ ] **Step 5: Run tests and confirm GREEN**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_worker.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the worker**

```powershell
git add src/bakery_scanner/prototype/camera_worker.py scripts/run_camera_inference_worker.py tests/prototype/test_camera_worker.py
git commit -m "feat: serve persistent camera inference"
```

---

### Task 6: Implement typed Flutter protocol models and process ownership

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/inference/inference_launch_config.dart`
- Create: `apps/bakery_camera_flutter/lib/src/inference/inference_worker_client.dart`
- Create: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`
- Create: `apps/bakery_camera_flutter/test/inference/inference_launch_config_test.dart`
- Create: `apps/bakery_camera_flutter/test/inference/inference_worker_client_test.dart`

**Interfaces:**
- Consumes: `BAKERY_INFERENCE_PYTHON`, `BAKERY_REPO_ROOT`, worker stdout/stderr, and captured image paths.
- Produces: `InferenceLaunchConfig.fromEnvironment`, `InferenceWorkerClient.start()`, `.analyze(String imagePath)`, `.shutdown()`, typed startup/progress/result events, and a bounded diagnostic log.

- [ ] **Step 1: Write failing launch-config tests**

```dart
test('launch config resolves only explicit environment values', () {
  final config = InferenceLaunchConfig.fromEnvironment({
    'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
    'BAKERY_REPO_ROOT': r'C:\workspace\bixolon_bakery_scanner',
  });
  expect(config.workerScript, endsWith(r'scripts\run_camera_inference_worker.py'));
  expect(config.warmupImage, endsWith(r'samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg'));
});
```

Assert missing values fail closed with a Korean actionable message and that no shell metacharacter processing occurs.

- [ ] **Step 2: Write failing result-model tests**

Assert finite image geometry, unique deterministic object IDs, valid boxes, exactly three candidates on Unknown, no candidates on confirmed objects, and:

```dart
expect(
  result.registeredCount + result.unknownCount,
  result.objects.length,
);
```

- [ ] **Step 3: Write failing client lifecycle tests**

Use a `WorkerProcessAdapter` fake. Assert analysis is rejected before `ready`, progress phases are ordered and request-correlated, result completers correlate by request ID, malformed stdout makes the client fatal, stderr retains only its newest 200 lines, and shutdown terminates only its owned child if graceful exit times out.

- [ ] **Step 4: Run tests and confirm RED**

Run from the app directory: `flutter test test/inference`

Expected: the inference files do not exist.

- [ ] **Step 5: Implement immutable models and strict parsing**

Define `InferenceCandidate`, `InferenceObject`, `StageTimings`, `StartupMetrics`, `InferenceResult`, `WorkerStatus`, and `WorkerPhase`. Reject unknown event types and malformed fields rather than rendering partial results.

- [ ] **Step 6: Implement environment resolution and `Process.start`**

Use:

```dart
final process = await Process.start(
  config.pythonExecutable,
  [
    config.workerScript,
    '--repo-root', config.repoRoot,
    '--device', 'auto',
    '--warmup-image', config.warmupImage,
  ],
  runInShell: false,
);
```

Decode stdout as UTF-8 lines, stderr separately, and maintain one `Completer<InferenceResult>` per request ID.

- [ ] **Step 7: Run tests and confirm GREEN**

Run: `flutter test test/inference`

Expected: all tests pass.

- [ ] **Step 8: Commit the Flutter worker client**

```powershell
git add apps/bakery_camera_flutter/lib/src/inference apps/bakery_camera_flutter/test/inference
git commit -m "feat: connect evaluator to inference worker"
```

---

### Task 7: Own the Windows camera and POS-facing timing state

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/camera/camera_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart`
- Create: `apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart`

**Interfaces:**
- Consumes: `CameraController`, `InferenceWorkerClient`, still captures, and a monotonic clock.
- Produces: `ScannerController.initialize()`, `.analyze()`, `.resetCapture()`, `.reconnectCamera()`, `.selectObject(String?)`, and immutable `ScannerState`.

- [ ] **Step 1: Write failing readiness and single-flight tests**

```dart
test('analysis requires camera and model readiness and is single-flight', () async {
  final controller = ScannerController(
    camera: fakeCamera,
    worker: fakeWorker,
    clock: fakeClock,
  );
  await controller.initialize();
  final first = controller.analyze();
  expect(controller.state.isAnalyzing, isTrue);
  await expectLater(controller.analyze(), throwsStateError);
  await first;
  expect(controller.state.result, isNotNull);
});
```

Also test no-camera state, camera reconnect, worker fatal, capture failure, empty detections, reset to live preview, and selected object ID clearing on reset.

- [ ] **Step 2: Write failing timing tests**

Advance a fake monotonic clock through button press, still capture, worker response, and rendered-frame acknowledgement. Assert `captureMs` and `pressToRenderedResultMs` are distinct from the worker's `timings.total`.

- [ ] **Step 3: Run tests and confirm RED**

Run: `flutter test test/scanner/scanner_controller_test.dart`

Expected: `ScannerController` does not exist.

- [ ] **Step 4: Implement camera ownership**

Enumerate `availableCameras()`, select the first, initialize still capture, listen for camera errors, and dispose the exact controller during reconnect and application shutdown. Store captures only in one session-owned temporary directory.

- [ ] **Step 5: Implement capture, progress, and rendered-result acknowledgement**

On `분석하기`, freeze single-flight state, time the still capture, send the absolute JPEG path, map worker progress into Korean factual phases, decode captured dimensions, and retain the exact image until `다시 촬영`. Complete press-to-render timing only from a post-frame callback after the result and overlay have rendered.

- [ ] **Step 6: Run tests and confirm GREEN**

Run: `flutter test test/scanner/scanner_controller_test.dart`

Expected: all tests pass.

- [ ] **Step 7: Commit camera state**

```powershell
git add apps/bakery_camera_flutter/lib/src/camera apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart
git commit -m "feat: capture and time camera analyses"
```

---

### Task 8: Implement coordinate-correct interactive overlays

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart`
- Create: `apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart`

**Interfaces:**
- Consumes: captured image size, viewport size, result boxes, and selected object ID.
- Produces: `ContainedImageTransform` and `ResultOverlayPainter`.

- [ ] **Step 1: Write failing letterbox and selection tests**

```dart
test('maps image coordinates through BoxFit.contain offsets', () {
  final transform = ContainedImageTransform(
    imageSize: const Size(400, 200),
    viewportSize: const Size(300, 300),
  );
  expect(transform.imageRect, const Rect.fromLTWH(0, 75, 300, 150));
  expect(
    transform.mapBox(const Rect.fromLTRB(100, 50, 300, 150)),
    const Rect.fromLTRB(75, 112.5, 225, 187.5),
  );
});
```

Add a painter test proving confirmed boxes use teal, Unknown boxes use amber, and the selected box alone receives the thicker highlight.

- [ ] **Step 2: Run tests and confirm RED**

Run: `flutter test test/scanner/result_overlay_test.dart`

Expected: overlay classes do not exist.

- [ ] **Step 3: Implement mapping and painting**

Use the minimum viewport/image scale, centered `BoxFit.contain` offsets, image-bound clipping, and stable label placement inside the visible viewport. Render `object_id` only as identity, not visible copy.

- [ ] **Step 4: Run tests and confirm GREEN**

Run: `flutter test test/scanner/result_overlay_test.dart`

Expected: all tests pass.

- [ ] **Step 5: Commit overlays**

```powershell
git add apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart
git commit -m "feat: draw selectable bakery result overlays"
```

---

### Task 9: Build the Toss-principled bakery evaluation screen

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/main.dart`
- Create: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`

**Interfaces:**
- Consumes: `ScannerController` and `ScannerState`.
- Produces: the evaluation viewer at `1280x820` and `1024x720`.

- [ ] **Step 1: Re-read the approved design and frontend guidance**

Read `docs/superpowers/specs/2026-07-29-flutter-windows-camera-prototype-design.md` and `C:\Users\OMEN\.codex\skills\frontend-design\SKILL.md` completely. Implement the approved scan-first evaluation viewer and its fixed tokens; do not reinterpret it as a checkout screen or analytics dashboard.

- [ ] **Step 2: Write failing hierarchy and copy tests**

Test these exact behaviors:

- only one primary action exists in each mode: `분석하기` or `다시 촬영`;
- the action is disabled until camera and model are both ready;
- startup and analysis states show a Korean phase plus elapsed time;
- result headline follows `총 8개 · 412 ms · GPU`;
- confirmed rows show name, confidence, and path;
- Unknown rows are expanded and show candidates `1`, `2`, and `3` with names and scores;
- model load/warm-up appear only under `모델 정보`;
- no UI string says `정확도` for a live capture;
- row selection highlights the matching overlay.

- [ ] **Step 3: Write failing accessibility and size tests**

At both `1280x820` and `1024x720`, assert no overflow exceptions. Assert every action has a semantic label and a minimum `44x44` target, keyboard focus is visible, and result content scrolls only inside the right rail.

- [ ] **Step 4: Run UI tests and confirm RED**

Run: `flutter test test/ui/scanner_screen_test.dart`

Expected: UI components do not exist.

- [ ] **Step 5: Implement the exact visual token system**

Use:

```dart
const counterCanvas = Color(0xFFEEF1F4);
const cameraInk = Color(0xFF111417);
const resultPaper = Color(0xFFFFFFFF);
const actionBlue = Color(0xFF176BFF);
const confirmedTeal = Color(0xFF0E8A72);
const unknownAmber = Color(0xFFC76B00);
const failureRed = Color(0xFFC43A3A);
```

Use `Segoe UI Variable` with `Malgun Gothic` fallback and tabular number features for time/confidence. Use no gradients, glass effects, ambient animation, or dashboard-card grid.

- [ ] **Step 6: Implement the scan-first composition**

Allocate approximately 70 percent to the camera stage and the remainder to one white receipt-like result rail. Keep camera/model/device status quiet at the top, the scan headline first in the rail, counts second, objects third, and timing/model details in collapsed disclosures. Keep the full-width primary action visible without scrolling.

Show these actionable states exactly:

- `카메라를 찾지 못했습니다` / `카메라 다시 연결`
- `모델을 준비하고 있습니다`
- `모델을 준비하지 못했습니다`
- `이미지를 촬영하지 못했습니다` / `다시 촬영`
- `감지된 빵이 없습니다`

- [ ] **Step 7: Run UI tests and static analysis**

```powershell
flutter test test/ui/scanner_screen_test.dart
flutter analyze
```

Expected: all tests pass and the analyzer reports no issues.

- [ ] **Step 8: Commit the UI**

```powershell
git add apps/bakery_camera_flutter/lib apps/bakery_camera_flutter/test/ui
git commit -m "feat: add bakery camera evaluation UI"
```

---

### Task 10: Add launcher, warm benchmark, and real Windows validation

**Files:**
- Create: `apps/bakery_camera_flutter/Run-Camera-Prototype.ps1`
- Create: `apps/bakery_camera_flutter/README.md`
- Create: `scripts/benchmark_camera_worker.py`
- Create: `tests/prototype/test_camera_benchmark.py`
- Create: `artifacts/evaluations/flutter_camera_prototype_20260729/smoke_report.json`

**Interfaces:**
- Consumes: release executable, explicit Python runtime, connected camera, fixed captured image, and warmed worker.
- Produces: a runnable prototype, 20-run p50/p95 evidence, and real-camera smoke evidence.

- [ ] **Step 1: Write a failing nearest-rank benchmark summary test**

```python
def test_summarize_twenty_warm_runs_uses_nearest_rank_p95():
    values = tuple(float(value) for value in range(1, 21))
    summary = summarize_ms(values)
    assert summary == {"count": 20, "p50": 10.0, "p95": 19.0, "max": 20.0}
```

Also test that benchmark input rejects fewer than 20 measured runs and excludes startup/warm-up.

- [ ] **Step 2: Run the benchmark tests and confirm RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/prototype/test_camera_benchmark.py -q`

Expected: benchmark module does not exist.

- [ ] **Step 3: Implement the fixed-image benchmark**

Start one worker, wait for one `ready`, analyze the same canonical captured image 20 times, reject any second startup event, summarize worker-total and every stage, and write deterministic JSON containing device, model IDs, policy ID, detector threshold, load/warm-up values, run count, p50, p95, and max.

- [ ] **Step 4: Add a location-independent launcher**

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$Python
)
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $appRoot '..\..')).Path
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$exePath = Join-Path $appRoot 'build\windows\x64\runner\Release\bakery_camera_prototype.exe'
$env:BAKERY_INFERENCE_PYTHON = $pythonPath
$env:BAKERY_REPO_ROOT = $repoRoot
& $exePath
exit $LASTEXITCODE
```

The README gives one GPU-runtime example and one embedded CPU-runtime example, explains first startup/warm-up versus per-image timing, and states that live confidence/Top-3 is not accuracy.

- [ ] **Step 5: Verify the worker on automatic GPU and forced CPU**

Run the worker with `--device auto`, send `ping`, one analyze request, and shutdown. Expected on the RTX 5080 PC: one `ready` with `cuda:0`, threshold `0.5691395401954651`, and a clean exit. Repeat with `--device cpu`; expected: the same result schema with `ready.device == "cpu"`.

- [ ] **Step 6: Run the 20-analysis warm benchmark**

```powershell
$env:PYTHONPATH='src'
python scripts/benchmark_camera_worker.py `
  --repo-root . `
  --device auto `
  --image samples/batch2_e3_m3_h3/g20_b02_e_0301.jpg `
  --runs 20 `
  --output artifacts/evaluations/flutter_camera_prototype_20260729/warm_benchmark.json
```

Expected: exactly one startup/warm-up, 20 measured results, and p50/p95 for worker total and all stages.

- [ ] **Step 7: Run all automated verification and build release**

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/prototype tests/classification/test_runtime.py tests/test_rfdetr.py -q
Set-Location apps/bakery_camera_flutter
flutter test
flutter analyze
flutter build windows --release
```

Expected: every command exits 0.

- [ ] **Step 8: Perform the connected-camera smoke**

Launch the release app and confirm:

- live preview and still capture work;
- `분석하기` stays disabled until camera and warmed model are ready;
- two consecutive captures do not reload or warm models;
- GPU is shown on the RTX 5080 PC;
- frozen-image boxes align at both supported window sizes;
- registered counts plus Unknown equal total objects;
- every Unknown shows exactly three ranked candidates;
- headline press-to-result time, worker total, and stage details are distinct;
- `다시 촬영`, no-camera reconnect, and empty-detection states are legible.

Record the selected device, startup/load/warm-up values, both real-camera press-to-result values, object/count checks, overlay checks, and the fixed-image benchmark path in `smoke_report.json`. Do not record an accuracy percentage for the unlabeled live captures.

- [ ] **Step 9: Commit launcher, benchmark, and documentation**

```powershell
git add apps/bakery_camera_flutter/Run-Camera-Prototype.ps1 apps/bakery_camera_flutter/README.md scripts/benchmark_camera_worker.py tests/prototype/test_camera_benchmark.py artifacts/evaluations/flutter_camera_prototype_20260729
git commit -m "test: validate camera evaluator on Windows"
```
