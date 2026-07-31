import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import 'captured_review_overlay.dart';
import 'customer_review_presentation.dart';

/// Links every customer review ledger row to its object in the retained image.
class CustomerReviewView extends StatefulWidget {
  const CustomerReviewView({
    required this.state,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onContinue,
    this.onRetakeCapture,
    this.imageProviderFactory = customerReviewFileImageProvider,
    super.key,
  });

  final CheckoutState state;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback onContinue;
  final VoidCallback? onRetakeCapture;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  @override
  State<CustomerReviewView> createState() => _CustomerReviewViewState();
}

class _CustomerReviewViewState extends State<CustomerReviewView> {
  String? _selectedObjectId;

  @override
  void initState() {
    super.initState();
    _selectedObjectId = _initialSelection(widget.state);
  }

  @override
  void didUpdateWidget(CustomerReviewView oldWidget) {
    super.didUpdateWidget(oldWidget);
    final selectedObjectId = _selectedObjectId;
    if (selectedObjectId == null) {
      _selectedObjectId = _initialSelection(widget.state);
      return;
    }
    final previous = _draftFor(oldWidget.state, selectedObjectId);
    final current = _draftFor(widget.state, selectedObjectId);
    if (current == null ||
        (previous?.isResolved == false && current.isResolved)) {
      _selectedObjectId = _initialSelection(widget.state);
    }
  }

  ObjectDraft? _draftFor(CheckoutState state, String objectId) {
    for (final draft in state.objectDrafts) {
      if (draft.inferenceObject.objectId == objectId) return draft;
    }
    return null;
  }

  String? _initialSelection(CheckoutState state) =>
      state.activeObject?.inferenceObject.objectId ??
      (state.objectDrafts.isEmpty
          ? null
          : state.objectDrafts.first.inferenceObject.objectId);

  void _selectObject(String objectId) => setState(() {
    _selectedObjectId = objectId;
  });

  @override
  Widget build(BuildContext context) {
    final presentation = CustomerReviewPresentation.fromDrafts(
      widget.state.objectDrafts,
    );
    final selectedObjectId = _selectedObjectId;
    final selectedDraft = selectedObjectId == null
        ? null
        : _draftFor(widget.state, selectedObjectId);
    final unresolvedCount = widget.state.objectDrafts
        .where((draft) => !draft.isResolved)
        .length;
    final allResolved = unresolvedCount == 0;
    final imagePath = widget.state.capturedEvidenceDisplayPath;
    final imageWidth = widget.state.capturedImageWidth;
    final imageHeight = widget.state.capturedImageHeight;
    final hasCaptureOverlay =
        imagePath != null &&
        imageWidth != null &&
        imageWidth > 0 &&
        imageHeight != null &&
        imageHeight > 0;

    return CheckoutScaffold(
      title: '\uC0C1\uD488 \uD655\uC778',
      primaryAction: BakeryPrimaryButton(
        label: allResolved ? '\uC8FC\uBB38 \uD655\uC778' : '\uB2E4\uC74C',
        onPressed: allResolved ? widget.onContinue : null,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            BakeryStatusBanner(
              status: unresolvedCount == 0
                  ? BakeryStatus.ready
                  : BakeryStatus.uncertain,
              title: unresolvedCount == 0
                  ? '\uD655\uC778 \uC644\uB8CC'
                  : '\uC774 \uBE75\uC774 \uB9DE\uB098\uC694?',
              message: unresolvedCount == 0
                  ? '\uBAA8\uB4E0 \uC0C1\uD488\uC744 \uD655\uC778\uD588\uC5B4\uC694.'
                  : '\uC9C4\uD589\uD558\uAE30 \uC804 \uBAA8\uB4E0 \uC0C1\uD488\uC744 \uD655\uC778\uD574 \uC8FC\uC138\uC694.',
            ),
            const SizedBox(height: 16),
            if (hasCaptureOverlay) ...[
              CapturedReviewOverlay(
                imagePath: imagePath,
                imageWidth: imageWidth,
                imageHeight: imageHeight,
                objects: presentation.objects,
                selectedObjectId: selectedObjectId,
                onSelectObject: _selectObject,
                imageProviderFactory: widget.imageProviderFactory,
              ),
              const SizedBox(height: 20),
            ],
            if (!allResolved)
              Text(
                '\uD655\uC778\uC774 \uB05D\uB098\uC9C0 \uC54A\uC740 \uC0C1\uD488 $unresolvedCount\uAC1C\uAC00 \uC788\uC2B5\uB2C8\uB2E4.',
              ),
            if (!allResolved) const SizedBox(height: 12),
            for (final item in presentation.objects) ...[
              _ReviewLedgerRow(
                item: item,
                draft: _draftFor(widget.state, item.objectId),
                selected: item.objectId == selectedObjectId,
                onTap: () => _selectObject(item.objectId),
              ),
              if (item.objectId == selectedObjectId && selectedDraft != null)
                _SelectedObjectActions(
                  draft: selectedDraft,
                  productForCandidate: widget.productForCandidate,
                  onChooseTop3: widget.onChooseTop3,
                  onOpenCatalog: widget.onOpenCatalog,
                  onRetakeCapture: widget.onRetakeCapture,
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ReviewLedgerRow extends StatelessWidget {
  const _ReviewLedgerRow({
    required this.item,
    required this.draft,
    required this.selected,
    required this.onTap,
  });

  final CustomerReviewObject item;
  final ObjectDraft? draft;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final product = draft?.product;
    return ListTile(
      key: Key('customer-review-row-${item.objectId}'),
      selected: selected,
      leading: Text(item.numberLabel),
      title: Text(item.label),
      subtitle: Text('\uC0AC\uC9C4\uC5D0\uC11C ${item.numberLabel}\uBC88'),
      trailing: product == null ? null : PriceText(amount: product.unitPrice),
      onTap: onTap,
    );
  }
}

class _SelectedObjectActions extends StatelessWidget {
  const _SelectedObjectActions({
    required this.draft,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onRetakeCapture,
  });

  final ObjectDraft draft;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback? onRetakeCapture;

  @override
  Widget build(BuildContext context) {
    if (draft.isResolved) return const SizedBox.shrink();
    final objectId = draft.inferenceObject.objectId;
    return Padding(
      key: Key('customer-review-candidate-panel-$objectId'),
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (draft.requiresCatalogSelection)
            const Text(
              '\uBAA9\uB85D\uC5D0\uC11C \uC0C1\uD488\uC744 \uCC3E\uC544 \uC120\uD0DD\uD574 \uC8FC\uC138\uC694.',
            )
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final candidate in draft.candidates)
                  if (productForCandidate(objectId, candidate.skuId)
                      case final product?)
                    OutlinedButton(
                      onPressed: () => onChooseTop3(objectId, candidate.skuId),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(product.displayName),
                          PriceText(amount: product.unitPrice),
                        ],
                      ),
                    ),
              ],
            ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: () => onOpenCatalog(objectId),
                child: const Text(
                  '\uC804\uCCB4 \uC0C1\uD488\uC5D0\uC11C \uCC3E\uAE30',
                ),
              ),
              if (onRetakeCapture != null)
                TextButton(
                  onPressed: onRetakeCapture,
                  child: const Text('\uB2E4\uC2DC \uCD2C\uC601'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
