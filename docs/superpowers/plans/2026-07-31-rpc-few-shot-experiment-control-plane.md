# RPC Few-shot Experiment Control-plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, fail-closed control plane that materializes and evaluates the frozen RPC 2019 few-shot SKU protocol without changing the released bakery pipeline.

**Architecture:** A research-only `bakery_scanner.experiments.rpc_fewshot` package owns immutable dataset records, leakage-safe roles, nested support selections, stage scheduling, and compact receipts. Operational tools only materialize manifests or score precomputed, hash-bound evidence; model training, embeddings, crops, and raw predictions remain external artifacts supplied by explicitly declared adapters.

**Tech Stack:** Python 3.11, standard library, NumPy, scikit-learn, PyYAML, pytest.

## Global Constraints

- Keep `configs/pipelines/canonical_cpu.yaml`, production model manifests, and the 20-SKU runtime contracts unchanged.
- Use only `C:\workspace\archive` as the RPC source root; reject the duplicate `C:\workspace\archive\retail_product_checkout` root.
- Verify source annotations and every materialized image by lowercase SHA-256 before a run can proceed.
- Record source/split/selection/preprocess/model/calibration/policy/code/environment/output provenance in canonical JSON; never overwrite an existing manifest or receipt.
- A Stage-5 schedule is derived only from four hash-bound Stage-4 confirmation receipts for the same method, selector, fold, and support seed; the certificate proves last failure, provisional minimum, next passing anchor, and the balanced 150-shot reference. Nested JSON condition fields are re-parsed against their deterministic `condition_id` before either a condition or score receipt is trusted.
- Keep image pixels, crops, embeddings, raw predictions, checkpoints, and full run output external to Git.
- Treat missing model adapters, model artifacts, GPU suites, and retail detector evidence as `unavailable` or `unverified`, never as passing results.
- Apply the canonical EXIF-transposed RGB crop contract and fail closed on malformed or out-of-bounds boxes.
- Use test-first development for every production behavior and run tests with `PYTHONPATH=src` in this worktree.

---

## Planned file structure

| File | Responsibility |
| --- | --- |
| `src/bakery_scanner/experiments/__init__.py` | Public, research-only RPC experiment interfaces. |
| `src/bakery_scanner/experiments/rpc_manifest.py` | RPC source identity, strict COCO index, canonical manifest writing, image hashing. |
| `src/bakery_scanner/experiments/rpc_splits.py` | Deterministic five-fold base/novel assignment and burst-atomic calibration/selection roles. |
| `src/bakery_scanner/experiments/rpc_support.py` | Nested RND/DIV ordered support selection from hash-bound external embeddings. |
| `src/bakery_scanner/experiments/rpc_protocol.py` | Staged matrix generation, condition validation, canonical run receipts. |
| `src/bakery_scanner/experiments/rpc_metrics.py` | Forced Top-1, final classification, paired bootstrap, and passing-rule evaluation for arbitrary RPC class orders. |
| `tools/data/build_rpc_fewshot_manifests.py` | Explicit CLI to validate RPC and write a new immutable experiment input directory. |
| `tools/evaluate/score_rpc_fewshot.py` | Explicit CLI to validate external evidence and write compact stage receipts. |
| `data/manifests/rpc_2019_v1.json` | Git-tracked source contract with known annotation digests and split counts. |
| `experiments/20260731-rpc-fewshot/experiment.yaml` | Preregistered Stage-1 experiment declaration. |
| `tests/experiments/test_rpc_*.py` | Hermetic contract tests using tiny synthetic COCO and embedding fixtures. |

### Task 1: Create the immutable RPC source and input-manifest contract

**Files:**
- Create: `src/bakery_scanner/experiments/__init__.py`
- Create: `src/bakery_scanner/experiments/rpc_manifest.py`
- Create: `data/manifests/rpc_2019_v1.json`
- Create: `tests/experiments/test_rpc_manifest.py`

**Interfaces:**
- Produces `RpcDatasetContract`, `RpcImage`, `RpcObject`, `load_rpc_index(contract, root)`, and `write_new_json(path, payload)`.
- Consumes immutable source identity in `data/manifests/rpc_2019_v1.json` and returns only valid one-object `train2019` records plus scene records for validation/test.

- [ ] **Step 1: Write failing source-contract tests**

