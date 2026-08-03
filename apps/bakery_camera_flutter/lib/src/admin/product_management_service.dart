import 'dart:collection';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';

import '../catalog/catalog_photo_store.dart';
import '../catalog/product.dart';
import '../persistence/app_database.dart';

/// A single, validated catalog change. Saving always creates a new immutable
/// revision; it never mutates the revision frozen by a checkout session.
final class ProductDraft {
  const ProductDraft.add({
    required this.productId,
    required this.displayName,
    required this.unitPriceKrw,
    required this.categoryId,
    required this.sortOrder,
    this.recognitionSkuId,
    this.active = true,
    this.photo,
  }) : isNew = true,
       removePhoto = false;

  const ProductDraft.edit({
    required this.productId,
    required this.displayName,
    required this.unitPriceKrw,
    required this.categoryId,
    required this.sortOrder,
    required this.recognitionSkuId,
    required this.active,
    this.photo,
    this.removePhoto = false,
  }) : isNew = false;

  final bool isNew;
  final String productId;
  final String displayName;
  final int unitPriceKrw;
  final int? recognitionSkuId;
  final String categoryId;
  final bool active;
  final int sortOrder;
  final CatalogPhoto? photo;
  final bool removePhoto;
}

/// COW catalog writer. Its database transaction supplies one active revision
/// at all times, a reproducible revision digest, and append-only audit proof.
final class ProductManagementService {
  factory ProductManagementService({
    required BakeryDatabase database,
    String Function()? createId,
    DateTime Function()? now,
    CatalogPhotoStore? photoStore,
  }) => ProductManagementService._(
    database,
    createId ?? const Uuid().v4,
    now ?? DateTime.now,
    photoStore,
  );

  ProductManagementService._(
    this._database,
    this._createId,
    this._now,
    this._photoStore,
  );

  final BakeryDatabase _database;
  final String Function() _createId;
  final DateTime Function() _now;
  final CatalogPhotoStore? _photoStore;

  /// Imports a product photograph through the same guarded storage boundary
  /// used by catalog edits. Checkout and inference files never have a path to
  /// this API.
  Future<CatalogPhoto> importPhoto(
    File source, {
    required CatalogPhotoProvenance provenance,
  }) async {
    final store = _photoStore;
    if (store == null) {
      throw StateError('catalog photo storage is not configured');
    }
    return store.importFile(
      source,
      provenance: provenance,
      forbiddenArtifactHashes: await _protectedOperationalPhotoHashes(),
    );
  }

  Future<File?> resolvePhoto(ManagedCatalogProduct product) async {
    final store = _photoStore;
    final photo = _photoOf(product);
    if (store == null || photo == null) return null;
    return store.resolveVerified(photo);
  }

  Future<ManagedCatalogSnapshot> activeCatalog() async {
    final active = await _activeRevision();
    final products = await _productsFor(active.revisionId);
    return ManagedCatalogSnapshot(
      revision: _revision(active),
      products: List.unmodifiable(products.map(_managedProduct)),
    );
  }

  Future<ManagedCatalogSnapshot> save(ProductDraft draft) =>
      _database.transaction(() async {
        final previous = await _activeRevision();
        final existing = await _productsFor(previous.revisionId);
        final proposed = existing.map(_managedProduct).toList(growable: true);
        _apply(proposed, draft);
        final normalized = proposed
            .map(_normalizeForActiveMapping)
            .toList(growable: false);
        _validate(normalized);
        await _verifyCatalogPhotoMembership(normalized);

        final revisionId = _createId();
        if (revisionId.trim().isEmpty || revisionId == previous.revisionId) {
          throw StateError(
            'new catalog revision id must be distinct and non-empty',
          );
        }
        final createdAt = _now().toUtc();
        final digest = _canonicalSha256(normalized);
        // The partial unique index permits one active revision. This is still
        // atomic to every other connection because the entire save is one
        // transaction; no reader can observe an active-revision gap.
        await (_database.update(_database.catalogRevisions)
              ..where((row) => row.revisionId.equals(previous.revisionId)))
            .write(const CatalogRevisionsCompanion(isActive: Value(false)));
        await _database
            .into(_database.catalogRevisions)
            .insert(
              CatalogRevisionsCompanion.insert(
                revisionId: revisionId,
                sha256: digest,
                createdAtUs: createdAt.microsecondsSinceEpoch,
                isActive: true,
              ),
            );
        await _database.batch((batch) {
          batch.insertAll(
            _database.products,
            normalized
                .map((product) => _productCompanion(revisionId, product))
                .toList(growable: false),
          );
        });
        final auditDetail = jsonEncode(
          _orderedMap({
            'after_revision_id': revisionId,
            'after_sha256': digest,
            'before_revision_id': previous.revisionId,
            'before_sha256': previous.sha256,
            'change_product_id': draft.productId,
          }),
        );
        await _database
            .into(_database.auditEvents)
            .insert(
              AuditEventsCompanion.insert(
                eventId: '$revisionId/catalog-revision-saved',
                eventType: 'catalog_revision_saved',
                occurredAtUs: createdAt.microsecondsSinceEpoch,
                detail: Value(auditDetail),
              ),
            );
        return ManagedCatalogSnapshot(
          revision: CatalogRevision(
            revisionId: revisionId,
            sha256: digest,
            createdAt: createdAt,
          ),
          products: List.unmodifiable(normalized),
        );
      });

