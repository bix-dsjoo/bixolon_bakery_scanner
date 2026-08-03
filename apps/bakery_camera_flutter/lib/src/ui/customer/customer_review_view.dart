import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/price_text.dart';
import '../bixolon_theme_extension.dart';
import 'captured_review_overlay.dart';
import 'catalog_picker.dart';
import 'checkout_review_workspace.dart';
import 'customer_review_presentation.dart';

/// Links every customer review ledger row to its object in the retained image.
class CustomerReviewView extends StatefulWidget {
  const CustomerReviewView({
    required this.state,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onContinue,
    this.selectedObjectId,
    this.onSelectObject,
    this.onRetakeCapture,
    this.catalogDiscovery,
    this.catalogSearch,
    this.onCatalogSelected,
    this.onCloseCatalog,
    this.imageProviderFactory = customerReviewFileImageProvider,
    super.key,
  });

  final CheckoutState state;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback onContinue;
  final String? selectedObjectId;
  final ValueChanged<String>? onSelectObject;
  final VoidCallback? onRetakeCapture;
  final CustomerCatalogDiscovery? catalogDiscovery;
  final Future<List<Product>> Function(String query)? catalogSearch;
  final ValueChanged<Product>? onCatalogSelected;
  final VoidCallback? onCloseCatalog;
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
    if (widget.onSelectObject != null) return;
    if (oldWidget.onSelectObject != null) {
      _selectedObjectId = _initialSelection(widget.state);
      return;
    }
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
      state.objectDrafts
          .where((draft) => !draft.isResolved)
          .firstOrNull
          ?.inferenceObject
          .objectId ??
      state.objectDrafts.firstOrNull?.inferenceObject.objectId;

  void _selectObject(String objectId) {
    final onSelectObject = widget.onSelectObject;
    if (onSelectObject != null) {
      onSelectObject(objectId);
      return;
    }
    setState(() => _selectedObjectId = objectId);
  }

  @override
  Widget build(BuildContext context) {
    final presentation = CustomerReviewPresentation.fromDrafts(
      widget.state.objectDrafts,
    );
    final selectedObjectId = widget.onSelectObject == null
        ? _selectedObjectId
        : widget.selectedObjectId;
    final selectedDraft = selectedObjectId == null
        ? null
        : _draftFor(widget.state, selectedObjectId);
    final unresolvedCount = widget.state.objectDrafts
        .where((draft) => !draft.isResolved)
        .length;
    final allResolved = unresolvedCount == 0;
    final confirmedCount = widget.state.objectDrafts.length - unresolvedCount;
    return CheckoutReviewWorkspace(
      state: widget.state,
      presentation: presentation,
      selectedObjectId: selectedObjectId,
      onSelectObject: _selectObject,
      taskTitle: selectedDraft?.isResolved == false
          ? '${presentation.objects.where((item) => item.objectId == selectedObjectId).firstOrNull?.numberLabel ?? ''}번 · 상품 확인 필요'
          : '주문 내역',
      taskContent: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _ReviewProgress(
            totalCount: widget.state.objectDrafts.length,
            confirmedCount: confirmedCount,
            unresolvedCount: unresolvedCount,
          ),
          const SizedBox(height: 12),
          Expanded(
            child: _ReviewTaskPane(
              presentation: presentation,
              state: widget.state,
              selectedObjectId: selectedObjectId,
              selectedDraft: selectedDraft,
              onSelectObject: _selectObject,
              productForCandidate: widget.productForCandidate,
              onChooseTop3: widget.onChooseTop3,
              onOpenCatalog: widget.onOpenCatalog,
              onRetakeCapture: widget.onRetakeCapture,
              catalogDiscovery: widget.catalogDiscovery,
              catalogSearch: widget.catalogSearch,
              onCatalogSelected: widget.onCatalogSelected,
              onCloseCatalog: widget.onCloseCatalog,
            ),
          ),
        ],
      ),
      primaryActionLabel: allResolved ? '주문 확인' : '확인할 빵 $unresolvedCount개 남음',
      onPrimaryAction: allResolved ? widget.onContinue : null,
      imageProviderFactory: widget.imageProviderFactory,
      legacySceneKey: const Key('customer-review-scene-pane'),
      legacyTaskKey: const Key('customer-review-task-pane'),
      legacyDividerKey: const Key('customer-review-workspace-divider'),
    );
  }
}

