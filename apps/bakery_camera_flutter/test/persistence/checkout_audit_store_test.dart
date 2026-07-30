import 'dart:convert';

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
      createId: (prefix) => '$prefix-${++nextId}',
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
          path: 'sessions/$sessionId/attempt-001.jpg',
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
        path: 'sessions/$sessionId/attempt-001.jpg',
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
        path: 'sessions/$sessionId/attempt-001.jpg',
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
    'complete attempt rejects model provenance outside session snapshot',
    () async {
      var mismatchId = 0;
      final mismatchRuntime = _runtimeSnapshot(repvitSha256: _hash('9'));
      final mismatchStore = DatabaseCheckoutAuditStore(
        database: db,
        runtimeSnapshot: mismatchRuntime,
        references: references,
        createId: (prefix) => 'mismatch-$prefix-${++mismatchId}',
        now: () => DateTime.utc(2026, 7, 30, 8),
      );
      final sessionId = await _beginSession(mismatchStore, revision);
      final attempt = await mismatchStore.stageAttempt(
        sessionId: sessionId,
        attemptNumber: 1,
        image: CapturedAuditFile(
          fileId: 'image-1',
          path: 'sessions/$sessionId/attempt-001.jpg',
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
  String sessionId,
) async {
  final attempt = await store.stageAttempt(
    sessionId: sessionId,
    attemptNumber: 1,
    image: CapturedAuditFile(
      fileId: 'image-1',
      path: 'sessions/$sessionId/attempt-001.jpg',
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
  final List<String> failedOperations = [];

  @override
  Future<VerifiedAuditFileReference> capturedImage(
    CapturedAuditFile image,
  ) async {
    return VerifiedAuditFileReference(
      relativePath: image.path,
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
      relativePath: 'sessions/session-1/attempt-001.inference.json',
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
      relativePath: 'sessions/${order.sessionId}/final-order.json',
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
    failedOperations.add(operation);
  }
}

String _hash(String character) => character * 64;

final _receiptJson = canonicalInferenceReceiptJson(
  result: buildUiInferenceResult(),
  runtimeSnapshot: _runtimeSnapshot(),
);
final _receiptSha = _receiptHash(_receiptJson);

String _receiptHash(String json) =>
    sha256.convert(utf8.encode(json)).toString();
