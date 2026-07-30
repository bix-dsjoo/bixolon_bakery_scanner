import 'package:flutter/material.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_ports.dart';
import '../components/price_text.dart';

/// Customer catalog only. It has no inference dependency and deliberately
/// renders a neutral package fallback when the approved catalog photo is absent.
class CatalogPicker extends StatefulWidget {
  const CatalogPicker({
    required this.catalog,
    required this.onSelected,
    super.key,
  });

  final CatalogRepository catalog;
  final ValueChanged<Product> onSelected;

  @override
  State<CatalogPicker> createState() => _CatalogPickerState();
}

class _CatalogPickerState extends State<CatalogPicker> {
  final _search = TextEditingController();
  Future<CustomerCatalogDiscovery>? _discovery;
  List<Product>? _searched;
  String? _category;

  @override
  void initState() {
    super.initState();
    _discovery = widget.catalog.customerDiscovery();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _searchProducts(String query) async {
    final results = await widget.catalog.search(query);
    if (mounted) setState(() => _searched = results);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<CustomerCatalogDiscovery>(
    future: _discovery,
    builder: (context, snapshot) {
      if (!snapshot.hasData) {
        return const Center(child: CircularProgressIndicator());
      }
      final discovery = snapshot.requireData;
      final all = _searched ?? discovery.catalog.products;
      final categories =
          all.map((product) => product.categoryId).toSet().toList()..sort();
      final visible = _category == null
          ? all
          : all.where((product) => product.categoryId == _category).toList();
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
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
                  label: Text(category),
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
    },
  );
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
    subtitle: Text(product.categoryId),
    trailing: PriceText(amount: product.unitPrice),
    onTap: () => onSelected(product),
  );
}