class _ReviewProgress extends StatelessWidget {
  const _ReviewProgress({
    required this.totalCount,
    required this.confirmedCount,
    required this.unresolvedCount,
  });

  final int totalCount;
  final int confirmedCount;
  final int unresolvedCount;

  @override
  Widget build(BuildContext context) {
    final allResolved = unresolvedCount == 0;
    return Semantics(
      key: const Key('customer-review-progress'),
      container: true,
      label: allResolved
          ? '\uBE75 $totalCount\uAC1C \uD655\uC778 \uC644\uB8CC'
          : '\uBE75 $totalCount\uAC1C \uC911 $confirmedCount\uAC1C \uD655\uC778, $unresolvedCount\uAC1C \uD655\uC778 \uD544\uC694',
      child: ExcludeSemantics(
        child: Row(
          children: [
            Icon(
              allResolved
                  ? Icons.check_circle
                  : Icons.tips_and_updates_outlined,
              color: allResolved
                  ? BixolonThemeExtension.of(context).confirmed
                  : BixolonThemeExtension.of(context).uncertainty,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                allResolved
                    ? '\uBE75 $totalCount\uAC1C\uB97C \uBAA8\uB450 \uD655\uC778\uD588\uC5B4\uC694'
                    : '\uBE75 $totalCount\uAC1C \uC911 $confirmedCount\uAC1C\uB97C \uCC3E\uC558\uC5B4\uC694. $unresolvedCount\uAC1C\uB9CC \uD655\uC778\uD574 \uC8FC\uC138\uC694.',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReviewTaskPane extends StatelessWidget {
  const _ReviewTaskPane({
    required this.presentation,
    required this.state,
    required this.selectedObjectId,
    required this.selectedDraft,
    required this.onSelectObject,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onRetakeCapture,
    required this.catalogDiscovery,
    required this.catalogSearch,
    required this.onCatalogSelected,
    required this.onCloseCatalog,
  });

  final CustomerReviewPresentation presentation;
  final CheckoutState state;
  final String? selectedObjectId;
  final ObjectDraft? selectedDraft;
  final ValueChanged<String> onSelectObject;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback? onRetakeCapture;
  final CustomerCatalogDiscovery? catalogDiscovery;
  final Future<List<Product>> Function(String query)? catalogSearch;
  final ValueChanged<Product>? onCatalogSelected;
  final VoidCallback? onCloseCatalog;

  ObjectDraft? _draftFor(String objectId) {
    for (final draft in state.objectDrafts) {
      if (draft.inferenceObject.objectId == objectId) return draft;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final selectedItems = presentation.objects
        .where((item) => item.objectId == selectedObjectId)
        .toList(growable: false);
    final selectedItem = selectedItems.firstOrNull;
    final activeDraft = selectedDraft;
    final catalog = catalogDiscovery;
    final searchCatalog = catalogSearch;
    final selectCatalog = onCatalogSelected;
    return catalog != null && searchCatalog != null && selectCatalog != null
        ? SingleChildScrollView(
            padding: const EdgeInsets.only(left: 4),
            child: CatalogPicker(
              discovery: catalog,
              search: searchCatalog,
              onSelected: selectCatalog,
              onClose: onCloseCatalog,
            ),
          )
        : SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(4, 0, 0, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final item in presentation.objects)
                  if (_draftFor(item.objectId) case final draft?)
                    if (draft.isResolved) ...[
                      _ReviewLedgerRow(
                        item: item,
                        draft: draft,
                        selected: item.objectId == selectedObjectId,
                        onTap: () => onSelectObject(item.objectId),
                      ),
                      Divider(color: tokens.divider, height: 1),
                    ],
                if (selectedItem != null &&
                    activeDraft != null &&
                    !activeDraft.isResolved) ...[
                  _ReviewLedgerRow(
                    item: selectedItem,
                    draft: activeDraft,
                    selected: true,
                    onTap: () => onSelectObject(selectedItem.objectId),
                  ),
                  Divider(color: tokens.divider, height: 1),
                  const SizedBox(height: 12),
                  _SelectedObjectActions(
                    item: selectedItem,
                    draft: activeDraft,
                    productForCandidate: productForCandidate,
                    onChooseTop3: onChooseTop3,
                    onOpenCatalog: onOpenCatalog,
                    onRetakeCapture: onRetakeCapture,
                  ),
                ],
              ],
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
  final ObjectDraft draft;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final confirmed = draft.isResolved;
    return ListTile(
      key: Key('customer-review-row-${item.objectId}'),
      dense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      horizontalTitleGap: 8,
      selected: selected,
      selectedTileColor: tokens.selectedSurface,
      leading: Icon(
        confirmed ? Icons.check_circle : Icons.help_outline,
        color: confirmed ? tokens.confirmed : tokens.uncertainty,
        size: 20,
      ),
      title: Text(
        confirmed
            ? draft.product!.displayName
            : '${item.numberLabel}번 · 상품 확인 필요',
        maxLines: 1,
        style: Theme.of(context).textTheme.labelLarge,
      ),
      subtitle: Text(
        confirmed
            ? '${item.numberLabel}번 · 개당 ${PriceText.formatKrw(draft.product!.unitPrice)}'
            : '아래 후보 중에서 선택해 주세요',
        maxLines: 1,
      ),
      onTap: onTap,
    );
  }
}

class _SelectedObjectActions extends StatelessWidget {
  const _SelectedObjectActions({
    required this.item,
    required this.draft,
    required this.productForCandidate,
    required this.onChooseTop3,
    required this.onOpenCatalog,
    required this.onRetakeCapture,
  });

  final CustomerReviewObject item;
  final ObjectDraft draft;
  final Product? Function(String objectId, int skuId) productForCandidate;
  final void Function(String objectId, int skuId) onChooseTop3;
  final ValueChanged<String> onOpenCatalog;
  final VoidCallback? onRetakeCapture;

  @override
  Widget build(BuildContext context) {
    final objectId = draft.inferenceObject.objectId;
    if (draft.isResolved) {
      return Column(
        key: Key('customer-review-selected-panel-$objectId'),
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('선택한 상품: ${draft.product!.displayName}'),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => onOpenCatalog(objectId),
            icon: const Icon(Icons.edit_outlined),
            label: const Text('변경'),
          ),
        ],
      );
    }
    return Column(
      key: Key('customer-review-candidate-panel-$objectId'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          draft.requiresCatalogSelection
              ? '\uC774 \uBE75\uC740 \uCD94\uCC9C \uD6C4\uBCF4\uAC00 \uC5C6\uC5B4\uC694.'
              : '\uAC00\uC7A5 \uBE44\uC2B7\uD55C \uC0C1\uD488\uC774\uC5D0\uC694.',
        ),
        const SizedBox(height: 12),
        if (!draft.requiresCatalogSelection)
          for (final (index, candidate) in draft.candidates.indexed)
            if (productForCandidate(objectId, candidate.skuId)
                case final product?) ...[
              OutlinedButton(
                onPressed: () => onChooseTop3(objectId, candidate.skuId),
                style: OutlinedButton.styleFrom(
                  alignment: Alignment.centerLeft,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                ),
                child: Row(
                  children: [
                    SizedBox(
                      width: 52,
                      child: Text(
                        'Top ${index + 1}',
                        style: Theme.of(context).textTheme.labelMedium,
                      ),
                    ),
                    if (product.displayName != 'Top ${index + 1}')
                      Expanded(child: Text(product.displayName))
                    else
                      const Spacer(),
                    PriceText(amount: product.unitPrice),
                    const SizedBox(width: 8),
                    const Icon(Icons.chevron_right),
                  ],
                ),
              ),
              const SizedBox(height: 8),
            ],
        TextButton.icon(
          onPressed: () => onOpenCatalog(objectId),
          icon: const Icon(Icons.search),
          label: const Text('\uB2E4\uB978 \uC0C1\uD488 \uCC3E\uAE30'),
        ),
        if (onRetakeCapture != null)
          TextButton.icon(
            onPressed: onRetakeCapture,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text(
              '\uBE75\uC744 \uB2E4\uC2DC \uB193\uACE0 \uCD2C\uC601',
            ),
          ),
      ],
    );
  }
}
