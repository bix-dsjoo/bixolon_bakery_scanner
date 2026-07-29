import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';

typedef CameraEnumerator = Future<List<CameraDescription>> Function();
typedef CameraControllerFactory =
    CameraControllerHandle Function(CameraDescription description);
typedef SessionDirectoryFactory = Future<Directory> Function();

final class CapturedFrame {
  const CapturedFrame(this.path);

  final String path;
}

abstract interface class CameraControllerHandle {
  CameraController? get previewController;
  bool get isInitialized;
  bool get hasError;
  String? get errorDescription;

  void addListener(VoidCallback listener);
  void removeListener(VoidCallback listener);
  Future<void> initialize();
  Future<String> takePicturePath();
  Future<void> dispose();
}

abstract interface class CameraSession {
  bool get isReady;
  String? get lastError;
  CameraController? get previewController;
  Stream<String> get errors;

  Future<bool> initialize();
  Future<CapturedFrame> captureStill();
  Future<void> releaseCapture(String absolutePath);
  Future<bool> reconnect();
  Future<void> close();
}

final class CameraService implements CameraSession {
  CameraService({
    CameraEnumerator? enumerateCameras,
    CameraControllerFactory? createController,
    SessionDirectoryFactory? createSessionDirectory,
  }) : _enumerateCameras = enumerateCameras ?? availableCameras,
       _createController =
           createController ??
           ((description) => _PluginCameraControllerHandle(description)),
       _createSessionDirectory =
           createSessionDirectory ??
           (() => Directory.systemTemp.createTemp('bixolon-camera-session-'));

  final CameraEnumerator _enumerateCameras;
  final CameraControllerFactory _createController;
  final SessionDirectoryFactory _createSessionDirectory;
  final StreamController<String> _errors = StreamController<String>.broadcast(
    sync: true,
  );

  CameraControllerHandle? _controller;
  VoidCallback? _controllerListener;
  Directory? _sessionDirectory;
  String? _lastError;
  int _captureSequence = 0;
  bool _closed = false;

  @override
  bool get isReady =>
      !_closed &&
      _controller != null &&
      _controller!.isInitialized &&
      _lastError == null;

  @override
  String? get lastError => _lastError;

  @override
  CameraController? get previewController => _controller?.previewController;

  @override
  Stream<String> get errors => _errors.stream;

  @override
  Future<bool> initialize() async {
    _ensureOpen();
    await _ensureSessionDirectory();
    return _connect();
  }

  @override
  Future<bool> reconnect() async {
    _ensureOpen();
    await _ensureSessionDirectory();
    await _disposeCurrentController();
    return _connect();
  }

  Future<bool> _connect() async {
    _lastError = null;
    CameraControllerHandle? candidate;
    try {
      final cameras = await _enumerateCameras();
      if (cameras.isEmpty) {
        _lastError = '카메라를 찾지 못했습니다';
        return false;
      }

      candidate = _createController(cameras.first);
      final ownedController = candidate;
      void listener() => _handleControllerChange(ownedController);
      candidate.addListener(listener);
      _controller = candidate;
      _controllerListener = listener;
      await candidate.initialize();
      if (candidate.hasError || !candidate.isInitialized) {
        final error = candidate.errorDescription ?? '카메라를 초기화하지 못했습니다';
        _publishError(error);
        await _disposeCurrentController();
        return false;
      }
      return true;
    } catch (error) {
      _lastError = '카메라를 초기화하지 못했습니다: $error';
      if (identical(_controller, candidate)) {
        await _disposeCurrentController();
      } else if (candidate != null) {
        await candidate.dispose();
      }
      return false;
    }
  }

  void _handleControllerChange(CameraControllerHandle owner) {
    if (!identical(owner, _controller) || !owner.hasError) {
      return;
    }
    _publishError(owner.errorDescription ?? '카메라 연결 오류가 발생했습니다');
  }

  void _publishError(String error) {
    _lastError = error;
    if (!_errors.isClosed) {
      _errors.add(error);
    }
  }

  @override
  Future<CapturedFrame> captureStill() async {
    _ensureOpen();
    final controller = _controller;
    final directory = _sessionDirectory;
    if (!isReady || controller == null || directory == null) {
      throw StateError('camera capture requires an initialized camera');
    }

    final sourcePath = await controller.takePicturePath();
    final source = File(sourcePath);
    if (!source.isAbsolute || !await source.exists()) {
      throw StateError('camera returned an invalid capture path');
    }
    _captureSequence += 1;
    final destination = File(
      '${directory.path}${Platform.pathSeparator}'
      'capture-$_captureSequence.jpg',
    );
    await source.copy(destination.path);
    return CapturedFrame(destination.absolute.path);
  }

  @override
  Future<void> releaseCapture(String absolutePath) async {
    final directory = _sessionDirectory;
    if (directory == null) {
      return;
    }
    final capture = File(absolutePath).absolute;
    if (!_samePath(capture.parent.path, directory.absolute.path)) {
      throw ArgumentError.value(
        absolutePath,
        'absolutePath',
        'capture is not owned by this camera session',
      );
    }
    if (await capture.exists()) {
      await capture.delete();
    }
  }

  Future<void> _ensureSessionDirectory() async {
    if (_sessionDirectory != null) {
      return;
    }
    final directory = await _createSessionDirectory();
    _sessionDirectory = directory.absolute;
  }

  Future<void> _disposeCurrentController() async {
    final controller = _controller;
    final listener = _controllerListener;
    _controller = null;
    _controllerListener = null;
    if (controller == null) {
      return;
    }
    if (listener != null) {
      controller.removeListener(listener);
    }
    await controller.dispose();
  }

  @override
  Future<void> close() async {
    if (_closed) {
      return;
    }
    _closed = true;
    await _disposeCurrentController();
    final directory = _sessionDirectory;
    _sessionDirectory = null;
    if (directory != null && await directory.exists()) {
      await directory.delete(recursive: true);
    }
    await _errors.close();
  }

  void _ensureOpen() {
    if (_closed) {
      throw StateError('camera session is closed');
    }
  }

  static bool _samePath(String left, String right) {
    if (Platform.isWindows) {
      return left.toLowerCase() == right.toLowerCase();
    }
    return left == right;
  }
}

final class _PluginCameraControllerHandle implements CameraControllerHandle {
  _PluginCameraControllerHandle(CameraDescription description)
    : _controller = CameraController(
        description,
        ResolutionPreset.max,
        enableAudio: false,
      );

  final CameraController _controller;

  @override
  CameraController get previewController => _controller;

  @override
  bool get isInitialized => _controller.value.isInitialized;

  @override
  bool get hasError => _controller.value.hasError;

  @override
  String? get errorDescription => _controller.value.errorDescription;

  @override
  void addListener(VoidCallback listener) {
    _controller.addListener(listener);
  }

  @override
  void removeListener(VoidCallback listener) {
    _controller.removeListener(listener);
  }

  @override
  Future<void> initialize() => _controller.initialize();

  @override
  Future<String> takePicturePath() async {
    final capture = await _controller.takePicture();
    return capture.path;
  }

  @override
  Future<void> dispose() => _controller.dispose();
}
