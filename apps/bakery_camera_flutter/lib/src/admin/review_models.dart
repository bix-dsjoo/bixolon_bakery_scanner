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

/// A reviewer conclusion is evidence about a checkout, not a mutation of the
/// stored inference result or customer order.
enum ReviewConclusion {
  aiCorrect,
  customerCorrect,
  bothIncorrect,
  insufficientEvidence,
}

extension ReviewConclusionStorage on ReviewConclusion {
  String get storageValue => switch (this) {
    ReviewConclusion.aiCorrect => 'ai_correct',
    ReviewConclusion.customerCorrect => 'customer_correct',
    ReviewConclusion.bothIncorrect => 'both_incorrect',
    ReviewConclusion.insufficientEvidence => 'insufficient_evidence',
  };

  static ReviewConclusion parse(String value) => switch (value) {
    'ai_correct' => ReviewConclusion.aiCorrect,
    'customer_correct' => ReviewConclusion.customerCorrect,
    'both_incorrect' => ReviewConclusion.bothIncorrect,
    'insufficient_evidence' => ReviewConclusion.insufficientEvidence,
    _ => throw StateError('unknown review conclusion: $value'),
  };
}

enum ReviewIssueTag {
  productMisclassification,
  miss,
  duplicate,
  merge,
  split,
  nonTargetDetection,
  imageQuality,
  catalogIssue,
}

extension ReviewIssueTagStorage on ReviewIssueTag {
  String get storageValue => switch (this) {
    ReviewIssueTag.productMisclassification => 'product_misclassification',
    ReviewIssueTag.miss => 'miss',
    ReviewIssueTag.duplicate => 'duplicate',
    ReviewIssueTag.merge => 'merge',
    ReviewIssueTag.split => 'split',
    ReviewIssueTag.nonTargetDetection => 'non_target_detection',
    ReviewIssueTag.imageQuality => 'image_quality',
    ReviewIssueTag.catalogIssue => 'catalog_issue',
  };

  static ReviewIssueTag? tryParse(String value) {
    for (final tag in ReviewIssueTag.values) {
      if (tag.storageValue == value) return tag;
    }
    return null;
  }
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
    this.conclusion = ReviewConclusion.aiCorrect,
    required this.reasonCode,
    this.note,
    required this.authorLabel,
  });

  final String sessionId;
  final String? attemptId;
  final String? objectId;
  final ReviewStatus reviewStatus;
  final String? correctProductId;
  final ReviewConclusion conclusion;
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
    required this.conclusion,
    required this.authorLabel,
    required this.createdAt,
  });

  final String annotationId;
  final ReviewTarget target;
  final ReviewStatus reviewStatus;
  final String reasonCode;
  final String? note;
  final String? correctProductId;
  final ReviewConclusion conclusion;
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
