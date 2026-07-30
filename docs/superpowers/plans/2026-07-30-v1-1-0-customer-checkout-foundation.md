# 1.1.0 Customer Checkout Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the evaluator-first Flutter screen with a customer self-checkout flow that scans bread, fails closed on uncertain inference, lets the customer resolve products from Top 3 or the full catalog, simulates payment, commits a reproducible audit record, and returns to the ready screen.

**Architecture:** Keep `ScannerController` as the camera/inference adapter and add a `CheckoutController` application state machine above it. Store catalog, sessions, attempts, immutable inference receipts, customer resolutions, final orders, payments, settings, and retention events in a typed Drift database; store captured images in a content-hashed audit file store. Customer choices never mutate the inference receipt: they create separate `ObjectResolution` rows. One `commitPayment` database transaction persists the final order, payment, terminal session state, and audit event before the UI may show completion.

**Tech Stack:** Flutter 3.44.7/Dart 3.12, Material 3, Pretendard 1.3.9, Drift 2.34.3 with `drift_flutter` 0.3.1, `crypto` 3.0.7, `uuid` 4.6.0, `path_provider` 2.1.6, Widgetbook 3.25.0, `flutter_test`, Drift in-memory tests, Flutter golden and semantics tests, Windows release build.

## Global Constraints

- Treat `docs/superpowers/specs/2026-07-30-v1-1-0-self-checkout-admin-console-design.md` as the acceptance contract.
- Preserve the canonical inference contract and strict JSON parser. A worker `Unknown` remains `Unknown` in its immutable receipt and is excluded from AI registered-SKU totals.
- Customer resolution is a checkout fact, not a model correction. Persist its source as one of the five approved `CustomerResolutionSource` values.
- Never synthesize a product candidate, candidate score, detector box, provenance hash, or model decision path.
- Hash the exact captured file before moving it into audit storage. Persist its relative path, byte size, and SHA-256 together.
- Do not modify `portable_cpu_smoke/`, legacy inference behavior, or canonical pipeline configuration.
- Preserve unrelated worktree changes, including `.github/workflows/ci.yml` and `tests/contract/test_repository_policy.py`.
- Use Korean customer copy; technical hashes, timings, and model names remain absent from customer screens.
- Generated illustrations are UI-only assets. They never become product photos, camera evidence, model inputs, training data, or evaluation data.
- Every behavior change starts with a failing test and ends with focused tests plus `flutter analyze`.

---

## Task 1: Pin the 1.1.0 application and tooling foundation

**Files:**

- Modify: `apps/bakery_camera_flutter/pubspec.yaml`
- Modify: `apps/bakery_camera_flutter/pubspec.lock`
- Create: `apps/bakery_camera_flutter/tool/download_pretendard.ps1`
- Create: `apps/bakery_camera_flutter/assets/fonts/pretendard_manifest.json`
- Create: `apps/bakery_camera_flutter/assets/fonts/OFL.txt`
- Create after the pinned download: `apps/bakery_camera_flutter/assets/fonts/Pretendard-Regular.otf`
- Create after the pinned download: `apps/bakery_camera_flutter/assets/fonts/Pretendard-Medium.otf`
- Create after the pinned download: `apps/bakery_camera_flutter/assets/fonts/Pretendard-SemiBold.otf`
- Create after the pinned download: `apps/bakery_camera_flutter/assets/fonts/Pretendard-Bold.otf`
- Test: `apps/bakery_camera_flutter/test/assets/font_manifest_test.dart`

- [ ] **Step 1: Write the failing font-manifest contract test**

```dart
test('bundled Pretendard files match the declared immutable manifest', () {
  final manifest = jsonDecode(
    File('assets/fonts/pretendard_manifest.json').readAsStringSync(),
  ) as Map<String, Object?>;
  expect(manifest['release'], '1.3.9');
  final files = manifest['files']! as List<Object?>;
  expect(files, hasLength(5));
  for (final value in files.cast<Map<String, Object?>>()) {
    final file = File('assets/fonts/${value['path']}');
    expect(file.existsSync(), isTrue, reason: file.path);
    expect(file.lengthSync(), value['bytes']);
    expect(sha256.convert(file.readAsBytesSync()).toString(), value['sha256']);
  }
});
```

- [ ] **Step 2: Run the test to verify it fails because the manifest/assets do not exist**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
flutter test test\assets\font_manifest_test.dart
```

Expected: FAIL with `PathNotFoundException` for `pretendard_manifest.json`.

- [ ] **Step 3: Set the application version and add exact dependency families**

Change `version` to `1.1.0+4` and add:

```yaml
dependencies:
  flutter:
    sdk: flutter
  camera: 0.12.0+2
  camera_windows: 0.2.6+4
  crypto: ^3.0.7
  cupertino_icons: ^1.0.8
  drift: ^2.34.3
  drift_flutter: ^0.3.1
  flutter_svg: ^2.3.0
  path: 1.9.1
  path_provider: ^2.1.6
  uuid: ^4.6.0

dev_dependencies:
  build_runner: ^2.15.3
  drift_dev: ^2.34.3
  flutter_lints: ^6.0.0
  flutter_test:
    sdk: flutter
  widgetbook: ^3.25.0
