import 'dart:convert';

import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
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

AuditRuntimeSnapshot _runtimeSnapshot() => AuditRuntimeSnapshot(
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
  startupDevice: 'cpu',
  startupLoadMs: 12.5,
  startupWarmupMs: 7,
);

final class _References implements AuditReferenceVerifier {
  bool failFinalOrder = false;

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
  Future<VerifiedAuditFileReference> inferenceReceipt(
    ImmutableJsonReceipt receipt,
  ) async {
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
}

String _hash(String character) => character * 64;

const _receiptJson = '{"request_id":"analysis-1"}';
final _receiptSha = sha256.convert(utf8.encode(_receiptJson)).toString();
