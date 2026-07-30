import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_history_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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
