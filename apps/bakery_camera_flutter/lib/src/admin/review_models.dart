import 'admin_models.dart';

enum ReviewStatus { open, reviewed, needsFollowUp }

extension ReviewStatusStorage on ReviewStatus {
  String get storageValue => switch (this) {
    ReviewStatus.open => 'open',
    ReviewStatus.reviewed => 'reviewed',
    ReviewStatus.needsFollowUp => 'needs_follow_up',
  };

  static ReviewStatus parse(String value) => switch (value) {
    'open' => ReviewStatus.open,
    'reviewed' => ReviewStatus.reviewed,
    'needs_follow_up' => ReviewStatus.needsFollowUp,
    _ => throw StateError('unknown review status: $value'),
  };
}

enum ReviewPriority {
  integrityFailure,
  customerOverride,
  unknownResolvedByCustomer,
  manualCatalogResolution,
  retakeOrFailure,
}

final class ReviewTarget {
  const ReviewTarget({required this.sessionId, this.attemptId, this.objectId});

  final String sessionId;
  final String? attemptId;

  /// The immutable inference-object row ID, when the review is object scoped.
  final String? objectId;

  String get key => '$sessionId|${attemptId ?? ''}|${objectId ?? ''}';
}

final class AdminReviewAnnotationDraft {
  const AdminReviewAnnotationDraft({
    required this.sessionId,
    this.attemptId,
    this.objectId,
    required this.reviewStatus,
    this.correctProductId,
    required this.reasonCode,
    this.note,
    required this.authorLabel,
  });

  final String sessionId;
  final String? attemptId;
  final String? objectId;
  final ReviewStatus reviewStatus;
  final String? correctProductId;
  final String reasonCode;
  final String? note;
  final String authorLabel;

  ReviewTarget get target => ReviewTarget(
    sessionId: sessionId,
    attemptId: attemptId,
    objectId: objectId,
  );
}

final class AdminReviewAnnotation {
  const AdminReviewAnnotation({
    required this.annotationId,
    required this.target,
    required this.reviewStatus,
    required this.reasonCode,
    required this.note,
    required this.correctProductId,
    required this.authorLabel,
    required this.createdAt,
  });

  final String annotationId;
  final ReviewTarget target;
  final ReviewStatus reviewStatus;
  final String reasonCode;
  final String? note;
  final String? correctProductId;
  final String authorLabel;
  final DateTime createdAt;
}

final class ReviewFilter {
  const ReviewFilter({this.status});
  final ReviewStatus? status;
}

final class ReviewInboxItem {
  const ReviewInboxItem({
    required this.target,
    required this.priority,
    required this.status,
    required this.occurredAt,
    required this.summary,
  });

  final ReviewTarget target;
  final ReviewPriority priority;
  final ReviewStatus status;
  final DateTime occurredAt;
  final String summary;

  String get sessionId => target.sessionId;
}

final class ReviewPage {
  ReviewPage({required List<ReviewInboxItem> items, this.nextCursor})
    : items = List.unmodifiable(items);

  final List<ReviewInboxItem> items;
  final PageCursor? nextCursor;
}

final class ReviewProductOption {
  const ReviewProductOption({
    required this.productId,
    required this.displayName,
    required this.active,
  });

  final String productId;
  final String displayName;
  final bool active;
}

final class ReviewDetail {
  ReviewDetail({
    required this.target,
    required List<AdminReviewAnnotation> annotations,
    required List<ReviewProductOption> products,
  }) : annotations = List.unmodifiable(annotations),
       products = List.unmodifiable(products);

  final ReviewTarget target;
  final List<AdminReviewAnnotation> annotations;
  final List<ReviewProductOption> products;
}
