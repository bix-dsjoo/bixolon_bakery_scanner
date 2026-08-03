# BIXOLON Bakery Kiosk Visual Redesign Implementation Plan

> **Execution note:** Implement this plan in the current checkout because the
> user explicitly asked to continue the existing 1.1.0 work. Preserve all
> unrelated and already-in-progress changes. Do not create a new version or
> alter the canonical inference, catalog revision, audit, or payment contracts.

**Goal:** Turn the existing 1.1.0 customer checkout into a compact, mature
operational kiosk UI while preserving the current phases, actions, automatic
classification behavior, fail-closed outcomes, and correction workflows.

**Architecture:** Keep `CheckoutController` and `CheckoutState` as the only
workflow authority. Recompose the customer shell into three structural regions:
a full-width compact header, a centered content viewport, and an optional
full-width action rail. Ready, review, and order provide their own bounded
workspaces inside that shell. Both review and order reuse
`CapturedReviewOverlay`, so the retained canonical capture and its canonical
boxes remain the shared visual source of truth.

**Tech stack:** Flutter 3 / Dart, Material 3, Pretendard, `flutter_test`,
golden tests, Windows release packaging, Computer Use for live EXE review.

**Responsibility and acceptance test:** Customer-facing presentation owns only
layout, visual hierarchy, and selection affordances. The acceptance test is
that the existing checkout journey produces the same state and totals, while
ready/review/order fit at 1024x720 and 1280x820, actionless states have no empty
rail, and capture boxes select the matching review task or order line.

---

## Constraints that apply to every task

- Keep application version `1.1.0`.
- Preserve `catalog-v1.1.0-r2` and its immutable predecessor.
- Do not alter detector/classifier/fusion decisions or turn `Unknown` into a
  registered SKU.
- Do not change the phase sequence:
  `ready -> analyzing -> retakeRequired|customerReview|orderReview -> paying -> paymentComplete`.
- Preserve one primary customer action in its current bottom location.
- Preserve administrator-entry confirmation and payment durability behavior.
- Do not introduce gradients, glow, blur, glass effects, decorative color
  rails, nested cards, or elevated hover motion.
- Use the existing neutral token set and BIXOLON orange as the only routine
  accent. Blue remains a focus indication, not a decorative accent.
- Use `apply_patch` for source edits and keep the current dirty worktree intact.

## Task 1: Rebuild the shared customer shell

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`

### Step 1: Add failing shell contract tests

Add widget tests that assert the structural surfaces, rather than pixel colors:

```dart
testWidgets('customer shell uses full-width compact header and action rail', (
  tester,
) async {
  tester.view.physicalSize = const Size(1024, 720);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await _pump(
    tester,
    CheckoutScaffold(
      title: '셀프 계산',
      primaryAction: const SizedBox(key: Key('action'), height: 52),
      child: const SizedBox(),
    ),
  );

  expect(tester.getRect(find.byKey(const Key('customer-header'))).width, 1024);
  expect(tester.getSize(find.byKey(const Key('customer-header'))).height, 60);
  expect(
    tester.getRect(find.byKey(const Key('customer-action-rail'))).width,
    1024,
  );
});

testWidgets('customer shell omits its rail when there is no action', (
  tester,
) async {
  await _pump(
    tester,
    const CheckoutScaffold(title: '빵 확인', child: SizedBox()),
  );

  expect(find.byKey(const Key('customer-action-rail')), findsNothing);
});
```

Extend the kiosk-name test to assert that the header renders a single horizontal
identity row and does not create a second floating administrator control:

```dart
expect(find.byKey(const Key('customer-header-identity')), findsOneWidget);
expect(find.byKey(const Key('customer-header-action')), findsOneWidget);
```

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart --plain-name "customer shell"
```

Expected: FAIL because `primaryAction` is required, the header/action keys do
not exist, and the current shell constrains all three regions to `maxWidth`.

### Step 2: Make the action rail optional and surfaces full width

Change the public shell contract to:

```dart
const CheckoutScaffold({
  required this.title,
  required this.child,
  this.primaryAction,
  this.maxWidth = 1240,
  this.scrollable = true,
  super.key,
});

final Widget? primaryAction;
```

