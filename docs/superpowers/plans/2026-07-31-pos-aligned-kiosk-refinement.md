# POS-Aligned Kiosk Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the production BIXOLON POS visual system to the customer kiosk while simplifying Ready, subordinating rare order exceptions, and preserving every checkout and inference behavior.

**Architecture:** Keep the existing `CheckoutScaffold`, customer phase views, checkout controller, and fail-closed pipeline. Extend the existing theme contract with the POS-derived semantic colors and radii, then consume those shared tokens from the header, Ready, order rows, quantity stepper, and catalog modal. No controller, state transition, inference, audit, catalog, or payment interface changes.

**Tech Stack:** Flutter 3.44.7, Dart, Material 3, Pretendard bundled fonts, `flutter_test`, golden tests, Windows release packaging

## Global Constraints

- Keep application version `1.1.0`.
- Preserve every customer action, state transition, model decision, catalog revision, persisted audit record, and payment semantic.
- Preserve the canonical image coordinate frame and all detection-box geometry.
- Preserve fail-closed `Unknown`; never replace it with an arbitrary registered SKU.
- Keep the left captured-evidence/right task workspace and bidirectional box-to-row selection.
- Use the POS-derived color, typography, spacing, border, and radius tokens from `docs/superpowers/specs/2026-07-31-kiosk-hierarchy-refinement-design.md`.
- Use one orange filled primary action per customer screen.
- Keep touch targets at least 48 px and keyboard focus visible.
- Do not add gradients, glow, glass, structural cards, decorative badges, or unnecessary shadows.
- Do not modify `portable_cpu_smoke/` or legacy inference behavior.
- Treat unavailable hardware, artifact, GPU, and payment suites as unverified, never passed.

---

## File Structure

**Theme contract**

- Modify `apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart`
  to own POS-derived semantic colors and radii.
- Modify `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart` to map the
  approved Pretendard type ramp and shared button/list styles.
- Modify `apps/bakery_camera_flutter/test/ui/app_theme_test.dart` and
  `apps/bakery_camera_flutter/test/ui/design_system_test.dart` to lock the
  token contract.

**Shared customer shell**

- Modify `apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart`
  to implement the 60 px header plus divider and simpler left/right groups.
- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
  to expose administrator entry only during Ready and to use the modal radius.
- Modify `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
  to lock header geometry and administrator visibility.

**Ready**

- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart` to
  remove the status banner and pre-recognition camera overlay.
- Modify `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
  and `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
  to lock one-line guidance and the uncropped camera.

**Order**

- Create `apps/bakery_camera_flutter/lib/src/ui/components/bakery_secondary_button.dart`
  for neutral, subordinate customer actions.
- Modify `apps/bakery_camera_flutter/lib/src/ui/components/quantity_stepper.dart`
  to use the shared POS border and focus tokens.
- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
  to tighten the split workspace, align rows, use pale-orange selection, and
  replace exception text links with secondary buttons.
