# RF-DETR Fusion Nine-Image Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Evaluate the fixed nine Batch2 images with the RF-DETR-L detector and the \`fusion_local_or_global_consensus_margin_v1\` classifier policy, producing fail-closed per-object results and an E/M/H latency summary.

**Architecture:** Import the RF-DETR-L checkpoint and paired calibration from the approved bakery scanner sidecar, then adapt its prediction output to the existing canonical \`BreadProposal\` contract. Activate a deterministic schema-v3 fusion artifact in the current classifier configuration. A dedicated evaluation entrypoint will run canonical image loading, RF-DETR proposal creation, current classifier fusion decisions, and result/overlay/report emission without changing the existing D-FINE production factory.

**Tech Stack:** Python 3.10+, PyTorch, RF-DETR, Pillow, PyYAML, pytest.

## Global Constraints

- Keep original canonical RGB image coordinates and valid \`[x_min, y_min, x_max, y_max]\` boxes.
- Use the detector checkpoint and calibration as an immutable paired artifact; record SHA-256 provenance.
- A class may be emitted only when Fusion Top-1 equals DINOv3 local Top-1, or when it equals both RepViT and DINOv3 global Top-1 and the Fusion Top-1/Top-2 margin is at least \`0.85\`; otherwise emit \`Unknown\`.
- Preserve the existing D-FINE factory and existing classifier decision paths; the new runner is evaluation-scoped.
- Do not claim accuracy or performance before recording the actual nine-image run output.

---

## File Structure

- \`models/rfdetr_large_bakery_v1/\`: immutable RF-DETR-L checkpoint, calibration, and manifest copied from the approved sidecar.
- \`src/bakery_scanner/detectors/rfdetr.py\`: RF-DETR-L loader plus deterministic conversion to \`BreadProposal\`.
- \`configs/classifier_policy.yaml\`: schema-v3 fusion policy path and SHA-256 binding.
- \`scripts/run_rfdetr_fusion_batch2.py\`: reproducible nine-image evaluation and report generation.
- \`tests/detectors/test_rfdetr.py\`: adapter validation and canonical box conversion tests.
- \`tests/classification/test_fusion_policy.py\`: policy artifact/config binding regression coverage.

### Task 1: Bind the schema-v3 fusion policy artifact

**Files:**
- Create: \`artifacts/e2e_current_source/classification/fusion_local_or_global_consensus_margin_v1.json\`
- Modify: \`configs/classifier_policy.yaml\`
- Test: \`tests/classification/test_fusion_policy.py\`

**Interfaces:**
- Consumes: \`scripts/train_classifier_fusion_policy.py\`, development evidence, and \`ClassifierConfig.load(path)\`.
- Produces: a \`FusionPolicyArtifact\` with \`schema_version == 3\`, decision rule \`fusion_local_or_global_consensus_margin_v1\`, and \`consensus_margin_floor == 0.85\`, bound by \`fusion_policy_sha256\` in the YAML.

- [ ] **Step 1: Write the failing configuration-binding test**

\`\`\`python
config = ClassifierConfig.load(config_path)
assert config.fusion_policy is not None
assert config.fusion_policy_sha256 == sha256_file(config.fusion_policy)
assert config.fusion_policy.decision_rule == "fusion_local_or_global_consensus_margin_v1"
assert config.fusion_policy.consensus_margin_floor == pytest.approx(0.85)
\`\`\`

- [ ] **Step 2: Run the focused test and verify it fails because no fusion policy is bound**

Run: \`pytest tests/classification/test_fusion_policy.py -q\`

Expected: FAIL at the new configuration-binding assertion.

- [ ] **Step 3: Generate the canonical schema-v3 artifact and bind its exact SHA-256**

\`\`\`powershell
python scripts/train_classifier_fusion_policy.py --config configs/classifier_policy.yaml --evidence artifacts/e2e_current_source/classification/development_evidence.jsonl --output artifacts/e2e_current_source/classification/fusion_local_or_global_consensus_margin_v1.json --decision-rule fusion_local_or_global_consensus_margin_v1 --consensus-margin-floor 0.85 --folds 5 --seed 20260729
\`\`\`

Add the generated relative artifact path and the output of \`Get-FileHash -Algorithm SHA256\` under the classifier \`calibration\` section, using the runtime's \`fusion_policy\` and \`fusion_policy_sha256\` keys.

- [ ] **Step 4: Run focused classifier policy and runtime tests**

Run: \`pytest tests/classification/test_fusion_policy.py tests/classification/test_runtime.py -q\`

Expected: PASS, including local agreement, high-margin global consensus, low-margin \`Unknown\`, and \`fusion_global_consensus_margin\` reason assertions.

- [ ] **Step 5: Commit the artifact, configuration, and test**

\`\`\`bash
git add configs/classifier_policy.yaml artifacts/e2e_current_source/classification/fusion_local_or_global_consensus_margin_v1.json tests/classification/test_fusion_policy.py
git commit -m "feat: bind fusion consensus policy"
\`\`\`

### Task 2: Add the RF-DETR-L proposal adapter and paired model manifest

**Files:**
- Create: \`models/rfdetr_large_bakery_v1/checkpoint.pth\`
- Create: \`models/rfdetr_large_bakery_v1/calibration.json\`
- Create: \`models/rfdetr_large_bakery_v1/manifest.json\`
- Create: \`src/bakery_scanner/detectors/rfdetr.py\`
- Test: \`tests/detectors/test_rfdetr.py\`

**Interfaces:**
- Consumes: a PIL canonical RGB image and \`RFDetrRunner.predict(image_id: int, image: Image.Image)\`.
- Produces: \`tuple[BreadProposal, ...]\`, ordered by descending confidence then coordinates, with clipped positive finite boxes.

- [ ] **Step 1: Write failing adapter tests using a fake RF-DETR prediction object**

\`\`\`python
runner = RFDetrRunner.from_model(fake_model, score_threshold=0.5)
proposals = runner.predict(7, Image.new("RGB", (100, 60)))
assert [(p.image_id, p.class_id, p.box_xyxy) for p in proposals] == [(7, 0, (0.0, 3.0, 100.0, 60.0))]
assert all(p.source == "rfdetr_large_bakery_v1" for p in proposals)
\`\`\`

Include malformed, background, off-canvas, and non-positive boxes and assert that they are rejected.

- [ ] **Step 2: Run the adapter test and verify it fails because the module is absent**

Run: \`pytest tests/detectors/test_rfdetr.py -q\`

Expected: FAIL with an import error for \`bakery_scanner.detectors.rfdetr\`.

- [ ] **Step 3: Write minimal RF-DETR loader and normalizer**

\`\`\`python
class RFDetrRunner:
    @classmethod
    def load(cls, checkpoint: Path, score_threshold: float) -> "RFDetrRunner": ...

    def predict(self, image_id: int, image: Image.Image) -> tuple[BreadProposal, ...]: ...
\`\`\`

Use \`rfdetr.RFDETRLarge(pretrain_weights=str(checkpoint), num_classes=1)\` and \`predict(image, threshold=score_threshold, include_source_image=False)\`. Accept only product class \`0\`, clip xyxy boxes to the image, enforce finite positive geometry, and emit deterministic order.

- [ ] **Step 4: Copy the approved checkpoint/calibration without altering their bytes and write a hash manifest**

Copy only \`detector/checkpoint.pth\` and \`detector/calibration.json\` from \`C:\\workspace\\bakery_ai_scanner\\output\\desktop_pos_base15_ux_fixed\\models-base15-ux-v3\`. Write \`manifest.json\` with source paths, SHA-256 values, threshold extracted from calibration, and source model label \`rfdetr_large_bakery_v1\`.

- [ ] **Step 5: Run adapter tests and checksum verification**

Run: \`pytest tests/detectors/test_rfdetr.py -q\`

Expected: PASS. Verify every manifest SHA-256 against its local file before evaluation.

- [ ] **Step 6: Commit the adapter, tests, and lightweight manifest**

\`\`\`bash
git add src/bakery_scanner/detectors/rfdetr.py tests/detectors/test_rfdetr.py models/rfdetr_large_bakery_v1/manifest.json
git commit -m "feat: add RF-DETR proposal adapter"
\`\`\`

### Task 3: Create and execute the nine-image RF-DETR/fusion evaluation

**Files:**
- Create: \`scripts/run_rfdetr_fusion_batch2.py\`
- Create: \`artifacts/evaluations/rfdetr_fusion_batch2_<timestamp>/report.json\`
- Create: \`artifacts/evaluations/rfdetr_fusion_batch2_<timestamp>/overlays/*.jpg\`
- Test: \`tests/detectors/test_rfdetr.py\`, \`tests/classification/test_runtime.py\`

**Interfaces:**
- Consumes: the fixed E/M/H samples, RF-DETR manifest/checkpoint, and \`ClassifierRuntime\` configured with the schema-v3 policy.
- Produces: JSON containing per-image detector/classifier outputs, per-object decision path/unknown reason, and E/M/H mean image latency in milliseconds.

- [ ] **Step 1: Add a failing report-aggregation test**

\`\`\`python
summary = summarize_profiles([
    {"profile": "E", "elapsed_ms": 10.0},
    {"profile": "E", "elapsed_ms": 14.0},
])
assert summary["E"]["mean_ms"] == pytest.approx(12.0)
\`\`\`

- [ ] **Step 2: Run the focused test and verify it fails because the runner helper is absent**

Run: \`pytest tests/detectors/test_rfdetr.py -q\`

Expected: FAIL at importing \`summarize_profiles\` from the evaluation module.

- [ ] **Step 3: Implement the evaluation entrypoint**

\`\`\`python
def summarize_profiles(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, float]]: ...
def run_image(path: Path, profile: str, detector: RFDetrRunner, classifier: ClassifierRuntime) -> dict[str, object]: ...
\`\`\`

Use \`load_canonical_image\`, detect all proposals, crop validated proposals in canonical coordinates, run \`ClassifierRuntime\`, render labels and \`Unknown\` reason to overlays, and record detector/classifier/total timing. Do not route this evaluation runner through the legacy CPU MobileNet adapter.

- [ ] **Step 4: Run unit/regression tests**

Run: \`pytest tests/detectors/test_rfdetr.py tests/classification/test_fusion_policy.py tests/classification/test_runtime.py -q\`

Expected: PASS.

- [ ] **Step 5: Execute the fixed nine-image run after one warm-up image**

Run: \`python scripts/run_rfdetr_fusion_batch2.py --input-root samples/batch2_e3_m3_h3 --classifier-config configs/classifier_policy.yaml --detector-manifest models/rfdetr_large_bakery_v1/manifest.json --output-root artifacts/evaluations\`

Expected: a timestamped report and overlays for exactly 9 images. Read the report before publishing the E/M/H means.

- [ ] **Step 6: Commit the evaluation source and tests, but not generated report/overlays or model checkpoint**

\`\`\`bash
git add scripts/run_rfdetr_fusion_batch2.py tests/detectors/test_rfdetr.py
git commit -m "feat: evaluate RF-DETR fusion samples"
\`\`\`

## Self-Review

- Spec coverage: Task 1 implements exactly the two allowed auto-confirm branches and fail-closed \`Unknown\`; Task 2 imports RF-DETR-L plus its post-processing contract; Task 3 produces the requested nine-image E/M/H result and preserves reproducible evidence.
- Placeholder scan: no deferred or unspecified implementation steps remain.
- Type consistency: detector results use the existing \`BreadProposal\`; classifier results remain \`ClassifierRuntime\` outputs; evaluation aggregation accepts serialized per-image records.
