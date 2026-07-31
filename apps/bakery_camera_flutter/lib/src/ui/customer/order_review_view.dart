import 'package:flutter/material.dart';

import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import '../components/quantity_stepper.dart';
import 'captured_review_overlay.dart';
import 'customer_review_presentation.dart';

/// Keeps the retained capture beside the commercial order so automatically
/// accepted products remain explainable without creating a separate phase.
class OrderReviewView extends StatefulWidget {
  const OrderReviewView({
    required this.state,
    required this.onSetQuantity,
    required this.onAddProduct,
    required this.onOverrideObject,
    required this.onCountMismatch,
    required this.onPay,
    required this.onRemoveProduct,
    this.imageProviderFactory = customerReviewFileImageProvider,
    super.key,
  });

  final CheckoutState state;
  final void Function(String productId, int quantity) onSetQuantity;
  final VoidCallback onAddProduct;
  final ValueChanged<String> onOverrideObject;
  final VoidCallback onCountMismatch;
  final VoidCallback onPay;
  final ValueChanged<String> onRemoveProduct;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  @override
  State<OrderReviewView> createState() => _OrderReviewViewState();
}

class _OrderReviewViewState extends State<OrderReviewView> {
  String? _selectedObjectId;

  @override
  void initState() {
    super.initState();
    _selectedObjectId = _firstObjectId(widget.state);
  }

  @override
  void didUpdateWidget(OrderReviewView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final selectedObjectId = _selectedObjectId;
    if (selectedObjectId == null ||
        !widget.state.objectDrafts.any(
          (draft) => draft.inferenceObject.objectId == selectedObjectId,
        )) {
      _selectedObjectId = _firstObjectId(widget.state);
    }
  }

  String? _firstObjectId(CheckoutState state) => state.objectDrafts
      .map((draft) => draft.inferenceObject.objectId)
      .firstOrNull;

  void _selectObject(String objectId) =>
      setState(() => _selectedObjectId = objectId);

