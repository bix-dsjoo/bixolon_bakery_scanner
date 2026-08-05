# Worktree Consolidation Handoff

## Integrated branches and merge SHAs

| Integration merge | Source branch at integration | Source head |
| --- | --- | --- |
| `a28caa2c0f0700f2c987241792c92bd7ce23b1ad` | `codex/rtx5080-15plus5-inference` | `1172777eb07444eed1666f54a7f798f2826ee241` |
| `7eb068ea0d891499e4a654d7d4b1152ae376500d` | `codex/dual-runtime-exe` | `fc709c7982d3a717fc98d6ff0c0251ea0a8bedb9` |
| `659b5486dfcd0a43f28ad7db7c819e8b8e8a9cf8` | `codex/few-shot-data-optimization` | `e41d9df1a6db621ab33e1aca0adbbb846c029831` |

The integration branch begins from the local `master` tip
`6078a08d48ccb9e5935001c1181e00d0d3b1ffe1`, which already contained eight
local commits ahead of `origin/master` for deployment planning and the
double-click package path. The three source worktrees and their branches are
intentionally retained after integration.

## Completed responsibilities

- RTX 5080 15+5: added an explicit static TensorRT candidate runtime,
  admission and artifact-evidence checks, RF-DETR OOF training/evaluation
  contracts, 15+5 data inventory contracts, and benchmark receipt boundaries.
  The candidate path remains fail-closed when admission or required evidence
  is absent.
- GPU/CPU dual runtime: added explicit runtime-profile selection, GPU/CPU
  execution and fallback provenance, Flutter status presentation, installer
  runtime locking, and deployment validation coverage. The merged worker
  preserves both deployed code-identity attestation and candidate-profile
  selection; neither path silently falls back.
- RPC few-shot research: added immutable RPC input manifests, leakage-safe
  class/scene splits, nested support selection, provenance-bound evidence
  scoring, stage selection/reselection, and experiment summaries/receipts.
- Documentation: added the canonical fail-closed workflow infographics,
  integration design and execution plan, H1 closed-pipeline plans and
  summaries, and this handoff.

## Experiment and benchmark evidence

- The committed RTX OOF and p95 result receipts live under
  `benchmarks/results/rtx5080_15plus5_*` with corresponding summaries and
  protocols. Their own documents define their evidence status; this handoff
  does not assert a new accuracy or latency result.
- The committed RPC conclusions and development receipts live under
  `experiments/20260731-rpc-fewshot/`. They document a research workflow and
  do not convert unavailable external artifacts into accepted production
  evidence.
- The retained H1 20-SKU and 200-SKU closed-pipeline summaries live under
  `experiments/2026-08-04-h1-*-closed-pipeline-summary.md`. They are
  oracle-box classification evidence and explicitly exclude detector accuracy;
  they must not be presented as end-to-end scan-image results.
- No new model, calibration, benchmark, or deployment release is claimed by
  this consolidation alone.

## External artifacts retained outside Git

- `C:/workspace/bixolon_bakery_scanner/archive/` contains the retained Retail
  Product Checkout raw data: 167,484 files and 31,810,311,622 bytes at
  consolidation time. It is now explicitly ignored by `/archive/` and was not
  deleted or added to Git.
- `C:/Users/OMEN/.codex/worktrees/5d23/bixolon_bakery_scanner/datasets/classifier/`
  is a separate local classifier-data copy (about 0.12 GiB when inventoried).
  `/datasets/classification/` remains ignored.
- Weights, support/prototype banks, raw predictions, full runs, engines, and
  installers remain external artifacts governed by `artifacts.lock.json` and
  component manifests. None were staged by this integration.

## Validation performed and unverified boundaries

| Scope | Result |
| --- | --- |
| Worker conflict contract | `python -m pytest -q tests/prototype/test_camera_worker.py`: 22 passed before the RTX merge commit. |
| Post-RTX Python suite | `python -m pytest -q tests`: 1118 passed, 1 skipped, 21 deselected in 60.12s. |
| Post-dual-runtime Python boundary | `tests/integration/test_rtx5080_15plus5_gpu.py`, `tests/prototype/test_camera_protocol.py`, `tests/prototype/test_camera_runtime.py`, and `tests/prototype/test_camera_worker.py`: 132 passed, 1 deselected. |
| RPC manifest/metrics/splits/support | 77 passed in 3.55s. |
| Final all-branch Python suite | Started twice with `python -m pytest -q tests`; neither completed within 10 minutes. The high-cost `test_rpc_protocol.py` fixture creates and revalidates real Stage-1 scorer receipts. Final full-suite status is **unverified**, not passed. |
| Flutter analysis and tests | **Unverified**: `flutter` is not installed or on PATH in this environment. |
| External engine/GPU acceptance | **Unverified** here: no admitted RTX engine bundle or target hardware run was available. |

The `pytest` console launcher was also unsuitable in this shell because it
omitted the repository root from `sys.path`, making `scripts` and `tools`
imports fail during collection. Use `python -m pytest` for this checkout.

## Recommended next actions

1. Install or expose the pinned Flutter SDK, then run `flutter analyze` and
   `flutter test` from `apps/bakery_camera_flutter`.
2. Run `python -m pytest -q tests` in an environment allowed to finish the
   high-cost RPC protocol suite; record the final receipt rather than treating
   the partial runs above as full verification.
3. Run the configured artifact verification and the external RTX engine/GPU
   acceptance protocol with declared artifacts, hardware, and warmed latency
   conditions. Preserve `Unknown` for every missing or rejected admission.
4. Review the PR diff for the retained source history and external-data
   exclusion, obtain at least one approval, and wait for required CI checks
   before merging to `master`.
