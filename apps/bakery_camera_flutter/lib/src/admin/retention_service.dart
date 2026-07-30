import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';
import 'package:path/path.dart' as path;
import 'package:uuid/uuid.dart';

import '../persistence/app_database.dart';

final class RetentionEvidenceFile {
  const RetentionEvidenceFile({
    required this.attemptId,
    required this.sessionId,
    required this.relativePath,
    required this.byteSize,
    required this.sha256,
  });

  final String attemptId;
  final String sessionId;
  final String relativePath;
  final int byteSize;
  final String sha256;

  String get identity =>
      '$attemptId\u0000$relativePath\u0000$byteSize\u0000$sha256';
}

final class RetentionPreview {
  RetentionPreview({
    required this.previewId,
    required this.cutoff,
    required Iterable<RetentionEvidenceFile> files,
  }) : files = List.unmodifiable(files),
       affectedSessionIds = List.unmodifiable(
         files.map((file) => file.sessionId).toSet().toList()..sort(),
       ),
       totalByteSize = files.fold(0, (sum, file) => sum + file.byteSize);

  final String previewId;
  final DateTime cutoff;
  final List<RetentionEvidenceFile> files;
  final List<String> affectedSessionIds;
  final int totalByteSize;
}

final class RetentionExecutionResult {
  const RetentionExecutionResult({
    required this.filesRemoved,
    required this.bytesRemoved,
    required this.quarantineCleanupPending,
  });

  final int filesRemoved;
  final int bytesRemoved;
  final bool quarantineCleanupPending;
}

/// A two-phase, image-only retention boundary.
///
/// Immutable database receipts, payments, orders, hashes, and annotations are
/// deliberately outside this service. It removes only verified capture files
/// after a preview is shown and the exact same evidence is revalidated.
final class RetentionService {
  factory RetentionService({
    required BakeryDatabase database,
    required Directory evidenceRoot,
    String Function()? createId,
    DateTime Function()? now,
    bool Function()? isSafeToRun,
  }) => RetentionService._(
    database,
    evidenceRoot,
    createId ?? const Uuid().v4,
    now ?? DateTime.now,
    isSafeToRun ?? (() => true),
  );

  RetentionService._(
    this._database,
    this._evidenceRoot,
    this._createId,
    this._now,
    this._isSafeToRun,
  );

  final BakeryDatabase _database;
  final Directory _evidenceRoot;
  final String Function() _createId;
  final DateTime Function() _now;
  final bool Function() _isSafeToRun;
  final Map<String, RetentionPreview> _previews = {};

  Future<RetentionPreview> preview(DateTime cutoff) async {
    _requireSafeBoundary();
    await _verifiedRoot();
    final previewId = _safeId(_createId());
    if (_previews.containsKey(previewId)) {
      throw StateError('retention preview ID must be unique');
    }
    final files = await _eligibleFiles(cutoff.toUtc());
    for (final file in files) {
      await _verifyExactFile(file);
    }
    final result = RetentionPreview(
      previewId: previewId,
      cutoff: cutoff.toUtc(),
      files: files,
    );
    _previews[previewId] = result;
    return result;
  }

