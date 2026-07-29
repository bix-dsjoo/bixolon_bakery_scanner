import 'dart:async';
import 'dart:io';

import 'package:bakery_camera_prototype/src/camera/camera_service.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  group('CameraService', () {
    late Directory testRoot;
    late Directory sessionDirectory;
    late File pluginCapture;
    late List<FakeCameraHandle> handles;
    late int directoryCreates;

    setUp(() async {
      testRoot = await Directory.systemTemp.createTemp(
        'bakery-camera-service-test-',
      );
      sessionDirectory = Directory(
        '${testRoot.path}${Platform.pathSeparator}owned-session',
      );
      pluginCapture = File(
        '${testRoot.path}${Platform.pathSeparator}plugin-capture.jpg',
      );
      await pluginCapture.writeAsBytes(const [0xff, 0xd8, 0xff, 0xd9]);
      handles = [];
      directoryCreates = 0;
    });

    tearDown(() async {
      if (await testRoot.exists()) {
        await testRoot.delete(recursive: true);
      }
    });

    CameraService createService({
      Future<List<CameraDescription>> Function()? enumerate,
    }) {
      return CameraService(
        enumerateCameras:
            enumerate ??
            () async => const [
              CameraDescription(
                name: 'first-camera',
                lensDirection: CameraLensDirection.external,
                sensorOrientation: 0,
              ),
              CameraDescription(
                name: 'second-camera',
                lensDirection: CameraLensDirection.external,
                sensorOrientation: 0,
              ),
            ],
        createController: (description) {
          final handle = FakeCameraHandle(
            name: description.name,
            capturePath: pluginCapture.path,
          );
          handles.add(handle);
          return handle;
        },
        createSessionDirectory: () async {
          directoryCreates += 1;
          return sessionDirectory.create();
        },
      );
    }

    test(
      'initialization selects the first camera and reconnect disposes exactly '
      'the replaced controller',
      () async {
        final service = createService();

        expect(await service.initialize(), isTrue);
        expect(handles.map((handle) => handle.name), ['first-camera']);
        final first = handles.single;

        expect(await service.reconnect(), isTrue);

        expect(first.disposeCalls, 1);
        expect(handles, hasLength(2));
        expect(handles.last.name, 'first-camera');
        expect(handles.last.disposeCalls, 0);
        expect(directoryCreates, 1);

        await service.close();
        expect(first.disposeCalls, 1);
        expect(handles.last.disposeCalls, 1);
      },
    );

    test('no camera fails closed without creating a controller', () async {
      final service = createService(enumerate: () async => const []);

      expect(await service.initialize(), isFalse);

      expect(service.isReady, isFalse);
      expect(service.lastError, '카메라를 찾지 못했습니다');
      expect(handles, isEmpty);
      await service.close();
    });

    test('camera errors disable readiness and are observable', () async {
      final service = createService();
      final errors = <String>[];
      service.errors.listen(errors.add);
      await service.initialize();

      handles.single.emitError('camera disconnected');
      await _pump();

      expect(service.isReady, isFalse);
      expect(service.lastError, 'camera disconnected');
      expect(errors, ['camera disconnected']);
      await service.close();
    });

    test(
      'captures live only in the one session directory until released',
      () async {
        final service = createService();
        await service.initialize();

        final capture = await service.captureStill();

        expect(
          File(capture.path).parent.absolute.path,
          sessionDirectory.absolute.path,
        );
        expect(File(capture.path).existsSync(), isTrue);
        expect(directoryCreates, 1);
        expect(pluginCapture.existsSync(), isFalse);

        await service.releaseCapture(capture.path);

        expect(File(capture.path).existsSync(), isFalse);
        await service.close();
      },
    );

    test(
      'close removes session files and closes errors when controller disposal '
      'fails',
      () async {
        final service = createService();
        await service.initialize();
        final capture = await service.captureStill();
        handles.single.disposeError = StateError('dispose failed');
        final errorsDone = service.errors.drain<void>();

        await expectLater(service.close(), throwsStateError);

        expect(handles.single.disposeCalls, 1);
        expect(File(capture.path).existsSync(), isFalse);
        expect(sessionDirectory.existsSync(), isFalse);
        await errorsDone;
      },
    );
  });

  group('ScannerController', () {
    late FakeCameraSession camera;
    late FakeInferenceSession worker;
    late FakeMonotonicClock clock;
    late ScannerController controller;

    setUp(() {
      camera = FakeCameraSession();
      worker = FakeInferenceSession();
      clock = FakeMonotonicClock();
      controller = ScannerController(
        camera: camera,
        worker: worker,
        clock: clock.call,
        readImageSize: (_) async =>
            const CapturedImageSize(width: 1920, height: 1080),
      );
    });

    tearDown(() async {
      await controller.close();
    });

    test(
      'analysis requires camera and model readiness and is single-flight',
      () async {
        await controller.initialize();
        final first = controller.analyze();

        expect(controller.state.isAnalyzing, isTrue);
        await expectLater(controller.analyze(), throwsStateError);

        await worker.analysisStarted;
        worker.completeAnalysis(_emptyResult());
        await first;

        expect(controller.state.result, isNotNull);
        expect(controller.state.isAnalyzing, isFalse);
      },
    );

    test('analysis is disabled when no camera is available', () async {
      camera.initializeResult = false;

      await controller.initialize();

      expect(controller.state.cameraReady, isFalse);
      expect(controller.state.workerStatus, WorkerStatus.ready);
      expect(controller.state.canAnalyze, isFalse);
      await expectLater(controller.analyze(), throwsStateError);
    });

    test(
      'camera reconnect restores readiness through the same session',
      () async {
        camera.initializeResult = false;
        await controller.initialize();
        camera.reconnectResult = true;

        await controller.reconnectCamera();

        expect(camera.reconnectCalls, 1);
        expect(controller.state.cameraReady, isTrue);
        expect(controller.state.canAnalyze, isTrue);
      },
    );

    test(
      'camera reconnect disables analysis immediately and is single-flight',
      () async {
        await controller.initialize();
        camera.reconnectCompleter = Completer<bool>();

        final reconnect = controller.reconnectCamera();

        expect(controller.state.cameraReady, isFalse);
        expect(controller.state.canAnalyze, isFalse);
        await expectLater(controller.analyze(), throwsStateError);
        await expectLater(controller.reconnectCamera(), throwsStateError);

        camera.reconnectCompleter!.complete(true);
        await reconnect;
        expect(controller.state.cameraReady, isTrue);
        expect(controller.state.canAnalyze, isTrue);
      },
    );

    test('camera reconnect failure remains fail-closed in state', () async {
      await controller.initialize();
      camera.reconnectError = StateError('dispose failed');

      await controller.reconnectCamera();

      expect(controller.state.cameraReady, isFalse);
      expect(controller.state.canAnalyze, isFalse);
      expect(controller.state.cameraError, contains('dispose failed'));
    });

    test('worker fatal disables analysis with an actionable state', () async {
      await controller.initialize();

      worker.emit(
        const FatalWorkerEvent(
          code: 'artifact_hash_mismatch',
          message: 'model integrity failed',
        ),
      );

      expect(controller.state.workerStatus, WorkerStatus.fatal);
      expect(controller.state.workerError, contains('model integrity failed'));
      expect(controller.state.canAnalyze, isFalse);
    });

    test(
      'capture failure ends single-flight and preserves a retryable error',
      () async {
        camera.captureError = StateError('camera busy');
        await controller.initialize();

        await expectLater(controller.analyze(), throwsStateError);

        expect(controller.state.isAnalyzing, isFalse);
        expect(controller.state.analysisError, '이미지를 촬영하지 못했습니다');
        expect(controller.state.capturedImagePath, isNull);
        expect(worker.analyzeCalls, 0);
      },
    );

    test('empty detections are a valid retained result', () async {
      await controller.initialize();
      final analysis = controller.analyze();
      await worker.analysisStarted;
      worker.completeAnalysis(_emptyResult());

      await analysis;

      expect(controller.state.result!.objects, isEmpty);
      expect(controller.state.analysisError, isNull);
      expect(controller.state.capturedImagePath, camera.capture.path);
      expect(camera.releasedPaths, isEmpty);
    });

    test('result selects the lowest-score unresolved object first', () async {
      await controller.initialize();
      final analysis = controller.analyze();
      await worker.analysisStarted;
      worker.completeAnalysis(buildOrderingInferenceResult());

      await analysis;

      expect(controller.state.selectedObjectId, 'object-3');
    });

    test(
      'reset returns to live preview and clears the selected object identity',
      () async {
        await controller.initialize();
        final analysis = controller.analyze();
        await worker.analysisStarted;
        worker.completeAnalysis(_confirmedResult());
        await analysis;
        controller.selectObject('object-1');

        await controller.resetCapture();

        expect(camera.releasedPaths, [camera.capture.path]);
        expect(controller.state.result, isNull);
        expect(controller.state.capturedImagePath, isNull);
        expect(controller.state.selectedObjectId, isNull);
        expect(controller.state.captureMs, isNull);
        expect(controller.state.pressToRenderedResultMs, isNull);
        expect(controller.state.canAnalyze, isTrue);
      },
    );

    test('camera errors clear readiness after initialization', () async {
      await controller.initialize();

      camera.emitError('USB camera removed');

      expect(controller.state.cameraReady, isFalse);
      expect(controller.state.cameraError, 'USB camera removed');
      expect(controller.state.canAnalyze, isFalse);
    });

    test('worker progress maps to factual Korean phases', () async {
      await controller.initialize();
      final analysis = controller.analyze();
      expect(controller.state.phaseLabel, '이미지를 촬영하고 있어요.');
      await worker.analysisStarted;

      worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.detecting,
        ),
      );
      expect(controller.state.phaseLabel, '빵을 찾고 있어요.');
      worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.classifying,
        ),
      );
      expect(controller.state.phaseLabel, '빵 종류를 확인하고 있어요.');
      worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.rechecking,
        ),
      );
      expect(controller.state.phaseLabel, '분류 결과를 다시 확인하고 있어요.');
      worker.emit(
        const ProgressWorkerEvent(
          requestId: 'analysis-1',
          phase: WorkerPhase.aggregating,
        ),
      );
      expect(controller.state.phaseLabel, '결과를 정리하고 있어요.');

      worker.completeAnalysis(_emptyResult());
      await analysis;
    });

    test(
      'capture and worker timings stay separate from post-frame press timing',
      () async {
        camera.onCapture = () => clock.advance(20);
        await controller.initialize();

        clock.advance(100);
        final analysis = controller.analyze();
        await worker.analysisStarted;
        clock.advance(5);
        worker.completeAnalysis(_emptyResult(workerTotalMs: 37));
        await analysis;

        expect(controller.state.captureMs, 20);
        expect(controller.state.result!.timings.totalMs, 37);
        expect(controller.state.pressToRenderedResultMs, isNull);
        expect(controller.state.awaitingRenderedResult, isTrue);
        expect(
          controller.state.capturedImageSize,
          const CapturedImageSize(width: 1920, height: 1080),
        );

        clock.advance(16);
        controller.acknowledgeResultRendered();

        expect(controller.state.pressToRenderedResultMs, 41);
        expect(controller.state.awaitingRenderedResult, isFalse);

        clock.advance(10);
        controller.acknowledgeResultRendered();
        expect(controller.state.pressToRenderedResultMs, 41);
      },
    );
  });
}

