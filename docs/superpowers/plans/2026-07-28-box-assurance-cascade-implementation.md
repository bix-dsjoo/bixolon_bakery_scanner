# Box Assurance Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build a D-FINE-N 640 box-assurance cascade that reaches zero locked-set box errors at IoU 0.50 and 0.75 while proving RTX 5080 warm E2E p95 <= 0.5 seconds.

**Architecture:** Preserve D-FINE low-score candidates for recall. Build a non-destructive proposal graph. MobileNetV4 produces first-pass four-state, quality, and coordinate-delta outputs; ConvNeXt-Tiny only rechecks ambiguous graph components. All thresholds are cross-fit from other folds.

**Tech Stack:** Python 3.11, PyTorch, timm, D-FINE, CUDA 12.8, RTX 5080, pytest.

## Global Constraints

- Retain the existing staged 299 images, 1,410 boxes, grouped five folds, and valid D-FINE OOF receipts.
- Model training and inference use cuda:0 only. CPU is restricted to tests, artifact validation, and deterministic graph code.
- Keep raw D-FINE score >= .001 and at most 30 source candidates per image.
- Never use hard NMS to delete an overlapping candidate.
- Every target-fold checkpoint and threshold may use only the other four folds.
- Acceptance: zero misses, false positives, duplicates, split errors, merge errors, and Unknown components at IoU .50 and .75; E2E warm p95 <= .5 seconds.
- Development report must state operational_guarantee: false and list missing real empty-tray, overlap, and obstruction data.

---

### Task 0: Align repository pipeline contract with the approved cascade

**Files:**

- Modify: AGENTS.md
- Modify: README.md
- Modify: docs/superpowers/specs/2026-07-27-final-inference-pipeline-design.md
- Create: tests/test_pipeline_contract.py

- [ ] **Step 1: Write the required contract assertions in documentation tests.**

~~~python
def test_pipeline_contract_names_mobile_first_and_conditional_convnext():
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "MobileNetV4" in text and "conditional ConvNeXt-Tiny" in text
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_pipeline_contract.py -q

- [ ] **Step 3: Document the approved boundary.**

State that D-FINE-N creates recall-first candidates, MobileNetV4 performs first-pass Box Assurance, and ConvNeXt-Tiny is conditional only for ambiguity. State that the final component resolver—not NMS—owns duplicate versus overlap decisions and that the locked-set IoU .50/.75 zero-error plus E2E p95 gates are required.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_pipeline_contract.py -q
git add AGENTS.md README.md docs/superpowers/specs/2026-07-27-final-inference-pipeline-design.md tests/test_pipeline_contract.py
git commit -m "docs: align pipeline with box assurance cascade"
~~~

### Task 1: Immutable assurance contracts and labels

**Files:**

- Create: src/bakery_scanner/verifier/assurance.py
- Modify: src/bakery_scanner/contracts.py
- Modify: src/bakery_scanner/verifier/data.py
- Create: tests/test_box_assurance_contracts.py
- Modify: tests/test_verifier_data.py

**Interfaces:**

~~~python
class AssuranceBackend(StrEnum):
    MOBILE = "mobilenetv4_conv_small"
    CONVNEXT = "convnext_tiny"

@dataclass(frozen=True, slots=True)
class BoxAssurancePrediction:
    image_id: int
    candidate_xywh: Box
    state_probabilities: tuple[float, float, float, float]
    quality: float
    delta_xywh: tuple[float, float, float, float]
    backend: AssuranceBackend
~~~

- [ ] **Step 1: Write failing contract tests.**

~~~python
def test_prediction_requires_probability_sum_and_bounded_quality():
    with pytest.raises(ValueError, match="quality"):
        BoxAssurancePrediction(1, BOX, (1, 0, 0, 0), 1.1, (0, 0, 0, 0), AssuranceBackend.MOBILE)

def test_partial_label_requires_gt_delta():
    assert label_assurance_crop(partial, (target,)).target_delta_xywh != (0, 0, 0, 0)
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_box_assurance_contracts.py tests/test_verifier_data.py -q

- [ ] **Step 3: Implement strict contracts and deterministic labels.**

Validate positive image ID, in-bounds finite source box, four probabilities summing within 1e-6, quality in [0,1], finite deltas, and known backend. Generate labels from only supplied image IDs: EXACTLY_ONE gets quality one at IoU >= .75; PARTIAL receives GT-to-candidate delta; INVALID and MULTIPLE have zero delta.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_box_assurance_contracts.py tests/test_verifier_data.py -q
git add src/bakery_scanner/contracts.py src/bakery_scanner/verifier/assurance.py src/bakery_scanner/verifier/data.py tests/test_box_assurance_contracts.py tests/test_verifier_data.py
git commit -m "feat: define box assurance contracts"
~~~

### Task 2: Non-destructive proposal graph and component resolver

**Files:**

- Create: src/bakery_scanner/detectors/proposal_graph.py
- Create: tests/test_proposal_graph.py
- Modify: src/bakery_scanner/detectors/proposal_policy.py

