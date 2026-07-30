import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_admin_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('transaction filters retain every explicit audit outcome', () {
    const filter = TransactionFilter(
      paymentStatus: TransactionPaymentStatus.completed,
      resolutionSource: 'customer_catalog',
      requiresUnknown: true,
      requiresRetake: true,
      requiresFailure: true,
    );

    expect(filter.paymentStatus, TransactionPaymentStatus.completed);
    expect(filter.resolutionSource, 'customer_catalog');
    expect(filter.requiresUnknown, isTrue);
    expect(filter.requiresRetake, isTrue);
    expect(filter.requiresFailure, isTrue);
  });

  test(
    'history filters immutable sessions and paginates with a compound cursor',
    () async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      await _seed(database);
      final repository = DatabaseAdminRepository(database);

      final all = await repository.transactions(
        const TransactionFilter(),
        null,
        limit: 1,
      );
      expect(all.items.single.sessionId, 'session-c');
      final next = await repository.transactions(
        const TransactionFilter(),
        all.nextCursor,
        limit: 1,
      );
      expect(next.items.single.sessionId, 'session-b');
      expect(
        (await repository.transactions(
        TransactionFilter(
            dateRange: DateRange.utc(
              DateTime.fromMicrosecondsSinceEpoch(0, isUtc: true),
              DateTime.fromMicrosecondsSinceEpoch(150, isUtc: true),
            ),
          ),
          null,
        )).items.map((row) => row.sessionId),
        ['session-b', 'session-a'],
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(sessionQuery: 'session-a'),
          null,
        )).items.single.sessionId,
        'session-a',
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(
            paymentStatus: TransactionPaymentStatus.completed,
          ),
          null,
        )).items.single.sessionId,
        'session-a',
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(resolutionSource: 'customer_catalog'),
          null,
        )).items.single.sessionId,
        'session-a',
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(requiresUnknown: true),
          null,
        )).items.single.sessionId,
        'session-a',
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(requiresRetake: true),
          null,
        )).items.single.sessionId,
        'session-b',
      );
      expect(
        (await repository.transactions(
          const TransactionFilter(requiresFailure: true),
          null,
        )).items.single.sessionId,
        'session-b',
      );
    },
  );
}

const _hash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

