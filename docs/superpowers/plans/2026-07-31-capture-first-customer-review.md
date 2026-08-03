# Capture-First Customer Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the isolated crop in customer review with a full retained capture, linked numbered detection overlays, and an in-context correction ledger.

**Architecture:** A small presentation model maps immutable `ObjectDraft` values to customer-safe display records: stable sequence, canonical rectangle, plain-language state, and product display. A dedicated overlay renders and hit-tests those records against the retained image. `CustomerReviewView` owns selected-object UI state and links it to flat rows, while existing checkout-controller selection, catalog, and count-mismatch paths remain the only mutations.

**Tech Stack:** Flutter/Dart 3.12, Material widgets, `flutter_test`, existing checkout and inference contracts.

## Global Constraints

- Preserve the canonical EXIF-transposed RGB capture coordinate frame; every rendered box derives directly from an in-bounds immutable `bboxXyxy`.
- Preserve fail-closed classification: `Unknown` remains `Unknown` until the existing customer top-3 or catalog resolution is recorded; do not expose confidence, model scores, detector names, hashes, or provenance to the customer.
- Do not alter inference, candidate ranking/order, retained image bytes/path/hash, audit receipts, or checkout-resolution provenance.
- Use only existing controller calls: `chooseTop3`, catalog selection, `continueToOrderReview`, and `reportCountMismatch` (then the existing retake flow).
- Retain Korean customer copy, 48 px minimum interactive targets, screen-reader labels, keyboard focus, 1024×720 and 1280×820 layouts, and 200% text-scale support.
- Keep the default customer review as a full scene; do not restore `CapturedReviewImage` or `SelectedObjectCropGeometry` to any customer flow.

---

## File Structure

- Create `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_presentation.dart`: immutable customer-safe review records.
- Create `apps/bakery_camera_flutter/lib/src/ui/customer/captured_review_overlay.dart`: retained still, canonical boxes, and object selection.
- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`: selected overlay, review ledger, and conditional candidate panel.
- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`: connects retake request to `reportCountMismatch`.
- Create `apps/bakery_camera_flutter/test/ui/customer_review_presentation_test.dart`: presentation-state unit tests.
- Create `apps/bakery_camera_flutter/test/ui/captured_review_overlay_test.dart`: canonical coordinates, semantics, and taps.
- Modify `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`: ledger, candidates, catalog, and retake route.
- Modify `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`: removes crop contracts and verifies overlay image provider.
- Modify `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart` and `test/ui/goldens/customer_review_1280x820.png`: accessibility, responsive, and visual evidence.

### Task 1: Customer-safe review presentation model

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_presentation.dart`
- Test: `apps/bakery_camera_flutter/test/ui/customer_review_presentation_test.dart`

**Interfaces:**
- Consumes: `List<ObjectDraft>`, immutable `InferenceObject.bboxXyxy`, and `ObjectDraft.product`.
- Produces: `CustomerReviewPresentation.fromDrafts(List<ObjectDraft>)`, `CustomerReviewObject`, `CustomerReviewObjectState`, and `CustomerReviewObject.rect` for Tasks 2–3.

- [ ] **Step 1: Write the failing tests**

```dart
test('keeps inference order, canonical boxes, and customer-safe labels', () {
  final presentation = CustomerReviewPresentation.fromDrafts([
    ObjectDraft.accepted(inferenceObject: registered, product: croissant),
    ObjectDraft.unresolved(unknown),
  ]);

  expect(presentation.objects.map((item) => item.displayNumber), [1, 2]);
  expect(presentation.objects[0].rect, const Rect.fromLTRB(10, 20, 500, 500));
  expect(presentation.objects[0].state, CustomerReviewObjectState.confirmed);
  expect(presentation.objects[0].label, 'Croissant');
  expect(presentation.objects[1].state, CustomerReviewObjectState.needsChoice);
  expect(presentation.objects[1].label, '상품을 확인해 주세요');
});