```

Declare the four OTF files with weights 400, 500, 600, and 700 under the `Pretendard` family. Declare `assets/illustrations/` and `assets/asset_manifest.json`.

- [ ] **Step 4: Implement the pinned font acquisition script**

`download_pretendard.ps1` must:

1. Download `https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip`.
2. Extract into a newly created temporary directory.
3. Copy the four named OTF files and `LICENSE` as `OFL.txt`.
4. Compute byte size and SHA-256 for all five outputs.
5. Write sorted JSON with `release`, `source_url`, `license`, and `files`.
6. Refuse to overwrite a non-matching existing asset unless `-Replace` is supplied.
7. Remove only its verified temporary directory in `finally`.

- [ ] **Step 5: Generate the lockfile and assets**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tool\download_pretendard.ps1
flutter pub get
```

Expected: all dependencies resolve for Dart 3.12 and the five font files match the generated manifest.

- [ ] **Step 6: Run the focused test and analyzer**

Run:

```powershell
flutter test test\assets\font_manifest_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/pubspec.yaml apps/bakery_camera_flutter/pubspec.lock apps/bakery_camera_flutter/tool/download_pretendard.ps1 apps/bakery_camera_flutter/assets/fonts apps/bakery_camera_flutter/test/assets/font_manifest_test.dart
git commit -m "build: pin v1.1.0 Flutter and Pretendard foundation"
```

---

## Task 2: Define catalog, checkout, receipt, and order domain contracts

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/catalog/product.dart`
- Create: `apps/bakery_camera_flutter/lib/src/checkout/checkout_models.dart`
- Create: `apps/bakery_camera_flutter/lib/src/checkout/checkout_state.dart`
- Create: `apps/bakery_camera_flutter/lib/src/checkout/checkout_ports.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/checkout_models_test.dart`

- [ ] **Step 1: Write failing tests for identity separation and resolution sources**

```dart
test('product identity is independent from recognition SKU identity', () {
  const product = Product(
    productId: 'product-cream-bun',
    displayName: '크림빵',
    unitPrice: 2800,
    recognitionSkuId: null,
    categoryId: 'filled-bread',
    photoAssetPath: null,
    active: true,
    sortOrder: 20,
  );
  expect(product.productId, 'product-cream-bun');
  expect(product.recognitionSkuId, isNull);
});

test('customer resolution source parses only the five audited values', () {
  expect(
    CustomerResolutionSource.values.map((value) => value.storageValue).toSet(),
    {
      'ai_auto_customer_accepted',
      'customer_top3',
      'customer_catalog',
      'customer_overrode_auto',
      'customer_manual_cart',
    },
  );
  expect(
    () => CustomerResolutionSource.parse('model_autocorrected'),
    throwsFormatException,
  );
});
```

- [ ] **Step 2: Run the test and confirm missing types fail compilation**

Run:

```powershell
flutter test test\checkout\checkout_models_test.dart
```

Expected: FAIL because `Product` and checkout domain types do not exist.

- [ ] **Step 3: Implement immutable domain types and enums**

Define:

```dart
enum CheckoutPhase {
  ready,
  analyzing,
  retakeRequired,
  customerReview,
  orderReview,
  paying,
  paymentComplete,
  recoverableFailure,
  terminalFailure,
}

enum CustomerResolutionSource {
  aiAutoCustomerAccepted('ai_auto_customer_accepted'),
  customerTop3('customer_top3'),
  customerCatalog('customer_catalog'),
  customerOverrodeAuto('customer_overrode_auto'),
  customerManualCart('customer_manual_cart');

  const CustomerResolutionSource(this.storageValue);
  final String storageValue;
}
```

Also implement `Product`, `CatalogRevision`, `CheckoutLine`, `ObjectDraft`, `ObjectResolutionDraft`, `FinalOrderDraft`, `PaymentReceipt`, `CheckoutFailure`, and immutable `CheckoutState`. Required invariants:

- monetary values are non-negative integer KRW;
- quantities are positive;
- `recognitionSkuId` and an approved `photoAssetPath` are nullable but `productId` and `categoryId` never are;
- only inference objects can carry `objectId`;
- one object draft has either an accepted product or an unresolved candidate set;
- candidate sets preserve exact rank, SKU ID, SKU name, and score from `InferenceResult`;
- `CheckoutState.canPay` requires `orderReview`, no unresolved objects, and at least one positive-quantity line.

- [ ] **Step 4: Define application ports without storage/framework coupling**

```dart
abstract interface class CheckoutAuditStore {
  Future<List<InterruptedCheckout>> interruptNonterminalSessions(
    DateTime detectedAt,
  );
  Future<String> beginSession(SessionSnapshot snapshot);
  Future<StagedAttempt> stageAttempt({
    required String sessionId,
    required int attemptNumber,
    required CapturedAuditFile image,
  });
  Future<PersistedAttempt> completeAttempt({
    required StagedAttempt attempt,
    required InferenceResult result,
    required ImmutableJsonReceipt receipt,
  });
  Future<void> recordResolution(ObjectResolutionDraft resolution);
  Future<void> replaceDraftOrder(String sessionId, List<CheckoutLine> lines);
  Future<PaymentReceipt> commitSimulatedPayment(FinalOrderDraft order);
  Future<void> abandonSession(String sessionId, String reason);
}

