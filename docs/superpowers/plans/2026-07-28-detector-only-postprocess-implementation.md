# Detector-Only Postprocess Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Establish whether the existing D-FINE-N 640 OOF detector alone can meet the locked 299-image zero-error gate at IoU .50 and .75 using only leakage-safe score and overlap-aware postprocessing. RTX 5080 E2E latency is explicitly excluded from this evaluation iteration.

**Architecture:** Keep the five completed detector OOF artifacts immutable. Decode native candidates and recall-first raw candidates through a deterministic Soft-NMS policy that decays but never suppresses overlaps. For every target fold, select score and Soft-NMS parameters only on the other four folds, then generate an immutable error, overlay, and latency report.

**Tech Stack:** Python 3.11, D-FINE, PyTorch/CUDA 12.8, RTX 5080, NumPy/Pillow, pytest.

## Global Constraints

- Reuse exactly the completed D-FINE-N 640 seed 20260724 fold 0-4 receipts; do not restart a 60-run matrix, modify staged data, or train a verifier.
- All model inference and latency measurement use RTX 5080 cuda:0; deterministic policy and tests may use CPU.
- Preserve original xywh coordinates and raw recall candidates with score >= .001 and top-30 per image/source.
- Soft-NMS must decay scores, never delete a candidate simply because it overlaps another candidate.
- A target fold must not select its own score, Soft-NMS, or final threshold.
- Acceptance requires zero misses, false positives, duplicates, split errors, and merge errors at both IoU .50 and .75 across all 299 images. Failure is evidence, not success.
- Reports remain development-only and explicitly name absent real empty-tray, overlap, and obstruction data.

---

### Task 1: Implement deterministic detector-only candidate decoding and Soft-NMS

**Files:**

- Create: src/bakery_scanner/detectors/soft_nms.py
- Modify: src/bakery_scanner/detectors/proposal_policy.py
- Create: tests/test_soft_nms.py

**Interfaces:**

~~~python
@dataclass(frozen=True, slots=True)
class SoftNmsPolicy:
    score_threshold: float
    overlap_threshold: float
    sigma: float

def soft_nms(proposals: Sequence[BreadProposal], policy: SoftNmsPolicy) -> tuple[BreadProposal, ...]:
    """Return canonical score-decayed candidates without deleting overlap rows."""

def final_boxes(proposals: Sequence[BreadProposal], policy: SoftNmsPolicy) -> Mapping[int, tuple[Box, ...]]:
    """Apply the final score threshold after deterministic score decay."""
~~~

- [ ] **Step 1: Write failing behavior tests.**

~~~python
def test_soft_nms_decays_overlapping_lower_score_without_deleting_row():
    result = soft_nms((high_score_box, overlap_box), SoftNmsPolicy(.1, .3, .5))
    assert len(result) == 2
    assert result[1].score < overlap_box.score

def test_non_overlapping_candidates_keep_original_score():
    assert soft_nms((left_box, right_box), policy) == (left_box, right_box)

def test_final_threshold_is_applied_after_decay():
    assert final_boxes((high_score_box, overlap_box), policy) == {1: (high_score_box.box,)}
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_soft_nms.py -q

Expected: FAIL because the module and policy do not exist.

- [ ] **Step 3: Implement canonical Gaussian Soft-NMS.**

Process each source image independently. Sort by score descending and by source-coordinate tie-breakers. Retain every row, decay only later overlapping rows with the configured Gaussian formula, preserve valid in-bounds boxes, and apply the score threshold only after all decays. Reject invalid policy values and duplicate candidate coordinates.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_soft_nms.py tests/test_proposal_policy.py -q
git add src/bakery_scanner/detectors/soft_nms.py src/bakery_scanner/detectors/proposal_policy.py tests/test_soft_nms.py
git commit -m "feat: add deterministic detector soft nms"
~~~

### Task 2: Add leakage-safe detector-only cross-fit selection and error report

**Files:**

- Create: src/bakery_scanner/detectors/detector_only_selection.py
- Create: scripts/select_detector_only.py
- Create: tests/test_detector_only_selection.py
- Generate: artifacts/box_system/reports/detector_only_development.json

**Interfaces:**

~~~python
@dataclass(frozen=True, slots=True)
class DetectorOnlyPolicy:
    raw_source: Literal["native", "recall_top30"]
    score_threshold: float
    overlap_threshold: float
    sigma: float

def cross_fit_detector_only_policies(detector_oof: OofArtifact, ...) -> Mapping[int, DetectorOnlyPolicy]: ...
def write_detector_only_report(...) -> Path: ...
def assert_locked_zero_error(report: EvaluationReport) -> None: ...
~~~

- [ ] **Step 1: Write failing cross-fit and gate tests.**

~~~python
def test_fold_zero_policy_excludes_fold_zero_candidates_and_labels():
    policy = cross_fit_detector_only_policies(...)[0]
    assert policy.calibration_image_ids.isdisjoint(fold_image_ids[0])

def test_zero_error_gate_rejects_iou75_duplicate():
    with pytest.raises(ValueError, match="IoU 0.75"):
        assert_locked_zero_error(report_with_duplicate_at_75)

def test_report_marks_detector_only_failure_without_operational_claim(tmp_path):
    payload = json.loads(write_detector_only_report(...).read_text())
    assert payload["operational_guarantee"] is False
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_detector_only_selection.py -q

- [ ] **Step 3: Implement parameter search and immutable evidence.**

