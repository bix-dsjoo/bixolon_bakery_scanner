# Risk-Ranked Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically return a correct Top-1 SKU for at least 90% of registered single-bread crops with registered automatic error rate below 5%, no automatic unregistered SKU, otherwise return `Unknown` plus Top-3 containing the registered truth.

**Architecture:** Collect one full, hash-bound evidence row from the same RepViT/DINO-local path used at runtime.  A capture-group out-of-fold regularized candidate ranker learns SKU ordering, and a separate out-of-fold risk calibrator decides whether the ranked Top-1 is safe to emit.  The runtime consumes one immutable ranker/calibrator artifact and fails closed when any provenance or feature-contract check fails.

**Tech Stack:** Python 3.11, NumPy, scikit-learn, PyTorch, Pydantic, pytest.

## Global Constraints

- Inputs are verifier-confirmed single-bread crops; Detector and Verifier quality are out of scope for this classifier target.
- Batch 1 is development-only; Batch 2 must not participate in feature fitting, model fitting, or threshold selection.
- `auto_correct / registered_count >= 0.90`, `registered_auto_errors / auto_count < 0.05`, registered Unknown Top-3 recall `== 1.0`, and unregistered automatic count `== 0` are required on a fixed locked Batch 2 report; no result may claim OOD coverage without unregistered examples.
- Preserve the existing canonical EXIF visual frame, 5%/10%/15% crop contract, model hashes, and original image box.
- DINO local candidates remain DINO Top-5 union RepViT Top-3, with a maximum of eight candidates and the v3 source-balanced local coreset.
- Every invalid artifact, missing feature, or inference exception returns `Unknown`; do not fall back to an uncalibrated SKU.
- Do not stage `datasets/` or `models/` junctions and do not merge this worktree.

---

### Task 1: Versioned full-evidence contract and collector

**Files:**
- Create: `src/bakery_scanner/classification/full_evidence.py`
- Modify: `scripts/collect_classifier_evidence.py`
- Modify: `src/bakery_scanner/classification/{repvit,dinov3,local_bank}.py`
- Test: `tests/classification/test_full_evidence.py`

**Interfaces:**
- Produces `FullEvidenceRow` with `candidate_sku_ids`, per-candidate features, labels, source group, and all model/local-bank hashes.
- Produces `collect_full_rows(inputs, repvit, prototype_bank, dino, local_bank, *, paddings, provenance) -> tuple[FullEvidenceRow, ...]`.
- `DinoV3Rechecker.score_global_and_local(...)` additionally returns local product-patch count and ratio without changing global/local score values.

- [ ] **Step 1: Write failing serialization and feature-alignment tests**

```python
def test_full_evidence_row_requires_aligned_unique_candidates():
    with pytest.raises(ValueError, match="candidate"):
        FullEvidenceRow(..., candidate_sku_ids=(1, 1), candidate_features=((0.1,), (0.2,)))

def test_collect_full_rows_records_repvit_ood_and_local_patch_metadata():
    row = collect_full_rows((input_row,), fake_repvit, fake_bank, fake_dino, fake_local, paddings=(.05, .10, .15))[0]
    assert row.nearest_prototype_distance == pytest.approx(.02)
    assert row.local_product_patch_count > 0
```

- [ ] **Step 2: Run focused tests to prove the contract is absent**

Run: `python -m pytest tests/classification/test_full_evidence.py -q`

Expected: FAIL because `FullEvidenceRow` and `collect_full_rows` do not exist.

- [ ] **Step 3: Implement canonical evidence rows and exact runtime evidence collection**

```python
@dataclass(frozen=True, slots=True)
class FullEvidenceRow:
    candidate_sku_ids: tuple[int, ...]
    candidate_features: tuple[tuple[float, ...], ...]
    repvit_crop_disagreement: float
    nearest_prototype_distance: float
    local_product_patch_count: int
    local_product_patch_ratio: float

def collect_full_rows(...):
    crops, product_boxes = make_padded_crops_with_product_boxes(...)
    repvit_evidence = repvit.score_with_evidence(crops)
    global_scores, local_evidence = dino.score_global_and_local(...)
    return canonical_full_rows
```