abstract interface class CatalogRepository {
  Future<CatalogSnapshot> activeCatalog();
  Future<Product?> productForRecognitionSku(int recognitionSkuId);
  Future<CustomerCatalogDiscovery> customerDiscovery();
  Future<List<Product>> search(String query);
}
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
dart format lib\src\catalog lib\src\checkout test\checkout
flutter test test\checkout\checkout_models_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/catalog apps/bakery_camera_flutter/lib/src/checkout apps/bakery_camera_flutter/test/checkout
git commit -m "feat: define checkout and catalog domain contracts"
```

---

## Task 3: Implement the typed local audit database and migrations

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/persistence/app_database.dart`
- Generated: `apps/bakery_camera_flutter/lib/src/persistence/app_database.g.dart`
- Create: `apps/bakery_camera_flutter/lib/src/persistence/database_factory.dart`
- Create: `apps/bakery_camera_flutter/lib/src/persistence/database_checkout_audit_store.dart`
- Create: `apps/bakery_camera_flutter/lib/src/persistence/database_catalog_repository.dart`
- Create: `apps/bakery_camera_flutter/test/persistence/app_database_test.dart`
- Create: `apps/bakery_camera_flutter/test/persistence/checkout_audit_store_test.dart`

- [ ] **Step 1: Write failing database schema and constraint tests**

Test an in-memory database for:

```dart
test('schema rejects a registered inference object without provenance', () async {
  await expectLater(
    db.into(db.inferenceObjects).insert(
      InferenceObjectsCompanion.insert(
        attemptId: 'attempt-1',
        objectId: 'object-1',
        skuId: const Value(7),
        skuName: '크루아상',
        decisionPath: 'repvit_direct',
        confidence: 0.97,
        bboxJson: '[10,20,100,150]',
        detectorSource: 'rfdetr_large_bakery_v1',
        detectorScore: 0.95,
        provenanceJson: '{}',
      ),
    ),
    throwsA(isA<InvalidDataException>()),
  );
});

test('payment commit is idempotent by session id', () async {
  final first = await store.commitSimulatedPayment(order);
  final second = await store.commitSimulatedPayment(order);
  expect(second.paymentId, first.paymentId);
  expect(await db.select(db.finalOrders).get(), hasLength(1));
  expect(await db.select(db.simulatedPayments).get(), hasLength(1));
});
```

- [ ] **Step 2: Run and verify compilation fails**

Run:

```powershell
flutter test test\persistence\app_database_test.dart test\persistence\checkout_audit_store_test.dart
```

Expected: FAIL because the database and repositories do not exist.

- [ ] **Step 3: Define schema version 1**

Create Drift tables with explicit text primary keys and foreign keys:

- `catalog_revisions`
- `products`
- `checkout_sessions`
- `scan_attempts`
- `inference_objects`
- `inference_candidates`
- `object_resolutions`
- `draft_order_lines`
- `final_orders`
- `final_order_lines`
- `simulated_payments`
- `audit_events`
- `settings_revisions`
- `app_settings`
- `retention_events`

Use integer microseconds UTC for timestamps, integer KRW for price, integer bytes, real probabilities, and JSON text only for canonical boxes/provenance/config snapshots. Product revisions include nullable approved photo relative path, byte size, SHA-256, media type, and provenance note as one all-null/all-present group. Add unique constraints for `(attempt_id, object_id)`, `(inference_object_id, rank)`, and one payment per session. Enable foreign keys in `beforeOpen`.

Install `settings-v1` with retry limit 2, payment-complete duration 4 seconds, customer auto-reset enabled, evidence retention 90 days, Korean locale, kiosk display name `BIXOLON Bakery`, and admin author label `prototype-admin`. Sessions reference one immutable settings revision so mid-session changes apply only to the next customer.

`inference_objects` validation must enforce:

- registered: non-null SKU, non-`Unknown` name, registered decision path, no candidates;
- unknown: null SKU, name `Unknown`, path `unknown_top3`, exactly three ranked candidates recorded in the same transaction;
- provenance JSON includes every hash already required by `InferenceObject.fromJson`.

- [ ] **Step 4: Implement database creation and migration hooks**

Production uses:

```dart
BakeryDatabase.production()
    : super(driftDatabase(
        name: 'bixolon_bakery_checkout_v1_1_0',
        native: const DriftNativeOptions(shareAcrossIsolates: false),
      ));
```

Tests use `NativeDatabase.memory()`. Set `schemaVersion => 1`; reject any database with a newer schema. Export `schemaVersion`, application version, and last migration result through a diagnostic query.

- [ ] **Step 5: Implement repositories and the atomic payment transaction**

`beginSession` snapshots the active catalog revision, operational settings revision, and the already-verified model/calibration/preprocessing/policy identities. `stageAttempt` inserts the attempt and hashed image reference before inference is invoked. `completeAttempt` inserts the canonical immutable JSON receipt reference, all objects, candidates, provenance, timings, startup metrics, presentation state, and retake reason in one transaction. `commitSimulatedPayment` must:

1. return the existing receipt if the session already has a payment;
2. verify every object has a current resolution;
3. verify requested product IDs and prices match the session’s catalog revision;
4. copy draft lines to immutable final lines;
5. insert final order and simulated payment;
6. mark the session `completed`;
7. append `payment_committed`;
8. verify the pending final-order receipt path, byte size, and SHA-256;
9. commit once.

Any failure rolls back every write in that list.

- [ ] **Step 6: Generate code and run database tests**

