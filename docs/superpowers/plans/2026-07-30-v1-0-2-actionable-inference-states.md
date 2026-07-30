# 1.0.2 Actionable Inference States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show every scan as `정상 인식`, `알 수 없음`, or `이 사진만으로 판단하기 어려워요`, preserving canonical inference and guiding retakes only when evidence is not usable.

**Architecture:** A versioned presentation-policy adapter consumes final RF-DETR proposals and immutable classifier decisions after inference completes. It emits an additive `presentation` result section. Flutter deserializes that section into immutable view data and switches the result rail to the appropriate action-first state, leaving evidence under a disclosure.

**Tech Stack:** Python 3.11/pytest, Flutter/Dart 3/flutter_test, existing Windows offline payload/installer tooling.

## Global Constraints

- Do not modify RF-DETR-L threshold, Box Assurance, component resolver, RepViT gate, DINOv3 evidence, fusion artifact, classifier artifacts, or canonical counts.
- There is no segmentation model; call the user-visible condition `검출/분리 문제` or `후보 근거 부족`, never segmentation success/failure.
- Do not state that a product is new or unregistered. `Unknown` remains fail-closed and never aggregates as a SKU.
- Presentation policy values route UI only. Version, SHA-256 verify, and report them; they are not classifier thresholds.
- If any `needs_retake` condition applies, do not present the result count as a usable final total. Keep boxes/evidence as diagnostics only.
- Overlay labels show ordinal plus product/state without confidence. Use canonical visual-frame coordinates unchanged.
- Keep Windows GPU preference/CPU fallback and legacy portable CPU smoke behavior intact.

---

## File Structure

- Create `configs/camera_presentation_policy.json`: signed v1 UI-routing policy.
- Create `src/bakery_scanner/prototype/presentation_policy.py`: validated policy and pure presentation-state derivation.
- Modify `src/bakery_scanner/prototype/camera_runtime.py`: load the policy and emit the additive payload.
- Modify `src/bakery_scanner/prototype/camera_protocol.py`: validate presentation payload consistency before emitting it.
- Modify `tests/prototype/test_camera_runtime.py`, `tests/prototype/test_camera_protocol.py`; create `tests/prototype/test_presentation_policy.py`.
- Modify `deployment/build_camera_installer.ps1`, `tests/deployment/test_camera_installer_payload.py`, and `tests/deployment/test_camera_installer_manifest.py`: bundle and hash the policy.
- Modify `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart`: strict Dart contract parsing.
- Create `apps/bakery_camera_flutter/lib/src/ui/presentation_state.dart` and `retake_guidance.dart`: copy and state-specific UI.
- Modify `evaluation_view_data.dart`, `result_rail.dart`, `evaluation_summary.dart`, `evaluation_object_list.dart`, `candidate_evidence_table.dart`, `scanner_screen.dart`, and `scanner/result_overlay.dart`.
- Modify Flutter parser, fixture, rail, screen, and overlay tests.

### Task 1: Add a fixed presentation-policy adapter

**Files:**
- Create: `configs/camera_presentation_policy.json`
- Create: `src/bakery_scanner/prototype/presentation_policy.py`
- Test: `tests/prototype/test_presentation_policy.py`

**Interfaces:**
- Consumes: final ordered proposals/decisions and canonical image dimensions.
- Produces: `PresentationDecision.to_payload()` containing `state`, `final_count_usable`, `retake_scope`, `retake_object_ids`, `instruction_code`, `candidate_object_ids`, `policy_id`, and `policy_sha256`.
- Policy values: `candidate_top1_min_score=0.30`, `candidate_top12_min_margin=0.05`, `box_overlap_iou=0.70`.

- [ ] **Step 1: Write the failing policy tests**

```python
def test_unknown_with_useful_top3_stays_unknown(policy):
    result = policy.evaluate(
        proposals=(proposal("object-1", (10, 10, 200, 200)),),
        decisions=(unknown(top3=(0.62, 0.31, 0.07)),),
    )

    assert result.to_payload()["state"] == "unknown"
    assert result.to_payload()["candidate_object_ids"] == ["object-1"]
    assert result.to_payload()["final_count_usable"] is True


def test_weak_unknown_requests_object_retake(policy):
    result = policy.evaluate(
        proposals=(proposal("object-1", (10, 10, 200, 200)),),
        decisions=(unknown(top3=(0.29, 0.28, 0.27)),),
    )

    assert result.to_payload()["state"] == "needs_retake"
    assert result.to_payload()["retake_scope"] == "object"
    assert result.to_payload()["instruction_code"] == "candidate_evidence_weak"
    assert result.to_payload()["candidate_object_ids"] == []
```