  Future<RetentionExecutionResult> execute(String previewId) async {
    _requireSafeBoundary();
    final preview = _previews[previewId];
    if (preview == null) {
      throw StateError('retention preview is unavailable or already executed');
    }
    final root = await _verifiedRoot();
    final actual = await _eligibleFiles(preview.cutoff);
    if (!_sameEvidence(preview.files, actual)) {
      throw StateError('retention preview changed; create a new preview');
    }
    for (final file in actual) {
      await _verifyExactFile(file, root: root);
    }
    if (actual.isEmpty) {
      _previews.remove(previewId);
      return const RetentionExecutionResult(
        filesRemoved: 0,
        bytesRemoved: 0,
        quarantineCleanupPending: false,
      );
    }

    final now = _now().toUtc();
    await _appendAudit(
      eventId: '$previewId/retention-pending',
      eventType: 'retention_pending',
      occurredAt: now,
      detail: _detail(preview),
    );

    final quarantine = await _quarantineDirectory(root, previewId);
    final moved = <RetentionEvidenceFile>[];
    try {
      for (final file in actual) {
        final source = await _verifyExactFile(file, root: root);
        final destination = await _quarantineTarget(quarantine, file);
        await destination.parent.create(recursive: true);
        await source.rename(destination.path);
        moved.add(file);
      }
      await _database.transaction(() async {
        await _database.batch((batch) {
          batch.insertAll(
            _database.retentionEvents,
            actual
                .map(
                  (file) => RetentionEventsCompanion.insert(
                    retentionEventId: '$previewId/${file.attemptId}',
                    attemptId: file.attemptId,
                    relativePath: file.relativePath,
                    originalByteSize: file.byteSize,
                    originalSha256: file.sha256,
                    prunedAtUs: now.microsecondsSinceEpoch,
                    reason: 'configured_evidence_retention',
                  ),
                )
                .toList(growable: false),
          );
        });
        await _database
            .into(_database.auditEvents)
            .insert(
              AuditEventsCompanion.insert(
                eventId: '$previewId/retention-executed',
                eventType: 'retention_executed',
                occurredAtUs: now.microsecondsSinceEpoch,
                detail: Value(_detail(preview)),
              ),
            );
      });
    } catch (error) {
      await _appendPartialFailure(preview, moved, error);
      rethrow;
    }

    var cleanupPending = false;
    try {
      if (await quarantine.exists()) await quarantine.delete(recursive: true);
    } catch (error) {
      cleanupPending = true;
      await _appendAudit(
        eventId: '$previewId/retention-quarantine-cleanup-failed',
        eventType: 'retention_partial_failure',
        occurredAt: _now().toUtc(),
        detail: jsonEncode({
          'preview_id': preview.previewId,
          'quarantine_path': path.relative(quarantine.path, from: root),
          'stage': 'quarantine_cleanup',
          'error': error.toString(),
        }),
      );
    }
    _previews.remove(previewId);
    return RetentionExecutionResult(
      filesRemoved: actual.length,
      bytesRemoved: actual.fold(0, (sum, file) => sum + file.byteSize),
      quarantineCleanupPending: cleanupPending,
    );
  }

  void _requireSafeBoundary() {
    if (!_isSafeToRun()) {
      throw StateError(
        'retention requires idle customer flow or administrator mode',
      );
    }
  }

  Future<String> _verifiedRoot() async {
    if (!await _evidenceRoot.exists()) {
      throw StateError('retention evidence root does not exist');
    }
    final root = await _evidenceRoot.resolveSymbolicLinks();
    if (!path.isAbsolute(root)) {
      throw StateError('retention evidence root must be absolute');
    }
    return path.normalize(root);
  }

  Future<List<RetentionEvidenceFile>> _eligibleFiles(DateTime cutoff) async {
    final attempts =
        await (_database.select(_database.scanAttempts)
              ..where(
                (row) => row.capturedAtUs.isSmallerOrEqualValue(
                  cutoff.microsecondsSinceEpoch,
                ),
              )
              ..orderBy([(row) => OrderingTerm.asc(row.attemptId)]))
            .get();
    final sessions = {
      for (final row
          in await _database.select(_database.checkoutSessions).get())
        row.sessionId: row,
    };
    final pruned = <String>{
      for (final row in await _database.select(_database.retentionEvents).get())
        '${row.attemptId}\u0000${row.relativePath}\u0000${row.originalByteSize}\u0000${row.originalSha256}',
    };
    final result = <RetentionEvidenceFile>[];
    for (final attempt in attempts) {
      final session = sessions[attempt.sessionId];
      if (session == null) {
        throw StateError('attempt has no checkout session');
      }
      final file = RetentionEvidenceFile(
        attemptId: attempt.attemptId,
        sessionId: session.sessionId,
        relativePath: attempt.imageRelativePath,
        byteSize: attempt.imageByteSize,
        sha256: attempt.imageSha256,
      );
      if (!pruned.contains(file.identity)) result.add(file);
    }
    return List.unmodifiable(result);
  }

