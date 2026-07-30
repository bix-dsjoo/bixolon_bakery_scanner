import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
import 'package:bakery_camera_prototype/src/app/app_mode_controller.dart';
import 'package:bakery_camera_prototype/src/app/app_mode_surface.dart';
import 'package:bakery_camera_prototype/src/ui/admin/dashboard_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_destination.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_detail_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_history_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/customer_checkout_journey_fixture.dart';

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

      expect(
        find.byKey(const ValueKey('dashboard-summary-ledger')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey('dashboard-rate-ledger')),
        findsOneWidget,
      );

      expect(find.text('결제 완료'), findsOneWidget);
      expect(find.text('21,600원'), findsOneWidget);
      expect(find.text('확인 필요'), findsWidgets);
      expect(find.textContaining('정확도'), findsNothing);
    },
  );

  testWidgets('dashboard never shows ready without injected diagnostics', (
    tester,
  ) async {
    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: DashboardScreen(repository: repository, range: _range),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('진단 전'), findsOneWidget);
    expect(find.text('정상'), findsNothing);
  });

  testWidgets('dashboard renders unavailable when live diagnostics fail', (
    tester,
  ) async {
    final repository = _Repository();
    final availability = ValueNotifier(DashboardAvailability.unavailable);
    addTearDown(availability.dispose);
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: DashboardScreen(
          repository: repository,
          range: _range,
          readiness: availability,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('점검 필요'), findsOneWidget);
    expect(find.text('정상'), findsNothing);
  });

  testWidgets(
    'attention tap filters and opens the exact admin transaction detail',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      late CustomerCheckoutJourneyFixture fixture;
      await tester.runAsync(() async {
        fixture = await CustomerCheckoutJourneyFixture.create();
        await fixture.controller.initialize();
      });
      addTearDown(() => tester.runAsync(fixture.dispose));
      final lifecycle = _DashboardLifecycle();
      final modes = AppModeController(customerLifecycle: lifecycle);
      await modes.enterAdmin(abandonConfirmed: true);
      final repository = _AttentionRepository();

      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: BakeryAppSurface(
            checkout: fixture.controller,
            customerLifecycle: lifecycle,
            createModeController: (_) => modes,
            adminDestinationBuilder:
                (context, destination, onAttention, initialSessionId) =>
                    destination == AdminDestination.dashboard
                    ? DashboardScreen(
                        repository: repository,
                        range: _range,
                        onAttentionSelected: onAttention,
                      )
                    : destination == AdminDestination.transactions
                    ? TransactionHistoryScreen(
                        repository: repository,
                        initialSessionId: initialSessionId,
                      )
                    : Text('destination:${destination.name}'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('고객 선택이 필요한 빵'));
      await tester.pumpAndSettle();

      expect(modes.destination, AdminDestination.transactions);
      expect(
        repository.transactionFilters.single.sessionQuery,
        'session-review',
      );
      expect(repository.detailRequests, ['session-review']);
      expect(find.byType(TransactionDetailScreen), findsOneWidget);
    },
  );
}

final class _DashboardLifecycle implements CustomerModeLifecycle {
  @override
  Future<void> abandonForAdminEntry(String reason) async {}

  @override
  bool get hasActiveCustomerCheckout => false;

  @override
  Future<void> startFreshCustomerSession() async {}
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

final class _AttentionRepository extends _Repository
    implements TransactionAuditRepository {
  final transactionFilters = <TransactionFilter>[];
  final detailRequests = <String>[];

  @override
  Future<List<AttentionItem>> recentAttentionItems({
    required int limit,
  }) async => [
    AttentionItem(
      sessionId: 'session-review',
      kind: AttentionKind.unresolvedUnknown,
      occurredAt: DateTime.utc(2026, 7, 30, 12),
      label: '고객 선택이 필요한 빵',
    ),
  ];

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) async {
    detailRequests.add(sessionId);
    return AdminTransactionDetail(
      sessionId: sessionId,
      startedAt: DateTime.utc(2026, 7, 30),
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
  }

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    transactionFilters.add(filter);
    return TransactionPage(
      items: [
        TransactionListItem(
          sessionId: filter.sessionQuery ?? 'unexpected',
          startedAt: DateTime.utc(2026, 7, 30),
          terminalState: 'completed',
          breadCount: 0,
          finalAmountKrw: 0,
          scanAttemptCount: 0,
          resolutionSources: const [],
          hasUnknown: true,
          hasRetake: false,
          hasFailure: false,
        ),
      ],
    );
  }
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
