# Production E2E Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic GPU E2E bakery-scanner runtime and a 299-image grouped-OOF report with Top-1, Top-3, FP, Unknown, and latency.

**Architecture:** The original three 20-SKU COCO sources become immutable evaluation labels while the detector staging output remains one-class. Strict assurance, classifier, E2E, and benchmark modules compose the required pipeline and create only provenance-backed reports.

**Tech Stack:** Python 3.11, PyTorch CUDA 12.8 on RTX 5080 cuda:0, torchvision, timm, Pillow, NumPy, Pydantic, pytest.

## Global Constraints

- Source coordinates are preserved; a final item is a SKU or `Unknown`, with confidence and path.
- D-FINE proposals keep score >= 0.001/top-30 until assurance; resolver never uses hard NMS.
- MobileNetV4 is first assurance; ConvNeXt-Tiny/DINOv3 are conditional only.
- RepViT uses 5%, 10%, 15% crops; invalid evidence always fails closed to `Unknown`.
- Each target fold uses other folds only. The 299-image result is grouped OOF development, never a release claim.
- Runtime is CUDA:0/FP32/deterministic. Timings synchronize every stage and whole-image path.

---

### Task 1: SKU ground truth and final contracts

**Files:**
- Create: `src/bakery_scanner/e2e/__init__.py`
- Create: `src/bakery_scanner/e2e/contracts.py`
- Create: `src/bakery_scanner/e2e/ground_truth.py`
- Create: `tests/e2e/test_contracts.py`
- Create: `tests/e2e/test_ground_truth.py`

**Interfaces:** `FinalObject(box, sku_id, confidence, decision_path, top3)`, `SkuGroundTruth(image_id, box, sku_id)`, and `load_source_sku_ground_truth(config)`.

- [ ] **Step 1: Write failing tests.**

```python
def test_source_loader_preserves_all_twenty_skus(tmp_path):
    labels = load_source_sku_ground_truth(config_with_three_source_coco_files(tmp_path))
    assert {row.sku_id for rows in labels.values() for row in rows} == set(range(1, 21))

def test_unknown_requires_three_distinct_ranked_skus():
    with pytest.raises(ValueError, match="three distinct"):
        FinalObject(BOX, None, .2, "unknown_top3", (6, 6, 19))
```

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_contracts.py tests/e2e/test_ground_truth.py -q`. Expected: missing `bakery_scanner.e2e`.
- [ ] **Step 3: Implement the contracts and loader.** Require finite `[0,1]` confidence; Unknown requires `unknown_top3` and three unique IDs; SKU decisions require no Top-3 and a valid direct/recheck path. Read each original COCO source, verify category IDs/names against `datasets/classes.json`, convert `xywh` to `Box`, and do not change staged annotations.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_contracts.py tests/e2e/test_ground_truth.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/e2e tests/e2e; git commit -m "feat: add sku-aware e2e contracts"`.

### Task 2: Box Assurance contracts and component resolver

**Files:**
- Create: `src/bakery_scanner/verifier/assurance.py`
- Create: `src/bakery_scanner/detectors/proposal_graph.py`
- Create: `tests/test_box_assurance_contracts.py`
- Create: `tests/test_proposal_graph.py`

**Interfaces:** `BoxAssurancePrediction`, `AssuranceBackend`, `AssurancePolicy`, `build_proposal_components(proposals)`, and `resolve_component(component, predictions, policy)`.

- [ ] **Step 1: Write failing tests.**

```python
def test_overlap_does_not_delete_either_candidate():
    assert build_proposal_components((LEFT, RIGHT))[0].members == (LEFT, RIGHT)

def test_unresolved_multiple_becomes_unknown_not_merged():
    assert resolve_component(merged_component(), predictions(), policy())[0].outcome == "Unknown"
```

Test state-probability normalization, finite deltas, in-bounds corrections, exact-one duplicate resolution, partial local re-evaluation, and multiple-box recovery.

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/test_box_assurance_contracts.py tests/test_proposal_graph.py -q`. Expected: missing modules.
- [ ] **Step 3: Implement.** Link candidates only by same-image overlap, containment, or normalized-center distance; retain every member. Reject INVALID, preserve compatible EXACTLY_ONE, apply finite clipped PARTIAL delta then re-evaluate locally, use independent candidates for MULTIPLE, otherwise emit Unknown.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/test_box_assurance_contracts.py tests/test_proposal_graph.py tests/test_proposal_policy.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/verifier/assurance.py src/bakery_scanner/detectors/proposal_graph.py tests/test_box_assurance_contracts.py tests/test_proposal_graph.py; git commit -m "feat: resolve box assurance components"`.

### Task 3: Conditional MobileNetV4/ConvNeXt models and OOF artifacts

