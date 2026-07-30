import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('admin entry sheet explains and confirms audit abandonment', (
    tester,
  ) async {
    bool? confirmed;
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(
          body: AdminEntryConfirmationSheet(
            onCancel: () => confirmed = false,
            onConfirm: () => confirmed = true,
          ),
        ),
      ),
    );

    expect(find.text('진행 중인 고객 계산은 취소되고 기록으로 남습니다.'), findsOneWidget);
    await tester.tap(find.text('계산을 취소하고 관리자 모드로 이동'));
    expect(confirmed, isTrue);
  });
}
