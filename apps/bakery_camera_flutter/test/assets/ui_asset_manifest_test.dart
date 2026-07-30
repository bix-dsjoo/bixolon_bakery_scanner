import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
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
        expect(entry['asset_id'], isA<String>());
        expect(entry['screen'], isA<String>());
        expect(entry['purpose'], isA<String>());
        expect(entry['generator_path'], isA<String>());
        expect(entry['alpha_validation'], {
          'decoded_rgba': true,
          'transparent_corners': true,
          'transparent_edge_pixels': true,
        });
        expect(entry['review_state'], 'approved');
        expect(entry['not_product_or_inference_evidence'], isTrue);
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

  test('the verifier rejects a nested unlisted illustration', () async {
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
      '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}nested${Platform.pathSeparator}not_approved.png',
    );
    await unlisted.parent.create(recursive: true);
    await unlisted.writeAsBytes(const [137, 80, 78, 71, 13, 10, 26, 10]);

    expect(
      await verifyUiAssets(appRoot: root),
      contains(contains('nested/not_approved.png')),
    );
  });

  test(
    'the verifier rejects every unallowlisted file below illustrations',
    () async {
      final root = await _copyAssetsToTempRoot();
      addTearDown(() => root.delete(recursive: true));
      final nestedWebp = File(
        '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}nested${Platform.pathSeparator}not_approved.webp',
      );
      final arbitraryFile = File(
        '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}unapproved-notes.txt',
      );
      await nestedWebp.parent.create(recursive: true);
      await nestedWebp.writeAsBytes(const [0x52, 0x49, 0x46, 0x46]);
      await arbitraryFile.writeAsString('not a shipped illustration');

      final errors = await verifyUiAssets(appRoot: root);

      expect(errors, contains(contains('not_approved.webp')));
      expect(errors, contains(contains('unapproved-notes.txt')));
    },
  );

  test(
    'the verifier rejects illustration links without following them',
    () async {
      final root = await _copyAssetsToTempRoot();
      addTearDown(() => root.delete(recursive: true));
      final link = Link(
        '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}linked_illustration',
      );

      final errors = await verifyUiAssets(
        appRoot: root,
        illustrationEntities: (_) async* {
          yield link;
        },
      );

      expect(errors, contains(contains('illustration link is not allowed')));
    },
  );

  test(
    'the verifier rejects an illustrations root directory link during normal enumeration',
    () async {
      final root = await _copyAssetsToTempRoot();
      addTearDown(() => root.delete(recursive: true));
      final illustrations = Directory(
        '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations',
      );
      final linkedTarget = Directory(
        '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations-target',
      );

      try {
        await illustrations.rename(linkedTarget.path);
        await Link(illustrations.path).create(linkedTarget.path);
      } on FileSystemException {
        // Windows can deny directory-link creation without Developer Mode or
        // elevated privileges. The injected-entity seam above still covers
        // the link rejection branch on those hosts.
        markTestSkipped(
          'directory-link creation is unavailable on this host; the injected '
          'entity seam still exercises the link rejection branch',
        );
      }

      expect(
        await verifyUiAssets(appRoot: root),
        contains(
          contains('assets/illustrations must be a directory, not a link'),
        ),
      );
    },
  );

  test('the verifier rejects an opaque RGBA illustration', () async {
    final root = await _copyAssetsToTempRoot();
    addTearDown(() => root.delete(recursive: true));
    final asset = File(
      '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}illustrations${Platform.pathSeparator}manual_cart_entry.png',
    );
    final opaquePng = _opaqueRgbaPng();
    await asset.writeAsBytes(opaquePng);

    final manifestFile = File(
      '${root.path}${Platform.pathSeparator}assets${Platform.pathSeparator}asset_manifest.json',
    );
    final manifest =
        jsonDecode(await manifestFile.readAsString()) as Map<String, dynamic>;
    final entry = (manifest['generated_ui_illustrations'] as List<dynamic>)
        .cast<Map<String, dynamic>>()
        .singleWhere((value) => value['allowed_use'] == 'manual_cart_entry');
    entry['width'] = 1;
    entry['height'] = 1;
    entry['byte_size'] = opaquePng.length;
    entry['sha256'] = sha256.convert(opaquePng).toString();
    await manifestFile.writeAsString(jsonEncode(manifest));

    expect(
      await verifyUiAssets(appRoot: root),
      contains(contains('genuinely transparent alpha pixels')),
    );
  });
}

Future<Directory> _copyAssetsToTempRoot() async {
  final root = await Directory.systemTemp.createTemp('ui-asset-gate-');
  final sourceAssets = Directory('assets');
  await for (final entity in sourceAssets.list(recursive: true)) {
    if (entity is! File) continue;
    final destination = File(
      '${root.path}${Platform.pathSeparator}${entity.path}',
    );
    await destination.parent.create(recursive: true);
    await entity.copy(destination.path);
  }
  return root;
}

Uint8List _opaqueRgbaPng() {
  final compressed = ZLibEncoder().convert(<int>[0, 0xFF, 0x80, 0x00, 0xFF]);
  return Uint8List.fromList(<int>[
    137,
    80,
    78,
    71,
    13,
    10,
    26,
    10,
    0,
    0,
    0,
    13,
    73,
    72,
    68,
    82,
    0,
    0,
    0,
    1,
    0,
    0,
    0,
    1,
    8,
    6,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    ..._chunk('IDAT', compressed),
    0,
    0,
    0,
    0,
    73,
    69,
    78,
    68,
    0,
    0,
    0,
    0,
  ]);
}

List<int> _chunk(String type, List<int> data) => <int>[
  (data.length >> 24) & 0xFF,
  (data.length >> 16) & 0xFF,
  (data.length >> 8) & 0xFF,
  data.length & 0xFF,
  ...type.codeUnits,
  ...data,
  0,
  0,
  0,
  0,
];
