# 1.1.0 Admin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-device administrator mode that explains what happened at checkout, lets the prototype operator inspect and annotate mistakes, manages the customer product catalog safely, surfaces inference and artifact diagnostics, configures supported local settings, and always returns to the customer ready screen.

**Architecture:** Add an explicit `AppModeController` above the customer and admin shells. Admin screens read projections from the same immutable Drift audit database created by the customer foundation. Mutations are append-only annotations, new catalog revisions, supported settings changes, and audited retention actions; inference receipts and completed orders are never edited. A diagnostics facade combines persisted receipts with live `ScannerController`/worker status while preserving the canonical pipeline’s artifact and fail-closed contracts.

**Tech Stack:** Existing 1.1.0 Flutter/Material 3/Pretendard foundation, Drift typed queries and transactions, Widgetbook, Flutter widget/golden/semantics tests, Windows keyboard navigation, existing inference worker protocol and artifact manifests.

## Global Constraints

- Complete `2026-07-30-v1-1-0-customer-checkout-foundation.md` through Task 10 before beginning this plan.
- Treat `docs/superpowers/specs/2026-07-30-v1-1-0-self-checkout-admin-console-design.md` as the acceptance contract.
- The prototype operator may be both customer and administrator, but the UI modes remain visibly and behaviorally separate.
- Customer mode is the default at cold start and after payment. Admin exit always returns to a fresh customer-ready screen.
- Do not provide any admin action that rewrites raw inference, candidates, scores, boxes, timings, provenance, captured evidence, completed orders, or payments.
- Admin “correct answer” is an annotation with author/time/reason; it does not become a model or policy change.
- Product changes create catalog revisions. A completed order continues to display the product name and price snapshot captured at purchase.
- Diagnostics may display model/policy/config/artifact identity but may not bypass SHA verification, alter immutable policy thresholds, or silently fall back to legacy implementations.
- Retention preview is read-only. Retention execution requires explicit confirmation, records an event, and preserves aggregate receipts required by the approved policy.
- Preserve unrelated worktree changes and legacy/portable CPU boundaries.

---

## Task 1: Add explicit customer/admin mode ownership and guarded entry

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/app/app_mode_controller.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/admin_shell.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/admin_destination.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/app/bakery_app.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Test: `apps/bakery_camera_flutter/test/app/app_mode_controller_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/admin_shell_test.dart`

- [ ] **Step 1: Write failing mode-transition tests**

```dart
test('cold start and payment reset always select customer mode', () {
  final controller = AppModeController();
  expect(controller.mode, AppMode.customer);
  controller.enterAdmin();
  controller.onPaymentCompleted();
  expect(controller.mode, AppMode.customer);
});

testWidgets('admin exit shows ready and re-entry restores admin navigation state',
    (tester) async {
  await tester.pumpWidget(fixture.inAdmin());
  await tester.tap(find.text('거래 내역'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('고객 화면으로 돌아가기'));
  await tester.pumpAndSettle();
  expect(find.text('빵을 올려주세요'), findsOneWidget);
  expect(find.text('거래 내역'), findsNothing);
  fixture.modeController.enterAdmin();
  await tester.pumpAndSettle();
  expect(fixture.modeController.destination, AdminDestination.transactions);
});
```

- [ ] **Step 2: Run and confirm missing implementation failure**

Run:

```powershell
flutter test test\app\app_mode_controller_test.dart test\ui\admin\admin_shell_test.dart
```

Expected: FAIL at compile time.

- [ ] **Step 3: Implement mode and admin navigation**

Define:

```dart
enum AppMode { customer, admin }

enum AdminDestination {
  dashboard,
  transactions,
  reviewInbox,
  products,
  diagnostics,
  settings,
}
```

`AppModeController` owns mode and selected admin destination and preserves the last admin destination/filter state across customer-mode visits. Admin entry uses the approved prototype header control and a confirmation sheet explaining that an active customer checkout will be abandoned. Do not imply authentication in 1.1.0. Admin exit abandons only a genuinely empty/incomplete customer session through the audited application service; it never deletes a paid session.