```python
def test_load_rpc_index_rejects_duplicate_extracted_root(tmp_path: Path):
    contract = RpcDatasetContract.default()
    duplicate = tmp_path / "retail_product_checkout"
    duplicate.mkdir()
    with pytest.raises(ValueError, match="duplicate extracted RPC root"):
        load_rpc_index(contract, duplicate)


def test_write_new_json_refuses_to_replace_receipt(tmp_path: Path):
    output = tmp_path / "manifest.json"
    write_new_json(output, {"schema_version": 1})
    with pytest.raises(FileExistsError):
        write_new_json(output, {"schema_version": 1})
```

- [ ] **Step 2: Run the new tests and verify the expected import failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_manifest.py -v`

Expected: FAIL because `bakery_scanner.experiments.rpc_manifest` does not exist.

- [ ] **Step 3: Implement strict source indexing and canonical persistence**

```python
@dataclass(frozen=True, slots=True)
class RpcDatasetContract:
    annotation_sha256: Mapping[str, str]
    image_counts: Mapping[str, int]

    @classmethod
    def default(cls) -> "RpcDatasetContract":
        return cls(
            annotation_sha256={"train2019": TRAIN_SHA, "val2019": VAL_SHA, "test2019": TEST_SHA},
            image_counts={"train2019": 53739, "val2019": 6000, "test2019": 24000},
        )


def load_rpc_index(contract: RpcDatasetContract, root: Path) -> RpcIndex:
    root = Path(root).resolve()
    if root.name == "retail_product_checkout":
        raise ValueError("duplicate extracted RPC root is not an experiment source")
    annotations = {split: root / f"instances_{split}.json" for split in contract.annotation_sha256}
    for split, path in annotations.items():
        require_sha256(path, contract.annotation_sha256[split])
    return RpcIndex.from_coco(annotations, expected_image_counts=contract.image_counts)


def write_new_json(path: Path, payload: Mapping[str, object]) -> str:
    if path.exists():
        raise FileExistsError(f"refusing to replace immutable record: {path}")
    encoded = canonical_json_bytes(payload)
    atomic_write_new(path, encoded)
    return hashlib.sha256(encoded).hexdigest()
```

- [ ] **Step 4: Add the fixed contract JSON**

```json
{"annotation_sha256":{"test2019":"2a1cb518b202c7e13a74b4ca742aad76f6246cba788288bac6423c7d4a97ba58","train2019":"2fe6891a1f33d54104116940bd2b6167d2e20b846c66808ad33e98cc3775125a","val2019":"25afdfed91bc09bff595399e0876a5707708a7061be3fa4121d13385abd1bde7"},"image_counts":{"test2019":24000,"train2019":53739,"val2019":6000},"schema_version":1,"source":"RPC 2019"}
```

- [ ] **Step 5: Run the focused tests, then commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_manifest.py -v`

Expected: PASS.

```powershell
git add src/bakery_scanner/experiments data/manifests/rpc_2019_v1.json tests/experiments/test_rpc_manifest.py
git commit -m "feat: add immutable RPC experiment input contract"
```

### Task 2: Materialize leakage-safe class folds and checkout roles

**Files:**
- Modify: `src/bakery_scanner/experiments/rpc_manifest.py`
- Create: `src/bakery_scanner/experiments/rpc_splits.py`
- Create: `tests/experiments/test_rpc_splits.py`

**Interfaces:**
- Consumes `RpcIndex` (including the source COCO category/supercategory metadata) and returns `ClassFoldAssignment` and `SceneRoleAssignment`. `RpcImage` represents one physical source COCO image exactly once; its linked `RpcObject` records carry all category annotations. Burst and role image counts are distinct `RpcImage` counts, never annotation counts.
- Produces `build_class_folds(index, *, split_version, seed)` and `build_scene_roles(index, *, split_version)`.
- `ClassFoldAssignment` guarantees five folds of 40 novel and 160 base categories; `SceneRoleAssignment` guarantees exactly one of `calibration`, `development_selection`, or `locked_acceptance` for every checkout burst. Checkout difficulty is read from the RPC COCO image `level` field, never inferred from filename suffix. The two validation role image counts must differ by no more than the largest validation burst; otherwise the split fails closed.

- [ ] **Step 1: Write failing split tests**

