# RTX 5080 15+5 Single-Frame Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Build the approved single-frame 15+5 RTX 5080 pipeline with grouped OOF evidence, fail-closed rearrangement and Unknown behavior, and a hard warmed p95 100ms acceptance gate for every valid runtime path.

**Architecture:** Keep the canonical CPU and legacy paths untouched. Add a versioned GPU candidate that uses a class-agnostic RF-DETR-L detector, an independent scene-completeness Gate, batched RepViT direct approval, conditional single-pass DINOv3 global/local evidence, and immutable fusion. Build fold-specific FP32 references first, then export static ONNX graphs and hash-bound TensorRT FP16 engines; the final train-all artifact remains development-complete / production-unverified.

**Tech Stack:** Python 3.11, pytest 9, NumPy 2.4, Pillow 12.2, OpenCV 5, scikit-learn 1.9, PyTorch 2.13 CUDA 13 runtime, RF-DETR 1.8.3-compatible local API, externally provisioned ONNX and TensorRT runtime, RTX 5080, Flutter/Dart strict protocol consumers.

## Global Constraints

- Use only the current datasets tree as labeled image evidence: 299 mixed scenes, 1,406 boxes, 15 base classes with 84 isolated images each, and 5 incremental classes with 5 isolated images each.
- Keep SKU IDs 1 through 20 in canonical order; preserve the existing 15+5 catalog identity.
- Use grouped 5-fold OOF with three training folds, one calibration fold, and one evaluation fold per rotation; evaluation images and crops never enter training, support, threshold, or policy selection.
- Apply EXIF transpose and RGB conversion before every model; all boxes are finite in-bounds canonical xyxy.
- Do not modify configs/pipelines/canonical_cpu.yaml, portable_cpu_smoke, or legacy behavior.
- New code lives under bakery_scanner.data, bakery_scanner.detection, bakery_scanner.classification, bakery_scanner.pipelines, bakery_scanner.benchmarking, and responsibility-oriented tools directories.
- Every positive final object count is eligible for accepted_scan; zero targets return needs_retake with no_target_detected. Current 3--7 counts are quality-evidence only.
- RepViT batch 14 and DINO batch 7 are static invocation capacities: deterministically chunk all positive counts in original order, pad only the final chunk, ignore padded rows, concatenate evidence, and abort the whole scan on any chunk failure.
- Never emit partial objects for a needs_retake scan.
- RepViT direct approval requires the immutable calibrated class-wise Gate. Only direct rejections run DINOv3.
- Fusion accepts only when the ranked SKU equals local Top-1, or both model global Top-1 values equal it and fusion margin is at least 0.85; every other object is Unknown.
- Unknown is excluded from SKU totals and carries exactly three unique ranked active-catalog candidates.
- The 100ms boundary starts with encoded JPEG bytes already in worker memory and ends with a validated in-memory result payload; decode is included and file I/O, acquisition, UI, engine build, initial load, and warm-up are excluded.
- E, M, H, overall, DINO, needs_retake, Unknown, count_1_2, count_3_7, and count_8_plus slices each require warmed p95 at or below 100ms; the outer count slices are performance-only until independent quality evidence exists.
- TensorRT/ONNX packages and engines are external artifacts. The current bundled runtime reports tensorrt, torch_tensorrt, and onnx unavailable; engine work must fail closed until an external runtime manifest with byte sizes and SHA-256 passes admission.
- No silent PyTorch, CPU, lower-resolution, smaller-detector, or lower-precision fallback is allowed.
- Dataset payloads, checkpoints, ONNX files, TensorRT engines, support banks, and raw receipts stay outside Git. Git stores manifests, split identities, policies, compact summaries, source, configs, and tests.
- Skipped artifact, GPU, package, or performance suites are unverified, never passed.
- Commit messages use Korean type(scope): description format and each task ends in one focused commit.

---

## File Structure

- configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml: immutable candidate composition and runtime limits.
- configs/evaluation/rtx5080_15plus5_oof_v1.yaml: grouped OOF, utility, quality, and p95 acceptance contract.
- data/splits/rtx5080_15plus5_oof_v1/: five compact fold manifests and one inventory identity.
- src/bakery_scanner/data/sku_scene.py: strict 20-class scene inventory without losing COCO SKU labels.
- src/bakery_scanner/data/oof15plus5.py: group identity, duplicate audit, fold roles, and manifest serialization.
- src/bakery_scanner/pipelines/rtx5080_15plus5/contracts.py: scan, object, location, confidence, retake, timing, and deterministic JSON contracts.
- src/bakery_scanner/pipelines/rtx5080_15plus5/config.py: strict YAML loader for pipeline and runtime profile.
- src/bakery_scanner/pipelines/rtx5080_15plus5/admission.py: artifact, engine, runtime, binding, and compatibility verification.
- src/bakery_scanner/pipelines/rtx5080_15plus5/runtime.py: decode-to-payload orchestration with no legacy fallback.
- src/bakery_scanner/detection/completeness.py: pure completeness evidence and retake decision.
- src/bakery_scanner/detection/rfdetr_trt.py: class-agnostic detector TensorRT adapter.
- src/bakery_scanner/classification/trt.py: static RepViT/DINO TensorRT adapters and padded batch masks.
- src/bakery_scanner/benchmarking/oof15plus5.py: quality, utility, Top3, counterfactual, and confidence-bound receipts.
- src/bakery_scanner/benchmarking/rtx5080_acceptance.py: schema-v3 path-aware p95 receipt and hard Gate.
- tools/data/build_rtx5080_15plus5_oof.py: operational inventory and split builder.
- tools/train/train_rfdetr_bread_oof.py: five class-agnostic detector folds and final train-all run.
- tools/train/train_repvit_15plus5_oof.py: five classifier folds and final train-all run.
- tools/train/build_dinov3_15plus5_oof.py: fold-safe global/local support builders.
- tools/train/calibrate_rtx5080_15plus5.py: fold-specific direct and fusion policy calibration.
- tools/package/export_rtx5080_15plus5_onnx.py: static ONNX export.
- tools/package/build_rtx5080_15plus5_engines.py: hash-bound trtexec engine build.
- tools/evaluate/run_rtx5080_15plus5_oof.py: fold OOF execution and compact quality receipt.
- tools/benchmark/run_rtx5080_15plus5.py: warmed path-aware RTX 5080 benchmark.
- Focused tests mirror every first-party module and producer/consumer boundary.

## Task 1: Immutable 15+5 Inventory and Grouped OOF Splits

**Files:**
- Create: src/bakery_scanner/data/sku_scene.py
- Create: src/bakery_scanner/data/oof15plus5.py
- Create: tools/data/build_rtx5080_15plus5_oof.py
- Create: tests/data/test_sku_scene.py
- Create: tests/data/test_oof15plus5.py
- Create: data/splits/rtx5080_15plus5_oof_v1/inventory.json
- Create: data/splits/rtx5080_15plus5_oof_v1/fold-0.json through fold-4.json

**Interfaces:**
- Consumes: Path datasets with classifier/base, classifier/incremental, and the three COCO sources.
- Produces: load_inventory(root: Path) -> SkuSceneInventory; build_oof_folds(inventory: SkuSceneInventory, seed: int = 20260803) -> tuple[OofFold, ...]; write_oof_manifests(folds, inventory, output) -> None.

- [ ] **Step 1: Write failing inventory tests**

~~~python
def test_inventory_preserves_twenty_sku_labels(dataset_fixture):
    inventory = load_inventory(dataset_fixture)
    assert inventory.scene_count == 299
    assert inventory.box_count == 1406
    assert inventory.difficulty_counts == {"E": 100, "M": 99, "H": 100}
    assert inventory.isolated_counts[4] == 5
    assert inventory.isolated_counts[1] == 84
    assert {box.sku_id for scene in inventory.scenes for box in scene.boxes} == set(range(1, 21))


def test_inventory_rejects_coco_box_outside_declared_image(tmp_path):
    root = build_dataset_fixture(tmp_path, bbox=[10, 10, 9999, 10])
    with pytest.raises(ValueError, match="canonical image bounds"):
        load_inventory(root)
