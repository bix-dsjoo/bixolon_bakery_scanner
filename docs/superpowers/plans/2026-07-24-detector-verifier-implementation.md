# Detector + Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent CPU-deployed bakery box scanner in this repository using D-FINE-N, RTMDet-Tiny, a four-state crop verifier, annotation-masked pseudo-background recovery, conflict recovery, and a grouped-OOF development report.

**Architecture:** A new `bakery_scanner` Python package owns data preparation, detector experiment orchestration, verifier training, candidate fusion, deterministic solving, OpenVINO inference, and development reporting. Both detectors learn the single class `1: bread`; the final JSON API returns verified bread boxes that a future 20-class classifier can consume without depending on another repository.

**Tech Stack:** Python 3.11, PyTorch/timm for verifier training, official D-FINE commit `7fe2f8889f0b7b817f20c315b40fc15a4fb64ae6`, MMDetection `3.x` commit `ecac3a77becc63f23d9f6980b2a36f86acd00a8a`, MMDeploy commit `3f8604bd72e8e15d06b2e0552fe2fdb8f8de33c4`, OpenVINO `2026.2.1`, OpenCV, NumPy, SciPy, scikit-learn, Pillow, Pydantic, pytest.

**Approved design:** `docs/superpowers/specs/2026-07-24-detector-verifier-design.md`

**Execution override:** `docs/superpowers/plans/2026-07-24-existing-data-only-override.md` is binding for this run. It replaces any task detail that needs new physical images, tray coordinates, calibration, or a locked acceptance set.

## Global Constraints

- All work is contained in `C:\workspace\bixolon_bakery_scanner`.
- Runtime target is Windows 11 on Intel Core Ultra 9 285K with CPU inference.
- Processing latency is not an initial selection constraint.
- Initial deployment uses OpenVINO FP32; lower precision is accepted only when the locked acceptance output is identical.
- Camera position, distance, tray ROI, background, and lighting are fixed.
- Bread instances may touch or overlap.
- Runtime always returns boxes; it does not request a recapture or reject the whole scan.
- Both detectors train one category only: `1: bread`.
- Primary candidates are D-FINE-N 768 and RTMDet-Tiny 768.
- D-FINE-N 640 and RTMDet-Tiny 640 run as comparison candidates and conflict-recovery audits.
- Dataset splits group `(capture_batch, scene_number)` so E/H/M views of one scene never cross folds.
- Every detector, verifier, fusion, and solver threshold is selected from out-of-fold development evidence.
- The locked acceptance set is never used to select models, thresholds, weights, or post-processing.
- Primary success is Scan Exact Match Rate: zero misses, zero false positives, and zero duplicates per image.
- Seed is `20260724`; detector experiments additionally use `20260725` and `20260726`.
- Generated checkpoints, staged images, external repositories, virtual environments, and acceptance images are not committed.

## File Map

```text
pyproject.toml                                  package metadata and dependency groups
.gitignore                                     generated data, environments, artifacts, weights
configs/box_system.yaml                        paths, folds, experiment and recovery settings
configs/upstream/dfine_bread.yml               D-FINE single-class overlay
configs/upstream/rtmdet_tiny_bread.py          RTMDet single-class overlay
scripts/bootstrap_training.ps1                 pinned isolated detector environments
scripts/run_detector_matrix.ps1                four variants × three seeds × five folds
src/bakery_scanner/config.py                   validated project configuration
src/bakery_scanner/contracts.py                immutable boxes, proposals, results and enums
src/bakery_scanner/data/coco.py                strict COCO loading and one-class conversion
src/bakery_scanner/data/folds.py               scene grouping and five-fold manifests
src/bakery_scanner/data/preprocess.py          tray homography, color normalization, health
src/bakery_scanner/detectors/experiments.py    reproducible run specifications and receipts
src/bakery_scanner/detectors/dfine.py          D-FINE train/predict/export boundary
src/bakery_scanner/detectors/rtmdet.py         RTMDet train/predict/export boundary
src/bakery_scanner/detectors/oof.py            out-of-fold evidence and model-pair selection
src/bakery_scanner/evaluation.py               matching, SEMR and scenario metrics
src/bakery_scanner/verifier/data.py            four-state verifier sample generation
src/bakery_scanner/verifier/model.py           MobileNetV3 multi-head verifier
src/bakery_scanner/coverage.py                 fixed-tray reference and uncovered foreground
src/bakery_scanner/fusion.py                   candidate relationship graph and fusion
src/bakery_scanner/recovery.py                 640 audit and high-resolution tile recovery
src/bakery_scanner/solver.py                   deterministic global hypothesis selection
src/bakery_scanner/runtime.py                  end-to-end detector+verifier orchestration
src/bakery_scanner/openvino_runtime.py         CPU model loading and equivalence checks
src/bakery_scanner/acceptance.py               locked acceptance lease and report
src/bakery_scanner/cli.py                      project CLI
tests/                                         unit and integration tests mirroring modules
```

---

### Task 1: Project Foundation, Configuration, and Core Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `configs/box_system.yaml`
- Create: `src/bakery_scanner/__init__.py`
- Create: `src/bakery_scanner/config.py`
- Create: `src/bakery_scanner/contracts.py`
- Create: `tests/test_config.py`
- Create: `tests/test_contracts.py`

