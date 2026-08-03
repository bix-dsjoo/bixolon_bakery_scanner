# GPU Batch Evidence Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align usable-scene Unknown routing with Top3 customer review, replace per-object camera classification with the existing batch classifier, and produce trustworthy E/M/H RTX 5080 evidence for the TensorRT phase.

**Architecture:** The canonical model/policy path remains unchanged. A new immutable presentation policy separates detector-scene retakes from classification ambiguity, while `CameraInferenceRuntime` sends all stable ordered boxes through `ClassifierPipeline.infer_many` once per image. A grouped benchmark receipt reports per-sample wall time, stage time, object count and conditional-DINO rate without permitting GPU fallback.

**Tech Stack:** Python 3.11, PyTorch 2.13.0+cu130, torchvision 0.28.0+cu130, RF-DETR 1.8.3, pytest 9, Flutter/Dart contract tests, RTX 5080 CUDA runtime.

## Global Constraints

- Preserve `configs/pipelines/canonical_cpu.yaml` and its RF-DETR-L -> RepViT -> conditional DINOv3 -> immutable fusion semantics.
- Load the detector threshold from `models/rfdetr_large_bakery_v1/manifest.json`; never hard-code a second threshold.
- Preserve exact `unknown_top3`, three unique ranked candidates, stable canonical box order and complete provenance.
- A usable scene with classification ambiguity routes to `Unknown + Top3`; only zero detections and calibrated overlap route to retake in this phase.
- Do not change model weights, preprocessing, calibrated gate, fusion margin `0.85`, support/prototype banks or SKU acceptance.
- Do not modify `portable_cpu_smoke/` or legacy behavior.
- Measure file read through in-memory result payload; exclude camera capture, IPC, Flutter render and user interaction.
- Do not claim the 100ms target until a committed E/M/H performance receipt passes every group.
- Skipped artifact/GPU suites are `unverified`, not passed.
- TensorRT, ONNX and Torch-TensorRT are absent from the current local Python environment. This phase ends at the evidence gate; the follow-on engine plan starts after its exact runtime bundle and phase-1 receipt are fixed.

---

## File Structure

- `policies/presentation/camera_action_state_v2.json`: immutable scene-only presentation policy artifact.
- `src/bakery_scanner/prototype/presentation_policy.py`: parse v1 for compatibility and execute v2 scene routing.
- `src/bakery_scanner/prototype/camera_protocol.py`: validate v2 result presentation identity.
- `src/bakery_scanner/prototype/camera_runtime.py`: load v2 and batch all ordered classifier objects.
- `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`: accept v2 presentation while preserving Top3.
- `configs/gpu_rfdetr_classifier_policy.yaml`: explicit GPU batch mode and all-object microbatching.
- `src/bakery_scanner/benchmarking/gpu_worker_receipt.py`: deterministic grouped latency receipt contract.
- `scripts/benchmark_camera_worker.py`: worker orchestration and external raw-run writer.
- `benchmarks/protocols/rtx5080_worker_p95_v1.json`: reviewed E/M/H protocol.
- `benchmarks/summaries/rtx5080_gpu_batch_fp32_20260803.md`: compact reviewed outcome after a valid run.
- Focused Python/Flutter tests verify each producer/consumer boundary.

## Task 1: Scene-Only Presentation Policy v2

