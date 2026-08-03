// ignore_for_file: prefer_initializing_formals

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';

import '../audit/audit_file_store.dart';
import '../audit/canonical_json_encoder.dart';
import '../catalog/product.dart';
import '../checkout/checkout_models.dart';
import '../checkout/checkout_ports.dart';
import '../inference/inference_models.dart';
import 'app_database.dart';

typedef AuditIdGenerator = String Function(String prefix);
typedef AuditClock = DateTime Function();

final class VerifiedAuditFileReference {
  VerifiedAuditFileReference({
    required this.relativePath,
    required this.byteSize,
    required this.sha256,
  }) {
    _requireRelativePath(relativePath);
    if (byteSize <= 0) {
      throw ArgumentError.value(byteSize, 'byteSize', 'must be positive');
    }
    _requireSha256(sha256, 'sha256');
  }

  final String relativePath;
  final int byteSize;
  final String sha256;
}

abstract interface class AuditReferenceVerifier {
  Future<VerifiedAuditFileReference> capturedImage({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required CapturedAuditFile image,
  });
  Future<VerifiedAuditFileReference> inferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  });
  Future<VerifiedAuditFileReference> finalOrderReceipt(FinalOrderDraft order);
}

/// Optional extension for preserving retained evidence when a database write
/// fails after its corresponding metadata has been produced.
abstract interface class AuditRecoveryMarkerWriter {
  Future<void> recordDatabaseFailure({
    required String operation,
    required VerifiedAuditFileReference file,
    required Object error,
  });
}

/// Both failures matter: the database transaction rolled back and retained
/// evidence could not be marked for recovery.
final class AuditRecoveryMarkerFailure extends StateError {
  AuditRecoveryMarkerFailure({
    required this.databaseError,
    required this.markerError,
    required this.retainedFile,
  }) : super(
         'database write failed and recovery marker persistence also failed: '
         '$databaseError; $markerError',
       );

  final Object databaseError;
  final Object markerError;
  final VerifiedAuditFileReference retainedFile;
}

/// Concrete bridge from the storage-neutral database port to audit files.
final class AuditFileStoreReferenceVerifier
    implements AuditReferenceVerifier, AuditRecoveryMarkerWriter {
  AuditFileStoreReferenceVerifier(this._files);

  final AuditFileStore _files;

  @override
  Future<VerifiedAuditFileReference> capturedImage({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required CapturedAuditFile image,
  }) async {
    final expectedPath = AuditFileStore.captureRelativePath(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
    );
    if (image.path != expectedPath) {
      throw StateError(
        'captured image path is not bound to its staged attempt',
      );
    }
    return _reference(
      await _files.verifyExisting(
        relativePath: expectedPath,
        sha256: image.sha256,
      ),
    );
  }

  @override
  Future<VerifiedAuditFileReference> inferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) async => _reference(
    await _files.retainInferenceReceipt(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
      receipt: receipt,
    ),
  );

  @override
  Future<VerifiedAuditFileReference> finalOrderReceipt(
    FinalOrderDraft order,
  ) async => _reference(await _files.retainFinalOrderReceipt(order));

  @override
  Future<void> recordDatabaseFailure({
    required String operation,
    required VerifiedAuditFileReference file,
    required Object error,
  }) => _files.recordDatabaseFailure(
    operation: operation,
    file: StoredAuditFile(
      relativePath: file.relativePath,
      byteSize: file.byteSize,
      sha256: file.sha256,
    ),
    error: error,
  );

  /// Finds retained files that cannot be trusted at process startup. This is
  /// deliberately read-only; recovery records an audit flag instead of
  /// deleting the only copy of the evidence.
  Future<List<String>> findRecoveryCandidates(
    Iterable<String> referencedRelativePaths,
  ) => _files.findRecoveryCandidates(
    referencedRelativePaths: referencedRelativePaths,
  );

  /// Verifies every durable database reference at startup. Missing and changed
  /// evidence are reported, never removed or rewritten.
  Future<List<String>> findInvalidRecoveryReferences(
    Iterable<StoredAuditFile> references,
  ) async {
    final issues = <String>{};
    for (final reference in references) {
      try {
        await _files.verifyExisting(
          relativePath: reference.relativePath,
          byteSize: reference.byteSize,
          sha256: reference.sha256,
        );
      } on FileSystemException {
        issues.add(reference.relativePath);
      } on StateError {
        issues.add(reference.relativePath);
      } on ArgumentError {
        issues.add(reference.relativePath);
      }
    }
    return List.unmodifiable(issues.toList()..sort());
  }

  VerifiedAuditFileReference _reference(StoredAuditFile file) =>
      VerifiedAuditFileReference(
        relativePath: file.relativePath,
        byteSize: file.byteSize,
        sha256: file.sha256,
      );
}

/// Runtime facts already verified by the artifact loader before checkout starts.
///
/// The database adapter snapshots these with each session because the Task 2
/// storage-neutral [SessionSnapshot] intentionally carries only catalog state.
final class AuditRuntimeSnapshot {
  AuditRuntimeSnapshot({
    required this.detectorId,
    required this.detectorSha256,
    required this.repvitArtifactId,
    required this.repvitSha256,
    required this.repvitManifestSha256,
    required this.repvitPrototypeSha256,
    required this.dinov3ArtifactId,
    required this.dinov3Sha256,
    required this.dinov3SupportSha256,
    required this.calibrationId,
    required this.calibrationSha256,
    required this.preprocessSha256,
    required this.fusionPolicyId,
    required this.fusionPolicySha256,
    required this.configSnapshotJson,
    required this.startupDevice,
    required this.startupLoadMs,
    required this.startupWarmupMs,
    this.startupFallbackReason,
  }) {
    for (final entry in {
      'detectorId': detectorId,
      'repvitArtifactId': repvitArtifactId,
      'dinov3ArtifactId': dinov3ArtifactId,
      'calibrationId': calibrationId,
      'fusionPolicyId': fusionPolicyId,
      'startupDevice': startupDevice,
    }.entries) {
      if (entry.value.trim().isEmpty) {
        throw ArgumentError.value(entry.value, entry.key, 'must not be empty');
      }
    }
    for (final entry in {
      'detectorSha256': detectorSha256,
      'repvitSha256': repvitSha256,
      'repvitManifestSha256': repvitManifestSha256,
      'repvitPrototypeSha256': repvitPrototypeSha256,
      'dinov3Sha256': dinov3Sha256,
      'dinov3SupportSha256': dinov3SupportSha256,
      'calibrationSha256': calibrationSha256,
      'preprocessSha256': preprocessSha256,
      'fusionPolicySha256': fusionPolicySha256,
    }.entries) {
      _requireSha256(entry.value, entry.key);
    }
    final decoded = jsonDecode(configSnapshotJson);
    if (decoded is! Map<String, Object?>) {
      throw ArgumentError.value(
        configSnapshotJson,
        'configSnapshotJson',
        'must be a JSON object',
      );
    }
    for (final entry in {
      'startupLoadMs': startupLoadMs,
      'startupWarmupMs': startupWarmupMs,
    }.entries) {
      if (!entry.value.isFinite || entry.value < 0) {
        throw ArgumentError.value(
          entry.value,
          entry.key,
          'must be finite and non-negative',
        );
      }
    }
  }

