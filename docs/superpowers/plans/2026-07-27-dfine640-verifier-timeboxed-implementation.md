# D-FINE-N 640 + Verifier Timeboxed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a GPU-only, development-scoped D-FINE-N 640 proposal detector paired with a four-state crop verifier, using only the existing 299 images / 1,410 boxes.

**Architecture:** One fixed detector (`dfine_n_640`, seed `20260724`) emits recall-oriented candidates. A fold-isolated verifier labels each original candidate box as `INVALID`, `EXACTLY_ONE`, `PARTIAL`, or `MULTIPLE`; uncertainty is retained as an unresolved decision, never silently counted as bread. Five grouped OOF folds calibrate policy, then one full-data detector/verifier bundle is trained.

**Tech Stack:** Python 3.11, CUDA 12.8, RTX 5080, pinned D-FINE, PyTorch/timm MobileNetV4, Pillow/OpenCV/NumPy, pytest.

**Supersedes for this execution:** only the 60-run four-variant matrix portion of [the original plan](2026-07-24-detector-verifier-implementation.md). Preserve that plan and every existing artifact. D-FINE 768 and both RTMDet variants are intentionally excluded.

## Global Constraints

- Training and model inference require RTX 5080 `cuda:0`; CPU is permitted only for file integrity and tests.
- Use exactly the existing staged 299 images and 1,410 boxes. Do not add recaptures, empty trays, corners, or synthetic physical-obstruction claims.
- Keep `(capture_batch, scene_number)` groups whole.
- Raw detector policy is fixed before calibration: score `>= 0.001`, sort `(-score, y, x, height, width)`, retain at most 30 rows per run/image/source.
- A target fold's detector/verifier threshold uses only the other four folds.
- Keep source-image coordinates and record unresolved verifier states; `PARTIAL`/ `MULTIPLE` are not final positive counts.
- All reports must say development-only, not an operational 100% guarantee, and name missing empty-tray, tray-corner, real overlap/obstruction, and independent acceptance data.

## Current-Run Handoff

The running `dfine_n_640-seed20260724-fold0` is required evidence. Do not interrupt it before `receipt.json`, `validation_predictions.json`, and `processed_validation_image_ids.json` exist and pass hash/held-out-ID validation. At that boundary, record parent/child PIDs and timestamp; stop the obsolete 60-run parent before it starts another full train. Preserve any partial next-run directory under `artifacts/box_system/failed-runs/`; do not delete it.

---

### Task 1: Freeze a resumable D-FINE-N 640 five-fold schedule

**Files:**

- Create: `scripts/run_dfine640_oof.ps1`
- Modify: `src/bakery_scanner/detectors/oof.py`
- Modify: `src/bakery_scanner/detectors/selection.py`
- Modify: `src/bakery_scanner/detectors/proposal_policy.py`
- Modify: `tests/test_oof.py`
- Modify: `tests/test_proposal_policy.py`

**Interfaces:**

```python
def retain_raw_proposals(proposals: Iterable[BreadProposal]) -> Sequence[BreadProposal]:
    """Return floor-filtered, canonical, per-image/source top-30 proposals."""
def load_complete_oof_artifact(*, detector_root: Path, fold_root: Path, staged_root: Path, expected_experiments: Iterable[DetectorExperiment], config_root: Path | None = None) -> OofArtifact:
    """Revalidate complete, held-out, hash-consistent detector evidence."""
```

- [ ] **Step 1: Write failing policy tests.**

```python
def test_calibration_keeps_each_run_top30_before_seed_union():
    # A seed-A score of .51 remains eligible despite seed-B higher boxes
    assert 0.51 in candidate_scores_by_run_then_union(artifact, "dfine_n_640")

def test_disk_oof_rejects_floor_score_duplicate_xyxy(tmp_path):
    write_complete_run(tmp_path, predictions=[box(.9), box(.8)])
    with pytest.raises(ValueError, match="duplicate"):
        load_complete_oof_artifact(detector_root=tmp_path / "detectors", fold_root=tmp_path / "folds", staged_root=tmp_path / "staged", expected_experiments=(experiment,))
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_proposal_policy.py tests/test_oof.py -q`

