# Canonical Frame + Local Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the entire scan pipeline use EXIF-normalized visual coordinates, then extend conditional DINOv3 recheck with global Top-5 retrieval and product-mask local patch reranking.

**Architecture:** A shared canonical-image adapter owns EXIF transpose, RGB conversion, dimensions, and raw-to-visual orientation provenance. Detector, Verifier, Classifier, evidence, and benchmark consume its visual frame. RepViT retains its direct safe gate; an abstention triggers DINO global retrieval, local matching only for five global candidates, calibrated fusion, then safe SKU confirmation or `Unknown` Top-3.

**Tech Stack:** Python 3.11, Pillow, PyTorch 2.13, Torchvision 0.28, timm 1.0.28, DINOv3 0.0.1, NumPy, Pydantic, pytest.

## Global Constraints

- The visual original image is `ImageOps.exif_transpose(image).convert("RGB")`; its pixel coordinates are the only default output coordinates.
- Detector model-space normalization, letterboxing, and perspective transforms return boxes to the visual frame; EXIF orientation is not reversed in ordinary results.
- The in-progress ConvNeXt-Tiny Verifier must accept and return only canonical visual-frame boxes; before it is integrated, its branch must add the same orientation-six contract test. This plan does not overwrite that separate worktree.
- All online and offline consumers fail closed if a box is outside canonical visual dimensions.
- RepViT direct confirmation never loads or runs DINO local/global scoring.
- DINO global scoring retains the existing 5%, 10%, 15% padded crops and exactly 20 global SKU prototypes.
- Local scoring evaluates exactly five deterministic global candidates, uses only verified-product patch centers, and never upgrades a missing/invalid local artifact to a SKU.
- All local bank, DINO, RepViT, preprocessing, canonical-frame, evidence, calibration, and result provenance is hash-bound.
- Batch1 is development only and Batch2 is locked only; neither result may be reported as a release pass unless all source/capture-group/coverage gates pass.
- Do not claim 100% accuracy or full-pipeline latency without a valid calibration, canonical DINO source manifest, and independent locked report.
- Preserve unrelated Detector/Verifier work and do not stage `datasets/` or `models/` junctions.

---

## File Map

```text
src/bakery_scanner/data/preprocess.py
    CanonicalImage adapter, EXIF orientation provenance, visual-frame validation
src/bakery_scanner/detectors/dfine.py
    D-FINE visual-frame input/output boundary
src/bakery_scanner/classification/{config,contracts,preprocess,runtime,dinov3,policy,evidence}.py
    canonical classifier inputs, patch-bank validation/scoring, rerank policy/provenance
configs/classifier_policy.yaml
    canonical-frame and local patch-bank artifact identity
scripts/{collect_classifier_evidence,calibrate_classifier_policy,evaluate_classifier_policy,benchmark_classifier_pipeline}.py
    canonical input enforcement and global/local evidence/reporting
scripts/build_dinov3_local_patch_bank.py
    deterministic local support-bank builder
tests/{test_preprocess,test_dfine}.py
tests/classification/{test_config,test_preprocess,test_dinov3,test_policy,test_runtime,test_evidence,test_benchmark,test_local_bank}.py
    contracts, numerical scoring, leakage, evaluation, and latency regression coverage
README.md
docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md
    executable workflow and superseded global-only wording
```

### Task 1: Canonical Visual Image Contract

**Files:**
- Modify: `src/bakery_scanner/data/preprocess.py`
- Modify: `tests/test_preprocess.py`
- Create: `tests/data/test_canonical_image.py`

**Interfaces:**
- Produces `CanonicalImage(image: Image.Image, visual_size: tuple[int, int], raw_size: tuple[int, int], exif_orientation: int, frame_version: str)`.
- Produces `canonicalize_image(image: Image.Image) -> CanonicalImage` and `load_canonical_image(path: Path) -> CanonicalImage`.
- Produces `CanonicalImage.require_box(box: Box) -> None`.

