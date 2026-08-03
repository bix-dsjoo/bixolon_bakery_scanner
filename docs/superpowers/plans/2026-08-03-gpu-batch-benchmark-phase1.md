# GPU Batch and Benchmark Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the camera worker's per-object classifier loop and produce trustworthy E/M/H RTX 5080 evidence that determines the next TensorRT optimization step.

**Architecture:** The detector preserves canonical RF-DETR behavior, while all ordered detector boxes are passed once to the existing `ClassifierPipeline.infer_many`. The benchmark moves from one repeatedly measured image to a fixed grouped manifest and reports per-group/overall percentiles with fallback and conditional-DINO evidence.

**Tech Stack:** Python 3.11, PyTorch 2.13 CUDA, pytest, persistent JSON Lines camera worker.

## Global Constraints

- Do not change model weights, detector threshold, preprocessing, calibration, fusion policy or Unknown acceptance.
- Preserve detector order, box coordinates, one decision per candidate and all provenance.
- Keep canonical CPU and `portable_cpu_smoke/` unchanged.
- Never claim p95 improvement without a committed result receipt.
- Skipped artifact/GPU suites are unverified, not passed.
- This phase ends at an evidence checkpoint. TensorRT FP16 implementation starts only after the receipt identifies remaining stage budgets and export/runtime compatibility.

---

## File Structure

- `src/bakery_scanner/prototype/camera_runtime.py`: one batch classifier call per image.
- `configs/gpu_rfdetr_classifier_policy.yaml`: explicit GPU batch mode and object microbatch policy.
- `scripts/benchmark_camera_worker.py`: grouped E/M/H benchmark and receipt builder.
- `benchmarks/protocols/`: fixed manifest schema and reviewed protocol.
- `tests/prototype/test_camera_runtime.py`: batch ordering and conditional-DINO contract.
- `tests/prototype/test_camera_benchmark.py`: grouped percentile and fallback rejection contract.

### Task 1: Camera Worker Batch Classification

**Files:**
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Modify: `configs/gpu_rfdetr_classifier_policy.yaml`
- Test: `tests/prototype/test_camera_runtime.py`

**Interfaces:**
- Consumes: `ClassifierPipeline.infer_many(image, boxes, repvit_max_objects, dino_max_objects)`.
- Produces: one ordered `BatchInferenceResult` per image and unchanged result-object semantics.

- [ ] **Step 1: Write a failing batch-only runtime test**

```python
def test_camera_runtime_batches_all_ordered_objects_once(tmp_path):
    classifier = FakeBatchClassifier()
    classifier.infer = lambda *args, **kwargs: pytest.fail("serial infer used")
    result = _runtime(tmp_path, classifier=classifier).analyze(IMAGE, "batch-1")
    assert classifier.infer_many_calls == [EXPECTED_ORDERED_BOXES]
    assert [row["object_id"] for row in result["objects"]] == ["object-1", "object-2", "object-3"]
```

- [ ] **Step 2: Run the focused test and verify serial-loop failure**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py -q`

Expected: FAIL because `analyze` calls `classifier.infer` once per proposal.

- [ ] **Step 3: Implement one batch call**

```python
boxes = tuple(proposal.box for proposal in ordered)
batch = backend.classifier.infer_many(
    frame,
    boxes,
    repvit_max_objects=_batch_limit(backend.classifier.config.runtime.repvit_microbatch_objects, len(boxes)),
    dino_max_objects=_batch_limit(backend.classifier.config.runtime.dinov3_microbatch_objects, len(boxes)),
)
if len(batch.decisions) != len(ordered):
    raise ValueError("classifier batch decisions must align with detector proposals")
decisions = list(zip(ordered, batch.decisions, strict=True))
```

Set the GPU config to `mode: batch_pytorch`, `repvit_microbatch_objects: all`, and `dinov3_microbatch_objects: all`. Emit the rechecking progress phase when `batch.dino_object_count > 0`. Use batch stage timings rather than summing identical per-object batch timings.

- [ ] **Step 4: Verify camera runtime and worker tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the batch runtime**

```powershell
git add src/bakery_scanner/prototype/camera_runtime.py configs/gpu_rfdetr_classifier_policy.yaml tests/prototype/test_camera_runtime.py
git commit -m "perf: batch camera classifier objects"
```

### Task 2: Grouped E/M/H Benchmark Contract

**Files:**
- Create: `benchmarks/protocols/rtx5080_worker_p95_v1.json`
- Modify: `scripts/benchmark_camera_worker.py`
- Modify: `tests/prototype/test_camera_benchmark.py`

**Interfaces:**
- Consumes: manifest rows `{group, image_path}` and worker result events.
- Produces: schema-v2 report with per-group and overall percentiles, object count, DINO rate and fallback audit.

- [ ] **Step 1: Write failing grouped-report tests**

```python
def test_report_requires_one_hundred_observations_per_group():
    with pytest.raises(ValueError, match="100 observations"):
        build_grouped_report(READY, {"E": RESULTS_99, "M": RESULTS_100, "H": RESULTS_100})


