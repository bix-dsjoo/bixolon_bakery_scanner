import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_detail_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_history_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'dart:async';

void main() {
  testWidgets('history shows human outcome before audit badges', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: _Repository()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('transaction-list')), findsOneWidget);
    expect(find.byType(Card), findsNothing);
    expect(find.text('결제 완료'), findsOneWidget);
    expect(find.text('자동 확인'), findsOneWidget);
    expect(find.text('session-1'), findsOneWidget);
  });

  testWidgets('history loads the next cursor page without hiding the first', (
    tester,
  ) async {
    final repository = _PagedRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('session-first'), findsOneWidget);
    await tester.tap(find.text('더 보기'));
    await tester.pumpAndSettle();

    expect(find.text('session-first'), findsOneWidget);
    expect(find.text('session-second'), findsOneWidget);
    expect(repository.cursorRequests, 1);
  });

  testWidgets('history ignores an old cursor page after a filter reload', (
    tester,
  ) async {
    final repository = _RacingRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('transaction-load-more')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const Key('transaction-filter-session')),
      'new',
    );
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    repository.completeReload();
    await tester.pumpAndSettle();
    repository.completeLoadMore();
    await tester.pumpAndSettle();

    expect(find.text('session-new'), findsOneWidget);
    expect(find.text('session-old-page'), findsNothing);
  });

  testWidgets(
    'history ignores a stale reload error after a newer filter result',
    (tester) async {
      final repository = _ReloadErrorRaceRepository();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: TransactionHistoryScreen(repository: repository),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('transaction-filter-session')),
        'old',
      );
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();
      await tester.enterText(
        find.byKey(const Key('transaction-filter-session')),
        'new',
      );
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();

      repository.completeOldError();
      await tester.pumpAndSettle();

      expect(find.text('session-new'), findsOneWidget);
      expect(find.byKey(const Key('transaction-reload-error')), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('history ignores a stale load-more error after a filter reload', (
    tester,
  ) async {
    final repository = _LoadMoreErrorRaceRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('transaction-load-more')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const Key('transaction-filter-session')),
      'new',
    );
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    repository.completeLoadMoreError();
    await tester.pumpAndSettle();

    expect(find.text('session-new'), findsOneWidget);
    expect(find.byKey(const Key('transaction-load-more-error')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('history ignores a reload error after it is disposed', (
    tester,
  ) async {
    final repository = _DeferredInitialRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pump();

    await tester.pumpWidget(const SizedBox.shrink());
    repository.completeError();
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'history shows retryable reload and load-more errors after busy recovery',
    (tester) async {
      final repository = _CurrentErrorRepository();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: TransactionHistoryScreen(repository: repository),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('transaction-reload-error')), findsOneWidget);
      expect(find.byKey(const Key('transaction-retry-reload')), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('transaction-retry-reload')),
            )
            .onPressed,
        isNotNull,
      );

      await tester.tap(find.byKey(const Key('transaction-retry-reload')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('transaction-load-more')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('transaction-load-more-error')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('transaction-load-more')), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('transaction-load-more')),
            )
            .onPressed,
        isNotNull,
      );
    },
  );

  testWidgets('history shows a retryable current detail error', (tester) async {
    final repository = _DetailErrorRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('session-1'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('transaction-detail-error')), findsOneWidget);
    expect(find.byKey(const Key('transaction-retry-detail')), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('transaction-retry-detail')));
    await tester.pumpAndSettle();

    expect(find.byType(Scaffold), findsOneWidget);
    expect(repository.detailRequests, 2);
  });

  testWidgets('history ignores a detail error after it is disposed', (
    tester,
  ) async {
    final repository = _DeferredDetailRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('session-1'));
    await tester.pump();
    await tester.pumpWidget(const SizedBox.shrink());
    repository.completeError();
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets('history serializes rapid detail taps into one navigation', (
    tester,
  ) async {
    final repository = _DeferredDetailRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: TransactionHistoryScreen(repository: repository),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('session-1'));
    await tester.tap(find.text('session-1'));
    await tester.pump();

    expect(repository.detailRequests, 1);
    repository.completeSuccess();
    await tester.pumpAndSettle();

    expect(find.byType(TransactionDetailScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'initial session deep link filters then pushes that exact transaction detail',
    (tester) async {
      final repository = _DeepLinkRepository();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: TransactionHistoryScreen(
            repository: repository,
            initialSessionId: 'session-attention',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(repository.filters.single.sessionQuery, 'session-attention');
      expect(repository.detailRequests, ['session-attention']);
      expect(find.byType(TransactionDetailScreen), findsOneWidget);
      expect(find.text('session-attention'), findsWidgets);
    },
  );
}

final class _DeepLinkRepository extends _Repository {
  final filters = <TransactionFilter>[];
  final detailRequests = <String>[];

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    filters.add(filter);
    return TransactionPage(items: [_item('session-attention')]);
  }

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) async {
    detailRequests.add(sessionId);
    return _detail(sessionId);
  }
}

final class _DetailErrorRepository extends _Repository {
  var detailRequests = 0;

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) {
    detailRequests++;
    if (detailRequests == 1) return Future.error(StateError('detail failed'));
    return Future.value(_detail(sessionId));
  }
}

