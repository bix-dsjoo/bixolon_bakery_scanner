import 'dart:convert';

import 'package:crypto/crypto.dart';

import '../persistence/app_database.dart';
import 'diagnostics_models.dart';

abstract interface class DiagnosticsAuditReader {
  Future<DiagnosticsStorageStatus> storageStatus();
  Future<DiagnosticsObservedArtifacts?> latestObservedArtifacts();
  Future<List<DiagnosticsStoredAttempt>> completedAttempts();
}

/// A read-only facade over live scanner state and immutable persisted receipts.
/// It has no dependency on policy mutation or worker transport commands.
final class DiagnosticsService {
  DiagnosticsService({
    required DiagnosticsLiveState live,
    required this.expectedArtifacts,
    required this.audit,
  }) : liveState = (() => live);

  DiagnosticsService.live({
    required this.liveState,
    required this.expectedArtifacts,
    required this.audit,
  });

  final DiagnosticsLiveState Function() liveState;
  final DiagnosticsExpectedArtifacts expectedArtifacts;
  final DiagnosticsAuditReader audit;

  Future<DiagnosticsSnapshot> refresh() async {
    final live = liveState();
    final results = await Future.wait<dynamic>([
      audit.storageStatus(),
      audit.latestObservedArtifacts(),
      audit.completedAttempts(),
    ]);
    final storage = results[0] as DiagnosticsStorageStatus;
    final observed = results[1] as DiagnosticsObservedArtifacts?;
    final attempts = results[2] as List<DiagnosticsStoredAttempt>;
    final artifacts = _artifacts(observed);
    final impact =
        live.cameraReady &&
            live.worker.isReady &&
            storage.persistenceReady &&
            artifacts.allVerified
        ? DiagnosticsCustomerImpact.ready
        : DiagnosticsCustomerImpact.actionRequired;
    return DiagnosticsSnapshot(
      customerImpact: impact,
      live: live,
      artifacts: artifacts,
      storage: storage,
      timing: _timing(attempts),
    );
  }

  DiagnosticsArtifactReport _artifacts(
    DiagnosticsObservedArtifacts? observed,
  ) => DiagnosticsArtifactReport(
    detector: DiagnosticsArtifactStatus(
      label: 'RF-DETR-L',
      expectedId: expectedArtifacts.detectorId,
      expectedSha256: expectedArtifacts.detectorSha256,
      observedId: observed?.detectorId,
      observedSha256: observed?.detectorSha256,
    ),
    repvit: DiagnosticsArtifactStatus(
      label: 'RepViT-M1',
      expectedId: expectedArtifacts.repvitId,
      expectedSha256: expectedArtifacts.repvitSha256,
      observedId: observed?.repvitId,
      observedSha256: observed?.repvitSha256,
    ),
    dinov3: DiagnosticsArtifactStatus(
      label: 'DINOv3',
      expectedId: expectedArtifacts.dinov3Id,
      expectedSha256: expectedArtifacts.dinov3Sha256,
      observedId: observed?.dinov3Id,
      observedSha256: observed?.dinov3Sha256,
    ),
    fusion: DiagnosticsArtifactStatus(
      label: 'Fusion policy',
      expectedId: expectedArtifacts.fusionPolicyId,
      expectedSha256: expectedArtifacts.fusionPolicySha256,
      observedId: observed?.fusionPolicyId,
      observedSha256: observed?.fusionPolicySha256,
    ),
  );

  DiagnosticsTimingSummary _timing(List<DiagnosticsStoredAttempt> rows) {
    if (rows.isEmpty) return const DiagnosticsTimingSummary.empty();
    DiagnosticsDistribution distribution(Iterable<double> values) {
      final sorted = values.toList()..sort();
      final p50Index = ((sorted.length - 1) * .5).round();
      return DiagnosticsDistribution(
        minimumMs: sorted.first,
        p50Ms: sorted[p50Index],
        maximumMs: sorted.last,
      );
    }

    return DiagnosticsTimingSummary(
      sampleCount: rows.length,
      conditionalDinoRate:
          rows.where((row) => row.dinov3Ms > 0).length / rows.length,
      decodePreprocess: distribution(rows.map((row) => row.decodePreprocessMs)),
      detector: distribution(rows.map((row) => row.detectorMs)),
      repvit: distribution(rows.map((row) => row.repvitMs)),
      dinov3: distribution(rows.map((row) => row.dinov3Ms)),
      postprocess: distribution(rows.map((row) => row.postprocessMs)),
      total: distribution(rows.map((row) => row.totalMs)),
    );
  }
}

