import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/audit/audit_file_store.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_checkout_audit_store.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart' show OrderingTerm, Value;
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  late BakeryDatabase db;
  late Product product;
  late CatalogRevision revision;
  late _References references;
  late DatabaseCheckoutAuditStore store;
  var nextId = 0;

  setUp(() async {
    db = openInMemoryBakeryDatabase();
    product = Product(
      productId: 'product-croissant',
      displayName: '크루아상',
      unitPrice: 2800,
      recognitionSkuId: 6,
      categoryId: 'pastry',
      photoAssetPath: null,
      active: true,
      sortOrder: 1,
    );
    revision = CatalogRevision(
      revisionId: 'catalog-v1',
      sha256: _hash('a'),
      createdAt: DateTime.utc(2026, 7, 30, 7),
    );
    await _seedCatalog(db, revision, product);
    references = _References();
    store = DatabaseCheckoutAuditStore(
      database: db,
      runtimeSnapshot: _runtimeSnapshot(),
      references: references,
      createId: (_) => _uuidFor(++nextId),
      now: () => DateTime.utc(2026, 7, 30, 8),
    );
  });

  tearDown(() async {
    await db.close();
  });

  test(
    'session snapshots catalog settings and verified runtime identities',
    () async {
      final sessionId = await store.beginSession(
        SessionSnapshot(
          sessionStartedAt: DateTime.utc(2026, 7, 30, 7, 30),
          catalogRevision: revision,
        ),
      );

      final session = await (db.select(
        db.checkoutSessions,
      )..where((row) => row.sessionId.equals(sessionId))).getSingle();

      expect(session.catalogRevisionId, 'catalog-v1');
      expect(session.settingsRevisionId, 'settings-v1');
      expect(session.detectorId, 'rfdetr_large_bakery_v1');
      expect(session.repvitArtifactId, 'repvit_m1_15plus5_v1');
      expect(session.dinov3ArtifactId, 'dinov3_vits16_15plus5_v1');
      expect(session.fusionPolicySha256, _hash('3'));

      await db
          .into(db.settingsRevisions)
          .insert(
            SettingsRevisionsCompanion.insert(
              revisionId: 'settings-v2',
              createdAtUs: DateTime.utc(
                2026,
                7,
                30,
                7,
                40,
              ).microsecondsSinceEpoch,
              retryLimit: 3,
              paymentCompleteDurationSeconds: 5,
              customerAutoReset: true,
              evidenceRetentionDays: 60,
              locale: 'ko-KR',
              kioskDisplayName: 'BIXOLON Bakery',
              adminAuthorLabel: 'prototype-admin',
            ),
          );
      await db
          .update(db.appSettings)
          .write(
            const AppSettingsCompanion(
              activeSettingsRevisionId: Value('settings-v2'),
            ),
          );
      final nextSessionId = await _beginSession(store, revision);
      final firstSession = await (db.select(
        db.checkoutSessions,
      )..where((row) => row.sessionId.equals(sessionId))).getSingle();
      final nextSession = await (db.select(
        db.checkoutSessions,
      )..where((row) => row.sessionId.equals(nextSessionId))).getSingle();

      expect(firstSession.settingsRevisionId, 'settings-v1');
      expect(nextSession.settingsRevisionId, 'settings-v2');
      expect(await store.retryLimitForSession(sessionId), 2);
      expect(await store.retryLimitForSession(nextSessionId), 3);
    },
  );

  test(
    'complete attempt stores immutable Unknown and exact top three',
    () async {
      final sessionId = await _beginSession(store, revision);
      final attempt = await store.stageAttempt(
        sessionId: sessionId,
        attemptNumber: 1,
        image: CapturedAuditFile(
          fileId: 'image-1',
          path: _capturePath(sessionId, DateTime.utc(2026, 7, 30, 8), 1),
          sha256: _hash('4'),
        ),
      );
      final result = buildUiInferenceResult();

      await store.completeAttempt(
        attempt: attempt,
        result: result,
        receipt: ImmutableJsonReceipt(
          canonicalJson: _receiptJson,
          sha256: _receiptSha,
        ),
      );

      final objects = await (db.select(
        db.inferenceObjects,
      )..orderBy([(row) => OrderingTerm.asc(row.objectId)])).get();
      final candidates = await (db.select(
        db.inferenceCandidates,
      )..orderBy([(row) => OrderingTerm.asc(row.rank)])).get();
      final savedAttempt = await (db.select(
        db.scanAttempts,
      )..where((row) => row.attemptId.equals(attempt.attemptId))).getSingle();

      expect(objects, hasLength(2));
      expect(objects.last.skuId, isNull);
      expect(objects.last.skuName, 'Unknown');
      expect(objects.last.decisionPath, 'unknown_top3');
      expect(candidates.map((candidate) => candidate.rank), [1, 2, 3]);
      expect(candidates.map((candidate) => candidate.skuId), [10, 11, 12]);
      expect(savedAttempt.receiptSha256, _receiptSha);
      expect(savedAttempt.presentationState, 'unknown');
      expect(savedAttempt.status, 'completed');
    },
  );

  test('complete attempt rejects a receipt unrelated to its result', () async {
    final sessionId = await _beginSession(store, revision);
    final attempt = await store.stageAttempt(
      sessionId: sessionId,
      attemptNumber: 1,
      image: CapturedAuditFile(
        fileId: 'image-1',
        path: _capturePath(sessionId, DateTime.utc(2026, 7, 30, 8), 1),
        sha256: _hash('4'),
      ),
    );

    await expectLater(
      store.completeAttempt(
        attempt: attempt,
        result: buildUiInferenceResult(),
        receipt: ImmutableJsonReceipt(
          canonicalJson: '{"request_id":"different-result"}',
          sha256: sha256
              .convert(utf8.encode('{"request_id":"different-result"}'))
              .toString(),
        ),
      ),
      throwsA(isA<StateError>()),
    );

    expect(await db.select(db.inferenceObjects).get(), isEmpty);
    expect((await db.select(db.scanAttempts).getSingle()).status, 'staged');
  });

  test(
    'database failure marks retained capture evidence for recovery',
    () async {
      final sessionId = await _beginSession(store, revision);
      final image = CapturedAuditFile(
        fileId: 'image-1',
        path: _capturePath(sessionId, DateTime.utc(2026, 7, 30, 8), 1),
        sha256: _hash('4'),
      );
      await store.stageAttempt(
        sessionId: sessionId,
        attemptNumber: 1,
        image: image,
      );

      await expectLater(
        store.stageAttempt(
          sessionId: sessionId,
          attemptNumber: 1,
          image: image,
        ),
        throwsA(isA<Exception>()),
      );

      expect(references.failedOperations, ['stage_attempt']);
    },
  );

  test(
    'stage attempt rejects capture paths outside its exact audit location',
    () async {
      final sessionId = await _beginSession(store, revision);
      final capturedAt = DateTime.utc(2026, 7, 30, 8);
      final expected = _capturePath(sessionId, capturedAt, 1);
      final wrongPaths = [
        'recovery/markers.jsonl',
        _capturePath(_uuidFor(999), capturedAt, 1),
        _capturePath(sessionId, DateTime.utc(2026, 7, 31, 8), 1),
        _capturePath(sessionId, capturedAt, 2),
        'sessions/2026/07/30/not-a-uuid/attempt-001.jpg',
      ];

      for (final path in wrongPaths) {
        await expectLater(
          store.stageAttempt(
            sessionId: sessionId,
            attemptNumber: 1,
            image: CapturedAuditFile(
              fileId: 'image-1',
              path: path,
              sha256: _hash('4'),
            ),
          ),
          throwsA(isA<StateError>()),
          reason: 'expected $expected, got $path',
        );
      }
    },
  );

  test(
    'marker write failure surfaces both persistence and recovery failure',
    () async {
      final sessionId = await _beginSession(store, revision);
      final image = CapturedAuditFile(
        fileId: 'image-1',
        path: _capturePath(sessionId, DateTime.utc(2026, 7, 30, 8), 1),
        sha256: _hash('4'),
      );
      await store.stageAttempt(
        sessionId: sessionId,
        attemptNumber: 1,
        image: image,
      );
      references.failMarkerWrite = true;

      await expectLater(
        store.stageAttempt(
          sessionId: sessionId,
          attemptNumber: 1,
          image: image,
        ),
        throwsA(
          isA<AuditRecoveryMarkerFailure>()
              .having(
                (error) => error.databaseError,
                'database error',
                isNotNull,
              )
              .having((error) => error.markerError, 'marker error', isNotNull)
              .having(
                (error) => error.retainedFile.relativePath,
                'retained file path',
                image.path,
              )
              .having(
                (error) => error.retainedFile.byteSize,
                'retained file size',
                42,
              )
              .having(
                (error) => error.retainedFile.sha256,
                'retained file hash',
                image.sha256,
              ),
        ),
      );
    },
  );

  test(
    'failed marker leaves actual retained evidence discoverable at startup',
    () async {
      final temporaryDirectory = await Directory.systemTemp.createTemp(
        'audit-recovery-',
      );
      try {
        final files = AuditFileStore(
          Directory('${temporaryDirectory.path}/audit'),
        );
        final references = _FileBackedFailingMarkerReferences(files);
        var id = 700;
        final fileStore = DatabaseCheckoutAuditStore(
          database: db,
          runtimeSnapshot: _runtimeSnapshot(),
          references: references,
          createId: (_) => _uuidFor(++id),
          now: () => DateTime.utc(2026, 7, 30, 8),
        );
        final sessionId = await _beginSession(fileStore, revision);
        final source = File('${temporaryDirectory.path}/capture.jpg');
        await source.writeAsBytes(const [1, 2, 3, 4], flush: true);
        final stored = await files.retainCapture(
          sessionId: sessionId,
          attemptNumber: 1,
          capturedAtUtc: DateTime.utc(2026, 7, 30, 8),
          sourcePath: source.path,
        );
        await db.customStatement('''
CREATE TRIGGER reject_stage_for_recovery_test
BEFORE INSERT ON scan_attempts
BEGIN
  SELECT RAISE(ABORT, 'injected stage failure');
END
''');

        await expectLater(
          fileStore.stageAttempt(
            sessionId: sessionId,
            attemptNumber: 1,
            image: CapturedAuditFile(
              fileId: 'image-1',
              path: stored.relativePath,
              sha256: stored.sha256,
            ),
          ),
          throwsA(
            isA<AuditRecoveryMarkerFailure>().having(
              (error) => error.retainedFile.relativePath,
              'retained file path',
              stored.relativePath,
            ),
          ),
        );

        expect(await files.findRecoveryCandidates(), [stored.relativePath]);
        expect(await File(files.resolve(stored.relativePath)).exists(), isTrue);
      } finally {
        await temporaryDirectory.delete(recursive: true);
      }
    },
  );

  test(
    'startup recovery flags a missing referenced capture and retains its audit row',
    () async {
      final fixture = await _fileBackedPaidOrder(
        database: db,
        revision: revision,
        product: product,
      );
      addTearDown(() => fixture.temporaryDirectory.delete(recursive: true));

      await File(fixture.files.resolve(fixture.capturePath)).delete();

      final report = await fixture.store.recoverInterruptedCheckout(
        DateTime.utc(2026, 7, 30, 9),
      );

      expect(report.evidenceIssuePaths, contains(fixture.capturePath));
      expect(
        (await db.select(db.auditEvents).get()).where(
          (event) =>
              event.sessionId == fixture.sessionId &&
              event.eventType == 'evidence_recovery_required',
        ),
        hasLength(1),
      );
      expect(
        await (db.select(
          db.scanAttempts,
        )..where((row) => row.sessionId.equals(fixture.sessionId))).get(),
        hasLength(1),
      );

      final secondReport = await fixture.store.recoverInterruptedCheckout(
        DateTime.utc(2026, 7, 30, 10),
      );
      expect(secondReport.evidenceIssuePaths, contains(fixture.capturePath));
      expect(
        (await db.select(db.auditEvents).get()).where(
          (event) =>
              event.sessionId == fixture.sessionId &&
              event.eventType == 'evidence_recovery_required',
        ),
        hasLength(1),
      );
    },
  );

  test(
    'startup recovery flags tampered inference and final-order receipts by metadata',
    () async {
      final fixture = await _fileBackedPaidOrder(
        database: db,
        revision: revision,
        product: product,
      );
      addTearDown(() => fixture.temporaryDirectory.delete(recursive: true));

      await File(
        fixture.files.resolve(fixture.inferenceReceiptPath),
      ).writeAsString('{"tampered":true}', flush: true);
      await File(
        fixture.files.resolve(fixture.finalOrderReceiptPath),
      ).writeAsString('{"tampered":true}', flush: true);

      final report = await fixture.store.recoverInterruptedCheckout(
        DateTime.utc(2026, 7, 30, 9),
      );

      expect(
        report.evidenceIssuePaths,
        containsAll([
          fixture.inferenceReceiptPath,
          fixture.finalOrderReceiptPath,
        ]),
      );
      expect(
        (await db.select(db.auditEvents).get()).where(
          (event) =>
              event.sessionId == fixture.sessionId &&
              event.eventType == 'evidence_recovery_required',
        ),
        hasLength(2),
      );
      expect(
        await File(
          fixture.files.resolve(fixture.inferenceReceiptPath),
        ).readAsString(),
        '{"tampered":true}',
      );
      expect(
        await File(
          fixture.files.resolve(fixture.finalOrderReceiptPath),
        ).readAsString(),
        '{"tampered":true}',
      );
    },
  );

  test(
    'complete attempt rejects model provenance outside session snapshot',
    () async {
      var mismatchId = 0;
      final mismatchRuntime = _runtimeSnapshot(repvitSha256: _hash('9'));
      final mismatchStore = DatabaseCheckoutAuditStore(
        database: db,
        runtimeSnapshot: mismatchRuntime,
        references: references,
        createId: (_) => _uuidFor(500 + ++mismatchId),
        now: () => DateTime.utc(2026, 7, 30, 8),
      );
      final sessionId = await _beginSession(mismatchStore, revision);
      final attempt = await mismatchStore.stageAttempt(
        sessionId: sessionId,
        attemptNumber: 1,
        image: CapturedAuditFile(
          fileId: 'image-1',
          path: _capturePath(sessionId, DateTime.utc(2026, 7, 30, 8), 1),
          sha256: _hash('4'),
        ),
      );

      await expectLater(
        mismatchStore.completeAttempt(
          attempt: attempt,
          result: buildUiInferenceResult(),
          receipt: ImmutableJsonReceipt(
            canonicalJson: canonicalInferenceReceiptJson(
              result: buildUiInferenceResult(),
              runtimeSnapshot: mismatchRuntime,
            ),
            sha256: _receiptHash(
              canonicalInferenceReceiptJson(
                result: buildUiInferenceResult(),
                runtimeSnapshot: mismatchRuntime,
              ),
            ),
          ),
        ),
        throwsA(isA<StateError>()),
      );

      expect(await db.select(db.inferenceObjects).get(), isEmpty);
    },
  );

  test('payment commit is idempotent by session id', () async {
    final setup = await _resolvedOrder(
      store: store,
      revision: revision,
      product: product,
    );

    final first = await store.commitSimulatedPayment(setup.order);
    final second = await store.commitSimulatedPayment(setup.order);

    expect(second.paymentId, first.paymentId);
    expect(await db.select(db.finalOrders).get(), hasLength(1));
    expect(await db.select(db.simulatedPayments).get(), hasLength(1));
    expect(
      (await db.select(db.checkoutSessions).getSingle()).state,
      'completed',
    );
    expect(
      (await db.select(db.auditEvents).get()).where(
        (event) => event.eventType == 'payment_committed',
      ),
      hasLength(1),
    );
  });

  test('payment rejects a basket that omits resolved products', () async {
    final otherProduct = Product(
      productId: 'product-baguette',
      displayName: '바게트',
      unitPrice: 3200,
      recognitionSkuId: 10,
      categoryId: 'bread',
      photoAssetPath: null,
      active: true,
      sortOrder: 2,
    );
    await _seedProduct(db, revision, otherProduct);
    final sessionId = await _beginSession(store, revision);
    await _completeAttempt(store, sessionId);
    for (final inferenceObject in buildUiInferenceResult().objects) {
      await store.recordResolution(
        ObjectResolutionDraft(
          sessionId: sessionId,
          inferenceObject: inferenceObject,
          product: product,
          source: inferenceObject.isUnknown
              ? CustomerResolutionSource.customerCatalog
              : CustomerResolutionSource.aiAutoCustomerAccepted,
          resolvedAt: DateTime.utc(2026, 7, 30, 7, 45),
        ),
      );
    }
    final order = FinalOrderDraft(
      sessionId: sessionId,
      catalogRevision: revision,
      lines: [CheckoutLine(product: otherProduct, quantity: 2)],
      createdAt: DateTime.utc(2026, 7, 30, 8),
    );
    await store.replaceDraftOrder(sessionId, order.lines);

    await expectLater(
      store.commitSimulatedPayment(order),
      throwsA(isA<StateError>()),
    );

    expect(await db.select(db.finalOrders).get(), isEmpty);
    expect(await db.select(db.simulatedPayments).get(), isEmpty);
  });

  test('cross-session resolutions cannot satisfy payment', () async {
    final targetSessionId = await _beginSession(store, revision);
    await _completeAttempt(store, targetSessionId);
    final otherSessionId = await _beginSession(store, revision);
    final objects = await db.select(db.inferenceObjects).get();
    for (final object in objects) {
      await expectLater(
        db
            .into(db.objectResolutions)
            .insert(
              ObjectResolutionsCompanion.insert(
                resolutionId: 'forged-${object.objectId}',
                sessionId: otherSessionId,
                inferenceObjectId: Value(object.inferenceObjectId),
                productRevisionId:
                    '${revision.revisionId}/${product.productId}',
                productId: product.productId,
                recognitionSkuId: Value(product.recognitionSkuId),
                productName: product.displayName,
                unitPriceKrw: product.unitPrice,
                source: CustomerResolutionSource.customerCatalog.storageValue,
                resolvedAtUs: DateTime.utc(
                  2026,
                  7,
                  30,
                  7,
                  45,
                ).microsecondsSinceEpoch,
                canonicalBboxJson: Value(object.bboxJson),
                isCurrent: true,
              ),
            ),
        throwsA(isA<Exception>()),
      );
    }
    final order = FinalOrderDraft(
      sessionId: targetSessionId,
      catalogRevision: revision,
      lines: [CheckoutLine(product: product, quantity: 2)],
      createdAt: DateTime.utc(2026, 7, 30, 8),
    );
    await store.replaceDraftOrder(targetSessionId, order.lines);

    await expectLater(
      store.commitSimulatedPayment(order),
      throwsA(isA<StateError>()),
    );

    expect(await db.select(db.finalOrders).get(), isEmpty);
  });

  test(
    'Unknown rejects AI auto acceptance and altered candidate evidence',
    () async {
      final sessionId = await _beginSession(store, revision);
      await _completeAttempt(store, sessionId);
      final unknown = buildUiInferenceResult().objects.last;

      await expectLater(
        store.recordResolution(
          ObjectResolutionDraft(
            sessionId: sessionId,
            inferenceObject: unknown,
            product: product,
            source: CustomerResolutionSource.aiAutoCustomerAccepted,
            resolvedAt: DateTime.utc(2026, 7, 30, 7, 45),
          ),
        ),
        throwsA(isA<StateError>()),
      );

      final altered = InferenceObject.fromJson(
        buildInferenceObjectJson(
          id: 'object-2',
          skuId: null,
          name: 'Unknown',
          confidence: 0.4,
          decisionPath: 'unknown_top3',
          box: const [600.0, 100.0, 1000.0, 600.0],
          candidates: const [
            {'rank': 1, 'sku_id': 10, 'sku_name': 'Sugar Donut', 'score': 0.87},
            {'rank': 2, 'sku_id': 11, 'sku_name': 'Cream Donut', 'score': 0.76},
            {
              'rank': 3,
              'sku_id': 12,
              'sku_name': 'Glazed Donut',
              'score': 0.62,
            },
          ],
        ),
        index: 2,
        imageWidth: 1920,
        imageHeight: 1080,
      );
      await expectLater(
        store.recordResolution(
          ObjectResolutionDraft(
            sessionId: sessionId,
            inferenceObject: altered,
            product: product,
            source: CustomerResolutionSource.customerCatalog,
            resolvedAt: DateTime.utc(2026, 7, 30, 7, 46),
          ),
        ),
        throwsA(isA<StateError>()),
      );

      expect(await db.select(db.objectResolutions).get(), isEmpty);
    },
  );

  test(
    'registered resolution source exactly follows AI product identity',
    () async {
      final otherProduct = Product(
        productId: 'product-baguette',
        displayName: 'Baguette',
        unitPrice: 3200,
        recognitionSkuId: 10,
        categoryId: 'bread',
        photoAssetPath: null,
        active: true,
        sortOrder: 2,
      );
      await _seedProduct(db, revision, otherProduct);
      final registered = buildUiInferenceResult().objects.singleWhere(
        (object) => !object.isUnknown,
      );

      final matchingSessionId = await _beginSession(store, revision);
      await _completeAttempt(store, matchingSessionId);
      for (final source in [
        CustomerResolutionSource.customerTop3,
        CustomerResolutionSource.customerCatalog,
        CustomerResolutionSource.customerOverrodeAuto,
        CustomerResolutionSource.customerManualCart,
      ]) {
        await expectLater(
          store.recordResolution(
            ObjectResolutionDraft(
              sessionId: matchingSessionId,
              inferenceObject: registered,
              product: product,
              source: source,
              resolvedAt: DateTime.utc(2026, 7, 30, 7, 45),
            ),
          ),
          throwsA(isA<StateError>()),
        );
      }
      await store.recordResolution(
        ObjectResolutionDraft(
          sessionId: matchingSessionId,
          inferenceObject: registered,
          product: product,
          source: CustomerResolutionSource.aiAutoCustomerAccepted,
          resolvedAt: DateTime.utc(2026, 7, 30, 7, 46),
        ),
      );

      final differingSessionId = await _beginSession(store, revision);
      await _completeAttempt(store, differingSessionId);
      for (final source in [
        CustomerResolutionSource.aiAutoCustomerAccepted,
        CustomerResolutionSource.customerTop3,
        CustomerResolutionSource.customerCatalog,
        CustomerResolutionSource.customerManualCart,
      ]) {
        await expectLater(
          store.recordResolution(
            ObjectResolutionDraft(
              sessionId: differingSessionId,
              inferenceObject: registered,
              product: otherProduct,
              source: source,
              resolvedAt: DateTime.utc(2026, 7, 30, 7, 47),
            ),
          ),
          throwsA(isA<StateError>()),
        );
      }
      await store.recordResolution(
        ObjectResolutionDraft(
          sessionId: differingSessionId,
          inferenceObject: registered,
          product: otherProduct,
          source: CustomerResolutionSource.customerOverrodeAuto,
          resolvedAt: DateTime.utc(2026, 7, 30, 7, 48),
        ),
      );

      expect(await db.select(db.objectResolutions).get(), hasLength(2));
    },
  );

  test(
    'registered inference without a session catalog mapping records only catalog selection',
    () async {
      await (db.update(db.products)
            ..where((row) => row.productId.equals(product.productId)))
          .write(const ProductsCompanion(recognitionSkuId: Value(null)));
      final catalogOnlyProduct = Product(
        productId: product.productId,
        displayName: product.displayName,
        unitPrice: product.unitPrice,
        recognitionSkuId: null,
        categoryId: product.categoryId,
        photoAssetPath: null,
        active: true,
        sortOrder: product.sortOrder,
      );
      final sessionId = await _beginSession(store, revision);
      await _completeAttempt(store, sessionId);
      final registered = buildUiInferenceResult().objects.singleWhere(
        (object) => !object.isUnknown,
      );

      await expectLater(
        store.recordResolution(
          ObjectResolutionDraft(
            sessionId: sessionId,
            inferenceObject: registered,
            product: catalogOnlyProduct,
            source: CustomerResolutionSource.customerOverrodeAuto,
            resolvedAt: DateTime.utc(2026, 7, 30, 7, 45),
          ),
        ),
        throwsA(isA<StateError>()),
      );

      await store.recordResolution(
        ObjectResolutionDraft(
          sessionId: sessionId,
          inferenceObject: registered,
          product: catalogOnlyProduct,
          source: CustomerResolutionSource.customerCatalog,
          resolvedAt: DateTime.utc(2026, 7, 30, 7, 46),
        ),
      );

      expect(
        (await db.select(db.objectResolutions).getSingle()).source,
        CustomerResolutionSource.customerCatalog.storageValue,
      );
    },
  );

  test('payment revalidates registered resolution source semantics', () async {
    final setup = await _resolvedOrder(
      store: store,
      revision: revision,
      product: product,
    );
    final registered = (await db.select(db.inferenceObjects).get()).singleWhere(
      (object) => object.skuId != null,
    );
    await (db.update(db.objectResolutions)..where(
          (row) => row.inferenceObjectId.equals(registered.inferenceObjectId),
        ))
        .write(
          ObjectResolutionsCompanion(
            source: Value(
              CustomerResolutionSource.customerCatalog.storageValue,
            ),
          ),
        );

    await expectLater(
      store.commitSimulatedPayment(setup.order),
      throwsA(isA<StateError>()),
    );

    expect(await db.select(db.finalOrders).get(), isEmpty);
    expect(await db.select(db.simulatedPayments).get(), isEmpty);
  });

  test(
    'completed evidence and paid order rows reject mutation and deletion',
    () async {
      final setup = await _resolvedOrder(
        store: store,
        revision: revision,
        product: product,
      );
      await store.commitSimulatedPayment(setup.order);
      final unknown = (await db.select(db.inferenceObjects).get()).singleWhere(
        (object) => object.skuId == null,
      );
      final registered = (await db.select(db.inferenceObjects).get())
          .singleWhere((object) => object.skuId != null);
      final candidate = (await db.select(db.inferenceCandidates).get()).first;
      final finalLine = (await db.select(db.finalOrderLines).get()).first;
      final finalOrder = await db.select(db.finalOrders).getSingle();
      final payment = await db.select(db.simulatedPayments).getSingle();

      await expectLater(
        db
            .into(db.inferenceObjects)
            .insert(
              InferenceObjectsCompanion.insert(
                inferenceObjectId: '${registered.attemptId}/object-99',
                attemptId: registered.attemptId,
                objectId: 'object-99',
                skuId: Value(registered.skuId),
                skuName: registered.skuName,
                decisionPath: registered.decisionPath,
                confidence: registered.confidence,
                bboxJson: registered.bboxJson,
                detectorSource: registered.detectorSource,
                detectorScore: registered.detectorScore,
                provenanceJson: registered.provenanceJson,
                unknownReason: const Value(null),
              ),
            ),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.update(db.inferenceObjects)..where(
              (row) => row.inferenceObjectId.equals(unknown.inferenceObjectId),
            ))
            .write(
              const InferenceObjectsCompanion(
                skuId: Value(6),
                skuName: Value('Croissant'),
                decisionPath: Value('repvit_direct'),
                unknownReason: Value(null),
              ),
            ),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.delete(db.inferenceCandidates)..where(
              (row) => row.inferenceCandidateId.equals(
                candidate.inferenceCandidateId,
              ),
            ))
            .go(),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.delete(
          db.finalOrderLines,
        )..where((row) => row.finalLineId.equals(finalLine.finalLineId))).go(),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.update(
          db.checkoutSessions,
        )..where((row) => row.sessionId.equals(setup.order.sessionId))).write(
          const CheckoutSessionsCompanion(detectorId: Value('other-detector')),
        ),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.update(db.catalogRevisions)
              ..where((row) => row.revisionId.equals(revision.revisionId)))
            .write(CatalogRevisionsCompanion(sha256: Value(_hash('8')))),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.update(db.settingsRevisions)
              ..where((row) => row.revisionId.equals('settings-v1')))
            .write(const SettingsRevisionsCompanion(retryLimit: Value(9))),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.update(db.finalOrders)
              ..where((row) => row.orderId.equals(finalOrder.orderId)))
            .write(const FinalOrdersCompanion(totalAmountKrw: Value(1))),
        throwsA(isA<Exception>()),
      );
      await expectLater(
        (db.delete(
          db.simulatedPayments,
        )..where((row) => row.paymentId.equals(payment.paymentId))).go(),
        throwsA(isA<Exception>()),
      );

      expect(
        (await db.select(db.inferenceObjects).get())
            .singleWhere((object) => object.objectId == 'object-2')
            .skuName,
        'Unknown',
      );
      expect(await db.select(db.inferenceCandidates).get(), hasLength(3));
      expect(await db.select(db.finalOrderLines).get(), hasLength(2));
      expect(await db.select(db.finalOrders).get(), hasLength(1));
      expect(await db.select(db.simulatedPayments).get(), hasLength(1));
    },
  );

  test(
    'failed final receipt verification rolls back the payment commit',
    () async {
      final setup = await _resolvedOrder(
        store: store,
        revision: revision,
        product: product,
      );
      references.failFinalOrder = true;

      await expectLater(
        store.commitSimulatedPayment(setup.order),
        throwsA(isA<StateError>()),
      );

      expect(await db.select(db.finalOrders).get(), isEmpty);
      expect(await db.select(db.finalOrderLines).get(), isEmpty);
      expect(await db.select(db.simulatedPayments).get(), isEmpty);
      expect(
        (await db.select(db.checkoutSessions).getSingle()).state,
        'active',
      );
      expect(
        (await db.select(db.auditEvents).get()).where(
          (event) => event.eventType == 'payment_committed',
        ),
        isEmpty,
      );
    },
  );

  test(
    'database failure after final rows start rolls back every write',
    () async {
      final setup = await _resolvedOrder(
        store: store,
        revision: revision,
        product: product,
      );
      await db.customStatement('''
CREATE TRIGGER reject_test_payment
BEFORE INSERT ON simulated_payments
BEGIN
  SELECT RAISE(ABORT, 'injected payment failure');
END
''');

      await expectLater(
        store.commitSimulatedPayment(setup.order),
        throwsA(isA<Exception>()),
      );

      expect(await db.select(db.finalOrders).get(), isEmpty);
      expect(await db.select(db.finalOrderLines).get(), isEmpty);
      expect(await db.select(db.simulatedPayments).get(), isEmpty);
      expect(
        (await db.select(db.checkoutSessions).getSingle()).state,
        'active',
      );
      expect(
        (await db.select(db.auditEvents).get()).where(
          (event) => event.eventType == 'payment_committed',
        ),
        isEmpty,
      );
      expect(references.failedOperations, ['commit_payment']);
    },
  );

  test(
    'unresolved inference object rejects payment without partial writes',
    () async {
      final sessionId = await _beginSession(store, revision);
      final attempt = await _completeAttempt(store, sessionId);
      expect(attempt.attemptId, isNotEmpty);
      final order = FinalOrderDraft(
        sessionId: sessionId,
        catalogRevision: revision,
        lines: [CheckoutLine(product: product, quantity: 1)],
        createdAt: DateTime.utc(2026, 7, 30, 8),
      );
      await store.replaceDraftOrder(sessionId, order.lines);

      await expectLater(
        store.commitSimulatedPayment(order),
        throwsA(isA<StateError>()),
      );

      expect(await db.select(db.finalOrders).get(), isEmpty);
      expect(await db.select(db.simulatedPayments).get(), isEmpty);
    },
  );

  test('manual-cart mode requires exhausted retries and pays without object '
      'resolutions', () async {
    final sessionId = await _beginSession(store, revision);
    await _completeAttempt(store, sessionId, attemptNumber: 1);
    await _completeAttempt(store, sessionId, attemptNumber: 2);

    await expectLater(
      store.enterManualCartMode(sessionId, DateTime.utc(2026, 7, 30, 8, 1)),
      throwsA(isA<StateError>()),
    );

    await _completeAttempt(store, sessionId, attemptNumber: 3);
    await store.enterManualCartMode(sessionId, DateTime.utc(2026, 7, 30, 8, 2));
    final order = FinalOrderDraft(
      sessionId: sessionId,
      catalogRevision: revision,
      lines: [CheckoutLine(product: product, quantity: 1)],
      createdAt: DateTime.utc(2026, 7, 30, 8, 3),
    );
    await store.replaceDraftOrder(sessionId, order.lines);

    final receipt = await store.commitSimulatedPayment(order);

    expect(receipt.amount, product.unitPrice);
    final finalLine = await db.select(db.finalOrderLines).getSingle();
    expect(
      finalLine.resolutionSource,
      CustomerResolutionSource.customerManualCart.storageValue,
    );
    expect(await db.select(db.objectResolutions).get(), isEmpty);
    expect(
      (await db.select(db.auditEvents).get()).where(
        (event) => event.eventType == 'manual_cart_entered',
      ),
      hasLength(1),
    );
  });
}