- [ ] **Step 4: Build the admin shell**

Use a persistent left navigation rail at desktop widths, a compact drawer at 1024×720, visible “관리자 모드” label, and one fixed “고객 화면으로 돌아가기” action. Customer controls and live cart never render inside the shell.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\app lib\src\ui\admin test\app test\ui\admin
flutter test test\app\app_mode_controller_test.dart test\ui\admin\admin_shell_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/app apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/app apps/bakery_camera_flutter/test/ui/admin
git commit -m "feat: add guarded customer and admin modes"
```

---

## Task 2: Implement admin read projections and dashboard metrics

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/admin/admin_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/admin/admin_repository.dart`
- Create: `apps/bakery_camera_flutter/lib/src/persistence/database_admin_repository.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/dashboard_screen.dart`
- Test: `apps/bakery_camera_flutter/test/admin/admin_repository_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/dashboard_screen_test.dart`

- [ ] **Step 1: Write failing projection tests**

Seed fixed sessions and assert:

```dart
expect(summary.completedOrders, 3);
expect(summary.grossKrw, 21600);
expect(summary.scanAttempts, 5);
expect(summary.retakeSessions, 1);
expect(summary.unknownObjects, 2);
expect(summary.customerResolvedUnknownObjects, 1);
expect(summary.customerOverrides, 1);
expect(summary.manualCartLines, 1);
expect(summary.failedSessions, 1);
```

Use injected UTC date boundaries so results are deterministic in Asia/Seoul presentation.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\admin_repository_test.dart test\ui\admin\dashboard_screen_test.dart
```

Expected: FAIL because projections do not exist.

- [ ] **Step 3: Implement `AdminRepository` projections**

Expose:

```dart
Future<AdminDashboardSummary> dashboard(DateRange range);
Stream<AdminDashboardSummary> watchDashboard(DateRange range);
Future<List<AttentionItem>> recentAttentionItems({required int limit});
```

Compute:

- completed orders and gross from committed payments only;
- AI Unknown from immutable inference objects;
- customer-resolved Unknown from current resolution source;
- override from `customer_overrode_auto`;
- retake and failures from terminal session/attempt states;
- unresolved review count without counting abandoned empty sessions.

- [ ] **Step 4: Build a decision-oriented dashboard**

Top section answers “오늘 셀프 계산이 정상 동작했는가?” with completed checkouts, paid total, attention count, and system availability. Secondary cards show retake, AI Unknown, override, manual entry, and failure rates with numerator/denominator. A recent attention list links to transaction detail. Do not expose vanity charts or claim model accuracy.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\admin lib\src\persistence lib\src\ui\admin test\admin test\ui\admin
flutter test test\admin\admin_repository_test.dart test\ui\admin\dashboard_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin apps/bakery_camera_flutter/lib/src/persistence/database_admin_repository.dart apps/bakery_camera_flutter/lib/src/ui/admin/dashboard_screen.dart apps/bakery_camera_flutter/test/admin apps/bakery_camera_flutter/test/ui/admin/dashboard_screen_test.dart
git commit -m "feat: add audited admin dashboard projections"
```

---

## Task 3: Build transaction history and immutable transaction detail

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/transaction_history_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/transaction_detail_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/widgets/audit_fact_table.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/admin/admin_repository.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_admin_repository.dart`
- Test: `apps/bakery_camera_flutter/test/admin/transaction_projection_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/transaction_history_screen_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/transaction_detail_screen_test.dart`

- [ ] **Step 1: Write failing history/detail tests**

Cover filtering by date, session ID, payment status, resolution source, AI Unknown, retake, and failure. Detail assertions must show:

- checkout lifecycle timestamps;
- each scan attempt and retained image hash/path;
- immutable object SKU/Unknown, box, confidence, decision path, candidates;
- detector/model/policy/calibration/preprocessing/prototype hashes;
- customer resolution history and current resolution;
- final order and payment snapshot;
- measured stage timings without a performance claim.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\transaction_projection_test.dart test\ui\admin\transaction_history_screen_test.dart test\ui\admin\transaction_detail_screen_test.dart
```