- [ ] **Step 1: Write EXIF orientation tests**

```python
def test_canonicalize_transposes_orientation_six_and_preserves_visual_box():
    encoded = exif_oriented_jpeg(size=(40, 20), orientation=6)
    frame = canonicalize_image(Image.open(encoded))
    assert frame.visual_size == (20, 40)
    frame.require_box(Box(1, 2, 10, 20))
    with pytest.raises(ValueError, match="canonical visual"):
        frame.require_box(Box(15, 2, 10, 20))
```

Also test identity orientation, malformed/missing EXIF identity fallback, RGB conversion, immutable provenance, and exact raw-to-visual transform metadata.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python -m pytest tests/data/test_canonical_image.py -q`

Expected: FAIL because `CanonicalImage` and `canonicalize_image` do not exist.

- [ ] **Step 3: Implement the adapter without changing letterbox behavior**

```python
@dataclass(frozen=True, slots=True)
class CanonicalImage:
    image: Image.Image
    visual_size: tuple[int, int]
    raw_size: tuple[int, int]
    exif_orientation: int
    frame_version: Literal["exif_visual_rgb_v1"]

def canonicalize_image(image: Image.Image) -> CanonicalImage:
    raw_size = image.size
    orientation = int(image.getexif().get(274, 1))
    visual = ImageOps.exif_transpose(image).convert("RGB")
    return CanonicalImage(visual, visual.size, raw_size, orientation, "exif_visual_rgb_v1")
```

Keep `normalize_capture()` as the model-space letterbox helper, but require callers to pass `CanonicalImage.image`; it must not apply EXIF a second time.

- [ ] **Step 4: Run canonical-frame tests**

Run: `python -m pytest tests/data/test_canonical_image.py tests/test_preprocess.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/bakery_scanner/data/preprocess.py tests/data/test_canonical_image.py tests/test_preprocess.py
git commit -m "feat: define canonical visual image frame"
```

### Task 2: Apply the Canonical Frame at Detector and Classifier Boundaries

**Files:**
- Modify: `src/bakery_scanner/detectors/dfine.py`
- Modify: `src/bakery_scanner/classification/{runtime,preprocess,evidence}.py`
- Modify: `scripts/{collect_classifier_evidence,benchmark_classifier_pipeline}.py`
- Modify: `tests/test_dfine.py`
- Modify: `tests/classification/{test_preprocess,test_runtime,test_evidence,test_benchmark}.py`

**Interfaces:**
- Consumes `CanonicalImage` from Task 1.
- `DFineRunner.predict()` receives a materialized canonical-RGB input and parses boxes against `frame.visual_size`, never raw encoded dimensions.
- `ClassifierPipeline.infer(frame: CanonicalImage, box: Box) -> ClassificationDecision` replaces raw-image entry points.
- Evidence and benchmark image loaders return `(CanonicalImage, Box)` and reject dimensions that differ from manifest dimensions.

- [ ] **Step 1: Write failing end-to-end orientation tests**

```python
def test_runtime_crops_visual_frame_not_raw_jpeg_frame():
    frame = canonical_frame_with_orientation_six()
    result = pipeline().infer(frame, Box(1, 2, 10, 20))
    assert result.box == Box(1, 2, 10, 20)
    assert result.provenance.canonical_frame_version == "exif_visual_rgb_v1"
```

Add a D-FINE runner test that sends an orientation-six image through the materialization boundary and confirms its parsed result uses `(20, 40)`, not raw `(40, 20)`. Add evidence and benchmark tests where declared COCO/manifest dimensions equal the visual size and fail when they equal only raw JPEG size.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m pytest tests/classification/test_runtime.py tests/classification/test_evidence.py tests/classification/test_benchmark.py -q`

Expected: FAIL because raw `PIL.Image` entry points remain accepted.

- [ ] **Step 3: Replace raw image entry points atomically**

