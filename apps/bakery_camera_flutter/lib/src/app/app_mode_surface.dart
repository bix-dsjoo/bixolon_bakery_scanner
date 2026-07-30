import 'package:flutter/material.dart';

import '../checkout/checkout_controller.dart';
import '../ui/admin/admin_destination.dart';
import '../ui/admin/admin_shell.dart';
import '../ui/customer/customer_checkout_screen.dart';
import 'app_mode_controller.dart';

typedef AppModeControllerFactory =
    AppModeController Function(CustomerModeLifecycle customerLifecycle);

/// The live customer/admin surface used after checkout bootstrap succeeds.
///
/// It keeps the operational bootstrap outside the customer/admin state
/// transition so the durable lifecycle boundary can be exercised directly.
class BakeryAppSurface extends StatefulWidget {
  const BakeryAppSurface({
    required this.checkout,
    this.customerLifecycle,
    this.adminDestinationBuilder,
    this.createModeController,
    super.key,
  });

  final CheckoutController checkout;
  final CustomerModeLifecycle? customerLifecycle;
  final AdminDestinationBuilder? adminDestinationBuilder;
  final AppModeControllerFactory? createModeController;

  @override
  State<BakeryAppSurface> createState() => _BakeryAppSurfaceState();
}

class _BakeryAppSurfaceState extends State<BakeryAppSurface> {
  late final AppModeController _modes =
      (widget.createModeController ??
      (lifecycle) => AppModeController(customerLifecycle: lifecycle))(
        widget.customerLifecycle ??
            CheckoutCustomerModeLifecycle(widget.checkout),
      );

  @override
  void dispose() {
    _modes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _modes,
    builder: (context, _) => switch (_modes.mode) {
      AppMode.customer => CustomerCheckoutScreen(
        controller: widget.checkout,
        requiresAdminEntryConfirmation: _modes.requiresAbandonConfirmation,
        onEnterAdmin: _modes.enterAdmin,
        onPaymentCompleted: _modes.onPaymentCompleted,
      ),
      AppMode.admin => AdminShell(
        controller: _modes,
        onReturnToCustomer: _modes.exitAdmin,
        destinationBuilder: widget.adminDestinationBuilder ?? _adminPlaceholder,
      ),
    },
  );
}

Widget _adminPlaceholder(BuildContext context, AdminDestination destination) =>
    Center(
      child: Text(
        '${destination.label} 화면을 준비하고 있어요.',
        style: Theme.of(context).textTheme.bodyLarge,
      ),
    );

final class CheckoutCustomerModeLifecycle implements CustomerModeLifecycle {
  const CheckoutCustomerModeLifecycle(this._checkout);

  final CheckoutController _checkout;

  @override
  bool get hasActiveCustomerCheckout => _checkout.hasActiveCustomerCheckout;

  @override
  Future<void> abandonForAdminEntry(String reason) {
    if (reason != 'admin_mode_entered') {
      throw ArgumentError.value(reason, 'reason', 'is not an admin entry');
    }
    return _checkout.abandonForAdminEntry();
  }

  @override
  Future<void> startFreshCustomerSession() =>
      _checkout.startFreshCustomerSession();
}
