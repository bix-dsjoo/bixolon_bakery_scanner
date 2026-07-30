import 'package:drift/drift.dart';

import '../persistence/app_database.dart';
import 'admin_models.dart';
import 'review_models.dart';

abstract interface class ReviewRepository {
  Future<void> annotate(AdminReviewAnnotationDraft draft);
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  });
  Future<ReviewDetail> reviewDetail(ReviewTarget target);
}

/// Writes only annotation rows.  Checkout, inference and payment tables are
/// never mutated by this service.
final class DatabaseReviewService implements ReviewRepository {
  DatabaseReviewService(
    this._database, {
    required this.createId,
    required this.now,
  });

  final BakeryDatabase _database;
  final String Function(AdminReviewAnnotationDraft draft) createId;
  final DateTime Function() now;

  @override
  Future<void> annotate(AdminReviewAnnotationDraft draft) async {
    _requireText(draft.sessionId, 'sessionId');
    _requireText(draft.reasonCode, 'reasonCode');
    _requireText(draft.authorLabel, 'authorLabel');
    final annotationId = createId(draft);
    _requireText(annotationId, 'annotationId');
    await _database.transaction(() async {
      final existing =
          await (_database.select(_database.adminReviewAnnotations)
                ..where((row) => row.annotationId.equals(annotationId)))
              .getSingleOrNull();
      if (existing != null) {
        if (_sameDraft(existing, draft)) return;
        throw StateError('annotation id is already bound to different content');
      }
      final session =
          await (_database.select(_database.checkoutSessions)
                ..where((row) => row.sessionId.equals(draft.sessionId)))
              .getSingleOrNull();
      if (session == null) {
        throw ArgumentError.value(
          draft.sessionId,
          'sessionId',
          'unknown checkout session',
        );
      }
      await _validateTarget(draft);
      if (draft.correctProductId case final productId?) {
        final product =
            await (_database.select(_database.products)
                  ..where(
                    (row) =>
                        row.catalogRevisionId.equals(session.catalogRevisionId),
                  )
                  ..where((row) => row.productId.equals(productId)))
                .getSingleOrNull();
        if (product == null) {
          throw ArgumentError.value(
            productId,
            'correctProductId',
            'not in frozen catalog revision',
          );
        }
      }
      await _database
          .into(_database.adminReviewAnnotations)
          .insert(
            AdminReviewAnnotationsCompanion.insert(
              annotationId: annotationId,
              sessionId: draft.sessionId,
              attemptId: Value(draft.attemptId),
              objectId: Value(draft.objectId),
              reviewStatus: draft.reviewStatus.storageValue,
              correctProductId: Value(draft.correctProductId),
              reasonCode: draft.reasonCode.trim(),
              note: Value(_trimOrNull(draft.note)),
              authorLabel: draft.authorLabel.trim(),
              createdAtUs: now().toUtc().microsecondsSinceEpoch,
            ),
          );
    });
  }