- Modify `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
  to use the same selected-row semantic surface.
- Modify `apps/bakery_camera_flutter/test/ui/design_system_test.dart`,
  `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`,
  `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`,
  and `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`
  to lock the component contract.

**Visual evidence**

- Update customer and design-system PNGs under
  `apps/bakery_camera_flutter/test/ui/goldens/`.
- Do not add files under `apps/bakery_camera_flutter/test/ui/failures/`.

---

### Task 1: Lock the POS-derived theme contract

**Files:**

- Modify: `apps/bakery_camera_flutter/test/ui/app_theme_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`

**Interfaces:**

- Consumes: existing `BixolonThemeExtension.of(BuildContext)` and
  `buildBakeryTheme()`.
- Produces: `selectedSurface`, `controlBorder`, `disabledAction`,
  `modalRadius`, and the approved `TextTheme` roles used by later tasks.

- [ ] **Step 1: Write failing theme tests**

Replace the typography expectations in
`test/ui/app_theme_test.dart` with:

```dart
test('customer typography follows the production POS hierarchy', () {
  final textTheme = buildBakeryTheme().textTheme;

  expect(textTheme.headlineSmall?.fontSize, 24);
  expect(textTheme.headlineSmall?.fontWeight, FontWeight.w500);
  expect(textTheme.titleLarge?.fontSize, 18);
  expect(textTheme.titleLarge?.fontWeight, FontWeight.w600);
  expect(textTheme.titleMedium?.fontSize, 15);
  expect(textTheme.titleMedium?.fontWeight, FontWeight.w600);
  expect(textTheme.bodyLarge?.fontSize, 14);
  expect(textTheme.bodyLarge?.fontWeight, FontWeight.w500);
  expect(textTheme.bodyMedium?.fontSize, 13);
  expect(textTheme.bodyMedium?.fontWeight, FontWeight.w400);
  expect(textTheme.labelLarge?.fontSize, 16);
  expect(textTheme.labelLarge?.fontWeight, FontWeight.w600);
  expect(textTheme.labelMedium?.fontSize, 12);
  expect(textTheme.labelMedium?.fontWeight, FontWeight.w500);
});
```

Extend the token test in `test/ui/design_system_test.dart` with:

```dart
expect(tokens.canvas, const Color(0xFFFFFFFF));
expect(tokens.ink, const Color(0xFF000000));
expect(tokens.mutedInk, const Color(0xFF5C5C5C));
expect(tokens.divider, const Color(0xFFE8E8E8));
expect(tokens.action, const Color(0xFFEE7203));
expect(tokens.selectedSurface, const Color(0xFFFCEAD9));
expect(tokens.controlBorder, const Color(0xFFD8D8D8));
expect(tokens.disabledAction, const Color(0xFFFAD5B3));
expect(tokens.focus, const Color(0xFF184C9F));
expect(tokens.confirmed, const Color(0xFF268B20));
expect(tokens.controlRadius, 5);
expect(tokens.surfaceRadius, 5);
expect(tokens.modalRadius, 10);
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
cd apps\bakery_camera_flutter
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\app_theme_test.dart test\ui\design_system_test.dart
```

Expected: compilation fails because the new token properties do not exist,
and the old typography/radius values do not match.

- [ ] **Step 3: Extend `BixolonThemeExtension`**

Add these constructor parameters, fields, copy parameters, copy assignments,
and lerp entries:

```dart
required this.selectedSurface,
required this.controlBorder,
required this.disabledAction,
required this.modalRadius,
```

```dart
final Color selectedSurface;
final Color controlBorder;
final Color disabledAction;
final double modalRadius;
```

Use this concrete `bixolon` value:

```dart
static const bixolon = BixolonThemeExtension(
  canvas: Color(0xFFFFFFFF),
  paper: Color(0xFFFFFFFF),
  ink: Color(0xFF000000),
  mutedInk: Color(0xFF5C5C5C),
  divider: Color(0xFFE8E8E8),
  action: Color(0xFFEE7203),
  selectedSurface: Color(0xFFFCEAD9),
  controlBorder: Color(0xFFD8D8D8),
  disabledAction: Color(0xFFFAD5B3),
  focus: Color(0xFF184C9F),
  confirmed: Color(0xFF268B20),
  uncertainty: Color(0xFFC76B00),
  error: Color(0xFFCC2427),
  controlRadius: 5,
  surfaceRadius: 5,
  modalRadius: 10,
);
```

In `lerp`, use `Color.lerp` for the three new colors and linear interpolation
for `modalRadius`.

- [ ] **Step 4: Map the approved type ramp in `app_theme.dart`**

Replace the current `TextTheme` with:

```dart
const textTheme = TextTheme(
  headlineSmall: TextStyle(
    fontSize: 24,
    height: 1.35,
    fontWeight: FontWeight.w500,
  ),
  titleLarge: TextStyle(
    fontSize: 18,
    height: 1.35,
    fontWeight: FontWeight.w600,
    fontFeatures: tabularFigures,
  ),
  titleMedium: TextStyle(
    fontSize: 15,
    height: 1.35,
    fontWeight: FontWeight.w600,
  ),
  bodyLarge: TextStyle(
    fontSize: 14,
    height: 1.4,
    fontWeight: FontWeight.w500,
  ),
  bodyMedium: TextStyle(
    fontSize: 13,
    height: 1.35,
    fontWeight: FontWeight.w400,
  ),
  labelLarge: TextStyle(
    fontSize: 16,
    height: 1.35,
    fontWeight: FontWeight.w600,
  ),
  labelMedium: TextStyle(
    fontSize: 12,
    height: 1.4,
    fontWeight: FontWeight.w500,
  ),
);
```

Change the shared outlined-button border to `tokens.controlBorder` and retain
the existing focused border behavior.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\dart.bat format lib\src\ui\bixolon_theme_extension.dart lib\src\ui\app_theme.dart test\ui\app_theme_test.dart test\ui\design_system_test.dart
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\app_theme_test.dart test\ui\design_system_test.dart
```