```python
def test_class_folds_make_each_category_novel_exactly_once(index: RpcIndex):
    folds = build_class_folds(index, split_version="rpc-v1", seed=7)
    assert len(folds) == 5
    assert all(len(fold.novel_category_ids) == 40 for fold in folds)
    assert sorted(category for fold in folds for category in fold.novel_category_ids) == list(range(1, 201))


def test_scene_roles_keep_adjacent_burst_atomic(index: RpcIndex):
    roles = build_scene_roles(index, split_version="rpc-v1")
    assert len({(row.split, row.burst_id) for row in roles if row.split != "test2019"}) == len({row.burst_id for row in roles if row.split != "test2019"})
```

- [ ] **Step 2: Run and confirm missing-module failures**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_splits.py -v`

Expected: FAIL because `rpc_splits` is missing.

- [ ] **Step 3: Implement stable assignments and validation**

```python
def build_class_folds(index: RpcIndex, *, split_version: str, seed: int) -> tuple[ClassFoldAssignment, ...]:
    # sort by (supercategory, sha256(split_version, category_id, seed)); round-robin into five folds
    # assert each fold has exactly forty novel IDs and every category occurs once
    ordered = sorted(index.categories, key=lambda row: (row.supercategory, stable_digest(split_version, seed, row.category_id)))
    novel = tuple(tuple(row.category_id for row in ordered[offset::5]) for offset in range(5))
    return tuple(ClassFoldAssignment.from_novel(index.categories, fold_index, ids) for fold_index, ids in enumerate(novel))


def build_scene_roles(index: RpcIndex, *, split_version: str) -> tuple[SceneRoleAssignment, ...]:
    # form <=120-second bursts inside (date, suffix, difficulty), assign val bursts deterministically,
    # and map every test burst to locked_acceptance
    val_bursts = build_bursts(index.checkout_images("val2019"))
    assigned = assign_balanced_bursts(val_bursts, split_version=split_version)
    locked = tuple(SceneRoleAssignment.locked(burst) for burst in build_bursts(index.checkout_images("test2019")))
    return validate_scene_roles(tuple(assigned) + locked, category_ids=index.category_ids)
```

- [ ] **Step 4: Add invalid-role tests and run focused coverage**

```python
def test_scene_roles_rejects_sku_missing_from_calibration(index_without_sku: RpcIndex):
    with pytest.raises(ValueError, match="calibration role must contain every category"):
        build_scene_roles(index_without_sku, split_version="rpc-v1")
```

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_splits.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the split boundary**

```powershell
git add src/bakery_scanner/experiments/rpc_splits.py tests/experiments/test_rpc_splits.py
git commit -m "feat: add leakage-safe RPC class and scene splits"
```

### Task 3: Add nested, deterministic support selection

**Files:**
- Create: `src/bakery_scanner/experiments/rpc_support.py`
- Create: `tests/experiments/test_rpc_support.py`

**Interfaces:**
- Consumes validated `SupportCandidate(category_id, source_identity, source_file_name, image_sha256, capture_stratum, embedding)` records for train images.
- Produces `materialize_support_order(candidates, method, seed)` and `support_prefix(order, shot_count)`.
- `materialize_support_order` accepts only `"rnd"` and `"div"`; all later shot conditions are immutable prefixes of one order.

- [ ] **Step 1: Write failing nested-support tests**

```python
def test_diversity_order_selects_one_stratum_before_repeating():
    ordered = materialize_support_order(_candidates(), method="div", seed=11)
    assert [row.source_identity for row in ordered[:3]] == ["centroid", "far-a", "far-b"]
    assert support_prefix(ordered, 1) == ordered[:1]
    assert support_prefix(ordered, 3)[:1] == support_prefix(ordered, 1)


def test_selector_rejects_duplicate_source_identity():
    with pytest.raises(ValueError, match="duplicate source identity"):
        materialize_support_order(_duplicate_candidates(), method="rnd", seed=11)
```

- [ ] **Step 2: Run and verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_support.py -v`

Expected: FAIL because `rpc_support` is missing.

- [ ] **Step 3: Implement RND and DIV without hidden sampling**

