# Top5 + Catalog Assisted Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace new Top3 Unknown evidence with exact Top5 evidence and let customers resolve it through Top5 selection or the existing full-catalog search without mutating inference receipts.

**Architecture:** The Python classifier remains the sole producer of ranked model evidence, the camera worker transports exact Top5 evidence, and Flutter stores customer choices as separate audited resolutions. Existing Top3 database rows remain readable; new rows use `unknown_top5` and `customer_top5`.

**Tech Stack:** Python 3.11, pytest, Flutter/Dart 3.12, Drift/SQLite, flutter_test.

## Global Constraints

- Preserve the RF-DETR-L threshold, RepViT direct gate, conditional DINOv3, immutable fusion rule and fail-closed `Unknown` behavior.
- New Unknown decisions require exactly five unique registered SKU candidates ranked 1 through 5; registered decisions contain no candidates.
- Top5 is user assistance, never an automatic SKU acceptance path.
- Top5 selection, catalog selection and unresolved Unknown are distinct audited outcomes.
- Existing `unknown_top3` and `customer_top3` records remain immutable and readable.
- Do not modify `portable_cpu_smoke/` or legacy inference behavior.
- Use deterministic JSON, stable candidate ordering and complete provenance.

---

## File Structure

- `src/bakery_scanner/classification/contracts.py`: canonical Top5 decision record.
- `src/bakery_scanner/classification/policy.py`: policy-produced Top5 for direct/fusion rejection.
- `src/bakery_scanner/classification/runtime.py`: runtime/failure Top5 production.
- `src/bakery_scanner/prototype/camera_runtime.py`: worker Top5 serialization.
- `src/bakery_scanner/prototype/presentation_policy.py`: scene-only retake versus Unknown routing.
- `policies/presentation/camera_action_state_v2.json`: immutable scene presentation policy.
- `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`: strict Top5 parser.
- `apps/bakery_camera_flutter/lib/src/checkout/checkout_models.dart`: new customer resolution source.
- `apps/bakery_camera_flutter/lib/src/checkout/checkout_controller.dart`: exact Top5 selection.
- `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`: five-candidate UI plus catalog search.
- `apps/bakery_camera_flutter/lib/src/persistence/app_database.dart`: schema v5 constraints and migration.
- `apps/bakery_camera_flutter/lib/src/persistence/database_checkout_audit_store.dart`: Top5 audit verification.
- `apps/bakery_camera_flutter/lib/src/admin/`: legacy/new source labels and filters.
- Matching Python and Flutter test files own contract, UI, persistence and integration evidence.

### Task 1: Python Top5 Classification Contract

**Files:**
- Modify: `src/bakery_scanner/classification/contracts.py`
- Modify: `src/bakery_scanner/classification/policy.py`
- Modify: `src/bakery_scanner/classification/runtime.py`
- Test: `tests/classification/test_contracts.py`
- Test: `tests/classification/test_policy.py`
- Test: `tests/classification/test_runtime.py`

**Interfaces:**
- Produces: `DecisionPath.UNKNOWN_TOP5`, `ClassificationDecision.top5: tuple[SkuCandidate, ...]`.
- Consumes: existing calibrated 20-SKU score vectors and deterministic rank order.

- [ ] **Step 1: Write failing contract and policy tests**

```python
def test_unknown_requires_exactly_five_unique_ranked_candidates():
    decision = _unknown_decision(
        top5=tuple(SkuCandidate(rank, rank, 1.0 / rank) for rank in range(1, 6))
    )
    assert decision.decision_path is DecisionPath.UNKNOWN_TOP5
    assert [row.rank for row in decision.top5] == [1, 2, 3, 4, 5]


def test_policy_rejection_preserves_ranked_top5():
    decision = policy.after_local_recheck(repvit, dino, local, box=BOX)
    assert decision.decision == "unknown"
    assert len(decision.top5) == 5
    assert len({row.sku_id for row in decision.top5}) == 5
```

