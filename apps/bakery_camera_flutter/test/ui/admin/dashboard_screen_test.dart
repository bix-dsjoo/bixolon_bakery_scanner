import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
import 'package:bakery_camera_prototype/src/ui/admin/dashboard_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'dashboard presents paid total and attention without accuracy claim',
    (tester) async {
      final repository = _Repository();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: DashboardScreen(repository: repository, range: _range),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('결제 완료'), findsOneWidget);
      expect(find.text('21,600원'), findsOneWidget);
      expect(find.text('확인 필요'), findsWidgets);
      expect(find.textContaining('정확도'), findsNothing);
    },
  );
}

final _range = DateRange.utc(
  DateTime.utc(2026, 7, 30),
  DateTime.utc(2026, 7, 31),
);

final class _Repository implements AdminRepository {
  @override
  Future<AdminDashboardSummary> dashboard(DateRange range) async =>
      const AdminDashboardSummary(
        completedOrders: 3,
        grossKrw: 21600,
        scanAttempts: 5,
        retakeSessions: 1,
        unknownObjects: 2,
        customerResolvedUnknownObjects: 1,
        customerOverrides: 1,
        manualCartLines: 1,
        failedSessions: 1,
        unresolvedAttentionCount: 2,
      );

  @override
  Future<List<AttentionItem>> recentAttentionItems({
    required int limit,
  }) async => const [];

  @override
  Stream<AdminDashboardSummary> watchDashboard(DateRange range) =>
      Stream.value(awaitableSummary);
}

const awaitableSummary = AdminDashboardSummary(
  completedOrders: 3,
  grossKrw: 21600,
  scanAttempts: 5,
  retakeSessions: 1,
  unknownObjects: 2,
  customerResolvedUnknownObjects: 1,
  customerOverrides: 1,
  manualCartLines: 1,
  failedSessions: 1,
  unresolvedAttentionCount: 2,
);