**Files:**
- Create: `policies/presentation/camera_action_state_v2.json`
- Modify: `src/bakery_scanner/prototype/presentation_policy.py`
- Modify: `src/bakery_scanner/prototype/camera_protocol.py`
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`
- Modify: `deployment/camera_installer/payload-paths.json`
- Test: `tests/prototype/test_presentation_policy.py`
- Test: `tests/prototype/test_camera_protocol.py`
- Test: `tests/prototype/test_camera_runtime.py`
- Test: `tests/deployment/test_camera_installer_payload.py`
- Test: `tests/deployment/test_camera_installer_manifest.py`
- Test: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Test: `apps/bakery_camera_flutter/test/persistence/checkout_audit_store_test.dart`

**Interfaces:**
- Consumes: proposal objects with canonical `bbox_xyxy` and classification decisions with immutable `top3`.
- Produces: `PresentationPolicy` v2 with `policy_id="camera_action_state_v2"`; result state is `normal`, `unknown`, or `needs_retake`, and v2 retake instruction is only `no_bread_detected` or `separate_breads`.

- [ ] **Step 1: Write failing Python policy tests**

```python
def test_v2_weak_unknown_routes_to_top3_review_not_retake(tmp_path):
    policy = _load_v2_policy(tmp_path)
    result = policy.evaluate(
        proposals=[_proposal("object-1", (0, 0, 20, 20))],
        decisions=[_decision("object-1", sku_id=None, top3=[(1, 0.01), (2, 0.01), (3, 0.0)])],
    )
    assert result.state == "unknown"
    assert result.final_count_usable is True
    assert result.candidate_object_ids == ("object-1",)
    assert result.retake_object_ids == ()


def test_v2_overlap_still_requires_retake(tmp_path):
    policy = _load_v2_policy(tmp_path)
    result = policy.evaluate(proposals=OVERLAPPING_PROPOSALS, decisions=DECISIONS)
    assert result.state == "needs_retake"
    assert result.instruction_code == "separate_breads"
    assert result.candidate_object_ids == ()
```

- [ ] **Step 2: Run Python policy tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_presentation_policy.py -q`

Expected: FAIL because policy v2 is absent and v1 routes weak evidence to `candidate_evidence_weak` retake.

- [ ] **Step 3: Add the immutable policy artifact and strict v2 loader**

```json
{
  "box_overlap_iou": 0.7,
  "policy_id": "camera_action_state_v2",
  "schema_version": 2
}
```

`PresentationPolicy.load` must bind `policy_sha256` to the exact bytes. Add `schema_version: Literal[1, 2]` and make the two v1 candidate-threshold fields optional only in memory for v2; reject missing threshold fields in v1 and reject extra threshold fields in v2. Preserve parsing of `configs/camera_presentation_policy.json` for focused v1 compatibility tests, but `CameraInferenceRuntime.initialize` must load only `policies/presentation/camera_action_state_v2.json` for new runs.

- [ ] **Step 4: Implement v2 routing**

```python
if not normalized_proposals:
    return self._scan_retake("no_bread_detected")
if object_ids := _overlapping_object_ids(normalized_proposals, self.box_overlap_iou):
    return self._object_retake("separate_breads", object_ids)
if object_ids := _unknown_ids(normalized_decisions):
    return self._unknown(object_ids)
return self._normal()
```

Do not use Top1 score or Top1-Top2 margin in v2.

- [ ] **Step 5: Write failing protocol and Dart parser tests**

```python
def test_protocol_accepts_v2_scene_policy_result():
    result = _result(_presentation(policy_id="camera_action_state_v2"))
    validate_result_event(result)
```

```dart
test('accepts camera action state v2 while preserving exact Top3', () {
  final result = InferenceResult.fromJson(resultJson(policyId: 'camera_action_state_v2'));
  expect(result.presentation.policyId, 'camera_action_state_v2');
  expect(result.objects.last.candidates, hasLength(3));
});
```

