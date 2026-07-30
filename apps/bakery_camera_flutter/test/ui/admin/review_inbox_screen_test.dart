import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/ui/admin/review_inbox_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'inbox explains the exception and saves an append-only annotation',
    (tester) async {
      final repository = _ReviewRepository();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: ReviewInboxScreen(repository: repository),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('고객이 AI 추천을 바꿨음'), findsOneWidget);
      await tester.tap(find.text('고객이 AI 추천을 바꿨음'));
      await tester.pumpAndSettle();
      expect(find.text('이 기록은 모델 결과를 바꾸지 않습니다.'), findsOneWidget);
      final save = tester.widget<FilledButton>(
        find.byKey(const Key('review-save')),
      );
      expect(save.onPressed, isNotNull);
      await tester.tap(find.byKey(const Key('review-save')));
      await tester.pumpAndSettle();
      expect(repository.saved, hasLength(1));
      expect(repository.saved.single.reviewStatus, ReviewStatus.reviewed);
    },
  );
}

final class _ReviewRepository implements ReviewRepository {
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
            displayName: '소금빵',
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
        summary: '고객이 AI 추천을 바꿨음',
      ),
    ],
  );
}
