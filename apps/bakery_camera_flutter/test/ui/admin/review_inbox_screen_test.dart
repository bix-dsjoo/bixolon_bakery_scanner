import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/ui/admin/review_inbox_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('inbox opens an exception and saves an append-only annotation', (
    tester,
  ) async {
    final repository = _ReviewRepository();
    await tester.pumpWidget(_app(repository));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('review-inbox-session-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-save')));
    await tester.pumpAndSettle();

    expect(repository.saved, hasLength(1));
    expect(repository.saved.single.reviewStatus, ReviewStatus.reviewed);
  });

  testWidgets(
    'review detail records four conclusions, tag and note, requiring a product only for both incorrect',
    (tester) async {
      final repository = _ReviewRepository();
      await tester.pumpWidget(_app(repository));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('review-inbox-session-1')));
      await tester.pumpAndSettle();

      for (final conclusion in ReviewConclusion.values) {
        expect(
          find.byKey(Key('review-conclusion-${conclusion.storageValue}')),
          findsOneWidget,
        );
      }
      await tester.tap(
        find.byKey(const Key('review-conclusion-both_incorrect')),
      );
      await tester.tap(find.byKey(const Key('review-save')));
      await tester.pump();
      expect(find.byKey(const Key('review-correct-product')), findsOneWidget);

      await tester.tap(find.byKey(const Key('review-correct-product')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bread').last);
      await tester.enterText(
        find.byKey(const Key('review-note')),
        'overlapped',
      );
      await tester.scrollUntilVisible(
        find.byKey(const Key('review-save')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('review-save')));
      await tester.pumpAndSettle();

      expect(repository.saved, hasLength(1));
      expect(
        repository.saved.single.conclusion,
        ReviewConclusion.bothIncorrect,
      );
      expect(repository.saved.single.correctProductId, 'bread');
      expect(repository.saved.single.reasonCode, 'product_misclassification');
      expect(repository.saved.single.note, 'overlapped');
    },
  );

  testWidgets('detail load and save errors offer a recovery action', (
    tester,
  ) async {
    final repository = _FailingReviewRepository();
    await tester.pumpWidget(_app(repository));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('review-inbox-retry')), findsOneWidget);
    await tester.tap(find.byKey(const Key('review-inbox-retry')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-inbox-session-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('review-detail-retry')), findsOneWidget);
    await tester.tap(find.byKey(const Key('review-detail-retry')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-save')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('review-save-retry')), findsOneWidget);
  });
}

Widget _app(ReviewRepository repository) => MaterialApp(
  theme: buildBakeryTheme(),
  home: ReviewInboxScreen(repository: repository),
);

class _ReviewRepository implements ReviewRepository {
  final saved = <AdminReviewAnnotationDraft>[];
  final target = const ReviewTarget(
    sessionId: 'session-1',
    objectId: 'object-1',
  );

  @override
  Future<void> annotate(AdminReviewAnnotationDraft draft) async =>
      saved.add(draft);

  @override
  Future<ReviewDetail> reviewDetail(ReviewTarget requested) async =>
      ReviewDetail(
        target: requested,
        annotations: const [],
        products: const [
          ReviewProductOption(
            productId: 'bread',
            displayName: 'Bread',
            active: true,
          ),
        ],
      );

  @override
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async => ReviewPage(
    items: [
      ReviewInboxItem(
        target: target,
        priority: ReviewPriority.customerOverride,
        status: ReviewStatus.open,
        occurredAt: DateTime.utc(2026),
        summary: 'Customer changed AI choice',
      ),
    ],
  );
}

final class _FailingReviewRepository extends _ReviewRepository {
  int _inboxCalls = 0;
  int _detailCalls = 0;
  int _saveCalls = 0;

  @override
  Future<void> annotate(AdminReviewAnnotationDraft draft) async {
    if (_saveCalls++ == 0) throw StateError('save unavailable');
    return super.annotate(draft);
  }

  @override
  Future<ReviewDetail> reviewDetail(ReviewTarget requested) async {
    if (_detailCalls++ == 0) throw StateError('detail unavailable');
    return super.reviewDetail(requested);
  }

  @override
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    if (_inboxCalls++ == 0) throw StateError('inbox unavailable');
    return super.reviewInbox(filter, after, limit: limit);
  }
}
