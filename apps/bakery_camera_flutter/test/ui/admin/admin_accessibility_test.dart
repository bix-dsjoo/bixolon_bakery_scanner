import 'dart:async';

import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/admin/admin_repository.dart';
import 'package:bakery_camera_prototype/src/admin/diagnostics_models.dart';
import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/admin/retention_service.dart';
import 'package:bakery_camera_prototype/src/admin/review_models.dart';
import 'package:bakery_camera_prototype/src/admin/review_service.dart';
import 'package:bakery_camera_prototype/src/admin/settings_models.dart';
import 'package:bakery_camera_prototype/src/admin/settings_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:bakery_camera_prototype/src/ui/admin/dashboard_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/diagnostics_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/product_management_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/review_inbox_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/settings_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/transaction_detail_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUpAll(_loadVisualFonts);

  testWidgets(
    'admin panels remain keyboard-readable at kiosk dimensions and 200 percent text',
    (tester) async {
      final semantics = tester.ensureSemantics();
      for (final size in const [Size(1024, 720), Size(1280, 820)]) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        for (final scale in const [1.0, 2.0]) {
          await tester.pumpWidget(_app(_dashboard(), scale: scale));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull, reason: '$size / $scale');
          _expectMinimumTargets(tester);
          await tester.sendKeyEvent(LogicalKeyboardKey.tab);
          await tester.pump();
          expect(tester.binding.focusManager.primaryFocus, isNotNull);

          await tester.pumpWidget(_app(_detail(), scale: scale));
          await tester.pumpAndSettle();
          expect(find.byType(ListView), findsWidgets);
          expect(tester.takeException(), isNull);

          await tester.pumpWidget(_app(_settings(), scale: scale));
          await tester.pumpAndSettle();
          await _scrollTo(tester, find.byKey(const Key('retention-preview')));
          expect(find.byKey(const Key('retention-preview')), findsOneWidget);
        }
      }
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      semantics.dispose();
    },
  );

  testWidgets('admin golden surfaces match reviewed desktop layouts', (
    tester,
  ) async {
    final database = openInMemoryBakeryDatabase();
    addTearDown(database.close);
    await CatalogSeed(database).installIfEmpty();
    final products = ProductManagementService(
      database: database,
      createId: () => 'golden-catalog-v2',
      now: () => DateTime.utc(2026, 7, 30),
    );
    await _golden(tester, _dashboard(), 'admin_dashboard_1280x820.png');
    await _golden(tester, _detail(), 'admin_transaction_detail_1280x820.png');
    await _golden(tester, _review(), 'admin_review_1280x820.png');
    await _golden(
      tester,
      ProductManagementScreen(service: products),
      'admin_products_1280x820.png',
    );
    await _golden(tester, _diagnostics(), 'admin_diagnostics_1280x820.png');
    await _golden(tester, _settings(), 'admin_settings_1280x820.png');
  });
}

Future<void> _loadVisualFonts() async {
  final pretendard = FontLoader('Pretendard')
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Regular.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Medium.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-SemiBold.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Bold.otf'));
  final materialIcons = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  await Future.wait([pretendard.load(), materialIcons.load()]);
}

Widget _app(Widget child, {double scale = 1}) => MaterialApp(
  theme: buildBakeryTheme(),
  home: MediaQuery(
    data: MediaQueryData(
      textScaler: TextScaler.linear(scale),
      highContrast: true,
    ),
    child: Scaffold(body: child),
  ),
);

Widget _dashboard() => DashboardScreen(
  repository: _AdminRepository(),
  range: DateRange.utc(DateTime.utc(2026, 7, 30), DateTime.utc(2026, 7, 31)),
  onAttentionSelected: (_) {},
);

Widget _detail() => TransactionDetailScreen(detail: _detailModel);

Widget _review() => ReviewInboxScreen(
  repository: _ReviewRepository(),
  currentAdminAuthor: () async => 'prototype-admin',
);

Widget reviewedProductsGoldenPanel() => const Scaffold(
  appBar: null,
  body: Padding(
    padding: EdgeInsets.all(24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '상품 관리',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
        ),
        SizedBox(height: 8),
        Text('다음 고객 계산부터 새 상품 정보가 적용됩니다.'),
        SizedBox(height: 20),
        Card(
          child: ListTile(
            leading: Icon(Icons.image_not_supported_outlined),
            title: Text('사진 준비 중'),
            subtitle: Text('직접 선택 가능 · 자동 인식 연결 없음'),
            trailing: Text('1,300원'),
          ),
        ),
      ],
    ),
  ),
);

