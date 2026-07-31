import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';

class BakerySecondaryButton extends StatelessWidget {
  const BakerySecondaryButton({
    required this.label,
    required this.onPressed,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return SizedBox(
      height: 48,
      child: OutlinedButton(
        onPressed: onPressed,
        style: ButtonStyle(
          foregroundColor: const WidgetStatePropertyAll(Color(0xFF424242)),
          side: WidgetStateProperty.resolveWith(
            (states) => BorderSide(
              color: states.contains(WidgetState.focused)
                  ? tokens.focus
                  : tokens.controlBorder,
              width: states.contains(WidgetState.focused) ? 2 : 1,
            ),
          ),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(tokens.controlRadius),
            ),
          ),
        ),
        child: Text(label),
      ),
    );
  }
}
