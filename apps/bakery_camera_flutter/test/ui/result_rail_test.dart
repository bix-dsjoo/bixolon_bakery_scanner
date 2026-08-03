import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/bixolon_brand.dart';
import 'package:bakery_camera_prototype/src/ui/evaluation_summary.dart';
import 'package:bakery_camera_prototype/src/ui/result_rail.dart';
import 'package:bakery_camera_prototype/src/ui/result_disclosures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  testWidgets(
    'result summary separates counts, latencies, and compute device',
    (tester) async {
      await _pumpRail(tester, selectedObjectId: 'object-3');

      expect(find.text('대상 3'), findsOneWidget);
      expect(find.text('확정 1'), findsOneWidget);
      expect(find.text('알 수 없음 2'), findsOneWidget);
      expect(find.text('화면 표시까지'), findsOneWidget);
      expect(find.text('420 ms'), findsOneWidget);
      expect(find.text('모델 추론'), findsOneWidget);
      expect(find.text('352 ms'), findsOneWidget);
      expect(find.text('CPU'), findsOneWidget);
      expect(find.text('SCAN RESULT'), findsNothing);
    },
  );

  testWidgets(
    'each object appears once and only selected unresolved shows top3',
    (tester) async {
      await _pumpRail(tester, selectedObjectId: 'object-3');

      expect(find.byKey(const Key('evaluation-object-row')), findsNWidgets(3));
      expect(find.byKey(const Key('candidate-row')), findsNWidgets(3));
      expect(
        find.text(
          'AI가 이 빵의 제품을 알 수 없다고 판단했어요. '
          '가능성이 높은 제품 3개를 참고용으로 보여드려요.',
        ),
        findsOneWidget,
      );
      expect(find.text('순위'), findsOneWidget);
      expect(find.text('예상 제품'), findsOneWidget);
      expect(find.text('판정 점수'), findsOneWidget);
      expect(find.byType(Checkbox), findsNothing);
      expect(find.byType(Radio<int>), findsNothing);
      expect(find.text('품목별 수량'), findsOneWidget);
    },
  );

  testWidgets('object row selection emits canonical object identity', (
    tester,
  ) async {
    String? selected;
    await _pumpRail(
      tester,
      selectedObjectId: 'object-3',
      onSelectObject: (value) => selected = value,
    );

    await tester.tap(find.byKey(const Key('evaluation-object-row-object-2')));
    await tester.pump();

    expect(selected, 'object-2');
  });

  testWidgets('selected row uses neutral selection without replacing status', (
    tester,
  ) async {
    await _pumpRail(tester, selectedObjectId: 'object-3');

    final rowSurface = tester.widget<Container>(
      find.byKey(const Key('object-row-surface-object-3')),
    );
    final rowDecoration = rowSurface.decoration! as BoxDecoration;
    expect(rowDecoration.color, bixolonCanvas);
    expect(rowDecoration.border!.top.color, bixolonInk);
    expect(rowDecoration.border!.top.width, 1);

    final statusDot = tester.widget<Container>(
      find.byKey(const Key('object-semantic-dot-object-3')),
    );
    final statusDecoration = statusDot.decoration! as BoxDecoration;
    expect(statusDecoration.color, unknownAmber);
  });

  testWidgets('secondary disclosures separate quantities timing and evidence', (
    tester,
  ) async {
    await _pumpRail(tester, selectedObjectId: 'object-3');

    await tester.ensureVisible(find.text('품목별 수량'));
    await tester.tap(find.text('품목별 수량'));
    await tester.pumpAndSettle();
    expect(find.text('Pastry Bread'), findsWidgets);
    expect(find.text('Unknown'), findsNothing);

    await tester.ensureVisible(find.text('단계별 시간'));
    await tester.tap(find.text('단계별 시간'));
    await tester.pumpAndSettle();
    expect(find.text('빵 위치 찾기 · Detector'), findsOneWidget);
    expect(find.text('1차 품목 분류 · RepViT'), findsOneWidget);
    expect(find.text('재확인 · DINOv3'), findsOneWidget);
    expect(find.text('실행 안 함'), findsOneWidget);

    await tester.ensureVisible(find.text('모델 정보'));
    await tester.tap(find.text('모델 정보'));
    await tester.pumpAndSettle();
    expect(
      find.text('fusion_local_or_global_consensus_margin_v1'),
      findsOneWidget,
    );
    expect(find.text('CPU로 전환'), findsOneWidget);
    expect(find.text('consensus_failed'), findsOneWidget);
    expect(
      find.text(
        '판정 점수는 모델이 품목을 선택한 상대 점수이며 '
        '실제 정확도를 의미하지 않습니다.',
      ),
      findsOneWidget,
    );
  });

  testWidgets(
    'empty retake result keeps diagnostics free of fake object rows',
    (tester) async {
      final result = InferenceResult.fromJson({
        'type': 'result',
        'request_id': 'empty',
        'image': {'width': 1280, 'height': 720},
        'device': 'cpu',
        'objects': <Object?>[],
        'counts': <String, Object?>{},
        'unknown_count': 0,
        'presentation': {
          'state': 'needs_retake',
          'final_count_usable': false,
          'retake_scope': 'scan',
          'retake_object_ids': <Object?>[],
          'instruction_code': 'no_bread_detected',
          'candidate_object_ids': <Object?>[],
          'policy_id': 'camera_action_state_v1',
          'policy_sha256': '1' * 64,
        },
        'timings_ms': {
          'decode_preprocess': 1.0,
          'detector': 2.0,
          'crop': 0.0,
          'repvit': 0.0,
          'dinov3': 0.0,
          'fusion': 0.0,
          'postprocess': 1.0,
          'total': 4.0,
        },
        'diagnostics': {'object_count': 0, 'dino_object_count': 0},
      });
      await _pumpRail(tester, result: result);

      expect(find.text('이 사진만으로 판단하기 어려워요'), findsOneWidget);
      expect(find.text('분석 참고'), findsOneWidget);
      await tester.tap(find.text('분석 참고'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('evaluation-object-row')), findsNothing);
    },
  );

  testWidgets(
    'scan retake leads with instruction and hides final count until diagnostics',
    (tester) async {
      await _pumpRail(tester, result: _scanRetakeResult());

      expect(find.text('이 사진만으로 판단하기 어려워요'), findsOneWidget);
      expect(find.text('빵을 찾지 못했어요. 빵이 모두 보이도록 다시 촬영해 주세요'), findsOneWidget);
      expect(find.textContaining('총 '), findsNothing);
      expect(find.byType(EvaluationSummary), findsNothing);
      expect(find.byType(QuantityDisclosure), findsNothing);
      expect(find.text('분석 참고'), findsOneWidget);
      expect(find.byType(StageTimingDisclosure), findsNothing);

      await tester.tap(find.text('분석 참고'));
      await tester.pumpAndSettle();

      expect(find.byType(StageTimingDisclosure), findsOneWidget);
      expect(find.byType(QuantityDisclosure), findsNothing);
    },
  );

  testWidgets(
    'object retake row shows retake status and never recommends candidates',
    (tester) async {
      await _pumpRail(
        tester,
        result: _objectRetakeResult(),
        selectedObjectId: 'object-2',
      );

      await tester.tap(find.text('분석 참고'));
      await tester.pumpAndSettle();

      expect(find.text('다시 촬영 필요'), findsOneWidget);
      expect(find.byKey(const Key('candidate-row')), findsNothing);
      expect(find.text('가능성이 높은 제품 3개'), findsNothing);
    },
  );

  testWidgets('normal presentation retains final summary and quantity flow', (
    tester,
  ) async {
    await _pumpRail(tester, result: _normalResult());

    expect(find.byType(EvaluationSummary), findsOneWidget);
    expect(find.byType(QuantityDisclosure), findsOneWidget);
    expect(find.text('확정 1'), findsOneWidget);
    expect(find.text('분석 참고'), findsNothing);
  });

  testWidgets('only worker-authorized Unknown shows exactly three candidates', (
    tester,
  ) async {
    await _pumpRail(tester, selectedObjectId: 'object-2');

    expect(find.byKey(const Key('candidate-row')), findsNWidgets(3));
    expect(find.text('가능성이 높은 제품 3개'), findsOneWidget);
  });

  testWidgets('result rail visual regression at the minimum supported width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpRail(tester, selectedObjectId: 'object-3');

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/result_rail_360x720.png'),
    );
  });
}

