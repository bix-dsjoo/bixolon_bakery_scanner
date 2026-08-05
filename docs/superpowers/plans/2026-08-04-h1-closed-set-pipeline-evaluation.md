# H1 Closed-Set Pipeline Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare H1 with 10 and 50 real supports per SKU using the full classification decision flow, including `Unknown`, without contaminating locked evaluation data.

**Architecture:** Keep detector evaluation out of scope by supplying GT boxes. For each support size, train the frozen-RepViT H1 head on train supports, calibrate its gate and the fusion policy only on a disjoint calibration cohort, then evaluate the fixed decision recipe on a locked cohort. DINOv3 global and local support evidence is built from the same real support prefix; direct gate rejections alone invoke DINOv3.

**Tech Stack:** Python, NumPy, PyTorch CPU, cached RepViT/DINOv3 features, immutable JSON result receipts.

## Global Constraints

- Use only the fixed 20 SKU IDs `1,4,7,8,45,46,47,48,63,64,67,70,124,125,129,130,176,177,180,181`.
- Use real `train2019` support images selected by the deterministic `div`, seed `101`, prefix rule.
- Keep train, calibration, and locked evaluation identities disjoint.
- Evaluate GT-box crops only; report this explicitly and do not claim detector accuracy.
- Accept a SKU only through the calibrated direct gate or immutable fusion consensus; otherwise report `Unknown`.
- Preserve model, feature-cache, data-split, seed, and code SHA-256 values in an external receipt under `C:\workspace\rpc_fewshot_runs`.

---

### Task 1: Resolve disjoint 20-SKU feature cohorts

**Files:**
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\resolve_h1_pipeline_cohorts.py`
- Read: `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-system-dev-support-features-v5\manifest.json`
- Read: `C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\full-system-calibration-support-features-v6\manifest.json`
- Test: output receipt validation in the runner before any fit.

**Interfaces:**
- Consumes: cache manifests with source identities, annotation IDs, category IDs, and feature-array hashes.
- Produces: `resolve_cohorts(manifests, sku_ids) -> {train_supports, calibration_queries, locked_queries}` with identity-disjoint arrays.

- [ ] **Step 1: Write a cohort assertion before fitting**

```python
assert not (set(train_ids) & set(calibration_ids))
assert not (set(train_ids) & set(locked_ids))
assert not (set(calibration_ids) & set(locked_ids))
```

- [ ] **Step 2: Run the assertion against the manifests**

Run: `python resolve_h1_pipeline_cohorts.py`

Expected: a receipt containing non-empty train, calibration, and locked counts for every selected SKU.

- [ ] **Step 3: Stop if a locked cohort is unavailable**

```python
if not locked_rows:
    raise ValueError("locked 20-SKU feature cohort is unavailable; cannot claim full-pipeline result")
```

- [ ] **Step 4: Run cohort resolution again**

Run: `python resolve_h1_pipeline_cohorts.py`

Expected: the same identity hashes and counts on repeated read-only resolution.

### Task 2: Fit H1, direct gate, and DINO support evidence on development data

**Files:**
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\run_h1_closed_pipeline_20sku.py`
- Read: `src/bakery_scanner/experiments/rpc_research_worker.py`
- Test: deterministic model and support-prefix assertions in the runner.

**Interfaces:**
- Consumes: 10- or 50-shot train support prefix and disjoint calibration crop features.
- Produces: `fit_h1(shot) -> H1Head`, `fit_direct_gate(head, calibration) -> Gate`, and DINO global/local prototypes.

- [ ] **Step 1: Assert every support set is exactly the requested real prefix**

```python
for sku_id, rows in supports.items():
    assert len(rows) == shot
    assert all(row.source_identity.startswith("train2019:") for row in rows)
```

- [ ] **Step 2: Train only the 20-way linear H1 head with frozen RepViT features**

```python
model = torch.nn.Linear(384, 20)
train_x = F.normalize(features * (1.0 + noise), dim=1)
loss = F.cross_entropy(model(train_x), labels)
```

- [ ] **Step 3: Choose the direct gate from calibration scores only**

```python
candidate = calibrated_confidence >= threshold
false_accepts = np.sum(candidate & (predicted_sku != truth))
```

Select the highest calibration threshold with zero false direct accepts; no such threshold means the gate always routes to DINOv3.

- [ ] **Step 4: Build DINO global and four-region local prototypes from the same support prefix**

```python
global_prototype = norm(support_dino_global).mean(axis=0)
local_prototype = local4(support_dino_patches).mean(axis=0)
```

