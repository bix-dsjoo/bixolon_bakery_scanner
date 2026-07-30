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
