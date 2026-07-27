# Safe Local Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm a registered SKU only when independent RepViT and DINO-family evidence is safe; otherwise emit `Unknown`, three ranked candidates, and a machine-readable reason.

**Architecture:** RepViT-M1 scores three padded crops and supplies a pooled feature. Its probability, margin, crop disagreement, and prototype distance govern the direct path. An abstention invokes DINOv3 once for global retrieval, then scores the deterministic union of DINO Top-5 and RepViT Top-2 against an equal-size foreground-aware local bank. Local evidence reranks candidates but cannot independently confirm a SKU.

**Tech Stack:** Python 3.11, PyTorch, NumPy, Pydantic, pytest.

## Global Constraints

- Input is a canonical visual image and one Verifier-confirmed bread box.
- `Unknown` is a valid safe result; Top-3 recall is reported but is not a release gate.
- DINO global and DINO local are one DINO-family source, not two independent votes.
- Until the Verifier provides a foreground mask, use an eroded box and record the fallback in provenance.
- Batch1 develops only artifacts/thresholds; Batch2 remains locked.
- Do not stage `datasets/` or `models/` junctions, and do not merge this worktree.

---

### Task 1: RepViT direct evidence and abstention contract

**Files:**
- Modify: `src/bakery_scanner/classification/{repvit,config,contracts,policy,runtime}.py`
- Modify: `tests/classification/{test_repvit,test_policy,test_runtime,test_config}.py`

**Interfaces:**
- `RepVitM1Runner.score_with_evidence(crops) -> RepVitEvidence(scores, feature, crop_disagreement)`.
- `RepVitPrototypeBank.distances(feature) -> dict[int, float]`.
- `DecisionPolicy.direct(repvit_scores, evidence, *, box) -> ClassificationDecision | None`.

- [ ] Write a failing test proving that high softmax confidence is rejected when either crop disagreement or prototype distance exceeds its calibrated direct gate.
- [ ] Run `python -m pytest tests/classification/test_policy.py tests/classification/test_repvit.py -q` and confirm the direct path still accepts the score without those gates.
- [ ] Add strict prototype-bank provenance validation and the calibrated direct-gate fields; pass RepViT evidence from runtime without constructing DINO on a safe direct decision.
- [ ] Re-run the focused tests and commit `feat: gate RepViT direct decisions with OOD evidence`.

### Task 2: Deterministic foreground-aware local evidence

**Files:**
- Modify: `src/bakery_scanner/classification/{dinov3,local_bank}.py`
- Modify: `scripts/build_dinov3_support.py`
- Modify: `tests/classification/{test_dinov3,test_local_bank}.py`

**Interfaces:**
- `candidate_union(dino_scores, repvit_scores) -> tuple[int, ...]` returns DINO Top-5 union RepViT Top-2 in deterministic rank order, maximum seven IDs.
- `LocalPatchBank.score(candidate_ids, patch_tokens, product_mask) -> LocalEvidence` uses top-3 reference averaging and a trimmed query mean.

- [ ] Write failing numerical tests for candidate union, top-3 reference averaging, trimmed query aggregation, and eroded-box patch masking.
- [ ] Run `python -m pytest tests/classification/test_dinov3.py tests/classification/test_local_bank.py -q` and confirm the current rectangular/max-similarity implementation fails the expected assertions.
- [ ] Build source-balanced deterministic coreset banks, with exactly the configured cap per SKU where data permits; persist source membership and foreground-mask fallback metadata.
- [ ] Implement the union and local scorer, then re-run focused tests and commit `feat: use balanced foreground local DINO evidence`.

### Task 3: Calibrated recheck decision and reasoned Unknown result

**Files:**
- Modify: `src/bakery_scanner/classification/{contracts,policy,runtime,evidence}.py`
- Modify: `tests/classification/{test_contracts,test_policy,test_runtime,test_evidence}.py`

**Interfaces:**
- `ClassificationDecision.unknown_reason: str | None`.
- `DecisionPolicy.after_local_recheck(repvit, repvit_evidence, dino_global, dino_local, *, box) -> ClassificationDecision`.

- [ ] Write a failing test in which local similarity favors a SKU but RepViT and DINO-global disagree; assert `Unknown` with three candidates and `unknown_reason="cross_model_disagreement"`.
- [ ] Run `python -m pytest tests/classification/test_policy.py tests/classification/test_runtime.py -q` and confirm no `unknown_reason` exists.
- [ ] Add canonical, hash-bound calibration fields for every evidence input and require RepViT/DINO-family agreement plus absolute score and margin gates. Use candidate-only softmax only for Top-3 order.
- [ ] Make runtime invoke DINO only after direct abstention; explicit DINO artifact/inference failures return `Unknown` with their failure reason.
- [ ] Re-run focused tests and commit `feat: return calibrated Unknown decisions with reasons`.

### Task 4: Development calibration and locked Batch2 report

**Files:**
- Modify: `scripts/{collect_classifier_evidence,calibrate_classifier_policy,evaluate_classifier_policy,benchmark_classifier_pipeline}.py`
- Modify: `src/bakery_scanner/classification/evidence.py`
- Modify: `tests/classification/{test_evidence,test_benchmark,test_calibration_selection}.py`
- Modify: `docs/superpowers/specs/2026-07-27-safe-local-rerank-revision.md`

- [ ] Write failing tests asserting that Batch2 evaluation cannot select thresholds and that its report separates direct/recheck/Unknown paths and reason counts.
- [ ] Run the relevant test modules and confirm the legacy evidence schema cannot produce the report.
- [ ] Collect complete evidence vectors only from Batch1, produce a versioned calibration artifact, and evaluate the exact artifact once on Batch2 without parameter selection.
- [ ] Record automatic SKU errors, Unknown count/reasons, Top-3 recall, DINO invocation rate, and p50/p95 stage/total latency; do not call this release validation without representative OOD data.
- [ ] Run `python -m pytest tests/classification -q`, `git diff --check`, and commit `feat: calibrate and report safe classifier decisions`.
