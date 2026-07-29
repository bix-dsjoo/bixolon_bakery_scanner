import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/bixolon_brand.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('BIXOLON orange uses the approved brand color', () {
    expect(bixolonOrange, const Color(0xFFEE7203));
  });

  test('result semantic colors remain distinct from BIXOLON orange', () {
    expect(confirmedTeal, isNot(bixolonOrange));
    expect(unknownAmber, isNot(bixolonOrange));
    expect(failureRed, isNot(bixolonOrange));
  });

  testWidgets('decorative X is excluded from accessibility semantics', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: BixolonBrandDecoration()));

    expect(find.byType(ExcludeSemantics), findsOneWidget);
  });
}