Expected: FAIL because queries/screens are absent.

- [ ] **Step 3: Implement paged, stable projections**

Add:

```dart
Future<TransactionPage> transactions(TransactionFilter filter, PageCursor? after);
Future<AdminTransactionDetail> transactionDetail(String sessionId);
```

Sort by `startedAtUtc DESC, sessionId DESC`. Cursor contains both values. Return copied immutable view models, not Drift rows. Missing evidence files produce an integrity warning and never disappear from the timeline.

- [ ] **Step 4: Build history and detail UI**

History uses human-readable outcome labels first and technical badges second. Detail begins with “고객이 무엇을 결제했는가?” and “AI와 고객 판단이 어디서 달랐는가?”, then progressively discloses inference/provenance/timing evidence. Captured images remain local and show a missing/hash-mismatch state when verification fails.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\admin lib\src\persistence lib\src\ui\admin test\admin test\ui\admin
flutter test test\admin\transaction_projection_test.dart test\ui\admin\transaction_history_screen_test.dart test\ui\admin\transaction_detail_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin apps/bakery_camera_flutter/lib/src/persistence/database_admin_repository.dart apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/test/admin apps/bakery_camera_flutter/test/ui/admin
git commit -m "feat: add transaction audit history and detail"
```

---

## Task 4: Add review inbox and append-only administrator annotations

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/admin/review_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/admin/review_service.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/app_database.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_admin_repository.dart`
- Generated: `apps/bakery_camera_flutter/lib/src/persistence/app_database.g.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/review_inbox_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/review_detail_screen.dart`
- Test: `apps/bakery_camera_flutter/test/admin/review_service_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/review_inbox_screen_test.dart`

- [ ] **Step 1: Write failing review-priority and immutability tests**

Prioritize:

1. integrity failure;
2. customer override;
3. AI Unknown resolved by customer;
4. manual catalog resolution;
5. retake/failure.

Test that annotating a review creates a new row but leaves inference, customer resolution, and final order byte-for-byte unchanged.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\review_service_test.dart test\ui\admin\review_inbox_screen_test.dart
```

Expected: FAIL because annotation storage/service is absent.

- [ ] **Step 3: Add schema version 2 and migration test**

Add `admin_review_annotations`:

- `annotation_id`;
- `session_id`;
- nullable `attempt_id` and `object_id`;
- `review_status` (`open`, `reviewed`, `needs_follow_up`);
- nullable `correct_product_id`;
- `reason_code`;
- `note`;
- `author_label`;
- `created_at_utc`.

Upgrade schema 1→2 without modifying existing rows. Add a migration test that opens a version-1 fixture, upgrades, and verifies checkout history.

- [ ] **Step 4: Implement append-only review service**

```dart
Future<void> annotate(AdminReviewAnnotationDraft draft);
Future<ReviewPage> reviewInbox(ReviewFilter filter, PageCursor? after);
Future<ReviewDetail> reviewDetail(ReviewTarget target);
```

Validate correct product against an existing catalog revision but allow inactive historical products. Never trigger model training, policy edits, or catalog mutation.

- [ ] **Step 5: Build inbox/detail UI**

Use plain labels: “고객이 AI 추천을 바꿈”, “AI가 상품을 확정하지 못함”, “증빙 파일 확인 필요”. The annotation form explicitly states “이 기록은 모델 결과를 바꾸지 않습니다.” One main action saves the annotation.

- [ ] **Step 6: Generate and run tests**

Run:

```powershell
dart run build_runner build --delete-conflicting-outputs
dart format lib\src\admin lib\src\persistence lib\src\ui\admin test\admin test\ui\admin
flutter test test\persistence test\admin\review_service_test.dart test\ui\admin\review_inbox_screen_test.dart
flutter analyze
```

Expected: PASS, including schema 1→2 migration.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin apps/bakery_camera_flutter/lib/src/persistence apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/test/admin apps/bakery_camera_flutter/test/persistence apps/bakery_camera_flutter/test/ui/admin
git commit -m "feat: add append-only checkout review inbox"
```