Future<void> _pump() => Future<void>.delayed(Duration.zero);

final class FakeCameraHandle implements CameraControllerHandle {
  FakeCameraHandle({required this.name, required this.capturePath});

  final String name;
  final String capturePath;
  final List<VoidCallback> _listeners = [];
  bool _initialized = false;
  String? _error;
  int disposeCalls = 0;
  Object? disposeError;

  @override
  CameraController? get previewController => null;

  @override
  bool get hasError => _error != null;

  @override
  String? get errorDescription => _error;

  @override
  bool get isInitialized => _initialized;

  @override
  void addListener(VoidCallback listener) {
    _listeners.add(listener);
  }

  @override
  Future<void> dispose() async {
    disposeCalls += 1;
    _initialized = false;
    final error = disposeError;
    if (error != null) {
      throw error;
    }
  }

  @override
  Future<void> initialize() async {
    _initialized = true;
  }

  @override
  void removeListener(VoidCallback listener) {
    _listeners.remove(listener);
  }

  @override
  Future<String> takePicturePath() async => capturePath;

  void emitError(String error) {
    _error = error;
    for (final listener in List<VoidCallback>.from(_listeners)) {
      listener();
    }
  }
}

final class FakeCameraSession implements CameraSession {
  final _errors = StreamController<String>.broadcast(sync: true);
  final capture = const CapturedFrame(r'C:\session\capture-1.jpg');
  bool initializeResult = true;
  bool reconnectResult = true;
  Object? captureError;
  Object? reconnectError;
  Completer<bool>? reconnectCompleter;
  VoidCallback? onCapture;
  int reconnectCalls = 0;
  int closeCalls = 0;
  final releasedPaths = <String>[];
  bool _ready = false;

