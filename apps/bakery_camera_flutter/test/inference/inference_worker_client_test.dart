import 'dart:async';
import 'dart:convert';

import 'package:bakery_camera_prototype/src/inference/inference_launch_config.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/inference/inference_worker_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late FakeWorkerProcess ownedProcess;
  late FakeWorkerProcess unrelatedProcess;
  late InferenceWorkerClient client;

  setUp(() {
    ownedProcess = FakeWorkerProcess();
    unrelatedProcess = FakeWorkerProcess();
    client = InferenceWorkerClient(
      config: InferenceLaunchConfig.fromEnvironment(const {
        'BAKERY_INFERENCE_PYTHON': r'C:\runtime & tools\python.exe',
        'BAKERY_REPO_ROOT': r'C:\repo & literal',
      }),
      startProcess: (_) async => ownedProcess,
      shutdownTimeout: const Duration(milliseconds: 5),
    );
  });

  tearDown(() async {
    await ownedProcess.close();
    await unrelatedProcess.close();
  });

  test('analysis is rejected until the worker emits ready', () async {
    final start = client.start();
    await _pump();

    expect(() => client.analyze(r'C:\captures\frame.jpg'), throwsStateError);

    ownedProcess.emitJson({'type': 'loading'});
    await _pump();
    expect(client.status, WorkerStatus.loading);
    ownedProcess.emitJson({'type': 'warming', 'device': 'cpu'});
    await _pump();
    expect(client.status, WorkerStatus.warming);
    ownedProcess.emitJson(_readyJson());
    await _pump();
    expect(client.status, WorkerStatus.ready);
    await start;

    expect(client.status, WorkerStatus.ready);
  });

  test('start exposes typed startup events in protocol order', () async {
    final events = <WorkerEvent>[];
    client.events.listen(events.add);
    final start = client.start();
    await _pump();

    ownedProcess.emitJson({'type': 'loading'});
    ownedProcess.emitJson({'type': 'warming', 'device': 'cpu'});
    ownedProcess.emitJson(_readyJson());
    await start;

    expect(events.map((event) => event.runtimeType), [
      StartupWorkerEvent,
      StartupWorkerEvent,
      ReadyWorkerEvent,
    ]);
  });

  test('progress phases remain ordered and request-correlated', () async {
    await _startReady(client, ownedProcess);
    final progress = <ProgressWorkerEvent>[];
    client.events
        .where((event) => event is ProgressWorkerEvent)
        .cast<ProgressWorkerEvent>()
        .listen(progress.add);

    final analysis = client.analyze(r'C:\captures\frame.jpg');
    final request = jsonDecode(ownedProcess.sentLines.single);
    final requestId = request['request_id'] as String;
    for (final phase in ['detecting', 'classifying', 'aggregating']) {
      ownedProcess.emitJson({
        'type': 'progress',
        'request_id': requestId,
        'phase': phase,
      });
    }
    ownedProcess.emitJson(_resultJson(requestId));

    await analysis;
    expect(progress.map((event) => event.requestId), everyElement(requestId));
    expect(progress.map((event) => event.phase), [
      WorkerPhase.detecting,
      WorkerPhase.classifying,
      WorkerPhase.aggregating,
    ]);
  });

  test('out-of-order progress makes the client fatal', () async {
    await _startReady(client, ownedProcess);
    final analysis = client.analyze(r'C:\captures\frame.jpg');
    final requestId =
        (jsonDecode(ownedProcess.sentLines.single) as Map)['request_id']
            as String;

    ownedProcess.emitJson({
      'type': 'progress',
      'request_id': requestId,
      'phase': 'classifying',
    });

    await expectLater(analysis, throwsStateError);
    expect(client.status, WorkerStatus.fatal);
  });

  test('result completers correlate by request ID', () async {
    await _startReady(client, ownedProcess);

    final first = client.analyze(r'C:\captures\first.jpg');
    final second = client.analyze(r'C:\captures\second.jpg');
    final firstId =
        (jsonDecode(ownedProcess.sentLines[0]) as Map)['request_id'] as String;
    final secondId =
        (jsonDecode(ownedProcess.sentLines[1]) as Map)['request_id'] as String;
    _emitCompleteProgress(ownedProcess, firstId);
    _emitCompleteProgress(ownedProcess, secondId);
    ownedProcess.emitJson(_resultJson(secondId));
    ownedProcess.emitJson(_resultJson(firstId));

    expect((await first).requestId, firstId);
    expect((await second).requestId, secondId);
  });

  test('malformed stdout makes the client fatal', () async {
    final fatalEvents = <FatalWorkerEvent>[];
    final observedStatuses = <WorkerStatus>[];
    client.events
        .where((event) => event is FatalWorkerEvent)
        .cast<FatalWorkerEvent>()
        .listen((event) {
          fatalEvents.add(event);
          observedStatuses.add(client.status);
        });
    final start = client.start();
    await _pump();

    ownedProcess.emitStdout('{not json}\n');

    await expectLater(start, throwsStateError);
    expect(client.status, WorkerStatus.fatal);
    expect(fatalEvents, hasLength(1));
    expect(fatalEvents.single.code, 'client_fatal');
    expect(fatalEvents.single.message, contains('invalid worker stdout event'));
    expect(observedStatuses, [WorkerStatus.fatal]);
  });

  test('stderr retains only the newest 200 diagnostic lines', () async {
    final start = client.start();
    await _pump();
    ownedProcess.emitJson({'type': 'loading'});
    final diagnostics = List.generate(
      205,
      (index) => 'diagnostic-${index + 1}',
    ).join('\n');
    ownedProcess.emitStderr('$diagnostics\n');
    ownedProcess.emitJson({'type': 'warming', 'device': 'cpu'});
    ownedProcess.emitJson(_readyJson());
    await start;
    await _pump();

    expect(client.diagnostics, hasLength(200));
    expect(client.diagnostics.first, 'diagnostic-6');
    expect(client.diagnostics.last, 'diagnostic-205');
  });

  test('shutdown kills only its owned child after graceful timeout', () async {
    await _startReady(client, ownedProcess);

    await client.shutdown();

    expect(ownedProcess.killCalls, 1);
    expect(unrelatedProcess.killCalls, 0);
    expect(jsonDecode(ownedProcess.sentLines.last)['type'], 'shutdown');
    expect(client.status, WorkerStatus.stopped);
  });

  test('shutdown kill failure emits an observable fatal transition', () async {
    ownedProcess.killResult = false;
    final fatalEvents = <FatalWorkerEvent>[];
    client.events
        .where((event) => event is FatalWorkerEvent)
        .cast<FatalWorkerEvent>()
        .listen(fatalEvents.add);
    await _startReady(client, ownedProcess);

    await expectLater(client.shutdown(), throwsStateError);

    expect(client.status, WorkerStatus.fatal);
    expect(fatalEvents, hasLength(1));
    expect(fatalEvents.single.code, 'client_fatal');
    expect(
      fatalEvents.single.message,
      contains('owned inference worker could not be killed'),
    );
  });

  test(
    'stopped acknowledgement followed by exit failure remains observable',
    () async {
      ownedProcess.completeExitOnKill = false;
      ownedProcess.killResult = false;
      final fatalEvents = <FatalWorkerEvent>[];
      client.events
          .where((event) => event is FatalWorkerEvent)
          .cast<FatalWorkerEvent>()
          .listen(fatalEvents.add);
      await _startReady(client, ownedProcess);

      final shutdown = client.shutdown();
      final shutdownRequest =
          jsonDecode(ownedProcess.sentLines.last) as Map<String, Object?>;
      ownedProcess.emitJson({
        'type': 'stopped',
        'request_id': shutdownRequest['request_id'],
      });

      await expectLater(shutdown, throwsStateError);
      expect(ownedProcess.killCalls, 1);
      expect(client.status, WorkerStatus.fatal);
      expect(fatalEvents, hasLength(1));
      expect(fatalEvents.single.code, 'client_fatal');
      expect(
        fatalEvents.single.message,
        contains('owned inference worker could not be killed'),
      );
    },
  );

  test(
    'shutdown owns a child that finishes starting during shutdown',
    () async {
      final delayedStart = Completer<WorkerProcessAdapter>();
      client = InferenceWorkerClient(
        config: InferenceLaunchConfig.fromEnvironment(const {
          'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
          'BAKERY_REPO_ROOT': r'C:\repo',
        }),
        startProcess: (_) => delayedStart.future,
        shutdownTimeout: const Duration(milliseconds: 20),
      );

      final start = client.start();
      final startExpectation = expectLater(start, throwsStateError);
      await _pump();
      var shutdownCompleted = false;
      final shutdown = client.shutdown().whenComplete(() {
        shutdownCompleted = true;
      });
      await _pump();
      final completedBeforeChildWasOwned = shutdownCompleted;
      delayedStart.complete(ownedProcess);

      await startExpectation.timeout(const Duration(milliseconds: 100));
      await shutdown.timeout(const Duration(milliseconds: 100));
      expect(completedBeforeChildWasOwned, isFalse);
      expect(ownedProcess.killCalls, 1);
      expect(unrelatedProcess.killCalls, 0);
      expect(client.status, WorkerStatus.stopped);
    },
  );

  test('shutdown and start settle when the starter never resolves', () async {
    final delayedStart = Completer<WorkerProcessAdapter>();
    client = InferenceWorkerClient(
      config: InferenceLaunchConfig.fromEnvironment(const {
        'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
        'BAKERY_REPO_ROOT': r'C:\repo',
      }),
      startProcess: (_) => delayedStart.future,
      shutdownTimeout: const Duration(milliseconds: 5),
    );

    final start = client.start();
    final startExpectation = expectLater(start, throwsStateError);
    await _pump();
    final firstShutdown = client.shutdown();
    final concurrentShutdown = client.shutdown();

    await Future.wait([
      firstShutdown,
      concurrentShutdown,
    ]).timeout(const Duration(milliseconds: 100));
    await startExpectation.timeout(const Duration(milliseconds: 100));
    expect(client.status, WorkerStatus.stopped);
    expect(ownedProcess.killCalls, 0);
    expect(unrelatedProcess.killCalls, 0);
  });

  test(
    'a child returned after bounded shutdown is still killed once',
    () async {
      final delayedStart = Completer<WorkerProcessAdapter>();
      client = InferenceWorkerClient(
        config: InferenceLaunchConfig.fromEnvironment(const {
          'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
          'BAKERY_REPO_ROOT': r'C:\repo',
        }),
        startProcess: (_) => delayedStart.future,
        shutdownTimeout: const Duration(milliseconds: 5),
      );

      final start = client.start();
      final startErrorFuture = start.then<Object?>(
        (_) => null,
        onError: (Object error) => error,
      );
      await _pump();
      await client.shutdown().timeout(const Duration(milliseconds: 100));
      final startError = await startErrorFuture.timeout(
        const Duration(milliseconds: 20),
      );
      delayedStart.complete(ownedProcess);
      await _pump();
      await _pump();

      expect(startError, isA<StateError>());
      expect(ownedProcess.killCalls, 1);
      expect(unrelatedProcess.killCalls, 0);
      expect(client.status, WorkerStatus.stopped);
    },
  );

  test(
    'late cancelled-start kill failure transitions stopped client to fatal',
    () async {
      final delayedStart = Completer<WorkerProcessAdapter>();
      ownedProcess.killResult = false;
      client = InferenceWorkerClient(
        config: InferenceLaunchConfig.fromEnvironment(const {
          'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
          'BAKERY_REPO_ROOT': r'C:\repo',
        }),
        startProcess: (_) => delayedStart.future,
        shutdownTimeout: const Duration(milliseconds: 5),
      );
      final fatalEvents = <FatalWorkerEvent>[];
      client.events
          .where((event) => event is FatalWorkerEvent)
          .cast<FatalWorkerEvent>()
          .listen(fatalEvents.add);

      final startError = client.start().then<Object?>(
        (_) => null,
        onError: (Object error) => error,
      );
      await _pump();
      await client.shutdown().timeout(const Duration(milliseconds: 100));
      expect(await startError, isA<StateError>());
      expect(client.status, WorkerStatus.stopped);

      delayedStart.complete(ownedProcess);
      await _pump();
      await _pump();

      expect(ownedProcess.killCalls, 1);
      expect(client.status, WorkerStatus.fatal);
      expect(fatalEvents, hasLength(1));
      expect(fatalEvents.single.code, 'client_fatal');
      expect(
        fatalEvents.single.message,
        contains('owned inference worker could not be killed'),
      );
    },
  );

  test('shutdown settles when killed child never reports exit', () async {
    ownedProcess.completeExitOnKill = false;
    await _startReady(client, ownedProcess);

    final firstShutdown = client.shutdown();
    final concurrentShutdown = client.shutdown();

    await Future.wait([
      firstShutdown,
      concurrentShutdown,
    ]).timeout(const Duration(milliseconds: 100));
    expect(ownedProcess.killCalls, 1);
    expect(unrelatedProcess.killCalls, 0);
    expect(client.status, WorkerStatus.stopped);
  });
}

