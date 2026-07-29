import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';

import '../camera/camera_service.dart';
import '../inference/inference_models.dart';
import '../inference/inference_worker_client.dart';

typedef MonotonicClock = double Function();
typedef CapturedImageSizeReader =
    Future<CapturedImageSize> Function(String absolutePath);

abstract interface class InferenceSession {
  WorkerStatus get status;
  Stream<WorkerEvent> get events;

  Future<void> start();
  Future<InferenceResult> analyze(String imagePath);
  Future<void> shutdown();
}

final class InferenceWorkerSession implements InferenceSession {
  const InferenceWorkerSession(this._client);

  final InferenceWorkerClient _client;

  @override
  WorkerStatus get status => _client.status;

  @override
  Stream<WorkerEvent> get events => _client.events;

  @override
  Future<void> start() => _client.start();

  @override
  Future<InferenceResult> analyze(String imagePath) =>
      _client.analyze(imagePath);

  @override
  Future<void> shutdown() => _client.shutdown();
}

final class CapturedImageSize {
  const CapturedImageSize({required this.width, required this.height})
    : assert(width > 0),
      assert(height > 0);

  final int width;
  final int height;

  @override
  bool operator ==(Object other) =>
      other is CapturedImageSize &&
      other.width == width &&
      other.height == height;

  @override
  int get hashCode => Object.hash(width, height);
}

enum ScannerPhase {
  idle,
  capturing,
  detecting,
  classifying,
  rechecking,
  aggregating,
  result,
  failure,
}

@immutable
final class ScannerState {
  const ScannerState({
    required this.cameraReady,
    required this.workerStatus,
    required this.startupMetrics,
    required this.device,
    required this.cameraError,
    required this.workerError,
    required this.analysisError,
    required this.isAnalyzing,
    required this.phase,
    required this.capturedImagePath,
    required this.capturedImageSize,
    required this.result,
    required this.captureMs,
    required this.pressToRenderedResultMs,
    required this.awaitingRenderedResult,
    required this.selectedObjectId,
  });

  const ScannerState.initial()
    : cameraReady = false,
      workerStatus = WorkerStatus.notStarted,
      startupMetrics = null,
      device = null,
      cameraError = null,
      workerError = null,
      analysisError = null,
      isAnalyzing = false,
      phase = ScannerPhase.idle,
      capturedImagePath = null,
      capturedImageSize = null,
      result = null,
      captureMs = null,
      pressToRenderedResultMs = null,
      awaitingRenderedResult = false,
      selectedObjectId = null;

  final bool cameraReady;
  final WorkerStatus workerStatus;
  final StartupMetrics? startupMetrics;
  final String? device;
  final String? cameraError;
  final String? workerError;
  final String? analysisError;
  final bool isAnalyzing;
  final ScannerPhase phase;
  final String? capturedImagePath;
  final CapturedImageSize? capturedImageSize;
  final InferenceResult? result;
  final double? captureMs;
  final double? pressToRenderedResultMs;
  final bool awaitingRenderedResult;
  final String? selectedObjectId;

  bool get canAnalyze =>
      cameraReady &&
      workerStatus == WorkerStatus.ready &&
      !isAnalyzing &&
      capturedImagePath == null;

  String get phaseLabel => switch (phase) {
    ScannerPhase.idle => '촬영 준비',
    ScannerPhase.capturing => '이미지 촬영 중',
    ScannerPhase.detecting => '빵 위치 찾는 중',
    ScannerPhase.classifying => '품목 확인 중',
    ScannerPhase.rechecking => 'DINOv3 재확인 중',
    ScannerPhase.aggregating => '결과 정리 중',
    ScannerPhase.result => '분석 결과',
    ScannerPhase.failure => '분석을 완료하지 못했습니다',
  };

  ScannerState copyWith({
    bool? cameraReady,
    WorkerStatus? workerStatus,
    Object? startupMetrics = _unchanged,
    Object? device = _unchanged,
    Object? cameraError = _unchanged,
    Object? workerError = _unchanged,
    Object? analysisError = _unchanged,
    bool? isAnalyzing,
    ScannerPhase? phase,
    Object? capturedImagePath = _unchanged,
    Object? capturedImageSize = _unchanged,
    Object? result = _unchanged,
    Object? captureMs = _unchanged,
    Object? pressToRenderedResultMs = _unchanged,
    bool? awaitingRenderedResult,
    Object? selectedObjectId = _unchanged,
  }) {
    return ScannerState(
      cameraReady: cameraReady ?? this.cameraReady,
      workerStatus: workerStatus ?? this.workerStatus,
      startupMetrics: identical(startupMetrics, _unchanged)
          ? this.startupMetrics
          : startupMetrics as StartupMetrics?,
      device: identical(device, _unchanged) ? this.device : device as String?,
      cameraError: identical(cameraError, _unchanged)
          ? this.cameraError
          : cameraError as String?,
      workerError: identical(workerError, _unchanged)
          ? this.workerError
          : workerError as String?,
      analysisError: identical(analysisError, _unchanged)
          ? this.analysisError
          : analysisError as String?,
      isAnalyzing: isAnalyzing ?? this.isAnalyzing,
      phase: phase ?? this.phase,
      capturedImagePath: identical(capturedImagePath, _unchanged)
          ? this.capturedImagePath
          : capturedImagePath as String?,
      capturedImageSize: identical(capturedImageSize, _unchanged)
          ? this.capturedImageSize
          : capturedImageSize as CapturedImageSize?,
      result: identical(result, _unchanged)
          ? this.result
          : result as InferenceResult?,
      captureMs: identical(captureMs, _unchanged)
          ? this.captureMs
          : captureMs as double?,
      pressToRenderedResultMs: identical(pressToRenderedResultMs, _unchanged)
          ? this.pressToRenderedResultMs
          : pressToRenderedResultMs as double?,
      awaitingRenderedResult:
          awaitingRenderedResult ?? this.awaitingRenderedResult,
      selectedObjectId: identical(selectedObjectId, _unchanged)
          ? this.selectedObjectId
          : selectedObjectId as String?,
    );
  }
}