Run:

```powershell
dart run build_runner build --delete-conflicting-outputs
dart format lib\src\persistence test\persistence
flutter test test\persistence\app_database_test.dart test\persistence\checkout_audit_store_test.dart
flutter analyze
```

Expected: PASS with schema version 1 and atomic rollback assertions.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/persistence apps/bakery_camera_flutter/test/persistence
git commit -m "feat: add immutable checkout audit database"
```

---

## Task 4: Add content-hashed image audit storage

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/audit/audit_file_store.dart`
- Create: `apps/bakery_camera_flutter/lib/src/audit/canonical_json_encoder.dart`
- Create: `apps/bakery_camera_flutter/lib/src/audit/sha256_file_hasher.dart`
- Create: `apps/bakery_camera_flutter/test/audit/audit_file_store_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_checkout_audit_store.dart`

- [ ] **Step 1: Write failing tests for copy, hash, deduplication, and traversal rejection**

```dart
test('stores bytes under session/attempt with verified metadata', () async {
  final stored = await store.retainCapture(
    sessionId: '00000000-0000-4000-8000-000000000001',
    attemptNumber: 1,
    capturedAtUtc: DateTime.utc(2026, 7, 30, 1, 2, 3),
    sourcePath: source.path,
  );
  expect(
    stored.relativePath,
    'sessions/2026/07/30/00000000-0000-4000-8000-000000000001/'
    'attempt-001.jpg',
  );
  expect(stored.byteSize, 4);
  expect(stored.sha256, sha256.convert([1, 2, 3, 4]).toString());
  expect(await File(store.resolve(stored.relativePath)).readAsBytes(), [1, 2, 3, 4]);
});

test('rejects identifiers that could escape the audit root', () async {
  await expectLater(
    store.retainCapture(
      sessionId: '..',
      attemptNumber: 1,
      capturedAtUtc: DateTime.utc(2026, 7, 30),
      sourcePath: source.path,
    ),
    throwsArgumentError,
  );
});
```

- [ ] **Step 2: Run and confirm missing implementation failure**

Run:

```powershell
flutter test test\audit\audit_file_store_test.dart
```

Expected: FAIL at compile time.

- [ ] **Step 3: Implement safe two-phase file retention**

`retainCapture` must stream SHA-256, copy to `attempt-NNN.jpg.pending`, flush, verify byte count/hash, atomically rename to `attempt-NNN.jpg`, and return relative path metadata. Only UUID-shaped session IDs, positive attempt numbers, and UTC timestamps are accepted. The resolved final path must remain under `sessions/YYYY/MM/DD/{session_id}/`. If the final file already exists, return it only when its size and hash match; otherwise fail closed. Never delete the camera source until the database has accepted its metadata.

- [ ] **Step 4: Integrate the file store with attempt persistence**

Add `retainInferenceReceipt` and `retainFinalOrderReceipt`. They encode validated domain objects with lexicographically sorted JSON object keys and stable numeric formatting, write `attempt-NNN.inference.json` and `final-order.json` through the same pending/flush/hash/rename process, and return immutable metadata. On database failure, keep the retained file and append a recovery marker; startup recovery flags orphaned files for admin review instead of deleting evidence automatically.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\audit test\audit
flutter test test\audit\audit_file_store_test.dart test\persistence\checkout_audit_store_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/audit apps/bakery_camera_flutter/lib/src/persistence/database_checkout_audit_store.dart apps/bakery_camera_flutter/test/audit
git commit -m "feat: retain content-hashed scan evidence"
```

---

## Task 5: Seed a revisioned product catalog and full-list search

**Files:**

- Create: `apps/bakery_camera_flutter/assets/catalog/catalog_v1.json`
- Create: `apps/bakery_camera_flutter/assets/catalog/catalog_v1.sha256`
- Create: `apps/bakery_camera_flutter/lib/src/catalog/catalog_seed.dart`
- Modify: `apps/bakery_camera_flutter/pubspec.yaml`
- Modify: `apps/bakery_camera_flutter/lib/src/persistence/database_catalog_repository.dart`
- Test: `apps/bakery_camera_flutter/test/catalog/catalog_seed_test.dart`
- Test: `apps/bakery_camera_flutter/test/catalog/catalog_repository_test.dart`

- [ ] **Step 1: Write failing seed and search tests**

```dart
test('seed import creates one immutable revision and active products', () async {
  await seed.installIfEmpty();
  final snapshot = await repository.activeCatalog();
  expect(snapshot.revisionId, 'catalog-v1');
  expect(snapshot.products, isNotEmpty);
  expect(snapshot.products.every((product) => product.unitPrice >= 0), isTrue);
});

