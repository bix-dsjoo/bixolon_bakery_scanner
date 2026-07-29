# Unified Bakery Inference Evaluator UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 초보 평가자도 한 화면에서 박스·최종 품목·`알 수 없음` Top-3·판정 경로·단계별 속도를 빠짐없이 검토할 수 있도록 결과 패널과 주변 UI를 일관된 평가 워크스테이션으로 재구성한다.

**Architecture:** 추론 결과를 변경하지 않는 immutable presentation adapter가 화면 표시 순서, 표시 번호, 한글 판정 경로, 점수 표현을 만든다. 결과 패널은 요약, 단일 대상 목록, 선택된 `알 수 없음`의 Top-3, 보조 상세 정보로 분리하고, 같은 표시 번호를 카메라 오버레이와 양방향 선택에 사용한다. 카메라 영역, 상단 상태, 빈 화면, 진행 상태, 오류, 하단 행동은 동일한 토큰과 문장 체계로 정리한다.

**Tech Stack:** Flutter 3.44.7, Dart 3.12, Material, `camera_windows`, Flutter widget/unit tests, Windows Release build.

## Global Constraints

- 주 사용자는 이 앱을 처음 사용하는 모델 평가자이며, 화면의 단일 작업은 추론 결과와 Top-3 및 속도 검토다.
- Detector, 박스 좌표, 분류 결과, 점수, 판정 정책, 추론 단계, worker JSON 계약은 변경하지 않는다.
- `Unknown`의 사용자 표시명은 모든 기본 UI에서 `알 수 없음`으로 고정한다.
- 요약에는 `대상`, `확정`, `알 수 없음`, `화면 표시까지`, `모델 추론`, `GPU/CPU`를 서로 구분해 표시한다.
- 모든 대상은 기본 목록에 정확히 한 번만 나타난다. `알 수 없음`을 먼저, 그 안에서는 Top-1 후보 점수가 낮은 순으로 정렬한다.
- 선택된 `알 수 없음` 한 건만 Top-3를 펼치며 후보는 수정 버튼처럼 보이지 않는 읽기 전용 표다.
- 품목별 수량은 확정 품목만 집계하며 `알 수 없음`을 품목으로 집계하지 않는다.
- 오버레이는 얇은 박스와 표시 번호를 기본으로 하고 선택된 박스만 이름과 두꺼운 외곽선을 표시한다.
- 디자인 토큰은 BIXOLON Orange `#EE7203`, canvas `#F7F7F5`, ink `#171717`, divider `#D9D9D6`, confirmed teal `#0E8A72`, unknown amber `#C76B00`, error red `#C43A3A`, focus blue `#176BFF`를 사용한다.
- Pretendard를 디지털 UI의 우선 글꼴로 사용하고, 수치에는 tabular figures와 오른쪽 정렬을 사용한다.
- 장식용 주황 띠, 대각선 X, 그라데이션, 과도한 카드 중첩, 큰 채움형 오버레이 라벨은 추가하지 않는다.
- 결과 콘텐츠에는 스크롤 영역을 하나만 두고 `분석하기`/`다시 촬영` 버튼은 고정한다.
- 1280×820과 1024×720에서 overflow 없이 카메라와 결과 패널을 동시에 표시한다.
- 고유한 시각적 서명은 장식이 아니라 이미지 박스와 결과 행을 잇는 동일한 표시 번호다.
- 기존 카메라, worker, GPU→CPU fallback, 모델 warm-up, 결과 계약 테스트를 모두 유지한다.

---

## File Structure

```text
apps/bakery_camera_flutter/lib/src/ui/
  evaluation_view_data.dart       immutable 화면 표시 모델과 정렬/라벨 변환
  evaluation_summary.dart         대상/확정/알 수 없음/두 지연시간/device
  evaluation_object_list.dart     대상 단일 목록과 선택 상태
  candidate_evidence_table.dart   선택된 알 수 없음의 읽기 전용 Top-3
  result_disclosures.dart         수량/단계별 시간/모델 정보
  result_rail.dart                결과 상태와 위 컴포넌트 조립
  scanner_screen.dart             전체 64/36 작업 공간과 양방향 선택
  status_strip.dart               준비/진행/실패의 짧은 상태 표현
  app_theme.dart                  공통 타입, 버튼, divider, focus 토큰
  bixolon_brand.dart              기존 브랜드 토큰과 작은 primitive

apps/bakery_camera_flutter/lib/src/scanner/
  result_overlay.dart             번호 박스 painter와 hit testing
  scanner_controller.dart         초기 선택과 선택 ID 보존

apps/bakery_camera_flutter/test/support/
  inference_fixtures.dart         여러 UI 테스트가 공유하는 실제 계약 fixture

apps/bakery_camera_flutter/test/ui/
  evaluation_view_data_test.dart
  result_rail_test.dart
  scanner_screen_test.dart
  bixolon_brand_test.dart

apps/bakery_camera_flutter/test/scanner/
  result_overlay_test.dart
  scanner_controller_test.dart
```