  @override
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    if (limit <= 0) {
      throw ArgumentError.value(limit, 'limit', 'must be positive');
    }
    final data = await _snapshot();
    final items = _buildInbox(data)
        .where((item) => filter.status == null || item.status == filter.status)
        .where((item) => after == null || _isAfter(item, after))
        .toList();
    final page = items.take(limit).toList(growable: false);
    final last = page.isEmpty ? null : page.last;
    return ReviewPage(
      items: page,
      nextCursor: page.length < items.length && last != null
          ? PageCursor(startedAt: last.occurredAt, sessionId: last.sessionId)
          : null,
    );
  }

  @override
  Future<ReviewDetail> reviewDetail(ReviewTarget target) async {
    await _validateTarget(
      AdminReviewAnnotationDraft(
        sessionId: target.sessionId,
        attemptId: target.attemptId,
        objectId: target.objectId,
        reviewStatus: ReviewStatus.open,
        reasonCode: 'detail',
        authorLabel: 'detail',
      ),
    );
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(target.sessionId))).getSingle();
    final annotations = await (_database.select(
      _database.adminReviewAnnotations,
    )..where((row) => row.sessionId.equals(target.sessionId))).get();
    final products =
        await (_database.select(_database.products)..where(
              (row) => row.catalogRevisionId.equals(session.catalogRevisionId),
            ))
            .get();
    annotations.sort((a, b) => b.createdAtUs.compareTo(a.createdAtUs));
    products.sort((a, b) => a.sortOrder.compareTo(b.sortOrder));
    return ReviewDetail(
      target: target,
      annotations: annotations.map(_annotation).toList(growable: false),
      products: products
          .map(
            (product) => ReviewProductOption(
              productId: product.productId,
              displayName: product.displayName,
              active: product.active,
            ),
          )
          .toList(growable: false),
    );
  }

  Future<void> _validateTarget(AdminReviewAnnotationDraft draft) async {
    if (draft.attemptId case final attemptId?) {
      final attempt = await (_database.select(
        _database.scanAttempts,
      )..where((row) => row.attemptId.equals(attemptId))).getSingleOrNull();
      if (attempt == null || attempt.sessionId != draft.sessionId) {
        throw ArgumentError.value(
          attemptId,
          'attemptId',
          'does not belong to session',
        );
      }
    }
    if (draft.objectId case final objectId?) {
      final object =
          await (_database.select(_database.inferenceObjects)
                ..where((row) => row.inferenceObjectId.equals(objectId)))
              .getSingleOrNull();
      if (object == null) {
        throw ArgumentError.value(
          objectId,
          'objectId',
          'unknown inference object',
        );
      }
      final attempt = await (_database.select(
        _database.scanAttempts,
      )..where((row) => row.attemptId.equals(object.attemptId))).getSingle();
      if (attempt.sessionId != draft.sessionId ||
          (draft.attemptId != null && attempt.attemptId != draft.attemptId)) {
        throw ArgumentError.value(
          objectId,
          'objectId',
          'does not belong to target',
        );
      }
    }
  }

  Future<_ReviewData> _snapshot() async => _database.transaction(
    () async => _ReviewData(
      sessions: await _database.select(_database.checkoutSessions).get(),
      attempts: await _database.select(_database.scanAttempts).get(),
      objects: await _database.select(_database.inferenceObjects).get(),
      resolutions: await _database.select(_database.objectResolutions).get(),
      events: await _database.select(_database.auditEvents).get(),
      annotations: await _database
          .select(_database.adminReviewAnnotations)
          .get(),
    ),
  );

  List<ReviewInboxItem> _buildInbox(_ReviewData data) {
    final attemptsBySession = _group(data.attempts, (row) => row.sessionId);
    final attemptsById = {for (final row in data.attempts) row.attemptId: row};
    final objectsBySession = <String, List<InferenceObjectRow>>{};
    for (final object in data.objects) {
      final sessionId = attemptsById[object.attemptId]?.sessionId;
      if (sessionId != null) {
        objectsBySession.putIfAbsent(sessionId, () => []).add(object);
      }
    }
    final resolutionsBySession = _group(
      data.resolutions,
      (row) => row.sessionId,
    );
    final integritySessions = data.events
        .where((event) => event.eventType == 'evidence_integrity_failure')
        .map((event) => event.sessionId)
        .whereType<String>()
        .toSet();
    final latest = <String, AdminReviewAnnotationRow>{};
    for (final annotation in data.annotations) {
      final key = ReviewTarget(
        sessionId: annotation.sessionId,
        attemptId: annotation.attemptId,
        objectId: annotation.objectId,
      ).key;
      final previous = latest[key];
      if (previous == null ||
          annotation.createdAtUs > previous.createdAtUs ||
          (annotation.createdAtUs == previous.createdAtUs &&
              annotation.annotationId.compareTo(previous.annotationId) > 0)) {
        latest[key] = annotation;
      }
    }
    final items = <ReviewInboxItem>[];
    for (final session in data.sessions) {
      final attempts =
          attemptsBySession[session.sessionId] ?? const <ScanAttemptRow>[];
      final objects =
          objectsBySession[session.sessionId] ?? const <InferenceObjectRow>[];
      final resolutions =
          resolutionsBySession[session.sessionId] ??
          const <ObjectResolutionRow>[];
      final priority = integritySessions.contains(session.sessionId)
          ? ReviewPriority.integrityFailure
          : resolutions.any((row) => row.source == 'customer_overrode_auto')
          ? ReviewPriority.customerOverride
          : _hasUnknownResolved(objects, resolutions)
          ? ReviewPriority.unknownResolvedByCustomer
          : resolutions.any((row) => row.source == 'customer_catalog')
          ? ReviewPriority.manualCatalogResolution
          : (session.state == 'failed' ||
                attempts.length > 1 ||
                attempts.any((row) => row.retakeReason != null))
          ? ReviewPriority.retakeOrFailure
          : null;
      if (priority == null) continue;
      final target = _targetFor(
        session.sessionId,
        priority,
        objects,
        resolutions,
      );
      final annotation = latest[target.key];
      items.add(
        ReviewInboxItem(
          target: target,
          priority: priority,
          status: annotation == null
              ? ReviewStatus.open
              : ReviewStatusStorage.parse(annotation.reviewStatus),
          occurredAt: DateTime.fromMicrosecondsSinceEpoch(
            session.startedAtUs,
            isUtc: true,
          ),
          summary: _summary(priority),
        ),
      );
    }
    items.sort((left, right) {
      final priority = left.priority.index.compareTo(right.priority.index);
      if (priority != 0) return priority;
      final time = right.occurredAt.compareTo(left.occurredAt);
      return time != 0 ? time : left.sessionId.compareTo(right.sessionId);
    });
    return items;
  }

  static bool _hasUnknownResolved(
    List<InferenceObjectRow> objects,
    List<ObjectResolutionRow> resolutions,
  ) => objects.any(
    (object) =>
        object.skuId == null &&
        resolutions.any(
          (resolution) =>
              resolution.inferenceObjectId == object.inferenceObjectId,
        ),
  );
  static ReviewTarget _targetFor(
    String sessionId,
    ReviewPriority priority,
    List<InferenceObjectRow> objects,
    List<ObjectResolutionRow> resolutions,
  ) {
    if (priority == ReviewPriority.unknownResolvedByCustomer) {
      final resolved = resolutions
          .map((row) => row.inferenceObjectId)
          .whereType<String>()
          .toSet();
      final object = objects
          .where(
            (row) =>
                row.skuId == null && resolved.contains(row.inferenceObjectId),
          )
          .firstOrNull;
      if (object != null) {
        return ReviewTarget(
          sessionId: sessionId,
          objectId: object.inferenceObjectId,
        );
      }
    }
    final linked = resolutions
        .where((row) => row.inferenceObjectId != null)
        .firstOrNull;
    return ReviewTarget(
      sessionId: sessionId,
      objectId: linked?.inferenceObjectId,
    );
  }

  static String _summary(ReviewPriority priority) => switch (priority) {
    ReviewPriority.integrityFailure => '증빙 파일 확인 필요',
    ReviewPriority.customerOverride => '고객이 AI 추천을 바꿨음',
    ReviewPriority.unknownResolvedByCustomer => 'AI가 상품을 확정하지 못함',
    ReviewPriority.manualCatalogResolution => '고객이 전체 상품에서 선택함',
    ReviewPriority.retakeOrFailure => '재촬영 또는 실패 확인 필요',
  };
  static bool _isAfter(ReviewInboxItem item, PageCursor cursor) =>
      item.occurredAt.isBefore(cursor.startedAt) ||
      (item.occurredAt == cursor.startedAt &&
          item.sessionId.compareTo(cursor.sessionId) < 0);
  static Map<K, List<T>> _group<T, K>(Iterable<T> rows, K Function(T row) key) {
    final result = <K, List<T>>{};
    for (final row in rows) {
      result.putIfAbsent(key(row), () => []).add(row);
    }
    return result;
  }

  static AdminReviewAnnotation _annotation(AdminReviewAnnotationRow row) =>
      AdminReviewAnnotation(
        annotationId: row.annotationId,
        target: ReviewTarget(
          sessionId: row.sessionId,
          attemptId: row.attemptId,
          objectId: row.objectId,
        ),
        reviewStatus: ReviewStatusStorage.parse(row.reviewStatus),
        reasonCode: row.reasonCode,
        note: row.note,
        correctProductId: row.correctProductId,
        authorLabel: row.authorLabel,
        createdAt: DateTime.fromMicrosecondsSinceEpoch(
          row.createdAtUs,
          isUtc: true,
        ),
      );
  static bool _sameDraft(
    AdminReviewAnnotationRow row,
    AdminReviewAnnotationDraft draft,
  ) =>
      row.sessionId == draft.sessionId &&
      row.attemptId == draft.attemptId &&
      row.objectId == draft.objectId &&
      row.reviewStatus == draft.reviewStatus.storageValue &&
      row.correctProductId == draft.correctProductId &&
      row.reasonCode == draft.reasonCode.trim() &&
      row.note == _trimOrNull(draft.note) &&
      row.authorLabel == draft.authorLabel.trim();
  static void _requireText(String value, String name) {
    if (value.trim().isEmpty) {
      throw ArgumentError.value(value, name, 'must not be empty');
    }
  }

  static String? _trimOrNull(String? value) =>
      value == null || value.trim().isEmpty ? null : value.trim();
}

final class _ReviewData {
  const _ReviewData({
    required this.sessions,
    required this.attempts,
    required this.objects,
    required this.resolutions,
    required this.events,
    required this.annotations,
  });
  final List<CheckoutSessionRow> sessions;
  final List<ScanAttemptRow> attempts;
  final List<InferenceObjectRow> objects;
  final List<ObjectResolutionRow> resolutions;
  final List<AuditEventRow> events;
  final List<AdminReviewAnnotationRow> annotations;
}
