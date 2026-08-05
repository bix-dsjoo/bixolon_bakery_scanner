import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'inference_launch_config.dart';
import 'inference_models.dart';

abstract interface class WorkerProcessAdapter {
  Stream<List<int>> get stdout;
  Stream<List<int>> get stderr;
  Future<int> get exitCode;

  void writeLine(String line);
  bool kill();
}

typedef WorkerProcessStarter =
    Future<WorkerProcessAdapter> Function(InferenceLaunchConfig config);

final class WorkerRequestException implements Exception {
  const WorkerRequestException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => 'WorkerRequestException($code): $message';
}

/// Immutable observation of events the strict client has already accepted.
/// It adds no worker commands and cannot be used to change runtime policy.
final class WorkerDiagnosticSnapshot {
  WorkerDiagnosticSnapshot._({
    required this.status,
    required this.startupMetrics,
    required this.fatalEvent,
    required this.lastWorkerError,
    required List<String> diagnostics,
  }) : diagnostics = List.unmodifiable(diagnostics);

  final WorkerStatus status;
  final StartupMetrics? startupMetrics;
  final FatalWorkerEvent? fatalEvent;
  final WorkerErrorEvent? lastWorkerError;
  final List<String> diagnostics;
}

final class InferenceWorkerClient {
  InferenceWorkerClient({
    required this.config,
    WorkerProcessStarter? startProcess,
    this.shutdownTimeout = const Duration(seconds: 3),
  }) : _startProcess = startProcess ?? _startOwnedProcess;

  final InferenceLaunchConfig config;
  final Duration shutdownTimeout;
  final WorkerProcessStarter _startProcess;
  final StreamController<WorkerEvent> _events =
      StreamController<WorkerEvent>.broadcast(sync: true);
  final List<String> _diagnostics = [];
  final Map<String, Completer<InferenceResult>> _pending = {};
  final Map<String, WorkerPhase?> _progress = {};

  WorkerProcessAdapter? _process;
  Future<WorkerProcessAdapter>? _startingProcess;
  Completer<void>? _startOwnershipCompleter;
  Completer<void>? _startCompleter;
  Completer<void>? _stoppedCompleter;
  Future<void>? _shutdownFuture;
  Object? _cancelledStartTerminationError;
  WorkerStatus _status = WorkerStatus.notStarted;
  int _requestSequence = 0;
  String? _shutdownRequestId;
  bool _shuttingDown = false;
  StartupMetrics? _startupMetrics;
  FatalWorkerEvent? _fatalEvent;
  WorkerErrorEvent? _lastWorkerError;

  WorkerStatus get status => _status;
  Stream<WorkerEvent> get events => _events.stream;
  List<String> get diagnostics => List.unmodifiable(_diagnostics);
  WorkerDiagnosticSnapshot get diagnosticSnapshot => WorkerDiagnosticSnapshot._(
    status: _status,
    startupMetrics: _startupMetrics,
    fatalEvent: _fatalEvent,
    lastWorkerError: _lastWorkerError,
    diagnostics: _diagnostics,
  );

  Future<void> start() {
    if (_status != WorkerStatus.notStarted) {
      throw StateError('inference worker can only be started once');
    }
    _status = WorkerStatus.starting;
    final ready = Completer<void>();
    _startCompleter = ready;

    try {
      final startingProcess = _startProcess(config);
      final ownership = Completer<void>();
      _startingProcess = startingProcess;
      _startOwnershipCompleter = ownership;
      unawaited(_finishStartingProcess(startingProcess, ownership));
    } catch (error, stackTrace) {
      _markFatal(
        StateError('inference worker failed to start: $error'),
        stackTrace,
      );
    }
    return ready.future;
  }