  final String detectorId;
  final String detectorSha256;
  final String repvitArtifactId;
  final String repvitSha256;
  final String repvitManifestSha256;
  final String repvitPrototypeSha256;
  final String dinov3ArtifactId;
  final String dinov3Sha256;
  final String dinov3SupportSha256;
  final String calibrationId;
  final String calibrationSha256;
  final String preprocessSha256;
  final String fusionPolicyId;
  final String fusionPolicySha256;
  final String configSnapshotJson;
  final String startupDevice;
  final double startupLoadMs;
  final double startupWarmupMs;
  final String? startupFallbackReason;
}

String canonicalInferenceReceiptJson({
  required InferenceResult result,
  required AuditRuntimeSnapshot runtimeSnapshot,
}) {
  final receipt = <String, Object?>{
    'receipt_version': 'checkout_inference_receipt_v1',
    'runtime_snapshot': {
      'detector_id': runtimeSnapshot.detectorId,
      'detector_sha256': runtimeSnapshot.detectorSha256,
      'repvit_artifact_id': runtimeSnapshot.repvitArtifactId,
      'repvit_sha256': runtimeSnapshot.repvitSha256,
      'repvit_manifest_sha256': runtimeSnapshot.repvitManifestSha256,
      'repvit_prototype_sha256': runtimeSnapshot.repvitPrototypeSha256,
      'dinov3_artifact_id': runtimeSnapshot.dinov3ArtifactId,
      'dinov3_sha256': runtimeSnapshot.dinov3Sha256,
      'dinov3_support_sha256': runtimeSnapshot.dinov3SupportSha256,
      'calibration_id': runtimeSnapshot.calibrationId,
      'calibration_sha256': runtimeSnapshot.calibrationSha256,
      'preprocess_sha256': runtimeSnapshot.preprocessSha256,
      'fusion_policy_id': runtimeSnapshot.fusionPolicyId,
      'fusion_policy_sha256': runtimeSnapshot.fusionPolicySha256,
      'config_snapshot': jsonDecode(runtimeSnapshot.configSnapshotJson),
      'startup_device': runtimeSnapshot.startupDevice,
      'startup_load_ms': runtimeSnapshot.startupLoadMs,
      'startup_warmup_ms': runtimeSnapshot.startupWarmupMs,
      'startup_fallback_reason': runtimeSnapshot.startupFallbackReason,
    },
    'result': {
      'request_id': result.requestId,
      'image': {'width': result.imageWidth, 'height': result.imageHeight},
      'device': result.device,
      'objects': [
        for (final object in result.objects)
          {
            'object_id': object.objectId,
            'sku_id': object.skuId,
            'sku_name': object.skuName,
            'bbox_xyxy': object.bboxXyxy,
            'confidence': object.confidence,
            'decision_path': object.decisionPath,
            'top3': [
              for (final candidate in object.candidates)
                {
                  'rank': candidate.rank,
                  'sku_id': candidate.skuId,
                  'sku_name': candidate.skuName,
                  'score': candidate.score,
                },
            ],
            'unknown_reason': object.unknownReason,
            'detector': {
              'source': object.detectorSource,
              'score': object.detectorScore,
            },
            'provenance': object.provenance,
          },
      ],
      'counts': {
        for (final skuId in result.counts.keys.toList()..sort())
          '$skuId': result.counts[skuId],
      },
      'unknown_count': result.unknownCount,
      'presentation': {
        'state': _presentationState(result.presentation.state),
        'final_count_usable': result.presentation.finalCountUsable,
        'retake_scope': _retakeScope(result.presentation.retakeScope),
        'retake_object_ids': result.presentation.retakeObjectIds,
        'instruction_code': _retakeReason(result.presentation.instruction),
        'candidate_object_ids': result.presentation.candidateObjectIds,
        'policy_id': result.presentation.policyId,
        'policy_sha256': result.presentation.policySha256,
      },
      'timings_ms': {
        'decode_preprocess': result.timings.decodePreprocessMs,
        'detector': result.timings.detectorMs,
        'repvit': result.timings.repvitMs,
        'dinov3': result.timings.dinov3Ms,
        'postprocess': result.timings.postprocessMs,
        'total': result.timings.totalMs,
      },
    },
  };
  return canonicalJsonEncode(receipt);
}

