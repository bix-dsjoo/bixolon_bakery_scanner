import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/catalog/catalog_photo_store.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temporaryDirectory;
  late CatalogPhotoStore store;

  setUp(() async {
    temporaryDirectory = await Directory.systemTemp.createTemp(
      'catalog-photo-',
    );
    store = CatalogPhotoStore(
      Directory(
        '${temporaryDirectory.path}${Platform.pathSeparator}application-data',
      ),
      maximumByteSize: 1024 * 1024,
    );
  });
  tearDown(() => temporaryDirectory.delete(recursive: true));

  test('imports a decoded PNG with immutable provenance metadata', () async {
    final source = File(
      '${temporaryDirectory.path}${Platform.pathSeparator}product.png',
    );
    final bytes = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8////fwYGBgYmEAHCAD34BABm6tHAAAAAAElFTkSuQmCC',
    );
    await source.writeAsBytes(bytes);

    final imported = await store.importFile(
      source,
      provenanceNote: 'Operator approved product photograph on 2026-07-31',
    );

    expect(imported.relativePath, startsWith('catalog-media/'));
    expect(imported.relativePath, endsWith('.png'));
    expect(imported.byteSize, bytes.length);
    expect(imported.sha256, sha256.convert(bytes).toString());
    expect(imported.mediaType, 'image/png');
    expect(imported.provenanceNote, isNotEmpty);
    expect(
      await File(
        '${store.applicationDataDirectory.path}${Platform.pathSeparator}${imported.relativePath}',
      ).readAsBytes(),
      bytes,
    );
  });

  test('rejects non-image and protected operational artifact sources', () async {
    final broken = File(
      '${temporaryDirectory.path}${Platform.pathSeparator}broken.jpg',
    );
    await broken.writeAsBytes(const [1, 2, 3]);
    final inferenceDirectory = Directory(
      '${temporaryDirectory.path}${Platform.pathSeparator}inference',
    );
    await inferenceDirectory.create();
    final inference = File(
      '${inferenceDirectory.path}${Platform.pathSeparator}evidence.png',
    );
    await inference.writeAsBytes(
      base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8////fwYGBgYmEAHCAD34BABm6tHAAAAAAElFTkSuQmCC',
      ),
    );

    await expectLater(
      () => store.importFile(broken, provenanceNote: 'approved'),
      throwsA(isA<FormatException>()),
    );
    await expectLater(
      () => store.importFile(inference, provenanceNote: 'approved'),
      throwsA(isA<ArgumentError>()),
    );
  });

  test('does not resolve a catalog photo whose persisted bytes changed', () async {
    final source = File(
      '${temporaryDirectory.path}${Platform.pathSeparator}approved.png',
    );
    await source.writeAsBytes(
      base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8////fwYGBgYmEAHCAD34BABm6tHAAAAAAElFTkSuQmCC',
      ),
    );
    final imported = await store.importFile(source, provenanceNote: 'approved');
    final destination = File(
      '${store.applicationDataDirectory.path}${Platform.pathSeparator}${imported.relativePath}',
    );
    await destination.writeAsBytes(const [1, 2, 3], flush: true);

    await expectLater(() => store.resolveVerified(imported), throwsStateError);
  });
}