~~~

- [ ] **Step 2: Run the inventory tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/data/test_sku_scene.py -q

Expected: FAIL during import because bakery_scanner.data.sku_scene does not exist.

- [ ] **Step 3: Implement strict inventory records**

~~~python
@dataclass(frozen=True, slots=True)
class SkuBox:
    sku_id: int
    box_xywh: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class SourceImage:
    sku_id: int
    identity: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class SceneRecord:
    scene_id: str
    source_name: str
    file_name: str
    difficulty: Literal["E", "M", "H"]
    capture_number: int
    width: int
    height: int
    image_sha256: str
    boxes: tuple[SkuBox, ...]


@dataclass(frozen=True, slots=True)
class SkuSceneInventory:
    scenes: tuple[SceneRecord, ...]
    isolated_by_sku: Mapping[int, tuple[SourceImage, ...]]
    source_sha256: str


@dataclass(frozen=True, slots=True)
class OofFold:
    fold_index: int
    training_scene_ids: tuple[str, ...]
    calibration_scene_ids: tuple[str, ...]
    evaluation_scene_ids: tuple[str, ...]
    group_roles: Mapping[str, Literal["train", "calibration", "evaluation"]]
    manifest_sha256: str
~~~

load_inventory validates exact class maps, unique identities, finite positive xywh, image bounds, on-disk dimensions after EXIF transpose, lowercase SHA-256, and the exact expected counts. It reads but never copies or rewrites dataset images.

- [ ] **Step 4: Write failing group and role tests**

~~~python
def test_same_batch_capture_number_never_crosses_fold(inventory):
    folds = build_oof_folds(inventory, seed=20260803)
    for fold in folds:
        roles = fold.group_roles
        assert len(roles) == len(set(roles))
        assert set(roles.values()) == {"train", "calibration", "evaluation"}


def test_every_scene_is_evaluated_exactly_once(inventory):
    folds = build_oof_folds(inventory, seed=20260803)
    evaluated = [scene_id for fold in folds for scene_id in fold.evaluation_scene_ids]
    assert sorted(evaluated) == sorted(scene.scene_id for scene in inventory.scenes)
~~~

- [ ] **Step 5: Implement conservative grouping and five rotations**

Use group ID source_name:capture_number. Compute a deterministic 64-bit dHash from EXIF-transposed grayscale 9x8 pixels. Union groups in the same source when Hamming distance is at most 4, then stratify group-level SKU presence, E/M/H, object-count bin, and image shape. For fold index n, evaluation is split n, calibration is split (n + 1) modulo 5, and the remaining three splits are training.

- [ ] **Step 6: Add deterministic manifest serialization**

Each manifest includes schema_version 1, seed 20260803, source_sha256, scene IDs by role, group IDs by role, SKU counts by role, difficulty counts by role, and its own canonical payload SHA-256. Refuse to replace an existing output directory unless its bytes are exactly identical.

- [ ] **Step 7: Run focused tests and generate reviewed manifests**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/data/test_sku_scene.py tests/data/test_oof15plus5.py -q

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python tools/data/build_rtx5080_15plus5_oof.py --dataset-root datasets --output data/splits/rtx5080_15plus5_oof_v1

Expected: tests pass; command reports 299 scenes, 1,406 boxes, 20 SKUs, and five disjoint role manifests.

- [ ] **Step 8: Commit the inventory and split identities**

~~~powershell
git add src/bakery_scanner/data/sku_scene.py src/bakery_scanner/data/oof15plus5.py tools/data/build_rtx5080_15plus5_oof.py tests/data/test_sku_scene.py tests/data/test_oof15plus5.py data/splits/rtx5080_15plus5_oof_v1
git commit -m "feat(data): 15+5 OOF 분할 계약 추가"
~~~

## Task 2: Candidate Config, Result Contracts, and Admission

**Files:**
- Create: configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml
- Create: configs/evaluation/rtx5080_15plus5_oof_v1.yaml
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/__init__.py
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/contracts.py
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/config.py
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/admission.py
- Create: tests/pipelines/rtx5080_15plus5/test_contracts.py
- Create: tests/pipelines/rtx5080_15plus5/test_config.py
- Create: tests/pipelines/rtx5080_15plus5/test_admission.py

**Interfaces:**
- Produces: ScanResult.to_json_bytes(), load_candidate_config(path: Path) -> CandidateConfig, admit_candidate(config, content_root, runtime_identity) -> AdmissionReceipt.
- Consumes: exact artifact paths, sizes, SHA-256, TensorRT binding schemas, active catalog, and runtime identity.

- [ ] **Step 1: Write failing result-contract tests**

~~~python
def test_unknown_is_excluded_from_sku_totals():
    result = accepted_scan(objects=(registered_object(15), unknown_object((4, 6, 9))))
    assert result.object_total == 2
    assert result.registered_object_total == 1
    assert result.unknown_total == 1
    assert result.sku_totals == {15: 1}


def test_needs_retake_forbids_partial_objects():
    with pytest.raises(ValueError, match="must not contain final objects"):
        ScanResult.needs_retake(
            scan_id="scan-1",
            retake_chain_id="chain-1",
            attempt=1,
            reasons=(RetakeReason.UNCOVERED_FOREGROUND,),
            problem_regions=(),
            objects=(registered_object(1),),
        )
~~~

- [ ] **Step 2: Run contract tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/pipelines/rtx5080_15plus5/test_contracts.py -q

Expected: FAIL because the candidate package is absent.

- [ ] **Step 3: Implement immutable public contracts**

~~~python
class ScanState(str, Enum):
    ACCEPTED = "accepted_scan"
    NEEDS_RETAKE = "needs_retake"
    ADMISSION_FAILED = "admission_failed"


class DecisionPath(str, Enum):
    DIRECT = "direct_approved"
    CONSENSUS = "consensus_approved"
    UNKNOWN = "unknown_top3"


class RetakeReason(str, Enum):
    NO_TARGET_DETECTED = "no_target_detected"
    UNCOVERED_FOREGROUND = "uncovered_foreground"
    OVERLAP_OR_OCCLUSION = "overlap_or_occlusion"
    POSSIBLE_SPLIT = "possible_split"
    POSSIBLE_MERGE = "possible_merge"
    TRUNCATED_OBJECT = "truncated_object"
    CAPTURE_QUALITY_UNVERIFIED = "capture_quality_unverified"
    COMPLETENESS_RISK_EXCEEDED = "completeness_risk_exceeded"


@dataclass(frozen=True, slots=True)
class ObjectLocation:
    box_xyxy: tuple[float, float, float, float]
    center_normalized: tuple[float, float]
    object_order: int


@dataclass(frozen=True, slots=True)
class CandidateConfidence:
    detector_calibrated: float
    sku_acceptance_calibrated: float | None
    fusion_margin: float | None


@dataclass(frozen=True, slots=True)
class FinalObject:
    object_id: str
    sku_id: int | None
    sku_name: str
    decision_path: DecisionPath
    location: ObjectLocation
    confidence: CandidateConfidence
    top3: tuple[SkuCandidate, ...]
    provenance: ObjectProvenance


@dataclass(frozen=True, slots=True)
class StageTimings:
    decode_canonical: float
    detector: float
    completeness: float
    crop: float
    repvit: float
    direct_gate: float
    dinov3: float
    fusion_payload: float
    total: float


@dataclass(frozen=True, slots=True)
class ScanProvenance:
    pipeline_id: str
    runtime_profile_id: str
    admission_receipt_sha256: str
    artifact_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ScanResult:
    scan_id: str
    retake_chain_id: str
    state: ScanState
    objects: tuple[FinalObject, ...]
    reasons: tuple[RetakeReason, ...]
    timings_ms: StageTimings
    provenance: ScanProvenance
    manual_catalog_required: bool

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            scan_result_payload(self),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
~~~