- [ ] **Step 2: Run the focused tests and verify they fail for the Top3 contract**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/classification/test_contracts.py tests/classification/test_policy.py tests/classification/test_runtime.py -q`

Expected: FAIL because `UNKNOWN_TOP5` and `top5` do not exist and current policy truncates at three.

- [ ] **Step 3: Implement the minimal Top5 decision contract and producers**

```python
class DecisionPath(str, Enum):
    REPVIT_DIRECT = "repvit_direct"
    DINOV3_CONFIRMED = "dinov3_confirmed"
    FUSION_RANKED = "fusion_ranked"
    UNKNOWN_TOP5 = "unknown_top5"


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    # existing fields unchanged
    top5: tuple[SkuCandidate, ...]


top_indices = ranked[:5]
candidates = tuple(
    SkuCandidate(rank, sku_ids[index], float(scores[index]))
    for rank, index in enumerate(top_indices, start=1)
)
```

Update all registered constructors to use `top5=()` and all Unknown constructors to use ranks 1..5. Deterministic JSON uses the `top5` key.

- [ ] **Step 4: Run focused classification tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/classification -q`

Expected: PASS with no Top3-only production assertion remaining in canonical classification tests.

- [ ] **Step 5: Commit the classification contract**

```powershell
git add src/bakery_scanner/classification tests/classification
git commit -m "feat: produce fail-closed Top5 candidates"
```

### Task 2: Worker Top5 Protocol and Scene-Only Retake Policy

**Files:**
- Create: `policies/presentation/camera_action_state_v2.json`
- Modify: `src/bakery_scanner/prototype/camera_runtime.py`
- Modify: `src/bakery_scanner/prototype/presentation_policy.py`
- Modify: `src/bakery_scanner/prototype/camera_protocol.py`
- Test: `tests/prototype/test_camera_runtime.py`
- Test: `tests/prototype/test_presentation_policy.py`
- Test: `tests/prototype/test_camera_protocol.py`
- Test: `tests/prototype/test_camera_worker.py`

**Interfaces:**
- Consumes: `ClassificationDecision.top5` from Task 1.
- Produces: result object `top5`, decision path `unknown_top5`, presentation policy `camera_action_state_v2`.

- [ ] **Step 1: Write failing worker and presentation tests**

```python
def test_unknown_result_serializes_exact_top5():
    result = runtime.analyze(IMAGE, "request-top5")
    unknown = next(row for row in result["objects"] if row["sku_id"] is None)
    assert unknown["decision_path"] == "unknown_top5"
    assert [row["rank"] for row in unknown["top5"]] == [1, 2, 3, 4, 5]


def test_weak_unknown_routes_to_user_candidates_not_retake(policy):
    decision = policy.evaluate(proposals=PROPOSALS, decisions=WEAK_UNKNOWN)
    assert decision.state == "unknown"
    assert decision.candidate_object_ids == ("object-1",)
```

- [ ] **Step 2: Run focused tests and verify the Top3/weak-retake failures**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_presentation_policy.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_worker.py -q`

Expected: FAIL because the worker emits `top3` and v1 routes weak candidates to `candidate_evidence_weak` retake.

- [ ] **Step 3: Add immutable presentation policy v2**

```json
{
  "box_overlap_iou": 0.7,
  "policy_id": "camera_action_state_v2",
  "schema_version": 2
}
```

Load this exact file from `CameraInferenceRuntime.initialize`. V2 evaluates only no-object and overlap retakes; every usable-scene Unknown becomes presentation state `unknown`.

- [ ] **Step 4: Serialize and validate exact Top5**

```python
top5 = [
    {"rank": c.rank, "sku_id": c.sku_id, "sku_name": sku_names[c.sku_id], "score": c.score}
    for c in decision.top5
]
if len(top5) != 5:
    raise ValueError("Unknown decisions must preserve exactly five candidates")
```

Change registered objects to emit an empty `top5`. Update strict result and presentation validation to require policy v2 and reject candidates on retake results.

- [ ] **Step 5: Run prototype tests**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/prototype -q`

Expected: PASS.

- [ ] **Step 6: Commit the worker protocol change**

