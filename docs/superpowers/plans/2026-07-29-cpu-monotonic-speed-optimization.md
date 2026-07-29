# CPU Monotonic Speed Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible 299-image CPU baseline and a PyTorch batch/compile candidate that is promoted only when every currently correct object remains correct and both paired mean and p95 latency improve.

**Architecture:** Preserve `ClassifierPipeline.infer()` as the serial reference and add an image-level `infer_many()` path that batches the three RepViT crops and conditional DINO global/local feature extraction without duplicating decision policy. A deterministic comparator freezes object outcomes, while an AB/BA paired benchmark separates real latency improvement from CPU noise.

**Tech Stack:** Python 3.11, PyTorch 2.8 CPU FP32, Pillow, NumPy, SciPy, Pydantic, pytest, Windows `ctypes` process-affinity API

## Global Constraints

- Work on the existing `master` branch as previously requested; stage only files listed by the active task.
- Preserve all pre-existing dirty-worktree changes and the complete legacy D-FINE path.
- Keep RF-DETR-L, score threshold `0.5691395401954651`, RepViT, DINOv3, preprocessing, direct gate, fusion policy and FP32 unchanged.
- Use the current 299 images and 1,406 GT objects only as the execution-regression set; do not tune model or policy thresholds on it.
- Hard quality floors: Top-1 `>= 1,349`, Top-3 `>= 1,390`, FP `= 0`, FN `<= 5`, `Unknown <= 48`, confirmed A-to-B errors `<= 4`.
- Every one of the current 1,349 correct objects must remain the same correct SKU.
- Existing failures may remain or improve according to the approved monotonic transition table; no safe `Unknown` may become a wrong SKU.
- Do not overwrite or delete an existing report. Write through a staging path and atomically rename it.
- A speed claim requires at least three 299-image AB/BA passes and one-sided paired-bootstrap 95% confidence-interval upper bounds below zero for both mean and p95 deltas.
- This plan stops after PyTorch eager/compile candidates. OpenVINO, ONNX Runtime, quantization, early exit, distillation and detector replacement require later conditional plans.

---

## File Structure

- Create `src/bakery_scanner/e2e/cpu_dataset.py`: load the three COCO sources as one stable 299-image E/M/H evaluation sequence.
- Create `src/bakery_scanner/e2e/cpu_regression.py`: deterministic IoU-0.50 object states, monotonic transitions and aggregate gates.
- Create `src/bakery_scanner/e2e/cpu_latency.py`: AB/BA pass records and deterministic paired-bootstrap summaries.
- Modify `src/bakery_scanner/classification/repvit.py`: object-aligned RepViT microbatch evidence API.
- Modify `src/bakery_scanner/classification/dinov3.py`: object-aligned DINO global/local microbatch evidence API.
- Modify `src/bakery_scanner/classification/runtime.py`: `infer_many()` orchestration and image-level stage timings while retaining `infer()`.
- Modify `src/bakery_scanner/classification/config.py`: strict serial/batch/compile, thread and process-affinity options with serial-safe defaults.
- Modify `configs/cpu_rfdetr_classifier_policy.yaml`: pin a promoted mode only after the final gate passes.
- Create `scripts/benchmark_cpu_rfdetr_299.py`: baseline, candidate, microbatch-screen and paired benchmark CLI.
- Create `tests/e2e/test_cpu_dataset.py`: dataset count, order and profile-token tests.
- Create `tests/e2e/test_cpu_regression.py`: deterministic matching and all allowed/forbidden state transitions.
- Create `tests/e2e/test_cpu_latency.py`: AB/BA and bootstrap acceptance tests.
- Modify `tests/classification/test_repvit.py`: serial-equivalent RepViT batch evidence tests.
- Modify `tests/classification/test_dinov3.py`: serial-equivalent DINO batch evidence tests.
- Modify `tests/classification/test_runtime.py`: mixed direct/recheck `infer_many()` tests.
- Modify `tests/classification/test_config.py`: runtime-mode and microbatch validation tests.
- Create `tests/test_benchmark_cpu_rfdetr_299.py`: CLI/report contract and no-overwrite tests.

---