Define SkuCandidate and ObjectProvenance in the same module with strict rank,
SKU, score, artifact-ID, and SHA-256 validation. Use sorted compact JSON with
allow_nan=False. Object order is lexicographic center_y_norm, center_x_norm,
x_min, y_min. Unknown requires sku_id None, sku_name Unknown, null SKU
acceptance confidence, and exact ranked Top3. manual_catalog_required is true
only for needs_retake attempt 3 and later. Implement
scan_result_payload(result: ScanResult) -> dict[str, object] in the same module;
it emits every declared field, derives counts from objects, and validates the
payload before returning it.

- [ ] **Step 4: Write failing config and admission tests**

~~~python
def test_config_requires_static_chunk_capacities_and_hard_p95(candidate_config):
    assert candidate_config.runtime.repvit_chunk_capacity_objects == 7
    assert candidate_config.runtime.dinov3_chunk_capacity_objects == 7
    assert candidate_config.runtime.p95_limit_ms == 100.0
    assert candidate_config.runtime.precision == "FP16"
    assert candidate_config.runtime.stage_budgets_ms == {
        "decode_canonical": 10.0,
        "detector": 36.0,
        "completeness": 6.0,
        "crop": 4.0,
        "repvit": 12.0,
        "direct_gate": 2.0,
        "dinov3": 18.0,
        "fusion_payload": 6.0,
        "headroom": 8.0,
    }


def test_admission_rejects_engine_hash_mismatch(candidate_root, runtime_identity):
    replace_bytes(candidate_root / "engines" / "rfdetr.engine")
    with pytest.raises(AdmissionError, match="SHA-256 mismatch"):
        admit_candidate(load_candidate_config(CONFIG), candidate_root, runtime_identity)
~~~

- [ ] **Step 5: Add strict config and evaluation artifacts**

The pipeline YAML fixes pipeline_id rtx5080_15plus5_single_frame_v1, device CUDA:0, precision FP16, seven-object RepViT/DINO chunk capacities, RepViT batch 14 (tight/context pairs), DINO batch 7, fusion margin 0.85, p95 limit 100.0, and the exact stage budgets asserted above. The evaluation YAML fixes IoU 0.50, seed 20260803, five folds, 3/1/1 roles, the utility floors from the spec, seven path slices, and count_1_2/count_3_7/count_8_plus latency slices.

- [ ] **Step 6: Implement fail-closed admission**

~~~python
@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    device: Literal["cuda:0"]
    gpu_name: Literal["NVIDIA GeForce RTX 5080"]
    compute_capability: str
    driver_version: str
    cuda_version: str
    tensorrt_version: str


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    pipeline_id: str
    artifacts: tuple[VerifiedArtifact, ...]
    runtime: RuntimeIdentity
    admitted: Literal[True]


def admit_candidate(
    config: CandidateConfig,
    content_root: Path,
    runtime: RuntimeIdentity,
) -> AdmissionReceipt:
    verified = tuple(verify_declared_artifact(content_root, item) for item in config.artifacts)
    require_runtime_match(config.runtime, runtime)
    require_exact_bindings(config.engines, inspect_engine_bindings(runtime))
    return AdmissionReceipt(config.pipeline_id, verified, runtime, admitted=True)
~~~

Admission binds model, ONNX, engine, preprocessing, support, policy, catalog, driver, CUDA, TensorRT, compute capability, dtype, shape, and binding semantics. Any mismatch raises AdmissionError and never constructs a runtime.

- [ ] **Step 7: Run focused tests**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/pipelines/rtx5080_15plus5/test_contracts.py tests/pipelines/rtx5080_15plus5/test_config.py tests/pipelines/rtx5080_15plus5/test_admission.py -q

Expected: PASS.

- [ ] **Step 8: Commit candidate contracts**

~~~powershell
git add configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml configs/evaluation/rtx5080_15plus5_oof_v1.yaml src/bakery_scanner/pipelines/rtx5080_15plus5 tests/pipelines/rtx5080_15plus5
git commit -m "feat(pipeline): RTX 5080 후보 계약 추가"
~~~

## Task 3: Scene Completeness and Rearrangement Gate

**Files:**
- Create: src/bakery_scanner/detection/completeness.py
- Modify: src/bakery_scanner/detection/__init__.py
- Create: tests/detection/test_completeness.py
- Create: tests/detection/test_completeness_counterfactual.py

**Interfaces:**
- Consumes: canonical RGB dimensions, detector BreadProposal values, ForegroundEvidence, CaptureQuality, and CompletenessPolicy.
- Produces: evaluate_completeness(frame_size, proposals, foreground, quality, policy) -> CompletenessDecision and build_counterfactuals(gt_boxes) -> tuple[CounterfactualCase, ...].

- [ ] **Step 1: Write failing pure-decision tests**

~~~python
def test_uncovered_foreground_requires_retake():
    decision = evaluate_completeness(
        frame_size=(4284, 5712),
        proposals=THREE_VALID_BOXES,
        foreground=ForegroundEvidence(uncovered_ratio=0.08, problem_regions=((10, 10, 80, 80),)),
        quality=GOOD_QUALITY,
        policy=policy(max_uncovered_ratio=0.03),
    )
    assert decision.accepted is False
    assert decision.reasons == (RetakeReason.UNCOVERED_FOREGROUND,)


def test_zero_target_requires_retake():
    decision = evaluate_completeness(
        frame_size=(4284, 5712),
        proposals=(),
        foreground=FULLY_COVERED_FOREGROUND,
        quality=GOOD_QUALITY,
        policy=policy(),
    )
    assert decision.reasons == (RetakeReason.NO_TARGET_DETECTED,)
~~~

- [ ] **Step 2: Run completeness tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/detection/test_completeness.py -q

Expected: FAIL because bakery_scanner.detection.completeness does not exist.

- [ ] **Step 3: Implement evidence and policy types**

~~~python
@dataclass(frozen=True, slots=True)
class ForegroundEvidence:
    uncovered_ratio: float
    covered_ratio: float
    problem_regions: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class CompletenessPolicy:
    max_uncovered_ratio: float
    max_pair_iou: float
    border_margin_ratio: float
    min_blur_score: float
    exposure_range: tuple[float, float]


@dataclass(frozen=True, slots=True)
class CaptureQuality:
    blur_score: float
    exposure_score: float
    reflection_ratio: float


@dataclass(frozen=True, slots=True)
class CompletenessDecision:
    accepted: bool
    reasons: tuple[RetakeReason, ...]
    problem_regions: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class CounterfactualCase:
    evidence_kind: Literal["counterfactual"]
    fault: Literal["missing", "merge", "split", "truncation"]
    proposals: tuple[BreadProposal, ...]
~~~

evaluate_completeness returns all applicable reasons in fixed enum order. Invalid/non-finite detector boxes raise InvalidDetectorOutput instead of becoming a retake, because partial output from a malformed engine is a runtime failure.

- [ ] **Step 4: Implement foreground analysis as an injected boundary**

Define ForegroundAnalyzer.analyze(canonical_rgb, tray_roi, proposals) -> ForegroundEvidence. The reference analyzer uses fixed-resolution Lab distance from the calibrated tray background, morphology with manifest-bound kernel sizes, and box-union coverage. It can only produce evidence and problem regions; it cannot create detector boxes or SKU labels.

- [ ] **Step 5: Add counterfactual stress cases**

~~~python
def build_counterfactuals(boxes):
    return (
        *remove_each_box(boxes),
        *merge_each_overlapping_pair(boxes),
        *split_each_box(boxes),
        *move_each_box_across_tray_boundary(boxes),
    )
~~~

Tests assert every generated missing, merge, split, and truncation case is rejected by the calibrated fixture policy, and that counterfactual metrics carry evidence_kind="counterfactual" so they cannot be counted as observed detector misses.

- [ ] **Step 6: Run completeness and contract suites**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/detection/test_completeness.py tests/detection/test_completeness_counterfactual.py tests/test_pipeline_contract.py -q

Expected: PASS and canonical CPU contract remains unchanged.

- [ ] **Step 7: Commit completeness Gate**

~~~powershell
git add src/bakery_scanner/detection/completeness.py src/bakery_scanner/detection/__init__.py tests/detection
git commit -m "feat(detection): 장면 완전성 재배치 Gate 추가"
~~~

## Task 4: Class-Agnostic RF-DETR-L OOF Reference