**Interfaces:**
- Produces: `ScannerConfig.load(path: Path) -> ScannerConfig`
- Produces: immutable `Box`, `SceneKey`, `BreadProposal`, `VerifiedBreadBox`, `BoxSystemResult`
- Produces: enums `DetectorKind`, `VerifierState`

- [ ] **Step 1: Write failing configuration and contract tests**

```python
def test_config_loads_current_dataset_paths():
    config = ScannerConfig.load(Path("configs/box_system.yaml"))
    assert len(config.dataset.sources) == 3
    assert config.dataset.expected_images == 299
    assert config.dataset.expected_boxes == 1410
    assert {row.input_size for row in config.detectors.variants} == {640, 768}


def test_bread_proposal_rejects_nonfinite_or_out_of_bounds_box():
    with pytest.raises(ValueError):
        BreadProposal(
            image_id=1,
            source="dfine_n_768",
            score=float("nan"),
            box=Box(0, 0, 10, 10),
            image_width=100,
            image_height=100,
        )
```

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m pytest tests/test_config.py tests/test_contracts.py -v`

Expected: FAIL because `bakery_scanner` does not exist.

- [ ] **Step 3: Add package metadata**

```toml
[build-system]
requires = ["setuptools>=78"]
build-backend = "setuptools.build_meta"

[project]
name = "bixolon-bakery-scanner"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = [
  "numpy>=2.4,<2.5",
  "Pillow==12.2.0",
  "opencv-python>=5.0,<5.1",
  "scipy>=1.17,<1.18",
  "scikit-learn>=1.9,<2",
  "PyYAML>=6.0,<7",
  "pydantic>=2.13,<3"
]

[project.optional-dependencies]
verifier = ["torch>=2.8,<2.9", "torchvision>=0.23,<0.24", "timm==1.0.28"]
runtime = ["openvino==2026.2.1"]
dev = ["pytest>=9.1,<10", "pytest-cov>=7.1,<8"]

[project.scripts]
bakery-boxes = "bakery_scanner.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 4: Implement strict immutable records**

```python
@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class VerifierState(IntEnum):
    INVALID = 0
    EXACTLY_ONE = 1
    PARTIAL = 2
    MULTIPLE = 3


@dataclass(frozen=True, slots=True)
class BreadProposal:
    image_id: int
    source: str
    score: float
    box: Box
    image_width: int
    image_height: int
    class_id: int = 1
    class_name: str = "bread"
```

Validate exact integer identities, finite scores in `[0,1]`, positive boxes,
source bounds, `1/bread`, unique source names, non-empty hashes, and canonical
ordering. `BoxSystemResult.to_json_bytes` and `.from_json_bytes` use UTF-8,
sorted keys, compact separators, reject extra/missing fields, and round-trip
to identical bytes.

- [ ] **Step 5: Add the project configuration**

```yaml
seed: 20260724
artifact_root: artifacts/box_system
camera:
  calibration: artifacts/box_system/calibration/tray_calibration.json
  canonical_size: 1536
dataset:
  sources:
    - name: group_15class
      images: datasets/detection/group_15class/images
      annotations: datasets/detection/group_15class/annotations/instances.json
    - name: group_20class_batch01
      images: datasets/detection/group_20class_batch01/images
      annotations: datasets/detection/group_20class_batch01/annotations/instances.json
    - name: group_20class_batch02
      images: datasets/detection/group_20class_batch02/images
      annotations: datasets/detection/group_20class_batch02/annotations/instances.json
  expected_images: 299
  expected_boxes: 1410
  folds: 5
detectors:
  seeds: [20260724, 20260725, 20260726]
  variants:
    - {name: dfine_n_640, backend: dfine, input_size: 640, role: audit}
    - {name: dfine_n_768, backend: dfine, input_size: 768, role: primary}
    - {name: rtmdet_tiny_640, backend: rtmdet, input_size: 640, role: audit}
    - {name: rtmdet_tiny_768, backend: rtmdet, input_size: 768, role: secondary}
runtime:
  device: CPU
  precision: FP32
  proposal_limit: 30
```

- [ ] **Step 6: Ignore generated state**

```text
.venv/
.venvs/
third_party/
artifacts/
acceptance_data/
__pycache__/
.pytest_cache/
*.pt
*.pth
*.onnx
*.xml
*.bin
```

- [ ] **Step 7: Install and run focused tests**

Run: `python -m pip install -e ".[dev]"; python -m pytest tests/test_config.py tests/test_contracts.py -v`

Expected: all tests pass.

- [ ] **Step 8: Commit project foundation**

```powershell
git add pyproject.toml .gitignore configs src tests
git commit -m "build: initialize bakery box scanner"
```

### Task 2: COCO Merge, Camera Normalization, and Scene-Grouped Folds

**Files:**
- Create: `src/bakery_scanner/data/__init__.py`
- Create: `src/bakery_scanner/data/coco.py`
- Create: `src/bakery_scanner/data/preprocess.py`
- Create: `src/bakery_scanner/data/folds.py`
- Create: `tests/test_coco.py`
- Create: `tests/test_preprocess.py`
- Create: `tests/test_folds.py`

