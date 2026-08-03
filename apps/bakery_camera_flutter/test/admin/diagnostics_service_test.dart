import 'dart:convert';

import 'package:bakery_camera_prototype/src/admin/diagnostics_models.dart';
import 'package:bakery_camera_prototype/src/admin/diagnostics_service.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  test(
    'reports current verified startup facts and comparable completed receipt timing only',
    () async {
      final service = DiagnosticsService(
        live: const DiagnosticsLiveState(
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
          ),
        ),
        expectedArtifacts: const DiagnosticsExpectedArtifacts(
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _detectorHash,
          repvitId: 'repvit_m1_15plus5_v1',
          repvitSha256: _repvitHash,
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _dinov3Hash,
          fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
          fusionPolicySha256: _fusionHash,
          configSha256: 'config-current',
        ),
        audit: _FakeDiagnosticsAuditReader(),
      );

      final snapshot = await service.refresh();

      expect(snapshot.customerImpact, DiagnosticsCustomerImpact.ready);
      expect(snapshot.live.worker.detectorThreshold, 0.42);
      expect(snapshot.artifacts.detector.isVerified, isTrue);
      expect(snapshot.artifacts.repvit.isVerified, isTrue);
      expect(snapshot.artifacts.dinov3.isVerified, isTrue);
      expect(snapshot.timing.sampleCount, 2);
      expect(snapshot.timing.device, 'cpu');
      expect(snapshot.timing.configSha256, 'config-current');
      expect(snapshot.timing.conditionalDinoRate, 0.5);
      expect(snapshot.timing.total.p50Ms, 180);
      expect(snapshot.storage.schemaVersion, 4);
      expect(snapshot.storage.activeCatalogRevisionId, 'catalog-v2');
    },
  );

  test(
    'keeps customer checkout ready with a healthy empty audit database',
    () async {
      final service = DiagnosticsService(
        live: const DiagnosticsLiveState(
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
          ),
        ),
        expectedArtifacts: const DiagnosticsExpectedArtifacts(
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _detectorHash,
          repvitId: 'repvit_m1_15plus5_v1',
          repvitSha256: _repvitHash,
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _dinov3Hash,
          fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
          fusionPolicySha256: _fusionHash,
          configSha256: 'config-current',
        ),
        audit: const _EmptyDiagnosticsAuditReader(),
      );

      final snapshot = await service.refresh();

      expect(snapshot.customerImpact, DiagnosticsCustomerImpact.ready);
      expect(snapshot.historicalReceiptArtifacts, isNull);
      expect(snapshot.timing.sampleCount, 0);
    },
  );

  test(
    'labels stale receipt provenance without allowing it to decide readiness',
    () async {
      final service = DiagnosticsService(
        live: const DiagnosticsLiveState(
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
          ),
        ),
        expectedArtifacts: const DiagnosticsExpectedArtifacts(
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _detectorHash,
          repvitId: 'repvit_m1_15plus5_v1',
          repvitSha256: _repvitHash,
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _dinov3Hash,
          fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
          fusionPolicySha256: _fusionHash,
          configSha256: 'config-current',
        ),
        audit: _FakeDiagnosticsAuditReader(configSha256: 'config-stale'),
      );

      final snapshot = await service.refresh();

      expect(snapshot.customerImpact, DiagnosticsCustomerImpact.ready);
      expect(snapshot.historicalReceiptArtifacts!.isStale, isTrue);
      expect(snapshot.artifacts.allVerified, isTrue);
    },
  );

  test('groups timing only for the current device and configuration', () async {
    final service = DiagnosticsService(
      live: const DiagnosticsLiveState(
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
        ),
      ),
      expectedArtifacts: const DiagnosticsExpectedArtifacts(
        detectorId: 'rfdetr_large_bakery_v1',
        detectorSha256: _detectorHash,
        repvitId: 'repvit_m1_15plus5_v1',
        repvitSha256: _repvitHash,
        dinov3Id: 'dinov3_vits16_15plus5_v1',
        dinov3Sha256: _dinov3Hash,
        fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
        fusionPolicySha256: _fusionHash,
        configSha256: 'config-current',
      ),
      audit: _FakeDiagnosticsAuditReader(
        attempts: const [
          DiagnosticsStoredAttempt(
            device: 'cpu',
            configSha256: 'config-current',
            decodePreprocessMs: 10,
            detectorMs: 40,
            repvitMs: 30,
            dinov3Ms: 0,
            postprocessMs: 10,
            totalMs: 90,
          ),
          DiagnosticsStoredAttempt(
            device: 'cuda:0',
            configSha256: 'config-current',
            decodePreprocessMs: 20,
            detectorMs: 70,
            repvitMs: 50,
            dinov3Ms: 110,
            postprocessMs: 20,
            totalMs: 180,
          ),
          DiagnosticsStoredAttempt(
            device: 'cpu',
            configSha256: 'config-stale',
            decodePreprocessMs: 30,
            detectorMs: 90,
            repvitMs: 60,
            dinov3Ms: 0,
            postprocessMs: 30,
            totalMs: 210,
          ),
        ],
      ),
    );

    final snapshot = await service.refresh();

    expect(snapshot.timing.sampleCount, 1);
    expect(snapshot.timing.total.p50Ms, 90);
    expect(snapshot.timing.device, 'cpu');
    expect(snapshot.timing.configSha256, 'config-current');
  });

  test(
    'keeps an artifact mismatch actionable and never upgrades readiness',
    () async {
      final service = DiagnosticsService(
        live: const DiagnosticsLiveState(
          cameraReady: true,
          cameraLastError: null,
          worker: WorkerDiagnosticsState.fatal(
            code: 'artifact_mismatch',
            message: 'SHA-256 mismatch',
          ),
        ),
        expectedArtifacts: const DiagnosticsExpectedArtifacts(
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _detectorHash,
          repvitId: 'repvit_m1_15plus5_v1',
          repvitSha256: _repvitHash,
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _dinov3Hash,
          fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
          fusionPolicySha256: _fusionHash,
          configSha256: 'config-current',
        ),
        audit: _FakeDiagnosticsAuditReader(withDinov3Mismatch: true),
      );

      final snapshot = await service.refresh();

      expect(snapshot.customerImpact, DiagnosticsCustomerImpact.actionRequired);
      expect(snapshot.live.worker.fatalCode, 'artifact_mismatch');
      expect(snapshot.artifacts.dinov3.isVerified, isFalse);
    },
  );

  test(
    'database reader uses the one active revision and completed receipts',
    () async {
      final fixture = await CustomerCheckoutJourneyFixture.create();
      addTearDown(fixture.dispose);
      await fixture.controller.initialize();
      await fixture.controller.scan();
      final reader = DatabaseDiagnosticsAuditReader(
        database: fixture.database,
        auditRoot: fixture.files.rootPath,
      );

      final storage = await reader.storageStatus();
      final attempts = await reader.completedAttempts();
      final retainedProbes = await fixture.database
          .customSelect(
            "SELECT name FROM sqlite_temp_master WHERE name LIKE 'diagnostics_probe_%'",
          )
          .get();

      expect(storage.activeCatalogRevisionId, 'catalog-v1');
      expect(storage.persistenceReady, isTrue);
      expect(retainedProbes, isEmpty);
      expect(attempts, hasLength(1));
      expect(attempts.single.detectorMs, 120);
      expect(attempts.single.device, 'cpu');
      expect(
        attempts.single.configSha256,
        sha256.convert(utf8.encode('{"pipeline":"canonical_cpu"}')).toString(),
      );
    },
  );

  test(
    'real healthy database with no receipts remains ready from current startup',
    () async {
      final fixture = await CustomerCheckoutJourneyFixture.create();
      addTearDown(fixture.dispose);
      final configSha256 = sha256
          .convert(utf8.encode('{"pipeline":"canonical_cpu"}'))
          .toString();
      final service = DiagnosticsService(
        live: const DiagnosticsLiveState(
          cameraReady: true,
          cameraLastError: null,
          worker: WorkerDiagnosticsState.ready(
            device: 'cpu',
            loadMs: 1,
            warmupMs: 1,
            detectorThreshold: 0.42,
            detectorId: 'rfdetr_large_bakery_v1',
            repvitId: 'repvit_m1_15plus5_v1',
            dinov3Id: 'dinov3_vits16_15plus5_v1',
            fusionPolicyId: 'fusion-v1',
          ),
        ),
        expectedArtifacts: DiagnosticsExpectedArtifacts(
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: 'b' * 64,
          repvitId: 'repvit_m1_15plus5_v1',
          repvitSha256: 'a' * 64,
          dinov3Id: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: 'd' * 64,
          fusionPolicyId: 'fusion-v1',
          fusionPolicySha256: '3' * 64,
          configSha256: configSha256,
        ),
        audit: DatabaseDiagnosticsAuditReader(
          database: fixture.database,
          auditRoot: fixture.files.rootPath,
        ),
      );

      final snapshot = await service.refresh();

      expect(snapshot.customerImpact, DiagnosticsCustomerImpact.ready);
      expect(snapshot.historicalReceiptArtifacts, isNull);
      expect(snapshot.timing.sampleCount, 0);
    },
  );
}