**Files:**
- Create: tools/train/train_rfdetr_bread_oof.py
- Create: tools/evaluate/evaluate_rfdetr_bread_oof.py
- Create: tests/tools/test_train_rfdetr_bread_oof.py
- Create: tests/tools/test_evaluate_rfdetr_bread_oof.py
- Create: models/rfdetr_l_bread_gpu_fp16_v1/README.md

**Interfaces:**
- Consumes: split manifests from Task 1 and class-agnostic staged COCO produced by existing bakery_scanner.data.coco.
- Produces externally: fold checkpoints, predictions, calibration evidence, FP32 manifests, and final train-all checkpoint; Git receives only compact manifests and documentation after artifact generation.

- [ ] **Step 1: Write failing training-spec tests**

~~~python
def test_fold_training_uses_only_train_role(split_manifest, fake_model):
    run_fold_training(split_manifest, fold_index=2, model_factory=lambda: fake_model)
    assert fake_model.train_kwargs["dataset_dir"].endswith("fold-2/train")
    assert fake_model.train_kwargs["device"] == "cuda:0"
    assert fake_model.train_kwargs["num_classes"] == 1


def test_training_notes_bind_split_seed_and_source_hash(fake_model):
    notes = fake_model.train_kwargs["notes"]
    assert notes["fold_manifest_sha256"] == SPLIT_SHA
    assert notes["seed"] == 20260803
    assert notes["category_map"] == {"1": "bread"}
~~~

- [ ] **Step 2: Run tool tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_train_rfdetr_bread_oof.py -q

Expected: FAIL because the operational tool module does not exist.

- [ ] **Step 3: Implement fold-safe staging and training**

Use RFDETRLarge.train with device="cuda:0", a single bread category, deterministic seed 20260803 + fold index, output directory outside Git, and notes containing every source/split/config hash. The tool refuses an output directory that already contains a receipt and never deletes an existing run.

- [ ] **Step 4: Write failing deterministic detector-evaluation tests**

~~~python
def test_threshold_selection_uses_calibration_only():
    receipt = select_detector_policy(CAL_ROWS, EVAL_ROWS)
    assert receipt.selected_from_image_ids == tuple(sorted(CAL_IDS))
    assert not set(receipt.selected_from_image_ids) & set(EVAL_IDS)


def test_detector_receipt_reports_every_primary_error():
    metrics = evaluate_detector(GT, PREDICTIONS, iou_threshold=0.50)
    assert set(metrics.error_counts) == {"miss", "duplicate", "non_target", "split", "merge"}
~~~

- [ ] **Step 5: Implement calibration and evaluation**

Select score threshold on the calibration role by minimizing scan critical errors, then unnecessary retakes, then choosing the highest tied threshold. Evaluate the frozen threshold on the evaluation role using deterministic IoU 0.50 one-to-one matching. Non-target rejection remains unverified because no negative scenes exist.

- [ ] **Step 6: Run hermetic tests, then artifact-marked fold commands**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_train_rfdetr_bread_oof.py tests/tools/test_evaluate_rfdetr_bread_oof.py tests/test_rfdetr.py -q

Run once per fold with the bundled Python:

~~~powershell
artifacts/installer_payload/1.1.0-final4/runtime/python/python.exe tools/train/train_rfdetr_bread_oof.py --splits data/splits/rtx5080_15plus5_oof_v1 --fold all --output C:/bixolon-artifacts/bixolon_bakery_scanner/rfdetr_l_bread_oof_v1
~~~

Expected: five fold receipts identify disjoint train/calibration/evaluation scenes. If training dependencies are absent, record unverified_missing_rfdetr_train_runtime and do not fabricate fold results.

- [ ] **Step 7: Commit source and model documentation**

~~~powershell
git add tools/train/train_rfdetr_bread_oof.py tools/evaluate/evaluate_rfdetr_bread_oof.py tests/tools/test_train_rfdetr_bread_oof.py tests/tools/test_evaluate_rfdetr_bread_oof.py models/rfdetr_l_bread_gpu_fp16_v1/README.md
git commit -m "feat(detection): RF-DETR-L OOF 학습 도구 추가"
~~~

## Task 5: RepViT and DINO Fold-Safe 15+5 Evidence

**Files:**
- Create: tools/train/train_repvit_15plus5_oof.py
- Create: tools/train/build_dinov3_15plus5_oof.py
- Modify: src/bakery_scanner/classification/preprocess.py
- Modify: src/bakery_scanner/classification/runtime.py
- Create: tests/tools/test_train_repvit_15plus5_oof.py
- Create: tests/tools/test_build_dinov3_15plus5_oof.py
- Modify: tests/classification/test_preprocess.py
- Modify: tests/classification/test_runtime.py

**Interfaces:**
- Consumes: isolated images, training-role GT scene crops, fold split manifest, and existing RepViT/DINO architecture loaders.
- Produces: fold RepViT checkpoints, class-balanced prototype banks, DINO global/local support, and aligned tight/context batch evidence.

- [ ] **Step 1: Write failing source-isolation tests**

~~~python
def test_eval_scene_crop_never_enters_repvit_training(fold_sources):
    rows = build_repvit_sources(fold_sources, fold_index=0)
    assert not set(rows.scene_ids) & set(fold_sources.evaluation_scene_ids)
    assert not set(rows.scene_ids) & set(fold_sources.calibration_scene_ids)


def test_support_bank_uses_only_isolated_and_training_scene_crops(fold_sources):
    rows = build_dino_sources(fold_sources, fold_index=0)
    assert set(rows.source_roles) <= {"isolated", "train_scene"}
~~~

- [ ] **Step 2: Run tool tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_train_repvit_15plus5_oof.py tests/tools/test_build_dinov3_15plus5_oof.py -q

Expected: FAIL because the new tools do not exist.

- [ ] **Step 3: Add deterministic tight/context crops**

~~~python
@dataclass(frozen=True, slots=True)
class CropPair:
    tight: Image.Image
    context: Image.Image
    box: Box


def build_crop_pair(frame: CanonicalImage, box: Box, context_padding: float = 0.10) -> CropPair:
    return CropPair(
        tight=crop_visual_box(frame, box, padding=0.0),
        context=crop_visual_box(frame, box, padding=context_padding),
        box=box,
    )
~~~

The transform records interpolation, input size 224, context padding 0.10, RGB normalization, and canonical frame version in a hashable descriptor.

- [ ] **Step 4: Implement class/source-balanced RepViT training**

Build each epoch with equal SKU contribution and equal isolated/scene source contribution when both exist. Initialize the 20-way head from the declared base artifact, preserve the canonical class map, freeze early backbone stages, train the final stage and head, and select the checkpoint only from the calibration role. Record per-SKU source counts and hashes.

- [ ] **Step 5: Implement fold-safe DINO support**

One DINO forward yields global and local tokens. Cap global prototype contributors and local patches per SKU and per source before aggregation. Save support metadata containing weights SHA-256, preprocessing SHA-256, fold SHA-256, source counts, source manifest SHA-256, tensor shape, dtype, and canonical class order.

- [ ] **Step 6: Add runtime crop-consistency tests**

~~~python
def test_direct_gate_rejects_tight_context_top1_disagreement(pipeline):
    result = pipeline.infer_many(CANONICAL, (BOX,), repvit_rows_per_invocation=14, dino_objects_per_invocation=7)
    assert result.dino_object_count == 1
    assert result.decisions[0].decision_path is not DecisionPath.REPVIT_DIRECT
~~~

RepViT receives deterministic ordered 2N row chunks ordered tight-1, context-1, tight-2, context-2, with at most seven objects per static invocation. DINO receives only rejected object context crops in ordered seven-object padded chunks. Final chunks are padded, padded rows are ignored, and chunk evidence is concatenated back to original object order; any chunk failure aborts the whole scan.

- [ ] **Step 7: Run focused suites and artifact commands**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_train_repvit_15plus5_oof.py tests/tools/test_build_dinov3_15plus5_oof.py tests/classification/test_preprocess.py tests/classification/test_runtime.py -q