**Interfaces:**
- Produces: `load_sources(config) -> tuple[CocoSource, ...]`
- Produces: `stage_single_class_dataset(sources, calibration, output) -> StagedDataset`
- Produces: `normalize_capture(image, calibration) -> NormalizedCapture`
- Produces: `build_scene_folds(dataset, fold_count=5, seed=20260724) -> tuple[FoldManifest, ...]`

- [ ] **Step 1: Write failing merge, coordinate, and leakage tests**

```python
def test_real_sources_merge_to_one_bread_class(config, calibration, tmp_path):
    staged = stage_single_class_dataset(load_sources(config), calibration, tmp_path)
    assert staged.image_count == 299
    assert staged.box_count == 1410
    payload = json.loads(staged.annotations.read_text(encoding="utf-8"))
    assert payload["categories"] == [
        {"id": 1, "name": "bread", "supercategory": "object"}
    ]


def test_box_transform_round_trips_with_half_pixel_tolerance(calibration):
    normalized = normalize_capture(Image.new("RGB", (400, 300)), calibration)
    box = Box(100, 80, 120, 90)
    restored = normalized.canonical_box_to_source(
        normalized.source_box_to_canonical(box)
    )
    assert restored == pytest.approx(box, abs=.5)


def test_same_batch_and_scene_never_cross_folds(staged_dataset):
    folds = build_scene_folds(staged_dataset, fold_count=5, seed=20260724)
    owners = {}
    for fold in folds:
        for scene in fold.validation_scenes:
            assert scene not in owners
            owners[scene] = fold.index
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_coco.py tests/test_preprocess.py tests/test_folds.py -v`

Expected: FAIL because the data modules are absent.

- [ ] **Step 3: Implement camera calibration and normalization**

```python
@dataclass(frozen=True, slots=True)
class CaptureHealth:
    focus_score: float
    focus_ok: bool
    exposure_mean: float
    exposure_ok: bool
    color_delta: float
    color_ok: bool
    corner_residual_px: float
    geometry_ok: bool


@dataclass(frozen=True, slots=True)
class NormalizedCapture:
    image: Image.Image
    health: CaptureHealth
    source_to_canonical: np.ndarray
    canonical_to_source: np.ndarray
```

`CameraCalibration` stores four normalized ROI corners, a canonical
1536×1536 target, neutral-patch Lab reference, focus lower bound, exposure
interval, color-delta upper bound, and source-image hashes. Calibration uses
at least 20 empty-tray images and writes observed extrema plus a 10% margin.
Normalization applies EXIF transpose, homography, neutral color gain, and
health measurement but never rejects an image.

- [ ] **Step 4: Implement strict COCO merge and staging**

Decode JSON with `utf-8-sig`, validate image and annotation IDs, verify files,
namespace IDs by source order, remap every category to `1/bread`, transform
all four box corners into canonical coordinates, write 1536×1536 canonical
PNG images, and atomically write sorted COCO JSON. Strict mode requires
exactly 299 images and 1,410 boxes.

- [ ] **Step 5: Implement deterministic scene folds**

```python
_SCENE = re.compile(
    r"^(?P<batch>g15|g20_b01|g20_b02)_(?P<view>[ehm])_(?P<number>\d{4})\.jpg$"
)
```

Group by `(batch, number)`. Use
`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20260724)` with
strata `(object_count_bin, overlap_proxy)` where bins are `0-2`, `3-5`, `6+`
and overlap proxy is whether any GT pair intersects. Serialize train/validation
scene keys, image IDs, source hashes, and manifest hash for every fold.

- [ ] **Step 6: Run focused tests twice**

Run:

```powershell
python -m pytest tests/test_coco.py tests/test_preprocess.py tests/test_folds.py -v
python -m pytest tests/test_coco.py tests/test_preprocess.py tests/test_folds.py -v
```

Expected: both runs pass with identical manifest hashes.

- [ ] **Step 7: Commit data foundation**

```powershell
git add src/bakery_scanner/data tests/test_coco.py tests/test_preprocess.py tests/test_folds.py
git commit -m "feat: stage scene-grouped bread detection data"
```

### Task 3: Exact-Match Evaluation and Detector Experiment Matrix

**Files:**
- Create: `src/bakery_scanner/evaluation.py`
- Create: `src/bakery_scanner/detectors/__init__.py`
- Create: `src/bakery_scanner/detectors/experiments.py`
- Create: `tests/test_evaluation.py`
- Create: `tests/test_experiments.py`

**Interfaces:**
- Produces: `match_boxes(gt, predictions, iou_threshold) -> MatchResult`
- Produces: `evaluate_scans(gt, predictions, scenarios) -> EvaluationReport`
- Produces: `experiment_matrix(config) -> tuple[DetectorExperiment, ...]`

- [ ] **Step 1: Write failing exact-match and matrix tests**

