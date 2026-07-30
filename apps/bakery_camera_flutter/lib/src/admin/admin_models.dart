/// A UTC interval rendered in the operator's configured local timezone.
/// The end is exclusive, which keeps adjacent calendar days deterministic.
final class DateRange {
  DateRange.utc(DateTime startInclusive, DateTime endExclusive)
    : startInclusive = startInclusive.toUtc(),
      endExclusive = endExclusive.toUtc() {
    if (!this.endExclusive.isAfter(this.startInclusive)) {
      throw ArgumentError('endExclusive must be after startInclusive');
    }
  }

  final DateTime startInclusive;
  final DateTime endExclusive;

  bool includes(DateTime instant) {
    final utc = instant.toUtc();
    return !utc.isBefore(startInclusive) && utc.isBefore(endExclusive);
  }
}

final class MetricRate {
  const MetricRate(this.numerator, this.denominator);

  final int numerator;
  final int denominator;

  double get value => denominator == 0 ? 0 : numerator / denominator;
}

/// The live operating state is deliberately separate from historical audit
/// projections. It is unknown until a readiness or diagnostics source reports.
enum DashboardAvailability { unknown, ready, unavailable }

/// Event timestamps used by the dashboard's bounded historical metrics.
///
/// Paid totals use the immutable approved payment time. Scan, Unknown and
/// retake metrics use the capture time of each scan attempt. Resolution and
/// manual-entry metrics use the customer's resolution time. Failures use the
/// terminal session time. The attention queue is current-state work, sorted by
/// the same object-capture or terminal-session timestamps rather than an
/// inferred accuracy score.
abstract final class DashboardMetricTimestampSemantics {
  static const paidTotal = 'simulated_payments.paid_at_us';
  static const scanAndUnknown = 'scan_attempts.captured_at_us';
  static const resolution = 'object_resolutions.resolved_at_us';
  static const failure = 'checkout_sessions.terminal_at_us';
}

/// Read-only operational totals. These are not model-accuracy estimates.
final class AdminDashboardSummary {
  const AdminDashboardSummary({
    required this.completedOrders,
    required this.grossKrw,
    required this.scanAttempts,
    required this.retakeSessions,
    required this.unknownObjects,
    required this.customerResolvedUnknownObjects,
    required this.customerOverrides,
    required this.manualCartLines,
    required this.failedSessions,
    required this.unresolvedAttentionCount,
  });

  final int completedOrders;
  final int grossKrw;
  final int scanAttempts;
  final int retakeSessions;
  final int unknownObjects;
  final int customerResolvedUnknownObjects;
  final int customerOverrides;
  final int manualCartLines;
  final int failedSessions;
  final int unresolvedAttentionCount;

  MetricRate get retakeRate => MetricRate(retakeSessions, completedOrders);
  MetricRate get unknownRate => MetricRate(unknownObjects, scanAttempts);
  MetricRate get overrideRate => MetricRate(customerOverrides, completedOrders);
  MetricRate get manualEntryRate =>
      MetricRate(manualCartLines, completedOrders);
  MetricRate get failureRate => MetricRate(failedSessions, completedOrders);
}

enum AttentionKind { unresolvedUnknown, failedSession }

final class AttentionItem {
  const AttentionItem({
    required this.sessionId,
    required this.kind,
    required this.occurredAt,
    required this.label,
  });

  final String sessionId;
  final AttentionKind kind;
  final DateTime occurredAt;
  final String label;
}

enum TransactionPaymentStatus { any, completed, unpaid }

/// Explicit search constraints over immutable checkout records. A null boolean
/// does not constrain the corresponding audited condition.
final class TransactionFilter {
  const TransactionFilter({
    this.dateRange,
    this.sessionQuery,
    this.productQuery,
    this.modelPolicyQuery,
    this.paymentStatus = TransactionPaymentStatus.any,
    this.terminalState,
    this.resolutionSource,
    this.requiresUnknown,
    this.requiresRetake,
    this.requiresFailure,
  });

