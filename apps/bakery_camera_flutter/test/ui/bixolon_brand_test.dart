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

  test('shared controls use the compact border and corner tokens', () {
    expect(bixolonControlBorderWidth, 1);
    expect(bixolonControlRadius, 6);
  });

  testWidgets('status dot is compact and carries its status label', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: BixolonStatusDot(label: 'Camera connected'),
        ),
      ),
    );

    expect(find.bySemanticsLabel('Camera connected'), findsOneWidget);
    expect(
      tester.getSize(find.byType(BixolonStatusDot)),
      const Size.square(bixolonStatusDotSize),
    );
  });

  testWidgets('legacy decoration renders no X motif', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: BixolonBrandDecoration(size: 64)),
    );

    expect(
      find.descendant(
        of: find.byType(BixolonBrandDecoration),
        matching: find.byType(CustomPaint),
      ),
      findsNothing,
    );
    expect(
      find.descendant(
        of: find.byType(BixolonBrandDecoration),
        matching: find.byType(ExcludeSemantics),
      ),
      findsOneWidget,
    );
  });
}