```python
def test_duplicate_fails_scan_with_complete_recall():
    report = evaluate_scans(
        gt={1: (Box(0, 0, 10, 10),)},
        predictions={1: (Box(0, 0, 10, 10), Box(1, 1, 10, 10))},
        scenarios={1: frozenset({"touching"})},
    )
    assert report.sem_exact == 0.0
    assert report.duplicates == 1


def test_matrix_has_four_variants_three_seeds_five_folds(config):
    rows = experiment_matrix(config)
    assert len(rows) == 60
    assert {(r.backend, r.input_size) for r in rows} == {
        ("dfine", 640), ("dfine", 768),
        ("rtmdet", 640), ("rtmdet", 768),
    }
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_evaluation.py tests/test_experiments.py -v`

Expected: FAIL because evaluation and experiment modules are absent.

- [ ] **Step 3: Implement maximum-cardinality matching and SEMR**

Build an IoU matrix and use `scipy.optimize.linear_sum_assignment` with dummy
rows/columns so valid cardinality is maximized before IoU. Report matches at
0.50/0.75/0.90, misses, false positives, duplicates, split errors, merge
errors, overall SEMR, strict SEMR@0.75/0.90, and every scenario stratum.
A scan is exact only when misses, false positives, and duplicates are all zero.

- [ ] **Step 4: Implement immutable experiment records**

```python
@dataclass(frozen=True, slots=True)
class DetectorExperiment:
    name: str
    backend: Literal["dfine", "rtmdet"]
    input_size: Literal[640, 768]
    seed: int
    fold: int

    @property
    def run_id(self) -> str:
        return f"{self.name}-seed{self.seed}-fold{self.fold}"
```

Each run receipt records config bytes, fold hash, upstream commit, command,
environment, checkpoint hash, raw prediction hash, start/end time, and status.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_evaluation.py tests/test_experiments.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit evaluation and experiment definitions**

```powershell
git add src/bakery_scanner/evaluation.py src/bakery_scanner/detectors tests/test_evaluation.py tests/test_experiments.py
git commit -m "feat: define exact-match detector experiments"
```

### Task 4: Pinned D-FINE/RTMDet Training and OOF Evidence

**Files:**
- Create: `configs/upstream/dfine_bread.yml`
- Create: `configs/upstream/rtmdet_tiny_bread.py`
- Create: `scripts/bootstrap_training.ps1`
- Create: `scripts/run_detector_matrix.ps1`
- Create: `src/bakery_scanner/detectors/dfine.py`
- Create: `src/bakery_scanner/detectors/rtmdet.py`
- Create: `src/bakery_scanner/detectors/oof.py`
- Create: `tests/test_dfine.py`
- Create: `tests/test_rtmdet.py`
- Create: `tests/test_oof.py`

**Interfaces:**
- Produces: `DFineRunner.train/predict/export_onnx`
- Produces: `RTMDetRunner.train/predict/export_onnx`
- Produces: `collect_oof_predictions(...) -> OofArtifact`
- Produces: `select_complementary_pair(reports) -> DetectorPairSelection`

- [ ] **Step 1: Write failing adapter and OOF isolation tests**

```python
def test_dfine_xyxy_is_normalized_to_source_xywh():
    rows = parse_dfine_output(
        image_id=7,
        image_size=(100, 80),
        labels=[0],
        boxes=[[10, 20, 40, 60]],
        scores=[.2],
        source="dfine_n_768",
    )
    assert rows[0].box == Box(10, 20, 30, 40)
    assert rows[0].class_name == "bread"


def test_oof_never_contains_training_scene(fake_runs, tmp_path):
    artifact = collect_oof_predictions(fake_runs, fake_runner_factory, tmp_path)
    assert all(
        row.scene not in artifact.training_scenes_by_run[row.run_id]
        for row in artifact.predictions
    )
```

- [ ] **Step 2: Confirm failures**

Run: `python -m pytest tests/test_dfine.py tests/test_rtmdet.py tests/test_oof.py -v`

Expected: FAIL because detector adapters are absent.

- [ ] **Step 3: Add isolated pinned bootstrap**

```powershell
$ErrorActionPreference = "Stop"
git clone https://github.com/Peterande/D-FINE.git third_party/D-FINE
git -C third_party/D-FINE checkout 7fe2f8889f0b7b817f20c315b40fc15a4fb64ae6
git clone --branch 3.x https://github.com/open-mmlab/mmdetection.git third_party/mmdetection
git -C third_party/mmdetection checkout ecac3a77becc63f23d9f6980b2a36f86acd00a8a
git clone https://github.com/open-mmlab/mmdeploy.git third_party/mmdeploy
git -C third_party/mmdeploy checkout 3f8604bd72e8e15d06b2e0552fe2fdb8f8de33c4
py -3.11 -m venv .venvs/dfine
py -3.11 -m venv .venvs/rtmdet
```

The script reuses a checkout only when HEAD equals the pinned commit and
installs each framework only in its own virtual environment.

- [ ] **Step 4: Add single-class upstream overlays**

D-FINE inherits its official N custom config and sets one class, COCO remap
off, staged fold paths, seed, and experiment input size. RTMDet inherits
`rtmdet_tiny_8xb32-300e_coco.py`, sets `num_classes=1`,
`metainfo={"classes": ("bread",)}`, staged fold paths, seed, and all resize
scales to 640 or 768.