test('search uses normalized Korean display name and stable sort order', () async {
  final result = await repository.search('크림');
  expect(result.map((product) => product.displayName), contains('크림빵'));
  expect(result, orderedEquals([...result]..sort(Product.customerSort)));
});
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
flutter test test\catalog
```

Expected: FAIL because catalog seed data is absent.

- [ ] **Step 3: Add the prototype catalog**

Create deterministic JSON with:

```json
{
  "revision_id": "catalog-v1",
  "currency": "KRW",
  "products": [
    {
      "product_id": "product-almond-campagne",
      "display_name": "아몬드 깜빠뉴",
      "unit_price": 4800,
      "recognition_sku_id": 1,
      "category_id": "rustic-bread",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 10
    },
    {
      "product_id": "product-walnut-donut",
      "display_name": "호두 도넛",
      "unit_price": 3200,
      "recognition_sku_id": 2,
      "category_id": "donut",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 20
    },
    {
      "product_id": "product-croissant",
      "display_name": "크루아상",
      "unit_price": 3000,
      "recognition_sku_id": 3,
      "category_id": "pastry",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 30
    },
    {
      "product_id": "product-pastry-bread",
      "display_name": "페이스트리 빵",
      "unit_price": 3500,
      "recognition_sku_id": 4,
      "category_id": "pastry",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 40
    },
    {
      "product_id": "product-mini-bread",
      "display_name": "미니 식빵",
      "unit_price": 2500,
      "recognition_sku_id": 5,
      "category_id": "loaf",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 50
    },
    {
      "product_id": "product-cream-bun",
      "display_name": "크림빵",
      "unit_price": 2800,
      "recognition_sku_id": null,
      "category_id": "filled-bread",
      "photo_asset_path": null,
      "active": true,
      "sort_order": 60
    }
  ]
}
```

The seed is prototype commercial data, not a model artifact. Compute and commit its SHA-256 sidecar. Import once; never edit an existing revision in place. Product photos stay null until the operator imports approved, licensed, locally hashed catalog photography in the admin product workflow; the UI uses a neutral non-identifying bread icon plus the customer’s selected camera crop rather than generating or fabricating a product photo.

- [ ] **Step 4: Implement search and SKU mapping**

Normalize query by trimming, lowercasing ASCII, and removing spaces. Search only active products. `productForRecognitionSku` returns null for missing/inactive mappings and never substitutes by display name. `customerDiscovery` returns frequently purchased products from completed orders first, then stable photo/category groups, name search, and the complete active catalog; absent approved photography uses the explicit neutral fallback.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\catalog test\catalog
flutter test test\catalog
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/assets/catalog apps/bakery_camera_flutter/pubspec.yaml apps/bakery_camera_flutter/lib/src/catalog apps/bakery_camera_flutter/lib/src/persistence/database_catalog_repository.dart apps/bakery_camera_flutter/test/catalog
git commit -m "feat: seed revisioned customer product catalog"
```

---

## Task 6: Implement the checkout state machine above ScannerController

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/checkout/checkout_controller.dart`
- Create: `apps/bakery_camera_flutter/lib/src/checkout/inference_checkout_mapper.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/checkout_controller_test.dart`
- Modify: `apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart`

- [ ] **Step 1: Write failing transition tests**

Cover:

```dart
test('empty or unsafe scan requires retake and exposes no candidates', () async {
  worker.completeAnalysis(emptyResult);
  await controller.scan();
  expect(controller.state.phase, CheckoutPhase.retakeRequired);
  expect(controller.state.objectDrafts, isEmpty);
});

test('unknown scan enters review with exact Top 3', () async {
  worker.completeAnalysis(resultWithOneUnknown);
  await controller.scan();
  expect(controller.state.phase, CheckoutPhase.customerReview);
  expect(controller.state.activeObject!.candidates, resultWithOneUnknown.objects.single.candidates);
});

test('all mapped registered detections go directly to editable order review', () async {
  worker.completeAnalysis(registeredResult);
  await controller.scan();
  expect(controller.state.phase, CheckoutPhase.orderReview);
  expect(controller.state.objectDrafts.every((object) => object.product != null), isTrue);
});
```

Also test illegal transitions, single-flight scan/payment, retry limit/manual-cart entry, count-mismatch return to retake, analysis cancellation/abandonment, camera/worker terminal failure, image/attempt persistence before the worker call, immutable receipt persistence before presentation, and cold-start interruption.

- [ ] **Step 2: Run and confirm missing controller failure**

Run:

```powershell
flutter test test\checkout\checkout_controller_test.dart
```

Expected: FAIL at compile time.

- [ ] **Step 3: Implement inference-to-checkout mapping**

For every `InferenceObject`:

- registered SKU with active product mapping: preselect product and enter the editable `orderReview` state when every object maps;
- registered SKU without active product mapping: unresolved full-catalog choice, preserving AI result;
- `Unknown`: unresolved with the exact Top 3; each candidate maps independently to an active product or remains unavailable;
- unsafe count/location/image/detection/separation/candidate evidence: `retakeRequired` with one factual reason and no product output;
- image/attempt persistence failure: stop before inference and enter the actionable storage failure state;
- strict worker-result or immutable-receipt persistence failure: present no customer resolution and retain technical audit evidence.

Do not change `InferenceResult`, `InferenceObject`, candidate scores, or provenance.

- [ ] **Step 4: Implement controller commands**

Implement:

```dart
Future<void> initialize();
Future<void> scan();
Future<void> cancelScan();
Future<void> retake();
Future<void> enterManualCart();
Future<void> chooseTop3(String objectId, int recognitionSkuId);
Future<void> chooseCatalog(String objectId, String productId);
Future<void> acceptAiSelection(String objectId);
Future<void> continueToOrderReview();
Future<void> reportCountMismatch();
Future<void> addManualProduct(String productId);
Future<void> setQuantity(String productId, int quantity);
Future<void> removeProduct(String productId);
Future<void> pay();
Future<void> startNextCustomer();
Future<void> close();
```

Every choice writes a new resolution row while preserving previous rows as history; “current” is the newest sequence. Unchanged automatic objects receive `ai_auto_customer_accepted` only when the final order is frozen for payment. The cart aggregates customer product quantity, while inference totals remain separately queryable. `enterManualCart` is enabled only after the session-snapshotted retry limit and records lines with no object ID, box, location, or confidence.

- [ ] **Step 5: Stage capture evidence before invoking inference**

Change `ScannerController.analyze` to accept a checkout-only `beforeInference` callback:

```dart
typedef BeforeInference = Future<void> Function(ScannerCapture capture);