- [ ] **Step 6: Run protocol/parser tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py -q`

Run: `flutter test test/inference/inference_models_test.dart`

Working directory for the Flutter command: `apps/bakery_camera_flutter`

Expected: FAIL because both strict consumers currently accept only `camera_action_state_v1`.

- [ ] **Step 7: Update strict consumers to v2**

Keep result fields unchanged. Accept `camera_action_state_v2`, require its SHA-256, forbid `candidate_evidence_weak` for v2, and continue requiring exactly three ranked candidates for every candidate object ID.

- [ ] **Step 8: Bind v2 into the installer payload**

Add `policies/presentation/camera_action_state_v2.json` to `deployment/camera_installer/payload-paths.json` and update payload/manifest tests to assert its exact relative path and SHA-256. Keep the v1 config file in the payload for compatibility, but production runtime admission must name and load v2.

- [ ] **Step 9: Verify Top3 and catalog resolution audit separation**

The existing Flutter checkout tests must explicitly prove that selecting an exact candidate records `resolution_source="customer_top3"` with rank 1, 2, or 3, while selecting from full catalog search records `resolution_source="customer_catalog"` with no candidate rank. Both paths must reference the immutable inference object instead of overwriting its `sku_id`, `top3`, or provenance. Add a focused regression only if the existing assertions do not cover all three conditions.

- [ ] **Step 10: Run focused Python and Flutter tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_presentation_policy.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Run: `flutter test test/inference/inference_models_test.dart test/ui/customer_checkout_contract_test.dart test/persistence/checkout_audit_store_test.dart`

Expected: all focused tests pass.

- [ ] **Step 11: Commit policy v2**

```powershell
git add policies/presentation/camera_action_state_v2.json deployment/camera_installer/payload-paths.json src/bakery_scanner/prototype/presentation_policy.py src/bakery_scanner/prototype/camera_protocol.py src/bakery_scanner/prototype/camera_runtime.py tests/prototype tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py apps/bakery_camera_flutter/lib/src/inference/inference_models.dart apps/bakery_camera_flutter/test/inference/inference_models_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart apps/bakery_camera_flutter/test/persistence/checkout_audit_store_test.dart
git commit -m "feat: route usable Unknown scans to Top3 review"
```

## Task 2: Camera Worker All-Object Batch Classification

**Files:**
- Modify: `configs/gpu_rfdetr_classifier_policy.yaml`
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Test: `tests/prototype/test_camera_classifier_configs.py`
- Test: `tests/prototype/test_camera_runtime.py`
- Test: `tests/prototype/test_camera_worker.py`

**Interfaces:**
- Consumes: `ClassifierPipeline.infer_many(image, boxes, *, repvit_max_objects, dino_max_objects) -> BatchInferenceResult`.
- Produces: one aligned `BatchInferenceResult` per analyzed image and unchanged worker JSON object semantics.

- [ ] **Step 1: Write a failing batch-only runtime test**

```python
def test_camera_runtime_batches_all_ordered_objects_once(tmp_path):
    classifier = FakeBatchClassifier(decisions=DECISIONS)
    classifier.infer = lambda *args, **kwargs: pytest.fail("serial infer used")
    runtime = _runtime(tmp_path, classifier=classifier, proposals=UNSORTED_PROPOSALS)

    result = runtime.analyze(IMAGE, "batch-objects")

    assert classifier.infer_many_calls == [EXPECTED_ORDERED_BOXES]
    assert [row["object_id"] for row in result["objects"]] == ["object-1", "object-2", "object-3"]
    assert [row["decision_path"] for row in result["objects"]] == EXPECTED_PATHS
```

- [ ] **Step 2: Run camera runtime tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py::test_camera_runtime_batches_all_ordered_objects_once -q`

Expected: FAIL because `analyze` invokes `classifier.infer` once per proposal.

- [ ] **Step 3: Make GPU batch mode explicit in configuration**

```yaml
runtime:
  device: CUDA:0
  precision: FP32
  mode: batch_pytorch
  repvit_microbatch_objects: all
  dinov3_microbatch_objects: all
```

Update the config contract test to require these exact GPU values while leaving the CPU canonical config unchanged.

- [ ] **Step 4: Replace the per-object loop with one batch call**

```python
boxes = tuple(proposal.box for proposal in ordered)
batch = backend.classifier.infer_many(
    frame,
    boxes,
    repvit_max_objects=_batch_limit(
        backend.classifier.config.runtime.repvit_microbatch_objects,
        len(boxes),
    ),
    dino_max_objects=_batch_limit(
        backend.classifier.config.runtime.dinov3_microbatch_objects,
        len(boxes),
    ),
)
if len(batch.decisions) != len(ordered):
    raise ValueError("classifier batch decisions must align with detector proposals")
decisions = list(zip(ordered, batch.decisions, strict=True))
```