test('does not leak scores, decision paths, or model identifiers', () {
  final item = CustomerReviewPresentation.fromDrafts([ObjectDraft.unresolved(unknown)])
      .objects.single;
  expect(item.customerSemantics, isNot(contains('0.88')));
  expect(item.customerSemantics, isNot(contains('DINO')));
  expect(item.customerSemantics, contains('사진에서 01번'));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/ui/customer_review_presentation_test.dart`

Expected: FAIL because the presentation file and types do not exist.

- [ ] **Step 3: Write the minimal immutable projection**

```dart
enum CustomerReviewObjectState { confirmed, needsChoice, needsCatalog }

final class CustomerReviewObject {
  const CustomerReviewObject({
    required this.objectId,
    required this.displayNumber,
    required this.rect,
    required this.state,
    required this.label,
    required this.draft,
  });

  final String objectId;
  final int displayNumber;
  final Rect rect;
  final CustomerReviewObjectState state;
  final String label;
  final ObjectDraft draft;

  String get numberLabel => displayNumber.toString().padLeft(2, '0');
  String get customerSemantics => '사진에서 $numberLabel번, $label';
}

final class CustomerReviewPresentation {
  CustomerReviewPresentation._(this.objects);

  factory CustomerReviewPresentation.fromDrafts(List<ObjectDraft> drafts) =>
      CustomerReviewPresentation._(List.unmodifiable([
        for (var index = 0; index < drafts.length; index += 1)
          _item(drafts[index], index + 1),
      ]));

  final List<CustomerReviewObject> objects;
}
```

Implement `_item` with `Rect.fromLTRB` from `bboxXyxy`; use `draft.product!.displayName` for resolved objects, `needsChoice` for unresolved top-3 objects, and `needsCatalog` otherwise. Do not read confidence, candidate score, decision path, detector, or provenance.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/ui/customer_review_presentation_test.dart`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_presentation.dart apps/bakery_camera_flutter/test/ui/customer_review_presentation_test.dart
git commit -m "feat: add customer review presentation model"
```

### Task 2: Canonical retained-capture overlay

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/customer/captured_review_overlay.dart`
- Test: `apps/bakery_camera_flutter/test/ui/captured_review_overlay_test.dart`

**Interfaces:**
- Consumes: `CustomerReviewPresentation.objects`, original image width/height, retained display path, and selected object ID.
- Produces: `CapturedReviewOverlay` with `onSelectObject(String objectId)` and overlay keys `customer-review-overlay-<objectId>` for Task 3.

- [ ] **Step 1: Write the failing overlay tests**

```dart
testWidgets('maps canonical boxes into the full retained image and selects them', (tester) async {
  String? selected;
  await pumpOverlay(tester, onSelectObject: (id) => selected = id);

  final box = tester.getRect(find.byKey(const Key('customer-review-overlay-object-2')));
  final image = tester.getRect(find.byKey(const Key('captured-review-full-scene')));
  expect(box.left, closeTo(image.left + image.width * 600 / 1920, 1));
  expect(box.top, closeTo(image.top + image.height * 100 / 1080, 1));
  await tester.tap(find.byKey(const Key('customer-review-overlay-object-2')));
  expect(selected, 'object-2');
});

testWidgets('announces selected attention object without model detail', (tester) async {
  await pumpOverlay(tester, selectedObjectId: 'object-2');
  expect(find.bySemanticsLabel('사진에서 02번, 상품을 확인해 주세요, 선택됨'), findsOneWidget);
  expect(find.textContaining('0.88'), findsNothing);
  expect(find.textContaining('confidence'), findsNothing);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/ui/captured_review_overlay_test.dart`

Expected: FAIL because `CapturedReviewOverlay` does not exist.

- [ ] **Step 3: Write the full-scene overlay**

```dart
class CapturedReviewOverlay extends StatelessWidget {
  const CapturedReviewOverlay({
    required this.imagePath,
    required this.imageWidth,
    required this.imageHeight,
    required this.objects,
    required this.selectedObjectId,
    required this.onSelectObject,
    this.imageProviderFactory = customerReviewFileImageProvider,
    super.key,
  });

  final String imagePath;
  final int imageWidth;
  final int imageHeight;
  final List<CustomerReviewObject> objects;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;
}
```

Render `AspectRatio(aspectRatio: imageWidth / imageHeight)` with the file image in a `Stack` keyed `captured-review-full-scene`. In `LayoutBuilder`, create each `Positioned` box using canonical rectangle values divided by the image dimensions. Every box is a 48 px-or-larger `Semantics(button: true, selected: ...)` and `InkWell` whose tap calls `onSelectObject(item.objectId)`. Render number and customer-safe label; selected uses BIXOLON orange and a thicker outline, confirmed uses quiet graphite, and unresolved uses the existing uncertainty colour. Keep the image visible through a low-opacity tint. Reuse the current missing-image fallback, but never invoke crop/zoom geometry.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/ui/captured_review_overlay_test.dart`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- apps/bakery_camera_flutter/lib/src/ui/customer/captured_review_overlay.dart apps/bakery_camera_flutter/test/ui/captured_review_overlay_test.dart
git commit -m "feat: show customer review detection overlay"
```

### Task 3: Linked review ledger and correction path

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`

**Interfaces:**
- Consumes: Task 1 presentation, Task 2 overlay, existing `onChooseTop3`, `onOpenCatalog`, `onContinue`, and `CheckoutController.reportCountMismatch`.
- Produces: stateful `CustomerReviewView` with optional `onRetakeCapture` and row keys `customer-review-row-<objectId>`.

- [ ] **Step 1: Write the failing linked-review tests**

```dart
testWidgets('links numbered ledger row to the selected image box', (tester) async {
  await pumpReview(tester, drafts: [acceptedDraft, unresolvedDraft]);
  await tester.tap(find.byKey(const Key('customer-review-row-object-2')));
  expect(find.bySemanticsLabel('사진에서 02번, 상품을 확인해 주세요, 선택됨'), findsOneWidget);
  expect(find.byKey(const Key('customer-review-candidate-panel-object-2')), findsOneWidget);
  expect(find.byKey(const Key('customer-review-candidate-panel-object-1')), findsNothing);
});

testWidgets('preserves candidate order and routes catalog and retake', (tester) async {
  final calls = <String>[];
  await pumpReview(tester, onChoose: (_, sku) => calls.add('candidate:$sku'),
      onCatalog: (id) => calls.add('catalog:$id'), onRetake: () => calls.add('retake'));
  await tester.tap(find.text('Top 2'));
  await tester.tap(find.text('전체 상품에서 찾기'));
  await tester.tap(find.text('다시 촬영'));
  expect(calls, ['candidate:11', 'catalog:object-2', 'retake']);
});
```

Replace the old crop-zoom assertion with an image-provider test on `CapturedReviewOverlay`, and assert neither `selected-object-crop` nor `selected-object-zoom` exists.

- [ ] **Step 2: Run tests to verify failure**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_screen_test.dart`

Expected: FAIL because the ledger, selection state, and retake callback do not exist.

- [ ] **Step 3: Replace crop UI with the linked ledger**

Convert `CustomerReviewView` to `StatefulWidget`. Initialise `_selectedObjectId` to the active unresolved draft ID, otherwise the first draft ID; reconcile it in `didUpdateWidget` when the selected draft resolves. Build its presentation from all `state.objectDrafts`, not only `activeObject`.

```dart
CustomerReviewView(
  state: state,
  productForCandidate: widget.controller.productForCandidate,
  onChooseTop3: widget.controller.chooseTop3,
  onOpenCatalog: _showCatalogForObject,
  onRetakeCapture: () => widget.controller.reportCountMismatch(),
  onContinue: widget.controller.continueToOrderReview,
)
```

When retained path and dimensions exist, render `CapturedReviewOverlay` above the ledger. Render a flat row for every object: number, label, product price only if resolved, and explicit `사진에서 02번` reference. Tapping a row or box updates the same selection. Render existing candidate products in supplied order and the catalog action only within the selected unresolved row. Place `다시 촬영` with that correction route when `onRetakeCapture` is supplied. Keep `BakeryPrimaryButton` disabled until every draft resolves and add an unresolved-count summary above it.

Delete `CapturedReviewImage` and `SelectedObjectCropGeometry` after moving the image-provider typedef/function to the overlay file. Do not change `CheckoutState`, `ObjectDraft`, `InferenceObject`, controller resolution, or audit logic.

- [ ] **Step 4: Run tests to verify pass**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_screen_test.dart`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart
git commit -m "feat: link customer review capture and ledger"
```

### Task 4: Accessibility, responsive visual verification, and evidence

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png`

**Interfaces:**
- Consumes: complete review UI from Tasks 1–3.
- Produces: evidence that full-scene review and correction controls remain usable without changing checkout or audit contracts.

- [ ] **Step 1: Add failing accessibility and layout assertions**

```dart
testWidgets('review overlay and ledger stay reachable at kiosk sizes and 200 percent text', (tester) async {
  await pumpReviewAt(tester, const Size(1024, 720), scale: 2, highContrast: true);
  expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
  expect(find.byKey(const Key('customer-review-row-object-2')), findsOneWidget);
  expect(tester.takeException(), isNull);
  _expectMinimumTouchTarget(tester, find.byKey(const Key('customer-review-overlay-object-2')));
});

testWidgets('review exposes photo number and state to assistive technology', (tester) async {
  final semantics = tester.ensureSemantics();
  await pumpReview(tester);
  expect(find.bySemanticsLabel(contains('사진에서 02번')), findsOneWidget);
  expect(find.textContaining('confidence'), findsNothing);
  semantics.dispose();
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `flutter test test/ui/customer_checkout_accessibility_test.dart`

Expected: FAIL before Task 3 is complete, then PASS once its assertions are implemented.

- [ ] **Step 3: Update the review fixture and golden deliberately**

Give `_reviewState` a deterministic local image provider through the overlay test seam, or use a checked-in tiny non-production test fixture, so the golden includes a full scene and two labelled boxes. Do not add a real scan or derived customer data to Git. Regenerate only this golden:

```powershell
flutter test --update-goldens test/ui/customer_checkout_accessibility_test.dart
```

Inspect `customer_review_1280x820.png`: it must show full image, all numbered boxes, one obvious selected box, the matching ledger row, and candidates only for the unresolved row.

- [ ] **Step 4: Run complete relevant verification**

```powershell
flutter test test/ui/customer_review_presentation_test.dart test/ui/captured_review_overlay_test.dart test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_screen_test.dart test/ui/customer_checkout_accessibility_test.dart
flutter analyze
flutter test
```

Expected: all listed tests and analysis PASS. Record unavailable Windows camera, artifact, or hardware suites as unverified.

- [ ] **Step 5: Commit**

```powershell
git add -- apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png
git commit -m "test: verify capture-first customer review"
```

## Plan self-review

**Spec coverage:** Task 1 creates stable numbered customer-safe data; Task 2 preserves canonical full-scene geometry and selectable boxes; Task 3 links image/list selection and preserves candidate, catalog, and retake pathways; Task 4 verifies text scale, focus, semantics, visual regression, and broad Flutter checks. Immutable audit, candidate, and `Unknown` rules are protected globally and not touched by any task.

**Placeholder scan:** no TBDs, TODOs, deferred implementation, or undefined cross-task API remains.

**Type consistency:** `CustomerReviewPresentation`, `CustomerReviewObject`, `CapturedReviewOverlay`, `onSelectObject`, and `onRetakeCapture` are defined before use. Existing controller calls retain their exact names and signatures.