Build the shell in this order:

```dart
Column(
  children: [
    SizedBox(
      key: const Key('customer-header'),
      height: 60,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: tokens.paper,
          border: Border(bottom: BorderSide(color: tokens.divider)),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: const _CustomerHeader(),
          ),
        ),
      ),
    ),
    Expanded(
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: /* bounded scrollable or non-scrollable body */,
        ),
      ),
    ),
    if (primaryAction != null)
      SizedBox(
        key: const Key('customer-action-rail'),
        height: 76,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: tokens.paper,
            border: Border(top: BorderSide(color: tokens.divider)),
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: /* action aligned to the content grid */,
            ),
          ),
        ),
      ),
  ],
)
```

The header identity is one line: `BIXOLON Bakery`, a thin separator, and
`title`. Render the snapshotted kiosk name as muted secondary text only when it
fits; use `Expanded`, `maxLines: 1`, and `TextOverflow.ellipsis` so 200% text
does not increase the 60 px header.

### Step 3: Put administrator entry into the header grid

Add an inherited header-action scope beside `KioskDisplayNameScope`:

```dart
class KioskHeaderActionScope extends InheritedWidget {
  const KioskHeaderActionScope({
    required this.action,
    required super.child,
    super.key,
  });

  final Widget action;

  static Widget? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<KioskHeaderActionScope>()
      ?.action;

  @override
  bool updateShouldNotify(KioskHeaderActionScope oldWidget) =>
      action != oldWidget.action;
}
```

In `CustomerCheckoutScreen`, replace the top-right `Stack` overlay with
`KioskHeaderActionScope(action: CustomerAdminEntryControl(...), child: content)`.
Keep the current rule that the administrator action is absent while a catalog
correction surface is open.

### Step 4: Verify the shell at both kiosk sizes and 200% text

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "customer checkout states remain usable"
```

Expected: PASS, with all interactive controls at least 48 px and no overflow.

### Step 5: Commit the shell

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart
git commit -m "refactor: compact customer kiosk shell"
```

## Task 2: Make ready, analyzing, retake, paying, and completion spatially honest

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/analyzing_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/retake_required_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/payment_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_status_banner.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`

### Step 1: Add failing space and action-presence tests

Add these assertions:

```dart
testWidgets('ready keeps the complete camera scene above the action rail', (
  tester,
) async {
  tester.view.physicalSize = const Size(1024, 720);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await _pump(tester, ReadyView(onScan: () {}));

  final scene = tester.getRect(find.byKey(const Key('live-tray-placement-guide')));
  final rail = tester.getRect(find.byKey(const Key('customer-action-rail')));
  expect(scene.bottom, lessThanOrEqualTo(rail.top));
  expect(scene.width / scene.height, closeTo(16 / 9, 0.02));
});

testWidgets('analyzing and paying do not render an empty action rail', (
  tester,
) async {
  await _pump(tester, const AnalyzingView());
  expect(find.byKey(const Key('customer-action-rail')), findsNothing);
  await _pump(tester, PaymentView(state: _payingState));
  expect(find.byKey(const Key('customer-action-rail')), findsNothing);
});
```

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart --plain-name "action rail"
```

Expected: FAIL because analyzing and paying currently pass a 56 px empty widget.

### Step 2: Recompose ready as a bounded workspace

Set `scrollable: false`. Use a compact one-line instruction above an `Expanded`
camera region. Inside the expanded region, fit the canonical aspect ratio using
the smaller of the available width and height:

```dart
Column(
  crossAxisAlignment: CrossAxisAlignment.stretch,
  children: [
    const _PlacementInstruction(),
    const SizedBox(height: 12),
    Expanded(
      child: Center(
        child: AspectRatio(
          key: const Key('live-tray-placement-guide'),
          aspectRatio: previewAspectRatio,
          child: /* unchanged canonical preview and placement guide */,
        ),
      ),
    ),
    const SizedBox(height: 8),
    const Text('트레이가 화면 안에 모두 보이도록 맞춰주세요.'),
  ],
)
```

