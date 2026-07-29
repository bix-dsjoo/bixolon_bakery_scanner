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

import '../support/inference_fixtures.dart';

void main() {
  testWidgets(
    'compact divider header and flat 64/36 panes identify the scan console',
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
      expect(paneRatio, closeTo(64 / 36, 0.15));

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

  testWidgets('result pane remains at least 360 pixels wide at 1024', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pumpScreen(tester, fixture.controller);

    expect(
      tester.getSize(find.byKey(const Key('result-pane'))).width,
      greaterThanOrEqualTo(360),
    );
  });

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

      fixture.worker.complete(buildUiInferenceResult());
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
    fixture.worker.complete(buildUiInferenceResult());
    await tester.pumpAndSettle();

    final confirmedDot = tester.widget<Container>(
      find.byKey(const Key('object-semantic-dot-object-1')),
    );
    final unknownDot = tester.widget<Container>(
      find.byKey(const Key('object-semantic-dot-object-2')),
    );
    final confirmedDecoration = confirmedDot.decoration! as BoxDecoration;
    final unknownDecoration = unknownDot.decoration! as BoxDecoration;

    expect(confirmedDecoration.color, confirmedTeal);
    expect(unknownDecoration.color, unknownAmber);
    expect(confirmedDecoration.color, isNot(bixolonOrange));
    expect(unknownDecoration.color, isNot(bixolonOrange));
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
    expect(find.text('카메라를 찾지 못했어요.'), findsOneWidget);
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
      expect(find.text('카메라를 연결하고 있어요.'), findsOneWidget);
      expect(find.text('카메라 다시 연결'), findsNothing);

      fixture.camera.initializeCompleter!.complete(false);
      await tester.pumpAndSettle();
      expect(find.text('카메라를 찾지 못했어요.'), findsOneWidget);
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

      expect(find.textContaining('이미지를 촬영하고 있어요.'), findsOneWidget);
      expect(find.textContaining('ms'), findsWidgets);

      fixture.worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.detecting,
        ),
      );
      await tester.pump();
      expect(find.textContaining('빵을 찾고 있어요.'), findsOneWidget);

      fixture.worker.complete(buildUiInferenceResult());
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
      fixture.worker.complete(buildUiInferenceResult());
      await tester.pumpAndSettle();

      expect(find.text('대상 2'), findsOneWidget);
      expect(find.text('확정 1'), findsOneWidget);
      expect(find.text('알 수 없음 1'), findsOneWidget);
      expect(find.text('화면 표시까지'), findsOneWidget);
      expect(find.text('412 ms'), findsOneWidget);
      expect(find.text('모델 추론'), findsOneWidget);
      expect(find.text('290 ms'), findsOneWidget);
      expect(find.text('GPU'), findsWidgets);
      expect(find.text('Croissant'), findsWidgets);
      expect(find.text('92.0%'), findsOneWidget);
      expect(find.text('RepViT 직접 확정'), findsOneWidget);
      expect(find.text('알 수 없음'), findsWidgets);
      await tester.tap(find.byKey(const Key('evaluation-object-row-object-2')));
      await tester.pump();
      expect(find.byKey(const Key('candidate-row')), findsNWidgets(3));
      expect(find.text('1'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('Sugar Donut'), findsOneWidget);
      expect(find.text('88.0%'), findsNWidgets(2));
      expect(find.text('정확도'), findsNothing);

      expect(find.text('120 ms'), findsNothing);
      await tester.ensureVisible(find.text('모델 정보'));
      await tester.tap(find.text('모델 정보'));
      await tester.pumpAndSettle();
      expect(find.text('120 ms'), findsOneWidget);
      expect(find.text('30 ms'), findsOneWidget);

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
      fixture.worker.complete(buildUiInferenceResult());
      await tester.pump();

      expect(find.text('대상 2'), findsOneWidget);
      expect(find.text('290 ms'), findsNWidgets(2));

      await tester.pump();
      expect(find.text('412 ms'), findsOneWidget);
      expect(find.text('290 ms'), findsOneWidget);
    },
  );

  testWidgets('tapping an overlay box selects the matching evaluation row', (
    tester,
  ) async {
    final fixture = ScannerFixture();
    addTearDown(fixture.close);
    await _pumpScreen(tester, fixture.controller);
    await tester.tap(find.text('분석하기'));
    await tester.pump();
    fixture.worker.complete(buildUiInferenceResult());
    await tester.pumpAndSettle();

    final overlay = tester
        .widgetList<CustomPaint>(find.byType(CustomPaint))
        .where((widget) => widget.painter is ResultOverlayPainter)
        .single;
    final painter = overlay.painter! as ResultOverlayPainter;
    final overlayFinder = find.byWidget(overlay);
    final target = painter.transform
        .mapBox(
          painter.items
              .singleWhere((item) => item.objectId == 'object-1')
              .imageBox,
        )
        .center;

    await tester.tapAt(tester.getTopLeft(overlayFinder) + target);
    await tester.pump();

    expect(fixture.controller.state.selectedObjectId, 'object-1');
    expect(find.byKey(const Key('candidate-row')), findsNothing);
  });

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
      fixture.worker.complete(buildUiInferenceResult());
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
    fixture.worker.complete(buildUiInferenceResult());
    await tester.pumpAndSettle();

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();

    final surface = tester.widget<Container>(
      find.byKey(const Key('object-row-surface-object-2')),
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
