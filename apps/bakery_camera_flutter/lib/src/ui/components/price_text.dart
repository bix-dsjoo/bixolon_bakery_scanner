import 'package:flutter/material.dart';

class PriceText extends StatelessWidget {
  const PriceText({required this.amount, super.key, this.style});

  final int amount;
  final TextStyle? style;

  static String formatKrw(int amount) {
    if (amount < 0) {
      throw ArgumentError.value(
        amount,
        'amount',
        'Checkout price cannot be negative.',
      );
    }
    final digits = amount.toString();
    final groups = <String>[];
    for (var end = digits.length; end > 0; end -= 3) {
      groups.add(digits.substring(end < 3 ? 0 : end - 3, end));
    }
    return '${groups.reversed.join(',')}원';
  }

  @override
  Widget build(BuildContext context) {
    final priceStyle = (style ?? Theme.of(context).textTheme.titleMedium)!
        .copyWith(fontFeatures: const [FontFeature.tabularFigures()]);
    return Text(formatKrw(amount), style: priceStyle, textAlign: TextAlign.end);
  }
}