Widget _diagnostics() => DiagnosticsScreen(load: () async => _diagnosticsModel);

Widget _settings() => SettingsScreen(
  settings: _SettingsRepository(),
  retention: _RetentionRepository(),
);

Future<void> _golden(WidgetTester tester, Widget screen, String name) async {
  tester.view.physicalSize = const Size(1280, 820);
  tester.view.devicePixelRatio = 1;
  await tester.pumpWidget(_app(screen));
  await tester.pumpAndSettle();
  await expectLater(
    find.byType(Scaffold).first,
    matchesGoldenFile('../goldens/$name'),
  );
}

void _expectMinimumTargets(WidgetTester tester) {
  final controls = find
      .byWidgetPredicate(
        (widget) =>
            widget is FilledButton ||
            widget is OutlinedButton ||
            widget is IconButton,
      )
      .evaluate();
  for (final element in controls) {
    expect(
      tester
          .getSize(
            find.byElementPredicate(
              (candidate) => identical(candidate, element),
            ),
          )
          .shortestSide,
      greaterThanOrEqualTo(48),
    );
  }
}

Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  final scrollable = find.byType(Scrollable).first;
  for (
    var attempt = 0;
    attempt < 8 && finder.evaluate().isEmpty;
    attempt += 1
  ) {
    await tester.drag(scrollable, const Offset(0, -220));
    await tester.pump();
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

final class _AdminRepository implements AdminRepository {
  static const _summary = AdminDashboardSummary(
    completedOrders: 12,
    grossKrw: 84200,
    scanAttempts: 15,
    retakeSessions: 1,
    unknownObjects: 2,
    customerResolvedUnknownObjects: 1,
    customerOverrides: 1,
    manualCartLines: 1,
    failedSessions: 0,
    unresolvedAttentionCount: 1,
  );

  @override
  Future<AdminDashboardSummary> dashboard(DateRange range) async => _summary;
  @override
  Stream<AdminDashboardSummary> watchDashboard(DateRange range) =>
      Stream.value(_summary);
  @override
  Future<List<AttentionItem>> recentAttentionItems({
    required int limit,
  }) async => [
    AttentionItem(
      sessionId: 'session-1',
      kind: AttentionKind.unresolvedUnknown,
      occurredAt: DateTime.utc(2026, 7, 30, 12),
      label: '고객 선택이 필요한 빵',
    ),
  ];
}

final class _ReviewRepository implements ReviewRepository {
  @override
  Future<void> annotate(AdminReviewAnnotationDraft draft) async {}
  @override
  Future<ReviewDetail> reviewDetail(ReviewTarget target) async =>
      ReviewDetail(target: target, annotations: const [], products: const []);
  @override
  Future<ReviewPage> reviewInbox(
    ReviewFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async => ReviewPage(
    items: [
      ReviewInboxItem(
        target: const ReviewTarget(
          sessionId: 'session-1',
          objectId: 'object-2',
        ),
        priority: ReviewPriority.customerOverride,
        status: ReviewStatus.open,
        occurredAt: DateTime.utc(2026, 7, 30, 12),
        summary: '고객이 AI 추천을 바꿨어요',
      ),
    ],
  );
}

final class _SettingsRepository implements KioskSettingsRepository {
  final KioskSettings value = KioskSettings(
    revisionId: 'settings-v1',
    updatedAt: DateTime.utc(2026, 7, 30),
    kioskDisplayName: 'BIXOLON Bakery',
    retryLimit: 2,
    paymentCompleteDurationSeconds: 4,
    customerAutoReset: true,
    evidenceRetentionDays: 90,
    locale: 'ko-KR',
    adminAuthorLabel: 'prototype-admin',
  );
  @override
  Future<KioskSettings> current() async => value;
  @override
  Future<KioskSettings> save(KioskSettingsDraft draft) async => value;
}

final class _RetentionRepository implements RetentionRepository {
  @override
  Future<RetentionExecutionResult> execute(String previewId) async =>
      const RetentionExecutionResult(
        filesRemoved: 0,
        bytesRemoved: 0,
        quarantineCleanupPending: false,
      );
  @override
  Future<RetentionPreview> preview(DateTime cutoff) async =>
      RetentionPreview(previewId: 'preview', cutoff: cutoff, files: const []);
}

final _detailModel = AdminTransactionDetail(
  sessionId: 'session-1',
  startedAt: DateTime.utc(2026, 7, 30, 12),
  terminalAt: DateTime.utc(2026, 7, 30, 12, 1),
  terminalState: 'completed',
  terminalReason: null,
  catalogRevisionId: 'catalog-v1',
  settingsRevisionId: 'settings-v1',
  configSnapshotJson: '{"pipeline":"canonical_cpu"}',
  artifacts: _artifactModel,
  attempts: const [],
  resolutions: [
    AdminObjectResolution(
      resolutionId: 'resolution-1',
      inferenceObjectId: 'object-2',
      productId: 'sugar-donut',
      productName: '슈가 도넛',
      recognitionSkuId: 10,
      unitPriceKrw: 2500,
      source: 'customer_top3',
      resolvedAt: DateTime.utc(2026, 7, 30, 12),
      candidateRank: 1,
      canonicalBoxJson: '[1,2,3,4]',
      isCurrent: true,
    ),
  ],
  order: AdminFinalOrder(
    orderId: 'order-1',
    createdAt: DateTime.utc(2026, 7, 30, 12),
    totalQuantity: 2,
    totalAmountKrw: 5300,
    receipt: const AdminEvidenceReference(
      relativePath: 'order.json',
      sha256: 'a',
      byteSize: 1,
      integrity: AuditEvidenceIntegrity.retained,
    ),
    lines: const [],
  ),
  payment: AdminPaymentSnapshot(
    paymentId: 'payment-1',
    amountKrw: 5300,
    provider: 'simulated',
    status: 'approved',
    finalOrderSha256: 'a' * 64,
    paidAt: DateTime.utc(2026, 7, 30, 12, 1),
  ),
  hasIntegrityWarning: false,
);

const _artifactModel = AdminArtifactSnapshot(
  detectorId: 'rfdetr_large_bakery_v1',
  detectorSha256: 'a',
  repvitArtifactId: 'repvit_m1_15plus5_v1',
  repvitSha256: 'b',
  repvitManifestSha256: 'c',
  repvitPrototypeSha256: 'd',
  dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
  dinov3Sha256: 'e',
  dinov3SupportSha256: 'f',
  calibrationId: 'calibration-v1',
  calibrationSha256: '0',
  preprocessSha256: '1',
  fusionPolicyId: 'fusion-v1',
  fusionPolicySha256: '2',
);

const _diagnosticsModel = DiagnosticsSnapshot(
  customerImpact: DiagnosticsCustomerImpact.ready,
  live: DiagnosticsLiveState(
    cameraReady: true,
    cameraLastError: null,
    worker: WorkerDiagnosticsState.ready(
      device: 'cpu',
      loadMs: 1,
      warmupMs: 1,
      detectorThreshold: .42,
      detectorId: 'rfdetr_large_bakery_v1',
      repvitId: 'repvit_m1_15plus5_v1',
      dinov3Id: 'dinov3_vits16_15plus5_v1',
      fusionPolicyId: 'fusion-v1',
    ),
  ),
  artifacts: DiagnosticsArtifactReport(
    detector: DiagnosticsArtifactStatus(
      label: 'RF-DETR-L',
      expectedId: 'rfdetr_large_bakery_v1',
      expectedSha256: 'a',
      observedId: 'rfdetr_large_bakery_v1',
      observedSha256: 'a',
      currentStartupId: 'rfdetr_large_bakery_v1',
    ),
    repvit: DiagnosticsArtifactStatus(
      label: 'RepViT-M1',
      expectedId: 'repvit_m1_15plus5_v1',
      expectedSha256: 'b',
      observedId: 'repvit_m1_15plus5_v1',
      observedSha256: 'b',
      currentStartupId: 'repvit_m1_15plus5_v1',
    ),
    dinov3: DiagnosticsArtifactStatus(
      label: 'DINOv3',
      expectedId: 'dinov3_vits16_15plus5_v1',
      expectedSha256: 'c',
      observedId: 'dinov3_vits16_15plus5_v1',
      observedSha256: 'c',
      currentStartupId: 'dinov3_vits16_15plus5_v1',
    ),
    fusion: DiagnosticsArtifactStatus(
      label: 'Fusion',
      expectedId: 'fusion-v1',
      expectedSha256: 'd',
      observedId: 'fusion-v1',
      observedSha256: 'd',
      currentStartupId: 'fusion-v1',
    ),
  ),
  storage: DiagnosticsStorageStatus(
    schemaVersion: 4,
    migrationStatus: 'created_schema_v4',
    auditRoot: 'C:/audit',
    persistenceReady: true,
    activeCatalogRevisionId: 'catalog-v1',
  ),
  timing: DiagnosticsTimingSummary.empty(),
);
