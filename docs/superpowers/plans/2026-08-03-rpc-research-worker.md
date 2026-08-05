# RPC Research Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Generate reproducible RPC 2019 Stage-1 M0/M1/M2 evidence and method/shot comparisons from approved DINOv3 ViT-S/16 and RepViT-M1 research backbones.

**Architecture:** A research-only worker consumes the resolved RPC manifest, scene-role manifest, and ground-truth manifests outside Git. It extracts deterministic oracle-box features once, materializes hash-bound RND/DIV support selections, then scores frozen M0/M1/M2 recipes over the pre-registered Stage-1 conditions. It writes external embeddings, model heads, raw evidence, and compact receipts only; the canonical bakery pipeline remains unchanged.

**Tech Stack:** Python 3.11, PyTorch CUDA, torchvision, timm, DINOv3, safetensors, NumPy, scikit-learn, existing bakery_scanner.experiments contracts.

## Global Constraints

- Use only C:\workspace\archive; reject retail_product_checkout as a duplicate extraction.
- Accept DINOv3 only at SHA-256 08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d.
- Accept timm/repvit_m1.dist_in1k only at SHA-256 217aca2b9a9149ebbab4faac93719036a227fd2fbde623cd51f780f49b7610a4.
- Store crops, embeddings, checkpoints, support banks, raw predictions, and receipts only under C:\workspace\rpc_fewshot_runs.
- Stage 1 uses oracle COCO boxes and branch forced Top-1. It never changes detector, gates, fusion, Unknown, or configs/pipelines/canonical_cpu.yaml.
- Support draws are deterministic, prefix-nested, and bind source identity, byte size, and SHA-256.
- Report this as an RPC 2019 research result, never as a bakery deployment claim.

---

### Task 1: Verify artifacts and materialize oracle features

**Files:**
- Create: src/bakery_scanner/experiments/rpc_research_worker.py
- Create: tests/experiments/test_rpc_research_worker.py
- Create: tools/experiments/run_rpc_research_features.py

**Interfaces:**
- ResearchArtifacts.from_paths(repvit_path: Path, dino_path: Path) -> ResearchArtifacts
- OracleFeatureRow(source_identity: str, annotation_id: int, category_id: int, bbox_xywh: tuple[float, float, float, float], difficulty: str)
- extract_oracle_features(index: RpcIndex, artifacts: ResearchArtifacts, output: Path) -> Path

- [ ] Step 1: Write failing tests.

~~~python
def test_research_artifacts_reject_wrong_dino_digest(tmp_path: Path):
    with pytest.raises(ValueError, match="DINOv3 SHA-256 mismatch"):
        ResearchArtifacts.from_paths(tmp_path / "repvit.safetensors", tmp_path / "dino.pth")


def test_oracle_feature_row_is_bound_to_source_and_box():
    row = OracleFeatureRow("val2019:7:item.jpg", 11, 7, (1.0, 2.0, 3.0, 4.0), "E")
    assert row.identity == "val2019:7:item.jpg:11"
~~~

- [ ] Step 2: Run pytest tests/experiments/test_rpc_research_worker.py -v and verify it fails because the types do not exist.

- [ ] Step 3: Implement strict digests, canonical RGB oracle cropping, 384-dimensional L2-normalized RepViT and DINO global features, and 196 by 384 DINO patch features. Emit no-replace float16 arrays plus one canonical feature manifest.

- [ ] Step 4: Run the new tests; a one-image fixture must record both global vectors and the 196 patch features.

- [ ] Step 5: Commit.

~~~powershell
git add src/bakery_scanner/experiments/rpc_research_worker.py tools/experiments/run_rpc_research_features.py tests/experiments/test_rpc_research_worker.py
git commit -m "feat: add RPC research feature worker"
~~~

### Task 2: Materialize nested RND and DIV support banks

**Files:**
- Modify: src/bakery_scanner/experiments/rpc_research_worker.py
- Modify: tests/experiments/test_rpc_research_worker.py
- Create: tools/experiments/materialize_rpc_research_supports.py

**Interfaces:**
- materialize_support_bank(rows: Sequence[OracleFeatureRow], selector: str, seed: int, maximum_shots: int) -> SupportBank
- SupportBank.prefix(shot_count: int) -> tuple[SupportExample, ...]

- [ ] Step 1: Write failing tests.

~~~python
def test_random_support_prefixes_are_seeded_and_nested():
    bank = materialize_support_bank(rows, selector="rnd", seed=101, maximum_shots=5)
    assert bank.prefix(1) == bank.prefix(5)[:1]
    assert bank.prefix(3) == bank.prefix(5)[:3]


def test_diverse_one_shot_uses_centroid_medoid():
    bank = materialize_support_bank(rows, selector="div", seed=101, maximum_shots=1)
    assert bank.prefix(1)[0].source_identity == "centroid-medoid.jpg"
~~~