```python
def materialize_support_order(
    candidates: Sequence[SupportCandidate], *, method: Literal["rnd", "div"], seed: int
) -> tuple[SupportCandidate, ...]:
    # RND ranks SHA256(f"{seed}:{source_identity}"); DIV starts at the centroid medoid,
    # then deterministic farthest-first with capture-stratum round-robin.
    validate_support_candidates(candidates)
    if method == "rnd":
        return tuple(sorted(candidates, key=lambda row: stable_digest(seed, row.source_identity)))
    return diversity_round_robin(candidates, seed=seed)


def support_prefix(order: Sequence[SupportCandidate], shot_count: int) -> tuple[SupportCandidate, ...]:
    if shot_count < 1 or shot_count > len(order):
        raise ValueError("shot_count exceeds available unique support")
    return tuple(order[:shot_count])
```

- [ ] **Step 4: Add tie, insufficient-shot, and input-embedding digest tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_support.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the selector**

```powershell
git add src/bakery_scanner/experiments/rpc_support.py tests/experiments/test_rpc_support.py
git commit -m "feat: add nested RPC few-shot support selection"
```

### Task 4: Define the staged experiment matrix and immutable receipts

**Files:**
- Create: `src/bakery_scanner/experiments/rpc_protocol.py`
- Create: `experiments/20260731-rpc-fewshot/experiment.yaml`
- Create: `tests/experiments/test_rpc_protocol.py`

**Interfaces:**
- Consumes class folds, support orders, and a `StageRequest`.
- Produces `ExperimentCondition`, `stage_one_conditions()`, `ascending_conditions(methods)`, `refinement_shots(last_failure, first_pass)`, and `write_experiment_receipt()`.
- Receipts accept `completed`, `failed`, or `unavailable`; no condition may claim a result without all declared SHA-256 values and an external-output URI.

- [ ] **Step 1: Write the Stage-1 matrix tests**

```python
def test_stage_one_has_exactly_twelve_cells_before_fold_seed_expansion():
    cells = stage_one_conditions(seeds=(1,), folds=range(5))
    assert {(row.method, row.selector, row.shot_count) for row in cells} == {
        (method, selector, shot)
        for method, selector in (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
        for shot in (1, 3, 5)
    }


def test_receipt_rejects_missing_policy_hash():
    with pytest.raises(ValueError, match="policy_sha256"):
        ExperimentReceipt.completed(
            condition_id="stage1-m1-div-k3-fold0-seed101",
            model_sha256="a" * 64,
            support_manifest_sha256="b" * 64,
            calibration_sha256="c" * 64,
            policy_sha256="",
            output_uri="file:///external/run",
        )
```

- [ ] **Step 2: Run and confirm RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_protocol.py -v`

Expected: FAIL because `rpc_protocol` is missing.

- [ ] **Step 3: Implement schedulers and receipts**

```python
def refinement_shots(last_failure: int, first_pass: int) -> tuple[int, ...]:
    rules = {(3, 5): (4,), (5, 10): (6, 8), (10, 20): (12, 15, 18)}
    if (last_failure, first_pass) not in rules:
        raise ValueError("interval has no preregistered refinement rule")
    return rules[(last_failure, first_pass)]


def write_experiment_receipt(path: Path, receipt: ExperimentReceipt) -> str:
    return write_new_json(path, receipt.to_payload())
```

- [ ] **Step 4: Add the Stage-1 declaration and receipt immutability tests**

```yaml
schema_version: 1
experiment_id: 20260731-rpc-fewshot-stage1
hypothesis: frozen visual support representations can preserve novel-SKU Top-1 with at most five labeled images
status: planned
seed_schedule: [101, 102, 103, 104, 105]
stage: cheap_low_shot_screen
```

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_protocol.py -v`

Expected: PASS.

- [ ] **Step 5: Commit protocol scheduling**

```powershell
git add src/bakery_scanner/experiments/rpc_protocol.py experiments/20260731-rpc-fewshot/experiment.yaml tests/experiments/test_rpc_protocol.py
git commit -m "feat: define RPC few-shot experiment protocol"
```

### Task 5: Score hash-bound research evidence and apply the passing rule

**Files:**
- Create: `src/bakery_scanner/experiments/rpc_metrics.py`
- Create: `tools/data/build_rpc_fewshot_manifests.py`
- Create: `tools/evaluate/score_rpc_fewshot.py`
- Create: `tests/experiments/test_rpc_metrics.py`
- Create: `tests/experiments/test_rpc_tools.py`

