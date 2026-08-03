import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as path;

/// Immutable metadata for approved sale-product photography.
///
/// This is deliberately separate from checkout captures and inference
/// evidence. Its relative path is always rooted beneath `catalog-media`.
final class CatalogPhoto {
  const CatalogPhoto({
    required this.relativePath,
    required this.byteSize,
    required this.sha256,
    required this.mediaType,
    required this.provenanceNote,
  });

  final String relativePath;
  final int byteSize;
  final String sha256;
  final String mediaType;
  final String provenanceNote;
}

/// An operator-approved local source record for catalog photography.
///
/// This is intentionally not an arbitrary filename or free-form assertion.
/// The immutable record is stored with the copied content hash so a later
/// reviewer can establish which local photo-record was approved. It does not
/// accept checkout, inference, generated, training, or model artifacts as a
/// source kind.
final class CatalogPhotoProvenance {
  const CatalogPhotoProvenance.approvedLocalImport({
    required this.sourceReference,
  });

  static const _kind = 'operator_approved_local_product_photo';

  final String sourceReference;

  String serialize() {
    _validateSourceReference(sourceReference);
    return jsonEncode({
      'kind': _kind,
      'source_reference': sourceReference.trim(),
    });
  }

  static CatalogPhotoProvenance parse(String serialized) {
    Object? decoded;
    try {
      decoded = jsonDecode(serialized);
    } on FormatException {
      throw const FormatException('catalog photo provenance is invalid');
    }
    if (decoded is! Map<String, Object?> ||
        decoded.length != 2 ||
        decoded['kind'] != _kind ||
        decoded['source_reference'] is! String) {
      throw const FormatException('catalog photo provenance is invalid');
    }
    final provenance = CatalogPhotoProvenance.approvedLocalImport(
      sourceReference: decoded['source_reference']! as String,
    );
    _validateSourceReference(provenance.sourceReference);
    if (serialized != provenance.serialize()) {
      throw const FormatException('catalog photo provenance is not canonical');
    }
    return provenance;
  }

  static void _validateSourceReference(String value) {
    final normalized = value.trim();
    if (normalized.length < 3 ||
        normalized.length > 128 ||
        normalized.contains(RegExp(r'[\\/]')) ||
        normalized.contains('..')) {
      throw const FormatException(
        'catalog photo source reference must be an approved local record id',
      );
    }
  }
}

/// Imports only verified, locally chosen JPEG/PNG sale-product photographs.
///
/// The caller supplies application data, never an arbitrary destination. The
/// store copies content-addressed bytes after decoding them so extension-only
/// and corrupt image inputs do not enter the catalog.
final class CatalogPhotoStore {
  CatalogPhotoStore(
    this.applicationDataDirectory, {
    this.maximumByteSize = 8 * 1024 * 1024,
    Iterable<String> forbiddenArtifactHashes = const [],
  }) : _forbiddenArtifactHashes = Set.unmodifiable(forbiddenArtifactHashes),
       assert(maximumByteSize > 0);

  final Directory applicationDataDirectory;
  final int maximumByteSize;
  final Set<String> _forbiddenArtifactHashes;

  Future<CatalogPhoto> importFile(
    File source, {
    required CatalogPhotoProvenance provenance,
    Iterable<String> forbiddenArtifactHashes = const [],
  }) async {
    final normalizedNote = provenance.serialize();
    final sourcePath = await _resolveAndValidateSource(source);
    final extension = path.extension(sourcePath).toLowerCase();
    if (extension != '.png' && extension != '.jpg' && extension != '.jpeg') {
      throw FormatException('catalog photographs must be JPEG or PNG');
    }
    final sourceFile = File(sourcePath);
    final size = await sourceFile.length();
    if (size <= 0 || size > maximumByteSize) {
      throw ArgumentError.value(
        size,
        'source',
        'exceeds the catalog photo size limit',
      );
    }
    final bytes = await sourceFile.readAsBytes();
    final mediaType = _mediaTypeFor(bytes, extension);
    await _verifyDecodable(bytes);
    final digest = sha256.convert(bytes).toString();
    if (_forbiddenArtifactHashes.contains(digest) ||
        forbiddenArtifactHashes.contains(digest)) {
      throw ArgumentError.value(
        source.path,
        'source',
        'matches a protected operational or generated artifact',
      );
    }
    final normalizedExtension = mediaType == 'image/png' ? '.png' : '.jpg';
    // Preserve POSIX separators in database provenance on every host.
    final relativePath = path.posix.join(
      'catalog-media',
      '$digest$normalizedExtension',
    );
    final destination = File(
      path.join(applicationDataDirectory.path, relativePath),
    );
    await destination.parent.create(recursive: true);
    if (await destination.exists()) {
      final existing = await destination.readAsBytes();
      if (existing.length != bytes.length ||
          sha256.convert(existing).toString() != digest) {
        throw StateError('catalog photo destination hash mismatch');
      }
    } else {
      await destination.writeAsBytes(bytes, flush: true);
      final copied = await destination.readAsBytes();
      if (copied.length != bytes.length ||
          sha256.convert(copied).toString() != digest) {
        throw StateError('catalog photo copy hash mismatch');
      }
    }
    return CatalogPhoto(
      relativePath: relativePath,
      byteSize: bytes.length,
      sha256: digest,
      mediaType: mediaType,
      provenanceNote: normalizedNote,
    );
  }

