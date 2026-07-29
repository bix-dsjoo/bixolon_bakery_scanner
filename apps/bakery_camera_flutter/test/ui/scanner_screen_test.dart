import 'dart:async';

import 'package:bakery_camera_prototype/src/camera/camera_service.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/result_overlay.dart'
    hide confirmedTeal, unknownAmber;
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/bixolon_brand.dart';
import 'package:bakery_camera_prototype/src/ui/scanner_screen.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'compact divider header and flat 70/30 panes identify the scan console',
    (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await _pumpScreen(tester, fixture.controller);

      final header = tester.widget<DecoratedBox>(
        find.byKey(const Key('bixolon-header')),
      );
      final headerDecoration = header.decoration as BoxDecoration;
      expect(headerDecoration.color, Colors.white);
      expect(
        headerDecoration.border,
        const Border(
          bottom: BorderSide(
            color: bixolonDivider,
            width: bixolonControlBorderWidth,
          ),
        ),
      );
      expect(
        tester.getSize(find.byKey(const Key('bixolon-header'))).height,
        60,
      );
      expect(find.byType(BixolonWordmark), findsOneWidget);
      expect(find.text('Bakery AI Scanner'), findsOneWidget);

      final cameraPane = find.byKey(const Key('camera-pane'));
      final resultPane = find.byKey(const Key('result-pane'));
      final paneRatio =
          tester.getSize(cameraPane).width / tester.getSize(resultPane).width;
      expect(paneRatio, closeTo(7 / 3, 0.15));

      expect(find.byType(BixolonBrandDecoration), findsNothing);

      final cameraSurface = tester.widget<DecoratedBox>(
        find.byKey(const Key('camera-surface')),
      );
      final cameraDecoration = cameraSurface.decoration as BoxDecoration;
      expect(
        cameraDecoration.border,
        Border.all(color: bixolonDivider, width: bixolonControlBorderWidth),
      );
      expect(cameraDecoration.borderRadius, BorderRadius.circular(6));

      final resultSurface = tester.widget<DecoratedBox>(
        find.byKey(const Key('result-surface')),
      );
      final resultDecoration = resultSurface.decoration as BoxDecoration;
      expect(resultDecoration.color, Colors.white);
      expect(
        resultDecoration.border,
        Border.all(color: bixolonDivider, width: bixolonControlBorderWidth),
      );
      expect(resultDecoration.borderRadius, BorderRadius.circular(6));
    },
  );

  testWidgets('camera and result panes contain no Orange bands or panels', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    await _pumpScreen(tester, fixture.controller);

    expect(find.byKey(const Key('camera-readiness-band')), findsNothing);

    final rail = tester.widget<DecoratedBox>(
      find.byKey(const Key('result-rail-surface')),
    );
    final railDecoration = rail.decoration as BoxDecoration;
    expect(railDecoration.color, Colors.white);
    expect(railDecoration.border, isNull);
  });

  testWidgets(
    'analysis is Orange while recapture is the sole black outlined action',
    (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);
      await _pumpScreen(tester, fixture.controller);

      final analyze = tester.widget<FilledButton>(
        find.byKey(const Key('primary-action')),
      );
      expect(
        analyze.style!.backgroundColor!.resolve(<WidgetState>{}),
        bixolonOrange,
      );
      expect(find.byType(FilledButton), findsOneWidget);
      expect(find.byType(OutlinedButton), findsNothing);

      await tester.tap(find.text('분석하기'));
      await tester.pump();

      final inFlightRecapture = tester.widget<OutlinedButton>(
        find.byKey(const Key('primary-action')),
      );
      expect(inFlightRecapture.onPressed, isNull);
      expect(
        inFlightRecapture.style!.foregroundColor!.resolve({
          WidgetState.disabled,
        }),
        bixolonMutedInk,
      );
      expect(
        inFlightRecapture.style!.backgroundColor!.resolve({
          WidgetState.disabled,
        }),
        bixolonCanvas,
      );
      expect(
        inFlightRecapture.style!.side!.resolve({WidgetState.disabled})!.color,
        bixolonDivider,
      );

      fixture.worker.complete(_result());
      await tester.pumpAndSettle();

      final recapture = tester.widget<OutlinedButton>(
        find.byKey(const Key('primary-action')),
      );
      expect(
        recapture.style!.foregroundColor!.resolve(<WidgetState>{}),
        cameraInk,
      );
      expect(recapture.style!.side!.resolve(<WidgetState>{})!.color, cameraInk);
      expect(find.byType(FilledButton), findsNothing);
      expect(find.byType(OutlinedButton), findsOneWidget);
    },
  );

  testWidgets('confirmed and Unknown rows retain teal and amber semantics', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    await _pumpScreen(tester, fixture.controller);

    await tester.tap(find.text('분석하기'));
    await tester.pump();
    fixture.worker.complete(_result());
    await tester.pumpAndSettle();

    final confirmedSurface = tester.widget<Container>(
      find.byKey(const Key('object-row-surface-object-1')),
    );
    final unknownSurface = tester.widget<Container>(
      find.byKey(const Key('object-row-surface-object-2')),
    );
    final confirmedDecoration = confirmedSurface.decoration! as BoxDecoration;
    final unknownDecoration = unknownSurface.decoration! as BoxDecoration;
    final confirmedBorder = confirmedDecoration.border! as Border;
    final unknownBorder = unknownDecoration.border! as Border;

    expect(confirmedBorder.left.color, confirmedTeal);
    expect(unknownBorder.left.color, unknownAmber);
    expect(confirmedBorder.left.color, isNot(bixolonOrange));
    expect(unknownBorder.left.color, isNot(bixolonOrange));
  });

  testWidgets('analysis stays disabled until camera and model are ready', (
    tester,
  ) async {
    final fixture = ScannerFixture(cameraReady: false);
    addTearDown(fixture.close);

    await _pumpScreen(tester, fixture.controller);

    final action = tester.widget<FilledButton>(
      find.byKey(const Key('primary-action')),
    );
    expect(action.onPressed, isNull);
    expect(
      action.style!.backgroundColor!.resolve({WidgetState.disabled}),
      bixolonDivider,
    );
    expect(
      action.style!.foregroundColor!.resolve({WidgetState.disabled}),
      bixolonMutedInk,
    );
    expect(
      action.style!.side!.resolve({WidgetState.disabled})!.color,
      bixolonDivider,
    );
    expect(find.text('분석하기'), findsOneWidget);
    expect(find.text('카메라를 찾지 못했습니다'), findsOneWidget);
    expect(find.text('카메라 다시 연결'), findsOneWidget);
  });

  testWidgets(
    'camera initialization and reconnect are distinct from camera failure',
    (tester) async {
      final fixture = ScannerFixture(cameraReady: false);
      fixture.camera.initializeCompleter = Completer<bool>();
      addTearDown(fixture.close);

      await _mountScreen(tester, fixture.controller);
      await tester.pump();

      expect(find.text('카메라 연결 중'), findsOneWidget);
      expect(find.text('카메라를 연결하고 있습니다'), findsOneWidget);
      expect(find.text('카메라 다시 연결'), findsNothing);

      fixture.camera.initializeCompleter!.complete(false);
      await tester.pumpAndSettle();
      expect(find.text('카메라를 찾지 못했습니다'), findsOneWidget);
      expect(find.text('카메라 다시 연결'), findsOneWidget);

      fixture.camera.reconnectCompleter = Completer<bool>();
      await tester.tap(find.text('카메라 다시 연결'));
      await tester.pump();
      expect(find.text('카메라 연결 중'), findsOneWidget);
      expect(find.text('카메라 다시 연결'), findsNothing);

      fixture.camera.reconnectCompleter!.complete(true);
      await tester.pumpAndSettle();
      expect(find.text('카메라 연결됨'), findsOneWidget);
    },
  );

  testWidgets(
    'startup and analysis show factual Korean phase and elapsed time',
    (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);

      await _pumpScreen(tester, fixture.controller);
      await tester.tap(find.text('분석하기'));
      await tester.pump();

      expect(find.textContaining('이미지 촬영 중'), findsOneWidget);
      expect(find.textContaining('ms'), findsWidgets);

      fixture.worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.detecting,
        ),
      );
      await tester.pump();
      expect(find.textContaining('빵 위치 찾는 중'), findsOneWidget);

      fixture.worker.complete(_result());
      await tester.pumpAndSettle();
    },
  );

  testWidgets(
    'result rail presents evidence and links row selection to overlay',
    (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);
      await _pumpScreen(tester, fixture.controller);

      await tester.tap(find.text('분석하기'));
      await tester.pump();
      fixture.nowMs = 412;
      fixture.worker.complete(_result());
      await tester.pumpAndSettle();

      expect(find.text('총 2개 · 412 ms · GPU'), findsOneWidget);
      expect(find.text('Croissant'), findsWidgets);
      expect(find.text('92.0%'), findsOneWidget);
      expect(find.text('RepViT 직접 확정'), findsOneWidget);
      expect(find.text('Unknown'), findsWidgets);
      final unknownRow = find.byKey(const Key('object-row-object-2'));
      expect(
        find.descendant(of: unknownRow, matching: find.text('1')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: unknownRow, matching: find.text('2')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: unknownRow, matching: find.text('3')),
        findsOneWidget,
      );
      expect(find.text('Sugar Donut'), findsOneWidget);
      expect(find.text('88.0%'), findsOneWidget);
      expect(find.text('정확도'), findsNothing);

      expect(find.text('120 ms'), findsNothing);
      await tester.ensureVisible(find.text('모델 정보'));
      await tester.tap(find.text('모델 정보'));
      await tester.pumpAndSettle();
      expect(find.text('120 ms'), findsOneWidget);
      expect(find.text('30 ms'), findsOneWidget);

      await tester.tap(find.byKey(const Key('object-row-object-2')));
      await tester.pump();
      final paint = tester
          .widgetList<CustomPaint>(find.byType(CustomPaint))
          .where((widget) => widget.painter is ResultOverlayPainter)
          .single;
      expect(
        (paint.painter! as ResultOverlayPainter).selectedObjectId,
        'object-2',
      );
      expect(find.text('다시 촬영'), findsOneWidget);
      expect(find.byKey(const Key('primary-action')), findsOneWidget);
    },
  );

  testWidgets(
    'first result frame uses worker total until press-to-render is acknowledged',
    (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);
      await _pumpScreen(tester, fixture.controller);

      await tester.tap(find.text('분석하기'));
      await tester.pump();
      fixture.nowMs = 412;
      fixture.worker.complete(_result());
      await tester.pump();

      expect(find.text('총 2개 · 290 ms · GPU'), findsOneWidget);
      expect(find.textContaining('총 2개 · 0 ms'), findsNothing);

      await tester.pump();
      expect(find.text('총 2개 · 412 ms · GPU'), findsOneWidget);
    },
  );

  for (final size in const [Size(1280, 820), Size(1024, 720)]) {
    testWidgets('result composition has no overflow at ${size.width.toInt()}x'
        '${size.height.toInt()}', (tester) async {
      final fixture = ScannerFixture();
      addTearDown(fixture.close);
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await _pumpScreen(tester, fixture.controller);

      await tester.tap(find.text('분석하기'));
      await tester.pump();
      fixture.worker.complete(_result());
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('result-scroll')), findsOneWidget);
      expect(find.byType(Scrollable), findsOneWidget);
      final action = tester.getSize(find.byKey(const Key('primary-action')));
      expect(action.width, greaterThanOrEqualTo(44));
      expect(action.height, greaterThanOrEqualTo(44));
      final semantics = tester.getSemantics(
        find.byKey(const Key('primary-action')),
      );
      expect(semantics.label, '다시 촬영');
    });
  }

  testWidgets('primary action exposes a visible keyboard focus treatment', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    await _pumpScreen(tester, fixture.controller);

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('primary-action')),
    );
    expect(
      button.style!.side!.resolve({WidgetState.focused})!.color,
      actionBlue,
    );
    expect(button.style!.minimumSize!.resolve({})!.height, 52);
  });

  testWidgets('object row paints a visible local keyboard focus treatment', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    await _pumpScreen(tester, fixture.controller);
    await tester.tap(find.text('분석하기'));
    await tester.pump();
    fixture.worker.complete(_result());
    await tester.pumpAndSettle();

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();

    final surface = tester.widget<Container>(
      find.byKey(const Key('object-row-surface-object-1')),
    );
    final decoration = surface.decoration! as BoxDecoration;
    expect(decoration.border!.top.color, actionBlue);
    expect(decoration.border!.top.width, 2);
  });
}