Add exact boundary tests: no proposals -> scan `no_bread_detected`; IoU `0.70` -> both IDs + `separate_breads`; IoU `0.699` does not trigger; score `0.30` and margin `0.05` remain candidates; all registered decisions -> `normal`; malformed policy/hash mismatch rejects startup; result order is deterministic.

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `python -m pytest tests/prototype/test_presentation_policy.py -q`

Expected: FAIL because the artifact and module do not exist.

- [ ] **Step 3: Implement the policy and adapter**

Create the policy file as:

```json
{
  "box_overlap_iou": 0.7,
  "candidate_top12_min_margin": 0.05,
  "candidate_top1_min_score": 0.3,
  "policy_id": "camera_action_state_v1",
  "schema_version": 1
}
```

`PresentationPolicy.load(Path)` requires exactly those fields, checks finite `[0,1]` values, and stores `sha256(path.read_bytes())`. `evaluate` must apply this order:

```python
if not proposals:
    return scan_retake("no_bread_detected")
if ids := overlapping_object_ids(proposals, threshold=policy.box_overlap_iou):
    return object_retake("separate_breads", ids)
if ids := weak_unknown_ids(decisions, top1_min=0.30, top12_margin=0.05):
    return object_retake("candidate_evidence_weak", ids)
if ids := unknown_ids(decisions):
    return unknown(candidate_object_ids=ids)
return normal()
```

Calculate IoU only on valid canonical XYXY boxes, sort IDs, and never alter proposals, decisions, or counts.

- [ ] **Step 4: Run the focused test and confirm success**

Run: `python -m pytest tests/prototype/test_presentation_policy.py -q`

Expected: PASS with boundary coverage.

- [ ] **Step 5: Commit**

```powershell
git add configs/camera_presentation_policy.json src/bakery_scanner/prototype/presentation_policy.py tests/prototype/test_presentation_policy.py
git commit -m "feat: add camera presentation policy"
```

### Task 2: Add the presentation field to the Python worker contract

**Files:**
- Modify: `src/bakery_scanner/prototype/camera_runtime.py:130-355,635-699`
- Modify: `src/bakery_scanner/prototype/camera_protocol.py:130-175`
- Test: `tests/prototype/test_camera_runtime.py`
- Test: `tests/prototype/test_camera_protocol.py`

**Interfaces:**
- Consumes: the Task 1 `PresentationPolicy`; existing output objects/counts unchanged.
- Produces: required `presentation` map on every `type: result` event.
- Values: `state=normal|unknown|needs_retake`, `retake_scope=null|scan|object`, valid lowercase SHA-256 policy hash.

- [ ] **Step 1: Write failing runtime/protocol tests**

```python
def test_runtime_adds_presentation_without_mutating_counts(tmp_path):
    result = initialized_runtime_with_weak_unknown(tmp_path).analyze(image_path, "r1")

    assert result["counts"] == {"6": 1}
    assert result["unknown_count"] == 1
    presentation = result["presentation"]
    assert presentation["state"] == "needs_retake"
    assert presentation["final_count_usable"] is False
    assert presentation["retake_scope"] == "object"
    assert presentation["retake_object_ids"] == ["object-2"]
    assert presentation["instruction_code"] == "candidate_evidence_weak"


def test_protocol_rejects_inconsistent_presentation():
    with pytest.raises(ValueError, match="presentation"):
        validate_result_event(result_with(
            state="normal", final_count_usable=False, retake_scope=None
        ))
```

Add malformed cases for non-SHA hashes, scan state with object IDs, object state without object IDs, normal/unknown with a retake instruction, and candidate IDs referring to a registered object.

- [ ] **Step 2: Run the tests and confirm failure**

Run: `python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py -q`

Expected: FAIL because output does not contain `presentation` and no validator exists.

- [ ] **Step 3: Implement additive result emission**

In `CameraInferenceRuntime.initialize`, load `root/configs/camera_presentation_policy.json` after existing detector/classifier integrity checks. In `analyze`, call the adapter after final `_result_objects(...)` aggregation and add only:

