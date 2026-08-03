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

/// Supplies the one header action without making each customer phase own a
/// second overlay stack.
class KioskHeaderActionScope extends InheritedWidget {
  const KioskHeaderActionScope({
    required this.action,
    required super.child,
    super.key,
  });

  final Widget action;

  static Widget? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<KioskHeaderActionScope>()
      ?.action;

  @override
  bool updateShouldNotify(KioskHeaderActionScope oldWidget) =>
      action != oldWidget.action;
}

/// A customer shell with a compact full-width header and optional action rail.
class CheckoutScaffold extends StatelessWidget {
  const CheckoutScaffold({
    required this.title,
    required this.child,
    this.primaryAction,
    this.maxWidth = 1240,
    this.scrollable = true,
    super.key,
  });

  final String title;
  final Widget child;
  final Widget? primaryAction;
  final double maxWidth;
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              key: const Key('customer-header'),
              height: 61,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: tokens.paper,
                  border: Border(
                    bottom: BorderSide(color: tokens.divider, width: 1),
                  ),
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(maxWidth: maxWidth),
                    child: SizedBox(
                      width: maxWidth,
                      child: _CustomerHeader(title: title),
                    ),
                  ),
                ),
              ),
            ),
            Expanded(
              child: Center(
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: maxWidth),
                  child: scrollable
                      ? SingleChildScrollView(
                          padding: const EdgeInsets.symmetric(horizontal: 24),
                          child: child,
                        )
                      : Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 24),
                          child: child,
                        ),
                ),
              ),
            ),
            if (primaryAction case final action?)
              SizedBox(
                key: const Key('customer-action-rail'),
                height: 76,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: tokens.paper,
                    border: Border(top: BorderSide(color: tokens.divider)),
                  ),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: BoxConstraints(maxWidth: maxWidth),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 24),
                        child: action,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CustomerHeader extends StatelessWidget {
  const _CustomerHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final headerAction = KioskHeaderActionScope.maybeOf(context);
    final textTheme = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          const BixolonWordmark(style: TextStyle(fontSize: 16, height: 1.2)),
          const SizedBox(width: 16),
          Flexible(
            fit: FlexFit.tight,
            child: Text(
              title,
              key: const Key('customer-page-title'),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: textTheme.titleMedium,
            ),
          ),
          const Spacer(),
          if (headerAction != null)
            SizedBox(
              key: const Key('customer-header-action'),
              height: 48,
              child: headerAction,
            ),
        ],
      ),
    );
  }
}