Future<String> _beginSession(
  DatabaseCheckoutAuditStore store,
  CatalogRevision revision,
) => store.beginSession(
  SessionSnapshot(
    sessionStartedAt: DateTime.utc(2026, 7, 30, 7, 30),
    catalogRevision: revision,
  ),
);

Future<StagedAttempt> _completeAttempt(
  DatabaseCheckoutAuditStore store,
  String sessionId, {
  int attemptNumber = 1,
}) async {
  final attempt = await store.stageAttempt(
    sessionId: sessionId,
    attemptNumber: attemptNumber,
    image: CapturedAuditFile(
      fileId: 'image-$attemptNumber',
      path: _capturePath(
        sessionId,
        DateTime.utc(2026, 7, 30, 8),
        attemptNumber,
      ),
      sha256: _hash('4'),
    ),
  );
  await store.completeAttempt(
    attempt: attempt,
    result: buildUiInferenceResult(),
    receipt: ImmutableJsonReceipt(
      canonicalJson: _receiptJson,
      sha256: _receiptSha,
    ),
  );
  return attempt;
}

Future<({FinalOrderDraft order})> _resolvedOrder({
  required DatabaseCheckoutAuditStore store,
  required CatalogRevision revision,
  required Product product,
}) async {
  final sessionId = await _beginSession(store, revision);
  await _completeAttempt(store, sessionId);
  final result = buildUiInferenceResult();
  for (final inferenceObject in result.objects) {
    await store.recordResolution(
      ObjectResolutionDraft(
        sessionId: sessionId,
        inferenceObject: inferenceObject,
        product: product,
        source: inferenceObject.isUnknown
            ? CustomerResolutionSource.customerCatalog
            : CustomerResolutionSource.aiAutoCustomerAccepted,
        resolvedAt: DateTime.utc(2026, 7, 30, 7, 45),
      ),
    );
  }
  final order = FinalOrderDraft(
    sessionId: sessionId,
    catalogRevision: revision,
    lines: [CheckoutLine(product: product, quantity: 2)],
    createdAt: DateTime.utc(2026, 7, 30, 8),
  );
  await store.replaceDraftOrder(sessionId, order.lines);
  return (order: order);
}

