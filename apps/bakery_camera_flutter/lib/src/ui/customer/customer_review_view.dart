import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import '../bixolon_theme_extension.dart';
import 'captured_review_overlay.dart';
import 'catalog_picker.dart';
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

  void _selectObject(String objectId) =>
      setState(() => _selectedObjectId = objectId);

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
    final confirmedCount = widget.state.objectDrafts.length - unresolvedCount;
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
      title: '\uBE75 \uD655\uC778',
      maxWidth: 1240,
      scrollable: false,
      primaryAction: BakeryPrimaryButton(
        label: allResolved
            ? '\uC8FC\uBB38 \uD655\uC778'
            : '\uD655\uC778\uD560 \uBE75 $unresolvedCount\uAC1C \uB0A8\uC74C',
        onPressed: allResolved ? widget.onContinue : null,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _ReviewProgress(
              totalCount: widget.state.objectDrafts.length,
              confirmedCount: confirmedCount,
              unresolvedCount: unresolvedCount,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final horizontal = constraints.maxWidth >= 760;
                  final scene = _ReviewScenePane(
                    hasCaptureOverlay: hasCaptureOverlay,
                    imagePath: imagePath,
                    imageWidth: imageWidth,
                    imageHeight: imageHeight,
                    presentation: presentation,
                    selectedObjectId: selectedObjectId,
                    onSelectObject: _selectObject,
                    imageProviderFactory: widget.imageProviderFactory,
                  );
                  final tasks = _ReviewTaskPane(
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
                  );
                  if (!horizontal) {
                    return Column(
                      children: [
                        Expanded(flex: 3, child: scene),
                        const SizedBox(height: 12),
                        Expanded(flex: 4, child: tasks),
                      ],
                    );
                  }
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(flex: 3, child: scene),
                      const SizedBox(width: 20),
                      VerticalDivider(
                        key: const Key('customer-review-workspace-divider'),
                        width: 1,
                        thickness: 1,
                      ),
                      const SizedBox(width: 20),
                      Expanded(flex: 2, child: tasks),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
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

class _ReviewScenePane extends StatelessWidget {
  const _ReviewScenePane({
    required this.hasCaptureOverlay,
    required this.imagePath,
    required this.imageWidth,
    required this.imageHeight,
    required this.presentation,
    required this.selectedObjectId,
    required this.onSelectObject,
    required this.imageProviderFactory,
  });

  final bool hasCaptureOverlay;
  final String? imagePath;
  final int? imageWidth;
  final int? imageHeight;
  final CustomerReviewPresentation presentation;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: const Key('customer-review-scene-pane'),
      padding: const EdgeInsets.only(right: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '\uCD2C\uC601\uD55C \uD2B8\uB808\uC774',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Expanded(
            child: Center(
              child: hasCaptureOverlay
                  ? CapturedReviewOverlay(
                      imagePath: imagePath!,
                      imageWidth: imageWidth!,
                      imageHeight: imageHeight!,
                      objects: presentation.objects,
                      selectedObjectId: selectedObjectId,
                      onSelectObject: onSelectObject,
                      imageProviderFactory: imageProviderFactory,
                    )
                  : const _MissingCapture(),
            ),
          ),
        ],
      ),
    );
  }
}

class _MissingCapture extends StatelessWidget {
  const _MissingCapture();