Run: artifacts/installer_payload/1.1.0-final4/runtime/python/python.exe tools/train/train_repvit_15plus5_oof.py --splits data/splits/rtx5080_15plus5_oof_v1 --fold all --output C:/bixolon-artifacts/bixolon_bakery_scanner/repvit_15plus5_oof_v1

Run: artifacts/installer_payload/1.1.0-final4/runtime/python/python.exe tools/train/build_dinov3_15plus5_oof.py --splits data/splits/rtx5080_15plus5_oof_v1 --fold all --output C:/bixolon-artifacts/bixolon_bakery_scanner/dinov3_15plus5_oof_v1

- [ ] **Step 8: Commit fold-safe classifier evidence**

~~~powershell
git add tools/train/train_repvit_15plus5_oof.py tools/train/build_dinov3_15plus5_oof.py src/bakery_scanner/classification/preprocess.py src/bakery_scanner/classification/runtime.py tests/tools/test_train_repvit_15plus5_oof.py tests/tools/test_build_dinov3_15plus5_oof.py tests/classification/test_preprocess.py tests/classification/test_runtime.py
git commit -m "feat(classification): 15+5 OOF 증거 학습 추가"
~~~

## Task 6: Fold-Specific Calibration, Fusion, and Quality Gate

**Files:**
- Create: tools/train/calibrate_rtx5080_15plus5.py
- Create: src/bakery_scanner/benchmarking/oof15plus5.py
- Create: tests/tools/test_calibrate_rtx5080_15plus5.py
- Create: tests/benchmarking/test_oof15plus5.py
- Create after valid calibration: policies/classification/fusion_15plus5_oof_v1.json

**Interfaces:**
- Consumes: fold calibration evidence and separate fold evaluation predictions.
- Produces: CalibrationBundle per fold, OofAcceptanceReceipt, and a final-development policy created only after the OOF report is frozen.

- [ ] **Step 1: Write failing fold-policy isolation tests**

~~~python
def test_fold_policy_uses_only_calibration_role(calibration_rows, evaluation_rows):
    bundle = calibrate_fold(calibration_rows, fold_index=3)
    assert bundle.source_scene_ids == tuple(sorted(CAL_SCENE_IDS))
    assert not set(bundle.source_scene_ids) & set(EVAL_SCENE_IDS)


def test_sku_without_zero_error_acceptance_disables_direct_gate():
    bundle = calibrate_fold(rows_with_wrong_direct_sku4, fold_index=0)
    assert bundle.direct_gates[4].enabled is False
~~~

- [ ] **Step 2: Run calibration tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_calibrate_rtx5080_15plus5.py -q

Expected: FAIL because the calibration tool does not exist.

- [ ] **Step 3: Implement direct and fusion calibration**

For each SKU, search confidence, margin, prototype distance, and crop disagreement thresholds. Eligible direct regions have zero wrong accepted SKU on calibration evidence; select maximum coverage, then stricter confidence, margin, distance, and disagreement in deterministic tie order. Keep the immutable fusion acceptance expression:

~~~python
accepted = (
    fusion_sku == dino_local_top1
    or (
        repvit_global_top1 == fusion_sku
        and dino_global_top1 == fusion_sku
        and fusion_margin >= 0.85
    )
)
~~~

- [ ] **Step 4: Write failing quality/utility receipt tests**

~~~python
def test_wrong_auto_approval_rejects_receipt():
    receipt = evaluate_oof(ROWS_WITH_ONE_WRONG_AUTO, POLICY_BY_FOLD)
    assert receipt.status == "quality-rejected"


def test_all_unknown_cannot_pass_utility():
    receipt = evaluate_oof(ALL_UNKNOWN_ROWS, POLICY_BY_FOLD)
    assert receipt.quality.wrong_auto_approval_count == 0
    assert receipt.status == "utility-rejected"
~~~

- [ ] **Step 5: Implement OOF acceptance metrics**

Use deterministic IoU 0.50 one-to-one matching. Report misses, duplicates, non-target detections, splits, merges, detected-count mismatch, object-order mismatch, wrong auto approval, Unknown, Top3 rank hits, E/M/H, SKU, object-count, image-shape, base/incremental, and observed/counterfactual evidence separately. Compute exact one-sided 95% upper bounds and state the current sample-size limits.

- [ ] **Step 6: Freeze the OOF report before final policy creation**

The command first writes an immutable OOF receipt from five fold-specific policies. Only after that receipt hash is finalized may it build fusion_15plus5_oof_v1.json from pooled calibration evidence. The final policy stores the frozen OOF receipt SHA-256 and cannot be used to recompute that receipt.

- [ ] **Step 7: Run focused tests and calibration**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_calibrate_rtx5080_15plus5.py tests/benchmarking/test_oof15plus5.py tests/classification/test_fusion_policy.py -q

Run: artifacts/installer_payload/1.1.0-final4/runtime/python/python.exe tools/train/calibrate_rtx5080_15plus5.py --evidence-root C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_oof_v1 --splits data/splits/rtx5080_15plus5_oof_v1 --policy policies/classification/fusion_15plus5_oof_v1.json

- [ ] **Step 8: Commit calibration contracts and valid policy**

~~~powershell
git add tools/train/calibrate_rtx5080_15plus5.py src/bakery_scanner/benchmarking/oof15plus5.py tests/tools/test_calibrate_rtx5080_15plus5.py tests/benchmarking/test_oof15plus5.py policies/classification/fusion_15plus5_oof_v1.json
git commit -m "feat(policy): 15+5 OOF 수락 정책 추가"
~~~

## Task 7: Static ONNX Export and TensorRT Engine Admission

**Files:**
- Create: tools/package/export_rtx5080_15plus5_onnx.py
- Create: tools/package/build_rtx5080_15plus5_engines.py
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/engine_manifest.py
- Create: tests/tools/test_export_rtx5080_15plus5_onnx.py
- Create: tests/tools/test_build_rtx5080_15plus5_engines.py
- Create: tests/pipelines/rtx5080_15plus5/test_engine_manifest.py
- Create: models/rfdetr_l_bread_gpu_fp16_v1/manifest.schema.json
- Create: models/repvit_m1_15plus5_gpu_fp16_v1/manifest.schema.json
- Create: models/dinov3_vits16_15plus5_gpu_fp16_v1/manifest.schema.json

**Interfaces:**
- Consumes: final/fold FP32 checkpoints, exact preprocessing descriptors, and external runtime-manifest.json containing TensorRT Python binding and trtexec identities.
- Produces externally: static detector batch 1, RepViT batch 14 (seven tight/context object pairs per invocation), and DINO batch 7 (seven rejected objects per invocation) FP16 engines plus manifests. These are chunk capacities, not scan-count limits.

- [ ] **Step 1: Write failing runtime-manifest admission tests**

~~~python
def test_engine_build_refuses_unprovisioned_runtime(tmp_path):
    with pytest.raises(EngineBuildError, match="runtime manifest"):
        build_engines(
            runtime_manifest=tmp_path / "missing.json",
            onnx_root=tmp_path / "onnx",
            output=tmp_path / "engines",
        )


def test_runtime_manifest_requires_trtexec_and_python_binding_hashes(tmp_path):
    manifest = runtime_manifest_without("trtexec_sha256")
    with pytest.raises(ValueError, match="trtexec_sha256"):
        load_engine_runtime_manifest(manifest)
~~~

- [ ] **Step 2: Run engine tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_export_rtx5080_15plus5_onnx.py tests/tools/test_build_rtx5080_15plus5_engines.py tests/pipelines/rtx5080_15plus5/test_engine_manifest.py -q

Expected: FAIL because export/build contracts are absent.

- [ ] **Step 3: Implement static ONNX export**

RF-DETR uses the verified local API:

~~~python
onnx_path = model.export(
    output_dir=str(output_dir),
    shape=(detector_size, detector_size),
    batch_size=1,
    dynamic_batch=False,
    format="onnx",
    opset_version=17,
    notes=provenance_payload,
)
~~~

RepViT exports a fixed float32 tensor shape (14, 3, 224, 224). DINO exports (7, 3, 224, 224) and returns global embeddings plus local patch tensors from one graph. Export tests use fake exporters and validate shapes, names, output semantics, hashes, and refusal to overwrite.

