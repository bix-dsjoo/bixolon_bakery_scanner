import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
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
}

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

final class _Repository implements TransactionAuditRepository {
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
