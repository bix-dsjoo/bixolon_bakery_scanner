import 'dart:convert';

/// Encodes JSON deterministically for immutable audit receipts.
///
/// Object keys are lexicographically sorted, arrays retain their supplied
/// order, and non-finite numbers are rejected rather than serialized through
/// a platform-specific representation.
String canonicalJsonEncode(Object? value) => jsonEncode(_canonicalize(value));

Object? _canonicalize(Object? value) {
  if (value == null || value is bool || value is String || value is int) {
    return value;
  }
  if (value is double) {
    if (!value.isFinite) {
      throw ArgumentError.value(value, 'value', 'JSON numbers must be finite');
    }
    if (value == 0 || value == value.truncateToDouble()) {
      return value.toInt();
    }
    return value;
  }
  if (value is List) {
    return [for (final item in value) _canonicalize(item)];
  }
  if (value is Map) {
    if (value.keys.any((key) => key is! String)) {
      throw ArgumentError.value(
        value,
        'value',
        'JSON object keys must be strings',
      );
    }
    final keys = value.keys.cast<String>().toList()..sort();
    return <String, Object?>{
      for (final key in keys) key: _canonicalize(value[key]),
    };
  }
  throw ArgumentError.value(value, 'value', 'is not a JSON value');
}