### Task 1: Immutable evaluation presentation model

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/evaluation_view_data.dart`
- Create: `apps/bakery_camera_flutter/test/support/inference_fixtures.dart`
- Create: `apps/bakery_camera_flutter/test/ui/evaluation_view_data_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`

**Interfaces:**
- Consumes: `ScannerState`, `InferenceResult`, `InferenceObject`, `StageTimings`, `StartupMetrics`.
- Produces: `EvaluationPanelData.fromState(ScannerState)`, `EvaluationObjectRow`, `EvaluationStageTiming`, `decisionPathLabel(String)`.
- `EvaluationObjectRow.object` always points to the untouched worker object; `displayNumber` is its one-based canonical position in `InferenceResult.objects`.

- [ ] **Step 1: Extract one shared inference fixture without changing its JSON contract**

Move the existing valid result JSON builder from `scanner_screen_test.dart` into:

```dart
InferenceResult buildInferenceResult({
  List<Map<String, Object?>>? objects,
  Map<String, Object?>? timings,
}) {
  return InferenceResult.fromJson({
    'type': 'result',
    'request_id': 'analyze-1',
    'image': {'width': 1280.0, 'height': 720.0},
    'device': 'cuda:0',
    'objects': objects ?? validEvaluationObjects,
    'counts': {'101': 1},
    'unknown_count': 2,
    'timings_ms': timings ?? {
      'decode_preprocess': 12.0,
      'detector': 240.0,
      'repvit': 80.0,
      'dinov3': 60.0,
      'postprocess': 20.0,
      'total': 412.0,
    },
  });
}
```

Update current UI tests to import the helper. Keep `InferenceResult.fromJson` as the only fixture construction path so schema validation remains exercised.

- [ ] **Step 2: Write failing adapter tests**

Cover these assertions:

```dart
test('orders unknown low-score first and preserves canonical numbers', () {
  final data = EvaluationPanelData.fromState(stateWithEvaluationResult());
  expect(data.rows.map((row) => row.object.isUnknown), [true, true, false]);
  expect(data.rows.map((row) => row.displayNumber), [3, 2, 1]);
  expect(data.rows.first.decisionScore, 0.21);
  expect(data.confirmedCount + data.unknownCount, data.totalCount);
});

test('maps decision paths and stage labels to evaluator copy', () {
  expect(decisionPathLabel('repvit_direct'), 'RepViT 직접 확정');
  expect(decisionPathLabel('dinov3_confirmed'), 'DINOv3 재확인');
  expect(decisionPathLabel('fusion_ranked'), 'Fusion 확정');
  expect(decisionPathLabel('unknown_top3'), '알 수 없음');
  expect(EvaluationStageTiming.dinov3(0).displayValue, '실행 안 함');
});
```

Also assert that confirmed rows use `InferenceObject.confidence`, unresolved rows use `candidates.first.score`, and `quantityRows` excludes every unresolved object.

- [ ] **Step 3: Run the focused test and verify RED**

Run:

```powershell
$env:Path='C:\workspace\tools\flutter-3.44.7\bin;'+$env:Path
flutter test test\ui\evaluation_view_data_test.dart
```

Expected: FAIL because `EvaluationPanelData` and related types do not exist.

- [ ] **Step 4: Implement the presentation adapter**

Use immutable records with explicit display semantics:

```dart
final class EvaluationObjectRow {
  const EvaluationObjectRow({
    required this.displayNumber,
    required this.object,
    required this.decisionLabel,
    required this.decisionScore,
  });

  final int displayNumber;
  final InferenceObject object;
  final String decisionLabel;
  final double decisionScore;
}