  Future<InferenceResult> analyze(String imagePath) {
    if (_status != WorkerStatus.ready || _shuttingDown) {
      throw StateError('inference analysis requires a ready worker');
    }
    if (imagePath.trim().isEmpty) {
      throw ArgumentError.value(imagePath, 'imagePath', 'must not be empty');
    }
    final requestId = _nextRequestId('analysis');
    final completer = Completer<InferenceResult>();
    _pending[requestId] = completer;
    _progress[requestId] = null;
    _writeRequest({
      'type': 'analyze',
      'request_id': requestId,
      'image_path': imagePath,
    });
    return completer.future;
  }

  Future<void> shutdown() {
    final existing = _shutdownFuture;
    if (existing != null) {
      return existing;
    }
    if (_status == WorkerStatus.stopped) {
      return Future<void>.value();
    }
    final shutdown = _performShutdown();
    _shutdownFuture = shutdown;
    return shutdown;
  }

  Future<void> _performShutdown() async {
    _shuttingDown = true;
    final stopped = Completer<void>();
    _stoppedCompleter = stopped;
    final start = _startCompleter;
    if (start != null && !start.isCompleted) {
      start.completeError(
        StateError('inference worker was shut down while starting'),
      );
    }

    try {
      var process = _process;
      final ownership = _startOwnershipCompleter;
      if (process == null && ownership != null && !ownership.isCompleted) {
        try {
          await ownership.future.timeout(shutdownTimeout);
        } on TimeoutException {
          _appendDiagnostic(
            'worker start did not finish before shutdown timeout',
          );
        }
        final terminationError = _cancelledStartTerminationError;
        if (terminationError != null) {
          throw terminationError;
        }
        _status = WorkerStatus.stopped;
        return;
      }

      process = _process;
      if (process == null) {
        _status = WorkerStatus.stopped;
        return;
      }

      final requestId = _nextRequestId('shutdown');
      _shutdownRequestId = requestId;
      if (_status != WorkerStatus.fatal) {
        _writeRequest({'type': 'shutdown', 'request_id': requestId});
      }

      var exited = false;
      try {
        await Future.any<void>([
          stopped.future,
          process.exitCode.then((_) {
            exited = true;
          }),
        ]).timeout(shutdownTimeout);
        if (!exited) {
          await process.exitCode.timeout(shutdownTimeout);
        }
      } on TimeoutException {
        if (!process.kill()) {
          throw StateError('owned inference worker could not be killed');
        }
        await _awaitExitAfterKill(process);
      }
      _status = WorkerStatus.stopped;
    } catch (error, stackTrace) {
      _markFatal(error, stackTrace, null, true);
      rethrow;
    } finally {
      _completePending(
        StateError('inference worker shut down before returning a result'),
      );
      if (!stopped.isCompleted) {
        stopped.complete();
      }
    }
  }

  Future<void> _finishStartingProcess(
    Future<WorkerProcessAdapter> startingProcess,
    Completer<void> ownership,
  ) async {
    try {
      final process = await startingProcess;
      if (identical(_startingProcess, startingProcess)) {
        _startingProcess = null;
      }
      _process = process;
      if (_shuttingDown || _status == WorkerStatus.stopped) {
        await _terminateCancelledStart(process);
        return;
      }
      if (_status == WorkerStatus.fatal) {
        await _terminateCancelledStart(process);
        return;
      }
      _listenToProcess(process);
    } catch (error, stackTrace) {
      if (!_shuttingDown && _status != WorkerStatus.stopped) {
        _markFatal(
          StateError('inference worker failed to start: $error'),
          stackTrace,
        );
      }
    } finally {
      if (identical(_startingProcess, startingProcess)) {
        _startingProcess = null;
      }
      if (!ownership.isCompleted) {
        ownership.complete();
      }
    }
  }

  void _listenToProcess(WorkerProcessAdapter process) {
    process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(
          _onStdoutLine,
          onError: (Object error, StackTrace stackTrace) {
            _markFatal(
              StateError('worker stdout is not valid UTF-8: $error'),
              stackTrace,
            );
          },
        );
    process.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen(
          _appendDiagnostic,
          onError: (Object error) {
            _appendDiagnostic('stderr decode failed: $error');
          },
        );
    unawaited(
      process.exitCode.then(
        _onProcessExit,
        onError: (Object error, StackTrace stackTrace) {
          _markFatal(
            StateError('worker exit status failed: $error'),
            stackTrace,
          );
        },
      ),
    );
  }

