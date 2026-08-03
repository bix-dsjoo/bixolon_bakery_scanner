import 'dart:convert';

import 'package:drift/drift.dart' show OrderingTerm;
import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  test(
    'customer checkout retains immutable inference separately from paid choices',
    () async {
      final journey = await CustomerCheckoutJourneyFixture.create();
      addTearDown(journey.dispose);

      await journey.completeRegisteredUnknownAndManualCartPurchase();

      final attempt = await journey.database
          .select(journey.database.scanAttempts)
          .getSingle();
      final objects = await journey.database
          .select(journey.database.inferenceObjects)
          .get();
      final resolutions = await journey.database
          .select(journey.database.objectResolutions)
          .get();
      final orders = await journey.database
          .select(journey.database.finalOrders)
          .get();
      final payments = await journey.database
          .select(journey.database.simulatedPayments)
          .get();
      final lines = await journey.database
          .select(journey.database.finalOrderLines)
          .get();

      expect(objects.where((object) => object.skuId == null), hasLength(1));
      expect(objects.where((object) => object.skuId != null), hasLength(1));
      final registered = objects.singleWhere((object) => object.skuId != null);
      final unknown = objects.singleWhere((object) => object.skuId == null);
      expect(registered.objectId, 'object-1');
      expect(registered.skuId, 6);
      expect(registered.decisionPath, 'repvit_direct');
      expect(registered.detectorSource, 'rfdetr');
      expect(unknown.objectId, 'object-2');
      expect(unknown.skuId, isNull);
      expect(unknown.decisionPath, 'unknown_top3');
      expect(unknown.unknownReason, 'consensus_failed');
      _expectPersistedObjectProvenance(registered.provenanceJson);
      _expectPersistedObjectProvenance(
        unknown.provenanceJson,
        failureCode: 'consensus_failed',
      );
      expect(resolutions.map((row) => row.source).toSet(), {
        'ai_auto_customer_accepted',
        'customer_top3',
      });
      expect(
        lines.map((line) => '${line.productId}:${line.quantity}').toSet(),
        {'croissant:1', 'sugar-donut:1', 'milk-bread:2'},
      );
      expect(
        lines
            .map((line) => '${line.productId}:${line.resolutionSource}')
            .toSet(),
        {
          'croissant:ai_auto_customer_accepted',
          'sugar-donut:customer_top3',
          'milk-bread:customer_manual_cart',
        },
      );
      expect(orders.single.totalQuantity, 4);
      expect(orders.single.totalAmountKrw, 7900);
      expect(payments.single.amountKrw, 7900);
      expect(attempt.imageSha256, journey.captureSha256);
      expect(attempt.receiptSha256, journey.inferenceReceiptSha256);
      expect(await journey.hasVerifiedAuditEvidence(attempt), isTrue);
      expect(journey.customerReturnedToReady, isTrue);
    },
  );

  test(
    'controller audits Top3 and catalog choices without changing Unknown inference',
    () async {
      await _expectCustomerResolution(
        choose: (journey) => journey.controller.chooseTop3('object-2', 10),
        expectedSource: 'customer_top3',
        expectedCandidateRank: 1,
      );
      await _expectCustomerResolution(
        choose: (journey) =>
            journey.controller.chooseCatalog('object-2', 'milk-bread'),
        expectedSource: 'customer_catalog',
        expectedCandidateRank: null,
      );
    },
  );
}