String decisionPathLabel(String path) => switch (path) {
  'repvit_direct' => 'RepViT 직접 확정',
  'dinov3_confirmed' => 'DINOv3 재확인',
  'fusion_ranked' => 'Fusion 확정',
  'unknown_top3' => '알 수 없음',
  _ => throw ArgumentError.value(path, 'path', '지원하지 않는 판정 경로'),
};
```

Build canonical rows first, then sort a copied list with:

```dart
rows.sort((a, b) {
  if (a.object.isUnknown != b.object.isUnknown) {
    return a.object.isUnknown ? -1 : 1;
  }
  if (a.object.isUnknown) {
    final scoreOrder = a.decisionScore.compareTo(b.decisionScore);
    if (scoreOrder != 0) return scoreOrder;
  }
  return a.displayNumber.compareTo(b.displayNumber);
});
```

Expose five stage rows with plain-language labels and keep `captureMs` separate:
`촬영`, `이미지 준비`, `빵 위치 찾기 · Detector`, `1차 품목 분류 · RepViT`,
`재확인 · DINOv3`, `결과 정리`.

- [ ] **Step 5: Run adapter and existing schema tests**

Run:

```powershell
flutter test test\ui\evaluation_view_data_test.dart test\inference\inference_models_test.dart
```

Expected: PASS.

- [ ] **Step 6: Commit the adapter**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/evaluation_view_data.dart apps/bakery_camera_flutter/test/support/inference_fixtures.dart apps/bakery_camera_flutter/test/ui/evaluation_view_data_test.dart apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart
git commit -m "refactor: add inference evaluation view data"
```

### Task 2: Summary, single object list, and selected Top-3

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/evaluation_summary.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart`
- Create: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`

**Interfaces:**
- Consumes: `EvaluationPanelData`, `EvaluationObjectRow`, selected object ID.
- Produces: `EvaluationSummary`, `EvaluationObjectList`, `CandidateEvidenceTable`.
- Emits only `ValueChanged<String>` selection events; it cannot alter model output or candidate scores.

- [ ] **Step 1: Write failing widget tests for the visible hierarchy**

Use a 360 px-wide result pane and assert:

```dart
expect(find.text('대상 3'), findsOneWidget);
expect(find.text('확정 1'), findsOneWidget);
expect(find.text('알 수 없음 2'), findsOneWidget);
expect(find.text('화면 표시까지'), findsOneWidget);
expect(find.text('모델 추론'), findsOneWidget);
expect(find.byKey(const Key('evaluation-object-row')), findsNWidgets(3));
expect(find.text('품목별 수량'), findsNothing);
expect(tester.takeException(), isNull);
```

Tap the second unresolved row and verify that only it contains:

```dart
expect(find.text('AI가 이 빵의 품목을 알 수 없다고 판단했어요. '
    '가능성이 높은 품목 3개를 참고용으로 보여드려요.'), findsOneWidget);
expect(find.byKey(const Key('candidate-row')), findsNWidgets(3));
expect(find.text('순위'), findsOneWidget);
expect(find.text('예상 품목'), findsOneWidget);
expect(find.text('판정 점수'), findsOneWidget);
```

Verify candidate rows expose no `onTap`, button semantics, checkbox, radio, or correction copy.

- [ ] **Step 2: Run the result rail test and verify RED**

Run:

```powershell
flutter test test\ui\result_rail_test.dart
```

Expected: FAIL because the new components and hierarchy are absent.

- [ ] **Step 3: Implement the compact summary**

`EvaluationSummary` renders two lines:

```text
대상 9   확정 4   알 수 없음 5
화면 표시까지 726 ms   모델 추론 412 ms   GPU
```

Use semantic labels containing the full label/value pair, amber only on the unresolved count, and tabular figures. Never combine the two latency values into `726 ms · GPU`.

- [ ] **Step 4: Implement the single object list**

Each row contains:

```text
[03] 알 수 없음              21.0%
     알 수 없음
```

or:

```text
[01] Pastry Bread            48.4%
     Fusion 확정
```

Use `InkWell` with a 44 px minimum height, visible hover/focus/selected states, a 2 px orange selected keyline, teal/amber 6 px semantic dot, and no filled status badge. Add:

```dart
Semantics(
  selected: selected,
  button: true,
  label: '${row.displayNumber}번 ${row.object.isUnknown ? '알 수 없음' : row.object.skuName}, '
      '${row.decisionLabel}, 판정 점수 ${formatPercent(row.decisionScore)}',
  child: ...
)
```

- [ ] **Step 5: Implement the selected Top-3 evidence table**

Render exactly `object.candidates` ranks 1–3. Give numeric cells tabular figures and right alignment. Do not show `unknownReason` in the default flow; reserve it for model details because it is a machine reason code.