  Future<void> _terminateCancelledStart(WorkerProcessAdapter process) async {
    if (!process.kill()) {
      final error = StateError('owned inference worker could not be killed');
      _cancelledStartTerminationError = error;
      _appendDiagnostic(error.toString());
      _markFatal(error, null, null, true);
      return;
    }
    await _awaitExitAfterKill(process);
  }

  Future<void> _awaitExitAfterKill(WorkerProcessAdapter process) async {
    try {
      await process.exitCode.timeout(shutdownTimeout);
    } on TimeoutException {
      _appendDiagnostic('killed worker did not report exit before timeout');
    } catch (error) {
      _appendDiagnostic('killed worker exit status failed: $error');
    }
  }

  void _onStdoutLine(String line) {
    if (_status == WorkerStatus.fatal || _status == WorkerStatus.stopped) {
      return;
    }
    try {
      final decoded = jsonDecode(line);
      if (decoded is! Map || decoded.keys.any((key) => key is! String)) {
        throw const FormatException('worker event must be a JSON object');
      }
      final event = WorkerEvent.fromJson(Map<String, Object?>.from(decoded));
      _handleEvent(event);
    } catch (error, stackTrace) {
      _markFatal(StateError('invalid worker stdout event: $error'), stackTrace);
    }
  }

  void _handleEvent(WorkerEvent event) {
    switch (event) {
      case StartupWorkerEvent():
        _handleStartup(event);
      case ReadyWorkerEvent():
        if (_status != WorkerStatus.warming) {
          throw const FormatException('ready event arrived out of order');
        }
        _status = WorkerStatus.ready;
        _startupMetrics = event.metrics;
        final start = _startCompleter;
        if (start == null || start.isCompleted) {
          throw const FormatException('ready event was emitted more than once');
        }
        start.complete();
      case ProgressWorkerEvent():
        _handleProgress(event);
      case ResultWorkerEvent():
        _handleResult(event);
      case WorkerErrorEvent():
        _handleWorkerError(event);
      case FatalWorkerEvent():
        _markFatal(
          StateError('worker fatal ${event.code}: ${event.message}'),
          null,
          event,
        );
        return;
      case StoppedWorkerEvent():
        _handleStopped(event);
      case PongWorkerEvent():
        throw const FormatException('unsolicited pong event');
    }
    _events.add(event);
  }

  void _handleStartup(StartupWorkerEvent event) {
    final expected = switch (event.status) {
      WorkerStatus.loading => WorkerStatus.starting,
      WorkerStatus.warming => WorkerStatus.loading,
      _ => throw const FormatException('invalid startup status'),
    };
    if (_status != expected) {
      throw const FormatException('startup event arrived out of order');
    }
    _status = event.status;
  }

  void _handleProgress(ProgressWorkerEvent event) {
    if (_status != WorkerStatus.ready ||
        !_pending.containsKey(event.requestId)) {
      throw const FormatException(
        'progress event does not match a pending request',
      );
    }
    final previous = _progress[event.requestId];
    final legal = switch (previous) {
      null => event.phase == WorkerPhase.detecting,
      WorkerPhase.detecting => event.phase == WorkerPhase.classifying,
      WorkerPhase.classifying =>
        event.phase == WorkerPhase.rechecking ||
            event.phase == WorkerPhase.aggregating,
      WorkerPhase.rechecking => event.phase == WorkerPhase.aggregating,
      WorkerPhase.aggregating => false,
    };
    if (!legal) {
      throw const FormatException('progress event arrived out of order');
    }
    _progress[event.requestId] = event.phase;
  }

