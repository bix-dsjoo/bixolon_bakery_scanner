# Worktree Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all local worktree changes into one verified PR targeting `master` without deleting or committing external data.

**Architecture:** `codex/consolidate-worktrees` starts at the local `master` tip and receives normal merge commits from the three named worktree branches. A handoff document records the merged responsibilities and external-data boundary. The original branches and worktree directories remain intact through PR review and merge.

**Tech Stack:** Git, GitHub CLI, Python/pytest, Flutter/Dart, repository artifact and benchmark contracts.

## Global Constraints

- Preserve all source worktrees and do not delete external data.
- Do not commit `archive/`, `datasets/`, checkpoints, raw predictions, full runs, support banks, or installers.
- Keep the canonical CPU pipeline fail-closed: no fallback from `Unknown` to a registered SKU.
- Do not claim quality or latency improvements without committed receipt evidence.
- Merge to `master` only after one approval and all required GitHub checks pass.

---

### Task 1: Freeze the integration inventory

**Files:**
- Create: `docs/worktree-consolidation-handoff.md` (initialized with source inventory, completed in Task 6)
- Verify: Git refs and all listed worktree paths

**Interfaces:**
- Consumes: `master`, `codex/rtx5080-15plus5-inference`, `codex/dual-runtime-exe`, and `codex/few-shot-data-optimization` refs.
- Produces: recorded base/head SHA, changed-file summary, and local-data inventory.

- [ ] **Step 1: Capture immutable source refs and worktree state**

```powershell
git worktree list --porcelain
git status --short
git rev-parse master
git rev-parse codex/rtx5080-15plus5-inference
git rev-parse codex/dual-runtime-exe
git rev-parse codex/few-shot-data-optimization
```

Expected: every source ref resolves and the original worktree paths are captured.

- [ ] **Step 2: Record branch scopes**

```powershell
git diff --stat master...codex/rtx5080-15plus5-inference
git diff --stat master...codex/dual-runtime-exe
git diff --stat master...codex/few-shot-data-optimization
```

Expected: no file is staged merely by inventorying it.

### Task 2: Protect and classify root working-tree content

**Files:**
- Modify: `.gitignore`
- Candidate add: `docs/assets/infographics/bakery-scanner-beginner-workflow.png`
- Candidate add: `docs/assets/infographics/bakery-scanner-clean-workflow.png`
- Candidate add: `docs/assets/infographics/bakery-scanner-clean-workflow.svg`
- Exclude: `archive/`, `datasets/`, and generated Flutter files with no normalized content delta

**Interfaces:**
- Consumes: root untracked/modified state.
- Produces: a Git-safe root worktree and explicit external-data exclusion.

- [ ] **Step 1: Verify data and generated-file boundaries**

```powershell
Get-ChildItem archive -Recurse -File | Measure-Object Length -Sum
git diff --raw -- apps/bakery_camera_flutter/windows/flutter/generated_plugin_registrant.cc apps/bakery_camera_flutter/windows/flutter/generated_plugins.cmake
```

Expected: raw data is retained locally and generated files are included only if a real raw delta exists.

- [ ] **Step 2: Add the archive exclusion**

Add this exact line to `.gitignore` while retaining `/datasets/classification/`:

```gitignore
/archive/
```

- [ ] **Step 3: Validate and stage only approved documentation sources**

```powershell
Get-Item docs/assets/infographics/* | Select-Object Name,Length,LastWriteTime
git add -- .gitignore docs/assets/infographics
git diff --cached --check
git diff --cached --name-status
```

Expected: no raw external-data or generated-only file is staged.

- [ ] **Step 4: Commit root cleanup**

```powershell
git commit -m "docs(운영): 로컬 데이터 경계와 워크플로 인포그래픽 정리"
```

Expected: one focused commit contains the ignore rule and accepted documentation assets.

### Task 3: Merge the RTX 5080 15+5 branch

**Files:**
- Modify: files introduced by `master...codex/rtx5080-15plus5-inference`
- Test: focused `tests/` files selected from the merge diff

**Interfaces:**
- Consumes: canonical artifact lock, RF-DETR/RepViT/DINOv3 contracts, and RTX runtime evidence boundary.
- Produces: 15+5 OOF evidence, TensorRT static-engine validation, and benchmark admission contracts.

- [ ] **Step 1: Preview and merge with history**

```powershell
git merge-tree $(git merge-base HEAD codex/rtx5080-15plus5-inference) HEAD codex/rtx5080-15plus5-inference | Select-Object -First 200
git merge --no-ff codex/rtx5080-15plus5-inference -m "merge: RTX 5080 15+5 추론 및 증거 경계 통합"
```