InferenceResult _scanRetakeResult() => InferenceResult.fromJson({
  'type': 'result',
  'request_id': 'scan-retake',
  'image': {'width': 1280, 'height': 720},
  'device': 'cpu',
  'objects': <Object?>[],
  'counts': <String, Object?>{},
  'unknown_count': 0,
  'presentation': buildPresentationJson(
    state: 'needs_retake',
    finalCountUsable: false,
    retakeScope: 'scan',
    instructionCode: 'no_bread_detected',
  ),
  'timings_ms': {
    'decode_preprocess': 1.0,
    'detector': 2.0,
    'crop': 0.0,
    'repvit': 0.0,
    'dinov3': 0.0,
    'fusion': 0.0,
    'postprocess': 1.0,
    'total': 4.0,
  },
  'diagnostics': {'object_count': 0, 'dino_object_count': 0},
});

InferenceResult _objectRetakeResult() => buildUiInferenceResult(
  presentation: buildPresentationJson(
    state: 'needs_retake',
    finalCountUsable: false,
    retakeScope: 'object',
    retakeObjectIds: const ['object-2'],
    instructionCode: 'candidate_evidence_weak',
  ),
);

InferenceResult _normalResult() => InferenceResult.fromJson({
  'type': 'result',
  'request_id': 'normal-result',
  'image': {'width': 1280, 'height': 720},
  'device': 'cpu',
  'objects': [
    buildInferenceObjectJson(
      id: 'object-1',
      skuId: 1,
      name: 'Pastry Bread',
      confidence: 0.91,
      decisionPath: 'repvit_direct',
      box: [10.0, 20.0, 210.0, 220.0],
    ),
  ],
  'counts': {'1': 1},
  'unknown_count': 0,
  'presentation': buildPresentationJson(),
  'timings_ms': {
    'decode_preprocess': 12.0,
    'detector': 240.0,
    'crop': 0.0,
    'repvit': 80.0,
    'dinov3': 0.0,
    'fusion': 0.0,
    'postprocess': 20.0,
    'total': 352.0,
  },
  'diagnostics': {'object_count': 1, 'dino_object_count': 0},
});