**Interfaces:**

~~~python
@dataclass(frozen=True, slots=True)
class ProposalComponent:
    image_id: int
    members: tuple[BreadProposal, ...]

def build_proposal_components(proposals: Sequence[BreadProposal]) -> tuple[ProposalComponent, ...]: ...
def resolve_component(component: ProposalComponent,
                      predictions: Mapping[Box, BoxAssurancePrediction],
                      policy: AssurancePolicy) -> tuple[ResolvedBox, ...]: ...
~~~

- [ ] **Step 1: Write failing resolver tests.**

~~~python
def test_overlap_creates_component_without_nms_deletion():
    assert build_proposal_components((left_bread, right_bread))[0].members == (left_bread, right_bread)

def test_multiple_component_recovers_two_exact_boxes():
    assert len(resolve_component(component, predictions, policy)) == 2

def test_unresolved_merge_returns_unknown_not_final_merge():
    assert resolve_component(component, merged_only, policy)[0].outcome == "Unknown"
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_proposal_graph.py -q

- [ ] **Step 3: Implement graph and resolver.**

Link same-image candidates by overlap, containment, or normalized center distance. Keep all members. Apply only finite, in-bounds deltas. Retain compatible EXACTLY_ONE boxes; re-evaluate PARTIAL locally; use existing separated candidates for MULTIPLE; otherwise emit Unknown.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_proposal_graph.py tests/test_proposal_policy.py -q
git add src/bakery_scanner/detectors/proposal_graph.py src/bakery_scanner/detectors/proposal_policy.py tests/test_proposal_graph.py
git commit -m "feat: resolve detector proposal components"
~~~

### Task 3: Dual-head MobileNetV4 and conditional ConvNeXt-Tiny models

**Files:**

- Modify: src/bakery_scanner/verifier/model.py
- Modify: src/bakery_scanner/verifier/assurance.py
- Create: tests/test_assurance_model.py
- Modify: tests/test_verifier_model.py

**Interfaces:**

