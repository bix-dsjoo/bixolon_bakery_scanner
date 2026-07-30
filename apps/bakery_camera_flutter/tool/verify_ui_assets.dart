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
    if (entry['tool_provenance'] is! String ||
        (entry['tool_provenance'] as String).trim().isEmpty) {
      errors.add('$label is missing generation tool provenance');
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
    final dimensions = _readTransparentPngDimensions(bytes);
    if (dimensions == null) {
      errors.add('$label is not an RGBA PNG with an alpha channel');
    } else if (entry['width'] != dimensions.$1 ||
        entry['height'] != dimensions.$2) {
      errors.add('$label declared dimensions do not match the PNG');
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
    await for (final entity in illustrations.list(followLinks: false)) {
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

(int, int)? _readTransparentPngDimensions(Uint8List bytes) {
  if (bytes.length < 29) return null;
  for (var index = 0; index < _pngSignature.length; index++) {
    if (bytes[index] != _pngSignature[index]) return null;
  }
  if (String.fromCharCodes(bytes.sublist(12, 16)) != 'IHDR') return null;
  final width = _readUint32(bytes, 16);
  final height = _readUint32(bytes, 20);
  const colorTypeIndex = 25;
  if (width <= 0 || height <= 0 || bytes[colorTypeIndex] != 6) return null;
  return (width, height);
}

int _readUint32(Uint8List bytes, int offset) =>
    (bytes[offset] << 24) |
    (bytes[offset + 1] << 16) |
    (bytes[offset + 2] << 8) |
    bytes[offset + 3];