- [ ] **Step 5: Implement command-backed adapters**

Adapters receive an injectable command runner so tests consume fixture JSON
without importing upstream libraries. Production uses official train/test/
export commands in the pinned environments. Parsers retain candidates down
to score `0.001`, cap each image at 30 after canonical sorting, convert to
canonical xywh, and reject unknown images, classes, duplicates, and invalid
coordinates.

- [ ] **Step 6: Implement OOF collection and pair selection**

Require one validation prediction artifact for every
model×seed×fold run. Select the pair lexicographically by union misses,
overlap merge errors, false/duplicate proposals, primary standalone misses,
SEMR after score calibration, and CPU latency last. Preserve all raw
predictions and alternatives, not only the winner.

- [ ] **Step 7: Run focused tests and script syntax checks**

Run:

```powershell
python -m pytest tests/test_dfine.py tests/test_rtmdet.py tests/test_oof.py -v
[scriptblock]::Create((Get-Content -Raw scripts/bootstrap_training.ps1)) | Out-Null
[scriptblock]::Create((Get-Content -Raw scripts/run_detector_matrix.ps1)) | Out-Null
```

Expected: tests pass and scripts parse.

- [ ] **Step 8: Commit detector orchestration**

```powershell
git add configs/upstream scripts src/bakery_scanner/detectors tests/test_dfine.py tests/test_rtmdet.py tests/test_oof.py
git commit -m "feat: collect heterogeneous detector OOF evidence"
```

### Task 5: Four-State Crop Verifier

**Files:**
- Create: `src/bakery_scanner/verifier/__init__.py`
- Create: `src/bakery_scanner/verifier/data.py`
- Create: `src/bakery_scanner/verifier/model.py`
- Create: `tests/test_verifier_data.py`
- Create: `tests/test_verifier_model.py`

**Interfaces:**
- Produces: `VerifierSample`
- Produces: `build_verifier_manifest(oof, ground_truth, folds, output)`
- Produces: `BoxVerifierNet`
- Produces: `train_verifier_oof(...) -> VerifierOofArtifact`
- Produces: `calibrate_verifier(oof) -> VerifierCalibration`

- [ ] **Step 1: Write failing state, leakage, and output-shape tests**

```python
def test_manifest_contains_all_four_states(scene_fixture, tmp_path):
    manifest = build_verifier_manifest(
        scene_fixture.oof, scene_fixture.gt, scene_fixture.folds, tmp_path
    )
    assert {row.state for row in manifest.samples} == set(VerifierState)


def test_samples_inherit_source_scene_fold(scene_fixture, tmp_path):
    manifest = build_verifier_manifest(
        scene_fixture.oof, scene_fixture.gt, scene_fixture.folds, tmp_path
    )
    assert all(
        row.fold == scene_fixture.fold_for(row.source_scene)
        for row in manifest.samples
    )


def test_model_outputs_four_states_and_regression_heads(fake_backbone):
    output = BoxVerifierNet(fake_backbone, feature_count=8)(
        torch.zeros(2, 3, 256, 256)
    )
    assert output.state_logits.shape == (2, 4)
    assert output.expected_iou.shape == (2, 1)
    assert output.delta.shape == (2, 4)
    assert output.occupancy.shape == (2, 1)
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_verifier_data.py tests/test_verifier_model.py -v`

Expected: FAIL because verifier modules are absent.

- [ ] **Step 3: Generate deterministic verifier samples**

Generate `EXACTLY_ONE` from GT and IoU 0.75–1.0 jitter, `PARTIAL` by clipping
15–45% from one or two sides, `MULTIPLE` from unions of adjacent GT and real
merge errors, and `INVALID` from OOF false proposals, tray background, gaps,
hands, tongs, wrappers, labels, and crumbs. Each crop includes 15% context,
stores target IoU, `dx/dy/dw/dh`, occupancy, source scene, and inherited fold.

- [ ] **Step 4: Implement the verifier network**

```python
class BoxVerifierNet(nn.Module):
    def __init__(self, backbone: nn.Module, feature_count: int) -> None:
        super().__init__()
        self.backbone = backbone
        self.state_head = nn.Linear(feature_count, 4)
        self.iou_head = nn.Linear(feature_count, 1)
        self.delta_head = nn.Linear(feature_count, 4)
        self.occupancy_head = nn.Linear(feature_count, 1)
```

Production uses
`timm.create_model("mobilenetv3_small_100", pretrained=True, num_classes=0,
global_pool="avg")`. Use 256×256 ImageNet-normalized crops, state
cross-entropy, Smooth-L1 IoU/occupancy loss, and delta loss only for
`EXACTLY_ONE/PARTIAL`. Train five OOF folds with early-stopping patience 15.

- [ ] **Step 5: Calibrate from OOF evidence**

