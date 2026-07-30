import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as path;

const _requiredUses = {'manual_cart_entry', 'payment_complete'};
const _requiredProhibitions = {
  'product_photo',
  'camera_evidence',
  'model_input',
  'training_data',
  'evaluation_data',
};
const _pngSignature = <int>[137, 80, 78, 71, 13, 10, 26, 10];
const _expectedAssetIds = {
  'manual_cart_entry': 'manual-cart-entry',
  'payment_complete': 'payment-complete',
};
const _requiredAlphaValidation = {
  'decoded_rgba': true,
  'transparent_corners': true,
  'transparent_edge_pixels': true,
};

Future<void> main() async {
  final errors = await verifyUiAssets();
  if (errors.isEmpty) {
    stdout.writeln('Verified exactly two audited UI illustrations.');
    return;
  }
  for (final error in errors) {
    stderr.writeln('UI asset verification: $error');
  }
  exitCode = 1;
}

/// Validates the only generated customer illustrations permitted in this app.
///
/// The tool deliberately rejects any unmanifested PNG in the illustration
/// directory, so generated art cannot be repurposed as product, evidence, or
/// model material by merely adding a file.
Future<List<String>> verifyUiAssets({Directory? appRoot}) async {
  final root = appRoot ?? Directory.current;
  final errors = <String>[];
  final manifestFile = File(
    path.join(root.path, 'assets', 'asset_manifest.json'),
  );
  if (!await manifestFile.exists()) {
    return ['missing assets/asset_manifest.json'];
  }

  Map<String, dynamic> manifest;
  try {
    manifest =
        jsonDecode(await manifestFile.readAsString()) as Map<String, dynamic>;
  } on Object catch (error) {
    return ['invalid asset manifest: $error'];
  }
  if (manifest['schema_version'] != 1) {
    errors.add('schema_version must be 1');
  }
  final rawEntries = manifest['generated_ui_illustrations'];
  if (rawEntries is! List || rawEntries.length != 2) {
    return [
      ...errors,
      'generated_ui_illustrations must contain exactly two entries',
    ];
  }

  final manifestPaths = <String>{};
  final uses = <String>{};
  for (final rawEntry in rawEntries) {
    if (rawEntry is! Map) {
      errors.add('each generated_ui_illustrations entry must be an object');
      continue;
    }
    final entry = Map<String, dynamic>.from(rawEntry);
    final label = entry['allowed_use'] ?? 'unknown';
    if (entry['kind'] != 'generated_ui_illustration') {
      errors.add('$label is not a generated_ui_illustration');
    }
    final allowedUse = entry['allowed_use'];
    if (allowedUse is! String ||
        !_requiredUses.contains(allowedUse) ||
        !uses.add(allowedUse)) {
      errors.add('allowed_use must be one unique approved value: $label');
    }
    final assetPath = entry['path'];
    if (assetPath is! String ||
        !assetPath.startsWith('assets/illustrations/') ||
        !manifestPaths.add(assetPath)) {
      errors.add('$label has an invalid or duplicate asset path');
      continue;
    }
    if (entry['format'] != 'png' || entry['transparent_background'] != true) {
      errors.add('$label must declare a transparent PNG');
    }
    if (entry['prompt'] is! String ||
        (entry['prompt'] as String).trim().isEmpty) {
      errors.add('$label is missing its approved prompt');
    }
    if (entry['asset_id'] != _expectedAssetIds[allowedUse]) {
      errors.add('$label must record its approved asset_id');
    }
    if (entry['screen'] is! String ||
        (entry['screen'] as String).trim().isEmpty) {
      errors.add('$label is missing its screen provenance');
    }
    if (entry['purpose'] is! String ||
        (entry['purpose'] as String).trim().isEmpty) {
      errors.add('$label is missing its purpose provenance');
    }
    if (entry['tool_provenance'] is! String ||
        (entry['tool_provenance'] as String).trim().isEmpty) {
      errors.add('$label is missing generation tool provenance');
    }
    if (entry['generator_path'] is! String ||
        (entry['generator_path'] as String).trim().isEmpty) {
      errors.add('$label is missing generator path provenance');
    }
    final generatedAt = entry['generated_at_utc'];
    if (generatedAt is! String ||
        DateTime.tryParse(generatedAt)?.isUtc != true) {
      errors.add('$label must record a UTC generation timestamp');
    }
    final prohibitedUses = entry['prohibited_uses'];
    if (prohibitedUses is! List ||
        !_requiredProhibitions.every(prohibitedUses.contains)) {
      errors.add('$label is missing a required prohibited use');
    }
    final alphaValidation = entry['alpha_validation'];
    if (alphaValidation is! Map ||
        !_requiredAlphaValidation.entries.every(
          (value) => alphaValidation[value.key] == value.value,
        )) {
      errors.add('$label is missing required alpha validation provenance');
    }
    if (entry['review_state'] != 'approved') {
      errors.add('$label must have approved visual review state');
    }
    if (entry['not_product_or_inference_evidence'] != true) {
      errors.add('$label must be classified as non-product, non-evidence UI');
    }

    final file = File(path.join(root.path, assetPath));
    if (!await file.exists()) {
      errors.add('$label asset file is missing');
      continue;
    }
    final bytes = await file.readAsBytes();
    if (entry['byte_size'] != bytes.length) {
      errors.add('$label byte_size does not match the file');
    }
    if (entry['sha256'] != sha256.convert(bytes).toString()) {
      errors.add('$label SHA-256 does not match the file');
    }
    final png = _decodeRgbaPng(bytes);
    if (png == null) {
      errors.add('$label is not an RGBA PNG with an alpha channel');
    } else if (entry['width'] != png.width || entry['height'] != png.height) {
      errors.add('$label declared dimensions do not match the PNG');
    } else {
      if (!png.hasTransparentPixel) {
        errors.add('$label must contain genuinely transparent alpha pixels');
      }
      if (!png.hasTransparentCorners) {
        errors.add('$label must retain transparent alpha corners');
      }
      if (!png.hasTransparentEdgePixels) {
        errors.add('$label must retain transparent alpha edge pixels');
      }
    }
  }

  if (uses.length != _requiredUses.length || !uses.containsAll(_requiredUses)) {
    errors.add('both approved use locations must be represented exactly once');
  }
  final expectedPaths = {
    'assets/illustrations/manual_cart_entry.png',
    'assets/illustrations/payment_complete.png',
  };
  if (manifestPaths.length != expectedPaths.length ||
      !manifestPaths.containsAll(expectedPaths)) {
    errors.add('manifest paths must be the two approved illustration files');
  }

  final illustrations = Directory(
    path.join(root.path, 'assets', 'illustrations'),
  );
  if (!await illustrations.exists()) {
    errors.add('assets/illustrations directory is missing');
  } else {
    await for (final entity in illustrations.list(
      followLinks: false,
      recursive: true,
    )) {
      if (entity is File &&
          path.extension(entity.path).toLowerCase() == '.png') {
        final relativePath = path
            .relative(entity.path, from: root.path)
            .replaceAll('\\', '/');
        if (!manifestPaths.contains(relativePath)) {
          errors.add('unlisted generated illustration: $relativePath');
        }
      }
    }
  }
  return errors;
}

