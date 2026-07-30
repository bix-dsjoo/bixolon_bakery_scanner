import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as path;

import '../checkout/checkout_models.dart';
import '../checkout/checkout_ports.dart';
import 'canonical_json_encoder.dart';
import 'sha256_file_hasher.dart';

final class StoredAuditFile {
  const StoredAuditFile({
    required this.relativePath,
    required this.byteSize,
    required this.sha256,
  });

  final String relativePath;
  final int byteSize;
  final String sha256;
}

/// Retains audit evidence only beneath the application-owned audit root.
final class AuditFileStore implements AuditDisplayPathResolver {
  AuditFileStore(Directory root, {Sha256FileHasher? hasher})
    : _root = Directory(path.normalize(path.absolute(root.path))),
      _hasher = hasher ?? Sha256FileHasher();

  static final _uuid = RegExp(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  );
  static final _canonicalFinalAuditPath = RegExp(
    '^sessions/[0-9]{4}/[0-9]{2}/[0-9]{2}/${_uuid.pattern.substring(1, _uuid.pattern.length - 1)}/'
    r'(?:attempt-[0-9]{3,}.(?:jpg|inference.json)|final-order.json)$',
  );

  final Directory _root;
  final Sha256FileHasher _hasher;
  String? _canonicalRoot;

  String get rootPath => _root.path;

  Future<StoredAuditFile> retainCapture({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required String sourcePath,
  }) async {
    final source = File(sourcePath);
    if (!await source.exists()) {
      throw ArgumentError.value(sourcePath, 'sourcePath', 'must name a file');
    }
    final relativePath = _attemptPath(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
      extension: 'jpg',
    );
    return _retainFromFile(source: source, relativePath: relativePath);
  }

  static String captureRelativePath({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
  }) {
    if (attemptNumber <= 0) {
      throw ArgumentError.value(
        attemptNumber,
        'attemptNumber',
        'must be positive',
      );
    }
    _requireSessionId(sessionId);
    _requireUtc(capturedAtUtc, 'capturedAtUtc');
    return path.posix.join(
      'sessions',
      capturedAtUtc.year.toString().padLeft(4, '0'),
      capturedAtUtc.month.toString().padLeft(2, '0'),
      capturedAtUtc.day.toString().padLeft(2, '0'),
      sessionId,
      'attempt-${attemptNumber.toString().padLeft(3, '0')}.jpg',
    );
  }