Expected: all focused theme and design-system tests pass.

- [ ] **Step 6: Commit the token contract**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart apps/bakery_camera_flutter/lib/src/ui/app_theme.dart apps/bakery_camera_flutter/test/ui/app_theme_test.dart apps/bakery_camera_flutter/test/ui/design_system_test.dart
git commit -m "style: align kiosk theme with production POS"
```

---

### Task 2: Simplify the shared header and restrict administrator entry

**Files:**

- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`

**Interfaces:**

- Consumes: `CheckoutScaffold(title, child, primaryAction, maxWidth,
  scrollable)` and `KioskHeaderActionScope`.
- Produces: a 61 px header, left brand/stage group, far-right action slot, and
  Ready-only administrator visibility.

- [ ] **Step 1: Write failing shell and phase tests**

Change the header-height assertion to:

```dart
expect(tester.getSize(find.byKey(const Key('customer-header'))).height, 61);
```

Replace the kiosk-display-name test with:

```dart
testWidgets('customer header omits redundant kiosk display name', (
  tester,
) async {
  await _pump(
    tester,
    KioskDisplayNameScope(
      displayName: 'BIXOLON Seongsu',
      child: const CheckoutScaffold(
        title: '셀프 계산',
        child: SizedBox(),
      ),
    ),
  );

  expect(find.byKey(const Key('kiosk-display-name')), findsNothing);
  expect(find.text('BIXOLON Seongsu'), findsNothing);
});
```

Extend the existing administrator test after its Ready assertions:

```dart
expect(adminAction.right, closeTo(header.right - 24, 1));

await tester.runAsync(fixture.controller.scan);
await tester.pumpAndSettle();

expect(
  fixture.controller.state.phase,
  isNot(CheckoutPhase.ready),
);
expect(find.byKey(const Key('customer-header-action')), findsNothing);
expect(find.text('관리자'), findsNothing);
```

- [ ] **Step 2: Run the targeted shell tests and verify RED**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart --plain-name "customer shell keeps header and action rail full width"
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart --plain-name "customer header omits redundant kiosk display name"
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart --plain-name "administrator entry is aligned inside the customer header"
```

Expected: the height, kiosk-name, right-edge alignment, and non-Ready
administrator assertions fail against the current shell.

- [ ] **Step 3: Simplify `_CustomerHeader`**

Set the header `SizedBox` height to `61`.

Replace the current row contents with:

```dart
const BixolonWordmark(style: TextStyle(fontSize: 16, height: 1.2)),
const SizedBox(width: 16),
Flexible(
  child: Text(
    title,
    key: const Key('customer-page-title'),
    maxLines: 1,
    overflow: TextOverflow.ellipsis,
    style: textTheme.titleMedium,
  ),
),
const Spacer(),
if (headerAction != null)
  SizedBox(
    key: const Key('customer-header-action'),
    height: 48,
    child: headerAction,
  ),