Expected: fail due to seed-mixed cap or missing canonical duplicate check.

- [ ] **Step 3: Implement the policy boundary.**

Apply raw policy separately for each `run_id` before unioning calibration candidate scores. Reject same `(run_id, image_id, source, xyxy)` duplicate rows at score `>= .001` in the disk loader. Keep lower-score rows ignorable.

- [ ] **Step 4: Implement the dedicated runner.**

`run_dfine640_oof.ps1` validates an existing completed fold with receipt/config/fold/prediction/processed-ID hashes, reuses valid fold 0, and trains only missing fold 1–4 using `.venvs/dfine/Scripts/python.exe third_party/D-FINE/train.py -c $RunConfig -d cuda:0`. It must emit the current raw prediction, canonical JSON, processed IDs, generated config, and receipt contracts; it must not emit 768/RTMDet runs.

- [ ] **Step 5: Verify and commit.**

Run:

```powershell
[scriptblock]::Create((Get-Content -Raw scripts/run_dfine640_oof.ps1)) | Out-Null
python -m pytest tests/test_dfine.py tests/test_oof.py tests/test_proposal_policy.py tests/test_detector_selection.py -q
git add scripts/run_dfine640_oof.ps1 src/bakery_scanner/detectors tests/test_oof.py tests/test_proposal_policy.py
git commit -m "feat: narrow detector OOF to dfine 640"
```

### Task 2: Create fold-isolated four-state verifier examples

**Files:**

- Create: `src/bakery_scanner/verifier/__init__.py`
- Create: `src/bakery_scanner/verifier/data.py`
- Create: `tests/test_verifier_data.py`

**Interfaces:**

```python
class VerifierState(IntEnum):
    INVALID = 0
    EXACTLY_ONE = 1
    PARTIAL = 2
    MULTIPLE = 3

@dataclass(frozen=True, slots=True)
class VerifierExample:
    image_id: int
    crop_xywh: Box
    state: VerifierState

def build_verifier_examples(*, image_ids: frozenset[int],
                            ground_truth: Mapping[int, Sequence[Box]],
                            seed: int) -> Sequence[VerifierExample]:
    """Return deterministic four-state crop metadata restricted to image_ids."""
```

- [ ] **Step 1: Write failing data tests.**

```python
def test_examples_cover_four_states_deterministically():
    examples = build_verifier_examples(image_ids=frozenset({1}), ground_truth=boxes, seed=7)
    assert {row.state for row in examples} == set(VerifierState)

def test_training_examples_never_include_validation_image():
    assert {row.image_id for row in train_examples}.isdisjoint(validation_ids)
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_verifier_data.py -q`

- [ ] **Step 3: Implement bounded crop labels.**

With local seeded randomness and image-bound clamping, create:
- `EXACTLY_ONE`: exactly one GT fully contained; every other GT overlap ≤ .05.
- `PARTIAL`: target overlaps crop but is not fully contained.
- `MULTIPLE`: at least two GT boxes overlap crop by > .05.
- `INVALID`: no GT overlap.

Serialize the seed and generation parameters with every fold artifact.

- [ ] **Step 4: Verify and commit.**

Run:

```powershell
python -m pytest tests/test_verifier_data.py -q
git add src/bakery_scanner/verifier tests/test_verifier_data.py
git commit -m "feat: create fold-isolated verifier examples"
```

### Task 3: Train five GPU verifier folds

**Files:**