  Future<File> _verifyExactFile(
    RetentionEvidenceFile file, {
    String? root,
  }) async {
    final verifiedRoot = root ?? await _verifiedRoot();
    final candidate = await _resolveContained(verifiedRoot, file.relativePath);
    if (!await candidate.exists()) {
      throw StateError('retention evidence is missing: ${file.relativePath}');
    }
    final resolved = path.normalize(await candidate.resolveSymbolicLinks());
    if (!path.isWithin(verifiedRoot, resolved)) {
      throw StateError('retention evidence escapes configured root');
    }
    final bytes = await candidate.readAsBytes();
    if (bytes.length != file.byteSize ||
        sha256.convert(bytes).toString() != file.sha256) {
      throw StateError('retention evidence hash or size changed');
    }
    return candidate;
  }

  Future<File> _resolveContained(String root, String relativePath) async {
    if (relativePath.trim().isEmpty ||
        path.isAbsolute(relativePath) ||
        relativePath.contains('\\')) {
      throw StateError('retention evidence path is not a safe relative path');
    }
    final resolved = path.normalize(
      path.joinAll([root, ...relativePath.split('/')]),
    );
    if (!path.isWithin(root, resolved)) {
      throw StateError('retention evidence path escapes configured root');
    }
    return File(resolved);
  }

  Future<Directory> _quarantineDirectory(String root, String previewId) async {
    final directory = Directory(
      path.normalize(path.join(root, 'retention-quarantine', previewId)),
    );
    if (!path.isWithin(root, directory.path)) {
      throw StateError('retention quarantine escapes configured root');
    }
    return directory;
  }

  Future<File> _quarantineTarget(
    Directory quarantine,
    RetentionEvidenceFile file,
  ) async {
    final result = path.normalize(
      path.joinAll([quarantine.path, ...file.relativePath.split('/')]),
    );
    if (!path.isWithin(quarantine.path, result)) {
      throw StateError('retention quarantine target escapes containment');
    }
    return File(result);
  }

  static bool _sameEvidence(
    List<RetentionEvidenceFile> expected,
    List<RetentionEvidenceFile> actual,
  ) {
    final expectedIds = expected.map((file) => file.identity).toSet();
    final actualIds = actual.map((file) => file.identity).toSet();
    return expectedIds.length == actualIds.length &&
        expectedIds.every(actualIds.contains);
  }

  static String _safeId(String value) {
    final trimmed = value.trim();
    if (!RegExp(r'^[a-zA-Z0-9_-]{1,128}$').hasMatch(trimmed)) {
      throw ArgumentError.value(
        value,
        'previewId',
        'must be a safe identifier',
      );
    }
    return trimmed;
  }

  String _detail(RetentionPreview preview) => jsonEncode({
    'affected_session_ids': preview.affectedSessionIds,
    'cutoff_utc': preview.cutoff.toIso8601String(),
    'file_count': preview.files.length,
    'preview_id': preview.previewId,
    'preserved_records': [
      'checkout_sessions',
      'inference_receipts',
      'customer_resolutions',
      'final_orders',
      'simulated_payments',
      'admin_review_annotations',
      'file_sha256',
      'file_byte_size',
    ],
    'total_bytes': preview.totalByteSize,
  });

  Future<void> _appendAudit({
    required String eventId,
    required String eventType,
    required DateTime occurredAt,
    required String detail,
  }) => _database
      .into(_database.auditEvents)
      .insert(
        AuditEventsCompanion.insert(
          eventId: eventId,
          eventType: eventType,
          occurredAtUs: occurredAt.microsecondsSinceEpoch,
          detail: Value(detail),
        ),
      );

  Future<void> _appendPartialFailure(
    RetentionPreview preview,
    List<RetentionEvidenceFile> moved,
    Object error,
  ) async {
    try {
      await _appendAudit(
        eventId: '${preview.previewId}/retention-partial-failure',
        eventType: 'retention_partial_failure',
        occurredAt: _now().toUtc(),
        detail: jsonEncode({
          'error': error.toString(),
          'moved_attempt_ids': moved.map((file) => file.attemptId).toList(),
          'preview_id': preview.previewId,
          'stage': 'move_or_metadata_commit',
        }),
      );
    } catch (_) {
      // The pending record remains the recovery signal if recording the
      // secondary failure itself is unavailable.
    }
  }
}