/// Drift adapter intentionally reads only complete receipts. A staged attempt
/// is not operational timing evidence and is excluded rather than guessed.
final class DatabaseDiagnosticsAuditReader implements DiagnosticsAuditReader {
  DatabaseDiagnosticsAuditReader({
    required this.database,
    required this.auditRoot,
  });

  final BakeryDatabase database;
  final String auditRoot;

  @override
  Future<DiagnosticsStorageStatus> storageStatus() async {
    try {
      await _verifyPersistenceWrite();
      final settings = await database
          .select(database.appSettings)
          .getSingleOrNull();
      return DiagnosticsStorageStatus(
        schemaVersion: database.schemaVersion,
        migrationStatus:
            settings?.lastMigrationResult ?? 'settings not initialized',
        auditRoot: auditRoot,
        persistenceReady: true,
        activeCatalogRevisionId: await _activeCatalogRevisionId(),
      );
    } on Object {
      return DiagnosticsStorageStatus(
        schemaVersion: database.schemaVersion,
        migrationStatus: 'persistence check failed',
        auditRoot: auditRoot,
        persistenceReady: false,
      );
    }
  }

  /// Exercises the same local SQLite connection with transient state only.
  /// No checkout, audit, catalog, or policy row is written by a health check.
  Future<void> _verifyPersistenceWrite() async {
    final table = 'diagnostics_probe_${DateTime.now().microsecondsSinceEpoch}';
    await database.transaction(() async {
      await database.customStatement(
        'CREATE TEMP TABLE $table (probe_value INTEGER NOT NULL)',
      );
      try {
        await database.customStatement('INSERT INTO $table VALUES (1)');
        final result = await database
            .customSelect('SELECT probe_value FROM $table')
            .getSingle();
        if (result.read<int>('probe_value') != 1) {
          throw StateError('persistence write probe returned an invalid value');
        }
      } finally {
        await database.customStatement('DROP TABLE IF EXISTS $table');
      }
    });
  }

  Future<String?> _activeCatalogRevisionId() async {
    final revisions = await database.select(database.catalogRevisions).get();
    final active = revisions.where((row) => row.isActive).toList();
    if (active.length != 1) return null;
    return active.single.revisionId;
  }

  @override
  Future<DiagnosticsObservedArtifacts?> latestObservedArtifacts() async {
    final sessions = await database.select(database.checkoutSessions).get();
    if (sessions.isEmpty) return null;
    sessions.sort(
      (left, right) => right.startedAtUs.compareTo(left.startedAtUs),
    );
    final session = sessions.first;
    return DiagnosticsObservedArtifacts(
      detectorId: session.detectorId,
      detectorSha256: session.detectorSha256,
      repvitId: session.repvitArtifactId,
      repvitSha256: session.repvitSha256,
      dinov3Id: session.dinov3ArtifactId,
      dinov3Sha256: session.dinov3Sha256,
      fusionPolicyId: session.fusionPolicyId,
      fusionPolicySha256: session.fusionPolicySha256,
      configSha256: sha256
          .convert(utf8.encode(session.configSnapshotJson))
          .toString(),
    );
  }

  @override
  Future<List<DiagnosticsStoredAttempt>> completedAttempts() async {
    final rows = await database.select(database.scanAttempts).get();
    return rows
        .where(
          (row) =>
              row.status == 'completed' &&
              row.decodePreprocessMs != null &&
              row.detectorMs != null &&
              row.repvitMs != null &&
              row.dinov3Ms != null &&
              row.postprocessMs != null &&
              row.totalMs != null,
        )
        .map(
          (row) => DiagnosticsStoredAttempt(
            decodePreprocessMs: row.decodePreprocessMs!,
            detectorMs: row.detectorMs!,
            repvitMs: row.repvitMs!,
            dinov3Ms: row.dinov3Ms!,
            postprocessMs: row.postprocessMs!,
            totalMs: row.totalMs!,
          ),
        )
        .toList(growable: false);
  }
}