```powershell
git add policies/presentation/camera_action_state_v2.json src/bakery_scanner/prototype tests/prototype
git commit -m "feat: expose Top5 for usable Unknown scans"
```

### Task 3: Flutter Top5 Model, Review UI and Catalog Escape Hatch

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/checkout/checkout_models.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/checkout/checkout_controller.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart`
- Test: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/checkout_models_test.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/checkout_controller_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`

**Interfaces:**
- Consumes: worker `top5` and `unknown_top5` from Task 2.
- Produces: `chooseTop5(objectId, skuId)` and `CustomerResolutionSource.customerTop5`.

- [ ] **Step 1: Write failing Dart model and widget tests**

```dart
test('Unknown requires exactly five ranked candidates', () {
  final result = InferenceResult.fromJson(resultWithTop5());
  expect(result.objects.single.candidates, hasLength(5));
  expect(result.objects.single.candidates.map((row) => row.rank), [1, 2, 3, 4, 5]);
});

testWidgets('review shows five candidates and catalog search', (tester) async {
  await pumpUnknownReview(tester, candidateCount: 5);
  expect(find.byKey(const Key('customer-review-candidate-choice')), findsNWidgets(5));
  expect(find.text('다른 상품 찾기'), findsOneWidget);
});
```

- [ ] **Step 2: Run focused Flutter tests and verify failure**

Run: `flutter test test/inference/inference_models_test.dart test/checkout/checkout_models_test.dart test/checkout/checkout_controller_test.dart test/ui/customer_checkout_contract_test.dart test/ui/result_rail_test.dart`

Working directory: `apps/bakery_camera_flutter`

Expected: FAIL because the parser requires `top3`, the controller exposes `chooseTop3`, and only three choices render.

- [ ] **Step 3: Implement strict Top5 parsing and selection**

```dart
if (skuId == null) {
  if (decisionPath != 'unknown_top5' ||
      candidates.length != 5 ||
      candidates.asMap().entries.any((e) => e.value.rank != e.key + 1) ||
      candidates.map((e) => e.skuId).toSet().length != 5) {
    throw const FormatException('Unknown objects require exactly five ranked candidates');
  }
}

enum CustomerResolutionSource {
  // legacy customerTop3 remains parseable
  customerTop3('customer_top3'),
  customerTop5('customer_top5'),
  customerCatalog('customer_catalog'),
  // existing values unchanged
}
```

Rename active callbacks and labels to Top5. Keep the existing `CatalogPicker` and catalog snapshot behavior; do not copy inference scores into catalog search results.

- [ ] **Step 4: Run focused Flutter tests**

Run: `flutter test test/inference/inference_models_test.dart test/checkout/checkout_models_test.dart test/checkout/checkout_controller_test.dart test/ui/customer_checkout_contract_test.dart test/ui/result_rail_test.dart`

Expected: PASS.

- [ ] **Step 5: Commit the in-memory and UI flow**

```powershell
git add apps/bakery_camera_flutter/lib/src/inference apps/bakery_camera_flutter/lib/src/checkout apps/bakery_camera_flutter/lib/src/ui apps/bakery_camera_flutter/test/inference apps/bakery_camera_flutter/test/checkout apps/bakery_camera_flutter/test/ui
git commit -m "feat: let customers choose Top5 or search catalog"
```