```

Do not render `displayName`, `kiosk-display-name`, or the vertical divider.
Keep `KioskDisplayNameScope` temporarily as a compatibility carrier so this
visual change does not alter session settings or other interfaces.

- [ ] **Step 4: Restrict `KioskHeaderActionScope` to Ready**

Change the scope guard in `CustomerCheckoutScreen.build` to:

```dart
if (widget.onEnterAdmin == null ||
    state.phase != CheckoutPhase.ready ||
    _catalogObjectId != null ||
    _catalogAddsProduct) {
  return scopedContent;
}
```

No administrator callback, confirmation copy, or audit behavior changes.

- [ ] **Step 5: Run shell and admin journey regression tests**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\dart.bat format lib\src\ui\components\checkout_scaffold.dart lib\src\ui\customer\customer_checkout_screen.dart test\ui\customer_checkout_screen_test.dart
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart test\app\bakery_app_admin_journey_test.dart test\ui\customer_admin_entry_control_test.dart test\ui\admin_entry_confirmation_sheet_test.dart
```

Expected: all tests pass; administrator confirmation remains unchanged and
administrator entry is absent after Ready.

- [ ] **Step 6: Commit the shell refinement**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart
git commit -m "style: simplify customer checkout header"
```

---

### Task 3: Reduce Ready to one instruction, camera, and scan action

**Files:**

- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart`

**Interfaces:**

- Consumes: `ReadyView(onScan, previewController)`,
  `CanonicalCameraPreview`, and `BakeryPrimaryButton`.
- Produces: `ready-placement-instruction`, an overlay-free canonical camera,
  and the existing `live-tray-placement-guide` geometry key.

- [ ] **Step 1: Write failing Ready copy and structure tests**

Replace the Ready presentation assertions in
`test/ui/customer_checkout_screen_test.dart` with:

```dart
expect(
  find.byKey(const Key('ready-placement-instruction')),
  findsOneWidget,
);
expect(find.text('트레이를 카메라 아래에 맞춰주세요.'), findsOneWidget);
expect(find.text('빵을 트레이에 올려주세요'), findsNothing);
expect(
  find.text('빵이 겹치지 않도록 펼쳐 놓으면 더 잘 확인할 수 있어요.'),
  findsNothing,
);
expect(find.byType(BakeryStatusBanner), findsNothing);
expect(find.text('빵 확인하기'), findsOneWidget);
expect(find.byType(FilledButton), findsOneWidget);
expect(find.byKey(const Key('live-tray-placement-guide')), findsOneWidget);
```

Add this contract assertion after pumping `ReadyView`:

```dart
final camera = find.byKey(const Key('live-tray-placement-guide'));
expect(
  find.descendant(
    of: camera,
    matching: find.byKey(const Key('ready-camera-focus-guide')),
  ),
  findsNothing,
);
```

- [ ] **Step 2: Run the focused Ready tests and verify RED**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart --plain-name "ready explains placement and exposes one scan action"
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_contract_test.dart --plain-name "ready preview preserves a useful tray aspect ratio"
```

Expected: the status-banner and duplicate-copy assertions fail.

- [ ] **Step 3: Replace the Ready body**

Remove the `bakery_status_banner.dart` import.

Build the body column in this order:

```dart
Text(
  '트레이를 카메라 아래에 맞춰주세요.',
  key: const Key('ready-placement-instruction'),
  style: Theme.of(context).textTheme.bodyLarge,
),
const SizedBox(height: 12),
Expanded(
  child: Center(
    child: AspectRatio(
      key: const Key('live-tray-placement-guide'),
      aspectRatio: previewAspectRatio,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(
          BixolonThemeExtension.of(context).surfaceRadius,
        ),
        child: previewController != null
            ? CanonicalCameraPreview(
                child: CameraPreview(previewController!),
              )
            : const ColoredBox(color: Color(0xFF2B2B2B)),
      ),
    ),
  ),
),
```

Use `EdgeInsets.only(top: 12, bottom: 12)`. Remove the bottom duplicate text,
the `Stack`, the centered 190 x 120 `DecoratedBox`, and every pre-recognition
overlay.

- [ ] **Step 4: Run Ready, camera, and accessibility tests**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\dart.bat format lib\src\ui\customer\ready_view.dart test\ui\customer_checkout_screen_test.dart test\ui\customer_checkout_contract_test.dart
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_screen_test.dart test\ui\customer_checkout_contract_test.dart test\ui\customer_checkout_accessibility_test.dart
```

