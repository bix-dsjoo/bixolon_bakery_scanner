import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late BakeryDatabase database;
  late DatabaseReviewService service;

  setUp(() async {
    database = openInMemoryBakeryDatabase();
    service = DatabaseReviewService(
      database,
      createId: (_) => 'annotation-1',
      now: () => DateTime.utc(2026, 7, 31),
    );
    await _seed(database);
  });

  tearDown(() => database.close());

  test(
    'inbox orders integrity, override, unknown, catalog, then retake',
    () async {
      final page = await service.reviewInbox(const ReviewFilter(), null);

      expect(page.items.map((item) => item.sessionId), [
        'integrity',
        'override',
        'unknown',
        'catalog',
        'retake',
      ]);
    },
  );

  test(
    'review cursor preserves priority, timestamp, and session-id ordering',
    () async {
      await _insertSession(database, 'override-a', startedAtUs: 9);
      await _insertSession(database, 'override-b', startedAtUs: 9);
      await _insertAttemptAndObject(
        database,
        sessionId: 'override-a',
        source: 'customer_overrode_auto',
      );
      await _insertAttemptAndObject(
        database,
        sessionId: 'override-b',
        source: 'customer_overrode_auto',
      );

      final first = await service.reviewInbox(
        const ReviewFilter(),
        null,
        limit: 2,
      );
      final second = await service.reviewInbox(
        const ReviewFilter(),
        first.nextCursor,
        limit: 2,
      );
      final third = await service.reviewInbox(
        const ReviewFilter(),
        second.nextCursor,
        limit: 99,
      );

      expect(first.items.map((item) => item.sessionId), [
        'integrity',
        'override-a',
      ]);
      expect(second.items.map((item) => item.sessionId), [
        'override-b',
        'override',
      ]);
      expect(
        [
          ...first.items,
          ...second.items,
          ...third.items,
        ].map((item) => item.sessionId),
        [
          'integrity',
          'override-a',
          'override-b',
          'override',
          'unknown',
          'catalog',
          'retake',
        ],
      );
    },
  );

  test(
    'annotation is append-only and leaves checkout evidence untouched',
    () async {
      final inferenceBefore = await database
          .select(database.inferenceObjects)
          .get();
      final resolutionsBefore = await database
          .select(database.objectResolutions)
          .get();
      final orderBefore = await database.select(database.finalOrders).get();

      await service.annotate(
        const AdminReviewAnnotationDraft(
          sessionId: 'unknown',
          objectId: 'unknown-object',
          reviewStatus: ReviewStatus.reviewed,
          reasonCode: 'customer_choice_correct',
          authorLabel: 'prototype-admin',
          note: 'checked',
        ),
      );

      expect(
        await database.select(database.inferenceObjects).get(),
        inferenceBefore,
      );
      expect(
        await database.select(database.objectResolutions).get(),
        resolutionsBefore,
      );
      expect(await database.select(database.finalOrders).get(), orderBefore);
      final rows = await database.select(database.adminReviewAnnotations).get();
      expect(rows, hasLength(1));
      expect(rows.single.reviewStatus, 'reviewed');
      await expectLater(
        database
            .update(database.adminReviewAnnotations)
            .write(
              const AdminReviewAnnotationsCompanion(note: Value('changed')),
            ),
        throwsA(isA<Exception>()),
      );
    },
  );

  test(
    'review detail reads immutable AI outcome candidates unknown reason and customer resolution before annotations',
    () async {
      await database
          .into(database.inferenceCandidates)
          .insert(
            InferenceCandidatesCompanion.insert(
              inferenceCandidateId: 'unknown-candidate-1',
              inferenceObjectId: 'unknown-object',
              rank: 1,
              skuId: 7,
              skuName: 'Suggested bread',
              score: .71,
            ),
          );
      await service.annotate(
        const AdminReviewAnnotationDraft(
          sessionId: 'unknown',
          objectId: 'unknown-object',
          reviewStatus: ReviewStatus.reviewed,
          reasonCode: 'image_quality',
          note: 'first review',
          authorLabel: 'prototype-admin',
        ),
      );
      await DatabaseReviewService(
        database,
        createId: (_) => 'other-target-annotation',
        now: () => DateTime.utc(2026, 7, 31, 1),
      ).annotate(
        const AdminReviewAnnotationDraft(
          sessionId: 'unknown',
          reviewStatus: ReviewStatus.reviewed,
          reasonCode: 'catalog_issue',
          note: 'unrelated target note',
          authorLabel: 'prototype-admin',
        ),
      );

      final detail = await service.reviewDetail(
        const ReviewTarget(sessionId: 'unknown', objectId: 'unknown-object'),
      );

      expect(detail.immutableSession.sessionId, 'unknown');
      expect(detail.immutableSession.targetObjectId, 'unknown-object');
      expect(detail.immutableObjects, hasLength(1));
      final object = detail.immutableObjects.single;
      expect(object.skuName, 'Unknown');
      expect(object.unknownReason, 'ambiguous');
      expect(object.candidates.single.skuName, 'Suggested bread');
      expect(object.customerResolution!.source, 'customer_catalog');
      expect(object.customerResolution!.productName, 'Bread');
      expect(detail.annotations, hasLength(1));
      expect(detail.annotations.single.note, 'first review');
    },
  );

  test(
    'attempt-only review target exposes immutable objects from that exact attempt',
    () async {
      await database
          .into(database.scanAttempts)
          .insert(
            ScanAttemptsCompanion.insert(
              attemptId: 'unknown-attempt-2',
              sessionId: 'unknown',
              attemptNumber: 2,
              capturedAtUs: 3,
              imageRelativePath: 'unknown-2.jpg',
              imageByteSize: 1,
              imageSha256:
                  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              status: 'staged',
            ),
          );
      await database
          .into(database.inferenceObjects)
          .insert(
            InferenceObjectsCompanion.insert(
              inferenceObjectId: 'unknown-object-2',
              attemptId: 'unknown-attempt-2',
              objectId: 'unknown-object-2',
              skuId: const Value(7),
              skuName: 'Registered',
              decisionPath: 'repvit_direct',
              confidence: .8,
              bboxJson: '[0,0,1,1]',
              detectorSource: 'detector',
              detectorScore: .8,
              provenanceJson: _provenance,
              unknownReason: const Value(null),
            ),
          );

      final detail = await service.reviewDetail(
        const ReviewTarget(
          sessionId: 'unknown',
          attemptId: 'unknown-attempt-2',
        ),
      );

      expect(detail.immutableSession.targetAttemptId, 'unknown-attempt-2');
      expect(
        detail.immutableObjects.map((object) => object.inferenceObjectId),
        ['unknown-object-2'],
      );
    },
  );

  test('same annotation id retries idempotently without another row', () async {
    const draft = AdminReviewAnnotationDraft(
      sessionId: 'catalog',
      reviewStatus: ReviewStatus.reviewed,
      reasonCode: 'catalog_issue',
      authorLabel: 'prototype-admin',
    );
    await service.annotate(draft);
    await service.annotate(draft);
    expect(
      await database.select(database.adminReviewAnnotations).get(),
      hasLength(1),
    );
  });

  test(
    'concurrent same-id retries reconcile one identical annotation',
    () async {
      const draft = AdminReviewAnnotationDraft(
        sessionId: 'catalog',
        reviewStatus: ReviewStatus.reviewed,
        reasonCode: 'catalog_issue',
        authorLabel: 'prototype-admin',
      );
      final second = DatabaseReviewService(
        database,
        createId: (_) => 'concurrent-annotation',
        now: () => DateTime.utc(2026, 7, 31),
      );
      final first = DatabaseReviewService(
        database,
        createId: (_) => 'concurrent-annotation',
        now: () => DateTime.utc(2026, 7, 31),
      );

      await Future.wait([first.annotate(draft), second.annotate(draft)]);

      expect(
        await (database.select(
              database.adminReviewAnnotations,
            )..where((row) => row.annotationId.equals('concurrent-annotation')))
            .get(),
        hasLength(1),
      );
    },
  );

  test(
    'concurrent same-id divergent annotations fail without rewriting',
    () async {
      final first = DatabaseReviewService(
        database,
        createId: (_) => 'divergent-annotation',
        now: () => DateTime.utc(2026, 7, 31),
      );
      final second = DatabaseReviewService(
        database,
        createId: (_) => 'divergent-annotation',
        now: () => DateTime.utc(2026, 7, 31),
      );
      const baseline = AdminReviewAnnotationDraft(
        sessionId: 'catalog',
        reviewStatus: ReviewStatus.reviewed,
        reasonCode: 'catalog_issue',
        authorLabel: 'prototype-admin',
      );
      const divergent = AdminReviewAnnotationDraft(
        sessionId: 'catalog',
        reviewStatus: ReviewStatus.needsFollowUp,
        reasonCode: 'image_quality',
        authorLabel: 'prototype-admin',
      );

      final results = await Future.wait<Object?>([
        first
            .annotate(baseline)
            .then<Object?>((_) => null, onError: (Object error) => error),
        second
            .annotate(divergent)
            .then<Object?>((_) => null, onError: (Object error) => error),
      ]);

      expect(results.where((result) => result != null), hasLength(1));
      final row =
          await (database.select(database.adminReviewAnnotations)..where(
                (row) => row.annotationId.equals('divergent-annotation'),
              ))
              .getSingle();
      expect(row.reasonCode, anyOf('catalog_issue', 'image_quality'));
    },
  );

  test(
    'correct product must belong to the target session frozen catalog',
    () async {
      await expectLater(
        service.annotate(
          const AdminReviewAnnotationDraft(
            sessionId: 'unknown',
            reviewStatus: ReviewStatus.reviewed,
            correctProductId: 'missing-product',
            reasonCode: 'ai_incorrect',
            authorLabel: 'prototype-admin',
          ),
        ),
        throwsA(isA<ArgumentError>()),
      );
    },
  );

  test(
    'raw SQL allows a retired product in frozen catalog and rejects others',
    () async {
      await database.customStatement(
        '''
INSERT INTO admin_review_annotations (
  annotation_id, session_id, review_status, correct_product_id,
  reason_code, author_label, created_at_us
) VALUES (?, ?, ?, ?, ?, ?, ?)
''',
        [
          'raw-retired',
          'unknown',
          'reviewed',
          'product',
          'catalog_issue',
          'admin',
          1,
        ],
      );

      await database
          .into(database.catalogRevisions)
          .insert(
            CatalogRevisionsCompanion.insert(
              revisionId: 'catalog-v2',
              sha256: 'b' * 64,
              createdAtUs: 2,
              isActive: false,
            ),
          );
      await database
          .into(database.products)
          .insert(
            ProductsCompanion.insert(
              productRevisionId: 'catalog-v2/other',
              catalogRevisionId: 'catalog-v2',
              productId: 'other-product',
              displayName: 'Other',
              unitPriceKrw: 1000,
              categoryId: 'bread',
              active: true,
              sortOrder: 2,
            ),
          );
      for (final productId in ['other-product', 'missing-product']) {
        await expectLater(
          database.customStatement(
            '''
INSERT INTO admin_review_annotations (
  annotation_id, session_id, review_status, correct_product_id,
  reason_code, author_label, created_at_us
) VALUES (?, ?, ?, ?, ?, ?, ?)
''',
            [
              'raw-$productId',
              'unknown',
              'reviewed',
              productId,
              'catalog_issue',
              'admin',
              2,
            ],
          ),
          throwsA(isA<Exception>()),
        );
      }
    },
  );
}