Enumerate all unique `EXACTLY_ONE` probabilities. Choose the largest threshold
with zero false rejection of valid GT crops, then minimize accepted invalid,
partial, and multiple samples. Persist complete logits, targets, scenes,
folds, checkpoint hashes, and selected calibration.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_verifier_data.py tests/test_verifier_model.py -v`

Expected: all tests pass without downloading weights in unit tests.

- [ ] **Step 7: Commit verifier**

```powershell
git add src/bakery_scanner/verifier tests/test_verifier_data.py tests/test_verifier_model.py
git commit -m "feat: train four-state crop verifier"
```

### Task 6: Fixed-Tray Foreground Coverage

**Files:**
- Create: `src/bakery_scanner/coverage.py`
- Create: `tests/test_coverage.py`

**Interfaces:**
- Produces: `TrayReference`
- Produces: `CoverageResult`
- Produces: `build_tray_reference(empty_images, roi_mask) -> TrayReference`
- Produces: `measure_coverage(image, reference, boxes) -> CoverageResult`

- [ ] **Step 1: Write failing empty, missed-region, and touching tests**

```python
def test_empty_tray_has_zero_uncovered(reference):
    result = measure_coverage(reference.empty_image, reference, ())
    assert result.uncovered_pixels == 0
    assert result.uncovered_ratio == 0.0


def test_unboxed_foreground_is_reported(reference, image_with_two_breads):
    result = measure_coverage(
        image_with_two_breads, reference, (Box(5, 5, 20, 20),)
    )
    assert result.uncovered_pixels > 0


def test_connected_components_are_not_exposed_as_object_count(reference, touching):
    result = measure_coverage(touching, reference, ())
    assert not hasattr(result, "object_count")
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_coverage.py -v`

Expected: FAIL because coverage is absent.

- [ ] **Step 3: Implement robust foreground measurement**

Build per-pixel Lab median and median absolute deviation from at least 20
empty-tray images. Foreground score combines normalized Lab distance and Sobel
edge residual. Calibrate the minimum component area from the maximum observed
empty/crumb/lighting component plus 10%. Expand selected boxes by 3% only for
coverage accounting. Return uncovered pixels, ratio, and regions; never infer
product count from connected components.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_coverage.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit coverage verifier**

```powershell
git add src/bakery_scanner/coverage.py tests/test_coverage.py
git commit -m "feat: verify fixed-tray foreground coverage"
```

### Task 7: Candidate Fusion, Recovery, and Global Solver

**Files:**
- Create: `src/bakery_scanner/fusion.py`
- Create: `src/bakery_scanner/recovery.py`
- Create: `src/bakery_scanner/solver.py`
- Create: `tests/test_fusion.py`
- Create: `tests/test_recovery.py`
- Create: `tests/test_solver.py`

**Interfaces:**
- Produces: `build_hypotheses(primary, secondary, verifier)`
- Produces: `RecoveryRunner.recover(image, hypotheses, coverage)`
- Produces: `solve_boxes(hypotheses, coverage, calibration) -> SolverResult`

- [ ] **Step 1: Write failing one-to-many and duplicate tests**

```python
def test_one_to_two_retains_merged_and_split_hypotheses():
    rows = build_hypotheses(
        primary=(proposal(Box(0, 0, 30, 10), "dfine_n_768"),),
        secondary=(
            proposal(Box(0, 0, 14, 10), "rtmdet_tiny_768"),
            proposal(Box(16, 0, 14, 10), "rtmdet_tiny_768"),
        ),
        verifier=fake_verifier(),
    )
    assert {row.kind for row in rows} >= {"merged", "split"}


def test_solver_keeps_real_overlap_and_removes_same_object_duplicate():
    result = solve_boxes(
        overlap_and_duplicate_hypotheses(),
        coverage_fixture(),
        solver_calibration(),
    )
    assert len(result.boxes) == 2
    assert result.duplicate_count == 1
```

- [ ] **Step 2: Write failing recovery-order test**

```python
def test_recovery_order_is_low_scores_640_then_tiles(fake_backends):
    evidence = RecoveryRunner(fake_backends).recover(
        conflict_image(), conflict_hypotheses(), uncovered_coverage()
    )
    assert evidence.executed_stages == (
        "low_score_restore",
        "dfine_n_640",
        "rtmdet_tiny_640",
        "dfine_n_768_tiles",
    )
