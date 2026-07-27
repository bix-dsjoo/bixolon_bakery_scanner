# Task 6 implementation report

## Status

Implemented and committed Task 6: independent evidence validation and
collection, grouped development-only policy selection, immutable locked-set
evaluation, atomic artifacts, metrics, and release gating.

## Commit

- `4105ba4 feat: calibrate classifier abstention policy`

## Files

- `src/bakery_scanner/classification/evidence.py`
  - Immutable `EvidenceInput`, `EvidenceRow`, `EvaluatedRow`, and
    `ClassificationMetrics`.
  - Exact JSONL schema and image/box/role/label/hash validation.
  - Duplicate sample/image rejection and RepViT training-image leakage
    rejection.
  - Canonical evidence serialization, atomic sibling temporary-file writes,
    grouped splits, calibration selection, policy prediction, and metrics.
- `scripts/collect_classifier_evidence.py`
  - Loads the configured RepViT training manifest and rejects leaked images.
  - Forces RepViT and DINOv3 scoring for every manifest row before writing.
  - Writes canonical JSONL only after all rows validate.
- `scripts/calibrate_classifier_policy.py`
  - Accepts development evidence only.
  - Runs cross-fit safety gates before atomically writing canonical
    `PolicyCalibration`.
- `scripts/evaluate_classifier_policy.py`
  - Accepts locked-acceptance evidence only.
  - Applies an existing calibration exactly once and never selects or writes
    calibration parameters.
  - Reports locked/calibration hashes, artifact IDs, overall, per-SKU,
    base-15, incremental-5, registered, and unregistered slices, plus exact
    failure sample IDs.
  - Returns nonzero unless all three overall release metrics equal `1.0`;
    `None` never passes.
- `tests/classification/test_evidence.py`
  - Manifest leakage/schema/bounds/identity tests, evidence vector tests,
    metric denominator and unregistered behavior, forced dual-model
    collection, atomic output, and locked report tests.
- `tests/classification/test_calibration_selection.py`
  - Five-fold group isolation, deterministic selection, locked-role
    rejection, safe unregistered abstention, and held-out-only failure
    rejection.

## Grouped-selection decisions

- Uses `StratifiedGroupKFold(n_splits=5, shuffle=True,
  random_state=20260727)`.
- Stratification labels are `sku:01` through `sku:20` or `unregistered`;
  grouping uses `capture_group`.
- Each fold fits only its training groups. Held-out predictions are pooled
  only for cross-fit metrics.
- RepViT and DINOv3 temperatures are independently selected by registered-row
  multiclass NLL over the exact prescribed temperature grid, with lower
  temperature as the tie break.
- Alpha uses registered Top-3 misses, fused NLL, then lower alpha over the
  exact prescribed 21-value grid.
- Direct and recheck candidates use non-dominated observed threshold pairs
  plus `(1.0, 1.0)`. Recheck candidates are recomputed for each direct-gate
  candidate from rows that actually reach recheck.
- Complete gates use the prescribed lexicographic ordering:
  automatic errors, fallback misses, assisted failures, negative automatic
  count, DINO invocation count, then threshold tuple.
- Unregistered automatic SKU output is an automatic and assisted error.
  Unregistered rows are never included in fallback Top-3 recall.
- Any pooled cross-fit automatic error, fallback miss, or assisted failure
  aborts before the final artifact can be written. Only after that gate is
  one final policy fitted on all development rows.
- Locked-acceptance roles are rejected by selection, and development roles
  are rejected by locked evaluation.

## Verification

- Exact Task 6 command:
  - `python -m pytest tests/classification/test_evidence.py tests/classification/test_calibration_selection.py -q`
  - Result: `22 passed in 4.22s`
- Classifier regression:
  - `python -m pytest tests/classification -q`
  - Result: `109 passed in 4.75s`
  - Existing warning: unregistered `pytest.mark.integration` in
    `tests/classification/test_repvit.py`.
- Shared contract/config/preprocess regression:
  - `python -m pytest tests/test_contracts.py tests/test_config.py tests/test_preprocess.py -q`
  - Result: `8 passed in 0.82s`
- `ruff check`: all checks passed.
- `ruff format --check`: all six Task 6 files formatted.
- `compileall`: exit zero.
- All three CLI `--help` commands: exit zero.
- `git diff --check`: exit zero.

## Unresolved concerns

- No independent development or locked-acceptance evidence manifests are
  currently used by this task, so no real calibration artifact, locked-set
  accuracy claim, or release approval is produced. The implemented commands
  intentionally require those data.
- The classifier suite emits one pre-existing warning because the repository
  has not registered the `integration` pytest marker. This task does not
  modify shared pytest configuration.
- The requested report split is implemented as base SKU IDs `1..15` and
  incremental SKU IDs `16..20`, matching the `15plus5` artifact ordering.