Future<void> _pumpScreen(
  WidgetTester tester,
  ScannerController controller,
) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: buildBakeryTheme(),
      home: ScannerScreen(controller: controller),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _mountScreen(WidgetTester tester, ScannerController controller) =>
    tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: ScannerScreen(controller: controller),
      ),
    );

final class ScannerFixture {
  ScannerFixture({bool cameraReady = true})
    : camera = FakeCamera(cameraReady),
      worker = FakeWorker() {
    controller = ScannerController(
      camera: camera,
      worker: worker,
      clock: () => nowMs,
      readImageSize: (_) async =>
          const CapturedImageSize(width: 1920, height: 1080),
    );
  }

  final FakeCamera camera;
  final FakeWorker worker;
  double nowMs = 0;
  late final ScannerController controller;

  Future<void> close() => controller.close();
}

final class FakeCamera implements CameraSession {
  FakeCamera(this.ready);

  final errorsController = StreamController<String>.broadcast(sync: true);
  bool ready;
  Completer<bool>? initializeCompleter;
  Completer<bool>? reconnectCompleter;

  @override
  Stream<String> get errors => errorsController.stream;
  @override
  bool get isReady => ready;
  @override
  String? get lastError => ready ? null : '카메라를 찾지 못했습니다';
  @override
  CameraController? get previewController => null;
  @override
  Future<bool> initialize() async {
    final pending = initializeCompleter;
    if (pending != null) {
      ready = await pending.future;
    }
    return ready;
  }

