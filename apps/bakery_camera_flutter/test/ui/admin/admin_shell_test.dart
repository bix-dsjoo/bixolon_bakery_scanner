import 'package:bakery_camera_prototype/src/app/app_mode_controller.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_destination.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_shell.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'admin shell separates the customer checkout and restores selection',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final controller = AppModeController(customerLifecycle: _Lifecycle());
      await controller.enterAdmin(abandonConfirmed: true);

      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: SizedBox(
            width: 1280,
            height: 820,
            child: AdminShell(
              controller: controller,
              onReturnToCustomer: controller.exitAdmin,
              destinationBuilder: (context, destination) =>
                  Text('destination:${destination.name}'),
            ),
          ),
        ),
      );

      expect(find.text('관리자 모드'), findsOneWidget);
      expect(find.text('빵을 올려주세요'), findsNothing);
      expect(find.text('거래 내역'), findsOneWidget);

      await tester.tap(find.text('거래 내역'));
      await tester.pumpAndSettle();
      expect(find.text('destination:transactions'), findsOneWidget);

      await tester.tap(find.text('고객 화면으로 돌아가기'));
      await tester.pumpAndSettle();
      expect(controller.mode, AppMode.customer);
      expect(controller.destination, AdminDestination.transactions);
    },
  );

  testWidgets('compact width uses a drawer without customer controls', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AppModeController(customerLifecycle: _Lifecycle());
    await controller.enterAdmin(abandonConfirmed: true);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: SizedBox(
          width: 1024,
          height: 720,
          child: AdminShell(
            controller: controller,
            onReturnToCustomer: controller.exitAdmin,
            destinationBuilder: (context, destination) => const SizedBox(),
          ),
        ),
      ),
    );

    expect(tester.widget<Scaffold>(find.byType(Scaffold)).drawer, isNotNull);
    expect(find.text('빵 확인하기'), findsNothing);
  });
}

final class _Lifecycle implements CustomerModeLifecycle {
  @override
  Future<void> abandonForAdminEntry(String reason) async {}

  @override
  bool get hasActiveCustomerCheckout => false;

  @override
  Future<void> startFreshCustomerSession() async {}
}
