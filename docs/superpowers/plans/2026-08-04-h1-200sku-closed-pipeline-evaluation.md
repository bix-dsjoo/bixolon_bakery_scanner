# H1 200-SKU Closed Pipeline Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the 200-SKU six-real-shot H1 classification pipeline with calibrated `Unknown` decisions on a locked GT-box cohort.

**Architecture:** Extract fresh 200-SKU calibration and locked features from the original image identities because the previous all-SKU calibration cache is zero-valued. Fit frozen-RepViT H1 with six real support images per SKU; use calibration only to freeze the direct gate and conditional DINOv3 fusion policy, then evaluate the locked cohort once.

**Tech Stack:** Python, PyTorch CPU, NumPy memory-mapped feature arrays, RepViT-M1, DINOv3 ViT-S/16, JSON receipts.

## Global Constraints

- The catalog is all 200 RPC SKUs, with exactly six `train2019` images per SKU selected by `div`, seed `101`.
- Calibration and locked image identities must be distinct from each other and from every support identity.
- All cache rows must have non-zero RepViT and DINOv3 feature norms before fitting.
- Detector is excluded: GT boxes are supplied; no detector claim is permitted.
- Direct gate accepts only calibration-correct H1 predictions; all other crops run DINOv3.
- Fusion accepts only calibration-correct consensus predictions; all remaining crops are `Unknown`.
- Raw data, generated feature caches, and full predictions remain under `C:\workspace\rpc_fewshot_runs`.

---

### Task 1: Materialize fresh all-SKU calibration and locked feature cohorts

**Files:**
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\materialize_h1_200sku_calibration_features.py`
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\materialize_h1_200sku_locked_features.py`
- Test: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\test_h1_closed_pipeline_common.py`

**Interfaces:**
- Consumes: `resolved_inputs.json`, `calibration_ground_truth_v2.json`, and `locked_ground_truth_v2.json`.
- Produces: two verified oracle-feature manifests with 36,852 calibration rows and 294,333 locked rows.

- [ ] **Step 1: Assert selected identities are disjoint**

```python
require_disjoint_identities(
    train_ids=train_support_ids,
    calibration_ids=calibration_ids,
    locked_ids=locked_ids,
)
```

- [ ] **Step 2: Extract with exact hash-verified RepViT and DINOv3 artifacts**

```python
artifacts = ResearchArtifacts.from_paths(repvit_path, dino_path)
extract_oracle_features(index, artifacts, output, batch_size=16)
```

- [ ] **Step 3: Validate non-zero features before downstream use**

```python
require_nonzero_feature_rows(repvit_rows, label="calibration RepViT")
require_nonzero_feature_rows(dino_rows, label="calibration DINOv3")
```

### Task 2: Fit the six-shot H1 head and freeze gate and fusion policy

**Files:**
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\run_h1_closed_pipeline_200sku.py`
- Read: `src/bakery_scanner/experiments/rpc_research_worker.py`

**Interfaces:**
- Consumes: six-shot support prefix, fresh calibration query features.
- Produces: a 200-way H1 linear head and immutable gate/fusion parameters in the receipt.

- [ ] **Step 1: Train only the H1 linear head on frozen 384-D RepViT features**

```python
model = torch.nn.Linear(384, 200)
loss = F.cross_entropy(model(F.normalize(features * (1.0 + noise), dim=1)), labels)
```

- [ ] **Step 2: Choose the highest-coverage zero-error direct gate from calibration**

```python
threshold = np.nextafter(max_wrong_confidence, np.inf)
assert not np.any((confidence >= threshold) & (prediction != truth))
```

- [ ] **Step 3: Build DINO global and four-region local support prototypes and freeze a zero-error fusion threshold**

```python
accepted = consensus & (fusion_confidence >= threshold)
assert not np.any(accepted & (fusion_prediction != truth))
```

### Task 3: Evaluate the locked 200-SKU cohort and record the result

**Files:**
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\h1_closed_pipeline_200sku_6shot_locked.json`
- Create: `experiments/2026-08-04-h1-200sku-closed-pipeline-summary.md`

**Interfaces:**
- Consumes: frozen Task 2 head, gate, fusion policy and locked features.
- Produces: correct-SKU rate, `Unknown` rate, accepted-SKU precision, and conditional-DINO rate.

- [ ] **Step 1: Run DINO only for direct-gate rejections**

```python
direct = repvit_confidence >= gate_threshold
reroute = ~direct
```

- [ ] **Step 2: Fail closed**

```python
final_sku = np.full(len(locked_truth), UNKNOWN_ID)
final_sku[direct] = repvit_prediction[direct]
final_sku[reroute & fusion_accepted] = fusion_prediction[reroute & fusion_accepted]
```

- [ ] **Step 3: Verify external receipt before reporting**

```python
assert result["locked_query_count"] == 294333
assert result["locked"]["unknown_rate"] >= 0.0
```

## Self-Review

- Coverage: full 200-SKU support, fresh calibration and locked features, H1/gate/DINO/fusion, and fail-closed locked evaluation are each explicit.
- Placeholder scan: none.
- Type consistency: feature manifests feed NumPy arrays; support maps feed H1/prototype fitting; frozen policy feeds locked final SKU arrays.

## Execution Handoff

The user explicitly asked to rerun the entire experiment; execute inline and notify only after a locked result receipt is available.