- [ ] **Step 4: Implement external runtime identity validation**

runtime-manifest.json contains TensorRT version, CUDA version, driver compatibility range, compute capability, Python wheel path/size/SHA-256, trtexec path/size/SHA-256, ONNX wheel path/size/SHA-256, and build host identity. The builder hashes every executable and wheel before invoking it.

- [ ] **Step 5: Implement deterministic trtexec commands**

~~~python
command = [
    str(runtime.trtexec),
    f"--onnx={onnx_path}",
    f"--saveEngine={engine_path}",
    "--fp16",
    "--useCudaGraph",
    "--profilingVerbosity=detailed",
    "--builderOptimizationLevel=5",
]
subprocess.run(command, check=True, env=clean_runtime_env(runtime))
~~~

Static shapes come from the ONNX graph; dynamic profiles are forbidden. Capture stdout, stderr, exact command, elapsed time, engine size, engine SHA-256, bindings, workspace, tactic sources, GPU identity, and runtime identity in an external build receipt.

- [ ] **Step 6: Add FP32 versus FP16 evidence comparison**

On all 299 scenes, compare canonical boxes, raw score vectors, Top3 ordering, direct/consensus/Unknown decisions, and non-timing provenance. The FP16 candidate receives separate calibration; any wrong auto approval, object loss, non-finite output, or binding mismatch rejects the engine.

- [ ] **Step 7: Run hermetic tests and provisioned engine build**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_export_rtx5080_15plus5_onnx.py tests/tools/test_build_rtx5080_15plus5_engines.py tests/pipelines/rtx5080_15plus5/test_engine_manifest.py -q

Run only after the external manifest exists:

~~~powershell
python tools/package/export_rtx5080_15plus5_onnx.py --artifact-root C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_final_v1 --output C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_onnx_v1
python tools/package/build_rtx5080_15plus5_engines.py --runtime-manifest C:/bixolon-artifacts/bixolon_bakery_scanner/runtimes/tensorrt_rtx5080_v1/runtime-manifest.json --onnx-root C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_onnx_v1 --output C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_engines_v1
~~~

Absent runtime yields unverified_missing_tensorrt_runtime and stops this task before any readiness claim.

- [ ] **Step 8: Commit export/build code and schemas**

~~~powershell
git add tools/package/export_rtx5080_15plus5_onnx.py tools/package/build_rtx5080_15plus5_engines.py src/bakery_scanner/pipelines/rtx5080_15plus5/engine_manifest.py tests/tools/test_export_rtx5080_15plus5_onnx.py tests/tools/test_build_rtx5080_15plus5_engines.py tests/pipelines/rtx5080_15plus5/test_engine_manifest.py models/rfdetr_l_bread_gpu_fp16_v1/manifest.schema.json models/repvit_m1_15plus5_gpu_fp16_v1/manifest.schema.json models/dinov3_vits16_15plus5_gpu_fp16_v1/manifest.schema.json
git commit -m "feat(runtime): TensorRT FP16 engine 계약 추가"
~~~

## Task 8: Static-Batch RTX 5080 Runtime

**Files:**
- Create: src/bakery_scanner/detection/rfdetr_trt.py
- Create: src/bakery_scanner/classification/trt.py
- Create: src/bakery_scanner/pipelines/rtx5080_15plus5/runtime.py
- Create: tests/detection/test_rfdetr_trt.py
- Create: tests/classification/test_trt.py
- Create: tests/pipelines/rtx5080_15plus5/test_runtime.py
- Create: tests/integration/test_rtx5080_15plus5_gpu.py

**Interfaces:**
- Consumes: admitted EngineSession values, encoded JPEG bytes, CompletenessPolicy, direct policy, fusion policy, and ScanContext.
- Produces: Rtx5080Pipeline.infer(encoded: bytes, context: ScanContext) -> ScanResult.

- [ ] **Step 1: Write failing orchestration tests with fake sessions**

~~~python
def test_runtime_batches_all_repvit_crops_once(fake_sessions):
    runtime = build_runtime(fake_sessions, detector_boxes=FIVE_BOXES)
    result = runtime.infer(JPEG_BYTES, context=SCAN_CONTEXT)
    assert fake_sessions.repvit.calls == [(14, 3, 224, 224)]
    assert result.object_total == 5


def test_runtime_calls_dino_once_only_for_rejections(fake_sessions):
    fake_sessions.repvit.direct_accept = (True, False, True, False, True)
    result = build_runtime(fake_sessions).infer(JPEG_BYTES, context=SCAN_CONTEXT)
    assert fake_sessions.dino.call_count == 1
    assert fake_sessions.dino.valid_rows == 2
~~~

- [ ] **Step 2: Run runtime tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/detection/test_rfdetr_trt.py tests/classification/test_trt.py tests/pipelines/rtx5080_15plus5/test_runtime.py -q

Expected: FAIL because the adapters and runtime do not exist.

- [ ] **Step 3: Implement TensorRT session protocols and static adapters**

~~~python
class EngineSession(Protocol):
    def execute(self, bindings: Mapping[str, DeviceTensor], stream: CudaStream) -> Mapping[str, DeviceTensor]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ScanContext:
    scan_id: str
    retake_chain_id: str
    attempt: int


class DeviceTensor(Protocol):
    shape: tuple[int, ...]
    dtype: str


class CudaStream(Protocol):
    def synchronize(self) -> None:
        raise NotImplementedError


class RepVitTensorRtRunner:
    def score_pairs(self, crop_pairs: Sequence[GpuCropPair]) -> RepVitBatchEvidence:
        return self._execute_ordered_chunks(crop_pairs, objects_per_chunk=7, rows_per_object=2)


class DinoTensorRtRunner:
    def score_rejections(self, crops: Sequence[GpuCrop]) -> DinoBatchEvidence:
        return self._execute_ordered_chunks(crops, objects_per_chunk=7, rows_per_object=1)
~~~

Preallocate detector batch 1, RepViT batch 14, and DINO batch 7 buffers at startup. Partition every positive count deterministically in original object order, pad only each final chunk, retain a boolean valid mask, prohibit reads from padded outputs, and concatenate valid evidence in original order. Any chunk failure aborts the entire scan with no partial objects or totals.

- [ ] **Step 4: Implement one decode and GPU-resident crop flow**

Decode encoded JPEG, apply EXIF orientation, convert to canonical RGB, and retain an invertible transform. Detector preprocessing, foreground analysis, and crop tensors share the same canonical device image. No PIL crop, host tensor round-trip, or object-by-object inference is allowed.

- [ ] **Step 5: Run detector and completeness concurrently**

Use two admitted CUDA streams. Synchronize only before evaluate_completeness. Record decode_canonical, detector, completeness, crop, repvit, direct_gate, dinov3, fusion_payload, and total CUDA-event timings. total is host wall clock from encoded bytes to validated JSON bytes.

- [ ] **Step 6: Implement fail-closed branching**

Malformed detector output raises RuntimeInferenceError. Zero targets or other completeness failure produces needs_retake with no final objects; positive object counts are never retaken for batch capacity. Accepted scenes run ordered RepViT chunks; direct rejections run ordered DINO chunks; immutable fusion produces registered SKU or Unknown. Engine/CUDA/OOM or any chunk error aborts the entire result and never invokes a legacy runtime.

- [ ] **Step 7: Run hermetic and GPU-marked tests**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/detection/test_rfdetr_trt.py tests/classification/test_trt.py tests/pipelines/rtx5080_15plus5/test_runtime.py -q

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/integration/test_rtx5080_15plus5_gpu.py -m gpu -q

Expected: hermetic tests pass. GPU test passes only with admitted external engines; otherwise it is explicitly unavailable and does not establish completion.

- [ ] **Step 8: Commit static runtime**

~~~powershell
git add src/bakery_scanner/detection/rfdetr_trt.py src/bakery_scanner/classification/trt.py src/bakery_scanner/pipelines/rtx5080_15plus5/runtime.py tests/detection/test_rfdetr_trt.py tests/classification/test_trt.py tests/pipelines/rtx5080_15plus5/test_runtime.py tests/integration/test_rtx5080_15plus5_gpu.py
git commit -m "feat(runtime): RTX 5080 정적 배치 추론 추가"
~~~