```python
"presentation": self._presentation_policy.evaluate(
    proposals=ordered_proposals,
    decisions=ordered_decisions,
).to_payload(),
```

Add `validate_result_event(result)` in `camera_protocol.py` and call it immediately before `emit(result)`. It validates presentation field shape, enum relations, object IDs, and hashes but must not reclassify anything. Invalid output becomes the existing `analysis_failed` event.

- [ ] **Step 4: Run the tests and confirm success**

Run: `python -m pytest tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py -q`

Expected: PASS; existing box/count/progress determinism stays green.

- [ ] **Step 5: Commit**

```powershell
git add src/bakery_scanner/prototype/camera_runtime.py src/bakery_scanner/prototype/camera_protocol.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py
git commit -m "feat: emit actionable camera presentation state"
```

### Task 3: Include the policy in the offline 1.0.2 package

**Files:**
- Modify: `deployment/build_camera_installer.ps1`
- Test: `tests/deployment/test_camera_installer_payload.py`
- Test: `tests/deployment/test_camera_installer_manifest.py`
- Modify: `apps/bakery_camera_flutter/pubspec.yaml`

**Interfaces:**
- Consumes: `configs/camera_presentation_policy.json`.
- Produces: payload file `configs/camera_presentation_policy.json` and its normal manifest SHA entry.
- Version: update `1.0.1+2` to `1.0.2+3`.

- [ ] **Step 1: Write the failing packaging test**

```python
def test_camera_payload_contains_hashed_presentation_policy(payload_root):
    policy = payload_root / "configs" / "camera_presentation_policy.json"
    manifest = load_payload_manifest(payload_root)

    assert policy.is_file()
    assert manifest["files"]["configs/camera_presentation_policy.json"] == sha256(policy)
```

Add a tamper test that changes policy bytes and requires the package verifier to report this path.

- [ ] **Step 2: Run the packaging tests and confirm failure**

Run: `python -m pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Expected: FAIL because the policy is not copied or manifested.

- [ ] **Step 3: Copy via the existing config payload mechanism**

Update `build_camera_installer.ps1` to copy the policy under `configs` through the existing recursive manifest generator—no duplicate independent copy. Update `pubspec.yaml` to `version: 1.0.2+3`.

- [ ] **Step 4: Run the packaging tests and confirm success**

Run: `python -m pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Expected: PASS with exact hash verification.

- [ ] **Step 5: Commit**

```powershell
git add deployment/build_camera_installer.ps1 tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py apps/bakery_camera_flutter/pubspec.yaml
git commit -m "build: bundle presentation policy in camera installer"
```

### Task 4: Parse the strict presentation contract in Flutter

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_models.dart:61-405`
- Create: `apps/bakery_camera_flutter/lib/src/ui/presentation_state.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_view_data.dart:5-125`
- Test: `apps/bakery_camera_flutter/test/inference/inference_models_test.dart`
- Test: `apps/bakery_camera_flutter/test/support/inference_fixtures.dart`
- Test: `apps/bakery_camera_flutter/test/ui/evaluation_view_data_test.dart`

**Interfaces:**
- Consumes: result `presentation` JSON from Task 2.
- Produces: immutable `InferencePresentation`, `CameraPresentationState`, `EvaluationPanelData.presentation`, and row `showCandidates`.
- Enums: `InferencePresentationState.normal|unknown|needsRetake`, `RetakeScope.scan|object`, `RetakeInstruction.noBreadDetected|separateBreads|candidateEvidenceWeak`.

- [ ] **Step 1: Write failing parser/view-data tests**

```dart
test('parses object retake without changing canonical counts', () {
  final result = InferenceResult.fromJson(resultJson(
    presentation: presentationJson(
      state: 'needs_retake',
      finalCountUsable: false,
      retakeScope: 'object',
      retakeObjectIds: ['object-2'],
      instructionCode: 'candidate_evidence_weak',
      candidateObjectIds: const [],
    ),
  ));

  expect(result.counts, {6: 1});
  expect(result.presentation.retakeObjectIds, ['object-2']);
});

