import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';

/// The only emphasized action on a customer checkout surface.
class BakeryPrimaryButton extends StatelessWidget {
  const BakeryPrimaryButton({
    required this.label,
    required this.onPressed,
    super.key,
    this.icon,
    this.autofocus = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final style = ButtonStyle(
      backgroundColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.disabled)
            ? tokens.disabledAction
            : tokens.action,
      ),
      foregroundColor: const WidgetStatePropertyAll(Colors.white),
      minimumSize: const WidgetStatePropertyAll(Size(48, 56)),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(tokens.controlRadius),
        ),
      ),
      side: WidgetStateProperty.resolveWith(
        (states) => BorderSide(
          color: states.contains(WidgetState.focused)
              ? tokens.focus
              : Colors.transparent,
          width: states.contains(WidgetState.focused) ? 2 : 0,
        ),
      ),
    );
    final button = icon == null
        ? FilledButton(
            onPressed: onPressed,
            autofocus: autofocus,
            style: style,
            child: Text(label),
          )
        : FilledButton.icon(
            onPressed: onPressed,
            autofocus: autofocus,
            style: style,
            icon: Icon(icon!),
            label: Text(label),
          );
    return Semantics(
      button: true,
      enabled: onPressed != null,
      label: label,
      onTap: onPressed,
      child: SizedBox(width: double.infinity, height: 56, child: button),
    );
  }
}