Load only hash-valid OOF artifacts. For each target fold enumerate native/recall candidate source plus finite score, overlap, and sigma grids based only on the other four folds. Rank IoU .75 errors first, then IoU .50 errors, then deterministic latency-independent tie breaks. Apply one selected policy to the held-out fold and report fold and total errors at .50/.75, all policy inputs, receipts, prediction hashes, candidate counts, and development-only limitations.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_detector_only_selection.py tests/test_soft_nms.py tests/test_oof.py -q
python scripts/select_detector_only.py --help
git add src/bakery_scanner/detectors/detector_only_selection.py scripts/select_detector_only.py tests/test_detector_only_selection.py
git commit -m "feat: cross-fit detector only policy"
~~~

### Task 3: Render all detector-only errors in source coordinates

**Files:**

- Create: scripts/render_detector_only_errors.py
- Create: tests/test_detector_only_error_overlays.py
- Generate: artifacts/box_system/reports/detector_only_errors/

**Interfaces:**

~~~python
def render_error_overlay(*, image: Path, ground_truth: Sequence[Box],
                         predictions: Sequence[Box], output: Path,
                         iou_threshold: float) -> None: ...
~~~

- [ ] **Step 1: Write failing overlay tests.**

~~~python
def test_renderer_writes_original_size_png_for_iou75_error(tmp_path):
    render_error_overlay(image=source, ground_truth=(gt,), predictions=(bad_box,), output=output, iou_threshold=.75)
    assert Image.open(output).size == Image.open(source).size

def test_renderer_refuses_exact_image_without_error(tmp_path):
    with pytest.raises(ValueError, match="error"):
        render_error_overlay(image=source, ground_truth=(gt,), predictions=(gt,), output=output, iou_threshold=.75)
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_detector_only_error_overlays.py -q

- [ ] **Step 3: Implement report-driven rendering.**

Read only the immutable detector-only report, render one PNG per non-exact image at each failing IoU threshold, and draw GT/prediction/miss/duplicate/false-positive annotations in source coordinates. Write an index JSON that links each overlay to its fold, policy, and error categories. Do not generate overlays for exact images.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_detector_only_error_overlays.py -q
git add scripts/render_detector_only_errors.py tests/test_detector_only_error_overlays.py
git commit -m "feat: render detector only error overlays"
~~~

### Task 4: Measure RTX 5080 detector-only E2E latency and gate the result

> **Superseded by user direction on 2026-07-28:** speed is excluded from the current evaluation. Do not implement or execute this task in this plan iteration.

**Files:**

- Create: scripts/benchmark_detector_only_e2e.py
- Create: tests/test_detector_only_benchmark.py
- Generate: artifacts/box_system/reports/detector_only_latency.json

**Interfaces:**

~~~python
@dataclass(frozen=True, slots=True)
class LatencyReport:
    preprocessing: Percentiles
    detector: Percentiles
    postprocess: Percentiles
    e2e: Percentiles
    device_name: str

def assert_e2e_p95(report: LatencyReport, maximum_seconds: float = .5) -> None: ...
~~~

- [ ] **Step 1: Write failing latency contract tests.**

~~~python
def test_latency_gate_accepts_half_second_p95():
    assert_e2e_p95(report_with(e2e_p95=.5))

def test_latency_gate_rejects_above_half_second():
    with pytest.raises(ValueError, match="p95"):
        assert_e2e_p95(report_with(e2e_p95=.501))
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_detector_only_benchmark.py -q

- [ ] **Step 3: Implement warm GPU benchmark.**

Require cuda:0 and RTX 5080. Run at least ten warm-up images before timed samples. Use the final detector-only cross-fit policy for each image and synchronize CUDA around stage timing. Persist preprocessing, detector, postprocess, and E2E mean/p50/p95 values and the exact policy/report hashes. Refuse to write a latency report if E2E p95 exceeds .5 seconds.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_detector_only_benchmark.py -q
python scripts/benchmark_detector_only_e2e.py --help
git add scripts/benchmark_detector_only_e2e.py tests/test_detector_only_benchmark.py
git commit -m "feat: benchmark detector only e2e"
~~~

### Task 5: Execute evaluation and publish the evidence-based decision

**Files:**

- Modify: README.md
- Generate: artifacts/box_system/reports/detector_only_development.json
- Generate: artifacts/box_system/reports/detector_only_latency.json
- Generate: artifacts/box_system/reports/detector_only_errors/

- [ ] **Step 1: Revalidate all detector OOF artifacts.**

Run:

~~~powershell
$env:PYTHONPATH='src'
0..4 | ForEach-Object {
  python scripts/select_dfine640_verifier.py --validate-detector-fold $_ --config configs/box_system.yaml
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
~~~

Expected: every fold returns detector_fold_validated.

- [ ] **Step 2: Create the detector-only report and error overlays.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python scripts/select_detector_only.py --config configs/box_system.yaml --output artifacts/box_system/reports/detector_only_development.json
python scripts/render_detector_only_errors.py --report artifacts/box_system/reports/detector_only_development.json --output-dir artifacts/box_system/reports/detector_only_errors
~~~


- [ ] **Step 3: Publish only the evidenced result.**

If the locked IoU .50/.75 gates pass, state detector-only passed only for the locked 299-image scope. If either gate fails, document every error category and link its source-coordinate overlay; do not call the detector complete and do not start a verifier automatically. Latency is not evaluated in this iteration.

- [ ] **Step 4: Final verification and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_soft_nms.py tests/test_detector_only_selection.py tests/test_detector_only_error_overlays.py tests/test_detector_only_benchmark.py -q
git diff --check
git status --short
~~~

## Completion Evidence

- Five existing D-FINE fold receipts and raw/canonical predictions pass their immutable audits.
- Detector-only report proves either all locked gates pass or exactly why they fail, at both IoU .50 and .75.
- Every non-exact result has a source-coordinate error overlay and deterministic policy provenance.
- Latency is explicitly excluded from this evaluation iteration; no speed claim is made.