```

- [ ] **Step 3: Confirm tests fail**

Run: `python -m pytest tests/test_fusion.py tests/test_recovery.py tests/test_solver.py -v`

Expected: FAIL because fusion, recovery, and solver are absent.

- [ ] **Step 4: Implement relationship graph and fusion**

Connect candidates by calibrated IoU or normalized center distance with area
ratio 0.5–2.0. Produce `1↔1`, `1↔0`, `1↔N`, and `N↔N` components.
Use verifier expected IoU and detector reliability for weighted fusion of
`1↔1`. Preserve both merged and split hypotheses for `1↔N`. Do not apply
ordinary cross-model NMS.

- [ ] **Step 5: Implement ordered recovery**

Restore low-score 768 candidates, run both 640 models, then run D-FINE-N 768
on 2×2 source tiles with 25% overlap. Map tile boxes back to canonical
coordinates. Mark a box touching an internal tile edge as partial unless
another source confirms it. Verify every recovered candidate.

- [ ] **Step 6: Implement deterministic beam solver**

Use canonical hypothesis ordering and beam width 256. Score detector agreement,
`EXACTLY_ONE`, expected IoU, and coverage gain; subtract duplicate,
partial/multiple, and outside-ROI penalties. Enumerate OOF-derived
threshold/weight combinations and select lexicographically by misses, false
positives, duplicates, merge/split errors, strict SEMR@0.75, then complexity.

- [ ] **Step 7: Run tests twice for determinism**

Run:

```powershell
python -m pytest tests/test_fusion.py tests/test_recovery.py tests/test_solver.py -v
python -m pytest tests/test_fusion.py tests/test_recovery.py tests/test_solver.py -v
```

Expected: all tests pass identically.

- [ ] **Step 8: Commit solver pipeline**

```powershell
git add src/bakery_scanner/fusion.py src/bakery_scanner/recovery.py src/bakery_scanner/solver.py tests/test_fusion.py tests/test_recovery.py tests/test_solver.py
git commit -m "feat: fuse and solve overlapping bread boxes"
```

### Task 8: End-to-End Runtime and Canonical Audit Output

**Files:**
- Create: `src/bakery_scanner/runtime.py`
- Create: `tests/test_runtime.py`
- Create: `tests/test_result_serialization.py`

**Interfaces:**
- Produces: `BoxSystemPipeline.infer(image, source_id) -> BoxSystemResult`
- Produces: canonical JSON containing final boxes and all audit evidence

- [ ] **Step 1: Write failing orchestration and serialization tests**

```python
def test_runtime_stage_order(fakes):
    result = fakes.pipeline.infer(
        Image.new("RGB", (100, 100)), source_id="scan-1"
    )
    assert fakes.calls == [
        "normalize",
        "dfine_n_768",
        "rtmdet_tiny_768",
        "verify",
        "coverage",
        "solve",
    ]
    assert all(row.class_name == "bread" for row in result.boxes)


def test_result_round_trip_is_byte_identical(result):
    payload = result.to_json_bytes()
    assert BoxSystemResult.from_json_bytes(payload).to_json_bytes() == payload
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_runtime.py tests/test_result_serialization.py -v`

Expected: FAIL because runtime orchestration is absent.

- [ ] **Step 3: Implement end-to-end orchestration**

Normalize once, run both 768 detectors, build hypotheses, verify crops,
measure coverage, and solve. Trigger recovery only for `PARTIAL/MULTIPLE`,
one-to-many/many-to-many relations, or uncovered foreground above calibration.
If ambiguity remains, always return the highest calibrated solver result and
add `UNRESOLVED_FORCED_DECISION`.

- [ ] **Step 4: Implement complete audit output**

Store source SHA-256, camera health, artifact hashes, raw detector proposals,
verifier outputs, coverage ratio/regions, recovery stages, chosen boxes,
decision quality, conflict codes, and per-stage milliseconds. Object IDs use
top-left ordering as `bread-0001`, `bread-0002`, and so on. Reject non-finite
or non-canonical serialized values.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_runtime.py tests/test_result_serialization.py -v`

Expected: all tests pass.

- [ ] **Step 6: Commit runtime**

```powershell
git add src/bakery_scanner/runtime.py tests/test_runtime.py tests/test_result_serialization.py
git commit -m "feat: orchestrate audited box inference"
```

### Task 9: OpenVINO FP32 Deployment and CLI

**Files:**
- Create: `src/bakery_scanner/openvino_runtime.py`
- Create: `src/bakery_scanner/cli.py`
- Create: `tests/test_openvino_runtime.py`
- Create: `tests/test_cli.py`
- Create: `scripts/export_openvino.ps1`

**Interfaces:**
- Produces: `OpenVinoDetector`, `OpenVinoVerifier`
- Produces: `compare_backends(reference, candidate) -> EquivalenceReport`
- Produces CLI commands `calibrate-camera`, `stage-data`, `run-oof`, `train-verifier`, `calibrate-solver`, `export-openvino`, `compare-backends`, `infer`

- [ ] **Step 1: Write failing lazy-load and equivalence tests**

```python
def test_openvino_compiles_cpu_latency_single_stream(fake_core, artifact):
    load_openvino_model(artifact, core=fake_core)
    assert fake_core.compile_calls == [
        (artifact.xml, "CPU", {
            "PERFORMANCE_HINT": "LATENCY",
            "NUM_STREAMS": "1",
        })
    ]


def test_count_change_fails_equivalence(reference_result):
    changed = replace(reference_result, boxes=reference_result.boxes[:-1])
    assert compare_backends((reference_result,), (changed,)).equivalent is False
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_openvino_runtime.py tests/test_cli.py -v`

Expected: FAIL because runtime deployment and CLI are absent.

- [ ] **Step 3: Implement OpenVINO conversion and lazy loading**

Import OpenVINO only inside factories. Convert ONNX with `ov.convert_model`,
save with `compress_to_fp16=False`, compile on `CPU` with latency hint and one
stream, and record OpenVINO version, input/output names, preprocessing,
checkpoint hash, ONNX hash, XML hash, and BIN hash.

- [ ] **Step 4: Implement backend equivalence**

Require identical final count, verifier state, recovery stages, SEMR, misses,
false positives, duplicates, split and merge errors. Allow at most 0.5 source
pixel coordinate delta and `1e-4` score delta. Any mismatch blocks lower
precision and keeps FP32.

