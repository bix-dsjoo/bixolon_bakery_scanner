# ConvNeXt-Tiny Verifier Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unexecuted MobileNetV4 verifier with the repository-mandated ConvNeXt-Tiny verifier, then finish the approved D-FINE-N 640 + verifier GPU bundle without mixing verifier backbones.

**Architecture:** D-FINE-N 640 detector OOF remains unchanged. The verifier keeps the existing four-state crop contract (`INVALID`, `EXACTLY_ONE`, `PARTIAL`, `MULTIPLE`), deterministic preprocessing, receipt schema, held-out-fold restriction, and cross-fit interface; only the pinned timm backbone becomes `convnext_tiny`. MobileNetV4 verifier evidence is incompatible and may not be reused.

**Tech Stack:** Python 3.11, PyTorch, timm 1.0.28 (`convnext_tiny`), CUDA 12.8, RTX 5080, pytest.

## Global Constraints

- Root `AGENTS.md` mandates `D-FINE-N → ConvNeXt-Tiny verifier → RepViT-M1 → conditional DINOv3`; source, runners, receipts, selection, and bundle manifests must agree.
- Do not interrupt detector fold 4. Train and infer models only on RTX 5080 `cuda:0`; CPU is only for validation and tests.
- Use only staged 299 images / 1,410 boxes and the current grouped five-fold split. Do not add physical recaptures or claim operational 100% detection.
- Preserve source coordinates; `PARTIAL`, `MULTIPLE`, and unresolved results are not final bread counts.
- Do not overwrite/reuse MobileNetV4 verifier artifacts. Every new verifier receipt must name `convnext_tiny`.

---

### Task 1: Pin verifier source and runners to ConvNeXt-Tiny

**Files:**

- Modify: `src/bakery_scanner/verifier/model.py`
- Modify: `scripts/run_verifier_oof.ps1`
- Modify: `scripts/train_dfine640_verifier_final.ps1`
- Modify: `tests/test_verifier_model.py`
- Modify: `tests/test_detector_bundle.py`

**Interfaces:**

```python
MODEL_NAME = "convnext_tiny"

def build_convnext_tiny_verifier(*, pretrained: bool = True) -> nn.Module:
    """Create the pinned ConvNeXt-Tiny classifier with exactly four logits."""
```

- [ ] **Step 1: Write failing identity tests.**

```python
def test_verifier_uses_convnext_tiny():
    assert verifier_model.MODEL_NAME == "convnext_tiny"
    model = verifier_model.build_convnext_tiny_verifier(pretrained=False)
    assert model(torch.zeros(2, 3, 224, 224)).shape == (2, 4)

def test_mobile_net_receipt_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="convnext_tiny"):
        verifier_model.validate_completed_fold_receipt(
            receipt_with("mobilenetv4_conv_small")
        )
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_verifier_model.py -q`

Expected: FAIL because current source declares `mobilenetv4_conv_small` and lacks the ConvNeXt builder.

- [ ] **Step 3: Substitute the backbone without changing the four-state contract.**

Set `MODEL_NAME = "convnext_tiny"`; construct `timm.create_model("convnext_tiny", pretrained=pretrained, num_classes=4)`; retain RGB 224×224 preprocessing, four-logit validation, deterministic seed, and `cuda:0` enforcement. Update model help/receipt error text to ConvNeXt-Tiny.

- [ ] **Step 4: Update runners and bundle checks.**

Set `$ModelName = "convnext_tiny"` in both PowerShell runners; reject completed-fold or final-bundle receipts whose `model_name` differs. Retain existing hash, held-out-ID, class-order, preprocessing, and device checks.

- [ ] **Step 5: Verify and commit.**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_verifier_model.py tests/test_detector_bundle.py -q
[scriptblock]::Create((Get-Content -Raw scripts/run_verifier_oof.ps1)) | Out-Null
[scriptblock]::Create((Get-Content -Raw scripts/train_dfine640_verifier_final.ps1)) | Out-Null
git add src/bakery_scanner/verifier/model.py scripts/run_verifier_oof.ps1 scripts/train_dfine640_verifier_final.ps1 tests/test_verifier_model.py tests/test_detector_bundle.py
git commit -m "fix: align verifier with convnext tiny contract"
```

### Task 2: Reject incompatible verifier provenance in policy and bundle consumers

**Files:**

- Modify: `src/bakery_scanner/detectors/dfine640_selection.py`
- Modify: `src/bakery_scanner/detectors/bundle.py`
- Modify: `tests/test_dfine640_selection.py`
- Modify: `tests/test_detector_bundle.py`

**Interfaces:**

```python
EXPECTED_VERIFIER_MODEL_NAME = "convnext_tiny"

