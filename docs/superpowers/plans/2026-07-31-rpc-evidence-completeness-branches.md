# RPC Evidence Completeness and Branch Scores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RPC score receipts fail closed unless evidence exactly covers a hash-bound locked ground-truth manifest, and preserve separate RepViT-global, DINOv3-global, and DINOv3-local score vectors and summaries.

**Architecture:** A canonical external `rpc-fewshot-locked-ground-truth` JSON manifest is the authoritative expected-object set. The single scorer and aggregate scorer load it once, verify its SHA-256 against each condition's bound cohort digest, and compare exact evidence identities. `ResearchEvidenceRow` uses one registered category order with three required score vectors; metric helpers summarize any named branch while final-system metrics continue to use `predicted_category_id`.

**Tech Stack:** Python 3.11 dataclasses, canonical JSON/JSONL, pytest, Ruff.

## Global Constraints

- Missing, duplicate, or extra locked objects fail closed before any score is emitted.
- Completeness identity is exactly `(sample_id, object_id, burst_id, difficulty, truth_category_id)`.
- Candidate and reference conditions must bind the same canonical ground-truth manifest SHA-256.
- All three branch vectors are finite, equal in length to the complete registered category order, and have deterministic first-maximum Top-1 behavior.
- Stage-1 output reports RepViT-global and DINOv3-global summaries plus their Top-1 agreement.
- Full scoring output retains RepViT-global, DINOv3-global, and DINOv3-local summaries.
- Existing unrelated worktree files remain untouched.

---

### Task 1: Exact locked-cohort completeness

**Files:**
- Modify: `src/bakery_scanner/experiments/rpc_metrics.py`
- Modify: `tools/evaluate/score_rpc_fewshot.py`
- Test: `tests/experiments/test_rpc_metrics.py`
- Test: `tests/experiments/test_rpc_tools.py`
- Test: `tests/experiments/test_rpc_scoring_plan.py`

**Interfaces:**
- Consumes: canonical manifest object with `schema_version`, `kind`, and `objects`.
- Produces: `LockedGroundTruthRow`, `load_locked_ground_truth(...)`, and exact evidence-to-manifest validation used by single and aggregate scoring.

- [x] **Step 1: Write failing unit tests**

Add literal fixtures proving one omitted object, one extra object, and one changed burst/difficulty/truth identity are rejected.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/experiments/test_rpc_metrics.py tests/experiments/test_rpc_tools.py -q`

Expected: failures because evidence has no `object_id`, the manifest loader does not exist, and scoring accepts incomplete evidence.

- [x] **Step 3: Implement the minimal completeness contract**

Add validated immutable ground-truth rows, canonical manifest loading/digest checks, and exact set equality against evidence identities. Add required single and aggregate CLI manifest arguments and record the validated manifest digest/counts in receipts.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/experiments/test_rpc_metrics.py tests/experiments/test_rpc_tools.py tests/experiments/test_rpc_scoring_plan.py -q`

Expected: all selected tests pass.

### Task 2: Three independent model branches

**Files:**
- Modify: `src/bakery_scanner/experiments/rpc_metrics.py`
- Modify: `tools/evaluate/score_rpc_fewshot.py`
- Test: `tests/experiments/test_rpc_metrics.py`
- Test: `tests/experiments/test_rpc_tools.py`

**Interfaces:**
- Consumes: `score_category_ids`, `repvit_global_scores`, `dinov3_global_scores`, and `dinov3_local_scores`.
- Produces: `branch_top1_summary(rows, branch=..., novel_category_ids=...)` and `branch_top1_agreement(rows, first=..., second=...)`.

- [x] **Step 1: Write failing branch-schema and summary tests**

Add literal rows where each branch has a different Top-1. Assert separate branch recalls, deterministic agreement, vector-length validation, and the scorer's Stage-1/full branch receipt sections.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/experiments/test_rpc_metrics.py tests/experiments/test_rpc_tools.py -q`

Expected: failures because only one generic score vector exists.

- [x] **Step 3: Implement the minimal branch contract**

Replace the generic vector with three required vectors, add branch selectors/summaries, emit Stage-1 global summaries/agreement, and preserve all three branch summaries in completed score receipts.

- [x] **Step 4: Run focused verification**

Run: `python -m pytest tests/experiments -q`

Expected: all experiment tests pass.

### Task 3: Repository verification and commit

**Files:**
- Verify all modified source, tool, test, experiment, and plan files.

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: one reviewed commit containing the two contract fixes.

- [x] **Step 1: Run static checks**

Run: `ruff check src/bakery_scanner/experiments tools/evaluate tests/experiments`

Expected: zero errors.

- [x] **Step 2: Run the full hermetic suite**

Run: `python -m pytest -q`

Expected: zero failures; unavailable artifact/GPU suites remain explicitly skipped or deselected.

- [x] **Step 3: Review and commit**

Run `git diff --check`, review `git status --short`, stage only intended files, and commit with:

```text
fix: bind RPC evidence to locked ground truth
```
