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
  Future<CustomerCatalogDiscovery> customerDiscoveryFor(
    CatalogSnapshot catalog,
  ) async {
    final countsByRevisionProduct = <String, int>{};
    final completedOrderLines =
        await (_database.select(_database.finalOrderLines).join([
          innerJoin(
            _database.finalOrders,
            _database.finalOrders.orderId.equalsExp(
              _database.finalOrderLines.orderId,
            ),
          ),
          innerJoin(
            _database.checkoutSessions,
            _database.checkoutSessions.sessionId.equalsExp(
              _database.finalOrders.sessionId,
            ),
          ),
        ])..where(_database.checkoutSessions.state.equals('completed'))).get();
    for (final row in completedOrderLines) {
      final line = row.readTable(_database.finalOrderLines);
      countsByRevisionProduct.update(
        line.productRevisionId,
        (count) => count + line.quantity,
        ifAbsent: () => line.quantity,
      );
    }
    final featuredProducts = [...catalog.products]
      ..sort((left, right) {
        final leftCount =
            countsByRevisionProduct['${catalog.revision.revisionId}/${left.productId}'] ??
            0;
        final rightCount =
            countsByRevisionProduct['${catalog.revision.revisionId}/${right.productId}'] ??
            0;
        final frequency = rightCount.compareTo(leftCount);
        return frequency == 0 ? Product.customerSort(left, right) : frequency;
      });
    return CustomerCatalogDiscovery(
      catalog: catalog,
      featuredProducts: featuredProducts.take(6).toList(growable: false),
    );
  }

  Future<CustomerCatalogDiscovery> customerDiscovery() async =>
      customerDiscoveryFor(await activeCatalog());

  /// Includes inactive products for the administrator only. It intentionally
  /// resolves one frozen active revision and never changes a live checkout
  /// snapshot.
  Future<ManagedCatalogSnapshot> activeCatalogForManagement() async {
    final revisions = await (_database.select(
      _database.catalogRevisions,
    )..where((row) => row.isActive.equals(true))).get();
    if (revisions.length != 1) {
      throw StateError('exactly one active catalog revision is required');
    }
    final revision = revisions.single;
    final rows =
        await (_database.select(_database.products)
              ..where(
                (row) => row.catalogRevisionId.equals(revision.revisionId),
              )
              ..orderBy([
                (row) => OrderingTerm.asc(row.sortOrder),
                (row) => OrderingTerm.asc(row.productId),
              ]))
            .get();
    return ManagedCatalogSnapshot(
      revision: _revision(revision),
      products: List.unmodifiable(rows.map(_managedProduct)),
    );
  }

  @override
  Future<Product?> productForRecognitionSku(int recognitionSkuId) async {
    if (recognitionSkuId < 1 || recognitionSkuId > 20) {
      return null;
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

  Future<List<Product>> search(String query) async {
    final catalog = await activeCatalog();
    return catalog.search(query);
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

  ManagedCatalogProduct _managedProduct(ProductRow row) =>
      ManagedCatalogProduct(
        productId: row.productId,
        displayName: row.displayName,
        unitPriceKrw: row.unitPriceKrw,
        recognitionSkuId: row.recognitionSkuId,
        categoryId: row.categoryId,
        active: row.active,
        sortOrder: row.sortOrder,
        photoAssetPath: row.photoRelativePath,
        photoByteSize: row.photoByteSize,
        photoSha256: row.photoSha256,
        photoMediaType: row.photoMediaType,
        photoProvenanceNote: row.photoProvenanceNote,
      );
}