test('weak Unknown hides candidates in view data', () {
  final data = EvaluationPanelData.fromState(stateWithWeakUnknown());

  expect(data.presentation.finalCountUsable, isFalse);
  expect(data.rows.single.showCandidates, isFalse);
  expect(data.presentation.primaryInstruction, '빵이 잘 보이도록 다시 촬영해 주세요');
});
```

Add parser failures for absent presentation, non-SHA policy hash, absent referenced ID, state/scope contradiction, and candidate IDs naming registered objects; add normal-state count equality.

- [ ] **Step 2: Run the Flutter tests and confirm failure**

Run: `flutter test test/inference/inference_models_test.dart test/ui/evaluation_view_data_test.dart`

Expected: FAIL because result models have no `presentation` property.

- [ ] **Step 3: Implement deserialization and UI-only mapping**

Require `presentation` in `InferenceResult.fromJson`; validate its IDs against parsed `objects` after canonical count validation. Preserve existing `InferenceObject`, `counts`, and `unknownCount` semantics.

In `presentation_state.dart`, implement this only UI copy:

```dart
String instructionFor(RetakeInstruction instruction) => switch (instruction) {
  RetakeInstruction.noBreadDetected => '빵을 찾지 못했어요. 빵이 모두 보이도록 다시 촬영해 주세요',
  RetakeInstruction.separateBreads => '빵 사이 간격을 두고 다시 촬영해 주세요',
  RetakeInstruction.candidateEvidenceWeak => '빵이 잘 보이도록 다시 촬영해 주세요',
};
```

Expose `showCandidates` only for worker-provided candidate IDs. Do not recompute score logic in Dart.

- [ ] **Step 4: Run the Flutter tests and confirm success**

Run: `flutter test test/inference/inference_models_test.dart test/ui/evaluation_view_data_test.dart`

Expected: PASS with strict rejection and unchanged canonical count tests.

- [ ] **Step 5: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/inference/inference_models.dart apps/bakery_camera_flutter/lib/src/ui/presentation_state.dart apps/bakery_camera_flutter/lib/src/ui/evaluation_view_data.dart apps/bakery_camera_flutter/test/inference/inference_models_test.dart apps/bakery_camera_flutter/test/support/inference_fixtures.dart apps/bakery_camera_flutter/test/ui/evaluation_view_data_test.dart
git commit -m "feat: parse camera presentation states"
```

### Task 5: Render Normal, Unknown, and retake-first result rails

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/retake_guidance.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart:36-171`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_summary.dart:7-77`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart:8-149`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart:8-111`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart:263-319`
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart`
- Test: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`
- Test: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`
- Test: `apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart`

**Interfaces:**
- Consumes: Task 4 panel presentation and row `showCandidates`.
- Produces: action-first rail, collapsible `분석 참고`, diagnostic rows, and overlay `isRetake`/`statusLabel`.

- [ ] **Step 1: Write failing widget and painter tests**

```dart
testWidgets('scan retake suppresses final total and leads with instruction', (
  tester,
) async {
  await pumpResultRail(tester, stateWithScanRetake());

  expect(find.text('이 사진만으로 판단하기 어려워요'), findsOneWidget);
  expect(find.text('빵을 찾지 못했어요. 빵이 모두 보이도록 다시 촬영해 주세요'), findsOneWidget);
  expect(find.textContaining('총 '), findsNothing);
  expect(find.text('분석 참고'), findsOneWidget);
});

test('retake overlay label has no confidence', () {
  expect(overlayLabel(retakeItem), '02  다시 촬영 필요');
  expect(overlayLabel(retakeItem), isNot(contains('%')));
});
```

Add cases: normal retains existing summary/quantity rows; useful Unknown shows exactly three candidate rows; weak candidates show none; object retake label wins over product label; retake still has `다시 촬영`; keyboard semantics have guidance; existing 1280x820/1024x720 layouts do not overflow.

- [ ] **Step 2: Run the UI tests and confirm failure**

Run: `flutter test test/ui/result_rail_test.dart test/ui/scanner_screen_test.dart test/scanner/result_overlay_test.dart`

Expected: FAIL because the current rail always renders summary and any selected Unknown shows candidates.

- [ ] **Step 3: Implement action-first rendering**

Create `RetakeGuidance` with:

```text
이 사진만으로 판단하기 어려워요
[specific instruction]
분석 참고  ▾
```