Future<void> _expectCustomerResolution({
  required Future<void> Function(CustomerCheckoutJourneyFixture) choose,
  required String expectedSource,
  required int? expectedCandidateRank,
}) async {
  final journey = await CustomerCheckoutJourneyFixture.create();
  try {
    await journey.controller.initialize();
    await journey.controller.scan();
    final before = await _unknownEvidenceSnapshot(journey);

    expect(before.skuId, isNull);
    expect(before.skuName, 'Unknown');
    expect(before.decisionPath, 'unknown_top3');
    expect(before.provenanceJson, isNotEmpty);
    expect(before.candidates, [
      (rank: 1, skuId: 10, skuName: 'Sugar Donut', score: 0.88),
      (rank: 2, skuId: 11, skuName: 'Cream Donut', score: 0.76),
      (rank: 3, skuId: 12, skuName: 'Glazed Donut', score: 0.62),
    ]);
    await choose(journey);

    final resolution = await (journey.database
          .select(journey.database.objectResolutions)
        ..where(
          (row) => row.inferenceObjectId.equals(before.inferenceObjectId),
        ))
        .getSingle();
    expect(resolution.source, expectedSource);
    expect(resolution.candidateRank, expectedCandidateRank);
    if (expectedCandidateRank != null) {
      expect(resolution.candidateRank, inInclusiveRange(1, 3));
    }
    final after = await _unknownEvidenceSnapshot(journey);
    expect(after.inferenceObjectId, before.inferenceObjectId);
    expect(after.skuId, before.skuId);
    expect(after.skuName, before.skuName);
    expect(after.decisionPath, before.decisionPath);
    expect(after.confidence, before.confidence);
    expect(after.bboxJson, before.bboxJson);
    expect(after.detectorSource, before.detectorSource);
    expect(after.detectorScore, before.detectorScore);
    expect(after.provenanceJson, before.provenanceJson);
    expect(after.unknownReason, before.unknownReason);
    expect(after.candidates, before.candidates);
  } finally {
    await journey.dispose();
  }
}

Future<
  ({
    String inferenceObjectId,
    int? skuId,
    String skuName,
    String decisionPath,
    double confidence,
    String bboxJson,
    String detectorSource,
    double detectorScore,
    String provenanceJson,
    String? unknownReason,
    List<({int rank, int skuId, String skuName, double score})> candidates,
  })
> _unknownEvidenceSnapshot(CustomerCheckoutJourneyFixture journey) async {
  final unknown = await (journey.database
        .select(journey.database.inferenceObjects)
        ..where((row) => row.objectId.equals('object-2')))
      .getSingle();
  final candidates = await (journey.database
        .select(journey.database.inferenceCandidates)
      ..where(
        (row) => row.inferenceObjectId.equals(unknown.inferenceObjectId),
      )
      ..orderBy([(row) => OrderingTerm.asc(row.rank)]))
      .get();
  return (
    inferenceObjectId: unknown.inferenceObjectId,
    skuId: unknown.skuId,
    skuName: unknown.skuName,
    decisionPath: unknown.decisionPath,
    confidence: unknown.confidence,
    bboxJson: unknown.bboxJson,
    detectorSource: unknown.detectorSource,
    detectorScore: unknown.detectorScore,
    provenanceJson: unknown.provenanceJson,
    unknownReason: unknown.unknownReason,
    candidates: [
      for (final candidate in candidates)
        (
          rank: candidate.rank,
          skuId: candidate.skuId,
          skuName: candidate.skuName,
          score: candidate.score,
        ),
    ],
  );
}

void _expectPersistedObjectProvenance(String encoded, {String? failureCode}) {
  final provenance = jsonDecode(encoded) as Map<String, Object?>;
  expect(provenance, {
    'detector_id': 'rfdetr_large_bakery_v1',
    'repvit_artifact_id': 'repvit_m1_15plus5_v1',
    'repvit_sha256': 'a' * 64,
    'repvit_manifest_sha256': 'b' * 64,
    'repvit_prototype_sha256': 'c' * 64,
    'dinov3_artifact_id': 'dinov3_vits16_15plus5_v1',
    'dinov3_sha256': 'd' * 64,
    'dinov3_support_sha256': 'e' * 64,
    'calibration_id': 'policy-v1',
    'calibration_sha256': 'f' * 64,
    'preprocess_sha256': '0' * 64,
    'canonical_frame_version': 'exif_visual_rgb_v1',
    'exif_orientation': 1,
    'failure_code': failureCode,
  });
}
