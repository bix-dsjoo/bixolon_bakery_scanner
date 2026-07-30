import 'admin_models.dart';

abstract interface class AdminRepository {
  Future<AdminDashboardSummary> dashboard(DateRange range);

  Stream<AdminDashboardSummary> watchDashboard(DateRange range);

  Future<List<AttentionItem>> recentAttentionItems({required int limit});
}

abstract interface class TransactionAuditRepository {
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  });

  Future<AdminTransactionDetail> transactionDetail(String sessionId);
}