Validate finite feature values, exact canonical SKU IDs, candidate count 1–8, and exact artifact/provenance hashes.  Make `to_json_bytes()` canonical and reject missing/extra keys in `from_mapping()`.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/classification/test_full_evidence.py tests/classification/test_dinov3.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bakery_scanner/classification/full_evidence.py src/bakery_scanner/classification/repvit.py src/bakery_scanner/classification/dinov3.py src/bakery_scanner/classification/local_bank.py scripts/collect_classifier_evidence.py tests/classification/test_full_evidence.py tests/classification/test_dinov3.py
git commit -m "feat: collect full classifier ranking evidence"
```

### Task 2: Capture-group cross-fit candidate ranker

**Files:**
- Create: `src/bakery_scanner/classification/fusion_ranker.py`
- Modify: `src/bakery_scanner/classification/full_evidence.py`
- Test: `tests/classification/test_fusion_ranker.py`

**Interfaces:**
- Produces `FusionRankerArtifact` with schema version, feature schema, regularization, model coefficients, intercept, evidence hash, and exact artifact hashes.
- `fit_oof_ranker(rows, *, folds, seed) -> OofRankingResult` returns one held-out ranked result for every development row.
- `FusionRankerArtifact.rank(row) -> RankedCandidates` returns all candidate SKUs in deterministic score-descending/SKU-ascending order.

- [ ] **Step 1: Write failing ranker isolation and deterministic-order tests**

```python
def test_oof_ranker_never_trains_on_its_held_out_capture_group():
    result = fit_oof_ranker(rows, folds=2, seed=7)
    assert all(group not in fold.training_groups for group, fold in result.held_out_groups)

def test_ranker_breaks_equal_scores_by_sku_id():
    assert artifact.rank(row).sku_ids[:2] == (4, 8)
```

- [ ] **Step 2: Run focused tests to prove the ranker is absent**

Run: `python -m pytest tests/classification/test_fusion_ranker.py -q`

Expected: FAIL because `fusion_ranker` does not exist.

- [ ] **Step 3: Implement a regularized candidate logistic ranker**

```python
def candidate_matrix(rows):
    # One row per (sample, candidate); target is candidate_sku_id == true sku.
    return features, labels, sample_indices

def fit_oof_ranker(rows, *, folds, seed):
    # StratifiedGroupKFold by capture_group; fit LogisticRegression(C=0.1,
    # class_weight="balanced", random_state=seed, max_iter=2000) per fold.
```

Use only registered development rows, standardize feature columns using each training fold only, and persist final-fit scaler/coefficients.  Reject an artifact whose feature schema or evidence/model hashes differ.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/classification/test_fusion_ranker.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bakery_scanner/classification/fusion_ranker.py src/bakery_scanner/classification/full_evidence.py tests/classification/test_fusion_ranker.py
git commit -m "feat: rank classifier candidates out of fold"
```

### Task 3: Risk calibrator and constrained threshold selection

**Files:**
- Create: `src/bakery_scanner/classification/risk_calibrator.py`
- Modify: `src/bakery_scanner/classification/fusion_ranker.py`
- Test: `tests/classification/test_risk_calibrator.py`

**Interfaces:**
- `RiskCalibratorArtifact.predict_risk(ranked_row) -> float` returns a finite value in `[0, 1]`.
- `select_zero_error_threshold(oof_rows) -> float | None` returns the lowest risk threshold whose automatic OOF predictions have zero errors and correct Top-1 coverage of at least 0.90, otherwise `None`.
- `RiskCalibratorArtifact.decide(ranked_row) -> Literal["sku", "unknown"]` uses only its immutable selected threshold.