Require canonical frames at production entry points. Materialize one EXIF-transposed RGB image for D-FINE model input (temporary file lifecycle is owned by the inference entry point) and parse its boxes with the canonical visual size. Update crop helpers to accept `CanonicalImage` or `(visual_image, visual_size)` only, call `frame.require_box(box)` before crops, and set `canonical_frame_version` plus EXIF orientation in `ModelProvenance`. No code may call `Image.open()` and pass its result straight into D-FINE or classifier inference.

When the Verifier branch is integrated, its producer/consumer test must prove that a D-FINE proposal and the verifier's accepted box retain identical canonical coordinates. Treat absence of that test as an integration blocker, not as permission to add a raw-coordinate conversion.

- [ ] **Step 4: Reproduce the Batch1/Batch2 correction as a regression**

Add a guarded integration test that loads one EXIF-oriented Batch1 annotation, applies its visual-frame COCO box, and asserts the same crop bytes as the corresponding visually oriented reference. Do not assert a model accuracy percentage in a unit test.

- [ ] **Step 5: Run classifier boundary tests**

Run: `python -m pytest tests/test_dfine.py tests/classification/test_preprocess.py tests/classification/test_runtime.py tests/classification/test_evidence.py tests/classification/test_benchmark.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/bakery_scanner/detectors/dfine.py src/bakery_scanner/classification scripts/collect_classifier_evidence.py scripts/benchmark_classifier_pipeline.py tests/test_dfine.py tests/classification
git commit -m "feat: enforce visual coordinates at model boundaries"
```

### Task 3: Versioned DINO Local Patch-Bank Artifact

**Files:**
- Modify: `src/bakery_scanner/classification/config.py`
- Modify: `src/bakery_scanner/classification/dinov3.py`
- Create: `src/bakery_scanner/classification/local_bank.py`
- Create: `scripts/build_dinov3_local_patch_bank.py`
- Create: `tests/classification/test_local_bank.py`
- Modify: `configs/classifier_policy.yaml`

**Interfaces:**
- Produces `LocalPatchBank.load(path: Path, config: ClassifierConfig) -> LocalPatchBank`.
- Produces `LocalPatchBank.score(candidate_sku_ids: tuple[int, ...], patch_tokens: Tensor, patch_mask: Tensor) -> dict[int, float]`.
- Adds `dinov3.local_bank` and `local_bank_sha256` to strict configuration.

- [ ] **Step 1: Write failing artifact tests**

```python
def test_local_bank_rejects_wrong_dino_or_preprocess_hash(tmp_path):
    payload = valid_local_bank_payload(dino_weights_sha256="0" * 64)
    with pytest.raises(ValueError, match="DINO weights"):
        LocalPatchBank.load(write_bank(tmp_path, payload), config())
```

Also test canonical JSON, exact 20-SKU class map, normalized finite `(N, 384)` patch tensors, nonempty per-SKU banks, source hashes, and bank SHA mismatch.

- [ ] **Step 2: Run test and confirm failure**

Run: `python -m pytest tests/classification/test_local_bank.py -q`

Expected: FAIL because local-bank code and config do not exist.

- [ ] **Step 3: Implement deterministic bank construction**

The builder reads canonical source-manifest entries, canonicalizes each image, creates its verified product mask, extracts `x_norm_patchtokens` from `forward_features()`, retains centers inside the product mask, L2-normalizes, and writes canonical metadata plus tensors by atomic replacement. Its artifact metadata must include DINO weights/global-support/preprocess/canonical-frame hashes, class map, source-manifest hash, per-SKU count, and tensor hash.

- [ ] **Step 4: Add a CPU fake-encoder numerical test and artifact schema test**

```python
def test_patch_centers_exclude_padding_and_background():
    centers = patch_centers(grid_height=14, grid_width=14, input_size=224)
    mask = product_patch_mask(Box(28, 28, 168, 168), centers)
    assert int(mask.sum()) == 100
```

- [ ] **Step 5: Run local-bank tests**

