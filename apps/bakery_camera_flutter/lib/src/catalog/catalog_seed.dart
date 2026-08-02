import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';
import 'package:flutter/services.dart';

import '../persistence/app_database.dart';

/// Installs and activates the current immutable prototype catalog revision.
final class CatalogSeed {
  CatalogSeed(this._database, {AssetBundle? assets})
    : _assets = assets ?? rootBundle;

  static const catalogAssetPath = 'assets/catalog/catalog_v1_1_0_r2.json';
  static const sha256AssetPath = 'assets/catalog/catalog_v1_1_0_r2.sha256';

  final BakeryDatabase _database;
  final AssetBundle _assets;

  Future<void> installIfEmpty() async {
    final seed = await _loadAndVerify();
    await _database.transaction(() async {
      final existing = await _database.select(_database.catalogRevisions).get();
      if (existing.any((revision) => revision.revisionId == seed.revisionId)) {
        return;
      }

      await _database
          .update(_database.catalogRevisions)
          .write(const CatalogRevisionsCompanion(isActive: Value(false)));

      await _database
          .into(_database.catalogRevisions)
          .insert(
            CatalogRevisionsCompanion.insert(
              revisionId: seed.revisionId,
              sha256: seed.sha256,
              createdAtUs: 0,
              isActive: true,
            ),
          );
      await _database.batch((batch) {
        batch.insertAll(
          _database.products,
          seed.products
              .map(
                (product) => ProductsCompanion.insert(
                  productRevisionId: '${seed.revisionId}/${product.productId}',
                  catalogRevisionId: seed.revisionId,
                  productId: product.productId,
                  displayName: product.displayName,
                  unitPriceKrw: product.unitPrice,
                  recognitionSkuId: Value(product.recognitionSkuId),
                  categoryId: product.categoryId,
                  active: product.active,
                  sortOrder: product.sortOrder,
                ),
              )
              .toList(growable: false),
        );
      });
    });
  }

  Future<_CatalogSeedDocument> _loadAndVerify() async {
    final data = await _assets.load(catalogAssetPath);
    final bytes = Uint8List.sublistView(
      data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
    );
    final observedSha256 = sha256.convert(bytes).toString();
    final expectedSha256 = (await _assets.loadString(sha256AssetPath)).trim();
    if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(expectedSha256) ||
        expectedSha256 != observedSha256) {
      throw StateError('catalog seed SHA-256 verification failed');
    }

    final decoded = jsonDecode(utf8.decode(bytes));
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('catalog seed must be a JSON object');
    }
    if (decoded['revision_id'] != 'catalog-v1.1.0-r4' ||
        decoded['currency'] != 'KRW') {
      throw const FormatException('catalog seed has an unsupported revision');
    }
    final products = decoded['products'];
    if (products is! List || products.isEmpty) {
      throw const FormatException('catalog seed must declare products');
    }
    return _CatalogSeedDocument(
      revisionId: decoded['revision_id'] as String,
      sha256: observedSha256,
      products: products
          .map((product) => _SeedProduct.fromJson(product))
          .toList(growable: false),
    );
  }
}

final class _CatalogSeedDocument {
  const _CatalogSeedDocument({
    required this.revisionId,
    required this.sha256,
    required this.products,
  });

  final String revisionId;
  final String sha256;
  final List<_SeedProduct> products;
}

final class _SeedProduct {
  const _SeedProduct({
    required this.productId,
    required this.displayName,
    required this.unitPrice,
    required this.recognitionSkuId,
    required this.categoryId,
    required this.active,
    required this.sortOrder,
  });

  factory _SeedProduct.fromJson(Object? value) {
    if (value is! Map<String, dynamic> || value['photo_asset_path'] != null) {
      throw const FormatException(
        'catalog seed products must not include product photography',
      );
    }
    final productId = value['product_id'];
    final displayName = value['display_name'];
    final unitPrice = value['unit_price'];
    final recognitionSkuId = value['recognition_sku_id'];
    final categoryId = value['category_id'];
    final active = value['active'];
    final sortOrder = value['sort_order'];
    if (productId is! String ||
        productId.isEmpty ||
        displayName is! String ||
        displayName.isEmpty ||
        unitPrice is! int ||
        unitPrice < 0 ||
        (recognitionSkuId != null &&
            (recognitionSkuId is! int ||
                recognitionSkuId < 1 ||
                recognitionSkuId > 20)) ||
        categoryId is! String ||
        categoryId.isEmpty ||
        active is! bool ||
        sortOrder is! int ||
        sortOrder < 0) {
      throw const FormatException('catalog seed contains an invalid product');
    }
    return _SeedProduct(
      productId: productId,
      displayName: displayName,
      unitPrice: unitPrice,
      recognitionSkuId: recognitionSkuId as int?,
      categoryId: categoryId,
      active: active,
      sortOrder: sortOrder,
    );
  }

  final String productId;
  final String displayName;
  final int unitPrice;
  final int? recognitionSkuId;
  final String categoryId;
  final bool active;
  final int sortOrder;
}