### Task 1: Stable 299-Image Dataset Contract

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_dataset.py`
- Create: `tests/e2e/test_cpu_dataset.py`

**Interfaces:**
- Consumes: the three `datasets/detection/*/annotations/instances.json` COCO files and their `images/` directories.
- Produces: `CpuEvaluationSample` and `load_cpu_evaluation_samples(root: Path) -> tuple[CpuEvaluationSample, ...]`.

- [ ] **Step 1: Write the failing dataset-contract tests**

```python
from pathlib import Path

from bakery_scanner.e2e.cpu_dataset import (
    _profile_from_name,
    load_cpu_evaluation_samples,
)


def test_cpu_dataset_has_fixed_counts_profiles_and_unique_keys():
    samples = load_cpu_evaluation_samples(Path("."))

    assert len(samples) == 299
    assert sum(len(sample.targets) for sample in samples) == 1406
    assert {profile: sum(s.profile == profile for s in samples) for profile in "EMH"} == {
        "E": 100,
        "M": 99,
        "H": 100,
    }
    assert len({sample.key for sample in samples}) == 299


def test_profile_is_found_by_token_not_fixed_filename_position(tmp_path):
    assert _profile_from_name("g15_e_0302.jpg") == "E"
    assert _profile_from_name("g20_b01_m_0702.jpg") == "M"
    assert _profile_from_name("g20_b02_h_0714.jpg") == "H"
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
pytest tests/e2e/test_cpu_dataset.py -q
```

Expected: FAIL with `ModuleNotFoundError: bakery_scanner.e2e.cpu_dataset`.

- [ ] **Step 3: Implement the immutable sample contract and COCO loader**

```python
@dataclass(frozen=True, slots=True)
class CpuEvaluationTarget:
    annotation_id: int
    sku_id: int
    box: Box


@dataclass(frozen=True, slots=True)
class CpuEvaluationSample:
    key: str
    source: str
    source_image_id: int
    image_path: Path
    profile: Literal["E", "M", "H"]
    targets: tuple[CpuEvaluationTarget, ...]


def _profile_from_name(name: str) -> Literal["E", "M", "H"]:
    tokens = Path(name).stem.lower().split("_")
    matches = tuple(token.upper() for token in tokens if token in {"e", "m", "h"})
    if len(matches) != 1:
        raise ValueError(f"image name must contain exactly one E/M/H token: {name}")
    return cast(Literal["E", "M", "H"], matches[0])
```

Load sources in fixed order `group_15class`, `group_20class_batch01`,
`group_20class_batch02`; sort images by integer COCO image ID and targets by
integer annotation ID. Reject missing images, duplicate sample keys, invalid
boxes, unknown category IDs and any final count other than 299/1,406.

- [ ] **Step 4: Run the focused tests**

Run: `pytest tests/e2e/test_cpu_dataset.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit the dataset contract**

```powershell
git add src/bakery_scanner/e2e/cpu_dataset.py tests/e2e/test_cpu_dataset.py
git commit -m "feat: define CPU 299-image evaluation dataset"
```

---

### Task 2: Deterministic Object Baseline and Monotonic Gate

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_regression.py`
- Create: `tests/e2e/test_cpu_regression.py`

**Interfaces:**
- Consumes: `CpuEvaluationTarget`, `BreadProposal`, `ClassificationDecision`.
- Produces: `ObjectOutcome`, `ObjectRecord`, `ImageRegressionRecord`, `compare_run(reference, candidate) -> RegressionGateReport`.

- [ ] **Step 1: Write failing outcome and transition tests**

```python
def _record(
    outcome: str,
    *,
    expected: int,
    predicted: int | None,
    top3: tuple[int, ...] = (),
) -> ObjectRecord:
    return ObjectRecord(
        sample_key="fixture/e_0001.jpg",
        annotation_id=1,
        expected_sku=expected,
        outcome=ObjectOutcome(outcome),
        predicted_sku=predicted,
        top3_sku_ids=top3,
        matched_proposal_index=0 if outcome != "missed" else None,
        iou=1.0 if outcome != "missed" else None,
    )


def test_monotonic_gate_rejects_a_correct_object_becoming_unknown():
    reference = _record("correct", expected=6, predicted=6)
    candidate = _record("top3_candidate", expected=6, predicted=None, top3=(6, 5, 8))

    report = compare_run((reference,), (candidate,))

    assert not report.passed
    assert report.regressions[0].reason == "correct_object_regressed"


@pytest.mark.parametrize(
    ("before", "after", "allowed"),
    [
        ("correct", "correct", True),
        ("top3_candidate", "correct", True),
        ("candidate_out_unknown", "top3_candidate", True),
        ("misclassified", "candidate_out_unknown", True),
        ("missed", "candidate_out_unknown", True),
        ("top3_candidate", "candidate_out_unknown", False),
        ("candidate_out_unknown", "misclassified", False),
        ("correct", "misclassified", False),
    ],
)
def test_transition_table(before, after, allowed):
    assert transition_is_allowed(before, after) is allowed
```

Also add a tie test with two equal-IoU predictions proving the same annotation
ID and proposal are selected after input-order permutations. Add record-level
tests proving that `CORRECT -> CORRECT` still requires the identical correct
SKU, `MISCLASSIFIED -> MISCLASSIFIED` is allowed only for the identical A-to-B
mapping, and changing one wrong SKU into a different wrong SKU is rejected.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest tests/e2e/test_cpu_regression.py -q`

Expected: FAIL because `cpu_regression` does not exist.

- [ ] **Step 3: Implement deterministic records and matching**

```python
class ObjectOutcome(str, Enum):
    CORRECT = "correct"
    TOP3_CANDIDATE = "top3_candidate"
    CANDIDATE_OUT_UNKNOWN = "candidate_out_unknown"
    MISCLASSIFIED = "misclassified"
    MISSED = "missed"


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    sample_key: str
    annotation_id: int
    expected_sku: int
    outcome: ObjectOutcome
    predicted_sku: int | None
    top3_sku_ids: tuple[int, ...]
    matched_proposal_index: int | None
    iou: float | None


_ALLOWED = {
    ObjectOutcome.CORRECT: {ObjectOutcome.CORRECT},
    ObjectOutcome.TOP3_CANDIDATE: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
    },
    ObjectOutcome.CANDIDATE_OUT_UNKNOWN: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
    },
    ObjectOutcome.MISCLASSIFIED: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
        ObjectOutcome.MISCLASSIFIED,
    },
    ObjectOutcome.MISSED: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
        ObjectOutcome.MISSED,
    },
}
```

Sort matching edges by:

```python
(-iou, target.annotation_id, -proposal.score, *proposal.box.xyxy, proposal_index)
```

Perform greedy one-to-one assignment at IoU `0.50`. Emit an explicit
`MISSED` record for every unmatched GT and count every unmatched prediction as
FP. Aggregate Top-1, Top-3, FP, FN, Unknown and confirmed A-to-B mappings.

- [ ] **Step 4: Add and pass exact floor tests**

Add a test that accepts exactly Top-1 1,349, Top-3 1,390, FP 0, FN 5,
Unknown 48 and misclassified 4, then rejects each metric when worsened by one.

Run: `pytest tests/e2e/test_cpu_regression.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the comparator**

```powershell
git add src/bakery_scanner/e2e/cpu_regression.py tests/e2e/test_cpu_regression.py
git commit -m "feat: add monotonic CPU regression gate"
```

---

### Task 3: Paired AB/BA Latency Statistics

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_latency.py`
- Create: `tests/e2e/test_cpu_latency.py`

**Interfaces:**
- Consumes: equal-keyed serial and candidate image latency rows from at least three AB/BA passes.
- Produces: `PairedLatencyReport` and `compare_paired_latency(passes, *, seed=20260729, bootstrap_samples=10000)`.

- [ ] **Step 1: Write failing deterministic-bootstrap tests**

```python
def _passes(
    *,
    reference: tuple[float, ...],
    candidate: tuple[float, ...],
    count: int,
) -> tuple[PairedPass, ...]:
    keys = tuple(f"image-{index:04d}" for index in range(len(reference)))
    reference_rows = tuple(
        ImageLatency(key, value) for key, value in zip(keys, reference, strict=True)
    )
    candidate_rows = tuple(
        ImageLatency(key, value) for key, value in zip(keys, candidate, strict=True)
    )
    return tuple(
        PairedPass(
            pass_index=index,
            order="AB" if index % 2 == 0 else "BA",
            reference=reference_rows,
            candidate=candidate_rows,
        )
        for index in range(count)
    )


def test_paired_latency_requires_both_mean_and_p95_ci_below_zero():
    passes = _passes(reference=(100, 110, 120, 130), candidate=(70, 80, 90, 100), count=3)

    report = compare_paired_latency(passes, seed=20260729, bootstrap_samples=2000)

    assert report.mean_delta_ms < 0
    assert report.p95_delta_ms < 0
    assert report.mean_ci_upper_ms < 0
    assert report.p95_ci_upper_ms < 0
    assert report.passed


def test_paired_latency_rejects_noise_overlap():
    passes = _passes(reference=(100, 101, 100, 101), candidate=(99, 102, 99, 102), count=3)
    assert not compare_paired_latency(
        passes, seed=20260729, bootstrap_samples=2000
    ).passed
```

Add validation tests for missing keys, fewer than three passes, duplicate image
keys, non-AB/BA order and non-finite values.

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `pytest tests/e2e/test_cpu_latency.py -q`

Expected: FAIL with missing `cpu_latency`.

- [ ] **Step 3: Implement paired resampling**

Add immutable records that reject empty keys, non-finite/negative latency,
duplicate image keys, non-contiguous pass indices and a broken AB/BA sequence:

```python
@dataclass(frozen=True, slots=True)
class ImageLatency:
    image_key: str
    total_ms: float


@dataclass(frozen=True, slots=True)
class PairedPass:
    pass_index: int
    order: Literal["AB", "BA"]
    reference: tuple[ImageLatency, ...]
    candidate: tuple[ImageLatency, ...]
```

For each bootstrap sample, resample image keys with replacement and retain all
passes for each sampled key, preserving the reference/candidate pair and
AB/BA observation for that image. Compute point statistics over all matched
pass-image rows and cluster-bootstrap statistics over sampled image keys:

```python
mean_delta = mean(candidate) - mean(reference)
p95_delta = percentile(candidate, 95) - percentile(reference, 95)
```

Use the 95th percentile of each bootstrap delta distribution as the one-sided
95% upper bound. `passed` is true only when both point deltas and both upper
bounds are strictly below zero.

- [ ] **Step 4: Run deterministic tests twice**

Run:

```powershell
pytest tests/e2e/test_cpu_latency.py -q
pytest tests/e2e/test_cpu_latency.py -q
```

Expected: identical passing results both times.

- [ ] **Step 5: Commit the latency gate**

```powershell
git add src/bakery_scanner/e2e/cpu_latency.py tests/e2e/test_cpu_latency.py
git commit -m "feat: add paired CPU latency gate"
```

---

### Task 4: RepViT Object Microbatch Scoring

**Files:**
- Modify: `src/bakery_scanner/classification/repvit.py`
- Modify: `tests/classification/test_repvit.py`

**Interfaces:**
- Consumes: `Sequence[tuple[Image.Image, Image.Image, Image.Image]]` and positive `max_objects`.
- Produces: `RepVitM1Runner.score_many_with_evidence(crop_groups, *, max_objects) -> tuple[RepVitEvidence, ...]`.

- [ ] **Step 1: Write a failing serial-equivalence test**

```python
def _crops(color: str) -> tuple[Image.Image, Image.Image, Image.Image]:
    return tuple(Image.new("RGB", (8, 8), color) for _ in range(3))


class RecordingEvidenceModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.batch_sizes: list[int] = []

    def forward_features(self, batch: torch.Tensor) -> torch.Tensor:
        self.batch_sizes.append(batch.shape[0])
        return batch.mean(dim=1, keepdim=True).repeat(1, 384, 1, 1)

    def forward_head(self, features: torch.Tensor, *, pre_logits: bool) -> torch.Tensor:
        return features.mean(dim=(2, 3))[:, :20]


def _recording_evidence_runner() -> RepVitM1Runner:
    return RepVitM1Runner(
        model=RecordingEvidenceModel(),
        sku_ids=tuple(range(1, 21)),
        transform=transforms.ToTensor(),
        model_id="repvit_m1_15plus5_v1",
        device=torch.device("cpu"),
    )


def test_score_many_matches_serial_evidence_and_preserves_object_order():
    runner = _recording_evidence_runner()
    groups = (_crops("red"), _crops("green"), _crops("blue"))

    expected = tuple(runner.score_with_evidence(group) for group in groups)
    actual = runner.score_many_with_evidence(groups, max_objects=2)

    assert len(actual) == 3
    for left, right in zip(actual, expected, strict=True):
        assert left.scores.values == pytest.approx(right.scores.values, abs=1e-7)
        assert torch.allclose(left.feature, right.feature, atol=1e-7, rtol=0)
        assert left.crop_disagreement == pytest.approx(right.crop_disagreement, abs=1e-7)
    assert runner.model.batch_sizes[-2:] == (6, 3)
```

Add tests rejecting `max_objects <= 0`, empty crop groups and groups that do not
contain exactly three crops.

- [ ] **Step 2: Run the focused test and confirm the missing-method failure**

Run:

```powershell
pytest tests/classification/test_repvit.py::test_score_many_matches_serial_evidence_and_preserves_object_order -q
```

Expected: FAIL with missing `score_many_with_evidence`.

- [ ] **Step 3: Implement one object-aligned batch kernel**

Create a private `_score_evidence_batch(crops)` that accepts exactly
`3 * object_count` crops, validates features as
`(3 * object_count, 384, H, W)` and logits as
`(3 * object_count, 20)`, reshapes them to object-major form, and constructs
one `RepVitEvidence` per object.
Implement:

```python
def score_many_with_evidence(self, crop_groups, *, max_objects):
    groups = _validated_crop_groups(crop_groups)
    results = []
    for start in range(0, len(groups), max_objects):
        flattened = tuple(crop for group in groups[start:start + max_objects] for crop in group)
        results.extend(self._score_evidence_batch(flattened))
    return tuple(results)
```

Refactor `score_with_evidence()` to delegate to this method with one group and
`max_objects=1`, so serial and batch share the same scoring math.

- [ ] **Step 4: Run RepViT and runtime regression tests**

Run:

```powershell
pytest tests/classification/test_repvit.py tests/classification/test_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the RepViT batch API**

```powershell
git add src/bakery_scanner/classification/repvit.py tests/classification/test_repvit.py
git commit -m "feat: batch RepViT crop evidence"
```

---

### Task 5: DINO Global/Local Object Microbatch Scoring

**Files:**
- Modify: `src/bakery_scanner/classification/dinov3.py`
- Modify: `tests/classification/test_dinov3.py`

**Interfaces:**
- Consumes: aligned crop groups, crop-relative product-box groups, local bank and aligned RepViT score vectors.
- Produces: `DinoGlobalLocalEvidence` and
  `score_many_global_and_local_evidence(crop_groups, product_box_groups, local_bank, *, repvit_scores, max_objects) -> tuple[DinoGlobalLocalEvidence, ...]`.

- [ ] **Step 1: Write the failing DINO serial-equivalence test**

```python
def _crops(color: str) -> tuple[Image.Image, Image.Image, Image.Image]:
    return tuple(Image.new("RGB", (224, 224), color) for _ in range(3))


def _full_box() -> Box:
    return Box(0, 0, 224, 224)


def _repvit_scores(top_sku: int) -> ModelScoreVector:
    values = [0.0] * 20
    values[top_sku - 1] = 1.0
    return ModelScoreVector(
        "repvit_m1_15plus5_v1",
        tuple(range(1, 21)),
        tuple(values),
        "probability",
    )


def _evidence_payload(rows) -> tuple[float, ...]:
    return tuple(
        value
        for row in rows
        for value in (
            *row.global_scores.values,
            *(row.local_scores.get(sku_id, -1.0) for sku_id in range(1, 21)),
            float(row.product_patch_count),
            row.product_patch_ratio,
        )
    )


class RecordingFeatureEncoder(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.batch_sizes: list[int] = []

    def forward_features(self, batch: torch.Tensor):
        self.batch_sizes.append(batch.shape[0])
        return {
            "x_norm_clstoken": torch.nn.functional.normalize(
                torch.ones((batch.shape[0], 384)), dim=1
            ),
            "x_norm_patchtokens": torch.nn.functional.normalize(
                torch.ones((batch.shape[0], 196, 384)), dim=2
            ),
        }


def test_many_local_evidence_matches_serial_and_batches_encoder_calls(local_bank):
    encoder = RecordingFeatureEncoder()
    runner = _runner_with_encoder(encoder)
    crop_groups = (_crops("red"), _crops("green"), _crops("blue"))
    boxes = ((_full_box(),) * 3,) * 3
    repvit = (_repvit_scores(1), _repvit_scores(2), _repvit_scores(3))

    expected = tuple(
        DinoGlobalLocalEvidence(
            *runner.score_global_and_local_evidence(
                crops, product_boxes, local_bank, repvit_scores=scores
            )
        )
        for crops, product_boxes, scores in zip(crop_groups, boxes, repvit, strict=True)
    )
    actual = runner.score_many_global_and_local_evidence(
        crop_groups, boxes, local_bank, repvit_scores=repvit, max_objects=2
    )

    assert _evidence_payload(actual) == pytest.approx(_evidence_payload(expected))
    assert encoder.batch_sizes[-2:] == (6, 3)
```

Add tests for alignment mismatches and per-object candidate-union preservation.

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `pytest tests/classification/test_dinov3.py -q`

Expected: FAIL with missing batch API.

- [ ] **Step 3: Implement batched encoder extraction and per-object local scoring**

Add:

```python
@dataclass(frozen=True, slots=True)
class DinoGlobalLocalEvidence:
    global_scores: ModelScoreVector
    local_scores: dict[int, float]
    product_patch_count: int
    product_patch_ratio: float
```

Run `encoder.forward_features()` once per object microbatch. Validate and
reshape class tokens from `(3 * objects, 384)` to `(objects, 3, 384)` and patch
tokens from `(3 * objects, patch_count, 384)` to
`(objects, 3, patch_count, 384)`, then reuse the existing candidate-union,
product mask and `LocalPatchBank.score()` logic per object. Keep local-bank
scoring per object; only neural feature extraction is batched.

Refactor `score_global_and_local_evidence()` to delegate to the many-object
method with one object and return its four legacy tuple fields.

- [ ] **Step 4: Run DINO and runtime regression tests**

Run:

```powershell
pytest tests/classification/test_dinov3.py tests/classification/test_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the DINO batch API**

```powershell
git add src/bakery_scanner/classification/dinov3.py tests/classification/test_dinov3.py
git commit -m "feat: batch DINO global local evidence"
```

---

### Task 6: Image-Level Batch Classifier Orchestration

**Files:**
- Modify: `src/bakery_scanner/classification/runtime.py`
- Modify: `tests/classification/test_runtime.py`

**Interfaces:**
- Consumes: one `Image.Image | CanonicalImage`, ordered `Sequence[Box]`, RepViT/DINO object microbatch sizes.
- Produces: `BatchStageTimings`, `BatchInferenceResult`, and
  `ClassifierPipeline.infer_many(image, boxes, *, repvit_max_objects, dino_max_objects) -> BatchInferenceResult`.

- [ ] **Step 1: Write a failing mixed-path orchestration test**

```python
class ManyRecordingRunner(RecordingRunner):
    def __init__(self, evidence: tuple[RepVitEvidence, ...]) -> None:
        super().__init__(evidence[0].scores)
        self.evidence = evidence

    def score_many_with_evidence(self, crop_groups, *, max_objects):
        assert max_objects == 2
        return self.evidence


class ManyFullEvidenceDino(FullEvidenceDino):
    def __init__(self, evidence: tuple[DinoGlobalLocalEvidence, ...]) -> None:
        super().__init__(evidence[0].global_scores)
        self.evidence = evidence
        self.received_object_count = 0

    def score_many_global_and_local_evidence(
        self, crop_groups, product_box_groups, local_bank, *, repvit_scores, max_objects
    ):
        assert max_objects == 2
        self.received_object_count = len(crop_groups)
        return self.evidence


def test_infer_many_batches_repvit_and_only_rechecks_direct_rejections():
    repvit = ManyRecordingRunner(
        (
            RepVitEvidence(_repvit_scores({6: 0.80, 5: 0.20}), torch.ones(384), 0.01),
            RepVitEvidence(_repvit_scores({5: 0.50, 6: 0.30}), torch.ones(384), 0.01),
            RepVitEvidence(_repvit_scores({19: 0.50, 6: 0.30}), torch.ones(384), 0.01),
        )
    )
    dino = ManyFullEvidenceDino(
        (
            DinoGlobalLocalEvidence(_dino_scores({5: 0.80}), {5: 0.90}, 32, 0.5),
            DinoGlobalLocalEvidence(_dino_scores({19: 0.80}), {19: 0.90}, 32, 0.5),
        )
    )
    pipeline = _pipeline(repvit=repvit, dino_loader=lambda: dino)

    result = pipeline.infer_many(
        _image(),
        (Box(1, 1, 20, 20), Box(22, 1, 20, 20), Box(43, 1, 16, 20)),
        repvit_max_objects=2,
        dino_max_objects=2,
    )

    assert len(result.decisions) == 3
    assert result.decisions[0].decision_path is DecisionPath.REPVIT_DIRECT
    assert dino.received_object_count == 2
    assert result.dino_object_count == 2
    assert result.timings.total_ms >= (
        result.timings.crop_ms + result.timings.repvit_ms
    )
```

Add tests for empty boxes, box-order preservation, a DINO microbatch failure
returning fail-closed decisions only for that failed recheck batch while direct
objects remain unchanged, and `infer()` remaining byte-for-byte compatible for
existing fixtures.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest tests/classification/test_runtime.py -q`

Expected: FAIL with missing `infer_many`.

- [ ] **Step 3: Add image-level contracts**

```python
@dataclass(frozen=True, slots=True)
class BatchStageTimings:
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    total_ms: float


@dataclass(frozen=True, slots=True)
class BatchInferenceResult:
    decisions: tuple[ClassificationDecision, ...]
    timings: BatchStageTimings
    dino_object_count: int
```

Validate all timing values as finite and non-negative.

- [ ] **Step 4: Implement `infer_many()` without policy duplication**

The method must:

1. canonicalize the image once;
2. validate every ordered box;
3. build all crop/product-box groups;
4. call `repvit.score_many_with_evidence`;
5. call the existing `policy.direct()` for each object;
6. batch only rejected objects through DINO;
7. call the existing `_fusion_decision()` for each rejected object;
8. restore decisions to input order;
9. apply `_with_metadata()` and return image-level timings.

Keep `infer()` unchanged as the serial reference. Do not implement fusion math
inside `infer_many()`. In batch mode, each decision's `StageTimings` records the
wall time of the microbatch containing that object and is not additive across
objects. `BatchStageTimings` is the authoritative image-level latency record.

- [ ] **Step 5: Run classification tests**

Run:

```powershell
pytest tests/classification/test_runtime.py tests/classification/test_repvit.py tests/classification/test_dinov3.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the batch pipeline**

```powershell
git add src/bakery_scanner/classification/runtime.py tests/classification/test_runtime.py
git commit -m "feat: add image-level batch classification"
```

---

### Task 7: Strict CPU Runtime and Compile Options

**Files:**
- Modify: `src/bakery_scanner/classification/config.py`
- Modify: `tests/classification/test_config.py`
- Modify: `src/bakery_scanner/classification/runtime.py`

**Interfaces:**
- Consumes: optional YAML runtime keys.
- Produces: validated `runtime.mode`, microbatch sizes, thread/process-affinity settings and model-compile selection.

- [ ] **Step 1: Write failing strict-config tests**

```python
from bakery_scanner.classification.config import ClassifierRuntimeConfig


def test_cpu_runtime_accepts_batch_compile_options():
    runtime = ClassifierRuntimeConfig(
        device="CPU",
        precision="FP32",
        mode="batch_pytorch_compile",
        repvit_microbatch_objects=4,
        dinov3_microbatch_objects="all",
        intra_op_threads=8,
        inter_op_threads=1,
        cpu_affinity=[0, 1, 2, 3],
        compile_models=["repvit", "dinov3"],
    )
    assert runtime.repvit_microbatch_objects == 4
    assert runtime.compile_models == ("repvit", "dinov3")


@pytest.mark.parametrize("value", [0, -1, 3, 16])
def test_runtime_rejects_unsupported_microbatch_sizes(value):
    with pytest.raises(ValueError, match="microbatch"):
        ClassifierRuntimeConfig(
            device="CPU",
            precision="FP32",
            mode="batch_pytorch",
            repvit_microbatch_objects=value,
        )
```

Also reject compile models in `serial_reference`, non-CPU compile mode,
`inter_op_threads != 1`, empty/negative/duplicate affinity IDs, duplicate
compile model names and unknown mode names.

- [ ] **Step 2: Run and confirm strict-model failures**

Run: `pytest tests/classification/test_config.py -q`

Expected: new tests fail because the fields are not defined.

- [ ] **Step 3: Add serial-safe defaults**

```python
class ClassifierRuntimeConfig(_StrictModel):
    device: Literal["CPU", "CUDA:0"]
    precision: Literal["FP32"]
    mode: Literal[
        "serial_reference",
        "batch_pytorch",
        "batch_pytorch_compile",
    ] = "serial_reference"
    repvit_microbatch_objects: Literal[1, 2, 4, 8, "all"] = 1
    dinov3_microbatch_objects: Literal[1, 2, 4, 8, "all"] = 1
    intra_op_threads: int | None = None
    inter_op_threads: Literal[1] = 1
    cpu_affinity: Literal["all"] | tuple[int, ...] = "all"
    compile_models: tuple[Literal["repvit", "dinov3"], ...] = ()
```

Add a model validator enforcing the relationships tested in Step 1. Resolve
`"all"` to the current image's object count only at the scorer call site.
Existing GPU and CPU configs without new keys must continue to load as
`serial_reference`.

- [ ] **Step 4: Apply process-global threads once and compile selected models**

Add `configure_cpu_process(runtime: ClassifierRuntimeConfig) -> None` with a
module lock and remembered applied thread/affinity tuple. For CPU only, call
`torch.set_num_threads()` when configured and call
`torch.set_num_interop_threads(1)` before any model inference. Repeated calls
with the same tuple are no-ops; a conflicting tuple raises and tells the caller
to use a fresh worker process. Add a small Windows-only affinity adapter around
`GetProcessAffinityMask`/`SetProcessAffinityMask` using `ctypes`; validate
configured logical CPU IDs against the worker's inherited process mask and
apply the subset to the current worker only. `"all"` preserves the inherited
mask. Unit tests monkeypatch the adapter and do not alter the pytest process.

The benchmark CLI must start a fresh worker process for each thread candidate,
configure threads once, and then load both reference and candidate pipelines in
that process. Compile only the named candidate model modules, catch no compile
exceptions, and expose compile failure as a candidate failure rather than
silently reverting.

Do not modify `configs/cpu_rfdetr_classifier_policy.yaml` yet.

- [ ] **Step 5: Run config and runtime tests**

Run:

```powershell
pytest tests/classification/test_config.py tests/classification/test_runtime.py -q
```

Expected: all tests pass and existing configs load as serial.

- [ ] **Step 6: Commit runtime options**

```powershell
git add src/bakery_scanner/classification/config.py src/bakery_scanner/classification/runtime.py tests/classification/test_config.py
git commit -m "feat: configure CPU batch compile runtime"
```

---

### Task 8: Reproducible 299-Image Benchmark CLI

**Files:**
- Create: `scripts/benchmark_cpu_rfdetr_299.py`
- Create: `tests/test_benchmark_cpu_rfdetr_299.py`
- Modify: `src/bakery_scanner/e2e/rfdetr_cpu.py`
- Modify: `tests/test_rfdetr_cpu.py`

**Interfaces:**
- Consumes: package root, classifier config, runtime mode, sample profile, candidate thread/affinity/microbatch/compile overrides, output path, pass count, AB/BA first order and bootstrap seed.
- Produces: schema-v2 atomic JSON containing artifact hashes, per-image/per-object states, stage timings, quality gate and paired latency report.
- Exposes `run_benchmark(options: BenchmarkOptions, dependencies: BenchmarkDependencies | None = None) -> dict[str, object]`; tests inject a dependency bundle whose sample loader returns 299 immutable fake samples with E/M/H counts 100/99/100 and 1,406 total targets, and whose detector/classifier runners return fixed object records and latency rows.

- [ ] **Step 1: Write failing report-contract tests with fake models**

```python
def test_benchmark_report_has_299_contract_and_applied_detector_threshold(
    fake_benchmark_dependencies, tmp_path
):
    report = run_benchmark(
        BenchmarkOptions(
            package_root=tmp_path,
            classifier_config=tmp_path / "policy.yaml",
            reference_mode="serial_reference",
            candidate_mode="batch_pytorch",
            sample_profile="all299",
            intra_op_threads=1,
            repvit_microbatch=1,
            dino_microbatch=1,
            cpu_affinity="all",
            compile_models=(),
            passes=3,
            first_order="AB",
            bootstrap_seed=20260729,
            output=tmp_path / "result",
        ),
        dependencies=fake_benchmark_dependencies,
    )

    assert report["schema_version"] == 2
    assert report["detector"]["score_threshold"] == 0.5691395401954651
    assert report["dataset"] == {"images": 299, "objects": 1406}
    assert tuple(report["profiles"]) == ("E", "M", "H")
    assert report["quality_gate"]["reference"]["fp"] == 0
    assert report["latency_gate"]["bootstrap_seed"] == 20260729


def test_benchmark_refuses_to_overwrite_existing_output(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        run_benchmark(_options(tmp_path, output=output))
```

Define `_options()` and `fake_benchmark_dependencies` in the test module using
the exact `BenchmarkOptions`/`BenchmarkDependencies` constructors. Also test
that a fake inference exception preserves the staging directory by atomically
renaming it to an `output.failed.UUID` sibling and writing `failure.json`; do
not delete partial evidence.

- [ ] **Step 2: Run tests and confirm the missing script/module failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
pytest tests/test_benchmark_cpu_rfdetr_299.py tests/test_rfdetr_cpu.py -q
```

Expected: FAIL because the new runner and schema-v2 summaries do not exist.

- [ ] **Step 3: Extend profile summaries**

Replace the mean-only helper with a typed summary that validates all E/M/H
groups and records image count, mean, p50 and p95 for total and every stage.
Keep the old `summarize_profiles(rows)` name as a compatibility wrapper for the
existing nine-image runner.

- [ ] **Step 4: Implement the benchmark runner**

Required CLI:

```text
--package-root PATH
--classifier-config PATH
--reference-mode serial_reference
--candidate-mode batch_pytorch|batch_pytorch_compile
--sample-profile all299|batch2_e3_m3_h3
--intra-op-threads INT
--cpu-affinity all|COMMA_SEPARATED_LOGICAL_CPU_IDS
--repvit-microbatch 1|2|4|8|all
--dino-microbatch 1|2|4|8|all
--compile-model repvit|dinov3  (repeatable; omitted means compile neither)
--passes INT
--first-order AB|BA
--bootstrap-seed INT
--output PATH
```

The runner must load the detector threshold only from
`models/rfdetr_large_bakery_v1/manifest.json`, call
`load_cpu_evaluation_samples()` for `all299` or the existing
`resolve_batch2_e3_m3_h3()` profile for the nine-image screen, warm both paths,
alternate AB/BA by pass starting from `--first-order`, and use `compare_run()`
plus `compare_paired_latency()`. Candidate overrides are applied to an
in-memory validated config and are recorded in the report; they do not rewrite
the source YAML.

The top-level schema-v2 keys are exactly `schema_version`, `created_at_utc`,
`dataset`, `detector`, `artifacts`, `runtime`, `profiles`, `quality_gate`,
`latency_gate` and `passes`. `detector` contains `artifact_id`,
`score_threshold`, `manifest_sha256`, `checkpoint_sha256` and
`calibration_sha256`. `artifacts` contains the RepViT checkpoint/manifest/
prototype hashes, DINO weights/support/local-bank hashes, preprocessing hash,
direct-calibration hash, fusion-policy hash, all three COCO annotation hashes
and an ordered-image-list hash. `runtime` contains Python, PyTorch and OS/CPU
identifiers, active Windows power-plan text, reference/candidate modes,
intra/inter-op threads, requested/applied process affinity, both microbatch
sizes, compiled model names and warm-up count. Each E/M/H profile
records image/object counts plus mean/p50/p95 for canonicalization, detector,
crop, RepViT, DINO, fusion and end-to-end latency. `quality_gate` contains the
reference/candidate aggregates, object regressions and `passed`.
`latency_gate` contains seed, bootstrap sample count, paired point deltas,
one-sided upper bounds and `passed`. Each pass records `pass_index`, `order`
and reference/candidate arrays keyed by image; each image row includes all
stage timings, DINO object count/rate, proposals and object records.

Read the active power plan without changing it by invoking
`powercfg /getactivescheme` once in the worker and record the sanitized output.
Failure to read it is recorded as `unavailable`; it must not abort inference or
trigger a system-setting change.

Write `report.json` under a UUID staging directory and rename the directory to
the requested output only after all gates and serialization complete. On any
exception, write sanitized exception type/message to `failure.json` and rename
the staging directory to a non-colliding `output.failed.UUID` sibling.

- [ ] **Step 5: Run CLI unit and existing RF-DETR tests**

Run:

```powershell
pytest tests/test_benchmark_cpu_rfdetr_299.py tests/test_rfdetr_cpu.py tests/test_rfdetr.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the benchmark CLI**

```powershell
git add scripts/benchmark_cpu_rfdetr_299.py src/bakery_scanner/e2e/rfdetr_cpu.py tests/test_benchmark_cpu_rfdetr_299.py tests/test_rfdetr_cpu.py
git commit -m "feat: benchmark CPU pipeline on 299 images"
```

---

### Task 9: Establish Reference, Screen Candidates and Promote Only a Winner

**Files:**
- Modify conditionally after a passing gate: `configs/cpu_rfdetr_classifier_policy.yaml`
- Generate without overwriting: `artifacts/evaluations/cpu-monotonic-$runId/report.json`

**Interfaces:**
- Consumes: the completed benchmark CLI and current hash-valid artifacts.
- Produces: one serial baseline, screened microbatch/compile candidates, and either a promoted config or an explicit no-promotion result.

- [ ] **Step 1: Run the complete focused automated suite**

Run:

```powershell
$env:PYTHONPATH='src;.'
pytest tests/e2e/test_cpu_dataset.py tests/e2e/test_cpu_regression.py tests/e2e/test_cpu_latency.py tests/classification/test_config.py tests/classification/test_repvit.py tests/classification/test_dinov3.py tests/classification/test_runtime.py tests/test_benchmark_cpu_rfdetr_299.py tests/test_rfdetr.py tests/test_rfdetr_cpu.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Create the three-pass serial baseline**

Run:

```powershell
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:PYTHONPATH='src;.'
python scripts/benchmark_cpu_rfdetr_299.py `
  --package-root . `
  --classifier-config configs/cpu_rfdetr_classifier_policy.yaml `
  --reference-mode serial_reference `
  --candidate-mode serial_reference `
  --sample-profile all299 `
  --passes 3 `
  --first-order AB `
  --bootstrap-seed 20260729 `
  --output "artifacts/evaluations/cpu-monotonic-serial-$runId"
```

Expected: 299 images, 1,406 GT, Top-1 1,349, Top-3 1,390, FP 0, FN 5,
Unknown 48 and exactly `SKU2 -> SKU6`, `SKU6 -> SKU19`, `SKU17 -> SKU16`,
`SKU4 -> SKU6`. If these values differ, stop and investigate the baseline; do
not optimize against a shifted reference.

- [ ] **Step 3: Screen thread and microbatch candidates on the fixed E/M/H nine-image profile**

Test `intra_op_threads` values `1`, `4`, `8`, `16`, `24` that do not exceed
the host logical-CPU count. For the best thread count, compare inherited
`all` affinity with two documented subsets derived from the worker's allowed
logical CPU IDs (first half and alternating IDs); discard invalid/empty
subsets. For the best thread/affinity candidate test RepViT microbatch
`1`, `2`, `4`, `8`, `all`; then test DINO
microbatch `1`, `2`, `4`, `8`, `all`. Each candidate must run in a fresh
process using:

```powershell
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts/benchmark_cpu_rfdetr_299.py `
  --package-root . `
  --classifier-config configs/cpu_rfdetr_classifier_policy.yaml `
  --reference-mode serial_reference `
  --candidate-mode batch_pytorch `
  --sample-profile batch2_e3_m3_h3 `
  --intra-op-threads 8 `
  --cpu-affinity all `
  --repvit-microbatch 4 `
  --dino-microbatch 2 `
  --passes 3 `
  --first-order AB `
  --bootstrap-seed 20260729 `
  --output "artifacts/evaluations/cpu-screen-$runId"
```

Use the same warm-up and three alternating AB/BA passes. Retain only candidates
with identical nine-image object decisions and lower mean and p95.

Expected: a ranked candidate table; no candidate is promoted from this screen.

- [ ] **Step 4: Screen compile candidates**

For the best eager microbatch candidate, separately test:

```text
compile_models: [repvit]
compile_models: [dinov3]
compile_models: [repvit, dinov3]
```

Reject graph breaks, compile errors, any decision difference, mean regression
or p95 regression. Keep eager when compile does not produce a clear win.

- [ ] **Step 5: Run the top two candidates on all 299 images**

Run each candidate for at least three alternating AB/BA passes against the
serial reference. A candidate passes only when:

```text
quality_gate.passed = true
latency_gate.mean_ci_upper_ms < 0
latency_gate.p95_ci_upper_ms < 0
```

Expected: either one ranked winner or no passing candidate.

- [ ] **Step 6: Promote only a passing winner**

If a winner exists, update only the `runtime:` section of
`configs/cpu_rfdetr_classifier_policy.yaml` with its exact mode, microbatch and
thread/affinity values. If no candidate passes, leave the config as
`serial_reference` and preserve all rejection reports.

- [ ] **Step 7: Re-run the winner from the pinned config**

Run one fresh three-pass 299-image benchmark using only the updated config.

Expected: the same quality result and a passing paired latency gate. If the
pinned rerun fails, preserve its report, restore only this task's uncommitted
`runtime:` edit with `apply_patch`, and do not create the promotion commit.

- [ ] **Step 8: Commit the promotion only when Step 7 passes**

```powershell
git add configs/cpu_rfdetr_classifier_policy.yaml
git commit -m "perf: promote verified CPU batch runtime"
```

If no candidate passes, do not create this commit and report that
`serial_reference` remains canonical.

---

## Final Verification

- [ ] Run the focused suite from Task 9 Step 1.
- [ ] Confirm the final report records all artifact/data hashes, applied detector threshold, thread/affinity settings, microbatch sizes and runtime mode.
- [ ] Confirm current correct objects have zero regressions and the aggregate floors pass.
- [ ] Confirm paired mean and p95 one-sided 95% CI upper bounds are both below zero.
- [ ] Confirm `git diff --cached --name-only` contains only the intended task files before every commit.
- [ ] Confirm existing user-modified files outside the active task remain untouched.
- [ ] Do not claim OpenVINO/ONNX/model-change completion; those are outside this plan.