const Object _unchanged = Object();
final Stopwatch _monotonicStopwatch = Stopwatch()..start();

final class ScannerController extends ChangeNotifier {
  factory ScannerController({
    required CameraSession camera,
    required InferenceSession worker,
    MonotonicClock? clock,
    CapturedImageSizeReader? readImageSize,
  }) {
    return ScannerController._(
      camera,
      worker,
      clock ?? _systemMonotonicClock,
      readImageSize ?? _decodeImageSize,
    );
  }

  ScannerController._(
    this._camera,
    this._worker,
    this._clock,
    this._readImageSize,
  );

  final CameraSession _camera;
  final InferenceSession _worker;
  final MonotonicClock _clock;
  final CapturedImageSizeReader _readImageSize;

  ScannerState _state = const ScannerState.initial();
  StreamSubscription<String>? _cameraErrors;
  StreamSubscription<WorkerEvent>? _workerEvents;
  double? _pressStartedAtMs;
  bool _initialized = false;
  bool _closed = false;

  ScannerState get state => _state;
  CameraController? get previewController => _camera.previewController;

  double? get activePressElapsedMs {
    final start = _pressStartedAtMs;
    if (start == null || !_state.isAnalyzing) {
      return null;
    }
    return _clock() - start;
  }

  Future<void> initialize() async {
    _ensureOpen();
    if (_initialized) {
      throw StateError('scanner controller can only be initialized once');
    }
    _initialized = true;
    _cameraErrors = _camera.errors.listen(_onCameraError);
    _workerEvents = _worker.events.listen(_onWorkerEvent);
    _replaceState(_state.copyWith(workerStatus: WorkerStatus.starting));

    await Future.wait([_initializeCamera(), _initializeWorker()]);
  }

  Future<void> _initializeCamera() async {
    try {
      final ready = await _camera.initialize();
      _replaceState(
        _state.copyWith(
          cameraReady: ready,
          cameraError: ready ? null : _camera.lastError,
        ),
      );
    } catch (error) {
      _replaceState(
        _state.copyWith(
          cameraReady: false,
          cameraError: '카메라를 초기화하지 못했습니다: $error',
        ),
      );
    }
  }

  Future<void> _initializeWorker() async {
    try {
      await _worker.start();
      _replaceState(_state.copyWith(workerStatus: _worker.status));
    } catch (error) {
      _replaceState(
        _state.copyWith(
          workerStatus: WorkerStatus.fatal,
          workerError: '모델을 준비하지 못했습니다: $error',
        ),
      );
    }
  }

  Future<void> analyze() async {
    _ensureOpen();
    if (!_state.canAnalyze) {
      throw StateError('analysis requires a ready camera and model');
    }

    _pressStartedAtMs = _clock();
    _replaceState(
      _state.copyWith(
        isAnalyzing: true,
        phase: ScannerPhase.capturing,
        analysisError: null,
        result: null,
        capturedImagePath: null,
        capturedImageSize: null,
        captureMs: null,
        pressToRenderedResultMs: null,
        awaitingRenderedResult: false,
        selectedObjectId: null,
      ),
    );

    var captureCompleted = false;
    try {
      final captureStarted = _clock();
      final capture = await _camera.captureStill();
      final captureMs = _clock() - captureStarted;
      captureCompleted = true;
      _replaceState(
        _state.copyWith(capturedImagePath: capture.path, captureMs: captureMs),
      );

      final imageSize = await _readImageSize(capture.path);
      _replaceState(_state.copyWith(capturedImageSize: imageSize));
      final result = await _worker.analyze(capture.path);
      _replaceState(
        _state.copyWith(
          isAnalyzing: false,
          phase: ScannerPhase.result,
          result: result,
          awaitingRenderedResult: true,
        ),
      );
    } catch (error, stackTrace) {
      final message = captureCompleted ? '분석을 완료하지 못했습니다' : '이미지를 촬영하지 못했습니다';
      _replaceState(
        _state.copyWith(
          isAnalyzing: false,
          phase: ScannerPhase.failure,
          analysisError: message,
          awaitingRenderedResult: false,
        ),
      );
      Error.throwWithStackTrace(StateError('$message: $error'), stackTrace);
    }
  }