def test_report_rejects_gpu_fallback_and_reports_p99():
    ready = _ready(device="cuda:0", fallback_reason="cuda_load_failed")
    with pytest.raises(ValueError, match="fallback"):
        build_grouped_report(ready, GROUPED_RESULTS)
```

- [ ] **Step 2: Run benchmark tests and verify missing grouped API**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_benchmark.py -q`

Expected: FAIL because the current report supports one image, 20 runs, p50/p95/max only.

- [ ] **Step 3: Implement strict manifest and grouped summaries**

```python
GROUPS = ("E", "M", "H")
MINIMUM_GROUP_OBSERVATIONS = 100
PERCENTILES = (0.50, 0.90, 0.95, 0.99)

def summarize_ms(values):
    ordered = sorted(_finite_ms(value) for value in values)
    return {
        "count": len(ordered),
        "p50": _nearest_rank(ordered, 0.50),
        "p90": _nearest_rank(ordered, 0.90),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
    }
```

The report must contain image ID, group, object count, Unknown count, DINO execution indicator, runtime identity and stage timings for every observation. Reject a non-CUDA device, any fallback reason, duplicated request ID or missing group.

- [ ] **Step 4: Define the protocol artifact**

`rtx5080_worker_p95_v1.json` fixes: at least 20 warm-ups, at least 100 measured observations per E/M/H, alternating image order, warmed worker boundary, p95 <=100ms for each group and overall, and no fallback samples.

- [ ] **Step 5: Run benchmark contract tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_benchmark.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the benchmark contract**

```powershell
git add benchmarks/protocols/rtx5080_worker_p95_v1.json scripts/benchmark_camera_worker.py tests/prototype/test_camera_benchmark.py
git commit -m "bench: add grouped RTX 5080 latency receipt"
```

### Task 3: Hermetic Regression and GPU Preflight

**Files:**
- Modify: `tests/prototype/test_camera_runtime.py`
- Modify: `tests/prototype/test_camera_benchmark.py`
- Create after measurement: `benchmarks/results/rtx5080_gpu_batch_fp32_20260803.json`
- Create after measurement: `benchmarks/summaries/rtx5080_gpu_batch_fp32_20260803.md`

**Interfaces:**
- Consumes: Tasks 1-2 and external model/data artifacts.
- Produces: committed evidence or an explicit unverified preflight report.

- [ ] **Step 1: Add serial-reference versus batch decision parity test**

```python
assert [row.box for row in batch.decisions] == [row.box for row in serial]
assert [row.decision_path for row in batch.decisions] == [row.decision_path for row in serial]
assert [row.sku_id for row in batch.decisions] == [row.sku_id for row in serial]
assert [tuple(c.sku_id for c in row.top5) for row in batch.decisions] == [
    tuple(c.sku_id for c in row.top5) for row in serial
]
```

- [ ] **Step 2: Run the full hermetic Python suite**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest`

Expected: all selected tests pass; unavailable artifact/GPU/slow suites are listed as unverified.

- [ ] **Step 3: Verify local artifacts before GPU execution**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m bakery_scanner.artifacts.cli verify --lock artifacts.lock.json`

Expected: every declared runtime artifact verifies. If any is absent or mismatched, stop GPU claims and record the exact missing IDs; do not fabricate a receipt.

- [ ] **Step 4: Execute the grouped RTX 5080 benchmark when preflight passes**

Run: `python scripts/benchmark_camera_worker.py --repo-root . --device cuda --manifest C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\manifest.json --protocol benchmarks/protocols/rtx5080_worker_p95_v1.json --output C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\gpu_batch_fp32_raw.json`

Expected: a schema-v2 external raw receipt with at least 100 observations in each group and no fallback.

- [ ] **Step 5: Commit only the compact reviewed receipt and summary**

The compact result records manifest ID/hash rather than private image paths, all runtime/artifact hashes, per-group/overall percentiles, DINO rates, and the quality-parity receipt ID. If p95 remains above 100ms, the summary states the measured bottleneck and opens the next TensorRT subproject without claiming target completion.

- [ ] **Step 6: Commit the evidence checkpoint**

```powershell
git add tests/prototype benchmarks/results benchmarks/summaries
git commit -m "bench: record GPU batch FP32 checkpoint"
```