  final DateRange? dateRange;
  final String? sessionQuery;
  final String? productQuery;
  final String? modelPolicyQuery;
  final TransactionPaymentStatus paymentStatus;
  final String? terminalState;
  final String? resolutionSource;
  final bool? requiresUnknown;
  final bool? requiresRetake;
  final bool? requiresFailure;
}

/// A compound cursor prevents duplicate or skipped records sharing a timestamp.
final class PageCursor {
  const PageCursor({required this.startedAt, required this.sessionId});

  final DateTime startedAt;
  final String sessionId;
}

final class TransactionPage {
  TransactionPage({required List<TransactionListItem> items, this.nextCursor})
    : items = List.unmodifiable(items);

  final List<TransactionListItem> items;
  final PageCursor? nextCursor;
}

final class TransactionListItem {
  TransactionListItem({
    required this.sessionId,
    required this.startedAt,
    required this.terminalState,
    required this.breadCount,
    required this.finalAmountKrw,
    required this.scanAttemptCount,
    required List<String> resolutionSources,
    required this.hasUnknown,
    required this.hasRetake,
    required this.hasFailure,
  }) : resolutionSources = List.unmodifiable(resolutionSources);

  final String sessionId;
  final DateTime startedAt;
  final String terminalState;
  final int breadCount;
  final int? finalAmountKrw;
  final int scanAttemptCount;
  final List<String> resolutionSources;
  final bool hasUnknown;
  final bool hasRetake;
  final bool hasFailure;
}

enum AuditEvidenceIntegrity {
  unverified,
  retained,
  retentionExpired,
  missing,
  hashMismatch,
  unavailable,
}

final class AdminEvidenceReference {
  const AdminEvidenceReference({
    required this.relativePath,
    required this.sha256,
    required this.byteSize,
    required this.integrity,
  });

  final String relativePath;
  final String sha256;
  final int byteSize;
  final AuditEvidenceIntegrity integrity;
}

final class AdminInferenceCandidate {
  const AdminInferenceCandidate({
    required this.rank,
    required this.skuId,
    required this.skuName,
    required this.score,
  });

  final int rank;
  final int skuId;
  final String skuName;
  final double score;
}

final class AdminInferenceObject {
  AdminInferenceObject({
    required this.objectId,
    required this.skuId,
    required this.skuName,
    required this.boxJson,
    required this.confidence,
    required this.decisionPath,
    required this.detectorSource,
    required this.detectorScore,
    required List<AdminInferenceCandidate> candidates,
    required this.unknownReason,
  }) : candidates = List.unmodifiable(candidates);

  final String objectId;
  final int? skuId;
  final String skuName;
  final String boxJson;
  final double confidence;
  final String decisionPath;
  final String detectorSource;
  final double detectorScore;
  final List<AdminInferenceCandidate> candidates;
  final String? unknownReason;
}

final class AdminObjectResolution {
  const AdminObjectResolution({
    required this.resolutionId,
    required this.inferenceObjectId,
    required this.productId,
    required this.productName,
    required this.recognitionSkuId,
    required this.unitPriceKrw,
    required this.source,
    required this.resolvedAt,
    required this.candidateRank,
    required this.canonicalBoxJson,
    required this.isCurrent,
  });

  final String resolutionId;
  final String? inferenceObjectId;
  final String productId;
  final String productName;
  final int? recognitionSkuId;
  final int unitPriceKrw;
  final String source;
  final DateTime resolvedAt;
  final int? candidateRank;
  final String? canonicalBoxJson;
  final bool isCurrent;
}

final class AdminScanAttempt {
  AdminScanAttempt({
    required this.attemptNumber,
    required this.capturedAt,
    required this.status,
    required this.image,
    required this.receipt,
    required this.presentationState,
    required this.retakeReason,
    required Map<String, double?> timingsMs,
    required List<AdminInferenceObject> objects,
  }) : timingsMs = Map.unmodifiable(timingsMs),
       objects = List.unmodifiable(objects);

