import 'dart:io';

import 'package:crypto/crypto.dart';

final class FileHash {
  const FileHash({required this.byteSize, required this.sha256});

  final int byteSize;
  final String sha256;
}

/// Performs bounded-buffer file reads so evidence is never loaded wholesale.
final class Sha256FileHasher {
  static const _chunkSize = 64 * 1024;

  Future<FileHash> hashFile(File file) async {
    final input = await file.open(mode: FileMode.read);
    try {
      final sink = _DigestSink();
      final converter = sha256.startChunkedConversion(sink);
      var byteSize = 0;
      while (true) {
        final bytes = await input.read(_chunkSize);
        if (bytes.isEmpty) break;
        converter.add(bytes);
        byteSize += bytes.length;
      }
      converter.close();
      return FileHash(byteSize: byteSize, sha256: sink.value.toString());
    } finally {
      await input.close();
    }
  }

  Future<FileHash> copyAndHash({
    required File source,
    required File destination,
  }) async {
    final input = await source.open(mode: FileMode.read);
    final output = await destination.open(mode: FileMode.write);
    try {
      final sink = _DigestSink();
      final converter = sha256.startChunkedConversion(sink);
      var byteSize = 0;
      while (true) {
        final bytes = await input.read(_chunkSize);
        if (bytes.isEmpty) break;
        converter.add(bytes);
        await output.writeFrom(bytes);
        byteSize += bytes.length;
      }
      converter.close();
      await output.flush();
      return FileHash(byteSize: byteSize, sha256: sink.value.toString());
    } finally {
      await input.close();
      await output.close();
    }
  }

  Future<FileHash> writeAndHash({
    required List<int> bytes,
    required File destination,
  }) async {
    final output = await destination.open(mode: FileMode.write);
    try {
      final digest = sha256.convert(bytes).toString();
      await output.writeFrom(bytes);
      await output.flush();
      return FileHash(byteSize: bytes.length, sha256: digest);
    } finally {
      await output.close();
    }
  }
}

final class _DigestSink implements Sink<Digest> {
  Digest? _value;

  Digest get value => _value ?? (throw StateError('digest was not produced'));

  @override
  void add(Digest data) {
    if (_value != null) {
      throw StateError('digest was already produced');
    }
    _value = data;
  }

  @override
  void close() {}
}