- [ ] **Step 6: Replace the existing duplicated result rail**

`ResultRail` becomes one `CustomScrollView` or one `SingleChildScrollView` containing:

1. evaluation summary;
2. one object list;
3. secondary disclosures added by Task 3.

Delete the default-visible product count list, repeated confirmed cards, every simultaneously expanded Top-3, `SCAN RESULT`, and the decorative horizontal heading rule.

- [ ] **Step 7: Run result panel tests**

Run:

```powershell
flutter test test\ui\result_rail_test.dart test\ui\scanner_screen_test.dart
```

Expected: PASS with no overflow exception.

- [ ] **Step 8: Commit the result hierarchy**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/evaluation_summary.dart apps/bakery_camera_flutter/lib/src/ui/evaluation_object_list.dart apps/bakery_camera_flutter/lib/src/ui/candidate_evidence_table.dart apps/bakery_camera_flutter/lib/src/ui/result_rail.dart apps/bakery_camera_flutter/test/ui/result_rail_test.dart
git commit -m "feat: redesign inference evaluation results"
```

### Task 3: Quantity, timing, and model disclosures

**Files:**
- Create: `apps/bakery_camera_flutter/lib/src/ui/result_disclosures.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/result_rail_test.dart`

**Interfaces:**
- Consumes: `EvaluationPanelData`, `StartupMetrics?`.
- Produces: `QuantityDisclosure`, `StageTimingDisclosure`, `ModelInfoDisclosure`.
- Disclosure widgets are collapsed initially and share one divider/typography treatment.

- [ ] **Step 1: Write failing disclosure tests**

Assert:

```dart
await tester.tap(find.text('품목별 수량'));
await tester.pumpAndSettle();
expect(find.text('Unknown'), findsNothing);
expect(find.text('알 수 없음'), findsWidgets); // summary/list only

await tester.tap(find.text('단계별 시간'));
await tester.pumpAndSettle();
expect(find.text('빵 위치 찾기 · Detector'), findsOneWidget);
expect(find.text('재확인 · DINOv3'), findsOneWidget);
expect(find.text('실행 안 함'), findsOneWidget);

await tester.tap(find.text('모델 정보'));
await tester.pumpAndSettle();
expect(find.textContaining('fusion_local_or_global_consensus_margin_v1'),
    findsOneWidget);
expect(find.text('판정 점수는 모델이 품목을 선택한 상대 점수이며 '
    '실제 정확도를 의미하지 않습니다.'), findsOneWidget);
```

- [ ] **Step 2: Run disclosure tests and verify RED**

Run:

```powershell
flutter test test\ui\result_rail_test.dart --plain-name "secondary disclosures"
```

Expected: FAIL because the disclosure widgets are absent.

- [ ] **Step 3: Implement restrained disclosures**

Use a flat `ExpansionTile`-equivalent with 48 px header, one-pixel top divider, no card background, no outer radius, and a rotating chevron only. Quantity rows are `품목 / 수량`; timing rows are `단계 / 시간`; model rows are `항목 / 값`.

Show:

- Detector, RepViT, DINOv3 and fusion policy IDs;
- detector threshold;
- model load and warm-up times;
- GPU fallback reason only when non-null;
- unknown reason code only for the selected unresolved object under `기술 사유`.

- [ ] **Step 4: Verify disclosures and list invariants**

Run:

```powershell
flutter test test\ui\result_rail_test.dart test\ui\evaluation_view_data_test.dart
```

Expected: PASS; every object remains present once in the default list.

- [ ] **Step 5: Commit the technical details**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/result_disclosures.dart apps/bakery_camera_flutter/lib/src/ui/result_rail.dart apps/bakery_camera_flutter/test/ui/result_rail_test.dart
git commit -m "feat: add evaluator result disclosures"
```

