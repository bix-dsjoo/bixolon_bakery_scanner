# Overlay Readability and Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every detection readable on the captured image, make row selection unambiguous, replace internal decision jargon, and keep the Windows preview in the canonical non-mirrored orientation.

**Architecture:** Keep the worker result and canonical box coordinates unchanged. Change only Flutter presentation: the painter renders full labels, the row surface separates semantic status from selection, and a small preview wrapper cancels the Windows camera plugin's built-in software mirror.

**Tech Stack:** Flutter 3, Dart, `camera` 0.12.0+2, `camera_windows` 0.2.6+4, `flutter_test`.

## Global Constraints

- Image labels contain only `NN Product name`; they never contain confidence.
- Confirmed teal and Unknown amber represent result status only.
- Selection uses a neutral surface and outline, not orange.
- Live preview, captured image, and overlay use real-world left-to-right orientation.
- Inference, model artifacts, calibrated thresholds, and canonical boxes do not change.
- Preserve `models/rfdetr_large_bakery_v1/` as the user's untracked Junction.

---

### Task 1: Canonical Windows Camera Preview

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/canonical_camera_preview.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Create: `apps/bakery_camera_flutter/test/ui/canonical_camera_preview_test.dart`

**Interfaces:**
- Consumes: any initialized camera preview as a `Widget`.
- Produces: `CanonicalCameraPreview({required Widget child, TargetPlatform? platform})`.

- [ ] **Step 1: Write the failing test**

```dart
testWidgets('cancels the camera_windows horizontal mirror', (tester) async {
  await tester.pumpWidget(const CanonicalCameraPreview(
    platform: TargetPlatform.windows,
    child: SizedBox(key: Key('preview')),
  ));
  final transform = tester.widget<Transform>(find.byType(Transform));
  expect(transform.transform.storage[0], -1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/ui/canonical_camera_preview_test.dart`

Expected: FAIL because `CanonicalCameraPreview` does not exist.

- [ ] **Step 3: Write minimal implementation**

Wrap the child in `Transform.flip(flipX: true)` only on Windows. The pinned
`camera_windows` implementation mirrors every texture in
`texture_handler.cpp`; the second flip restores the captured-image direction.
Use the wrapper around `CameraPreview(preview)` in `scanner_screen.dart`.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/ui/canonical_camera_preview_test.dart test/ui/scanner_screen_test.dart`

Expected: PASS.

### Task 2: Full Overlay Labels

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart`
- Modify: `apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart`

**Interfaces:**
- Produces: `overlayLabel(ResultOverlayItem item) -> String`.
- The painter uses that label for every object and paints the selected object last.

- [ ] **Step 1: Write the failing tests**

```dart
test('all overlay labels contain number and display name without score', () {
  const item = ResultOverlayItem(
    objectId: 'object-1',
    displayNumber: 1,
    imageBox: Rect.fromLTRB(0, 0, 10, 10),
    displayName: 'Pastry Bread',
    isUnknown: false,
  );
  expect(overlayLabel(item), '01  Pastry Bread');
});
```

Add an overlap paint assertion proving the selected box color is the last color
painted at the shared edge.

- [ ] **Step 2: Run tests to verify they fail**

Run: `flutter test test/scanner/result_overlay_test.dart`

Expected: FAIL because unselected objects still render number-only chips and
selected paint order follows source order.

- [ ] **Step 3: Write minimal implementation**

Replace number chips plus selected-only label with one bounded full label for
every object. Sort a copied paint list so the selected object is last. Keep the
existing 1.5/3 pixel box widths and status colors.

- [ ] **Step 4: Run tests to verify they pass**

Run: `flutter test test/scanner/result_overlay_test.dart`

Expected: PASS.

### Task 3: Clear Selection and Plain Decision Copy

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_view_data.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/evaluation_view_data_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`
- Update: `apps/bakery_camera_flutter/test/ui/goldens/result_rail_360x720.png`

**Interfaces:**
- Keeps existing object selection IDs and callbacks unchanged.
- Maps decision paths to user-facing labels only.

- [ ] **Step 1: Write failing assertions**

Assert:

```dart
expect(decisionPathLabel('repvit_direct'), '첫 분석에서 확정');
expect(decisionPathLabel('dinov3_confirmed'), '추가 확인 후 확정');
expect(decisionPathLabel('fusion_ranked'), '추가 확인 후 확정');
```

In the result-rail widget test, assert the selected row has a neutral selected
surface and outline while its semantic dot remains teal or amber.

- [ ] **Step 2: Run tests to verify they fail**

Run: `flutter test test/ui/evaluation_view_data_test.dart test/ui/result_rail_test.dart`

Expected: FAIL on old technical copy and orange selected rail.

- [ ] **Step 3: Write minimal implementation**

Remove the colored left rail. Keep a one-pixel divider for ordinary rows. Give
the selected row a light neutral fill and a one-pixel `bixolonInk` outline.
Keep the status dot unchanged. Replace only the three user-facing decision
labels above; immutable runtime path values remain unchanged.

- [ ] **Step 4: Run tests and refresh the golden**

Run:

```powershell
flutter test test/ui/evaluation_view_data_test.dart
flutter test test/ui/result_rail_test.dart --update-goldens
flutter test test/ui/result_rail_test.dart
```

Expected: PASS.

### Task 4: Regression, Release, and Installer

**Files:**
- Generated: `apps/bakery_camera_flutter/build/windows/x64/runner/Release/*`
- Generated: `artifacts/installer_payload/1.0.0/*`
- Generated: `dist/BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe`

- [ ] **Step 1: Run Flutter verification**

Run:

```powershell
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build windows --release
```

Expected: formatter clean, analyze clean, all tests pass, release build succeeds.

- [ ] **Step 2: Rebuild the payload and installer**

Use the repository's existing camera installer build script without changing
the payload allowlist or model artifacts.

Run:

```powershell
.\scripts\build_camera_installer.ps1
```

Expected: installer build succeeds and the final SHA-256 sidecar is regenerated.

- [ ] **Step 3: Verify output integrity**

Record installer byte size and SHA-256, confirm the payload includes the new
Flutter executable, and run the existing payload verification.

- [ ] **Step 4: Commit**

Stage only the source, tests, golden, spec, and plan. Never stage the user model
Junction or ignored build artifacts.