Future<void> _insertSession(
  BakeryDatabase db,
  String sessionId, {
  required int startedAtUs,
}) async {
  const hash =
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  await db
      .into(db.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: sessionId,
          state: 'active',
          startedAtUs: startedAtUs,
          catalogRevisionId: 'catalog-v1',
          settingsRevisionId: 'settings-v1',
          detectorId: 'detector',
          detectorSha256: hash,
          repvitArtifactId: 'repvit',
          repvitSha256: hash,
          repvitManifestSha256: hash,
          repvitPrototypeSha256: hash,
          dinov3ArtifactId: 'dino',
          dinov3Sha256: hash,
          dinov3SupportSha256: hash,
          calibrationId: 'calibration',
          calibrationSha256: hash,
          preprocessSha256: hash,
          fusionPolicyId: 'policy',
          fusionPolicySha256: hash,
          configSnapshotJson: '{}',
        ),
      );
}

Future<void> _insertAttemptAndObject(
  BakeryDatabase db, {
  required String sessionId,
  required String source,
}) async {
  const hash =
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  await db
      .into(db.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: '$sessionId-attempt',
          sessionId: sessionId,
          attemptNumber: 1,
          capturedAtUs: 1,
          imageRelativePath: '$sessionId.jpg',
          imageByteSize: 1,
          imageSha256: hash,
          status: 'staged',
        ),
      );
  await db
      .into(db.inferenceObjects)
      .insert(
        InferenceObjectsCompanion.insert(
          inferenceObjectId: '$sessionId-object',
          attemptId: '$sessionId-attempt',
          objectId: '$sessionId-object',
          skuId: const Value(7),
          skuName: 'Registered',
          decisionPath: 'repvit_direct',
          confidence: .2,
          bboxJson: '[0,0,1,1]',
          detectorSource: 'detector',
          detectorScore: .5,
          provenanceJson: _provenance,
          unknownReason: const Value(null),
        ),
      );
  await db
      .into(db.objectResolutions)
      .insert(
        ObjectResolutionsCompanion.insert(
          resolutionId: '$sessionId-resolution',
          sessionId: sessionId,
          inferenceObjectId: Value('$sessionId-object'),
          productRevisionId: 'catalog-v1/product',
          productId: 'product',
          productName: 'Bread',
          unitPriceKrw: 1000,
          source: source,
          resolvedAtUs: 2,
          canonicalBboxJson: const Value('[0,0,1,1]'),
          isCurrent: true,
        ),
      );
}

