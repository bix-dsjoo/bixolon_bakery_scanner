# All-Surfaces Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Flutter application's generic card-and-accent-strip styling with a restrained operational-ledger visual system across every existing customer, administrator, and evaluator surface while preserving behavior.

**Architecture:** Start with theme and shared primitives, then migrate customer and administrator surfaces onto those primitives without moving behavioral state or callbacks. Keep screen-specific presentation inside the existing screen files, add small shared flat-section and ledger-row widgets only where at least two screens need the same visual contract, and validate each migration with focused widget tests before updating goldens.

**Tech Stack:** Flutter 3 / Dart 3, Material 3, Pretendard assets, `flutter_test`, existing golden-test harness.

## Global Constraints

- Do not add or remove features, destinations, data, user-flow steps, or inference behavior.
- Preserve the existing customer bottom-action region, administrator destination order, and `1100` px compact breakpoint.
- Use `#F7F7F5` canvas, `#FFFFFF` paper, `#171717` ink, `#626262` muted ink, `#E5E3E0` divider, and `#EE7203` as the single accent.
- Use a 4 px control radius and 8 px surface radius.
- Do not add gradients, glow, blur, glass effects, or ambient shadow.
- Keep status text and shape/icon semantics; never rely on color alone.
- Preserve 44 px minimum interactive targets, keyboard focus, text scaling, and layouts at `1280×820` and `1024×720`.
- Do not change `portable_cpu_smoke/` or legacy inference behavior.

---

### Task 1: Lock the visual contracts in tests

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/admin/dashboard_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/admin/product_management_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/admin/settings_screen_test.dart`

**Interfaces:**
- Consumes: existing public screen constructors and theme builder.
- Produces: behavioral assertions that distinguish flat sections and ledger rows from independent `Card` widgets.

- [ ] **Step 1: Add failing shared-style assertions**

Add assertions that pump representative customer and administrator widgets,
then verify the redesigned contracts:

```dart
expect(find.byType(Card), findsNothing);
expect(find.byKey(const ValueKey('customer-page-title')), findsOneWidget);
expect(find.byKey(const ValueKey('status-message')), findsOneWidget);
expect(find.byKey(const ValueKey('dashboard-summary-ledger')), findsOneWidget);
expect(find.byKey(const ValueKey('product-list')), findsOneWidget);
expect(find.byKey(const ValueKey('settings-sections')), findsOneWidget);
```

Retain every existing callback, text, navigation, and semantic assertion in
the touched tests.

- [ ] **Step 2: Run the focused tests and confirm the new assertions fail**

Run:

```powershell
flutter test test/ui/design_system_test.dart test/ui/admin/dashboard_screen_test.dart test/ui/admin/product_management_screen_test.dart test/ui/admin/settings_screen_test.dart
```

Expected: failures for the new keys and existing `Card` widgets, with existing
behavioral assertions still passing up to those failures.

- [ ] **Step 3: Commit the failing contract tests**

```powershell
git add apps/bakery_camera_flutter/test/ui
git commit -m "test: define restrained visual contracts"
```

### Task 2: Refine theme tokens and shared customer primitives

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/bixolon_theme_extension.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/checkout_scaffold.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_status_banner.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/bakery_primary_button.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/product_tile.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/components/quantity_stepper.dart`
- Test: `apps/bakery_camera_flutter/test/ui/design_system_test.dart`

**Interfaces:**
- Consumes: `BixolonThemeExtension.of(BuildContext)`.
- Produces: the existing shared widget APIs with new keys
  `customer-page-title` and `status-message`; no constructor signature changes.

- [ ] **Step 1: Reduce global radius and define restrained component themes**

Set `controlRadius` to `4` and `surfaceRadius` to `8`. Add `cardTheme`,
`inputDecorationTheme`, `dividerTheme`, `listTileTheme`, and distinct button
foreground/background/side rules in `buildBakeryTheme()`. `CardThemeData`
must have zero elevation, `tokens.paper`, a `tokens.divider` border, and an
8 px radius so unmigrated boundary-bearing cards remain quiet during the
transition.

- [ ] **Step 2: Remove decorative customer title and status strips**

In `CheckoutScaffold`, replace the title's left orange border with a keyed,
plain title block:

```dart
KeyedSubtree(
  key: const ValueKey('customer-page-title'),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [const BixolonWordmark(), const SizedBox(height: 8), Text(title)],
  ),
)
```

In `BakeryStatusBanner`, keep the icon, title, and supporting text but replace
the left accent border with a full 1 px neutral border and a semantic tint no
stronger than 6% opacity. Add `key: const ValueKey('status-message')`.

- [ ] **Step 3: Simplify action and row primitives**

Render `BakeryPrimaryButton` without an icon when the caller does not require a
distinct icon-only meaning. Make `ProductTile` a flat row with a bottom
divider, not a decorated rounded container. Keep `QuantityStepper` as one
bounded control because its boundary communicates a single compound input.

- [ ] **Step 4: Run the design-system tests**

Run:

```powershell
flutter test test/ui/design_system_test.dart test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart
```