Define `_batch_limit(value: int | str, object_count: int) -> int` so `"all"` resolves to `max(1, object_count)` and integer values pass through unchanged. Emit `rechecking` when `batch.dino_object_count > 0`. Use `batch.timings.repvit_ms` and `batch.timings.dinov3_ms`; do not sum the same batch duration once per object.

- [ ] **Step 5: Add fail-closed alignment and empty-scene tests**

```python
def test_camera_runtime_rejects_misaligned_batch_decisions(tmp_path):
    with pytest.raises(ValueError, match="align"):
        _runtime(tmp_path, classifier=ONE_DECISION_FOR_TWO_BOXES).analyze(IMAGE, "misaligned")


def test_empty_scene_never_calls_classifier(tmp_path):
    runtime = _runtime(tmp_path, proposals=(), classifier=FailIfCalledClassifier())
    result = runtime.analyze(IMAGE, "empty")
    assert result["objects"] == []
    assert result["presentation"]["instruction_code"] == "no_bread_detected"
```

- [ ] **Step 6: Run worker/config regression tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_classifier_configs.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py -q`

Expected: PASS with stable Top3, box order, progress phases and aggregate counts.

- [ ] **Step 7: Commit the batch runtime**

```powershell
git add configs/gpu_rfdetr_classifier_policy.yaml src/bakery_scanner/prototype/camera_runtime.py tests/prototype/test_camera_classifier_configs.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py
git commit -m "perf: batch camera classifier objects"
```

## Task 3: Deterministic Grouped GPU Receipt Contract

**Files:**
- Create: `src/bakery_scanner/benchmarking/gpu_worker_receipt.py`
- Modify: `src/bakery_scanner/benchmarking/__init__.py`
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Modify: `src/bakery_scanner/prototype/camera_protocol.py`
- Create: `tests/benchmarking/test_gpu_worker_receipt.py`
- Create: `benchmarks/protocols/rtx5080_worker_p95_v1.json`
- Modify: `scripts/benchmark_camera_worker.py`
- Modify: `tests/prototype/test_camera_benchmark.py`
- Modify: `tests/prototype/test_camera_protocol.py`
- Modify: `tests/prototype/test_camera_runtime.py`
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`
- Modify: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`

**Interfaces:**
- Consumes: a fixed external manifest with rows `{image_id, group, image_path, image_sha256}` and worker result events.
- Produces: `GpuWorkerReceipt` schema v2 with sample rows and per-stage group/overall summaries; worker and Flutter consumers share the exact eight-stage timing schema.

- [ ] **Step 1: Write failing percentile and group tests**

```python
def test_nearest_rank_summary_includes_p90_p95_p99():
    assert summarize_ms(range(1, 101)) == {
        "count": 100,
        "p50": 50.0,
        "p90": 90.0,
        "p95": 95.0,
        "p99": 99.0,
        "max": 100.0,
    }


def test_receipt_requires_one_hundred_observations_per_group():
    with pytest.raises(ValueError, match="100 observations"):
        build_receipt(READY_CUDA, {"E": E_99, "M": M_100, "H": H_100})
```

- [ ] **Step 2: Run receipt tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/benchmarking/test_gpu_worker_receipt.py -q`

Expected: FAIL because `gpu_worker_receipt` does not exist.

- [ ] **Step 3: Implement strict receipt types**

```python
GROUPS = ("E", "M", "H")
MINIMUM_GROUP_OBSERVATIONS = 100
STAGES = ("decode_preprocess", "detector", "crop", "repvit", "dinov3", "fusion", "postprocess", "total")

@dataclass(frozen=True, slots=True)
class GpuSample:
    request_id: str
    image_id: str
    group: str
    image_sha256: str
    object_count: int
    dino_object_count: int
    timings_ms: Mapping[str, float]

@dataclass(frozen=True, slots=True)
class GpuWorkerReceipt:
    schema_version: Literal[2]
    runtime: Mapping[str, object]
    artifacts: Mapping[str, str]
    samples: tuple[GpuSample, ...]
    summaries: Mapping[str, object]
```