Keep the fallback aspect ratio at 16:9. Do not use `BoxFit.cover`; no part of
the camera view may be cropped.

### Step 3: Remove empty rails and reduce decorative status containers

- Omit `primaryAction` in `AnalyzingView` and `PaymentView`.
- Center the concise progress/status block in the available body rather than at
  the top of a large blank page.
- Keep the existing factual copy and no artificial payment spinner.
- Restyle `BakeryStatusBanner` as a flat status row for routine ready/loading
  states: small state icon or progress indicator, title, optional muted detail,
  no filled rounded card. Retain a subtle tinted background and border only for
  uncertain/error states where it communicates risk.
- Keep retake's `다시 촬영` primary action and `직접 담기` tertiary action.
- Keep completion's amount and next-customer action; remove excess illustration
  height and nested status treatment.

### Step 4: Re-run behavioral and accessibility tests

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "customer checkout states remain usable"
```

Expected: PASS. Existing copy, payment durability, retake gating, and next
customer race behavior remain unchanged.

### Step 5: Commit the state surfaces

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/analyzing_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/retake_required_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/payment_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/lib/src/ui/components/bakery_status_banner.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart
git commit -m "refactor: tighten customer checkout states"
```

## Task 3: Refine review into one scene and one task ledger

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/captured_review_overlay.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`

### Step 1: Strengthen the existing bidirectional-selection test

Keep the current overlay-to-row assertions and add structural expectations:

```dart
expect(find.byKey(const Key('customer-review-scene-pane')), findsOneWidget);
expect(find.byKey(const Key('customer-review-task-pane')), findsOneWidget);
final scene = tester.getRect(
  find.byKey(const Key('customer-review-scene-pane')),
);
final tasks = tester.getRect(
  find.byKey(const Key('customer-review-task-pane')),
);
expect(scene.left, lessThan(tasks.left));
expect(scene.width / tasks.width, closeTo(1.5, 0.18));
```

Add an all-resolved review assertion:

```dart
expect(find.text('확인할 빵 0개 남음'), findsNothing);
expect(find.text('주문 확인'), findsOneWidget);
```

Run:

```powershell
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "review selection remains bidirectional"
```

Expected: FAIL until stable pane keys and the 60/40 ratio are implemented.

### Step 2: Remove card-within-card presentation

Keep `CustomerReviewPresentation` unchanged. In `CustomerReviewView`:

- Keep the captured scene on the left and task on the right at widths >= 760.
- Use `Expanded(flex: 3)` and `Expanded(flex: 2)` with a 1 px vertical divider
  plus 20 px padding, rather than two independently rounded cards.
- Make the scene pane a neutral canvas with only the retained image surface.
- Replace the progress card with a compact ledger heading:
  `인식된 빵 N개 · 확인 필요 M개`.
- Keep up to five object selectors visible as compact list rows; use a local
  `ListView` when more items or 200% text require scrolling.
- Keep only the selected object's decision controls expanded.
- Show confirmed items as ordinary rows with a text state, not green cards.
- Use orange only for the selected box/action and amber only for unresolved
  state. Confirmed boxes remain neutral.

Add stable keys:

```dart
const Key('customer-review-scene-pane')
const Key('customer-review-task-pane')
```

### Step 3: Make the overlay visually precise without changing coordinates

In `CapturedReviewOverlay`, preserve the existing `BoxFit.fill` because the
container already has the exact canonical aspect ratio. Keep canonical box
math unchanged. Reduce unselected fill opacity and border weight:

```dart
color: color.withValues(alpha: selected ? 0.10 : 0.04),
border: Border.all(color: color, width: selected ? 3 : 1.5),
```

Keep the selected box painted last, minimum 48 px hit targets, numbered labels,
and semantic selected state.

### Step 4: Flatten the in-context catalog

Keep catalog search, categories, products, close/back behavior, and selection
callbacks. Remove redundant outer cards and decorative chips. Categories may
remain choice chips because they are filters, but use small radius, neutral
unselected treatment, and one selected accent. Product results become dense
48 px list rows with price aligned right.

### Step 5: Run review contracts

Run:

```powershell
flutter test test/ui/customer_checkout_contract_test.dart
flutter test test/ui/customer_checkout_screen_test.dart --plain-name "catalog search keeps"
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "review"
```

Expected: PASS. Retained path, image dimensions, box coordinates, SKU candidate
selection, and customer-safe evidence rules remain unchanged.

### Step 6: Commit the review workspace

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/captured_review_overlay.dart apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart
git commit -m "refactor: clarify capture review workspace"
```

