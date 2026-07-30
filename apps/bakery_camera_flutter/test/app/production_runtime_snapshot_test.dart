import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production snapshot binds the effective fusion provenance', () {
    final source = File('lib/src/app/bakery_app.dart').readAsStringSync();

    expect(
      source,
      contains(
        "calibrationId: 'fusion_policy_fusion_local_or_global_consensus_margin_v1'",
      ),
    );
    expect(
      source,
      contains(
        "calibrationSha256:\n      '06c692d5b35583bfd99498805da474b7e9dfa7c8c36eeed04307695f7e885dcc'",
      ),
    );
  });
}