  @override
  Stream<String> get errors => _errors.stream;

  @override
  bool get isReady => _ready;

  @override
  String? get lastError => _ready ? null : '카메라를 찾지 못했습니다';

  @override
  CameraController? get previewController => null;

  @override
  Future<bool> initialize() async {
    _ready = initializeResult;
    return _ready;
  }

  @override
  Future<CapturedFrame> captureStill() async {
    onCapture?.call();
    final error = captureError;
    if (error != null) {
      throw error;
    }
    return capture;
  }

  @override
  Future<bool> reconnect() async {
    reconnectCalls += 1;
    final error = reconnectError;
    if (error != null) {
      throw error;
    }
    final pending = reconnectCompleter;
    if (pending != null) {
      reconnectResult = await pending.future;
    }
    _ready = reconnectResult;
    return _ready;
  }

  @override
  Future<void> releaseCapture(String absolutePath) async {
    releasedPaths.add(absolutePath);
  }

  @override
  Future<void> close() async {
    closeCalls += 1;
    await _errors.close();
  }

  void emitError(String error) {
    _ready = false;
    _errors.add(error);
  }
}

final class FakeInferenceSession implements InferenceSession {
  final _events = StreamController<WorkerEvent>.broadcast(sync: true);
  final _analysisStarted = Completer<void>();
  Completer<InferenceResult>? _analysis;
  WorkerStatus _status = WorkerStatus.notStarted;
  int analyzeCalls = 0;
  int shutdownCalls = 0;

