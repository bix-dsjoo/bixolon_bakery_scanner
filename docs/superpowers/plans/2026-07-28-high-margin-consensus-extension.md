# High-margin global consensus extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved high-margin three-model consensus path to the immutable fusion-policy artifact.

**Architecture:** Extend the policy artifact with a schema-v3 rule and a fixed `0.85` margin floor.  `FusionPolicyArtifact.decide()` remains the only acceptance decision point; runtime maps the new abstention to a distinct Unknown reason.  The existing generator exposes the rule and the active configuration pins its generated artifact hash.

**Tech Stack:** Python 3.11, pytest, ruff, JSON policy artifacts.

## Global Constraints

- Preserve deterministic SKU tie ordering and schema-v1/v2 policy read compatibility.
- Do not alter detector, box assurance, component resolution, or model inference calls.
- Select the margin floor from Batch1 development evidence only; report Batch2 as non-independent evidence.
- Do not create a commit without an explicit user request.

---

### Task 1: Add the high-margin rule to the policy contract

**Files:**
- Modify: `tests/classification/test_fusion_policy.py`
- Modify: `src/bakery_scanner/classification/fusion_policy.py`

**Interfaces:**
- Consumes: `FusionPolicyArtifact.decide(row) -> tuple[FusionDecision, float]`
- Produces: schema-v3 `decision_rule="fusion_local_or_global_consensus_margin_v1"` with `consensus_margin_floor=0.85`.

- [x] **Step 1: Write failing tests**

```python
artifact = _artifact(
    decision_rule="fusion_local_or_global_consensus_margin_v1",
    consensus_margin_floor=0.85,
)
assert artifact.decide(consensus_row)[0].decision == "sku"
assert artifact.decide(low_margin_consensus_row)[0].decision == "unknown"
```

- [x] **Step 2: Run the targeted tests and verify failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/classification/test_fusion_policy.py -q`

Expected: failure because the artifact constructor does not yet accept the rule and floor.

- [x] **Step 3: Implement the minimal policy behavior**

```python
accepted = fusion_top1 == local_top1
accepted = accepted or (
    fusion_top1 == repvit_top1 == dino_global_top1
    and fusion_margin >= consensus_margin_floor
)
```

- [x] **Step 4: Run the targeted tests and verify pass**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/classification/test_fusion_policy.py -q`

Expected: PASS.

### Task 2: Activate and evaluate the immutable artifact

**Files:**
- Modify: `scripts/train_classifier_fusion_policy.py`
- Modify: `src/bakery_scanner/classification/runtime.py`
- Modify: `configs/classifier_policy.yaml`
- Generate: `artifacts/classification/fusion_policy_local_or_global_consensus_margin_v1.json`

**Interfaces:**
- Consumes: Batch1 full evidence and classifier model hashes.
- Produces: a hash-pinned schema-v3 policy artifact and `fusion_global_consensus_margin` Unknown reason.

- [x] **Step 1: Write a failing runtime test for the new Unknown reason**

```python
assert result.decision == "unknown"
assert result.unknown_reason == "fusion_global_consensus_margin"
```

- [x] **Step 2: Run the targeted runtime test and verify failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/classification/test_runtime.py -q`

Expected: failure because the runtime does not yet map the new rule.

- [x] **Step 3: Add CLI selection, runtime mapping, and regenerate artifact**

```powershell
$env:PYTHONPATH='src'
python scripts/train_classifier_fusion_policy.py --config configs/classifier_policy.yaml --evidence artifacts/classification/batch1.full_evidence.v3.jsonl --output artifacts/classification/fusion_policy_local_or_global_consensus_margin_v1.json --decision-rule fusion_local_or_global_consensus_margin_v1 --consensus-margin-floor 0.85
```

- [x] **Step 4: Pin the resulting SHA-256 and run evidence evaluation**

Run: `$env:PYTHONPATH='src'; python scripts/evaluate_fusion_classifier_policy.py --config configs/classifier_policy.yaml --development-evidence artifacts/classification/batch1.full_evidence.v3.jsonl --evidence artifacts/classification/batch2.full_evidence.v3.jsonl --policy artifacts/classification/fusion_policy_local_or_global_consensus_margin_v1.json --output artifacts/classification/batch2.fusion_policy_local_or_global_consensus_margin_v1.report.json`

Expected: Batch2 has 506 automatic results, 504 correct automatic results, 2 automatic errors, and 16 Unknown results.

### Task 3: Regression verification

**Files:**
- Test: `tests/classification`

**Interfaces:**
- Consumes: active configuration and generated policy artifact.
- Produces: passing regression suite and static analysis.

- [x] **Step 1: Run classifier regression tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/classification -q`

Expected: all tests pass.

- [x] **Step 2: Run static analysis and configuration load check**

Run: `$env:PYTHONPATH='src'; python -m ruff check src/bakery_scanner/classification/fusion_policy.py src/bakery_scanner/classification/runtime.py scripts/train_classifier_fusion_policy.py tests/classification/test_fusion_policy.py tests/classification/test_runtime.py`

Expected: `All checks passed!`
