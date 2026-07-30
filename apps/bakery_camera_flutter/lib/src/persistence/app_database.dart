// ignore_for_file: recursive_getters

import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

part 'app_database.g.dart';

const applicationVersion = '1.1.0+4';

@DataClassName('CatalogRevisionRow')
class CatalogRevisions extends Table {
  TextColumn get revisionId => text().withLength(min: 1)();
  TextColumn get sha256 => text().withLength(min: 64, max: 64)();
  IntColumn get createdAtUs => integer()();
  BoolColumn get isActive => boolean()();

  @override
  Set<Column<Object>> get primaryKey => {revisionId};

  @override
  List<String> get customConstraints => const [
    "CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*')",
  ];
}

@DataClassName('ProductRow')
class Products extends Table {
  TextColumn get productRevisionId => text().withLength(min: 1)();
  TextColumn get catalogRevisionId =>
      text().references(CatalogRevisions, #revisionId)();
  TextColumn get productId => text().withLength(min: 1)();
  TextColumn get displayName => text().withLength(min: 1)();
  IntColumn get unitPriceKrw =>
      integer().check(unitPriceKrw.isBiggerOrEqualValue(0))();
  IntColumn get recognitionSkuId =>
      integer().nullable().check(recognitionSkuId.isBetweenValues(1, 20))();
  TextColumn get categoryId => text().withLength(min: 1)();
  TextColumn get photoRelativePath => text().nullable()();
  IntColumn get photoByteSize =>
      integer().nullable().check(photoByteSize.isBiggerThanValue(0))();
  TextColumn get photoSha256 =>
      text().nullable().withLength(min: 64, max: 64)();
  TextColumn get photoMediaType => text().nullable()();
  TextColumn get photoProvenanceNote => text().nullable()();
  BoolColumn get active => boolean()();
  IntColumn get sortOrder =>
      integer().check(sortOrder.isBiggerOrEqualValue(0))();

  @override
  Set<Column<Object>> get primaryKey => {productRevisionId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (catalog_revision_id, product_id)',
    'UNIQUE (catalog_revision_id, recognition_sku_id)',
    '''
CHECK (
  (photo_relative_path IS NULL AND photo_byte_size IS NULL
    AND photo_sha256 IS NULL AND photo_media_type IS NULL
    AND photo_provenance_note IS NULL)
  OR
  (photo_relative_path IS NOT NULL AND length(photo_relative_path) > 0
    AND photo_relative_path NOT GLOB '/*'
    AND photo_relative_path NOT GLOB '\\*'
    AND photo_relative_path NOT LIKE '%:%'
    AND photo_relative_path NOT LIKE '%..%'
    AND photo_byte_size IS NOT NULL AND photo_byte_size > 0
    AND photo_sha256 IS NOT NULL AND length(photo_sha256) = 64
    AND photo_sha256 NOT GLOB '*[^0-9a-f]*'
    AND photo_media_type IS NOT NULL AND length(photo_media_type) > 0
    AND photo_provenance_note IS NOT NULL
    AND length(photo_provenance_note) > 0)
)''',
  ];
}

@DataClassName('SettingsRevisionRow')
class SettingsRevisions extends Table {
  TextColumn get revisionId => text().withLength(min: 1)();
  IntColumn get createdAtUs => integer()();
  IntColumn get retryLimit =>
      integer().check(retryLimit.isBiggerOrEqualValue(0))();
  IntColumn get paymentCompleteDurationSeconds =>
      integer().check(paymentCompleteDurationSeconds.isBiggerThanValue(0))();
  BoolColumn get customerAutoReset => boolean()();
  IntColumn get evidenceRetentionDays =>
      integer().check(evidenceRetentionDays.isBiggerThanValue(0))();
  TextColumn get locale => text().withLength(min: 1)();
  TextColumn get kioskDisplayName => text().withLength(min: 1)();
  TextColumn get adminAuthorLabel => text().withLength(min: 1)();

