import 'dart:async';

import 'package:bakery_camera_prototype/src/camera/camera_service.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/result_overlay.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/scanner_screen.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
    expect(find.text('분석하기'), findsOneWidget);
    expect(find.text('카메라를 찾지 못했습니다'), findsOneWidget);
    expect(find.text('카메라 다시 연결'), findsOneWidget);
  });

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

  @override
  Stream<String> get errors => errorsController.stream;
  @override
  bool get isReady => ready;
  @override
  String? get lastError => ready ? null : '카메라를 찾지 못했습니다';
  @override
  CameraController? get previewController => null;
  @override
  Future<bool> initialize() async => ready;
  @override
  Future<CapturedFrame> captureStill() async =>
      const CapturedFrame(r'C:\capture.jpg');
  @override
  Future<void> releaseCapture(String absolutePath) async {}
  @override
  Future<bool> reconnect() async => ready = true;
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
