import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('bundled Pretendard files match the declared immutable manifest', () {
    final manifest = jsonDecode(
      File('assets/fonts/pretendard_manifest.json').readAsStringSync(),
    ) as Map<String, Object?>;
    expect(manifest['release'], '1.3.9');
    final files = manifest['files']! as List<Object?>;
    expect(files, hasLength(5));
    for (final value in files.cast<Map<String, Object?>>()) {
      final file = File('assets/fonts/${value['path']}');
      expect(file.existsSync(), isTrue, reason: file.path);
      expect(file.lengthSync(), value['bytes']);
      expect(
        sha256.convert(file.readAsBytesSync()).toString(),
        value['sha256'],
      );
    }
  });
}
