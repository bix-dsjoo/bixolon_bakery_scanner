import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_admin_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('date range uses inclusive UTC start and exclusive UTC end', () {
    final range = DateRange.utc(
      DateTime.utc(2026, 7, 30),
      DateTime.utc(2026, 7, 31),
    );

    expect(range.includes(DateTime.utc(2026, 7, 30)), isTrue);
    expect(range.includes(DateTime.utc(2026, 7, 31)), isFalse);
  });

  test('summary rate keeps the operational numerator and denominator', () {
    const summary = AdminDashboardSummary(
      completedOrders: 3,
      grossKrw: 21600,
      scanAttempts: 5,
      retakeSessions: 1,
      unknownObjects: 2,
      customerResolvedUnknownObjects: 1,
      customerOverrides: 1,
      manualCartLines: 1,
      failedSessions: 1,
      unresolvedAttentionCount: 2,
    );

    expect(summary.retakeRate.numerator, 1);
    expect(summary.retakeRate.denominator, 3);
    expect(summary.unknownRate.denominator, 5);
    expect(summary.failureRate.denominator, 3);
  });

  test(
    'fixed audit seed projects committed checkout metrics for Seoul day',
    () async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      await _seedDashboard(database);

      final summary = await DatabaseAdminRepository(database).dashboard(
        DateRange.utc(
          DateTime.utc(2026, 7, 29, 15),
          DateTime.utc(2026, 7, 30, 15),
        ),
      );

      expect(summary.completedOrders, 3);
      expect(summary.grossKrw, 21600);
      expect(summary.scanAttempts, 5);
      expect(summary.retakeSessions, 1);
      expect(summary.unknownObjects, 2);
      expect(summary.customerResolvedUnknownObjects, 1);
      expect(summary.customerOverrides, 1);
      expect(summary.manualCartLines, 1);
      expect(summary.failedSessions, 1);
    },
  );
}

const _hash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _at = 1785373200000000; // 2026-07-30T00:00:00Z

Future<void> _seedDashboard(BakeryDatabase db) async {
  await db.customStatement('PRAGMA ignore_check_constraints = ON');
  await db
      .into(db.catalogRevisions)
      .insertOnConflictUpdate(
        CatalogRevisionsCompanion.insert(
          revisionId: 'catalog',
          sha256: _hash,
          createdAtUs: _at,
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
          displayName: '크루아상',
          unitPriceKrw: 2400,
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
          createdAtUs: _at,
          retryLimit: 2,
          paymentCompleteDurationSeconds: 5,
          customerAutoReset: true,
          evidenceRetentionDays: 30,
          locale: 'ko-KR',
          kioskDisplayName: 'BIXOLON',
          adminAuthorLabel: 'admin',
        ),
      );
  await db
      .into(db.appSettings)
      .insertOnConflictUpdate(
        AppSettingsCompanion.insert(
          settingsId: 'operational',
          activeSettingsRevisionId: 'settings',
          applicationVersionValue: '1.1.0',
          lastMigrationResult: 'ok',
        ),
      );
  for (final session in const ['paid-1', 'paid-2', 'paid-3', 'failed']) {
    await _insertSession(db, session);
  }
  await _attempt(db, 'attempt-1', 'paid-1', 1);
  await _attempt(db, 'attempt-2', 'paid-1', 2);
  await _attempt(db, 'attempt-3', 'paid-2', 1);
  await _attempt(db, 'attempt-4', 'paid-3', 1);
  await _attempt(db, 'attempt-5', 'failed', 1);
  await _object(db, 'unknown-unresolved', 'attempt-1', unknown: true);
  await _object(db, 'unknown-resolved', 'attempt-3', unknown: true);
  await _object(db, 'known-overridden', 'attempt-4', unknown: false);
  await _resolution(
    db,
    'resolved-unknown',
    'paid-2',
    'unknown-resolved',
    'customer_catalog',
  );
  await _resolution(
    db,
    'override',
    'paid-3',
    'known-overridden',
    'customer_overrode_auto',
  );
  await _resolution(db, 'manual', 'paid-1', null, 'customer_manual_cart');
  for (final session in const ['paid-1', 'paid-2', 'paid-3']) {
    final order = 'order-$session';
    await db
        .into(db.finalOrders)
        .insert(
          FinalOrdersCompanion.insert(
            orderId: order,
            sessionId: session,
            catalogRevisionId: 'catalog',
            createdAtUs: _at,
            totalQuantity: 1,
            totalAmountKrw: 7200,
            receiptRelativePath: '$session/final-order.json',
            receiptByteSize: 1,
            receiptSha256: _hash,
          ),
        );
    await db
        .into(db.simulatedPayments)
        .insert(
          SimulatedPaymentsCompanion.insert(
            paymentId: 'payment-$session',
            orderId: order,
            sessionId: session,
            amountKrw: 7200,
            currency: 'KRW',
            provider: 'simulated',
            status: 'approved',
            finalOrderSha256: _hash,
            paidAtUs: _at,
          ),
        );
  }
  for (final session in const ['paid-1', 'paid-2', 'paid-3', 'failed']) {
    await (db.update(
      db.checkoutSessions,
    )..where((row) => row.sessionId.equals(session))).write(
      CheckoutSessionsCompanion(
        state: Value(session == 'failed' ? 'failed' : 'completed'),
        terminalAtUs: const Value(_at),
        terminalReason: const Value('seed'),
      ),
    );
  }
}

Future<void> _insertSession(BakeryDatabase db, String id) => db
    .into(db.checkoutSessions)
    .insert(
      CheckoutSessionsCompanion.insert(
        sessionId: id,
        state: 'active',
        startedAtUs: _at,
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

Future<void> _attempt(
  BakeryDatabase db,
  String id,
  String session,
  int number,
) => db
    .into(db.scanAttempts)
    .insert(
      ScanAttemptsCompanion.insert(
        attemptId: id,
        sessionId: session,
        attemptNumber: number,
        capturedAtUs: _at,
        imageRelativePath: '$session/$id.jpg',
        imageByteSize: 1,
        imageSha256: _hash,
        status: 'staged',
      ),
    );

Future<void> _object(
  BakeryDatabase db,
  String id,
  String attempt, {
  required bool unknown,
}) => db
    .into(db.inferenceObjects)
    .insert(
      InferenceObjectsCompanion.insert(
        inferenceObjectId: id,
        attemptId: attempt,
        objectId: id,
        skuId: unknown ? const Value(null) : const Value(1),
        skuName: unknown ? 'Unknown' : '크루아상',
        decisionPath: unknown ? 'unknown_top3' : 'repvit_direct',
        confidence: .8,
        bboxJson: '[0,0,1,1]',
        detectorSource: 'detector',
        detectorScore: .8,
        provenanceJson:
            '{"padding":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
        unknownReason: unknown ? const Value('seed') : const Value(null),
      ),
    );

Future<void> _resolution(
  BakeryDatabase db,
  String id,
  String session,
  String? object,
  String source,
) => db
    .into(db.objectResolutions)
    .insert(
      ObjectResolutionsCompanion.insert(
        resolutionId: id,
        sessionId: session,
        inferenceObjectId: Value(object),
        productRevisionId: 'catalog/product',
        productId: 'product',
        productName: '크루아상',
        unitPriceKrw: 2400,
        source: source,
        resolvedAtUs: _at,
        canonicalBboxJson: Value(object == null ? null : '[0,0,1,1]'),
        isCurrent: true,
      ),
    );