**Files:**
- Modify: `src/bakery_scanner/verifier/model.py`
- Modify: `src/bakery_scanner/verifier/data.py`
- Create: `scripts/run_box_assurance_oof.ps1`
- Create: `tests/test_assurance_model.py`
- Create: `tests/test_box_assurance_oof.py`

**Interfaces:** `build_assurance_model(backend, pretrained=False)`, `run_assurance_cascade(mobile, convnext, candidates, image)`, and a hash-validated five-fold runner.

- [ ] **Step 1: Write failing tests.**

```python
def test_model_has_state_quality_and_delta_heads():
    state, quality, delta = build_assurance_model(AssuranceBackend.MOBILE)(torch.zeros(2, 3, 224, 224))
    assert state.shape == (2, 4) and quality.shape == (2,) and delta.shape == (2, 4)

def test_confident_mobile_skips_convnext():
    assert run_assurance_cascade(confident_mobile(), counting_convnext(), (PROPOSAL,), IMAGE).convnext_invocations == 0
```

Test low-quality/PARTIAL fallback once and receipt rejection when held-out labels enter training.

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/test_assurance_model.py tests/test_box_assurance_oof.py -q`. Expected: absent dual-head/OOF API.
- [ ] **Step 3: Implement.** Build timm backbones with four state logits, one quality logit, and four deltas; train state CE, quality BCE, and state-specific Smooth L1. ConvNeXt runs only for low margin/quality, PARTIAL/MULTIPLE, or graph conflict. Train sequential CUDA folds, validate D-FINE receipts, record hashes/predictions, and refuse CPU or overwrite.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/test_assurance_model.py tests/test_box_assurance_oof.py tests/test_verifier_model.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/verifier scripts/run_box_assurance_oof.ps1 tests/test_assurance_model.py tests/test_box_assurance_oof.py; git commit -m "feat: add conditional box assurance runners"`.

### Task 4: Conditional RepViT/DINOv3 SKU classifier

**Files:**
- Create: `src/bakery_scanner/classification/__init__.py`
- Create: `src/bakery_scanner/classification/contracts.py`
- Create: `src/bakery_scanner/classification/preprocess.py`
- Create: `src/bakery_scanner/classification/repvit.py`
- Create: `src/bakery_scanner/classification/dinov3.py`
- Create: `src/bakery_scanner/classification/policy.py`
- Create: `src/bakery_scanner/classification/runtime.py`
- Create: `configs/classifier_policy.yaml`
- Create: `tests/classification/test_runtime.py`
- Create: `tests/classification/test_policy.py`

**Interfaces:** `ClassifierPipeline.load(config_path)`, `ClassifierPipeline.infer(image, box)`, and `PolicyCalibration`.

- [ ] **Step 1: Write failing tests.**

```python
def test_crop_order_is_fixed():
    assert [crop.padding for crop in make_padded_crops(image(), BOX, (.05, .10, .15))] == [.05, .10, .15]

def test_direct_repvit_never_calls_dino():
    dino = CountingDino()
    assert pipeline(confident_repvit(), dino).infer(image(), BOX).decision_path == DecisionPath.REPVIT_DIRECT
    assert dino.calls == 0
```

Also test ambiguous DINO disagreement returns exactly three unique Top-3 candidates.

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/classification/test_runtime.py tests/classification/test_policy.py -q`. Expected: missing classification package.
- [ ] **Step 3: Implement.** Validate all checkpoint/support hashes, class maps, dimensions, and finite score vectors. Average three RepViT probabilities; lazily load/score normalized DINO embeddings only after direct gate failure. Calibration JSON owns temperatures/thresholds/weights. Only all-pass direct/recheck gates emit a SKU; all other paths emit deterministic Unknown + Top-3.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/classification -q`. Expected: PASS, including real checkpoint/support loading with one synthetic RGB crop and 20 finite scores from each configured model.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/classification configs/classifier_policy.yaml tests/classification; git commit -m "feat: add conditional sku classification"`.

### Task 5: Fold-aware E2E runtime and SKU metrics

**Files:**
- Create: `src/bakery_scanner/e2e/runtime.py`
- Create: `src/bakery_scanner/e2e/evaluation.py`
- Create: `scripts/evaluate_e2e.py`
- Create: `tests/e2e/test_runtime.py`
- Create: `tests/e2e/test_evaluation.py`

**Interfaces:** `E2EPipeline.for_fold(fold)`, `E2EPipeline.infer(image_id, image)`, `evaluate_e2e(ground_truth, predictions, thresholds=(.50, .75))`.

- [ ] **Step 1: Write failing tests.**

```python
def test_pipeline_classifies_only_resolved_boxes():
    trace, output = run_with_recording_fakes(resolved=(SKU_BOX, UNKNOWN_BOX))
    assert trace == ["detector", "mobile", "convnext", "resolver", "classifier"]
    assert output[1].sku_id is None