Validate finite non-negative times, unique request IDs, lowercase SHA-256, exact groups, 100 observations per group, `dino_object_count <= object_count`, CUDA device, and `fallback_reason is None`.

- [ ] **Step 4: Write failing worker-orchestrator tests**

```python
def test_benchmark_rejects_cuda_fallback():
    with pytest.raises(ValueError, match="fallback"):
        build_benchmark_report(_ready(fallback_reason="cuda_load_failed"), RESULTS)


def test_benchmark_preserves_group_object_and_dino_counts():
    report = build_benchmark_report(READY, GROUPED_RESULTS)
    assert report["groups"]["H"]["dino_execution_rate"] == 1.0
    assert report["groups"]["E"]["object_count"]["max"] == 3
```

- [ ] **Step 5: Extend the worker result timing and diagnostic contracts**

Change the strict worker `timings_ms` schema on both Python and Dart sides to exactly:

```text
decode_preprocess, detector, crop, repvit, dinov3, fusion, postprocess, total
```

The camera runtime takes `crop`, `repvit`, `dinov3`, and `fusion` once from `BatchInferenceResult.timings`; it must not multiply batch durations by object count. Add `object_count` and `dino_object_count` under a strict `diagnostics` object in the same result. Require `object_count == len(objects)` and `0 <= dino_object_count <= object_count` in `validate_result_event` and `InferenceResult.fromJson`. These values are diagnostics and do not affect SKU/count decisions. Add failing producer/consumer tests before changing the runtime or Dart model.

- [ ] **Step 6: Implement the fixed protocol artifact**

`benchmarks/protocols/rtx5080_worker_p95_v1.json` contains:

```json
{
  "device": "cuda:0",
  "groups": ["E", "M", "H"],
  "minimum_group_observations": 100,
  "minimum_warmups": 20,
  "overall_p95_limit_ms": 100.0,
  "per_group_p95_limit_ms": 100.0,
  "schema_version": 1,
  "worker_boundary": "file_read_to_in_memory_result_payload"
}
```

- [ ] **Step 7: Run receipt/orchestrator tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/benchmarking/test_gpu_worker_receipt.py tests/prototype/test_camera_benchmark.py tests/prototype/test_camera_protocol.py -q`

Expected: PASS.

- [ ] **Step 8: Commit the benchmark contract**

```powershell
git add src/bakery_scanner/benchmarking tests/benchmarking benchmarks/protocols/rtx5080_worker_p95_v1.json scripts/benchmark_camera_worker.py src/bakery_scanner/prototype/camera_runtime.py src/bakery_scanner/prototype/camera_protocol.py tests/prototype/test_camera_benchmark.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py apps/bakery_camera_flutter/lib/src/inference/inference_models.dart apps/bakery_camera_flutter/test/inference/inference_models_test.dart
git commit -m "bench: add grouped RTX 5080 worker receipt"
```

## Task 4: Hermetic Parity Gate

**Files:**
- Create: `src/bakery_scanner/benchmarking/decision_parity.py`
- Modify: `src/bakery_scanner/benchmarking/__init__.py`
- Create: `tests/benchmarking/test_decision_parity.py`
- Create: `tests/integration/test_gpu_batch_parity.py`
- Modify: `tools/benchmark/README.md`

**Interfaces:**
- Consumes: serial `ClassifierPipeline.infer` and candidate `infer_many` over the same canonical frame/boxes.
- Produces: `DecisionParityReceipt` plus a fail-closed comparison for boxes, SKU, confidence, decision path, Top3, Unknown reason and non-timing provenance.

- [ ] **Step 1: Write the failing parity comparison test**

```python
def test_compare_decisions_rejects_top3_order_change():
    reference = (_decision(top3=(C1, C2, C3)),)
    candidate = (_decision(top3=(C2, C1, C3)),)

    receipt = compare_decisions(reference, candidate)

    assert receipt.passed is False
    assert receipt.mismatches[0].fields == ("top3",)