- [ ] Step 2: Run pytest tests/experiments/test_rpc_research_worker.py -v and verify the named function is absent.

- [ ] Step 3: Implement SHA-256 RND ordering and DINO-global centroid-medoid, capture-stratum-aware farthest-first DIV ordering. Reject insufficient classes, duplicate source identities, and non-prefix extensions. Store complete ordered support identities and feature-array digest.

- [ ] Step 4: Run the support tests and verify nested draws and duplicate rejection pass.

- [ ] Step 5: Commit.

~~~powershell
git add src/bakery_scanner/experiments/rpc_research_worker.py tools/experiments/materialize_rpc_research_supports.py tests/experiments/test_rpc_research_worker.py
git commit -m "feat: materialize nested RPC support banks"
~~~

### Task 3: Implement M0, M1, M2 branch evidence

**Files:**
- Modify: src/bakery_scanner/experiments/rpc_research_worker.py
- Modify: tests/experiments/test_rpc_research_worker.py
- Create: tools/experiments/run_rpc_research_stage1.py

**Interfaces:**
- score_m1(repvit_support, dino_support, query) -> BranchPrediction
- score_m2(repvit_cache, dino_cache, query) -> BranchPrediction
- fit_m0_head(base_features, novel_features, frozen_base_rows) -> LinearHead

- [ ] Step 1: Write failing tests.

~~~python
def test_m1_scores_normalized_class_means():
    assert score_m1(repvit_support, dino_support, query).repvit_top1 == 7


def test_m2_normalizes_each_class_cache_count():
    assert score_m2(one_exemplar, query).dino_scores[7] == score_m2(duplicated_exemplars, query).dino_scores[7]


def test_m0_keeps_frozen_base_rows_unchanged():
    head = fit_m0_head(base_features, novel_features, base_rows_before_fit)
    assert torch.equal(head.base_rows, base_rows_before_fit)
~~~

- [ ] Step 2: Run pytest tests/experiments/test_rpc_research_worker.py -v and verify the scorer functions are absent.

- [ ] Step 3: Implement M1 L2-normalized class means, M2 class-normalized exemplar-kernel aggregation, and M0 fixed class-balanced new-row-only head training. Every method emits RepViT global, DINO global, and DINO local patch scores in one sorted 200-class order.

- [ ] Step 4: Run scorer tests and verify all three method semantics pass.

- [ ] Step 5: Commit.

~~~powershell
git add src/bakery_scanner/experiments/rpc_research_worker.py tools/experiments/run_rpc_research_stage1.py tests/experiments/test_rpc_research_worker.py
git commit -m "feat: score RPC few-shot method families"
~~~

### Task 4: Execute Stage 1 and report comparisons

**Files:**
- Modify: tools/experiments/run_rpc_research_stage1.py
- Modify: src/bakery_scanner/experiments/rpc_research_worker.py
- Modify: tests/experiments/test_rpc_research_worker.py
- Create: experiments/20260731-rpc-fewshot/README.md

**Interfaces:**
- run_stage1(inputs: StageOneInputs, output: Path) -> tuple[Path, ...]
- Consumes all 300 pre-registered Stage-1 conditions, external features, support banks, development ground truth, and immutable scoring plan.
- Produces raw branch evidence, canonical score receipts, selection receipt, and compact method table.

- [ ] Step 1: Write the failing end-to-end fixture.

~~~python
def test_stage1_runner_writes_all_four_methods_for_each_fold_seed(tmp_path: Path):
    receipt_paths = run_stage1(fixture_inputs, tmp_path)
    assert len(receipt_paths) == 300
    assert all(path.read_bytes() == canonical_json_bytes(json.loads(path.read_bytes())) for path in receipt_paths)
~~~

- [ ] Step 2: Run pytest tests/experiments/test_rpc_research_worker.py -v and verify run_stage1 is absent.

- [ ] Step 3: For every pre-registered condition, write no-replace raw branch scores and provenance externally, call tools/evaluate/score_rpc_fewshot.py, and derive Stage-1 selection solely from its complete receipt matrix. Summarize macro Top-1, wrong-SKU rate, branch agreement, and fold/seed intervals.

- [ ] Step 4: Run pytest tests/experiments/test_rpc_research_worker.py tests/experiments/test_rpc_scoring_plan.py tests/experiments/test_rpc_protocol.py -q. Verify altered or incomplete evidence is rejected.

- [ ] Step 5: Run the real feature, support, and Stage-1 commands. Expect 300 external receipts and one compact comparison summary. Do not claim a minimum shot count until Stage 2 through locked acceptance run.

- [ ] Step 6: Commit code and documentation.

~~~powershell
git add src/bakery_scanner/experiments/rpc_research_worker.py tools/experiments tests/experiments/test_rpc_research_worker.py experiments/20260731-rpc-fewshot/README.md
git commit -m "feat: run reproducible RPC stage-one research"
~~~