## Task 9: Camera Worker, Rearrangement, and Audit Consumers

**Files:**
- Modify: src/bakery_scanner/prototype/camera_runtime.py
- Modify: src/bakery_scanner/prototype/camera_protocol.py
- Modify: apps/bakery_camera_flutter/lib/src/inference/inference_models.dart
- Modify: apps/bakery_camera_flutter/lib/src/ui/customer_checkout_screen.dart
- Modify: tests/prototype/test_camera_runtime.py
- Modify: tests/prototype/test_camera_protocol.py
- Modify: apps/bakery_camera_flutter/test/inference/inference_models_test.dart
- Modify: apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart

**Interfaces:**
- Consumes: ScanResult schema from Task 2.
- Produces: strict worker JSON, retake problem overlays, retake_chain_id/attempt handling, and immutable customer_top3/customer_catalog audit.

- [ ] **Step 1: Write failing worker protocol tests**

~~~python
def test_worker_needs_retake_has_no_partial_objects():
    event = encode_scan_result(needs_retake_result(attempt=1))
    validate_result_event(event)
    assert event["objects"] == []
    assert event["sku_totals"] == {}


def test_third_retake_escalates_to_manual_catalog():
    result = runtime.analyze(JPEG, request("scan-3", "chain-1", attempt=3))
    assert result["state"] == "needs_retake"
    assert result["manual_catalog_required"] is True
~~~

- [ ] **Step 2: Run protocol tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py -q

Expected: FAIL because the existing protocol lacks the new scan schema and rearrangement chain.

- [ ] **Step 3: Add an explicit candidate runtime selector**

The worker selects rtx5080_15plus5_single_frame_v1 only when its admission succeeds. Existing CPU and legacy selectors retain current behavior. Candidate admission failure is returned explicitly and never chooses another runtime silently.

- [ ] **Step 4: Update strict Python and Dart consumers**

Require exact location, structured confidence, decision_path, Top3, retake reasons, problem regions, runtime_profile_id, and receipt_id. Validate registered counts from objects and Unknown separately. Reject unknown fields, non-finite values, invalid object order, and partial retake payloads.

- [ ] **Step 5: Implement rearrangement UI and audit separation**

The UI highlights problem regions, shows reason-specific separation/in-tray guidance, and recaptures under the same retake_chain_id with incremented attempt. At attempt 3 it opens full catalog entry without copying a partial inference. Top3 and catalog selections persist customer_top3 with exact rank or customer_catalog with null rank and never overwrite immutable inference.

- [ ] **Step 6: Run Python and Flutter contract suites**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py -q

Run from apps/bakery_camera_flutter: flutter test test/inference/inference_models_test.dart test/ui/customer_checkout_contract_test.dart

Expected: PASS with old protocol fixtures still accepted only by their declared legacy schema.

- [ ] **Step 7: Commit worker and consumer support**

~~~powershell
git add src/bakery_scanner/prototype/camera_runtime.py src/bakery_scanner/prototype/camera_protocol.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py apps/bakery_camera_flutter/lib/src/inference/inference_models.dart apps/bakery_camera_flutter/lib/src/ui/customer_checkout_screen.dart apps/bakery_camera_flutter/test/inference/inference_models_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart
git commit -m "feat(camera): 재배치 추론 결과 계약 연결"
~~~

## Task 10: End-to-End OOF Quality and Utility Receipt

**Files:**
- Create: tools/evaluate/run_rtx5080_15plus5_oof.py
- Create: tests/tools/test_run_rtx5080_15plus5_oof.py
- Create after valid run: benchmarks/results/rtx5080_15plus5_oof_v1.json
- Create after valid run: benchmarks/summaries/rtx5080_15plus5_oof_v1.md

**Interfaces:**
- Consumes: five fold detectors, classifiers, supports, fold policies, split manifests, and current 299 scenes.
- Produces: compact Git-safe OOF receipt with quality, utility, Top3, slices, confidence bounds, and explicit unverified boundaries.

- [ ] **Step 1: Write failing coordinator tests**

~~~python
def test_oof_runner_requires_exactly_one_result_per_scene(fake_folds):
    fake_folds[2].results.pop()
    with pytest.raises(ValueError, match="exactly 299"):
        build_oof_receipt(fake_folds)


def test_compact_receipt_has_no_private_paths(fake_folds):
    payload = build_oof_receipt(fake_folds).to_payload()
    assert "C:\\" not in json.dumps(payload)
    assert payload["non_target_rejection"]["status"] == "unverified_no_negative_scenes"
~~~

- [ ] **Step 2: Run coordinator tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_run_rtx5080_15plus5_oof.py -q

Expected: FAIL because the coordinator does not exist.

- [ ] **Step 3: Implement exact fold execution**

For each fold, load only its declared artifacts and policy, infer its evaluation scenes, and write raw external rows containing input/artifact hashes, predictions, timings, and status. Refuse duplicate or missing scene IDs and verify the union is exactly the inventory identity.

- [ ] **Step 4: Implement compact status selection**

~~~python
def select_status(receipt):
    if receipt.wrong_auto_approval_count or receipt.accepted_scan_critical_failure_count:
        return "quality-rejected"
    if not receipt.utility_passed:
        return "utility-rejected"
    if not receipt.top3_passed:
        return "quality-rejected"
    return "quality-passed-performance-unverified"
~~~

The compact result includes no image paths, crops, raw predictions, or proprietary payloads.

- [ ] **Step 5: Run hermetic tests and the OOF command**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_run_rtx5080_15plus5_oof.py tests/benchmarking/test_oof15plus5.py -q

Run: artifacts/installer_payload/1.1.0-final4/runtime/python/python.exe tools/evaluate/run_rtx5080_15plus5_oof.py --splits data/splits/rtx5080_15plus5_oof_v1 --artifact-root C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_oof_v1 --raw-output C:/bixolon-artifacts/bixolon_bakery_scanner/receipts/rtx5080_15plus5_oof_v1_raw.json --compact-output benchmarks/results/rtx5080_15plus5_oof_v1.json --summary benchmarks/summaries/rtx5080_15plus5_oof_v1.md

- [ ] **Step 6: Review and commit only real evidence**

If artifacts are absent, commit an unverified_missing_artifacts checkpoint listing exact artifact IDs and omit quality numbers. If the run exists, verify all hashes and commit its actual status without editing thresholds after seeing evaluation results.

~~~powershell
git add tools/evaluate/run_rtx5080_15plus5_oof.py tests/tools/test_run_rtx5080_15plus5_oof.py benchmarks/results/rtx5080_15plus5_oof_v1.json benchmarks/summaries/rtx5080_15plus5_oof_v1.md
git commit -m "bench(quality): 15+5 OOF 수락 증거 기록"
~~~

## Task 11: Path-Aware RTX 5080 100ms Hard Gate

**Files:**
- Create: src/bakery_scanner/benchmarking/rtx5080_acceptance.py
- Create: tools/benchmark/run_rtx5080_15plus5.py
- Create: tests/benchmarking/test_rtx5080_acceptance.py
- Create: tests/tools/test_run_rtx5080_15plus5_benchmark.py
- Create: benchmarks/protocols/rtx5080_15plus5_p95_v1.json
- Create after valid run: benchmarks/results/rtx5080_15plus5_p95_v1.json
- Create after valid run: benchmarks/summaries/rtx5080_15plus5_p95_v1.md

**Interfaces:**
- Consumes: admitted final TensorRT engines, current E/M/H images, forced-path fixtures, and quality receipt identity.
- Produces: schema-v3 PerformanceReceipt with at least 1,000 warmed observations for each required slice/path and a hard pass/fail status.

- [ ] **Step 1: Write failing receipt tests**

~~~python
@pytest.mark.parametrize("slice_name", ["E", "M", "H", "overall", "dinov3", "needs_retake", "unknown", "count_1_2", "count_3_7", "count_8_plus"])
def test_each_required_slice_needs_one_thousand_samples(slice_name, valid_samples):
    samples = tuple(row for row in valid_samples if row.slice_name != slice_name or row.index < 999)
    with pytest.raises(ValueError, match=f"{slice_name} requires 1000"):
        build_performance_receipt(samples, RUNTIME, ARTIFACTS)


