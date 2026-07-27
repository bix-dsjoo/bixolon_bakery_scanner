# Classifier Abstention + Top-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic classification runtime that automatically confirms only safe RepViT-M1/DINOv3 decisions and otherwise returns `Unknown` with a fused Top-3 list.

**Architecture:** A new `bakery_scanner.classification` package owns immutable contracts, artifact validation, three-crop preprocessing, RepViT and DINOv3 scoring, calibrated fusion, abstention policy, evidence collection, and evaluation. The online pipeline runs RepViT first and lazily runs DINOv3 only when the direct gate abstains; calibration tooling forces both models on independent labeled evidence and never tunes from the locked acceptance set.

**Tech Stack:** Python 3.11, PyTorch 2.13.0, Torchvision 0.28.0, timm 1.0.28, dinov3 0.0.1, NumPy, Pillow, Pydantic, pytest.

**Approved design:** `docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md`

## Global Constraints

- Input is an original RGB image plus a verified one-bread `Box`; Detector and Verifier behavior are outside this implementation scope.
- Classifier artifact is exactly `repvit_m1_15plus5_v1`.
- Conditional recheck artifact is exactly `dinov3_vits16_15plus5_v1`.
- Initial runtime is `CUDA:0`, FP32, deterministic inference.
- Every inference uses 5%, 10%, and 15% padded crops in that order.
- RepViT averages three softmax vectors; DINOv3 averages three L2-normalized embeddings and normalizes again.
- DINOv3 is not executed after a RepViT direct confirmation.
- A DINOv3 confirmation requires equal RepViT/DINO Top-1 SKU plus all calibrated gates.
- Any failed gate returns `Unknown`; it never promotes a low-confidence registered SKU.
- `Unknown` normally returns exactly three unique registered SKU candidates ranked by fused probability.
- Automatic SKU precision, fallback Top-3 recall, and assisted success must each be 100% on the locked acceptance set before release.
- Acceptance data never selects model parameters, temperatures, thresholds, margins, fusion weight, or confusion pairs.
- The existing 100% requirements describe the validated locked set, not unobserved inputs.
- Missing or incompatible checkpoints, manifests, support files, calibration artifacts, non-finite vectors, and class-map mismatches fail closed.
- Thresholds and fusion weights live only in a versioned calibration artifact, never as runtime constants.
- Preserve unrelated dirty-worktree changes and do not rewrite detector code.
- This classifier worktree uses the already-installed Torch 2.13 / Torchvision
  0.28 runtime, but does not change `pyproject.toml` dependency groups while
  Detector and Verifier development is active. A later integration change must
  update all model consumer groups together and run whole-pipeline regression
  and performance validation.

---

## File Map

```text
configs/classifier_policy.yaml
    artifact paths, hashes, device, precision, preprocessing, calibration path

src/bakery_scanner/classification/contracts.py
    immutable score, candidate, decision, provenance, and timing records
src/bakery_scanner/classification/config.py
    strict path-resolved classifier configuration
src/bakery_scanner/classification/preprocess.py
    deterministic 5/10/15 percent padded crops and 224x224 tensor transform
src/bakery_scanner/classification/repvit.py
    RepViT-M1 artifact validation and three-crop scoring
src/bakery_scanner/classification/dinov3.py
    DINOv3 ViT-S/16 artifact validation and prototype scoring
src/bakery_scanner/classification/policy.py
    calibration artifact, score calibration, fusion, gates, Top-3
src/bakery_scanner/classification/runtime.py
    lazy two-model orchestration, fail-closed behavior, latency/provenance
src/bakery_scanner/classification/evidence.py
    labeled evidence schema, grouped split checks, metrics, policy selection

scripts/collect_classifier_evidence.py
    force both models over an independent labeled manifest
scripts/calibrate_classifier_policy.py
    select and save policy using grouped development evidence
scripts/evaluate_classifier_policy.py
    immutable locked-set report without parameter selection
scripts/benchmark_classifier_pipeline.py
    warm-up, p50/p95, stage latency, and DINOv3 invocation rate
```

### Task 1: Immutable Contracts, Strict Configuration, and Dependency Profile

**Files:**
- Create: `src/bakery_scanner/classification/__init__.py`
- Create: `src/bakery_scanner/classification/contracts.py`
- Create: `src/bakery_scanner/classification/config.py`
- Create: `configs/classifier_policy.yaml`
- Create: `tests/classification/test_contracts.py`
- Create: `tests/classification/test_config.py`

