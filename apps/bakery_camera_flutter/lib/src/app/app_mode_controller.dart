import 'package:flutter/foundation.dart';

import '../ui/admin/admin_destination.dart';

enum AppMode { customer, admin }

/// The narrow customer-session boundary required when moving between the two
/// visibly separate app modes. It deliberately exposes no audit mutation other
/// than the application-owned, durable abandonment and fresh-session actions.
abstract interface class CustomerModeLifecycle {
  bool get hasActiveCustomerCheckout;

  Future<void> abandonForAdminEntry(String reason);

  Future<void> startFreshCustomerSession();
}

/// Owns the mode switch and remembers the operator's last console context.
///
/// A customer checkout is never discarded implicitly: [enterAdmin] returns
/// false until the caller has obtained an explicit abandonment confirmation.
final class AppModeController extends ChangeNotifier {
  AppModeController({required this.customerLifecycle});

  final CustomerModeLifecycle customerLifecycle;

  AppMode _mode = AppMode.customer;
  AdminDestination _destination = AdminDestination.dashboard;
  String? _transactionFilter;

  AppMode get mode => _mode;
  AdminDestination get destination => _destination;
  String? get transactionFilter => _transactionFilter;
  bool get requiresAbandonConfirmation =>
      _mode == AppMode.customer && customerLifecycle.hasActiveCustomerCheckout;

  /// Returns false without changing state when confirmation is required.
  Future<bool> enterAdmin({required bool abandonConfirmed}) async {
    if (_mode == AppMode.admin) return true;
    if (customerLifecycle.hasActiveCustomerCheckout) {
      if (!abandonConfirmed) return false;
      await customerLifecycle.abandonForAdminEntry('admin_mode_entered');
    }
    _mode = AppMode.admin;
    notifyListeners();
    return true;
  }

  /// Starts a new checkout before making customer controls visible again.
  Future<void> exitAdmin() async {
    if (_mode != AppMode.admin) {
      throw StateError('admin exit requires administrator mode');
    }
    await customerLifecycle.startFreshCustomerSession();
    _mode = AppMode.customer;
    notifyListeners();
  }

  /// Payment cannot leave the customer-facing checkout mode.
  void onPaymentCompleted() {
    if (_mode == AppMode.customer) return;
    _mode = AppMode.customer;
    notifyListeners();
  }

  void selectDestination(AdminDestination destination) {
    if (_destination == destination) return;
    _destination = destination;
    notifyListeners();
  }

  /// Filters are intentionally retained while the customer flow is visible.
  void updateTransactionFilter(String? value) {
    if (_transactionFilter == value) return;
    _transactionFilter = value;
    notifyListeners();
  }
}