---

# Task 6 review fix round 1

## Status

All three Important review findings and both requested Minor hygiene items were
implemented and committed.

## Commit

- `2d13599 fix: harden classifier evidence acceptance`

## Review findings addressed

1. Precomputed evidence leakage:
   - `calibrate_classifier_policy.py` and
     `evaluate_classifier_policy.py` now require `--config`.
   - Both verify the configured RepViT training manifest SHA-256, load its
     source-image hashes, and pass those hashes into `load_evidence_rows`.
   - A precomputed JSONL row whose `image_sha256` is in training is rejected
     before any calibration/report output replacement.
2. Locked report artifact identity:
   - The locked report now includes
     `repvit_checkpoint_sha256`, `repvit_manifest_sha256`,
     `dinov3_weights_sha256`, and `dinov3_support_sha256`.
   - These are reported with the existing RepViT/DINO artifact IDs,
     calibration hash, and locked evidence hash.
3. Undefined cross-fit metrics:
   - Pooled cross-fit metrics are checked for `None` in
     `auto_precision`, `fallback_top3_recall`, and `assisted_success`.
   - Selection raises before final fitting/output when any applicable metric
     is undefined. An all-Unknown development result therefore cannot produce
     a successful calibration artifact.
4. Capture-group hygiene:
   - Both `EvidenceInput` and `EvidenceRow` reject whitespace-only
     `capture_group` values.
5. Evaluator CLI behavior:
   - Focused tests cover development-role rejection without report
     replacement, nonzero release exit, calibration-file immutability, and
     precomputed training-image rejection.

## Tests added or updated

- Synthetic grouped selection now contains both safe automatic decisions and
  registered Unknown Top-3 decisions, so every required release metric has a
  denominator.
- Added explicit all-Unknown cross-fit rejection.
- Added CLI-level calibrator and evaluator leakage tests using a strict
  temporary classifier config and hashed RepViT manifest.
- Added exact locked-report model hash assertions.
- Added whitespace-only `capture_group` rejection.

## Verification

- Task 6:
  - `python -m pytest tests/classification/test_evidence.py tests/classification/test_calibration_selection.py -q`
  - `27 passed in 4.03s`
- Full classifier regression:
  - `python -m pytest tests/classification -q`
  - `114 passed in 4.91s`
  - One pre-existing unknown `integration` marker warning remains.
- Shared regression:
  - `python -m pytest tests/test_contracts.py tests/test_config.py tests/test_preprocess.py -q`
  - `8 passed in 0.86s`
- `compileall`, both changed CLI `--help` commands, `ruff check`,
  `ruff format --check`, and `git diff --check` all exited zero.

## Follow-up boundary

- Task 7 documentation must include the now-required `--config
  configs/classifier_policy.yaml` argument for both calibration and locked
  evaluation commands.
- No real development or locked-acceptance evidence was introduced, so
  real-data calibration and release acceptance remain data-dependent.

## Final review hardening wave

- Evidence rows now carry schema-versioned scenarios and cryptographic model
  provenance: RepViT checkpoint/manifest, DINO weights/support, and the
  versioned preprocessing digest. Calibration and locked evaluation recompute
  configured file digests and reject rows that do not match.
- `PolicyCalibration` now binds both the complete development evidence hash and
  a stable development-identity hash. Locked evaluation requires the exact
  development evidence used for calibration and rejects dev/locked image overlap.
- DINO source identities are mandatory. `--dino-source-manifest` is required by
  collection, calibration, and locked evaluation; it must be canonical JSON and
  its SHA-256 must equal `source_manifest_sha256` embedded in the support file.
  Both RepViT and DINO source hashes are excluded from evidence. The generator
  defaults to `datasets/classification/base_15class` and
  `datasets/classification/incremental_5class_crop`.
- Locked release requires `configs/locked_classifier_coverage_v1.json`: all 20
  SKUs, an unregistered crop, and every required scenario. A perfect incomplete
  subset cannot pass. Scenario slices are reported and must have zero applicable
  automatic, Top-3, and assisted errors.
- Threshold selection now retains every distinct `>=` acceptance mask; the old
  Pareto direction could discard safe intermediate thresholds. Automatic coverage
  uses registered inputs as its denominator. Benchmark path grouping uses the
  explicit decision path when supplied by online inference.

### Operational blocker

The checked-in DINO support references source-manifest SHA-256
`c3553d6c7d467d47a3b4f4f611073555e873e4f09a0f5a12db3ff269fecee964`, but the
matching canonical manifest is not present in this repository. Production
calibration/evaluation therefore remains intentionally fail-closed until a
manifest generated from the authoritative source roots hashes to that value (or
the support artifact is rebuilt with the resulting manifest digest).