Expected: tests pass at 1024 x 720 and 1280 x 820 without page scrolling or
camera cropping.

- [ ] **Step 5: Commit the Ready simplification**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart
git commit -m "style: simplify customer ready screen"
```

---

### Task 4: Normalize order hierarchy and rare exception controls

**Files:**

- Create: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_secondary_button.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/quantity_stepper.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart`

**Interfaces:**

- Consumes: `BixolonThemeExtension.selectedSurface`,
  `BixolonThemeExtension.controlBorder`,
  `BixolonThemeExtension.modalRadius`, existing order callbacks, and existing
  `QuantityStepper`.
- Produces: `BakerySecondaryButton(label, onPressed)`,
  `order-exception-actions`, `order-review-selected-line`, and consistent
  neutral exception actions without changing callback semantics.

- [ ] **Step 1: Write failing secondary-button and order tests**

Add to `test/ui/design_system_test.dart`:

```dart
testWidgets('secondary action is neutral and keeps a kiosk touch target', (
  tester,
) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: buildBakeryTheme(),
      home: Scaffold(
        body: BakerySecondaryButton(
          label: '상품 추가',
          onPressed: () {},
        ),
      ),
    ),
  );

  final button = tester.widget<OutlinedButton>(find.byType(OutlinedButton));
  final foreground = button.style!.foregroundColor!.resolve(<WidgetState>{});
  final side = button.style!.side!.resolve(<WidgetState>{});
  expect(foreground, const Color(0xFF424242));
  expect(side?.color, const Color(0xFFD8D8D8));
  expect(tester.getSize(find.byType(BakerySecondaryButton)).height, 48);
});
```

Add to the existing order contract test:

```dart
final exceptions = find.byKey(const Key('order-exception-actions'));
expect(exceptions, findsOneWidget);
expect(
  find.descendant(of: exceptions, matching: find.byType(OutlinedButton)),
  findsNWidgets(2),
);
expect(
  find.descendant(of: exceptions, matching: find.byType(TextButton)),
  findsNothing,
);
```

Add to `customer_checkout_screen_test.dart`:

```dart
final divider = tester.getRect(
  find.byKey(const Key('order-review-workspace-divider')),
);
final scene = tester.getRect(
  find.byKey(const Key('order-review-scene-pane')),
);
final task = tester.getRect(
  find.byKey(const Key('order-review-task-pane')),
);
expect(divider.width, 1);
expect(divider.left - scene.right, closeTo(12, 1));
expect(task.left - divider.right, closeTo(12, 1));
```

After selecting a recognized row, inspect its `ListTile`:

```dart
final selectedLine = tester.widget<ListTile>(
  find.byKey(const Key('order-review-selected-line')),
);
expect(
  selectedLine.selectedTileColor,
  const Color(0xFFFCEAD9),
);
```

- [ ] **Step 2: Run order and design-system tests and verify RED**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\design_system_test.dart test\ui\customer_checkout_contract_test.dart test\ui\customer_checkout_screen_test.dart
```

Expected: compilation fails because `BakerySecondaryButton` and the new keys
do not exist; current exception actions are text buttons and the gutter is
20 + 1 + 20.

- [ ] **Step 3: Create `BakerySecondaryButton`**

Create this component:

```dart
import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';