**Interfaces:**
- Consumes general-class `ResearchEvidenceRow` data, a frozen condition, and the paired balanced-reference evidence.
- Produces `forced_top1_summary`, `full_system_summary`, `paired_hierarchical_bootstrap`, and `passes_minimum_rule`.
- The data tool writes manifests only after all source checks pass. The evaluation tool accepts only precomputed evidence with matching condition/support/calibration/policy hashes and marks unavailable adapters explicitly.

- [ ] **Step 1: Write failing metric and tool-contract tests**

```python
def test_minimum_rule_rejects_unknown_only_safety_gain():
    candidate = FullSystemSummary(novel_macro_recall=0.0, wrong_sku_rate=0.0, unknown_rate=1.0, base_macro_recall=0.91, novel_sku_loss_over_ten_pp_fraction=1.0)
    reference = FullSystemSummary(novel_macro_recall=0.90, wrong_sku_rate=0.01, unknown_rate=0.05, base_macro_recall=0.91, novel_sku_loss_over_ten_pp_fraction=0.0)
    assert not passes_minimum_rule(candidate, reference, _paired_ci(candidate, reference))


def test_score_tool_rejects_evidence_from_another_support_manifest(tmp_path: Path):
    with pytest.raises(ValueError, match="support_manifest_sha256"):
        main(["--evidence", str(_evidence(tmp_path, support_hash="a" * 64)), "--condition", str(_condition(tmp_path, support_hash="b" * 64))])
```

- [ ] **Step 2: Run and verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_metrics.py tests/experiments/test_rpc_tools.py -v`

Expected: FAIL because research metrics and tool modules do not exist.

- [ ] **Step 3: Implement generic metrics and the preregistered bootstrap**

```python
def passes_minimum_rule(candidate: FullSystemSummary, reference: FullSystemSummary, interval: PairedInterval) -> bool:
    return (
        interval.novel_macro_recall_delta_lower >= -0.02
        and interval.wrong_sku_delta_upper <= 0.005
        and candidate.novel_sku_loss_over_ten_pp_fraction <= 0.05
        and candidate.base_macro_recall_delta >= -0.01
    )


def paired_hierarchical_bootstrap(
    candidate: Sequence[ResearchEvidenceRow], reference: Sequence[ResearchEvidenceRow], *, seed: int, replicates: int
) -> PairedInterval:
    # Resample novel SKU within fold, then scene burst within difficulty while retaining paired rows.
    paired = validate_paired_evidence(candidate, reference)
    generator = np.random.default_rng(seed)
    deltas = [resample_paired_delta(paired, generator) for _ in range(replicates)]
    return PairedInterval.from_deltas(deltas, confidence=0.95)
```

- [ ] **Step 4: Implement fail-closed CLIs and run focused tests**

```python
parser.add_argument("--rpc-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
# The builder rejects existing output; the scorer rejects any provenance mismatch.
```

Run: `$env:PYTHONPATH='src'; python -m pytest tests/experiments/test_rpc_metrics.py tests/experiments/test_rpc_tools.py -v`

Expected: PASS.

- [ ] **Step 5: Run all hermetic tests and commit the executable control plane**

Run: `$env:PYTHONPATH='src'; python -m pytest`

Expected: PASS with artifact, GPU, and slow suites reported separately as skipped/deselected where applicable.

```powershell
git add src/bakery_scanner/experiments/rpc_metrics.py tools/data/build_rpc_fewshot_manifests.py tools/evaluate/score_rpc_fewshot.py tests/experiments
git commit -m "feat: score fail-closed RPC few-shot evidence"
```

## Plan self-review

- Spec coverage: Tasks 1–2 cover external dataset identity, canonical indexing, class folds, and leakage-safe roles. Task 3 covers nested RND/DIV support. Task 4 covers the five-stage funnel's condition scheduling and provenance. Task 5 covers screen/full metrics, paired comparison, passing rule, and external evidence validation.
- Explicit non-goals: model weight download, RepViT/DINOv3 training execution, external embedding extraction, detector retraining, and production promotion are not implemented here; each requires approved external artifacts and a separately pinned adapter receipt.
- Boundary check: research metrics use arbitrary RPC category orders and stay outside the production 20-SKU `classification` contracts.
- Placeholder scan: no deferred implementation markers are used; every task states concrete interfaces, tests, commands, and expected outcomes.