### Task 4: Numbered overlay and bidirectional selection

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart`
- Modify: `apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart`
- Modify: `apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`

**Interfaces:**
- `ResultOverlayItem` adds `int displayNumber` and `String displayName`.
- `ResultOverlayHitTester.hitTest(Offset viewportPoint)` returns the topmost/smallest matching object ID or `null`.
- `ScannerController.selectObject(String?)` remains the single selection mutation API.

- [ ] **Step 1: Write failing painter and hit-test tests**

Test letterboxing, resize, overlapping boxes, and selection:

```dart
expect(hitTester.hitTest(selectedBoxCenter), 'object-2');
expect(hitTester.hitTest(const Offset(1, 1)), isNull);
expect(painter.selectedLabelFor('object-2'), '02  알 수 없음');
```

For overlap, choose the selected box first; otherwise choose the containing box with the smallest transformed area, then canonical display number.

- [ ] **Step 2: Run overlay tests and verify RED**

Run:

```powershell
flutter test test\scanner\result_overlay_test.dart
```

Expected: FAIL because display numbers and hit testing do not exist.

- [ ] **Step 3: Implement the restrained painter**

Draw every box with 1.5 px teal/amber stroke and a compact number chip placed inside the top-left corner. Draw the selected box with 3 px stroke and one label:

```text
03  알 수 없음
01  Pastry Bread
```

The chip may use a small opaque background for legibility; the full label appears only for selection and must be clamped into the displayed image rectangle.

- [ ] **Step 4: Add pointer and keyboard selection**

Wrap the captured-image stack with a `GestureDetector`. Convert tap position with the same `ContainedImageTransform`, call `ResultOverlayHitTester`, then `controller.selectObject(id)`. When a result first arrives, `ScannerController` selects the first unresolved row in presentation order, otherwise canonical object 1. Keep list and overlay selection synchronized by object ID.

- [ ] **Step 5: Run overlay/controller/screen tests**

Run:

```powershell
flutter test test\scanner\result_overlay_test.dart test\scanner\scanner_controller_test.dart test\ui\scanner_screen_test.dart
```

Expected: PASS for tap-to-list and list-to-overlay selection.

- [ ] **Step 6: Commit the numbered evidence loop**

```powershell
git add apps/bakery_camera_flutter/lib/src/scanner/result_overlay.dart apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart apps/bakery_camera_flutter/test/scanner/result_overlay_test.dart apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart
git commit -m "feat: link overlay boxes to evaluation rows"
```

### Task 5: Make the surrounding workflow visually and verbally consistent

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/bixolon_brand.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart`
- Modify: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`
- Modify: `apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart`

**Interfaces:**
- `ScannerState.phaseLabel` supplies plain Korean progress copy.
- `StatusStrip` supplies camera/model readiness and one actionable failure.
- `ScannerScreen` maintains one fixed action and a result pane minimum width of 360 px.

- [ ] **Step 1: Write failing copy and layout tests**

Verify exact phase copy:

```dart
expect(stateFor(ScannerPhase.detecting).phaseLabel, '빵을 찾고 있어요.');
expect(stateFor(ScannerPhase.classifying).phaseLabel, '빵 종류를 확인하고 있어요.');
expect(stateFor(ScannerPhase.rechecking).phaseLabel,
    '분류 결과를 다시 확인하고 있어요.');
expect(stateFor(ScannerPhase.aggregating).phaseLabel, '결과를 정리하고 있어요.');
```

Pump the screen at `1280×820` and `1024×720`; assert one primary action, one result scrollable, no overflow, and result pane width at least 360 px.

- [ ] **Step 2: Run copy/layout tests and verify RED**

Run:

```powershell
flutter test test\scanner\scanner_controller_test.dart test\ui\scanner_screen_test.dart
```

Expected: FAIL on old labels and old 70/30 allocation.

- [ ] **Step 3: Normalize typography and controls**

Set the theme to a quiet Windows evaluation surface:

- 20 px/700 screen title;
- 14 px/600 section title;
- 13 px/400 body;
- 12 px/500 metadata;
- 6 px control radius;
- 1 px neutral borders;
- 44 px minimum rows and 52 px primary action;
- blue 3 px keyboard focus ring;
- motion limited to 120–160 ms selection/focus transitions and disabled under reduced-motion settings.

Use orange only for the primary action and selected keyline. Keep camera black, results white, surrounding canvas `#F7F7F5`.

- [ ] **Step 4: Recompose the application shell**

Use approximately 64/36 allocation at 1280 px. Replace duplicated camera readiness text with one top status strip and one camera stage label. Keep the image area visually dominant. Replace idle and failure copy with:

```text
트레이를 카메라 아래에 놓고 분석하기를 눌러주세요.
빵을 찾지 못했어요. 트레이 위치를 확인하고 다시 촬영해 주세요.
카메라를 찾지 못했어요. 연결을 확인한 뒤 다시 연결해 주세요.
모델을 준비하지 못했어요. 앱을 다시 시작해 주세요.
```

