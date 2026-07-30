import 'package:bakery_camera_prototype/src/app/app_mode_controller.dart';
import 'package:bakery_camera_prototype/src/ui/admin/admin_destination.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('cold start and payment reset always select customer mode', () async {
    final lifecycle = _CustomerLifecycle(activeCheckout: false);
    final controller = AppModeController(customerLifecycle: lifecycle);

    expect(controller.mode, AppMode.customer);
    await controller.enterAdmin(abandonConfirmed: true);
    expect(controller.mode, AppMode.admin);

    controller.onPaymentCompleted();

    expect(controller.mode, AppMode.customer);
    expect(lifecycle.abandonReasons, isEmpty);
  });

  test(
    'admin entry keeps active checkout until abandonment is confirmed',
    () async {
      final lifecycle = _CustomerLifecycle(activeCheckout: true);
      final controller = AppModeController(customerLifecycle: lifecycle);

      final entered = await controller.enterAdmin(abandonConfirmed: false);

      expect(entered, isFalse);
      expect(controller.mode, AppMode.customer);
      expect(lifecycle.abandonReasons, isEmpty);

      expect(await controller.enterAdmin(abandonConfirmed: true), isTrue);
      expect(controller.mode, AppMode.admin);
      expect(lifecycle.abandonReasons, ['admin_mode_entered']);
    },
  );

  test(
    'admin exit starts a fresh customer session and preserves navigation',
    () async {
      final lifecycle = _CustomerLifecycle(activeCheckout: false);
      final controller = AppModeController(customerLifecycle: lifecycle);
      await controller.enterAdmin(abandonConfirmed: true);
      controller.selectDestination(AdminDestination.transactions);
      controller.updateTransactionFilter('completed');

      await controller.exitAdmin();

      expect(controller.mode, AppMode.customer);
      expect(lifecycle.freshCustomerStarts, 1);
      expect(controller.destination, AdminDestination.transactions);
      expect(controller.transactionFilter, 'completed');
    },
  );
}

final class _CustomerLifecycle implements CustomerModeLifecycle {
  _CustomerLifecycle({required this.activeCheckout});

  bool activeCheckout;
  final List<String> abandonReasons = [];
  int freshCustomerStarts = 0;

  @override
  bool get hasActiveCustomerCheckout => activeCheckout;

  @override
  Future<void> abandonForAdminEntry(String reason) async {
    abandonReasons.add(reason);
    activeCheckout = false;
  }

  @override
  Future<void> startFreshCustomerSession() async {
    freshCustomerStarts += 1;
    activeCheckout = true;
  }
}