  void _selectLine(List<String> objectIds) {
    if (objectIds.isEmpty) return;
    final current = _selectedObjectId;
    if (current != null && objectIds.contains(current)) return;
    _selectObject(objectIds.first);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final total = state.lines.fold(0, (sum, line) => sum + line.totalPrice);
    final presentation = CustomerReviewPresentation.fromDrafts(
      state.objectDrafts,
    );
    final imagePath = state.capturedEvidenceDisplayPath;
    final imageWidth = state.capturedImageWidth;
    final imageHeight = state.capturedImageHeight;
    final hasCapture =
        imagePath != null &&
        imageWidth != null &&
        imageWidth > 0 &&
        imageHeight != null &&
        imageHeight > 0;

    return CheckoutScaffold(
      title: '주문 확인',
      maxWidth: 1240,
      scrollable: false,
      primaryAction: BakeryPrimaryButton(
        label: '${PriceText.formatKrw(total)} 결제하기',
        onPressed: state.canPay ? widget.onPay : null,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final scene = _OrderScenePane(
              hasCapture: hasCapture,
              imagePath: imagePath,
              imageWidth: imageWidth,
              imageHeight: imageHeight,
              presentation: presentation,
              selectedObjectId: _selectedObjectId,
              onSelectObject: _selectObject,
              imageProviderFactory: widget.imageProviderFactory,
            );
            final task = _OrderTaskPane(
              state: state,
              total: total,
              selectedObjectId: _selectedObjectId,
              onSelectLine: _selectLine,
              onSetQuantity: widget.onSetQuantity,
              onAddProduct: widget.onAddProduct,
              onOverrideObject: widget.onOverrideObject,
              onCountMismatch: widget.onCountMismatch,
              onRemoveProduct: widget.onRemoveProduct,
            );
            if (constraints.maxWidth < 760) {
              return Column(
                children: [
                  Expanded(flex: 3, child: scene),
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 12),
                  Expanded(flex: 4, child: task),
                ],
              );
            }
            return Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(flex: 3, child: scene),
                const SizedBox(width: 20),
                const VerticalDivider(
                  key: Key('order-review-workspace-divider'),
                  width: 1,
                  thickness: 1,
                ),
                const SizedBox(width: 20),
                Expanded(flex: 2, child: task),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _OrderScenePane extends StatelessWidget {
  const _OrderScenePane({
    required this.hasCapture,
    required this.imagePath,
    required this.imageWidth,
    required this.imageHeight,
    required this.presentation,
    required this.selectedObjectId,
    required this.onSelectObject,
    required this.imageProviderFactory,
  });

  final bool hasCapture;
  final String? imagePath;
  final int? imageWidth;
  final int? imageHeight;
  final CustomerReviewPresentation presentation;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  @override
  Widget build(BuildContext context) => Padding(
    key: const Key('order-review-scene-pane'),
    padding: const EdgeInsets.only(right: 4),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('촬영한 트레이', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Expanded(
          child: Center(
            child: hasCapture
                ? CapturedReviewOverlay(
                    imagePath: imagePath!,
                    imageWidth: imageWidth!,
                    imageHeight: imageHeight!,
                    objects: presentation.objects,
                    selectedObjectId: selectedObjectId,
                    onSelectObject: onSelectObject,
                    imageProviderFactory: imageProviderFactory,
                  )
                : const _OrderMissingCapture(),
          ),
        ),
      ],
    ),
  );
}

class _OrderMissingCapture extends StatelessWidget {
  const _OrderMissingCapture();

  @override
  Widget build(BuildContext context) => Semantics(
    label: '직접 담기 안내 그림',
    image: true,
    child: Image.asset(
      'assets/illustrations/manual_cart_entry.png',
      height: 120,
      fit: BoxFit.contain,
      excludeFromSemantics: true,
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    ),
  );
}

class _OrderTaskPane extends StatelessWidget {
  const _OrderTaskPane({
    required this.state,
    required this.total,
    required this.selectedObjectId,
    required this.onSelectLine,
    required this.onSetQuantity,
    required this.onAddProduct,
    required this.onOverrideObject,
    required this.onCountMismatch,
    required this.onRemoveProduct,
  });

  final CheckoutState state;
  final int total;
  final String? selectedObjectId;
  final ValueChanged<List<String>> onSelectLine;
  final void Function(String productId, int quantity) onSetQuantity;
  final VoidCallback onAddProduct;
  final ValueChanged<String> onOverrideObject;
  final VoidCallback onCountMismatch;
  final ValueChanged<String> onRemoveProduct;

  List<String> _recognizedObjectIds(CheckoutLine line) => [
    for (final draft in state.objectDrafts)
      if (draft.product?.productId == line.product.productId)
        draft.inferenceObject.objectId,
  ];

  @override
  Widget build(BuildContext context) => KeyedSubtree(
    key: const Key('order-review-task-pane'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text('주문 내역', style: Theme.of(context).textTheme.titleMedium),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.only(left: 4),
            children: [
              for (final line in state.lines)
                _OrderLine(
                  line: line,
                  selectedObjectId: selectedObjectId,
                  onSetQuantity: onSetQuantity,
                  recognizedObjectIds: _recognizedObjectIds(line),
                  onSelectLine: onSelectLine,
                  onOverrideObject: onOverrideObject,
                  onRemove:
                      state.objectDrafts.any(
                        (draft) =>
                            draft.product?.productId == line.product.productId,
                      )
                      ? null
                      : () => onRemoveProduct(line.product.productId),
                ),
            ],
          ),
        ),
        const Divider(height: 24),
        Padding(
          padding: const EdgeInsets.only(left: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('합계', style: Theme.of(context).textTheme.titleLarge),
              PriceText(
                amount: total,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 4,
          children: [
            TextButton(onPressed: onAddProduct, child: const Text('상품 추가')),
            TextButton(
              onPressed: onCountMismatch,
              child: const Text('실제 빵 수가 달라요'),
            ),
          ],
        ),
      ],
    ),
  );
}

class _OrderLine extends StatelessWidget {
  const _OrderLine({
    required this.line,
    required this.selectedObjectId,
    required this.onSetQuantity,
    required this.recognizedObjectIds,
    required this.onSelectLine,
    required this.onOverrideObject,
    required this.onRemove,
  });

  final CheckoutLine line;
  final String? selectedObjectId;
  final void Function(String productId, int quantity) onSetQuantity;
  final List<String> recognizedObjectIds;
  final ValueChanged<List<String>> onSelectLine;
  final ValueChanged<String> onOverrideObject;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) => ListTile(
    key: Key('order-review-line-${line.product.productId}'),
    selected: recognizedObjectIds.contains(selectedObjectId),
    selectedTileColor: Theme.of(
      context,
    ).colorScheme.primary.withValues(alpha: 0.08),
    onTap: recognizedObjectIds.isEmpty
        ? null
        : () => onSelectLine(recognizedObjectIds),
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
        if (recognizedObjectIds.length == 1)
          IconButton(
            tooltip: '인식 상품 변경',
            onPressed: () => onOverrideObject(recognizedObjectIds.single),
            icon: const Icon(Icons.edit_outlined),
          )
        else if (recognizedObjectIds.length > 1)
          PopupMenuButton<String>(
            tooltip: '인식 상품 변경',
            onSelected: onOverrideObject,
            itemBuilder: (context) => [
              for (var index = 0; index < recognizedObjectIds.length; index++)
                PopupMenuItem(
                  value: recognizedObjectIds[index],
                  child: Text('${index + 1}번째 상품 변경'),
                ),
            ],
            icon: const Icon(Icons.edit_outlined),
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