Future<void> analyze({BeforeInference? beforeInference});
```

After capture and canonical-size decoding, `ScannerController` awaits the callback before `_worker.analyze`. `CheckoutController` uses it to retain the image and call `stageAttempt`; a callback failure proves `worker.analyzeCalls == 0`. After strict parsing, checkout writes `attempt-NNN.inference.json` and calls `completeAttempt` before publishing `retakeRequired`, `customerReview`, or `orderReview`. Add a narrowly scoped `releaseCurrentCapture()`; invoke it only after retained metadata is durable. Preserve the optional callback and existing `resetCapture()` compatibility tests for evaluator-level unit tests.

- [ ] **Step 6: Run tests**

Run:

```powershell
dart format lib\src\checkout lib\src\scanner test\checkout test\scanner
flutter test test\checkout\checkout_controller_test.dart test\scanner\scanner_controller_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/checkout apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart apps/bakery_camera_flutter/test/checkout apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart
git commit -m "feat: orchestrate audited customer checkout states"
```

---

## Task 7: Build the Material 3 BIXOLON design system and component catalog

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/bixolon_brand.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_primary_button.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_status_banner.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/product_tile.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/quantity_stepper.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/price_text.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart`
- Create: `apps/bakery_camera_flutter/widgetbook/main.dart`
- Test: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/goldens/design_system_1280x820.png`

- [ ] **Step 1: Write failing token, touch-target, text-scale, and golden tests**

Assert:

- `ThemeData.useMaterial3 == true`;
- `fontFamily == Pretendard`;
- color roles come from `BixolonThemeExtension`;
- primary action minimum height is 56 logical pixels;
- controls preserve at least 48×48 hit regions;
- price uses tabular figures;
- 200% text scale has no overflow at 1024×720;
- focused controls have a visible non-color-only outline.

- [ ] **Step 2: Run and record expected failures**

Run:

```powershell
flutter test test\ui\design_system_test.dart
```

Expected: FAIL because the extension and components do not exist.

- [ ] **Step 3: Implement tokens and components**

Use the approved palette and typography:

- canvas `#F7F7F5`;
- ink `#171717`;
- brand/action orange `#EE7203`;
- focus blue `#176BFF`;
- confirmed teal `#0E8A72`;
- uncertainty amber `#C76B00`;
- error red `#C43A3A`;
- spacing scale 4/8/12/16/24/32/48;
- radii 6 for controls, 12 for customer surfaces;
- weights 400/500/600/700 only.

Use one emphasized action per page. Status banners include icon, title, and explanatory text so meaning is not color-only.

- [ ] **Step 4: Add Widgetbook use cases**

Catalog ready, loading, uncertainty, error, disabled, focus, long Korean text, 200% text, each candidate availability state, quantities 1/9/99, and 0/large KRW prices. Widgetbook is a development entry point only and is not imported by production `main.dart`.

- [ ] **Step 5: Update and verify the golden**

Run:

```powershell
flutter test --update-goldens test\ui\design_system_test.dart
flutter test test\ui\design_system_test.dart
flutter analyze
```

