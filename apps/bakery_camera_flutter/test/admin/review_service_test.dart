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
