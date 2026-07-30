/// A sellable catalog item whose identity is intentionally distinct from an
/// optional recognition-model SKU identity.
final class Product {
  Product({
    required this.productId,
    required this.displayName,
    required this.unitPrice,
    required this.recognitionSkuId,
    required this.categoryId,
    required this.photoAssetPath,
    required this.active,
    required this.sortOrder,
  }) : assert(productId != ''),
       assert(displayName != ''),
       assert(recognitionSkuId == null || recognitionSkuId > 0),
       assert(categoryId != ''),
       assert(photoAssetPath == null || photoAssetPath != ''),
       assert(sortOrder >= 0) {
    if (unitPrice < 0) {
      throw ArgumentError.value(unitPrice, 'unitPrice', 'must be non-negative');
    }
  }

  final String productId;
  final String displayName;
  final int unitPrice;
  final int? recognitionSkuId;
  final String categoryId;
  final String? photoAssetPath;
  final bool active;
  final int sortOrder;

  static int customerSort(Product left, Product right) {
    final sortOrder = left.sortOrder.compareTo(right.sortOrder);
    if (sortOrder != 0) return sortOrder;
    return left.productId.compareTo(right.productId);
  }
}

final class CatalogRevision {
  const CatalogRevision({
    required this.revisionId,
    required this.sha256,
    required this.createdAt,
  }) : assert(revisionId != ''),
       assert(sha256 != '');

  final String revisionId;
  final String sha256;
  final DateTime createdAt;
}

final class CatalogSnapshot {
  CatalogSnapshot({required this.revision, required List<Product> products})
    : products = List.unmodifiable(products);

  final CatalogRevision revision;
  final List<Product> products;

  /// Searches only the immutable product revision captured for a checkout.
  /// Customer discovery must never re-read a newly activated catalog mid-sale.
  List<Product> search(String query) {
    final normalized = _normalizeSearch(query);
    final matches =
        products
            .where(
              (product) =>
                  product.active &&
                  (normalized.isEmpty ||
                      _normalizeSearch(
                        product.displayName,
                      ).contains(normalized)),
            )
            .toList(growable: false)
          ..sort(Product.customerSort);
    return List.unmodifiable(matches);
  }

  static String _normalizeSearch(String value) =>
      value.trim().toLowerCase().replaceAll(' ', '');
}

final class CustomerCatalogDiscovery {
  CustomerCatalogDiscovery({
    required this.catalog,
    required List<Product> featuredProducts,
  }) : featuredProducts = List.unmodifiable(featuredProducts);

  final CatalogSnapshot catalog;
  final List<Product> featuredProducts;
}