Expected: PASS after visually checking the updated PNG at 100% scale.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui apps/bakery_camera_flutter/widgetbook apps/bakery_camera_flutter/test/ui/design_system_test.dart apps/bakery_camera_flutter/test/ui/goldens/design_system_1280x820.png
git commit -m "feat: add BIXOLON customer design system"
```

---

## Task 8: Replace the evaluator screen with the customer checkout screens

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/app/bakery_app.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/analyzing_view.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/retake_required_view.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/payment_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/main.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`
- Create: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`

- [ ] **Step 1: Replace evaluator assertions with customer acceptance tests**

Write widget tests for:

- ready: “빵을 올려주세요” and one “빵 확인하기” CTA;
- analyzing: factual progress copy and disabled navigation;
- retake: no products/scores/boxes, only rearrangement guidance and “다시 촬영”;
- repeated retake: direct-entry action appears only at the snapshotted retry limit;
- customer review: one object question at a time, Top 3 plus “전체 상품에서 찾기”;
- registered result override: customer can replace an AI-selected product from the full list;
- full catalog: frequent products, categories, name search, then complete active list;
- order review: grouped products, quantity, unit price, total, add/remove, and a physical-count mismatch action;
- payment: single-flight and no completion before durable commit;
- completion: receipt summary and automatic/manual next-customer reset;
- customer mode: no GPU, hashes, timings, decision paths, detector boxes, or admin navigation.

- [ ] **Step 2: Run the focused tests and confirm old UI fails them**

Run:

```powershell
flutter test test\ui\scanner_screen_test.dart test\ui\customer_checkout_screen_test.dart
```

Expected: FAIL because `ScannerScreen` still presents evaluator terminology and controls.

- [ ] **Step 3: Implement one-question-per-screen composition**

`CustomerCheckoutScreen` listens to `CheckoutController` and switches exhaustively on `CheckoutPhase`. Keep camera preview only where it helps placement or object selection. Use the captured still and selected object crop for review, without technical overlays in customer mode. `CatalogPicker` follows `customerDiscovery`: frequent completed purchases, category groups, name search, and the stable complete list. It shows approved catalog photography when present and an explicit neutral fallback when absent; it never calls inference or displays generated product imagery.

- [ ] **Step 4: Wire production dependencies**

Move root construction from `main.dart` into `BakeryApp.bootstrap()`:

1. open database;
2. seed catalog if empty;
3. create audit file store;
4. create camera and worker;
5. create scanner and checkout controllers;
6. recover interrupted sessions;
7. render customer mode.

If database/artifact initialization fails, show a customer-safe unavailable screen and record the technical error when storage is available.

- [ ] **Step 5: Run widget tests**

Run:

```powershell
dart format lib\main.dart lib\src\app lib\src\ui\customer test\ui
flutter test test\ui\scanner_screen_test.dart test\ui\customer_checkout_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/main.dart apps/bakery_camera_flutter/lib/src/app apps/bakery_camera_flutter/lib/src/ui/customer apps/bakery_camera_flutter/test/ui
git commit -m "feat: deliver customer self-checkout screens"
```

---

## Task 9: Generate and gate the two approved customer illustrations

**Files:**

- Create: `apps/bakery_camera_flutter/assets/illustrations/manual_cart_entry.png`
- Create: `apps/bakery_camera_flutter/assets/illustrations/payment_complete.png`
- Create: `apps/bakery_camera_flutter/assets/asset_manifest.json`
- Create: `apps/bakery_camera_flutter/tool/verify_ui_assets.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/payment_view.dart`
- Test: `apps/bakery_camera_flutter/test/assets/ui_asset_manifest_test.dart`

- [ ] **Step 1: Write the failing asset gate**

The test must assert exactly two `generated_ui_illustration` entries, approved usage locations, transparent PNG, declared pixel dimensions, byte size, SHA-256, prompt, generation date, and the prohibitions:

```dart
expect(entry['allowed_use'], isIn(['manual_cart_entry', 'payment_complete']));
expect(entry['prohibited_uses'], containsAll([
  'product_photo',
  'camera_evidence',
  'model_input',
  'training_data',
  'evaluation_data',
]));
```

- [ ] **Step 2: Run and confirm missing assets fail**

Run:

```powershell
flutter test test\assets\ui_asset_manifest_test.dart
```

Expected: FAIL because the two files and manifest are absent.

- [ ] **Step 3: Use the `imagegen` skill to generate one asset at a time**

Generate `manual_cart_entry.png` with:

> Transparent-background, warm editorial receipt-stamp illustration for a Korean self-checkout bakery kiosk. A customer hand gently places one bread item into a simple paper tray, paired with a small catalog/list cue. Flat shapes, restrained BIXOLON orange accent, charcoal ink, cream paper tone, subtle imperfect print texture, no text, no logo, no product-identifying photorealism, no UI chrome, friendly and functional, centered composition, legible at 240 px.

Generate `payment_complete.png` with:

> Transparent-background, warm editorial receipt-stamp illustration for a Korean self-checkout bakery kiosk. A simple paper receipt with a clear check mark and a small bread silhouette, conveying completed simulated payment and readiness for the next customer. Flat shapes, restrained BIXOLON orange accent, confirmed teal used only for the check, charcoal ink, cream paper tone, subtle imperfect print texture, no text, no logo, no currency symbol, no UI chrome, friendly and calm, centered composition, legible at 240 px.

Do not pass camera captures or product photos as references. Do not generate additional decorative assets.

- [ ] **Step 4: Inspect, crop only transparent padding if necessary, and manifest exact outputs**

Use `view_image` for visual QA. Record the exact prompts, model/tool provenance returned by ImageGen, timestamp, dimensions, byte size, and SHA-256. `verify_ui_assets.dart` recalculates size/hash and fails on unlisted files.

- [ ] **Step 5: Integrate with graceful fallback**

Illustrations support, but never carry, meaning. If asset decoding fails, the same title, body, and CTA remain visible. Add semantic labels; exclude purely decorative texture layers from semantics.

- [ ] **Step 6: Run tests**

Run:

```powershell
dart run tool\verify_ui_assets.dart
flutter test test\assets\ui_asset_manifest_test.dart test\ui\customer_checkout_screen_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/assets/illustrations apps/bakery_camera_flutter/assets/asset_manifest.json apps/bakery_camera_flutter/tool/verify_ui_assets.dart apps/bakery_camera_flutter/lib/src/ui/customer apps/bakery_camera_flutter/test/assets
git commit -m "feat: add audited checkout illustrations"
```

---

## Task 10: Make simulated payment, reset, and crash recovery durable

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/checkout/simulated_payment_service.dart`
- Create: `apps/bakery_camera_flutter/lib/src/checkout/checkout_recovery.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/checkout/checkout_controller.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/app/bakery_app.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/simulated_payment_test.dart`
- Test: `apps/bakery_camera_flutter/test/checkout/checkout_recovery_test.dart`