- Create: `src/bakery_scanner/verifier/model.py`
- Create: `scripts/run_verifier_oof.ps1`
- Create: `tests/test_verifier_model.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class VerifierPrediction:
    image_id: int
    crop_xywh: Box
    probabilities: tuple[float, float, float, float]

def classify_verifier_batch(model: nn.Module, crops: Tensor) -> Tensor:
    """Return a [batch, 4] softmax probability tensor."""
```

- [ ] **Step 1: Write failing output/device tests.**

```python
def test_verifier_outputs_four_normalized_probabilities():
    assert torch.allclose(classify_verifier_batch(model, crops).sum(dim=1), torch.ones(2))
def test_verifier_runner_rejects_cpu_device():
    with pytest.raises(ValueError, match="cuda:0"):
        runner.train(train_manifest, output_dir, device="cpu")
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_verifier_model.py -q`

- [ ] **Step 3: Implement MobileNetV4 verifier.**

Use timm MobileNetV4 with fixed RGB crop preprocessing and four logits. Enforce `cuda:0`, deterministic seed, and record checkpoint/class order/preprocessing/training-fold/config hashes in its receipt.

- [ ] **Step 4: Implement the OOF runner.**

For fold *k*, train only on the other four groups. Run inference only on fold *k* D-FINE candidates; write original box, four probabilities, fold, and verifier receipt hash to `verifier_predictions.json`. Never derive validation labels after prediction.

- [ ] **Step 5: Verify and commit.**

Run:

```powershell
python -m pytest tests/test_verifier_data.py tests/test_verifier_model.py -q
[scriptblock]::Create((Get-Content -Raw scripts/run_verifier_oof.ps1)) | Out-Null
git add src/bakery_scanner/verifier scripts/run_verifier_oof.ps1 tests/test_verifier_data.py tests/test_verifier_model.py
git commit -m "feat: train grouped OOF verifier"
```

### Task 4: Cross-fit D-FINE + verifier decisions and development report

**Files:**

- Create: `src/bakery_scanner/detectors/dfine640_selection.py`
- Create: `scripts/select_dfine640_verifier.py`
- Modify: `src/bakery_scanner/detectors/selection.py`
- Create: `tests/test_dfine640_selection.py`
- Modify: `tests/test_detector_selection.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class FoldPolicy:
    detector_score_threshold: float
    minimum_exactly_one_probability: float

def cross_fit_policies(*, detector_oof: OofArtifact,
                       verifier_predictions: Mapping[int, Sequence[VerifierPrediction]],
                       folds: Mapping[int, int]) -> Mapping[int, FoldPolicy]:
    """Return a separately selected detector/verifier policy for folds 0 through 4."""
```

- [ ] **Step 1: Write a failing no-self-calibration test.**

```python
def test_fold_zero_policy_uses_only_other_four_folds():
    policies = cross_fit_policies(detector_oof=artifact, verifier_predictions=predictions, folds=folds)
    assert policies[0] == FoldPolicy(.42, .80)
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_dfine640_selection.py -q`

- [ ] **Step 3: Implement recall-first cross-fitting.**

For target fold *k*, enumerate detector/verifier candidate thresholds from folds other than *k* plus zero. Rank by unresolved/missed breads, merge errors, invalid false positives, duplicates, then SEMR@.50; deterministic score order resolves only exact ties. Apply each policy only to its target fold.

- [ ] **Step 4: Write the immutable development report.**

Record staged count `299/1410`, staged and fold hashes, all five detector/verifier receipts, raw/canonical prediction hashes, per-fold policies, misses, false positives, duplicates, split errors, merge errors, SEMR@.50/.75/.90, scenario strata, config bytes/hashes, and `operational_guarantee: false`.

- [ ] **Step 5: Verify and commit.**

Run:

```powershell
python -m pytest tests/test_detector_selection.py tests/test_dfine640_selection.py -q
python scripts/select_dfine640_verifier.py --help
git add src/bakery_scanner/detectors scripts/select_dfine640_verifier.py tests/test_detector_selection.py tests/test_dfine640_selection.py
git commit -m "feat: cross-fit dfine verifier policy"
```