  @override
  Set<Column<Object>> get primaryKey => {revisionId};
}

@DataClassName('AppSettingsRow')
class AppSettings extends Table {
  TextColumn get settingsId => text().withLength(min: 1)();
  TextColumn get activeSettingsRevisionId =>
      text().references(SettingsRevisions, #revisionId)();
  TextColumn get applicationVersionValue => text().withLength(min: 1)();
  TextColumn get lastMigrationResult => text().withLength(min: 1)();

  @override
  Set<Column<Object>> get primaryKey => {settingsId};
}

@DataClassName('CheckoutSessionRow')
class CheckoutSessions extends Table {
  TextColumn get sessionId => text().withLength(min: 1)();
  TextColumn get state => text().withLength(min: 1)();
  IntColumn get startedAtUs => integer()();
  IntColumn get terminalAtUs => integer().nullable()();
  TextColumn get terminalReason => text().nullable()();
  TextColumn get catalogRevisionId =>
      text().references(CatalogRevisions, #revisionId)();
  TextColumn get settingsRevisionId =>
      text().references(SettingsRevisions, #revisionId)();
  TextColumn get detectorId => text().withLength(min: 1)();
  TextColumn get detectorSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get repvitArtifactId => text().withLength(min: 1)();
  TextColumn get repvitSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get repvitManifestSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get repvitPrototypeSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get dinov3ArtifactId => text().withLength(min: 1)();
  TextColumn get dinov3Sha256 => text().withLength(min: 64, max: 64)();
  TextColumn get dinov3SupportSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get calibrationId => text().withLength(min: 1)();
  TextColumn get calibrationSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get preprocessSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get fusionPolicyId => text().withLength(min: 1)();
  TextColumn get fusionPolicySha256 => text().withLength(min: 64, max: 64)();
  TextColumn get configSnapshotJson => text().withLength(min: 2)();

  @override
  Set<Column<Object>> get primaryKey => {sessionId};

  @override
  List<String> get customConstraints => const [
    "CHECK (state IN ('active', 'completed', 'abandoned', 'interrupted', 'failed'))",
    'CHECK (json_valid(config_snapshot_json))',
    '''
CHECK (
  length(detector_sha256) = 64
  AND detector_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(repvit_sha256) = 64
  AND repvit_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(repvit_manifest_sha256) = 64
  AND repvit_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(repvit_prototype_sha256) = 64
  AND repvit_prototype_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(dinov3_sha256) = 64
  AND dinov3_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(dinov3_support_sha256) = 64
  AND dinov3_support_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(calibration_sha256) = 64
  AND calibration_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(preprocess_sha256) = 64
  AND preprocess_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(fusion_policy_sha256) = 64
  AND fusion_policy_sha256 NOT GLOB '*[^0-9a-f]*'
)''',
    '''
CHECK (
  (terminal_at_us IS NULL AND terminal_reason IS NULL
    AND state = 'active')
  OR
  (terminal_at_us IS NOT NULL AND terminal_reason IS NOT NULL
    AND state <> 'active')
)''',
  ];
}

@DataClassName('ScanAttemptRow')
class ScanAttempts extends Table {
  TextColumn get attemptId => text().withLength(min: 1)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  IntColumn get attemptNumber =>
      integer().check(attemptNumber.isBiggerThanValue(0))();
  IntColumn get capturedAtUs => integer()();
  TextColumn get imageRelativePath => text().withLength(min: 1)();
  IntColumn get imageByteSize =>
      integer().check(imageByteSize.isBiggerThanValue(0))();
  TextColumn get imageSha256 => text().withLength(min: 64, max: 64)();
  TextColumn get status => text().withLength(min: 1)();
  IntColumn get canonicalWidth => integer().nullable()();
  IntColumn get canonicalHeight => integer().nullable()();
  TextColumn get receiptRelativePath => text().nullable()();
  IntColumn get receiptByteSize => integer().nullable()();
  TextColumn get receiptSha256 =>
      text().nullable().withLength(min: 64, max: 64)();
  TextColumn get presentationState => text().nullable()();
  BoolColumn get finalCountUsable => boolean().nullable()();
  TextColumn get retakeScope => text().nullable()();
  TextColumn get retakeReason => text().nullable()();
  TextColumn get presentationPolicyId => text().nullable()();
  TextColumn get presentationPolicySha256 =>
      text().nullable().withLength(min: 64, max: 64)();
  RealColumn get decodePreprocessMs => real().nullable()();
  RealColumn get detectorMs => real().nullable()();
  RealColumn get repvitMs => real().nullable()();
  RealColumn get dinov3Ms => real().nullable()();
  RealColumn get postprocessMs => real().nullable()();
  RealColumn get totalMs => real().nullable()();
  TextColumn get startupDevice => text().nullable()();
  RealColumn get startupLoadMs => real().nullable()();
  RealColumn get startupWarmupMs => real().nullable()();
  TextColumn get startupFallbackReason => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {attemptId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (session_id, attempt_number)',
    "CHECK (status IN ('staged', 'completed'))",
    '''
CHECK (
  length(image_sha256) = 64
  AND image_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(image_relative_path) > 0
  AND image_relative_path NOT GLOB '/*'
  AND image_relative_path NOT GLOB '\\*'
  AND image_relative_path NOT LIKE '%:%'
  AND image_relative_path NOT LIKE '%..%'
)''',
    '''
CHECK (
  (status = 'staged' AND canonical_width IS NULL AND canonical_height IS NULL
    AND receipt_relative_path IS NULL AND receipt_byte_size IS NULL
    AND receipt_sha256 IS NULL)
  OR (status = 'completed'
    AND canonical_width IS NOT NULL AND canonical_width > 0
    AND canonical_height IS NOT NULL AND canonical_height > 0
    AND receipt_relative_path IS NOT NULL
    AND length(receipt_relative_path) > 0
    AND receipt_byte_size IS NOT NULL AND receipt_byte_size > 0
    AND receipt_sha256 IS NOT NULL AND length(receipt_sha256) = 64
    AND presentation_policy_id IS NOT NULL
    AND length(presentation_policy_id) > 0
    AND presentation_policy_sha256 IS NOT NULL
    AND length(presentation_policy_sha256) = 64)
)''',
    '''
CHECK (
  receipt_relative_path IS NULL
  OR (
    receipt_relative_path NOT GLOB '/*'
    AND receipt_relative_path NOT GLOB '\\*'
    AND receipt_relative_path NOT LIKE '%:%'
    AND receipt_relative_path NOT LIKE '%..%'
    AND receipt_sha256 IS NOT NULL
    AND receipt_sha256 NOT GLOB '*[^0-9a-f]*'
    AND presentation_policy_sha256 IS NOT NULL
    AND presentation_policy_sha256 NOT GLOB '*[^0-9a-f]*'
  )
)''',
  ];
}

@DataClassName('InferenceObjectRow')
class InferenceObjects extends Table {
  TextColumn get inferenceObjectId => text().withLength(min: 1)();
  TextColumn get attemptId => text().references(ScanAttempts, #attemptId)();
  TextColumn get objectId => text().withLength(min: 1)();
  IntColumn get skuId =>
      integer().nullable().check(skuId.isBetweenValues(1, 20))();
  TextColumn get skuName => text().withLength(min: 1)();
  TextColumn get decisionPath => text().withLength(min: 1)();
  RealColumn get confidence => real().check(confidence.isBetweenValues(0, 1))();
  TextColumn get bboxJson => text().withLength(min: 9)();
  TextColumn get detectorSource => text().withLength(min: 1)();
  RealColumn get detectorScore =>
      real().check(detectorScore.isBetweenValues(0, 1))();
  TextColumn get provenanceJson => text().withLength(min: 100)();
  TextColumn get unknownReason => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {inferenceObjectId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (attempt_id, object_id)',
    '''
CHECK (
  (sku_id IS NOT NULL AND sku_name <> 'Unknown'
    AND decision_path IN ('repvit_direct', 'dinov3_confirmed', 'fusion_ranked')
    AND unknown_reason IS NULL)
  OR
  (sku_id IS NULL AND sku_name = 'Unknown'
    AND decision_path = 'unknown_top3' AND length(unknown_reason) > 0)
)''',
    'CHECK (json_valid(bbox_json) AND json_array_length(bbox_json) = 4)',
    '''
CHECK (
  CASE WHEN json_valid(provenance_json) THEN
    json_type(provenance_json, '\$.detector_id') = 'text'
    AND json_type(provenance_json, '\$.repvit_artifact_id') = 'text'
    AND json_extract(provenance_json, '\$.repvit_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.repvit_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.repvit_sha256')) = 64
    AND json_extract(provenance_json, '\$.repvit_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_extract(provenance_json, '\$.repvit_manifest_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.repvit_manifest_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.repvit_manifest_sha256')) = 64
    AND json_extract(provenance_json, '\$.repvit_manifest_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_extract(provenance_json, '\$.repvit_prototype_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.repvit_prototype_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.repvit_prototype_sha256')) = 64
    AND json_extract(provenance_json, '\$.repvit_prototype_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_type(provenance_json, '\$.dinov3_artifact_id') = 'text'
    AND json_extract(provenance_json, '\$.dinov3_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.dinov3_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.dinov3_sha256')) = 64
    AND json_extract(provenance_json, '\$.dinov3_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_extract(provenance_json, '\$.dinov3_support_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.dinov3_support_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.dinov3_support_sha256')) = 64
    AND json_extract(provenance_json, '\$.dinov3_support_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_type(provenance_json, '\$.calibration_id') = 'text'
    AND json_extract(provenance_json, '\$.calibration_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.calibration_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.calibration_sha256')) = 64
    AND json_extract(provenance_json, '\$.calibration_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_extract(provenance_json, '\$.preprocess_sha256') IS NOT NULL
    AND json_type(provenance_json, '\$.preprocess_sha256') = 'text'
    AND length(json_extract(provenance_json, '\$.preprocess_sha256')) = 64
    AND json_extract(provenance_json, '\$.preprocess_sha256')
      NOT GLOB '*[^0-9a-f]*'
    AND json_extract(provenance_json, '\$.canonical_frame_version')
      = 'exif_visual_rgb_v1'
    AND json_extract(provenance_json, '\$.exif_orientation') BETWEEN 1 AND 8
  ELSE 0 END
)''',
  ];
}

@DataClassName('InferenceCandidateRow')
class InferenceCandidates extends Table {
  TextColumn get inferenceCandidateId => text().withLength(min: 1)();
  TextColumn get inferenceObjectId =>
      text().references(InferenceObjects, #inferenceObjectId)();
  IntColumn get rank => integer().check(rank.isBetweenValues(1, 3))();
  IntColumn get skuId => integer().check(skuId.isBetweenValues(1, 20))();
  TextColumn get skuName => text().withLength(min: 1)();
  RealColumn get score => real().check(score.isBetweenValues(0, 1))();

  @override
  Set<Column<Object>> get primaryKey => {inferenceCandidateId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (inference_object_id, rank)',
  ];
}

@DataClassName('ObjectResolutionRow')
class ObjectResolutions extends Table {
  TextColumn get resolutionId => text().withLength(min: 1)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  TextColumn get inferenceObjectId =>
      text().nullable().references(InferenceObjects, #inferenceObjectId)();
  TextColumn get productRevisionId =>
      text().references(Products, #productRevisionId)();
  TextColumn get productId => text().withLength(min: 1)();
  IntColumn get recognitionSkuId => integer().nullable()();
  TextColumn get productName => text().withLength(min: 1)();
  IntColumn get unitPriceKrw =>
      integer().check(unitPriceKrw.isBiggerOrEqualValue(0))();
  TextColumn get source => text().withLength(min: 1)();
  IntColumn get resolvedAtUs => integer()();
  IntColumn get candidateRank => integer().nullable()();
  TextColumn get canonicalBboxJson => text().nullable()();
  BoolColumn get isCurrent => boolean()();

  @override
  Set<Column<Object>> get primaryKey => {resolutionId};

  @override
  List<String> get customConstraints => const [
    '''
CHECK (source IN (
  'ai_auto_customer_accepted', 'customer_top3', 'customer_catalog',
  'customer_overrode_auto', 'customer_manual_cart'
))''',
    '''
CHECK (
  (inference_object_id IS NULL AND source = 'customer_manual_cart'
    AND canonical_bbox_json IS NULL)
  OR
  (inference_object_id IS NOT NULL AND canonical_bbox_json IS NOT NULL
    AND json_valid(canonical_bbox_json)
    AND json_array_length(canonical_bbox_json) = 4)
)''',
  ];
}

@DataClassName('DraftOrderLineRow')
class DraftOrderLines extends Table {
  TextColumn get draftLineId => text().withLength(min: 1)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  TextColumn get productRevisionId =>
      text().references(Products, #productRevisionId)();
  TextColumn get productId => text().withLength(min: 1)();
  TextColumn get productName => text().withLength(min: 1)();
  IntColumn get recognitionSkuId => integer().nullable()();
  IntColumn get unitPriceKrw =>
      integer().check(unitPriceKrw.isBiggerOrEqualValue(0))();
  IntColumn get quantity => integer().check(quantity.isBiggerThanValue(0))();

  @override
  Set<Column<Object>> get primaryKey => {draftLineId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (session_id, product_id)',
  ];
}

@DataClassName('FinalOrderRow')
class FinalOrders extends Table {
  TextColumn get orderId => text().withLength(min: 1)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  TextColumn get catalogRevisionId =>
      text().references(CatalogRevisions, #revisionId)();
  IntColumn get createdAtUs => integer()();
  IntColumn get totalQuantity =>
      integer().check(totalQuantity.isBiggerThanValue(0))();
  IntColumn get totalAmountKrw =>
      integer().check(totalAmountKrw.isBiggerOrEqualValue(0))();
  TextColumn get receiptRelativePath => text().withLength(min: 1)();
  IntColumn get receiptByteSize =>
      integer().check(receiptByteSize.isBiggerThanValue(0))();
  TextColumn get receiptSha256 => text().withLength(min: 64, max: 64)();

  @override
  Set<Column<Object>> get primaryKey => {orderId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (session_id)',
    '''
CHECK (
  length(receipt_sha256) = 64
  AND receipt_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(receipt_relative_path) > 0
  AND receipt_relative_path NOT GLOB '/*'
  AND receipt_relative_path NOT GLOB '\\*'
  AND receipt_relative_path NOT LIKE '%:%'
  AND receipt_relative_path NOT LIKE '%..%'
)''',
  ];
}

@DataClassName('FinalOrderLineRow')
class FinalOrderLines extends Table {
  TextColumn get finalLineId => text().withLength(min: 1)();
  TextColumn get orderId => text().references(FinalOrders, #orderId)();
  TextColumn get productRevisionId =>
      text().references(Products, #productRevisionId)();
  TextColumn get productId => text().withLength(min: 1)();
  IntColumn get recognitionSkuId => integer().nullable()();
  TextColumn get productName => text().withLength(min: 1)();
  IntColumn get unitPriceKrw =>
      integer().check(unitPriceKrw.isBiggerOrEqualValue(0))();
  IntColumn get quantity => integer().check(quantity.isBiggerThanValue(0))();
  IntColumn get lineAmountKrw =>
      integer().check(lineAmountKrw.isBiggerOrEqualValue(0))();
  TextColumn get resolutionSource => text().withLength(min: 1)();

  @override
  Set<Column<Object>> get primaryKey => {finalLineId};

  @override
  List<String> get customConstraints => const [
    '''
CHECK (resolution_source IN (
  'ai_auto_customer_accepted', 'customer_top3', 'customer_catalog',
  'customer_overrode_auto', 'customer_manual_cart'
))''',
  ];
}

@DataClassName('SimulatedPaymentRow')
class SimulatedPayments extends Table {
  TextColumn get paymentId => text().withLength(min: 1)();
  TextColumn get orderId => text().references(FinalOrders, #orderId)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  IntColumn get amountKrw =>
      integer().check(amountKrw.isBiggerOrEqualValue(0))();
  TextColumn get currency => text().withLength(min: 1)();
  TextColumn get provider => text().withLength(min: 1)();
  TextColumn get status => text().withLength(min: 1)();
  TextColumn get finalOrderSha256 => text().withLength(min: 64, max: 64)();
  IntColumn get paidAtUs => integer()();

  @override
  Set<Column<Object>> get primaryKey => {paymentId};

  @override
  List<String> get customConstraints => const [
    'UNIQUE (order_id)',
    'UNIQUE (session_id)',
    "CHECK (currency = 'KRW' AND provider = 'simulated' AND status = 'approved')",
    "CHECK (length(final_order_sha256) = 64 "
        "AND final_order_sha256 NOT GLOB '*[^0-9a-f]*')",
  ];
}

@DataClassName('AuditEventRow')
class AuditEvents extends Table {
  TextColumn get eventId => text().withLength(min: 1)();
  TextColumn get sessionId =>
      text().nullable().references(CheckoutSessions, #sessionId)();
  TextColumn get eventType => text().withLength(min: 1)();
  IntColumn get occurredAtUs => integer()();
  TextColumn get detail => text().nullable()();

  @override
  Set<Column<Object>> get primaryKey => {eventId};
}

@DataClassName('RetentionEventRow')
class RetentionEvents extends Table {
  TextColumn get retentionEventId => text().withLength(min: 1)();
  TextColumn get attemptId => text().references(ScanAttempts, #attemptId)();
  TextColumn get relativePath => text().withLength(min: 1)();
  IntColumn get originalByteSize =>
      integer().check(originalByteSize.isBiggerThanValue(0))();
  TextColumn get originalSha256 => text().withLength(min: 64, max: 64)();
  IntColumn get prunedAtUs => integer()();
  TextColumn get reason => text().withLength(min: 1)();

  @override
  Set<Column<Object>> get primaryKey => {retentionEventId};

  @override
  List<String> get customConstraints => const [
    '''
CHECK (
  length(original_sha256) = 64
  AND original_sha256 NOT GLOB '*[^0-9a-f]*'
  AND length(relative_path) > 0
  AND relative_path NOT GLOB '/*'
  AND relative_path NOT GLOB '\\*'
  AND relative_path NOT LIKE '%:%'
  AND relative_path NOT LIKE '%..%'
)''',
  ];
}

/// Operator annotations are deliberately separate from checkout evidence.  A
/// review records what the operator concluded; it never replaces an inference
/// result, customer choice, order, or payment snapshot.
@DataClassName('AdminReviewAnnotationRow')
class AdminReviewAnnotations extends Table {
  TextColumn get annotationId => text().withLength(min: 1)();
  TextColumn get sessionId => text().references(CheckoutSessions, #sessionId)();
  TextColumn get attemptId =>
      text().nullable().references(ScanAttempts, #attemptId)();
  TextColumn get objectId =>
      text().nullable().references(InferenceObjects, #inferenceObjectId)();
  TextColumn get reviewStatus => text().withLength(min: 1)();
  TextColumn get correctProductId => text().nullable()();
  TextColumn get conclusionCode =>
      text().withDefault(const Constant('ai_correct'))();
  TextColumn get reasonCode => text().withLength(min: 1)();
  TextColumn get note => text().nullable()();
  TextColumn get authorLabel => text().withLength(min: 1)();
  IntColumn get createdAtUs => integer()();

  @override
  Set<Column<Object>> get primaryKey => {annotationId};

  @override
  List<String> get customConstraints => const [
    "CHECK (review_status IN ('open', 'reviewed', 'needs_follow_up'))",
    "CHECK (conclusion_code IN ('ai_correct', 'customer_correct', 'both_incorrect', 'insufficient_evidence'))",
  ];
}

@DriftDatabase(
  tables: [
    CatalogRevisions,
    Products,
    CheckoutSessions,
    ScanAttempts,
    InferenceObjects,
    InferenceCandidates,
    ObjectResolutions,
    DraftOrderLines,
    FinalOrders,
    FinalOrderLines,
    SimulatedPayments,
    AuditEvents,
    SettingsRevisions,
    AppSettings,
    RetentionEvents,
    AdminReviewAnnotations,
  ],
)
class BakeryDatabase extends _$BakeryDatabase {
  BakeryDatabase(super.executor);

  BakeryDatabase.production()
    : super(
        driftDatabase(
          name: 'bixolon_bakery_checkout_v1_1_0',
          native: const DriftNativeOptions(shareAcrossIsolates: false),
        ),
      );

  String _lastMigrationResult = 'not_opened';

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (migrator) async {
      await migrator.createAll();
      await _installIntegrityGuards();
      _lastMigrationResult = 'created_schema_v3';
      await _installSettings();
    },
    onUpgrade: (migrator, from, to) async {
      if (from > to) {
        throw StateError(
          'database schema $from is newer than supported schema $to',
        );
      }
      if (from == 1 && to == 2) {
        await migrator.createTable(adminReviewAnnotations);
        await _installReviewIntegrityGuards();
        return;
      }
      if (from == 2 && to == 3) {
        await migrator.addColumn(
          adminReviewAnnotations,
          adminReviewAnnotations.conclusionCode,
        );
        await _installReviewIntegrityGuards();
        return;
      }
      if (from == 1 && to == 3) {
        await migrator.createTable(adminReviewAnnotations);
        await _installReviewIntegrityGuards();
        return;
      }
      throw StateError('no migration path from schema $from to $to');
    },
    beforeOpen: (details) async {
      if ((details.versionBefore ?? 0) > schemaVersion) {
        throw StateError(
          'database schema ${details.versionBefore} is newer than '
          'supported schema $schemaVersion',
        );
      }
      await customStatement('PRAGMA foreign_keys = ON');
      if (!details.wasCreated) {
        _lastMigrationResult = details.hadUpgrade
            ? 'migrated_${details.versionBefore}_to_${details.versionNow}'
            : 'opened_schema_${details.versionNow}';
      }
      await _updateDiagnosticRow();
    },
  );

  Future<DatabaseDiagnostics> diagnostics() async {
    final settings = await (select(
      appSettings,
    )..where((row) => row.settingsId.equals('operational'))).getSingle();
    return DatabaseDiagnostics(
      schemaVersion: schemaVersion,
      applicationVersion: settings.applicationVersionValue,
      lastMigrationResult: settings.lastMigrationResult,
    );
  }

  Future<void> _installSettings() async {
    await into(settingsRevisions).insert(
      SettingsRevisionsCompanion.insert(
        revisionId: 'settings-v1',
        createdAtUs: 0,
        retryLimit: 2,
        paymentCompleteDurationSeconds: 4,
        customerAutoReset: true,
        evidenceRetentionDays: 90,
        locale: 'ko-KR',
        kioskDisplayName: 'BIXOLON Bakery',
        adminAuthorLabel: 'prototype-admin',
      ),
    );
    await into(appSettings).insert(
      AppSettingsCompanion.insert(
        settingsId: 'operational',
        activeSettingsRevisionId: 'settings-v1',
        applicationVersionValue: applicationVersion,
        lastMigrationResult: _lastMigrationResult,
      ),
    );
  }

  Future<void> _installIntegrityGuards() async {
    await customStatement('''
CREATE UNIQUE INDEX catalog_revisions_one_active
ON catalog_revisions (is_active)
WHERE is_active = 1
''');
    await customStatement('''
CREATE UNIQUE INDEX object_resolutions_one_current
ON object_resolutions (inference_object_id)
WHERE is_current = 1 AND inference_object_id IS NOT NULL
''');
    await customStatement('''
CREATE TRIGGER inference_candidates_unknown_only
BEFORE INSERT ON inference_candidates
BEGIN
  SELECT CASE WHEN (
    SELECT sku_id IS NOT NULL
    FROM inference_objects
    WHERE inference_object_id = NEW.inference_object_id
  ) THEN RAISE(ABORT, 'registered inference objects cannot have candidates')
  END;
END
''');
    await customStatement('''
CREATE TRIGGER immutable_inference_candidate_no_insert
BEFORE INSERT ON inference_candidates
WHEN EXISTS (
  SELECT 1
  FROM inference_objects AS object
  JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE object.inference_object_id = NEW.inference_object_id
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'immutable scan cannot gain inference candidates');
END
''');
    await customStatement('''
CREATE TRIGGER completed_attempt_evidence_guard
BEFORE UPDATE OF status ON scan_attempts
WHEN NEW.status = 'completed'
BEGIN
  SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM inference_objects AS object
    WHERE object.attempt_id = NEW.attempt_id
      AND (
        (object.sku_id IS NULL AND (
          SELECT count(*)
          FROM inference_candidates AS candidate
          WHERE candidate.inference_object_id = object.inference_object_id
        ) <> 3)
        OR
        (object.sku_id IS NOT NULL AND EXISTS (
          SELECT 1
          FROM inference_candidates AS candidate
          WHERE candidate.inference_object_id = object.inference_object_id
        ))
      )
  ) THEN RAISE(ABORT, 'inference candidate evidence is incomplete')
  END;
END
''');
    await customStatement('''
CREATE TRIGGER checkout_session_snapshot_immutable
BEFORE UPDATE OF
  started_at_us, catalog_revision_id, settings_revision_id,
  detector_id, detector_sha256,
  repvit_artifact_id, repvit_sha256, repvit_manifest_sha256,
  repvit_prototype_sha256,
  dinov3_artifact_id, dinov3_sha256, dinov3_support_sha256,
  calibration_id, calibration_sha256, preprocess_sha256,
  fusion_policy_id, fusion_policy_sha256, config_snapshot_json
ON checkout_sessions
BEGIN
  SELECT RAISE(ABORT, 'checkout session snapshot is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_checkout_session_no_update
BEFORE UPDATE ON checkout_sessions
WHEN OLD.state <> 'active'
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout session is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_checkout_session_no_delete
BEFORE DELETE ON checkout_sessions
WHEN OLD.state <> 'active'
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout session is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER catalog_revision_identity_no_update
BEFORE UPDATE OF revision_id, sha256, created_at_us ON catalog_revisions
BEGIN
  SELECT RAISE(ABORT, 'catalog revision identity is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER catalog_revision_no_delete
BEFORE DELETE ON catalog_revisions
BEGIN
  SELECT RAISE(ABORT, 'catalog revision is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER settings_revision_no_update
BEFORE UPDATE ON settings_revisions
BEGIN
  SELECT RAISE(ABORT, 'settings revision is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER settings_revision_no_delete
BEFORE DELETE ON settings_revisions
BEGIN
  SELECT RAISE(ABORT, 'settings revision is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER snapshotted_product_no_update
BEFORE UPDATE ON products
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE catalog_revision_id = OLD.catalog_revision_id
)
BEGIN
  SELECT RAISE(ABORT, 'snapshotted product revision is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER snapshotted_product_no_delete
BEFORE DELETE ON products
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE catalog_revision_id = OLD.catalog_revision_id
)
BEGIN
  SELECT RAISE(ABORT, 'snapshotted product revision is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_scan_attempt_no_update
BEFORE UPDATE ON scan_attempts
WHEN OLD.status = 'completed'
BEGIN
  SELECT RAISE(ABORT, 'completed scan attempt is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_scan_attempt_no_delete
BEFORE DELETE ON scan_attempts
WHEN OLD.status = 'completed'
BEGIN
  SELECT RAISE(ABORT, 'completed scan attempt is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_session_scan_attempt_no_insert
BEFORE INSERT ON scan_attempts
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = NEW.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout cannot gain scan attempts');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_session_scan_attempt_no_update
BEFORE UPDATE ON scan_attempts
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id IN (OLD.session_id, NEW.session_id) AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout scan attempts are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_session_scan_attempt_no_delete
BEFORE DELETE ON scan_attempts
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = OLD.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout scan attempts are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_inference_object_no_insert
BEFORE INSERT ON inference_objects
WHEN EXISTS (
  SELECT 1
  FROM scan_attempts AS attempt
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE attempt.attempt_id = NEW.attempt_id
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'immutable scan cannot gain inference objects');
END
''');
    await customStatement('''
CREATE TRIGGER completed_inference_object_no_update
BEFORE UPDATE ON inference_objects
WHEN EXISTS (
  SELECT 1
  FROM scan_attempts AS attempt
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE attempt.attempt_id IN (OLD.attempt_id, NEW.attempt_id)
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'inference object is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_inference_object_no_delete
BEFORE DELETE ON inference_objects
WHEN EXISTS (
  SELECT 1
  FROM scan_attempts AS attempt
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE attempt.attempt_id = OLD.attempt_id
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'inference object is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_inference_candidate_no_update
BEFORE UPDATE ON inference_candidates
WHEN EXISTS (
  SELECT 1
  FROM inference_objects AS object
  JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE object.inference_object_id IN (
    OLD.inference_object_id, NEW.inference_object_id
  )
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'inference candidate is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER completed_inference_candidate_no_delete
BEFORE DELETE ON inference_candidates
WHEN EXISTS (
  SELECT 1
  FROM inference_objects AS object
  JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
  JOIN checkout_sessions AS session ON session.session_id = attempt.session_id
  WHERE object.inference_object_id = OLD.inference_object_id
    AND (attempt.status = 'completed' OR session.state <> 'active')
)
BEGIN
  SELECT RAISE(ABORT, 'inference candidate is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER object_resolution_session_guard_insert
BEFORE INSERT ON object_resolutions
WHEN NEW.inference_object_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM inference_objects AS object
    JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
    WHERE object.inference_object_id = NEW.inference_object_id
      AND attempt.session_id = NEW.session_id
  )
BEGIN
  SELECT RAISE(ABORT, 'resolution object does not belong to session');
END
''');
    await customStatement('''
CREATE TRIGGER object_resolution_session_guard_update
BEFORE UPDATE OF session_id, inference_object_id ON object_resolutions
WHEN NEW.inference_object_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM inference_objects AS object
    JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
    WHERE object.inference_object_id = NEW.inference_object_id
      AND attempt.session_id = NEW.session_id
  )
BEGIN
  SELECT RAISE(ABORT, 'resolution object does not belong to session');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_resolution_no_insert
BEFORE INSERT ON object_resolutions
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = NEW.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout resolutions are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_resolution_no_update
BEFORE UPDATE ON object_resolutions
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id IN (OLD.session_id, NEW.session_id) AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout resolutions are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_resolution_no_delete
BEFORE DELETE ON object_resolutions
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = OLD.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout resolutions are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_draft_line_no_insert
BEFORE INSERT ON draft_order_lines
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = NEW.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout draft is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_draft_line_no_update
BEFORE UPDATE ON draft_order_lines
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id IN (OLD.session_id, NEW.session_id) AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout draft is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_draft_line_no_delete
BEFORE DELETE ON draft_order_lines
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = OLD.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout draft is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_final_order_no_insert
BEFORE INSERT ON final_orders
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = NEW.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout cannot gain a final order');
END
''');
    await customStatement('''
CREATE TRIGGER final_order_no_update
BEFORE UPDATE ON final_orders
BEGIN
  SELECT RAISE(ABORT, 'final order is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER final_order_no_delete
BEFORE DELETE ON final_orders
BEGIN
  SELECT RAISE(ABORT, 'final order is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_final_line_no_insert
BEFORE INSERT ON final_order_lines
WHEN EXISTS (
  SELECT 1
  FROM final_orders AS final_order
  JOIN checkout_sessions AS session
    ON session.session_id = final_order.session_id
  WHERE final_order.order_id = NEW.order_id AND session.state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout cannot gain final order lines');
END
''');
    await customStatement('''
CREATE TRIGGER paid_final_line_no_insert
BEFORE INSERT ON final_order_lines
WHEN EXISTS (
  SELECT 1 FROM simulated_payments WHERE order_id = NEW.order_id
)
BEGIN
  SELECT RAISE(ABORT, 'paid final order lines are immutable');
END
''');
    await customStatement('''
CREATE TRIGGER final_order_line_no_update
BEFORE UPDATE ON final_order_lines
BEGIN
  SELECT RAISE(ABORT, 'final order line is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER final_order_line_no_delete
BEFORE DELETE ON final_order_lines
BEGIN
  SELECT RAISE(ABORT, 'final order line is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER payment_order_session_guard
BEFORE INSERT ON simulated_payments
WHEN NOT EXISTS (
  SELECT 1 FROM final_orders
  WHERE order_id = NEW.order_id AND session_id = NEW.session_id
)
BEGIN
  SELECT RAISE(ABORT, 'payment order does not belong to session');
END
''');
    await customStatement('''
CREATE TRIGGER terminal_payment_no_insert
BEFORE INSERT ON simulated_payments
WHEN EXISTS (
  SELECT 1 FROM checkout_sessions
  WHERE session_id = NEW.session_id AND state <> 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'terminal checkout cannot gain a payment');
END
''');
    await customStatement('''
CREATE TRIGGER simulated_payment_no_update
BEFORE UPDATE ON simulated_payments
BEGIN
  SELECT RAISE(ABORT, 'simulated payment is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER simulated_payment_no_delete
BEFORE DELETE ON simulated_payments
BEGIN
  SELECT RAISE(ABORT, 'simulated payment is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER audit_event_no_update
BEFORE UPDATE ON audit_events
BEGIN
  SELECT RAISE(ABORT, 'audit event is append-only');
END
''');
    await customStatement('''
CREATE TRIGGER audit_event_no_delete
BEFORE DELETE ON audit_events
BEGIN
  SELECT RAISE(ABORT, 'audit event is append-only');
END
''');
    await customStatement('''
CREATE TRIGGER retention_event_no_update
BEFORE UPDATE ON retention_events
BEGIN
  SELECT RAISE(ABORT, 'retention event is immutable');
END
''');
    await customStatement('''
CREATE TRIGGER retention_event_no_delete
BEFORE DELETE ON retention_events
BEGIN
  SELECT RAISE(ABORT, 'retention event is immutable');
END
''');
    await _installReviewIntegrityGuards();
  }

  Future<void> _installReviewIntegrityGuards() async {
    // Schema v2 already owns the first three named guards. Recreate every
    // review guard so a real v2 database upgrades to the v3 contract instead
    // of failing on SQLite's duplicate-trigger error.
    await customStatement(
      'DROP TRIGGER IF EXISTS admin_review_annotation_target_context',
    );
    await customStatement(
      'DROP TRIGGER IF EXISTS admin_review_annotation_correct_product_context',
    );
    await customStatement(
      'DROP TRIGGER IF EXISTS admin_review_annotation_no_update',
    );
    await customStatement(
      'DROP TRIGGER IF EXISTS admin_review_annotation_no_delete',
    );
    await customStatement('''
CREATE TRIGGER admin_review_annotation_target_context
BEFORE INSERT ON admin_review_annotations
WHEN (NEW.attempt_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM scan_attempts
  WHERE attempt_id = NEW.attempt_id AND session_id = NEW.session_id
)) OR (NEW.object_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM inference_objects AS object
  JOIN scan_attempts AS attempt ON attempt.attempt_id = object.attempt_id
  WHERE object.inference_object_id = NEW.object_id
    AND attempt.session_id = NEW.session_id
    AND (NEW.attempt_id IS NULL OR NEW.attempt_id = attempt.attempt_id)
))
BEGIN
  SELECT RAISE(ABORT, 'review target does not belong to session');
END
''');
    await customStatement('''
CREATE TRIGGER admin_review_annotation_correct_product_context
BEFORE INSERT ON admin_review_annotations
WHEN NEW.correct_product_id IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM products AS product
  JOIN checkout_sessions AS session ON session.session_id = NEW.session_id
  WHERE product.catalog_revision_id = session.catalog_revision_id
    AND product.product_id = NEW.correct_product_id
)
BEGIN
  SELECT RAISE(ABORT, 'review correct product is not in frozen catalog');
END
''');
    await customStatement('''
CREATE TRIGGER admin_review_annotation_no_update
BEFORE UPDATE ON admin_review_annotations
BEGIN
  SELECT RAISE(ABORT, 'admin review annotation is append-only');
END
''');
    await customStatement('''
CREATE TRIGGER admin_review_annotation_no_delete
BEFORE DELETE ON admin_review_annotations
BEGIN
  SELECT RAISE(ABORT, 'admin review annotation is append-only');
END
''');
  }

  Future<void> _updateDiagnosticRow() async {
    await (update(
      appSettings,
    )..where((row) => row.settingsId.equals('operational'))).write(
      AppSettingsCompanion(
        applicationVersionValue: const Value(applicationVersion),
        lastMigrationResult: Value(_lastMigrationResult),
      ),
    );
  }
}

final class DatabaseDiagnostics {
  const DatabaseDiagnostics({
    required this.schemaVersion,
    required this.applicationVersion,
    required this.lastMigrationResult,
  });

  final int schemaVersion;
  final String applicationVersion;
  final String lastMigrationResult;
}