- [ ] **Step 1: Write failing zero-error/coverage tests**

```python
def test_selector_chooses_most_permissive_zero_error_threshold_at_90_coverage():
    threshold = select_zero_error_threshold(oof_rows)
    assert threshold == pytest.approx(0.31)

def test_selector_returns_none_when_zero_error_cannot_reach_90_percent():
    assert select_zero_error_threshold(oof_rows) is None
```

- [ ] **Step 2: Run focused tests to prove selection is absent**

Run: `python -m pytest tests/classification/test_risk_calibrator.py -q`

Expected: FAIL because `risk_calibrator` does not exist.

- [ ] **Step 3: Implement out-of-fold risk calibration**

```python
def risk_features(ranked_row):
    return (ranked_row.top1_score, ranked_row.top1_margin,
            ranked_row.repvit_crop_disagreement,
            ranked_row.nearest_prototype_distance,
            ranked_row.dino_global_margin,
            ranked_row.local_margin,
            ranked_row.local_product_patch_ratio)
```

Fit a regularized logistic model whose positive target means “ranked Top-1 is wrong”.  Produce OOF risk predictions with the same capture-group folds, enumerate sorted unique risk values, and select the greatest accepted set satisfying both constraints.  If no threshold meets 90%/0-error, write a fail-closed artifact with `threshold=None` and report its measured maximum safe coverage.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/classification/test_risk_calibrator.py tests/classification/test_fusion_ranker.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bakery_scanner/classification/risk_calibrator.py src/bakery_scanner/classification/fusion_ranker.py tests/classification/test_risk_calibrator.py
git commit -m "feat: select zero-error classifier risk gate"
```

### Task 4: Immutable runtime artifact and fail-closed decision path

**Files:**
- Modify: `src/bakery_scanner/classification/{config,contracts,runtime,policy}.py`
- Create: `scripts/train_classifier_fusion_policy.py`
- Test: `tests/classification/{test_config,test_contracts,test_runtime}.py`

**Interfaces:**
- `FusionPolicyArtifact.load(path, *, expected_hashes) -> FusionPolicyArtifact` validates ranker, risk calibrator, feature schema, and exact model/preprocess/local-bank hashes.
- `ClassifierPipeline.infer(...)` returns `DecisionPath.FUSION_RANKED` for accepted ranker decisions and `Unknown` with `fusion_risk_high` when the artifact abstains.

- [ ] **Step 1: Write failing runtime artifact tests**

```python
def test_runtime_accepts_fusion_ranked_sku_only_when_risk_gate_accepts():
    assert pipeline.infer(image, box).decision_path is DecisionPath.FUSION_RANKED

def test_runtime_returns_unknown_when_fusion_artifact_hash_is_wrong():
    assert pipeline.infer(image, box).unknown_reason == "fusion_artifact_invalid"
```

- [ ] **Step 2: Run focused tests to prove runtime has no fusion artifact path**

Run: `python -m pytest tests/classification/test_runtime.py tests/classification/test_contracts.py -q`

Expected: FAIL because `FUSION_RANKED` and `FusionPolicyArtifact` do not exist.

- [ ] **Step 3: Implement the immutable artifact path**

```python
if fusion_policy is not None:
    ranked = fusion_policy.ranker.rank(runtime_evidence)
    if fusion_policy.risk_calibrator.decide(ranked) == "sku":
        return sku_decision(ranked.top1_sku_id, DecisionPath.FUSION_RANKED)
    return unknown_decision(ranked.top3, reason="fusion_risk_high")