---

## Task 5: Implement revisioned product management

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/admin/product_management_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/catalog/catalog_photo_store.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/product_management_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/product_editor_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_catalog_repository.dart`
- Test: `apps/bakery_camera_flutter/test/admin/product_management_service_test.dart`
- Test: `apps/bakery_camera_flutter/test/catalog/catalog_photo_store_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/product_management_screen_test.dart`

- [ ] **Step 1: Write failing revision tests**

Test:

- add a manually selectable product with null recognition SKU;
- import an approved JPEG/PNG product photo with relative path, byte size, SHA-256, media type, and provenance note;
- map at most one active product to a recognition SKU;
- edit name/price by creating a new catalog revision;
- deactivate instead of deleting a historical product;
- completed order retains old name/price;
- invalid price, duplicate product ID, and conflicting SKU mapping fail before commit.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\product_management_service_test.dart test\ui\admin\product_management_screen_test.dart
```

Expected: FAIL because the service/screens do not exist.

- [ ] **Step 3: Implement copy-on-write catalog revisions**

Every save:

1. reads the current active revision;
2. clones all product rows into a new UUID revision;
3. applies one validated change;
4. computes canonical JSON and SHA-256;
5. marks the new revision active and old revision inactive in one transaction;
6. appends an audit event with before/after revision IDs.

`product_id` stays stable across revisions. `recognition_sku_id` remains optional and unique among active products in the new revision. `CatalogPhotoStore` accepts only decoded JPEG/PNG files under the configured size limit, hashes and copies them into the application-data `catalog-media/{sha256}.{ext}` directory, and rejects path traversal or hash mismatch. It never accepts ImageGen output, a checkout capture, inference evidence, or a model/training/evaluation artifact as catalog photography.

- [ ] **Step 4: Build product list/editor**

Lead with customer display name, approved photo/fallback, price, availability, and “AI 연결됨/직접 선택 전용”. Put model SKU mapping and photo provenance under advanced disclosures. Explain that changing a product affects future checkouts only.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\admin lib\src\catalog lib\src\persistence lib\src\ui\admin test\admin test\catalog test\ui\admin
flutter test test\admin\product_management_service_test.dart test\catalog\catalog_photo_store_test.dart test\ui\admin\product_management_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin/product_management_service.dart apps/bakery_camera_flutter/lib/src/catalog/catalog_photo_store.dart apps/bakery_camera_flutter/lib/src/persistence/database_catalog_repository.dart apps/bakery_camera_flutter/lib/src/ui/admin/product_management_screen.dart apps/bakery_camera_flutter/lib/src/ui/admin/product_editor_screen.dart apps/bakery_camera_flutter/test/admin/product_management_service_test.dart apps/bakery_camera_flutter/test/catalog/catalog_photo_store_test.dart apps/bakery_camera_flutter/test/ui/admin/product_management_screen_test.dart
git commit -m "feat: add revisioned product management"
```

---

## Task 6: Add system diagnostics without runtime policy mutation

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/admin/diagnostics_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/admin/diagnostics_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/diagnostics_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_worker_client.dart`
- Test: `apps/bakery_camera_flutter/test/admin/diagnostics_service_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/diagnostics_screen_test.dart`

- [ ] **Step 1: Write failing factual diagnostics tests**

Assert the service reports:

