# Customer Review Split Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the retained tray capture visible while customers resolve only exceptional bakery objects, with explicit catalog return paths and a compact order review.

**Architecture:** `CustomerReviewView` becomes a non-scrolling two-pane workspace at kiosk widths: the canonical retained capture remains in the left pane and the selected exception plus compact object progress stays in the right pane. `CustomerCheckoutScreen` keeps catalog selection in the same review shell and provides an explicit close action. Narrow or high-text-scale layouts remain reachable through a stacked fallback with local pane scrolling.

**Tech Stack:** Flutter Material 3, Dart widget tests, Flutter golden tests.

## Global Constraints

- Preserve the canonical retained image, canonical boxes, inference outcomes, SKU/count fields, and fail-closed `Unknown` behavior.
- Do not change detector, classifier, fusion, artifact, or checkout audit contracts.
- Customer UI must not expose model scores, policy names, hashes, or other inference evidence.
- Preserve 48 px minimum touch targets and support 1024×720 and 1280×820 kiosk sizes at 100% and 200% text scale.
- Keep version 1.1.0 and the existing `codex/v1-1-0-self-checkout` branch.

---

### Task 1: Fixed review workspace

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`

**Interfaces:**
- Consumes: `CheckoutState.objectDrafts`, canonical capture path/dimensions, `CapturedReviewOverlay`.
- Produces: `customer-review-scene-pane`, `customer-review-task-pane`, and `customer-review-progress` widget keys; overlay selection updates the task pane without global scrolling.

- [ ] **Step 1: Write the failing split-workspace tests**

```dart
expect(find.byKey(const Key('customer-review-scene-pane')), findsOneWidget);
expect(find.byKey(const Key('customer-review-task-pane')), findsOneWidget);
expect(
  tester.getTopLeft(find.byKey(const Key('customer-review-scene-pane'))).dx,
  lessThan(tester.getTopLeft(find.byKey(const Key('customer-review-task-pane'))).dx),
);
await tester.tap(find.byKey(const Key('customer-review-overlay-object-2')));
await tester.pumpAndSettle();
expect(find.byKey(const Key('customer-review-candidate-panel-object-2')), findsOneWidget);
expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
```

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart`

Expected: FAIL because the two fixed pane keys and non-scrolling selection behavior do not exist.

- [ ] **Step 3: Implement the two-pane review**

Replace cross-page `Scrollable.ensureVisible` navigation with local selected-object state. Build a `LayoutBuilder` that renders an `Expanded(flex: 3)` canonical capture pane and `Expanded(flex: 2)` task pane at kiosk width, with a stacked fallback below the kiosk breakpoint. Show one clear progress statement, compact status chips for every object, and only the selected unresolved candidate panel.

- [ ] **Step 4: Run the targeted tests and verify GREEN**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart`

Expected: PASS with no overflow or semantics exceptions.

### Task 2: In-context catalog and explicit return

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`

**Interfaces:**
- Consumes: existing `onOpenCatalog`, session-bound `CustomerCatalogDiscovery`, and catalog search callback.
- Produces: `onClose` for `CatalogPicker`, `customer-catalog-close`, Korean category labels, and a catalog panel that returns to the same selected object.

- [ ] **Step 1: Write the failing catalog return test**

```dart
await tester.tap(find.text('다른 상품 찾기'));
expect(find.byKey(const Key('customer-catalog-close')), findsOneWidget);
await tester.tap(find.byKey(const Key('customer-catalog-close')));
expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
expect(find.byKey(const Key('customer-review-candidate-panel-object-2')), findsOneWidget);
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `flutter test test/ui/customer_checkout_contract_test.dart`

Expected: FAIL because catalog selection replaces the complete page and has no close callback.

- [ ] **Step 3: Implement local catalog mode**

Add an optional `onClose` to `CatalogPicker`, render a 48 px close control, map known category IDs to Korean customer labels, and retain `_catalogObjectId` until the customer selects a product or closes the panel. On close, clear catalog mode without changing checkout state or selected object.

- [ ] **Step 4: Run the contract and accessibility tests and verify GREEN**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart`

Expected: PASS with Korean labels, explicit return, and minimum touch targets.

### Task 3: Camera aspect and compact order correction

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`

**Interfaces:**
- Consumes: camera controller aspect ratio and existing order callbacks.
- Produces: `live-tray-preview-aspect`, line-level product correction actions, and one count-mismatch secondary action.

- [ ] **Step 1: Write failing camera and order hierarchy tests**

```dart
expect(find.byKey(const Key('live-tray-preview-aspect')), findsOneWidget);
expect(find.textContaining('상품 변경'), findsNothing);
expect(find.byTooltip('인식 상품 변경'), findsWidgets);
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart`

Expected: FAIL because the preview is fixed to 180 px height and correction links are repeated below the order.

- [ ] **Step 3: Implement aspect-preserving preview and row-level correction**

Use an `AspectRatio` derived from `CameraController.value.aspectRatio` with a 16:9 fallback and `BoxFit.contain` behavior through `CanonicalCameraPreview`. Move recognized-object correction into a single 48 px edit control on each applicable order row, keep quantity and subtotal together, and retain one secondary “실제 빵 수가 달라요” action.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `flutter test test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart`

Expected: PASS without overflow at required kiosk sizes and text scales.

### Task 4: Visual evidence, full regression, and executable

**Files:**
- Update: `apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png`
- Update: `apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png`
- Update: `apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png`

**Interfaces:**
- Consumes: completed customer widgets and tracked golden fixtures.
- Produces: reviewed 1280×820 visual evidence and the version 1.1.0 Windows executable.

- [ ] **Step 1: Generate the three changed goldens**

Run: `flutter test test/ui/customer_checkout_accessibility_test.dart --update-goldens`

Expected: the ready preview is proportionate, review is a stable split workspace, and order controls are compact.

- [ ] **Step 2: Inspect the generated images**

Open each changed PNG and confirm the primary task is visible without scrolling, the retained capture is not cropped, and the footer does not cover content.

- [ ] **Step 3: Run customer and checkout regression suites**

Run: `flutter test test/ui test/checkout test/integration/customer_checkout_journey_test.dart`

Expected: PASS; unavailable external suites are reported as unverified.

- [ ] **Step 4: Build and launch**

Run: `flutter build windows --release`

Expected: release executable builds successfully and launches into the customer ready screen.

- [ ] **Step 5: Repeat live UX paths**

Exercise mixed recognition, all-exception recognition, box-to-object switching, catalog open/close, order correction, count mismatch, and retake. Do not initiate a real payment.