**Interfaces:**
- Produces: `DecisionPath`, `SkuCandidate`, `ModelScoreVector`, `ClassificationDecision`, `ModelProvenance`, `StageTimings`.
- Produces: `ClassifierConfig.load(path: Path) -> ClassifierConfig`.
- Consumes later: every runner, policy, runtime, and script imports these exact records.

- [ ] **Step 1: Write contract tests**

```python
def test_unknown_requires_exactly_three_unique_candidates():
    with pytest.raises(ValueError, match="three unique"):
        ClassificationDecision(
            decision="unknown",
            sku_id=None,
            confidence=0.4,
            decision_path=DecisionPath.UNKNOWN_TOP3,
            top3=(SkuCandidate(1, 6, 0.7), SkuCandidate(2, 6, 0.6)),
            provenance=valid_provenance(),
            timings=StageTimings(1.0, 2.0, 3.0),
        )


def test_sku_decision_has_no_top3_and_matching_path():
    result = ClassificationDecision(
        decision="sku",
        sku_id=6,
        confidence=0.98,
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=valid_provenance(),
        timings=StageTimings(1.0, 0.0, 1.0),
    )
    assert result.sku_id == 6
```

Also assert: finite scores only, SKU IDs are 1 through 20, `ModelScoreVector`
contains all 20 unique IDs in canonical order, candidates are ranks 1/2/3,
scores are in `[0, 1]`, and JSON output is canonical UTF-8.

- [ ] **Step 2: Run contract tests and confirm the missing module failure**

Run: `python -m pytest tests/classification/test_contracts.py -q`

Expected: FAIL with `ModuleNotFoundError: bakery_scanner.classification`.

- [ ] **Step 3: Implement immutable contracts**

```python
class DecisionPath(str, Enum):
    REPVIT_DIRECT = "repvit_direct"
    DINOV3_CONFIRMED = "dinov3_confirmed"
    UNKNOWN_TOP3 = "unknown_top3"


@dataclass(frozen=True, slots=True)
class ModelScoreVector:
    model_id: str
    sku_ids: tuple[int, ...]
    values: tuple[float, ...]
    score_kind: Literal["probability", "similarity"]


@dataclass(frozen=True, slots=True)
class SkuCandidate:
    rank: int
    sku_id: int
    score: float


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    repvit_artifact_id: str
    repvit_sha256: str
    dinov3_artifact_id: str
    dinov3_sha256: str
    calibration_id: str
    calibration_sha256: str
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class StageTimings:
    repvit_ms: float
    dinov3_ms: float
    total_ms: float


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    decision: Literal["sku", "unknown"]
    sku_id: int | None
    confidence: float
    decision_path: DecisionPath
    top3: tuple[SkuCandidate, ...]
    provenance: ModelProvenance
    timings: StageTimings
```

Implement `ClassificationDecision.to_json_bytes()` with exact sorted keys and
`allow_nan=False`. Do not add a fourth decision state.

The test file defines this exact valid fixture and uses it in the Step 1
examples:

```python
def valid_provenance():
    return ModelProvenance(
        repvit_artifact_id="repvit_m1_15plus5_v1",
        repvit_sha256="0" * 64,
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        dinov3_sha256="1" * 64,
        calibration_id="policy_v1",
        calibration_sha256="2" * 64,
    )
```

- [ ] **Step 4: Write configuration tests**

```python
def test_classifier_config_resolves_paths_and_pins_artifacts():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    assert config.repvit.artifact_id == "repvit_m1_15plus5_v1"
    assert config.dinov3.artifact_id == "dinov3_vits16_15plus5_v1"
    assert config.preprocess.paddings == (0.05, 0.10, 0.15)
    assert config.runtime.device == "CUDA:0"
    assert config.runtime.precision == "FP32"
```

Also test rejection of unknown YAML keys, non-SHA-256 hashes, reordered or
duplicate padding values, non-224 input size, and a calibration path inside
the locked acceptance directory.

- [ ] **Step 5: Implement strict standalone classifier configuration**

Create `configs/classifier_policy.yaml` with these exact values:

```yaml
schema_version: 1
repvit:
  artifact_id: repvit_m1_15plus5_v1
  checkpoint: ../models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt
  checkpoint_sha256: 0369c148c3b208ea41140cc220a6871367eaa8ed52b0cedfa97d39f4b2d76cfc
  manifest: ../models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.manifest.json
  manifest_sha256: f2bb1787295a76ee8b2bb049223557a87a88309038c963ea1617a3c7aacf1e56
dinov3:
  artifact_id: dinov3_vits16_15plus5_v1
  weights: ../models/dinov3_vits16_15plus5_v1/dinov3_vits16_pretrain_lvd1689m-08c60483.pth
  weights_sha256: 08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d
  support: ../models/dinov3_vits16_15plus5_v1/dinov3_vits16_15plus5_v1_support.pt
  support_sha256: f395e38a93905a2a4e53522b8632274813604f1c5f98f4baff0cbfdf91431aea
preprocess:
  input_size: 224
  paddings: [0.05, 0.10, 0.15]
runtime:
  device: CUDA:0
  precision: FP32
calibration:
  artifact: ../artifacts/classification/policy_v1.json
```