final class _FakeDiagnosticsAuditReader implements DiagnosticsAuditReader {
  _FakeDiagnosticsAuditReader({
    this.withDinov3Mismatch = false,
    this.configSha256 = 'config-current',
    this.attempts = _defaultAttempts,
  });

  final bool withDinov3Mismatch;
  final String configSha256;
  final List<DiagnosticsStoredAttempt> attempts;

  @override
  Future<DiagnosticsStorageStatus> storageStatus() async =>
      const DiagnosticsStorageStatus(
        schemaVersion: 4,
        migrationStatus: 'schema 4 ready',
        auditRoot: 'C:/audit',
        persistenceReady: true,
        activeCatalogRevisionId: 'catalog-v2',
      );

  @override
  Future<DiagnosticsObservedArtifacts?> latestObservedArtifacts() async =>
      DiagnosticsObservedArtifacts(
        detectorId: 'rfdetr_large_bakery_v1',
        detectorSha256: _detectorHash,
        repvitId: 'repvit_m1_15plus5_v1',
        repvitSha256: _repvitHash,
        dinov3Id: 'dinov3_vits16_15plus5_v1',
        dinov3Sha256: withDinov3Mismatch
            ? 'not-the-expected-hash'
            : _dinov3Hash,
        fusionPolicyId: 'fusion_local_or_global_consensus_margin_v1',
        fusionPolicySha256: _fusionHash,
        configSha256: configSha256,
      );