### Task 5: Train one final full-data bundle and smoke it on GPU

**Files:**

- Create: `src/bakery_scanner/detectors/bundle.py`
- Create: `scripts/train_dfine640_verifier_final.ps1`
- Create: `tests/test_detector_bundle.py`

**Interfaces:**

```python
def validate_final_bundle(bundle_root: Path, *, expected_staged_images: int = 299,
                          expected_staged_boxes: int = 1410) -> None:
    """Raise unless every immutable final-bundle member and its hash is present."""
```

- [ ] **Step 1: Write a failing bundle test.**

```python
def test_bundle_requires_detector_verifier_policy_and_hashes(tmp_path):
    with pytest.raises(ValueError, match="verifier checkpoint"):
        validate_final_bundle(tmp_path)
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_detector_bundle.py -q`

- [ ] **Step 3: Implement full-data GPU training.**

Train one D-FINE-N 640 on all 299 images and one verifier on all generated examples on `cuda:0`. The manifest includes detector/verifier checkpoints, config/preprocessing/class order, final policy, training-data/report hashes, and GPU/runtime metadata. Refuse absent or hash-mismatched inputs.

- [ ] **Step 4: Add one-image GPU smoke inference.**

Assert detector boxes stay in original bounds, verifier probabilities sum to one within `1e-6`, and every result has a declared four-state outcome.

- [ ] **Step 5: Verify and commit.**

Run:

```powershell
python -m pytest tests/test_detector_bundle.py tests/test_verifier_model.py -q
[scriptblock]::Create((Get-Content -Raw scripts/train_dfine640_verifier_final.ps1)) | Out-Null
git add src/bakery_scanner/detectors/bundle.py scripts/train_dfine640_verifier_final.ps1 tests/test_detector_bundle.py
git commit -m "feat: package final dfine verifier bundle"
```

### Task 6: Execute the revised pipeline and document scope

**Files:**

- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-24-existing-data-only-override.md`
- Create generated: `artifacts/box_system/reports/dfine640_verifier_development.json`

- [ ] **Step 1: Audit current fold 0 at completion.**

Run:

```powershell
python scripts/select_dfine640_verifier.py --validate-detector-fold 0 --config configs/box_system.yaml
```

Expected: completed receipt hash-matches config/fold/prediction/processed IDs and processed IDs exactly equal fold-0 validation IDs.

- [ ] **Step 2: Perform the controlled handoff.**

After Step 1 succeeds, write PID/timestamp to `artifacts/box_system/logs/dfine640-handoff.json`, stop the obsolete matrix parent, retain any partial next run in failed-runs, and confirm no trainer remains before starting the new runner.

- [ ] **Step 3: Run OOF and selection.**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dfine640_oof.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_verifier_oof.ps1
python scripts/select_dfine640_verifier.py --config configs/box_system.yaml --output artifacts/box_system/reports/dfine640_verifier_development.json
```

Expected: exactly five detector and five verifier receipts and an immutable development-only report.

- [ ] **Step 4: Train final bundle and audit.**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/train_dfine640_verifier_final.ps1
python -m pytest -q
git diff --check
git status --short
```

- [ ] **Step 5: Document scope accurately.**

State that D-FINE-N 640 seed 20260724 plus verifier was selected for time, 768/RTMDet were not trained, and this work does not establish operational 100% detection.

## Completion Evidence

- Five valid D-FINE-N 640 seed-20260724 OOF receipts and five verifier OOF receipts exist.
- Each of 299 staged images appears exactly once per OOF fold group; report inputs include all 1,410 boxes.
- Cross-fit policies never use a target fold to select its own thresholds.
- A full-data detector/verifier bundle passes manifest validation and one-image GPU smoke inference.
- Report is immutable, contains every listed error category and limitation, and makes no operational guarantee.