Keep this configuration separate from `ScannerConfig` so detector work remains
loadable before classifier calibration exists.

- [ ] **Step 6: Preserve shared dependency declarations during staged work**

Use the already-installed Torch 2.13 / Torchvision 0.28 runtime for this
worktree's tests. Do not modify `pyproject.toml` or the Detector/Verifier
dependency groups while their implementation is active. A later integration
change must declare one compatible runtime for Detector, Verifier, RepViT, and
DINOv3, then validate the full pipeline.

- [ ] **Step 7: Run Task 1 tests**

Run: `python -m pytest tests/classification/test_contracts.py tests/classification/test_config.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```powershell
git add configs/classifier_policy.yaml src/bakery_scanner/classification/__init__.py src/bakery_scanner/classification/contracts.py src/bakery_scanner/classification/config.py tests/classification/test_contracts.py tests/classification/test_config.py
git commit -m "feat: define classifier runtime contracts"
```

### Task 2: Three-Crop Preprocessing and RepViT-M1 Runner

**Files:**
- Create: `src/bakery_scanner/classification/preprocess.py`
- Create: `src/bakery_scanner/classification/repvit.py`
- Create: `tests/classification/test_preprocess.py`
- Create: `tests/classification/test_repvit.py`

**Interfaces:**
- Consumes: `Box`, `ClassifierConfig`, `ModelScoreVector`.
- Produces: `make_padded_crops(image, box, paddings) -> tuple[Image.Image, ...]`.
- Produces: `RepVitM1Runner.load(config, *, device: torch.device | None = None) -> RepVitM1Runner`.
- Produces: `RepVitM1Runner.score(crops) -> ModelScoreVector`.

- [ ] **Step 1: Write preprocessing tests**

```python
def test_three_padded_crops_are_ordered_and_clipped():
    image = Image.new("RGB", (100, 80))
    crops = make_padded_crops(image, Box(0, 0, 40, 20), (0.05, 0.10, 0.15))
    assert len(crops) == 3
    assert [crop.size for crop in crops] == [(42, 21), (44, 22), (46, 23)]
```

Define expansion as `padding * box.width` horizontally and
`padding * box.height` vertically, split equally across both sides, with
floor on left/top and ceil on right/bottom before clipping. Test a centered
box, all four image edges, invalid image mode conversion, and deterministic
pixel equality.

- [ ] **Step 2: Run preprocessing tests and confirm failure**

Run: `python -m pytest tests/classification/test_preprocess.py -q`

Expected: FAIL because `preprocess.py` is absent.

- [ ] **Step 3: Implement crops and transform**

```python
def make_padded_crops(
    image: Image.Image,
    box: Box,
    paddings: tuple[float, ...],
) -> tuple[Image.Image, ...]:
    rgb = image.convert("RGB")
    return tuple(_crop_one(rgb, box, padding) for padding in paddings)