Raw worker diagnostics stay inside `모델 정보`; the primary screen never shows a stack trace or machine-only error first.

- [ ] **Step 5: Verify keyboard and semantics**

Tab order must be object rows → disclosures → fixed action. Space/Enter selects rows and toggles disclosures. Screen-reader labels must distinguish `화면 표시까지` from `모델 추론` and read Top-3 rank/name/score in that order.

Run:

```powershell
flutter test test\ui\bixolon_brand_test.dart test\ui\scanner_screen_test.dart
```

Expected: PASS.

- [ ] **Step 6: Commit the unified shell**

```powershell
git add apps/bakery_camera_flutter/lib/src/ui/app_theme.dart apps/bakery_camera_flutter/lib/src/ui/bixolon_brand.dart apps/bakery_camera_flutter/lib/src/ui/status_strip.dart apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart apps/bakery_camera_flutter/lib/src/scanner/scanner_controller.dart apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart apps/bakery_camera_flutter/test/scanner/scanner_controller_test.dart
git commit -m "feat: unify evaluator workflow UI"
```

### Task 6: Full regression, visual QA, and release build

**Files:**
- Modify: `apps/bakery_camera_flutter/README.md`
- Create: `artifacts/ui_review/bakery_evaluator_1280x820.png`
- Create: `artifacts/ui_review/bakery_evaluator_1024x720.png`

**Interfaces:**
- Consumes: the completed evaluator UI.
- Produces: verified screenshots, full test evidence, analyzer evidence, and a Windows Release build used by the installer plan.

- [ ] **Step 1: Run all Flutter tests**

Run:

```powershell
$env:Path='C:\workspace\tools\flutter-3.44.7\bin;'+$env:Path
Set-Location apps\bakery_camera_flutter
flutter test
```

Expected: all tests pass; the current baseline of 71 tests may increase but none may be removed solely to make the redesign pass.

- [ ] **Step 2: Run static analysis**

Run:

```powershell
flutter analyze
```

Expected: `No issues found!`

- [ ] **Step 3: Build Windows Release**

Run:

```powershell
flutter build windows --release
```

Expected: `build\windows\x64\runner\Release\bakery_camera_prototype.exe` plus required DLL/data output.

- [ ] **Step 4: Perform real camera visual QA**

Launch with the validated Python 3.11 runtime, capture the same tray twice, and verify:

1. second analysis does not reload models;
2. overlay and row selection work in both directions;
3. every unresolved object exposes exactly three candidates;
4. worker total remains unchanged by the UI redesign within normal measurement noise;
5. no label hides a neighboring bread;
6. both target window sizes retain one result scrollbar and fixed action.

Capture the two screenshots under `artifacts/ui_review/`. Inspect them at original resolution before accepting.

- [ ] **Step 5: Update the evaluator README**

Document the evaluator-first information hierarchy, `알 수 없음` interpretation, selection behavior, two latency definitions, stage timings, and the statement that a model score is not measured accuracy. Remove the previous decorative orange-band/X description.

- [ ] **Step 6: Re-run release verification**

Run:

```powershell
flutter test
flutter analyze
flutter build windows --release
```

Expected: tests pass, analyzer is clean, Release build succeeds.

- [ ] **Step 7: Commit the verified UI**

```powershell
git add apps/bakery_camera_flutter/README.md artifacts/ui_review/bakery_evaluator_1280x820.png artifacts/ui_review/bakery_evaluator_1024x720.png
git commit -m "docs: verify evaluator UI redesign"
```

## Self-Review

- Spec coverage: Tasks 1–3 implement summary, one object list, selected Top-3, quantities, timings, model details, and exact copy. Task 4 implements the numbered overlay/list loop. Task 5 aligns the rest of the workflow. Task 6 covers responsive, visual, behavioral, release, and documentation verification.
- Pipeline boundary: every transformation is presentation-only; no detector, box, classifier, fusion, score, timing, or result schema is modified.
- Type consistency: `EvaluationPanelData` and `EvaluationObjectRow` are created in Task 1 and consumed unchanged in Tasks 2–3; `displayNumber` is added to `ResultOverlayItem` in Task 4 and remains derived from canonical result order.
- Duplication check: confirmed objects appear once in the default list; quantities and model evidence are collapsed secondary disclosures; only one unresolved Top-3 expands.
- Accessibility check: minimum hit sizes, keyboard selection, visible focus, semantic labels, reduced motion, and two supported window sizes are explicit tasks.