Expected: all pass.

- [ ] **Step 5: Commit the shared visual system**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui apps/bakery_camera_flutter/test/ui/design_system_test.dart
git commit -m "style: establish operational ledger visual system"
```

### Task 3: Migrate every customer checkout state

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/ready_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/analyzing_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/retake_required_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/catalog_picker.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/order_review_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/payment_view.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/customer/customer_checkout_screen.dart`
- Test: `apps/bakery_camera_flutter/test/ui/customer_checkout_screen_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/customer_checkout_contract_test.dart`

**Interfaces:**
- Consumes: the unchanged checkout controller/state and shared UI component
  constructors.
- Produces: the same customer action callbacks and state transitions with flat,
  divided product and candidate rows.

- [ ] **Step 1: Add a failing customer visual-structure test**

For ready, review, order, retake, and completion states, assert one filled
primary action and no nested `Card` widgets:

```dart
expect(find.byType(FilledButton), findsOneWidget);
expect(find.byType(Card), findsNothing);
```

Keep existing state-specific text and callback assertions.

- [ ] **Step 2: Flatten customer content without changing order**

Keep the camera viewport boundary. Convert product candidates, order lines,
and catalog results to flat rows separated by `Divider`. Remove icons from
text actions such as catalog search, product add, and mismatch reporting.
Keep delete and quantity icons because they are conventional direct-manipulation
controls.

- [ ] **Step 3: Restrain empty, retake, and completion artwork**

Cap secondary illustrations at the smaller of their current size or 128 px,
reduce surrounding whitespace, and keep all instructions and actions in their
existing order. Do not change assets or copy.

- [ ] **Step 4: Run customer tests**

Run:

```powershell
flutter test test/ui/customer_checkout_screen_test.dart test/ui/customer_checkout_contract_test.dart test/ui/customer_checkout_accessibility_test.dart test/integration/customer_checkout_journey_test.dart
```

Expected: all pass.

- [ ] **Step 5: Commit customer surface migration**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/customer apps/bakery_camera_flutter/test/ui
git commit -m "style: flatten customer checkout surfaces"
```

### Task 4: Rebuild the administrator shell and dashboard presentation

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/admin_shell.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/dashboard_screen.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/admin_shell_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/dashboard_screen_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/admin/admin_accessibility_test.dart`

**Interfaces:**
- Consumes: unchanged `AppModeController`, `AdminDestination`, dashboard
  repository, and attention callback.
- Produces: `dashboard-summary-ledger` and `dashboard-rate-ledger` keyed
  grouped regions; destination selection behavior is unchanged.

- [ ] **Step 1: Quiet the navigation**

Replace the administrator `Chip` with `Text('관리자')` using muted label
styling. Remove the icon from the return-to-customer outlined button. Keep the
selected row background and add a 2 px orange indicator inside the selected
navigation row only.

- [ ] **Step 2: Replace metric cards with one ledger**

Create one keyed summary region:

```dart
Semantics(
  container: true,
  child: Container(
    key: const ValueKey('dashboard-summary-ledger'),
    decoration: BoxDecoration(
      border: Border.symmetric(horizontal: BorderSide(color: tokens.divider)),
    ),
    child: Row(children: summaryCells),
  ),
)
```

Each cell keeps the same label and value. Separate cells with vertical
hairlines, use tabular figures, and remove metric icons.

- [ ] **Step 3: Flatten rates and attention**

Render operational rates under `dashboard-rate-ledger` as aligned compact
cells with no independent cards. Render recent attention as divided
`ListTile` rows with no leading arrow and retain the trailing chevron and
callback.

- [ ] **Step 4: Run shell and dashboard tests**

Run:

```powershell
flutter test test/ui/admin/admin_shell_test.dart test/ui/admin/dashboard_screen_test.dart test/ui/admin/dashboard_readiness_controller_test.dart test/ui/admin/admin_accessibility_test.dart
```

Expected: all pass.

- [ ] **Step 5: Commit shell and dashboard**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/admin/admin_shell.dart apps/bakery_camera_flutter/lib/src/ui/admin/dashboard_screen.dart apps/bakery_camera_flutter/test/ui/admin
git commit -m "style: turn admin overview into an operational ledger"
```

### Task 5: Flatten administrator work queues, records, products, diagnostics, and settings

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/transaction_history_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/transaction_detail_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/review_inbox_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/review_detail_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/product_management_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/product_editor_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/diagnostics_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/settings_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/retention_preview_dialog.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/admin/widgets/audit_fact_table.dart`
- Test: corresponding files under `apps/bakery_camera_flutter/test/ui/admin/`

**Interfaces:**
- Consumes: unchanged repositories, models, and callbacks.
- Produces: keyed `product-list`, `settings-sections`, and
  `diagnostics-sections` regions while preserving current actions and fields.

- [ ] **Step 1: Add failing collection and section assertions**

Add keys to the expected tests and assert the top-level collections contain no
`Card` descendants:

```dart
expect(find.byKey(const ValueKey('product-list')), findsOneWidget);
expect(find.byKey(const ValueKey('settings-sections')), findsOneWidget);
expect(find.byKey(const ValueKey('diagnostics-sections')), findsOneWidget);
```

- [ ] **Step 2: Flatten transaction and review records**

Replace record cards with divided rows. Keep filter controls, sort/order,
selected values, evidence, review choices, and callbacks. Use a two-column
`LayoutBuilder` branch only when the current content fits at widths of at least
900 px; otherwise retain the existing reading order in one column.

- [ ] **Step 3: Convert products to dense list rows**

Use one keyed `ListView`/`Column` region. Each row keeps thumbnail, product
name, price, sale state, recognition state, expand/details affordance, and edit
action. Replace status `Chip` widgets with icon-plus-text status labels and
thin dividers. Remove the icon from the labeled add-product button.

- [ ] **Step 4: Convert diagnostics and settings to flat sections**

Keep one subtle readiness summary and make refresh a normal-width filled
button. Render connectivity, pipeline, provenance, settings, retention, and
administrator fields as section headings followed by aligned rows and
dividers. Remove the icon from labeled refresh and retention-preview buttons.
Preserve copy buttons for hashes.

- [ ] **Step 5: Run administrator screen tests**

Run:

```powershell
flutter test test/ui/admin
```

Expected: all pass.

- [ ] **Step 6: Commit administrator surface migration**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/admin apps/bakery_camera_flutter/test/ui/admin
git commit -m "style: flatten administrator work surfaces"
```

### Task 6: Align evaluator and scanner surfaces

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_disclosures.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/retake_guidance.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_summary.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart`
- Test: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/canonical_camera_preview_test.dart`

**Interfaces:**
- Consumes: unchanged presentation state and evaluation view data.
- Produces: the same boxes, counts, confidence, paths, and disclosure behavior
  using flat ruled information regions.

- [ ] **Step 1: Preserve evidence boundaries and flatten summaries**

Keep camera, crop, overlay, and evidence-table boundaries because they encode
canonical image/evidence regions. Remove decorative rounded wrappers around
plain summary text and object metadata. Use dividers between result objects.

- [ ] **Step 2: Reduce status-strip emphasis**

Keep status wording, system state, and controls. Use neutral background,
hairline separators, and semantic text/icon color only for the state itself.
Remove filled pills that do not indicate an interactive selection.

- [ ] **Step 3: Run evaluator tests**

Run:

```powershell
flutter test test/ui/scanner_screen_test.dart test/ui/result_rail_test.dart test/ui/canonical_camera_preview_test.dart test/ui/evaluation_view_data_test.dart
```

Expected: all pass.

- [ ] **Step 4: Commit evaluator alignment**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui apps/bakery_camera_flutter/test/ui
git commit -m "style: align evaluator with restrained visual system"
```

### Task 7: Regenerate goldens and verify the complete application

**Files:**
- Modify: `apps/bakery_camera_flutter/test/ui/goldens/*.png`
- Modify only if assertions require intentional visual updates:
  `apps/bakery_camera_flutter/test/ui/*_test.dart`

**Interfaces:**
- Consumes: all migrated surfaces.
- Produces: reviewed 1280×820 and result-rail golden evidence.

- [ ] **Step 1: Format and analyze**

Run:

```powershell
dart format lib test
flutter analyze
```

Expected: formatting completes and analysis reports no issues.

- [ ] **Step 2: Run the full non-golden Flutter suite**

Run:

```powershell
flutter test --exclude-tags=golden
```

Expected: all tests pass with no skips treated as passes.

- [ ] **Step 3: Regenerate approved goldens**

Run the repository's golden update command:

```powershell
flutter test test/ui --update-goldens
```

Expected: only existing approved golden files change; no new screen or state is
introduced.

- [ ] **Step 4: Inspect every changed golden**

Open each changed PNG and verify:

- no decorative left title/status strip;
- no gradient, glow, glass, or ambient shadow;
- one dominant customer action;
- dashboard metrics read as one ledger;
- product, review, and attention content reads as lists;
- settings and diagnostics read as flat sections;
- no clipping at 1280×820; and
- status remains understandable without color.

- [ ] **Step 5: Run the full Flutter suite including goldens**

Run:

```powershell
flutter test
```

Expected: all tests pass.

- [ ] **Step 6: Verify repository boundaries**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; no changes under `portable_cpu_smoke/`; no
unrelated user files are staged.

- [ ] **Step 7: Commit final golden evidence**

```powershell
git add apps/bakery_camera_flutter/test/ui/goldens apps/bakery_camera_flutter/test/ui
git commit -m "test: refresh restrained UI golden evidence"
```

## Plan self-review

- Every design-spec section maps to Tasks 2–7.
- Every behavioral migration begins with or preserves focused test coverage.
- Shared constructors remain stable; later tasks consume only existing widget
  APIs and documented keys.
- No placeholder, deferred requirement, feature addition, or inference change
  appears in the plan.
- The plan uses one implementation stream because all tasks modify the same
  shared Flutter theme and widget tree; parallel edits would create avoidable
  conflicts.