def validate_verifier_provenance(receipt: Mapping[str, object]) -> None:
    """Raise unless a receipt declares the required ConvNeXt-Tiny verifier."""
```

- [ ] **Step 1: Write failing consumer tests.**

```python
def test_selection_rejects_mobile_net_receipt():
    with pytest.raises(ValueError, match="convnext_tiny"):
        load_verified_verifier_artifact(receipt_with("mobilenetv4_conv_small"))

def test_bundle_requires_convnext_provenance(tmp_path):
    write_otherwise_valid_bundle(
        tmp_path, verifier_model_name="mobilenetv4_conv_small"
    )
    with pytest.raises(ValueError, match="convnext_tiny"):
        validate_final_bundle(tmp_path)
```

- [ ] **Step 2: Confirm RED.**

Run: `python -m pytest tests/test_dfine640_selection.py tests/test_detector_bundle.py -q`

- [ ] **Step 3: Enforce provenance at every consumer boundary.**

Require exactly `convnext_tiny` when loading verifier OOF receipts for cross-fit selection and final-bundle manifests. Preserve all existing receipt/hash validation and name both actual and expected model in errors.

- [ ] **Step 4: Verify and commit.**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_dfine640_selection.py tests/test_detector_bundle.py tests/test_verifier_model.py -q
git add src/bakery_scanner/detectors/dfine640_selection.py src/bakery_scanner/detectors/bundle.py tests/test_dfine640_selection.py tests/test_detector_bundle.py
git commit -m "fix: bind selection to convnext verifier provenance"
```

### Task 3: Execute and audit ConvNeXt-Tiny GPU evidence

**Files:**

- Generate: `artifacts/box_system/verifiers/convnext_tiny-seed20260724-fold{0..4}/`
- Generate: `artifacts/box_system/reports/dfine640_verifier_development.json`
- Generate: final bundle under `artifacts/box_system/final/`

- [ ] **Step 1: Finish and audit detector fold 4.**

Run:

```powershell
$env:PYTHONPATH='src'
python scripts/select_dfine640_verifier.py --validate-detector-fold 4 --config configs/box_system.yaml
```

Expected: `{"fold": 4, "status": "detector_fold_validated"}` and five valid detector OOF folds.

- [ ] **Step 2: Train five ConvNeXt-Tiny verifier OOF folds sequentially on GPU.**

Run: `powershell -ExecutionPolicy Bypass -File scripts/run_verifier_oof.ps1`

Expected: exactly five completed `convnext_tiny-seed20260724-fold*` receipts with GPU, hash, four-state class-order, and held-out-ID evidence.

- [ ] **Step 3: Cross-fit policy and inspect immutable development-only report.**

Run:

```powershell
$env:PYTHONPATH='src'
python scripts/select_dfine640_verifier.py --config configs/box_system.yaml --output artifacts/box_system/reports/dfine640_verifier_development.json
```

Expected: each target fold selects policy only from other folds; report includes misses, duplicates, merges, splits, invalid false positives, scenario strata, all hashes, and `operational_guarantee: false`.

- [ ] **Step 4: Train full-data D-FINE-N 640 + ConvNeXt-Tiny and run a GPU smoke inference.**

Run: `powershell -ExecutionPolicy Bypass -File scripts/train_dfine640_verifier_final.ps1`

Expected: manifest validates staged `299/1410`, declares `convnext_tiny`, records GPU/runtime metadata, and smoke inference preserves original bounds with four probabilities summing to one within `1e-6`.

- [ ] **Step 5: Final verification.**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_detector_bundle.py tests/test_verifier_model.py tests/test_dfine640_selection.py -q
git diff --check
git status --short
```

## Completion Evidence

- Source, runners, receipts, selection, and final bundle consistently declare `convnext_tiny`; MobileNetV4 verifier artifacts are rejected.
- Detector folds 0–4 and ConvNeXt-Tiny verifier folds 0–4 pass hash and held-out-ID audits.
- Cross-fit has no target-fold self-calibration; the report is development-only.
- Final GPU bundle validates and completes one-image source-coordinate smoke inference.