- camera connection/readiness and last error;
- worker status/device/startup load/warmup;
- canonical detector, RepViT, conditional DINO, and fusion policy IDs;
- calibrated detector threshold from worker startup metrics;
- expected and observed artifact hashes;
- database schema/migration status and audit root;
- recent stage timing distribution and conditional-DINO rate from stored receipts;
- no setter for detector threshold, fusion margin, model path, or artifact hash.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\diagnostics_service_test.dart test\ui\admin\diagnostics_screen_test.dart
```

Expected: FAIL because diagnostics facade is missing.

- [ ] **Step 3: Expose a read-only worker snapshot**

Add an immutable `WorkerDiagnosticSnapshot` produced from already-validated startup events and fatal events. Do not add protocol commands that modify the worker. Artifact mismatch remains fatal; diagnostics reports it rather than offering “ignore”.

- [ ] **Step 4: Implement stored performance summaries**

Compute warmed receipt distributions only from explicitly selected completed attempts with stage timings. Label them “관측된 실행 시간” and display sample count/device/config hash. Do not call them benchmarks or performance improvements unless a committed benchmark receipt exists.

- [ ] **Step 5: Build diagnostics UI**

Begin with customer impact: “계산 가능/점검 필요”. Then camera, inference pipeline, artifact integrity, storage, and measured receipts. Provide copy-to-clipboard for IDs/hashes but no mutation fields.

- [ ] **Step 6: Run tests**

Run:

```powershell
dart format lib\src\admin lib\src\inference lib\src\ui\admin test\admin test\ui\admin
flutter test test\admin\diagnostics_service_test.dart test\ui\admin\diagnostics_screen_test.dart test\inference
flutter analyze
```

Expected: PASS with existing strict worker protocol tests unchanged.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin/diagnostics_models.dart apps/bakery_camera_flutter/lib/src/admin/diagnostics_service.dart apps/bakery_camera_flutter/lib/src/inference/inference_worker_client.dart apps/bakery_camera_flutter/lib/src/ui/admin/diagnostics_screen.dart apps/bakery_camera_flutter/test/admin/diagnostics_service_test.dart apps/bakery_camera_flutter/test/ui/admin/diagnostics_screen_test.dart
git commit -m "feat: add read-only pipeline diagnostics"
```

---

## Task 7: Add supported settings and audited retention

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/admin/settings_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/admin/settings_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/admin/retention_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/settings_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/admin/retention_preview_dialog.dart`
- Test: `apps/bakery_camera_flutter/test/admin/settings_service_test.dart`
- Test: `apps/bakery_camera_flutter/test/admin/retention_service_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/settings_screen_test.dart`

- [ ] **Step 1: Write failing settings and retention tests**

Supported settings:

- kiosk display name;
- retake retry limit;
- payment-complete display duration;
- customer auto-reset enabled;
- audit evidence retention days;
- locale fixed to Korean for 1.1.0;
- admin author label.

Test that unsupported keys and model/policy threshold keys are rejected. Retention tests use a temporary verified root and fixed clock; preview and execution counts must match.

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\admin\settings_service_test.dart test\admin\retention_service_test.dart test\ui\admin\settings_screen_test.dart
```

Expected: FAIL because services/screens are absent.

- [ ] **Step 3: Implement typed settings**

Store each setting with value, type, updated time, and author in a copy-on-write settings revision. Validate retry limit 1–5, complete duration 2–30 seconds, and evidence retention 7–3650 days. Activate the new revision in one transaction and apply it from the next customer session. Settings changes append before/after revision audit events. Never treat arbitrary database keys as UI settings.

- [ ] **Step 4: Implement two-phase retention**

`preview(cutoff)` enumerates exact eligible evidence files and sessions without mutation. `execute(previewId)`:

1. revalidates the preview and root containment;
2. marks rows `retention_pending`;
3. moves exact files into an app-owned quarantine directory;
4. commits evidence-removed metadata and retention event;
5. deletes only quarantined files;
6. records any partial failure for recovery.

Never delete database receipts, final order/payment snapshots, hashes, or review annotations in 1.1.0. Never recursively delete an unresolved or broad path.

- [ ] **Step 5: Build settings and confirmation UI**

Group “고객 화면”, “감사 기록”, and “관리자 표시”. Retention preview shows cutoff, affected sessions/files/bytes, preserved records, and irreversible effect before enabling the confirmation action.

- [ ] **Step 6: Run tests**

