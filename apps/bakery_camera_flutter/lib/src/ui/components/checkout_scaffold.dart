import 'package:flutter/material.dart';

import '../bixolon_brand.dart';
import '../bixolon_theme_extension.dart';

/// Carries the kiosk label from the session-bound settings revision through
/// every customer view without consulting mutable operational settings.
class KioskDisplayNameScope extends InheritedWidget {
  const KioskDisplayNameScope({
    required this.displayName,
    required super.child,
    super.key,
  });

  final String displayName;

  static String? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<KioskDisplayNameScope>()
      ?.displayName;

  @override
  bool updateShouldNotify(KioskDisplayNameScope oldWidget) =>
      displayName != oldWidget.displayName;
}

/// A customer shell with one fixed next action and receipt-style structure.
class CheckoutScaffold extends StatelessWidget {
  const CheckoutScaffold({
    required this.title,
    required this.child,
    required this.primaryAction,
    super.key,
  });

  final String title;
  final Widget child;
  final Widget primaryAction;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 24, 24, 16),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      border: Border(
                        left: BorderSide(color: tokens.action, width: 4),
                        bottom: BorderSide(color: tokens.ink, width: 1),
                      ),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(12, 0, 0, 12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const BixolonWordmark(),
                          const SizedBox(height: 8),
                          if (KioskDisplayNameScope.maybeOf(context)
                              case final displayName?) ...[
                            Text(
                              displayName,
                              key: const Key('kiosk-display-name'),
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                            const SizedBox(height: 4),
                          ],
                          Text(
                            title,
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: child,
                  ),
                ),
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: tokens.paper,
                    border: Border(top: BorderSide(color: tokens.divider)),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: primaryAction,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
