import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production snapshot derives provenance from both release runtime policies', () {
    final source = File('lib/src/app/bakery_app.dart').readAsStringSync();
    final releaseProvenances = [
      File('../../configs/cpu_rfdetr_classifier_policy.yaml'),
      File('../../configs/gpu_rfdetr_classifier_policy.yaml'),
    ].map(_effectiveFusionProvenance).toSet();

    expect(releaseProvenances, hasLength(1));
    final provenance = releaseProvenances.single;
    expect(
      source,
      contains("calibrationId: 'fusion_policy_${provenance.decisionRule}'"),
    );
    expect(source, contains("calibrationSha256:\n      '${provenance.sha256}'"));
  });
}

({String decisionRule, String sha256}) _effectiveFusionProvenance(
  File configFile,
) {
  final config = configFile.readAsStringSync();
  final relativePolicyPath = RegExp(
    r'fusion_policy:\s*(\S+)',
  ).firstMatch(config)![1]!;
  final configuredSha256 = RegExp(
    r'fusion_policy_sha256:\s*([0-9a-f]{64})',
  ).firstMatch(config)![1]!;
  final policyFile = File.fromUri(
    configFile.parent.uri.resolve(relativePolicyPath),
  );
  final policy = jsonDecode(policyFile.readAsStringSync()) as Map<String, dynamic>;
  final policySha256 = sha256.convert(policyFile.readAsBytesSync()).toString();

  expect(configuredSha256, policySha256);
  return (decisionRule: policy['decision_rule'] as String, sha256: policySha256);
}