  /// Returns the approved image only after rechecking its persisted identity.
  /// A missing or changed file is an integrity failure, not a substitute image.
  Future<File> resolveVerified(CatalogPhoto photo) async {
    final expectedExtension = photo.mediaType == 'image/png' ? '.png' : '.jpg';
    final expectedPath = path.posix.join(
      'catalog-media',
      '${photo.sha256}$expectedExtension',
    );
    if (photo.relativePath != expectedPath ||
        photo.byteSize <= 0 ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(photo.sha256)) {
      throw StateError('catalog photo metadata is invalid');
    }
    try {
      CatalogPhotoProvenance.parse(photo.provenanceNote);
    } on FormatException {
      throw StateError('catalog photo provenance is invalid');
    }
    final file = File(
      path.join(applicationDataDirectory.path, photo.relativePath),
    );
    if (!await file.exists()) {
      throw StateError('catalog photo does not exist');
    }
    final bytes = await file.readAsBytes();
    if (bytes.length != photo.byteSize ||
        sha256.convert(bytes).toString() != photo.sha256) {
      throw StateError('catalog photo hash mismatch');
    }
    try {
      final observedMediaType = _mediaTypeFor(bytes, expectedExtension);
      if (observedMediaType != photo.mediaType) {
        throw StateError('catalog photo media type mismatch');
      }
      await _verifyDecodable(bytes);
    } on FormatException {
      throw StateError('catalog photo media type mismatch');
    }
    return file;
  }

  Future<String> _resolveAndValidateSource(File source) async {
    if (!await source.exists()) {
      throw ArgumentError.value(source.path, 'source', 'does not exist');
    }
    final resolved = path.normalize(await source.resolveSymbolicLinks());
    final loweredSegments = path
        .split(resolved)
        .map((segment) => segment.toLowerCase())
        .toSet();
    const prohibited = {
      'imagegen',
      'generated',
      'checkout',
      'sessions',
      'inference',
      'evidence',
      'training',
      'train',
      'evaluation',
      'eval',
      'models',
      'prototype-banks',
      'support-banks',
    };
    if (loweredSegments.any(prohibited.contains)) {
      throw ArgumentError.value(
        source.path,
        'source',
        'is not permitted catalog photography',
      );
    }
    return resolved;
  }

  String _mediaTypeFor(Uint8List bytes, String extension) {
    final png =
        bytes.length >= 8 &&
        bytes[0] == 0x89 &&
        bytes[1] == 0x50 &&
        bytes[2] == 0x4e &&
        bytes[3] == 0x47 &&
        bytes[4] == 0x0d &&
        bytes[5] == 0x0a &&
        bytes[6] == 0x1a &&
        bytes[7] == 0x0a;
    final jpeg =
        bytes.length >= 3 &&
        bytes[0] == 0xff &&
        bytes[1] == 0xd8 &&
        bytes[2] == 0xff;
    if (png && extension == '.png') {
      return 'image/png';
    }
    if (jpeg && (extension == '.jpg' || extension == '.jpeg')) {
      return 'image/jpeg';
    }
    throw const FormatException(
      'catalog photo bytes do not match JPEG/PNG type',
    );
  }

  Future<void> _verifyDecodable(Uint8List bytes) async {
    ui.Codec? codec;
    ui.Image? image;
    try {
      codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      image = frame.image;
      if (image.width <= 0 || image.height <= 0) {
        throw const FormatException('catalog photo has invalid dimensions');
      }
    } on FormatException {
      rethrow;
    } catch (_) {
      throw const FormatException('catalog photo cannot be decoded');
    } finally {
      image?.dispose();
      codec?.dispose();
    }
  }
}
