import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';

class QuantityStepper extends StatelessWidget {
  const QuantityStepper({required this.quantity, super.key, this.onChanged})
    : assert(quantity >= 1);

  final int quantity;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final controlStyle = ButtonStyle(
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
          width: states.contains(WidgetState.focused) ? 3 : 0,
        ),
      ),
    );
    return Semantics(
      label: '수량 $quantity',
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: tokens.divider),
          borderRadius: BorderRadius.circular(tokens.controlRadius),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: '수량 줄이기',
              onPressed: onChanged == null || quantity == 1
                  ? null
                  : () => onChanged!(quantity - 1),
              constraints: const BoxConstraints.tightFor(width: 48, height: 48),
              style: controlStyle,
              icon: const Icon(Icons.remove),
            ),
            SizedBox(
              width: 40,
              child: Text(
                '$quantity',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            IconButton(
              tooltip: '수량 늘리기',
              onPressed: onChanged == null
                  ? null
                  : () => onChanged!(quantity + 1),
              constraints: const BoxConstraints.tightFor(width: 48, height: 48),
              style: controlStyle,
              icon: const Icon(Icons.add),
            ),
          ],
        ),
      ),
    );
  }
}