class BakerySecondaryButton extends StatelessWidget {
  const BakerySecondaryButton({
    required this.label,
    required this.onPressed,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return SizedBox(
      height: 48,
      child: OutlinedButton(
        onPressed: onPressed,
        style: ButtonStyle(
          foregroundColor: const WidgetStatePropertyAll(Color(0xFF424242)),
          side: WidgetStateProperty.resolveWith(
            (states) => BorderSide(
              color: states.contains(WidgetState.focused)
                  ? tokens.focus
                  : tokens.controlBorder,
              width: states.contains(WidgetState.focused) ? 2 : 1,
            ),
          ),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(tokens.controlRadius),
            ),
          ),
        ),
        child: Text(label),
      ),
    );
  }
}
```

- [ ] **Step 4: Apply the POS order structure**

In `OrderReviewView`, change the wide split to:

```dart
Expanded(flex: 3, child: scene),
const SizedBox(width: 12),
const VerticalDivider(
  key: Key('order-review-workspace-divider'),
  width: 1,
  thickness: 1,
),
const SizedBox(width: 12),
Expanded(flex: 2, child: task),
```

In `_OrderTaskPane`, replace the exception `Wrap` with:

```dart
Wrap(
  key: const Key('order-exception-actions'),
  spacing: 8,
  runSpacing: 8,
  children: [
    BakerySecondaryButton(
      label: '상품 추가',
      onPressed: onAddProduct,
    ),
    BakerySecondaryButton(
      label: '실제 빵 수가 달라요',
      onPressed: onCountMismatch,
    ),
  ],
),
```

Import `bakery_secondary_button.dart`.

In `_OrderLine`, use:

```dart
key: recognizedObjectIds.contains(selectedObjectId)
    ? const Key('order-review-selected-line')
    : Key('order-review-line-${line.product.productId}'),
selectedTileColor: BixolonThemeExtension.of(context).selectedSurface,
contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
minTileHeight: 64,
```

Keep all quantity, override, remove, and row-selection callbacks unchanged.
Apply `tokens.selectedSurface` to selected rows in
`customer_review_view.dart` as well.

- [ ] **Step 5: Normalize the stepper and catalog modal**

In `quantity_stepper.dart`, change the resting container border from
`tokens.divider` to `tokens.controlBorder`. Change focused borders from width
3 to width 2. Keep both 48 px icon-button constraints.

In `_OrderReviewCatalogPanel`, use:

```dart
borderRadius: BorderRadius.circular(tokens.modalRadius),
```

for both `Material` and `DecoratedBox`. Keep the existing modal dismissal,
catalog search, and selection callbacks.

- [ ] **Step 6: Run order, review, accessibility, and journey tests**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\dart.bat format lib\src\ui\components\bakery_secondary_button.dart lib\src\ui\components\quantity_stepper.dart lib\src\ui\customer\order_review_view.dart lib\src\ui\customer\customer_review_view.dart lib\src\ui\customer\customer_checkout_screen.dart test\ui\design_system_test.dart test\ui\customer_checkout_contract_test.dart test\ui\customer_checkout_screen_test.dart test\ui\customer_checkout_accessibility_test.dart
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\design_system_test.dart test\ui\customer_checkout_contract_test.dart test\ui\customer_checkout_screen_test.dart test\ui\customer_checkout_accessibility_test.dart test\app\bakery_app_admin_journey_test.dart
```

Expected: all focused tests pass, bidirectional box/row selection still
passes, exception callbacks still fire, and 200% text has no overflow.

