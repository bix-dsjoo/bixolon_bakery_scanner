import 'package:flutter/material.dart';

import '../../admin/product_management_service.dart';
import '../../catalog/product.dart';
import '../bixolon_theme_extension.dart';
import 'product_editor_screen.dart';

/// Catalog administration emphasizes the facts a shopper sees. The optional
/// recognition mapping and photo provenance are disclosure-only evidence.
final class ProductManagementScreen extends StatefulWidget {
  const ProductManagementScreen({required this.service, super.key});

  final ProductManagementService service;

  @override
  State<ProductManagementScreen> createState() =>
      _ProductManagementScreenState();
}

class _ProductManagementScreenState extends State<ProductManagementScreen> {
  ManagedCatalogSnapshot? _catalog;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final catalog = await widget.service.activeCatalog();
      if (!mounted) return;
      setState(() {
        _catalog = catalog;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _openEditor([ManagedCatalogProduct? product]) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) =>
            ProductEditorScreen(service: widget.service, product: product),
      ),
    );
    if (mounted) {
      await _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _catalog == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              '\uC0C1\uD488 \uC815\uBCF4\uB97C \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.',
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _reload,
              child: const Text('\uB2E4\uC2DC \uC2DC\uB3C4'),
            ),
          ],
        ),
      );
    }
    final catalog = _catalog!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '\uBC14\uAFB8\uBA74 \uB2E4\uC74C \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9\uB429\uB2C8\uB2E4. \uC774\uBBF8 \uACB0\uC81C\uB41C \uC8FC\uBB38\uC740 \uBC14\uB00C\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            key: const Key('product-add'),
            onPressed: () => _openEditor(),
            icon: const Icon(Icons.add),
            label: const Text('\uC0C1\uD488 \uCD94\uAC00'),
          ),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: ListView.separated(
            itemCount: catalog.products.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (context, index) => _ProductCard(
              product: catalog.products[index],
              service: widget.service,
              onEdit: () => _openEditor(catalog.products[index]),
            ),
          ),
        ),
      ],
    );
  }
}

class _ProductCard extends StatelessWidget {
  const _ProductCard({
    required this.product,
    required this.service,
    required this.onEdit,
  });

  final ManagedCatalogProduct product;
  final ProductManagementService service;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ProductPhoto(
                  service: service,
                  product: product,
                  tokens: tokens,
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        product.displayName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(_krw(product.unitPriceKrw)),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 6,
                        children: [
                          Chip(
                            avatar: Icon(
                              product.active
                                  ? Icons.check_circle_outline
                                  : Icons.pause_circle_outline,
                              size: 18,
                            ),
                            label: Text(
                              product.active
                                  ? '\uD310\uB9E4 \uAC00\uB2A5'
                                  : '\uD310\uB9E4 \uC911\uC9C0',
                            ),
                          ),
                          Chip(
                            label: Text(
                              product.active && product.recognitionSkuId != null
                                  ? 'AI \uC5F0\uACB0\uB428'
                                  : '\uC9C1\uC811 \uC120\uD0DD \uC804\uC6A9',
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: '\uC0C1\uD488 \uC218\uC815',
                  onPressed: onEdit,
                  icon: const Icon(Icons.edit_outlined),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('\uC0C1\uC138 \uC815\uBCF4'),
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Model SKU mapping'),
                  subtitle: Text(
                    product.recognitionSkuId?.toString() ??
                        '\uC9C1\uC811 \uC120\uD0DD \uC804\uC6A9',
                  ),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('\uC0AC\uC9C4 \uCD9C\uCC98'),
                  subtitle: Text(
                    product.photoProvenanceNote ??
                        '\uB4F1\uB85D\uB41C \uC0C1\uD488 \uC0AC\uC9C4\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.',
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ProductPhoto extends StatelessWidget {
  const _ProductPhoto({
    required this.service,
    required this.product,
    required this.tokens,
  });

  final ProductManagementService service;
  final ManagedCatalogProduct product;
  final BixolonThemeExtension tokens;

  @override
  Widget build(BuildContext context) => FutureBuilder(
    future: service.resolvePhoto(product),
    builder: (context, snapshot) {
      final file = snapshot.data;
      return Container(
        width: 56,
        height: 56,
        clipBehavior: Clip.antiAlias,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: tokens.canvas,
          borderRadius: BorderRadius.circular(8),
        ),
        child: snapshot.hasError
            ? Semantics(
                label:
                    '\uC0C1\uD488 \uC0AC\uC9C4 \uBB34\uACB0\uC131 \uC624\uB958',
                child: const Tooltip(
                  message: '\uC0AC\uC9C4 \uBB34\uACB0\uC131 \uC624\uB958',
                  child: Icon(Icons.broken_image_outlined),
                ),
              )
            : file == null
            ? const Icon(
                Icons.bakery_dining_outlined,
                semanticLabel: '\uC0C1\uD488 \uC0AC\uC9C4 \uC5C6\uC74C',
              )
            : Image.file(
                file,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => Semantics(
                  label:
                      '\uC0C1\uD488 \uC0AC\uC9C4 \uBB34\uACB0\uC131 \uC624\uB958',
                  child: const Icon(Icons.broken_image_outlined),
                ),
              ),
      );
    },
  );
}

String _krw(int value) {
  final chars = value.toString().split('').reversed.toList(growable: false);
  final pieces = <String>[];
  for (var index = 0; index < chars.length; index += 3) {
    pieces.add(
      chars.skip(index).take(3).toList(growable: false).reversed.join(),
    );
  }
  return '${pieces.reversed.join(',')}\uC6D0';
}