final class _DeferredDetailRepository extends _Repository {
  final _pendingDetail = Completer<AdminTransactionDetail>();
  var detailRequests = 0;

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) {
    detailRequests++;
    return _pendingDetail.future;
  }

  void completeError() =>
      _pendingDetail.completeError(StateError('detail disposed'));
  void completeSuccess() => _pendingDetail.complete(_detailForSession());

  AdminTransactionDetail _detailForSession() => _detail('session-1');
}

AdminTransactionDetail _detail(String sessionId) => AdminTransactionDetail(
  sessionId: sessionId,
  startedAt: DateTime.utc(2026),
  terminalAt: null,
  terminalState: 'completed',
  terminalReason: null,
  catalogRevisionId: 'catalog-v1',
  settingsRevisionId: 'settings-v1',
  configSnapshotJson: '{}',
  artifacts: const AdminArtifactSnapshot(
    detectorId: 'detector',
    detectorSha256: 'a',
    repvitArtifactId: 'repvit',
    repvitSha256: 'a',
    repvitManifestSha256: 'a',
    repvitPrototypeSha256: 'a',
    dinov3ArtifactId: 'dino',
    dinov3Sha256: 'a',
    dinov3SupportSha256: 'a',
    calibrationId: 'calibration',
    calibrationSha256: 'a',
    preprocessSha256: 'a',
    fusionPolicyId: 'policy',
    fusionPolicySha256: 'a',
  ),
  attempts: const [],
  resolutions: const [],
  order: null,
  payment: null,
  hasIntegrityWarning: false,
);

final class _ReloadErrorRaceRepository implements TransactionAuditRepository {
  final _old = Completer<TransactionPage>();
  var _requestCount = 0;

  void completeOldError() =>
      _old.completeError(StateError('old reload failed'));

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) {
    _requestCount++;
    if (_requestCount == 1) {
      return Future.value(TransactionPage(items: [_item('session-first')]));
    }
    if (filter.sessionQuery == 'old') return _old.future;
    return Future.value(TransactionPage(items: [_item('session-new')]));
  }
}

final class _LoadMoreErrorRaceRepository implements TransactionAuditRepository {
  final _more = Completer<TransactionPage>();
  var _initialServed = false;

  void completeLoadMoreError() =>
      _more.completeError(StateError('more failed'));

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) {
    if (!_initialServed) {
      _initialServed = true;
      return Future.value(
        TransactionPage(
          items: [_item('session-first')],
          nextCursor: PageCursor(
            startedAt: DateTime.utc(2026),
            sessionId: 'first',
          ),
        ),
      );
    }
    if (after != null) return _more.future;
    return Future.value(TransactionPage(items: [_item('session-new')]));
  }
}