- [ ] **Step 1: Write failing durability tests**

Test:

- two rapid pay taps create one order/payment;
- database commit failure does not show completion or clear cart;
- app restart after committed payment opens a fresh ready session;
- every nonterminal session from a previous process becomes `interrupted` and is never resumed or counted as paid;
- orphaned retained evidence is flagged for admin review;
- next-customer reset occurs only after `PaymentReceipt` returns.

- [ ] **Step 2: Run and verify failures**

Run:

```powershell
flutter test test\checkout\simulated_payment_test.dart test\checkout\checkout_recovery_test.dart
```

Expected: FAIL because recovery/payment services do not exist.

- [ ] **Step 3: Implement deterministic simulated payment**

Use injected `Clock` and `IdGenerator`. The service introduces no random failure and no artificial delay. Payment method is stored as `simulated`; status is `approved`. The receipt contains payment ID, order ID, session ID, amount, currency, and committed UTC time.

- [ ] **Step 4: Implement startup recovery rules**

Apply the spec exactly:

- completed/abandoned/failed session: never reopen, start ready;
- every nonterminal review, order-review, scan, or paying session: atomically mark `interrupted` at startup and retain all already-persisted evidence;
- interrupted sessions remain admin-reviewable but are never resumed, automatically paid, or included in sales;
- corrupt/missing evidence: terminal audit flag, do not silently delete;
- payment exists but session flag is stale: repair in one audited transaction and start ready.

- [ ] **Step 5: Run tests**

Run:

```powershell
dart format lib\src\checkout lib\src\app test\checkout
flutter test test\checkout\simulated_payment_test.dart test\checkout\checkout_recovery_test.dart
flutter analyze
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/checkout apps/bakery_camera_flutter/lib/src/app apps/bakery_camera_flutter/test/checkout
git commit -m "feat: make simulated checkout transaction durable"
```

---

## Task 11: Validate customer flow, accessibility, audit integrity, and Windows packaging

**Files:**

- Create: `apps/bakery_camera_flutter/test/integration/customer_checkout_journey_test.dart`
- Create: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/customer_retake_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png`
- Create: `apps/bakery_camera_flutter/test/ui/goldens/customer_complete_1280x820.png`
- Modify: `apps/bakery_camera_flutter/README.md`
- Modify: `apps/bakery_camera_flutter/windows/runner/Runner.rc`

- [ ] **Step 1: Write the end-to-end fixture journey**

The test must execute:

1. initialize camera/worker/database;
2. scan one registered and one Unknown object;
3. accept the registered product;
4. choose the Unknown from Top 3;
5. add one full-catalog product manually;
6. change quantity;
7. pay once;
8. assert final order/customer totals;
9. assert immutable AI totals still exclude Unknown;
10. assert image/provenance hashes and resolution source history;
11. reset to ready.

- [ ] **Step 2: Add semantics and golden coverage**

Run with 1024×720 and 1280×820, 100% and 200% text scale, keyboard-only focus traversal, high-contrast focus outlines, and Korean screen-reader labels. Ensure all tappable controls meet target size and no screen relies on score interpretation.

- [ ] **Step 3: Run the full Flutter suite**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
dart run build_runner build --delete-conflicting-outputs
dart run tool\verify_ui_assets.dart
flutter test
flutter analyze
```

Expected: all tests PASS; skipped suites are reported as unverified rather than passed.

- [ ] **Step 4: Run repository contract tests**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner
$env:PYTHONPATH='src'
python -m pytest tests\contract -q
```

Expected: PASS without touching unrelated pending contract-test changes.

- [ ] **Step 5: Build Windows release and inspect packaged assets**

Run:

```powershell
Set-Location C:\workspace\bixolon_bakery_scanner\apps\bakery_camera_flutter
flutter build windows --release
Get-ChildItem build\windows\x64\runner\Release\data\flutter_assets\assets -Recurse
```

Expected: build succeeds and includes font manifest/files, catalog seed/hash, exactly two generated illustrations, and asset manifest. This verifies packaging only; it is not an accuracy or latency claim.

- [ ] **Step 6: Update customer/operator documentation**

Document installation, ready-to-payment journey, simulated-payment limitation, customer resolution semantics, local audit directory, crash recovery, font/asset licensing, and the fact that technical review moves to the admin plan.

- [ ] **Step 7: Commit**

```powershell
git add apps/bakery_camera_flutter/test/integration apps/bakery_camera_flutter/test/ui apps/bakery_camera_flutter/README.md apps/bakery_camera_flutter/windows/runner/Runner.rc
git commit -m "test: verify v1.1.0 customer checkout foundation"
```

---

## Customer Plan Exit Criteria

- Customer can complete ready → scan → retake/review → order review → simulated payment → ready without staff.
- Unknown remains immutable in the inference receipt; customer resolution is separately attributed.
- Full product catalog is available for any uncertain or overridden object and for manual cart entry.
- Payment completion is visible only after one durable, idempotent database commit.
- Admin-readable audit data contains exact inference/candidate/provenance/timing/image facts and customer choice history.
- Customer screens contain no technical evaluator controls or model internals.
- Pretendard and the two approved illustrations are locally bundled, hashed, licensed, and packaged.
- Focused tests, full Flutter tests, analyzer, repository contracts, and Windows build all have recorded outcomes.
