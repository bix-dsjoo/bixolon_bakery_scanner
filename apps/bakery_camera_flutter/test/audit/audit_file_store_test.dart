import 'dart:io';

import 'package:bakery_camera_prototype/src/audit/audit_file_store.dart';
import 'package:bakery_camera_prototype/src/audit/canonical_json_encoder.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/persistence/database_checkout_audit_store.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory temporaryDirectory;
  late Directory auditRoot;
  late File source;
  late AuditFileStore store;

  setUp(() async {
    temporaryDirectory = await Directory.systemTemp.createTemp('audit-store-');
    auditRoot = Directory(
      '${temporaryDirectory.path}${Platform.pathSeparator}audit',
    );
    source = File(
      '${temporaryDirectory.path}${Platform.pathSeparator}capture.jpg',
    );
    await source.writeAsBytes(const [1, 2, 3, 4], flush: true);
    store = AuditFileStore(auditRoot);
  });

  tearDown(() async {
    await temporaryDirectory.delete(recursive: true);
  });

  test('stores bytes under session attempt with verified metadata', () async {
    final stored = await store.retainCapture(
      sessionId: '00000000-0000-4000-8000-000000000001',
      attemptNumber: 1,
      capturedAtUtc: DateTime.utc(2026, 7, 30, 1, 2, 3),
      sourcePath: source.path,
    );

    expect(
      stored.relativePath,
      'sessions/2026/07/30/00000000-0000-4000-8000-000000000001/'
      'attempt-001.jpg',
    );
    expect(stored.byteSize, 4);
    expect(stored.sha256, sha256.convert([1, 2, 3, 4]).toString());
    expect(await File(store.resolve(stored.relativePath)).readAsBytes(), [
      1,
      2,
      3,
      4,
    ]);
    expect(await source.exists(), isTrue);
  });

  test('returns an existing matching capture without overwriting it', () async {
    final first = await store.retainCapture(
      sessionId: '00000000-0000-4000-8000-000000000001',
      attemptNumber: 1,
      capturedAtUtc: DateTime.utc(2026, 7, 30),
      sourcePath: source.path,
    );
    await source.writeAsBytes(const [1, 2, 3, 4], flush: true);

    final second = await store.retainCapture(
      sessionId: '00000000-0000-4000-8000-000000000001',
      attemptNumber: 1,
      capturedAtUtc: DateTime.utc(2026, 7, 30),
      sourcePath: source.path,
    );

    expect(second.relativePath, first.relativePath);
    expect(second.sha256, first.sha256);
  });

  test(
    'fails closed when an existing capture differs from the source',
    () async {
      await store.retainCapture(
        sessionId: '00000000-0000-4000-8000-000000000001',
        attemptNumber: 1,
        capturedAtUtc: DateTime.utc(2026, 7, 30),
        sourcePath: source.path,
      );
      await source.writeAsBytes(const [9, 9, 9, 9], flush: true);

      await expectLater(
        store.retainCapture(
          sessionId: '00000000-0000-4000-8000-000000000001',
          attemptNumber: 1,
          capturedAtUtc: DateTime.utc(2026, 7, 30),
          sourcePath: source.path,
        ),
        throwsA(isA<StateError>()),
      );
    },
  );

  test(
    'rejects identifiers and paths that could escape the audit root',
    () async {
      await expectLater(
        store.retainCapture(
          sessionId: '..',
          attemptNumber: 1,
          capturedAtUtc: DateTime.utc(2026, 7, 30),
          sourcePath: source.path,
        ),
        throwsArgumentError,
      );
      expect(() => store.resolve('../outside.jpg'), throwsArgumentError);
    },
  );

  test(
    'rejects an empty capture instead of retaining unusable evidence',
    () async {
      await source.writeAsBytes(const [], flush: true);

      await expectLater(
        store.retainCapture(
          sessionId: '00000000-0000-4000-8000-000000000001',
          attemptNumber: 1,
          capturedAtUtc: DateTime.utc(2026, 7, 30),
          sourcePath: source.path,
        ),
        throwsA(isA<StateError>()),
      );
    },
  );

  test('flags pending files for recovery without deleting them', () async {
    final pending = File(
      '${auditRoot.path}${Platform.pathSeparator}sessions'
      '${Platform.pathSeparator}2026${Platform.pathSeparator}07'
      '${Platform.pathSeparator}30${Platform.pathSeparator}'
      '00000000-0000-4000-8000-000000000001'
      '${Platform.pathSeparator}attempt-001.jpg.pending',
    );
    await pending.parent.create(recursive: true);
    await pending.writeAsBytes(const [1, 2, 3, 4], flush: true);

    final orphans = await store.findRecoveryCandidates();

    expect(orphans, [endsWith('attempt-001.jpg.pending')]);
    expect(await pending.exists(), isTrue);
  });

  test(
    'retains a canonical inference receipt through the database boundary',
    () async {
      const sessionId = '00000000-0000-4000-8000-000000000001';
      final receiptJson = canonicalJsonEncode({
        'z': 1.0,
        'a': {'second': 2, 'first': true},
      });
      final receipt = ImmutableJsonReceipt(
        canonicalJson: receiptJson,
        sha256: sha256.convert(receiptJson.codeUnits).toString(),
      );

      final reference = await AuditFileStoreReferenceVerifier(store)
          .inferenceReceipt(
            sessionId: sessionId,
            attemptNumber: 1,
            capturedAtUtc: DateTime.utc(2026, 7, 30),
            receipt: receipt,
          );

      expect(
        reference.relativePath,
        'sessions/2026/07/30/$sessionId/attempt-001.inference.json',
      );
      expect(
        await File(store.resolve(reference.relativePath)).readAsString(),
        '{"a":{"first":true,"second":2},"z":1}',
      );
    },
  );

  test('bridge accepts only the exact staged capture location', () async {
    const sessionId = '00000000-0000-4000-8000-000000000001';
    const otherSessionId = '00000000-0000-4000-8000-000000000002';
    final capturedAt = DateTime.utc(2026, 7, 30);
    final stored = await store.retainCapture(
      sessionId: sessionId,
      attemptNumber: 1,
      capturedAtUtc: capturedAt,
      sourcePath: source.path,
    );
    final bridge = AuditFileStoreReferenceVerifier(store);
    final image = CapturedAuditFile(
      fileId: 'capture-1',
      path: stored.relativePath,
      sha256: stored.sha256,
    );

    final verified = await bridge.capturedImage(
      sessionId: sessionId,
      attemptNumber: 1,
      capturedAtUtc: capturedAt,
      image: image,
    );

    expect(verified.relativePath, stored.relativePath);
    await expectLater(
      bridge.capturedImage(
        sessionId: otherSessionId,
        attemptNumber: 1,
        capturedAtUtc: capturedAt,
        image: image,
      ),
      throwsA(isA<StateError>()),
    );
  });

  test(
    'persists a recovery marker without deleting retained evidence',
    () async {
      final stored = await store.retainCapture(
        sessionId: '00000000-0000-4000-8000-000000000001',
        attemptNumber: 1,
        capturedAtUtc: DateTime.utc(2026, 7, 30),
        sourcePath: source.path,
      );

      await store.recordDatabaseFailure(
        operation: 'stage_attempt',
        file: stored,
        error: StateError('injected database failure'),
      );

      final marker = File(
        '${auditRoot.path}${Platform.pathSeparator}recovery'
        '${Platform.pathSeparator}markers.jsonl',
      );
      expect(
        await marker.readAsString(),
        contains('"operation":"stage_attempt"'),
      );
      expect(await File(store.resolve(stored.relativePath)).exists(), isTrue);
    },
  );

  test(
    'recovery scan flags an unreferenced canonical final and honors a marker',
    () async {
      final stored = await store.retainCapture(
        sessionId: '00000000-0000-4000-8000-000000000001',
        attemptNumber: 1,
        capturedAtUtc: DateTime.utc(2026, 7, 30),
        sourcePath: source.path,
      );

      expect(await store.findRecoveryCandidates(), [stored.relativePath]);

      await store.recordDatabaseFailure(
        operation: 'stage_attempt',
        file: stored,
        error: StateError('injected database failure'),
      );

      expect(await store.findRecoveryCandidates(), isEmpty);
      expect(
        await store.findRecoveryCandidates(
          referencedRelativePaths: [stored.relativePath],
        ),
        isEmpty,
      );
      expect(await File(store.resolve(stored.relativePath)).exists(), isTrue);
    },
  );
}