  Future<CatalogRevisionRow> _activeRevision() async {
    final revisions = await (_database.select(
      _database.catalogRevisions,
    )..where((row) => row.isActive.equals(true))).get();
    if (revisions.length != 1) {
      throw StateError('exactly one active catalog revision is required');
    }
    return revisions.single;
  }

  Future<List<ProductRow>> _productsFor(String revisionId) =>
      (_database.select(_database.products)
            ..where((row) => row.catalogRevisionId.equals(revisionId))
            ..orderBy([
              (row) => OrderingTerm.asc(row.sortOrder),
              (row) => OrderingTerm.asc(row.productId),
            ]))
          .get();

  void _apply(List<ManagedCatalogProduct> products, ProductDraft draft) {
    final index = products.indexWhere(
      (product) => product.productId == draft.productId,
    );
    if (draft.isNew) {
      if (index != -1) {
        throw ArgumentError.value(
          draft.productId,
          'productId',
          'already exists',
        );
      }
      products.add(_fromDraft(draft));
      return;
    }
    if (index == -1) {
      throw ArgumentError.value(draft.productId, 'productId', 'does not exist');
    }
    final previous = products[index];
    products[index] = _fromDraft(
      draft,
      retainedPhoto: draft.removePhoto
          ? null
          : draft.photo ?? _photoOf(previous),
    );
  }

  ManagedCatalogProduct _fromDraft(
    ProductDraft draft, {
    CatalogPhoto? retainedPhoto,
  }) {
    final photo = draft.photo ?? retainedPhoto;
    return ManagedCatalogProduct(
      productId: draft.productId.trim(),
      displayName: draft.displayName.trim(),
      unitPriceKrw: draft.unitPriceKrw,
      recognitionSkuId: draft.recognitionSkuId,
      categoryId: draft.categoryId.trim(),
      active: draft.active,
      sortOrder: draft.sortOrder,
      photoAssetPath: photo?.relativePath,
      photoByteSize: photo?.byteSize,
      photoSha256: photo?.sha256,
      photoMediaType: photo?.mediaType,
      photoProvenanceNote: photo?.provenanceNote,
    );
  }

  CatalogPhoto? _photoOf(ManagedCatalogProduct product) {
    final path = product.photoAssetPath;
    final size = product.photoByteSize;
    final hash = product.photoSha256;
    final type = product.photoMediaType;
    final note = product.photoProvenanceNote;
    if (path == null &&
        size == null &&
        hash == null &&
        type == null &&
        note == null) {
      return null;
    }
    if (path == null ||
        size == null ||
        hash == null ||
        type == null ||
        note == null) {
      throw StateError('catalog product photo metadata is incomplete');
    }
    return CatalogPhoto(
      relativePath: path,
      byteSize: size,
      sha256: hash,
      mediaType: type,
      provenanceNote: note,
    );
  }

  ManagedCatalogProduct _normalizeForActiveMapping(
    ManagedCatalogProduct product,
  ) {
    // Recognition is only meaningful for products available to automatic
    // checkout. Keeping it null for retired rows makes the active-SKU rule
    // explicit without altering any frozen previous revision.
    if (product.active) return product;
    return ManagedCatalogProduct(
      productId: product.productId,
      displayName: product.displayName,
      unitPriceKrw: product.unitPriceKrw,
      recognitionSkuId: null,
      categoryId: product.categoryId,
      active: false,
      sortOrder: product.sortOrder,
      photoAssetPath: product.photoAssetPath,
      photoByteSize: product.photoByteSize,
      photoSha256: product.photoSha256,
      photoMediaType: product.photoMediaType,
      photoProvenanceNote: product.photoProvenanceNote,
    );
  }

  void _validate(List<ManagedCatalogProduct> products) {
    final ids = <String>{};
    final activeSkus = <int>{};
    for (final product in products) {
      if (!RegExp(r'^[a-z0-9][a-z0-9-]{0,63}$').hasMatch(product.productId)) {
        throw ArgumentError.value(
          product.productId,
          'productId',
          'must be stable lowercase identifier',
        );
      }
      if (product.displayName.trim().isEmpty) {
        throw ArgumentError.value(
          product.displayName,
          'displayName',
          'is required',
        );
      }
      if (product.unitPriceKrw < 0) {
        throw ArgumentError.value(
          product.unitPriceKrw,
          'unitPriceKrw',
          'must be non-negative',
        );
      }
      if (product.categoryId.trim().isEmpty || product.sortOrder < 0) {
        throw ArgumentError('categoryId and sortOrder must be valid');
      }
      if (!ids.add(product.productId)) {
        throw ArgumentError.value(
          product.productId,
          'productId',
          'is duplicated',
        );
      }
      final sku = product.recognitionSkuId;
      if (sku != null && (sku < 1 || sku > 20)) {
        throw ArgumentError.value(
          sku,
          'recognitionSkuId',
          'must be registered',
        );
      }
      if (product.active && sku != null && !activeSkus.add(sku)) {
        throw ArgumentError.value(
          sku,
          'recognitionSkuId',
          'maps more than one active product',
        );
      }
      _validatePhoto(product);
    }
  }

