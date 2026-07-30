import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production snapshot derives effective provenance from classifier policy', () {
    final source = File('lib/src/app/bakery_app.dart').readAsStringSync();
    final config = File('../../configs/classifier_policy.yaml').readAsStringSync();
    final policyFile = File(
      '../../policies/classification/fusion_local_or_global_consensus_margin_v1.json',
    );
    final policy = jsonDecode(policyFile.readAsStringSync()) as Map<String, dynamic>;
    final decisionRule = policy['decision_rule'] as String;
    final policySha256 = sha256.convert(policyFile.readAsBytesSync()).toString();
    final configuredSha256 = RegExp(
      r'fusion_policy_sha256:\s*([0-9a-f]{64})',
    ).firstMatch(config)![1];

    expect(configuredSha256, policySha256);
    expect(
      source,
      contains("calibrationId: 'fusion_policy_$decisionRule'"),
    );
    expect(source, contains("calibrationSha256:\n      '$policySha256'"));
  });
}