  @override
  Widget build(BuildContext context) => const Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.image_not_supported_outlined),
        SizedBox(height: 8),
        Text(
          '\uCD2C\uC601 \uC774\uBBF8\uC9C0\uB97C \uD45C\uC2DC\uD560 \uC218 \uC5C6\uC5B4\uC694.',
        ),
      ],
    ),
  );
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
    final catalog = catalogDiscovery;
    final searchCatalog = catalogSearch;
    final selectCatalog = onCatalogSelected;
    return KeyedSubtree(
      key: const Key('customer-review-task-pane'),
      child: catalog != null && searchCatalog != null && selectCatalog != null
          ? SingleChildScrollView(
              padding: const EdgeInsets.only(left: 4),
              child: CatalogPicker(
                discovery: catalog,
                search: searchCatalog,
                onSelected: selectCatalog,
                onClose: onCloseCatalog,
              ),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
                  child: Text(
                    selectedDraft?.isResolved == false
                        ? '${selectedItem?.numberLabel ?? ''}\uBC88 \uBE75\uB9CC \uD655\uC778\uD574 \uC8FC\uC138\uC694'
                        : '\uC778\uC2DD\uD55C \uBE75',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                SizedBox(
                  height: 64,
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final objects = presentation.objects;
                      if (objects.length <= 5) {
                        const horizontalPadding = 8.0;
                        const gap = 4.0;
                        final width =
                            (constraints.maxWidth -
                                (horizontalPadding * 2) -
                                (gap * (objects.length - 1))) /
                            objects.length;
                        return Padding(
                          padding: const EdgeInsets.only(
                            right: horizontalPadding,
                          ),
                          child: Row(
                            children: [
                              for (
                                var index = 0;
                                index < objects.length;
                                index++
                              ) ...[
                                if (index > 0) const SizedBox(width: gap),
                                _ReviewLedgerRow(
                                  width: width,
                                  item: objects[index],
                                  draft: _draftFor(objects[index].objectId),
                                  selected:
                                      objects[index].objectId ==
                                      selectedObjectId,
                                  onTap: () =>
                                      onSelectObject(objects[index].objectId),
                                ),
                              ],
                            ],
                          ),
                        );
                      }
                      return ListView.separated(
                        padding: const EdgeInsets.only(right: 8),
                        scrollDirection: Axis.horizontal,
                        itemCount: objects.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 4),
                        itemBuilder: (context, index) {
                          final item = objects[index];
                          return _ReviewLedgerRow(
                            width: 96,
                            item: item,
                            draft: _draftFor(item.objectId),
                            selected: item.objectId == selectedObjectId,
                            onTap: () => onSelectObject(item.objectId),
                          );
                        },
                      );
                    },
                  ),
                ),
                Divider(color: tokens.divider),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(4, 4, 0, 12),
                    child: selectedItem == null || selectedDraft == null
                        ? const SizedBox.shrink()
                        : selectedDraft!.isResolved
                        ? _ResolvedObjectSummary(draft: selectedDraft!)
                        : _SelectedObjectActions(
                            item: selectedItem,
                            draft: selectedDraft!,
                            productForCandidate: productForCandidate,
                            onChooseTop3: onChooseTop3,
                            onOpenCatalog: onOpenCatalog,
                            onRetakeCapture: onRetakeCapture,
                          ),
                  ),
                ),
              ],
            ),
    );
  }
}

class _ReviewLedgerRow extends StatelessWidget {
  const _ReviewLedgerRow({
    required this.width,
    required this.item,
    required this.draft,
    required this.selected,
    required this.onTap,
  });

  final double width;
  final CustomerReviewObject item;
  final ObjectDraft? draft;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final confirmed = draft?.isResolved ?? false;
    return SizedBox(
      width: width,
      child: ListTile(
        key: Key('customer-review-row-${item.objectId}'),
        dense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 6),
        horizontalTitleGap: 4,
        selected: selected,
        selectedTileColor: tokens.selectedSurface,
        leading: Icon(
          confirmed ? Icons.check_circle : Icons.help_outline,
          color: confirmed ? tokens.confirmed : tokens.uncertainty,
          size: 20,
        ),
        title: Text(
          '${item.numberLabel}\uBC88',
          maxLines: 1,
          style: Theme.of(context).textTheme.labelLarge,
        ),
        subtitle: Text(
          confirmed ? '\uD655\uC778' : '\uD655\uC778 \uD544\uC694',
          maxLines: 1,
        ),
        onTap: onTap,
      ),
    );
  }
}

class _ResolvedObjectSummary extends StatelessWidget {
  const _ResolvedObjectSummary({required this.draft});

  final ObjectDraft draft;

  @override
  Widget build(BuildContext context) {
    final product = draft.product!;
    final tokens = BixolonThemeExtension.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: tokens.confirmed),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '\uC790\uB3D9\uC73C\uB85C \uD655\uC778\uD588\uC5B4\uC694',
                ),
                const SizedBox(height: 4),
                Text(
                  product.displayName,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
          ),
          PriceText(amount: product.unitPrice),
        ],
      ),
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
    if (draft.isResolved) return const SizedBox.shrink();
    final objectId = draft.inferenceObject.objectId;
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
          for (final candidate in draft.candidates)
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
                    Expanded(child: Text(product.displayName)),
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
