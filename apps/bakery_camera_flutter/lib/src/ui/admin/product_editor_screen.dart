import 'package:flutter/material.dart';

import '../../admin/product_management_service.dart';
import '../../catalog/product.dart';

/// Minimal editor intentionally avoids model controls. Photo import is a
/// separately verified local-file service operation, never a generated or scan
/// artifact picker.
final class ProductEditorScreen extends StatefulWidget {
  const ProductEditorScreen({required this.service, this.product, super.key});

  final ProductManagementService service;
  final ManagedCatalogProduct? product;

  @override
  State<ProductEditorScreen> createState() => _ProductEditorScreenState();
}

class _ProductEditorScreenState extends State<ProductEditorScreen> {
  late final TextEditingController _id;
  late final TextEditingController _name;
  late final TextEditingController _price;
  late final TextEditingController _category;
  late final TextEditingController _sortOrder;
  bool _active = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final product = widget.product;
    _id = TextEditingController(text: product?.productId ?? '');
    _name = TextEditingController(text: product?.displayName ?? '');
    _price = TextEditingController(
      text: product?.unitPriceKrw.toString() ?? '',
    );
    _category = TextEditingController(text: product?.categoryId ?? 'bread');
    _sortOrder = TextEditingController(
      text: product?.sortOrder.toString() ?? '0',
    );
    _active = product?.active ?? true;
  }

  @override
  void dispose() {
    _id.dispose();
    _name.dispose();
    _price.dispose();
    _category.dispose();
    _sortOrder.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final price = int.tryParse(_price.text.trim());
    final sortOrder = int.tryParse(_sortOrder.text.trim());
    if (price == null || sortOrder == null) {
      setState(
        () => _error =
            '\uAC00\uACA9\uACFC \uC21C\uC11C\uB97C \uC22B\uC790\uB85C \uC785\uB825\uD574 \uC8FC\uC138\uC694.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final existing = widget.product;
      await widget.service.save(
        existing == null
            ? ProductDraft.add(
                productId: _id.text,
                displayName: _name.text,
                unitPriceKrw: price,
                categoryId: _category.text,
                sortOrder: sortOrder,
                active: _active,
              )
            : ProductDraft.edit(
                productId: existing.productId,
                displayName: _name.text,
                unitPriceKrw: price,
                categoryId: _category.text,
                sortOrder: sortOrder,
                recognitionSkuId: existing.recognitionSkuId,
                active: _active,
              ),
      );
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on ArgumentError catch (error) {
      if (mounted) {
        setState(
          () => _error =
              error.message?.toString() ??
              '\uC785\uB825 \uAC12\uC744 \uD655\uC778\uD574 \uC8FC\uC138\uC694.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.product == null
            ? '\uC0C1\uD488 \uCD94\uAC00'
            : '\uC0C1\uD488 \uC218\uC815',
      ),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          TextField(
            controller: _id,
            enabled: widget.product == null,
            decoration: const InputDecoration(labelText: '\uC0C1\uD488 ID'),
          ),
          TextField(
            controller: _name,
            decoration: const InputDecoration(
              labelText:
                  '\uACE0\uAC1D\uC5D0\uAC8C \uBCF4\uC774\uB294 \uC774\uB984',
            ),
          ),
          TextField(
            controller: _price,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: '\uAC00\uACA9 (\uC6D0)',
            ),
          ),
          TextField(
            controller: _category,
            decoration: const InputDecoration(
              labelText: '\uCE74\uD14C\uACE0\uB9AC',
            ),
          ),
          TextField(
            controller: _sortOrder,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: '\uC9C4\uC5F4 \uC21C\uC11C',
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('\uD310\uB9E4 \uAC00\uB2A5'),
            value: _active,
            onChanged: _saving
                ? null
                : (value) => setState(() => _active = value),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(
              _saving ? '\uC800\uC7A5 \uC911' : '\uBCC0\uACBD \uC800\uC7A5',
            ),
          ),
        ],
      ),
    ),
  );
}