- [ ] **Step 7: Commit the order hierarchy**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/components/bakery_secondary_button.dart apps/bakery_camera_flutter/lib/src/ui/components/quantity_stepper.dart apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart apps/bakery_camera_flutter/test/ui/design_system_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart apps/bakery_camera_flutter/test/ui/customer_checkout_accessibility_test.dart
git commit -m "style: normalize customer order hierarchy"
```

---

### Task 5: Regenerate visual evidence and verify the Windows release

**Files:**

- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_retake_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/customer_complete_1280x820.png`
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/design_system_1280x820.png`

**Interfaces:**

- Consumes: the completed theme, shell, Ready, review, and order components.
- Produces: committed visual evidence, a passing full test suite, a Windows
  release, a verified `1.1.0` installer payload, and a live UX observation.

- [ ] **Step 1: Run golden tests before updating and inspect the expected RED**

Run:

```powershell
cd apps\bakery_camera_flutter
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test test\ui\customer_checkout_accessibility_test.dart test\ui\design_system_test.dart
```

Expected: golden comparisons fail only for the intentionally changed customer
and design-system screens. Any semantics, overflow, or interaction failure
must be fixed before updating goldens.

- [ ] **Step 2: Regenerate the approved goldens**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test --update-goldens test\ui\customer_checkout_accessibility_test.dart test\ui\design_system_test.dart
```

Inspect every changed PNG and confirm:

- Ready has one instruction and no white camera box.
- Administrator is at the far right only in Ready evidence.
- Header typography and spacing are consistent.
- Review and Order retain the real image and labeled boxes.
- Order exception actions are neutral outlined controls.
- Total and payment remain the strongest commercial actions.
- No clipped text, nested structural card, or broken footer surface appears.

- [ ] **Step 3: Run exact-source verification**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\dart.bat format --output=none --set-exit-if-changed lib test
C:\workspace\tools\flutter-3.44.7\bin\dart.bat analyze
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test
git diff --check
```

Expected: formatting reports zero changed files, analysis reports no issues,
all Flutter tests pass, and `git diff --check` is clean.

- [ ] **Step 4: Build the Windows release**

Run:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat build windows --release
```

Expected:

```text
build\windows\x64\runner\Release\bakery_camera_prototype.exe
```

exists and the build exits successfully.

- [ ] **Step 5: Package version 1.1.0**

From the repository root, run:

```powershell
python scripts\build_camera_installer_payload.py --release-dir apps\bakery_camera_flutter\build\windows\x64\runner\Release --runtime-root artifacts\installer_payload\1.1.0-ux-final2\runtime --vc-runtime-dir artifacts\installer_payload\1.1.0-ux-final2 --output artifacts\installer_payload\1.1.0-pos-aligned-r1 --app-version 1.1.0
```

Expected:

```text
artifacts\installer_payload\1.1.0-pos-aligned-r1\bakery_camera_prototype.exe
```

exists with its runtime and installation manifest.

- [ ] **Step 6: Verify the packaged runtime**

Run:

```powershell
$env:PYTHONPATH='.'
python scripts\verify_camera_installation.py --root artifacts\installer_payload\1.1.0-pos-aligned-r1 --launch-worker-smoke --worker-device cpu --analysis-count 1
```

Expected: manifest verification, CPU runtime startup, worker readiness, and
one analysis smoke pass. Do not interpret the smoke output as an accuracy or
latency claim.

- [ ] **Step 7: Perform live Windows UX checks**

Launch the exact packaged executable and use Computer control to check:

1. Ready contains the BIXOLON/stage header, far-right administrator, one
   instruction, camera, and scan action only.
2. No white placement box appears over the live camera.
3. Scanning reaches automatic Order when the immutable inference policy
   accepts every object.
4. Captured image and detected boxes remain on the left.
5. Box-to-row and row-to-box selection both work.
6. `상품 추가` and `실제 빵 수가 달라요` are clearly controls but remain
   subordinate to total and payment.
7. Administrator is absent during analyzing, review, order, and payment.
8. Do not initiate a real payment.

Close the app after the checks and record unavailable physical payment
hardware as unverified.

- [ ] **Step 8: Commit visual evidence**

```powershell
git add apps/bakery_camera_flutter/test/ui/goldens/customer_ready_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_retake_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_review_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_order_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/customer_complete_1280x820.png apps/bakery_camera_flutter/test/ui/goldens/design_system_1280x820.png
git commit -m "test: update POS-aligned kiosk visual evidence"
```

Do not stage `apps/bakery_camera_flutter/test/ui/failures/`.