  @override
  Future<CapturedFrame> captureStill() async =>
      const CapturedFrame(r'C:\capture.jpg');
  @override
  Future<void> releaseCapture(String absolutePath) async {}
  @override
  Future<bool> reconnect() async {
    final pending = reconnectCompleter;
    ready = pending == null ? true : await pending.future;
    return ready;
  }

  @override
  Future<void> close() => errorsController.close();
}

final class FakeWorker implements InferenceSession {
  final eventController = StreamController<WorkerEvent>.broadcast(sync: true);
  Completer<InferenceResult>? pending;
  WorkerStatus current = WorkerStatus.notStarted;

  @override
  Stream<WorkerEvent> get events => eventController.stream;
  @override
  WorkerStatus get status => current;
  @override
  Future<void> start() async {
    current = WorkerStatus.ready;
    eventController.add(
      ReadyWorkerEvent(
        device: 'cuda:0',
        metrics: const StartupMetrics(
          device: 'cuda:0',
          loadMs: 120,
          warmupMs: 30,
          fallbackReason: null,
          detectorId: 'rfdetr_large_bakery_v1',
          repvitId: 'repvit_m1_15plus5_v1',
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
          detectorThreshold: 0.5691395401954651,
        ),
      ),
    );
  }

  @override
  Future<InferenceResult> analyze(String imagePath) {
    pending = Completer<InferenceResult>();
    return pending!.future;
  }

