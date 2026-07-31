import 'package:flutter/material.dart';

import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import '../components/quantity_stepper.dart';

class OrderReviewView extends StatelessWidget {
  const OrderReviewView({
    required this.state,
    required this.onSetQuantity,
    required this.onAddProduct,
    required this.onOverrideObject,
    required this.onCountMismatch,
    required this.onPay,
    required this.onRemoveProduct,
    super.key,
  });

  final CheckoutState state;
  final void Function(String productId, int quantity) onSetQuantity;
  final VoidCallback onAddProduct;
  final ValueChanged<String> onOverrideObject;
  final VoidCallback onCountMismatch;
  final VoidCallback onPay;
  final ValueChanged<String> onRemoveProduct;

  @override
  Widget build(BuildContext context) {
    final total = state.lines.fold(0, (sum, line) => sum + line.totalPrice);
    return CheckoutScaffold(
      title: '주문 확인',
      primaryAction: BakeryPrimaryButton(
        label: '${PriceText.formatKrw(total)} 결제하기',
        onPressed: state.canPay ? onPay : null,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (state.objectDrafts.isEmpty) ...[
              Semantics(
                label: '직접 담기 안내 그림',
                image: true,
                child: Image.asset(
                  'assets/illustrations/manual_cart_entry.png',
                  height: 120,
                  fit: BoxFit.contain,
                  excludeFromSemantics: true,
                  errorBuilder: (_, _, _) => const SizedBox.shrink(),
                ),
              ),
              const SizedBox(height: 8),
            ],
            for (final line in state.lines)
              _OrderLine(
                line: line,
                onSetQuantity: onSetQuantity,
                onRemove:
                    state.objectDrafts.any(
                      (draft) =>
                          draft.product?.productId == line.product.productId,
                    )
                    ? null
                    : () => onRemoveProduct(line.product.productId),
              ),
            const Divider(height: 32),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('합계', style: Theme.of(context).textTheme.titleLarge),
                PriceText(
                  amount: total,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ],
            ),
            const SizedBox(height: 16),
            TextButton(onPressed: onAddProduct, child: const Text('상품 추가')),
            for (final draft in state.objectDrafts.where(
              (value) => value.isResolved,
            ))
              TextButton(
                onPressed: () =>
                    onOverrideObject(draft.inferenceObject.objectId),
                child: Text('${draft.product!.displayName} 상품 변경'),
              ),
            TextButton(
              onPressed: onCountMismatch,
              child: const Text('실제 빵 수가 달라요'),
            ),
          ],
        ),
      ),
    );
  }
}

class _OrderLine extends StatelessWidget {
  const _OrderLine({
    required this.line,
    required this.onSetQuantity,
    required this.onRemove,
  });

  final CheckoutLine line;
  final void Function(String productId, int quantity) onSetQuantity;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) => ListTile(
    title: Text(line.product.displayName),
    subtitle: Text('개당 ${PriceText.formatKrw(line.product.unitPrice)}'),
    trailing: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        QuantityStepper(
          quantity: line.quantity,
          onChanged: (quantity) =>
              onSetQuantity(line.product.productId, quantity),
        ),
        if (onRemove != null)
          IconButton(
            tooltip: '상품 삭제',
            onPressed: onRemove,
            icon: const Icon(Icons.delete_outline),
          ),
      ],
    ),
  );
}