Future<void> _seedCatalog(
  BakeryDatabase db,
  CatalogRevision revision,
  Product product,
) async {
  await db
      .into(db.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: revision.revisionId,
          sha256: revision.sha256,
          createdAtUs: revision.createdAt.microsecondsSinceEpoch,
          isActive: true,
        ),
      );
  await db
      .into(db.products)
      .insert(
        ProductsCompanion.insert(
          productRevisionId: '${revision.revisionId}/${product.productId}',
          catalogRevisionId: revision.revisionId,
          productId: product.productId,
          displayName: product.displayName,
          unitPriceKrw: product.unitPrice,
          recognitionSkuId: Value(product.recognitionSkuId),
          categoryId: product.categoryId,
          active: product.active,
          sortOrder: product.sortOrder,
        ),
      );
}

AuditRuntimeSnapshot _runtimeSnapshot({String? repvitSha256}) =>
    AuditRuntimeSnapshot(
      detectorId: 'rfdetr_large_bakery_v1',
      detectorSha256: _hash('b'),
      repvitArtifactId: 'repvit_m1_15plus5_v1',
      repvitSha256: repvitSha256 ?? _hash('a'),
      repvitManifestSha256: _hash('b'),
      repvitPrototypeSha256: _hash('c'),
      dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
      dinov3Sha256: _hash('d'),
      dinov3SupportSha256: _hash('e'),
      calibrationId: 'policy-v1',
      calibrationSha256: _hash('f'),
      preprocessSha256: _hash('0'),
      fusionPolicyId: 'fusion-v1',
      fusionPolicySha256: _hash('3'),
      configSnapshotJson: '{"pipeline":"canonical_cpu"}',
      startupDevice: 'cpu',
      startupLoadMs: 12.5,
      startupWarmupMs: 7,
    );

