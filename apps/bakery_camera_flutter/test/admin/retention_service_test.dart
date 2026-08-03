import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/admin/retention_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late BakeryDatabase database;
  late Directory root;
  late RetentionService service;

  setUp(() async {
    database = openInMemoryBakeryDatabase();
    await CatalogSeed(database).installIfEmpty();
    root = await Directory.systemTemp.createTemp('retention-service-');
    service = RetentionService(
      database: database,
      evidenceRoot: root,
      createId: () => 'retention-v1',
      now: () => DateTime.utc(2026, 7, 31, 9),
    );
    await _seedEvidence(database, root);
  });
  tearDown(() async {
    await database.close();
    if (await root.exists()) await root.delete(recursive: true);
  });

  test(
    'preview and execution retain immutable metadata for the exact files',
    () async {
      final preview = await service.preview(DateTime.utc(2026, 7, 1));

      expect(preview.files, hasLength(1));
      expect(preview.affectedSessionIds, ['retention-session']);
      expect(preview.totalByteSize, utf8.encode('old-evidence').length);
      final result = await service.execute(preview.previewId);

      expect(result.filesRemoved, preview.files.length);
      expect(result.bytesRemoved, preview.totalByteSize);
      expect(
        await File(
          '${root.path}${Platform.pathSeparator}sessions${Platform.pathSeparator}retention-session${Platform.pathSeparator}attempt-001.jpg',
        ).exists(),
        isFalse,
      );
      final record = await database
          .select(database.retentionEvents)
          .getSingle();
      expect(record.attemptId, 'retention-attempt');
      expect(record.relativePath, 'sessions/retention-session/attempt-001.jpg');
      expect(
        record.originalSha256,
        sha256.convert(utf8.encode('old-evidence')).toString(),
      );
      final events = await database.select(database.auditEvents).get();
      expect(
        events.map((event) => event.eventType),
        containsAll(['retention_pending', 'retention_executed']),
      );
    },
  );

  test('execution refuses a preview when the verified file changed', () async {
    final preview = await service.preview(DateTime.utc(2026, 7, 1));
    final file = File(
      '${root.path}${Platform.pathSeparator}sessions${Platform.pathSeparator}retention-session${Platform.pathSeparator}attempt-001.jpg',
    );
    await file.writeAsString('different bytes');

    await expectLater(
      () => service.execute(preview.previewId),
      throwsStateError,
    );
    expect(await file.exists(), isTrue);
    expect(await database.select(database.retentionEvents).get(), isEmpty);
  });

  test(
    'restart recovery restores an uncommitted quarantine before a new preview',
    () async {
      final source = File(
        '${root.path}${Platform.pathSeparator}sessions${Platform.pathSeparator}retention-session${Platform.pathSeparator}attempt-001.jpg',
      );
      final quarantine = File(
        '${root.path}${Platform.pathSeparator}retention-quarantine${Platform.pathSeparator}interrupted-preview${Platform.pathSeparator}sessions${Platform.pathSeparator}retention-session${Platform.pathSeparator}attempt-001.jpg',
      );
      await quarantine.parent.create(recursive: true);
      await source.rename(quarantine.path);

      final restarted = RetentionService(
        database: database,
        evidenceRoot: root,
        createId: () => 'retention-restarted',
        now: () => DateTime.utc(2026, 7, 31, 10),
      );
      final preview = await restarted.preview(DateTime.utc(2026, 7, 1));

      expect(preview.files, hasLength(1));
      expect(await source.exists(), isTrue);
      expect(await quarantine.exists(), isFalse);
      final result = await restarted.execute(preview.previewId);
      expect(result.filesRemoved, 1);
      expect(await source.exists(), isFalse);
      expect(
        (await database.select(database.auditEvents).get()).map(
          (event) => event.eventType,
        ),
        containsAll(['retention_recovered', 'retention_executed']),
      );
    },
  );

  test(
    'the same preview retries after a metadata failure without losing evidence',
    () async {
      var failMetadataOnce = true;
      service = RetentionService(
        database: database,
        evidenceRoot: root,
        createId: () => 'retention-v1',
        now: () => DateTime.utc(2026, 7, 31, 9),
        beforeMetadataCommit: () async {
          if (!failMetadataOnce) return;
          failMetadataOnce = false;
          throw StateError('injected metadata failure');
        },
      );
      final preview = await service.preview(DateTime.utc(2026, 7, 1));
      final source = File(
        '${root.path}${Platform.pathSeparator}sessions${Platform.pathSeparator}retention-session${Platform.pathSeparator}attempt-001.jpg',
      );

      await expectLater(
        () => service.execute(preview.previewId),
        throwsStateError,
      );
      expect(await source.exists(), isTrue);
      expect(await database.select(database.retentionEvents).get(), isEmpty);

      final result = await service.execute(preview.previewId);
      expect(result.filesRemoved, 1);
      expect(await source.exists(), isFalse);
      expect(
        (await database.select(database.auditEvents).get()).map(
          (event) => event.eventType,
        ),
        containsAll([
          'retention_pending',
          'retention_partial_failure',
          'retention_recovered',
          'retention_executed',
        ]),
      );
    },
  );
}

Future<void> _seedEvidence(BakeryDatabase database, Directory root) async {
  final catalog = await database.select(database.catalogRevisions).getSingle();
  await database
      .into(database.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: 'retention-session',
          state: 'active',
          startedAtUs: DateTime.utc(2026, 6, 1).microsecondsSinceEpoch,
          catalogRevisionId: catalog.revisionId,
          settingsRevisionId: 'settings-v1',
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _hash('a'),
          repvitArtifactId: 'repvit_m1_15plus5_v1',
          repvitSha256: _hash('b'),
          repvitManifestSha256: _hash('c'),
          repvitPrototypeSha256: _hash('d'),
          dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _hash('e'),
          dinov3SupportSha256: _hash('f'),
          calibrationId: 'calibration-v1',
          calibrationSha256: _hash('0'),
          preprocessSha256: _hash('1'),
          fusionPolicyId: 'fusion-v1',
          fusionPolicySha256: _hash('2'),
          configSnapshotJson: '{"pipeline":"canonical_cpu"}',
        ),
      );
  const relativePath = 'sessions/retention-session/attempt-001.jpg';
  final file = File(
    '${root.path}${Platform.pathSeparator}${relativePath.replaceAll('/', Platform.pathSeparator)}',
  );
  await file.parent.create(recursive: true);
  await file.writeAsString('old-evidence');
  final bytes = await file.readAsBytes();
  await database
      .into(database.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: 'retention-attempt',
          sessionId: 'retention-session',
          attemptNumber: 1,
          capturedAtUs: DateTime.utc(2026, 6, 1).microsecondsSinceEpoch,
          imageRelativePath: relativePath,
          imageByteSize: bytes.length,
          imageSha256: sha256.convert(bytes).toString(),
          status: 'staged',
        ),
      );
}

String _hash(String value) => value * 64;