final class _DeferredInitialRepository implements TransactionAuditRepository {
  final _initial = Completer<TransactionPage>();
  void completeError() => _initial.completeError(StateError('disposed'));
  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();
  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) => _initial.future;
}

final class _CurrentErrorRepository implements TransactionAuditRepository {
  var _attempt = 0;
  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();
  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) {
    _attempt++;
    if (_attempt == 1) return Future.error(StateError('reload failed'));
    if (after == null) {
      return Future.value(
        TransactionPage(
          items: [_item('session-recovered')],
          nextCursor: PageCursor(
            startedAt: DateTime.utc(2026),
            sessionId: 'recovered',
          ),
        ),
      );
    }
    return Future.error(StateError('load more failed'));
  }
}

TransactionListItem _item(String sessionId) => TransactionListItem(
  sessionId: sessionId,
  startedAt: DateTime.utc(2026),
  terminalState: 'completed',
  breadCount: 1,
  finalAmountKrw: 1000,
  scanAttemptCount: 1,
  resolutionSources: const [],
  hasUnknown: false,
  hasRetake: false,
  hasFailure: false,
);

final class _RacingRepository implements TransactionAuditRepository {
  final _more = Completer<TransactionPage>();
  final _reload = Completer<TransactionPage>();
  var _initialServed = false;

  void completeLoadMore() =>
      _more.complete(TransactionPage(items: [_item('session-old-page', 1)]));

  void completeReload() =>
      _reload.complete(TransactionPage(items: [_item('session-new', 3)]));

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) {
    if (!_initialServed) {
      _initialServed = true;
      return Future.value(
        TransactionPage(
          items: [_item('session-first', 2)],
          nextCursor: PageCursor(
            startedAt: DateTime.utc(2026, 1, 2),
            sessionId: 'session-first',
          ),
        ),
      );
    }
    return after == null ? _reload.future : _more.future;
  }

  static TransactionListItem _item(String sessionId, int day) =>
      TransactionListItem(
        sessionId: sessionId,
        startedAt: DateTime.utc(2026, 1, day),
        terminalState: 'completed',
        breadCount: 1,
        finalAmountKrw: 1000,
        scanAttemptCount: 1,
        resolutionSources: const [],
        hasUnknown: false,
        hasRetake: false,
        hasFailure: false,
      );
}

final class _PagedRepository implements TransactionAuditRepository {
  int cursorRequests = 0;

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    if (after == null) {
      return TransactionPage(
        items: [_item('session-first', 2)],
        nextCursor: PageCursor(
          startedAt: DateTime.utc(2026, 1, 2),
          sessionId: 'session-first',
        ),
      );
    }
    cursorRequests++;
    return TransactionPage(items: [_item('session-second', 1)]);
  }

  TransactionListItem _item(String sessionId, int day) => TransactionListItem(
    sessionId: sessionId,
    startedAt: DateTime.utc(2026, 1, day),
    terminalState: 'completed',
    breadCount: 1,
    finalAmountKrw: 1000,
    scanAttemptCount: 1,
    resolutionSources: const [],
    hasUnknown: false,
    hasRetake: false,
    hasFailure: false,
  );
}

class _Repository implements TransactionAuditRepository {
  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) =>
      throw UnimplementedError();

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async => TransactionPage(
    items: [
      TransactionListItem(
        sessionId: 'session-1',
        startedAt: DateTime.utc(2026),
        terminalState: 'completed',
        breadCount: 2,
        finalAmountKrw: 4200,
        scanAttemptCount: 1,
        resolutionSources: ['ai_auto_customer_accepted'],
        hasUnknown: false,
        hasRetake: false,
        hasFailure: false,
      ),
    ],
  );
}