```

- [ ] **Step 2: Run parity tests and verify RED if batch metadata differs**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/integration/test_gpu_batch_parity.py -q`

Expected: FAIL during collection because `bakery_scanner.benchmarking.decision_parity` does not exist.

- [ ] **Step 3: Implement the deterministic comparison receipt**

```python
@dataclass(frozen=True, slots=True)
class DecisionMismatch:
    index: int
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionParityReceipt:
    reference_count: int
    candidate_count: int
    mismatches: tuple[DecisionMismatch, ...]

    @property
    def passed(self) -> bool:
        return self.reference_count == self.candidate_count and not self.mismatches


def compare_decisions(
    reference: Sequence[ClassificationDecision],
    candidate: Sequence[ClassificationDecision],
) -> DecisionParityReceipt:
    mismatches = []
    for index in range(max(len(reference), len(candidate))):
        if index >= len(reference):
            mismatches.append(DecisionMismatch(index, ("missing_reference",)))
            continue
        if index >= len(candidate):
            mismatches.append(DecisionMismatch(index, ("missing_candidate",)))
            continue
        fields = tuple(
            field
            for field in _PARITY_FIELDS
            if getattr(reference[index], field) != getattr(candidate[index], field)
        )
        if fields:
            mismatches.append(DecisionMismatch(index, fields))
    return DecisionParityReceipt(
        len(reference), len(candidate), tuple(mismatches)
    )
```

Set `_PARITY_FIELDS` exactly to `("decision", "sku_id", "confidence", "box", "decision_path", "top3", "provenance", "unknown_reason")`. Dataclass equality then compares all Top3 SKU/rank/score values and all immutable artifact/model/policy provenance. Exclude only `timings` because serial and batch scheduling legitimately differ. Count mismatch is always a failure. Do not alter scores, gates, rankers or policies.

- [ ] **Step 4: Write the serial-versus-batch integration test**

Run the same canonical frame and stable ordered boxes through `ClassifierPipeline.infer` and `infer_many`, call `compare_decisions`, and assert `receipt.passed`. If this test exposes a metadata-only difference, make the smallest producer fix and add a focused unit test; any raw-score or final-decision difference is a blocking parity failure, not permission to loosen the comparator.

- [ ] **Step 5: Run classification, prototype and parity suites**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/classification tests/prototype tests/benchmarking/test_decision_parity.py tests/integration/test_gpu_batch_parity.py -q`

Expected: PASS.

- [ ] **Step 6: Document the phase-1 command and evidence boundary**

`tools/benchmark/README.md` must state the exact external manifest path, warm-up count, E/M/H observation count, worker boundary, artifact verification command and the prohibition on performance claims without a committed compact summary.

- [ ] **Step 7: Commit the parity gate**

```powershell
git add src/bakery_scanner/benchmarking/decision_parity.py src/bakery_scanner/benchmarking/__init__.py tests/benchmarking/test_decision_parity.py tests/integration/test_gpu_batch_parity.py tools/benchmark/README.md
git commit -m "test: gate GPU batch decision parity"
```

## Task 5: RTX 5080 Preflight and Evidence Checkpoint

**Files:**
- Create: `benchmarks/results/rtx5080_gpu_batch_fp32_20260803.json`
- Create: `benchmarks/summaries/rtx5080_gpu_batch_fp32_20260803.md`
- Modify: `docs/superpowers/specs/2026-08-03-rtx5080-gpu-p95-100ms-design.md` only to link the committed receipt without changing approved requirements.

**Interfaces:**
- Consumes: external model/data artifacts, phase-1 code, protocol `rtx5080_worker_p95_v1`.
- Produces: a compact Git-safe evidence checkpoint or an explicit `unverified` report.

- [ ] **Step 1: Run the complete hermetic Python suite**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest`

Expected: all default-selected tests pass; artifact/GPU/slow skips are listed as unverified.