final class DatabaseCheckoutAuditStore
    implements
        CheckoutAuditStore,
        CheckoutRecoveryPort,
        CustomerKioskPresentationSource {
  DatabaseCheckoutAuditStore({
    required BakeryDatabase database,
    required AuditRuntimeSnapshot runtimeSnapshot,
    required AuditReferenceVerifier references,
    required AuditIdGenerator createId,
    required AuditClock now,
  }) : _database = database,
       _runtime = runtimeSnapshot,
       _references = references,
       _createId = createId,
       _now = now;

  final BakeryDatabase _database;
  final AuditRuntimeSnapshot _runtime;
  final AuditReferenceVerifier _references;
  final AuditIdGenerator _createId;
  final AuditClock _now;

  @override
  Future<CheckoutRecoveryReport> recoverInterruptedCheckout(
    DateTime detectedAt,
  ) {
    final recoveredAt = detectedAt.toUtc();
    final recoveredAtUs = _utcMicros(recoveredAt, 'detectedAt');
    return _database.transaction(() async {
      final active = await (_database.select(
        _database.checkoutSessions,
      )..where((row) => row.state.equals('active'))).get();
      final interrupted = <String>[];
      final repaired = <String>[];
      for (final session in active) {
        final payment =
            await (_database.select(_database.simulatedPayments)
                  ..where((row) => row.sessionId.equals(session.sessionId)))
                .getSingleOrNull();
        if (payment != null) {
          await (_database.update(
            _database.checkoutSessions,
          )..where((row) => row.sessionId.equals(session.sessionId))).write(
            CheckoutSessionsCompanion(
              state: const Value('completed'),
              terminalAtUs: Value(payment.paidAtUs),
              terminalReason: const Value('payment_repaired_after_restart'),
            ),
          );
          await _appendEvent(
            session.sessionId,
            'payment_state_repaired_after_restart',
            recoveredAt,
          );
          repaired.add(session.sessionId);
          continue;
        }
        await (_database.update(
          _database.checkoutSessions,
        )..where((row) => row.sessionId.equals(session.sessionId))).write(
          CheckoutSessionsCompanion(
            state: const Value('interrupted'),
            terminalAtUs: Value(recoveredAtUs),
            terminalReason: const Value('process_restart'),
          ),
        );
        await _appendEvent(
          session.sessionId,
          'session_interrupted',
          recoveredAt,
        );
        interrupted.add(session.sessionId);
      }
      final evidenceIssues = await _findAndFlagRecoveryEvidence(recoveredAt);
      return CheckoutRecoveryReport(
        interruptedSessionIds: List.unmodifiable(interrupted),
        repairedPaymentSessionIds: List.unmodifiable(repaired),
        evidenceIssuePaths: evidenceIssues,
      );
    });
  }

  Future<List<String>> _findAndFlagRecoveryEvidence(DateTime detectedAt) async {
    final references = _references;
    if (references is! AuditFileStoreReferenceVerifier) return const [];
    final attempts = await _database.select(_database.scanAttempts).get();
    final orders = await _database.select(_database.finalOrders).get();
    final evidence = [
      for (final attempt in attempts)
        _RecoveryEvidenceReference(
          sessionId: attempt.sessionId,
          file: StoredAuditFile(
            relativePath: attempt.imageRelativePath,
            byteSize: attempt.imageByteSize,
            sha256: attempt.imageSha256,
          ),
        ),
      for (final attempt in attempts)
        if (attempt.receiptRelativePath != null)
          _RecoveryEvidenceReference(
            sessionId: attempt.sessionId,
            file: StoredAuditFile(
              relativePath: attempt.receiptRelativePath!,
              byteSize: attempt.receiptByteSize!,
              sha256: attempt.receiptSha256!,
            ),
          ),
      for (final order in orders)
        _RecoveryEvidenceReference(
          sessionId: order.sessionId,
          file: StoredAuditFile(
            relativePath: order.receiptRelativePath,
            byteSize: order.receiptByteSize,
            sha256: order.receiptSha256,
          ),
        ),
    ];
    final byPath = <String, _RecoveryEvidenceReference>{
      for (final reference in evidence) reference.file.relativePath: reference,
    };
    final orphanIssues = await references.findRecoveryCandidates(
      evidence.map((reference) => reference.file.relativePath),
    );
    final invalidIssues = await references.findInvalidRecoveryReferences(
      evidence.map((reference) => reference.file),
    );
    final issues = {...orphanIssues, ...invalidIssues}.toList()..sort();
    if (issues.isEmpty) return const [];
    for (final issue in issues) {
      final sessionId =
          byPath[issue]?.sessionId ?? _sessionIdFromRecoveryPath(issue);
      if (sessionId == null) continue;
      final session = await (_database.select(
        _database.checkoutSessions,
      )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
      if (session == null) continue;
      await _appendEvidenceRecoveryEvent(sessionId, issue, detectedAt);
    }
    return List.unmodifiable(issues);
  }

  @override
  Future<List<InterruptedCheckout>> interruptNonterminalSessions(
    DateTime detectedAt,
  ) {
    final interruptedAt = _utcMicros(detectedAt, 'detectedAt');
    return _database.transaction(() async {
      final sessions = await (_database.select(
        _database.checkoutSessions,
      )..where((row) => row.state.equals('active'))).get();
      for (final session in sessions) {
        await (_database.update(
          _database.checkoutSessions,
        )..where((row) => row.sessionId.equals(session.sessionId))).write(
          CheckoutSessionsCompanion(
            state: const Value('interrupted'),
            terminalAtUs: Value(interruptedAt),
            terminalReason: const Value('process_restart'),
          ),
        );
        await _appendEvent(
          session.sessionId,
          'session_interrupted',
          detectedAt,
        );
      }
      return [
        for (final session in sessions)
          InterruptedCheckout(
            sessionId: session.sessionId,
            interruptedAt: detectedAt.toUtc(),
          ),
      ];
    });
  }

  @override
  Future<String> beginSession(SessionSnapshot snapshot) {
    final startedAtUs = _utcMicros(
      snapshot.sessionStartedAt,
      'sessionStartedAt',
    );
    return _database.transaction(() async {
      final catalog =
          await (_database.select(_database.catalogRevisions)..where(
                (row) =>
                    row.revisionId.equals(snapshot.catalogRevision.revisionId) &
                    row.isActive.equals(true),
              ))
              .getSingleOrNull();
      if (catalog == null ||
          catalog.sha256 != snapshot.catalogRevision.sha256 ||
          catalog.createdAtUs !=
              snapshot.catalogRevision.createdAt
                  .toUtc()
                  .microsecondsSinceEpoch) {
        throw StateError('session catalog snapshot is not the active revision');
      }
      final settings = await (_database.select(
        _database.appSettings,
      )..where((row) => row.settingsId.equals('operational'))).getSingle();
      final sessionId = _newId('session');
      await _database
          .into(_database.checkoutSessions)
          .insert(
            CheckoutSessionsCompanion.insert(
              sessionId: sessionId,
              state: 'active',
              startedAtUs: startedAtUs,
              catalogRevisionId: catalog.revisionId,
              settingsRevisionId: settings.activeSettingsRevisionId,
              detectorId: _runtime.detectorId,
              detectorSha256: _runtime.detectorSha256,
              repvitArtifactId: _runtime.repvitArtifactId,
              repvitSha256: _runtime.repvitSha256,
              repvitManifestSha256: _runtime.repvitManifestSha256,
              repvitPrototypeSha256: _runtime.repvitPrototypeSha256,
              dinov3ArtifactId: _runtime.dinov3ArtifactId,
              dinov3Sha256: _runtime.dinov3Sha256,
              dinov3SupportSha256: _runtime.dinov3SupportSha256,
              calibrationId: _runtime.calibrationId,
              calibrationSha256: _runtime.calibrationSha256,
              preprocessSha256: _runtime.preprocessSha256,
              fusionPolicyId: _runtime.fusionPolicyId,
              fusionPolicySha256: _runtime.fusionPolicySha256,
              configSnapshotJson: _runtime.configSnapshotJson,
            ),
          );
      await _appendEvent(
        sessionId,
        'session_started',
        snapshot.sessionStartedAt,
      );
      return sessionId;
    });
  }

  @override
  Future<int> retryLimitForSession(String sessionId) async {
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    if (session == null) {
      throw StateError('checkout session does not exist');
    }
    final settings =
        await (_database.select(_database.settingsRevisions)..where(
              (row) => row.revisionId.equals(session.settingsRevisionId),
            ))
            .getSingle();
    return settings.retryLimit;
  }

  @override
  Future<CustomerCompletionPolicy> completionPolicyForSession(
    String sessionId,
  ) async {
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    if (session == null) {
      throw StateError('checkout session does not exist');
    }
    final settings =
        await (_database.select(_database.settingsRevisions)..where(
              (row) => row.revisionId.equals(session.settingsRevisionId),
            ))
            .getSingle();
    return CustomerCompletionPolicy(
      duration: Duration(seconds: settings.paymentCompleteDurationSeconds),
      autoReset: settings.customerAutoReset,
    );
  }

  @override
  Future<String> kioskDisplayNameForSession(String sessionId) async {
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    if (session == null) {
      throw StateError('checkout session does not exist');
    }
    final settings =
        await (_database.select(_database.settingsRevisions)..where(
              (row) => row.revisionId.equals(session.settingsRevisionId),
            ))
            .getSingle();
    return settings.kioskDisplayName;
  }

  @override
  Future<void> enterManualCartMode(String sessionId, DateTime enteredAt) {
    _utcMicros(enteredAt, 'enteredAt');
    return _database.transaction(() async {
      final session = await _activeSession(sessionId);
      final settings =
          await (_database.select(_database.settingsRevisions)..where(
                (row) => row.revisionId.equals(session.settingsRevisionId),
              ))
              .getSingle();
      final completedAttempts =
          await (_database.select(_database.scanAttempts)..where(
                (row) =>
                    row.sessionId.equals(sessionId) &
                    row.status.equals('completed'),
              ))
              .get();
      if (completedAttempts.length <= settings.retryLimit) {
        throw StateError('manual cart requires exhausted scan retries');
      }
      final existing =
          await (_database.select(_database.auditEvents)..where(
                (row) =>
                    row.sessionId.equals(sessionId) &
                    row.eventType.equals('manual_cart_entered'),
              ))
              .getSingleOrNull();
      if (existing != null) {
        throw StateError('manual cart mode is already active');
      }
      await _appendEvent(sessionId, 'manual_cart_entered', enteredAt);
    });
  }

  @override
  Future<StagedAttempt> stageAttempt({
    required String sessionId,
    required int attemptNumber,
    required CapturedAuditFile image,
  }) async {
    if (attemptNumber <= 0) {
      throw ArgumentError.value(
        attemptNumber,
        'attemptNumber',
        'must be positive',
      );
    }
    _requireSha256(image.sha256, 'image.sha256');
    final capturedAt = _now().toUtc();
    final expectedImagePath = AuditFileStore.captureRelativePath(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAt,
    );
    if (image.path != expectedImagePath) {
      throw StateError(
        'captured image path is not bound to its staged attempt',
      );
    }
    final reference = await _references.capturedImage(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAt,
      image: image,
    );
    if (reference.relativePath != expectedImagePath ||
        reference.sha256 != image.sha256) {
      throw StateError('captured image reference does not match staged image');
    }
    return _withRecoveryMarker(
      operation: 'stage_attempt',
      file: reference,
      action: () => _database.transaction(() async {
        await _activeSession(sessionId);
        final attemptId = _newId('attempt');
        await _database
            .into(_database.scanAttempts)
            .insert(
              ScanAttemptsCompanion.insert(
                attemptId: attemptId,
                sessionId: sessionId,
                attemptNumber: attemptNumber,
                capturedAtUs: capturedAt.microsecondsSinceEpoch,
                imageRelativePath: reference.relativePath,
                imageByteSize: reference.byteSize,
                imageSha256: reference.sha256,
                status: 'staged',
              ),
            );
        await _appendEvent(sessionId, 'attempt_staged', capturedAt);
        return StagedAttempt(
          attemptId: attemptId,
          sessionId: sessionId,
          attemptNumber: attemptNumber,
        );
      }),
    );
  }

  @override
  Future<PersistedAttempt> completeAttempt({
    required StagedAttempt attempt,
    required InferenceResult result,
    required ImmutableJsonReceipt receipt,
  }) async {
    final expectedReceipt = canonicalInferenceReceiptJson(
      result: result,
      runtimeSnapshot: _runtime,
    );
    if (receipt.canonicalJson != expectedReceipt) {
      throw StateError(
        'inference receipt is not canonically bound to result and runtime',
      );
    }
    final calculatedReceiptHash = sha256
        .convert(utf8.encode(receipt.canonicalJson))
        .toString();
    if (calculatedReceiptHash != receipt.sha256) {
      throw StateError('inference receipt SHA-256 does not match its contents');
    }
    final reference = await _references.inferenceReceipt(
      sessionId: attempt.sessionId,
      attemptNumber: attempt.attemptNumber,
      capturedAtUtc: DateTime.fromMicrosecondsSinceEpoch(
        (await (_database.select(_database.scanAttempts)
                  ..where((row) => row.attemptId.equals(attempt.attemptId)))
                .getSingle())
            .capturedAtUs,
        isUtc: true,
      ),
      receipt: receipt,
    );
    if (reference.sha256 != receipt.sha256) {
      throw StateError('inference receipt reference has a different SHA-256');
    }
    final width = _canonicalDimension(result.imageWidth, 'imageWidth');
    final height = _canonicalDimension(result.imageHeight, 'imageHeight');
    _validateInferenceObjects(result.objects);

    return _withRecoveryMarker(
      operation: 'complete_attempt',
      file: reference,
      action: () => _database.transaction(() async {
        final row =
            await (_database.select(_database.scanAttempts)..where(
                  (candidate) => candidate.attemptId.equals(attempt.attemptId),
                ))
                .getSingleOrNull();
        if (row == null ||
            row.sessionId != attempt.sessionId ||
            row.attemptNumber != attempt.attemptNumber ||
            row.status != 'staged') {
          throw StateError('attempt is not the matching staged attempt');
        }
        final session = await _activeSession(attempt.sessionId);
        _verifyRuntimeSnapshot(session);
        _verifyResultProvenance(result.objects, session);
        for (final object in result.objects) {
          final inferenceObjectId = '${attempt.attemptId}/${object.objectId}';
          await _database
              .into(_database.inferenceObjects)
              .insert(
                InferenceObjectsCompanion.insert(
                  inferenceObjectId: inferenceObjectId,
                  attemptId: attempt.attemptId,
                  objectId: object.objectId,
                  skuId: Value(object.skuId),
                  skuName: object.skuName,
                  decisionPath: object.decisionPath,
                  confidence: object.confidence,
                  bboxJson: jsonEncode(object.bboxXyxy),
                  detectorSource: object.detectorSource,
                  detectorScore: object.detectorScore,
                  provenanceJson: jsonEncode(object.provenance),
                  unknownReason: Value(object.unknownReason),
                ),
              );
          for (final candidate in object.candidates) {
            await _database
                .into(_database.inferenceCandidates)
                .insert(
                  InferenceCandidatesCompanion.insert(
                    inferenceCandidateId:
                        '$inferenceObjectId/${candidate.rank}',
                    inferenceObjectId: inferenceObjectId,
                    rank: candidate.rank,
                    skuId: candidate.skuId,
                    skuName: candidate.skuName,
                    score: candidate.score,
                  ),
                );
          }
        }
        await (_database.update(_database.scanAttempts)..where(
              (candidate) => candidate.attemptId.equals(attempt.attemptId),
            ))
            .write(
              ScanAttemptsCompanion(
                status: const Value('completed'),
                canonicalWidth: Value(width),
                canonicalHeight: Value(height),
                receiptRelativePath: Value(reference.relativePath),
                receiptByteSize: Value(reference.byteSize),
                receiptSha256: Value(reference.sha256),
                presentationState: Value(
                  _presentationState(result.presentation.state),
                ),
                finalCountUsable: Value(result.presentation.finalCountUsable),
                retakeScope: Value(
                  _retakeScope(result.presentation.retakeScope),
                ),
                retakeReason: Value(
                  _retakeReason(result.presentation.instruction),
                ),
                presentationPolicyId: Value(result.presentation.policyId),
                presentationPolicySha256: Value(
                  result.presentation.policySha256,
                ),
                decodePreprocessMs: Value(result.timings.decodePreprocessMs),
                detectorMs: Value(result.timings.detectorMs),
                repvitMs: Value(result.timings.repvitMs),
                dinov3Ms: Value(result.timings.dinov3Ms),
                postprocessMs: Value(result.timings.postprocessMs),
                totalMs: Value(result.timings.totalMs),
                startupDevice: Value(_runtime.startupDevice),
                startupLoadMs: Value(_runtime.startupLoadMs),
                startupWarmupMs: Value(_runtime.startupWarmupMs),
                startupFallbackReason: Value(_runtime.startupFallbackReason),
              ),
            );
        await _appendEvent(attempt.sessionId, 'attempt_completed', _now());
        return PersistedAttempt(attemptId: attempt.attemptId);
      }),
    );
  }

  @override
  Future<void> recordResolution(ObjectResolutionDraft resolution) {
    final resolvedAtUs = _utcMicros(resolution.resolvedAt, 'resolvedAt');
    return _database.transaction(() async {
      final session = await _activeSession(resolution.sessionId);
      final object = await _latestObject(
        resolution.sessionId,
        resolution.inferenceObject.objectId,
      );
      await _verifyInferenceIdentity(object, resolution.inferenceObject);
      final product = await _sessionProduct(session, resolution.product);
      final candidateRank = await _validateResolutionSource(
        session,
        object,
        resolution.inferenceObject,
        product,
        resolution.source,
      );
      await (_database.update(_database.objectResolutions)..where(
            (row) =>
                row.inferenceObjectId.equals(object.inferenceObjectId) &
                row.isCurrent.equals(true),
          ))
          .write(const ObjectResolutionsCompanion(isCurrent: Value(false)));
      await _database
          .into(_database.objectResolutions)
          .insert(
            ObjectResolutionsCompanion.insert(
              resolutionId: _newId('resolution'),
              sessionId: resolution.sessionId,
              inferenceObjectId: Value(object.inferenceObjectId),
              productRevisionId: product.productRevisionId,
              productId: product.productId,
              recognitionSkuId: Value(product.recognitionSkuId),
              productName: product.displayName,
              unitPriceKrw: product.unitPriceKrw,
              source: resolution.source.storageValue,
              resolvedAtUs: resolvedAtUs,
              candidateRank: Value(candidateRank),
              canonicalBboxJson: Value(object.bboxJson),
              isCurrent: true,
            ),
          );
      await _appendEvent(
        resolution.sessionId,
        'object_resolved',
        resolution.resolvedAt,
      );
    });
  }

  @override
  Future<void> replaceDraftOrder(String sessionId, List<CheckoutLine> lines) {
    if (lines.map((line) => line.product.productId).toSet().length !=
        lines.length) {
      throw ArgumentError.value(
        lines,
        'lines',
        'draft product IDs must be unique',
      );
    }
    return _database.transaction(() async {
      final session = await _activeSession(sessionId);
      final verified = <({ProductRow row, int quantity})>[];
      for (final line in lines) {
        verified.add((
          row: await _sessionProduct(session, line.product),
          quantity: line.quantity,
        ));
      }
      await (_database.delete(
        _database.draftOrderLines,
      )..where((row) => row.sessionId.equals(sessionId))).go();
      for (final entry in verified) {
        final product = entry.row;
        await _database
            .into(_database.draftOrderLines)
            .insert(
              DraftOrderLinesCompanion.insert(
                draftLineId: _newId('draft-line'),
                sessionId: sessionId,
                productRevisionId: product.productRevisionId,
                productId: product.productId,
                productName: product.displayName,
                recognitionSkuId: Value(product.recognitionSkuId),
                unitPriceKrw: product.unitPriceKrw,
                quantity: entry.quantity,
              ),
            );
      }
      await _appendEvent(sessionId, 'draft_order_replaced', _now());
    });
  }

  @override
  Future<PaymentReceipt> commitSimulatedPayment(
    FinalOrderDraft order, {
    SimulatedPaymentRequest? request,
  }) async {
    VerifiedAuditFileReference? retainedReceipt;
    try {
      return await _database.transaction(() async {
        final existing =
            await (_database.select(_database.simulatedPayments)
                  ..where((row) => row.sessionId.equals(order.sessionId)))
                .getSingleOrNull();
        if (existing != null) return _receipt(existing);

        final session = await _activeSession(order.sessionId);
        final paymentRequest =
            request ??
            SimulatedPaymentRequest(
              paymentId: _newId('payment'),
              orderId: _newId('order'),
              committedAt: _now().toUtc(),
            );
        await _verifyOrderCatalog(order, session);
        for (final line in order.lines) {
          await _sessionProduct(session, line.product);
        }
        final latestAttempt = await _latestCompletedAttempt(order.sessionId);
        final objects = latestAttempt == null
            ? const <InferenceObjectRow>[]
            : await (_database.select(_database.inferenceObjects)..where(
                    (row) => row.attemptId.equals(latestAttempt.attemptId),
                  ))
                  .get();
        final manualCartMode =
            await (_database.select(_database.auditEvents)..where(
                  (row) =>
                      row.sessionId.equals(order.sessionId) &
                      row.eventType.equals('manual_cart_entered'),
                ))
                .getSingleOrNull() !=
            null;
        final resolutions = manualCartMode || objects.isEmpty
            ? const <ObjectResolutionRow>[]
            : await (_database.select(_database.objectResolutions)..where(
                    (row) =>
                        row.isCurrent.equals(true) &
                        row.sessionId.equals(order.sessionId) &
                        row.inferenceObjectId.isIn(
                          objects
                              .map((object) => object.inferenceObjectId)
                              .toList(growable: false),
                        ),
                  ))
                  .get();
        if (!manualCartMode && resolutions.length != objects.length) {
          throw StateError('every current inference object must be resolved');
        }

        final draftLines = await (_database.select(
          _database.draftOrderLines,
        )..where((row) => row.sessionId.equals(order.sessionId))).get();
        _verifyDraftMatchesOrder(order, draftLines);
        final draftByProduct = {
          for (final line in draftLines) line.productId: line,
        };
        for (final resolution in resolutions) {
          final object = objects.singleWhere(
            (candidate) =>
                candidate.inferenceObjectId == resolution.inferenceObjectId,
          );
          final draft = draftByProduct[resolution.productId];
          if (draft == null) {
            throw StateError(
              'resolved product is missing from the persisted draft: '
              '${resolution.productId}',
            );
          }
          await _verifyPersistedResolution(
            session: session,
            object: object,
            resolution: resolution,
            draft: draft,
          );
        }
        for (final line in draftLines) {
          final resolvedCount = resolutions
              .where((resolution) => resolution.productId == line.productId)
              .length;
          if (resolvedCount > line.quantity) {
            throw StateError(
              'draft quantity is lower than resolved object count for '
              '${line.productId}',
            );
          }
        }

        final receiptReference = await _references.finalOrderReceipt(order);
        retainedReceipt = receiptReference;
        final orderId = paymentRequest.orderId;
        final paymentId = paymentRequest.paymentId;
        final paidAt = paymentRequest.committedAt.toUtc();
        await _database
            .into(_database.finalOrders)
            .insert(
              FinalOrdersCompanion.insert(
                orderId: orderId,
                sessionId: order.sessionId,
                catalogRevisionId: session.catalogRevisionId,
                createdAtUs: order.createdAt.toUtc().microsecondsSinceEpoch,
                totalQuantity: draftLines.fold(
                  0,
                  (total, line) => total + line.quantity,
                ),
                totalAmountKrw: draftLines.fold(
                  0,
                  (total, line) => total + (line.unitPriceKrw * line.quantity),
                ),
                receiptRelativePath: receiptReference.relativePath,
                receiptByteSize: receiptReference.byteSize,
                receiptSha256: receiptReference.sha256,
              ),
            );
        for (final line in draftLines) {
          final countsBySource = <String, int>{};
          for (final resolution in resolutions.where(
            (resolution) => resolution.productId == line.productId,
          )) {
            countsBySource[resolution.source] =
                (countsBySource[resolution.source] ?? 0) + 1;
          }
          for (final entry in countsBySource.entries) {
            await _insertFinalLine(
              orderId: orderId,
              draft: line,
              quantity: entry.value,
              source: entry.key,
            );
          }
          final resolvedQuantity = countsBySource.values.fold(
            0,
            (total, quantity) => total + quantity,
          );
          final manualQuantity = line.quantity - resolvedQuantity;
          if (manualQuantity > 0) {
            await _insertFinalLine(
              orderId: orderId,
              draft: line,
              quantity: manualQuantity,
              source: CustomerResolutionSource.customerManualCart.storageValue,
            );
          }
        }
        final amount = draftLines.fold(
          0,
          (total, line) => total + (line.unitPriceKrw * line.quantity),
        );
        await _database
            .into(_database.simulatedPayments)
            .insert(
              SimulatedPaymentsCompanion.insert(
                paymentId: paymentId,
                orderId: orderId,
                sessionId: order.sessionId,
                amountKrw: amount,
                currency: paymentRequest.currency,
                provider: paymentRequest.provider,
                status: paymentRequest.status,
                finalOrderSha256: receiptReference.sha256,
                paidAtUs: paidAt.microsecondsSinceEpoch,
              ),
            );
        await (_database.update(
          _database.checkoutSessions,
        )..where((row) => row.sessionId.equals(order.sessionId))).write(
          CheckoutSessionsCompanion(
            state: const Value('completed'),
            terminalAtUs: Value(paidAt.microsecondsSinceEpoch),
            terminalReason: const Value('payment_committed'),
          ),
        );
        await _appendEvent(order.sessionId, 'payment_committed', paidAt);
        return PaymentReceipt(
          paymentId: paymentId,
          orderId: orderId,
          sessionId: order.sessionId,
          amount: amount,
          currency: paymentRequest.currency,
          provider: paymentRequest.provider,
          status: paymentRequest.status,
          paidAt: paidAt,
        );
      });
    } catch (error) {
      final receipt = retainedReceipt;
      if (receipt != null) {
        await _recordDatabaseFailure(
          operation: 'commit_payment',
          file: receipt,
          error: error,
        );
      }
      rethrow;
    }
  }

  @override
  Future<void> abandonSession(String sessionId, String reason) {
    if (reason.trim().isEmpty) {
      throw ArgumentError.value(reason, 'reason', 'must not be empty');
    }
    final abandonedAt = _now().toUtc();
    return _database.transaction(() async {
      await _activeSession(sessionId);
      await (_database.update(
        _database.checkoutSessions,
      )..where((row) => row.sessionId.equals(sessionId))).write(
        CheckoutSessionsCompanion(
          state: const Value('abandoned'),
          terminalAtUs: Value(abandonedAt.microsecondsSinceEpoch),
          terminalReason: Value(reason),
        ),
      );
      await _appendEvent(sessionId, 'session_abandoned', abandonedAt);
    });
  }

  Future<CheckoutSessionRow> _activeSession(String sessionId) async {
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    if (session == null || session.state != 'active') {
      throw StateError('checkout session is not active: $sessionId');
    }
    return session;
  }

  Future<ProductRow> _sessionProduct(
    CheckoutSessionRow session,
    Product requested,
  ) async {
    final row =
        await (_database.select(_database.products)..where(
              (row) =>
                  row.catalogRevisionId.equals(session.catalogRevisionId) &
                  row.productId.equals(requested.productId),
            ))
            .getSingleOrNull();
    if (row == null ||
        !row.active ||
        row.displayName != requested.displayName ||
        row.unitPriceKrw != requested.unitPrice ||
        row.recognitionSkuId != requested.recognitionSkuId ||
        row.categoryId != requested.categoryId) {
      throw StateError(
        'product does not match session catalog: ${requested.productId}',
      );
    }
    return row;
  }

  Future<InferenceObjectRow> _latestObject(
    String sessionId,
    String objectId,
  ) async {
    final attempts =
        await (_database.select(_database.scanAttempts)
              ..where(
                (row) =>
                    row.sessionId.equals(sessionId) &
                    row.status.equals('completed'),
              )
              ..orderBy([(row) => OrderingTerm.desc(row.attemptNumber)]))
            .get();
    if (attempts.isEmpty) {
      throw StateError('session has no completed inference attempt');
    }
    final object =
        await (_database.select(_database.inferenceObjects)..where(
              (row) =>
                  row.attemptId.equals(attempts.first.attemptId) &
                  row.objectId.equals(objectId),
            ))
            .getSingleOrNull();
    if (object == null) {
      throw StateError('object is not in the latest completed attempt');
    }
    return object;
  }

  Future<ScanAttemptRow?> _latestCompletedAttempt(String sessionId) async {
    return (_database.select(_database.scanAttempts)
          ..where(
            (row) =>
                row.sessionId.equals(sessionId) &
                row.status.equals('completed'),
          )
          ..orderBy([(row) => OrderingTerm.desc(row.attemptNumber)])
          ..limit(1))
        .getSingleOrNull();
  }

  Future<void> _verifyInferenceIdentity(
    InferenceObjectRow row,
    InferenceObject object,
  ) async {
    if (row.skuId != object.skuId ||
        row.skuName != object.skuName ||
        row.decisionPath != object.decisionPath ||
        row.confidence != object.confidence ||
        row.bboxJson != jsonEncode(object.bboxXyxy) ||
        row.detectorSource != object.detectorSource ||
        row.detectorScore != object.detectorScore ||
        row.provenanceJson != jsonEncode(object.provenance) ||
        row.unknownReason != object.unknownReason) {
      throw StateError('resolution inference object does not match audit row');
    }
    final persistedCandidates =
        await (_database.select(_database.inferenceCandidates)
              ..where(
                (candidate) =>
                    candidate.inferenceObjectId.equals(row.inferenceObjectId),
              )
              ..orderBy([(candidate) => OrderingTerm.asc(candidate.rank)]))
            .get();
    if (persistedCandidates.length != object.candidates.length) {
      throw StateError('resolution candidate evidence does not match audit');
    }
    for (var index = 0; index < persistedCandidates.length; index += 1) {
      final persisted = persistedCandidates[index];
      final supplied = object.candidates[index];
      if (persisted.rank != supplied.rank ||
          persisted.skuId != supplied.skuId ||
          persisted.skuName != supplied.skuName ||
          persisted.score != supplied.score) {
        throw StateError('resolution candidate evidence does not match audit');
      }
    }
  }

  Future<int?> _validateResolutionSource(
    CheckoutSessionRow session,
    InferenceObjectRow row,
    InferenceObject object,
    ProductRow product,
    CustomerResolutionSource source,
  ) async {
    if (source == CustomerResolutionSource.customerManualCart) {
      throw StateError('object-linked resolution cannot be manual cart');
    }
    if (!object.isUnknown) {
      final automaticallyMappedProduct = await _mappedSessionProductForSku(
        session,
        object.skuId!,
      );
      if (automaticallyMappedProduct == null) {
        if (source != CustomerResolutionSource.customerCatalog) {
          throw StateError(
            'unmapped registered inference requires catalog selection',
          );
        }
        return null;
      }
      final expectedSource =
          product.productRevisionId ==
              automaticallyMappedProduct.productRevisionId
          ? CustomerResolutionSource.aiAutoCustomerAccepted
          : CustomerResolutionSource.customerOverrodeAuto;
      if (source != expectedSource) {
        throw StateError(
          'registered resolution source does not match AI product identity',
        );
      }
      return null;
    }
    if (source == CustomerResolutionSource.aiAutoCustomerAccepted ||
        source == CustomerResolutionSource.customerOverrodeAuto) {
      throw StateError('Unknown objects have no automatic SKU to accept');
    }
    if (source != CustomerResolutionSource.customerTop3) return null;
    if (product.recognitionSkuId == null) {
      throw StateError('Top 3 selection must map to a recognition SKU');
    }
    final candidate =
        await (_database.select(_database.inferenceCandidates)..where(
              (candidate) =>
                  candidate.inferenceObjectId.equals(row.inferenceObjectId) &
                  candidate.skuId.equals(product.recognitionSkuId!),
            ))
            .getSingleOrNull();
    if (candidate == null) {
      throw StateError('selected product is not an authorized Top 3 candidate');
    }
    return candidate.rank;
  }

  Future<ProductRow?> _mappedSessionProductForSku(
    CheckoutSessionRow session,
    int recognitionSkuId,
  ) async {
    final matches =
        await (_database.select(_database.products)..where(
              (row) =>
                  row.catalogRevisionId.equals(session.catalogRevisionId) &
                  row.active.equals(true) &
                  row.recognitionSkuId.equals(recognitionSkuId),
            ))
            .get();
    if (matches.length > 1) {
      throw StateError(
        'session catalog maps recognition SKU $recognitionSkuId more than once',
      );
    }
    return matches.firstOrNull;
  }

  void _verifyRuntimeSnapshot(CheckoutSessionRow session) {
    if (session.detectorId != _runtime.detectorId ||
        session.detectorSha256 != _runtime.detectorSha256 ||
        session.repvitArtifactId != _runtime.repvitArtifactId ||
        session.repvitSha256 != _runtime.repvitSha256 ||
        session.repvitManifestSha256 != _runtime.repvitManifestSha256 ||
        session.repvitPrototypeSha256 != _runtime.repvitPrototypeSha256 ||
        session.dinov3ArtifactId != _runtime.dinov3ArtifactId ||
        session.dinov3Sha256 != _runtime.dinov3Sha256 ||
        session.dinov3SupportSha256 != _runtime.dinov3SupportSha256 ||
        session.calibrationId != _runtime.calibrationId ||
        session.calibrationSha256 != _runtime.calibrationSha256 ||
        session.preprocessSha256 != _runtime.preprocessSha256 ||
        session.fusionPolicyId != _runtime.fusionPolicyId ||
        session.fusionPolicySha256 != _runtime.fusionPolicySha256 ||
        session.configSnapshotJson != _runtime.configSnapshotJson) {
      throw StateError('runtime identity differs from session snapshot');
    }
  }

  void _verifyResultProvenance(
    List<InferenceObject> objects,
    CheckoutSessionRow session,
  ) {
    for (final object in objects) {
      final provenance = object.provenance;
      if (provenance['detector_id'] != session.detectorId ||
          provenance['repvit_artifact_id'] != session.repvitArtifactId ||
          provenance['repvit_sha256'] != session.repvitSha256 ||
          provenance['repvit_manifest_sha256'] !=
              session.repvitManifestSha256 ||
          provenance['repvit_prototype_sha256'] !=
              session.repvitPrototypeSha256 ||
          provenance['dinov3_artifact_id'] != session.dinov3ArtifactId ||
          provenance['dinov3_sha256'] != session.dinov3Sha256 ||
          provenance['dinov3_support_sha256'] != session.dinov3SupportSha256 ||
          provenance['calibration_id'] != session.calibrationId ||
          provenance['calibration_sha256'] != session.calibrationSha256 ||
          provenance['preprocess_sha256'] != session.preprocessSha256) {
        throw StateError(
          'inference object provenance differs from session snapshot',
        );
      }
    }
  }

  Future<void> _verifyPersistedResolution({
    required CheckoutSessionRow session,
    required InferenceObjectRow object,
    required ObjectResolutionRow resolution,
    required DraftOrderLineRow draft,
  }) async {
    if (resolution.sessionId != session.sessionId ||
        resolution.canonicalBboxJson != object.bboxJson ||
        resolution.productRevisionId != draft.productRevisionId ||
        resolution.productId != draft.productId ||
        resolution.productName != draft.productName ||
        resolution.unitPriceKrw != draft.unitPriceKrw ||
        resolution.recognitionSkuId != draft.recognitionSkuId) {
      throw StateError('persisted resolution does not match session and draft');
    }
    final source = CustomerResolutionSource.parse(resolution.source);
    final automaticallyMappedProduct = object.skuId == null
        ? null
        : await _mappedSessionProductForSku(session, object.skuId!);
    if (object.skuId == null || automaticallyMappedProduct == null) {
      if (object.skuId != null &&
          source != CustomerResolutionSource.customerCatalog) {
        throw StateError('unmapped registered resolution source is invalid');
      }
      if (source != CustomerResolutionSource.customerTop3 &&
          source != CustomerResolutionSource.customerCatalog) {
        throw StateError('Unknown resolution source is invalid');
      }
      if (source == CustomerResolutionSource.customerTop3) {
        final candidate =
            await (_database.select(_database.inferenceCandidates)..where(
                  (row) =>
                      row.inferenceObjectId.equals(object.inferenceObjectId) &
                      row.rank.equalsNullable(resolution.candidateRank),
                ))
                .getSingleOrNull();
        if (candidate == null ||
            candidate.skuId != resolution.recognitionSkuId) {
          throw StateError(
            'Top 3 resolution does not match candidate evidence',
          );
        }
      } else if (resolution.candidateRank != null) {
        throw StateError('catalog resolution cannot claim a candidate rank');
      }
    } else {
      final expectedSource =
          resolution.productRevisionId ==
              automaticallyMappedProduct.productRevisionId
          ? CustomerResolutionSource.aiAutoCustomerAccepted
          : CustomerResolutionSource.customerOverrodeAuto;
      if (source != expectedSource) {
        throw StateError(
          'registered resolution source does not match AI product identity',
        );
      }
      if (resolution.candidateRank != null) {
        throw StateError('registered resolution cannot claim candidate rank');
      }
    }
  }

  Future<void> _verifyOrderCatalog(
    FinalOrderDraft order,
    CheckoutSessionRow session,
  ) async {
    if (order.catalogRevision.revisionId != session.catalogRevisionId) {
      throw StateError('order catalog revision differs from session snapshot');
    }
    final revision =
        await (_database.select(
              _database.catalogRevisions,
            )..where((row) => row.revisionId.equals(session.catalogRevisionId)))
            .getSingle();
    if (revision.sha256 != order.catalogRevision.sha256 ||
        revision.createdAtUs !=
            order.catalogRevision.createdAt.toUtc().microsecondsSinceEpoch) {
      throw StateError('order catalog identity differs from session snapshot');
    }
  }

  void _verifyDraftMatchesOrder(
    FinalOrderDraft order,
    List<DraftOrderLineRow> draft,
  ) {
    if (draft.length != order.lines.length || draft.isEmpty) {
      throw StateError('final order does not match the persisted draft');
    }
    final requested = {
      for (final line in order.lines) line.product.productId: line,
    };
    for (final row in draft) {
      final line = requested[row.productId];
      if (line == null ||
          line.quantity != row.quantity ||
          line.product.displayName != row.productName ||
          line.product.unitPrice != row.unitPriceKrw ||
          line.product.recognitionSkuId != row.recognitionSkuId) {
        throw StateError('final order line differs from the persisted draft');
      }
    }
  }

  Future<void> _insertFinalLine({
    required String orderId,
    required DraftOrderLineRow draft,
    required int quantity,
    required String source,
  }) {
    return _database
        .into(_database.finalOrderLines)
        .insert(
          FinalOrderLinesCompanion.insert(
            finalLineId: _newId('final-line'),
            orderId: orderId,
            productRevisionId: draft.productRevisionId,
            productId: draft.productId,
            recognitionSkuId: Value(draft.recognitionSkuId),
            productName: draft.productName,
            unitPriceKrw: draft.unitPriceKrw,
            quantity: quantity,
            lineAmountKrw: draft.unitPriceKrw * quantity,
            resolutionSource: source,
          ),
        );
  }

  PaymentReceipt _receipt(SimulatedPaymentRow payment) => PaymentReceipt(
    paymentId: payment.paymentId,
    orderId: payment.orderId,
    sessionId: payment.sessionId,
    amount: payment.amountKrw,
    currency: payment.currency,
    provider: payment.provider,
    status: payment.status,
    paidAt: DateTime.fromMicrosecondsSinceEpoch(payment.paidAtUs, isUtc: true),
  );

  Future<T> _withRecoveryMarker<T>({
    required String operation,
    required VerifiedAuditFileReference file,
    required Future<T> Function() action,
  }) async {
    try {
      return await action();
    } catch (error) {
      await _recordDatabaseFailure(
        operation: operation,
        file: file,
        error: error,
      );
      rethrow;
    }
  }

  Future<void> _recordDatabaseFailure({
    required String operation,
    required VerifiedAuditFileReference file,
    required Object error,
  }) async {
    if (_references case final AuditRecoveryMarkerWriter writer) {
      try {
        await writer.recordDatabaseFailure(
          operation: operation,
          file: file,
          error: error,
        );
      } catch (markerError) {
        throw AuditRecoveryMarkerFailure(
          databaseError: error,
          markerError: markerError,
          retainedFile: file,
        );
      }
    }
  }

  Future<void> _appendEvidenceRecoveryEvent(
    String sessionId,
    String relativePath,
    DateTime occurredAt,
  ) async {
    final existing =
        await (_database.select(_database.auditEvents)..where(
              (row) =>
                  row.sessionId.equals(sessionId) &
                  row.eventType.equals('evidence_recovery_required') &
                  row.detail.equals(relativePath),
            ))
            .getSingleOrNull();
    if (existing != null) return;
    await _appendEvent(
      sessionId,
      'evidence_recovery_required',
      occurredAt,
      detail: relativePath,
    );
  }

  Future<void> _appendEvent(
    String sessionId,
    String eventType,
    DateTime occurredAt, {
    String? detail,
  }) {
    return _database
        .into(_database.auditEvents)
        .insert(
          AuditEventsCompanion.insert(
            eventId: _newId('event'),
            sessionId: Value(sessionId),
            eventType: eventType,
            occurredAtUs: occurredAt.toUtc().microsecondsSinceEpoch,
            detail: Value(detail),
          ),
        );
  }

  String _newId(String prefix) {
    final value = _createId(prefix);
    if (value.trim().isEmpty) {
      throw StateError('ID generator returned an empty $prefix ID');
    }
    return value;
  }
}

final class _RecoveryEvidenceReference {
  const _RecoveryEvidenceReference({
    required this.sessionId,
    required this.file,
  });

  final String sessionId;
  final StoredAuditFile file;
}

String? _sessionIdFromRecoveryPath(String relativePath) {
  final segments = relativePath.split('/');
  final index = segments.indexOf('sessions');
  return index >= 0 && segments.length > index + 4 ? segments[index + 4] : null;
}

void _validateInferenceObjects(List<InferenceObject> objects) {
  for (final object in objects) {
    if (object.isUnknown) {
      if (object.skuName != 'Unknown' ||
          object.decisionPath != 'unknown_top3' ||
          object.candidates.length != 3 ||
          object.candidates.asMap().entries.any(
            (entry) => entry.value.rank != entry.key + 1,
          )) {
        throw StateError(
          'Unknown object requires exactly three ranked candidates',
        );
      }
    } else if (object.skuName == 'Unknown' ||
        !const {
          'repvit_direct',
          'dinov3_confirmed',
          'fusion_ranked',
        }.contains(object.decisionPath) ||
        object.candidates.isNotEmpty) {
      throw StateError('registered object identity is inconsistent');
    }
    final provenance = object.provenance;
    for (final field in const {
      'repvit_sha256',
      'repvit_manifest_sha256',
      'repvit_prototype_sha256',
      'dinov3_sha256',
      'dinov3_support_sha256',
      'calibration_sha256',
      'preprocess_sha256',
    }) {
      final value = provenance[field];
      if (value is! String) {
        throw StateError('object provenance is missing $field');
      }
      _requireSha256(value, 'provenance.$field');
    }
  }
}

int _canonicalDimension(double value, String name) {
  if (!value.isFinite || value <= 0 || value != value.roundToDouble()) {
    throw StateError('$name must be a positive integer in the canonical frame');
  }
  return value.toInt();
}

int _utcMicros(DateTime value, String name) {
  if (!value.isUtc) {
    throw ArgumentError.value(value, name, 'must be UTC');
  }
  return value.microsecondsSinceEpoch;
}

String _presentationState(InferencePresentationState state) => switch (state) {
  InferencePresentationState.normal => 'normal',
  InferencePresentationState.unknown => 'unknown',
  InferencePresentationState.needsRetake => 'needs_retake',
};

String? _retakeScope(RetakeScope? scope) => switch (scope) {
  null => null,
  RetakeScope.scan => 'scan',
  RetakeScope.object => 'object',
};

String? _retakeReason(RetakeInstruction? instruction) => switch (instruction) {
  null => null,
  RetakeInstruction.noBreadDetected => 'no_bread_detected',
  RetakeInstruction.separateBreads => 'separate_breads',
  RetakeInstruction.candidateEvidenceWeak => 'candidate_evidence_weak',
};

void _requireSha256(String value, String name) {
  if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(value)) {
    throw ArgumentError.value(value, name, 'must be a lowercase SHA-256');
  }
}

void _requireRelativePath(String value) {
  if (value.trim().isEmpty ||
      RegExp(r'^[A-Za-z]:[\\/]|^[/\\]').hasMatch(value) ||
      value.split(RegExp(r'[/\\]')).contains('..')) {
    throw ArgumentError.value(
      value,
      'relativePath',
      'must be a safe relative path',
    );
  }
}
