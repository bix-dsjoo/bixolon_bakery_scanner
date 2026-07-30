import 'package:flutter/material.dart';

import '../../app/app_mode_controller.dart';
import '../bixolon_brand.dart';
import '../bixolon_theme_extension.dart';
import 'admin_destination.dart';

typedef AdminDestinationBuilder =
    Widget Function(BuildContext context, AdminDestination destination);

/// A navigation-only administrator shell. Customer checkout controls and cart
/// content belong exclusively to the customer surface and never render here.
class AdminShell extends StatelessWidget {
  const AdminShell({
    required this.controller,
    required this.onReturnToCustomer,
    required this.destinationBuilder,
    super.key,
  });

  static const _compactBreakpoint = 1100.0;

  final AppModeController controller;
  final Future<void> Function() onReturnToCustomer;
  final AdminDestinationBuilder destinationBuilder;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < _compactBreakpoint;
        final content = _AdminContent(
          destination: controller.destination,
          child: destinationBuilder(context, controller.destination),
        );
        return Scaffold(
          appBar: compact
              ? AppBar(
                  title: const _AdminModeLabel(),
                  actions: [
                    TextButton(
                      onPressed: _returnToCustomer,
                      child: const Text('고객 화면으로 돌아가기'),
                    ),
                  ],
                )
              : null,
          drawer: compact
              ? Drawer(
                  child: SafeArea(
                    child: _AdminNavigation(
                      selected: controller.destination,
                      onSelected: (destination) {
                        controller.selectDestination(destination);
                        Navigator.of(context).pop();
                      },
                      onReturnToCustomer: _returnToCustomer,
                    ),
                  ),
                )
              : null,
          body: compact
              ? content
              : Row(
                  children: [
                    SizedBox(
                      width: 264,
                      child: _AdminNavigation(
                        selected: controller.destination,
                        onSelected: controller.selectDestination,
                        onReturnToCustomer: _returnToCustomer,
                      ),
                    ),
                    Expanded(child: content),
                  ],
                ),
        );
      },
    ),
  );

  Future<void> _returnToCustomer() => onReturnToCustomer();
}

class _AdminNavigation extends StatelessWidget {
  const _AdminNavigation({
    required this.selected,
    required this.onSelected,
    required this.onReturnToCustomer,
  });

  final AdminDestination selected;
  final ValueChanged<AdminDestination> onSelected;
  final Future<void> Function() onReturnToCustomer;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: tokens.paper,
        border: Border(right: BorderSide(color: tokens.divider)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 28, 24, 20),
            child: _AdminModeLabel(showWordmark: true),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final destination in AdminDestination.values)
                  _DestinationTile(
                    destination: destination,
                    selected: destination == selected,
                    onTap: () => onSelected(destination),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: OutlinedButton.icon(
              onPressed: onReturnToCustomer,
              icon: const Icon(Icons.storefront_outlined),
              label: const Text('고객 화면으로 돌아가기'),
            ),
          ),
        ],
      ),
    );
  }
}

class _DestinationTile extends StatelessWidget {
  const _DestinationTile({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final AdminDestination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    selected: selected,
    button: true,
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Material(
        color: Colors.transparent,
        child: ListTile(
          selected: selected,
          selectedTileColor: BixolonThemeExtension.of(
            context,
          ).action.withValues(alpha: 0.10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          title: Text(destination.label),
          onTap: onTap,
        ),
      ),
    ),
  );
}

class _AdminContent extends StatelessWidget {
  const _AdminContent({required this.destination, required this.child});

  final AdminDestination destination;
  final Widget child;

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            destination.label,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 6),
          Text(destination.description),
          const SizedBox(height: 28),
          Expanded(child: child),
        ],
      ),
    ),
  );
}

class _AdminModeLabel extends StatelessWidget {
  const _AdminModeLabel({this.showWordmark = false});

  final bool showWordmark;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (showWordmark) ...[
        const BixolonWordmark(),
        const SizedBox(height: 12),
      ],
      Semantics(
        label: '관리자 모드',
        child: const Chip(
          avatar: Icon(Icons.admin_panel_settings_outlined, size: 18),
          label: Text('관리자 모드'),
        ),
      ),
    ],
  );
}
