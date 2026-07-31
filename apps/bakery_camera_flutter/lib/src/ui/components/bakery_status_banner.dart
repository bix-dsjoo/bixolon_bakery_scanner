import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';

enum BakeryStatus { ready, loading, uncertain, error }

/// Explains a checkout status in words and iconography as well as color.
class BakeryStatusBanner extends StatelessWidget {
  const BakeryStatusBanner({
    required this.status,
    required this.title,
    required this.message,
    super.key,
  });

  final BakeryStatus status;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final presentation = switch (status) {
      BakeryStatus.ready => (Icons.check_circle_outline, tokens.confirmed),
      BakeryStatus.loading => (Icons.hourglass_top_outlined, tokens.focus),
      BakeryStatus.uncertain => (Icons.help_outline, tokens.uncertainty),
      BakeryStatus.error => (Icons.error_outline, tokens.error),
    };

    return Semantics(
      key: const ValueKey('status-message'),
      container: true,
      label: '$title. $message',
      child: ExcludeSemantics(
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: presentation.$2.withValues(alpha: 0.045),
            border: Border.all(color: tokens.divider),
            borderRadius: BorderRadius.circular(tokens.surfaceRadius),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(presentation.$1, color: presentation.$2, size: 24),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        message,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
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
