import 'package:bakery_camera_prototype/src/app/app_mode_controller.dart';
import 'package:bakery_camera_prototype/src/app/app_mode_surface.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_destination.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_shell.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  testWidgets(
    'app composition audits confirmed abandonment and retains admin context',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 1080);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      late CustomerCheckoutJourneyFixture fixture;
      await tester.runAsync(() async {
        fixture = await CustomerCheckoutJourneyFixture.create();
        await fixture.controller.initialize();
      });
      addTearDown(() => tester.runAsync(fixture.dispose));
      AppModeController? modes;

      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: BakeryAppSurface(
            checkout: fixture.controller,
            createModeController: (lifecycle) {
              return modes = AppModeController(customerLifecycle: lifecycle);
            },
          ),
        ),
      );
      await _pumpUntil(
        tester,
        () => find.byType(CustomerCheckoutScreen).evaluate().isNotEmpty,
      );

      await tester.tap(find.byIcon(Icons.admin_panel_settings_outlined).first);
      await _pumpUntil(
        tester,
        () => find.byType(AdminEntryConfirmationSheet).evaluate().isNotEmpty,
      );
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(
        find.descendant(
          of: find.byType(AdminEntryConfirmationSheet),
          matching: find.byType(FilledButton),
        ),
      );
      await _pumpUntil(
        tester,
        () =>
            find.byType(AdminShell).evaluate().isNotEmpty &&
            find.byType(AdminEntryConfirmationSheet).evaluate().isEmpty,
      );

      expect(find.byType(AdminShell), findsOneWidget);
      final abandoned = await fixture.database
          .select(fixture.database.checkoutSessions)
          .get();
      expect(abandoned.single.state, 'abandoned');

      await tester.tap(find.text(AdminDestination.transactions.label).first);
      await tester.pump();
      modes!.updateTransactionFilter('completed');

      await tester.tap(find.byIcon(Icons.storefront_outlined));
      await _pumpUntil(
        tester,
        () =>
            modes?.mode == AppMode.customer &&
            fixture.controller.state.phase == CheckoutPhase.ready,
      );

      expect(modes!.mode, AppMode.customer);
      expect(fixture.controller.state.phase, CheckoutPhase.ready);

      await tester.tap(find.byIcon(Icons.admin_panel_settings_outlined).first);
      await _pumpUntil(
        tester,
        () => find.byType(AdminEntryConfirmationSheet).evaluate().isNotEmpty,
      );
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(
        find.descendant(
          of: find.byType(AdminEntryConfirmationSheet),
          matching: find.byType(FilledButton),
        ),
      );
      await _pumpUntil(
        tester,
        () => find.byType(AdminShell).evaluate().isNotEmpty,
      );

      expect(modes!.destination, AdminDestination.transactions);
      expect(modes!.transactionFilter, 'completed');
      expect(find.byType(AdminShell), findsOneWidget);
    },
  );
}

Future<void> _pumpUntil(WidgetTester tester, bool Function() condition) async {
  for (var attempt = 0; attempt < 20; attempt += 1) {
    if (condition()) return;
    await tester.pump(const Duration(milliseconds: 50));
  }
  expect(condition(), isTrue, reason: 'expected app state did not settle');
}