Run: `python -m pytest tests/classification/test_local_bank.py tests/classification/test_dinov3.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add configs/classifier_policy.yaml src/bakery_scanner/classification/{config,dinov3,local_bank}.py scripts/build_dinov3_local_patch_bank.py tests/classification/test_local_bank.py tests/classification/test_dinov3.py
git commit -m "feat: add versioned DINO local patch bank"
```

### Task 4: Candidate-Conditioned Local DINO Scoring

**Files:**
- Modify: `src/bakery_scanner/classification/dinov3.py`
- Modify: `src/bakery_scanner/classification/contracts.py`
- Create: `tests/classification/test_local_rerank.py`

**Interfaces:**
- Produces `DinoLocalScores(candidate_sku_ids: tuple[int, ...], values: tuple[float, ...], matched_patch_count: int)`.
- Produces `DinoV3Rechecker.score_global_and_local(crops, product_boxes_224, candidate_sku_ids) -> tuple[ModelScoreVector, DinoLocalScores]`.

- [ ] **Step 1: Write numerical rerank-input tests**

```python
def test_local_score_uses_only_product_masked_query_tokens():
    scores = bank.score((6,), tokens_with_one_background_decoy, product_mask)
    assert scores[6] == pytest.approx(expected_product_only_score)
```

Test deterministic Top-5 candidate order, non-finite token rejection, zero selected patches, missing bank, exact tie ordering, and that the runner never evaluates SKU 6 when it is not in global Top-5.

- [ ] **Step 2: Run test and confirm failure**

Run: `python -m pytest tests/classification/test_local_rerank.py -q`

Expected: FAIL because global/local combined scoring does not exist.

- [ ] **Step 3: Implement global retrieval then local scoring**

Use DINO `forward_features()` once for the three crop tensors. Compute current global score from `x_norm_clstoken`; compute patch tokens from `x_norm_patchtokens`; generate 224-space masks from the canonical verified product rectangle in each crop; rank global scores by `(-score, sku_id)` and pass exactly five IDs into `LocalPatchBank.score`.

- [ ] **Step 4: Run local scoring tests**

Run: `python -m pytest tests/classification/test_local_rerank.py tests/classification/test_dinov3.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/bakery_scanner/classification/{contracts,dinov3}.py tests/classification/test_local_rerank.py tests/classification/test_dinov3.py
git commit -m "feat: score DINO local candidate patches"
```

### Task 5: Calibrated Global/Local Fusion and Safe Unknown Policy

**Files:**
- Modify: `src/bakery_scanner/classification/{policy,contracts,evidence,runtime}.py`
- Modify: `tests/classification/{test_policy,test_evidence,test_runtime}.py`

**Interfaces:**
- `PolicyCalibration` adds `local_bank_artifact_id`, `local_bank_sha256`, `global_temperature`, `local_temperature`, `local_beta`, `local_threshold`, and `rerank_margin`.
- `DecisionPolicy.after_local_recheck(repvit, global_dino, local_dino, box) -> ClassificationDecision`.

- [ ] **Step 1: Write failing safety-policy tests**

```python
def test_local_rerank_cannot_confirm_when_repvit_global_local_disagree():
    result = policy.after_local_recheck(repvit_for(6), global_for(6), local_for(5), BOX)
    assert result.decision == "unknown"
    assert [row.sku_id for row in result.top3] == [6, 5, 19]
```

Also test global/local candidate union, candidate-only softmax normalization, calibration hash mismatch, local failure fallback, equality thresholds, and deterministic ties.

- [ ] **Step 2: Run test and confirm failure**

Run: `python -m pytest tests/classification/test_policy.py tests/classification/test_runtime.py -q`

Expected: FAIL because local calibration and policy paths do not exist.

- [ ] **Step 3: Implement calibrated candidate-only fusion**

For the deterministic union of global Top-5 and local Top-5, calculate float64 softmax distributions after their individual temperatures and combine only those IDs:

```python
logit = beta * log(global_probability) + (1.0 - beta) * log(local_probability)
```

Require RepViT/global/reranked Top-1 agreement plus configured confidence and margin gates for SKU confirmation. Every other outcome, local failure, or provenance mismatch returns `Unknown` with three unique reranked candidates.

- [ ] **Step 4: Wire lazy runtime behavior**

Only after `policy.direct()` abstains: load DINO and local bank, score global Top-5 then local candidates, record local elapsed time and invocation state in canonical provenance. Catch explicit local artifact/inference failures only as `Unknown`; do not swallow programming or configuration errors.

- [ ] **Step 5: Run policy/runtime tests**

Run: `python -m pytest tests/classification/test_policy.py tests/classification/test_runtime.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/bakery_scanner/classification/{contracts,evidence,policy,runtime}.py tests/classification/test_policy.py tests/classification/test_evidence.py tests/classification/test_runtime.py
git commit -m "feat: fuse DINO global and local recheck"
```

### Task 6: Evidence Selection, Batch Evaluation, Benchmark, and Documentation

**Files:**
- Modify: `scripts/{collect_classifier_evidence,calibrate_classifier_policy,evaluate_classifier_policy,benchmark_classifier_pipeline}.py`
- Modify: `src/bakery_scanner/classification/evidence.py`
- Modify: `tests/classification/{test_evidence,test_benchmark}.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md`

**Interfaces:**
- Evidence rows add canonical-frame version, orientation provenance, DINO global vector, local candidate IDs/scores, local-bank hash, and source image hash.
- Benchmark reports direct, global-only recheck, and global+local recheck counts plus p50/p95.

- [ ] **Step 1: Write failing evidence/benchmark tests**

```python
def test_batch2_locked_report_rejects_raw_orientation_dimensions(tmp_path):
    manifest = locked_manifest_with_raw_jpeg_size_only(tmp_path)
    assert run_evaluator(manifest) == 2

def test_benchmark_separates_global_and_local_recheck_latency():
    report = aggregate_benchmark([direct(), global_only(), global_local()])
    assert report.global_local_recheck.image_count == 1
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/classification/test_evidence.py tests/classification/test_benchmark.py -q`

Expected: FAIL because canonical/local fields and path categories do not exist.

- [ ] **Step 3: Implement development-only local parameter selection**

Search deterministic temperature, beta, local threshold, and rerank-margin candidates using only grouped development evidence. Candidate selection must minimize automatic errors, then Top-3 misses, then assisted failures, then maximize safe confirmations. Locked evaluation reads the fixed artifact exactly once and reports global-only versus global+local metrics without selecting parameters.

- [ ] **Step 4: Add Batch1/Batch2 command contracts**

Document Batch1 as development and Batch2 as locked only. Every command must receive canonical source manifest, local-bank artifact, coverage contract, and EXIF-aware manifest dimensions. A missing/mismatched DINO source manifest or local bank fails before writing evidence/calibration/report.

- [ ] **Step 5: Run complete verification**

Run:

```powershell
python -m pytest tests/classification -q
python -m pytest tests/test_contracts.py tests/test_config.py tests/test_preprocess.py -q
python -m pytest tests/classification/test_repvit.py tests/classification/test_dinov3.py -m integration -q
python scripts/build_dinov3_local_patch_bank.py --help
python scripts/collect_classifier_evidence.py --help
python scripts/calibrate_classifier_policy.py --help
python scripts/evaluate_classifier_policy.py --help
python scripts/benchmark_classifier_pipeline.py --help
git diff --check
```

Expected: all code tests and help commands pass. If canonical DINO source manifest, independent Batch1/Batch2 manifests, local bank, or calibration artifact are unavailable, record release metrics and latency as blocked; do not invent values.

- [ ] **Step 6: Commit**

```powershell
git add scripts src/bakery_scanner/classification/evidence.py tests/classification README.md docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md
git commit -m "docs: evaluate local DINO rerank workflow"
```
