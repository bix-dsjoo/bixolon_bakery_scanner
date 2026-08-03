import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../components/price_text.dart';

/// Customer catalog only. It has no inference dependency and deliberately
/// renders a neutral package fallback when the approved catalog photo is absent.
class CatalogPicker extends StatefulWidget {
  const CatalogPicker({
    required this.discovery,
    required this.search,
    required this.onSelected,
    this.onClose,
    this.closeFocusNode,
    super.key,
  });

  final CustomerCatalogDiscovery discovery;
  final Future<List<Product>> Function(String query) search;
  final ValueChanged<Product> onSelected;
  final VoidCallback? onClose;
  final FocusNode? closeFocusNode;

  @override
  State<CatalogPicker> createState() => _CatalogPickerState();
}

class _CatalogPickerState extends State<CatalogPicker> {
  final _search = TextEditingController();
  List<Product>? _searched;
  String? _category;

  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _searchProducts(String query) async {
    final results = await widget.search(query);
    if (mounted) setState(() => _searched = results);
  }

  @override
  Widget build(BuildContext context) {
    final discovery = widget.discovery;
    final all = _searched ?? discovery.catalog.products;
    final categories = all.map((product) => product.categoryId).toSet().toList()
      ..sort();
    final visible = _category == null
        ? all
        : all.where((product) => product.categoryId == _category).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            IconButton(
              key: const Key('customer-catalog-close'),
              focusNode: widget.closeFocusNode,
              tooltip:
                  '\uC0C1\uD488 \uD655\uC778\uC73C\uB85C \uB3CC\uC544\uAC00\uAE30',
              onPressed:
                  widget.onClose ?? () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.arrow_back),
            ),
            const SizedBox(width: 8),
            Text(
              '\uB2E4\uB978 \uC0C1\uD488 \uCC3E\uAE30',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _search,
          onChanged: _searchProducts,
          decoration: const InputDecoration(
            labelText: '상품 이름 검색',
            prefixIcon: Icon(Icons.search),
          ),
        ),
        const SizedBox(height: 16),
        if (_search.text.isEmpty) ...[
          Text('자주 담는 빵', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final product in discovery.featuredProducts)
                ActionChip(
                  label: Text(product.displayName),
                  onPressed: () => widget.onSelected(product),
                ),
            ],
          ),
          const SizedBox(height: 16),
        ],
        Text('종류', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            ChoiceChip(
              label: const Text('전체'),
              selected: _category == null,
              onSelected: (_) => setState(() => _category = null),
            ),
            for (final category in categories)
              ChoiceChip(
                label: Text(_customerCategoryLabel(category)),
                selected: _category == category,
                onSelected: (_) => setState(() => _category = category),
              ),
          ],
        ),
        const SizedBox(height: 16),
        Text('전체 상품', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final product in visible)
          _CatalogRow(product: product, onSelected: widget.onSelected),
      ],
    );
  }
}

class _CatalogRow extends StatelessWidget {
  const _CatalogRow({required this.product, required this.onSelected});

  final Product product;
  final ValueChanged<Product> onSelected;

  @override
  Widget build(BuildContext context) => ListTile(
    leading: product.photoAssetPath == null
        ? const CircleAvatar(child: Icon(Icons.bakery_dining_outlined))
        : Image.asset(product.photoAssetPath!, fit: BoxFit.cover),
    title: Text(product.displayName),
    subtitle: Text(_customerCategoryLabel(product.categoryId)),
    trailing: PriceText(amount: product.unitPrice),
    onTap: () => onSelected(product),
  );
}

String _customerCategoryLabel(String categoryId) => switch (categoryId) {
  'bread' => '빵',
  'donut' => '\uB3C4\uB11B',
  'filled-bread' => '\uC18C\uAC00 \uB4E0 \uBE75',
  'loaf' => '\uC2DD\uBE75',
  'pastry' => '\uD398\uC774\uC2A4\uD2B8\uB9AC',
  'rustic-bread' => '\uD558\uB4DC\uACC4 \uBE75',
  'sweet' => '\uB2EC\uCF64\uD55C \uBE75',
  'savory' => '\uC2DD\uC0AC\uBE75',
  'sandwich' => '샌드위치',
  _ => categoryId,
};