  void _handleResult(ResultWorkerEvent event) {
    final requestId = event.result.requestId;
    final completer = _pending[requestId];
    if (completer == null || _progress[requestId] != WorkerPhase.aggregating) {
      throw const FormatException(
        'result does not match terminal progress for a pending request',
      );
    }
    _pending.remove(requestId);
    _progress.remove(requestId);
    completer.complete(event.result);
  }

  void _handleWorkerError(WorkerErrorEvent event) {
    _lastWorkerError = event;
    final requestId = event.requestId;
    if (requestId == null) {
      throw FormatException(
        'uncorrelated worker error ${event.code}: ${event.message}',
      );
    }
    final completer = _pending.remove(requestId);
    _progress.remove(requestId);
    if (completer == null) {
      throw const FormatException(
        'worker error does not match a pending request',
      );
    }
    completer.completeError(WorkerRequestException(event.code, event.message));
  }

  void _handleStopped(StoppedWorkerEvent event) {
    if (!_shuttingDown || event.requestId != _shutdownRequestId) {
      throw const FormatException('stopped event is not shutdown-correlated');
    }
    _status = WorkerStatus.stopped;
    final stopped = _stoppedCompleter;
    if (stopped == null || stopped.isCompleted) {
      throw const FormatException('stopped event was emitted more than once');
    }
    stopped.complete();
  }

  void _onProcessExit(int exitCode) {
    if (_status == WorkerStatus.stopped || _shuttingDown) {
      final stopped = _stoppedCompleter;
      if (stopped != null && !stopped.isCompleted) {
        stopped.complete();
      }
      return;
    }
    if (_status != WorkerStatus.fatal) {
      _markFatal(
        StateError('inference worker exited unexpectedly with code $exitCode'),
      );
    }
  }

  void _markFatal(
    Object error, [
    StackTrace? stackTrace,
    FatalWorkerEvent? observableEvent,
    bool transitionFromStopped = false,
  ]) {
    if (_status == WorkerStatus.fatal ||
        (_status == WorkerStatus.stopped && !transitionFromStopped)) {
      return;
    }
    _status = WorkerStatus.fatal;
    final fatal =
        observableEvent ??
        FatalWorkerEvent(code: 'client_fatal', message: error.toString());
    _fatalEvent = fatal;
    _events.add(fatal);
    final start = _startCompleter;
    if (start != null && !start.isCompleted) {
      start.completeError(error, stackTrace);
    }
    _completePending(error, stackTrace);
  }

  void _completePending(Object error, [StackTrace? stackTrace]) {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) {
        completer.completeError(error, stackTrace);
      }
    }
    _pending.clear();
    _progress.clear();
  }

  void _writeRequest(Map<String, Object?> request) {
    final process = _process;
    if (process == null) {
      throw StateError('inference worker process is not owned');
    }
    process.writeLine(jsonEncode(request));
  }

  String _nextRequestId(String prefix) {
    _requestSequence += 1;
    return '$prefix-$_requestSequence';
  }

  void _appendDiagnostic(String line) {
    _diagnostics.add(line);
    if (_diagnostics.length > 200) {
      _diagnostics.removeRange(0, _diagnostics.length - 200);
    }
  }

  static Future<WorkerProcessAdapter> _startOwnedProcess(
    InferenceLaunchConfig config,
  ) async {
    final process = await Process.start(
      config.pythonExecutable,
      config.arguments,
      runInShell: false,
      environment: const {'PYTHONDONTWRITEBYTECODE': '1'},
    );
    return _IoWorkerProcessAdapter(process);
  }
}

final class _IoWorkerProcessAdapter implements WorkerProcessAdapter {
  const _IoWorkerProcessAdapter(this._process);

  final Process _process;

  @override
  Stream<List<int>> get stdout => _process.stdout;

  @override
  Stream<List<int>> get stderr => _process.stderr;

  @override
  Future<int> get exitCode => _process.exitCode;

  @override
  void writeLine(String line) {
    _process.stdin.writeln(line);
  }

  @override
  bool kill() => _process.kill();
}