- [ ] **Step 2: Run Flutter static and contract verification**

Run: `flutter analyze`

Run: `flutter test test/inference test/checkout test/ui/customer_checkout_contract_test.dart`

Working directory: `apps/bakery_camera_flutter`

Expected: both commands exit 0.

- [ ] **Step 3: Verify all declared artifacts**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m bakery_scanner.artifacts.cli --root . --lock artifacts.lock.json`

Expected: every declared artifact matches ID, byte size and SHA-256. If an artifact is absent or mismatched, write the exact ID to the compact summary as `unverified` and do not run or claim GPU performance.

- [ ] **Step 4: Verify external E/M/H manifest identity**

Required file: `C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\manifest.json`

The manifest must contain only external absolute image paths, unique image IDs, groups E/M/H, lowercase image SHA-256, and at least one image per group. The raw receipt repeats the manifest SHA-256; Git stores only that identity.

- [ ] **Step 5: Execute the grouped benchmark**

Run:

```powershell
python scripts/benchmark_camera_worker.py --repo-root . --device cuda --manifest C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\manifest.json --protocol benchmarks/protocols/rtx5080_worker_p95_v1.json --output C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\gpu_batch_fp32_raw.json
```

Expected: schema-v2 raw receipt, at least 100 observations per E/M/H, no fallback, and complete artifact/runtime identity.

- [ ] **Step 6: Write the compact reviewed result**

Always create `benchmarks/results/rtx5080_gpu_batch_fp32_20260803.json`. It contains `status` plus only the evidence that exists: runtime/artifact/manifest hashes, per-group/overall summaries, object-count distribution, DINO rate and parity receipt ID. An unverified checkpoint records the exact missing IDs or manifest failure and omits fabricated timing summaries. It contains no private image paths or raw predictions.

`benchmarks/summaries/rtx5080_gpu_batch_fp32_20260803.md` states one of:

- `passed_phase1_checkpoint`: valid measurement and parity evidence exist.
- `unverified_missing_artifact`: artifact preflight failed with exact IDs.
- `unverified_missing_manifest`: external manifest is absent or invalid.
- `measured_target_miss`: valid measurement exists but one or more p95 gates exceed 100ms.

It must not state that the 100ms goal is complete unless E/M/H and overall p95 all pass.

- [ ] **Step 7: Run repository policy and diff checks**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/contract/test_repository_policy.py -q`

Run: `git diff --check`

Expected: PASS and no whitespace errors.

- [ ] **Step 8: Commit the evidence checkpoint**

```powershell
git add benchmarks/results/rtx5080_gpu_batch_fp32_20260803.json benchmarks/summaries/rtx5080_gpu_batch_fp32_20260803.md docs/superpowers/specs/2026-08-03-rtx5080-gpu-p95-100ms-design.md
git commit -m "bench: record RTX 5080 batch FP32 checkpoint"
```

## Follow-on TensorRT Plan Gate

After Task 5, write a separate implementation plan using the measured dominant stages and the exact provisioned runtime bundle. The current environment reports `tensorrt`, `torch_tensorrt`, `onnx`, and `onnxruntime` as unavailable, so no TensorRT implementation task may claim readiness before these are versioned and hash-bound.

The follow-on plan must consume:

- the committed phase-1 receipt ID and per-stage p95 values;
- exact TensorRT/Torch-TensorRT/ONNX package or wheel IDs, byte sizes and SHA-256;
- RTX 5080 compute capability and driver/CUDA compatibility;
- RF-DETR export output identity from `RFDETRLarge.export(format="tensorrt", batch_size=1, dynamic_batch=False)`;
- RepViT/DINO export graph coverage results;
- engine binding/profile schema and admission tests;
- reference FP32 versus FP16 raw-evidence and final-decision parity tests.

Only then plan RF-DETR engine integration, classifier engine integration, tensor crop, CUDA Graph and final locked acceptance. This evidence gate prevents implementing against an invented or unavailable runtime API.