- [ ] **Step 5: Implement focused CLI receipts**

Each command loads `configs/box_system.yaml` and atomically writes arguments,
input/output hashes, environment, duration, and exit status. `infer` accepts
an image and output JSON path and never imports training frameworks.

- [ ] **Step 6: Run tests and script syntax**

Run:

```powershell
python -m pytest tests/test_openvino_runtime.py tests/test_cli.py -v
[scriptblock]::Create((Get-Content -Raw scripts/export_openvino.ps1)) | Out-Null
bakery-boxes --help
```

Expected: tests pass, script parses, and help lists eight commands.

- [ ] **Step 7: Commit runtime deployment**

```powershell
git add src/bakery_scanner/openvino_runtime.py src/bakery_scanner/cli.py tests/test_openvino_runtime.py tests/test_cli.py scripts/export_openvino.ps1
git commit -m "feat: deploy box system with OpenVINO FP32"
```

### Task 10: Locked Acceptance, Full Verification, and Documentation

**Files:**
- Create: `src/bakery_scanner/acceptance.py`
- Create: `tests/test_acceptance.py`
- Modify: `src/bakery_scanner/cli.py`
- Create: `README.md`
- Create generated ignored output: `artifacts/box_system/acceptance/`

**Interfaces:**
- Produces: `BoxAcceptanceLease`
- Produces: `run_acceptance(lock_path) -> AcceptanceReport`
- Adds CLI commands `freeze-acceptance`, `acceptance`

- [ ] **Step 1: Write failing one-shot and scenario tests**

```python
def test_acceptance_creates_sentinel_before_first_image(fixture):
    report = run_acceptance(fixture.lock)
    assert fixture.events[0] == "sentinel-created"
    assert report.total_images >= 3000


def test_one_scenario_error_fails_acceptance():
    report = acceptance_report(
        overall_errors=0,
        scenarios={"overlap": scenario_report(errors=1)},
    )
    assert report.passed is False
```

- [ ] **Step 2: Confirm tests fail**

Run: `python -m pytest tests/test_acceptance.py -v`

Expected: FAIL because acceptance is absent.

- [ ] **Step 3: Implement immutable acceptance lock**

The lock records all artifact hashes, config hash, Git commit, acceptance
manifest hash, and at least 3,000 tagged images. Create
`artifacts/box_system/ACCEPTANCE_CONSUMED` atomically before opening an image;
reject every later run. Required zero-error strata are empty tray, touching,
overlap, tray edge, maximum count, and `bread_01` through `bread_20`.

- [ ] **Step 4: Implement acceptance report**

Acceptance passes only when the overall set and every populated required
stratum have zero misses, false positives, duplicates, split errors, and
merge errors. Report SEMR@0.50/0.75/0.90 and the 95% zero-failure upper bound
`1 - 0.05 ** (1 / n)`. State that finite zero-error evidence is not an
absolute guarantee for unseen operating conditions.

- [ ] **Step 5: Document the reproducible workflow**

README covers environment bootstrap, camera/empty-tray calibration, staging,
60 detector runs, OOF collection, verifier training, solver calibration,
OpenVINO export/equivalence, inference JSON, acceptance-data rules, one-shot
acceptance, audit receipts, and hard-case retraining.

- [ ] **Step 6: Run all verification**

Run:

```powershell
python -m pytest -q
git diff --check
bakery-boxes --help
```

Expected: all tests pass, no whitespace errors, and CLI lists ten commands.

- [ ] **Step 7: Run development pipeline before locked acceptance**

Run:

```powershell
bakery-boxes calibrate-camera --config configs/box_system.yaml --empty-images empty_tray --corners tray_corners.json
bakery-boxes stage-data --config configs/box_system.yaml
bakery-boxes run-oof --config configs/box_system.yaml
bakery-boxes train-verifier --config configs/box_system.yaml
bakery-boxes calibrate-solver --config configs/box_system.yaml
bakery-boxes export-openvino --config configs/box_system.yaml
bakery-boxes compare-backends --config configs/box_system.yaml
```

Expected: staging reports 299 images/1,410 boxes; every OOF prediction belongs
to its validation fold; selected pair and alternatives are recorded; verifier
and solver use OOF evidence only; FP32 backend produces identical final counts
and SEMR to the reference backend.

- [ ] **Step 8: Commit acceptance and documentation**

```powershell
git add src/bakery_scanner/acceptance.py src/bakery_scanner/cli.py tests/test_acceptance.py README.md
git commit -m "feat: gate detector verifier on exact-match acceptance"
```

## Final Completion Gate

Run only after Tasks 1–10:

```powershell
python -m pytest -q
git diff --check
git status --short
bakery-boxes compare-backends --config configs/box_system.yaml
```

Completion requires all tests passing, no whitespace errors, deterministic
fold manifests, complete OOF provenance, matching artifact hashes, and
identical reference/OpenVINO FP32 final counts and SEMR. Locked acceptance is
run only after at least 3,000 tagged images exist, and no model or threshold
changes are permitted after acceptance results are opened.