## Task 4: Keep capture evidence visible through order review

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`

### Step 1: Add failing order continuity and selection tests

Ensure `_orderState` carries the same retained capture metadata as
`_reviewState`, then add:

```dart
testWidgets('order keeps capture and selects its matching row from a box', (
  tester,
) async {
  await tester.pumpWidget(
    _app(
      OrderReviewView(
        state: _orderState,
        onSetQuantity: (_, _) {},
        onAddProduct: _noop,
        onOverrideObject: (_) {},
        onCountMismatch: _noop,
        onPay: _noop,
        onRemoveProduct: (_) {},
        imageProviderFactory: (_) =>
            const AssetImage(_reviewFixtureAssetPath),
      ),
    ),
  );
  await _precacheReviewFixture(tester);
  await tester.pumpAndSettle();

  expect(find.byKey(const Key('order-review-scene-pane')), findsOneWidget);
  expect(find.byKey(const Key('order-review-task-pane')), findsOneWidget);
  await tester.tap(
    find.byKey(const Key('customer-review-overlay-object-1')),
  );
  await tester.pump();
  expect(
    tester.widget<ListTile>(
      find.byKey(const Key('order-review-line-product-1')),
    ).selected,
    isTrue,
  );
});
```

Add the reverse direction by tapping the row and asserting the corresponding
overlay semantic has `isSelected`.

Run:

```powershell
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "order keeps capture"
```

Expected: FAIL because `OrderReviewView` is stateless, has no image-provider
seam, and currently renders only the order list.

### Step 2: Convert order review to a stateful split workspace

Add the image-provider test seam:

```dart
this.imageProviderFactory = customerReviewFileImageProvider,

final CustomerReviewImageProviderFactory imageProviderFactory;
```

Convert `OrderReviewView` to `StatefulWidget` with `_selectedObjectId`. Initialize
to the first recognized object. Build presentation objects using:

```dart
final presentation = CustomerReviewPresentation.fromDrafts(
  widget.state.objectDrafts,
);
```

At widths >= 760, render a 60/40 row:

```dart
Row(
  children: [
    Expanded(
      flex: 3,
      child: _OrderScenePane(
        key: const Key('order-review-scene-pane'),
        /* retained capture, boxes, selection */,
      ),
    ),
    const VerticalDivider(width: 41, thickness: 1),
    Expanded(
      flex: 2,
      child: _OrderTaskPane(
        key: const Key('order-review-task-pane'),
        /* order lines, total, tertiary corrections */,
      ),
    ),
  ],
)
```

At narrower widths, stack capture above task without changing the phase.
The task pane owns local scrolling. The page itself remains non-scrollable.

### Step 3: Link boxes and order lines

For each line, derive canonical object IDs exactly as today:

```dart
final recognizedObjectIds = [
  for (final draft in widget.state.objectDrafts)
    if (draft.product?.productId == line.product.productId)
      draft.inferenceObject.objectId,
];
```

Selection rules:

- Box tap sets `_selectedObjectId` to that object.
- A line is selected when `recognizedObjectIds` contains the selected ID.
- Line tap keeps the currently selected ID when it already belongs to that
  line; otherwise it selects the first recognized ID.
- Manually added lines have no box and do not alter box selection.
- Edit still passes the exact object ID to `onOverrideObject`.
- Quantity, remove, add product, count mismatch, total, `canPay`, and payment
  callbacks remain unchanged.

Add stable row keys:

```dart
Key('order-review-line-${line.product.productId}')
```

### Step 4: Verify the all-auto path

Add a journey test that scans a fixture whose objects are all direct/fusion
accepted, reaches `CheckoutPhase.orderReview` without manual choices, and
asserts:

```dart
expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
expect(find.byKey(const Key('order-review-task-pane')), findsOneWidget);
expect(find.textContaining('확인할 빵'), findsNothing);
```

This test guards the user-reported regression: automatic decisions must remain
automatic; the redesign only makes their evidence visible.

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart
flutter test test/ui/customer_checkout_accessibility_test.dart --plain-name "order"
flutter test test/ui/customer_checkout_contract_test.dart
```

