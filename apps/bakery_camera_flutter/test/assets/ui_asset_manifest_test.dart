import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import '../../tool/verify_ui_assets.dart';

void main() {
  test(
    'the audited manifest lists exactly the two approved UI illustrations',
    () async {
      final manifestFile = File('assets/asset_manifest.json');
      expect(await manifestFile.exists(), isTrue);

      final manifest =
          jsonDecode(await manifestFile.readAsString()) as Map<String, dynamic>;
      final entries = manifest['generated_ui_illustrations'] as List<dynamic>;
      expect(entries, hasLength(2));

      for (final rawEntry in entries) {
        final entry = rawEntry as Map<String, dynamic>;
        expect(entry['kind'], 'generated_ui_illustration');
        expect(
          entry['allowed_use'],
          isIn(['manual_cart_entry', 'payment_complete']),
        );
        expect(
          entry['prohibited_uses'],
          containsAll([
            'product_photo',
            'camera_evidence',
            'model_input',
            'training_data',
            'evaluation_data',
          ]),
        );
        expect(entry['path'], isA<String>());
        expect(await File(entry['path'] as String).exists(), isTrue);
        expect(entry['format'], 'png');
        expect(entry['transparent_background'], isTrue);
        expect(entry['width'], isA<int>());
        expect(entry['height'], isA<int>());
        expect(entry['byte_size'], isA<int>());
        expect(entry['sha256'], matches(RegExp(r'^[a-f0-9]{64}$')));
        expect(entry['prompt'], isA<String>());
        expect(entry['generated_at_utc'], isA<String>());
        expect(entry['tool_provenance'], isA<String>());
      }
      expect(await verifyUiAssets(), isEmpty);
    },
  );

  test('the verifier rejects an unlisted illustration', () async {
    final root = await Directory.systemTemp.createTemp('ui-asset-gate-');
    addTearDown(() => root.delete(recursive: true));
    final sourceAssets = Directory('assets');
    await for (final entity in sourceAssets.list(recursive: true)) {
      if (entity is! File) continue;
      final destination = File(
        '${root.path}${Platform.pathSeparator}${entity.path}',
      );
      await destination.parent.create(recursive: true);
      await entity.copy(destination.path);
    }
    final unlisted = File(
      '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}not_approved.png',
    );
    await unlisted.writeAsBytes(const [137, 80, 78, 71, 13, 10, 26, 10]);

    expect(
      await verifyUiAssets(appRoot: root),
      contains(contains('unlisted generated illustration')),
    );
  });
}