  @override
  Future<List<DiagnosticsStoredAttempt>> completedAttempts() async => attempts;
}

final class _EmptyDiagnosticsAuditReader implements DiagnosticsAuditReader {
  const _EmptyDiagnosticsAuditReader();

  @override
  Future<List<DiagnosticsStoredAttempt>> completedAttempts() async => const [];

  @override
  Future<DiagnosticsObservedArtifacts?> latestObservedArtifacts() async => null;

  @override
  Future<DiagnosticsStorageStatus> storageStatus() async =>
      const DiagnosticsStorageStatus(
        schemaVersion: 4,
        migrationStatus: 'schema 4 ready',
        auditRoot: 'C:/audit',
        persistenceReady: true,
        activeCatalogRevisionId: 'catalog-v2',
      );
}

const _defaultAttempts = [
  DiagnosticsStoredAttempt(
    device: 'cpu',
    configSha256: 'config-current',
    decodePreprocessMs: 10,
    detectorMs: 40,
    repvitMs: 30,
    dinov3Ms: 0,
    postprocessMs: 10,
    totalMs: 90,
  ),
  DiagnosticsStoredAttempt(
    device: 'cpu',
    configSha256: 'config-current',
    decodePreprocessMs: 20,
    detectorMs: 70,
    repvitMs: 50,
    dinov3Ms: 110,
    postprocessMs: 20,
    totalMs: 180,
  ),
];

const _detectorHash =
    '1111111111111111111111111111111111111111111111111111111111111111';
const _repvitHash =
    '2222222222222222222222222222222222222222222222222222222222222222';
const _dinov3Hash =
    '3333333333333333333333333333333333333333333333333333333333333333';
const _fusionHash =
    '4444444444444444444444444444444444444444444444444444444444444444';
