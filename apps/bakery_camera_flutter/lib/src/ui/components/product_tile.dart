import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';
import 'price_text.dart';

enum ProductAvailability { available, lowStock, unavailable, loading }

/// A receipt line item: product, availability in words, and a KRW price.
class ProductTile extends StatelessWidget {
  const ProductTile({
    required this.name,
    required this.price,
    required this.availability,
    super.key,
    this.trailing,
  });

  final String name;
  final int price;
  final ProductAvailability availability;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final status = switch (availability) {
      ProductAvailability.available => ('판매 가능', tokens.confirmed),
      ProductAvailability.lowStock => ('남은 수량이 적어요', tokens.uncertainty),
      ProductAvailability.unavailable => ('현재 판매하지 않아요', tokens.error),
      ProductAvailability.loading => ('상품 정보를 확인하고 있어요', tokens.focus),
    };
    final detail = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(name, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 4),
        Text(
          status.$1,
          style: Theme.of(
            context,
          ).textTheme.bodyMedium!.copyWith(color: status.$2),
        ),
      ],
    );

    return Semantics(
      container: true,
      label: '$name, ${status.$1}, ${PriceText.formatKrw(price)}',
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: tokens.paper,
          border: Border.symmetric(
            horizontal: BorderSide(color: tokens.divider),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: LayoutBuilder(
            builder: (context, constraints) {
              if (constraints.maxWidth < 440) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    detail,
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(child: PriceText(amount: price)),
                        if (trailing != null) ...[
                          const SizedBox(width: 16),
                          trailing!,
                        ],
                      ],
                    ),
                  ],
                );
              }
              return Row(
                children: [
                  Expanded(child: detail),
                  const SizedBox(width: 16),
                  PriceText(amount: price),
                  if (trailing != null) ...[
                    const SizedBox(width: 16),
                    trailing!,
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