Expected: PASS with unchanged line totals and `canPay` behavior.

### Step 5: Commit order continuity

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart
git commit -m "feat: preserve capture context in order review"
```

## Task 5: Integrate the correction panel and finish the visual system

**Files:**

- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/app_theme_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`

### Step 1: Add visual-system guard tests

Assert the restrained component contract:

```dart
expect(theme.cardTheme.elevation, 0);
expect(
  (theme.cardTheme.shape! as RoundedRectangleBorder).borderRadius,
  BorderRadius.circular(8),
);
expect(tokens.controlRadius, lessThanOrEqualTo(6));
expect(tokens.surfaceRadius, lessThanOrEqualTo(8));
```

Extend the order correction test to assert the retained scene and order task
remain in the tree while the panel is open.

Run:

```powershell
flutter test test/ui/app_theme_test.dart test/ui/design_system_test.dart test/ui/customer_checkout_screen_test.dart --plain-name "order correction"
```

Expected: the context-preservation test fails until the order split is wired
through the catalog overlay.

### Step 2: Reduce the correction panel to a real utility layer

Keep the current right-side panel, modal dismissal, search, close action, and
originating order context. Change only its visual layer:

- width: `min(480, viewport width - 32)`;
- radius: 8;
- one 1 px border;
- elevation: 2 or an equivalent single subtle shadow;
- neutral white surface;
- no decorative scrim color beyond a low-opacity black barrier;
- local scrolling only.

The panel must not replace the order page or create an additional customer
phase.

### Step 3: Normalize typography, controls, and surfaces

- Keep Pretendard and tabular figures.
- Use 20 px as the largest customer page title; routine section titles use
  15–16 px semibold.
- Keep touch targets at 48 px even when visual controls are denser.
- Keep control radius 4 and structural surface radius 8.
- Keep shadows only on the correction panel and modal sheets.
- Use divider lines only between persistent structural regions and list rows.
- Do not add icons to text actions unless the icon communicates a conventional
  edit/delete/close operation.

### Step 4: Run component tests

Run:

```powershell
flutter test test/ui/app_theme_test.dart
flutter test test/ui/bixolon_brand_test.dart
flutter test test/ui/design_system_test.dart
flutter test test/ui/customer_checkout_screen_test.dart
```

Expected: PASS with keyboard focus still using the existing blue 2 px outline.

### Step 5: Commit the integrated visual system

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart apps/bakery_camera_flutter/lib/src/ui/app_theme.dart apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart apps/bakery_camera_flutter/test/ui/app_theme_test.dart apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart apps/bakery_camera_flutter/test/ui/design_system_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart
git commit -m "style: normalize kiosk visual hierarchy"
```

## Task 6: Update goldens and complete automated verification

**Files:**

- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_retake_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_complete_1280x820.png`
- Modify if newly covered:
  `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`

### Step 1: Generate the five customer goldens

Run:

```powershell
flutter test test/ui/customer_checkout_accessibility_test.dart --update-goldens
```

Expected: PASS and only the intended customer goldens change. Admin goldens must
remain untouched.

### Step 2: Inspect every generated image

Open each image and verify:

- 60 px full-width single-row header;
- no central white slab or interrupted bottom background;
- ready camera fully visible with correct aspect ratio;
- review capture left and task right with one divider;
- order capture left and order task right;
- no nested rounded cards, colored side bars, gradients, glow, or heavy shadow;
- only the primary action dominates;
- Korean text is not clipped.

If any image fails a criterion, change source and repeat Task 6 Steps 1–2.

### Step 3: Run focused and full Flutter verification

Run:

```powershell
dart format --output=none --set-exit-if-changed lib test
dart analyze
flutter test test/ui/customer_checkout_screen_test.dart
flutter test test/ui/customer_checkout_contract_test.dart
flutter test test/ui/customer_checkout_accessibility_test.dart
flutter test
```

Expected:

- formatting exits 0;
- analyzer reports no issues;
- all focused tests pass;
- the full suite passes with no skipped suite described as passed.

### Step 4: Verify catalog and checkout regression boundaries

Run:

```powershell
flutter test test/catalog/catalog_seed_test.dart
flutter test test/catalog/catalog_repository_test.dart
flutter test test/admin/product_management_service_test.dart
flutter test test/checkout
```

Expected: PASS. Catalog revision `catalog-v1.1.0-r2`, prior revision
`catalog-v1.1.0`, registered/Unknown totals, line totals, and durable payment
contracts remain unchanged.

### Step 5: Commit reviewed goldens and tests

```powershell
git add apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_retake_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_complete_1280x820.png apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart
git commit -m "test: approve redesigned customer kiosk"
```

## Task 7: Build, package, and perform live EXE UX testing

**Files:**

- Build output:
  `apps/bakery_camera_flutter/build/windows/x64/runner/Release/`
- Package output:
  `artifacts/installer_payload/1.1.0-ux-redesign/`
- Modify only if a verified defect is found: the customer UI files and matching
  tests listed in Tasks 1–6.

### Step 1: Build the Windows release

Run from `apps/bakery_camera_flutter`:

```powershell
flutter build windows --release
```

Expected: exit 0 and a runnable `bakery_camera_prototype.exe` with its required
DLL/data files.

### Step 2: Package the exact release bundle

Use the repository's existing packaging command discovered via:

```powershell
rg -n "installer_payload|package.*windows|verify.*package" README.md docs tools scripts apps
```

Package to:

```text
C:\workspace\bixolon_bakery_scanner\artifacts\installer_payload\1.1.0-ux-redesign
```

Run the matching package verification command and record its file count and
success output. Do not copy only the EXE; preserve the complete Windows bundle.

### Step 3: Test the packaged EXE as a customer with Computer Use

Launch the packaged EXE and test these paths repeatedly:

1. 1024x720 ready: full camera view, no crop, one clear scan action.
2. 1280x820 ready: compact header and continuous full-width action rail.
3. analyzing: concise status, no empty footer.
4. all-auto scan: direct transition to order review, retained capture and boxes
   visible, no forced manual selection.
5. mixed-confidence scan: capture left, one unresolved task right, confirmed
   items visually quiet.
6. box -> review task and review task -> box selection.
7. box -> order line and order line -> box selection.
8. order correction: order and capture remain behind the right panel; close
   returns to the same selected line.
9. count mismatch -> retake -> scan again.
10. administrator entry -> cancel and continue customer checkout.
11. 200% text at 1024x720: capture remains visible and only the local task pane
    scrolls.

Do not confirm a real payment during UX testing. Stop at the enabled payment
button unless the environment uses the explicitly simulated payment service.

### Step 4: Fix verified live defects with a new failing test

For each observed defect:

1. capture the exact screen and state;
2. add a focused failing widget/golden test;
3. make the smallest presentation-only fix;
4. rerun the focused test and full customer UI suite;
5. rebuild and repeat the affected live path.

Do not adjust inference thresholds, catalog mappings, or automatic decision
rules to solve a visual problem.

### Step 5: Final verification and handoff

Run:

```powershell
dart analyze
flutter test
git diff --check
git status --short
```

Report:

- exact packaged EXE path;
- analyzer and test totals;
- package verification result;
- live paths exercised;
- any suite that was unavailable, labeled unverified;
- remaining unrelated dirty files, without deleting or staging them.

If Computer Use produces additional fixes, inspect `git diff --name-only` and
stage each verified customer UI source and its focused test by explicit path,
then commit them with:

```powershell
git commit -m "fix: resolve live kiosk usability defects"
```

Do not create this final commit when Computer Use finds no additional defect,
and do not stage catalog assets or generated Windows plugin files as part of a
presentation-only fix.