```

Keep RepViT direct and legacy local-policy code available only when no fusion artifact is configured.  The configured production artifact must be required after acceptance.  Add `fusion_policy` path/hash to strict configuration and provenance.

- [ ] **Step 4: Re-run focused tests**

Run: `python -m pytest tests/classification/test_config.py tests/classification/test_contracts.py tests/classification/test_runtime.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bakery_scanner/classification/config.py src/bakery_scanner/classification/contracts.py src/bakery_scanner/classification/runtime.py src/bakery_scanner/classification/policy.py scripts/train_classifier_fusion_policy.py tests/classification/test_config.py tests/classification/test_contracts.py tests/classification/test_runtime.py
git commit -m "feat: run immutable fusion classifier policy"
```

### Task 5: Batch reports and locked acceptance verification

**Files:**
- Modify: `scripts/{collect_classifier_evidence,evaluate_classifier_policy,evaluate_classifier_runtime}.py`
- Create: `scripts/evaluate_fusion_classifier_policy.py`
- Modify: `docs/superpowers/specs/2026-07-27-classifier-risk-ranked-top1-design.md`
- Test: `tests/classification/{test_evidence,test_runtime_evaluation}.py`

**Interfaces:**
- Produces a Batch 1 development report containing OOF ranker/risk metrics and an artifact eligibility result.
- Produces a locked Batch 2 report with automatic correct/error counts, correct Top-1 coverage, Top-3 recall, path/reason counts, candidate recall, and p50/p95 timing.

- [ ] **Step 1: Write failing report-boundary tests**

```python
def test_locked_report_rejects_any_threshold_selection_argument():
    with pytest.raises(ValueError, match="locked"):
        build_locked_fusion_report(rows, select_threshold=True)

def test_report_exposes_correct_top1_coverage_separately_from_auto_coverage():
    assert report["metrics"]["correct_top1_coverage"] == pytest.approx(.90)
```

- [ ] **Step 2: Run focused tests to prove report fields are absent**

Run: `python -m pytest tests/classification/test_evidence.py tests/classification/test_runtime_evaluation.py -q`

Expected: FAIL because the fusion report and `correct_top1_coverage` do not exist.

- [ ] **Step 3: Implement reports and run the prescribed data flow**

```bash
python -m scripts.collect_classifier_evidence --config configs/classifier_policy.yaml --manifest artifacts/classification/batch1.manifest.jsonl --dino-source-manifest artifacts/classification/dinov3_vits16_15plus5_v3.sources.json --output artifacts/classification/batch1.full_evidence.jsonl
python -m scripts.train_classifier_fusion_policy --config configs/classifier_policy.yaml --evidence artifacts/classification/batch1.full_evidence.jsonl --output artifacts/classification/fusion_policy_v1.json
python -m scripts.evaluate_fusion_classifier_policy --config configs/classifier_policy.yaml --evidence artifacts/classification/batch2.full_evidence.jsonl --policy artifacts/classification/fusion_policy_v1.json --output artifacts/classification/batch2.fusion_policy.report.json
```

The Batch 2 command accepts no folds, seed, fitting, or threshold-selection flag.  Mark the artifact ineligible when Batch 1 OOF cannot satisfy 90% correct Top-1 coverage with zero automatic errors.

- [ ] **Step 4: Re-run focused tests and full classifier suite**

Run: `python -m pytest tests/classification -q`

Expected: PASS.

- [ ] **Step 5: Verify the final change set and commit**

Run: `git diff --check`

Expected: exit code 0.

```bash
git add scripts src/bakery_scanner/classification docs/superpowers/specs tests/classification
git commit -m "feat: report risk-ranked classifier acceptance"
```

## Self-Review

- Spec coverage: Tasks 1–3 implement the evidence, ranker, and risk-calibrator responsibilities; Task 4 makes the artifact a provenance-bound runtime contract; Task 5 separates Batch 1 development from locked Batch 2 evaluation and reports every specified metric.
- Placeholder scan: no incomplete or deferred implementation markers are present.
- Type consistency: `FullEvidenceRow` feeds `FusionRankerArtifact`; its `RankedCandidates` feed `RiskCalibratorArtifact`; their combined `FusionPolicyArtifact` is the only new runtime artifact.