Future<void> _startReady(
  InferenceWorkerClient client,
  FakeWorkerProcess process,
) async {
  final start = client.start();
  await _pump();
  process.emitJson({'type': 'loading'});
  process.emitJson({'type': 'warming', 'device': 'cpu'});
  process.emitJson(_readyJson());
  await start;
}

void _emitCompleteProgress(FakeWorkerProcess process, String requestId) {
  for (final phase in ['detecting', 'classifying', 'aggregating']) {
    process.emitJson({
      'type': 'progress',
      'request_id': requestId,
      'phase': phase,
    });
  }
}

Map<String, Object?> _readyJson() {
  return {
    'type': 'ready',
    'device': 'cpu',
    'startup_metrics': {
      'device': 'cpu',
      'load_ms': 12.5,
      'warmup_ms': 7.0,
      'fallback_reason': null,
      'detector_id': 'rfdetr_large_bakery_v1',
      'repvit_id': 'repvit_m1_15plus5_v1',
      'dinov3_id': 'dinov3_vits16_15plus5_v1',
      'fusion_policy_id': 'fusion_local_or_global_v1',
      'detector_threshold': 0.42,
    },
  };
}

Map<String, Object?> _resultJson(String requestId) {
  return {
    'type': 'result',
    'request_id': requestId,
    'image': {'width': 640, 'height': 480},
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
  };
}