  void acknowledgeResultRendered() {
    if (!_state.awaitingRenderedResult) {
      return;
    }
    final start = _pressStartedAtMs;
    if (start == null) {
      throw StateError('result rendering has no matching button press');
    }
    _replaceState(
      _state.copyWith(
        pressToRenderedResultMs: _clock() - start,
        awaitingRenderedResult: false,
      ),
    );
  }

  Future<void> resetCapture() async {
    _ensureOpen();
    if (_state.isAnalyzing) {
      throw StateError('cannot reset a capture during analysis');
    }
    final path = _state.capturedImagePath;
    if (path != null) {
      await _camera.releaseCapture(path);
    }
    _pressStartedAtMs = null;
    _replaceState(
      _state.copyWith(
        phase: ScannerPhase.idle,
        analysisError: null,
        capturedImagePath: null,
        capturedImageSize: null,
        result: null,
        captureMs: null,
        pressToRenderedResultMs: null,
        awaitingRenderedResult: false,
        selectedObjectId: null,
      ),
    );
  }

  Future<void> reconnectCamera() async {
    _ensureOpen();
    if (_state.isAnalyzing) {
      throw StateError('cannot reconnect the camera during analysis');
    }
    final ready = await _camera.reconnect();
    _replaceState(
      _state.copyWith(
        cameraReady: ready,
        cameraError: ready ? null : _camera.lastError,
      ),
    );
  }

  void selectObject(String? objectId) {
    _ensureOpen();
    if (objectId != null &&
        !(_state.result?.objects.any((object) => object.objectId == objectId) ??
            false)) {
      throw ArgumentError.value(
        objectId,
        'objectId',
        'object does not belong to the current result',
      );
    }
    _replaceState(_state.copyWith(selectedObjectId: objectId));
  }

  void _onCameraError(String error) {
    _replaceState(_state.copyWith(cameraReady: false, cameraError: error));
  }

  void _onWorkerEvent(WorkerEvent event) {
    switch (event) {
      case StartupWorkerEvent():
        _replaceState(_state.copyWith(workerStatus: event.status));
      case ReadyWorkerEvent():
        _replaceState(
          _state.copyWith(
            workerStatus: WorkerStatus.ready,
            startupMetrics: event.metrics,
            device: event.device,
            workerError: null,
          ),
        );
      case ProgressWorkerEvent():
        if (_state.isAnalyzing) {
          _replaceState(_state.copyWith(phase: _scannerPhase(event.phase)));
        }
      case FatalWorkerEvent():
        _replaceState(
          _state.copyWith(
            workerStatus: WorkerStatus.fatal,
            workerError: '모델을 준비하지 못했습니다: ${event.message}',
            isAnalyzing: false,
            phase: ScannerPhase.failure,
          ),
        );
      case StoppedWorkerEvent():
        _replaceState(_state.copyWith(workerStatus: WorkerStatus.stopped));
      case ResultWorkerEvent() || WorkerErrorEvent() || PongWorkerEvent():
        break;
    }
  }

  Future<void> close() async {
    if (_closed) {
      return;
    }
    _closed = true;
    await _cameraErrors?.cancel();
    await _workerEvents?.cancel();
    Object? firstError;
    StackTrace? firstStackTrace;
    try {
      await _worker.shutdown();
    } catch (error, stackTrace) {
      firstError = error;
      firstStackTrace = stackTrace;
    }
    try {
      await _camera.close();
    } catch (error, stackTrace) {
      firstError ??= error;
      firstStackTrace ??= stackTrace;
    }
    if (firstError != null) {
      Error.throwWithStackTrace(firstError, firstStackTrace!);
    }
  }

  void _replaceState(ScannerState next) {
    if (_closed) {
      return;
    }
    _state = next;
    notifyListeners();
  }

  void _ensureOpen() {
    if (_closed) {
      throw StateError('scanner controller is closed');
    }
  }

  static ScannerPhase _scannerPhase(WorkerPhase phase) => switch (phase) {
    WorkerPhase.detecting => ScannerPhase.detecting,
    WorkerPhase.classifying => ScannerPhase.classifying,
    WorkerPhase.rechecking => ScannerPhase.rechecking,
    WorkerPhase.aggregating => ScannerPhase.aggregating,
  };

  static double _systemMonotonicClock() =>
      _monotonicStopwatch.elapsedMicroseconds / 1000;

  static Future<CapturedImageSize> _decodeImageSize(String absolutePath) async {
    final bytes = await File(absolutePath).readAsBytes();
    final codec = await ui.instantiateImageCodec(bytes);
    try {
      final frame = await codec.getNextFrame();
      try {
        return CapturedImageSize(
          width: frame.image.width,
          height: frame.image.height,
        );
      } finally {
        frame.image.dispose();
      }
    } finally {
      codec.dispose();
    }
  }
}
