import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/admin/settings_models.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
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
    await _show(tester, find.byKey(const Key('review-save')));
    await tester.tap(find.byKey(const Key('review-save')));
    await tester.pumpAndSettle();

    expect(repository.saved, hasLength(1));
    expect(repository.saved.single.reviewStatus, ReviewStatus.reviewed);
  });

  testWidgets('review annotation uses the current saved administrator author', (
    tester,
  ) async {
    final repository = _ReviewRepository();
    await tester.pumpWidget(
      _app(repository, currentAdminAuthor: () async => '성수점 관리자'),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('review-inbox-session-1')));
    await tester.pumpAndSettle();
    await _show(tester, find.byKey(const Key('review-save')));
    await tester.tap(find.byKey(const Key('review-save')));
    await tester.pumpAndSettle();

    expect(repository.saved.single.authorLabel, '성수점 관리자');
  });

  testWidgets(
    'review annotation resolves the persisted current settings author',
    (tester) async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      final settings = SettingsService(
        database: database,
        createId: () => 'settings-review-author',
        now: () => DateTime.utc(2026, 7, 31),
      );
      await settings.save(
        const KioskSettingsDraft(
          kioskDisplayName: 'BIXOLON Seongsu',
          retryLimit: 2,
          paymentCompleteDurationSeconds: 4,
          customerAutoReset: true,
          evidenceRetentionDays: 90,
          locale: SettingsService.koreanLocale,
          adminAuthorLabel: 'saved-ops-admin',
        ),
      );
      final repository = _ReviewRepository();
      await tester.pumpWidget(
        _app(
          repository,
          currentAdminAuthor: () async =>
              (await settings.current()).adminAuthorLabel,
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('review-inbox-session-1')));
      await tester.pumpAndSettle();
      await _show(tester, find.byKey(const Key('review-save')));
      await tester.tap(find.byKey(const Key('review-save')));
      await tester.pumpAndSettle();

      expect(repository.saved.single.authorLabel, 'saved-ops-admin');
    },
  );

  testWidgets(
    'review detail records four conclusions, tag and note, requiring a product only for both incorrect',
    (tester) async {
      final repository = _ReviewRepository();
      await tester.pumpWidget(_app(repository));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('review-inbox-session-1')));
      await tester.pumpAndSettle();

      for (final conclusion in ReviewConclusion.values) {
        await _show(
          tester,
          find.byKey(Key('review-conclusion-${conclusion.storageValue}')),
        );
        expect(
          find.byKey(Key('review-conclusion-${conclusion.storageValue}')),
          findsOneWidget,
        );
      }
      await tester.tap(
        find.byKey(const Key('review-conclusion-both_incorrect')),
      );
      await tester.pump();
      await _show(tester, find.byKey(const Key('review-correct-product')));
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
    await _show(tester, find.byKey(const Key('review-save')));
    await tester.tap(find.byKey(const Key('review-save')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('review-save-retry')), findsOneWidget);
  });

  testWidgets(
    'retained inbox shows a reload error banner and clears it after retry succeeds',
    (tester) async {
      final repository = _RetainedItemsReloadErrorRepository();
      await tester.pumpWidget(_app(repository));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('review-inbox-session-1')), findsOneWidget);

      await tester.tap(find.byKey(const Key('review-inbox-session-1')));
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('review-inbox-reload-error')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('review-inbox-retry-reload')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('review-inbox-session-1')), findsOneWidget);

      await tester.tap(find.byKey(const Key('review-inbox-retry-reload')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('review-inbox-reload-error')), findsNothing);
      expect(find.byKey(const Key('review-inbox-session-1')), findsOneWidget);
    },
  );

  testWidgets(
    'review detail shows immutable AI and customer facts with prior annotations before the new form',
    (tester) async {
      final repository = _EvidenceReviewRepository();
      await tester.pumpWidget(_app(repository));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('review-inbox-session-1')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('review-immutable-session')), findsOneWidget);
      expect(
        find.byKey(const Key('review-immutable-object-object-1')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('review-annotation-history')),
        findsOneWidget,
      );
      final aiOutcome = find.textContaining('AI 결과: Unknown');
      await _show(tester, aiOutcome);
      expect(aiOutcome, findsOneWidget);
      final unknownReason = find.textContaining('Unknown 사유: ambiguous');
      await _show(tester, unknownReason);
      expect(unknownReason, findsOneWidget);
      final candidate = find.textContaining('1. Suggested bread');
      await _show(tester, candidate);
      expect(candidate, findsOneWidget);
      final customerChoice = find.textContaining('상품: Customer bread');
      await _show(tester, customerChoice);
      expect(customerChoice, findsOneWidget);
      await _show(tester, find.text('existing append-only note'));
      expect(find.text('existing append-only note'), findsOneWidget);
      await _show(tester, find.byKey(const Key('review-save')));
      expect(find.byKey(const Key('review-save')), findsOneWidget);
    },
  );
}

Future<void> _show(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await Scrollable.ensureVisible(tester.element(finder), alignment: .5);
  await tester.pump();
}

Widget _app(
  ReviewRepository repository, {
  Future<String> Function()? currentAdminAuthor,
}) => MaterialApp(
  theme: buildBakeryTheme(),
  home: ReviewInboxScreen(
    repository: repository,
    currentAdminAuthor: currentAdminAuthor,
  ),
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
        immutableSession: ReviewImmutableSession(
          sessionId: requested.sessionId,
          terminalState: 'completed',
          targetAttemptId: requested.attemptId,
          targetObjectId: requested.objectId,
        ),
        immutableObjects: const [],
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

final class _EvidenceReviewRepository extends _ReviewRepository {
  @override
  Future<ReviewDetail> reviewDetail(ReviewTarget requested) async =>
      ReviewDetail(
        target: requested,
        immutableSession: ReviewImmutableSession(
          sessionId: requested.sessionId,
          terminalState: 'completed',
          targetAttemptId: requested.attemptId,
          targetObjectId: requested.objectId,
        ),
        immutableObjects: [
          ReviewImmutableObject(
            inferenceObjectId: 'object-1',
            objectId: 'object-1',
            skuId: null,
            skuName: 'Unknown',
            decisionPath: 'unknown_top3',
            confidence: .4,
            unknownReason: 'ambiguous',
            candidates: const [
              AdminInferenceCandidate(
                rank: 1,
                skuId: 7,
                skuName: 'Suggested bread',
                score: .71,
              ),
            ],
            customerResolution: const ReviewCustomerResolution(
              productId: 'customer-bread',
              productName: 'Customer bread',
              unitPriceKrw: 2300,
              source: 'customer_catalog',
              candidateRank: null,
            ),
          ),
        ],
        annotations: [
          AdminReviewAnnotation(
            annotationId: 'prior-annotation',
            target: requested,
            reviewStatus: ReviewStatus.reviewed,
            reasonCode: 'image_quality',
            note: 'existing append-only note',
            correctProductId: null,
            conclusion: ReviewConclusion.customerCorrect,
            authorLabel: 'prior-admin',
            createdAt: DateTime.utc(2026, 7, 31),
          ),
        ],
        products: const [
          ReviewProductOption(
            productId: 'bread',
            displayName: 'Bread',
            active: true,
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

final class _RetainedItemsReloadErrorRepository extends _ReviewRepository {
  int _inboxCalls = 0;

  @override
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    if (_inboxCalls++ == 1) throw StateError('inbox reload unavailable');
    return super.reviewInbox(filter, after, limit: limit);
  }
}