def test_one_path_over_one_hundred_ms_rejects_receipt(valid_samples):
    samples = replace_slice_p95(valid_samples, "dinov3", 100.01)
    assert build_performance_receipt(samples, RUNTIME, ARTIFACTS).status == "performance-rejected"
~~~

- [ ] **Step 2: Run receipt tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/benchmarking/test_rtx5080_acceptance.py -q

Expected: FAIL because rtx5080_acceptance does not exist.

- [ ] **Step 3: Implement schema-v3 samples and summaries**

Stages are decode_canonical, detector, completeness, crop, repvit, direct_gate, dinov3, fusion_payload, and total. Each sample records group, path flags, object count, DINO object count, input SHA-256, runtime identity, thermal state, and total wall time. Summaries report nearest-rank p50/p90/p95/p99/max and deterministic bootstrap p95 CI with seed 20260803.

- [ ] **Step 4: Implement deterministic benchmark scheduling**

Warm up at least 20 runs. Repeat E 100, M 99, and H 100 images in canonical sorted order until each group reaches 1,000 samples. Gather actual DINO, retake, and Unknown scans; repeat their sorted IDs until each path reaches 1,000. Record deterministic exact forced counts for count_1_2 and count_8_plus fixtures assembled only from current crop identities; label them evidence_kind forced_path_performance and never include them in accuracy or quality. count_3_7 is the current labeled quality-evidence slice.

- [ ] **Step 5: Enforce the 100ms and runtime Gates**

Reject when any required p95 exceeds 100.0, any artifact/runtime identity changes mid-run, fallback_reason is non-null, thermal throttling occurs without a clean rerun, a timing is non-finite, sample counts are short, or total is smaller than an individual stage.

- [ ] **Step 6: Run hermetic tests and the GPU benchmark**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/benchmarking/test_rtx5080_acceptance.py tests/tools/test_run_rtx5080_15plus5_benchmark.py -q

Run:

~~~powershell
python tools/benchmark/run_rtx5080_15plus5.py --dataset-root datasets --splits data/splits/rtx5080_15plus5_oof_v1 --config configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml --runtime-manifest C:/bixolon-artifacts/bixolon_bakery_scanner/runtimes/tensorrt_rtx5080_v1/runtime-manifest.json --artifact-root C:/bixolon-artifacts/bixolon_bakery_scanner/rtx5080_15plus5_final_v1 --protocol benchmarks/protocols/rtx5080_15plus5_p95_v1.json --raw-output C:/bixolon-artifacts/bixolon_bakery_scanner/receipts/rtx5080_15plus5_p95_v1_raw.json --compact-output benchmarks/results/rtx5080_15plus5_p95_v1.json --summary benchmarks/summaries/rtx5080_15plus5_p95_v1.md
~~~

Expected: only an actual receipt with E/M/H/overall/DINO/retake/Unknown p95 at or below 100ms receives performance-passed.

- [ ] **Step 7: Commit benchmark code and actual checkpoint**

~~~powershell
git add src/bakery_scanner/benchmarking/rtx5080_acceptance.py tools/benchmark/run_rtx5080_15plus5.py tests/benchmarking/test_rtx5080_acceptance.py tests/tools/test_run_rtx5080_15plus5_benchmark.py benchmarks/protocols/rtx5080_15plus5_p95_v1.json benchmarks/results/rtx5080_15plus5_p95_v1.json benchmarks/summaries/rtx5080_15plus5_p95_v1.md
git commit -m "bench(performance): RTX 5080 100ms Gate 기록"
~~~

## Task 12: Final Train-All Artifact, Compatibility, and Completion Receipt

**Files:**
- Create: tools/artifacts/register_rtx5080_15plus5.py
- Create: tests/tools/test_register_rtx5080_15plus5.py
- Modify: artifacts.lock.json
- Modify: docs/architecture/pipelines.md
- Modify: docs/architecture/repository.md
- Create: experiments/rtx5080_15plus5_single_frame_v1/conclusion.md
- Create: experiments/rtx5080_15plus5_single_frame_v1/receipt.json
- Modify: tests/contract/test_repository_policy.py
- Modify: tests/test_pipeline_contract.py

**Interfaces:**
- Consumes: frozen OOF receipt, final train-all checkpoints/support/policy, admitted engines, performance receipt, and full test evidence.
- Produces: registered external artifact identities and one final development status; it never promotes the candidate to production.

- [ ] **Step 1: Write failing completion tests**

~~~python
def test_completion_requires_quality_and_every_performance_path():
    with pytest.raises(ValueError, match="DINO path"):
        build_completion_receipt(QUALITY_PASSED, PERFORMANCE_WITHOUT_DINO, ARTIFACTS)


def test_completion_remains_production_unverified():
    receipt = build_completion_receipt(QUALITY_PASSED, PERFORMANCE_PASSED, ARTIFACTS)
    assert receipt.status == "development-complete"
    assert receipt.production_status == "unverified"
    assert "non_target_rejection" in receipt.unverified_boundaries
~~~

- [ ] **Step 2: Run completion tests and verify RED**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/tools/test_register_rtx5080_15plus5.py -q

Expected: FAIL because the registration tool does not exist.

- [ ] **Step 3: Train and build final artifacts without reusing OOF evaluation**

Train detector and RepViT on all 299 scene images plus declared isolated sources, build DINO support from all allowed development data, apply the already frozen final-development policy, export static ONNX, and build static TensorRT engines. Record that no independent final accuracy set remains.

- [ ] **Step 4: Register exact external identities**

The registration tool verifies every file, emits exact artifacts.lock.json entries with ID, size, SHA-256, storage class, and expected local path, and refuses Git-local model/engine payloads. It binds quality receipt, performance receipt, split inventory, code commit, runtime manifest, build receipt, and policy hash.

- [ ] **Step 5: Run full verification**

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest -m artifact

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest -m gpu

Run from apps/bakery_camera_flutter: flutter analyze

Run from apps/bakery_camera_flutter: flutter test

Run: $env:PYTHONPATH=(Resolve-Path src).Path; python -m bakery_scanner.artifacts.cli --root . --lock artifacts.lock.json

Run: git diff --check

Every unavailable suite remains listed under unverified_boundaries and prevents development-complete.

- [ ] **Step 6: Write the compact conclusion**

receipt.json contains only reviewed Git-safe identities, statuses, quality/utility summaries, p95 summaries, test counts, and unverified boundaries. conclusion.md states the exact outcome: development-complete / production-unverified, or the first failing state among quality-rejected, utility-rejected, performance-rejected, artifact-rejected, and unverified. It includes no raw predictions or private paths.

- [ ] **Step 7: Verify compatibility boundaries**

Run repository-policy and pipeline-contract tests proving canonical_cpu.yaml, portable_cpu_smoke, and legacy config identities and behavior remain unchanged. Review git diff --name-status and reject any modification under portable_cpu_smoke.

- [ ] **Step 8: Commit final registration and conclusion**

~~~powershell
git add tools/artifacts/register_rtx5080_15plus5.py tests/tools/test_register_rtx5080_15plus5.py artifacts.lock.json docs/architecture/pipelines.md docs/architecture/repository.md experiments/rtx5080_15plus5_single_frame_v1 tests/contract/test_repository_policy.py tests/test_pipeline_contract.py
git commit -m "docs(release): 15+5 개발 수락 증거 확정"
~~~

## Execution Checkpoints

- After Task 1: review data identities and fold leakage before any training.
- After Task 3: review retake false-positive behavior before coupling completeness to runtime.
- After Task 6: freeze OOF quality and utility evidence before final policy or TensorRT work.
- After Task 7: review provisioned runtime and FP16 comparison before runtime integration.
- After Task 10: stop on any wrong auto approval or utility failure.
- After Task 11: stop unless every required path p95 is at or below 100ms.
- After Task 12: the strongest permitted status remains development-complete / production-unverified.