  void complete(InferenceResult result) => pending!.complete(result);
  void emit(WorkerEvent event) => eventController.add(event);

  @override
  Future<void> shutdown() async {
    current = WorkerStatus.stopped;
    await eventController.close();
  }
}

InferenceResult _result() => InferenceResult.fromJson({
  'type': 'result',
  'request_id': 'analysis-1',
  'image': {'width': 1920, 'height': 1080},
  'device': 'cuda:0',
  'objects': [
    _object(
      id: 'object-1',
      skuId: 6,
      name: 'Croissant',
      confidence: 0.92,
      box: [10.0, 20.0, 500.0, 500.0],
    ),
    _object(
      id: 'object-2',
      skuId: null,
      name: 'Unknown',
      confidence: 0.4,
      box: [600.0, 100.0, 1000.0, 600.0],
      candidates: const [
        {'rank': 1, 'sku_id': 10, 'sku_name': 'Sugar Donut', 'score': 0.88},
        {'rank': 2, 'sku_id': 11, 'sku_name': 'Cream Donut', 'score': 0.76},
        {'rank': 3, 'sku_id': 12, 'sku_name': 'Glazed Donut', 'score': 0.62},
      ],
    ),
  ],
  'counts': {'6': 1},
  'unknown_count': 1,
  'timings_ms': {
    'decode_preprocess': 10.0,
    'detector': 120.0,
    'repvit': 50.0,
    'dinov3': 90.0,
    'postprocess': 20.0,
    'total': 290.0,
  },
});

Map<String, Object?> _object({
  required String id,
  required int? skuId,
  required String name,
  required double confidence,
  required List<double> box,
  List<Map<String, Object?>> candidates = const [],
}) => {
  'object_id': id,
  'sku_id': skuId,
  'sku_name': name,
  'bbox_xyxy': box,
  'confidence': confidence,
  'decision_path': skuId == null ? 'unknown_top3' : 'repvit_direct',
  'top3': candidates,
  'unknown_reason': skuId == null ? 'consensus_failed' : null,
  'detector': {'source': 'rfdetr', 'score': 0.95},
  'provenance': {
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_artifact_id': 'repvit_m1_15plus5_v1',
    'repvit_sha256': 'a' * 64,
    'repvit_manifest_sha256': 'b' * 64,
    'repvit_prototype_sha256': 'c' * 64,
    'dinov3_artifact_id': 'dinov3_vits16_15plus5_v1',
    'dinov3_sha256': 'd' * 64,
    'dinov3_support_sha256': 'e' * 64,
    'calibration_id': 'policy-v1',
    'calibration_sha256': 'f' * 64,
    'preprocess_sha256': '0' * 64,
    'canonical_frame_version': 'exif_visual_rgb_v1',
    'exif_orientation': 1,
    'failure_code': skuId == null ? 'consensus_failed' : null,
  },
};