def build_transform(input_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize((input_size, input_size), antialias=True),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
```

- [ ] **Step 4: Write RepViT runner tests with an injected fake model**

```python
def test_repvit_averages_three_softmax_vectors():
    logits = torch.stack([
        torch.arange(20, dtype=torch.float32),
        torch.arange(19, -1, -1, dtype=torch.float32),
        torch.zeros(20, dtype=torch.float32),
    ])
    runner = RepVitM1Runner(
        model=FixedLogitModel(logits),
        sku_ids=tuple(range(1, 21)),
        transform=build_transform(224),
        model_id="repvit_m1_15plus5_v1",
        device=torch.device("cpu"),
    )
    crops = tuple(Image.new("RGB", (32, 32), color) for color in ("red", "green", "blue"))
    result = runner.score(crops)
    assert result.model_id == "repvit_m1_15plus5_v1"
    assert result.score_kind == "probability"
    assert sum(result.values) == pytest.approx(1.0)
    expected = logits.softmax(dim=1).mean(dim=0).tolist()
    assert result.values == pytest.approx(expected)
```

`FixedLogitModel` stores the provided `(3, 20)` tensor and returns it after
asserting the incoming batch shape is `(3, 3, 224, 224)`.

Also test inference mode, batch shape `(3, 3, 224, 224)`, 20-logit
requirement, NaN rejection, checkpoint class-index order, manifest/checkpoint
class-map equality, and SHA mismatch failure before model construction.

- [ ] **Step 5: Implement RepViT loading and scoring**

```python
model = timm.create_model("repvit_m1", pretrained=False, num_classes=20)
checkpoint = torch.load(path, map_location="cpu", weights_only=True)
model.load_state_dict(checkpoint["state_dict"], strict=True)
model.to(device).eval()

with torch.inference_mode():
    logits = model(batch.to(device))
    probabilities = logits.softmax(dim=1).mean(dim=0)
```

Compute configured SHA-256 values by streaming files in 1 MiB chunks. Reject
any class index other than `{1: 0, ..., 20: 19}`.

- [ ] **Step 6: Add a real artifact CPU smoke test**

```python
@pytest.mark.integration
def test_real_repvit_artifact_loads_twenty_classes():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    runner = RepVitM1Runner.load(config, device=torch.device("cpu"))
    assert runner.sku_ids == tuple(range(1, 21))
```

The test may skip only when the configured model file is absent; it must not
skip for a hash or schema mismatch.

- [ ] **Step 7: Run Task 2 tests**

Run: `python -m pytest tests/classification/test_preprocess.py tests/classification/test_repvit.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```powershell
git add src/bakery_scanner/classification/preprocess.py src/bakery_scanner/classification/repvit.py tests/classification/test_preprocess.py tests/classification/test_repvit.py
git commit -m "feat: score verified crops with RepViT"
```

### Task 3: DINOv3 ViT-S/16 Prototype Rechecker

**Files:**
- Create: `src/bakery_scanner/classification/dinov3.py`
- Create: `tests/classification/test_dinov3.py`

**Interfaces:**
- Consumes: `ClassifierConfig`, the Task 2 crop transform, `ModelScoreVector`.
- Produces: `DinoV3Rechecker.load(config, *, device: torch.device | None = None) -> DinoV3Rechecker`.
- Produces: `DinoV3Rechecker.score(crops) -> ModelScoreVector`.

- [ ] **Step 1: Write DINOv3 tests using an injected fake encoder**

```python
def test_dinov3_averages_normalized_embeddings_then_scores_prototypes():
    embeddings = torch.zeros((3, 384), dtype=torch.float32)
    embeddings[0, 0] = 1
    embeddings[1, 1] = 1
    embeddings[2, 0:2] = 1
    prototypes = torch.eye(384, dtype=torch.float32)[:20]
    runner = DinoV3Rechecker(
        encoder=FixedEncoder(embeddings),
        prototypes=prototypes,
        sku_ids=tuple(range(1, 21)),
        transform=build_transform(224),
        model_id="dinov3_vits16_15plus5_v1",
        device=torch.device("cpu"),
    )
    crops = tuple(Image.new("RGB", (32, 32), color) for color in ("red", "green", "blue"))
    result = runner.score(crops)
    assert result.score_kind == "similarity"
    expected_embedding = functional.normalize(
        functional.normalize(embeddings, dim=1).mean(dim=0),
        dim=0,
    )
    assert result.values == pytest.approx((prototypes @ expected_embedding).tolist())
```

`FixedEncoder` stores the provided `(3, 384)` tensor and returns it after
asserting the incoming batch shape is `(3, 3, 224, 224)`.

Also test normalization before and after averaging, exact `(20, 384)`
prototype shape, unit-length prototype validation, support/RepViT class-map
equality, support-declared checkpoint hash equality, non-finite rejection, and
transform metadata equality with the runtime transform.

- [ ] **Step 2: Run tests and confirm the missing module failure**

Run: `python -m pytest tests/classification/test_dinov3.py -q`

Expected: FAIL because `dinov3.py` is absent.

- [ ] **Step 3: Implement strict DINOv3 loading**

```python
model = vit_small(
    patch_size=16,
    n_storage_tokens=4,
    mask_k_bias=True,
    layerscale_init=1e-5,
)
weights = torch.load(weights_path, map_location="cpu", weights_only=True)
support = torch.load(support_path, map_location="cpu", weights_only=True)
model.load_state_dict(weights, strict=True)
model.to(device).eval()
```

Validate `support["schema_version"]`, `support["dino_checkpoint"]`,
`support["transform"]`, 20-class map order, prototypes, and all configured
hashes before moving the model to CUDA.

When `device` is omitted, convert configured `CUDA:0` to PyTorch's canonical
`torch.device("cuda:0")`; the optional override exists only for artifact
validation tests and explicit offline CPU tools.

- [ ] **Step 4: Implement three-crop embedding scoring**

```python
with torch.inference_mode():
    embeddings = functional.normalize(model(batch.to(device)), dim=1)
    mean_embedding = functional.normalize(embeddings.mean(dim=0), dim=0)
    similarities = prototypes.to(device) @ mean_embedding
```

Return CPU float values in canonical SKU order and synchronize CUDA before
recording timing in the later runtime task.

- [ ] **Step 5: Add a real artifact CPU smoke test**

Load the actual weights and support, assert 20 SKU prototypes with dimension
384, run one synthetic RGB image, and assert exactly 20 finite similarities.
Skip only when the configured model files are absent.

- [ ] **Step 6: Run Task 3 tests**

Run: `python -m pytest tests/classification/test_dinov3.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/bakery_scanner/classification/dinov3.py tests/classification/test_dinov3.py
git commit -m "feat: add DINOv3 prototype recheck"
```

### Task 4: Versioned Calibration, Fusion, and Abstention Policy

**Files:**
- Create: `src/bakery_scanner/classification/policy.py`
- Create: `tests/classification/test_policy.py`

**Interfaces:**
- Produces: `PolicyCalibration.from_json_bytes(payload) -> PolicyCalibration`.
- Produces: `calibrate_repvit(scores, temperature) -> tuple[float, ...]`.
- Produces: `calibrate_dinov3(scores, temperature) -> tuple[float, ...]`.
- Produces: `fuse_probabilities(repvit, dino, alpha) -> tuple[float, ...]`.
- Produces: `DecisionPolicy.direct(repvit) -> ClassificationDecision | None`.
- Produces: `DecisionPolicy.after_recheck(repvit, dino) -> ClassificationDecision`.
- Produces: `DecisionPolicy.dino_failure(repvit) -> ClassificationDecision`.

- [ ] **Step 1: Write calibration artifact tests**

```python
def test_calibration_is_canonical_and_bound_to_artifacts():
    calibration = PolicyCalibration(
        schema_version=1,
        calibration_id="policy_v1",
        repvit_artifact_id="repvit_m1_15plus5_v1",
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        repvit_temperature=1.25,
        dinov3_temperature=0.75,
        alpha=0.60,
        direct_threshold=0.92,
        direct_margin=0.30,
        dino_threshold=0.85,
        fused_margin=0.20,
        evidence_sha256="0" * 64,
    )
    assert PolicyCalibration.from_json_bytes(calibration.to_json_bytes()) == calibration
```

Reject non-canonical JSON, missing/extra keys, invalid hashes, temperatures
not greater than zero, values outside `[0, 1]`, wrong artifact IDs, and NaN.

- [ ] **Step 2: Write fusion and decision tests**

```python
def test_direct_gate_skips_top3_when_threshold_and_margin_pass():
    result = policy().direct(repvit_scores(top1=0.95, top2=0.20))
    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert result.top3 == ()


def test_disagreement_abstains_with_three_fused_candidates():
    result = policy().after_recheck(
        repvit_scores(order=(6, 5, 19)),
        dino_scores(order=(5, 6, 19)),
    )
    assert result.decision == "unknown"
    assert [candidate.sku_id for candidate in result.top3] == [6, 5, 19]
```

Also test threshold equality, margin equality, agreement with weak DINO,
agreement with weak fused margin, deterministic SKU-ID tie breaking, alpha 0
and 1, exactly three unique candidates, and DINO failure returning RepViT
Top-3 with `unknown_top3`.

- [ ] **Step 3: Run policy tests and confirm failure**

Run: `python -m pytest tests/classification/test_policy.py -q`

Expected: FAIL because `policy.py` is absent.

- [ ] **Step 4: Implement calibration and fusion**

```python
def calibrate_repvit(probabilities, temperature):
    logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature
    return _softmax(logits)


def calibrate_dinov3(similarities, temperature):
    return _softmax(np.asarray(similarities, dtype=np.float64) / temperature)


def fuse_probabilities(repvit, dino, alpha):
    fused_logits = alpha * np.log(np.clip(repvit, 1e-12, 1.0))
    fused_logits += (1.0 - alpha) * np.log(np.clip(dino, 1e-12, 1.0))
    return _softmax(fused_logits)
```

Use float64 for policy math and convert to Python floats only at immutable
contract boundaries.

- [ ] **Step 5: Implement fail-closed gates**

```python
def after_recheck(self, repvit_scores, dino_scores):
    repvit = calibrate_repvit(repvit_scores.values, self.calibration.repvit_temperature)
    dino = calibrate_dinov3(dino_scores.values, self.calibration.dinov3_temperature)
    fused = fuse_probabilities(repvit, dino, self.calibration.alpha)
    if (
        _top1_id(repvit) == _top1_id(dino)
        and max(dino) >= self.calibration.dino_threshold
        and _margin(fused) >= self.calibration.fused_margin
    ):
        return _confirmed_decision(fused)
    return _unknown_with_top3(fused)
```

`direct()` uses both direct threshold and direct margin. Do not treat a
successful DINO gate as permission to accept disagreeing Top-1 IDs.

- [ ] **Step 6: Run Task 4 tests**

Run: `python -m pytest tests/classification/test_policy.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add src/bakery_scanner/classification/policy.py tests/classification/test_policy.py
git commit -m "feat: calibrate and fuse classifier decisions"
```

### Task 5: Lazy Online Classification Runtime

**Files:**
- Create: `src/bakery_scanner/classification/runtime.py`
- Create: `tests/classification/test_runtime.py`

**Interfaces:**
- Consumes: image, verified `Box`, config, RepViT runner, DINO runner, policy.
- Produces: `ClassifierPipeline.load(config_path: Path) -> ClassifierPipeline`.
- Produces: `ClassifierPipeline.infer(image: Image.Image, box: Box) -> ClassificationDecision`.

- [ ] **Step 1: Write orchestration tests with counting fakes**

```python
def test_direct_repvit_confirmation_never_calls_dino():
    dino = CountingDino()
    result = pipeline(repvit=confident_repvit(), dino=dino).infer(image(), box())
    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert dino.call_count == 0


def test_ambiguous_repvit_calls_dino_once_and_can_abstain():
    dino = CountingDino(scores=disagreeing_dino())
    result = pipeline(repvit=ambiguous_repvit(), dino=dino).infer(image(), box())
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert len(result.top3) == 3
    assert dino.call_count == 1
```

Also test three crops are reused by both models, DINO load is lazy, direct and
recheck confidence meanings, model provenance/hashes, per-stage timing,
CUDA synchronization via an injected clock, and canonical JSON.

- [ ] **Step 2: Write failure-path tests**

```python
def test_dino_failure_returns_unknown_and_repvit_top3():
    result = pipeline(repvit=ambiguous_repvit(), dino=FailingDino()).infer(image(), box())
    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert [candidate.rank for candidate in result.top3] == [1, 2, 3]
```

Artifact load failures and missing calibration must fail initialization;
only an inference-time DINO failure may degrade to RepViT-only Unknown Top-3.
Record the recheck failure code in provenance without exposing a traceback in
the canonical result.

- [ ] **Step 3: Run runtime tests and confirm failure**

Run: `python -m pytest tests/classification/test_runtime.py -q`

Expected: FAIL because `runtime.py` is absent.

- [ ] **Step 4: Implement lazy orchestration**

```python
def infer(self, image, box):
    started = self.clock()
    crops = make_padded_crops(image, box, self.config.preprocess.paddings)
    repvit_scores = self.repvit.score(crops)
    direct = self.policy.direct(repvit_scores)
    if direct is not None:
        return self._with_runtime_metadata(direct, started)
    try:
        dino_scores = self.dino.score(crops)
    except DinoInferenceError as exc:
        return self._with_failure_metadata(self.policy.dino_failure(repvit_scores), exc, started)
    return self._with_runtime_metadata(
        self.policy.after_recheck(repvit_scores, dino_scores),
        started,
    )
```

Catch only the package's explicit `DinoInferenceError`; do not convert
programming errors into `Unknown`.

- [ ] **Step 5: Run Task 5 tests**

Run: `python -m pytest tests/classification/test_runtime.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add src/bakery_scanner/classification/runtime.py tests/classification/test_runtime.py
git commit -m "feat: orchestrate conditional product recheck"
```

### Task 6: Independent Evidence, Grouped Calibration, and Locked Evaluation

**Files:**
- Create: `src/bakery_scanner/classification/evidence.py`
- Create: `scripts/collect_classifier_evidence.py`
- Create: `scripts/calibrate_classifier_policy.py`
- Create: `scripts/evaluate_classifier_policy.py`
- Create: `tests/classification/test_evidence.py`
- Create: `tests/classification/test_calibration_selection.py`

**Interfaces:**
- Produces: `EvidenceInput`, `EvidenceRow`, `ClassificationMetrics`.
- Produces: `load_evidence_manifest(path) -> tuple[EvidenceInput, ...]`.
- Produces: `select_policy(rows, folds=5, seed=20260727) -> PolicyCalibration`.
- Produces: `evaluate_policy(rows, calibration) -> ClassificationMetrics`.
- Produces JSONL evidence and canonical JSON calibration/evaluation artifacts.

- [ ] **Step 1: Define and test the evidence manifest**

Each input JSONL row has exact keys:

```json
{
  "sample_id": "cal-000001",
  "capture_group": "batch03:scene0042",
  "image_path": "images/cal-000001.png",
  "box_xyxy": [100, 200, 300, 420],
  "registered": true,
  "sku_id": 6,
  "role": "development"
}
```

`sku_id` is 1 through 20 for registered rows and `null` for unregistered
rows. Roles are exactly `development` or `locked_acceptance`. Reject duplicate
sample IDs, duplicate image SHA-256 values, missing groups, boxes outside image
bounds, registered/null mismatches, and any image hash present in the RepViT
training manifest.

- [ ] **Step 2: Write metric tests**

```python
def test_metrics_separate_precision_coverage_top3_and_assisted_success():
    metrics = evaluate_rows([
        auto_correct(6),
        unknown_with_top3(truth=5, candidates=(6, 5, 19)),
        unknown_with_top3(truth=19, candidates=(6, 5, 19)),
    ])
    assert metrics.auto_precision == 1.0
    assert metrics.auto_coverage == pytest.approx(1 / 3)
    assert metrics.fallback_top3_recall == 1.0
    assert metrics.assisted_success == 1.0
```

Define zero denominators explicitly: no auto decisions yields
`auto_precision=None`; no registered Unknown rows yields
`fallback_top3_recall=None`. Release-gate code must require the applicable
metric to equal 1.0 and must not treat `None` as passing.

- [ ] **Step 3: Write grouped policy-selection tests**

Use synthetic rows where a threshold that appears successful in the target
group fails when selected from other groups. Assert each fold policy uses
only the other four groups. Include unregistered rows as automatic-SKU errors
but exclude them from Top-3 recall.

- [ ] **Step 4: Implement evidence collection**

`collect_classifier_evidence.py` loads the classifier config and manifest,
forces both model runners for every development/acceptance sample, and writes:

```json
{
  "sample_id": "cal-000001",
  "capture_group": "batch03:scene0042",
  "registered": true,
  "sku_id": 6,
  "role": "development",
  "image_sha256": "64-lowercase-hex",
  "repvit_values": [0.01, 0.02],
  "dinov3_values": [0.11, 0.12],
  "repvit_artifact_id": "repvit_m1_15plus5_v1",
  "dinov3_artifact_id": "dinov3_vits16_15plus5_v1"
}
```

The real vectors contain exactly 20 finite values. The script writes only
after all rows validate, using a temporary sibling file followed by
`os.replace`.

- [ ] **Step 5: Implement grouped calibration selection**

Use `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20260727)`,
stratified by registered SKU ID or `unregistered`, grouped by
`capture_group`.

Use these deterministic candidate grids:

```python
TEMPERATURES = (0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00, 4.00)
ALPHAS = tuple(index / 20 for index in range(21))
```

Select parameters in this deterministic order for each grouped training
partition:

1. Select each model temperature independently by minimum multiclass negative
   log likelihood, with the lower temperature breaking ties.
2. Select `alpha` by the fewest registered-sample Top-3 misses over all
   samples, then fused negative log likelihood, then the lower alpha.
3. Build direct-gate candidate pairs from the Pareto frontier of observed
   `(RepViT Top-1 probability, RepViT margin)` values plus `(1.0, 1.0)`.
4. For each direct pair, build recheck-gate candidate pairs from the Pareto
   frontier of observed `(DINO Top-1 probability, fused margin)` values plus
   `(1.0, 1.0)`.
5. Select the complete gate tuple lexicographically by:

```text
auto_errors
fallback_top3_misses
assisted_failures
-auto_confirmed_count
dino_invocation_count
threshold tuple
```

The Pareto frontier contains only pairs for which no other pair is less
restrictive in both dimensions. Evaluate candidates using vectorized NumPy
boolean arrays; do not enumerate the Cartesian product of every raw score
value.

Pool held-out fold predictions to produce cross-fit development metrics, then
fit one final artifact on all development rows. Abort without writing an
artifact if cross-fit automatic errors, fallback misses, or assisted failures
are nonzero.

- [ ] **Step 6: Implement locked evaluation without selection**

`evaluate_classifier_policy.py` accepts only rows with
`role=locked_acceptance`, loads an existing calibration artifact, evaluates it
once, and writes a report containing artifact hashes, evidence hash, overall
metrics, per-SKU metrics, base-15/incremental-5 metrics, registered/unregistered
metrics, and exact failure sample IDs.

The command exits nonzero when any applicable release metric differs from
1.0. It never writes a replacement calibration artifact.

- [ ] **Step 7: Run Task 6 tests**

Run: `python -m pytest tests/classification/test_evidence.py tests/classification/test_calibration_selection.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

```powershell
git add src/bakery_scanner/classification/evidence.py scripts/collect_classifier_evidence.py scripts/calibrate_classifier_policy.py scripts/evaluate_classifier_policy.py tests/classification/test_evidence.py tests/classification/test_calibration_selection.py
git commit -m "feat: calibrate classifier abstention policy"
```

### Task 7: Performance Benchmark, Documentation, and End-to-End Verification

**Files:**
- Create: `scripts/benchmark_classifier_pipeline.py`
- Create: `tests/classification/test_benchmark.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md`

**Interfaces:**
- Consumes: `ClassifierPipeline`, a labeled or unlabeled benchmark manifest.
- Produces: canonical benchmark JSON with warm-up count, image count, p50/p95,
  per-stage latency, DINO invocation rate, device, precision, and artifact
  hashes.

- [ ] **Step 1: Write benchmark aggregation tests**

```python
def test_benchmark_reports_percentiles_and_conditional_rate():
    report = aggregate_benchmark([
        timing(total=10, repvit=4, dino=0),
        timing(total=20, repvit=4, dino=12),
        timing(total=30, repvit=5, dino=18),
    ])
    assert report.dino_invocation_rate == pytest.approx(2 / 3)
    assert report.total_p50_ms == 20
    assert report.total_p95_ms == pytest.approx(29)
```

Use NumPy's documented linear percentile method and assert warm-up rows are
excluded.

- [ ] **Step 2: Implement the benchmark command**

Command:

```powershell
python scripts/benchmark_classifier_pipeline.py `
  --config configs/classifier_policy.yaml `
  --manifest datasets/classification/benchmark_manifest.jsonl `
  --warmup 20 `
  --output artifacts/classification/benchmark.json
```

Synchronize CUDA immediately before starting and ending each measured stage.
Do not claim the 0.5-second full-pipeline target from classifier-only timing.

- [ ] **Step 3: Update documentation with executable commands**

Document these commands and their required input roles:

```powershell
python scripts/collect_classifier_evidence.py --config configs/classifier_policy.yaml --manifest datasets/classification/development_manifest.jsonl --output artifacts/classification/development_evidence.jsonl
python scripts/calibrate_classifier_policy.py --evidence artifacts/classification/development_evidence.jsonl --output artifacts/classification/policy_v1.json
python scripts/evaluate_classifier_policy.py --evidence artifacts/classification/locked_evidence.jsonl --calibration artifacts/classification/policy_v1.json --output artifacts/classification/locked-report.json
python scripts/benchmark_classifier_pipeline.py --config configs/classifier_policy.yaml --manifest datasets/classification/benchmark_manifest.jsonl --warmup 20 --output artifacts/classification/benchmark.json
```

State explicitly that the current model packages alone do not prove 100%
automatic precision or Top-3 recall; independent development and locked data
are required.

- [ ] **Step 4: Run classification tests**

Run: `python -m pytest tests/classification -q`

Expected: PASS with zero failures.

- [ ] **Step 5: Run existing contract and configuration regression tests**

Run: `python -m pytest tests/test_contracts.py tests/test_config.py tests/test_preprocess.py -q`

Expected: PASS with zero failures.

- [ ] **Step 6: Run real artifact smoke tests**

Run: `python -m pytest tests/classification/test_repvit.py tests/classification/test_dinov3.py -m integration -q`

Expected: PASS on the current workspace artifacts.

- [ ] **Step 7: Verify command help and documentation**

```powershell
python scripts/collect_classifier_evidence.py --help
python scripts/calibrate_classifier_policy.py --help
python scripts/evaluate_classifier_policy.py --help
python scripts/benchmark_classifier_pipeline.py --help
rg -n "auto_precision|fallback_top3_recall|assisted_success|repvit_m1_15plus5_v1|dinov3_vits16_15plus5_v1" README.md docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md
git diff --check
```

Expected: all commands exit zero, required terms are present, and no whitespace
errors are reported.

- [ ] **Step 8: Record the data-dependent completion boundary**

If no independent development and locked manifests exist, finish code
verification but report calibration, 100% accuracy acceptance, and performance
acceptance as blocked by missing evidence. Do not create thresholds, metrics,
or benchmark values.

- [ ] **Step 9: Commit Task 7**

```powershell
git add scripts/benchmark_classifier_pipeline.py tests/classification/test_benchmark.py README.md docs/superpowers/specs/2026-07-27-classifier-abstention-top3-design.md
git commit -m "docs: document classifier acceptance workflow"
```