_DecodedRgbaPng? _decodeRgbaPng(Uint8List bytes) {
  if (bytes.length < 33) return null;
  for (var index = 0; index < _pngSignature.length; index++) {
    if (bytes[index] != _pngSignature[index]) return null;
  }

  var offset = _pngSignature.length;
  int? width;
  int? height;
  final compressed = BytesBuilder(copy: false);
  var sawHeader = false;
  var sawEnd = false;
  while (offset + 12 <= bytes.length) {
    final length = _readUint32(bytes, offset);
    final dataOffset = offset + 8;
    final nextOffset = dataOffset + length + 4;
    if (nextOffset > bytes.length) return null;
    final type = String.fromCharCodes(bytes.sublist(offset + 4, dataOffset));
    final data = bytes.sublist(dataOffset, dataOffset + length);
    switch (type) {
      case 'IHDR':
        if (sawHeader || length != 13) return null;
        width = _readUint32(data, 0);
        height = _readUint32(data, 4);
        if (width <= 0 ||
            height <= 0 ||
            data[8] != 8 ||
            data[9] != 6 ||
            data[10] != 0 ||
            data[11] != 0 ||
            data[12] != 0) {
          return null;
        }
        sawHeader = true;
      case 'IDAT':
        if (!sawHeader || sawEnd) return null;
        compressed.add(data);
      case 'IEND':
        if (!sawHeader || length != 0) return null;
        sawEnd = true;
    }
    offset = nextOffset;
  }
  if (!sawHeader || !sawEnd || width == null || height == null) return null;
  const bytesPerPixel = 4;
  if (width > 32768 || height > 32768 || width * height > 100000000) {
    return null;
  }
  final rowLength = width * bytesPerPixel;
  Uint8List inflated;
  try {
    inflated = Uint8List.fromList(ZLibDecoder().convert(compressed.toBytes()));
  } on Object {
    return null;
  }
  if (inflated.length != height * (rowLength + 1)) return null;

  var hasTransparentPixel = false;
  var hasTransparentEdgePixels = false;
  final cornerAlpha = <int>[];
  var sourceOffset = 0;
  var previous = Uint8List(rowLength);
  for (var y = 0; y < height; y++) {
    final filter = inflated[sourceOffset++];
    if (filter > 4) return null;
    final row = Uint8List(rowLength);
    for (var x = 0; x < rowLength; x++) {
      final raw = inflated[sourceOffset++];
      final left = x >= bytesPerPixel ? row[x - bytesPerPixel] : 0;
      final up = previous[x];
      final upLeft = x >= bytesPerPixel ? previous[x - bytesPerPixel] : 0;
      row[x] = switch (filter) {
        0 => raw,
        1 => (raw + left) & 0xFF,
        2 => (raw + up) & 0xFF,
        3 => (raw + ((left + up) >> 1)) & 0xFF,
        4 => (raw + _paeth(left, up, upLeft)) & 0xFF,
        _ => 0,
      };
    }
    for (var x = 0; x < width; x++) {
      final alpha = row[x * bytesPerPixel + 3];
      if (alpha < 255) {
        hasTransparentPixel = true;
        if (y == 0 || y == height - 1 || x == 0 || x == width - 1) {
          hasTransparentEdgePixels = true;
        }
      }
    }
    if (y == 0 || y == height - 1) {
      cornerAlpha.add(row[3]);
      cornerAlpha.add(row[rowLength - 1]);
    }
    previous = row;
  }
  return _DecodedRgbaPng(
    width: width,
    height: height,
    hasTransparentPixel: hasTransparentPixel,
    hasTransparentCorners:
        cornerAlpha.length == 4 && cornerAlpha.every((alpha) => alpha < 255),
    hasTransparentEdgePixels: hasTransparentEdgePixels,
  );
}

int _paeth(int left, int up, int upLeft) {
  final prediction = left + up - upLeft;
  final leftDistance = (prediction - left).abs();
  final upDistance = (prediction - up).abs();
  final upLeftDistance = (prediction - upLeft).abs();
  if (leftDistance <= upDistance && leftDistance <= upLeftDistance) return left;
  if (upDistance <= upLeftDistance) return up;
  return upLeft;
}

class _DecodedRgbaPng {
  const _DecodedRgbaPng({
    required this.width,
    required this.height,
    required this.hasTransparentPixel,
    required this.hasTransparentCorners,
    required this.hasTransparentEdgePixels,
  });

  final int width;
  final int height;
  final bool hasTransparentPixel;
  final bool hasTransparentCorners;
  final bool hasTransparentEdgePixels;
}

int _readUint32(Uint8List bytes, int offset) =>
    (bytes[offset] << 24) |
    (bytes[offset + 1] << 16) |
    (bytes[offset + 2] << 8) |
    bytes[offset + 3];