### Task 4: Drift Schema v5 and Immutable Audit Compatibility

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/app_database.dart`
- Regenerate: `apps/bakery_camera_flutter/lib/src/persistence/app_database.g.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_checkout_audit_store.dart`
- Test: `apps/bakery_camera_flutter/test/persistence/app_database_test.dart`
- Test: `apps/bakery_camera_flutter/test/persistence/checkout_audit_store_test.dart`

**Interfaces:**
- Consumes: `customerTop5`, `unknown_top5`, candidate ranks 1..5.
- Produces: schema v5 that preserves v4 rows and validates new writes.

- [ ] **Step 1: Write failing v4-to-v5 migration and audit tests**

```dart
test('v5 migration preserves legacy Top3 rows and accepts new Top5 rows', () async {
  final before = await createSchemaV4WithTop3Receipt();
  final database = await openCurrentSchema(before);
  expect(database.schemaVersion, 5);
  expect(await legacyCandidateRanks(database), [1, 2, 3]);
  await persistNewTop5Receipt(database);
  expect(await newCandidateRanks(database), [1, 2, 3, 4, 5]);
});
```

- [ ] **Step 2: Run persistence tests and verify schema/rank failure**

Run: `flutter test test/persistence/app_database_test.dart test/persistence/checkout_audit_store_test.dart`

Working directory: `apps/bakery_camera_flutter`

Expected: FAIL because schema v4 constrains candidate ranks to 1..3 and allowed sources exclude `customer_top5`.

- [ ] **Step 3: Implement schema v5**

Change candidate rank to `1..5`; allow both old/new Unknown paths and resolution sources. Add an explicit v4-to-v5 migration that rebuilds constrained tables through Drift table migrations while copying every column unchanged.

```dart
@override
int get schemaVersion => 5;

if (from == 4 && to == 5) {
  await migrator.alterTable(TableMigration(inferenceObjects));
  await migrator.alterTable(TableMigration(inferenceCandidates));
  await migrator.alterTable(TableMigration(objectResolutions));
  await migrator.alterTable(TableMigration(finalOrderLines));
  await _installIntegrityGuards();
  return;
}
```

- [ ] **Step 4: Regenerate Drift code**

Run: `dart run build_runner build --delete-conflicting-outputs`

Working directory: `apps/bakery_camera_flutter`

Expected: exit 0 and only generated Drift output changes.

- [ ] **Step 5: Verify persistence and migration tests**

Run: `flutter test test/persistence/app_database_test.dart test/persistence/checkout_audit_store_test.dart`

Expected: PASS, with legacy hashes/IDs unchanged and new Top5 ranks accepted.

- [ ] **Step 6: Commit schema and audit changes**

```powershell
git add apps/bakery_camera_flutter/lib/src/persistence apps/bakery_camera_flutter/test/persistence
git commit -m "feat: persist audited Top5 resolutions"
```

### Task 5: Admin, Integration, Documentation and Full Verification

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/admin/`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/`
- Modify: `apps/bakery_camera_flutter/README.md`
- Modify: relevant `apps/bakery_camera_flutter/test/admin/`, `test/integration/`, and test fixtures.

**Interfaces:**
- Consumes: legacy/new paths and sources from Tasks 1-4.
- Produces: readable audit labels and end-to-end evidence for both histories.

- [ ] **Step 1: Write failing integration assertions**

```dart
expect(savedInference.decisionPath, 'unknown_top5');
expect(savedCandidates.map((row) => row.rank), [1, 2, 3, 4, 5]);
expect(savedResolution.source, 'customer_top5');
expect(adminDetail.resolutionLabel, 'Top5 추천 선택');
```

- [ ] **Step 2: Update fixtures, admin labels and README**

Document that Top5/search changes the customer order only; the original inference remains `Unknown`. Admin filters must label `customer_top3` as legacy and `customer_top5` as the current recommendation path. Render an explicit `모두 아님` action that leaves the object unresolved, and render catalog-unavailable Top5 rows as disabled rather than silently dropping evidence.

- [ ] **Step 3: Run the complete Python default suite**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest`

Expected: all selected tests pass; artifact/GPU/slow skips remain explicitly unverified.

- [ ] **Step 4: Run Flutter analyze and full tests**

Run: `flutter analyze`

Run: `flutter test`

Working directory: `apps/bakery_camera_flutter`

Expected: both commands exit 0.

- [ ] **Step 5: Verify repository policy and diff hygiene**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m pytest tests/contract/test_repository_policy.py -q`

Run: `git diff --check`

Expected: repository policy passes and no whitespace errors are reported.

- [ ] **Step 6: Commit the completed assisted-resolution vertical**

```powershell
git add apps/bakery_camera_flutter/README.md apps/bakery_camera_flutter/lib/src/admin apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/test/admin apps/bakery_camera_flutter/test/integration docs/superpowers
git commit -m "docs: document Top5 assisted checkout"
```
