import 'package:flutter/material.dart';

import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../bixolon_theme_extension.dart';
import '../components/bakery_secondary_button.dart';
import '../components/price_text.dart';
import '../components/quantity_stepper.dart';
import 'captured_review_overlay.dart';
import 'checkout_review_workspace.dart';
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
    this.selectedObjectId,
    this.onSelectObject,
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
  final String? selectedObjectId;
  final ValueChanged<String>? onSelectObject;
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
    if (widget.onSelectObject != null) return;
    if (oldWidget.onSelectObject != null) {
      _selectedObjectId = _firstObjectId(widget.state);
      return;
    }
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

  String? get _effectiveSelectedObjectId => widget.onSelectObject == null
      ? _selectedObjectId
      : widget.selectedObjectId;

  void _selectObject(String objectId) {
    final onSelectObject = widget.onSelectObject;
    if (onSelectObject != null) {
      onSelectObject(objectId);
      return;
    }
    setState(() => _selectedObjectId = objectId);
  }

  void _selectLine(List<String> objectIds) {
    if (objectIds.isEmpty) return;
    final current = _effectiveSelectedObjectId;
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
    final selectedObjectId = _effectiveSelectedObjectId;
    return CheckoutReviewWorkspace(
      state: state,
      presentation: presentation,
      selectedObjectId: selectedObjectId,
      onSelectObject: _selectObject,
      taskTitle: '주문 내역',
      taskContent: _OrderTaskPane(
        state: state,
        presentation: presentation,
        selectedObjectId: selectedObjectId,
        onSelectLine: _selectLine,
        onSetQuantity: widget.onSetQuantity,
        onOverrideObject: widget.onOverrideObject,
        onRemoveProduct: widget.onRemoveProduct,
      ),
      primaryActionLabel: '${PriceText.formatKrw(total)} 결제하기',
      onPrimaryAction: state.canPay ? widget.onPay : null,
      footerActions: Wrap(
        key: const Key('order-exception-actions'),
        spacing: 8,
        runSpacing: 8,
        children: [
          BakerySecondaryButton(
            label: '\uC0C1\uD488 \uCD94\uAC00',
            onPressed: widget.onAddProduct,
          ),
          BakerySecondaryButton(
            label: '다시 촬영',
            onPressed: widget.onCountMismatch,
          ),
        ],
      ),
      imageProviderFactory: widget.imageProviderFactory,
      legacySceneKey: const Key('order-review-scene-pane'),
      legacyTaskKey: const Key('order-review-task-pane'),
      legacyDividerKey: const Key('order-review-workspace-divider'),
    );
  }
}

class _OrderTaskPane extends StatelessWidget {
  const _OrderTaskPane({
    required this.state,
    required this.presentation,
    required this.selectedObjectId,
    required this.onSelectLine,
    required this.onSetQuantity,
    required this.onOverrideObject,
    required this.onRemoveProduct,
  });

  final CheckoutState state;
  final CustomerReviewPresentation presentation;
  final String? selectedObjectId;
  final ValueChanged<List<String>> onSelectLine;
  final void Function(String productId, int quantity) onSetQuantity;
  final ValueChanged<String> onOverrideObject;
  final ValueChanged<String> onRemoveProduct;

  List<String> _recognizedObjectIds(CheckoutLine line) => [
    for (final draft in state.objectDrafts)
      if (draft.product?.productId == line.product.productId)
        draft.inferenceObject.objectId,
  ];

  int _displayNumber(String objectId) => presentation.objects
      .firstWhere((object) => object.objectId == objectId)
      .displayNumber;

  @override
  Widget build(BuildContext context) => ListView.separated(
    padding: const EdgeInsets.only(left: 4),
    itemCount: state.lines.length,
    itemBuilder: (context, index) {
      final line = state.lines[index];
      return _OrderLine(
        line: line,
        selectedObjectId: selectedObjectId,
        onSetQuantity: onSetQuantity,
        recognizedObjectIds: _recognizedObjectIds(line),
        displayNumberForObject: _displayNumber,
        onSelectLine: onSelectLine,
        onOverrideObject: onOverrideObject,
        onRemove:
            state.objectDrafts.any(
              (draft) => draft.product?.productId == line.product.productId,
            )
            ? null
            : () => onRemoveProduct(line.product.productId),
      );
    },
    separatorBuilder: (context, index) => Divider(
      key: Key('order-review-line-divider-$index'),
      color: BixolonThemeExtension.of(context).divider,
      height: 1,
      thickness: 1,
    ),
  );
}

class _OrderLine extends StatelessWidget {
  const _OrderLine({
    required this.line,
    required this.selectedObjectId,
    required this.onSetQuantity,
    required this.recognizedObjectIds,
    required this.displayNumberForObject,
    required this.onSelectLine,
    required this.onOverrideObject,
    required this.onRemove,
  });

  final CheckoutLine line;
  final String? selectedObjectId;
  final void Function(String productId, int quantity) onSetQuantity;
  final List<String> recognizedObjectIds;
  final int Function(String objectId) displayNumberForObject;
  final ValueChanged<List<String>> onSelectLine;
  final ValueChanged<String> onOverrideObject;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final selected = recognizedObjectIds.contains(selectedObjectId);
    return ListTile(
      key: selected
          ? const Key('order-review-selected-line')
          : Key('order-review-line-${line.product.productId}'),
      selected: selected,
      selectedTileColor: BixolonThemeExtension.of(context).selectedSurface,
      selectedColor: BixolonThemeExtension.of(context).ink,
      iconColor: BixolonThemeExtension.of(context).mutedInk,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      minTileHeight: 64,
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
                    child: Text(
                      '${displayNumberForObject(recognizedObjectIds[index]).toString().padLeft(2, '0')}번 빵 변경',
                    ),
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
}