Future<void> _pumpRail(
  WidgetTester tester, {
  String? selectedObjectId,
  InferenceResult? result,
  ValueChanged<String?>? onSelectObject,
}) async {
  final inferenceResult = result ?? buildOrderingInferenceResult();
  final state = ScannerState.initial().copyWith(
    cameraReady: true,
    workerStatus: WorkerStatus.ready,
    startupMetrics: StartupMetrics(
      device: 'cpu',
      loadMs: 1500,
      warmupMs: 320,
      fallbackReason: 'cuda_unavailable',
      detectorId: 'rfdetr_large_bakery_v1',
      repvitId: 'repvit_m1_15plus5_v1',
      dinov3Id: 'dinov3_vits16_15plus5_v1',
      fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
      detectorThreshold: 0.5691395401954651,
    ),
    device: inferenceResult.device,
    result: inferenceResult,
    captureMs: 18.0,
    pressToRenderedResultMs: 420.0,
    selectedObjectId: selectedObjectId,
    phase: ScannerPhase.result,
  );
  await tester.pumpWidget(
    MaterialApp(
      theme: buildBakeryTheme(),
      home: Scaffold(
        body: Align(
          alignment: Alignment.topLeft,
          child: SizedBox(
            width: 360,
            height: 720,
            child: ResultRail(
              state: state,
              elapsedMs: 420,
              onSelectObject: onSelectObject ?? (_) {},
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
}