Future<void> _seedProduct(
  BakeryDatabase db,
  CatalogRevision revision,
  Product product,
) {
  return db
      .into(db.products)
      .insert(
        ProductsCompanion.insert(
          productRevisionId: '${revision.revisionId}/${product.productId}',
          catalogRevisionId: revision.revisionId,
          productId: product.productId,
          displayName: product.displayName,
          unitPriceKrw: product.unitPrice,
          recognitionSkuId: Value(product.recognitionSkuId),
          categoryId: product.categoryId,
          active: product.active,
          sortOrder: product.sortOrder,
        ),
      );
}

final class _References
    implements AuditReferenceVerifier, AuditRecoveryMarkerWriter {
  bool failFinalOrder = false;
  bool failMarkerWrite = false;
  final List<String> failedOperations = [];

  @override
  Future<VerifiedAuditFileReference> capturedImage({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required CapturedAuditFile image,
  }) async {
    return VerifiedAuditFileReference(
      relativePath: _capturePath(sessionId, capturedAtUtc, attemptNumber),
      byteSize: 42,
      sha256: image.sha256,
    );
  }

  @override
  Future<VerifiedAuditFileReference> inferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) async {
    return VerifiedAuditFileReference(
      relativePath: _receiptPath(
        sessionId,
        capturedAtUtc,
        'attempt-${attemptNumber.toString().padLeft(3, '0')}.inference.json',
      ),
      byteSize: receipt.canonicalJson.length,
      sha256: receipt.sha256,
    );
  }

  @override
  Future<VerifiedAuditFileReference> finalOrderReceipt(
    FinalOrderDraft order,
  ) async {
    if (failFinalOrder) {
      throw StateError('final order receipt hash verification failed');
    }
    return VerifiedAuditFileReference(
      relativePath: _receiptPath(
        order.sessionId,
        order.createdAt,
        'final-order.json',
      ),
      byteSize: 128,
      sha256: _hash('6'),
    );
  }

  @override
  Future<void> recordDatabaseFailure({
    required String operation,
    required VerifiedAuditFileReference file,
    required Object error,
  }) async {
    if (failMarkerWrite) {
      throw StateError('injected marker write failure');
    }
    failedOperations.add(operation);
  }
}