For `normal`, retain current summary/list/quantity flow. For `unknown`, keep summary and candidate tables only on `showCandidates`. For `needsRetake`, replace `EvaluationSummary` and `QuantityDisclosure` with `RetakeGuidance`; keep rows, model info, and timing under `분석 참고` as diagnostics.

Extend `ResultOverlayItem` with `isRetake` and `statusLabel`. In `scanner_screen.dart`, assign `다시 촬영 필요` for retake IDs, `알 수 없음` for Unknown, else SKU name. Paint retake boxes amber, confirmed boxes teal, selected boxes last, and never append confidence to labels. Replace `object.isUnknown` candidate gating with `row.showCandidates`.

- [ ] **Step 4: Run the UI tests and confirm success**

Run: `flutter test test/ui/result_rail_test.dart test/ui/scanner_screen_test.dart test/scanner/result_overlay_test.dart`

Expected: PASS; normal/Unknown remains usable, retakes suppress final total and guide recapture.

- [ ] **Step 5: Commit**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/retake_guidance.dart apps/bakery_camera_flutter/lib/src/ui/result_rail.dart apps/bakery_camera_flutter/lib/src/ui/evaluation_summary.dart apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart apps/bakery_camera_flutter/test/ui/result_rail_test.dart apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart
git commit -m "feat: guide camera retakes from inference evidence"
```

### Task 6: Verify and build the Windows 1.0.2 release

**Files:**
- Generated only: `artifacts/installer_payload/1.0.2/**`, `dist/1.0.2/**`.

**Interfaces:**
- Consumes: source changes from Tasks 1-5 and the existing offline model runtime.
- Produces: hash-verified 1.0.2 payload/installer and recorded UI-only validation evidence.

- [ ] **Step 1: Run all changed contracts**

From repository root:

```powershell
python -m pytest tests/prototype/test_presentation_policy.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_protocol.py tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q
```

From `apps/bakery_camera_flutter`:

```powershell
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat analyze
C:\workspace\tools\flutter-3.44.7\bin\flutter.bat test
```

Expected: selected Python tests pass, Flutter analysis reports `No issues found!`, and all Flutter tests pass.

- [ ] **Step 2: Build and smoke-test the offline executable/installer**

Run the existing 1.0.2 payload and installer workflow, then its package verifier and worker smoke command. Require the worker's JSON result to contain `presentation.policy_id == "camera_action_state_v1"`, a valid policy SHA-256, and the existing RF-DETR/RepViT/DINOv3/fusion identifiers.

- [ ] **Step 3: Manually accept the three flows on Windows**

Launch the payload EXE. Confirm a normal photo displays a final total; a useful Unknown displays `알 수 없음` and three candidates; an empty/overlapping/weak-evidence fixture leads with the correct retake instruction and no final total. Verify preview remains non-mirrored, labels are confidence-free, `분석 참고` exposes evidence/timings, and `다시 촬영` returns to live camera.

- [ ] **Step 4: Record delivery evidence**

Record payload and installer SHA-256, package verifier output, worker smoke output, device/backend, model IDs, presentation-policy SHA-256, test outputs, and observed latency in the 1.0.2 build report. Do not claim a latency or accuracy improvement: this release changes presentation routing only.

- [ ] **Step 5: Confirm release worktree scope**

Run:

```powershell
git status --short
```

Expected: only the known untracked user junction `models/rfdetr_large_bakery_v1/`, any ignored/generated 1.0.2 payloads, and no accidental tracked-source changes. Do not stage `models/rfdetr_large_bakery_v1/`, `apps/bakery_camera_flutter/test/ui/failures/`, model binaries, or generated payloads unless the existing release process explicitly tracks them.

## Plan Self-Review

- **Spec coverage:** Tasks 1-2 create deterministic Normal/Unknown/retake routing without changing inference; Task 3 packages it; Task 4 enforces a strict Flutter contract; Task 5 implements copy, candidate behavior, total suppression, diagnostics, and overlays; Task 6 verifies the Windows release.
- **No unsupported claim:** No task introduces a segmentation model or tells users a product is new/unregistered.
- **Type consistency:** `PresentationDecision.to_payload()` is emitted by Python, parsed as `InferencePresentation`, mapped by `CameraPresentationState`, and consumed by `EvaluationPanelData` and widgets.
- **Scope:** No detector, classifier, calibration, or legacy-pipeline behavior changes are planned.