Future<void> _pump() => Future<void>.delayed(Duration.zero);

final class FakeWorkerProcess implements WorkerProcessAdapter {
  final _stdout = StreamController<List<int>>();
  final _stderr = StreamController<List<int>>();
  final _exitCode = Completer<int>();
  final sentLines = <String>[];
  int killCalls = 0;
  bool completeExitOnKill = true;
  bool killResult = true;

  @override
  Stream<List<int>> get stdout => _stdout.stream;

  @override
  Stream<List<int>> get stderr => _stderr.stream;

  @override
  Future<int> get exitCode => _exitCode.future;

  @override
  void writeLine(String line) {
    sentLines.add(line);
  }

  @override
  bool kill() {
    killCalls += 1;
    if (killResult && completeExitOnKill && !_exitCode.isCompleted) {
      _exitCode.complete(137);
    }
    return killResult;
  }

  void emitJson(Map<String, Object?> event) {
    emitStdout('${jsonEncode(event)}\n');
  }

  void emitStdout(String text) {
    _stdout.add(utf8.encode(text));
  }

  void emitStderr(String text) {
    _stderr.add(utf8.encode(text));
  }

  Future<void> close() async {
    if (!_exitCode.isCompleted) {
      _exitCode.complete(0);
    }
    unawaited(_stdout.close());
    unawaited(_stderr.close());
  }
}
