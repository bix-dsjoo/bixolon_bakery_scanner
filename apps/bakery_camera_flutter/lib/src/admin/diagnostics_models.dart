// Read-only facts used by the administrator diagnostics surface. These models
// intentionally contain no policy, threshold, artifact-path, or model-update
// setters: diagnostics explains the running system but cannot change it.

enum DiagnosticsCustomerImpact { ready, actionRequired }

enum WorkerDiagnosticsStatus {
  notStarted,
  starting,
  loading,
  warming,
  ready,
  fatal,
  stopped,
}

final class WorkerDiagnosticsState {
  const WorkerDiagnosticsState._({
    required this.status,
    this.device,
    this.loadMs,
    this.warmupMs,
    this.detectorThreshold,
    this.fatalCode,
    this.lastError,
    this.diagnostics = const [],
  });

  const WorkerDiagnosticsState.ready({
    required String device,
    required double loadMs,
    required double warmupMs,
    required double detectorThreshold,
    String? lastError,
    List<String> diagnostics = const [],
  }) : this._(
         status: WorkerDiagnosticsStatus.ready,
         device: device,
         loadMs: loadMs,
         warmupMs: warmupMs,
         detectorThreshold: detectorThreshold,
         lastError: lastError,
         diagnostics: diagnostics,
       );

  const WorkerDiagnosticsState.fatal({
    required String code,
    required String message,
    List<String> diagnostics = const [],
  }) : this._(
         status: WorkerDiagnosticsStatus.fatal,
         fatalCode: code,
         lastError: message,
         diagnostics: diagnostics,
       );

  const WorkerDiagnosticsState.status({
    required WorkerDiagnosticsStatus status,
    String? device,
    String? lastError,
    List<String> diagnostics = const [],
  }) : this._(
         status: status,
         device: device,
         lastError: lastError,
         diagnostics: diagnostics,
       );

  final WorkerDiagnosticsStatus status;
  final String? device;
  final double? loadMs;
  final double? warmupMs;
  final double? detectorThreshold;
  final String? fatalCode;
  final String? lastError;
  final List<String> diagnostics;

  bool get isReady => status == WorkerDiagnosticsStatus.ready;
}

final class DiagnosticsLiveState {
  const DiagnosticsLiveState({
    required this.cameraReady,
    required this.cameraLastError,
    required this.worker,
  });

  final bool cameraReady;
  final String? cameraLastError;
  final WorkerDiagnosticsState worker;
}

final class DiagnosticsExpectedArtifacts {
  const DiagnosticsExpectedArtifacts({
    required this.detectorId,
    required this.detectorSha256,
    required this.repvitId,
    required this.repvitSha256,
    required this.dinov3Id,
    required this.dinov3Sha256,
    required this.fusionPolicyId,
    required this.fusionPolicySha256,
  });

  final String detectorId;
  final String detectorSha256;
  final String repvitId;
  final String repvitSha256;
  final String dinov3Id;
  final String dinov3Sha256;
  final String fusionPolicyId;
  final String fusionPolicySha256;
}

final class DiagnosticsObservedArtifacts {
  const DiagnosticsObservedArtifacts({
    required this.detectorId,
    required this.detectorSha256,
    required this.repvitId,
    required this.repvitSha256,
    required this.dinov3Id,
    required this.dinov3Sha256,
    required this.fusionPolicyId,
    required this.fusionPolicySha256,
    required this.configSha256,
  });

  final String detectorId;
  final String detectorSha256;
  final String repvitId;
  final String repvitSha256;
  final String dinov3Id;
  final String dinov3Sha256;
  final String fusionPolicyId;
  final String fusionPolicySha256;
  final String configSha256;
}

final class DiagnosticsArtifactStatus {
  const DiagnosticsArtifactStatus({
    required this.label,
    required this.expectedId,
    required this.expectedSha256,
    required this.observedId,
    required this.observedSha256,
  });

  final String label;
  final String expectedId;
  final String expectedSha256;
  final String? observedId;
  final String? observedSha256;

  bool get isVerified =>
      observedId == expectedId && observedSha256 == expectedSha256;
}

final class DiagnosticsArtifactReport {
  const DiagnosticsArtifactReport({
    required this.detector,
    required this.repvit,
    required this.dinov3,
    required this.fusion,
  });

  final DiagnosticsArtifactStatus detector;
  final DiagnosticsArtifactStatus repvit;
  final DiagnosticsArtifactStatus dinov3;
  final DiagnosticsArtifactStatus fusion;

  bool get allVerified =>
      detector.isVerified &&
      repvit.isVerified &&
      dinov3.isVerified &&
      fusion.isVerified;
}

final class DiagnosticsStorageStatus {
  const DiagnosticsStorageStatus({
    required this.schemaVersion,
    required this.migrationStatus,
    required this.auditRoot,
    required this.persistenceReady,
    this.activeCatalogRevisionId,
  });

  final int schemaVersion;
  final String migrationStatus;
  final String auditRoot;
  final bool persistenceReady;
  final String? activeCatalogRevisionId;
}

final class DiagnosticsStoredAttempt {
  const DiagnosticsStoredAttempt({
    required this.decodePreprocessMs,
    required this.detectorMs,
    required this.repvitMs,
    required this.dinov3Ms,
    required this.postprocessMs,
    required this.totalMs,
  });

  final double decodePreprocessMs;
  final double detectorMs;
  final double repvitMs;
  final double dinov3Ms;
  final double postprocessMs;
  final double totalMs;
}

final class DiagnosticsDistribution {
  const DiagnosticsDistribution({
    required this.minimumMs,
    required this.p50Ms,
    required this.maximumMs,
  });

  const DiagnosticsDistribution.empty()
    : minimumMs = null,
      p50Ms = null,
      maximumMs = null;

  final double? minimumMs;
  final double? p50Ms;
  final double? maximumMs;
}

final class DiagnosticsTimingSummary {
  const DiagnosticsTimingSummary({
    required this.sampleCount,
    required this.conditionalDinoRate,
    required this.decodePreprocess,
    required this.detector,
    required this.repvit,
    required this.dinov3,
    required this.postprocess,
    required this.total,
  });

  const DiagnosticsTimingSummary.empty()
    : sampleCount = 0,
      conditionalDinoRate = 0,
      decodePreprocess = const DiagnosticsDistribution.empty(),
      detector = const DiagnosticsDistribution.empty(),
      repvit = const DiagnosticsDistribution.empty(),
      dinov3 = const DiagnosticsDistribution.empty(),
      postprocess = const DiagnosticsDistribution.empty(),
      total = const DiagnosticsDistribution.empty();

  final int sampleCount;
  final double conditionalDinoRate;
  final DiagnosticsDistribution decodePreprocess;
  final DiagnosticsDistribution detector;
  final DiagnosticsDistribution repvit;
  final DiagnosticsDistribution dinov3;
  final DiagnosticsDistribution postprocess;
  final DiagnosticsDistribution total;
}

final class DiagnosticsSnapshot {
  const DiagnosticsSnapshot({
    required this.customerImpact,
    required this.live,
    required this.artifacts,
    required this.storage,
    required this.timing,
  });

  final DiagnosticsCustomerImpact customerImpact;
  final DiagnosticsLiveState live;
  final DiagnosticsArtifactReport artifacts;
  final DiagnosticsStorageStatus storage;
  final DiagnosticsTimingSummary timing;
}