Run:

```powershell
dart format lib\src\admin lib\src\ui\admin test\admin test\ui\admin
flutter test test\admin\settings_service_test.dart test\admin\retention_service_test.dart test\ui\admin\settings_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/admin apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/test/admin apps/bakery_camera_flutter/test/ui/admin/settings_screen_test.dart
git commit -m "feat: add audited kiosk settings and retention"
```

---

## Task 8: Validate the complete admin experience and 1.1.0 release

**Files:**

- Create: `apps/bakery_camera_flutter/test/integration/admin_audit_journey_test.dart`
- Create: `apps/bakery_camera_flutter/test/ui/admin/admin_accessibility_test.dart`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_dashboard_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_transaction_detail_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_review_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_products_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_diagnostics_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/admin_settings_1280x820.png`
- Modify: `apps/bakery_camera_flutter/README.md`
- Create: `docs/releases/1.1.0.md`

- [ ] **Step 1: Write the full audit journey**

With a fixed clock and in-memory database:

1. complete a customer order containing registered, Top-3-resolved, overridden, and manual products;
2. enter admin mode;
3. verify dashboard metrics;
4. filter and open the transaction;
5. verify AI vs customer vs final-order facts;
6. append an admin correction annotation;
7. create a new catalog revision;
8. verify old order snapshot remains unchanged;
9. inspect read-only diagnostics;
10. change one supported setting;
11. preview retention without executing it;
12. return to a fresh customer-ready screen.

- [ ] **Step 2: Add accessibility and visual regression coverage**

Test 1024×720/1280×820, 100%/200% text, keyboard traversal, selection/focus visibility, Korean semantics, table readability, progressive disclosure, and explicit confirmation for retention. Golden files must be visually reviewed before commit.

- [ ] **Step 3: Run generated-code and full Flutter verification**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
dart run build_runner build --delete-conflicting-outputs
dart run tool\verify_ui_assets.dart
flutter test
flutter analyze
```

Expected: PASS.

- [ ] **Step 4: Run repository-wide relevant checks**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner
$env:PYTHONPATH='src'
python -m pytest tests\contract -q
python -m pytest tests\unit -q
```

Expected: PASS. Artifact/GPU/performance suites not available in this environment must be recorded as unverified, never passed.

- [ ] **Step 5: Build and smoke-test the Windows release**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
flutter build windows --release
& .\build\windows\x64\runner\Release\bakery_camera_prototype.exe
```

Manually verify cold-start customer mode, one complete simulated checkout, admin entry, transaction visibility, annotation, diagnostics, settings, and return to ready. Stop the app normally. Do not infer accuracy or latency from this smoke test.

- [ ] **Step 6: Complete release documentation**

`docs/releases/1.1.0.md` records:

- customer/admin scope;
- database schema version and migration path;
- catalog/font/generated-asset IDs and SHA manifests;
- exact test/build commands and results;
- unavailable suites;
- simulated payment limitation;
- audit/retention behavior;
- known prototype limitation that admin mode has no authentication;
- canonical inference pipeline/config/artifact identities used in the release.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/test/integration apps/bakery_camera_flutter/test/ui/admin apps/bakery_camera_flutter/README.md docs/releases/1.1.0.md
git commit -m "release: verify BIXOLON bakery checkout 1.1.0"
```

---

## Admin Plan Exit Criteria

- The app opens in customer mode and always returns there after payment or explicit admin exit.
- Dashboard, transaction history/detail, review inbox, product management, diagnostics, and settings are available in one coherent admin shell.
- Every admin-visible inference fact can be traced to immutable stored evidence and provenance.
- Annotations, catalog revisions, settings changes, and retention actions are audited without rewriting history.
- Product management supports direct-selection-only products and keeps recognition identity separate.
- Diagnostics is useful but read-only for calibrated inference/policy/artifact controls.
- Full Flutter tests, analyzer, relevant repository tests, golden/accessibility review, Windows release build, and manual smoke test have recorded results.