- [ ] **Step 5: Run deterministic fit twice**

Run: `python run_h1_closed_pipeline_20sku.py --shot 10 --phase calibration`

Expected: matching head, gate, and support hashes for two executions with the fixed seed.

### Task 3: Calibrate and freeze the fusion acceptance policy

**Files:**
- Modify: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\run_h1_closed_pipeline_20sku.py`
- Test: calibration-only policy assertions in the same runner.

**Interfaces:**
- Consumes: H1 direct rejects and DINO global/local calibration scores.
- Produces: `FusionPolicy(weights, margin, consensus_rule)` serialized in the result receipt.

- [ ] **Step 1: Enumerate a fixed policy grid on calibration rows only**

```python
for margin in (0.0, 0.02, 0.05, 0.10, 0.15):
    accepted = (local_top1 == fused_top1) | ((repvit_top1 == dino_top1 == fused_top1) & (gap >= margin))
```

- [ ] **Step 2: Reject policies with incorrect accepted SKUs**

```python
wrong_accept = np.sum(accepted & (fused_top1 != truth))
if wrong_accept != 0:
    continue
```

- [ ] **Step 3: Choose the highest-coverage zero-wrong-accept policy and freeze it**

```python
best = max(valid_policies, key=lambda policy: policy.coverage)
```

- [ ] **Step 4: Verify the locked cohort is not read during selection**

Run: `python run_h1_closed_pipeline_20sku.py --shot 10 --phase calibration`

Expected: receipt reports `locked_query_count: 0` in calibration phase.

### Task 4: Evaluate the locked GT-box cohort for 10 and 50 supports

**Files:**
- Modify: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\run_h1_closed_pipeline_20sku.py`
- Create: `C:\workspace\rpc_fewshot_runs\20260804-rpc-gtbox-full-pipeline\h1_closed_pipeline_20sku_10_50_locked.json`
- Test: result receipt checks.

**Interfaces:**
- Consumes: frozen per-shot H1 head, gate, fusion policy, and locked GT-box query features.
- Produces: per-shot accuracy, accepted-SKU accuracy, `Unknown` rate, direct-gate rate, conditional-DINO rate, and provenance.

- [ ] **Step 1: Run direct gate and DINO conditionally**

```python
direct = confidence >= gate_threshold
final_sku[direct] = repvit_top1[direct]
reroute = ~direct
```

- [ ] **Step 2: Fail closed for every non-accepted fusion result**

```python
final_sku[reroute & ~fusion_accept] = UNKNOWN_ID
```

- [ ] **Step 3: Produce the 10-shot and 50-shot locked receipt**

Run: `python run_h1_closed_pipeline_20sku.py --shot 10 --phase locked` and `python run_h1_closed_pipeline_20sku.py --shot 50 --phase locked`

Expected: two results with separate model/policy hashes and no calibration refit during locked execution.

- [ ] **Step 4: Verify receipt integrity before reporting**

```python
assert result["scope"].startswith("oracle-box")
assert result["locked_query_count"] > 0
assert result["unknown_rate"] >= 0.0
```

### Task 5: Document the measured operating point

**Files:**
- Create: `experiments/2026-08-04-h1-20sku-closed-pipeline-summary.md`
- Read: external locked result receipt from Task 4.
- Test: manual comparison against receipt values.

**Interfaces:**
- Consumes: immutable external results only.
- Produces: a compact Git-safe conclusion that does not contain source images, model weights, or raw predictions.

- [ ] **Step 1: State the exact evaluation scope**

```markdown
GT-box crop classification only; detector accuracy is not measured.
```

- [ ] **Step 2: Compare 10 versus 50 real supports**

Include overall correct-SKU rate, `Unknown` rate, accepted-SKU precision, and conditional-DINO execution rate.

- [ ] **Step 3: Record the recommendation only if supported by the locked receipt**

```markdown
Choose 50 supports only if its locked correct-SKU rate is higher without reducing accepted-SKU precision.
```

## Self-Review

- Coverage: the plan separately handles frozen H1 fitting, calibration, fail-closed fusion, locked evaluation, and a Git-safe conclusion.
- Placeholders: none; all commands, assertions, and decision rules are specified.
- Type consistency: every task passes explicit support maps, feature arrays, and immutable receipt dictionaries to the next task.

## Execution Handoff

The user approved execution in this conversation; proceed with inline execution and report the locked comparison once the required cohorts and receipts are available.