  final int attemptNumber;
  final DateTime capturedAt;
  final String status;
  final AdminEvidenceReference image;
  final AdminEvidenceReference? receipt;
  final String? presentationState;
  final String? retakeReason;
  final Map<String, double?> timingsMs;
  final List<AdminInferenceObject> objects;
}

final class AdminOrderLine {
  const AdminOrderLine({
    required this.productName,
    required this.productId,
    required this.recognitionSkuId,
    required this.unitPriceKrw,
    required this.quantity,
    required this.lineAmountKrw,
    required this.resolutionSource,
  });

  final String productName;
  final String productId;
  final int? recognitionSkuId;
  final int unitPriceKrw;
  final int quantity;
  final int lineAmountKrw;
  final String resolutionSource;
}

final class AdminFinalOrder {
  AdminFinalOrder({
    required this.orderId,
    required this.createdAt,
    required this.totalQuantity,
    required this.totalAmountKrw,
    required this.receipt,
    required List<AdminOrderLine> lines,
  }) : lines = List.unmodifiable(lines);

  final String orderId;
  final DateTime createdAt;
  final int totalQuantity;
  final int totalAmountKrw;
  final AdminEvidenceReference receipt;
  final List<AdminOrderLine> lines;
}

final class AdminPaymentSnapshot {
  const AdminPaymentSnapshot({
    required this.paymentId,
    required this.amountKrw,
    required this.provider,
    required this.status,
    required this.finalOrderSha256,
    required this.paidAt,
  });

  final String paymentId;
  final int amountKrw;
  final String provider;
  final String status;
  final String finalOrderSha256;
  final DateTime paidAt;
}

final class AdminArtifactSnapshot {
  const AdminArtifactSnapshot({
    required this.detectorId,
    required this.detectorSha256,
    required this.repvitArtifactId,
    required this.repvitSha256,
    required this.repvitManifestSha256,
    required this.repvitPrototypeSha256,
    required this.dinov3ArtifactId,
    required this.dinov3Sha256,
    required this.dinov3SupportSha256,
    required this.calibrationId,
    required this.calibrationSha256,
    required this.preprocessSha256,
    required this.fusionPolicyId,
    required this.fusionPolicySha256,
  });

  final String detectorId;
  final String detectorSha256;
  final String repvitArtifactId;
  final String repvitSha256;
  final String repvitManifestSha256;
  final String repvitPrototypeSha256;
  final String dinov3ArtifactId;
  final String dinov3Sha256;
  final String dinov3SupportSha256;
  final String calibrationId;
  final String calibrationSha256;
  final String preprocessSha256;
  final String fusionPolicyId;
  final String fusionPolicySha256;
}

final class AdminTransactionDetail {
  AdminTransactionDetail({
    required this.sessionId,
    required this.startedAt,
    required this.terminalAt,
    required this.terminalState,
    required this.terminalReason,
    required this.catalogRevisionId,
    required this.settingsRevisionId,
    required this.configSnapshotJson,
    required this.artifacts,
    required List<AdminScanAttempt> attempts,
    required List<AdminObjectResolution> resolutions,
    required this.order,
    required this.payment,
    required this.hasIntegrityWarning,
  }) : attempts = List.unmodifiable(attempts),
       resolutions = List.unmodifiable(resolutions);

  final String sessionId;
  final DateTime startedAt;
  final DateTime? terminalAt;
  final String terminalState;
  final String? terminalReason;
  final String catalogRevisionId;
  final String settingsRevisionId;
  final String configSnapshotJson;
  final AdminArtifactSnapshot artifacts;
  final List<AdminScanAttempt> attempts;
  final List<AdminObjectResolution> resolutions;
  final AdminFinalOrder? order;
  final AdminPaymentSnapshot? payment;
  final bool hasIntegrityWarning;
}
