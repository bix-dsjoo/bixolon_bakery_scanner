import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late BakeryDatabase db;

  setUp(() {
    db = openInMemoryBakeryDatabase();
  });

  tearDown(() async {
    await db.close();
  });

  test('schema version 3 installs immutable operational settings', () async {
    final settings = await db.select(db.settingsRevisions).getSingle();
    final pointer = await db.select(db.appSettings).getSingle();
    final diagnostics = await db.diagnostics();

    expect(db.schemaVersion, 3);
    expect(settings.revisionId, 'settings-v1');
    expect(settings.retryLimit, 2);
    expect(settings.paymentCompleteDurationSeconds, 4);
    expect(settings.customerAutoReset, isTrue);
    expect(settings.evidenceRetentionDays, 90);
    expect(settings.locale, 'ko-KR');
    expect(settings.kioskDisplayName, 'BIXOLON Bakery');
    expect(settings.adminAuthorLabel, 'prototype-admin');
    expect(pointer.activeSettingsRevisionId, 'settings-v1');
    expect(diagnostics.schemaVersion, 3);
    expect(diagnostics.applicationVersion, '1.1.0+4');
    expect(diagnostics.lastMigrationResult, 'created_schema_v3');
  });

  test(
    'schema version 1 upgrades checkout history without rewriting it',
    () async {
      final previousWarningSetting =
          driftRuntimeOptions.dontWarnAboutMultipleDatabases;
      driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
      addTearDown(() {
        driftRuntimeOptions.dontWarnAboutMultipleDatabases =
            previousWarningSetting;
      });
      final directory = await Directory.systemTemp.createTemp(
        'bakery-v1-upgrade-',
      );
      final file = File('${directory.path}${Platform.pathSeparator}scanner.db');
      addTearDown(() async {
        if (directory.existsSync()) await directory.delete(recursive: true);
      });
      final original = BakeryDatabase(NativeDatabase(file));
      await original.select(original.appSettings).getSingle();
      await original
          .into(original.catalogRevisions)
          .insert(
            CatalogRevisionsCompanion.insert(
              revisionId: 'catalog-migration',
              sha256: _hash('a'),
              createdAtUs: 1,
              isActive: true,
            ),
          );
      await original
          .into(original.checkoutSessions)
          .insert(
            CheckoutSessionsCompanion.insert(
              sessionId: 'session-history',
              state: 'active',
              startedAtUs: 2,
              catalogRevisionId: 'catalog-migration',
              settingsRevisionId: 'settings-v1',
              detectorId: 'detector',
              detectorSha256: _hash('b'),
              repvitArtifactId: 'repvit',
              repvitSha256: _hash('c'),
              repvitManifestSha256: _hash('d'),
              repvitPrototypeSha256: _hash('e'),
              dinov3ArtifactId: 'dino',
              dinov3Sha256: _hash('f'),
              dinov3SupportSha256: _hash('0'),
              calibrationId: 'calibration',
              calibrationSha256: _hash('1'),
              preprocessSha256: _hash('2'),
              fusionPolicyId: 'policy',
              fusionPolicySha256: _hash('3'),
              configSnapshotJson: '{}',
            ),
          );
      await original.customStatement('DROP TABLE admin_review_annotations');
      await original.customStatement('PRAGMA user_version = 1');
      await original.close();

      final upgraded = BakeryDatabase(NativeDatabase(file));
      addTearDown(upgraded.close);
      expect(
        (await upgraded.select(upgraded.checkoutSessions).getSingle())
            .sessionId,
        'session-history',
      );
      expect(
        await upgraded.select(upgraded.adminReviewAnnotations).get(),
        isEmpty,
      );
      expect(
        (await upgraded.diagnostics()).lastMigrationResult,
        'migrated_1_to_3',
      );
    },
  );

  test(
    'schema version 2 preserves annotations and defaults the new conclusion',
    () async {
      final previousWarningSetting =
          driftRuntimeOptions.dontWarnAboutMultipleDatabases;
      driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
      addTearDown(() {
        driftRuntimeOptions.dontWarnAboutMultipleDatabases =
            previousWarningSetting;
      });
      final directory = await Directory.systemTemp.createTemp(
        'bakery-v2-upgrade-',
      );
      final file = File('${directory.path}${Platform.pathSeparator}scanner.db');
      addTearDown(() async {
        if (directory.existsSync()) await directory.delete(recursive: true);
      });
      final original = BakeryDatabase(NativeDatabase(file));
      await original.select(original.appSettings).getSingle();
      await original
          .into(original.catalogRevisions)
          .insert(
            CatalogRevisionsCompanion.insert(
              revisionId: 'catalog-v2-migration',
              sha256: _hash('a'),
              createdAtUs: 1,
              isActive: true,
            ),
          );
      await original
          .into(original.checkoutSessions)
          .insert(
            CheckoutSessionsCompanion.insert(
              sessionId: 'session-v2-history',
              state: 'active',
              startedAtUs: 2,
              catalogRevisionId: 'catalog-v2-migration',
              settingsRevisionId: 'settings-v1',
              detectorId: 'detector',
              detectorSha256: _hash('b'),
              repvitArtifactId: 'repvit',
              repvitSha256: _hash('c'),
              repvitManifestSha256: _hash('d'),
              repvitPrototypeSha256: _hash('e'),
              dinov3ArtifactId: 'dino',
              dinov3Sha256: _hash('f'),
              dinov3SupportSha256: _hash('0'),
              calibrationId: 'calibration',
              calibrationSha256: _hash('1'),
              preprocessSha256: _hash('2'),
              fusionPolicyId: 'policy',
              fusionPolicySha256: _hash('3'),
              configSnapshotJson: '{}',
            ),
          );
      await original.customStatement('DROP TABLE admin_review_annotations');
      await original.customStatement('''
CREATE TABLE admin_review_annotations (
  annotation_id TEXT NOT NULL PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES checkout_sessions(session_id),
  attempt_id TEXT NULL REFERENCES scan_attempts(attempt_id),
  object_id TEXT NULL REFERENCES inference_objects(inference_object_id),
  review_status TEXT NOT NULL CHECK (review_status IN ('open', 'reviewed', 'needs_follow_up')),
  correct_product_id TEXT NULL,
  reason_code TEXT NOT NULL,
  note TEXT NULL,
  author_label TEXT NOT NULL,
  created_at_us INTEGER NOT NULL
)
''');
      await original.customStatement('''
INSERT INTO admin_review_annotations (
  annotation_id, session_id, review_status, reason_code, author_label,
  created_at_us
) VALUES ('annotation-v2', 'session-v2-history', 'reviewed', 'catalog_issue', 'admin', 3)
''');
      await original.customStatement('PRAGMA user_version = 2');
      await original.close();

      final upgraded = BakeryDatabase(NativeDatabase(file));
      addTearDown(upgraded.close);
      final annotation = await upgraded
          .select(upgraded.adminReviewAnnotations)
          .getSingle();

      expect(annotation.annotationId, 'annotation-v2');
      expect(annotation.conclusionCode, 'ai_correct');
      expect(
        (await upgraded.diagnostics()).lastMigrationResult,
        'migrated_2_to_3',
      );
    },
  );

  test(
    'schema rejects a registered inference object without provenance',
    () async {
      await _seedAttempt(db);

      await expectLater(
        db
            .into(db.inferenceObjects)
            .insert(
              InferenceObjectsCompanion.insert(
                inferenceObjectId: 'attempt-1/object-1',
                attemptId: 'attempt-1',
                objectId: 'object-1',
                skuId: const Value(7),
                skuName: '소금빵',
                decisionPath: 'repvit_direct',
                confidence: 0.97,
                bboxJson: '[10,20,100,150]',
                detectorSource: 'rfdetr_large_bakery_v1',
                detectorScore: 0.95,
                provenanceJson: '{}',
                unknownReason: const Value(null),
              ),
            ),
        throwsA(isA<InvalidDataException>()),
      );
    },
  );

  test('schema enforces all-or-none product photo provenance', () async {
    await db
        .into(db.catalogRevisions)
        .insert(
          CatalogRevisionsCompanion.insert(
            revisionId: 'catalog-v1',
            sha256: _hash('a'),
            createdAtUs: 1,
            isActive: true,
          ),
        );

    await expectLater(
      db
          .into(db.products)
          .insert(
            ProductsCompanion.insert(
              productRevisionId: 'catalog-v1/product-1',
              catalogRevisionId: 'catalog-v1',
              productId: 'product-1',
              displayName: '소금빵',
              unitPriceKrw: 2800,
              recognitionSkuId: const Value(7),
              categoryId: 'bread',
              photoRelativePath: const Value('products/salt-bread.jpg'),
              active: true,
              sortOrder: 1,
            ),
          ),
      throwsA(isA<Exception>()),
    );
  });

  test('catalog repository reads only the active immutable revision', () async {
    await db
        .into(db.catalogRevisions)
        .insert(
          CatalogRevisionsCompanion.insert(
            revisionId: 'catalog-v1',
            sha256: _hash('a'),
            createdAtUs: 1,
            isActive: true,
          ),
        );
    await db
        .into(db.products)
        .insert(
          ProductsCompanion.insert(
            productRevisionId: 'catalog-v1/product-1',
            catalogRevisionId: 'catalog-v1',
            productId: 'product-1',
            displayName: '소금빵',
            unitPriceKrw: 2800,
            recognitionSkuId: const Value(7),
            categoryId: 'bread',
            active: true,
            sortOrder: 1,
          ),
        );
    final repository = DatabaseCatalogRepository(db);

    final catalog = await repository.activeCatalog();

    expect(catalog.revision.revisionId, 'catalog-v1');
    expect(catalog.products.single.productId, 'product-1');
    expect((await repository.productForRecognitionSku(7))?.displayName, '소금빵');
    expect(await repository.search('소금'), hasLength(1));
    expect(
      (await repository.customerDiscovery()).featuredProducts,
      hasLength(1),
    );
  });

  test('opening a newer database schema fails closed', () async {
    final previousWarningSetting =
        driftRuntimeOptions.dontWarnAboutMultipleDatabases;
    driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
    addTearDown(() {
      driftRuntimeOptions.dontWarnAboutMultipleDatabases =
          previousWarningSetting;
    });
    final directory = await Directory.systemTemp.createTemp(
      'bakery-newer-schema-',
    );
    final file = File('${directory.path}${Platform.pathSeparator}scanner.db');
    addTearDown(() async {
      if (directory.existsSync()) {
        await directory.delete(recursive: true);
      }
    });
    final original = BakeryDatabase(NativeDatabase(file));
    await original.select(original.appSettings).getSingle();
    await original.customStatement('PRAGMA user_version = 4');
    await original.close();
    final newer = BakeryDatabase(NativeDatabase(file));
    addTearDown(newer.close);

    await expectLater(
      newer.select(newer.appSettings).getSingle(),
      throwsA(isA<StateError>()),
    );
  });

  test('schema rejects non-hex hashes and unsafe audit paths', () async {
    await _seedAttempt(db);

    await expectLater(
      db
          .into(db.scanAttempts)
          .insert(
            ScanAttemptsCompanion.insert(
              attemptId: 'attempt-invalid-hash',
              sessionId: 'session-1',
              attemptNumber: 2,
              capturedAtUs: 4,
              imageRelativePath: 'sessions/session-1/attempt-002.jpg',
              imageByteSize: 42,
              imageSha256: 'g' * 64,
              status: 'staged',
            ),
          ),
      throwsA(isA<Exception>()),
    );
    await expectLater(
      db
          .into(db.scanAttempts)
          .insert(
            ScanAttemptsCompanion.insert(
              attemptId: 'attempt-unsafe-path',
              sessionId: 'session-1',
              attemptNumber: 3,
              capturedAtUs: 5,
              imageRelativePath: '../outside/attempt-003.jpg',
              imageByteSize: 42,
              imageSha256: _hash('5'),
              status: 'staged',
            ),
          ),
      throwsA(isA<Exception>()),
    );
  });

  test(
    'abandoned and interrupted sessions reject resurrection deletion and child writes',
    () async {
      await _seedAttempt(db);
      for (final state in ['abandoned', 'interrupted']) {
        final sessionId = 'session-$state';
        await _seedSession(db, sessionId);
        await (db.update(
          db.checkoutSessions,
        )..where((row) => row.sessionId.equals(sessionId))).write(
          CheckoutSessionsCompanion(
            state: Value(state),
            terminalAtUs: const Value(10),
            terminalReason: Value('$state-for-test'),
          ),
        );

        await expectLater(
          (db.update(
            db.checkoutSessions,
          )..where((row) => row.sessionId.equals(sessionId))).write(
            const CheckoutSessionsCompanion(
              state: Value('active'),
              terminalAtUs: Value(null),
              terminalReason: Value(null),
            ),
          ),
          throwsA(isA<Exception>()),
        );
        await expectLater(
          (db.delete(
            db.checkoutSessions,
          )..where((row) => row.sessionId.equals(sessionId))).go(),
          throwsA(isA<Exception>()),
        );
        await expectLater(
          db
              .into(db.scanAttempts)
              .insert(
                ScanAttemptsCompanion.insert(
                  attemptId: 'attempt-$state',
                  sessionId: sessionId,
                  attemptNumber: 1,
                  capturedAtUs: 11,
                  imageRelativePath: 'sessions/$sessionId/attempt-001.jpg',
                  imageByteSize: 42,
                  imageSha256: _hash('4'),
                  status: 'staged',
                ),
              ),
          throwsA(isA<Exception>()),
        );
      }
    },
  );

  test('raw SQL rejects short catalog and audit SHA-256 values', () async {
    await expectLater(
      db.customStatement(
        '''
INSERT INTO catalog_revisions
  (revision_id, sha256, created_at_us, is_active)
VALUES (?, ?, ?, ?)
''',
        ['catalog-short', 'a', 1, 0],
      ),
      throwsA(isA<Exception>()),
    );

    await _seedAttempt(db);
    await expectLater(
      db.customStatement(
        '''
INSERT INTO scan_attempts (
  attempt_id, session_id, attempt_number, captured_at_us,
  image_relative_path, image_byte_size, image_sha256, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''',
        [
          'attempt-short-hash',
          'session-1',
          2,
          4,
          'sessions/session-1/attempt-002.jpg',
          42,
          'a',
          'staged',
        ],
      ),
      throwsA(isA<Exception>()),
    );
  });

  test('raw SQL rejects short or empty final receipt metadata', () async {
    await _seedAttempt(db);

    await expectLater(
      db.customStatement(
        '''
INSERT INTO final_orders (
  order_id, session_id, catalog_revision_id, created_at_us,
  total_quantity, total_amount_krw, receipt_relative_path,
  receipt_byte_size, receipt_sha256
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
        [
          'order-short-hash',
          'session-1',
          'catalog-v1',
          5,
          1,
          2800,
          'sessions/session-1/final-order.json',
          42,
          'a',
        ],
      ),
      throwsA(isA<Exception>()),
    );
    await expectLater(
      db.customStatement(
        '''
INSERT INTO final_orders (
  order_id, session_id, catalog_revision_id, created_at_us,
  total_quantity, total_amount_krw, receipt_relative_path,
  receipt_byte_size, receipt_sha256
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
        [
          'order-empty-path',
          'session-1',
          'catalog-v1',
          6,
          1,
          2800,
          '',
          42,
          _hash('6'),
        ],
      ),
      throwsA(isA<Exception>()),
    );
  });

  test('raw SQL rejects an empty retained audit path', () async {
    await _seedAttempt(db);

    await expectLater(
      db.customStatement(
        '''
INSERT INTO retention_events (
  retention_event_id, attempt_id, relative_path, original_byte_size,
  original_sha256, pruned_at_us, reason
) VALUES (?, ?, ?, ?, ?, ?, ?)
''',
        ['retention-empty-path', 'attempt-1', '', 42, _hash('4'), 5, 'expired'],
      ),
      throwsA(isA<Exception>()),
    );
  });

  test(
    'raw SQL cannot re-parent an inference object into a terminal session',
    () async {
      await _seedAttempt(db);
      await _seedSession(db, 'session-terminal');
      await _seedStagedAttempt(
        db,
        sessionId: 'session-terminal',
        attemptId: 'attempt-terminal',
        attemptNumber: 1,
      );
      await _insertInferenceObject(
        db,
        inferenceObjectId: 'object-move',
        attemptId: 'attempt-1',
        objectId: 'object-move',
        isUnknown: false,
      );
      await _makeTerminal(db, 'session-terminal', 'abandoned');

      await expectLater(
        db.customStatement(
          '''
UPDATE inference_objects SET attempt_id = ?
WHERE inference_object_id = ?
''',
          ['attempt-terminal', 'object-move'],
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'raw SQL cannot re-parent a candidate into a terminal session',
    () async {
      await _seedAttempt(db);
      await _seedSession(db, 'session-terminal');
      await _seedStagedAttempt(
        db,
        sessionId: 'session-terminal',
        attemptId: 'attempt-terminal',
        attemptNumber: 1,
      );
      await _insertInferenceObject(
        db,
        inferenceObjectId: 'object-active',
        attemptId: 'attempt-1',
        objectId: 'object-active',
        isUnknown: true,
      );
      await _insertInferenceObject(
        db,
        inferenceObjectId: 'object-terminal',
        attemptId: 'attempt-terminal',
        objectId: 'object-terminal',
        isUnknown: true,
      );
      await db
          .into(db.inferenceCandidates)
          .insert(
            InferenceCandidatesCompanion.insert(
              inferenceCandidateId: 'candidate-move',
              inferenceObjectId: 'object-active',
              rank: 1,
              skuId: 10,
              skuName: 'Candidate',
              score: 0.8,
            ),
          );
      await _makeTerminal(db, 'session-terminal', 'interrupted');

      await expectLater(
        db.customStatement(
          '''
UPDATE inference_candidates SET inference_object_id = ?
WHERE inference_candidate_id = ?
''',
          ['object-terminal', 'candidate-move'],
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'raw SQL rejects a payment whose order belongs to another session',
    () async {
      await _seedAttempt(db);
      await _seedSession(db, 'session-active');
      await db
          .into(db.finalOrders)
          .insert(
            FinalOrdersCompanion.insert(
              orderId: 'order-terminal',
              sessionId: 'session-1',
              catalogRevisionId: 'catalog-v1',
              createdAtUs: 5,
              totalQuantity: 1,
              totalAmountKrw: 2800,
              receiptRelativePath: 'sessions/session-1/final-order.json',
              receiptByteSize: 42,
              receiptSha256: _hash('6'),
            ),
          );
      await _makeTerminal(db, 'session-1', 'completed');

      await expectLater(
        db.customStatement(
          '''
INSERT INTO simulated_payments (
  payment_id, order_id, session_id, amount_krw, currency, provider,
  status, final_order_sha256, paid_at_us
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
          [
            'payment-mismatched',
            'order-terminal',
            'session-active',
            2800,
            'KRW',
            'simulated',
            'approved',
            _hash('6'),
            6,
          ],
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'raw SQL rejects a completed attempt missing its receipt path',
    () async {
      await _seedAttempt(db);

      await expectLater(
        _insertRawCompletedAttempt(
          db,
          attemptId: 'attempt-missing-path',
          attemptNumber: 2,
          receiptRelativePath: null,
          receiptSha256: _hash('5'),
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'raw SQL rejects a completed attempt missing its receipt hash',
    () async {
      await _seedAttempt(db);

      await expectLater(
        _insertRawCompletedAttempt(
          db,
          attemptId: 'attempt-missing-hash',
          attemptNumber: 2,
          receiptRelativePath:
              'sessions/session-1/attempt-missing-hash.inference.json',
          receiptSha256: null,
        ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test('raw SQL rejects provenance missing a required SHA key', () async {
    await _seedAttempt(db);

    await expectLater(
      db.customStatement(
        '''
INSERT INTO inference_objects (
  inference_object_id, attempt_id, object_id, sku_id, sku_name,
  decision_path, confidence, bbox_json, detector_source, detector_score,
  provenance_json, unknown_reason
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
        [
          'object-missing-sha',
          'attempt-1',
          'object-missing-sha',
          7,
          'Registered SKU',
          'repvit_direct',
          0.9,
          '[10,20,100,150]',
          'rfdetr_large_bakery_v1',
          0.95,
          _provenanceJson(includeRepvitSha256: false),
          null,
        ],
      ),
      throwsA(isA<Exception>()),
    );
  });
}

Future<void> _seedAttempt(BakeryDatabase db) async {
  await db
      .into(db.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: 'catalog-v1',
          sha256: _hash('a'),
          createdAtUs: 1,
          isActive: true,
        ),
      );
  await _seedSession(db, 'session-1');
  await db
      .into(db.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: 'attempt-1',
          sessionId: 'session-1',
          attemptNumber: 1,
          capturedAtUs: 3,
          imageRelativePath: 'sessions/session-1/attempt-001.jpg',
          imageByteSize: 42,
          imageSha256: _hash('4'),
          status: 'staged',
        ),
      );
}

Future<void> _seedSession(BakeryDatabase db, String sessionId) async {
  await db
      .into(db.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: sessionId,
          state: 'active',
          startedAtUs: 2,
          catalogRevisionId: 'catalog-v1',
          settingsRevisionId: 'settings-v1',
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _hash('b'),
          repvitArtifactId: 'repvit_m1_15plus5_v1',
          repvitSha256: _hash('c'),
          repvitManifestSha256: _hash('d'),
          repvitPrototypeSha256: _hash('e'),
          dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _hash('f'),
          dinov3SupportSha256: _hash('0'),
          calibrationId: 'calibration-v1',
          calibrationSha256: _hash('1'),
          preprocessSha256: _hash('2'),
          fusionPolicyId: 'fusion-v1',
          fusionPolicySha256: _hash('3'),
          configSnapshotJson: '{"pipeline":"canonical_cpu"}',
        ),
      );
}

Future<void> _seedStagedAttempt(
  BakeryDatabase db, {
  required String sessionId,
  required String attemptId,
  required int attemptNumber,
}) {
  return db
      .into(db.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: attemptId,
          sessionId: sessionId,
          attemptNumber: attemptNumber,
          capturedAtUs: 3,
          imageRelativePath: 'sessions/$sessionId/$attemptId.jpg',
          imageByteSize: 42,
          imageSha256: _hash('4'),
          status: 'staged',
        ),
      );
}

Future<void> _insertInferenceObject(
  BakeryDatabase db, {
  required String inferenceObjectId,
  required String attemptId,
  required String objectId,
  required bool isUnknown,
}) {
  return db
      .into(db.inferenceObjects)
      .insert(
        InferenceObjectsCompanion.insert(
          inferenceObjectId: inferenceObjectId,
          attemptId: attemptId,
          objectId: objectId,
          skuId: Value(isUnknown ? null : 7),
          skuName: isUnknown ? 'Unknown' : 'Registered SKU',
          decisionPath: isUnknown ? 'unknown_top3' : 'repvit_direct',
          confidence: 0.9,
          bboxJson: '[10,20,100,150]',
          detectorSource: 'rfdetr_large_bakery_v1',
          detectorScore: 0.95,
          provenanceJson: _provenanceJson(),
          unknownReason: Value(isUnknown ? 'ambiguous' : null),
        ),
      );
}

Future<void> _makeTerminal(BakeryDatabase db, String sessionId, String state) {
  return (db.update(
    db.checkoutSessions,
  )..where((row) => row.sessionId.equals(sessionId))).write(
    CheckoutSessionsCompanion(
      state: Value(state),
      terminalAtUs: const Value(10),
      terminalReason: Value('$state-for-test'),
    ),
  );
}

Future<void> _insertRawCompletedAttempt(
  BakeryDatabase db, {
  required String attemptId,
  required int attemptNumber,
  required String? receiptRelativePath,
  required String? receiptSha256,
}) {
  return db.customStatement(
    '''
INSERT INTO scan_attempts (
  attempt_id, session_id, attempt_number, captured_at_us,
  image_relative_path, image_byte_size, image_sha256, status,
  canonical_width, canonical_height, receipt_relative_path,
  receipt_byte_size, receipt_sha256, presentation_policy_id,
  presentation_policy_sha256
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
    [
      attemptId,
      'session-1',
      attemptNumber,
      4,
      'sessions/session-1/$attemptId.jpg',
      42,
      _hash('4'),
      'completed',
      1920,
      1080,
      receiptRelativePath,
      42,
      receiptSha256,
      'presentation-v1',
      _hash('3'),
    ],
  );
}

String _provenanceJson({bool includeRepvitSha256 = true}) {
  return jsonEncode({
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_artifact_id': 'repvit_m1_15plus5_v1',
    if (includeRepvitSha256) 'repvit_sha256': _hash('c'),
    'repvit_manifest_sha256': _hash('d'),
    'repvit_prototype_sha256': _hash('e'),
    'dinov3_artifact_id': 'dinov3_vits16_15plus5_v1',
    'dinov3_sha256': _hash('f'),
    'dinov3_support_sha256': _hash('0'),
    'calibration_id': 'calibration-v1',
    'calibration_sha256': _hash('1'),
    'preprocess_sha256': _hash('2'),
    'canonical_frame_version': 'exif_visual_rgb_v1',
    'exif_orientation': 1,
  });
}

String _hash(String character) => character * 64;