  void _validatePhoto(ManagedCatalogProduct product) {
    final fields = [
      product.photoAssetPath,
      product.photoByteSize,
      product.photoSha256,
      product.photoMediaType,
      product.photoProvenanceNote,
    ];
    if (fields.every((field) => field == null)) return;
    if (fields.any((field) => field == null) ||
        product.photoAssetPath == null ||
        product.photoByteSize! <= 0 ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(product.photoSha256!) ||
        (product.photoMediaType != 'image/png' &&
            product.photoMediaType != 'image/jpeg')) {
      throw ArgumentError('catalog photo metadata is invalid');
    }
    final expectedExtension = product.photoMediaType == 'image/png'
        ? '.png'
        : '.jpg';
    final expectedPath =
        'catalog-media/${product.photoSha256}$expectedExtension';
    if (product.photoAssetPath != expectedPath) {
      throw ArgumentError('catalog photo metadata is invalid');
    }
    try {
      CatalogPhotoProvenance.parse(product.photoProvenanceNote!);
    } on FormatException {
      throw ArgumentError('catalog photo provenance is invalid');
    }
  }

  Future<void> _verifyCatalogPhotoMembership(
    List<ManagedCatalogProduct> products,
  ) async {
    final photos = products
        .map(_photoOf)
        .whereType<CatalogPhoto>()
        .toList(growable: false);
    if (photos.isEmpty) return;
    final store = _photoStore;
    if (store == null) {
      throw StateError('catalog photo storage is not configured');
    }
    for (final photo in photos) {
      await store.resolveVerified(photo);
    }
  }

  /// Audit captures remain protected even after someone copies their bytes to
  /// a benign-looking path. The store compares this complete digest set while
  /// it reads the actual import bytes, rather than trusting source filenames.
  Future<Set<String>> _protectedOperationalPhotoHashes() async {
    final attempts = await _database.select(_database.scanAttempts).get();
    return attempts.map((attempt) => attempt.imageSha256).toSet();
  }

  ProductsCompanion _productCompanion(
    String revisionId,
    ManagedCatalogProduct product,
  ) => ProductsCompanion.insert(
    productRevisionId: '$revisionId/${product.productId}',
    catalogRevisionId: revisionId,
    productId: product.productId,
    displayName: product.displayName,
    unitPriceKrw: product.unitPriceKrw,
    recognitionSkuId: Value(product.recognitionSkuId),
    categoryId: product.categoryId,
    photoRelativePath: Value(product.photoAssetPath),
    photoByteSize: Value(product.photoByteSize),
    photoSha256: Value(product.photoSha256),
    photoMediaType: Value(product.photoMediaType),
    photoProvenanceNote: Value(product.photoProvenanceNote),
    active: product.active,
    sortOrder: product.sortOrder,
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

  CatalogRevision _revision(CatalogRevisionRow row) => CatalogRevision(
    revisionId: row.revisionId,
    sha256: row.sha256,
    createdAt: DateTime.fromMicrosecondsSinceEpoch(
      row.createdAtUs,
      isUtc: true,
    ),
  );

  String _canonicalSha256(List<ManagedCatalogProduct> products) {
    final canonical = products.toList(growable: false)
      ..sort((left, right) => left.productId.compareTo(right.productId));
    final document = _orderedMap({
      'currency': 'KRW',
      'products': canonical
          .map(
            (product) => _orderedMap({
              'active': product.active,
              'category_id': product.categoryId,
              'display_name': product.displayName,
              'photo_byte_size': product.photoByteSize,
              'photo_media_type': product.photoMediaType,
              'photo_provenance_note': product.photoProvenanceNote,
              'photo_relative_path': product.photoAssetPath,
              'photo_sha256': product.photoSha256,
              'product_id': product.productId,
              'recognition_sku_id': product.recognitionSkuId,
              'sort_order': product.sortOrder,
              'unit_price_krw': product.unitPriceKrw,
            }),
          )
          .toList(growable: false),
    });
    return sha256.convert(utf8.encode(jsonEncode(document))).toString();
  }

  Map<String, Object?> _orderedMap(Map<String, Object?> values) {
    final sorted = SplayTreeMap<String, Object?>.from(values);
    return LinkedHashMap<String, Object?>.fromEntries(sorted.entries);
  }
}
