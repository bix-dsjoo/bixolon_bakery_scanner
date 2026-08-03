import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('active checkout requires confirmation before entering admin', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 820);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    bool? confirmed;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(
          body: CustomerAdminEntryControl(
            requiresAdminEntryConfirmation: true,
            onEnterAdmin: ({required abandonConfirmed}) async {
              confirmed = abandonConfirmed;
              return true;
            },
          ),
        ),
      ),
    );

    await tester.tap(find.text('관리자'));
    await tester.pumpAndSettle();
    expect(find.text('진행 중인 고객 계산은 취소되고 기록으로 남습니다.'), findsOneWidget);
    expect(confirmed, isNull);

    await tester.tap(find.text('계산을 취소하고 관리자 모드로 이동'));
    await tester.pumpAndSettle();
    expect(confirmed, isTrue);
  });
}