Future<void> _seed(BakeryDatabase db) async {
  await db
      .into(db.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: 'catalog',
          sha256: _hash,
          createdAtUs: 0,
          isActive: true,
        ),
      );
  await db
      .into(db.products)
      .insert(
        ProductsCompanion.insert(
          productRevisionId: 'catalog/product',
          catalogRevisionId: 'catalog',
          productId: 'product',
          displayName: '식빵',
          unitPriceKrw: 1000,
          categoryId: 'bread',
          active: true,
          sortOrder: 0,
        ),
      );
  await db
      .into(db.settingsRevisions)
      .insert(
        SettingsRevisionsCompanion.insert(
          revisionId: 'settings',
          createdAtUs: 0,
          retryLimit: 2,
          paymentCompleteDurationSeconds: 4,
          customerAutoReset: true,
          evidenceRetentionDays: 30,
          locale: 'ko-KR',
          kioskDisplayName: 'BIXOLON',
          adminAuthorLabel: 'admin',
        ),
      );
  for (final row in const [
    ('session-a', 100),
    ('session-b', 100),
    ('session-c', 200),
  ]) {
    await db
        .into(db.checkoutSessions)
        .insert(
          CheckoutSessionsCompanion.insert(
            sessionId: row.$1,
            state: 'active',
            startedAtUs: row.$2,
            catalogRevisionId: 'catalog',
            settingsRevisionId: 'settings',
            detectorId: 'detector',
            detectorSha256: _hash,
            repvitArtifactId: 'repvit',
            repvitSha256: _hash,
            repvitManifestSha256: _hash,
            repvitPrototypeSha256: _hash,
            dinov3ArtifactId: 'dino',
            dinov3Sha256: _hash,
            dinov3SupportSha256: _hash,
            calibrationId: 'calibration',
            calibrationSha256: _hash,
            preprocessSha256: _hash,
            fusionPolicyId: 'policy',
            fusionPolicySha256: _hash,
            configSnapshotJson: '{}',
          ),
        );
  }
  await _attempt(db, 'a-1', 'session-a', 1);
  await _attempt(db, 'b-1', 'session-b', 1);
  await _attempt(db, 'b-2', 'session-b', 2);
  await db
      .into(db.inferenceObjects)
      .insert(
        InferenceObjectsCompanion.insert(
          inferenceObjectId: 'unknown',
          attemptId: 'a-1',
          objectId: 'object',
          skuId: const Value(null),
          skuName: 'Unknown',
          decisionPath: 'unknown_top3',
          confidence: .2,
          bboxJson: '[0,0,1,1]',
          detectorSource: 'detector',
          detectorScore: .8,
          provenanceJson: _provenance,
          unknownReason: const Value('low consensus'),
        ),
      );
  await db
      .into(db.objectResolutions)
      .insert(
        ObjectResolutionsCompanion.insert(
          resolutionId: 'resolution',
          sessionId: 'session-a',
          inferenceObjectId: const Value('unknown'),
          productRevisionId: 'catalog/product',
          productId: 'product',
          productName: '식빵',
          unitPriceKrw: 1000,
          source: 'customer_catalog',
          resolvedAtUs: 101,
          canonicalBboxJson: const Value('[0,0,1,1]'),
          isCurrent: true,
        ),
      );
  await db
      .into(db.finalOrders)
      .insert(
        FinalOrdersCompanion.insert(
          orderId: 'order-a',
          sessionId: 'session-a',
          catalogRevisionId: 'catalog',
          createdAtUs: 101,
          totalQuantity: 1,
          totalAmountKrw: 1000,
          receiptRelativePath: 'session-a/order.json',
          receiptByteSize: 1,
          receiptSha256: _hash,
        ),
      );
  await db
      .into(db.simulatedPayments)
      .insert(
        SimulatedPaymentsCompanion.insert(
          paymentId: 'payment-a',
          orderId: 'order-a',
          sessionId: 'session-a',
          amountKrw: 1000,
          currency: 'KRW',
          provider: 'simulated',
          status: 'approved',
          finalOrderSha256: _hash,
          paidAtUs: 101,
        ),
      );
  await (db.update(
    db.checkoutSessions,
  )..where((row) => row.sessionId.equals('session-a'))).write(
    const CheckoutSessionsCompanion(
      state: Value('completed'),
      terminalAtUs: Value(102),
      terminalReason: Value('paid'),
    ),
  );
  await (db.update(
    db.checkoutSessions,
  )..where((row) => row.sessionId.equals('session-b'))).write(
    const CheckoutSessionsCompanion(
      state: Value('failed'),
      terminalAtUs: Value(102),
      terminalReason: Value('camera'),
    ),
  );
}

Future<void> _attempt(
  BakeryDatabase db,
  String id,
  String sessionId,
  int number,
) => db
    .into(db.scanAttempts)
    .insert(
      ScanAttemptsCompanion.insert(
        attemptId: id,
        sessionId: sessionId,
        attemptNumber: number,
        capturedAtUs: 101,
        imageRelativePath: '$id.jpg',
        imageByteSize: 1,
        imageSha256: _hash,
        status: 'staged',
      ),
    );

const _provenance =
    '{"detector_id":"detector","repvit_artifact_id":"repvit","repvit_sha256":"$_hash","repvit_manifest_sha256":"$_hash","repvit_prototype_sha256":"$_hash","dinov3_artifact_id":"dino","dinov3_sha256":"$_hash","dinov3_support_sha256":"$_hash","calibration_id":"calibration","calibration_sha256":"$_hash","preprocess_sha256":"$_hash","canonical_frame_version":"exif_visual_rgb_v1","exif_orientation":1}';