Future<void> _seed(BakeryDatabase db) async {
  const hash =
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
  await db
      .into(db.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: 'catalog-v1',
          sha256: hash,
          createdAtUs: 1,
          isActive: true,
        ),
      );
  await db
      .into(db.products)
      .insert(
        ProductsCompanion.insert(
          productRevisionId: 'catalog-v1/product',
          catalogRevisionId: 'catalog-v1',
          productId: 'product',
          displayName: 'Bread',
          unitPriceKrw: 1000,
          categoryId: 'bread',
          active: false,
          sortOrder: 1,
        ),
      );
  for (final id in ['integrity', 'override', 'unknown', 'catalog', 'retake']) {
    await db
        .into(db.checkoutSessions)
        .insert(
          CheckoutSessionsCompanion.insert(
            sessionId: id,
            state: 'active',
            startedAtUs: 1,
            catalogRevisionId: 'catalog-v1',
            settingsRevisionId: 'settings-v1',
            detectorId: 'detector',
            detectorSha256: hash,
            repvitArtifactId: 'repvit',
            repvitSha256: hash,
            repvitManifestSha256: hash,
            repvitPrototypeSha256: hash,
            dinov3ArtifactId: 'dino',
            dinov3Sha256: hash,
            dinov3SupportSha256: hash,
            calibrationId: 'calibration',
            calibrationSha256: hash,
            preprocessSha256: hash,
            fusionPolicyId: 'policy',
            fusionPolicySha256: hash,
            configSnapshotJson: '{}',
          ),
        );
  }
  await db
      .into(db.auditEvents)
      .insert(
        AuditEventsCompanion.insert(
          eventId: 'integrity-event',
          sessionId: const Value('integrity'),
          eventType: 'evidence_integrity_failure',
          occurredAtUs: 1,
        ),
      );
  for (final id in ['override', 'unknown', 'catalog', 'retake']) {
    await db
        .into(db.scanAttempts)
        .insert(
          ScanAttemptsCompanion.insert(
            attemptId: '$id-attempt',
            sessionId: id,
            attemptNumber: 1,
            capturedAtUs: 1,
            imageRelativePath: '$id.jpg',
            imageByteSize: 1,
            imageSha256: hash,
            status: 'staged',
          ),
        );
  }
  for (final id in ['override', 'unknown', 'catalog']) {
    final isUnknown = id == 'unknown';
    await db
        .into(db.inferenceObjects)
        .insert(
          InferenceObjectsCompanion.insert(
            inferenceObjectId: '$id-object',
            attemptId: '$id-attempt',
            objectId: '$id-object',
            skuId: Value(isUnknown ? null : 7),
            skuName: isUnknown ? 'Unknown' : 'Registered',
            decisionPath: isUnknown ? 'unknown_top3' : 'repvit_direct',
            confidence: .2,
            bboxJson: '[0,0,1,1]',
            detectorSource: 'detector',
            detectorScore: .5,
            provenanceJson: _provenance,
            unknownReason: Value(isUnknown ? 'ambiguous' : null),
          ),
        );
  }
  for (final entry in <(String, String)>[
    ('override', 'customer_overrode_auto'),
    ('unknown', 'customer_catalog'),
    ('catalog', 'customer_catalog'),
  ]) {
    await db
        .into(db.objectResolutions)
        .insert(
          ObjectResolutionsCompanion.insert(
            resolutionId: '${entry.$1}-resolution',
            sessionId: entry.$1,
            inferenceObjectId: Value('${entry.$1}-object'),
            productRevisionId: 'catalog-v1/product',
            productId: 'product',
            productName: 'Bread',
            unitPriceKrw: 1000,
            source: entry.$2,
            resolvedAtUs: 2,
            canonicalBboxJson: const Value('[0,0,1,1]'),
            isCurrent: true,
          ),
        );
  }
  await db
      .into(db.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: 'retake-attempt-2',
          sessionId: 'retake',
          attemptNumber: 2,
          capturedAtUs: 2,
          imageRelativePath: 'retake-2.jpg',
          imageByteSize: 1,
          imageSha256: hash,
          status: 'staged',
        ),
      );
}

const _provenance =
    '{"detector_id":"detector","repvit_artifact_id":"repvit","repvit_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","repvit_manifest_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","repvit_prototype_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","dinov3_artifact_id":"dino","dinov3_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","dinov3_support_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","calibration_id":"calibration","calibration_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","preprocess_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","canonical_frame_version":"exif_visual_rgb_v1","exif_orientation":1}';
