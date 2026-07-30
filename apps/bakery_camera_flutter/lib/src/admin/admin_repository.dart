import 'admin_models.dart';

abstract interface class AdminRepository {
  Future<AdminDashboardSummary> dashboard(DateRange range);

  Stream<AdminDashboardSummary> watchDashboard(DateRange range);

  Future<List<AttentionItem>> recentAttentionItems({required int limit});
}