final class _FileBackedFailingMarkerReferences
    implements AuditReferenceVerifier, AuditRecoveryMarkerWriter {
  _FileBackedFailingMarkerReferences(this._files);

  final AuditFileStore _files;

  @override
  Future<VerifiedAuditFileReference> capturedImage({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required CapturedAuditFile image,
  }) async {
    final file = await _files.verifyExisting(
      relativePath: image.path,
      sha256: image.sha256,
    );
    return VerifiedAuditFileReference(
      relativePath: file.relativePath,
      byteSize: file.byteSize,
      sha256: file.sha256,
    );
  }

  @override
  Future<VerifiedAuditFileReference> inferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) => throw UnimplementedError();

  @override
  Future<VerifiedAuditFileReference> finalOrderReceipt(FinalOrderDraft order) =>
      throw UnimplementedError();

  @override
  Future<void> recordDatabaseFailure({
    required String operation,
    required VerifiedAuditFileReference file,
    required Object error,
  }) => throw StateError('injected marker failure');
}

String _capturePath(
  String sessionId,
  DateTime capturedAtUtc,
  int attemptNumber,
) => _receiptPath(
  sessionId,
  capturedAtUtc,
  'attempt-${attemptNumber.toString().padLeft(3, '0')}.jpg',
);

String _receiptPath(
  String sessionId,
  DateTime occurredAtUtc,
  String fileName,
) =>
    'sessions/${occurredAtUtc.year.toString().padLeft(4, '0')}/'
    '${occurredAtUtc.month.toString().padLeft(2, '0')}/'
    '${occurredAtUtc.day.toString().padLeft(2, '0')}/$sessionId/$fileName';

