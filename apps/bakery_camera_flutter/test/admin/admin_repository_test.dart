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

  test(
    'dashboard assigns each metric to its audited event time across Seoul midnight',
    () async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      const afterSeoulDay = 1785423600000000; // 2026-07-30T13:00:00Z
      await _seedDashboard(
        database,
        earlierSessionIds: const {'paid-1', 'failed'},
        resolutionAtUs: afterSeoulDay,
      );

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
      expect(summary.customerResolvedUnknownObjects, 0);
      expect(summary.customerOverrides, 0);
      expect(summary.manualCartLines, 0);
      expect(summary.failedSessions, 1);
    },
  );

  test(
    'dashboard counts an Unknown resolved just after Seoul day start even when captured earlier',
    () async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      const seoulDayStartUs = 1785337200000000; // 2026-07-29T15:00:00Z
      await _seedDashboard(
        database,
        earlierSessionIds: const {'paid-2'},
        attemptCapturedAtUs: {
          'attempt-3': seoulDayStartUs - 1,
          'attempt-4': seoulDayStartUs - 1,
        },
        resolutionAtUs: seoulDayStartUs + 1,
      );

      final summary = await DatabaseAdminRepository(database).dashboard(
        DateRange.utc(
          DateTime.utc(2026, 7, 29, 15),
          DateTime.utc(2026, 7, 30, 15),
        ),
      );

      expect(summary.scanAttempts, 3);
      expect(summary.customerResolvedUnknownObjects, 1);
      expect(summary.customerOverrides, 1);
    },
  );
}

const _hash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _at = 1785373200000000; // 2026-07-30T00:00:00Z

Future<void> _seedDashboard(
  BakeryDatabase db, {
  Set<String> earlierSessionIds = const {},
  Map<String, int> attemptCapturedAtUs = const {},
  int resolutionAtUs = _at,
}) async {
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
    await _insertSession(
      db,
      session,
      startedAtUs: earlierSessionIds.contains(session) ? 1785298800000000 : _at,
    );
  }
  await _attempt(db, 'attempt-1', 'paid-1', 1, attemptCapturedAtUs);
  await _attempt(db, 'attempt-2', 'paid-1', 2, attemptCapturedAtUs);
  await _attempt(db, 'attempt-3', 'paid-2', 1, attemptCapturedAtUs);
  await _attempt(db, 'attempt-4', 'paid-3', 1, attemptCapturedAtUs);
  await _attempt(db, 'attempt-5', 'failed', 1, attemptCapturedAtUs);
  await _object(db, 'unknown-unresolved', 'attempt-1', unknown: true);
  await _object(db, 'unknown-resolved', 'attempt-3', unknown: true);
  await _object(db, 'known-overridden', 'attempt-4', unknown: false);
  for (final object in const ['unknown-unresolved', 'unknown-resolved']) {
    for (var rank = 1; rank <= 3; rank += 1) {
      await _candidate(db, object, rank);
    }
  }
  for (final attempt in const [
    ('attempt-1', 'paid-1'),
    ('attempt-2', 'paid-1'),
    ('attempt-3', 'paid-2'),
    ('attempt-4', 'paid-3'),
    ('attempt-5', 'failed'),
  ]) {
    await _completeAttempt(db, attempt.$1, attempt.$2);
  }
  await _resolution(
    db,
    'resolved-unknown',
    'paid-2',
    'unknown-resolved',
    'customer_catalog',
    resolvedAtUs: resolutionAtUs,
  );
  await _resolution(
    db,
    'override',
    'paid-3',
    'known-overridden',
    'customer_overrode_auto',
    resolvedAtUs: resolutionAtUs,
  );
  await _resolution(
    db,
    'manual',
    'paid-1',
    null,
    'customer_manual_cart',
    resolvedAtUs: resolutionAtUs,
  );
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

Future<void> _insertSession(
  BakeryDatabase db,
  String id, {
  required int startedAtUs,
}) => db
    .into(db.checkoutSessions)
    .insert(
      CheckoutSessionsCompanion.insert(
        sessionId: id,
        state: 'active',
        startedAtUs: startedAtUs,
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
  Map<String, int> capturedAtUs,
) => db
    .into(db.scanAttempts)
    .insert(
      ScanAttemptsCompanion.insert(
        attemptId: id,
        sessionId: session,
        attemptNumber: number,
        capturedAtUs: capturedAtUs[id] ?? _at,
        imageRelativePath: '$session/$id.jpg',
        imageByteSize: 1,
        imageSha256: _hash,
        status: 'staged',
      ),
    );

Future<void> _completeAttempt(BakeryDatabase db, String id, String session) =>
    (db.update(
      db.scanAttempts,
    )..where((row) => row.attemptId.equals(id))).write(
      ScanAttemptsCompanion(
        status: const Value('completed'),
        canonicalWidth: const Value(1),
        canonicalHeight: const Value(1),
        receiptRelativePath: Value('$session/$id.receipt.json'),
        receiptByteSize: const Value(1),
        receiptSha256: const Value(_hash),
        presentationPolicyId: const Value('customer_presentation_v1'),
        presentationPolicySha256: const Value(_hash),
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
        provenanceJson: _provenance,
        unknownReason: unknown ? const Value('seed') : const Value(null),
      ),
    );

const _provenance = '''
{
  "detector_id":"detector",
  "repvit_artifact_id":"repvit",
  "repvit_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "repvit_manifest_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "repvit_prototype_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "dinov3_artifact_id":"dino",
  "dinov3_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "dinov3_support_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "calibration_id":"calibration",
  "calibration_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "preprocess_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "canonical_frame_version":"exif_visual_rgb_v1",
  "exif_orientation":1
}
''';

Future<void> _candidate(BakeryDatabase db, String objectId, int rank) => db
    .into(db.inferenceCandidates)
    .insert(
      InferenceCandidatesCompanion.insert(
        inferenceCandidateId: '$objectId/candidate-$rank',
        inferenceObjectId: objectId,
        rank: rank,
        skuId: rank,
        skuName: 'candidate $rank',
        score: 1 - rank / 10,
      ),
    );

Future<void> _resolution(
  BakeryDatabase db,
  String id,
  String session,
  String? object,
  String source, {
  required int resolvedAtUs,
}) => db
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
        resolvedAtUs: resolvedAtUs,
        canonicalBboxJson: Value(object == null ? null : '[0,0,1,1]'),
        isCurrent: true,
      ),
    );
