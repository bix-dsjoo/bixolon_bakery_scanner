import '../catalog/product.dart';
import '../checkout/checkout_ports.dart';
import 'package:drift/drift.dart';

import 'app_database.dart';

final class DatabaseCatalogRepository implements CatalogRepository {
  const DatabaseCatalogRepository(this._database);

  final BakeryDatabase _database;

  @override
  Future<CatalogSnapshot> activeCatalog() async {
    final revisions = await (_database.select(
      _database.catalogRevisions,
    )..where((row) => row.isActive.equals(true))).get();
    if (revisions.length != 1) {
      throw StateError(
        'exactly one active catalog revision is required; '
        'found ${revisions.length}',
      );
    }
    final revision = revisions.single;
    final rows =
        await (_database.select(_database.products)
              ..where(
                (row) =>
                    row.catalogRevisionId.equals(revision.revisionId) &
                    row.active.equals(true),
              )
              ..orderBy([
                (row) => OrderingTerm.asc(row.sortOrder),
                (row) => OrderingTerm.asc(row.productId),
              ]))
            .get();
    return CatalogSnapshot(
      revision: _revision(revision),
      products: rows.map(_product).toList(growable: false),
    );
  }

  @override
  Future<CustomerCatalogDiscovery> customerDiscovery() async {
    final catalog = await activeCatalog();
    return CustomerCatalogDiscovery(
      catalog: catalog,
      featuredProducts: catalog.products.take(6).toList(growable: false),
    );
  }

  @override
  Future<Product?> productForRecognitionSku(int recognitionSkuId) async {
    if (recognitionSkuId < 1 || recognitionSkuId > 20) {
      throw ArgumentError.value(
        recognitionSkuId,
        'recognitionSkuId',
        'must be between 1 and 20',
      );
    }
    final catalog = await activeCatalog();
    final matches = catalog.products
        .where((product) => product.recognitionSkuId == recognitionSkuId)
        .toList(growable: false);
    if (matches.length > 1) {
      throw StateError(
        'catalog ${catalog.revision.revisionId} maps recognition SKU '
        '$recognitionSkuId more than once',
      );
    }
    return matches.firstOrNull;
  }

  @override
  Future<List<Product>> search(String query) async {
    final normalized = query.trim().toLowerCase();
    final catalog = await activeCatalog();
    if (normalized.isEmpty) return catalog.products;
    return catalog.products
        .where(
          (product) =>
              product.displayName.toLowerCase().contains(normalized) ||
              product.productId.toLowerCase().contains(normalized) ||
              product.categoryId.toLowerCase().contains(normalized),
        )
        .toList(growable: false);
  }

  CatalogRevision _revision(CatalogRevisionRow row) => CatalogRevision(
    revisionId: row.revisionId,
    sha256: row.sha256,
    createdAt: DateTime.fromMicrosecondsSinceEpoch(
      row.createdAtUs,
      isUtc: true,
    ),
  );

  Product _product(ProductRow row) => Product(
    productId: row.productId,
    displayName: row.displayName,
    unitPrice: row.unitPriceKrw,
    recognitionSkuId: row.recognitionSkuId,
    categoryId: row.categoryId,
    photoAssetPath: row.photoRelativePath,
    active: row.active,
    sortOrder: row.sortOrder,
  );
}