  Future<StoredAuditFile> retainInferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) async {
    final decoded = jsonDecode(receipt.canonicalJson);
    if (decoded is! Map ||
        canonicalJsonEncode(decoded) != receipt.canonicalJson) {
      throw StateError('inference receipt is not canonical JSON');
    }
    final bytes = utf8.encode(receipt.canonicalJson);
    final hash = sha256.convert(bytes).toString();
    if (hash != receipt.sha256) {
      throw StateError('inference receipt SHA-256 does not match its contents');
    }
    final relativePath = _attemptPath(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
      extension: 'inference.json',
    );
    return _retainBytes(bytes: bytes, sha256: hash, relativePath: relativePath);
  }

  Future<StoredAuditFile> retainFinalOrderReceipt(FinalOrderDraft order) async {
    _requireUtc(order.createdAt, 'order.createdAt');
    _requireSessionId(order.sessionId);
    final json = canonicalJsonEncode({
      'catalog_revision': {
        'created_at_us': order.catalogRevision.createdAt
            .toUtc()
            .microsecondsSinceEpoch,
        'revision_id': order.catalogRevision.revisionId,
        'sha256': order.catalogRevision.sha256,
      },
      'created_at_us': order.createdAt.microsecondsSinceEpoch,
      'lines': [
        for (final line in order.lines)
          {
            'product': {
              'category_id': line.product.categoryId,
              'display_name': line.product.displayName,
              'product_id': line.product.productId,
              'recognition_sku_id': line.product.recognitionSkuId,
              'unit_price_krw': line.product.unitPrice,
            },
            'quantity': line.quantity,
          },
      ],
      'receipt_version': 'checkout_final_order_receipt_v1',
      'session_id': order.sessionId,
      'total_price_krw': order.totalPrice,
    });
    final bytes = utf8.encode(json);
    final relativePath = _sessionPath(
      sessionId: order.sessionId,
      occurredAtUtc: order.createdAt,
      fileName: 'final-order.json',
    );
    return _retainBytes(
      bytes: bytes,
      sha256: sha256.convert(bytes).toString(),
      relativePath: relativePath,
    );
  }

  Future<StoredAuditFile> verifyExisting({
    required String relativePath,
    required String sha256,
    int? byteSize,
  }) async {
    _requireRelativePath(relativePath);
    _requireSha256(sha256);
    final file = File(resolve(relativePath));
    if (!await file.exists()) {
      throw StateError('audit file does not exist: $relativePath');
    }
    await _assertExistingFileInsideRoot(file);
    final hash = await _hasher.hashFile(file);
    if (hash.sha256 != sha256 ||
        (byteSize != null && hash.byteSize != byteSize)) {
      throw StateError('audit file does not match persisted metadata');
    }
    return StoredAuditFile(
      relativePath: relativePath,
      byteSize: hash.byteSize,
      sha256: hash.sha256,
    );
  }

  String resolve(String relativePath) {
    _requireRelativePath(relativePath);
    final resolved = path.normalize(
      path.joinAll([_root.path, ...relativePath.split('/')]),
    );
    if (!path.isWithin(_root.path, resolved)) {
      throw ArgumentError.value(
        relativePath,
        'relativePath',
        'escapes audit root',
      );
    }
    return resolved;
  }

  @override
  Future<String> resolveForDisplay(String relativePath) async {
    final file = File(resolve(relativePath));
    if (!await file.exists()) {
      throw StateError('audit display file does not exist: $relativePath');
    }
    await _assertExistingFileInsideRoot(file);
    return file.path;
  }

  /// Reports audit evidence requiring admin review; it never deletes evidence.
  ///
  /// [referencedRelativePaths] must be the durable database references known at
  /// startup. A canonical final file absent from both that set and a recovery
  /// marker is reported as an orphan.
  Future<List<String>> findRecoveryCandidates({
    Iterable<String> referencedRelativePaths = const [],
  }) async {
    if (!await _root.exists()) return const [];
    final referenced = {
      for (final value in referencedRelativePaths)
        if (_isCanonicalFinalAuditPath(value)) value,
    };
    final marked = await _markedRecoveryPaths();
    final sessions = Directory(path.join(_root.path, 'sessions'));
    if (!await sessions.exists()) return const [];
    final candidates = <String>[];
    await for (final entity in sessions.list(
      recursive: true,
      followLinks: false,
    )) {
      if (entity is! File) continue;
      final relativePath = _relativeFor(entity.path);
      if (relativePath.endsWith('.pending') &&
          _isCanonicalFinalAuditPath(
            relativePath.substring(0, relativePath.length - '.pending'.length),
          )) {
        candidates.add(relativePath);
      } else if (_isCanonicalFinalAuditPath(relativePath) &&
          !referenced.contains(relativePath) &&
          !marked.contains(relativePath)) {
        candidates.add(relativePath);
      }
    }
    candidates.sort();
    return candidates;
  }

  Future<Set<String>> _markedRecoveryPaths() async {
    final marker = File(path.join(_root.path, 'recovery', 'markers.jsonl'));
    if (!await marker.exists()) return const {};
    await _assertExistingFileInsideRoot(marker);
    final marked = <String>{};
    await for (final line
        in marker
            .openRead()
            .transform(utf8.decoder)
            .transform(const LineSplitter())) {
      try {
        final decoded = jsonDecode(line);
        if (decoded is! Map) continue;
        final file = decoded['file'];
        if (file is! Map) continue;
        final relativePath = file['relative_path'];
        if (relativePath is String &&
            _isCanonicalFinalAuditPath(relativePath)) {
          marked.add(relativePath);
        }
      } on FormatException {
        // A malformed marker is itself preserved for review and cannot make an
        // unrelated evidence file look referenced.
      }
    }
    return marked;
  }

  Future<void> recordDatabaseFailure({
    required String operation,
    required StoredAuditFile file,
    required Object error,
  }) async {
    final canonicalRoot = await _ensureRoot();
    final marker = File(path.join(canonicalRoot, 'recovery', 'markers.jsonl'));
    await marker.parent.create(recursive: true);
    await _assertDirectoryInsideRoot(marker.parent);
    final line = canonicalJsonEncode({
      'error_type': error.runtimeType.toString(),
      'file': {
        'byte_size': file.byteSize,
        'relative_path': file.relativePath,
        'sha256': file.sha256,
      },
      'operation': operation,
    });
    final output = await marker.open(mode: FileMode.append);
    try {
      await output.writeString('$line\n');
      await output.flush();
    } finally {
      await output.close();
    }
  }

  Future<StoredAuditFile> _retainFromFile({
    required File source,
    required String relativePath,
  }) async {
    final expected = await _hasher.hashFile(source);
    return _retain(
      relativePath: relativePath,
      expected: expected,
      writePending: (pending) =>
          _hasher.copyAndHash(source: source, destination: pending),
    );
  }

  Future<StoredAuditFile> _retainBytes({
    required List<int> bytes,
    required String sha256,
    required String relativePath,
  }) {
    return _retain(
      relativePath: relativePath,
      expected: FileHash(byteSize: bytes.length, sha256: sha256),
      writePending: (pending) =>
          _hasher.writeAndHash(bytes: bytes, destination: pending),
    );
  }

  Future<StoredAuditFile> _retain({
    required String relativePath,
    required FileHash expected,
    required Future<FileHash> Function(File pending) writePending,
  }) async {
    if (expected.byteSize <= 0) {
      throw StateError('audit evidence must not be empty');
    }
    final finalFile = File(resolve(relativePath));
    await finalFile.parent.create(recursive: true);
    await _assertDirectoryInsideRoot(finalFile.parent);
    if (await finalFile.exists()) {
      return _verifyMatching(finalFile, relativePath, expected);
    }
    final pending = File('${finalFile.path}.pending');
    if (await pending.exists()) {
      throw StateError(
        'pending audit evidence requires recovery review: $relativePath',
      );
    }
    final written = await writePending(pending);
    if (!_sameHash(written, expected)) {
      throw StateError(
        'pending audit evidence does not match its expected hash',
      );
    }
    final pendingHash = await _hasher.hashFile(pending);
    if (!_sameHash(pendingHash, expected)) {
      throw StateError('pending audit evidence failed verification');
    }
    try {
      await pending.rename(finalFile.path);
    } on FileSystemException {
      if (await finalFile.exists()) {
        return _verifyMatching(finalFile, relativePath, expected);
      }
      rethrow;
    }
    return _verifyMatching(finalFile, relativePath, expected);
  }

  Future<StoredAuditFile> _verifyMatching(
    File file,
    String relativePath,
    FileHash expected,
  ) async {
    await _assertExistingFileInsideRoot(file);
    final actual = await _hasher.hashFile(file);
    if (!_sameHash(actual, expected)) {
      throw StateError('existing audit evidence differs: $relativePath');
    }
    return StoredAuditFile(
      relativePath: relativePath,
      byteSize: actual.byteSize,
      sha256: actual.sha256,
    );
  }

  Future<String> _ensureRoot() async {
    await _root.create(recursive: true);
    final canonicalRoot = await _root.resolveSymbolicLinks();
    _canonicalRoot ??= path.normalize(canonicalRoot);
    return _canonicalRoot!;
  }

  Future<void> _assertDirectoryInsideRoot(Directory directory) async {
    final canonicalRoot = await _ensureRoot();
    final canonicalDirectory = path.normalize(
      await directory.resolveSymbolicLinks(),
    );
    if (canonicalDirectory != canonicalRoot &&
        !path.isWithin(canonicalRoot, canonicalDirectory)) {
      throw StateError('audit directory escapes its root');
    }
  }

  Future<void> _assertExistingFileInsideRoot(File file) async {
    final canonicalRoot = await _ensureRoot();
    final canonicalFile = path.normalize(await file.resolveSymbolicLinks());
    if (!path.isWithin(canonicalRoot, canonicalFile)) {
      throw StateError('audit file escapes its root');
    }
  }

  String _attemptPath({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required String extension,
  }) {
    if (extension == 'jpg') {
      return captureRelativePath(
        sessionId: sessionId,
        attemptNumber: attemptNumber,
        capturedAtUtc: capturedAtUtc,
      );
    }
    if (attemptNumber <= 0) {
      throw ArgumentError.value(
        attemptNumber,
        'attemptNumber',
        'must be positive',
      );
    }
    return _sessionPath(
      sessionId: sessionId,
      occurredAtUtc: capturedAtUtc,
      fileName:
          'attempt-${attemptNumber.toString().padLeft(3, '0')}.$extension',
    );
  }

  String _sessionPath({
    required String sessionId,
    required DateTime occurredAtUtc,
    required String fileName,
  }) {
    _requireSessionId(sessionId);
    _requireUtc(occurredAtUtc, 'occurredAtUtc');
    return path.posix.join(
      'sessions',
      occurredAtUtc.year.toString().padLeft(4, '0'),
      occurredAtUtc.month.toString().padLeft(2, '0'),
      occurredAtUtc.day.toString().padLeft(2, '0'),
      sessionId,
      fileName,
    );
  }

  String _relativeFor(String absolutePath) {
    final relative = path.relative(absolutePath, from: _root.path);
    return path.posix.joinAll(relative.split(path.separator));
  }

  static bool _sameHash(FileHash left, FileHash right) =>
      left.byteSize == right.byteSize && left.sha256 == right.sha256;

  static bool _isCanonicalFinalAuditPath(String value) =>
      _canonicalFinalAuditPath.hasMatch(value);

  static void _requireSessionId(String sessionId) {
    if (!_uuid.hasMatch(sessionId)) {
      throw ArgumentError.value(
        sessionId,
        'sessionId',
        'must be a lowercase UUID',
      );
    }
  }

  static void _requireUtc(DateTime value, String name) {
    if (!value.isUtc) {
      throw ArgumentError.value(value, name, 'must be UTC');
    }
  }

  static void _requireSha256(String value) {
    if (!RegExp(r'^[0-9a-f]{64}$').hasMatch(value)) {
      throw ArgumentError.value(value, 'sha256', 'must be a lowercase SHA-256');
    }
  }

  static void _requireRelativePath(String value) {
    if (value.isEmpty ||
        value.contains('\\') ||
        value.startsWith('/') ||
        value
            .split('/')
            .any((part) => part.isEmpty || part == '.' || part == '..')) {
      throw ArgumentError.value(
        value,
        'relativePath',
        'must be a safe POSIX relative path',
      );
    }
  }
}

final class AuditFileCheckoutEvidenceStore implements CheckoutEvidenceStore {
  const AuditFileCheckoutEvidenceStore(this._files);

  final AuditFileStore _files;

  @override
  Future<CapturedAuditFile> retainCapture({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required String sourcePath,
  }) async {
    final stored = await _files.retainCapture(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
      sourcePath: sourcePath,
    );
    return CapturedAuditFile(
      fileId: stored.relativePath,
      path: stored.relativePath,
      sha256: stored.sha256,
    );
  }

  @override
  Future<void> retainInferenceReceipt({
    required String sessionId,
    required int attemptNumber,
    required DateTime capturedAtUtc,
    required ImmutableJsonReceipt receipt,
  }) async {
    await _files.retainInferenceReceipt(
      sessionId: sessionId,
      attemptNumber: attemptNumber,
      capturedAtUtc: capturedAtUtc,
      receipt: receipt,
    );
  }
}