Expected: conflicts stop the merge for deliberate resolution; otherwise a merge commit is created.

- [ ] **Step 2: Verify structural integrity**

```powershell
git diff --check
pytest -q tests
```

Expected: no whitespace errors; test or unavailable-dependency evidence is captured precisely.

### Task 4: Merge the dual-runtime EXE branch

**Files:**
- Modify: files introduced by `master...codex/dual-runtime-exe`
- Test: dual-runtime Python contracts and Flutter tests changed by the branch

**Interfaces:**
- Consumes: runtime-scope protocol and installer boundary from the RTX merge.
- Produces: coherent GPU/CPU execution status and Flutter state that preserves failure provenance.

- [ ] **Step 1: Merge with history and inspect boundary**

```powershell
git merge --no-ff codex/dual-runtime-exe -m "merge: GPU CPU 이중 런타임 EXE 통합"
git diff HEAD~1..HEAD -- apps/bakery_camera_flutter src tests deployment scripts
```

Expected: no silent legacy fallback is introduced.

- [ ] **Step 2: Run affected verification**

From repository root:

```powershell
pytest -q tests
```

From `apps/bakery_camera_flutter` when Flutter is installed:

```powershell
flutter analyze
flutter test
```

Expected: passes are fresh; unavailable tooling is recorded as unverified.

### Task 5: Merge the few-shot data optimization branch

**Files:**
- Modify: files introduced by `master...codex/few-shot-data-optimization`
- Test: RPC few-shot unit and contract tests in the merged test paths

**Interfaces:**
- Consumes: external support-bank/artifact declarations and locked evidence contracts.
- Produces: deterministic few-shot selection, provenance-bound scoring, and experiment findings.

- [ ] **Step 1: Merge with history preserved**

```powershell
git merge --no-ff codex/few-shot-data-optimization -m "merge: RPC few-shot 실험 제어 및 결과 통합"
```

Expected: conflicts are resolved without weakening locked-data boundaries.

- [ ] **Step 2: Confirm fail-closed data treatment**

```powershell
pytest -q tests
git status --short
git ls-files archive datasets
```

Expected: tests produce evidence and Git tracks no raw external data paths.

### Task 6: Complete the future-work handoff record

**Files:**
- Create: `docs/worktree-consolidation-handoff.md`
- Test: `git diff --check`

**Interfaces:**
- Consumes: final merge SHAs, validation output, `experiments/`, `benchmarks/`, and artifact/policy contracts.
- Produces: durable summary of completed work, evidence status, external data locations, and next verification steps.

- [ ] **Step 1: Write evidence-backed handoff document**

Use exactly these headings:

```markdown
# Worktree Consolidation Handoff
## Integrated branches and merge SHAs
## Completed responsibilities
## Experiment and benchmark evidence
## External artifacts retained outside Git
## Validation performed and unverified boundaries
## Recommended next actions
```

Expected: every quality or performance statement cites a committed receipt or says `unverified`.

- [ ] **Step 2: Validate and commit the handoff**

```powershell
git diff --check
rg -n "archive/|datasets/" docs/worktree-consolidation-handoff.md
git add -- docs/worktree-consolidation-handoff.md
git commit -m "docs(인수): 통합 작업과 후속 검증 기준 기록"
```

Expected: the document names external data without adding it to the index.

### Task 7: Verify, publish, review, and merge

**Files:**
- Verify: all changes on `codex/consolidate-worktrees`
- Create: a GitHub PR to `master`

**Interfaces:**
- Consumes: clean integration branch, test evidence, GitHub authentication, and CI/approval policy.
- Produces: a reviewed merge on `master` and a post-merge integrity check.

- [ ] **Step 1: Run final local verification**

```powershell
git status -sb
git diff master...HEAD --check
pytest -q tests
```

From `apps/bakery_camera_flutter`, run `flutter analyze` and `flutter test` when the SDK is installed.

- [ ] **Step 2: Inspect scope and publish**

```powershell
git log --oneline master..HEAD
git diff --stat master...HEAD
git diff --name-only master...HEAD
gh auth status
git push -u origin codex/consolidate-worktrees
```

Create a Korean PR body that states purpose, major changes, verification, external-artifact treatment, impact scope, related work, and review requests.

- [ ] **Step 3: Merge only after required review and CI**

```powershell
$prNumber = gh pr view --json number --jq .number
gh pr checks $prNumber --watch
gh pr merge $prNumber --merge --delete-branch=false
git switch master
git pull --ff-only origin master
pytest -q tests
```

Expected: master contains the PR merge and retains all original worktrees and external data.