def test_metrics_count_top1_top3_fp_unknown_after_matching():
    report = evaluate_e2e({1: (gt(6), gt(5))}, {1: (sku(6), unknown((7, 5, 19)), sku(3))})
    assert (report.by_iou[.50].top1_correct, report.by_iou[.50].top3_correct, report.by_iou[.50].false_positives, report.by_iou[.50].unknown) == (1, 2, 1, 1)
```

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_runtime.py tests/e2e/test_evaluation.py -q`. Expected: absent modules.
- [ ] **Step 3: Implement.** Select fold-matched artifacts, normalize source boxes, resolve components, classify only resolved boxes, and emit canonical final objects. Match deterministically at IoU .50/.75 and report Top-1, Top-3, FP, Unknown, miss/duplicate/split/merge, quantities, provenance, and `grouped_oof_development_only` for exact 299-image/1,410-object coverage.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_runtime.py tests/e2e/test_evaluation.py -q; python scripts/evaluate_e2e.py --help`. Expected: PASS.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/e2e scripts/evaluate_e2e.py tests/e2e; git commit -m "feat: evaluate sku-aware e2e inference"`.

### Task 6: Warm CUDA benchmark

**Files:**
- Create: `src/bakery_scanner/e2e/benchmark.py`
- Create: `scripts/benchmark_e2e.py`
- Create: `tests/e2e/test_benchmark.py`
- Modify: `README.md`

**Interfaces:** `benchmark_e2e(pipeline, image_ids, warmup_count=10)` and canonical `BenchmarkReport`.

- [ ] **Step 1: Write failing tests.**

```python
def test_reports_mean_percentiles_and_conditional_rates():
    report = aggregate_benchmark((sample(10, False, False), sample(20, True, True), sample(30, False, True)))
    assert (report.total_mean_ms, report.total_p50_ms, report.total_p95_ms) == pytest.approx((20, 20, 29))
    assert report.convnext_rate == pytest.approx(1 / 3) and report.dino_rate == pytest.approx(2 / 3)

def test_rejects_partial_299_image_coverage():
    with pytest.raises(ValueError, match="299"):
        benchmark_e2e(pipeline(), tuple(range(1, 299)))
```

- [ ] **Step 2: Verify RED.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_benchmark.py -q`. Expected: missing benchmark module.
- [ ] **Step 3: Implement.** Require RTX 5080 cuda:0, at least ten warmups, and 299-image coverage. Synchronize CUDA around detector, assurance, classification, and E2E; write stage/E2E mean-p50-p95, precision/device/hashes, and conditional rates. Reject partial/failing runs and document commands in README.
- [ ] **Step 4: Verify GREEN.** Run `$env:PYTHONPATH='src'; python -m pytest tests/e2e/test_benchmark.py -q; python scripts/benchmark_e2e.py --help`. Expected: PASS.
- [ ] **Step 5: Commit.** Run `git add src/bakery_scanner/e2e/benchmark.py scripts/benchmark_e2e.py tests/e2e/test_benchmark.py README.md; git commit -m "feat: benchmark end-to-end gpu pipeline"`.

### Task 7: Generate and audit 299-image evidence

**Files:**
- Generate: `artifacts/box_system/assurance/mobile-fold{0..4}/`
- Generate: `artifacts/box_system/assurance/convnext-fold{0..4}/`
- Generate: `artifacts/e2e/evaluation-299.json`
- Generate: `artifacts/e2e/benchmark-299.json`

- [ ] **Step 1: Verify all code.** Run `$env:PYTHONPATH='src'; python -m pytest tests -q`. Expected: zero failures.
- [ ] **Step 2: Train assurance OOF.** Run `powershell -ExecutionPolicy Bypass -File scripts/run_box_assurance_oof.ps1 -Config configs/box_system.yaml -Device cuda:0`. Expected: valid held-out receipts for both models/five folds.
- [ ] **Step 3: Evaluate all scans.** Run `$env:PYTHONPATH='src'; python scripts/evaluate_e2e.py --config configs/box_system.yaml --classifier-config configs/classifier_policy.yaml --output artifacts/e2e/evaluation-299.json`. Expected: exact 299/1,410 scope and every requested metric at IoU .50/.75.
- [ ] **Step 4: Benchmark all scans.** Run `$env:PYTHONPATH='src'; python scripts/benchmark_e2e.py --config configs/box_system.yaml --classifier-config configs/classifier_policy.yaml --warmup 10 --output artifacts/e2e/benchmark-299.json`. Expected: synchronized stage/E2E latency summary and conditional rates.
- [ ] **Step 5: Audit.** Run `$env:PYTHONPATH='src'; python -m pytest tests -q; git diff --check`. Inspect both JSON reports for counts, metrics, provenance, and development-only limitation before making claims.