  @override
  Stream<WorkerEvent> get events => _events.stream;

  @override
  WorkerStatus get status => _status;

  Future<void> get analysisStarted => _analysisStarted.future;

  @override
  Future<void> start() async {
    _status = WorkerStatus.loading;
    _events.add(
      const StartupWorkerEvent(status: WorkerStatus.loading, device: null),
    );
    _status = WorkerStatus.warming;
    _events.add(
      const StartupWorkerEvent(status: WorkerStatus.warming, device: 'cpu'),
    );
    _status = WorkerStatus.ready;
    _events.add(ReadyWorkerEvent(device: 'cpu', metrics: _startupMetrics()));
  }

  @override
  Future<InferenceResult> analyze(String imagePath) {
    analyzeCalls += 1;
    _analysis = Completer<InferenceResult>();
    _analysisStarted.complete();
    return _analysis!.future;
  }

  @override
  Future<void> shutdown() async {
    shutdownCalls += 1;
    _status = WorkerStatus.stopped;
    await _events.close();
  }

  void emit(WorkerEvent event) {
    if (event is FatalWorkerEvent) {
      _status = WorkerStatus.fatal;
    }
    _events.add(event);
  }

  void completeAnalysis(InferenceResult result) {
    _analysis!.complete(result);
  }
}

final class FakeMonotonicClock {
  double _milliseconds = 0;

  double call() => _milliseconds;

  void advance(double milliseconds) {
    _milliseconds += milliseconds;
  }
}

StartupMetrics _startupMetrics() {
  return const StartupMetrics(
    device: 'cpu',
    loadMs: 120,
    warmupMs: 30,
    fallbackReason: null,
    detectorId: 'rfdetr_large_bakery_v1',
    repvitId: 'repvit_m1_15plus5_v1',
    dinov3Id: 'dinov3_vits16_15plus5_v1',
    fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
    detectorThreshold: 0.5,
  );
}

InferenceResult _emptyResult({double workerTotalMs = 37}) {
  return InferenceResult.fromJson({
    'type': 'result',
    'request_id': 'analysis-1',
    'image': {'width': 1920, 'height': 1080},
    'device': 'cpu',
    'objects': <Object?>[],
    'counts': <String, Object?>{},
    'unknown_count': 0,
    'timings_ms': {
      'decode_preprocess': 1.0,
      'detector': 20.0,
      'repvit': 8.0,
      'dinov3': 0.0,
      'postprocess': workerTotalMs - 29,
      'total': workerTotalMs,
    },
  });
}

InferenceResult _confirmedResult() {
  return InferenceResult.fromJson({
    'type': 'result',
    'request_id': 'analysis-1',
    'image': {'width': 1920, 'height': 1080},
    'device': 'cpu',
    'objects': [
      {
        'object_id': 'object-1',
        'sku_id': 6,
        'sku_name': 'Croissant',
        'bbox_xyxy': [10.0, 20.0, 110.0, 120.0],
        'confidence': 0.92,
        'decision_path': 'repvit_direct',
        'top3': <Object?>[],
        'unknown_reason': null,
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
          'failure_code': null,
        },
      },
    ],
    'counts': {'6': 1},
    'unknown_count': 0,
    'timings_ms': {
      'decode_preprocess': 1.0,
      'detector': 20.0,
      'repvit': 8.0,
      'dinov3': 0.0,
      'postprocess': 8.0,
      'total': 37.0,
    },
  });
}
