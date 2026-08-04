# Worktree Consolidation Design

## Goal

Preserve and integrate all committed development work from the active local
worktrees into one reviewable GitHub pull request targeting `master`, while
retaining external data locally and leaving a durable handoff record.

## Source inventory

| Source | Intended content | Handling |
| --- | --- | --- |
| `master` (8 local commits ahead of `origin/master`) | deployment planning and double-click package improvements | becomes the integration base |
| `codex/rtx5080-15plus5-inference` | RTX 5080 inference, 15+5 acceptance evidence, benchmark and artifact boundaries | merge with history preserved |
| `codex/dual-runtime-exe` | GPU/CPU dual-runtime protocol, Flutter state, installer checks | merge with history preserved |
| `codex/few-shot-data-optimization` | leakage-safe RPC few-shot experiment controls and findings | merge with history preserved |
| root working tree | classification-data ignore rule and documentation infographics | review and commit if valid |
| untracked local data | `archive/` (about 29.6 GiB) and `datasets/classifier/` (about 0.12 GiB) | retain on disk, exclude from Git, document as external artifacts |

## Integration approach

Use `codex/consolidate-worktrees`, based on the current local `master`, as a
temporary integration branch. Merge each committed worktree branch with normal
merge commits rather than squashing. This preserves the experiments' detailed
provenance and allows conflicts to be reviewed in context. Existing worktree
directories and their branches remain intact until the PR is merged and a
post-merge inspection confirms their content is represented.

The integration branch will also commit a handoff document under `docs/`.
It will group completed work by responsibility, record tested versus
unverified evidence, name relevant external artifacts without embedding them,
and point future work at the remaining gates.

## Data and safety rules

- Never add raw scans, derived data, checkpoints, or other external payloads
  to Git.
- Add an explicit `/archive/` ignore rule so the locally retained data cannot
  be accidentally staged; retain the existing classification-data ignore rule.
- Treat generated Flutter Windows plugin files as generated output. Include
  them only when they contain a real source-level delta after a normalized
  diff; otherwise leave them untouched.
- Resolve conflicts conservatively: retain the stricter validation and
  fail-closed `Unknown` behavior, and run the focused affected tests.
- Do not claim accuracy, latency, or release readiness without a committed
  receipt and fresh verification.

## Validation and delivery

1. Inspect the merge result for conflicts, unintended data files, and
   artifact-lock/provenance contract changes.
2. Run the relevant hermetic unit and contract suites, plus Flutter analysis
   or tests where the dual-runtime branch changes that boundary. Report
   unavailable suites as unverified.
3. Create a GitHub PR against `master` with a Korean summary, explicit test
   evidence, external-data treatment, and review requests.
4. Merge only after at least one approval and all required GitHub checks pass.
5. Re-check `master` after merge; only then consider pruning project-local
   worktrees, without deleting external data.