String _uuidFor(int value) =>
    '00000000-0000-4000-8000-${value.toString().padLeft(12, '0')}';

String _hash(String character) => character * 64;

final _receiptJson = canonicalInferenceReceiptJson(
  result: buildUiInferenceResult(),
  runtimeSnapshot: _runtimeSnapshot(),
);
final _receiptSha = _receiptHash(_receiptJson);

String _receiptHash(String json) =>
    sha256.convert(utf8.encode(json)).toString();

final class _FileBackedPaidOrder {
  const _FileBackedPaidOrder({
    required this.temporaryDirectory,
    required this.files,
    required this.store,
    required this.sessionId,
    required this.capturePath,
    required this.inferenceReceiptPath,
    required this.finalOrderReceiptPath,
  });

  final Directory temporaryDirectory;
  final AuditFileStore files;
  final DatabaseCheckoutAuditStore store;
  final String sessionId;
  final String capturePath;
  final String inferenceReceiptPath;
  final String finalOrderReceiptPath;
}

Future<_FileBackedPaidOrder> _fileBackedPaidOrder({
  required BakeryDatabase database,
  required CatalogRevision revision,
  required Product product,
}) async {
  final temporaryDirectory = await Directory.systemTemp.createTemp(
    'audit-recovery-reference-',
  );
  final files = AuditFileStore(Directory('${temporaryDirectory.path}/audit'));
  var id = 900;
  final store = DatabaseCheckoutAuditStore(
    database: database,
    runtimeSnapshot: _runtimeSnapshot(),
    references: AuditFileStoreReferenceVerifier(files),
    createId: (_) => _uuidFor(++id),
    now: () => DateTime.utc(2026, 7, 30, 8),
  );
  final sessionId = await _beginSession(store, revision);
  final capturedAt = DateTime.utc(2026, 7, 30, 8);
  final source = File('${temporaryDirectory.path}/capture.jpg');
  await source.writeAsBytes(const [1, 2, 3, 4], flush: true);
  final capture = await files.retainCapture(
    sessionId: sessionId,
    attemptNumber: 1,
    capturedAtUtc: capturedAt,
    sourcePath: source.path,
  );
  final attempt = await store.stageAttempt(
    sessionId: sessionId,
    attemptNumber: 1,
    image: CapturedAuditFile(
      fileId: 'capture-1',
      path: capture.relativePath,
      sha256: capture.sha256,
    ),
  );
  await store.completeAttempt(
    attempt: attempt,
    result: buildUiInferenceResult(),
    receipt: ImmutableJsonReceipt(
      canonicalJson: _receiptJson,
      sha256: _receiptSha,
    ),
  );
  for (final inferenceObject in buildUiInferenceResult().objects) {
    await store.recordResolution(
      ObjectResolutionDraft(
        sessionId: sessionId,
        inferenceObject: inferenceObject,
        product: product,
        source: inferenceObject.isUnknown
            ? CustomerResolutionSource.customerCatalog
            : CustomerResolutionSource.aiAutoCustomerAccepted,
        resolvedAt: DateTime.utc(2026, 7, 30, 8, 1),
      ),
    );
  }
  final order = FinalOrderDraft(
    sessionId: sessionId,
    catalogRevision: revision,
    lines: [CheckoutLine(product: product, quantity: 2)],
    createdAt: DateTime.utc(2026, 7, 30, 8, 2),
  );
  await store.replaceDraftOrder(sessionId, order.lines);
  await store.commitSimulatedPayment(order);
  final savedAttempt = await (database.select(
    database.scanAttempts,
  )..where((row) => row.attemptId.equals(attempt.attemptId))).getSingle();
  final savedOrder = await (database.select(
    database.finalOrders,
  )..where((row) => row.sessionId.equals(sessionId))).getSingle();
  return _FileBackedPaidOrder(
    temporaryDirectory: temporaryDirectory,
    files: files,
    store: store,
    sessionId: sessionId,
    capturePath: savedAttempt.imageRelativePath,
    inferenceReceiptPath: savedAttempt.receiptRelativePath!,
    finalOrderReceiptPath: savedOrder.receiptRelativePath,
  );
}
