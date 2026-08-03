import 'package:bakery_camera_prototype/src/admin/diagnostics_models.dart';
import 'package:bakery_camera_prototype/src/ui/admin/diagnostics_screen.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows customer impact first and copies identifiers only', (
    tester,
  ) async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (method) async {
          if (method.method == 'Clipboard.setData') return null;
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(body: DiagnosticsScreen(load: () async => _snapshot)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('diagnostics-sections')), findsOneWidget);
    expect(find.byType(Card), findsNothing);
    expect(find.text('고객 계산을 계속할 수 있어요'), findsOneWidget);
    expect(find.text('시스템 다시 확인하기'), findsOneWidget);
    expect(
      find.textContaining('최근 워커 오류', skipOffstage: false),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('copy-감사 루트-C:/audit')), findsNothing);
    final detectorId = find.textContaining(
      '기대 ID: rfdetr_large_bakery_v1',
      skipOffstage: false,
    );
    expect(detectorId, findsOneWidget);
    await tester.ensureVisible(detectorId);
    await tester.pumpAndSettle();
    expect(find.textContaining('설정 변경'), findsNothing);
    expect(
      find.textContaining('출처: 완료된 추론 영수증 · 기기 cpu', skipOffstage: false),
      findsOneWidget,
    );
    expect(
      find.textContaining('최근 영수증 증적은 현재 설정과 달라', skipOffstage: false),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const ValueKey('copy-기대 ID-rfdetr_large_bakery_v1')),
    );
    await tester.pumpAndSettle();
    expect(find.text('복사했어요'), findsOneWidget);
  });
}

const _snapshot = DiagnosticsSnapshot(
  customerImpact: DiagnosticsCustomerImpact.ready,
  live: DiagnosticsLiveState(
    cameraReady: true,
    cameraLastError: null,
    worker: WorkerDiagnosticsState.ready(
      device: 'cpu',
      loadMs: 320,
      warmupMs: 85,
      detectorThreshold: 0.42,
      detectorId: 'rfdetr_large_bakery_v1',
      repvitId: 'repvit_m1_15plus5_v1',
      dinov3Id: 'dinov3_vits16_15plus5_v1',
      fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
      lastError: 'previous request failed',
    ),
  ),
  artifacts: DiagnosticsArtifactReport(
    detector: DiagnosticsArtifactStatus(
      label: 'RF-DETR-L',
      expectedId: 'rfdetr_large_bakery_v1',
      expectedSha256:
          '1111111111111111111111111111111111111111111111111111111111111111',
      observedId: 'rfdetr_large_bakery_v1',
      observedSha256:
          '1111111111111111111111111111111111111111111111111111111111111111',
      currentStartupId: 'rfdetr_large_bakery_v1',
    ),
    repvit: DiagnosticsArtifactStatus(
      label: 'RepViT-M1',
      expectedId: 'repvit_m1_15plus5_v1',
      expectedSha256:
          '2222222222222222222222222222222222222222222222222222222222222222',
      observedId: 'repvit_m1_15plus5_v1',
      observedSha256:
          '2222222222222222222222222222222222222222222222222222222222222222',
      currentStartupId: 'repvit_m1_15plus5_v1',
    ),
    dinov3: DiagnosticsArtifactStatus(
      label: 'DINOv3',
      expectedId: 'dinov3_vits16_15plus5_v1',
      expectedSha256:
          '3333333333333333333333333333333333333333333333333333333333333333',
      observedId: 'dinov3_vits16_15plus5_v1',
      observedSha256:
          '3333333333333333333333333333333333333333333333333333333333333333',
      currentStartupId: 'dinov3_vits16_15plus5_v1',
    ),
    fusion: DiagnosticsArtifactStatus(
      label: 'Fusion policy',
      expectedId: 'fusion_local_or_global_consensus_margin_v1',
      expectedSha256:
          '4444444444444444444444444444444444444444444444444444444444444444',
      observedId: 'fusion_local_or_global_consensus_margin_v1',
      observedSha256:
          '4444444444444444444444444444444444444444444444444444444444444444',
      currentStartupId: 'fusion_local_or_global_consensus_margin_v1',
    ),
  ),
  storage: DiagnosticsStorageStatus(
    schemaVersion: 4,
    migrationStatus: 'schema 4 ready',
    auditRoot: 'C:/audit',
    persistenceReady: true,
    activeCatalogRevisionId: 'catalog-v2',
  ),
  timing: DiagnosticsTimingSummary(
    sampleCount: 1,
    device: 'cpu',
    configSha256:
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    conditionalDinoRate: 0,
    decodePreprocess: DiagnosticsDistribution(
      minimumMs: 1,
      p50Ms: 1,
      maximumMs: 1,
    ),
    detector: DiagnosticsDistribution(minimumMs: 1, p50Ms: 1, maximumMs: 1),
    repvit: DiagnosticsDistribution(minimumMs: 1, p50Ms: 1, maximumMs: 1),
    dinov3: DiagnosticsDistribution(minimumMs: 0, p50Ms: 0, maximumMs: 0),
    postprocess: DiagnosticsDistribution(minimumMs: 1, p50Ms: 1, maximumMs: 1),
    total: DiagnosticsDistribution(minimumMs: 4, p50Ms: 4, maximumMs: 4),
  ),
  historicalReceiptArtifacts: DiagnosticsObservedArtifacts(
    detectorId: 'rfdetr_large_bakery_v1',
    detectorSha256:
        '1111111111111111111111111111111111111111111111111111111111111111',
    repvitId: 'repvit_m1_15plus5_v1',
    repvitSha256:
        '2222222222222222222222222222222222222222222222222222222222222222',
    dinov3Id: 'dinov3_vits16_15plus5_v1',
    dinov3Sha256:
        '3333333333333333333333333333333333333333333333333333333333333333',
    fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
    fusionPolicySha256:
        '4444444444444444444444444444444444444444444444444444444444444444',
    configSha256:
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    isStale: true,
  ),
);