~~~python
class BoxAssuranceModel(nn.Module):
    def forward(self, crops: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        # [N,4] state logits, [N] quality logits, [N,4] deltas
        ...

def build_assurance_model(backend: AssuranceBackend, *, pretrained: bool) -> BoxAssuranceModel: ...
~~~

- [ ] **Step 1: Write failing head and conditional-path tests.**

~~~python
def test_mobile_emits_four_state_quality_and_delta_heads():
    state, quality, delta = build_assurance_model(AssuranceBackend.MOBILE, pretrained=False)(torch.zeros(2, 3, 224, 224))
    assert state.shape == (2, 4) and quality.shape == (2,) and delta.shape == (2, 4)

def test_confident_mobile_candidate_skips_convnext():
    assert run_cascade(confident_mobile_batch).convnext_count == 0
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_assurance_model.py tests/test_verifier_model.py -q

- [ ] **Step 3: Implement training and conditional fallback.**

Build pinned timm MobileNetV4 or ConvNeXt-Tiny with state, quality, and delta heads. Use cross entropy, BCE quality, and Smooth L1 delta loss only for EXACTLY_ONE/PARTIAL labels. ConvNeXt executes only for low state margin, low quality, PARTIAL, MULTIPLE, or graph conflict. Receipt records backend, loss weights, preprocessing, seed, cuda:0, label metadata, and artifact hashes.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_assurance_model.py tests/test_verifier_model.py -q
git add src/bakery_scanner/verifier/model.py src/bakery_scanner/verifier/assurance.py tests/test_assurance_model.py tests/test_verifier_model.py
git commit -m "feat: add conditional box assurance models"
~~~

### Task 4: Grouped five-fold GPU assurance evidence

**Files:**

- Create: scripts/run_box_assurance_oof.ps1
- Modify: src/bakery_scanner/verifier/model.py
- Create: tests/test_box_assurance_oof.py
- Generate: artifacts/box_system/assurance/{backend}-seed20260724-fold{0..4}/

**Interfaces:**

~~~python
def validate_completed_assurance_fold(*, run_root: Path, fold_manifest: Path,
                                      detector_predictions: Path,
                                      backend: AssuranceBackend) -> None: ...
~~~

- [ ] **Step 1: Write failing receipt-isolation tests.**

~~~python
def test_completed_assurance_fold_rejects_held_out_id_leakage(tmp_path):
    with pytest.raises(ValueError, match="held-out"):
        validate_completed_assurance_fold(...)

def test_oof_runner_rejects_cpu():
    with pytest.raises(ValueError, match="cuda:0"):
        run_oof(device="cpu")
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_box_assurance_oof.py -q

- [ ] **Step 3: Implement sequential runner.**

Revalidate five D-FINE receipts. For each fold train MobileNetV4 with the other four grouped folds, infer held-out candidates, train/infer ConvNeXt only on MobileNet ambiguity candidates, and write canonical predictions, IDs, receipt, configuration, and hashes. Run exactly one GPU job at a time and refuse overwrites.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_box_assurance_oof.py tests/test_assurance_model.py -q
[scriptblock]::Create((Get-Content -Raw scripts/run_box_assurance_oof.ps1)) | Out-Null
git add scripts/run_box_assurance_oof.ps1 src/bakery_scanner/verifier/model.py tests/test_box_assurance_oof.py
git commit -m "feat: train grouped box assurance oof"
~~~

### Task 5: Leakage-safe graph policy and zero-error report

**Files:**

- Create: src/bakery_scanner/detectors/box_assurance_selection.py
- Create: scripts/select_box_assurance.py
- Create: tests/test_box_assurance_selection.py
- Generate: artifacts/box_system/reports/box_assurance_development.json

**Interfaces:**

~~~python
@dataclass(frozen=True, slots=True)
class AssurancePolicy:
    mobile_exact_threshold: float
    mobile_quality_threshold: float
    convnext_exact_threshold: float
    convnext_quality_threshold: float
    graph_overlap_threshold: float

def cross_fit_assurance_policies(...) -> Mapping[int, AssurancePolicy]: ...
~~~

- [ ] **Step 1: Write failing isolation and IoU gate tests.**

~~~python
def test_target_fold_policy_uses_only_other_folds():
    assert policy_training_image_ids(0).isdisjoint(fold_ids[0])

def test_locked_gate_rejects_iou75_error():
    with pytest.raises(ValueError, match="IoU 0.75"):
        assert_locked_zero_error(report_with_one_iou75_miss)
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_box_assurance_selection.py -q

- [ ] **Step 3: Implement cross-fit report.**

Enumerate only thresholds observed in other folds plus zero. Rank IoU .75 misses, false positives, duplicates, split errors, merge errors, Unknown count, then IoU .50 errors with deterministic tie breaks. Report per-fold policies, all detector and assurance hashes, fallback rate, per-IoU errors, and operational_guarantee false.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_box_assurance_selection.py tests/test_proposal_graph.py -q
python scripts/select_box_assurance.py --help
git add src/bakery_scanner/detectors/box_assurance_selection.py scripts/select_box_assurance.py tests/test_box_assurance_selection.py
git commit -m "feat: cross-fit box assurance policy"
~~~

### Task 6: Final bundle and E2E GPU latency gate

**Files:**

- Modify: src/bakery_scanner/detectors/bundle.py
- Modify: scripts/train_dfine640_verifier_final.ps1
- Create: scripts/benchmark_box_assurance_e2e.py
- Create: tests/test_box_assurance_benchmark.py
- Modify: tests/test_detector_bundle.py

**Interfaces:**

~~~python
def validate_box_assurance_bundle(bundle_root: Path) -> None: ...
def benchmark_e2e(*, image_paths: Sequence[Path], device: str = "cuda:0") -> LatencyReport: ...
~~~

- [ ] **Step 1: Write failing bundle and p95 tests.**

~~~python
def test_bundle_requires_mobile_and_convnext_hashes(tmp_path):
    with pytest.raises(ValueError, match="convnext"):
        validate_box_assurance_bundle(tmp_path)

def test_latency_gate_rejects_p95_above_half_second():
    with pytest.raises(ValueError, match="p95"):
        assert_latency_gate(LatencyReport(p95_seconds=.501))
~~~

- [ ] **Step 2: Confirm RED.**

Run: $env:PYTHONPATH='src'; python -m pytest tests/test_detector_bundle.py tests/test_box_assurance_benchmark.py -q

- [ ] **Step 3: Implement final training, smoke, and benchmark.**

Train D-FINE, MobileNetV4, and ConvNeXt-Tiny sequentially on cuda:0 only after the OOF report has zero locked-set errors. Bundle checkpoints, graph policy, input snapshot, OOF report, smoke result, and hashes. Benchmark at least ten warm-up images and record every stage mean/p50/p95, overall p95, and ConvNeXt fallback rate.

- [ ] **Step 4: Verify and commit.**

Run:

~~~powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_detector_bundle.py tests/test_box_assurance_benchmark.py tests/test_box_assurance_selection.py -q
[scriptblock]::Create((Get-Content -Raw scripts/train_dfine640_verifier_final.ps1)) | Out-Null
git add src/bakery_scanner/detectors/bundle.py scripts/train_dfine640_verifier_final.ps1 scripts/benchmark_box_assurance_e2e.py tests/test_detector_bundle.py tests/test_box_assurance_benchmark.py
git commit -m "feat: package and benchmark box assurance cascade"
~~~

## Completion Evidence

- Existing D-FINE fold 0-4 receipts remain valid.
- Ten grouped assurance OOF receipts are hash-valid and held-out.
- Cross-fit report has zero errors at IoU .50 and .75 across all 299 images, with zero final Unknown components.
- Final manifest validates detector, both assurance models, graph policy, OOF report, smoke, and latency hashes.
- RTX 5080 warm E2E p95 is measured at or below .5 seconds without suppressing ambiguity for speed.
