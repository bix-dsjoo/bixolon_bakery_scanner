// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $CatalogRevisionsTable extends CatalogRevisions
    with TableInfo<$CatalogRevisionsTable, CatalogRevisionRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CatalogRevisionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _revisionIdMeta = const VerificationMeta(
    'revisionId',
  );
  @override
  late final GeneratedColumn<String> revisionId = GeneratedColumn<String>(
    'revision_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sha256Meta = const VerificationMeta('sha256');
  @override
  late final GeneratedColumn<String> sha256 = GeneratedColumn<String>(
    'sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtUsMeta = const VerificationMeta(
    'createdAtUs',
  );
  @override
  late final GeneratedColumn<int> createdAtUs = GeneratedColumn<int>(
    'created_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _isActiveMeta = const VerificationMeta(
    'isActive',
  );
  @override
  late final GeneratedColumn<bool> isActive = GeneratedColumn<bool>(
    'is_active',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_active" IN (0, 1))',
    ),
  );
  @override
  List<GeneratedColumn> get $columns => [
    revisionId,
    sha256,
    createdAtUs,
    isActive,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'catalog_revisions';
  @override
  VerificationContext validateIntegrity(
    Insertable<CatalogRevisionRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('revision_id')) {
      context.handle(
        _revisionIdMeta,
        revisionId.isAcceptableOrUnknown(data['revision_id']!, _revisionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_revisionIdMeta);
    }
    if (data.containsKey('sha256')) {
      context.handle(
        _sha256Meta,
        sha256.isAcceptableOrUnknown(data['sha256']!, _sha256Meta),
      );
    } else if (isInserting) {
      context.missing(_sha256Meta);
    }
    if (data.containsKey('created_at_us')) {
      context.handle(
        _createdAtUsMeta,
        createdAtUs.isAcceptableOrUnknown(
          data['created_at_us']!,
          _createdAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_createdAtUsMeta);
    }
    if (data.containsKey('is_active')) {
      context.handle(
        _isActiveMeta,
        isActive.isAcceptableOrUnknown(data['is_active']!, _isActiveMeta),
      );
    } else if (isInserting) {
      context.missing(_isActiveMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {revisionId};
  @override
  CatalogRevisionRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CatalogRevisionRow(
      revisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}revision_id'],
      )!,
      sha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sha256'],
      )!,
      createdAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at_us'],
      )!,
      isActive: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_active'],
      )!,
    );
  }

  @override
  $CatalogRevisionsTable createAlias(String alias) {
    return $CatalogRevisionsTable(attachedDatabase, alias);
  }
}

class CatalogRevisionRow extends DataClass
    implements Insertable<CatalogRevisionRow> {
  final String revisionId;
  final String sha256;
  final int createdAtUs;
  final bool isActive;
  const CatalogRevisionRow({
    required this.revisionId,
    required this.sha256,
    required this.createdAtUs,
    required this.isActive,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['revision_id'] = Variable<String>(revisionId);
    map['sha256'] = Variable<String>(sha256);
    map['created_at_us'] = Variable<int>(createdAtUs);
    map['is_active'] = Variable<bool>(isActive);
    return map;
  }

  CatalogRevisionsCompanion toCompanion(bool nullToAbsent) {
    return CatalogRevisionsCompanion(
      revisionId: Value(revisionId),
      sha256: Value(sha256),
      createdAtUs: Value(createdAtUs),
      isActive: Value(isActive),
    );
  }

  factory CatalogRevisionRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CatalogRevisionRow(
      revisionId: serializer.fromJson<String>(json['revisionId']),
      sha256: serializer.fromJson<String>(json['sha256']),
      createdAtUs: serializer.fromJson<int>(json['createdAtUs']),
      isActive: serializer.fromJson<bool>(json['isActive']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'revisionId': serializer.toJson<String>(revisionId),
      'sha256': serializer.toJson<String>(sha256),
      'createdAtUs': serializer.toJson<int>(createdAtUs),
      'isActive': serializer.toJson<bool>(isActive),
    };
  }

  CatalogRevisionRow copyWith({
    String? revisionId,
    String? sha256,
    int? createdAtUs,
    bool? isActive,
  }) => CatalogRevisionRow(
    revisionId: revisionId ?? this.revisionId,
    sha256: sha256 ?? this.sha256,
    createdAtUs: createdAtUs ?? this.createdAtUs,
    isActive: isActive ?? this.isActive,
  );
  CatalogRevisionRow copyWithCompanion(CatalogRevisionsCompanion data) {
    return CatalogRevisionRow(
      revisionId: data.revisionId.present
          ? data.revisionId.value
          : this.revisionId,
      sha256: data.sha256.present ? data.sha256.value : this.sha256,
      createdAtUs: data.createdAtUs.present
          ? data.createdAtUs.value
          : this.createdAtUs,
      isActive: data.isActive.present ? data.isActive.value : this.isActive,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CatalogRevisionRow(')
          ..write('revisionId: $revisionId, ')
          ..write('sha256: $sha256, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('isActive: $isActive')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(revisionId, sha256, createdAtUs, isActive);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CatalogRevisionRow &&
          other.revisionId == this.revisionId &&
          other.sha256 == this.sha256 &&
          other.createdAtUs == this.createdAtUs &&
          other.isActive == this.isActive);
}

class CatalogRevisionsCompanion extends UpdateCompanion<CatalogRevisionRow> {
  final Value<String> revisionId;
  final Value<String> sha256;
  final Value<int> createdAtUs;
  final Value<bool> isActive;
  final Value<int> rowid;
  const CatalogRevisionsCompanion({
    this.revisionId = const Value.absent(),
    this.sha256 = const Value.absent(),
    this.createdAtUs = const Value.absent(),
    this.isActive = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CatalogRevisionsCompanion.insert({
    required String revisionId,
    required String sha256,
    required int createdAtUs,
    required bool isActive,
    this.rowid = const Value.absent(),
  }) : revisionId = Value(revisionId),
       sha256 = Value(sha256),
       createdAtUs = Value(createdAtUs),
       isActive = Value(isActive);
  static Insertable<CatalogRevisionRow> custom({
    Expression<String>? revisionId,
    Expression<String>? sha256,
    Expression<int>? createdAtUs,
    Expression<bool>? isActive,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (revisionId != null) 'revision_id': revisionId,
      if (sha256 != null) 'sha256': sha256,
      if (createdAtUs != null) 'created_at_us': createdAtUs,
      if (isActive != null) 'is_active': isActive,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CatalogRevisionsCompanion copyWith({
    Value<String>? revisionId,
    Value<String>? sha256,
    Value<int>? createdAtUs,
    Value<bool>? isActive,
    Value<int>? rowid,
  }) {
    return CatalogRevisionsCompanion(
      revisionId: revisionId ?? this.revisionId,
      sha256: sha256 ?? this.sha256,
      createdAtUs: createdAtUs ?? this.createdAtUs,
      isActive: isActive ?? this.isActive,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (revisionId.present) {
      map['revision_id'] = Variable<String>(revisionId.value);
    }
    if (sha256.present) {
      map['sha256'] = Variable<String>(sha256.value);
    }
    if (createdAtUs.present) {
      map['created_at_us'] = Variable<int>(createdAtUs.value);
    }
    if (isActive.present) {
      map['is_active'] = Variable<bool>(isActive.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CatalogRevisionsCompanion(')
          ..write('revisionId: $revisionId, ')
          ..write('sha256: $sha256, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('isActive: $isActive, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ProductsTable extends Products
    with TableInfo<$ProductsTable, ProductRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ProductsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _productRevisionIdMeta = const VerificationMeta(
    'productRevisionId',
  );
  @override
  late final GeneratedColumn<String> productRevisionId =
      GeneratedColumn<String>(
        'product_revision_id',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _catalogRevisionIdMeta = const VerificationMeta(
    'catalogRevisionId',
  );
  @override
  late final GeneratedColumn<String> catalogRevisionId =
      GeneratedColumn<String>(
        'catalog_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES catalog_revisions (revision_id)',
        ),
      );
  static const VerificationMeta _productIdMeta = const VerificationMeta(
    'productId',
  );
  @override
  late final GeneratedColumn<String> productId = GeneratedColumn<String>(
    'product_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _displayNameMeta = const VerificationMeta(
    'displayName',
  );
  @override
  late final GeneratedColumn<String> displayName = GeneratedColumn<String>(
    'display_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitPriceKrwMeta = const VerificationMeta(
    'unitPriceKrw',
  );
  @override
  late final GeneratedColumn<int> unitPriceKrw = GeneratedColumn<int>(
    'unit_price_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(unitPriceKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _recognitionSkuIdMeta = const VerificationMeta(
    'recognitionSkuId',
  );
  @override
  late final GeneratedColumn<int> recognitionSkuId = GeneratedColumn<int>(
    'recognition_sku_id',
    aliasedName,
    true,
    check: () => ComparableExpr(recognitionSkuId).isBetweenValues(1, 20),
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _categoryIdMeta = const VerificationMeta(
    'categoryId',
  );
  @override
  late final GeneratedColumn<String> categoryId = GeneratedColumn<String>(
    'category_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _photoRelativePathMeta = const VerificationMeta(
    'photoRelativePath',
  );
  @override
  late final GeneratedColumn<String> photoRelativePath =
      GeneratedColumn<String>(
        'photo_relative_path',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _photoByteSizeMeta = const VerificationMeta(
    'photoByteSize',
  );
  @override
  late final GeneratedColumn<int> photoByteSize = GeneratedColumn<int>(
    'photo_byte_size',
    aliasedName,
    true,
    check: () => ComparableExpr(photoByteSize).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _photoSha256Meta = const VerificationMeta(
    'photoSha256',
  );
  @override
  late final GeneratedColumn<String> photoSha256 = GeneratedColumn<String>(
    'photo_sha256',
    aliasedName,
    true,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _photoMediaTypeMeta = const VerificationMeta(
    'photoMediaType',
  );
  @override
  late final GeneratedColumn<String> photoMediaType = GeneratedColumn<String>(
    'photo_media_type',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _photoProvenanceNoteMeta =
      const VerificationMeta('photoProvenanceNote');
  @override
  late final GeneratedColumn<String> photoProvenanceNote =
      GeneratedColumn<String>(
        'photo_provenance_note',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _activeMeta = const VerificationMeta('active');
  @override
  late final GeneratedColumn<bool> active = GeneratedColumn<bool>(
    'active',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("active" IN (0, 1))',
    ),
  );
  static const VerificationMeta _sortOrderMeta = const VerificationMeta(
    'sortOrder',
  );
  @override
  late final GeneratedColumn<int> sortOrder = GeneratedColumn<int>(
    'sort_order',
    aliasedName,
    false,
    check: () => ComparableExpr(sortOrder).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    productRevisionId,
    catalogRevisionId,
    productId,
    displayName,
    unitPriceKrw,
    recognitionSkuId,
    categoryId,
    photoRelativePath,
    photoByteSize,
    photoSha256,
    photoMediaType,
    photoProvenanceNote,
    active,
    sortOrder,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'products';
  @override
  VerificationContext validateIntegrity(
    Insertable<ProductRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('product_revision_id')) {
      context.handle(
        _productRevisionIdMeta,
        productRevisionId.isAcceptableOrUnknown(
          data['product_revision_id']!,
          _productRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productRevisionIdMeta);
    }
    if (data.containsKey('catalog_revision_id')) {
      context.handle(
        _catalogRevisionIdMeta,
        catalogRevisionId.isAcceptableOrUnknown(
          data['catalog_revision_id']!,
          _catalogRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_catalogRevisionIdMeta);
    }
    if (data.containsKey('product_id')) {
      context.handle(
        _productIdMeta,
        productId.isAcceptableOrUnknown(data['product_id']!, _productIdMeta),
      );
    } else if (isInserting) {
      context.missing(_productIdMeta);
    }
    if (data.containsKey('display_name')) {
      context.handle(
        _displayNameMeta,
        displayName.isAcceptableOrUnknown(
          data['display_name']!,
          _displayNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_displayNameMeta);
    }
    if (data.containsKey('unit_price_krw')) {
      context.handle(
        _unitPriceKrwMeta,
        unitPriceKrw.isAcceptableOrUnknown(
          data['unit_price_krw']!,
          _unitPriceKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_unitPriceKrwMeta);
    }
    if (data.containsKey('recognition_sku_id')) {
      context.handle(
        _recognitionSkuIdMeta,
        recognitionSkuId.isAcceptableOrUnknown(
          data['recognition_sku_id']!,
          _recognitionSkuIdMeta,
        ),
      );
    }
    if (data.containsKey('category_id')) {
      context.handle(
        _categoryIdMeta,
        categoryId.isAcceptableOrUnknown(data['category_id']!, _categoryIdMeta),
      );
    } else if (isInserting) {
      context.missing(_categoryIdMeta);
    }
    if (data.containsKey('photo_relative_path')) {
      context.handle(
        _photoRelativePathMeta,
        photoRelativePath.isAcceptableOrUnknown(
          data['photo_relative_path']!,
          _photoRelativePathMeta,
        ),
      );
    }
    if (data.containsKey('photo_byte_size')) {
      context.handle(
        _photoByteSizeMeta,
        photoByteSize.isAcceptableOrUnknown(
          data['photo_byte_size']!,
          _photoByteSizeMeta,
        ),
      );
    }
    if (data.containsKey('photo_sha256')) {
      context.handle(
        _photoSha256Meta,
        photoSha256.isAcceptableOrUnknown(
          data['photo_sha256']!,
          _photoSha256Meta,
        ),
      );
    }
    if (data.containsKey('photo_media_type')) {
      context.handle(
        _photoMediaTypeMeta,
        photoMediaType.isAcceptableOrUnknown(
          data['photo_media_type']!,
          _photoMediaTypeMeta,
        ),
      );
    }
    if (data.containsKey('photo_provenance_note')) {
      context.handle(
        _photoProvenanceNoteMeta,
        photoProvenanceNote.isAcceptableOrUnknown(
          data['photo_provenance_note']!,
          _photoProvenanceNoteMeta,
        ),
      );
    }
    if (data.containsKey('active')) {
      context.handle(
        _activeMeta,
        active.isAcceptableOrUnknown(data['active']!, _activeMeta),
      );
    } else if (isInserting) {
      context.missing(_activeMeta);
    }
    if (data.containsKey('sort_order')) {
      context.handle(
        _sortOrderMeta,
        sortOrder.isAcceptableOrUnknown(data['sort_order']!, _sortOrderMeta),
      );
    } else if (isInserting) {
      context.missing(_sortOrderMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {productRevisionId};
  @override
  ProductRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ProductRow(
      productRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_revision_id'],
      )!,
      catalogRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}catalog_revision_id'],
      )!,
      productId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_id'],
      )!,
      displayName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}display_name'],
      )!,
      unitPriceKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}unit_price_krw'],
      )!,
      recognitionSkuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recognition_sku_id'],
      ),
      categoryId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}category_id'],
      )!,
      photoRelativePath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}photo_relative_path'],
      ),
      photoByteSize: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}photo_byte_size'],
      ),
      photoSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}photo_sha256'],
      ),
      photoMediaType: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}photo_media_type'],
      ),
      photoProvenanceNote: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}photo_provenance_note'],
      ),
      active: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}active'],
      )!,
      sortOrder: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}sort_order'],
      )!,
    );
  }

  @override
  $ProductsTable createAlias(String alias) {
    return $ProductsTable(attachedDatabase, alias);
  }
}

class ProductRow extends DataClass implements Insertable<ProductRow> {
  final String productRevisionId;
  final String catalogRevisionId;
  final String productId;
  final String displayName;
  final int unitPriceKrw;
  final int? recognitionSkuId;
  final String categoryId;
  final String? photoRelativePath;
  final int? photoByteSize;
  final String? photoSha256;
  final String? photoMediaType;
  final String? photoProvenanceNote;
  final bool active;
  final int sortOrder;
  const ProductRow({
    required this.productRevisionId,
    required this.catalogRevisionId,
    required this.productId,
    required this.displayName,
    required this.unitPriceKrw,
    this.recognitionSkuId,
    required this.categoryId,
    this.photoRelativePath,
    this.photoByteSize,
    this.photoSha256,
    this.photoMediaType,
    this.photoProvenanceNote,
    required this.active,
    required this.sortOrder,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['product_revision_id'] = Variable<String>(productRevisionId);
    map['catalog_revision_id'] = Variable<String>(catalogRevisionId);
    map['product_id'] = Variable<String>(productId);
    map['display_name'] = Variable<String>(displayName);
    map['unit_price_krw'] = Variable<int>(unitPriceKrw);
    if (!nullToAbsent || recognitionSkuId != null) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId);
    }
    map['category_id'] = Variable<String>(categoryId);
    if (!nullToAbsent || photoRelativePath != null) {
      map['photo_relative_path'] = Variable<String>(photoRelativePath);
    }
    if (!nullToAbsent || photoByteSize != null) {
      map['photo_byte_size'] = Variable<int>(photoByteSize);
    }
    if (!nullToAbsent || photoSha256 != null) {
      map['photo_sha256'] = Variable<String>(photoSha256);
    }
    if (!nullToAbsent || photoMediaType != null) {
      map['photo_media_type'] = Variable<String>(photoMediaType);
    }
    if (!nullToAbsent || photoProvenanceNote != null) {
      map['photo_provenance_note'] = Variable<String>(photoProvenanceNote);
    }
    map['active'] = Variable<bool>(active);
    map['sort_order'] = Variable<int>(sortOrder);
    return map;
  }

  ProductsCompanion toCompanion(bool nullToAbsent) {
    return ProductsCompanion(
      productRevisionId: Value(productRevisionId),
      catalogRevisionId: Value(catalogRevisionId),
      productId: Value(productId),
      displayName: Value(displayName),
      unitPriceKrw: Value(unitPriceKrw),
      recognitionSkuId: recognitionSkuId == null && nullToAbsent
          ? const Value.absent()
          : Value(recognitionSkuId),
      categoryId: Value(categoryId),
      photoRelativePath: photoRelativePath == null && nullToAbsent
          ? const Value.absent()
          : Value(photoRelativePath),
      photoByteSize: photoByteSize == null && nullToAbsent
          ? const Value.absent()
          : Value(photoByteSize),
      photoSha256: photoSha256 == null && nullToAbsent
          ? const Value.absent()
          : Value(photoSha256),
      photoMediaType: photoMediaType == null && nullToAbsent
          ? const Value.absent()
          : Value(photoMediaType),
      photoProvenanceNote: photoProvenanceNote == null && nullToAbsent
          ? const Value.absent()
          : Value(photoProvenanceNote),
      active: Value(active),
      sortOrder: Value(sortOrder),
    );
  }

  factory ProductRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ProductRow(
      productRevisionId: serializer.fromJson<String>(json['productRevisionId']),
      catalogRevisionId: serializer.fromJson<String>(json['catalogRevisionId']),
      productId: serializer.fromJson<String>(json['productId']),
      displayName: serializer.fromJson<String>(json['displayName']),
      unitPriceKrw: serializer.fromJson<int>(json['unitPriceKrw']),
      recognitionSkuId: serializer.fromJson<int?>(json['recognitionSkuId']),
      categoryId: serializer.fromJson<String>(json['categoryId']),
      photoRelativePath: serializer.fromJson<String?>(
        json['photoRelativePath'],
      ),
      photoByteSize: serializer.fromJson<int?>(json['photoByteSize']),
      photoSha256: serializer.fromJson<String?>(json['photoSha256']),
      photoMediaType: serializer.fromJson<String?>(json['photoMediaType']),
      photoProvenanceNote: serializer.fromJson<String?>(
        json['photoProvenanceNote'],
      ),
      active: serializer.fromJson<bool>(json['active']),
      sortOrder: serializer.fromJson<int>(json['sortOrder']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'productRevisionId': serializer.toJson<String>(productRevisionId),
      'catalogRevisionId': serializer.toJson<String>(catalogRevisionId),
      'productId': serializer.toJson<String>(productId),
      'displayName': serializer.toJson<String>(displayName),
      'unitPriceKrw': serializer.toJson<int>(unitPriceKrw),
      'recognitionSkuId': serializer.toJson<int?>(recognitionSkuId),
      'categoryId': serializer.toJson<String>(categoryId),
      'photoRelativePath': serializer.toJson<String?>(photoRelativePath),
      'photoByteSize': serializer.toJson<int?>(photoByteSize),
      'photoSha256': serializer.toJson<String?>(photoSha256),
      'photoMediaType': serializer.toJson<String?>(photoMediaType),
      'photoProvenanceNote': serializer.toJson<String?>(photoProvenanceNote),
      'active': serializer.toJson<bool>(active),
      'sortOrder': serializer.toJson<int>(sortOrder),
    };
  }

  ProductRow copyWith({
    String? productRevisionId,
    String? catalogRevisionId,
    String? productId,
    String? displayName,
    int? unitPriceKrw,
    Value<int?> recognitionSkuId = const Value.absent(),
    String? categoryId,
    Value<String?> photoRelativePath = const Value.absent(),
    Value<int?> photoByteSize = const Value.absent(),
    Value<String?> photoSha256 = const Value.absent(),
    Value<String?> photoMediaType = const Value.absent(),
    Value<String?> photoProvenanceNote = const Value.absent(),
    bool? active,
    int? sortOrder,
  }) => ProductRow(
    productRevisionId: productRevisionId ?? this.productRevisionId,
    catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
    productId: productId ?? this.productId,
    displayName: displayName ?? this.displayName,
    unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
    recognitionSkuId: recognitionSkuId.present
        ? recognitionSkuId.value
        : this.recognitionSkuId,
    categoryId: categoryId ?? this.categoryId,
    photoRelativePath: photoRelativePath.present
        ? photoRelativePath.value
        : this.photoRelativePath,
    photoByteSize: photoByteSize.present
        ? photoByteSize.value
        : this.photoByteSize,
    photoSha256: photoSha256.present ? photoSha256.value : this.photoSha256,
    photoMediaType: photoMediaType.present
        ? photoMediaType.value
        : this.photoMediaType,
    photoProvenanceNote: photoProvenanceNote.present
        ? photoProvenanceNote.value
        : this.photoProvenanceNote,
    active: active ?? this.active,
    sortOrder: sortOrder ?? this.sortOrder,
  );
  ProductRow copyWithCompanion(ProductsCompanion data) {
    return ProductRow(
      productRevisionId: data.productRevisionId.present
          ? data.productRevisionId.value
          : this.productRevisionId,
      catalogRevisionId: data.catalogRevisionId.present
          ? data.catalogRevisionId.value
          : this.catalogRevisionId,
      productId: data.productId.present ? data.productId.value : this.productId,
      displayName: data.displayName.present
          ? data.displayName.value
          : this.displayName,
      unitPriceKrw: data.unitPriceKrw.present
          ? data.unitPriceKrw.value
          : this.unitPriceKrw,
      recognitionSkuId: data.recognitionSkuId.present
          ? data.recognitionSkuId.value
          : this.recognitionSkuId,
      categoryId: data.categoryId.present
          ? data.categoryId.value
          : this.categoryId,
      photoRelativePath: data.photoRelativePath.present
          ? data.photoRelativePath.value
          : this.photoRelativePath,
      photoByteSize: data.photoByteSize.present
          ? data.photoByteSize.value
          : this.photoByteSize,
      photoSha256: data.photoSha256.present
          ? data.photoSha256.value
          : this.photoSha256,
      photoMediaType: data.photoMediaType.present
          ? data.photoMediaType.value
          : this.photoMediaType,
      photoProvenanceNote: data.photoProvenanceNote.present
          ? data.photoProvenanceNote.value
          : this.photoProvenanceNote,
      active: data.active.present ? data.active.value : this.active,
      sortOrder: data.sortOrder.present ? data.sortOrder.value : this.sortOrder,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ProductRow(')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('productId: $productId, ')
          ..write('displayName: $displayName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('categoryId: $categoryId, ')
          ..write('photoRelativePath: $photoRelativePath, ')
          ..write('photoByteSize: $photoByteSize, ')
          ..write('photoSha256: $photoSha256, ')
          ..write('photoMediaType: $photoMediaType, ')
          ..write('photoProvenanceNote: $photoProvenanceNote, ')
          ..write('active: $active, ')
          ..write('sortOrder: $sortOrder')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    productRevisionId,
    catalogRevisionId,
    productId,
    displayName,
    unitPriceKrw,
    recognitionSkuId,
    categoryId,
    photoRelativePath,
    photoByteSize,
    photoSha256,
    photoMediaType,
    photoProvenanceNote,
    active,
    sortOrder,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ProductRow &&
          other.productRevisionId == this.productRevisionId &&
          other.catalogRevisionId == this.catalogRevisionId &&
          other.productId == this.productId &&
          other.displayName == this.displayName &&
          other.unitPriceKrw == this.unitPriceKrw &&
          other.recognitionSkuId == this.recognitionSkuId &&
          other.categoryId == this.categoryId &&
          other.photoRelativePath == this.photoRelativePath &&
          other.photoByteSize == this.photoByteSize &&
          other.photoSha256 == this.photoSha256 &&
          other.photoMediaType == this.photoMediaType &&
          other.photoProvenanceNote == this.photoProvenanceNote &&
          other.active == this.active &&
          other.sortOrder == this.sortOrder);
}

class ProductsCompanion extends UpdateCompanion<ProductRow> {
  final Value<String> productRevisionId;
  final Value<String> catalogRevisionId;
  final Value<String> productId;
  final Value<String> displayName;
  final Value<int> unitPriceKrw;
  final Value<int?> recognitionSkuId;
  final Value<String> categoryId;
  final Value<String?> photoRelativePath;
  final Value<int?> photoByteSize;
  final Value<String?> photoSha256;
  final Value<String?> photoMediaType;
  final Value<String?> photoProvenanceNote;
  final Value<bool> active;
  final Value<int> sortOrder;
  final Value<int> rowid;
  const ProductsCompanion({
    this.productRevisionId = const Value.absent(),
    this.catalogRevisionId = const Value.absent(),
    this.productId = const Value.absent(),
    this.displayName = const Value.absent(),
    this.unitPriceKrw = const Value.absent(),
    this.recognitionSkuId = const Value.absent(),
    this.categoryId = const Value.absent(),
    this.photoRelativePath = const Value.absent(),
    this.photoByteSize = const Value.absent(),
    this.photoSha256 = const Value.absent(),
    this.photoMediaType = const Value.absent(),
    this.photoProvenanceNote = const Value.absent(),
    this.active = const Value.absent(),
    this.sortOrder = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ProductsCompanion.insert({
    required String productRevisionId,
    required String catalogRevisionId,
    required String productId,
    required String displayName,
    required int unitPriceKrw,
    this.recognitionSkuId = const Value.absent(),
    required String categoryId,
    this.photoRelativePath = const Value.absent(),
    this.photoByteSize = const Value.absent(),
    this.photoSha256 = const Value.absent(),
    this.photoMediaType = const Value.absent(),
    this.photoProvenanceNote = const Value.absent(),
    required bool active,
    required int sortOrder,
    this.rowid = const Value.absent(),
  }) : productRevisionId = Value(productRevisionId),
       catalogRevisionId = Value(catalogRevisionId),
       productId = Value(productId),
       displayName = Value(displayName),
       unitPriceKrw = Value(unitPriceKrw),
       categoryId = Value(categoryId),
       active = Value(active),
       sortOrder = Value(sortOrder);
  static Insertable<ProductRow> custom({
    Expression<String>? productRevisionId,
    Expression<String>? catalogRevisionId,
    Expression<String>? productId,
    Expression<String>? displayName,
    Expression<int>? unitPriceKrw,
    Expression<int>? recognitionSkuId,
    Expression<String>? categoryId,
    Expression<String>? photoRelativePath,
    Expression<int>? photoByteSize,
    Expression<String>? photoSha256,
    Expression<String>? photoMediaType,
    Expression<String>? photoProvenanceNote,
    Expression<bool>? active,
    Expression<int>? sortOrder,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (productRevisionId != null) 'product_revision_id': productRevisionId,
      if (catalogRevisionId != null) 'catalog_revision_id': catalogRevisionId,
      if (productId != null) 'product_id': productId,
      if (displayName != null) 'display_name': displayName,
      if (unitPriceKrw != null) 'unit_price_krw': unitPriceKrw,
      if (recognitionSkuId != null) 'recognition_sku_id': recognitionSkuId,
      if (categoryId != null) 'category_id': categoryId,
      if (photoRelativePath != null) 'photo_relative_path': photoRelativePath,
      if (photoByteSize != null) 'photo_byte_size': photoByteSize,
      if (photoSha256 != null) 'photo_sha256': photoSha256,
      if (photoMediaType != null) 'photo_media_type': photoMediaType,
      if (photoProvenanceNote != null)
        'photo_provenance_note': photoProvenanceNote,
      if (active != null) 'active': active,
      if (sortOrder != null) 'sort_order': sortOrder,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ProductsCompanion copyWith({
    Value<String>? productRevisionId,
    Value<String>? catalogRevisionId,
    Value<String>? productId,
    Value<String>? displayName,
    Value<int>? unitPriceKrw,
    Value<int?>? recognitionSkuId,
    Value<String>? categoryId,
    Value<String?>? photoRelativePath,
    Value<int?>? photoByteSize,
    Value<String?>? photoSha256,
    Value<String?>? photoMediaType,
    Value<String?>? photoProvenanceNote,
    Value<bool>? active,
    Value<int>? sortOrder,
    Value<int>? rowid,
  }) {
    return ProductsCompanion(
      productRevisionId: productRevisionId ?? this.productRevisionId,
      catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
      productId: productId ?? this.productId,
      displayName: displayName ?? this.displayName,
      unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
      recognitionSkuId: recognitionSkuId ?? this.recognitionSkuId,
      categoryId: categoryId ?? this.categoryId,
      photoRelativePath: photoRelativePath ?? this.photoRelativePath,
      photoByteSize: photoByteSize ?? this.photoByteSize,
      photoSha256: photoSha256 ?? this.photoSha256,
      photoMediaType: photoMediaType ?? this.photoMediaType,
      photoProvenanceNote: photoProvenanceNote ?? this.photoProvenanceNote,
      active: active ?? this.active,
      sortOrder: sortOrder ?? this.sortOrder,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (productRevisionId.present) {
      map['product_revision_id'] = Variable<String>(productRevisionId.value);
    }
    if (catalogRevisionId.present) {
      map['catalog_revision_id'] = Variable<String>(catalogRevisionId.value);
    }
    if (productId.present) {
      map['product_id'] = Variable<String>(productId.value);
    }
    if (displayName.present) {
      map['display_name'] = Variable<String>(displayName.value);
    }
    if (unitPriceKrw.present) {
      map['unit_price_krw'] = Variable<int>(unitPriceKrw.value);
    }
    if (recognitionSkuId.present) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId.value);
    }
    if (categoryId.present) {
      map['category_id'] = Variable<String>(categoryId.value);
    }
    if (photoRelativePath.present) {
      map['photo_relative_path'] = Variable<String>(photoRelativePath.value);
    }
    if (photoByteSize.present) {
      map['photo_byte_size'] = Variable<int>(photoByteSize.value);
    }
    if (photoSha256.present) {
      map['photo_sha256'] = Variable<String>(photoSha256.value);
    }
    if (photoMediaType.present) {
      map['photo_media_type'] = Variable<String>(photoMediaType.value);
    }
    if (photoProvenanceNote.present) {
      map['photo_provenance_note'] = Variable<String>(
        photoProvenanceNote.value,
      );
    }
    if (active.present) {
      map['active'] = Variable<bool>(active.value);
    }
    if (sortOrder.present) {
      map['sort_order'] = Variable<int>(sortOrder.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ProductsCompanion(')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('productId: $productId, ')
          ..write('displayName: $displayName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('categoryId: $categoryId, ')
          ..write('photoRelativePath: $photoRelativePath, ')
          ..write('photoByteSize: $photoByteSize, ')
          ..write('photoSha256: $photoSha256, ')
          ..write('photoMediaType: $photoMediaType, ')
          ..write('photoProvenanceNote: $photoProvenanceNote, ')
          ..write('active: $active, ')
          ..write('sortOrder: $sortOrder, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $SettingsRevisionsTable extends SettingsRevisions
    with TableInfo<$SettingsRevisionsTable, SettingsRevisionRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SettingsRevisionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _revisionIdMeta = const VerificationMeta(
    'revisionId',
  );
  @override
  late final GeneratedColumn<String> revisionId = GeneratedColumn<String>(
    'revision_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtUsMeta = const VerificationMeta(
    'createdAtUs',
  );
  @override
  late final GeneratedColumn<int> createdAtUs = GeneratedColumn<int>(
    'created_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _retryLimitMeta = const VerificationMeta(
    'retryLimit',
  );
  @override
  late final GeneratedColumn<int> retryLimit = GeneratedColumn<int>(
    'retry_limit',
    aliasedName,
    false,
    check: () => ComparableExpr(retryLimit).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _paymentCompleteDurationSecondsMeta =
      const VerificationMeta('paymentCompleteDurationSeconds');
  @override
  late final GeneratedColumn<int> paymentCompleteDurationSeconds =
      GeneratedColumn<int>(
        'payment_complete_duration_seconds',
        aliasedName,
        false,
        check: () =>
            ComparableExpr(paymentCompleteDurationSeconds).isBiggerThanValue(0),
        type: DriftSqlType.int,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _customerAutoResetMeta = const VerificationMeta(
    'customerAutoReset',
  );
  @override
  late final GeneratedColumn<bool> customerAutoReset = GeneratedColumn<bool>(
    'customer_auto_reset',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("customer_auto_reset" IN (0, 1))',
    ),
  );
  static const VerificationMeta _evidenceRetentionDaysMeta =
      const VerificationMeta('evidenceRetentionDays');
  @override
  late final GeneratedColumn<int> evidenceRetentionDays = GeneratedColumn<int>(
    'evidence_retention_days',
    aliasedName,
    false,
    check: () => ComparableExpr(evidenceRetentionDays).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _localeMeta = const VerificationMeta('locale');
  @override
  late final GeneratedColumn<String> locale = GeneratedColumn<String>(
    'locale',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _kioskDisplayNameMeta = const VerificationMeta(
    'kioskDisplayName',
  );
  @override
  late final GeneratedColumn<String> kioskDisplayName = GeneratedColumn<String>(
    'kiosk_display_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _adminAuthorLabelMeta = const VerificationMeta(
    'adminAuthorLabel',
  );
  @override
  late final GeneratedColumn<String> adminAuthorLabel = GeneratedColumn<String>(
    'admin_author_label',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    revisionId,
    createdAtUs,
    retryLimit,
    paymentCompleteDurationSeconds,
    customerAutoReset,
    evidenceRetentionDays,
    locale,
    kioskDisplayName,
    adminAuthorLabel,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'settings_revisions';
  @override
  VerificationContext validateIntegrity(
    Insertable<SettingsRevisionRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('revision_id')) {
      context.handle(
        _revisionIdMeta,
        revisionId.isAcceptableOrUnknown(data['revision_id']!, _revisionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_revisionIdMeta);
    }
    if (data.containsKey('created_at_us')) {
      context.handle(
        _createdAtUsMeta,
        createdAtUs.isAcceptableOrUnknown(
          data['created_at_us']!,
          _createdAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_createdAtUsMeta);
    }
    if (data.containsKey('retry_limit')) {
      context.handle(
        _retryLimitMeta,
        retryLimit.isAcceptableOrUnknown(data['retry_limit']!, _retryLimitMeta),
      );
    } else if (isInserting) {
      context.missing(_retryLimitMeta);
    }
    if (data.containsKey('payment_complete_duration_seconds')) {
      context.handle(
        _paymentCompleteDurationSecondsMeta,
        paymentCompleteDurationSeconds.isAcceptableOrUnknown(
          data['payment_complete_duration_seconds']!,
          _paymentCompleteDurationSecondsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_paymentCompleteDurationSecondsMeta);
    }
    if (data.containsKey('customer_auto_reset')) {
      context.handle(
        _customerAutoResetMeta,
        customerAutoReset.isAcceptableOrUnknown(
          data['customer_auto_reset']!,
          _customerAutoResetMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_customerAutoResetMeta);
    }
    if (data.containsKey('evidence_retention_days')) {
      context.handle(
        _evidenceRetentionDaysMeta,
        evidenceRetentionDays.isAcceptableOrUnknown(
          data['evidence_retention_days']!,
          _evidenceRetentionDaysMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_evidenceRetentionDaysMeta);
    }
    if (data.containsKey('locale')) {
      context.handle(
        _localeMeta,
        locale.isAcceptableOrUnknown(data['locale']!, _localeMeta),
      );
    } else if (isInserting) {
      context.missing(_localeMeta);
    }
    if (data.containsKey('kiosk_display_name')) {
      context.handle(
        _kioskDisplayNameMeta,
        kioskDisplayName.isAcceptableOrUnknown(
          data['kiosk_display_name']!,
          _kioskDisplayNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_kioskDisplayNameMeta);
    }
    if (data.containsKey('admin_author_label')) {
      context.handle(
        _adminAuthorLabelMeta,
        adminAuthorLabel.isAcceptableOrUnknown(
          data['admin_author_label']!,
          _adminAuthorLabelMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_adminAuthorLabelMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {revisionId};
  @override
  SettingsRevisionRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SettingsRevisionRow(
      revisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}revision_id'],
      )!,
      createdAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at_us'],
      )!,
      retryLimit: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}retry_limit'],
      )!,
      paymentCompleteDurationSeconds: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}payment_complete_duration_seconds'],
      )!,
      customerAutoReset: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}customer_auto_reset'],
      )!,
      evidenceRetentionDays: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}evidence_retention_days'],
      )!,
      locale: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}locale'],
      )!,
      kioskDisplayName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kiosk_display_name'],
      )!,
      adminAuthorLabel: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}admin_author_label'],
      )!,
    );
  }

  @override
  $SettingsRevisionsTable createAlias(String alias) {
    return $SettingsRevisionsTable(attachedDatabase, alias);
  }
}

class SettingsRevisionRow extends DataClass
    implements Insertable<SettingsRevisionRow> {
  final String revisionId;
  final int createdAtUs;
  final int retryLimit;
  final int paymentCompleteDurationSeconds;
  final bool customerAutoReset;
  final int evidenceRetentionDays;
  final String locale;
  final String kioskDisplayName;
  final String adminAuthorLabel;
  const SettingsRevisionRow({
    required this.revisionId,
    required this.createdAtUs,
    required this.retryLimit,
    required this.paymentCompleteDurationSeconds,
    required this.customerAutoReset,
    required this.evidenceRetentionDays,
    required this.locale,
    required this.kioskDisplayName,
    required this.adminAuthorLabel,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['revision_id'] = Variable<String>(revisionId);
    map['created_at_us'] = Variable<int>(createdAtUs);
    map['retry_limit'] = Variable<int>(retryLimit);
    map['payment_complete_duration_seconds'] = Variable<int>(
      paymentCompleteDurationSeconds,
    );
    map['customer_auto_reset'] = Variable<bool>(customerAutoReset);
    map['evidence_retention_days'] = Variable<int>(evidenceRetentionDays);
    map['locale'] = Variable<String>(locale);
    map['kiosk_display_name'] = Variable<String>(kioskDisplayName);
    map['admin_author_label'] = Variable<String>(adminAuthorLabel);
    return map;
  }

  SettingsRevisionsCompanion toCompanion(bool nullToAbsent) {
    return SettingsRevisionsCompanion(
      revisionId: Value(revisionId),
      createdAtUs: Value(createdAtUs),
      retryLimit: Value(retryLimit),
      paymentCompleteDurationSeconds: Value(paymentCompleteDurationSeconds),
      customerAutoReset: Value(customerAutoReset),
      evidenceRetentionDays: Value(evidenceRetentionDays),
      locale: Value(locale),
      kioskDisplayName: Value(kioskDisplayName),
      adminAuthorLabel: Value(adminAuthorLabel),
    );
  }

  factory SettingsRevisionRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SettingsRevisionRow(
      revisionId: serializer.fromJson<String>(json['revisionId']),
      createdAtUs: serializer.fromJson<int>(json['createdAtUs']),
      retryLimit: serializer.fromJson<int>(json['retryLimit']),
      paymentCompleteDurationSeconds: serializer.fromJson<int>(
        json['paymentCompleteDurationSeconds'],
      ),
      customerAutoReset: serializer.fromJson<bool>(json['customerAutoReset']),
      evidenceRetentionDays: serializer.fromJson<int>(
        json['evidenceRetentionDays'],
      ),
      locale: serializer.fromJson<String>(json['locale']),
      kioskDisplayName: serializer.fromJson<String>(json['kioskDisplayName']),
      adminAuthorLabel: serializer.fromJson<String>(json['adminAuthorLabel']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'revisionId': serializer.toJson<String>(revisionId),
      'createdAtUs': serializer.toJson<int>(createdAtUs),
      'retryLimit': serializer.toJson<int>(retryLimit),
      'paymentCompleteDurationSeconds': serializer.toJson<int>(
        paymentCompleteDurationSeconds,
      ),
      'customerAutoReset': serializer.toJson<bool>(customerAutoReset),
      'evidenceRetentionDays': serializer.toJson<int>(evidenceRetentionDays),
      'locale': serializer.toJson<String>(locale),
      'kioskDisplayName': serializer.toJson<String>(kioskDisplayName),
      'adminAuthorLabel': serializer.toJson<String>(adminAuthorLabel),
    };
  }

  SettingsRevisionRow copyWith({
    String? revisionId,
    int? createdAtUs,
    int? retryLimit,
    int? paymentCompleteDurationSeconds,
    bool? customerAutoReset,
    int? evidenceRetentionDays,
    String? locale,
    String? kioskDisplayName,
    String? adminAuthorLabel,
  }) => SettingsRevisionRow(
    revisionId: revisionId ?? this.revisionId,
    createdAtUs: createdAtUs ?? this.createdAtUs,
    retryLimit: retryLimit ?? this.retryLimit,
    paymentCompleteDurationSeconds:
        paymentCompleteDurationSeconds ?? this.paymentCompleteDurationSeconds,
    customerAutoReset: customerAutoReset ?? this.customerAutoReset,
    evidenceRetentionDays: evidenceRetentionDays ?? this.evidenceRetentionDays,
    locale: locale ?? this.locale,
    kioskDisplayName: kioskDisplayName ?? this.kioskDisplayName,
    adminAuthorLabel: adminAuthorLabel ?? this.adminAuthorLabel,
  );
  SettingsRevisionRow copyWithCompanion(SettingsRevisionsCompanion data) {
    return SettingsRevisionRow(
      revisionId: data.revisionId.present
          ? data.revisionId.value
          : this.revisionId,
      createdAtUs: data.createdAtUs.present
          ? data.createdAtUs.value
          : this.createdAtUs,
      retryLimit: data.retryLimit.present
          ? data.retryLimit.value
          : this.retryLimit,
      paymentCompleteDurationSeconds:
          data.paymentCompleteDurationSeconds.present
          ? data.paymentCompleteDurationSeconds.value
          : this.paymentCompleteDurationSeconds,
      customerAutoReset: data.customerAutoReset.present
          ? data.customerAutoReset.value
          : this.customerAutoReset,
      evidenceRetentionDays: data.evidenceRetentionDays.present
          ? data.evidenceRetentionDays.value
          : this.evidenceRetentionDays,
      locale: data.locale.present ? data.locale.value : this.locale,
      kioskDisplayName: data.kioskDisplayName.present
          ? data.kioskDisplayName.value
          : this.kioskDisplayName,
      adminAuthorLabel: data.adminAuthorLabel.present
          ? data.adminAuthorLabel.value
          : this.adminAuthorLabel,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SettingsRevisionRow(')
          ..write('revisionId: $revisionId, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('retryLimit: $retryLimit, ')
          ..write(
            'paymentCompleteDurationSeconds: $paymentCompleteDurationSeconds, ',
          )
          ..write('customerAutoReset: $customerAutoReset, ')
          ..write('evidenceRetentionDays: $evidenceRetentionDays, ')
          ..write('locale: $locale, ')
          ..write('kioskDisplayName: $kioskDisplayName, ')
          ..write('adminAuthorLabel: $adminAuthorLabel')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    revisionId,
    createdAtUs,
    retryLimit,
    paymentCompleteDurationSeconds,
    customerAutoReset,
    evidenceRetentionDays,
    locale,
    kioskDisplayName,
    adminAuthorLabel,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SettingsRevisionRow &&
          other.revisionId == this.revisionId &&
          other.createdAtUs == this.createdAtUs &&
          other.retryLimit == this.retryLimit &&
          other.paymentCompleteDurationSeconds ==
              this.paymentCompleteDurationSeconds &&
          other.customerAutoReset == this.customerAutoReset &&
          other.evidenceRetentionDays == this.evidenceRetentionDays &&
          other.locale == this.locale &&
          other.kioskDisplayName == this.kioskDisplayName &&
          other.adminAuthorLabel == this.adminAuthorLabel);
}

class SettingsRevisionsCompanion extends UpdateCompanion<SettingsRevisionRow> {
  final Value<String> revisionId;
  final Value<int> createdAtUs;
  final Value<int> retryLimit;
  final Value<int> paymentCompleteDurationSeconds;
  final Value<bool> customerAutoReset;
  final Value<int> evidenceRetentionDays;
  final Value<String> locale;
  final Value<String> kioskDisplayName;
  final Value<String> adminAuthorLabel;
  final Value<int> rowid;
  const SettingsRevisionsCompanion({
    this.revisionId = const Value.absent(),
    this.createdAtUs = const Value.absent(),
    this.retryLimit = const Value.absent(),
    this.paymentCompleteDurationSeconds = const Value.absent(),
    this.customerAutoReset = const Value.absent(),
    this.evidenceRetentionDays = const Value.absent(),
    this.locale = const Value.absent(),
    this.kioskDisplayName = const Value.absent(),
    this.adminAuthorLabel = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SettingsRevisionsCompanion.insert({
    required String revisionId,
    required int createdAtUs,
    required int retryLimit,
    required int paymentCompleteDurationSeconds,
    required bool customerAutoReset,
    required int evidenceRetentionDays,
    required String locale,
    required String kioskDisplayName,
    required String adminAuthorLabel,
    this.rowid = const Value.absent(),
  }) : revisionId = Value(revisionId),
       createdAtUs = Value(createdAtUs),
       retryLimit = Value(retryLimit),
       paymentCompleteDurationSeconds = Value(paymentCompleteDurationSeconds),
       customerAutoReset = Value(customerAutoReset),
       evidenceRetentionDays = Value(evidenceRetentionDays),
       locale = Value(locale),
       kioskDisplayName = Value(kioskDisplayName),
       adminAuthorLabel = Value(adminAuthorLabel);
  static Insertable<SettingsRevisionRow> custom({
    Expression<String>? revisionId,
    Expression<int>? createdAtUs,
    Expression<int>? retryLimit,
    Expression<int>? paymentCompleteDurationSeconds,
    Expression<bool>? customerAutoReset,
    Expression<int>? evidenceRetentionDays,
    Expression<String>? locale,
    Expression<String>? kioskDisplayName,
    Expression<String>? adminAuthorLabel,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (revisionId != null) 'revision_id': revisionId,
      if (createdAtUs != null) 'created_at_us': createdAtUs,
      if (retryLimit != null) 'retry_limit': retryLimit,
      if (paymentCompleteDurationSeconds != null)
        'payment_complete_duration_seconds': paymentCompleteDurationSeconds,
      if (customerAutoReset != null) 'customer_auto_reset': customerAutoReset,
      if (evidenceRetentionDays != null)
        'evidence_retention_days': evidenceRetentionDays,
      if (locale != null) 'locale': locale,
      if (kioskDisplayName != null) 'kiosk_display_name': kioskDisplayName,
      if (adminAuthorLabel != null) 'admin_author_label': adminAuthorLabel,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SettingsRevisionsCompanion copyWith({
    Value<String>? revisionId,
    Value<int>? createdAtUs,
    Value<int>? retryLimit,
    Value<int>? paymentCompleteDurationSeconds,
    Value<bool>? customerAutoReset,
    Value<int>? evidenceRetentionDays,
    Value<String>? locale,
    Value<String>? kioskDisplayName,
    Value<String>? adminAuthorLabel,
    Value<int>? rowid,
  }) {
    return SettingsRevisionsCompanion(
      revisionId: revisionId ?? this.revisionId,
      createdAtUs: createdAtUs ?? this.createdAtUs,
      retryLimit: retryLimit ?? this.retryLimit,
      paymentCompleteDurationSeconds:
          paymentCompleteDurationSeconds ?? this.paymentCompleteDurationSeconds,
      customerAutoReset: customerAutoReset ?? this.customerAutoReset,
      evidenceRetentionDays:
          evidenceRetentionDays ?? this.evidenceRetentionDays,
      locale: locale ?? this.locale,
      kioskDisplayName: kioskDisplayName ?? this.kioskDisplayName,
      adminAuthorLabel: adminAuthorLabel ?? this.adminAuthorLabel,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (revisionId.present) {
      map['revision_id'] = Variable<String>(revisionId.value);
    }
    if (createdAtUs.present) {
      map['created_at_us'] = Variable<int>(createdAtUs.value);
    }
    if (retryLimit.present) {
      map['retry_limit'] = Variable<int>(retryLimit.value);
    }
    if (paymentCompleteDurationSeconds.present) {
      map['payment_complete_duration_seconds'] = Variable<int>(
        paymentCompleteDurationSeconds.value,
      );
    }
    if (customerAutoReset.present) {
      map['customer_auto_reset'] = Variable<bool>(customerAutoReset.value);
    }
    if (evidenceRetentionDays.present) {
      map['evidence_retention_days'] = Variable<int>(
        evidenceRetentionDays.value,
      );
    }
    if (locale.present) {
      map['locale'] = Variable<String>(locale.value);
    }
    if (kioskDisplayName.present) {
      map['kiosk_display_name'] = Variable<String>(kioskDisplayName.value);
    }
    if (adminAuthorLabel.present) {
      map['admin_author_label'] = Variable<String>(adminAuthorLabel.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SettingsRevisionsCompanion(')
          ..write('revisionId: $revisionId, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('retryLimit: $retryLimit, ')
          ..write(
            'paymentCompleteDurationSeconds: $paymentCompleteDurationSeconds, ',
          )
          ..write('customerAutoReset: $customerAutoReset, ')
          ..write('evidenceRetentionDays: $evidenceRetentionDays, ')
          ..write('locale: $locale, ')
          ..write('kioskDisplayName: $kioskDisplayName, ')
          ..write('adminAuthorLabel: $adminAuthorLabel, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $CheckoutSessionsTable extends CheckoutSessions
    with TableInfo<$CheckoutSessionsTable, CheckoutSessionRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $CheckoutSessionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _stateMeta = const VerificationMeta('state');
  @override
  late final GeneratedColumn<String> state = GeneratedColumn<String>(
    'state',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _startedAtUsMeta = const VerificationMeta(
    'startedAtUs',
  );
  @override
  late final GeneratedColumn<int> startedAtUs = GeneratedColumn<int>(
    'started_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _terminalAtUsMeta = const VerificationMeta(
    'terminalAtUs',
  );
  @override
  late final GeneratedColumn<int> terminalAtUs = GeneratedColumn<int>(
    'terminal_at_us',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _terminalReasonMeta = const VerificationMeta(
    'terminalReason',
  );
  @override
  late final GeneratedColumn<String> terminalReason = GeneratedColumn<String>(
    'terminal_reason',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _catalogRevisionIdMeta = const VerificationMeta(
    'catalogRevisionId',
  );
  @override
  late final GeneratedColumn<String> catalogRevisionId =
      GeneratedColumn<String>(
        'catalog_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES catalog_revisions (revision_id)',
        ),
      );
  static const VerificationMeta _settingsRevisionIdMeta =
      const VerificationMeta('settingsRevisionId');
  @override
  late final GeneratedColumn<String> settingsRevisionId =
      GeneratedColumn<String>(
        'settings_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES settings_revisions (revision_id)',
        ),
      );
  static const VerificationMeta _detectorIdMeta = const VerificationMeta(
    'detectorId',
  );
  @override
  late final GeneratedColumn<String> detectorId = GeneratedColumn<String>(
    'detector_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _detectorSha256Meta = const VerificationMeta(
    'detectorSha256',
  );
  @override
  late final GeneratedColumn<String> detectorSha256 = GeneratedColumn<String>(
    'detector_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _repvitArtifactIdMeta = const VerificationMeta(
    'repvitArtifactId',
  );
  @override
  late final GeneratedColumn<String> repvitArtifactId = GeneratedColumn<String>(
    'repvit_artifact_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _repvitSha256Meta = const VerificationMeta(
    'repvitSha256',
  );
  @override
  late final GeneratedColumn<String> repvitSha256 = GeneratedColumn<String>(
    'repvit_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _repvitManifestSha256Meta =
      const VerificationMeta('repvitManifestSha256');
  @override
  late final GeneratedColumn<String> repvitManifestSha256 =
      GeneratedColumn<String>(
        'repvit_manifest_sha256',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _repvitPrototypeSha256Meta =
      const VerificationMeta('repvitPrototypeSha256');
  @override
  late final GeneratedColumn<String> repvitPrototypeSha256 =
      GeneratedColumn<String>(
        'repvit_prototype_sha256',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _dinov3ArtifactIdMeta = const VerificationMeta(
    'dinov3ArtifactId',
  );
  @override
  late final GeneratedColumn<String> dinov3ArtifactId = GeneratedColumn<String>(
    'dinov3_artifact_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dinov3Sha256Meta = const VerificationMeta(
    'dinov3Sha256',
  );
  @override
  late final GeneratedColumn<String> dinov3Sha256 = GeneratedColumn<String>(
    'dinov3_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _dinov3SupportSha256Meta =
      const VerificationMeta('dinov3SupportSha256');
  @override
  late final GeneratedColumn<String> dinov3SupportSha256 =
      GeneratedColumn<String>(
        'dinov3_support_sha256',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _calibrationIdMeta = const VerificationMeta(
    'calibrationId',
  );
  @override
  late final GeneratedColumn<String> calibrationId = GeneratedColumn<String>(
    'calibration_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _calibrationSha256Meta = const VerificationMeta(
    'calibrationSha256',
  );
  @override
  late final GeneratedColumn<String> calibrationSha256 =
      GeneratedColumn<String>(
        'calibration_sha256',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _preprocessSha256Meta = const VerificationMeta(
    'preprocessSha256',
  );
  @override
  late final GeneratedColumn<String> preprocessSha256 = GeneratedColumn<String>(
    'preprocess_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _fusionPolicyIdMeta = const VerificationMeta(
    'fusionPolicyId',
  );
  @override
  late final GeneratedColumn<String> fusionPolicyId = GeneratedColumn<String>(
    'fusion_policy_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _fusionPolicySha256Meta =
      const VerificationMeta('fusionPolicySha256');
  @override
  late final GeneratedColumn<String> fusionPolicySha256 =
      GeneratedColumn<String>(
        'fusion_policy_sha256',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _configSnapshotJsonMeta =
      const VerificationMeta('configSnapshotJson');
  @override
  late final GeneratedColumn<String> configSnapshotJson =
      GeneratedColumn<String>(
        'config_snapshot_json',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 2),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  @override
  List<GeneratedColumn> get $columns => [
    sessionId,
    state,
    startedAtUs,
    terminalAtUs,
    terminalReason,
    catalogRevisionId,
    settingsRevisionId,
    detectorId,
    detectorSha256,
    repvitArtifactId,
    repvitSha256,
    repvitManifestSha256,
    repvitPrototypeSha256,
    dinov3ArtifactId,
    dinov3Sha256,
    dinov3SupportSha256,
    calibrationId,
    calibrationSha256,
    preprocessSha256,
    fusionPolicyId,
    fusionPolicySha256,
    configSnapshotJson,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'checkout_sessions';
  @override
  VerificationContext validateIntegrity(
    Insertable<CheckoutSessionRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('state')) {
      context.handle(
        _stateMeta,
        state.isAcceptableOrUnknown(data['state']!, _stateMeta),
      );
    } else if (isInserting) {
      context.missing(_stateMeta);
    }
    if (data.containsKey('started_at_us')) {
      context.handle(
        _startedAtUsMeta,
        startedAtUs.isAcceptableOrUnknown(
          data['started_at_us']!,
          _startedAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_startedAtUsMeta);
    }
    if (data.containsKey('terminal_at_us')) {
      context.handle(
        _terminalAtUsMeta,
        terminalAtUs.isAcceptableOrUnknown(
          data['terminal_at_us']!,
          _terminalAtUsMeta,
        ),
      );
    }
    if (data.containsKey('terminal_reason')) {
      context.handle(
        _terminalReasonMeta,
        terminalReason.isAcceptableOrUnknown(
          data['terminal_reason']!,
          _terminalReasonMeta,
        ),
      );
    }
    if (data.containsKey('catalog_revision_id')) {
      context.handle(
        _catalogRevisionIdMeta,
        catalogRevisionId.isAcceptableOrUnknown(
          data['catalog_revision_id']!,
          _catalogRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_catalogRevisionIdMeta);
    }
    if (data.containsKey('settings_revision_id')) {
      context.handle(
        _settingsRevisionIdMeta,
        settingsRevisionId.isAcceptableOrUnknown(
          data['settings_revision_id']!,
          _settingsRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_settingsRevisionIdMeta);
    }
    if (data.containsKey('detector_id')) {
      context.handle(
        _detectorIdMeta,
        detectorId.isAcceptableOrUnknown(data['detector_id']!, _detectorIdMeta),
      );
    } else if (isInserting) {
      context.missing(_detectorIdMeta);
    }
    if (data.containsKey('detector_sha256')) {
      context.handle(
        _detectorSha256Meta,
        detectorSha256.isAcceptableOrUnknown(
          data['detector_sha256']!,
          _detectorSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_detectorSha256Meta);
    }
    if (data.containsKey('repvit_artifact_id')) {
      context.handle(
        _repvitArtifactIdMeta,
        repvitArtifactId.isAcceptableOrUnknown(
          data['repvit_artifact_id']!,
          _repvitArtifactIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_repvitArtifactIdMeta);
    }
    if (data.containsKey('repvit_sha256')) {
      context.handle(
        _repvitSha256Meta,
        repvitSha256.isAcceptableOrUnknown(
          data['repvit_sha256']!,
          _repvitSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_repvitSha256Meta);
    }
    if (data.containsKey('repvit_manifest_sha256')) {
      context.handle(
        _repvitManifestSha256Meta,
        repvitManifestSha256.isAcceptableOrUnknown(
          data['repvit_manifest_sha256']!,
          _repvitManifestSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_repvitManifestSha256Meta);
    }
    if (data.containsKey('repvit_prototype_sha256')) {
      context.handle(
        _repvitPrototypeSha256Meta,
        repvitPrototypeSha256.isAcceptableOrUnknown(
          data['repvit_prototype_sha256']!,
          _repvitPrototypeSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_repvitPrototypeSha256Meta);
    }
    if (data.containsKey('dinov3_artifact_id')) {
      context.handle(
        _dinov3ArtifactIdMeta,
        dinov3ArtifactId.isAcceptableOrUnknown(
          data['dinov3_artifact_id']!,
          _dinov3ArtifactIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_dinov3ArtifactIdMeta);
    }
    if (data.containsKey('dinov3_sha256')) {
      context.handle(
        _dinov3Sha256Meta,
        dinov3Sha256.isAcceptableOrUnknown(
          data['dinov3_sha256']!,
          _dinov3Sha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_dinov3Sha256Meta);
    }
    if (data.containsKey('dinov3_support_sha256')) {
      context.handle(
        _dinov3SupportSha256Meta,
        dinov3SupportSha256.isAcceptableOrUnknown(
          data['dinov3_support_sha256']!,
          _dinov3SupportSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_dinov3SupportSha256Meta);
    }
    if (data.containsKey('calibration_id')) {
      context.handle(
        _calibrationIdMeta,
        calibrationId.isAcceptableOrUnknown(
          data['calibration_id']!,
          _calibrationIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_calibrationIdMeta);
    }
    if (data.containsKey('calibration_sha256')) {
      context.handle(
        _calibrationSha256Meta,
        calibrationSha256.isAcceptableOrUnknown(
          data['calibration_sha256']!,
          _calibrationSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_calibrationSha256Meta);
    }
    if (data.containsKey('preprocess_sha256')) {
      context.handle(
        _preprocessSha256Meta,
        preprocessSha256.isAcceptableOrUnknown(
          data['preprocess_sha256']!,
          _preprocessSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_preprocessSha256Meta);
    }
    if (data.containsKey('fusion_policy_id')) {
      context.handle(
        _fusionPolicyIdMeta,
        fusionPolicyId.isAcceptableOrUnknown(
          data['fusion_policy_id']!,
          _fusionPolicyIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_fusionPolicyIdMeta);
    }
    if (data.containsKey('fusion_policy_sha256')) {
      context.handle(
        _fusionPolicySha256Meta,
        fusionPolicySha256.isAcceptableOrUnknown(
          data['fusion_policy_sha256']!,
          _fusionPolicySha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_fusionPolicySha256Meta);
    }
    if (data.containsKey('config_snapshot_json')) {
      context.handle(
        _configSnapshotJsonMeta,
        configSnapshotJson.isAcceptableOrUnknown(
          data['config_snapshot_json']!,
          _configSnapshotJsonMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_configSnapshotJsonMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {sessionId};
  @override
  CheckoutSessionRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return CheckoutSessionRow(
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      state: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}state'],
      )!,
      startedAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}started_at_us'],
      )!,
      terminalAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}terminal_at_us'],
      ),
      terminalReason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}terminal_reason'],
      ),
      catalogRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}catalog_revision_id'],
      )!,
      settingsRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}settings_revision_id'],
      )!,
      detectorId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}detector_id'],
      )!,
      detectorSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}detector_sha256'],
      )!,
      repvitArtifactId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}repvit_artifact_id'],
      )!,
      repvitSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}repvit_sha256'],
      )!,
      repvitManifestSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}repvit_manifest_sha256'],
      )!,
      repvitPrototypeSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}repvit_prototype_sha256'],
      )!,
      dinov3ArtifactId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}dinov3_artifact_id'],
      )!,
      dinov3Sha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}dinov3_sha256'],
      )!,
      dinov3SupportSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}dinov3_support_sha256'],
      )!,
      calibrationId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}calibration_id'],
      )!,
      calibrationSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}calibration_sha256'],
      )!,
      preprocessSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}preprocess_sha256'],
      )!,
      fusionPolicyId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}fusion_policy_id'],
      )!,
      fusionPolicySha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}fusion_policy_sha256'],
      )!,
      configSnapshotJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}config_snapshot_json'],
      )!,
    );
  }

  @override
  $CheckoutSessionsTable createAlias(String alias) {
    return $CheckoutSessionsTable(attachedDatabase, alias);
  }
}

class CheckoutSessionRow extends DataClass
    implements Insertable<CheckoutSessionRow> {
  final String sessionId;
  final String state;
  final int startedAtUs;
  final int? terminalAtUs;
  final String? terminalReason;
  final String catalogRevisionId;
  final String settingsRevisionId;
  final String detectorId;
  final String detectorSha256;
  final String repvitArtifactId;
  final String repvitSha256;
  final String repvitManifestSha256;
  final String repvitPrototypeSha256;
  final String dinov3ArtifactId;
  final String dinov3Sha256;
  final String dinov3SupportSha256;
  final String calibrationId;
  final String calibrationSha256;
  final String preprocessSha256;
  final String fusionPolicyId;
  final String fusionPolicySha256;
  final String configSnapshotJson;
  const CheckoutSessionRow({
    required this.sessionId,
    required this.state,
    required this.startedAtUs,
    this.terminalAtUs,
    this.terminalReason,
    required this.catalogRevisionId,
    required this.settingsRevisionId,
    required this.detectorId,
    required this.detectorSha256,
    required this.repvitArtifactId,
    required this.repvitSha256,
    required this.repvitManifestSha256,
    required this.repvitPrototypeSha256,
    required this.dinov3ArtifactId,
    required this.dinov3Sha256,
    required this.dinov3SupportSha256,
    required this.calibrationId,
    required this.calibrationSha256,
    required this.preprocessSha256,
    required this.fusionPolicyId,
    required this.fusionPolicySha256,
    required this.configSnapshotJson,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['session_id'] = Variable<String>(sessionId);
    map['state'] = Variable<String>(state);
    map['started_at_us'] = Variable<int>(startedAtUs);
    if (!nullToAbsent || terminalAtUs != null) {
      map['terminal_at_us'] = Variable<int>(terminalAtUs);
    }
    if (!nullToAbsent || terminalReason != null) {
      map['terminal_reason'] = Variable<String>(terminalReason);
    }
    map['catalog_revision_id'] = Variable<String>(catalogRevisionId);
    map['settings_revision_id'] = Variable<String>(settingsRevisionId);
    map['detector_id'] = Variable<String>(detectorId);
    map['detector_sha256'] = Variable<String>(detectorSha256);
    map['repvit_artifact_id'] = Variable<String>(repvitArtifactId);
    map['repvit_sha256'] = Variable<String>(repvitSha256);
    map['repvit_manifest_sha256'] = Variable<String>(repvitManifestSha256);
    map['repvit_prototype_sha256'] = Variable<String>(repvitPrototypeSha256);
    map['dinov3_artifact_id'] = Variable<String>(dinov3ArtifactId);
    map['dinov3_sha256'] = Variable<String>(dinov3Sha256);
    map['dinov3_support_sha256'] = Variable<String>(dinov3SupportSha256);
    map['calibration_id'] = Variable<String>(calibrationId);
    map['calibration_sha256'] = Variable<String>(calibrationSha256);
    map['preprocess_sha256'] = Variable<String>(preprocessSha256);
    map['fusion_policy_id'] = Variable<String>(fusionPolicyId);
    map['fusion_policy_sha256'] = Variable<String>(fusionPolicySha256);
    map['config_snapshot_json'] = Variable<String>(configSnapshotJson);
    return map;
  }

  CheckoutSessionsCompanion toCompanion(bool nullToAbsent) {
    return CheckoutSessionsCompanion(
      sessionId: Value(sessionId),
      state: Value(state),
      startedAtUs: Value(startedAtUs),
      terminalAtUs: terminalAtUs == null && nullToAbsent
          ? const Value.absent()
          : Value(terminalAtUs),
      terminalReason: terminalReason == null && nullToAbsent
          ? const Value.absent()
          : Value(terminalReason),
      catalogRevisionId: Value(catalogRevisionId),
      settingsRevisionId: Value(settingsRevisionId),
      detectorId: Value(detectorId),
      detectorSha256: Value(detectorSha256),
      repvitArtifactId: Value(repvitArtifactId),
      repvitSha256: Value(repvitSha256),
      repvitManifestSha256: Value(repvitManifestSha256),
      repvitPrototypeSha256: Value(repvitPrototypeSha256),
      dinov3ArtifactId: Value(dinov3ArtifactId),
      dinov3Sha256: Value(dinov3Sha256),
      dinov3SupportSha256: Value(dinov3SupportSha256),
      calibrationId: Value(calibrationId),
      calibrationSha256: Value(calibrationSha256),
      preprocessSha256: Value(preprocessSha256),
      fusionPolicyId: Value(fusionPolicyId),
      fusionPolicySha256: Value(fusionPolicySha256),
      configSnapshotJson: Value(configSnapshotJson),
    );
  }

  factory CheckoutSessionRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return CheckoutSessionRow(
      sessionId: serializer.fromJson<String>(json['sessionId']),
      state: serializer.fromJson<String>(json['state']),
      startedAtUs: serializer.fromJson<int>(json['startedAtUs']),
      terminalAtUs: serializer.fromJson<int?>(json['terminalAtUs']),
      terminalReason: serializer.fromJson<String?>(json['terminalReason']),
      catalogRevisionId: serializer.fromJson<String>(json['catalogRevisionId']),
      settingsRevisionId: serializer.fromJson<String>(
        json['settingsRevisionId'],
      ),
      detectorId: serializer.fromJson<String>(json['detectorId']),
      detectorSha256: serializer.fromJson<String>(json['detectorSha256']),
      repvitArtifactId: serializer.fromJson<String>(json['repvitArtifactId']),
      repvitSha256: serializer.fromJson<String>(json['repvitSha256']),
      repvitManifestSha256: serializer.fromJson<String>(
        json['repvitManifestSha256'],
      ),
      repvitPrototypeSha256: serializer.fromJson<String>(
        json['repvitPrototypeSha256'],
      ),
      dinov3ArtifactId: serializer.fromJson<String>(json['dinov3ArtifactId']),
      dinov3Sha256: serializer.fromJson<String>(json['dinov3Sha256']),
      dinov3SupportSha256: serializer.fromJson<String>(
        json['dinov3SupportSha256'],
      ),
      calibrationId: serializer.fromJson<String>(json['calibrationId']),
      calibrationSha256: serializer.fromJson<String>(json['calibrationSha256']),
      preprocessSha256: serializer.fromJson<String>(json['preprocessSha256']),
      fusionPolicyId: serializer.fromJson<String>(json['fusionPolicyId']),
      fusionPolicySha256: serializer.fromJson<String>(
        json['fusionPolicySha256'],
      ),
      configSnapshotJson: serializer.fromJson<String>(
        json['configSnapshotJson'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'sessionId': serializer.toJson<String>(sessionId),
      'state': serializer.toJson<String>(state),
      'startedAtUs': serializer.toJson<int>(startedAtUs),
      'terminalAtUs': serializer.toJson<int?>(terminalAtUs),
      'terminalReason': serializer.toJson<String?>(terminalReason),
      'catalogRevisionId': serializer.toJson<String>(catalogRevisionId),
      'settingsRevisionId': serializer.toJson<String>(settingsRevisionId),
      'detectorId': serializer.toJson<String>(detectorId),
      'detectorSha256': serializer.toJson<String>(detectorSha256),
      'repvitArtifactId': serializer.toJson<String>(repvitArtifactId),
      'repvitSha256': serializer.toJson<String>(repvitSha256),
      'repvitManifestSha256': serializer.toJson<String>(repvitManifestSha256),
      'repvitPrototypeSha256': serializer.toJson<String>(repvitPrototypeSha256),
      'dinov3ArtifactId': serializer.toJson<String>(dinov3ArtifactId),
      'dinov3Sha256': serializer.toJson<String>(dinov3Sha256),
      'dinov3SupportSha256': serializer.toJson<String>(dinov3SupportSha256),
      'calibrationId': serializer.toJson<String>(calibrationId),
      'calibrationSha256': serializer.toJson<String>(calibrationSha256),
      'preprocessSha256': serializer.toJson<String>(preprocessSha256),
      'fusionPolicyId': serializer.toJson<String>(fusionPolicyId),
      'fusionPolicySha256': serializer.toJson<String>(fusionPolicySha256),
      'configSnapshotJson': serializer.toJson<String>(configSnapshotJson),
    };
  }

  CheckoutSessionRow copyWith({
    String? sessionId,
    String? state,
    int? startedAtUs,
    Value<int?> terminalAtUs = const Value.absent(),
    Value<String?> terminalReason = const Value.absent(),
    String? catalogRevisionId,
    String? settingsRevisionId,
    String? detectorId,
    String? detectorSha256,
    String? repvitArtifactId,
    String? repvitSha256,
    String? repvitManifestSha256,
    String? repvitPrototypeSha256,
    String? dinov3ArtifactId,
    String? dinov3Sha256,
    String? dinov3SupportSha256,
    String? calibrationId,
    String? calibrationSha256,
    String? preprocessSha256,
    String? fusionPolicyId,
    String? fusionPolicySha256,
    String? configSnapshotJson,
  }) => CheckoutSessionRow(
    sessionId: sessionId ?? this.sessionId,
    state: state ?? this.state,
    startedAtUs: startedAtUs ?? this.startedAtUs,
    terminalAtUs: terminalAtUs.present ? terminalAtUs.value : this.terminalAtUs,
    terminalReason: terminalReason.present
        ? terminalReason.value
        : this.terminalReason,
    catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
    settingsRevisionId: settingsRevisionId ?? this.settingsRevisionId,
    detectorId: detectorId ?? this.detectorId,
    detectorSha256: detectorSha256 ?? this.detectorSha256,
    repvitArtifactId: repvitArtifactId ?? this.repvitArtifactId,
    repvitSha256: repvitSha256 ?? this.repvitSha256,
    repvitManifestSha256: repvitManifestSha256 ?? this.repvitManifestSha256,
    repvitPrototypeSha256: repvitPrototypeSha256 ?? this.repvitPrototypeSha256,
    dinov3ArtifactId: dinov3ArtifactId ?? this.dinov3ArtifactId,
    dinov3Sha256: dinov3Sha256 ?? this.dinov3Sha256,
    dinov3SupportSha256: dinov3SupportSha256 ?? this.dinov3SupportSha256,
    calibrationId: calibrationId ?? this.calibrationId,
    calibrationSha256: calibrationSha256 ?? this.calibrationSha256,
    preprocessSha256: preprocessSha256 ?? this.preprocessSha256,
    fusionPolicyId: fusionPolicyId ?? this.fusionPolicyId,
    fusionPolicySha256: fusionPolicySha256 ?? this.fusionPolicySha256,
    configSnapshotJson: configSnapshotJson ?? this.configSnapshotJson,
  );
  CheckoutSessionRow copyWithCompanion(CheckoutSessionsCompanion data) {
    return CheckoutSessionRow(
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      state: data.state.present ? data.state.value : this.state,
      startedAtUs: data.startedAtUs.present
          ? data.startedAtUs.value
          : this.startedAtUs,
      terminalAtUs: data.terminalAtUs.present
          ? data.terminalAtUs.value
          : this.terminalAtUs,
      terminalReason: data.terminalReason.present
          ? data.terminalReason.value
          : this.terminalReason,
      catalogRevisionId: data.catalogRevisionId.present
          ? data.catalogRevisionId.value
          : this.catalogRevisionId,
      settingsRevisionId: data.settingsRevisionId.present
          ? data.settingsRevisionId.value
          : this.settingsRevisionId,
      detectorId: data.detectorId.present
          ? data.detectorId.value
          : this.detectorId,
      detectorSha256: data.detectorSha256.present
          ? data.detectorSha256.value
          : this.detectorSha256,
      repvitArtifactId: data.repvitArtifactId.present
          ? data.repvitArtifactId.value
          : this.repvitArtifactId,
      repvitSha256: data.repvitSha256.present
          ? data.repvitSha256.value
          : this.repvitSha256,
      repvitManifestSha256: data.repvitManifestSha256.present
          ? data.repvitManifestSha256.value
          : this.repvitManifestSha256,
      repvitPrototypeSha256: data.repvitPrototypeSha256.present
          ? data.repvitPrototypeSha256.value
          : this.repvitPrototypeSha256,
      dinov3ArtifactId: data.dinov3ArtifactId.present
          ? data.dinov3ArtifactId.value
          : this.dinov3ArtifactId,
      dinov3Sha256: data.dinov3Sha256.present
          ? data.dinov3Sha256.value
          : this.dinov3Sha256,
      dinov3SupportSha256: data.dinov3SupportSha256.present
          ? data.dinov3SupportSha256.value
          : this.dinov3SupportSha256,
      calibrationId: data.calibrationId.present
          ? data.calibrationId.value
          : this.calibrationId,
      calibrationSha256: data.calibrationSha256.present
          ? data.calibrationSha256.value
          : this.calibrationSha256,
      preprocessSha256: data.preprocessSha256.present
          ? data.preprocessSha256.value
          : this.preprocessSha256,
      fusionPolicyId: data.fusionPolicyId.present
          ? data.fusionPolicyId.value
          : this.fusionPolicyId,
      fusionPolicySha256: data.fusionPolicySha256.present
          ? data.fusionPolicySha256.value
          : this.fusionPolicySha256,
      configSnapshotJson: data.configSnapshotJson.present
          ? data.configSnapshotJson.value
          : this.configSnapshotJson,
    );
  }

  @override
  String toString() {
    return (StringBuffer('CheckoutSessionRow(')
          ..write('sessionId: $sessionId, ')
          ..write('state: $state, ')
          ..write('startedAtUs: $startedAtUs, ')
          ..write('terminalAtUs: $terminalAtUs, ')
          ..write('terminalReason: $terminalReason, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('settingsRevisionId: $settingsRevisionId, ')
          ..write('detectorId: $detectorId, ')
          ..write('detectorSha256: $detectorSha256, ')
          ..write('repvitArtifactId: $repvitArtifactId, ')
          ..write('repvitSha256: $repvitSha256, ')
          ..write('repvitManifestSha256: $repvitManifestSha256, ')
          ..write('repvitPrototypeSha256: $repvitPrototypeSha256, ')
          ..write('dinov3ArtifactId: $dinov3ArtifactId, ')
          ..write('dinov3Sha256: $dinov3Sha256, ')
          ..write('dinov3SupportSha256: $dinov3SupportSha256, ')
          ..write('calibrationId: $calibrationId, ')
          ..write('calibrationSha256: $calibrationSha256, ')
          ..write('preprocessSha256: $preprocessSha256, ')
          ..write('fusionPolicyId: $fusionPolicyId, ')
          ..write('fusionPolicySha256: $fusionPolicySha256, ')
          ..write('configSnapshotJson: $configSnapshotJson')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hashAll([
    sessionId,
    state,
    startedAtUs,
    terminalAtUs,
    terminalReason,
    catalogRevisionId,
    settingsRevisionId,
    detectorId,
    detectorSha256,
    repvitArtifactId,
    repvitSha256,
    repvitManifestSha256,
    repvitPrototypeSha256,
    dinov3ArtifactId,
    dinov3Sha256,
    dinov3SupportSha256,
    calibrationId,
    calibrationSha256,
    preprocessSha256,
    fusionPolicyId,
    fusionPolicySha256,
    configSnapshotJson,
  ]);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is CheckoutSessionRow &&
          other.sessionId == this.sessionId &&
          other.state == this.state &&
          other.startedAtUs == this.startedAtUs &&
          other.terminalAtUs == this.terminalAtUs &&
          other.terminalReason == this.terminalReason &&
          other.catalogRevisionId == this.catalogRevisionId &&
          other.settingsRevisionId == this.settingsRevisionId &&
          other.detectorId == this.detectorId &&
          other.detectorSha256 == this.detectorSha256 &&
          other.repvitArtifactId == this.repvitArtifactId &&
          other.repvitSha256 == this.repvitSha256 &&
          other.repvitManifestSha256 == this.repvitManifestSha256 &&
          other.repvitPrototypeSha256 == this.repvitPrototypeSha256 &&
          other.dinov3ArtifactId == this.dinov3ArtifactId &&
          other.dinov3Sha256 == this.dinov3Sha256 &&
          other.dinov3SupportSha256 == this.dinov3SupportSha256 &&
          other.calibrationId == this.calibrationId &&
          other.calibrationSha256 == this.calibrationSha256 &&
          other.preprocessSha256 == this.preprocessSha256 &&
          other.fusionPolicyId == this.fusionPolicyId &&
          other.fusionPolicySha256 == this.fusionPolicySha256 &&
          other.configSnapshotJson == this.configSnapshotJson);
}

class CheckoutSessionsCompanion extends UpdateCompanion<CheckoutSessionRow> {
  final Value<String> sessionId;
  final Value<String> state;
  final Value<int> startedAtUs;
  final Value<int?> terminalAtUs;
  final Value<String?> terminalReason;
  final Value<String> catalogRevisionId;
  final Value<String> settingsRevisionId;
  final Value<String> detectorId;
  final Value<String> detectorSha256;
  final Value<String> repvitArtifactId;
  final Value<String> repvitSha256;
  final Value<String> repvitManifestSha256;
  final Value<String> repvitPrototypeSha256;
  final Value<String> dinov3ArtifactId;
  final Value<String> dinov3Sha256;
  final Value<String> dinov3SupportSha256;
  final Value<String> calibrationId;
  final Value<String> calibrationSha256;
  final Value<String> preprocessSha256;
  final Value<String> fusionPolicyId;
  final Value<String> fusionPolicySha256;
  final Value<String> configSnapshotJson;
  final Value<int> rowid;
  const CheckoutSessionsCompanion({
    this.sessionId = const Value.absent(),
    this.state = const Value.absent(),
    this.startedAtUs = const Value.absent(),
    this.terminalAtUs = const Value.absent(),
    this.terminalReason = const Value.absent(),
    this.catalogRevisionId = const Value.absent(),
    this.settingsRevisionId = const Value.absent(),
    this.detectorId = const Value.absent(),
    this.detectorSha256 = const Value.absent(),
    this.repvitArtifactId = const Value.absent(),
    this.repvitSha256 = const Value.absent(),
    this.repvitManifestSha256 = const Value.absent(),
    this.repvitPrototypeSha256 = const Value.absent(),
    this.dinov3ArtifactId = const Value.absent(),
    this.dinov3Sha256 = const Value.absent(),
    this.dinov3SupportSha256 = const Value.absent(),
    this.calibrationId = const Value.absent(),
    this.calibrationSha256 = const Value.absent(),
    this.preprocessSha256 = const Value.absent(),
    this.fusionPolicyId = const Value.absent(),
    this.fusionPolicySha256 = const Value.absent(),
    this.configSnapshotJson = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  CheckoutSessionsCompanion.insert({
    required String sessionId,
    required String state,
    required int startedAtUs,
    this.terminalAtUs = const Value.absent(),
    this.terminalReason = const Value.absent(),
    required String catalogRevisionId,
    required String settingsRevisionId,
    required String detectorId,
    required String detectorSha256,
    required String repvitArtifactId,
    required String repvitSha256,
    required String repvitManifestSha256,
    required String repvitPrototypeSha256,
    required String dinov3ArtifactId,
    required String dinov3Sha256,
    required String dinov3SupportSha256,
    required String calibrationId,
    required String calibrationSha256,
    required String preprocessSha256,
    required String fusionPolicyId,
    required String fusionPolicySha256,
    required String configSnapshotJson,
    this.rowid = const Value.absent(),
  }) : sessionId = Value(sessionId),
       state = Value(state),
       startedAtUs = Value(startedAtUs),
       catalogRevisionId = Value(catalogRevisionId),
       settingsRevisionId = Value(settingsRevisionId),
       detectorId = Value(detectorId),
       detectorSha256 = Value(detectorSha256),
       repvitArtifactId = Value(repvitArtifactId),
       repvitSha256 = Value(repvitSha256),
       repvitManifestSha256 = Value(repvitManifestSha256),
       repvitPrototypeSha256 = Value(repvitPrototypeSha256),
       dinov3ArtifactId = Value(dinov3ArtifactId),
       dinov3Sha256 = Value(dinov3Sha256),
       dinov3SupportSha256 = Value(dinov3SupportSha256),
       calibrationId = Value(calibrationId),
       calibrationSha256 = Value(calibrationSha256),
       preprocessSha256 = Value(preprocessSha256),
       fusionPolicyId = Value(fusionPolicyId),
       fusionPolicySha256 = Value(fusionPolicySha256),
       configSnapshotJson = Value(configSnapshotJson);
  static Insertable<CheckoutSessionRow> custom({
    Expression<String>? sessionId,
    Expression<String>? state,
    Expression<int>? startedAtUs,
    Expression<int>? terminalAtUs,
    Expression<String>? terminalReason,
    Expression<String>? catalogRevisionId,
    Expression<String>? settingsRevisionId,
    Expression<String>? detectorId,
    Expression<String>? detectorSha256,
    Expression<String>? repvitArtifactId,
    Expression<String>? repvitSha256,
    Expression<String>? repvitManifestSha256,
    Expression<String>? repvitPrototypeSha256,
    Expression<String>? dinov3ArtifactId,
    Expression<String>? dinov3Sha256,
    Expression<String>? dinov3SupportSha256,
    Expression<String>? calibrationId,
    Expression<String>? calibrationSha256,
    Expression<String>? preprocessSha256,
    Expression<String>? fusionPolicyId,
    Expression<String>? fusionPolicySha256,
    Expression<String>? configSnapshotJson,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (sessionId != null) 'session_id': sessionId,
      if (state != null) 'state': state,
      if (startedAtUs != null) 'started_at_us': startedAtUs,
      if (terminalAtUs != null) 'terminal_at_us': terminalAtUs,
      if (terminalReason != null) 'terminal_reason': terminalReason,
      if (catalogRevisionId != null) 'catalog_revision_id': catalogRevisionId,
      if (settingsRevisionId != null)
        'settings_revision_id': settingsRevisionId,
      if (detectorId != null) 'detector_id': detectorId,
      if (detectorSha256 != null) 'detector_sha256': detectorSha256,
      if (repvitArtifactId != null) 'repvit_artifact_id': repvitArtifactId,
      if (repvitSha256 != null) 'repvit_sha256': repvitSha256,
      if (repvitManifestSha256 != null)
        'repvit_manifest_sha256': repvitManifestSha256,
      if (repvitPrototypeSha256 != null)
        'repvit_prototype_sha256': repvitPrototypeSha256,
      if (dinov3ArtifactId != null) 'dinov3_artifact_id': dinov3ArtifactId,
      if (dinov3Sha256 != null) 'dinov3_sha256': dinov3Sha256,
      if (dinov3SupportSha256 != null)
        'dinov3_support_sha256': dinov3SupportSha256,
      if (calibrationId != null) 'calibration_id': calibrationId,
      if (calibrationSha256 != null) 'calibration_sha256': calibrationSha256,
      if (preprocessSha256 != null) 'preprocess_sha256': preprocessSha256,
      if (fusionPolicyId != null) 'fusion_policy_id': fusionPolicyId,
      if (fusionPolicySha256 != null)
        'fusion_policy_sha256': fusionPolicySha256,
      if (configSnapshotJson != null)
        'config_snapshot_json': configSnapshotJson,
      if (rowid != null) 'rowid': rowid,
    });
  }

  CheckoutSessionsCompanion copyWith({
    Value<String>? sessionId,
    Value<String>? state,
    Value<int>? startedAtUs,
    Value<int?>? terminalAtUs,
    Value<String?>? terminalReason,
    Value<String>? catalogRevisionId,
    Value<String>? settingsRevisionId,
    Value<String>? detectorId,
    Value<String>? detectorSha256,
    Value<String>? repvitArtifactId,
    Value<String>? repvitSha256,
    Value<String>? repvitManifestSha256,
    Value<String>? repvitPrototypeSha256,
    Value<String>? dinov3ArtifactId,
    Value<String>? dinov3Sha256,
    Value<String>? dinov3SupportSha256,
    Value<String>? calibrationId,
    Value<String>? calibrationSha256,
    Value<String>? preprocessSha256,
    Value<String>? fusionPolicyId,
    Value<String>? fusionPolicySha256,
    Value<String>? configSnapshotJson,
    Value<int>? rowid,
  }) {
    return CheckoutSessionsCompanion(
      sessionId: sessionId ?? this.sessionId,
      state: state ?? this.state,
      startedAtUs: startedAtUs ?? this.startedAtUs,
      terminalAtUs: terminalAtUs ?? this.terminalAtUs,
      terminalReason: terminalReason ?? this.terminalReason,
      catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
      settingsRevisionId: settingsRevisionId ?? this.settingsRevisionId,
      detectorId: detectorId ?? this.detectorId,
      detectorSha256: detectorSha256 ?? this.detectorSha256,
      repvitArtifactId: repvitArtifactId ?? this.repvitArtifactId,
      repvitSha256: repvitSha256 ?? this.repvitSha256,
      repvitManifestSha256: repvitManifestSha256 ?? this.repvitManifestSha256,
      repvitPrototypeSha256:
          repvitPrototypeSha256 ?? this.repvitPrototypeSha256,
      dinov3ArtifactId: dinov3ArtifactId ?? this.dinov3ArtifactId,
      dinov3Sha256: dinov3Sha256 ?? this.dinov3Sha256,
      dinov3SupportSha256: dinov3SupportSha256 ?? this.dinov3SupportSha256,
      calibrationId: calibrationId ?? this.calibrationId,
      calibrationSha256: calibrationSha256 ?? this.calibrationSha256,
      preprocessSha256: preprocessSha256 ?? this.preprocessSha256,
      fusionPolicyId: fusionPolicyId ?? this.fusionPolicyId,
      fusionPolicySha256: fusionPolicySha256 ?? this.fusionPolicySha256,
      configSnapshotJson: configSnapshotJson ?? this.configSnapshotJson,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (state.present) {
      map['state'] = Variable<String>(state.value);
    }
    if (startedAtUs.present) {
      map['started_at_us'] = Variable<int>(startedAtUs.value);
    }
    if (terminalAtUs.present) {
      map['terminal_at_us'] = Variable<int>(terminalAtUs.value);
    }
    if (terminalReason.present) {
      map['terminal_reason'] = Variable<String>(terminalReason.value);
    }
    if (catalogRevisionId.present) {
      map['catalog_revision_id'] = Variable<String>(catalogRevisionId.value);
    }
    if (settingsRevisionId.present) {
      map['settings_revision_id'] = Variable<String>(settingsRevisionId.value);
    }
    if (detectorId.present) {
      map['detector_id'] = Variable<String>(detectorId.value);
    }
    if (detectorSha256.present) {
      map['detector_sha256'] = Variable<String>(detectorSha256.value);
    }
    if (repvitArtifactId.present) {
      map['repvit_artifact_id'] = Variable<String>(repvitArtifactId.value);
    }
    if (repvitSha256.present) {
      map['repvit_sha256'] = Variable<String>(repvitSha256.value);
    }
    if (repvitManifestSha256.present) {
      map['repvit_manifest_sha256'] = Variable<String>(
        repvitManifestSha256.value,
      );
    }
    if (repvitPrototypeSha256.present) {
      map['repvit_prototype_sha256'] = Variable<String>(
        repvitPrototypeSha256.value,
      );
    }
    if (dinov3ArtifactId.present) {
      map['dinov3_artifact_id'] = Variable<String>(dinov3ArtifactId.value);
    }
    if (dinov3Sha256.present) {
      map['dinov3_sha256'] = Variable<String>(dinov3Sha256.value);
    }
    if (dinov3SupportSha256.present) {
      map['dinov3_support_sha256'] = Variable<String>(
        dinov3SupportSha256.value,
      );
    }
    if (calibrationId.present) {
      map['calibration_id'] = Variable<String>(calibrationId.value);
    }
    if (calibrationSha256.present) {
      map['calibration_sha256'] = Variable<String>(calibrationSha256.value);
    }
    if (preprocessSha256.present) {
      map['preprocess_sha256'] = Variable<String>(preprocessSha256.value);
    }
    if (fusionPolicyId.present) {
      map['fusion_policy_id'] = Variable<String>(fusionPolicyId.value);
    }
    if (fusionPolicySha256.present) {
      map['fusion_policy_sha256'] = Variable<String>(fusionPolicySha256.value);
    }
    if (configSnapshotJson.present) {
      map['config_snapshot_json'] = Variable<String>(configSnapshotJson.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('CheckoutSessionsCompanion(')
          ..write('sessionId: $sessionId, ')
          ..write('state: $state, ')
          ..write('startedAtUs: $startedAtUs, ')
          ..write('terminalAtUs: $terminalAtUs, ')
          ..write('terminalReason: $terminalReason, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('settingsRevisionId: $settingsRevisionId, ')
          ..write('detectorId: $detectorId, ')
          ..write('detectorSha256: $detectorSha256, ')
          ..write('repvitArtifactId: $repvitArtifactId, ')
          ..write('repvitSha256: $repvitSha256, ')
          ..write('repvitManifestSha256: $repvitManifestSha256, ')
          ..write('repvitPrototypeSha256: $repvitPrototypeSha256, ')
          ..write('dinov3ArtifactId: $dinov3ArtifactId, ')
          ..write('dinov3Sha256: $dinov3Sha256, ')
          ..write('dinov3SupportSha256: $dinov3SupportSha256, ')
          ..write('calibrationId: $calibrationId, ')
          ..write('calibrationSha256: $calibrationSha256, ')
          ..write('preprocessSha256: $preprocessSha256, ')
          ..write('fusionPolicyId: $fusionPolicyId, ')
          ..write('fusionPolicySha256: $fusionPolicySha256, ')
          ..write('configSnapshotJson: $configSnapshotJson, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ScanAttemptsTable extends ScanAttempts
    with TableInfo<$ScanAttemptsTable, ScanAttemptRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ScanAttemptsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _attemptIdMeta = const VerificationMeta(
    'attemptId',
  );
  @override
  late final GeneratedColumn<String> attemptId = GeneratedColumn<String>(
    'attempt_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _attemptNumberMeta = const VerificationMeta(
    'attemptNumber',
  );
  @override
  late final GeneratedColumn<int> attemptNumber = GeneratedColumn<int>(
    'attempt_number',
    aliasedName,
    false,
    check: () => ComparableExpr(attemptNumber).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _capturedAtUsMeta = const VerificationMeta(
    'capturedAtUs',
  );
  @override
  late final GeneratedColumn<int> capturedAtUs = GeneratedColumn<int>(
    'captured_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _imageRelativePathMeta = const VerificationMeta(
    'imageRelativePath',
  );
  @override
  late final GeneratedColumn<String> imageRelativePath =
      GeneratedColumn<String>(
        'image_relative_path',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _imageByteSizeMeta = const VerificationMeta(
    'imageByteSize',
  );
  @override
  late final GeneratedColumn<int> imageByteSize = GeneratedColumn<int>(
    'image_byte_size',
    aliasedName,
    false,
    check: () => ComparableExpr(imageByteSize).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _imageSha256Meta = const VerificationMeta(
    'imageSha256',
  );
  @override
  late final GeneratedColumn<String> imageSha256 = GeneratedColumn<String>(
    'image_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _canonicalWidthMeta = const VerificationMeta(
    'canonicalWidth',
  );
  @override
  late final GeneratedColumn<int> canonicalWidth = GeneratedColumn<int>(
    'canonical_width',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _canonicalHeightMeta = const VerificationMeta(
    'canonicalHeight',
  );
  @override
  late final GeneratedColumn<int> canonicalHeight = GeneratedColumn<int>(
    'canonical_height',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _receiptRelativePathMeta =
      const VerificationMeta('receiptRelativePath');
  @override
  late final GeneratedColumn<String> receiptRelativePath =
      GeneratedColumn<String>(
        'receipt_relative_path',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _receiptByteSizeMeta = const VerificationMeta(
    'receiptByteSize',
  );
  @override
  late final GeneratedColumn<int> receiptByteSize = GeneratedColumn<int>(
    'receipt_byte_size',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _receiptSha256Meta = const VerificationMeta(
    'receiptSha256',
  );
  @override
  late final GeneratedColumn<String> receiptSha256 = GeneratedColumn<String>(
    'receipt_sha256',
    aliasedName,
    true,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _presentationStateMeta = const VerificationMeta(
    'presentationState',
  );
  @override
  late final GeneratedColumn<String> presentationState =
      GeneratedColumn<String>(
        'presentation_state',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _finalCountUsableMeta = const VerificationMeta(
    'finalCountUsable',
  );
  @override
  late final GeneratedColumn<bool> finalCountUsable = GeneratedColumn<bool>(
    'final_count_usable',
    aliasedName,
    true,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("final_count_usable" IN (0, 1))',
    ),
  );
  static const VerificationMeta _retakeScopeMeta = const VerificationMeta(
    'retakeScope',
  );
  @override
  late final GeneratedColumn<String> retakeScope = GeneratedColumn<String>(
    'retake_scope',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _retakeReasonMeta = const VerificationMeta(
    'retakeReason',
  );
  @override
  late final GeneratedColumn<String> retakeReason = GeneratedColumn<String>(
    'retake_reason',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _presentationPolicyIdMeta =
      const VerificationMeta('presentationPolicyId');
  @override
  late final GeneratedColumn<String> presentationPolicyId =
      GeneratedColumn<String>(
        'presentation_policy_id',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _presentationPolicySha256Meta =
      const VerificationMeta('presentationPolicySha256');
  @override
  late final GeneratedColumn<String> presentationPolicySha256 =
      GeneratedColumn<String>(
        'presentation_policy_sha256',
        aliasedName,
        true,
        additionalChecks: GeneratedColumn.checkTextLength(
          minTextLength: 64,
          maxTextLength: 64,
        ),
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _decodePreprocessMsMeta =
      const VerificationMeta('decodePreprocessMs');
  @override
  late final GeneratedColumn<double> decodePreprocessMs =
      GeneratedColumn<double>(
        'decode_preprocess_ms',
        aliasedName,
        true,
        type: DriftSqlType.double,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _detectorMsMeta = const VerificationMeta(
    'detectorMs',
  );
  @override
  late final GeneratedColumn<double> detectorMs = GeneratedColumn<double>(
    'detector_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _repvitMsMeta = const VerificationMeta(
    'repvitMs',
  );
  @override
  late final GeneratedColumn<double> repvitMs = GeneratedColumn<double>(
    'repvit_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _dinov3MsMeta = const VerificationMeta(
    'dinov3Ms',
  );
  @override
  late final GeneratedColumn<double> dinov3Ms = GeneratedColumn<double>(
    'dinov3_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _postprocessMsMeta = const VerificationMeta(
    'postprocessMs',
  );
  @override
  late final GeneratedColumn<double> postprocessMs = GeneratedColumn<double>(
    'postprocess_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _totalMsMeta = const VerificationMeta(
    'totalMs',
  );
  @override
  late final GeneratedColumn<double> totalMs = GeneratedColumn<double>(
    'total_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _startupDeviceMeta = const VerificationMeta(
    'startupDevice',
  );
  @override
  late final GeneratedColumn<String> startupDevice = GeneratedColumn<String>(
    'startup_device',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _startupLoadMsMeta = const VerificationMeta(
    'startupLoadMs',
  );
  @override
  late final GeneratedColumn<double> startupLoadMs = GeneratedColumn<double>(
    'startup_load_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _startupWarmupMsMeta = const VerificationMeta(
    'startupWarmupMs',
  );
  @override
  late final GeneratedColumn<double> startupWarmupMs = GeneratedColumn<double>(
    'startup_warmup_ms',
    aliasedName,
    true,
    type: DriftSqlType.double,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _startupFallbackReasonMeta =
      const VerificationMeta('startupFallbackReason');
  @override
  late final GeneratedColumn<String> startupFallbackReason =
      GeneratedColumn<String>(
        'startup_fallback_reason',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  @override
  List<GeneratedColumn> get $columns => [
    attemptId,
    sessionId,
    attemptNumber,
    capturedAtUs,
    imageRelativePath,
    imageByteSize,
    imageSha256,
    status,
    canonicalWidth,
    canonicalHeight,
    receiptRelativePath,
    receiptByteSize,
    receiptSha256,
    presentationState,
    finalCountUsable,
    retakeScope,
    retakeReason,
    presentationPolicyId,
    presentationPolicySha256,
    decodePreprocessMs,
    detectorMs,
    repvitMs,
    dinov3Ms,
    postprocessMs,
    totalMs,
    startupDevice,
    startupLoadMs,
    startupWarmupMs,
    startupFallbackReason,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'scan_attempts';
  @override
  VerificationContext validateIntegrity(
    Insertable<ScanAttemptRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('attempt_id')) {
      context.handle(
        _attemptIdMeta,
        attemptId.isAcceptableOrUnknown(data['attempt_id']!, _attemptIdMeta),
      );
    } else if (isInserting) {
      context.missing(_attemptIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('attempt_number')) {
      context.handle(
        _attemptNumberMeta,
        attemptNumber.isAcceptableOrUnknown(
          data['attempt_number']!,
          _attemptNumberMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_attemptNumberMeta);
    }
    if (data.containsKey('captured_at_us')) {
      context.handle(
        _capturedAtUsMeta,
        capturedAtUs.isAcceptableOrUnknown(
          data['captured_at_us']!,
          _capturedAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_capturedAtUsMeta);
    }
    if (data.containsKey('image_relative_path')) {
      context.handle(
        _imageRelativePathMeta,
        imageRelativePath.isAcceptableOrUnknown(
          data['image_relative_path']!,
          _imageRelativePathMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_imageRelativePathMeta);
    }
    if (data.containsKey('image_byte_size')) {
      context.handle(
        _imageByteSizeMeta,
        imageByteSize.isAcceptableOrUnknown(
          data['image_byte_size']!,
          _imageByteSizeMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_imageByteSizeMeta);
    }
    if (data.containsKey('image_sha256')) {
      context.handle(
        _imageSha256Meta,
        imageSha256.isAcceptableOrUnknown(
          data['image_sha256']!,
          _imageSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_imageSha256Meta);
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    } else if (isInserting) {
      context.missing(_statusMeta);
    }
    if (data.containsKey('canonical_width')) {
      context.handle(
        _canonicalWidthMeta,
        canonicalWidth.isAcceptableOrUnknown(
          data['canonical_width']!,
          _canonicalWidthMeta,
        ),
      );
    }
    if (data.containsKey('canonical_height')) {
      context.handle(
        _canonicalHeightMeta,
        canonicalHeight.isAcceptableOrUnknown(
          data['canonical_height']!,
          _canonicalHeightMeta,
        ),
      );
    }
    if (data.containsKey('receipt_relative_path')) {
      context.handle(
        _receiptRelativePathMeta,
        receiptRelativePath.isAcceptableOrUnknown(
          data['receipt_relative_path']!,
          _receiptRelativePathMeta,
        ),
      );
    }
    if (data.containsKey('receipt_byte_size')) {
      context.handle(
        _receiptByteSizeMeta,
        receiptByteSize.isAcceptableOrUnknown(
          data['receipt_byte_size']!,
          _receiptByteSizeMeta,
        ),
      );
    }
    if (data.containsKey('receipt_sha256')) {
      context.handle(
        _receiptSha256Meta,
        receiptSha256.isAcceptableOrUnknown(
          data['receipt_sha256']!,
          _receiptSha256Meta,
        ),
      );
    }
    if (data.containsKey('presentation_state')) {
      context.handle(
        _presentationStateMeta,
        presentationState.isAcceptableOrUnknown(
          data['presentation_state']!,
          _presentationStateMeta,
        ),
      );
    }
    if (data.containsKey('final_count_usable')) {
      context.handle(
        _finalCountUsableMeta,
        finalCountUsable.isAcceptableOrUnknown(
          data['final_count_usable']!,
          _finalCountUsableMeta,
        ),
      );
    }
    if (data.containsKey('retake_scope')) {
      context.handle(
        _retakeScopeMeta,
        retakeScope.isAcceptableOrUnknown(
          data['retake_scope']!,
          _retakeScopeMeta,
        ),
      );
    }
    if (data.containsKey('retake_reason')) {
      context.handle(
        _retakeReasonMeta,
        retakeReason.isAcceptableOrUnknown(
          data['retake_reason']!,
          _retakeReasonMeta,
        ),
      );
    }
    if (data.containsKey('presentation_policy_id')) {
      context.handle(
        _presentationPolicyIdMeta,
        presentationPolicyId.isAcceptableOrUnknown(
          data['presentation_policy_id']!,
          _presentationPolicyIdMeta,
        ),
      );
    }
    if (data.containsKey('presentation_policy_sha256')) {
      context.handle(
        _presentationPolicySha256Meta,
        presentationPolicySha256.isAcceptableOrUnknown(
          data['presentation_policy_sha256']!,
          _presentationPolicySha256Meta,
        ),
      );
    }
    if (data.containsKey('decode_preprocess_ms')) {
      context.handle(
        _decodePreprocessMsMeta,
        decodePreprocessMs.isAcceptableOrUnknown(
          data['decode_preprocess_ms']!,
          _decodePreprocessMsMeta,
        ),
      );
    }
    if (data.containsKey('detector_ms')) {
      context.handle(
        _detectorMsMeta,
        detectorMs.isAcceptableOrUnknown(data['detector_ms']!, _detectorMsMeta),
      );
    }
    if (data.containsKey('repvit_ms')) {
      context.handle(
        _repvitMsMeta,
        repvitMs.isAcceptableOrUnknown(data['repvit_ms']!, _repvitMsMeta),
      );
    }
    if (data.containsKey('dinov3_ms')) {
      context.handle(
        _dinov3MsMeta,
        dinov3Ms.isAcceptableOrUnknown(data['dinov3_ms']!, _dinov3MsMeta),
      );
    }
    if (data.containsKey('postprocess_ms')) {
      context.handle(
        _postprocessMsMeta,
        postprocessMs.isAcceptableOrUnknown(
          data['postprocess_ms']!,
          _postprocessMsMeta,
        ),
      );
    }
    if (data.containsKey('total_ms')) {
      context.handle(
        _totalMsMeta,
        totalMs.isAcceptableOrUnknown(data['total_ms']!, _totalMsMeta),
      );
    }
    if (data.containsKey('startup_device')) {
      context.handle(
        _startupDeviceMeta,
        startupDevice.isAcceptableOrUnknown(
          data['startup_device']!,
          _startupDeviceMeta,
        ),
      );
    }
    if (data.containsKey('startup_load_ms')) {
      context.handle(
        _startupLoadMsMeta,
        startupLoadMs.isAcceptableOrUnknown(
          data['startup_load_ms']!,
          _startupLoadMsMeta,
        ),
      );
    }
    if (data.containsKey('startup_warmup_ms')) {
      context.handle(
        _startupWarmupMsMeta,
        startupWarmupMs.isAcceptableOrUnknown(
          data['startup_warmup_ms']!,
          _startupWarmupMsMeta,
        ),
      );
    }
    if (data.containsKey('startup_fallback_reason')) {
      context.handle(
        _startupFallbackReasonMeta,
        startupFallbackReason.isAcceptableOrUnknown(
          data['startup_fallback_reason']!,
          _startupFallbackReasonMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {attemptId};
  @override
  ScanAttemptRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ScanAttemptRow(
      attemptId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}attempt_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      attemptNumber: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}attempt_number'],
      )!,
      capturedAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}captured_at_us'],
      )!,
      imageRelativePath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}image_relative_path'],
      )!,
      imageByteSize: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}image_byte_size'],
      )!,
      imageSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}image_sha256'],
      )!,
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
      canonicalWidth: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}canonical_width'],
      ),
      canonicalHeight: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}canonical_height'],
      ),
      receiptRelativePath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}receipt_relative_path'],
      ),
      receiptByteSize: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}receipt_byte_size'],
      ),
      receiptSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}receipt_sha256'],
      ),
      presentationState: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}presentation_state'],
      ),
      finalCountUsable: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}final_count_usable'],
      ),
      retakeScope: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}retake_scope'],
      ),
      retakeReason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}retake_reason'],
      ),
      presentationPolicyId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}presentation_policy_id'],
      ),
      presentationPolicySha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}presentation_policy_sha256'],
      ),
      decodePreprocessMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}decode_preprocess_ms'],
      ),
      detectorMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}detector_ms'],
      ),
      repvitMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}repvit_ms'],
      ),
      dinov3Ms: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}dinov3_ms'],
      ),
      postprocessMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}postprocess_ms'],
      ),
      totalMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}total_ms'],
      ),
      startupDevice: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}startup_device'],
      ),
      startupLoadMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}startup_load_ms'],
      ),
      startupWarmupMs: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}startup_warmup_ms'],
      ),
      startupFallbackReason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}startup_fallback_reason'],
      ),
    );
  }

  @override
  $ScanAttemptsTable createAlias(String alias) {
    return $ScanAttemptsTable(attachedDatabase, alias);
  }
}

class ScanAttemptRow extends DataClass implements Insertable<ScanAttemptRow> {
  final String attemptId;
  final String sessionId;
  final int attemptNumber;
  final int capturedAtUs;
  final String imageRelativePath;
  final int imageByteSize;
  final String imageSha256;
  final String status;
  final int? canonicalWidth;
  final int? canonicalHeight;
  final String? receiptRelativePath;
  final int? receiptByteSize;
  final String? receiptSha256;
  final String? presentationState;
  final bool? finalCountUsable;
  final String? retakeScope;
  final String? retakeReason;
  final String? presentationPolicyId;
  final String? presentationPolicySha256;
  final double? decodePreprocessMs;
  final double? detectorMs;
  final double? repvitMs;
  final double? dinov3Ms;
  final double? postprocessMs;
  final double? totalMs;
  final String? startupDevice;
  final double? startupLoadMs;
  final double? startupWarmupMs;
  final String? startupFallbackReason;
  const ScanAttemptRow({
    required this.attemptId,
    required this.sessionId,
    required this.attemptNumber,
    required this.capturedAtUs,
    required this.imageRelativePath,
    required this.imageByteSize,
    required this.imageSha256,
    required this.status,
    this.canonicalWidth,
    this.canonicalHeight,
    this.receiptRelativePath,
    this.receiptByteSize,
    this.receiptSha256,
    this.presentationState,
    this.finalCountUsable,
    this.retakeScope,
    this.retakeReason,
    this.presentationPolicyId,
    this.presentationPolicySha256,
    this.decodePreprocessMs,
    this.detectorMs,
    this.repvitMs,
    this.dinov3Ms,
    this.postprocessMs,
    this.totalMs,
    this.startupDevice,
    this.startupLoadMs,
    this.startupWarmupMs,
    this.startupFallbackReason,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['attempt_id'] = Variable<String>(attemptId);
    map['session_id'] = Variable<String>(sessionId);
    map['attempt_number'] = Variable<int>(attemptNumber);
    map['captured_at_us'] = Variable<int>(capturedAtUs);
    map['image_relative_path'] = Variable<String>(imageRelativePath);
    map['image_byte_size'] = Variable<int>(imageByteSize);
    map['image_sha256'] = Variable<String>(imageSha256);
    map['status'] = Variable<String>(status);
    if (!nullToAbsent || canonicalWidth != null) {
      map['canonical_width'] = Variable<int>(canonicalWidth);
    }
    if (!nullToAbsent || canonicalHeight != null) {
      map['canonical_height'] = Variable<int>(canonicalHeight);
    }
    if (!nullToAbsent || receiptRelativePath != null) {
      map['receipt_relative_path'] = Variable<String>(receiptRelativePath);
    }
    if (!nullToAbsent || receiptByteSize != null) {
      map['receipt_byte_size'] = Variable<int>(receiptByteSize);
    }
    if (!nullToAbsent || receiptSha256 != null) {
      map['receipt_sha256'] = Variable<String>(receiptSha256);
    }
    if (!nullToAbsent || presentationState != null) {
      map['presentation_state'] = Variable<String>(presentationState);
    }
    if (!nullToAbsent || finalCountUsable != null) {
      map['final_count_usable'] = Variable<bool>(finalCountUsable);
    }
    if (!nullToAbsent || retakeScope != null) {
      map['retake_scope'] = Variable<String>(retakeScope);
    }
    if (!nullToAbsent || retakeReason != null) {
      map['retake_reason'] = Variable<String>(retakeReason);
    }
    if (!nullToAbsent || presentationPolicyId != null) {
      map['presentation_policy_id'] = Variable<String>(presentationPolicyId);
    }
    if (!nullToAbsent || presentationPolicySha256 != null) {
      map['presentation_policy_sha256'] = Variable<String>(
        presentationPolicySha256,
      );
    }
    if (!nullToAbsent || decodePreprocessMs != null) {
      map['decode_preprocess_ms'] = Variable<double>(decodePreprocessMs);
    }
    if (!nullToAbsent || detectorMs != null) {
      map['detector_ms'] = Variable<double>(detectorMs);
    }
    if (!nullToAbsent || repvitMs != null) {
      map['repvit_ms'] = Variable<double>(repvitMs);
    }
    if (!nullToAbsent || dinov3Ms != null) {
      map['dinov3_ms'] = Variable<double>(dinov3Ms);
    }
    if (!nullToAbsent || postprocessMs != null) {
      map['postprocess_ms'] = Variable<double>(postprocessMs);
    }
    if (!nullToAbsent || totalMs != null) {
      map['total_ms'] = Variable<double>(totalMs);
    }
    if (!nullToAbsent || startupDevice != null) {
      map['startup_device'] = Variable<String>(startupDevice);
    }
    if (!nullToAbsent || startupLoadMs != null) {
      map['startup_load_ms'] = Variable<double>(startupLoadMs);
    }
    if (!nullToAbsent || startupWarmupMs != null) {
      map['startup_warmup_ms'] = Variable<double>(startupWarmupMs);
    }
    if (!nullToAbsent || startupFallbackReason != null) {
      map['startup_fallback_reason'] = Variable<String>(startupFallbackReason);
    }
    return map;
  }

  ScanAttemptsCompanion toCompanion(bool nullToAbsent) {
    return ScanAttemptsCompanion(
      attemptId: Value(attemptId),
      sessionId: Value(sessionId),
      attemptNumber: Value(attemptNumber),
      capturedAtUs: Value(capturedAtUs),
      imageRelativePath: Value(imageRelativePath),
      imageByteSize: Value(imageByteSize),
      imageSha256: Value(imageSha256),
      status: Value(status),
      canonicalWidth: canonicalWidth == null && nullToAbsent
          ? const Value.absent()
          : Value(canonicalWidth),
      canonicalHeight: canonicalHeight == null && nullToAbsent
          ? const Value.absent()
          : Value(canonicalHeight),
      receiptRelativePath: receiptRelativePath == null && nullToAbsent
          ? const Value.absent()
          : Value(receiptRelativePath),
      receiptByteSize: receiptByteSize == null && nullToAbsent
          ? const Value.absent()
          : Value(receiptByteSize),
      receiptSha256: receiptSha256 == null && nullToAbsent
          ? const Value.absent()
          : Value(receiptSha256),
      presentationState: presentationState == null && nullToAbsent
          ? const Value.absent()
          : Value(presentationState),
      finalCountUsable: finalCountUsable == null && nullToAbsent
          ? const Value.absent()
          : Value(finalCountUsable),
      retakeScope: retakeScope == null && nullToAbsent
          ? const Value.absent()
          : Value(retakeScope),
      retakeReason: retakeReason == null && nullToAbsent
          ? const Value.absent()
          : Value(retakeReason),
      presentationPolicyId: presentationPolicyId == null && nullToAbsent
          ? const Value.absent()
          : Value(presentationPolicyId),
      presentationPolicySha256: presentationPolicySha256 == null && nullToAbsent
          ? const Value.absent()
          : Value(presentationPolicySha256),
      decodePreprocessMs: decodePreprocessMs == null && nullToAbsent
          ? const Value.absent()
          : Value(decodePreprocessMs),
      detectorMs: detectorMs == null && nullToAbsent
          ? const Value.absent()
          : Value(detectorMs),
      repvitMs: repvitMs == null && nullToAbsent
          ? const Value.absent()
          : Value(repvitMs),
      dinov3Ms: dinov3Ms == null && nullToAbsent
          ? const Value.absent()
          : Value(dinov3Ms),
      postprocessMs: postprocessMs == null && nullToAbsent
          ? const Value.absent()
          : Value(postprocessMs),
      totalMs: totalMs == null && nullToAbsent
          ? const Value.absent()
          : Value(totalMs),
      startupDevice: startupDevice == null && nullToAbsent
          ? const Value.absent()
          : Value(startupDevice),
      startupLoadMs: startupLoadMs == null && nullToAbsent
          ? const Value.absent()
          : Value(startupLoadMs),
      startupWarmupMs: startupWarmupMs == null && nullToAbsent
          ? const Value.absent()
          : Value(startupWarmupMs),
      startupFallbackReason: startupFallbackReason == null && nullToAbsent
          ? const Value.absent()
          : Value(startupFallbackReason),
    );
  }

  factory ScanAttemptRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ScanAttemptRow(
      attemptId: serializer.fromJson<String>(json['attemptId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      attemptNumber: serializer.fromJson<int>(json['attemptNumber']),
      capturedAtUs: serializer.fromJson<int>(json['capturedAtUs']),
      imageRelativePath: serializer.fromJson<String>(json['imageRelativePath']),
      imageByteSize: serializer.fromJson<int>(json['imageByteSize']),
      imageSha256: serializer.fromJson<String>(json['imageSha256']),
      status: serializer.fromJson<String>(json['status']),
      canonicalWidth: serializer.fromJson<int?>(json['canonicalWidth']),
      canonicalHeight: serializer.fromJson<int?>(json['canonicalHeight']),
      receiptRelativePath: serializer.fromJson<String?>(
        json['receiptRelativePath'],
      ),
      receiptByteSize: serializer.fromJson<int?>(json['receiptByteSize']),
      receiptSha256: serializer.fromJson<String?>(json['receiptSha256']),
      presentationState: serializer.fromJson<String?>(
        json['presentationState'],
      ),
      finalCountUsable: serializer.fromJson<bool?>(json['finalCountUsable']),
      retakeScope: serializer.fromJson<String?>(json['retakeScope']),
      retakeReason: serializer.fromJson<String?>(json['retakeReason']),
      presentationPolicyId: serializer.fromJson<String?>(
        json['presentationPolicyId'],
      ),
      presentationPolicySha256: serializer.fromJson<String?>(
        json['presentationPolicySha256'],
      ),
      decodePreprocessMs: serializer.fromJson<double?>(
        json['decodePreprocessMs'],
      ),
      detectorMs: serializer.fromJson<double?>(json['detectorMs']),
      repvitMs: serializer.fromJson<double?>(json['repvitMs']),
      dinov3Ms: serializer.fromJson<double?>(json['dinov3Ms']),
      postprocessMs: serializer.fromJson<double?>(json['postprocessMs']),
      totalMs: serializer.fromJson<double?>(json['totalMs']),
      startupDevice: serializer.fromJson<String?>(json['startupDevice']),
      startupLoadMs: serializer.fromJson<double?>(json['startupLoadMs']),
      startupWarmupMs: serializer.fromJson<double?>(json['startupWarmupMs']),
      startupFallbackReason: serializer.fromJson<String?>(
        json['startupFallbackReason'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'attemptId': serializer.toJson<String>(attemptId),
      'sessionId': serializer.toJson<String>(sessionId),
      'attemptNumber': serializer.toJson<int>(attemptNumber),
      'capturedAtUs': serializer.toJson<int>(capturedAtUs),
      'imageRelativePath': serializer.toJson<String>(imageRelativePath),
      'imageByteSize': serializer.toJson<int>(imageByteSize),
      'imageSha256': serializer.toJson<String>(imageSha256),
      'status': serializer.toJson<String>(status),
      'canonicalWidth': serializer.toJson<int?>(canonicalWidth),
      'canonicalHeight': serializer.toJson<int?>(canonicalHeight),
      'receiptRelativePath': serializer.toJson<String?>(receiptRelativePath),
      'receiptByteSize': serializer.toJson<int?>(receiptByteSize),
      'receiptSha256': serializer.toJson<String?>(receiptSha256),
      'presentationState': serializer.toJson<String?>(presentationState),
      'finalCountUsable': serializer.toJson<bool?>(finalCountUsable),
      'retakeScope': serializer.toJson<String?>(retakeScope),
      'retakeReason': serializer.toJson<String?>(retakeReason),
      'presentationPolicyId': serializer.toJson<String?>(presentationPolicyId),
      'presentationPolicySha256': serializer.toJson<String?>(
        presentationPolicySha256,
      ),
      'decodePreprocessMs': serializer.toJson<double?>(decodePreprocessMs),
      'detectorMs': serializer.toJson<double?>(detectorMs),
      'repvitMs': serializer.toJson<double?>(repvitMs),
      'dinov3Ms': serializer.toJson<double?>(dinov3Ms),
      'postprocessMs': serializer.toJson<double?>(postprocessMs),
      'totalMs': serializer.toJson<double?>(totalMs),
      'startupDevice': serializer.toJson<String?>(startupDevice),
      'startupLoadMs': serializer.toJson<double?>(startupLoadMs),
      'startupWarmupMs': serializer.toJson<double?>(startupWarmupMs),
      'startupFallbackReason': serializer.toJson<String?>(
        startupFallbackReason,
      ),
    };
  }

  ScanAttemptRow copyWith({
    String? attemptId,
    String? sessionId,
    int? attemptNumber,
    int? capturedAtUs,
    String? imageRelativePath,
    int? imageByteSize,
    String? imageSha256,
    String? status,
    Value<int?> canonicalWidth = const Value.absent(),
    Value<int?> canonicalHeight = const Value.absent(),
    Value<String?> receiptRelativePath = const Value.absent(),
    Value<int?> receiptByteSize = const Value.absent(),
    Value<String?> receiptSha256 = const Value.absent(),
    Value<String?> presentationState = const Value.absent(),
    Value<bool?> finalCountUsable = const Value.absent(),
    Value<String?> retakeScope = const Value.absent(),
    Value<String?> retakeReason = const Value.absent(),
    Value<String?> presentationPolicyId = const Value.absent(),
    Value<String?> presentationPolicySha256 = const Value.absent(),
    Value<double?> decodePreprocessMs = const Value.absent(),
    Value<double?> detectorMs = const Value.absent(),
    Value<double?> repvitMs = const Value.absent(),
    Value<double?> dinov3Ms = const Value.absent(),
    Value<double?> postprocessMs = const Value.absent(),
    Value<double?> totalMs = const Value.absent(),
    Value<String?> startupDevice = const Value.absent(),
    Value<double?> startupLoadMs = const Value.absent(),
    Value<double?> startupWarmupMs = const Value.absent(),
    Value<String?> startupFallbackReason = const Value.absent(),
  }) => ScanAttemptRow(
    attemptId: attemptId ?? this.attemptId,
    sessionId: sessionId ?? this.sessionId,
    attemptNumber: attemptNumber ?? this.attemptNumber,
    capturedAtUs: capturedAtUs ?? this.capturedAtUs,
    imageRelativePath: imageRelativePath ?? this.imageRelativePath,
    imageByteSize: imageByteSize ?? this.imageByteSize,
    imageSha256: imageSha256 ?? this.imageSha256,
    status: status ?? this.status,
    canonicalWidth: canonicalWidth.present
        ? canonicalWidth.value
        : this.canonicalWidth,
    canonicalHeight: canonicalHeight.present
        ? canonicalHeight.value
        : this.canonicalHeight,
    receiptRelativePath: receiptRelativePath.present
        ? receiptRelativePath.value
        : this.receiptRelativePath,
    receiptByteSize: receiptByteSize.present
        ? receiptByteSize.value
        : this.receiptByteSize,
    receiptSha256: receiptSha256.present
        ? receiptSha256.value
        : this.receiptSha256,
    presentationState: presentationState.present
        ? presentationState.value
        : this.presentationState,
    finalCountUsable: finalCountUsable.present
        ? finalCountUsable.value
        : this.finalCountUsable,
    retakeScope: retakeScope.present ? retakeScope.value : this.retakeScope,
    retakeReason: retakeReason.present ? retakeReason.value : this.retakeReason,
    presentationPolicyId: presentationPolicyId.present
        ? presentationPolicyId.value
        : this.presentationPolicyId,
    presentationPolicySha256: presentationPolicySha256.present
        ? presentationPolicySha256.value
        : this.presentationPolicySha256,
    decodePreprocessMs: decodePreprocessMs.present
        ? decodePreprocessMs.value
        : this.decodePreprocessMs,
    detectorMs: detectorMs.present ? detectorMs.value : this.detectorMs,
    repvitMs: repvitMs.present ? repvitMs.value : this.repvitMs,
    dinov3Ms: dinov3Ms.present ? dinov3Ms.value : this.dinov3Ms,
    postprocessMs: postprocessMs.present
        ? postprocessMs.value
        : this.postprocessMs,
    totalMs: totalMs.present ? totalMs.value : this.totalMs,
    startupDevice: startupDevice.present
        ? startupDevice.value
        : this.startupDevice,
    startupLoadMs: startupLoadMs.present
        ? startupLoadMs.value
        : this.startupLoadMs,
    startupWarmupMs: startupWarmupMs.present
        ? startupWarmupMs.value
        : this.startupWarmupMs,
    startupFallbackReason: startupFallbackReason.present
        ? startupFallbackReason.value
        : this.startupFallbackReason,
  );
  ScanAttemptRow copyWithCompanion(ScanAttemptsCompanion data) {
    return ScanAttemptRow(
      attemptId: data.attemptId.present ? data.attemptId.value : this.attemptId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      attemptNumber: data.attemptNumber.present
          ? data.attemptNumber.value
          : this.attemptNumber,
      capturedAtUs: data.capturedAtUs.present
          ? data.capturedAtUs.value
          : this.capturedAtUs,
      imageRelativePath: data.imageRelativePath.present
          ? data.imageRelativePath.value
          : this.imageRelativePath,
      imageByteSize: data.imageByteSize.present
          ? data.imageByteSize.value
          : this.imageByteSize,
      imageSha256: data.imageSha256.present
          ? data.imageSha256.value
          : this.imageSha256,
      status: data.status.present ? data.status.value : this.status,
      canonicalWidth: data.canonicalWidth.present
          ? data.canonicalWidth.value
          : this.canonicalWidth,
      canonicalHeight: data.canonicalHeight.present
          ? data.canonicalHeight.value
          : this.canonicalHeight,
      receiptRelativePath: data.receiptRelativePath.present
          ? data.receiptRelativePath.value
          : this.receiptRelativePath,
      receiptByteSize: data.receiptByteSize.present
          ? data.receiptByteSize.value
          : this.receiptByteSize,
      receiptSha256: data.receiptSha256.present
          ? data.receiptSha256.value
          : this.receiptSha256,
      presentationState: data.presentationState.present
          ? data.presentationState.value
          : this.presentationState,
      finalCountUsable: data.finalCountUsable.present
          ? data.finalCountUsable.value
          : this.finalCountUsable,
      retakeScope: data.retakeScope.present
          ? data.retakeScope.value
          : this.retakeScope,
      retakeReason: data.retakeReason.present
          ? data.retakeReason.value
          : this.retakeReason,
      presentationPolicyId: data.presentationPolicyId.present
          ? data.presentationPolicyId.value
          : this.presentationPolicyId,
      presentationPolicySha256: data.presentationPolicySha256.present
          ? data.presentationPolicySha256.value
          : this.presentationPolicySha256,
      decodePreprocessMs: data.decodePreprocessMs.present
          ? data.decodePreprocessMs.value
          : this.decodePreprocessMs,
      detectorMs: data.detectorMs.present
          ? data.detectorMs.value
          : this.detectorMs,
      repvitMs: data.repvitMs.present ? data.repvitMs.value : this.repvitMs,
      dinov3Ms: data.dinov3Ms.present ? data.dinov3Ms.value : this.dinov3Ms,
      postprocessMs: data.postprocessMs.present
          ? data.postprocessMs.value
          : this.postprocessMs,
      totalMs: data.totalMs.present ? data.totalMs.value : this.totalMs,
      startupDevice: data.startupDevice.present
          ? data.startupDevice.value
          : this.startupDevice,
      startupLoadMs: data.startupLoadMs.present
          ? data.startupLoadMs.value
          : this.startupLoadMs,
      startupWarmupMs: data.startupWarmupMs.present
          ? data.startupWarmupMs.value
          : this.startupWarmupMs,
      startupFallbackReason: data.startupFallbackReason.present
          ? data.startupFallbackReason.value
          : this.startupFallbackReason,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ScanAttemptRow(')
          ..write('attemptId: $attemptId, ')
          ..write('sessionId: $sessionId, ')
          ..write('attemptNumber: $attemptNumber, ')
          ..write('capturedAtUs: $capturedAtUs, ')
          ..write('imageRelativePath: $imageRelativePath, ')
          ..write('imageByteSize: $imageByteSize, ')
          ..write('imageSha256: $imageSha256, ')
          ..write('status: $status, ')
          ..write('canonicalWidth: $canonicalWidth, ')
          ..write('canonicalHeight: $canonicalHeight, ')
          ..write('receiptRelativePath: $receiptRelativePath, ')
          ..write('receiptByteSize: $receiptByteSize, ')
          ..write('receiptSha256: $receiptSha256, ')
          ..write('presentationState: $presentationState, ')
          ..write('finalCountUsable: $finalCountUsable, ')
          ..write('retakeScope: $retakeScope, ')
          ..write('retakeReason: $retakeReason, ')
          ..write('presentationPolicyId: $presentationPolicyId, ')
          ..write('presentationPolicySha256: $presentationPolicySha256, ')
          ..write('decodePreprocessMs: $decodePreprocessMs, ')
          ..write('detectorMs: $detectorMs, ')
          ..write('repvitMs: $repvitMs, ')
          ..write('dinov3Ms: $dinov3Ms, ')
          ..write('postprocessMs: $postprocessMs, ')
          ..write('totalMs: $totalMs, ')
          ..write('startupDevice: $startupDevice, ')
          ..write('startupLoadMs: $startupLoadMs, ')
          ..write('startupWarmupMs: $startupWarmupMs, ')
          ..write('startupFallbackReason: $startupFallbackReason')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hashAll([
    attemptId,
    sessionId,
    attemptNumber,
    capturedAtUs,
    imageRelativePath,
    imageByteSize,
    imageSha256,
    status,
    canonicalWidth,
    canonicalHeight,
    receiptRelativePath,
    receiptByteSize,
    receiptSha256,
    presentationState,
    finalCountUsable,
    retakeScope,
    retakeReason,
    presentationPolicyId,
    presentationPolicySha256,
    decodePreprocessMs,
    detectorMs,
    repvitMs,
    dinov3Ms,
    postprocessMs,
    totalMs,
    startupDevice,
    startupLoadMs,
    startupWarmupMs,
    startupFallbackReason,
  ]);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ScanAttemptRow &&
          other.attemptId == this.attemptId &&
          other.sessionId == this.sessionId &&
          other.attemptNumber == this.attemptNumber &&
          other.capturedAtUs == this.capturedAtUs &&
          other.imageRelativePath == this.imageRelativePath &&
          other.imageByteSize == this.imageByteSize &&
          other.imageSha256 == this.imageSha256 &&
          other.status == this.status &&
          other.canonicalWidth == this.canonicalWidth &&
          other.canonicalHeight == this.canonicalHeight &&
          other.receiptRelativePath == this.receiptRelativePath &&
          other.receiptByteSize == this.receiptByteSize &&
          other.receiptSha256 == this.receiptSha256 &&
          other.presentationState == this.presentationState &&
          other.finalCountUsable == this.finalCountUsable &&
          other.retakeScope == this.retakeScope &&
          other.retakeReason == this.retakeReason &&
          other.presentationPolicyId == this.presentationPolicyId &&
          other.presentationPolicySha256 == this.presentationPolicySha256 &&
          other.decodePreprocessMs == this.decodePreprocessMs &&
          other.detectorMs == this.detectorMs &&
          other.repvitMs == this.repvitMs &&
          other.dinov3Ms == this.dinov3Ms &&
          other.postprocessMs == this.postprocessMs &&
          other.totalMs == this.totalMs &&
          other.startupDevice == this.startupDevice &&
          other.startupLoadMs == this.startupLoadMs &&
          other.startupWarmupMs == this.startupWarmupMs &&
          other.startupFallbackReason == this.startupFallbackReason);
}

class ScanAttemptsCompanion extends UpdateCompanion<ScanAttemptRow> {
  final Value<String> attemptId;
  final Value<String> sessionId;
  final Value<int> attemptNumber;
  final Value<int> capturedAtUs;
  final Value<String> imageRelativePath;
  final Value<int> imageByteSize;
  final Value<String> imageSha256;
  final Value<String> status;
  final Value<int?> canonicalWidth;
  final Value<int?> canonicalHeight;
  final Value<String?> receiptRelativePath;
  final Value<int?> receiptByteSize;
  final Value<String?> receiptSha256;
  final Value<String?> presentationState;
  final Value<bool?> finalCountUsable;
  final Value<String?> retakeScope;
  final Value<String?> retakeReason;
  final Value<String?> presentationPolicyId;
  final Value<String?> presentationPolicySha256;
  final Value<double?> decodePreprocessMs;
  final Value<double?> detectorMs;
  final Value<double?> repvitMs;
  final Value<double?> dinov3Ms;
  final Value<double?> postprocessMs;
  final Value<double?> totalMs;
  final Value<String?> startupDevice;
  final Value<double?> startupLoadMs;
  final Value<double?> startupWarmupMs;
  final Value<String?> startupFallbackReason;
  final Value<int> rowid;
  const ScanAttemptsCompanion({
    this.attemptId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.attemptNumber = const Value.absent(),
    this.capturedAtUs = const Value.absent(),
    this.imageRelativePath = const Value.absent(),
    this.imageByteSize = const Value.absent(),
    this.imageSha256 = const Value.absent(),
    this.status = const Value.absent(),
    this.canonicalWidth = const Value.absent(),
    this.canonicalHeight = const Value.absent(),
    this.receiptRelativePath = const Value.absent(),
    this.receiptByteSize = const Value.absent(),
    this.receiptSha256 = const Value.absent(),
    this.presentationState = const Value.absent(),
    this.finalCountUsable = const Value.absent(),
    this.retakeScope = const Value.absent(),
    this.retakeReason = const Value.absent(),
    this.presentationPolicyId = const Value.absent(),
    this.presentationPolicySha256 = const Value.absent(),
    this.decodePreprocessMs = const Value.absent(),
    this.detectorMs = const Value.absent(),
    this.repvitMs = const Value.absent(),
    this.dinov3Ms = const Value.absent(),
    this.postprocessMs = const Value.absent(),
    this.totalMs = const Value.absent(),
    this.startupDevice = const Value.absent(),
    this.startupLoadMs = const Value.absent(),
    this.startupWarmupMs = const Value.absent(),
    this.startupFallbackReason = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ScanAttemptsCompanion.insert({
    required String attemptId,
    required String sessionId,
    required int attemptNumber,
    required int capturedAtUs,
    required String imageRelativePath,
    required int imageByteSize,
    required String imageSha256,
    required String status,
    this.canonicalWidth = const Value.absent(),
    this.canonicalHeight = const Value.absent(),
    this.receiptRelativePath = const Value.absent(),
    this.receiptByteSize = const Value.absent(),
    this.receiptSha256 = const Value.absent(),
    this.presentationState = const Value.absent(),
    this.finalCountUsable = const Value.absent(),
    this.retakeScope = const Value.absent(),
    this.retakeReason = const Value.absent(),
    this.presentationPolicyId = const Value.absent(),
    this.presentationPolicySha256 = const Value.absent(),
    this.decodePreprocessMs = const Value.absent(),
    this.detectorMs = const Value.absent(),
    this.repvitMs = const Value.absent(),
    this.dinov3Ms = const Value.absent(),
    this.postprocessMs = const Value.absent(),
    this.totalMs = const Value.absent(),
    this.startupDevice = const Value.absent(),
    this.startupLoadMs = const Value.absent(),
    this.startupWarmupMs = const Value.absent(),
    this.startupFallbackReason = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : attemptId = Value(attemptId),
       sessionId = Value(sessionId),
       attemptNumber = Value(attemptNumber),
       capturedAtUs = Value(capturedAtUs),
       imageRelativePath = Value(imageRelativePath),
       imageByteSize = Value(imageByteSize),
       imageSha256 = Value(imageSha256),
       status = Value(status);
  static Insertable<ScanAttemptRow> custom({
    Expression<String>? attemptId,
    Expression<String>? sessionId,
    Expression<int>? attemptNumber,
    Expression<int>? capturedAtUs,
    Expression<String>? imageRelativePath,
    Expression<int>? imageByteSize,
    Expression<String>? imageSha256,
    Expression<String>? status,
    Expression<int>? canonicalWidth,
    Expression<int>? canonicalHeight,
    Expression<String>? receiptRelativePath,
    Expression<int>? receiptByteSize,
    Expression<String>? receiptSha256,
    Expression<String>? presentationState,
    Expression<bool>? finalCountUsable,
    Expression<String>? retakeScope,
    Expression<String>? retakeReason,
    Expression<String>? presentationPolicyId,
    Expression<String>? presentationPolicySha256,
    Expression<double>? decodePreprocessMs,
    Expression<double>? detectorMs,
    Expression<double>? repvitMs,
    Expression<double>? dinov3Ms,
    Expression<double>? postprocessMs,
    Expression<double>? totalMs,
    Expression<String>? startupDevice,
    Expression<double>? startupLoadMs,
    Expression<double>? startupWarmupMs,
    Expression<String>? startupFallbackReason,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (attemptId != null) 'attempt_id': attemptId,
      if (sessionId != null) 'session_id': sessionId,
      if (attemptNumber != null) 'attempt_number': attemptNumber,
      if (capturedAtUs != null) 'captured_at_us': capturedAtUs,
      if (imageRelativePath != null) 'image_relative_path': imageRelativePath,
      if (imageByteSize != null) 'image_byte_size': imageByteSize,
      if (imageSha256 != null) 'image_sha256': imageSha256,
      if (status != null) 'status': status,
      if (canonicalWidth != null) 'canonical_width': canonicalWidth,
      if (canonicalHeight != null) 'canonical_height': canonicalHeight,
      if (receiptRelativePath != null)
        'receipt_relative_path': receiptRelativePath,
      if (receiptByteSize != null) 'receipt_byte_size': receiptByteSize,
      if (receiptSha256 != null) 'receipt_sha256': receiptSha256,
      if (presentationState != null) 'presentation_state': presentationState,
      if (finalCountUsable != null) 'final_count_usable': finalCountUsable,
      if (retakeScope != null) 'retake_scope': retakeScope,
      if (retakeReason != null) 'retake_reason': retakeReason,
      if (presentationPolicyId != null)
        'presentation_policy_id': presentationPolicyId,
      if (presentationPolicySha256 != null)
        'presentation_policy_sha256': presentationPolicySha256,
      if (decodePreprocessMs != null)
        'decode_preprocess_ms': decodePreprocessMs,
      if (detectorMs != null) 'detector_ms': detectorMs,
      if (repvitMs != null) 'repvit_ms': repvitMs,
      if (dinov3Ms != null) 'dinov3_ms': dinov3Ms,
      if (postprocessMs != null) 'postprocess_ms': postprocessMs,
      if (totalMs != null) 'total_ms': totalMs,
      if (startupDevice != null) 'startup_device': startupDevice,
      if (startupLoadMs != null) 'startup_load_ms': startupLoadMs,
      if (startupWarmupMs != null) 'startup_warmup_ms': startupWarmupMs,
      if (startupFallbackReason != null)
        'startup_fallback_reason': startupFallbackReason,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ScanAttemptsCompanion copyWith({
    Value<String>? attemptId,
    Value<String>? sessionId,
    Value<int>? attemptNumber,
    Value<int>? capturedAtUs,
    Value<String>? imageRelativePath,
    Value<int>? imageByteSize,
    Value<String>? imageSha256,
    Value<String>? status,
    Value<int?>? canonicalWidth,
    Value<int?>? canonicalHeight,
    Value<String?>? receiptRelativePath,
    Value<int?>? receiptByteSize,
    Value<String?>? receiptSha256,
    Value<String?>? presentationState,
    Value<bool?>? finalCountUsable,
    Value<String?>? retakeScope,
    Value<String?>? retakeReason,
    Value<String?>? presentationPolicyId,
    Value<String?>? presentationPolicySha256,
    Value<double?>? decodePreprocessMs,
    Value<double?>? detectorMs,
    Value<double?>? repvitMs,
    Value<double?>? dinov3Ms,
    Value<double?>? postprocessMs,
    Value<double?>? totalMs,
    Value<String?>? startupDevice,
    Value<double?>? startupLoadMs,
    Value<double?>? startupWarmupMs,
    Value<String?>? startupFallbackReason,
    Value<int>? rowid,
  }) {
    return ScanAttemptsCompanion(
      attemptId: attemptId ?? this.attemptId,
      sessionId: sessionId ?? this.sessionId,
      attemptNumber: attemptNumber ?? this.attemptNumber,
      capturedAtUs: capturedAtUs ?? this.capturedAtUs,
      imageRelativePath: imageRelativePath ?? this.imageRelativePath,
      imageByteSize: imageByteSize ?? this.imageByteSize,
      imageSha256: imageSha256 ?? this.imageSha256,
      status: status ?? this.status,
      canonicalWidth: canonicalWidth ?? this.canonicalWidth,
      canonicalHeight: canonicalHeight ?? this.canonicalHeight,
      receiptRelativePath: receiptRelativePath ?? this.receiptRelativePath,
      receiptByteSize: receiptByteSize ?? this.receiptByteSize,
      receiptSha256: receiptSha256 ?? this.receiptSha256,
      presentationState: presentationState ?? this.presentationState,
      finalCountUsable: finalCountUsable ?? this.finalCountUsable,
      retakeScope: retakeScope ?? this.retakeScope,
      retakeReason: retakeReason ?? this.retakeReason,
      presentationPolicyId: presentationPolicyId ?? this.presentationPolicyId,
      presentationPolicySha256:
          presentationPolicySha256 ?? this.presentationPolicySha256,
      decodePreprocessMs: decodePreprocessMs ?? this.decodePreprocessMs,
      detectorMs: detectorMs ?? this.detectorMs,
      repvitMs: repvitMs ?? this.repvitMs,
      dinov3Ms: dinov3Ms ?? this.dinov3Ms,
      postprocessMs: postprocessMs ?? this.postprocessMs,
      totalMs: totalMs ?? this.totalMs,
      startupDevice: startupDevice ?? this.startupDevice,
      startupLoadMs: startupLoadMs ?? this.startupLoadMs,
      startupWarmupMs: startupWarmupMs ?? this.startupWarmupMs,
      startupFallbackReason:
          startupFallbackReason ?? this.startupFallbackReason,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (attemptId.present) {
      map['attempt_id'] = Variable<String>(attemptId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (attemptNumber.present) {
      map['attempt_number'] = Variable<int>(attemptNumber.value);
    }
    if (capturedAtUs.present) {
      map['captured_at_us'] = Variable<int>(capturedAtUs.value);
    }
    if (imageRelativePath.present) {
      map['image_relative_path'] = Variable<String>(imageRelativePath.value);
    }
    if (imageByteSize.present) {
      map['image_byte_size'] = Variable<int>(imageByteSize.value);
    }
    if (imageSha256.present) {
      map['image_sha256'] = Variable<String>(imageSha256.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (canonicalWidth.present) {
      map['canonical_width'] = Variable<int>(canonicalWidth.value);
    }
    if (canonicalHeight.present) {
      map['canonical_height'] = Variable<int>(canonicalHeight.value);
    }
    if (receiptRelativePath.present) {
      map['receipt_relative_path'] = Variable<String>(
        receiptRelativePath.value,
      );
    }
    if (receiptByteSize.present) {
      map['receipt_byte_size'] = Variable<int>(receiptByteSize.value);
    }
    if (receiptSha256.present) {
      map['receipt_sha256'] = Variable<String>(receiptSha256.value);
    }
    if (presentationState.present) {
      map['presentation_state'] = Variable<String>(presentationState.value);
    }
    if (finalCountUsable.present) {
      map['final_count_usable'] = Variable<bool>(finalCountUsable.value);
    }
    if (retakeScope.present) {
      map['retake_scope'] = Variable<String>(retakeScope.value);
    }
    if (retakeReason.present) {
      map['retake_reason'] = Variable<String>(retakeReason.value);
    }
    if (presentationPolicyId.present) {
      map['presentation_policy_id'] = Variable<String>(
        presentationPolicyId.value,
      );
    }
    if (presentationPolicySha256.present) {
      map['presentation_policy_sha256'] = Variable<String>(
        presentationPolicySha256.value,
      );
    }
    if (decodePreprocessMs.present) {
      map['decode_preprocess_ms'] = Variable<double>(decodePreprocessMs.value);
    }
    if (detectorMs.present) {
      map['detector_ms'] = Variable<double>(detectorMs.value);
    }
    if (repvitMs.present) {
      map['repvit_ms'] = Variable<double>(repvitMs.value);
    }
    if (dinov3Ms.present) {
      map['dinov3_ms'] = Variable<double>(dinov3Ms.value);
    }
    if (postprocessMs.present) {
      map['postprocess_ms'] = Variable<double>(postprocessMs.value);
    }
    if (totalMs.present) {
      map['total_ms'] = Variable<double>(totalMs.value);
    }
    if (startupDevice.present) {
      map['startup_device'] = Variable<String>(startupDevice.value);
    }
    if (startupLoadMs.present) {
      map['startup_load_ms'] = Variable<double>(startupLoadMs.value);
    }
    if (startupWarmupMs.present) {
      map['startup_warmup_ms'] = Variable<double>(startupWarmupMs.value);
    }
    if (startupFallbackReason.present) {
      map['startup_fallback_reason'] = Variable<String>(
        startupFallbackReason.value,
      );
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ScanAttemptsCompanion(')
          ..write('attemptId: $attemptId, ')
          ..write('sessionId: $sessionId, ')
          ..write('attemptNumber: $attemptNumber, ')
          ..write('capturedAtUs: $capturedAtUs, ')
          ..write('imageRelativePath: $imageRelativePath, ')
          ..write('imageByteSize: $imageByteSize, ')
          ..write('imageSha256: $imageSha256, ')
          ..write('status: $status, ')
          ..write('canonicalWidth: $canonicalWidth, ')
          ..write('canonicalHeight: $canonicalHeight, ')
          ..write('receiptRelativePath: $receiptRelativePath, ')
          ..write('receiptByteSize: $receiptByteSize, ')
          ..write('receiptSha256: $receiptSha256, ')
          ..write('presentationState: $presentationState, ')
          ..write('finalCountUsable: $finalCountUsable, ')
          ..write('retakeScope: $retakeScope, ')
          ..write('retakeReason: $retakeReason, ')
          ..write('presentationPolicyId: $presentationPolicyId, ')
          ..write('presentationPolicySha256: $presentationPolicySha256, ')
          ..write('decodePreprocessMs: $decodePreprocessMs, ')
          ..write('detectorMs: $detectorMs, ')
          ..write('repvitMs: $repvitMs, ')
          ..write('dinov3Ms: $dinov3Ms, ')
          ..write('postprocessMs: $postprocessMs, ')
          ..write('totalMs: $totalMs, ')
          ..write('startupDevice: $startupDevice, ')
          ..write('startupLoadMs: $startupLoadMs, ')
          ..write('startupWarmupMs: $startupWarmupMs, ')
          ..write('startupFallbackReason: $startupFallbackReason, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $InferenceObjectsTable extends InferenceObjects
    with TableInfo<$InferenceObjectsTable, InferenceObjectRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $InferenceObjectsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _inferenceObjectIdMeta = const VerificationMeta(
    'inferenceObjectId',
  );
  @override
  late final GeneratedColumn<String> inferenceObjectId =
      GeneratedColumn<String>(
        'inference_object_id',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _attemptIdMeta = const VerificationMeta(
    'attemptId',
  );
  @override
  late final GeneratedColumn<String> attemptId = GeneratedColumn<String>(
    'attempt_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES scan_attempts (attempt_id)',
    ),
  );
  static const VerificationMeta _objectIdMeta = const VerificationMeta(
    'objectId',
  );
  @override
  late final GeneratedColumn<String> objectId = GeneratedColumn<String>(
    'object_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _skuIdMeta = const VerificationMeta('skuId');
  @override
  late final GeneratedColumn<int> skuId = GeneratedColumn<int>(
    'sku_id',
    aliasedName,
    true,
    check: () => ComparableExpr(skuId).isBetweenValues(1, 20),
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _skuNameMeta = const VerificationMeta(
    'skuName',
  );
  @override
  late final GeneratedColumn<String> skuName = GeneratedColumn<String>(
    'sku_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _decisionPathMeta = const VerificationMeta(
    'decisionPath',
  );
  @override
  late final GeneratedColumn<String> decisionPath = GeneratedColumn<String>(
    'decision_path',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _confidenceMeta = const VerificationMeta(
    'confidence',
  );
  @override
  late final GeneratedColumn<double> confidence = GeneratedColumn<double>(
    'confidence',
    aliasedName,
    false,
    check: () => ComparableExpr(confidence).isBetweenValues(0, 1),
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bboxJsonMeta = const VerificationMeta(
    'bboxJson',
  );
  @override
  late final GeneratedColumn<String> bboxJson = GeneratedColumn<String>(
    'bbox_json',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 9),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _detectorSourceMeta = const VerificationMeta(
    'detectorSource',
  );
  @override
  late final GeneratedColumn<String> detectorSource = GeneratedColumn<String>(
    'detector_source',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _detectorScoreMeta = const VerificationMeta(
    'detectorScore',
  );
  @override
  late final GeneratedColumn<double> detectorScore = GeneratedColumn<double>(
    'detector_score',
    aliasedName,
    false,
    check: () => ComparableExpr(detectorScore).isBetweenValues(0, 1),
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _provenanceJsonMeta = const VerificationMeta(
    'provenanceJson',
  );
  @override
  late final GeneratedColumn<String> provenanceJson = GeneratedColumn<String>(
    'provenance_json',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 100),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unknownReasonMeta = const VerificationMeta(
    'unknownReason',
  );
  @override
  late final GeneratedColumn<String> unknownReason = GeneratedColumn<String>(
    'unknown_reason',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    inferenceObjectId,
    attemptId,
    objectId,
    skuId,
    skuName,
    decisionPath,
    confidence,
    bboxJson,
    detectorSource,
    detectorScore,
    provenanceJson,
    unknownReason,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'inference_objects';
  @override
  VerificationContext validateIntegrity(
    Insertable<InferenceObjectRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('inference_object_id')) {
      context.handle(
        _inferenceObjectIdMeta,
        inferenceObjectId.isAcceptableOrUnknown(
          data['inference_object_id']!,
          _inferenceObjectIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_inferenceObjectIdMeta);
    }
    if (data.containsKey('attempt_id')) {
      context.handle(
        _attemptIdMeta,
        attemptId.isAcceptableOrUnknown(data['attempt_id']!, _attemptIdMeta),
      );
    } else if (isInserting) {
      context.missing(_attemptIdMeta);
    }
    if (data.containsKey('object_id')) {
      context.handle(
        _objectIdMeta,
        objectId.isAcceptableOrUnknown(data['object_id']!, _objectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_objectIdMeta);
    }
    if (data.containsKey('sku_id')) {
      context.handle(
        _skuIdMeta,
        skuId.isAcceptableOrUnknown(data['sku_id']!, _skuIdMeta),
      );
    }
    if (data.containsKey('sku_name')) {
      context.handle(
        _skuNameMeta,
        skuName.isAcceptableOrUnknown(data['sku_name']!, _skuNameMeta),
      );
    } else if (isInserting) {
      context.missing(_skuNameMeta);
    }
    if (data.containsKey('decision_path')) {
      context.handle(
        _decisionPathMeta,
        decisionPath.isAcceptableOrUnknown(
          data['decision_path']!,
          _decisionPathMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_decisionPathMeta);
    }
    if (data.containsKey('confidence')) {
      context.handle(
        _confidenceMeta,
        confidence.isAcceptableOrUnknown(data['confidence']!, _confidenceMeta),
      );
    } else if (isInserting) {
      context.missing(_confidenceMeta);
    }
    if (data.containsKey('bbox_json')) {
      context.handle(
        _bboxJsonMeta,
        bboxJson.isAcceptableOrUnknown(data['bbox_json']!, _bboxJsonMeta),
      );
    } else if (isInserting) {
      context.missing(_bboxJsonMeta);
    }
    if (data.containsKey('detector_source')) {
      context.handle(
        _detectorSourceMeta,
        detectorSource.isAcceptableOrUnknown(
          data['detector_source']!,
          _detectorSourceMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_detectorSourceMeta);
    }
    if (data.containsKey('detector_score')) {
      context.handle(
        _detectorScoreMeta,
        detectorScore.isAcceptableOrUnknown(
          data['detector_score']!,
          _detectorScoreMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_detectorScoreMeta);
    }
    if (data.containsKey('provenance_json')) {
      context.handle(
        _provenanceJsonMeta,
        provenanceJson.isAcceptableOrUnknown(
          data['provenance_json']!,
          _provenanceJsonMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_provenanceJsonMeta);
    }
    if (data.containsKey('unknown_reason')) {
      context.handle(
        _unknownReasonMeta,
        unknownReason.isAcceptableOrUnknown(
          data['unknown_reason']!,
          _unknownReasonMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {inferenceObjectId};
  @override
  InferenceObjectRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return InferenceObjectRow(
      inferenceObjectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}inference_object_id'],
      )!,
      attemptId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}attempt_id'],
      )!,
      objectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}object_id'],
      )!,
      skuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}sku_id'],
      ),
      skuName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sku_name'],
      )!,
      decisionPath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}decision_path'],
      )!,
      confidence: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}confidence'],
      )!,
      bboxJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}bbox_json'],
      )!,
      detectorSource: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}detector_source'],
      )!,
      detectorScore: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}detector_score'],
      )!,
      provenanceJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}provenance_json'],
      )!,
      unknownReason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}unknown_reason'],
      ),
    );
  }

  @override
  $InferenceObjectsTable createAlias(String alias) {
    return $InferenceObjectsTable(attachedDatabase, alias);
  }
}

class InferenceObjectRow extends DataClass
    implements Insertable<InferenceObjectRow> {
  final String inferenceObjectId;
  final String attemptId;
  final String objectId;
  final int? skuId;
  final String skuName;
  final String decisionPath;
  final double confidence;
  final String bboxJson;
  final String detectorSource;
  final double detectorScore;
  final String provenanceJson;
  final String? unknownReason;
  const InferenceObjectRow({
    required this.inferenceObjectId,
    required this.attemptId,
    required this.objectId,
    this.skuId,
    required this.skuName,
    required this.decisionPath,
    required this.confidence,
    required this.bboxJson,
    required this.detectorSource,
    required this.detectorScore,
    required this.provenanceJson,
    this.unknownReason,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['inference_object_id'] = Variable<String>(inferenceObjectId);
    map['attempt_id'] = Variable<String>(attemptId);
    map['object_id'] = Variable<String>(objectId);
    if (!nullToAbsent || skuId != null) {
      map['sku_id'] = Variable<int>(skuId);
    }
    map['sku_name'] = Variable<String>(skuName);
    map['decision_path'] = Variable<String>(decisionPath);
    map['confidence'] = Variable<double>(confidence);
    map['bbox_json'] = Variable<String>(bboxJson);
    map['detector_source'] = Variable<String>(detectorSource);
    map['detector_score'] = Variable<double>(detectorScore);
    map['provenance_json'] = Variable<String>(provenanceJson);
    if (!nullToAbsent || unknownReason != null) {
      map['unknown_reason'] = Variable<String>(unknownReason);
    }
    return map;
  }

  InferenceObjectsCompanion toCompanion(bool nullToAbsent) {
    return InferenceObjectsCompanion(
      inferenceObjectId: Value(inferenceObjectId),
      attemptId: Value(attemptId),
      objectId: Value(objectId),
      skuId: skuId == null && nullToAbsent
          ? const Value.absent()
          : Value(skuId),
      skuName: Value(skuName),
      decisionPath: Value(decisionPath),
      confidence: Value(confidence),
      bboxJson: Value(bboxJson),
      detectorSource: Value(detectorSource),
      detectorScore: Value(detectorScore),
      provenanceJson: Value(provenanceJson),
      unknownReason: unknownReason == null && nullToAbsent
          ? const Value.absent()
          : Value(unknownReason),
    );
  }

  factory InferenceObjectRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return InferenceObjectRow(
      inferenceObjectId: serializer.fromJson<String>(json['inferenceObjectId']),
      attemptId: serializer.fromJson<String>(json['attemptId']),
      objectId: serializer.fromJson<String>(json['objectId']),
      skuId: serializer.fromJson<int?>(json['skuId']),
      skuName: serializer.fromJson<String>(json['skuName']),
      decisionPath: serializer.fromJson<String>(json['decisionPath']),
      confidence: serializer.fromJson<double>(json['confidence']),
      bboxJson: serializer.fromJson<String>(json['bboxJson']),
      detectorSource: serializer.fromJson<String>(json['detectorSource']),
      detectorScore: serializer.fromJson<double>(json['detectorScore']),
      provenanceJson: serializer.fromJson<String>(json['provenanceJson']),
      unknownReason: serializer.fromJson<String?>(json['unknownReason']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'inferenceObjectId': serializer.toJson<String>(inferenceObjectId),
      'attemptId': serializer.toJson<String>(attemptId),
      'objectId': serializer.toJson<String>(objectId),
      'skuId': serializer.toJson<int?>(skuId),
      'skuName': serializer.toJson<String>(skuName),
      'decisionPath': serializer.toJson<String>(decisionPath),
      'confidence': serializer.toJson<double>(confidence),
      'bboxJson': serializer.toJson<String>(bboxJson),
      'detectorSource': serializer.toJson<String>(detectorSource),
      'detectorScore': serializer.toJson<double>(detectorScore),
      'provenanceJson': serializer.toJson<String>(provenanceJson),
      'unknownReason': serializer.toJson<String?>(unknownReason),
    };
  }

  InferenceObjectRow copyWith({
    String? inferenceObjectId,
    String? attemptId,
    String? objectId,
    Value<int?> skuId = const Value.absent(),
    String? skuName,
    String? decisionPath,
    double? confidence,
    String? bboxJson,
    String? detectorSource,
    double? detectorScore,
    String? provenanceJson,
    Value<String?> unknownReason = const Value.absent(),
  }) => InferenceObjectRow(
    inferenceObjectId: inferenceObjectId ?? this.inferenceObjectId,
    attemptId: attemptId ?? this.attemptId,
    objectId: objectId ?? this.objectId,
    skuId: skuId.present ? skuId.value : this.skuId,
    skuName: skuName ?? this.skuName,
    decisionPath: decisionPath ?? this.decisionPath,
    confidence: confidence ?? this.confidence,
    bboxJson: bboxJson ?? this.bboxJson,
    detectorSource: detectorSource ?? this.detectorSource,
    detectorScore: detectorScore ?? this.detectorScore,
    provenanceJson: provenanceJson ?? this.provenanceJson,
    unknownReason: unknownReason.present
        ? unknownReason.value
        : this.unknownReason,
  );
  InferenceObjectRow copyWithCompanion(InferenceObjectsCompanion data) {
    return InferenceObjectRow(
      inferenceObjectId: data.inferenceObjectId.present
          ? data.inferenceObjectId.value
          : this.inferenceObjectId,
      attemptId: data.attemptId.present ? data.attemptId.value : this.attemptId,
      objectId: data.objectId.present ? data.objectId.value : this.objectId,
      skuId: data.skuId.present ? data.skuId.value : this.skuId,
      skuName: data.skuName.present ? data.skuName.value : this.skuName,
      decisionPath: data.decisionPath.present
          ? data.decisionPath.value
          : this.decisionPath,
      confidence: data.confidence.present
          ? data.confidence.value
          : this.confidence,
      bboxJson: data.bboxJson.present ? data.bboxJson.value : this.bboxJson,
      detectorSource: data.detectorSource.present
          ? data.detectorSource.value
          : this.detectorSource,
      detectorScore: data.detectorScore.present
          ? data.detectorScore.value
          : this.detectorScore,
      provenanceJson: data.provenanceJson.present
          ? data.provenanceJson.value
          : this.provenanceJson,
      unknownReason: data.unknownReason.present
          ? data.unknownReason.value
          : this.unknownReason,
    );
  }

  @override
  String toString() {
    return (StringBuffer('InferenceObjectRow(')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('attemptId: $attemptId, ')
          ..write('objectId: $objectId, ')
          ..write('skuId: $skuId, ')
          ..write('skuName: $skuName, ')
          ..write('decisionPath: $decisionPath, ')
          ..write('confidence: $confidence, ')
          ..write('bboxJson: $bboxJson, ')
          ..write('detectorSource: $detectorSource, ')
          ..write('detectorScore: $detectorScore, ')
          ..write('provenanceJson: $provenanceJson, ')
          ..write('unknownReason: $unknownReason')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    inferenceObjectId,
    attemptId,
    objectId,
    skuId,
    skuName,
    decisionPath,
    confidence,
    bboxJson,
    detectorSource,
    detectorScore,
    provenanceJson,
    unknownReason,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is InferenceObjectRow &&
          other.inferenceObjectId == this.inferenceObjectId &&
          other.attemptId == this.attemptId &&
          other.objectId == this.objectId &&
          other.skuId == this.skuId &&
          other.skuName == this.skuName &&
          other.decisionPath == this.decisionPath &&
          other.confidence == this.confidence &&
          other.bboxJson == this.bboxJson &&
          other.detectorSource == this.detectorSource &&
          other.detectorScore == this.detectorScore &&
          other.provenanceJson == this.provenanceJson &&
          other.unknownReason == this.unknownReason);
}

class InferenceObjectsCompanion extends UpdateCompanion<InferenceObjectRow> {
  final Value<String> inferenceObjectId;
  final Value<String> attemptId;
  final Value<String> objectId;
  final Value<int?> skuId;
  final Value<String> skuName;
  final Value<String> decisionPath;
  final Value<double> confidence;
  final Value<String> bboxJson;
  final Value<String> detectorSource;
  final Value<double> detectorScore;
  final Value<String> provenanceJson;
  final Value<String?> unknownReason;
  final Value<int> rowid;
  const InferenceObjectsCompanion({
    this.inferenceObjectId = const Value.absent(),
    this.attemptId = const Value.absent(),
    this.objectId = const Value.absent(),
    this.skuId = const Value.absent(),
    this.skuName = const Value.absent(),
    this.decisionPath = const Value.absent(),
    this.confidence = const Value.absent(),
    this.bboxJson = const Value.absent(),
    this.detectorSource = const Value.absent(),
    this.detectorScore = const Value.absent(),
    this.provenanceJson = const Value.absent(),
    this.unknownReason = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  InferenceObjectsCompanion.insert({
    required String inferenceObjectId,
    required String attemptId,
    required String objectId,
    this.skuId = const Value.absent(),
    required String skuName,
    required String decisionPath,
    required double confidence,
    required String bboxJson,
    required String detectorSource,
    required double detectorScore,
    required String provenanceJson,
    this.unknownReason = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : inferenceObjectId = Value(inferenceObjectId),
       attemptId = Value(attemptId),
       objectId = Value(objectId),
       skuName = Value(skuName),
       decisionPath = Value(decisionPath),
       confidence = Value(confidence),
       bboxJson = Value(bboxJson),
       detectorSource = Value(detectorSource),
       detectorScore = Value(detectorScore),
       provenanceJson = Value(provenanceJson);
  static Insertable<InferenceObjectRow> custom({
    Expression<String>? inferenceObjectId,
    Expression<String>? attemptId,
    Expression<String>? objectId,
    Expression<int>? skuId,
    Expression<String>? skuName,
    Expression<String>? decisionPath,
    Expression<double>? confidence,
    Expression<String>? bboxJson,
    Expression<String>? detectorSource,
    Expression<double>? detectorScore,
    Expression<String>? provenanceJson,
    Expression<String>? unknownReason,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (inferenceObjectId != null) 'inference_object_id': inferenceObjectId,
      if (attemptId != null) 'attempt_id': attemptId,
      if (objectId != null) 'object_id': objectId,
      if (skuId != null) 'sku_id': skuId,
      if (skuName != null) 'sku_name': skuName,
      if (decisionPath != null) 'decision_path': decisionPath,
      if (confidence != null) 'confidence': confidence,
      if (bboxJson != null) 'bbox_json': bboxJson,
      if (detectorSource != null) 'detector_source': detectorSource,
      if (detectorScore != null) 'detector_score': detectorScore,
      if (provenanceJson != null) 'provenance_json': provenanceJson,
      if (unknownReason != null) 'unknown_reason': unknownReason,
      if (rowid != null) 'rowid': rowid,
    });
  }

  InferenceObjectsCompanion copyWith({
    Value<String>? inferenceObjectId,
    Value<String>? attemptId,
    Value<String>? objectId,
    Value<int?>? skuId,
    Value<String>? skuName,
    Value<String>? decisionPath,
    Value<double>? confidence,
    Value<String>? bboxJson,
    Value<String>? detectorSource,
    Value<double>? detectorScore,
    Value<String>? provenanceJson,
    Value<String?>? unknownReason,
    Value<int>? rowid,
  }) {
    return InferenceObjectsCompanion(
      inferenceObjectId: inferenceObjectId ?? this.inferenceObjectId,
      attemptId: attemptId ?? this.attemptId,
      objectId: objectId ?? this.objectId,
      skuId: skuId ?? this.skuId,
      skuName: skuName ?? this.skuName,
      decisionPath: decisionPath ?? this.decisionPath,
      confidence: confidence ?? this.confidence,
      bboxJson: bboxJson ?? this.bboxJson,
      detectorSource: detectorSource ?? this.detectorSource,
      detectorScore: detectorScore ?? this.detectorScore,
      provenanceJson: provenanceJson ?? this.provenanceJson,
      unknownReason: unknownReason ?? this.unknownReason,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (inferenceObjectId.present) {
      map['inference_object_id'] = Variable<String>(inferenceObjectId.value);
    }
    if (attemptId.present) {
      map['attempt_id'] = Variable<String>(attemptId.value);
    }
    if (objectId.present) {
      map['object_id'] = Variable<String>(objectId.value);
    }
    if (skuId.present) {
      map['sku_id'] = Variable<int>(skuId.value);
    }
    if (skuName.present) {
      map['sku_name'] = Variable<String>(skuName.value);
    }
    if (decisionPath.present) {
      map['decision_path'] = Variable<String>(decisionPath.value);
    }
    if (confidence.present) {
      map['confidence'] = Variable<double>(confidence.value);
    }
    if (bboxJson.present) {
      map['bbox_json'] = Variable<String>(bboxJson.value);
    }
    if (detectorSource.present) {
      map['detector_source'] = Variable<String>(detectorSource.value);
    }
    if (detectorScore.present) {
      map['detector_score'] = Variable<double>(detectorScore.value);
    }
    if (provenanceJson.present) {
      map['provenance_json'] = Variable<String>(provenanceJson.value);
    }
    if (unknownReason.present) {
      map['unknown_reason'] = Variable<String>(unknownReason.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('InferenceObjectsCompanion(')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('attemptId: $attemptId, ')
          ..write('objectId: $objectId, ')
          ..write('skuId: $skuId, ')
          ..write('skuName: $skuName, ')
          ..write('decisionPath: $decisionPath, ')
          ..write('confidence: $confidence, ')
          ..write('bboxJson: $bboxJson, ')
          ..write('detectorSource: $detectorSource, ')
          ..write('detectorScore: $detectorScore, ')
          ..write('provenanceJson: $provenanceJson, ')
          ..write('unknownReason: $unknownReason, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $InferenceCandidatesTable extends InferenceCandidates
    with TableInfo<$InferenceCandidatesTable, InferenceCandidateRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $InferenceCandidatesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _inferenceCandidateIdMeta =
      const VerificationMeta('inferenceCandidateId');
  @override
  late final GeneratedColumn<String> inferenceCandidateId =
      GeneratedColumn<String>(
        'inference_candidate_id',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _inferenceObjectIdMeta = const VerificationMeta(
    'inferenceObjectId',
  );
  @override
  late final GeneratedColumn<String> inferenceObjectId =
      GeneratedColumn<String>(
        'inference_object_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES inference_objects (inference_object_id)',
        ),
      );
  static const VerificationMeta _rankMeta = const VerificationMeta('rank');
  @override
  late final GeneratedColumn<int> rank = GeneratedColumn<int>(
    'rank',
    aliasedName,
    false,
    check: () => ComparableExpr(rank).isBetweenValues(1, 3),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _skuIdMeta = const VerificationMeta('skuId');
  @override
  late final GeneratedColumn<int> skuId = GeneratedColumn<int>(
    'sku_id',
    aliasedName,
    false,
    check: () => ComparableExpr(skuId).isBetweenValues(1, 20),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _skuNameMeta = const VerificationMeta(
    'skuName',
  );
  @override
  late final GeneratedColumn<String> skuName = GeneratedColumn<String>(
    'sku_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _scoreMeta = const VerificationMeta('score');
  @override
  late final GeneratedColumn<double> score = GeneratedColumn<double>(
    'score',
    aliasedName,
    false,
    check: () => ComparableExpr(score).isBetweenValues(0, 1),
    type: DriftSqlType.double,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    inferenceCandidateId,
    inferenceObjectId,
    rank,
    skuId,
    skuName,
    score,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'inference_candidates';
  @override
  VerificationContext validateIntegrity(
    Insertable<InferenceCandidateRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('inference_candidate_id')) {
      context.handle(
        _inferenceCandidateIdMeta,
        inferenceCandidateId.isAcceptableOrUnknown(
          data['inference_candidate_id']!,
          _inferenceCandidateIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_inferenceCandidateIdMeta);
    }
    if (data.containsKey('inference_object_id')) {
      context.handle(
        _inferenceObjectIdMeta,
        inferenceObjectId.isAcceptableOrUnknown(
          data['inference_object_id']!,
          _inferenceObjectIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_inferenceObjectIdMeta);
    }
    if (data.containsKey('rank')) {
      context.handle(
        _rankMeta,
        rank.isAcceptableOrUnknown(data['rank']!, _rankMeta),
      );
    } else if (isInserting) {
      context.missing(_rankMeta);
    }
    if (data.containsKey('sku_id')) {
      context.handle(
        _skuIdMeta,
        skuId.isAcceptableOrUnknown(data['sku_id']!, _skuIdMeta),
      );
    } else if (isInserting) {
      context.missing(_skuIdMeta);
    }
    if (data.containsKey('sku_name')) {
      context.handle(
        _skuNameMeta,
        skuName.isAcceptableOrUnknown(data['sku_name']!, _skuNameMeta),
      );
    } else if (isInserting) {
      context.missing(_skuNameMeta);
    }
    if (data.containsKey('score')) {
      context.handle(
        _scoreMeta,
        score.isAcceptableOrUnknown(data['score']!, _scoreMeta),
      );
    } else if (isInserting) {
      context.missing(_scoreMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {inferenceCandidateId};
  @override
  InferenceCandidateRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return InferenceCandidateRow(
      inferenceCandidateId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}inference_candidate_id'],
      )!,
      inferenceObjectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}inference_object_id'],
      )!,
      rank: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}rank'],
      )!,
      skuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}sku_id'],
      )!,
      skuName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sku_name'],
      )!,
      score: attachedDatabase.typeMapping.read(
        DriftSqlType.double,
        data['${effectivePrefix}score'],
      )!,
    );
  }

  @override
  $InferenceCandidatesTable createAlias(String alias) {
    return $InferenceCandidatesTable(attachedDatabase, alias);
  }
}

class InferenceCandidateRow extends DataClass
    implements Insertable<InferenceCandidateRow> {
  final String inferenceCandidateId;
  final String inferenceObjectId;
  final int rank;
  final int skuId;
  final String skuName;
  final double score;
  const InferenceCandidateRow({
    required this.inferenceCandidateId,
    required this.inferenceObjectId,
    required this.rank,
    required this.skuId,
    required this.skuName,
    required this.score,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['inference_candidate_id'] = Variable<String>(inferenceCandidateId);
    map['inference_object_id'] = Variable<String>(inferenceObjectId);
    map['rank'] = Variable<int>(rank);
    map['sku_id'] = Variable<int>(skuId);
    map['sku_name'] = Variable<String>(skuName);
    map['score'] = Variable<double>(score);
    return map;
  }

  InferenceCandidatesCompanion toCompanion(bool nullToAbsent) {
    return InferenceCandidatesCompanion(
      inferenceCandidateId: Value(inferenceCandidateId),
      inferenceObjectId: Value(inferenceObjectId),
      rank: Value(rank),
      skuId: Value(skuId),
      skuName: Value(skuName),
      score: Value(score),
    );
  }

  factory InferenceCandidateRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return InferenceCandidateRow(
      inferenceCandidateId: serializer.fromJson<String>(
        json['inferenceCandidateId'],
      ),
      inferenceObjectId: serializer.fromJson<String>(json['inferenceObjectId']),
      rank: serializer.fromJson<int>(json['rank']),
      skuId: serializer.fromJson<int>(json['skuId']),
      skuName: serializer.fromJson<String>(json['skuName']),
      score: serializer.fromJson<double>(json['score']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'inferenceCandidateId': serializer.toJson<String>(inferenceCandidateId),
      'inferenceObjectId': serializer.toJson<String>(inferenceObjectId),
      'rank': serializer.toJson<int>(rank),
      'skuId': serializer.toJson<int>(skuId),
      'skuName': serializer.toJson<String>(skuName),
      'score': serializer.toJson<double>(score),
    };
  }

  InferenceCandidateRow copyWith({
    String? inferenceCandidateId,
    String? inferenceObjectId,
    int? rank,
    int? skuId,
    String? skuName,
    double? score,
  }) => InferenceCandidateRow(
    inferenceCandidateId: inferenceCandidateId ?? this.inferenceCandidateId,
    inferenceObjectId: inferenceObjectId ?? this.inferenceObjectId,
    rank: rank ?? this.rank,
    skuId: skuId ?? this.skuId,
    skuName: skuName ?? this.skuName,
    score: score ?? this.score,
  );
  InferenceCandidateRow copyWithCompanion(InferenceCandidatesCompanion data) {
    return InferenceCandidateRow(
      inferenceCandidateId: data.inferenceCandidateId.present
          ? data.inferenceCandidateId.value
          : this.inferenceCandidateId,
      inferenceObjectId: data.inferenceObjectId.present
          ? data.inferenceObjectId.value
          : this.inferenceObjectId,
      rank: data.rank.present ? data.rank.value : this.rank,
      skuId: data.skuId.present ? data.skuId.value : this.skuId,
      skuName: data.skuName.present ? data.skuName.value : this.skuName,
      score: data.score.present ? data.score.value : this.score,
    );
  }

  @override
  String toString() {
    return (StringBuffer('InferenceCandidateRow(')
          ..write('inferenceCandidateId: $inferenceCandidateId, ')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('rank: $rank, ')
          ..write('skuId: $skuId, ')
          ..write('skuName: $skuName, ')
          ..write('score: $score')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    inferenceCandidateId,
    inferenceObjectId,
    rank,
    skuId,
    skuName,
    score,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is InferenceCandidateRow &&
          other.inferenceCandidateId == this.inferenceCandidateId &&
          other.inferenceObjectId == this.inferenceObjectId &&
          other.rank == this.rank &&
          other.skuId == this.skuId &&
          other.skuName == this.skuName &&
          other.score == this.score);
}

class InferenceCandidatesCompanion
    extends UpdateCompanion<InferenceCandidateRow> {
  final Value<String> inferenceCandidateId;
  final Value<String> inferenceObjectId;
  final Value<int> rank;
  final Value<int> skuId;
  final Value<String> skuName;
  final Value<double> score;
  final Value<int> rowid;
  const InferenceCandidatesCompanion({
    this.inferenceCandidateId = const Value.absent(),
    this.inferenceObjectId = const Value.absent(),
    this.rank = const Value.absent(),
    this.skuId = const Value.absent(),
    this.skuName = const Value.absent(),
    this.score = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  InferenceCandidatesCompanion.insert({
    required String inferenceCandidateId,
    required String inferenceObjectId,
    required int rank,
    required int skuId,
    required String skuName,
    required double score,
    this.rowid = const Value.absent(),
  }) : inferenceCandidateId = Value(inferenceCandidateId),
       inferenceObjectId = Value(inferenceObjectId),
       rank = Value(rank),
       skuId = Value(skuId),
       skuName = Value(skuName),
       score = Value(score);
  static Insertable<InferenceCandidateRow> custom({
    Expression<String>? inferenceCandidateId,
    Expression<String>? inferenceObjectId,
    Expression<int>? rank,
    Expression<int>? skuId,
    Expression<String>? skuName,
    Expression<double>? score,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (inferenceCandidateId != null)
        'inference_candidate_id': inferenceCandidateId,
      if (inferenceObjectId != null) 'inference_object_id': inferenceObjectId,
      if (rank != null) 'rank': rank,
      if (skuId != null) 'sku_id': skuId,
      if (skuName != null) 'sku_name': skuName,
      if (score != null) 'score': score,
      if (rowid != null) 'rowid': rowid,
    });
  }

  InferenceCandidatesCompanion copyWith({
    Value<String>? inferenceCandidateId,
    Value<String>? inferenceObjectId,
    Value<int>? rank,
    Value<int>? skuId,
    Value<String>? skuName,
    Value<double>? score,
    Value<int>? rowid,
  }) {
    return InferenceCandidatesCompanion(
      inferenceCandidateId: inferenceCandidateId ?? this.inferenceCandidateId,
      inferenceObjectId: inferenceObjectId ?? this.inferenceObjectId,
      rank: rank ?? this.rank,
      skuId: skuId ?? this.skuId,
      skuName: skuName ?? this.skuName,
      score: score ?? this.score,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (inferenceCandidateId.present) {
      map['inference_candidate_id'] = Variable<String>(
        inferenceCandidateId.value,
      );
    }
    if (inferenceObjectId.present) {
      map['inference_object_id'] = Variable<String>(inferenceObjectId.value);
    }
    if (rank.present) {
      map['rank'] = Variable<int>(rank.value);
    }
    if (skuId.present) {
      map['sku_id'] = Variable<int>(skuId.value);
    }
    if (skuName.present) {
      map['sku_name'] = Variable<String>(skuName.value);
    }
    if (score.present) {
      map['score'] = Variable<double>(score.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('InferenceCandidatesCompanion(')
          ..write('inferenceCandidateId: $inferenceCandidateId, ')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('rank: $rank, ')
          ..write('skuId: $skuId, ')
          ..write('skuName: $skuName, ')
          ..write('score: $score, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ObjectResolutionsTable extends ObjectResolutions
    with TableInfo<$ObjectResolutionsTable, ObjectResolutionRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ObjectResolutionsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _resolutionIdMeta = const VerificationMeta(
    'resolutionId',
  );
  @override
  late final GeneratedColumn<String> resolutionId = GeneratedColumn<String>(
    'resolution_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _inferenceObjectIdMeta = const VerificationMeta(
    'inferenceObjectId',
  );
  @override
  late final GeneratedColumn<String> inferenceObjectId =
      GeneratedColumn<String>(
        'inference_object_id',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES inference_objects (inference_object_id)',
        ),
      );
  static const VerificationMeta _productRevisionIdMeta = const VerificationMeta(
    'productRevisionId',
  );
  @override
  late final GeneratedColumn<String> productRevisionId =
      GeneratedColumn<String>(
        'product_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES products (product_revision_id)',
        ),
      );
  static const VerificationMeta _productIdMeta = const VerificationMeta(
    'productId',
  );
  @override
  late final GeneratedColumn<String> productId = GeneratedColumn<String>(
    'product_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _recognitionSkuIdMeta = const VerificationMeta(
    'recognitionSkuId',
  );
  @override
  late final GeneratedColumn<int> recognitionSkuId = GeneratedColumn<int>(
    'recognition_sku_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _productNameMeta = const VerificationMeta(
    'productName',
  );
  @override
  late final GeneratedColumn<String> productName = GeneratedColumn<String>(
    'product_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitPriceKrwMeta = const VerificationMeta(
    'unitPriceKrw',
  );
  @override
  late final GeneratedColumn<int> unitPriceKrw = GeneratedColumn<int>(
    'unit_price_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(unitPriceKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sourceMeta = const VerificationMeta('source');
  @override
  late final GeneratedColumn<String> source = GeneratedColumn<String>(
    'source',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _resolvedAtUsMeta = const VerificationMeta(
    'resolvedAtUs',
  );
  @override
  late final GeneratedColumn<int> resolvedAtUs = GeneratedColumn<int>(
    'resolved_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _candidateRankMeta = const VerificationMeta(
    'candidateRank',
  );
  @override
  late final GeneratedColumn<int> candidateRank = GeneratedColumn<int>(
    'candidate_rank',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _canonicalBboxJsonMeta = const VerificationMeta(
    'canonicalBboxJson',
  );
  @override
  late final GeneratedColumn<String> canonicalBboxJson =
      GeneratedColumn<String>(
        'canonical_bbox_json',
        aliasedName,
        true,
        type: DriftSqlType.string,
        requiredDuringInsert: false,
      );
  static const VerificationMeta _isCurrentMeta = const VerificationMeta(
    'isCurrent',
  );
  @override
  late final GeneratedColumn<bool> isCurrent = GeneratedColumn<bool>(
    'is_current',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_current" IN (0, 1))',
    ),
  );
  @override
  List<GeneratedColumn> get $columns => [
    resolutionId,
    sessionId,
    inferenceObjectId,
    productRevisionId,
    productId,
    recognitionSkuId,
    productName,
    unitPriceKrw,
    source,
    resolvedAtUs,
    candidateRank,
    canonicalBboxJson,
    isCurrent,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'object_resolutions';
  @override
  VerificationContext validateIntegrity(
    Insertable<ObjectResolutionRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('resolution_id')) {
      context.handle(
        _resolutionIdMeta,
        resolutionId.isAcceptableOrUnknown(
          data['resolution_id']!,
          _resolutionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_resolutionIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('inference_object_id')) {
      context.handle(
        _inferenceObjectIdMeta,
        inferenceObjectId.isAcceptableOrUnknown(
          data['inference_object_id']!,
          _inferenceObjectIdMeta,
        ),
      );
    }
    if (data.containsKey('product_revision_id')) {
      context.handle(
        _productRevisionIdMeta,
        productRevisionId.isAcceptableOrUnknown(
          data['product_revision_id']!,
          _productRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productRevisionIdMeta);
    }
    if (data.containsKey('product_id')) {
      context.handle(
        _productIdMeta,
        productId.isAcceptableOrUnknown(data['product_id']!, _productIdMeta),
      );
    } else if (isInserting) {
      context.missing(_productIdMeta);
    }
    if (data.containsKey('recognition_sku_id')) {
      context.handle(
        _recognitionSkuIdMeta,
        recognitionSkuId.isAcceptableOrUnknown(
          data['recognition_sku_id']!,
          _recognitionSkuIdMeta,
        ),
      );
    }
    if (data.containsKey('product_name')) {
      context.handle(
        _productNameMeta,
        productName.isAcceptableOrUnknown(
          data['product_name']!,
          _productNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productNameMeta);
    }
    if (data.containsKey('unit_price_krw')) {
      context.handle(
        _unitPriceKrwMeta,
        unitPriceKrw.isAcceptableOrUnknown(
          data['unit_price_krw']!,
          _unitPriceKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_unitPriceKrwMeta);
    }
    if (data.containsKey('source')) {
      context.handle(
        _sourceMeta,
        source.isAcceptableOrUnknown(data['source']!, _sourceMeta),
      );
    } else if (isInserting) {
      context.missing(_sourceMeta);
    }
    if (data.containsKey('resolved_at_us')) {
      context.handle(
        _resolvedAtUsMeta,
        resolvedAtUs.isAcceptableOrUnknown(
          data['resolved_at_us']!,
          _resolvedAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_resolvedAtUsMeta);
    }
    if (data.containsKey('candidate_rank')) {
      context.handle(
        _candidateRankMeta,
        candidateRank.isAcceptableOrUnknown(
          data['candidate_rank']!,
          _candidateRankMeta,
        ),
      );
    }
    if (data.containsKey('canonical_bbox_json')) {
      context.handle(
        _canonicalBboxJsonMeta,
        canonicalBboxJson.isAcceptableOrUnknown(
          data['canonical_bbox_json']!,
          _canonicalBboxJsonMeta,
        ),
      );
    }
    if (data.containsKey('is_current')) {
      context.handle(
        _isCurrentMeta,
        isCurrent.isAcceptableOrUnknown(data['is_current']!, _isCurrentMeta),
      );
    } else if (isInserting) {
      context.missing(_isCurrentMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {resolutionId};
  @override
  ObjectResolutionRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return ObjectResolutionRow(
      resolutionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}resolution_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      inferenceObjectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}inference_object_id'],
      ),
      productRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_revision_id'],
      )!,
      productId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_id'],
      )!,
      recognitionSkuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recognition_sku_id'],
      ),
      productName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_name'],
      )!,
      unitPriceKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}unit_price_krw'],
      )!,
      source: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}source'],
      )!,
      resolvedAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}resolved_at_us'],
      )!,
      candidateRank: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}candidate_rank'],
      ),
      canonicalBboxJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}canonical_bbox_json'],
      ),
      isCurrent: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_current'],
      )!,
    );
  }

  @override
  $ObjectResolutionsTable createAlias(String alias) {
    return $ObjectResolutionsTable(attachedDatabase, alias);
  }
}

class ObjectResolutionRow extends DataClass
    implements Insertable<ObjectResolutionRow> {
  final String resolutionId;
  final String sessionId;
  final String? inferenceObjectId;
  final String productRevisionId;
  final String productId;
  final int? recognitionSkuId;
  final String productName;
  final int unitPriceKrw;
  final String source;
  final int resolvedAtUs;
  final int? candidateRank;
  final String? canonicalBboxJson;
  final bool isCurrent;
  const ObjectResolutionRow({
    required this.resolutionId,
    required this.sessionId,
    this.inferenceObjectId,
    required this.productRevisionId,
    required this.productId,
    this.recognitionSkuId,
    required this.productName,
    required this.unitPriceKrw,
    required this.source,
    required this.resolvedAtUs,
    this.candidateRank,
    this.canonicalBboxJson,
    required this.isCurrent,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['resolution_id'] = Variable<String>(resolutionId);
    map['session_id'] = Variable<String>(sessionId);
    if (!nullToAbsent || inferenceObjectId != null) {
      map['inference_object_id'] = Variable<String>(inferenceObjectId);
    }
    map['product_revision_id'] = Variable<String>(productRevisionId);
    map['product_id'] = Variable<String>(productId);
    if (!nullToAbsent || recognitionSkuId != null) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId);
    }
    map['product_name'] = Variable<String>(productName);
    map['unit_price_krw'] = Variable<int>(unitPriceKrw);
    map['source'] = Variable<String>(source);
    map['resolved_at_us'] = Variable<int>(resolvedAtUs);
    if (!nullToAbsent || candidateRank != null) {
      map['candidate_rank'] = Variable<int>(candidateRank);
    }
    if (!nullToAbsent || canonicalBboxJson != null) {
      map['canonical_bbox_json'] = Variable<String>(canonicalBboxJson);
    }
    map['is_current'] = Variable<bool>(isCurrent);
    return map;
  }

  ObjectResolutionsCompanion toCompanion(bool nullToAbsent) {
    return ObjectResolutionsCompanion(
      resolutionId: Value(resolutionId),
      sessionId: Value(sessionId),
      inferenceObjectId: inferenceObjectId == null && nullToAbsent
          ? const Value.absent()
          : Value(inferenceObjectId),
      productRevisionId: Value(productRevisionId),
      productId: Value(productId),
      recognitionSkuId: recognitionSkuId == null && nullToAbsent
          ? const Value.absent()
          : Value(recognitionSkuId),
      productName: Value(productName),
      unitPriceKrw: Value(unitPriceKrw),
      source: Value(source),
      resolvedAtUs: Value(resolvedAtUs),
      candidateRank: candidateRank == null && nullToAbsent
          ? const Value.absent()
          : Value(candidateRank),
      canonicalBboxJson: canonicalBboxJson == null && nullToAbsent
          ? const Value.absent()
          : Value(canonicalBboxJson),
      isCurrent: Value(isCurrent),
    );
  }

  factory ObjectResolutionRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return ObjectResolutionRow(
      resolutionId: serializer.fromJson<String>(json['resolutionId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      inferenceObjectId: serializer.fromJson<String?>(
        json['inferenceObjectId'],
      ),
      productRevisionId: serializer.fromJson<String>(json['productRevisionId']),
      productId: serializer.fromJson<String>(json['productId']),
      recognitionSkuId: serializer.fromJson<int?>(json['recognitionSkuId']),
      productName: serializer.fromJson<String>(json['productName']),
      unitPriceKrw: serializer.fromJson<int>(json['unitPriceKrw']),
      source: serializer.fromJson<String>(json['source']),
      resolvedAtUs: serializer.fromJson<int>(json['resolvedAtUs']),
      candidateRank: serializer.fromJson<int?>(json['candidateRank']),
      canonicalBboxJson: serializer.fromJson<String?>(
        json['canonicalBboxJson'],
      ),
      isCurrent: serializer.fromJson<bool>(json['isCurrent']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'resolutionId': serializer.toJson<String>(resolutionId),
      'sessionId': serializer.toJson<String>(sessionId),
      'inferenceObjectId': serializer.toJson<String?>(inferenceObjectId),
      'productRevisionId': serializer.toJson<String>(productRevisionId),
      'productId': serializer.toJson<String>(productId),
      'recognitionSkuId': serializer.toJson<int?>(recognitionSkuId),
      'productName': serializer.toJson<String>(productName),
      'unitPriceKrw': serializer.toJson<int>(unitPriceKrw),
      'source': serializer.toJson<String>(source),
      'resolvedAtUs': serializer.toJson<int>(resolvedAtUs),
      'candidateRank': serializer.toJson<int?>(candidateRank),
      'canonicalBboxJson': serializer.toJson<String?>(canonicalBboxJson),
      'isCurrent': serializer.toJson<bool>(isCurrent),
    };
  }

  ObjectResolutionRow copyWith({
    String? resolutionId,
    String? sessionId,
    Value<String?> inferenceObjectId = const Value.absent(),
    String? productRevisionId,
    String? productId,
    Value<int?> recognitionSkuId = const Value.absent(),
    String? productName,
    int? unitPriceKrw,
    String? source,
    int? resolvedAtUs,
    Value<int?> candidateRank = const Value.absent(),
    Value<String?> canonicalBboxJson = const Value.absent(),
    bool? isCurrent,
  }) => ObjectResolutionRow(
    resolutionId: resolutionId ?? this.resolutionId,
    sessionId: sessionId ?? this.sessionId,
    inferenceObjectId: inferenceObjectId.present
        ? inferenceObjectId.value
        : this.inferenceObjectId,
    productRevisionId: productRevisionId ?? this.productRevisionId,
    productId: productId ?? this.productId,
    recognitionSkuId: recognitionSkuId.present
        ? recognitionSkuId.value
        : this.recognitionSkuId,
    productName: productName ?? this.productName,
    unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
    source: source ?? this.source,
    resolvedAtUs: resolvedAtUs ?? this.resolvedAtUs,
    candidateRank: candidateRank.present
        ? candidateRank.value
        : this.candidateRank,
    canonicalBboxJson: canonicalBboxJson.present
        ? canonicalBboxJson.value
        : this.canonicalBboxJson,
    isCurrent: isCurrent ?? this.isCurrent,
  );
  ObjectResolutionRow copyWithCompanion(ObjectResolutionsCompanion data) {
    return ObjectResolutionRow(
      resolutionId: data.resolutionId.present
          ? data.resolutionId.value
          : this.resolutionId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      inferenceObjectId: data.inferenceObjectId.present
          ? data.inferenceObjectId.value
          : this.inferenceObjectId,
      productRevisionId: data.productRevisionId.present
          ? data.productRevisionId.value
          : this.productRevisionId,
      productId: data.productId.present ? data.productId.value : this.productId,
      recognitionSkuId: data.recognitionSkuId.present
          ? data.recognitionSkuId.value
          : this.recognitionSkuId,
      productName: data.productName.present
          ? data.productName.value
          : this.productName,
      unitPriceKrw: data.unitPriceKrw.present
          ? data.unitPriceKrw.value
          : this.unitPriceKrw,
      source: data.source.present ? data.source.value : this.source,
      resolvedAtUs: data.resolvedAtUs.present
          ? data.resolvedAtUs.value
          : this.resolvedAtUs,
      candidateRank: data.candidateRank.present
          ? data.candidateRank.value
          : this.candidateRank,
      canonicalBboxJson: data.canonicalBboxJson.present
          ? data.canonicalBboxJson.value
          : this.canonicalBboxJson,
      isCurrent: data.isCurrent.present ? data.isCurrent.value : this.isCurrent,
    );
  }

  @override
  String toString() {
    return (StringBuffer('ObjectResolutionRow(')
          ..write('resolutionId: $resolutionId, ')
          ..write('sessionId: $sessionId, ')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('productName: $productName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('source: $source, ')
          ..write('resolvedAtUs: $resolvedAtUs, ')
          ..write('candidateRank: $candidateRank, ')
          ..write('canonicalBboxJson: $canonicalBboxJson, ')
          ..write('isCurrent: $isCurrent')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    resolutionId,
    sessionId,
    inferenceObjectId,
    productRevisionId,
    productId,
    recognitionSkuId,
    productName,
    unitPriceKrw,
    source,
    resolvedAtUs,
    candidateRank,
    canonicalBboxJson,
    isCurrent,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ObjectResolutionRow &&
          other.resolutionId == this.resolutionId &&
          other.sessionId == this.sessionId &&
          other.inferenceObjectId == this.inferenceObjectId &&
          other.productRevisionId == this.productRevisionId &&
          other.productId == this.productId &&
          other.recognitionSkuId == this.recognitionSkuId &&
          other.productName == this.productName &&
          other.unitPriceKrw == this.unitPriceKrw &&
          other.source == this.source &&
          other.resolvedAtUs == this.resolvedAtUs &&
          other.candidateRank == this.candidateRank &&
          other.canonicalBboxJson == this.canonicalBboxJson &&
          other.isCurrent == this.isCurrent);
}

class ObjectResolutionsCompanion extends UpdateCompanion<ObjectResolutionRow> {
  final Value<String> resolutionId;
  final Value<String> sessionId;
  final Value<String?> inferenceObjectId;
  final Value<String> productRevisionId;
  final Value<String> productId;
  final Value<int?> recognitionSkuId;
  final Value<String> productName;
  final Value<int> unitPriceKrw;
  final Value<String> source;
  final Value<int> resolvedAtUs;
  final Value<int?> candidateRank;
  final Value<String?> canonicalBboxJson;
  final Value<bool> isCurrent;
  final Value<int> rowid;
  const ObjectResolutionsCompanion({
    this.resolutionId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.inferenceObjectId = const Value.absent(),
    this.productRevisionId = const Value.absent(),
    this.productId = const Value.absent(),
    this.recognitionSkuId = const Value.absent(),
    this.productName = const Value.absent(),
    this.unitPriceKrw = const Value.absent(),
    this.source = const Value.absent(),
    this.resolvedAtUs = const Value.absent(),
    this.candidateRank = const Value.absent(),
    this.canonicalBboxJson = const Value.absent(),
    this.isCurrent = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ObjectResolutionsCompanion.insert({
    required String resolutionId,
    required String sessionId,
    this.inferenceObjectId = const Value.absent(),
    required String productRevisionId,
    required String productId,
    this.recognitionSkuId = const Value.absent(),
    required String productName,
    required int unitPriceKrw,
    required String source,
    required int resolvedAtUs,
    this.candidateRank = const Value.absent(),
    this.canonicalBboxJson = const Value.absent(),
    required bool isCurrent,
    this.rowid = const Value.absent(),
  }) : resolutionId = Value(resolutionId),
       sessionId = Value(sessionId),
       productRevisionId = Value(productRevisionId),
       productId = Value(productId),
       productName = Value(productName),
       unitPriceKrw = Value(unitPriceKrw),
       source = Value(source),
       resolvedAtUs = Value(resolvedAtUs),
       isCurrent = Value(isCurrent);
  static Insertable<ObjectResolutionRow> custom({
    Expression<String>? resolutionId,
    Expression<String>? sessionId,
    Expression<String>? inferenceObjectId,
    Expression<String>? productRevisionId,
    Expression<String>? productId,
    Expression<int>? recognitionSkuId,
    Expression<String>? productName,
    Expression<int>? unitPriceKrw,
    Expression<String>? source,
    Expression<int>? resolvedAtUs,
    Expression<int>? candidateRank,
    Expression<String>? canonicalBboxJson,
    Expression<bool>? isCurrent,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (resolutionId != null) 'resolution_id': resolutionId,
      if (sessionId != null) 'session_id': sessionId,
      if (inferenceObjectId != null) 'inference_object_id': inferenceObjectId,
      if (productRevisionId != null) 'product_revision_id': productRevisionId,
      if (productId != null) 'product_id': productId,
      if (recognitionSkuId != null) 'recognition_sku_id': recognitionSkuId,
      if (productName != null) 'product_name': productName,
      if (unitPriceKrw != null) 'unit_price_krw': unitPriceKrw,
      if (source != null) 'source': source,
      if (resolvedAtUs != null) 'resolved_at_us': resolvedAtUs,
      if (candidateRank != null) 'candidate_rank': candidateRank,
      if (canonicalBboxJson != null) 'canonical_bbox_json': canonicalBboxJson,
      if (isCurrent != null) 'is_current': isCurrent,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ObjectResolutionsCompanion copyWith({
    Value<String>? resolutionId,
    Value<String>? sessionId,
    Value<String?>? inferenceObjectId,
    Value<String>? productRevisionId,
    Value<String>? productId,
    Value<int?>? recognitionSkuId,
    Value<String>? productName,
    Value<int>? unitPriceKrw,
    Value<String>? source,
    Value<int>? resolvedAtUs,
    Value<int?>? candidateRank,
    Value<String?>? canonicalBboxJson,
    Value<bool>? isCurrent,
    Value<int>? rowid,
  }) {
    return ObjectResolutionsCompanion(
      resolutionId: resolutionId ?? this.resolutionId,
      sessionId: sessionId ?? this.sessionId,
      inferenceObjectId: inferenceObjectId ?? this.inferenceObjectId,
      productRevisionId: productRevisionId ?? this.productRevisionId,
      productId: productId ?? this.productId,
      recognitionSkuId: recognitionSkuId ?? this.recognitionSkuId,
      productName: productName ?? this.productName,
      unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
      source: source ?? this.source,
      resolvedAtUs: resolvedAtUs ?? this.resolvedAtUs,
      candidateRank: candidateRank ?? this.candidateRank,
      canonicalBboxJson: canonicalBboxJson ?? this.canonicalBboxJson,
      isCurrent: isCurrent ?? this.isCurrent,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (resolutionId.present) {
      map['resolution_id'] = Variable<String>(resolutionId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (inferenceObjectId.present) {
      map['inference_object_id'] = Variable<String>(inferenceObjectId.value);
    }
    if (productRevisionId.present) {
      map['product_revision_id'] = Variable<String>(productRevisionId.value);
    }
    if (productId.present) {
      map['product_id'] = Variable<String>(productId.value);
    }
    if (recognitionSkuId.present) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId.value);
    }
    if (productName.present) {
      map['product_name'] = Variable<String>(productName.value);
    }
    if (unitPriceKrw.present) {
      map['unit_price_krw'] = Variable<int>(unitPriceKrw.value);
    }
    if (source.present) {
      map['source'] = Variable<String>(source.value);
    }
    if (resolvedAtUs.present) {
      map['resolved_at_us'] = Variable<int>(resolvedAtUs.value);
    }
    if (candidateRank.present) {
      map['candidate_rank'] = Variable<int>(candidateRank.value);
    }
    if (canonicalBboxJson.present) {
      map['canonical_bbox_json'] = Variable<String>(canonicalBboxJson.value);
    }
    if (isCurrent.present) {
      map['is_current'] = Variable<bool>(isCurrent.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ObjectResolutionsCompanion(')
          ..write('resolutionId: $resolutionId, ')
          ..write('sessionId: $sessionId, ')
          ..write('inferenceObjectId: $inferenceObjectId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('productName: $productName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('source: $source, ')
          ..write('resolvedAtUs: $resolvedAtUs, ')
          ..write('candidateRank: $candidateRank, ')
          ..write('canonicalBboxJson: $canonicalBboxJson, ')
          ..write('isCurrent: $isCurrent, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $DraftOrderLinesTable extends DraftOrderLines
    with TableInfo<$DraftOrderLinesTable, DraftOrderLineRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $DraftOrderLinesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _draftLineIdMeta = const VerificationMeta(
    'draftLineId',
  );
  @override
  late final GeneratedColumn<String> draftLineId = GeneratedColumn<String>(
    'draft_line_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _productRevisionIdMeta = const VerificationMeta(
    'productRevisionId',
  );
  @override
  late final GeneratedColumn<String> productRevisionId =
      GeneratedColumn<String>(
        'product_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES products (product_revision_id)',
        ),
      );
  static const VerificationMeta _productIdMeta = const VerificationMeta(
    'productId',
  );
  @override
  late final GeneratedColumn<String> productId = GeneratedColumn<String>(
    'product_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _productNameMeta = const VerificationMeta(
    'productName',
  );
  @override
  late final GeneratedColumn<String> productName = GeneratedColumn<String>(
    'product_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _recognitionSkuIdMeta = const VerificationMeta(
    'recognitionSkuId',
  );
  @override
  late final GeneratedColumn<int> recognitionSkuId = GeneratedColumn<int>(
    'recognition_sku_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _unitPriceKrwMeta = const VerificationMeta(
    'unitPriceKrw',
  );
  @override
  late final GeneratedColumn<int> unitPriceKrw = GeneratedColumn<int>(
    'unit_price_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(unitPriceKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _quantityMeta = const VerificationMeta(
    'quantity',
  );
  @override
  late final GeneratedColumn<int> quantity = GeneratedColumn<int>(
    'quantity',
    aliasedName,
    false,
    check: () => ComparableExpr(quantity).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    draftLineId,
    sessionId,
    productRevisionId,
    productId,
    productName,
    recognitionSkuId,
    unitPriceKrw,
    quantity,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'draft_order_lines';
  @override
  VerificationContext validateIntegrity(
    Insertable<DraftOrderLineRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('draft_line_id')) {
      context.handle(
        _draftLineIdMeta,
        draftLineId.isAcceptableOrUnknown(
          data['draft_line_id']!,
          _draftLineIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_draftLineIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('product_revision_id')) {
      context.handle(
        _productRevisionIdMeta,
        productRevisionId.isAcceptableOrUnknown(
          data['product_revision_id']!,
          _productRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productRevisionIdMeta);
    }
    if (data.containsKey('product_id')) {
      context.handle(
        _productIdMeta,
        productId.isAcceptableOrUnknown(data['product_id']!, _productIdMeta),
      );
    } else if (isInserting) {
      context.missing(_productIdMeta);
    }
    if (data.containsKey('product_name')) {
      context.handle(
        _productNameMeta,
        productName.isAcceptableOrUnknown(
          data['product_name']!,
          _productNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productNameMeta);
    }
    if (data.containsKey('recognition_sku_id')) {
      context.handle(
        _recognitionSkuIdMeta,
        recognitionSkuId.isAcceptableOrUnknown(
          data['recognition_sku_id']!,
          _recognitionSkuIdMeta,
        ),
      );
    }
    if (data.containsKey('unit_price_krw')) {
      context.handle(
        _unitPriceKrwMeta,
        unitPriceKrw.isAcceptableOrUnknown(
          data['unit_price_krw']!,
          _unitPriceKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_unitPriceKrwMeta);
    }
    if (data.containsKey('quantity')) {
      context.handle(
        _quantityMeta,
        quantity.isAcceptableOrUnknown(data['quantity']!, _quantityMeta),
      );
    } else if (isInserting) {
      context.missing(_quantityMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {draftLineId};
  @override
  DraftOrderLineRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return DraftOrderLineRow(
      draftLineId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}draft_line_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      productRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_revision_id'],
      )!,
      productId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_id'],
      )!,
      productName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_name'],
      )!,
      recognitionSkuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recognition_sku_id'],
      ),
      unitPriceKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}unit_price_krw'],
      )!,
      quantity: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}quantity'],
      )!,
    );
  }

  @override
  $DraftOrderLinesTable createAlias(String alias) {
    return $DraftOrderLinesTable(attachedDatabase, alias);
  }
}

class DraftOrderLineRow extends DataClass
    implements Insertable<DraftOrderLineRow> {
  final String draftLineId;
  final String sessionId;
  final String productRevisionId;
  final String productId;
  final String productName;
  final int? recognitionSkuId;
  final int unitPriceKrw;
  final int quantity;
  const DraftOrderLineRow({
    required this.draftLineId,
    required this.sessionId,
    required this.productRevisionId,
    required this.productId,
    required this.productName,
    this.recognitionSkuId,
    required this.unitPriceKrw,
    required this.quantity,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['draft_line_id'] = Variable<String>(draftLineId);
    map['session_id'] = Variable<String>(sessionId);
    map['product_revision_id'] = Variable<String>(productRevisionId);
    map['product_id'] = Variable<String>(productId);
    map['product_name'] = Variable<String>(productName);
    if (!nullToAbsent || recognitionSkuId != null) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId);
    }
    map['unit_price_krw'] = Variable<int>(unitPriceKrw);
    map['quantity'] = Variable<int>(quantity);
    return map;
  }

  DraftOrderLinesCompanion toCompanion(bool nullToAbsent) {
    return DraftOrderLinesCompanion(
      draftLineId: Value(draftLineId),
      sessionId: Value(sessionId),
      productRevisionId: Value(productRevisionId),
      productId: Value(productId),
      productName: Value(productName),
      recognitionSkuId: recognitionSkuId == null && nullToAbsent
          ? const Value.absent()
          : Value(recognitionSkuId),
      unitPriceKrw: Value(unitPriceKrw),
      quantity: Value(quantity),
    );
  }

  factory DraftOrderLineRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return DraftOrderLineRow(
      draftLineId: serializer.fromJson<String>(json['draftLineId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      productRevisionId: serializer.fromJson<String>(json['productRevisionId']),
      productId: serializer.fromJson<String>(json['productId']),
      productName: serializer.fromJson<String>(json['productName']),
      recognitionSkuId: serializer.fromJson<int?>(json['recognitionSkuId']),
      unitPriceKrw: serializer.fromJson<int>(json['unitPriceKrw']),
      quantity: serializer.fromJson<int>(json['quantity']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'draftLineId': serializer.toJson<String>(draftLineId),
      'sessionId': serializer.toJson<String>(sessionId),
      'productRevisionId': serializer.toJson<String>(productRevisionId),
      'productId': serializer.toJson<String>(productId),
      'productName': serializer.toJson<String>(productName),
      'recognitionSkuId': serializer.toJson<int?>(recognitionSkuId),
      'unitPriceKrw': serializer.toJson<int>(unitPriceKrw),
      'quantity': serializer.toJson<int>(quantity),
    };
  }

  DraftOrderLineRow copyWith({
    String? draftLineId,
    String? sessionId,
    String? productRevisionId,
    String? productId,
    String? productName,
    Value<int?> recognitionSkuId = const Value.absent(),
    int? unitPriceKrw,
    int? quantity,
  }) => DraftOrderLineRow(
    draftLineId: draftLineId ?? this.draftLineId,
    sessionId: sessionId ?? this.sessionId,
    productRevisionId: productRevisionId ?? this.productRevisionId,
    productId: productId ?? this.productId,
    productName: productName ?? this.productName,
    recognitionSkuId: recognitionSkuId.present
        ? recognitionSkuId.value
        : this.recognitionSkuId,
    unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
    quantity: quantity ?? this.quantity,
  );
  DraftOrderLineRow copyWithCompanion(DraftOrderLinesCompanion data) {
    return DraftOrderLineRow(
      draftLineId: data.draftLineId.present
          ? data.draftLineId.value
          : this.draftLineId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      productRevisionId: data.productRevisionId.present
          ? data.productRevisionId.value
          : this.productRevisionId,
      productId: data.productId.present ? data.productId.value : this.productId,
      productName: data.productName.present
          ? data.productName.value
          : this.productName,
      recognitionSkuId: data.recognitionSkuId.present
          ? data.recognitionSkuId.value
          : this.recognitionSkuId,
      unitPriceKrw: data.unitPriceKrw.present
          ? data.unitPriceKrw.value
          : this.unitPriceKrw,
      quantity: data.quantity.present ? data.quantity.value : this.quantity,
    );
  }

  @override
  String toString() {
    return (StringBuffer('DraftOrderLineRow(')
          ..write('draftLineId: $draftLineId, ')
          ..write('sessionId: $sessionId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('productName: $productName, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('quantity: $quantity')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    draftLineId,
    sessionId,
    productRevisionId,
    productId,
    productName,
    recognitionSkuId,
    unitPriceKrw,
    quantity,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is DraftOrderLineRow &&
          other.draftLineId == this.draftLineId &&
          other.sessionId == this.sessionId &&
          other.productRevisionId == this.productRevisionId &&
          other.productId == this.productId &&
          other.productName == this.productName &&
          other.recognitionSkuId == this.recognitionSkuId &&
          other.unitPriceKrw == this.unitPriceKrw &&
          other.quantity == this.quantity);
}

class DraftOrderLinesCompanion extends UpdateCompanion<DraftOrderLineRow> {
  final Value<String> draftLineId;
  final Value<String> sessionId;
  final Value<String> productRevisionId;
  final Value<String> productId;
  final Value<String> productName;
  final Value<int?> recognitionSkuId;
  final Value<int> unitPriceKrw;
  final Value<int> quantity;
  final Value<int> rowid;
  const DraftOrderLinesCompanion({
    this.draftLineId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.productRevisionId = const Value.absent(),
    this.productId = const Value.absent(),
    this.productName = const Value.absent(),
    this.recognitionSkuId = const Value.absent(),
    this.unitPriceKrw = const Value.absent(),
    this.quantity = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  DraftOrderLinesCompanion.insert({
    required String draftLineId,
    required String sessionId,
    required String productRevisionId,
    required String productId,
    required String productName,
    this.recognitionSkuId = const Value.absent(),
    required int unitPriceKrw,
    required int quantity,
    this.rowid = const Value.absent(),
  }) : draftLineId = Value(draftLineId),
       sessionId = Value(sessionId),
       productRevisionId = Value(productRevisionId),
       productId = Value(productId),
       productName = Value(productName),
       unitPriceKrw = Value(unitPriceKrw),
       quantity = Value(quantity);
  static Insertable<DraftOrderLineRow> custom({
    Expression<String>? draftLineId,
    Expression<String>? sessionId,
    Expression<String>? productRevisionId,
    Expression<String>? productId,
    Expression<String>? productName,
    Expression<int>? recognitionSkuId,
    Expression<int>? unitPriceKrw,
    Expression<int>? quantity,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (draftLineId != null) 'draft_line_id': draftLineId,
      if (sessionId != null) 'session_id': sessionId,
      if (productRevisionId != null) 'product_revision_id': productRevisionId,
      if (productId != null) 'product_id': productId,
      if (productName != null) 'product_name': productName,
      if (recognitionSkuId != null) 'recognition_sku_id': recognitionSkuId,
      if (unitPriceKrw != null) 'unit_price_krw': unitPriceKrw,
      if (quantity != null) 'quantity': quantity,
      if (rowid != null) 'rowid': rowid,
    });
  }

  DraftOrderLinesCompanion copyWith({
    Value<String>? draftLineId,
    Value<String>? sessionId,
    Value<String>? productRevisionId,
    Value<String>? productId,
    Value<String>? productName,
    Value<int?>? recognitionSkuId,
    Value<int>? unitPriceKrw,
    Value<int>? quantity,
    Value<int>? rowid,
  }) {
    return DraftOrderLinesCompanion(
      draftLineId: draftLineId ?? this.draftLineId,
      sessionId: sessionId ?? this.sessionId,
      productRevisionId: productRevisionId ?? this.productRevisionId,
      productId: productId ?? this.productId,
      productName: productName ?? this.productName,
      recognitionSkuId: recognitionSkuId ?? this.recognitionSkuId,
      unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
      quantity: quantity ?? this.quantity,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (draftLineId.present) {
      map['draft_line_id'] = Variable<String>(draftLineId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (productRevisionId.present) {
      map['product_revision_id'] = Variable<String>(productRevisionId.value);
    }
    if (productId.present) {
      map['product_id'] = Variable<String>(productId.value);
    }
    if (productName.present) {
      map['product_name'] = Variable<String>(productName.value);
    }
    if (recognitionSkuId.present) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId.value);
    }
    if (unitPriceKrw.present) {
      map['unit_price_krw'] = Variable<int>(unitPriceKrw.value);
    }
    if (quantity.present) {
      map['quantity'] = Variable<int>(quantity.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('DraftOrderLinesCompanion(')
          ..write('draftLineId: $draftLineId, ')
          ..write('sessionId: $sessionId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('productName: $productName, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('quantity: $quantity, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $FinalOrdersTable extends FinalOrders
    with TableInfo<$FinalOrdersTable, FinalOrderRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $FinalOrdersTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _orderIdMeta = const VerificationMeta(
    'orderId',
  );
  @override
  late final GeneratedColumn<String> orderId = GeneratedColumn<String>(
    'order_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _catalogRevisionIdMeta = const VerificationMeta(
    'catalogRevisionId',
  );
  @override
  late final GeneratedColumn<String> catalogRevisionId =
      GeneratedColumn<String>(
        'catalog_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES catalog_revisions (revision_id)',
        ),
      );
  static const VerificationMeta _createdAtUsMeta = const VerificationMeta(
    'createdAtUs',
  );
  @override
  late final GeneratedColumn<int> createdAtUs = GeneratedColumn<int>(
    'created_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _totalQuantityMeta = const VerificationMeta(
    'totalQuantity',
  );
  @override
  late final GeneratedColumn<int> totalQuantity = GeneratedColumn<int>(
    'total_quantity',
    aliasedName,
    false,
    check: () => ComparableExpr(totalQuantity).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _totalAmountKrwMeta = const VerificationMeta(
    'totalAmountKrw',
  );
  @override
  late final GeneratedColumn<int> totalAmountKrw = GeneratedColumn<int>(
    'total_amount_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(totalAmountKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _receiptRelativePathMeta =
      const VerificationMeta('receiptRelativePath');
  @override
  late final GeneratedColumn<String> receiptRelativePath =
      GeneratedColumn<String>(
        'receipt_relative_path',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _receiptByteSizeMeta = const VerificationMeta(
    'receiptByteSize',
  );
  @override
  late final GeneratedColumn<int> receiptByteSize = GeneratedColumn<int>(
    'receipt_byte_size',
    aliasedName,
    false,
    check: () => ComparableExpr(receiptByteSize).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _receiptSha256Meta = const VerificationMeta(
    'receiptSha256',
  );
  @override
  late final GeneratedColumn<String> receiptSha256 = GeneratedColumn<String>(
    'receipt_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    orderId,
    sessionId,
    catalogRevisionId,
    createdAtUs,
    totalQuantity,
    totalAmountKrw,
    receiptRelativePath,
    receiptByteSize,
    receiptSha256,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'final_orders';
  @override
  VerificationContext validateIntegrity(
    Insertable<FinalOrderRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('order_id')) {
      context.handle(
        _orderIdMeta,
        orderId.isAcceptableOrUnknown(data['order_id']!, _orderIdMeta),
      );
    } else if (isInserting) {
      context.missing(_orderIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('catalog_revision_id')) {
      context.handle(
        _catalogRevisionIdMeta,
        catalogRevisionId.isAcceptableOrUnknown(
          data['catalog_revision_id']!,
          _catalogRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_catalogRevisionIdMeta);
    }
    if (data.containsKey('created_at_us')) {
      context.handle(
        _createdAtUsMeta,
        createdAtUs.isAcceptableOrUnknown(
          data['created_at_us']!,
          _createdAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_createdAtUsMeta);
    }
    if (data.containsKey('total_quantity')) {
      context.handle(
        _totalQuantityMeta,
        totalQuantity.isAcceptableOrUnknown(
          data['total_quantity']!,
          _totalQuantityMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_totalQuantityMeta);
    }
    if (data.containsKey('total_amount_krw')) {
      context.handle(
        _totalAmountKrwMeta,
        totalAmountKrw.isAcceptableOrUnknown(
          data['total_amount_krw']!,
          _totalAmountKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_totalAmountKrwMeta);
    }
    if (data.containsKey('receipt_relative_path')) {
      context.handle(
        _receiptRelativePathMeta,
        receiptRelativePath.isAcceptableOrUnknown(
          data['receipt_relative_path']!,
          _receiptRelativePathMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_receiptRelativePathMeta);
    }
    if (data.containsKey('receipt_byte_size')) {
      context.handle(
        _receiptByteSizeMeta,
        receiptByteSize.isAcceptableOrUnknown(
          data['receipt_byte_size']!,
          _receiptByteSizeMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_receiptByteSizeMeta);
    }
    if (data.containsKey('receipt_sha256')) {
      context.handle(
        _receiptSha256Meta,
        receiptSha256.isAcceptableOrUnknown(
          data['receipt_sha256']!,
          _receiptSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_receiptSha256Meta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {orderId};
  @override
  FinalOrderRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return FinalOrderRow(
      orderId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}order_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      catalogRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}catalog_revision_id'],
      )!,
      createdAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at_us'],
      )!,
      totalQuantity: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}total_quantity'],
      )!,
      totalAmountKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}total_amount_krw'],
      )!,
      receiptRelativePath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}receipt_relative_path'],
      )!,
      receiptByteSize: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}receipt_byte_size'],
      )!,
      receiptSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}receipt_sha256'],
      )!,
    );
  }

  @override
  $FinalOrdersTable createAlias(String alias) {
    return $FinalOrdersTable(attachedDatabase, alias);
  }
}

class FinalOrderRow extends DataClass implements Insertable<FinalOrderRow> {
  final String orderId;
  final String sessionId;
  final String catalogRevisionId;
  final int createdAtUs;
  final int totalQuantity;
  final int totalAmountKrw;
  final String receiptRelativePath;
  final int receiptByteSize;
  final String receiptSha256;
  const FinalOrderRow({
    required this.orderId,
    required this.sessionId,
    required this.catalogRevisionId,
    required this.createdAtUs,
    required this.totalQuantity,
    required this.totalAmountKrw,
    required this.receiptRelativePath,
    required this.receiptByteSize,
    required this.receiptSha256,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['order_id'] = Variable<String>(orderId);
    map['session_id'] = Variable<String>(sessionId);
    map['catalog_revision_id'] = Variable<String>(catalogRevisionId);
    map['created_at_us'] = Variable<int>(createdAtUs);
    map['total_quantity'] = Variable<int>(totalQuantity);
    map['total_amount_krw'] = Variable<int>(totalAmountKrw);
    map['receipt_relative_path'] = Variable<String>(receiptRelativePath);
    map['receipt_byte_size'] = Variable<int>(receiptByteSize);
    map['receipt_sha256'] = Variable<String>(receiptSha256);
    return map;
  }

  FinalOrdersCompanion toCompanion(bool nullToAbsent) {
    return FinalOrdersCompanion(
      orderId: Value(orderId),
      sessionId: Value(sessionId),
      catalogRevisionId: Value(catalogRevisionId),
      createdAtUs: Value(createdAtUs),
      totalQuantity: Value(totalQuantity),
      totalAmountKrw: Value(totalAmountKrw),
      receiptRelativePath: Value(receiptRelativePath),
      receiptByteSize: Value(receiptByteSize),
      receiptSha256: Value(receiptSha256),
    );
  }

  factory FinalOrderRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return FinalOrderRow(
      orderId: serializer.fromJson<String>(json['orderId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      catalogRevisionId: serializer.fromJson<String>(json['catalogRevisionId']),
      createdAtUs: serializer.fromJson<int>(json['createdAtUs']),
      totalQuantity: serializer.fromJson<int>(json['totalQuantity']),
      totalAmountKrw: serializer.fromJson<int>(json['totalAmountKrw']),
      receiptRelativePath: serializer.fromJson<String>(
        json['receiptRelativePath'],
      ),
      receiptByteSize: serializer.fromJson<int>(json['receiptByteSize']),
      receiptSha256: serializer.fromJson<String>(json['receiptSha256']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'orderId': serializer.toJson<String>(orderId),
      'sessionId': serializer.toJson<String>(sessionId),
      'catalogRevisionId': serializer.toJson<String>(catalogRevisionId),
      'createdAtUs': serializer.toJson<int>(createdAtUs),
      'totalQuantity': serializer.toJson<int>(totalQuantity),
      'totalAmountKrw': serializer.toJson<int>(totalAmountKrw),
      'receiptRelativePath': serializer.toJson<String>(receiptRelativePath),
      'receiptByteSize': serializer.toJson<int>(receiptByteSize),
      'receiptSha256': serializer.toJson<String>(receiptSha256),
    };
  }

  FinalOrderRow copyWith({
    String? orderId,
    String? sessionId,
    String? catalogRevisionId,
    int? createdAtUs,
    int? totalQuantity,
    int? totalAmountKrw,
    String? receiptRelativePath,
    int? receiptByteSize,
    String? receiptSha256,
  }) => FinalOrderRow(
    orderId: orderId ?? this.orderId,
    sessionId: sessionId ?? this.sessionId,
    catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
    createdAtUs: createdAtUs ?? this.createdAtUs,
    totalQuantity: totalQuantity ?? this.totalQuantity,
    totalAmountKrw: totalAmountKrw ?? this.totalAmountKrw,
    receiptRelativePath: receiptRelativePath ?? this.receiptRelativePath,
    receiptByteSize: receiptByteSize ?? this.receiptByteSize,
    receiptSha256: receiptSha256 ?? this.receiptSha256,
  );
  FinalOrderRow copyWithCompanion(FinalOrdersCompanion data) {
    return FinalOrderRow(
      orderId: data.orderId.present ? data.orderId.value : this.orderId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      catalogRevisionId: data.catalogRevisionId.present
          ? data.catalogRevisionId.value
          : this.catalogRevisionId,
      createdAtUs: data.createdAtUs.present
          ? data.createdAtUs.value
          : this.createdAtUs,
      totalQuantity: data.totalQuantity.present
          ? data.totalQuantity.value
          : this.totalQuantity,
      totalAmountKrw: data.totalAmountKrw.present
          ? data.totalAmountKrw.value
          : this.totalAmountKrw,
      receiptRelativePath: data.receiptRelativePath.present
          ? data.receiptRelativePath.value
          : this.receiptRelativePath,
      receiptByteSize: data.receiptByteSize.present
          ? data.receiptByteSize.value
          : this.receiptByteSize,
      receiptSha256: data.receiptSha256.present
          ? data.receiptSha256.value
          : this.receiptSha256,
    );
  }

  @override
  String toString() {
    return (StringBuffer('FinalOrderRow(')
          ..write('orderId: $orderId, ')
          ..write('sessionId: $sessionId, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('totalQuantity: $totalQuantity, ')
          ..write('totalAmountKrw: $totalAmountKrw, ')
          ..write('receiptRelativePath: $receiptRelativePath, ')
          ..write('receiptByteSize: $receiptByteSize, ')
          ..write('receiptSha256: $receiptSha256')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    orderId,
    sessionId,
    catalogRevisionId,
    createdAtUs,
    totalQuantity,
    totalAmountKrw,
    receiptRelativePath,
    receiptByteSize,
    receiptSha256,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is FinalOrderRow &&
          other.orderId == this.orderId &&
          other.sessionId == this.sessionId &&
          other.catalogRevisionId == this.catalogRevisionId &&
          other.createdAtUs == this.createdAtUs &&
          other.totalQuantity == this.totalQuantity &&
          other.totalAmountKrw == this.totalAmountKrw &&
          other.receiptRelativePath == this.receiptRelativePath &&
          other.receiptByteSize == this.receiptByteSize &&
          other.receiptSha256 == this.receiptSha256);
}

class FinalOrdersCompanion extends UpdateCompanion<FinalOrderRow> {
  final Value<String> orderId;
  final Value<String> sessionId;
  final Value<String> catalogRevisionId;
  final Value<int> createdAtUs;
  final Value<int> totalQuantity;
  final Value<int> totalAmountKrw;
  final Value<String> receiptRelativePath;
  final Value<int> receiptByteSize;
  final Value<String> receiptSha256;
  final Value<int> rowid;
  const FinalOrdersCompanion({
    this.orderId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.catalogRevisionId = const Value.absent(),
    this.createdAtUs = const Value.absent(),
    this.totalQuantity = const Value.absent(),
    this.totalAmountKrw = const Value.absent(),
    this.receiptRelativePath = const Value.absent(),
    this.receiptByteSize = const Value.absent(),
    this.receiptSha256 = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  FinalOrdersCompanion.insert({
    required String orderId,
    required String sessionId,
    required String catalogRevisionId,
    required int createdAtUs,
    required int totalQuantity,
    required int totalAmountKrw,
    required String receiptRelativePath,
    required int receiptByteSize,
    required String receiptSha256,
    this.rowid = const Value.absent(),
  }) : orderId = Value(orderId),
       sessionId = Value(sessionId),
       catalogRevisionId = Value(catalogRevisionId),
       createdAtUs = Value(createdAtUs),
       totalQuantity = Value(totalQuantity),
       totalAmountKrw = Value(totalAmountKrw),
       receiptRelativePath = Value(receiptRelativePath),
       receiptByteSize = Value(receiptByteSize),
       receiptSha256 = Value(receiptSha256);
  static Insertable<FinalOrderRow> custom({
    Expression<String>? orderId,
    Expression<String>? sessionId,
    Expression<String>? catalogRevisionId,
    Expression<int>? createdAtUs,
    Expression<int>? totalQuantity,
    Expression<int>? totalAmountKrw,
    Expression<String>? receiptRelativePath,
    Expression<int>? receiptByteSize,
    Expression<String>? receiptSha256,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (orderId != null) 'order_id': orderId,
      if (sessionId != null) 'session_id': sessionId,
      if (catalogRevisionId != null) 'catalog_revision_id': catalogRevisionId,
      if (createdAtUs != null) 'created_at_us': createdAtUs,
      if (totalQuantity != null) 'total_quantity': totalQuantity,
      if (totalAmountKrw != null) 'total_amount_krw': totalAmountKrw,
      if (receiptRelativePath != null)
        'receipt_relative_path': receiptRelativePath,
      if (receiptByteSize != null) 'receipt_byte_size': receiptByteSize,
      if (receiptSha256 != null) 'receipt_sha256': receiptSha256,
      if (rowid != null) 'rowid': rowid,
    });
  }

  FinalOrdersCompanion copyWith({
    Value<String>? orderId,
    Value<String>? sessionId,
    Value<String>? catalogRevisionId,
    Value<int>? createdAtUs,
    Value<int>? totalQuantity,
    Value<int>? totalAmountKrw,
    Value<String>? receiptRelativePath,
    Value<int>? receiptByteSize,
    Value<String>? receiptSha256,
    Value<int>? rowid,
  }) {
    return FinalOrdersCompanion(
      orderId: orderId ?? this.orderId,
      sessionId: sessionId ?? this.sessionId,
      catalogRevisionId: catalogRevisionId ?? this.catalogRevisionId,
      createdAtUs: createdAtUs ?? this.createdAtUs,
      totalQuantity: totalQuantity ?? this.totalQuantity,
      totalAmountKrw: totalAmountKrw ?? this.totalAmountKrw,
      receiptRelativePath: receiptRelativePath ?? this.receiptRelativePath,
      receiptByteSize: receiptByteSize ?? this.receiptByteSize,
      receiptSha256: receiptSha256 ?? this.receiptSha256,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (orderId.present) {
      map['order_id'] = Variable<String>(orderId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (catalogRevisionId.present) {
      map['catalog_revision_id'] = Variable<String>(catalogRevisionId.value);
    }
    if (createdAtUs.present) {
      map['created_at_us'] = Variable<int>(createdAtUs.value);
    }
    if (totalQuantity.present) {
      map['total_quantity'] = Variable<int>(totalQuantity.value);
    }
    if (totalAmountKrw.present) {
      map['total_amount_krw'] = Variable<int>(totalAmountKrw.value);
    }
    if (receiptRelativePath.present) {
      map['receipt_relative_path'] = Variable<String>(
        receiptRelativePath.value,
      );
    }
    if (receiptByteSize.present) {
      map['receipt_byte_size'] = Variable<int>(receiptByteSize.value);
    }
    if (receiptSha256.present) {
      map['receipt_sha256'] = Variable<String>(receiptSha256.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('FinalOrdersCompanion(')
          ..write('orderId: $orderId, ')
          ..write('sessionId: $sessionId, ')
          ..write('catalogRevisionId: $catalogRevisionId, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('totalQuantity: $totalQuantity, ')
          ..write('totalAmountKrw: $totalAmountKrw, ')
          ..write('receiptRelativePath: $receiptRelativePath, ')
          ..write('receiptByteSize: $receiptByteSize, ')
          ..write('receiptSha256: $receiptSha256, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $FinalOrderLinesTable extends FinalOrderLines
    with TableInfo<$FinalOrderLinesTable, FinalOrderLineRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $FinalOrderLinesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _finalLineIdMeta = const VerificationMeta(
    'finalLineId',
  );
  @override
  late final GeneratedColumn<String> finalLineId = GeneratedColumn<String>(
    'final_line_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _orderIdMeta = const VerificationMeta(
    'orderId',
  );
  @override
  late final GeneratedColumn<String> orderId = GeneratedColumn<String>(
    'order_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES final_orders (order_id)',
    ),
  );
  static const VerificationMeta _productRevisionIdMeta = const VerificationMeta(
    'productRevisionId',
  );
  @override
  late final GeneratedColumn<String> productRevisionId =
      GeneratedColumn<String>(
        'product_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES products (product_revision_id)',
        ),
      );
  static const VerificationMeta _productIdMeta = const VerificationMeta(
    'productId',
  );
  @override
  late final GeneratedColumn<String> productId = GeneratedColumn<String>(
    'product_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _recognitionSkuIdMeta = const VerificationMeta(
    'recognitionSkuId',
  );
  @override
  late final GeneratedColumn<int> recognitionSkuId = GeneratedColumn<int>(
    'recognition_sku_id',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _productNameMeta = const VerificationMeta(
    'productName',
  );
  @override
  late final GeneratedColumn<String> productName = GeneratedColumn<String>(
    'product_name',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _unitPriceKrwMeta = const VerificationMeta(
    'unitPriceKrw',
  );
  @override
  late final GeneratedColumn<int> unitPriceKrw = GeneratedColumn<int>(
    'unit_price_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(unitPriceKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _quantityMeta = const VerificationMeta(
    'quantity',
  );
  @override
  late final GeneratedColumn<int> quantity = GeneratedColumn<int>(
    'quantity',
    aliasedName,
    false,
    check: () => ComparableExpr(quantity).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _lineAmountKrwMeta = const VerificationMeta(
    'lineAmountKrw',
  );
  @override
  late final GeneratedColumn<int> lineAmountKrw = GeneratedColumn<int>(
    'line_amount_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(lineAmountKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _resolutionSourceMeta = const VerificationMeta(
    'resolutionSource',
  );
  @override
  late final GeneratedColumn<String> resolutionSource = GeneratedColumn<String>(
    'resolution_source',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    finalLineId,
    orderId,
    productRevisionId,
    productId,
    recognitionSkuId,
    productName,
    unitPriceKrw,
    quantity,
    lineAmountKrw,
    resolutionSource,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'final_order_lines';
  @override
  VerificationContext validateIntegrity(
    Insertable<FinalOrderLineRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('final_line_id')) {
      context.handle(
        _finalLineIdMeta,
        finalLineId.isAcceptableOrUnknown(
          data['final_line_id']!,
          _finalLineIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_finalLineIdMeta);
    }
    if (data.containsKey('order_id')) {
      context.handle(
        _orderIdMeta,
        orderId.isAcceptableOrUnknown(data['order_id']!, _orderIdMeta),
      );
    } else if (isInserting) {
      context.missing(_orderIdMeta);
    }
    if (data.containsKey('product_revision_id')) {
      context.handle(
        _productRevisionIdMeta,
        productRevisionId.isAcceptableOrUnknown(
          data['product_revision_id']!,
          _productRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productRevisionIdMeta);
    }
    if (data.containsKey('product_id')) {
      context.handle(
        _productIdMeta,
        productId.isAcceptableOrUnknown(data['product_id']!, _productIdMeta),
      );
    } else if (isInserting) {
      context.missing(_productIdMeta);
    }
    if (data.containsKey('recognition_sku_id')) {
      context.handle(
        _recognitionSkuIdMeta,
        recognitionSkuId.isAcceptableOrUnknown(
          data['recognition_sku_id']!,
          _recognitionSkuIdMeta,
        ),
      );
    }
    if (data.containsKey('product_name')) {
      context.handle(
        _productNameMeta,
        productName.isAcceptableOrUnknown(
          data['product_name']!,
          _productNameMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_productNameMeta);
    }
    if (data.containsKey('unit_price_krw')) {
      context.handle(
        _unitPriceKrwMeta,
        unitPriceKrw.isAcceptableOrUnknown(
          data['unit_price_krw']!,
          _unitPriceKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_unitPriceKrwMeta);
    }
    if (data.containsKey('quantity')) {
      context.handle(
        _quantityMeta,
        quantity.isAcceptableOrUnknown(data['quantity']!, _quantityMeta),
      );
    } else if (isInserting) {
      context.missing(_quantityMeta);
    }
    if (data.containsKey('line_amount_krw')) {
      context.handle(
        _lineAmountKrwMeta,
        lineAmountKrw.isAcceptableOrUnknown(
          data['line_amount_krw']!,
          _lineAmountKrwMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_lineAmountKrwMeta);
    }
    if (data.containsKey('resolution_source')) {
      context.handle(
        _resolutionSourceMeta,
        resolutionSource.isAcceptableOrUnknown(
          data['resolution_source']!,
          _resolutionSourceMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_resolutionSourceMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {finalLineId};
  @override
  FinalOrderLineRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return FinalOrderLineRow(
      finalLineId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}final_line_id'],
      )!,
      orderId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}order_id'],
      )!,
      productRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_revision_id'],
      )!,
      productId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_id'],
      )!,
      recognitionSkuId: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}recognition_sku_id'],
      ),
      productName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}product_name'],
      )!,
      unitPriceKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}unit_price_krw'],
      )!,
      quantity: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}quantity'],
      )!,
      lineAmountKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}line_amount_krw'],
      )!,
      resolutionSource: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}resolution_source'],
      )!,
    );
  }

  @override
  $FinalOrderLinesTable createAlias(String alias) {
    return $FinalOrderLinesTable(attachedDatabase, alias);
  }
}

class FinalOrderLineRow extends DataClass
    implements Insertable<FinalOrderLineRow> {
  final String finalLineId;
  final String orderId;
  final String productRevisionId;
  final String productId;
  final int? recognitionSkuId;
  final String productName;
  final int unitPriceKrw;
  final int quantity;
  final int lineAmountKrw;
  final String resolutionSource;
  const FinalOrderLineRow({
    required this.finalLineId,
    required this.orderId,
    required this.productRevisionId,
    required this.productId,
    this.recognitionSkuId,
    required this.productName,
    required this.unitPriceKrw,
    required this.quantity,
    required this.lineAmountKrw,
    required this.resolutionSource,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['final_line_id'] = Variable<String>(finalLineId);
    map['order_id'] = Variable<String>(orderId);
    map['product_revision_id'] = Variable<String>(productRevisionId);
    map['product_id'] = Variable<String>(productId);
    if (!nullToAbsent || recognitionSkuId != null) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId);
    }
    map['product_name'] = Variable<String>(productName);
    map['unit_price_krw'] = Variable<int>(unitPriceKrw);
    map['quantity'] = Variable<int>(quantity);
    map['line_amount_krw'] = Variable<int>(lineAmountKrw);
    map['resolution_source'] = Variable<String>(resolutionSource);
    return map;
  }

  FinalOrderLinesCompanion toCompanion(bool nullToAbsent) {
    return FinalOrderLinesCompanion(
      finalLineId: Value(finalLineId),
      orderId: Value(orderId),
      productRevisionId: Value(productRevisionId),
      productId: Value(productId),
      recognitionSkuId: recognitionSkuId == null && nullToAbsent
          ? const Value.absent()
          : Value(recognitionSkuId),
      productName: Value(productName),
      unitPriceKrw: Value(unitPriceKrw),
      quantity: Value(quantity),
      lineAmountKrw: Value(lineAmountKrw),
      resolutionSource: Value(resolutionSource),
    );
  }

  factory FinalOrderLineRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return FinalOrderLineRow(
      finalLineId: serializer.fromJson<String>(json['finalLineId']),
      orderId: serializer.fromJson<String>(json['orderId']),
      productRevisionId: serializer.fromJson<String>(json['productRevisionId']),
      productId: serializer.fromJson<String>(json['productId']),
      recognitionSkuId: serializer.fromJson<int?>(json['recognitionSkuId']),
      productName: serializer.fromJson<String>(json['productName']),
      unitPriceKrw: serializer.fromJson<int>(json['unitPriceKrw']),
      quantity: serializer.fromJson<int>(json['quantity']),
      lineAmountKrw: serializer.fromJson<int>(json['lineAmountKrw']),
      resolutionSource: serializer.fromJson<String>(json['resolutionSource']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'finalLineId': serializer.toJson<String>(finalLineId),
      'orderId': serializer.toJson<String>(orderId),
      'productRevisionId': serializer.toJson<String>(productRevisionId),
      'productId': serializer.toJson<String>(productId),
      'recognitionSkuId': serializer.toJson<int?>(recognitionSkuId),
      'productName': serializer.toJson<String>(productName),
      'unitPriceKrw': serializer.toJson<int>(unitPriceKrw),
      'quantity': serializer.toJson<int>(quantity),
      'lineAmountKrw': serializer.toJson<int>(lineAmountKrw),
      'resolutionSource': serializer.toJson<String>(resolutionSource),
    };
  }

  FinalOrderLineRow copyWith({
    String? finalLineId,
    String? orderId,
    String? productRevisionId,
    String? productId,
    Value<int?> recognitionSkuId = const Value.absent(),
    String? productName,
    int? unitPriceKrw,
    int? quantity,
    int? lineAmountKrw,
    String? resolutionSource,
  }) => FinalOrderLineRow(
    finalLineId: finalLineId ?? this.finalLineId,
    orderId: orderId ?? this.orderId,
    productRevisionId: productRevisionId ?? this.productRevisionId,
    productId: productId ?? this.productId,
    recognitionSkuId: recognitionSkuId.present
        ? recognitionSkuId.value
        : this.recognitionSkuId,
    productName: productName ?? this.productName,
    unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
    quantity: quantity ?? this.quantity,
    lineAmountKrw: lineAmountKrw ?? this.lineAmountKrw,
    resolutionSource: resolutionSource ?? this.resolutionSource,
  );
  FinalOrderLineRow copyWithCompanion(FinalOrderLinesCompanion data) {
    return FinalOrderLineRow(
      finalLineId: data.finalLineId.present
          ? data.finalLineId.value
          : this.finalLineId,
      orderId: data.orderId.present ? data.orderId.value : this.orderId,
      productRevisionId: data.productRevisionId.present
          ? data.productRevisionId.value
          : this.productRevisionId,
      productId: data.productId.present ? data.productId.value : this.productId,
      recognitionSkuId: data.recognitionSkuId.present
          ? data.recognitionSkuId.value
          : this.recognitionSkuId,
      productName: data.productName.present
          ? data.productName.value
          : this.productName,
      unitPriceKrw: data.unitPriceKrw.present
          ? data.unitPriceKrw.value
          : this.unitPriceKrw,
      quantity: data.quantity.present ? data.quantity.value : this.quantity,
      lineAmountKrw: data.lineAmountKrw.present
          ? data.lineAmountKrw.value
          : this.lineAmountKrw,
      resolutionSource: data.resolutionSource.present
          ? data.resolutionSource.value
          : this.resolutionSource,
    );
  }

  @override
  String toString() {
    return (StringBuffer('FinalOrderLineRow(')
          ..write('finalLineId: $finalLineId, ')
          ..write('orderId: $orderId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('productName: $productName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('quantity: $quantity, ')
          ..write('lineAmountKrw: $lineAmountKrw, ')
          ..write('resolutionSource: $resolutionSource')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    finalLineId,
    orderId,
    productRevisionId,
    productId,
    recognitionSkuId,
    productName,
    unitPriceKrw,
    quantity,
    lineAmountKrw,
    resolutionSource,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is FinalOrderLineRow &&
          other.finalLineId == this.finalLineId &&
          other.orderId == this.orderId &&
          other.productRevisionId == this.productRevisionId &&
          other.productId == this.productId &&
          other.recognitionSkuId == this.recognitionSkuId &&
          other.productName == this.productName &&
          other.unitPriceKrw == this.unitPriceKrw &&
          other.quantity == this.quantity &&
          other.lineAmountKrw == this.lineAmountKrw &&
          other.resolutionSource == this.resolutionSource);
}

class FinalOrderLinesCompanion extends UpdateCompanion<FinalOrderLineRow> {
  final Value<String> finalLineId;
  final Value<String> orderId;
  final Value<String> productRevisionId;
  final Value<String> productId;
  final Value<int?> recognitionSkuId;
  final Value<String> productName;
  final Value<int> unitPriceKrw;
  final Value<int> quantity;
  final Value<int> lineAmountKrw;
  final Value<String> resolutionSource;
  final Value<int> rowid;
  const FinalOrderLinesCompanion({
    this.finalLineId = const Value.absent(),
    this.orderId = const Value.absent(),
    this.productRevisionId = const Value.absent(),
    this.productId = const Value.absent(),
    this.recognitionSkuId = const Value.absent(),
    this.productName = const Value.absent(),
    this.unitPriceKrw = const Value.absent(),
    this.quantity = const Value.absent(),
    this.lineAmountKrw = const Value.absent(),
    this.resolutionSource = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  FinalOrderLinesCompanion.insert({
    required String finalLineId,
    required String orderId,
    required String productRevisionId,
    required String productId,
    this.recognitionSkuId = const Value.absent(),
    required String productName,
    required int unitPriceKrw,
    required int quantity,
    required int lineAmountKrw,
    required String resolutionSource,
    this.rowid = const Value.absent(),
  }) : finalLineId = Value(finalLineId),
       orderId = Value(orderId),
       productRevisionId = Value(productRevisionId),
       productId = Value(productId),
       productName = Value(productName),
       unitPriceKrw = Value(unitPriceKrw),
       quantity = Value(quantity),
       lineAmountKrw = Value(lineAmountKrw),
       resolutionSource = Value(resolutionSource);
  static Insertable<FinalOrderLineRow> custom({
    Expression<String>? finalLineId,
    Expression<String>? orderId,
    Expression<String>? productRevisionId,
    Expression<String>? productId,
    Expression<int>? recognitionSkuId,
    Expression<String>? productName,
    Expression<int>? unitPriceKrw,
    Expression<int>? quantity,
    Expression<int>? lineAmountKrw,
    Expression<String>? resolutionSource,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (finalLineId != null) 'final_line_id': finalLineId,
      if (orderId != null) 'order_id': orderId,
      if (productRevisionId != null) 'product_revision_id': productRevisionId,
      if (productId != null) 'product_id': productId,
      if (recognitionSkuId != null) 'recognition_sku_id': recognitionSkuId,
      if (productName != null) 'product_name': productName,
      if (unitPriceKrw != null) 'unit_price_krw': unitPriceKrw,
      if (quantity != null) 'quantity': quantity,
      if (lineAmountKrw != null) 'line_amount_krw': lineAmountKrw,
      if (resolutionSource != null) 'resolution_source': resolutionSource,
      if (rowid != null) 'rowid': rowid,
    });
  }

  FinalOrderLinesCompanion copyWith({
    Value<String>? finalLineId,
    Value<String>? orderId,
    Value<String>? productRevisionId,
    Value<String>? productId,
    Value<int?>? recognitionSkuId,
    Value<String>? productName,
    Value<int>? unitPriceKrw,
    Value<int>? quantity,
    Value<int>? lineAmountKrw,
    Value<String>? resolutionSource,
    Value<int>? rowid,
  }) {
    return FinalOrderLinesCompanion(
      finalLineId: finalLineId ?? this.finalLineId,
      orderId: orderId ?? this.orderId,
      productRevisionId: productRevisionId ?? this.productRevisionId,
      productId: productId ?? this.productId,
      recognitionSkuId: recognitionSkuId ?? this.recognitionSkuId,
      productName: productName ?? this.productName,
      unitPriceKrw: unitPriceKrw ?? this.unitPriceKrw,
      quantity: quantity ?? this.quantity,
      lineAmountKrw: lineAmountKrw ?? this.lineAmountKrw,
      resolutionSource: resolutionSource ?? this.resolutionSource,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (finalLineId.present) {
      map['final_line_id'] = Variable<String>(finalLineId.value);
    }
    if (orderId.present) {
      map['order_id'] = Variable<String>(orderId.value);
    }
    if (productRevisionId.present) {
      map['product_revision_id'] = Variable<String>(productRevisionId.value);
    }
    if (productId.present) {
      map['product_id'] = Variable<String>(productId.value);
    }
    if (recognitionSkuId.present) {
      map['recognition_sku_id'] = Variable<int>(recognitionSkuId.value);
    }
    if (productName.present) {
      map['product_name'] = Variable<String>(productName.value);
    }
    if (unitPriceKrw.present) {
      map['unit_price_krw'] = Variable<int>(unitPriceKrw.value);
    }
    if (quantity.present) {
      map['quantity'] = Variable<int>(quantity.value);
    }
    if (lineAmountKrw.present) {
      map['line_amount_krw'] = Variable<int>(lineAmountKrw.value);
    }
    if (resolutionSource.present) {
      map['resolution_source'] = Variable<String>(resolutionSource.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('FinalOrderLinesCompanion(')
          ..write('finalLineId: $finalLineId, ')
          ..write('orderId: $orderId, ')
          ..write('productRevisionId: $productRevisionId, ')
          ..write('productId: $productId, ')
          ..write('recognitionSkuId: $recognitionSkuId, ')
          ..write('productName: $productName, ')
          ..write('unitPriceKrw: $unitPriceKrw, ')
          ..write('quantity: $quantity, ')
          ..write('lineAmountKrw: $lineAmountKrw, ')
          ..write('resolutionSource: $resolutionSource, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $SimulatedPaymentsTable extends SimulatedPayments
    with TableInfo<$SimulatedPaymentsTable, SimulatedPaymentRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SimulatedPaymentsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _paymentIdMeta = const VerificationMeta(
    'paymentId',
  );
  @override
  late final GeneratedColumn<String> paymentId = GeneratedColumn<String>(
    'payment_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _orderIdMeta = const VerificationMeta(
    'orderId',
  );
  @override
  late final GeneratedColumn<String> orderId = GeneratedColumn<String>(
    'order_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES final_orders (order_id)',
    ),
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _amountKrwMeta = const VerificationMeta(
    'amountKrw',
  );
  @override
  late final GeneratedColumn<int> amountKrw = GeneratedColumn<int>(
    'amount_krw',
    aliasedName,
    false,
    check: () => ComparableExpr(amountKrw).isBiggerOrEqualValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _currencyMeta = const VerificationMeta(
    'currency',
  );
  @override
  late final GeneratedColumn<String> currency = GeneratedColumn<String>(
    'currency',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _providerMeta = const VerificationMeta(
    'provider',
  );
  @override
  late final GeneratedColumn<String> provider = GeneratedColumn<String>(
    'provider',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _finalOrderSha256Meta = const VerificationMeta(
    'finalOrderSha256',
  );
  @override
  late final GeneratedColumn<String> finalOrderSha256 = GeneratedColumn<String>(
    'final_order_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _paidAtUsMeta = const VerificationMeta(
    'paidAtUs',
  );
  @override
  late final GeneratedColumn<int> paidAtUs = GeneratedColumn<int>(
    'paid_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    paymentId,
    orderId,
    sessionId,
    amountKrw,
    currency,
    provider,
    status,
    finalOrderSha256,
    paidAtUs,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'simulated_payments';
  @override
  VerificationContext validateIntegrity(
    Insertable<SimulatedPaymentRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('payment_id')) {
      context.handle(
        _paymentIdMeta,
        paymentId.isAcceptableOrUnknown(data['payment_id']!, _paymentIdMeta),
      );
    } else if (isInserting) {
      context.missing(_paymentIdMeta);
    }
    if (data.containsKey('order_id')) {
      context.handle(
        _orderIdMeta,
        orderId.isAcceptableOrUnknown(data['order_id']!, _orderIdMeta),
      );
    } else if (isInserting) {
      context.missing(_orderIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('amount_krw')) {
      context.handle(
        _amountKrwMeta,
        amountKrw.isAcceptableOrUnknown(data['amount_krw']!, _amountKrwMeta),
      );
    } else if (isInserting) {
      context.missing(_amountKrwMeta);
    }
    if (data.containsKey('currency')) {
      context.handle(
        _currencyMeta,
        currency.isAcceptableOrUnknown(data['currency']!, _currencyMeta),
      );
    } else if (isInserting) {
      context.missing(_currencyMeta);
    }
    if (data.containsKey('provider')) {
      context.handle(
        _providerMeta,
        provider.isAcceptableOrUnknown(data['provider']!, _providerMeta),
      );
    } else if (isInserting) {
      context.missing(_providerMeta);
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    } else if (isInserting) {
      context.missing(_statusMeta);
    }
    if (data.containsKey('final_order_sha256')) {
      context.handle(
        _finalOrderSha256Meta,
        finalOrderSha256.isAcceptableOrUnknown(
          data['final_order_sha256']!,
          _finalOrderSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_finalOrderSha256Meta);
    }
    if (data.containsKey('paid_at_us')) {
      context.handle(
        _paidAtUsMeta,
        paidAtUs.isAcceptableOrUnknown(data['paid_at_us']!, _paidAtUsMeta),
      );
    } else if (isInserting) {
      context.missing(_paidAtUsMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {paymentId};
  @override
  SimulatedPaymentRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SimulatedPaymentRow(
      paymentId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}payment_id'],
      )!,
      orderId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}order_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      amountKrw: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}amount_krw'],
      )!,
      currency: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}currency'],
      )!,
      provider: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}provider'],
      )!,
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
      finalOrderSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}final_order_sha256'],
      )!,
      paidAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}paid_at_us'],
      )!,
    );
  }

  @override
  $SimulatedPaymentsTable createAlias(String alias) {
    return $SimulatedPaymentsTable(attachedDatabase, alias);
  }
}

class SimulatedPaymentRow extends DataClass
    implements Insertable<SimulatedPaymentRow> {
  final String paymentId;
  final String orderId;
  final String sessionId;
  final int amountKrw;
  final String currency;
  final String provider;
  final String status;
  final String finalOrderSha256;
  final int paidAtUs;
  const SimulatedPaymentRow({
    required this.paymentId,
    required this.orderId,
    required this.sessionId,
    required this.amountKrw,
    required this.currency,
    required this.provider,
    required this.status,
    required this.finalOrderSha256,
    required this.paidAtUs,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['payment_id'] = Variable<String>(paymentId);
    map['order_id'] = Variable<String>(orderId);
    map['session_id'] = Variable<String>(sessionId);
    map['amount_krw'] = Variable<int>(amountKrw);
    map['currency'] = Variable<String>(currency);
    map['provider'] = Variable<String>(provider);
    map['status'] = Variable<String>(status);
    map['final_order_sha256'] = Variable<String>(finalOrderSha256);
    map['paid_at_us'] = Variable<int>(paidAtUs);
    return map;
  }

  SimulatedPaymentsCompanion toCompanion(bool nullToAbsent) {
    return SimulatedPaymentsCompanion(
      paymentId: Value(paymentId),
      orderId: Value(orderId),
      sessionId: Value(sessionId),
      amountKrw: Value(amountKrw),
      currency: Value(currency),
      provider: Value(provider),
      status: Value(status),
      finalOrderSha256: Value(finalOrderSha256),
      paidAtUs: Value(paidAtUs),
    );
  }

  factory SimulatedPaymentRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SimulatedPaymentRow(
      paymentId: serializer.fromJson<String>(json['paymentId']),
      orderId: serializer.fromJson<String>(json['orderId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      amountKrw: serializer.fromJson<int>(json['amountKrw']),
      currency: serializer.fromJson<String>(json['currency']),
      provider: serializer.fromJson<String>(json['provider']),
      status: serializer.fromJson<String>(json['status']),
      finalOrderSha256: serializer.fromJson<String>(json['finalOrderSha256']),
      paidAtUs: serializer.fromJson<int>(json['paidAtUs']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'paymentId': serializer.toJson<String>(paymentId),
      'orderId': serializer.toJson<String>(orderId),
      'sessionId': serializer.toJson<String>(sessionId),
      'amountKrw': serializer.toJson<int>(amountKrw),
      'currency': serializer.toJson<String>(currency),
      'provider': serializer.toJson<String>(provider),
      'status': serializer.toJson<String>(status),
      'finalOrderSha256': serializer.toJson<String>(finalOrderSha256),
      'paidAtUs': serializer.toJson<int>(paidAtUs),
    };
  }

  SimulatedPaymentRow copyWith({
    String? paymentId,
    String? orderId,
    String? sessionId,
    int? amountKrw,
    String? currency,
    String? provider,
    String? status,
    String? finalOrderSha256,
    int? paidAtUs,
  }) => SimulatedPaymentRow(
    paymentId: paymentId ?? this.paymentId,
    orderId: orderId ?? this.orderId,
    sessionId: sessionId ?? this.sessionId,
    amountKrw: amountKrw ?? this.amountKrw,
    currency: currency ?? this.currency,
    provider: provider ?? this.provider,
    status: status ?? this.status,
    finalOrderSha256: finalOrderSha256 ?? this.finalOrderSha256,
    paidAtUs: paidAtUs ?? this.paidAtUs,
  );
  SimulatedPaymentRow copyWithCompanion(SimulatedPaymentsCompanion data) {
    return SimulatedPaymentRow(
      paymentId: data.paymentId.present ? data.paymentId.value : this.paymentId,
      orderId: data.orderId.present ? data.orderId.value : this.orderId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      amountKrw: data.amountKrw.present ? data.amountKrw.value : this.amountKrw,
      currency: data.currency.present ? data.currency.value : this.currency,
      provider: data.provider.present ? data.provider.value : this.provider,
      status: data.status.present ? data.status.value : this.status,
      finalOrderSha256: data.finalOrderSha256.present
          ? data.finalOrderSha256.value
          : this.finalOrderSha256,
      paidAtUs: data.paidAtUs.present ? data.paidAtUs.value : this.paidAtUs,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SimulatedPaymentRow(')
          ..write('paymentId: $paymentId, ')
          ..write('orderId: $orderId, ')
          ..write('sessionId: $sessionId, ')
          ..write('amountKrw: $amountKrw, ')
          ..write('currency: $currency, ')
          ..write('provider: $provider, ')
          ..write('status: $status, ')
          ..write('finalOrderSha256: $finalOrderSha256, ')
          ..write('paidAtUs: $paidAtUs')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    paymentId,
    orderId,
    sessionId,
    amountKrw,
    currency,
    provider,
    status,
    finalOrderSha256,
    paidAtUs,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SimulatedPaymentRow &&
          other.paymentId == this.paymentId &&
          other.orderId == this.orderId &&
          other.sessionId == this.sessionId &&
          other.amountKrw == this.amountKrw &&
          other.currency == this.currency &&
          other.provider == this.provider &&
          other.status == this.status &&
          other.finalOrderSha256 == this.finalOrderSha256 &&
          other.paidAtUs == this.paidAtUs);
}

class SimulatedPaymentsCompanion extends UpdateCompanion<SimulatedPaymentRow> {
  final Value<String> paymentId;
  final Value<String> orderId;
  final Value<String> sessionId;
  final Value<int> amountKrw;
  final Value<String> currency;
  final Value<String> provider;
  final Value<String> status;
  final Value<String> finalOrderSha256;
  final Value<int> paidAtUs;
  final Value<int> rowid;
  const SimulatedPaymentsCompanion({
    this.paymentId = const Value.absent(),
    this.orderId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.amountKrw = const Value.absent(),
    this.currency = const Value.absent(),
    this.provider = const Value.absent(),
    this.status = const Value.absent(),
    this.finalOrderSha256 = const Value.absent(),
    this.paidAtUs = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SimulatedPaymentsCompanion.insert({
    required String paymentId,
    required String orderId,
    required String sessionId,
    required int amountKrw,
    required String currency,
    required String provider,
    required String status,
    required String finalOrderSha256,
    required int paidAtUs,
    this.rowid = const Value.absent(),
  }) : paymentId = Value(paymentId),
       orderId = Value(orderId),
       sessionId = Value(sessionId),
       amountKrw = Value(amountKrw),
       currency = Value(currency),
       provider = Value(provider),
       status = Value(status),
       finalOrderSha256 = Value(finalOrderSha256),
       paidAtUs = Value(paidAtUs);
  static Insertable<SimulatedPaymentRow> custom({
    Expression<String>? paymentId,
    Expression<String>? orderId,
    Expression<String>? sessionId,
    Expression<int>? amountKrw,
    Expression<String>? currency,
    Expression<String>? provider,
    Expression<String>? status,
    Expression<String>? finalOrderSha256,
    Expression<int>? paidAtUs,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (paymentId != null) 'payment_id': paymentId,
      if (orderId != null) 'order_id': orderId,
      if (sessionId != null) 'session_id': sessionId,
      if (amountKrw != null) 'amount_krw': amountKrw,
      if (currency != null) 'currency': currency,
      if (provider != null) 'provider': provider,
      if (status != null) 'status': status,
      if (finalOrderSha256 != null) 'final_order_sha256': finalOrderSha256,
      if (paidAtUs != null) 'paid_at_us': paidAtUs,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SimulatedPaymentsCompanion copyWith({
    Value<String>? paymentId,
    Value<String>? orderId,
    Value<String>? sessionId,
    Value<int>? amountKrw,
    Value<String>? currency,
    Value<String>? provider,
    Value<String>? status,
    Value<String>? finalOrderSha256,
    Value<int>? paidAtUs,
    Value<int>? rowid,
  }) {
    return SimulatedPaymentsCompanion(
      paymentId: paymentId ?? this.paymentId,
      orderId: orderId ?? this.orderId,
      sessionId: sessionId ?? this.sessionId,
      amountKrw: amountKrw ?? this.amountKrw,
      currency: currency ?? this.currency,
      provider: provider ?? this.provider,
      status: status ?? this.status,
      finalOrderSha256: finalOrderSha256 ?? this.finalOrderSha256,
      paidAtUs: paidAtUs ?? this.paidAtUs,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (paymentId.present) {
      map['payment_id'] = Variable<String>(paymentId.value);
    }
    if (orderId.present) {
      map['order_id'] = Variable<String>(orderId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (amountKrw.present) {
      map['amount_krw'] = Variable<int>(amountKrw.value);
    }
    if (currency.present) {
      map['currency'] = Variable<String>(currency.value);
    }
    if (provider.present) {
      map['provider'] = Variable<String>(provider.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (finalOrderSha256.present) {
      map['final_order_sha256'] = Variable<String>(finalOrderSha256.value);
    }
    if (paidAtUs.present) {
      map['paid_at_us'] = Variable<int>(paidAtUs.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SimulatedPaymentsCompanion(')
          ..write('paymentId: $paymentId, ')
          ..write('orderId: $orderId, ')
          ..write('sessionId: $sessionId, ')
          ..write('amountKrw: $amountKrw, ')
          ..write('currency: $currency, ')
          ..write('provider: $provider, ')
          ..write('status: $status, ')
          ..write('finalOrderSha256: $finalOrderSha256, ')
          ..write('paidAtUs: $paidAtUs, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $AuditEventsTable extends AuditEvents
    with TableInfo<$AuditEventsTable, AuditEventRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $AuditEventsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _eventIdMeta = const VerificationMeta(
    'eventId',
  );
  @override
  late final GeneratedColumn<String> eventId = GeneratedColumn<String>(
    'event_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _eventTypeMeta = const VerificationMeta(
    'eventType',
  );
  @override
  late final GeneratedColumn<String> eventType = GeneratedColumn<String>(
    'event_type',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _occurredAtUsMeta = const VerificationMeta(
    'occurredAtUs',
  );
  @override
  late final GeneratedColumn<int> occurredAtUs = GeneratedColumn<int>(
    'occurred_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _detailMeta = const VerificationMeta('detail');
  @override
  late final GeneratedColumn<String> detail = GeneratedColumn<String>(
    'detail',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    eventId,
    sessionId,
    eventType,
    occurredAtUs,
    detail,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'audit_events';
  @override
  VerificationContext validateIntegrity(
    Insertable<AuditEventRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('event_id')) {
      context.handle(
        _eventIdMeta,
        eventId.isAcceptableOrUnknown(data['event_id']!, _eventIdMeta),
      );
    } else if (isInserting) {
      context.missing(_eventIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    }
    if (data.containsKey('event_type')) {
      context.handle(
        _eventTypeMeta,
        eventType.isAcceptableOrUnknown(data['event_type']!, _eventTypeMeta),
      );
    } else if (isInserting) {
      context.missing(_eventTypeMeta);
    }
    if (data.containsKey('occurred_at_us')) {
      context.handle(
        _occurredAtUsMeta,
        occurredAtUs.isAcceptableOrUnknown(
          data['occurred_at_us']!,
          _occurredAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_occurredAtUsMeta);
    }
    if (data.containsKey('detail')) {
      context.handle(
        _detailMeta,
        detail.isAcceptableOrUnknown(data['detail']!, _detailMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {eventId};
  @override
  AuditEventRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return AuditEventRow(
      eventId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}event_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      ),
      eventType: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}event_type'],
      )!,
      occurredAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}occurred_at_us'],
      )!,
      detail: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}detail'],
      ),
    );
  }

  @override
  $AuditEventsTable createAlias(String alias) {
    return $AuditEventsTable(attachedDatabase, alias);
  }
}

class AuditEventRow extends DataClass implements Insertable<AuditEventRow> {
  final String eventId;
  final String? sessionId;
  final String eventType;
  final int occurredAtUs;
  final String? detail;
  const AuditEventRow({
    required this.eventId,
    this.sessionId,
    required this.eventType,
    required this.occurredAtUs,
    this.detail,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['event_id'] = Variable<String>(eventId);
    if (!nullToAbsent || sessionId != null) {
      map['session_id'] = Variable<String>(sessionId);
    }
    map['event_type'] = Variable<String>(eventType);
    map['occurred_at_us'] = Variable<int>(occurredAtUs);
    if (!nullToAbsent || detail != null) {
      map['detail'] = Variable<String>(detail);
    }
    return map;
  }

  AuditEventsCompanion toCompanion(bool nullToAbsent) {
    return AuditEventsCompanion(
      eventId: Value(eventId),
      sessionId: sessionId == null && nullToAbsent
          ? const Value.absent()
          : Value(sessionId),
      eventType: Value(eventType),
      occurredAtUs: Value(occurredAtUs),
      detail: detail == null && nullToAbsent
          ? const Value.absent()
          : Value(detail),
    );
  }

  factory AuditEventRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return AuditEventRow(
      eventId: serializer.fromJson<String>(json['eventId']),
      sessionId: serializer.fromJson<String?>(json['sessionId']),
      eventType: serializer.fromJson<String>(json['eventType']),
      occurredAtUs: serializer.fromJson<int>(json['occurredAtUs']),
      detail: serializer.fromJson<String?>(json['detail']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'eventId': serializer.toJson<String>(eventId),
      'sessionId': serializer.toJson<String?>(sessionId),
      'eventType': serializer.toJson<String>(eventType),
      'occurredAtUs': serializer.toJson<int>(occurredAtUs),
      'detail': serializer.toJson<String?>(detail),
    };
  }

  AuditEventRow copyWith({
    String? eventId,
    Value<String?> sessionId = const Value.absent(),
    String? eventType,
    int? occurredAtUs,
    Value<String?> detail = const Value.absent(),
  }) => AuditEventRow(
    eventId: eventId ?? this.eventId,
    sessionId: sessionId.present ? sessionId.value : this.sessionId,
    eventType: eventType ?? this.eventType,
    occurredAtUs: occurredAtUs ?? this.occurredAtUs,
    detail: detail.present ? detail.value : this.detail,
  );
  AuditEventRow copyWithCompanion(AuditEventsCompanion data) {
    return AuditEventRow(
      eventId: data.eventId.present ? data.eventId.value : this.eventId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      eventType: data.eventType.present ? data.eventType.value : this.eventType,
      occurredAtUs: data.occurredAtUs.present
          ? data.occurredAtUs.value
          : this.occurredAtUs,
      detail: data.detail.present ? data.detail.value : this.detail,
    );
  }

  @override
  String toString() {
    return (StringBuffer('AuditEventRow(')
          ..write('eventId: $eventId, ')
          ..write('sessionId: $sessionId, ')
          ..write('eventType: $eventType, ')
          ..write('occurredAtUs: $occurredAtUs, ')
          ..write('detail: $detail')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(eventId, sessionId, eventType, occurredAtUs, detail);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is AuditEventRow &&
          other.eventId == this.eventId &&
          other.sessionId == this.sessionId &&
          other.eventType == this.eventType &&
          other.occurredAtUs == this.occurredAtUs &&
          other.detail == this.detail);
}

class AuditEventsCompanion extends UpdateCompanion<AuditEventRow> {
  final Value<String> eventId;
  final Value<String?> sessionId;
  final Value<String> eventType;
  final Value<int> occurredAtUs;
  final Value<String?> detail;
  final Value<int> rowid;
  const AuditEventsCompanion({
    this.eventId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.eventType = const Value.absent(),
    this.occurredAtUs = const Value.absent(),
    this.detail = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  AuditEventsCompanion.insert({
    required String eventId,
    this.sessionId = const Value.absent(),
    required String eventType,
    required int occurredAtUs,
    this.detail = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : eventId = Value(eventId),
       eventType = Value(eventType),
       occurredAtUs = Value(occurredAtUs);
  static Insertable<AuditEventRow> custom({
    Expression<String>? eventId,
    Expression<String>? sessionId,
    Expression<String>? eventType,
    Expression<int>? occurredAtUs,
    Expression<String>? detail,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (eventId != null) 'event_id': eventId,
      if (sessionId != null) 'session_id': sessionId,
      if (eventType != null) 'event_type': eventType,
      if (occurredAtUs != null) 'occurred_at_us': occurredAtUs,
      if (detail != null) 'detail': detail,
      if (rowid != null) 'rowid': rowid,
    });
  }

  AuditEventsCompanion copyWith({
    Value<String>? eventId,
    Value<String?>? sessionId,
    Value<String>? eventType,
    Value<int>? occurredAtUs,
    Value<String?>? detail,
    Value<int>? rowid,
  }) {
    return AuditEventsCompanion(
      eventId: eventId ?? this.eventId,
      sessionId: sessionId ?? this.sessionId,
      eventType: eventType ?? this.eventType,
      occurredAtUs: occurredAtUs ?? this.occurredAtUs,
      detail: detail ?? this.detail,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (eventId.present) {
      map['event_id'] = Variable<String>(eventId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (eventType.present) {
      map['event_type'] = Variable<String>(eventType.value);
    }
    if (occurredAtUs.present) {
      map['occurred_at_us'] = Variable<int>(occurredAtUs.value);
    }
    if (detail.present) {
      map['detail'] = Variable<String>(detail.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('AuditEventsCompanion(')
          ..write('eventId: $eventId, ')
          ..write('sessionId: $sessionId, ')
          ..write('eventType: $eventType, ')
          ..write('occurredAtUs: $occurredAtUs, ')
          ..write('detail: $detail, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $AppSettingsTable extends AppSettings
    with TableInfo<$AppSettingsTable, AppSettingsRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $AppSettingsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _settingsIdMeta = const VerificationMeta(
    'settingsId',
  );
  @override
  late final GeneratedColumn<String> settingsId = GeneratedColumn<String>(
    'settings_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _activeSettingsRevisionIdMeta =
      const VerificationMeta('activeSettingsRevisionId');
  @override
  late final GeneratedColumn<String> activeSettingsRevisionId =
      GeneratedColumn<String>(
        'active_settings_revision_id',
        aliasedName,
        false,
        type: DriftSqlType.string,
        requiredDuringInsert: true,
        defaultConstraints: GeneratedColumn.constraintIsAlways(
          'REFERENCES settings_revisions (revision_id)',
        ),
      );
  static const VerificationMeta _applicationVersionValueMeta =
      const VerificationMeta('applicationVersionValue');
  @override
  late final GeneratedColumn<String> applicationVersionValue =
      GeneratedColumn<String>(
        'application_version_value',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  static const VerificationMeta _lastMigrationResultMeta =
      const VerificationMeta('lastMigrationResult');
  @override
  late final GeneratedColumn<String> lastMigrationResult =
      GeneratedColumn<String>(
        'last_migration_result',
        aliasedName,
        false,
        additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
        type: DriftSqlType.string,
        requiredDuringInsert: true,
      );
  @override
  List<GeneratedColumn> get $columns => [
    settingsId,
    activeSettingsRevisionId,
    applicationVersionValue,
    lastMigrationResult,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'app_settings';
  @override
  VerificationContext validateIntegrity(
    Insertable<AppSettingsRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('settings_id')) {
      context.handle(
        _settingsIdMeta,
        settingsId.isAcceptableOrUnknown(data['settings_id']!, _settingsIdMeta),
      );
    } else if (isInserting) {
      context.missing(_settingsIdMeta);
    }
    if (data.containsKey('active_settings_revision_id')) {
      context.handle(
        _activeSettingsRevisionIdMeta,
        activeSettingsRevisionId.isAcceptableOrUnknown(
          data['active_settings_revision_id']!,
          _activeSettingsRevisionIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_activeSettingsRevisionIdMeta);
    }
    if (data.containsKey('application_version_value')) {
      context.handle(
        _applicationVersionValueMeta,
        applicationVersionValue.isAcceptableOrUnknown(
          data['application_version_value']!,
          _applicationVersionValueMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_applicationVersionValueMeta);
    }
    if (data.containsKey('last_migration_result')) {
      context.handle(
        _lastMigrationResultMeta,
        lastMigrationResult.isAcceptableOrUnknown(
          data['last_migration_result']!,
          _lastMigrationResultMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_lastMigrationResultMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {settingsId};
  @override
  AppSettingsRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return AppSettingsRow(
      settingsId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}settings_id'],
      )!,
      activeSettingsRevisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}active_settings_revision_id'],
      )!,
      applicationVersionValue: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}application_version_value'],
      )!,
      lastMigrationResult: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}last_migration_result'],
      )!,
    );
  }

  @override
  $AppSettingsTable createAlias(String alias) {
    return $AppSettingsTable(attachedDatabase, alias);
  }
}

class AppSettingsRow extends DataClass implements Insertable<AppSettingsRow> {
  final String settingsId;
  final String activeSettingsRevisionId;
  final String applicationVersionValue;
  final String lastMigrationResult;
  const AppSettingsRow({
    required this.settingsId,
    required this.activeSettingsRevisionId,
    required this.applicationVersionValue,
    required this.lastMigrationResult,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['settings_id'] = Variable<String>(settingsId);
    map['active_settings_revision_id'] = Variable<String>(
      activeSettingsRevisionId,
    );
    map['application_version_value'] = Variable<String>(
      applicationVersionValue,
    );
    map['last_migration_result'] = Variable<String>(lastMigrationResult);
    return map;
  }

  AppSettingsCompanion toCompanion(bool nullToAbsent) {
    return AppSettingsCompanion(
      settingsId: Value(settingsId),
      activeSettingsRevisionId: Value(activeSettingsRevisionId),
      applicationVersionValue: Value(applicationVersionValue),
      lastMigrationResult: Value(lastMigrationResult),
    );
  }

  factory AppSettingsRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return AppSettingsRow(
      settingsId: serializer.fromJson<String>(json['settingsId']),
      activeSettingsRevisionId: serializer.fromJson<String>(
        json['activeSettingsRevisionId'],
      ),
      applicationVersionValue: serializer.fromJson<String>(
        json['applicationVersionValue'],
      ),
      lastMigrationResult: serializer.fromJson<String>(
        json['lastMigrationResult'],
      ),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'settingsId': serializer.toJson<String>(settingsId),
      'activeSettingsRevisionId': serializer.toJson<String>(
        activeSettingsRevisionId,
      ),
      'applicationVersionValue': serializer.toJson<String>(
        applicationVersionValue,
      ),
      'lastMigrationResult': serializer.toJson<String>(lastMigrationResult),
    };
  }

  AppSettingsRow copyWith({
    String? settingsId,
    String? activeSettingsRevisionId,
    String? applicationVersionValue,
    String? lastMigrationResult,
  }) => AppSettingsRow(
    settingsId: settingsId ?? this.settingsId,
    activeSettingsRevisionId:
        activeSettingsRevisionId ?? this.activeSettingsRevisionId,
    applicationVersionValue:
        applicationVersionValue ?? this.applicationVersionValue,
    lastMigrationResult: lastMigrationResult ?? this.lastMigrationResult,
  );
  AppSettingsRow copyWithCompanion(AppSettingsCompanion data) {
    return AppSettingsRow(
      settingsId: data.settingsId.present
          ? data.settingsId.value
          : this.settingsId,
      activeSettingsRevisionId: data.activeSettingsRevisionId.present
          ? data.activeSettingsRevisionId.value
          : this.activeSettingsRevisionId,
      applicationVersionValue: data.applicationVersionValue.present
          ? data.applicationVersionValue.value
          : this.applicationVersionValue,
      lastMigrationResult: data.lastMigrationResult.present
          ? data.lastMigrationResult.value
          : this.lastMigrationResult,
    );
  }

  @override
  String toString() {
    return (StringBuffer('AppSettingsRow(')
          ..write('settingsId: $settingsId, ')
          ..write('activeSettingsRevisionId: $activeSettingsRevisionId, ')
          ..write('applicationVersionValue: $applicationVersionValue, ')
          ..write('lastMigrationResult: $lastMigrationResult')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    settingsId,
    activeSettingsRevisionId,
    applicationVersionValue,
    lastMigrationResult,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is AppSettingsRow &&
          other.settingsId == this.settingsId &&
          other.activeSettingsRevisionId == this.activeSettingsRevisionId &&
          other.applicationVersionValue == this.applicationVersionValue &&
          other.lastMigrationResult == this.lastMigrationResult);
}

class AppSettingsCompanion extends UpdateCompanion<AppSettingsRow> {
  final Value<String> settingsId;
  final Value<String> activeSettingsRevisionId;
  final Value<String> applicationVersionValue;
  final Value<String> lastMigrationResult;
  final Value<int> rowid;
  const AppSettingsCompanion({
    this.settingsId = const Value.absent(),
    this.activeSettingsRevisionId = const Value.absent(),
    this.applicationVersionValue = const Value.absent(),
    this.lastMigrationResult = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  AppSettingsCompanion.insert({
    required String settingsId,
    required String activeSettingsRevisionId,
    required String applicationVersionValue,
    required String lastMigrationResult,
    this.rowid = const Value.absent(),
  }) : settingsId = Value(settingsId),
       activeSettingsRevisionId = Value(activeSettingsRevisionId),
       applicationVersionValue = Value(applicationVersionValue),
       lastMigrationResult = Value(lastMigrationResult);
  static Insertable<AppSettingsRow> custom({
    Expression<String>? settingsId,
    Expression<String>? activeSettingsRevisionId,
    Expression<String>? applicationVersionValue,
    Expression<String>? lastMigrationResult,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (settingsId != null) 'settings_id': settingsId,
      if (activeSettingsRevisionId != null)
        'active_settings_revision_id': activeSettingsRevisionId,
      if (applicationVersionValue != null)
        'application_version_value': applicationVersionValue,
      if (lastMigrationResult != null)
        'last_migration_result': lastMigrationResult,
      if (rowid != null) 'rowid': rowid,
    });
  }

  AppSettingsCompanion copyWith({
    Value<String>? settingsId,
    Value<String>? activeSettingsRevisionId,
    Value<String>? applicationVersionValue,
    Value<String>? lastMigrationResult,
    Value<int>? rowid,
  }) {
    return AppSettingsCompanion(
      settingsId: settingsId ?? this.settingsId,
      activeSettingsRevisionId:
          activeSettingsRevisionId ?? this.activeSettingsRevisionId,
      applicationVersionValue:
          applicationVersionValue ?? this.applicationVersionValue,
      lastMigrationResult: lastMigrationResult ?? this.lastMigrationResult,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (settingsId.present) {
      map['settings_id'] = Variable<String>(settingsId.value);
    }
    if (activeSettingsRevisionId.present) {
      map['active_settings_revision_id'] = Variable<String>(
        activeSettingsRevisionId.value,
      );
    }
    if (applicationVersionValue.present) {
      map['application_version_value'] = Variable<String>(
        applicationVersionValue.value,
      );
    }
    if (lastMigrationResult.present) {
      map['last_migration_result'] = Variable<String>(
        lastMigrationResult.value,
      );
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('AppSettingsCompanion(')
          ..write('settingsId: $settingsId, ')
          ..write('activeSettingsRevisionId: $activeSettingsRevisionId, ')
          ..write('applicationVersionValue: $applicationVersionValue, ')
          ..write('lastMigrationResult: $lastMigrationResult, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $RetentionEventsTable extends RetentionEvents
    with TableInfo<$RetentionEventsTable, RetentionEventRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $RetentionEventsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _retentionEventIdMeta = const VerificationMeta(
    'retentionEventId',
  );
  @override
  late final GeneratedColumn<String> retentionEventId = GeneratedColumn<String>(
    'retention_event_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _attemptIdMeta = const VerificationMeta(
    'attemptId',
  );
  @override
  late final GeneratedColumn<String> attemptId = GeneratedColumn<String>(
    'attempt_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES scan_attempts (attempt_id)',
    ),
  );
  static const VerificationMeta _relativePathMeta = const VerificationMeta(
    'relativePath',
  );
  @override
  late final GeneratedColumn<String> relativePath = GeneratedColumn<String>(
    'relative_path',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _originalByteSizeMeta = const VerificationMeta(
    'originalByteSize',
  );
  @override
  late final GeneratedColumn<int> originalByteSize = GeneratedColumn<int>(
    'original_byte_size',
    aliasedName,
    false,
    check: () => ComparableExpr(originalByteSize).isBiggerThanValue(0),
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _originalSha256Meta = const VerificationMeta(
    'originalSha256',
  );
  @override
  late final GeneratedColumn<String> originalSha256 = GeneratedColumn<String>(
    'original_sha256',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(
      minTextLength: 64,
      maxTextLength: 64,
    ),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _prunedAtUsMeta = const VerificationMeta(
    'prunedAtUs',
  );
  @override
  late final GeneratedColumn<int> prunedAtUs = GeneratedColumn<int>(
    'pruned_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _reasonMeta = const VerificationMeta('reason');
  @override
  late final GeneratedColumn<String> reason = GeneratedColumn<String>(
    'reason',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    retentionEventId,
    attemptId,
    relativePath,
    originalByteSize,
    originalSha256,
    prunedAtUs,
    reason,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'retention_events';
  @override
  VerificationContext validateIntegrity(
    Insertable<RetentionEventRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('retention_event_id')) {
      context.handle(
        _retentionEventIdMeta,
        retentionEventId.isAcceptableOrUnknown(
          data['retention_event_id']!,
          _retentionEventIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_retentionEventIdMeta);
    }
    if (data.containsKey('attempt_id')) {
      context.handle(
        _attemptIdMeta,
        attemptId.isAcceptableOrUnknown(data['attempt_id']!, _attemptIdMeta),
      );
    } else if (isInserting) {
      context.missing(_attemptIdMeta);
    }
    if (data.containsKey('relative_path')) {
      context.handle(
        _relativePathMeta,
        relativePath.isAcceptableOrUnknown(
          data['relative_path']!,
          _relativePathMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_relativePathMeta);
    }
    if (data.containsKey('original_byte_size')) {
      context.handle(
        _originalByteSizeMeta,
        originalByteSize.isAcceptableOrUnknown(
          data['original_byte_size']!,
          _originalByteSizeMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_originalByteSizeMeta);
    }
    if (data.containsKey('original_sha256')) {
      context.handle(
        _originalSha256Meta,
        originalSha256.isAcceptableOrUnknown(
          data['original_sha256']!,
          _originalSha256Meta,
        ),
      );
    } else if (isInserting) {
      context.missing(_originalSha256Meta);
    }
    if (data.containsKey('pruned_at_us')) {
      context.handle(
        _prunedAtUsMeta,
        prunedAtUs.isAcceptableOrUnknown(
          data['pruned_at_us']!,
          _prunedAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_prunedAtUsMeta);
    }
    if (data.containsKey('reason')) {
      context.handle(
        _reasonMeta,
        reason.isAcceptableOrUnknown(data['reason']!, _reasonMeta),
      );
    } else if (isInserting) {
      context.missing(_reasonMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {retentionEventId};
  @override
  RetentionEventRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return RetentionEventRow(
      retentionEventId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}retention_event_id'],
      )!,
      attemptId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}attempt_id'],
      )!,
      relativePath: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}relative_path'],
      )!,
      originalByteSize: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}original_byte_size'],
      )!,
      originalSha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}original_sha256'],
      )!,
      prunedAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}pruned_at_us'],
      )!,
      reason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}reason'],
      )!,
    );
  }

  @override
  $RetentionEventsTable createAlias(String alias) {
    return $RetentionEventsTable(attachedDatabase, alias);
  }
}

class RetentionEventRow extends DataClass
    implements Insertable<RetentionEventRow> {
  final String retentionEventId;
  final String attemptId;
  final String relativePath;
  final int originalByteSize;
  final String originalSha256;
  final int prunedAtUs;
  final String reason;
  const RetentionEventRow({
    required this.retentionEventId,
    required this.attemptId,
    required this.relativePath,
    required this.originalByteSize,
    required this.originalSha256,
    required this.prunedAtUs,
    required this.reason,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['retention_event_id'] = Variable<String>(retentionEventId);
    map['attempt_id'] = Variable<String>(attemptId);
    map['relative_path'] = Variable<String>(relativePath);
    map['original_byte_size'] = Variable<int>(originalByteSize);
    map['original_sha256'] = Variable<String>(originalSha256);
    map['pruned_at_us'] = Variable<int>(prunedAtUs);
    map['reason'] = Variable<String>(reason);
    return map;
  }

  RetentionEventsCompanion toCompanion(bool nullToAbsent) {
    return RetentionEventsCompanion(
      retentionEventId: Value(retentionEventId),
      attemptId: Value(attemptId),
      relativePath: Value(relativePath),
      originalByteSize: Value(originalByteSize),
      originalSha256: Value(originalSha256),
      prunedAtUs: Value(prunedAtUs),
      reason: Value(reason),
    );
  }

  factory RetentionEventRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return RetentionEventRow(
      retentionEventId: serializer.fromJson<String>(json['retentionEventId']),
      attemptId: serializer.fromJson<String>(json['attemptId']),
      relativePath: serializer.fromJson<String>(json['relativePath']),
      originalByteSize: serializer.fromJson<int>(json['originalByteSize']),
      originalSha256: serializer.fromJson<String>(json['originalSha256']),
      prunedAtUs: serializer.fromJson<int>(json['prunedAtUs']),
      reason: serializer.fromJson<String>(json['reason']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'retentionEventId': serializer.toJson<String>(retentionEventId),
      'attemptId': serializer.toJson<String>(attemptId),
      'relativePath': serializer.toJson<String>(relativePath),
      'originalByteSize': serializer.toJson<int>(originalByteSize),
      'originalSha256': serializer.toJson<String>(originalSha256),
      'prunedAtUs': serializer.toJson<int>(prunedAtUs),
      'reason': serializer.toJson<String>(reason),
    };
  }

  RetentionEventRow copyWith({
    String? retentionEventId,
    String? attemptId,
    String? relativePath,
    int? originalByteSize,
    String? originalSha256,
    int? prunedAtUs,
    String? reason,
  }) => RetentionEventRow(
    retentionEventId: retentionEventId ?? this.retentionEventId,
    attemptId: attemptId ?? this.attemptId,
    relativePath: relativePath ?? this.relativePath,
    originalByteSize: originalByteSize ?? this.originalByteSize,
    originalSha256: originalSha256 ?? this.originalSha256,
    prunedAtUs: prunedAtUs ?? this.prunedAtUs,
    reason: reason ?? this.reason,
  );
  RetentionEventRow copyWithCompanion(RetentionEventsCompanion data) {
    return RetentionEventRow(
      retentionEventId: data.retentionEventId.present
          ? data.retentionEventId.value
          : this.retentionEventId,
      attemptId: data.attemptId.present ? data.attemptId.value : this.attemptId,
      relativePath: data.relativePath.present
          ? data.relativePath.value
          : this.relativePath,
      originalByteSize: data.originalByteSize.present
          ? data.originalByteSize.value
          : this.originalByteSize,
      originalSha256: data.originalSha256.present
          ? data.originalSha256.value
          : this.originalSha256,
      prunedAtUs: data.prunedAtUs.present
          ? data.prunedAtUs.value
          : this.prunedAtUs,
      reason: data.reason.present ? data.reason.value : this.reason,
    );
  }

  @override
  String toString() {
    return (StringBuffer('RetentionEventRow(')
          ..write('retentionEventId: $retentionEventId, ')
          ..write('attemptId: $attemptId, ')
          ..write('relativePath: $relativePath, ')
          ..write('originalByteSize: $originalByteSize, ')
          ..write('originalSha256: $originalSha256, ')
          ..write('prunedAtUs: $prunedAtUs, ')
          ..write('reason: $reason')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    retentionEventId,
    attemptId,
    relativePath,
    originalByteSize,
    originalSha256,
    prunedAtUs,
    reason,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is RetentionEventRow &&
          other.retentionEventId == this.retentionEventId &&
          other.attemptId == this.attemptId &&
          other.relativePath == this.relativePath &&
          other.originalByteSize == this.originalByteSize &&
          other.originalSha256 == this.originalSha256 &&
          other.prunedAtUs == this.prunedAtUs &&
          other.reason == this.reason);
}

class RetentionEventsCompanion extends UpdateCompanion<RetentionEventRow> {
  final Value<String> retentionEventId;
  final Value<String> attemptId;
  final Value<String> relativePath;
  final Value<int> originalByteSize;
  final Value<String> originalSha256;
  final Value<int> prunedAtUs;
  final Value<String> reason;
  final Value<int> rowid;
  const RetentionEventsCompanion({
    this.retentionEventId = const Value.absent(),
    this.attemptId = const Value.absent(),
    this.relativePath = const Value.absent(),
    this.originalByteSize = const Value.absent(),
    this.originalSha256 = const Value.absent(),
    this.prunedAtUs = const Value.absent(),
    this.reason = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  RetentionEventsCompanion.insert({
    required String retentionEventId,
    required String attemptId,
    required String relativePath,
    required int originalByteSize,
    required String originalSha256,
    required int prunedAtUs,
    required String reason,
    this.rowid = const Value.absent(),
  }) : retentionEventId = Value(retentionEventId),
       attemptId = Value(attemptId),
       relativePath = Value(relativePath),
       originalByteSize = Value(originalByteSize),
       originalSha256 = Value(originalSha256),
       prunedAtUs = Value(prunedAtUs),
       reason = Value(reason);
  static Insertable<RetentionEventRow> custom({
    Expression<String>? retentionEventId,
    Expression<String>? attemptId,
    Expression<String>? relativePath,
    Expression<int>? originalByteSize,
    Expression<String>? originalSha256,
    Expression<int>? prunedAtUs,
    Expression<String>? reason,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (retentionEventId != null) 'retention_event_id': retentionEventId,
      if (attemptId != null) 'attempt_id': attemptId,
      if (relativePath != null) 'relative_path': relativePath,
      if (originalByteSize != null) 'original_byte_size': originalByteSize,
      if (originalSha256 != null) 'original_sha256': originalSha256,
      if (prunedAtUs != null) 'pruned_at_us': prunedAtUs,
      if (reason != null) 'reason': reason,
      if (rowid != null) 'rowid': rowid,
    });
  }

  RetentionEventsCompanion copyWith({
    Value<String>? retentionEventId,
    Value<String>? attemptId,
    Value<String>? relativePath,
    Value<int>? originalByteSize,
    Value<String>? originalSha256,
    Value<int>? prunedAtUs,
    Value<String>? reason,
    Value<int>? rowid,
  }) {
    return RetentionEventsCompanion(
      retentionEventId: retentionEventId ?? this.retentionEventId,
      attemptId: attemptId ?? this.attemptId,
      relativePath: relativePath ?? this.relativePath,
      originalByteSize: originalByteSize ?? this.originalByteSize,
      originalSha256: originalSha256 ?? this.originalSha256,
      prunedAtUs: prunedAtUs ?? this.prunedAtUs,
      reason: reason ?? this.reason,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (retentionEventId.present) {
      map['retention_event_id'] = Variable<String>(retentionEventId.value);
    }
    if (attemptId.present) {
      map['attempt_id'] = Variable<String>(attemptId.value);
    }
    if (relativePath.present) {
      map['relative_path'] = Variable<String>(relativePath.value);
    }
    if (originalByteSize.present) {
      map['original_byte_size'] = Variable<int>(originalByteSize.value);
    }
    if (originalSha256.present) {
      map['original_sha256'] = Variable<String>(originalSha256.value);
    }
    if (prunedAtUs.present) {
      map['pruned_at_us'] = Variable<int>(prunedAtUs.value);
    }
    if (reason.present) {
      map['reason'] = Variable<String>(reason.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('RetentionEventsCompanion(')
          ..write('retentionEventId: $retentionEventId, ')
          ..write('attemptId: $attemptId, ')
          ..write('relativePath: $relativePath, ')
          ..write('originalByteSize: $originalByteSize, ')
          ..write('originalSha256: $originalSha256, ')
          ..write('prunedAtUs: $prunedAtUs, ')
          ..write('reason: $reason, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $AdminReviewAnnotationsTable extends AdminReviewAnnotations
    with TableInfo<$AdminReviewAnnotationsTable, AdminReviewAnnotationRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $AdminReviewAnnotationsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _annotationIdMeta = const VerificationMeta(
    'annotationId',
  );
  @override
  late final GeneratedColumn<String> annotationId = GeneratedColumn<String>(
    'annotation_id',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sessionIdMeta = const VerificationMeta(
    'sessionId',
  );
  @override
  late final GeneratedColumn<String> sessionId = GeneratedColumn<String>(
    'session_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES checkout_sessions (session_id)',
    ),
  );
  static const VerificationMeta _attemptIdMeta = const VerificationMeta(
    'attemptId',
  );
  @override
  late final GeneratedColumn<String> attemptId = GeneratedColumn<String>(
    'attempt_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES scan_attempts (attempt_id)',
    ),
  );
  static const VerificationMeta _objectIdMeta = const VerificationMeta(
    'objectId',
  );
  @override
  late final GeneratedColumn<String> objectId = GeneratedColumn<String>(
    'object_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES inference_objects (inference_object_id)',
    ),
  );
  static const VerificationMeta _reviewStatusMeta = const VerificationMeta(
    'reviewStatus',
  );
  @override
  late final GeneratedColumn<String> reviewStatus = GeneratedColumn<String>(
    'review_status',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _correctProductIdMeta = const VerificationMeta(
    'correctProductId',
  );
  @override
  late final GeneratedColumn<String> correctProductId = GeneratedColumn<String>(
    'correct_product_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _conclusionCodeMeta = const VerificationMeta(
    'conclusionCode',
  );
  @override
  late final GeneratedColumn<String> conclusionCode = GeneratedColumn<String>(
    'conclusion_code',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('ai_correct'),
  );
  static const VerificationMeta _reasonCodeMeta = const VerificationMeta(
    'reasonCode',
  );
  @override
  late final GeneratedColumn<String> reasonCode = GeneratedColumn<String>(
    'reason_code',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _noteMeta = const VerificationMeta('note');
  @override
  late final GeneratedColumn<String> note = GeneratedColumn<String>(
    'note',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _authorLabelMeta = const VerificationMeta(
    'authorLabel',
  );
  @override
  late final GeneratedColumn<String> authorLabel = GeneratedColumn<String>(
    'author_label',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtUsMeta = const VerificationMeta(
    'createdAtUs',
  );
  @override
  late final GeneratedColumn<int> createdAtUs = GeneratedColumn<int>(
    'created_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    annotationId,
    sessionId,
    attemptId,
    objectId,
    reviewStatus,
    correctProductId,
    conclusionCode,
    reasonCode,
    note,
    authorLabel,
    createdAtUs,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'admin_review_annotations';
  @override
  VerificationContext validateIntegrity(
    Insertable<AdminReviewAnnotationRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('annotation_id')) {
      context.handle(
        _annotationIdMeta,
        annotationId.isAcceptableOrUnknown(
          data['annotation_id']!,
          _annotationIdMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_annotationIdMeta);
    }
    if (data.containsKey('session_id')) {
      context.handle(
        _sessionIdMeta,
        sessionId.isAcceptableOrUnknown(data['session_id']!, _sessionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_sessionIdMeta);
    }
    if (data.containsKey('attempt_id')) {
      context.handle(
        _attemptIdMeta,
        attemptId.isAcceptableOrUnknown(data['attempt_id']!, _attemptIdMeta),
      );
    }
    if (data.containsKey('object_id')) {
      context.handle(
        _objectIdMeta,
        objectId.isAcceptableOrUnknown(data['object_id']!, _objectIdMeta),
      );
    }
    if (data.containsKey('review_status')) {
      context.handle(
        _reviewStatusMeta,
        reviewStatus.isAcceptableOrUnknown(
          data['review_status']!,
          _reviewStatusMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_reviewStatusMeta);
    }
    if (data.containsKey('correct_product_id')) {
      context.handle(
        _correctProductIdMeta,
        correctProductId.isAcceptableOrUnknown(
          data['correct_product_id']!,
          _correctProductIdMeta,
        ),
      );
    }
    if (data.containsKey('conclusion_code')) {
      context.handle(
        _conclusionCodeMeta,
        conclusionCode.isAcceptableOrUnknown(
          data['conclusion_code']!,
          _conclusionCodeMeta,
        ),
      );
    }
    if (data.containsKey('reason_code')) {
      context.handle(
        _reasonCodeMeta,
        reasonCode.isAcceptableOrUnknown(data['reason_code']!, _reasonCodeMeta),
      );
    } else if (isInserting) {
      context.missing(_reasonCodeMeta);
    }
    if (data.containsKey('note')) {
      context.handle(
        _noteMeta,
        note.isAcceptableOrUnknown(data['note']!, _noteMeta),
      );
    }
    if (data.containsKey('author_label')) {
      context.handle(
        _authorLabelMeta,
        authorLabel.isAcceptableOrUnknown(
          data['author_label']!,
          _authorLabelMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_authorLabelMeta);
    }
    if (data.containsKey('created_at_us')) {
      context.handle(
        _createdAtUsMeta,
        createdAtUs.isAcceptableOrUnknown(
          data['created_at_us']!,
          _createdAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_createdAtUsMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {annotationId};
  @override
  AdminReviewAnnotationRow map(
    Map<String, dynamic> data, {
    String? tablePrefix,
  }) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return AdminReviewAnnotationRow(
      annotationId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}annotation_id'],
      )!,
      sessionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}session_id'],
      )!,
      attemptId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}attempt_id'],
      ),
      objectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}object_id'],
      ),
      reviewStatus: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}review_status'],
      )!,
      correctProductId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}correct_product_id'],
      ),
      conclusionCode: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}conclusion_code'],
      )!,
      reasonCode: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}reason_code'],
      )!,
      note: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}note'],
      ),
      authorLabel: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}author_label'],
      )!,
      createdAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at_us'],
      )!,
    );
  }

  @override
  $AdminReviewAnnotationsTable createAlias(String alias) {
    return $AdminReviewAnnotationsTable(attachedDatabase, alias);
  }
}

class AdminReviewAnnotationRow extends DataClass
    implements Insertable<AdminReviewAnnotationRow> {
  final String annotationId;
  final String sessionId;
  final String? attemptId;
  final String? objectId;
  final String reviewStatus;
  final String? correctProductId;
  final String conclusionCode;
  final String reasonCode;
  final String? note;
  final String authorLabel;
  final int createdAtUs;
  const AdminReviewAnnotationRow({
    required this.annotationId,
    required this.sessionId,
    this.attemptId,
    this.objectId,
    required this.reviewStatus,
    this.correctProductId,
    required this.conclusionCode,
    required this.reasonCode,
    this.note,
    required this.authorLabel,
    required this.createdAtUs,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['annotation_id'] = Variable<String>(annotationId);
    map['session_id'] = Variable<String>(sessionId);
    if (!nullToAbsent || attemptId != null) {
      map['attempt_id'] = Variable<String>(attemptId);
    }
    if (!nullToAbsent || objectId != null) {
      map['object_id'] = Variable<String>(objectId);
    }
    map['review_status'] = Variable<String>(reviewStatus);
    if (!nullToAbsent || correctProductId != null) {
      map['correct_product_id'] = Variable<String>(correctProductId);
    }
    map['conclusion_code'] = Variable<String>(conclusionCode);
    map['reason_code'] = Variable<String>(reasonCode);
    if (!nullToAbsent || note != null) {
      map['note'] = Variable<String>(note);
    }
    map['author_label'] = Variable<String>(authorLabel);
    map['created_at_us'] = Variable<int>(createdAtUs);
    return map;
  }

  AdminReviewAnnotationsCompanion toCompanion(bool nullToAbsent) {
    return AdminReviewAnnotationsCompanion(
      annotationId: Value(annotationId),
      sessionId: Value(sessionId),
      attemptId: attemptId == null && nullToAbsent
          ? const Value.absent()
          : Value(attemptId),
      objectId: objectId == null && nullToAbsent
          ? const Value.absent()
          : Value(objectId),
      reviewStatus: Value(reviewStatus),
      correctProductId: correctProductId == null && nullToAbsent
          ? const Value.absent()
          : Value(correctProductId),
      conclusionCode: Value(conclusionCode),
      reasonCode: Value(reasonCode),
      note: note == null && nullToAbsent ? const Value.absent() : Value(note),
      authorLabel: Value(authorLabel),
      createdAtUs: Value(createdAtUs),
    );
  }

  factory AdminReviewAnnotationRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return AdminReviewAnnotationRow(
      annotationId: serializer.fromJson<String>(json['annotationId']),
      sessionId: serializer.fromJson<String>(json['sessionId']),
      attemptId: serializer.fromJson<String?>(json['attemptId']),
      objectId: serializer.fromJson<String?>(json['objectId']),
      reviewStatus: serializer.fromJson<String>(json['reviewStatus']),
      correctProductId: serializer.fromJson<String?>(json['correctProductId']),
      conclusionCode: serializer.fromJson<String>(json['conclusionCode']),
      reasonCode: serializer.fromJson<String>(json['reasonCode']),
      note: serializer.fromJson<String?>(json['note']),
      authorLabel: serializer.fromJson<String>(json['authorLabel']),
      createdAtUs: serializer.fromJson<int>(json['createdAtUs']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'annotationId': serializer.toJson<String>(annotationId),
      'sessionId': serializer.toJson<String>(sessionId),
      'attemptId': serializer.toJson<String?>(attemptId),
      'objectId': serializer.toJson<String?>(objectId),
      'reviewStatus': serializer.toJson<String>(reviewStatus),
      'correctProductId': serializer.toJson<String?>(correctProductId),
      'conclusionCode': serializer.toJson<String>(conclusionCode),
      'reasonCode': serializer.toJson<String>(reasonCode),
      'note': serializer.toJson<String?>(note),
      'authorLabel': serializer.toJson<String>(authorLabel),
      'createdAtUs': serializer.toJson<int>(createdAtUs),
    };
  }

  AdminReviewAnnotationRow copyWith({
    String? annotationId,
    String? sessionId,
    Value<String?> attemptId = const Value.absent(),
    Value<String?> objectId = const Value.absent(),
    String? reviewStatus,
    Value<String?> correctProductId = const Value.absent(),
    String? conclusionCode,
    String? reasonCode,
    Value<String?> note = const Value.absent(),
    String? authorLabel,
    int? createdAtUs,
  }) => AdminReviewAnnotationRow(
    annotationId: annotationId ?? this.annotationId,
    sessionId: sessionId ?? this.sessionId,
    attemptId: attemptId.present ? attemptId.value : this.attemptId,
    objectId: objectId.present ? objectId.value : this.objectId,
    reviewStatus: reviewStatus ?? this.reviewStatus,
    correctProductId: correctProductId.present
        ? correctProductId.value
        : this.correctProductId,
    conclusionCode: conclusionCode ?? this.conclusionCode,
    reasonCode: reasonCode ?? this.reasonCode,
    note: note.present ? note.value : this.note,
    authorLabel: authorLabel ?? this.authorLabel,
    createdAtUs: createdAtUs ?? this.createdAtUs,
  );
  AdminReviewAnnotationRow copyWithCompanion(
    AdminReviewAnnotationsCompanion data,
  ) {
    return AdminReviewAnnotationRow(
      annotationId: data.annotationId.present
          ? data.annotationId.value
          : this.annotationId,
      sessionId: data.sessionId.present ? data.sessionId.value : this.sessionId,
      attemptId: data.attemptId.present ? data.attemptId.value : this.attemptId,
      objectId: data.objectId.present ? data.objectId.value : this.objectId,
      reviewStatus: data.reviewStatus.present
          ? data.reviewStatus.value
          : this.reviewStatus,
      correctProductId: data.correctProductId.present
          ? data.correctProductId.value
          : this.correctProductId,
      conclusionCode: data.conclusionCode.present
          ? data.conclusionCode.value
          : this.conclusionCode,
      reasonCode: data.reasonCode.present
          ? data.reasonCode.value
          : this.reasonCode,
      note: data.note.present ? data.note.value : this.note,
      authorLabel: data.authorLabel.present
          ? data.authorLabel.value
          : this.authorLabel,
      createdAtUs: data.createdAtUs.present
          ? data.createdAtUs.value
          : this.createdAtUs,
    );
  }

  @override
  String toString() {
    return (StringBuffer('AdminReviewAnnotationRow(')
          ..write('annotationId: $annotationId, ')
          ..write('sessionId: $sessionId, ')
          ..write('attemptId: $attemptId, ')
          ..write('objectId: $objectId, ')
          ..write('reviewStatus: $reviewStatus, ')
          ..write('correctProductId: $correctProductId, ')
          ..write('conclusionCode: $conclusionCode, ')
          ..write('reasonCode: $reasonCode, ')
          ..write('note: $note, ')
          ..write('authorLabel: $authorLabel, ')
          ..write('createdAtUs: $createdAtUs')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    annotationId,
    sessionId,
    attemptId,
    objectId,
    reviewStatus,
    correctProductId,
    conclusionCode,
    reasonCode,
    note,
    authorLabel,
    createdAtUs,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is AdminReviewAnnotationRow &&
          other.annotationId == this.annotationId &&
          other.sessionId == this.sessionId &&
          other.attemptId == this.attemptId &&
          other.objectId == this.objectId &&
          other.reviewStatus == this.reviewStatus &&
          other.correctProductId == this.correctProductId &&
          other.conclusionCode == this.conclusionCode &&
          other.reasonCode == this.reasonCode &&
          other.note == this.note &&
          other.authorLabel == this.authorLabel &&
          other.createdAtUs == this.createdAtUs);
}

class AdminReviewAnnotationsCompanion
    extends UpdateCompanion<AdminReviewAnnotationRow> {
  final Value<String> annotationId;
  final Value<String> sessionId;
  final Value<String?> attemptId;
  final Value<String?> objectId;
  final Value<String> reviewStatus;
  final Value<String?> correctProductId;
  final Value<String> conclusionCode;
  final Value<String> reasonCode;
  final Value<String?> note;
  final Value<String> authorLabel;
  final Value<int> createdAtUs;
  final Value<int> rowid;
  const AdminReviewAnnotationsCompanion({
    this.annotationId = const Value.absent(),
    this.sessionId = const Value.absent(),
    this.attemptId = const Value.absent(),
    this.objectId = const Value.absent(),
    this.reviewStatus = const Value.absent(),
    this.correctProductId = const Value.absent(),
    this.conclusionCode = const Value.absent(),
    this.reasonCode = const Value.absent(),
    this.note = const Value.absent(),
    this.authorLabel = const Value.absent(),
    this.createdAtUs = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  AdminReviewAnnotationsCompanion.insert({
    required String annotationId,
    required String sessionId,
    this.attemptId = const Value.absent(),
    this.objectId = const Value.absent(),
    required String reviewStatus,
    this.correctProductId = const Value.absent(),
    this.conclusionCode = const Value.absent(),
    required String reasonCode,
    this.note = const Value.absent(),
    required String authorLabel,
    required int createdAtUs,
    this.rowid = const Value.absent(),
  }) : annotationId = Value(annotationId),
       sessionId = Value(sessionId),
       reviewStatus = Value(reviewStatus),
       reasonCode = Value(reasonCode),
       authorLabel = Value(authorLabel),
       createdAtUs = Value(createdAtUs);
  static Insertable<AdminReviewAnnotationRow> custom({
    Expression<String>? annotationId,
    Expression<String>? sessionId,
    Expression<String>? attemptId,
    Expression<String>? objectId,
    Expression<String>? reviewStatus,
    Expression<String>? correctProductId,
    Expression<String>? conclusionCode,
    Expression<String>? reasonCode,
    Expression<String>? note,
    Expression<String>? authorLabel,
    Expression<int>? createdAtUs,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (annotationId != null) 'annotation_id': annotationId,
      if (sessionId != null) 'session_id': sessionId,
      if (attemptId != null) 'attempt_id': attemptId,
      if (objectId != null) 'object_id': objectId,
      if (reviewStatus != null) 'review_status': reviewStatus,
      if (correctProductId != null) 'correct_product_id': correctProductId,
      if (conclusionCode != null) 'conclusion_code': conclusionCode,
      if (reasonCode != null) 'reason_code': reasonCode,
      if (note != null) 'note': note,
      if (authorLabel != null) 'author_label': authorLabel,
      if (createdAtUs != null) 'created_at_us': createdAtUs,
      if (rowid != null) 'rowid': rowid,
    });
  }

  AdminReviewAnnotationsCompanion copyWith({
    Value<String>? annotationId,
    Value<String>? sessionId,
    Value<String?>? attemptId,
    Value<String?>? objectId,
    Value<String>? reviewStatus,
    Value<String?>? correctProductId,
    Value<String>? conclusionCode,
    Value<String>? reasonCode,
    Value<String?>? note,
    Value<String>? authorLabel,
    Value<int>? createdAtUs,
    Value<int>? rowid,
  }) {
    return AdminReviewAnnotationsCompanion(
      annotationId: annotationId ?? this.annotationId,
      sessionId: sessionId ?? this.sessionId,
      attemptId: attemptId ?? this.attemptId,
      objectId: objectId ?? this.objectId,
      reviewStatus: reviewStatus ?? this.reviewStatus,
      correctProductId: correctProductId ?? this.correctProductId,
      conclusionCode: conclusionCode ?? this.conclusionCode,
      reasonCode: reasonCode ?? this.reasonCode,
      note: note ?? this.note,
      authorLabel: authorLabel ?? this.authorLabel,
      createdAtUs: createdAtUs ?? this.createdAtUs,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (annotationId.present) {
      map['annotation_id'] = Variable<String>(annotationId.value);
    }
    if (sessionId.present) {
      map['session_id'] = Variable<String>(sessionId.value);
    }
    if (attemptId.present) {
      map['attempt_id'] = Variable<String>(attemptId.value);
    }
    if (objectId.present) {
      map['object_id'] = Variable<String>(objectId.value);
    }
    if (reviewStatus.present) {
      map['review_status'] = Variable<String>(reviewStatus.value);
    }
    if (correctProductId.present) {
      map['correct_product_id'] = Variable<String>(correctProductId.value);
    }
    if (conclusionCode.present) {
      map['conclusion_code'] = Variable<String>(conclusionCode.value);
    }
    if (reasonCode.present) {
      map['reason_code'] = Variable<String>(reasonCode.value);
    }
    if (note.present) {
      map['note'] = Variable<String>(note.value);
    }
    if (authorLabel.present) {
      map['author_label'] = Variable<String>(authorLabel.value);
    }
    if (createdAtUs.present) {
      map['created_at_us'] = Variable<int>(createdAtUs.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('AdminReviewAnnotationsCompanion(')
          ..write('annotationId: $annotationId, ')
          ..write('sessionId: $sessionId, ')
          ..write('attemptId: $attemptId, ')
          ..write('objectId: $objectId, ')
          ..write('reviewStatus: $reviewStatus, ')
          ..write('correctProductId: $correctProductId, ')
          ..write('conclusionCode: $conclusionCode, ')
          ..write('reasonCode: $reasonCode, ')
          ..write('note: $note, ')
          ..write('authorLabel: $authorLabel, ')
          ..write('createdAtUs: $createdAtUs, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $SettingsRevisionEntriesTable extends SettingsRevisionEntries
    with TableInfo<$SettingsRevisionEntriesTable, SettingsRevisionEntryRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SettingsRevisionEntriesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _revisionIdMeta = const VerificationMeta(
    'revisionId',
  );
  @override
  late final GeneratedColumn<String> revisionId = GeneratedColumn<String>(
    'revision_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'REFERENCES settings_revisions (revision_id)',
    ),
  );
  static const VerificationMeta _settingKeyMeta = const VerificationMeta(
    'settingKey',
  );
  @override
  late final GeneratedColumn<String> settingKey = GeneratedColumn<String>(
    'setting_key',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _valueTypeMeta = const VerificationMeta(
    'valueType',
  );
  @override
  late final GeneratedColumn<String> valueType = GeneratedColumn<String>(
    'value_type',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _valueJsonMeta = const VerificationMeta(
    'valueJson',
  );
  @override
  late final GeneratedColumn<String> valueJson = GeneratedColumn<String>(
    'value_json',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _updatedAtUsMeta = const VerificationMeta(
    'updatedAtUs',
  );
  @override
  late final GeneratedColumn<int> updatedAtUs = GeneratedColumn<int>(
    'updated_at_us',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _authorLabelMeta = const VerificationMeta(
    'authorLabel',
  );
  @override
  late final GeneratedColumn<String> authorLabel = GeneratedColumn<String>(
    'author_label',
    aliasedName,
    false,
    additionalChecks: GeneratedColumn.checkTextLength(minTextLength: 1),
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    revisionId,
    settingKey,
    valueType,
    valueJson,
    updatedAtUs,
    authorLabel,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'settings_revision_entries';
  @override
  VerificationContext validateIntegrity(
    Insertable<SettingsRevisionEntryRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('revision_id')) {
      context.handle(
        _revisionIdMeta,
        revisionId.isAcceptableOrUnknown(data['revision_id']!, _revisionIdMeta),
      );
    } else if (isInserting) {
      context.missing(_revisionIdMeta);
    }
    if (data.containsKey('setting_key')) {
      context.handle(
        _settingKeyMeta,
        settingKey.isAcceptableOrUnknown(data['setting_key']!, _settingKeyMeta),
      );
    } else if (isInserting) {
      context.missing(_settingKeyMeta);
    }
    if (data.containsKey('value_type')) {
      context.handle(
        _valueTypeMeta,
        valueType.isAcceptableOrUnknown(data['value_type']!, _valueTypeMeta),
      );
    } else if (isInserting) {
      context.missing(_valueTypeMeta);
    }
    if (data.containsKey('value_json')) {
      context.handle(
        _valueJsonMeta,
        valueJson.isAcceptableOrUnknown(data['value_json']!, _valueJsonMeta),
      );
    } else if (isInserting) {
      context.missing(_valueJsonMeta);
    }
    if (data.containsKey('updated_at_us')) {
      context.handle(
        _updatedAtUsMeta,
        updatedAtUs.isAcceptableOrUnknown(
          data['updated_at_us']!,
          _updatedAtUsMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_updatedAtUsMeta);
    }
    if (data.containsKey('author_label')) {
      context.handle(
        _authorLabelMeta,
        authorLabel.isAcceptableOrUnknown(
          data['author_label']!,
          _authorLabelMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_authorLabelMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {revisionId, settingKey};
  @override
  SettingsRevisionEntryRow map(
    Map<String, dynamic> data, {
    String? tablePrefix,
  }) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SettingsRevisionEntryRow(
      revisionId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}revision_id'],
      )!,
      settingKey: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}setting_key'],
      )!,
      valueType: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}value_type'],
      )!,
      valueJson: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}value_json'],
      )!,
      updatedAtUs: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}updated_at_us'],
      )!,
      authorLabel: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}author_label'],
      )!,
    );
  }

  @override
  $SettingsRevisionEntriesTable createAlias(String alias) {
    return $SettingsRevisionEntriesTable(attachedDatabase, alias);
  }
}

class SettingsRevisionEntryRow extends DataClass
    implements Insertable<SettingsRevisionEntryRow> {
  final String revisionId;
  final String settingKey;
  final String valueType;
  final String valueJson;
  final int updatedAtUs;
  final String authorLabel;
  const SettingsRevisionEntryRow({
    required this.revisionId,
    required this.settingKey,
    required this.valueType,
    required this.valueJson,
    required this.updatedAtUs,
    required this.authorLabel,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['revision_id'] = Variable<String>(revisionId);
    map['setting_key'] = Variable<String>(settingKey);
    map['value_type'] = Variable<String>(valueType);
    map['value_json'] = Variable<String>(valueJson);
    map['updated_at_us'] = Variable<int>(updatedAtUs);
    map['author_label'] = Variable<String>(authorLabel);
    return map;
  }

  SettingsRevisionEntriesCompanion toCompanion(bool nullToAbsent) {
    return SettingsRevisionEntriesCompanion(
      revisionId: Value(revisionId),
      settingKey: Value(settingKey),
      valueType: Value(valueType),
      valueJson: Value(valueJson),
      updatedAtUs: Value(updatedAtUs),
      authorLabel: Value(authorLabel),
    );
  }

  factory SettingsRevisionEntryRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SettingsRevisionEntryRow(
      revisionId: serializer.fromJson<String>(json['revisionId']),
      settingKey: serializer.fromJson<String>(json['settingKey']),
      valueType: serializer.fromJson<String>(json['valueType']),
      valueJson: serializer.fromJson<String>(json['valueJson']),
      updatedAtUs: serializer.fromJson<int>(json['updatedAtUs']),
      authorLabel: serializer.fromJson<String>(json['authorLabel']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'revisionId': serializer.toJson<String>(revisionId),
      'settingKey': serializer.toJson<String>(settingKey),
      'valueType': serializer.toJson<String>(valueType),
      'valueJson': serializer.toJson<String>(valueJson),
      'updatedAtUs': serializer.toJson<int>(updatedAtUs),
      'authorLabel': serializer.toJson<String>(authorLabel),
    };
  }

  SettingsRevisionEntryRow copyWith({
    String? revisionId,
    String? settingKey,
    String? valueType,
    String? valueJson,
    int? updatedAtUs,
    String? authorLabel,
  }) => SettingsRevisionEntryRow(
    revisionId: revisionId ?? this.revisionId,
    settingKey: settingKey ?? this.settingKey,
    valueType: valueType ?? this.valueType,
    valueJson: valueJson ?? this.valueJson,
    updatedAtUs: updatedAtUs ?? this.updatedAtUs,
    authorLabel: authorLabel ?? this.authorLabel,
  );
  SettingsRevisionEntryRow copyWithCompanion(
    SettingsRevisionEntriesCompanion data,
  ) {
    return SettingsRevisionEntryRow(
      revisionId: data.revisionId.present
          ? data.revisionId.value
          : this.revisionId,
      settingKey: data.settingKey.present
          ? data.settingKey.value
          : this.settingKey,
      valueType: data.valueType.present ? data.valueType.value : this.valueType,
      valueJson: data.valueJson.present ? data.valueJson.value : this.valueJson,
      updatedAtUs: data.updatedAtUs.present
          ? data.updatedAtUs.value
          : this.updatedAtUs,
      authorLabel: data.authorLabel.present
          ? data.authorLabel.value
          : this.authorLabel,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SettingsRevisionEntryRow(')
          ..write('revisionId: $revisionId, ')
          ..write('settingKey: $settingKey, ')
          ..write('valueType: $valueType, ')
          ..write('valueJson: $valueJson, ')
          ..write('updatedAtUs: $updatedAtUs, ')
          ..write('authorLabel: $authorLabel')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    revisionId,
    settingKey,
    valueType,
    valueJson,
    updatedAtUs,
    authorLabel,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SettingsRevisionEntryRow &&
          other.revisionId == this.revisionId &&
          other.settingKey == this.settingKey &&
          other.valueType == this.valueType &&
          other.valueJson == this.valueJson &&
          other.updatedAtUs == this.updatedAtUs &&
          other.authorLabel == this.authorLabel);
}

class SettingsRevisionEntriesCompanion
    extends UpdateCompanion<SettingsRevisionEntryRow> {
  final Value<String> revisionId;
  final Value<String> settingKey;
  final Value<String> valueType;
  final Value<String> valueJson;
  final Value<int> updatedAtUs;
  final Value<String> authorLabel;
  final Value<int> rowid;
  const SettingsRevisionEntriesCompanion({
    this.revisionId = const Value.absent(),
    this.settingKey = const Value.absent(),
    this.valueType = const Value.absent(),
    this.valueJson = const Value.absent(),
    this.updatedAtUs = const Value.absent(),
    this.authorLabel = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SettingsRevisionEntriesCompanion.insert({
    required String revisionId,
    required String settingKey,
    required String valueType,
    required String valueJson,
    required int updatedAtUs,
    required String authorLabel,
    this.rowid = const Value.absent(),
  }) : revisionId = Value(revisionId),
       settingKey = Value(settingKey),
       valueType = Value(valueType),
       valueJson = Value(valueJson),
       updatedAtUs = Value(updatedAtUs),
       authorLabel = Value(authorLabel);
  static Insertable<SettingsRevisionEntryRow> custom({
    Expression<String>? revisionId,
    Expression<String>? settingKey,
    Expression<String>? valueType,
    Expression<String>? valueJson,
    Expression<int>? updatedAtUs,
    Expression<String>? authorLabel,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (revisionId != null) 'revision_id': revisionId,
      if (settingKey != null) 'setting_key': settingKey,
      if (valueType != null) 'value_type': valueType,
      if (valueJson != null) 'value_json': valueJson,
      if (updatedAtUs != null) 'updated_at_us': updatedAtUs,
      if (authorLabel != null) 'author_label': authorLabel,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SettingsRevisionEntriesCompanion copyWith({
    Value<String>? revisionId,
    Value<String>? settingKey,
    Value<String>? valueType,
    Value<String>? valueJson,
    Value<int>? updatedAtUs,
    Value<String>? authorLabel,
    Value<int>? rowid,
  }) {
    return SettingsRevisionEntriesCompanion(
      revisionId: revisionId ?? this.revisionId,
      settingKey: settingKey ?? this.settingKey,
      valueType: valueType ?? this.valueType,
      valueJson: valueJson ?? this.valueJson,
      updatedAtUs: updatedAtUs ?? this.updatedAtUs,
      authorLabel: authorLabel ?? this.authorLabel,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (revisionId.present) {
      map['revision_id'] = Variable<String>(revisionId.value);
    }
    if (settingKey.present) {
      map['setting_key'] = Variable<String>(settingKey.value);
    }
    if (valueType.present) {
      map['value_type'] = Variable<String>(valueType.value);
    }
    if (valueJson.present) {
      map['value_json'] = Variable<String>(valueJson.value);
    }
    if (updatedAtUs.present) {
      map['updated_at_us'] = Variable<int>(updatedAtUs.value);
    }
    if (authorLabel.present) {
      map['author_label'] = Variable<String>(authorLabel.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SettingsRevisionEntriesCompanion(')
          ..write('revisionId: $revisionId, ')
          ..write('settingKey: $settingKey, ')
          ..write('valueType: $valueType, ')
          ..write('valueJson: $valueJson, ')
          ..write('updatedAtUs: $updatedAtUs, ')
          ..write('authorLabel: $authorLabel, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$BakeryDatabase extends GeneratedDatabase {
  _$BakeryDatabase(QueryExecutor e) : super(e);
  $BakeryDatabaseManager get managers => $BakeryDatabaseManager(this);
  late final $CatalogRevisionsTable catalogRevisions = $CatalogRevisionsTable(
    this,
  );
  late final $ProductsTable products = $ProductsTable(this);
  late final $SettingsRevisionsTable settingsRevisions =
      $SettingsRevisionsTable(this);
  late final $CheckoutSessionsTable checkoutSessions = $CheckoutSessionsTable(
    this,
  );
  late final $ScanAttemptsTable scanAttempts = $ScanAttemptsTable(this);
  late final $InferenceObjectsTable inferenceObjects = $InferenceObjectsTable(
    this,
  );
  late final $InferenceCandidatesTable inferenceCandidates =
      $InferenceCandidatesTable(this);
  late final $ObjectResolutionsTable objectResolutions =
      $ObjectResolutionsTable(this);
  late final $DraftOrderLinesTable draftOrderLines = $DraftOrderLinesTable(
    this,
  );
  late final $FinalOrdersTable finalOrders = $FinalOrdersTable(this);
  late final $FinalOrderLinesTable finalOrderLines = $FinalOrderLinesTable(
    this,
  );
  late final $SimulatedPaymentsTable simulatedPayments =
      $SimulatedPaymentsTable(this);
  late final $AuditEventsTable auditEvents = $AuditEventsTable(this);
  late final $AppSettingsTable appSettings = $AppSettingsTable(this);
  late final $RetentionEventsTable retentionEvents = $RetentionEventsTable(
    this,
  );
  late final $AdminReviewAnnotationsTable adminReviewAnnotations =
      $AdminReviewAnnotationsTable(this);
  late final $SettingsRevisionEntriesTable settingsRevisionEntries =
      $SettingsRevisionEntriesTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    catalogRevisions,
    products,
    settingsRevisions,
    checkoutSessions,
    scanAttempts,
    inferenceObjects,
    inferenceCandidates,
    objectResolutions,
    draftOrderLines,
    finalOrders,
    finalOrderLines,
    simulatedPayments,
    auditEvents,
    appSettings,
    retentionEvents,
    adminReviewAnnotations,
    settingsRevisionEntries,
  ];
}

typedef $$CatalogRevisionsTableCreateCompanionBuilder =
    CatalogRevisionsCompanion Function({
      required String revisionId,
      required String sha256,
      required int createdAtUs,
      required bool isActive,
      Value<int> rowid,
    });
typedef $$CatalogRevisionsTableUpdateCompanionBuilder =
    CatalogRevisionsCompanion Function({
      Value<String> revisionId,
      Value<String> sha256,
      Value<int> createdAtUs,
      Value<bool> isActive,
      Value<int> rowid,
    });

final class $$CatalogRevisionsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $CatalogRevisionsTable,
          CatalogRevisionRow
        > {
  $$CatalogRevisionsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static MultiTypedResultKey<$ProductsTable, List<ProductRow>>
  _productsRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.products,
    aliasName: 'catalog_revisions__revision_id__products__catalog_revision_id',
  );

  $$ProductsTableProcessedTableManager get productsRefs {
    final manager = $$ProductsTableTableManager($_db, $_db.products).filter(
      (f) => f.catalogRevisionId.revisionId.sqlEquals(
        $_itemColumn<String>('revision_id')!,
      ),
    );

    final cache = $_typedResult.readTableOrNull(_productsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$CheckoutSessionsTable, List<CheckoutSessionRow>>
  _checkoutSessionsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.checkoutSessions,
    aliasName:
        'catalog_revisions__revision_id__checkout_sessions__catalog_revision_id',
  );

  $$CheckoutSessionsTableProcessedTableManager get checkoutSessionsRefs {
    final manager =
        $$CheckoutSessionsTableTableManager($_db, $_db.checkoutSessions).filter(
          (f) => f.catalogRevisionId.revisionId.sqlEquals(
            $_itemColumn<String>('revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _checkoutSessionsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$FinalOrdersTable, List<FinalOrderRow>>
  _finalOrdersRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.finalOrders,
    aliasName:
        'catalog_revisions__revision_id__final_orders__catalog_revision_id',
  );

  $$FinalOrdersTableProcessedTableManager get finalOrdersRefs {
    final manager = $$FinalOrdersTableTableManager($_db, $_db.finalOrders)
        .filter(
          (f) => f.catalogRevisionId.revisionId.sqlEquals(
            $_itemColumn<String>('revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(_finalOrdersRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$CatalogRevisionsTableFilterComposer
    extends Composer<_$BakeryDatabase, $CatalogRevisionsTable> {
  $$CatalogRevisionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isActive => $composableBuilder(
    column: $table.isActive,
    builder: (column) => ColumnFilters(column),
  );

  Expression<bool> productsRefs(
    Expression<bool> Function($$ProductsTableFilterComposer f) f,
  ) {
    final $$ProductsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableFilterComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> checkoutSessionsRefs(
    Expression<bool> Function($$CheckoutSessionsTableFilterComposer f) f,
  ) {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> finalOrdersRefs(
    Expression<bool> Function($$FinalOrdersTableFilterComposer f) f,
  ) {
    final $$FinalOrdersTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableFilterComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$CatalogRevisionsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $CatalogRevisionsTable> {
  $$CatalogRevisionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isActive => $composableBuilder(
    column: $table.isActive,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$CatalogRevisionsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $CatalogRevisionsTable> {
  $$CatalogRevisionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get sha256 =>
      $composableBuilder(column: $table.sha256, builder: (column) => column);

  GeneratedColumn<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get isActive =>
      $composableBuilder(column: $table.isActive, builder: (column) => column);

  Expression<T> productsRefs<T extends Object>(
    Expression<T> Function($$ProductsTableAnnotationComposer a) f,
  ) {
    final $$ProductsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableAnnotationComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> checkoutSessionsRefs<T extends Object>(
    Expression<T> Function($$CheckoutSessionsTableAnnotationComposer a) f,
  ) {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> finalOrdersRefs<T extends Object>(
    Expression<T> Function($$FinalOrdersTableAnnotationComposer a) f,
  ) {
    final $$FinalOrdersTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.catalogRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$CatalogRevisionsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $CatalogRevisionsTable,
          CatalogRevisionRow,
          $$CatalogRevisionsTableFilterComposer,
          $$CatalogRevisionsTableOrderingComposer,
          $$CatalogRevisionsTableAnnotationComposer,
          $$CatalogRevisionsTableCreateCompanionBuilder,
          $$CatalogRevisionsTableUpdateCompanionBuilder,
          (CatalogRevisionRow, $$CatalogRevisionsTableReferences),
          CatalogRevisionRow,
          PrefetchHooks Function({
            bool productsRefs,
            bool checkoutSessionsRefs,
            bool finalOrdersRefs,
          })
        > {
  $$CatalogRevisionsTableTableManager(
    _$BakeryDatabase db,
    $CatalogRevisionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CatalogRevisionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CatalogRevisionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CatalogRevisionsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> revisionId = const Value.absent(),
                Value<String> sha256 = const Value.absent(),
                Value<int> createdAtUs = const Value.absent(),
                Value<bool> isActive = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CatalogRevisionsCompanion(
                revisionId: revisionId,
                sha256: sha256,
                createdAtUs: createdAtUs,
                isActive: isActive,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String revisionId,
                required String sha256,
                required int createdAtUs,
                required bool isActive,
                Value<int> rowid = const Value.absent(),
              }) => CatalogRevisionsCompanion.insert(
                revisionId: revisionId,
                sha256: sha256,
                createdAtUs: createdAtUs,
                isActive: isActive,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$CatalogRevisionsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                productsRefs = false,
                checkoutSessionsRefs = false,
                finalOrdersRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (productsRefs) db.products,
                    if (checkoutSessionsRefs) db.checkoutSessions,
                    if (finalOrdersRefs) db.finalOrders,
                  ],
                  addJoins: null,
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (productsRefs)
                        await $_getPrefetchedData<
                          CatalogRevisionRow,
                          $CatalogRevisionsTable,
                          ProductRow
                        >(
                          currentTable: table,
                          referencedTable: $$CatalogRevisionsTableReferences
                              ._productsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CatalogRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).productsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.catalogRevisionId == item.revisionId,
                              ),
                          typedResults: items,
                        ),
                      if (checkoutSessionsRefs)
                        await $_getPrefetchedData<
                          CatalogRevisionRow,
                          $CatalogRevisionsTable,
                          CheckoutSessionRow
                        >(
                          currentTable: table,
                          referencedTable: $$CatalogRevisionsTableReferences
                              ._checkoutSessionsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CatalogRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).checkoutSessionsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.catalogRevisionId == item.revisionId,
                              ),
                          typedResults: items,
                        ),
                      if (finalOrdersRefs)
                        await $_getPrefetchedData<
                          CatalogRevisionRow,
                          $CatalogRevisionsTable,
                          FinalOrderRow
                        >(
                          currentTable: table,
                          referencedTable: $$CatalogRevisionsTableReferences
                              ._finalOrdersRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CatalogRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).finalOrdersRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.catalogRevisionId == item.revisionId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$CatalogRevisionsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $CatalogRevisionsTable,
      CatalogRevisionRow,
      $$CatalogRevisionsTableFilterComposer,
      $$CatalogRevisionsTableOrderingComposer,
      $$CatalogRevisionsTableAnnotationComposer,
      $$CatalogRevisionsTableCreateCompanionBuilder,
      $$CatalogRevisionsTableUpdateCompanionBuilder,
      (CatalogRevisionRow, $$CatalogRevisionsTableReferences),
      CatalogRevisionRow,
      PrefetchHooks Function({
        bool productsRefs,
        bool checkoutSessionsRefs,
        bool finalOrdersRefs,
      })
    >;
typedef $$ProductsTableCreateCompanionBuilder =
    ProductsCompanion Function({
      required String productRevisionId,
      required String catalogRevisionId,
      required String productId,
      required String displayName,
      required int unitPriceKrw,
      Value<int?> recognitionSkuId,
      required String categoryId,
      Value<String?> photoRelativePath,
      Value<int?> photoByteSize,
      Value<String?> photoSha256,
      Value<String?> photoMediaType,
      Value<String?> photoProvenanceNote,
      required bool active,
      required int sortOrder,
      Value<int> rowid,
    });
typedef $$ProductsTableUpdateCompanionBuilder =
    ProductsCompanion Function({
      Value<String> productRevisionId,
      Value<String> catalogRevisionId,
      Value<String> productId,
      Value<String> displayName,
      Value<int> unitPriceKrw,
      Value<int?> recognitionSkuId,
      Value<String> categoryId,
      Value<String?> photoRelativePath,
      Value<int?> photoByteSize,
      Value<String?> photoSha256,
      Value<String?> photoMediaType,
      Value<String?> photoProvenanceNote,
      Value<bool> active,
      Value<int> sortOrder,
      Value<int> rowid,
    });

final class $$ProductsTableReferences
    extends BaseReferences<_$BakeryDatabase, $ProductsTable, ProductRow> {
  $$ProductsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $CatalogRevisionsTable _catalogRevisionIdTable(_$BakeryDatabase db) =>
      db.catalogRevisions.createAlias(
        'products__catalog_revision_id__catalog_revisions__revision_id',
      );

  $$CatalogRevisionsTableProcessedTableManager get catalogRevisionId {
    final $_column = $_itemColumn<String>('catalog_revision_id')!;

    final manager = $$CatalogRevisionsTableTableManager(
      $_db,
      $_db.catalogRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_catalogRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$ObjectResolutionsTable, List<ObjectResolutionRow>>
  _objectResolutionsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.objectResolutions,
    aliasName:
        'products__product_revision_id__object_resolutions__product_revision_id',
  );

  $$ObjectResolutionsTableProcessedTableManager get objectResolutionsRefs {
    final manager =
        $$ObjectResolutionsTableTableManager(
          $_db,
          $_db.objectResolutions,
        ).filter(
          (f) => f.productRevisionId.productRevisionId.sqlEquals(
            $_itemColumn<String>('product_revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _objectResolutionsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$DraftOrderLinesTable, List<DraftOrderLineRow>>
  _draftOrderLinesRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.draftOrderLines,
    aliasName:
        'products__product_revision_id__draft_order_lines__product_revision_id',
  );

  $$DraftOrderLinesTableProcessedTableManager get draftOrderLinesRefs {
    final manager =
        $$DraftOrderLinesTableTableManager($_db, $_db.draftOrderLines).filter(
          (f) => f.productRevisionId.productRevisionId.sqlEquals(
            $_itemColumn<String>('product_revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _draftOrderLinesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$FinalOrderLinesTable, List<FinalOrderLineRow>>
  _finalOrderLinesRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.finalOrderLines,
    aliasName:
        'products__product_revision_id__final_order_lines__product_revision_id',
  );

  $$FinalOrderLinesTableProcessedTableManager get finalOrderLinesRefs {
    final manager =
        $$FinalOrderLinesTableTableManager($_db, $_db.finalOrderLines).filter(
          (f) => f.productRevisionId.productRevisionId.sqlEquals(
            $_itemColumn<String>('product_revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _finalOrderLinesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$ProductsTableFilterComposer
    extends Composer<_$BakeryDatabase, $ProductsTable> {
  $$ProductsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get productRevisionId => $composableBuilder(
    column: $table.productRevisionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get displayName => $composableBuilder(
    column: $table.displayName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get photoRelativePath => $composableBuilder(
    column: $table.photoRelativePath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get photoByteSize => $composableBuilder(
    column: $table.photoByteSize,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get photoSha256 => $composableBuilder(
    column: $table.photoSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get photoMediaType => $composableBuilder(
    column: $table.photoMediaType,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get photoProvenanceNote => $composableBuilder(
    column: $table.photoProvenanceNote,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get active => $composableBuilder(
    column: $table.active,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get sortOrder => $composableBuilder(
    column: $table.sortOrder,
    builder: (column) => ColumnFilters(column),
  );

  $$CatalogRevisionsTableFilterComposer get catalogRevisionId {
    final $$CatalogRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> objectResolutionsRefs(
    Expression<bool> Function($$ObjectResolutionsTableFilterComposer f) f,
  ) {
    final $$ObjectResolutionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.objectResolutions,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ObjectResolutionsTableFilterComposer(
            $db: $db,
            $table: $db.objectResolutions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> draftOrderLinesRefs(
    Expression<bool> Function($$DraftOrderLinesTableFilterComposer f) f,
  ) {
    final $$DraftOrderLinesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.draftOrderLines,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$DraftOrderLinesTableFilterComposer(
            $db: $db,
            $table: $db.draftOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> finalOrderLinesRefs(
    Expression<bool> Function($$FinalOrderLinesTableFilterComposer f) f,
  ) {
    final $$FinalOrderLinesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.finalOrderLines,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrderLinesTableFilterComposer(
            $db: $db,
            $table: $db.finalOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$ProductsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $ProductsTable> {
  $$ProductsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get productRevisionId => $composableBuilder(
    column: $table.productRevisionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get displayName => $composableBuilder(
    column: $table.displayName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get photoRelativePath => $composableBuilder(
    column: $table.photoRelativePath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get photoByteSize => $composableBuilder(
    column: $table.photoByteSize,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get photoSha256 => $composableBuilder(
    column: $table.photoSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get photoMediaType => $composableBuilder(
    column: $table.photoMediaType,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get photoProvenanceNote => $composableBuilder(
    column: $table.photoProvenanceNote,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get active => $composableBuilder(
    column: $table.active,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get sortOrder => $composableBuilder(
    column: $table.sortOrder,
    builder: (column) => ColumnOrderings(column),
  );

  $$CatalogRevisionsTableOrderingComposer get catalogRevisionId {
    final $$CatalogRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ProductsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $ProductsTable> {
  $$ProductsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get productRevisionId => $composableBuilder(
    column: $table.productRevisionId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productId =>
      $composableBuilder(column: $table.productId, builder: (column) => column);

  GeneratedColumn<String> get displayName => $composableBuilder(
    column: $table.displayName,
    builder: (column) => column,
  );

  GeneratedColumn<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => column,
  );

  GeneratedColumn<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get categoryId => $composableBuilder(
    column: $table.categoryId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get photoRelativePath => $composableBuilder(
    column: $table.photoRelativePath,
    builder: (column) => column,
  );

  GeneratedColumn<int> get photoByteSize => $composableBuilder(
    column: $table.photoByteSize,
    builder: (column) => column,
  );

  GeneratedColumn<String> get photoSha256 => $composableBuilder(
    column: $table.photoSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get photoMediaType => $composableBuilder(
    column: $table.photoMediaType,
    builder: (column) => column,
  );

  GeneratedColumn<String> get photoProvenanceNote => $composableBuilder(
    column: $table.photoProvenanceNote,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get active =>
      $composableBuilder(column: $table.active, builder: (column) => column);

  GeneratedColumn<int> get sortOrder =>
      $composableBuilder(column: $table.sortOrder, builder: (column) => column);

  $$CatalogRevisionsTableAnnotationComposer get catalogRevisionId {
    final $$CatalogRevisionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableAnnotationComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<T> objectResolutionsRefs<T extends Object>(
    Expression<T> Function($$ObjectResolutionsTableAnnotationComposer a) f,
  ) {
    final $$ObjectResolutionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.productRevisionId,
          referencedTable: $db.objectResolutions,
          getReferencedColumn: (t) => t.productRevisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$ObjectResolutionsTableAnnotationComposer(
                $db: $db,
                $table: $db.objectResolutions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> draftOrderLinesRefs<T extends Object>(
    Expression<T> Function($$DraftOrderLinesTableAnnotationComposer a) f,
  ) {
    final $$DraftOrderLinesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.draftOrderLines,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$DraftOrderLinesTableAnnotationComposer(
            $db: $db,
            $table: $db.draftOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> finalOrderLinesRefs<T extends Object>(
    Expression<T> Function($$FinalOrderLinesTableAnnotationComposer a) f,
  ) {
    final $$FinalOrderLinesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.finalOrderLines,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrderLinesTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$ProductsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $ProductsTable,
          ProductRow,
          $$ProductsTableFilterComposer,
          $$ProductsTableOrderingComposer,
          $$ProductsTableAnnotationComposer,
          $$ProductsTableCreateCompanionBuilder,
          $$ProductsTableUpdateCompanionBuilder,
          (ProductRow, $$ProductsTableReferences),
          ProductRow,
          PrefetchHooks Function({
            bool catalogRevisionId,
            bool objectResolutionsRefs,
            bool draftOrderLinesRefs,
            bool finalOrderLinesRefs,
          })
        > {
  $$ProductsTableTableManager(_$BakeryDatabase db, $ProductsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ProductsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ProductsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ProductsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> productRevisionId = const Value.absent(),
                Value<String> catalogRevisionId = const Value.absent(),
                Value<String> productId = const Value.absent(),
                Value<String> displayName = const Value.absent(),
                Value<int> unitPriceKrw = const Value.absent(),
                Value<int?> recognitionSkuId = const Value.absent(),
                Value<String> categoryId = const Value.absent(),
                Value<String?> photoRelativePath = const Value.absent(),
                Value<int?> photoByteSize = const Value.absent(),
                Value<String?> photoSha256 = const Value.absent(),
                Value<String?> photoMediaType = const Value.absent(),
                Value<String?> photoProvenanceNote = const Value.absent(),
                Value<bool> active = const Value.absent(),
                Value<int> sortOrder = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ProductsCompanion(
                productRevisionId: productRevisionId,
                catalogRevisionId: catalogRevisionId,
                productId: productId,
                displayName: displayName,
                unitPriceKrw: unitPriceKrw,
                recognitionSkuId: recognitionSkuId,
                categoryId: categoryId,
                photoRelativePath: photoRelativePath,
                photoByteSize: photoByteSize,
                photoSha256: photoSha256,
                photoMediaType: photoMediaType,
                photoProvenanceNote: photoProvenanceNote,
                active: active,
                sortOrder: sortOrder,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String productRevisionId,
                required String catalogRevisionId,
                required String productId,
                required String displayName,
                required int unitPriceKrw,
                Value<int?> recognitionSkuId = const Value.absent(),
                required String categoryId,
                Value<String?> photoRelativePath = const Value.absent(),
                Value<int?> photoByteSize = const Value.absent(),
                Value<String?> photoSha256 = const Value.absent(),
                Value<String?> photoMediaType = const Value.absent(),
                Value<String?> photoProvenanceNote = const Value.absent(),
                required bool active,
                required int sortOrder,
                Value<int> rowid = const Value.absent(),
              }) => ProductsCompanion.insert(
                productRevisionId: productRevisionId,
                catalogRevisionId: catalogRevisionId,
                productId: productId,
                displayName: displayName,
                unitPriceKrw: unitPriceKrw,
                recognitionSkuId: recognitionSkuId,
                categoryId: categoryId,
                photoRelativePath: photoRelativePath,
                photoByteSize: photoByteSize,
                photoSha256: photoSha256,
                photoMediaType: photoMediaType,
                photoProvenanceNote: photoProvenanceNote,
                active: active,
                sortOrder: sortOrder,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$ProductsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                catalogRevisionId = false,
                objectResolutionsRefs = false,
                draftOrderLinesRefs = false,
                finalOrderLinesRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (objectResolutionsRefs) db.objectResolutions,
                    if (draftOrderLinesRefs) db.draftOrderLines,
                    if (finalOrderLinesRefs) db.finalOrderLines,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (catalogRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.catalogRevisionId,
                                    referencedTable: $$ProductsTableReferences
                                        ._catalogRevisionIdTable(db),
                                    referencedColumn: $$ProductsTableReferences
                                        ._catalogRevisionIdTable(db)
                                        .revisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (objectResolutionsRefs)
                        await $_getPrefetchedData<
                          ProductRow,
                          $ProductsTable,
                          ObjectResolutionRow
                        >(
                          currentTable: table,
                          referencedTable: $$ProductsTableReferences
                              ._objectResolutionsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ProductsTableReferences(
                                db,
                                table,
                                p0,
                              ).objectResolutionsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.productRevisionId ==
                                    item.productRevisionId,
                              ),
                          typedResults: items,
                        ),
                      if (draftOrderLinesRefs)
                        await $_getPrefetchedData<
                          ProductRow,
                          $ProductsTable,
                          DraftOrderLineRow
                        >(
                          currentTable: table,
                          referencedTable: $$ProductsTableReferences
                              ._draftOrderLinesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ProductsTableReferences(
                                db,
                                table,
                                p0,
                              ).draftOrderLinesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.productRevisionId ==
                                    item.productRevisionId,
                              ),
                          typedResults: items,
                        ),
                      if (finalOrderLinesRefs)
                        await $_getPrefetchedData<
                          ProductRow,
                          $ProductsTable,
                          FinalOrderLineRow
                        >(
                          currentTable: table,
                          referencedTable: $$ProductsTableReferences
                              ._finalOrderLinesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ProductsTableReferences(
                                db,
                                table,
                                p0,
                              ).finalOrderLinesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.productRevisionId ==
                                    item.productRevisionId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$ProductsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $ProductsTable,
      ProductRow,
      $$ProductsTableFilterComposer,
      $$ProductsTableOrderingComposer,
      $$ProductsTableAnnotationComposer,
      $$ProductsTableCreateCompanionBuilder,
      $$ProductsTableUpdateCompanionBuilder,
      (ProductRow, $$ProductsTableReferences),
      ProductRow,
      PrefetchHooks Function({
        bool catalogRevisionId,
        bool objectResolutionsRefs,
        bool draftOrderLinesRefs,
        bool finalOrderLinesRefs,
      })
    >;
typedef $$SettingsRevisionsTableCreateCompanionBuilder =
    SettingsRevisionsCompanion Function({
      required String revisionId,
      required int createdAtUs,
      required int retryLimit,
      required int paymentCompleteDurationSeconds,
      required bool customerAutoReset,
      required int evidenceRetentionDays,
      required String locale,
      required String kioskDisplayName,
      required String adminAuthorLabel,
      Value<int> rowid,
    });
typedef $$SettingsRevisionsTableUpdateCompanionBuilder =
    SettingsRevisionsCompanion Function({
      Value<String> revisionId,
      Value<int> createdAtUs,
      Value<int> retryLimit,
      Value<int> paymentCompleteDurationSeconds,
      Value<bool> customerAutoReset,
      Value<int> evidenceRetentionDays,
      Value<String> locale,
      Value<String> kioskDisplayName,
      Value<String> adminAuthorLabel,
      Value<int> rowid,
    });

final class $$SettingsRevisionsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $SettingsRevisionsTable,
          SettingsRevisionRow
        > {
  $$SettingsRevisionsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static MultiTypedResultKey<$CheckoutSessionsTable, List<CheckoutSessionRow>>
  _checkoutSessionsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.checkoutSessions,
    aliasName:
        'settings_revisions__revision_id__checkout_sessions__settings_revision_id',
  );

  $$CheckoutSessionsTableProcessedTableManager get checkoutSessionsRefs {
    final manager =
        $$CheckoutSessionsTableTableManager($_db, $_db.checkoutSessions).filter(
          (f) => f.settingsRevisionId.revisionId.sqlEquals(
            $_itemColumn<String>('revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _checkoutSessionsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$AppSettingsTable, List<AppSettingsRow>>
  _appSettingsRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.appSettings,
    aliasName:
        'settings_revisions__revision_id__app_settings__active_settings_revision_id',
  );

  $$AppSettingsTableProcessedTableManager get appSettingsRefs {
    final manager = $$AppSettingsTableTableManager($_db, $_db.appSettings)
        .filter(
          (f) => f.activeSettingsRevisionId.revisionId.sqlEquals(
            $_itemColumn<String>('revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(_appSettingsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<
    $SettingsRevisionEntriesTable,
    List<SettingsRevisionEntryRow>
  >
  _settingsRevisionEntriesRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.settingsRevisionEntries,
    aliasName:
        'settings_revisions__revision_id__settings_revision_entries__revision_id',
  );

  $$SettingsRevisionEntriesTableProcessedTableManager
  get settingsRevisionEntriesRefs {
    final manager =
        $$SettingsRevisionEntriesTableTableManager(
          $_db,
          $_db.settingsRevisionEntries,
        ).filter(
          (f) => f.revisionId.revisionId.sqlEquals(
            $_itemColumn<String>('revision_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _settingsRevisionEntriesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$SettingsRevisionsTableFilterComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionsTable> {
  $$SettingsRevisionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get retryLimit => $composableBuilder(
    column: $table.retryLimit,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get paymentCompleteDurationSeconds => $composableBuilder(
    column: $table.paymentCompleteDurationSeconds,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get customerAutoReset => $composableBuilder(
    column: $table.customerAutoReset,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get evidenceRetentionDays => $composableBuilder(
    column: $table.evidenceRetentionDays,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get locale => $composableBuilder(
    column: $table.locale,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get kioskDisplayName => $composableBuilder(
    column: $table.kioskDisplayName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get adminAuthorLabel => $composableBuilder(
    column: $table.adminAuthorLabel,
    builder: (column) => ColumnFilters(column),
  );

  Expression<bool> checkoutSessionsRefs(
    Expression<bool> Function($$CheckoutSessionsTableFilterComposer f) f,
  ) {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.settingsRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> appSettingsRefs(
    Expression<bool> Function($$AppSettingsTableFilterComposer f) f,
  ) {
    final $$AppSettingsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.appSettings,
      getReferencedColumn: (t) => t.activeSettingsRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$AppSettingsTableFilterComposer(
            $db: $db,
            $table: $db.appSettings,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> settingsRevisionEntriesRefs(
    Expression<bool> Function($$SettingsRevisionEntriesTableFilterComposer f) f,
  ) {
    final $$SettingsRevisionEntriesTableFilterComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.revisionId,
          referencedTable: $db.settingsRevisionEntries,
          getReferencedColumn: (t) => t.revisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SettingsRevisionEntriesTableFilterComposer(
                $db: $db,
                $table: $db.settingsRevisionEntries,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$SettingsRevisionsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionsTable> {
  $$SettingsRevisionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get retryLimit => $composableBuilder(
    column: $table.retryLimit,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get paymentCompleteDurationSeconds => $composableBuilder(
    column: $table.paymentCompleteDurationSeconds,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get customerAutoReset => $composableBuilder(
    column: $table.customerAutoReset,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get evidenceRetentionDays => $composableBuilder(
    column: $table.evidenceRetentionDays,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get locale => $composableBuilder(
    column: $table.locale,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get kioskDisplayName => $composableBuilder(
    column: $table.kioskDisplayName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get adminAuthorLabel => $composableBuilder(
    column: $table.adminAuthorLabel,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SettingsRevisionsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionsTable> {
  $$SettingsRevisionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get revisionId => $composableBuilder(
    column: $table.revisionId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<int> get retryLimit => $composableBuilder(
    column: $table.retryLimit,
    builder: (column) => column,
  );

  GeneratedColumn<int> get paymentCompleteDurationSeconds => $composableBuilder(
    column: $table.paymentCompleteDurationSeconds,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get customerAutoReset => $composableBuilder(
    column: $table.customerAutoReset,
    builder: (column) => column,
  );

  GeneratedColumn<int> get evidenceRetentionDays => $composableBuilder(
    column: $table.evidenceRetentionDays,
    builder: (column) => column,
  );

  GeneratedColumn<String> get locale =>
      $composableBuilder(column: $table.locale, builder: (column) => column);

  GeneratedColumn<String> get kioskDisplayName => $composableBuilder(
    column: $table.kioskDisplayName,
    builder: (column) => column,
  );

  GeneratedColumn<String> get adminAuthorLabel => $composableBuilder(
    column: $table.adminAuthorLabel,
    builder: (column) => column,
  );

  Expression<T> checkoutSessionsRefs<T extends Object>(
    Expression<T> Function($$CheckoutSessionsTableAnnotationComposer a) f,
  ) {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.settingsRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> appSettingsRefs<T extends Object>(
    Expression<T> Function($$AppSettingsTableAnnotationComposer a) f,
  ) {
    final $$AppSettingsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.appSettings,
      getReferencedColumn: (t) => t.activeSettingsRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$AppSettingsTableAnnotationComposer(
            $db: $db,
            $table: $db.appSettings,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> settingsRevisionEntriesRefs<T extends Object>(
    Expression<T> Function($$SettingsRevisionEntriesTableAnnotationComposer a)
    f,
  ) {
    final $$SettingsRevisionEntriesTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.revisionId,
          referencedTable: $db.settingsRevisionEntries,
          getReferencedColumn: (t) => t.revisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SettingsRevisionEntriesTableAnnotationComposer(
                $db: $db,
                $table: $db.settingsRevisionEntries,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$SettingsRevisionsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $SettingsRevisionsTable,
          SettingsRevisionRow,
          $$SettingsRevisionsTableFilterComposer,
          $$SettingsRevisionsTableOrderingComposer,
          $$SettingsRevisionsTableAnnotationComposer,
          $$SettingsRevisionsTableCreateCompanionBuilder,
          $$SettingsRevisionsTableUpdateCompanionBuilder,
          (SettingsRevisionRow, $$SettingsRevisionsTableReferences),
          SettingsRevisionRow,
          PrefetchHooks Function({
            bool checkoutSessionsRefs,
            bool appSettingsRefs,
            bool settingsRevisionEntriesRefs,
          })
        > {
  $$SettingsRevisionsTableTableManager(
    _$BakeryDatabase db,
    $SettingsRevisionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SettingsRevisionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SettingsRevisionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SettingsRevisionsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> revisionId = const Value.absent(),
                Value<int> createdAtUs = const Value.absent(),
                Value<int> retryLimit = const Value.absent(),
                Value<int> paymentCompleteDurationSeconds =
                    const Value.absent(),
                Value<bool> customerAutoReset = const Value.absent(),
                Value<int> evidenceRetentionDays = const Value.absent(),
                Value<String> locale = const Value.absent(),
                Value<String> kioskDisplayName = const Value.absent(),
                Value<String> adminAuthorLabel = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => SettingsRevisionsCompanion(
                revisionId: revisionId,
                createdAtUs: createdAtUs,
                retryLimit: retryLimit,
                paymentCompleteDurationSeconds: paymentCompleteDurationSeconds,
                customerAutoReset: customerAutoReset,
                evidenceRetentionDays: evidenceRetentionDays,
                locale: locale,
                kioskDisplayName: kioskDisplayName,
                adminAuthorLabel: adminAuthorLabel,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String revisionId,
                required int createdAtUs,
                required int retryLimit,
                required int paymentCompleteDurationSeconds,
                required bool customerAutoReset,
                required int evidenceRetentionDays,
                required String locale,
                required String kioskDisplayName,
                required String adminAuthorLabel,
                Value<int> rowid = const Value.absent(),
              }) => SettingsRevisionsCompanion.insert(
                revisionId: revisionId,
                createdAtUs: createdAtUs,
                retryLimit: retryLimit,
                paymentCompleteDurationSeconds: paymentCompleteDurationSeconds,
                customerAutoReset: customerAutoReset,
                evidenceRetentionDays: evidenceRetentionDays,
                locale: locale,
                kioskDisplayName: kioskDisplayName,
                adminAuthorLabel: adminAuthorLabel,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$SettingsRevisionsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                checkoutSessionsRefs = false,
                appSettingsRefs = false,
                settingsRevisionEntriesRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (checkoutSessionsRefs) db.checkoutSessions,
                    if (appSettingsRefs) db.appSettings,
                    if (settingsRevisionEntriesRefs) db.settingsRevisionEntries,
                  ],
                  addJoins: null,
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (checkoutSessionsRefs)
                        await $_getPrefetchedData<
                          SettingsRevisionRow,
                          $SettingsRevisionsTable,
                          CheckoutSessionRow
                        >(
                          currentTable: table,
                          referencedTable: $$SettingsRevisionsTableReferences
                              ._checkoutSessionsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$SettingsRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).checkoutSessionsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.settingsRevisionId == item.revisionId,
                              ),
                          typedResults: items,
                        ),
                      if (appSettingsRefs)
                        await $_getPrefetchedData<
                          SettingsRevisionRow,
                          $SettingsRevisionsTable,
                          AppSettingsRow
                        >(
                          currentTable: table,
                          referencedTable: $$SettingsRevisionsTableReferences
                              ._appSettingsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$SettingsRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).appSettingsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.activeSettingsRevisionId ==
                                    item.revisionId,
                              ),
                          typedResults: items,
                        ),
                      if (settingsRevisionEntriesRefs)
                        await $_getPrefetchedData<
                          SettingsRevisionRow,
                          $SettingsRevisionsTable,
                          SettingsRevisionEntryRow
                        >(
                          currentTable: table,
                          referencedTable: $$SettingsRevisionsTableReferences
                              ._settingsRevisionEntriesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$SettingsRevisionsTableReferences(
                                db,
                                table,
                                p0,
                              ).settingsRevisionEntriesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.revisionId == item.revisionId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$SettingsRevisionsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $SettingsRevisionsTable,
      SettingsRevisionRow,
      $$SettingsRevisionsTableFilterComposer,
      $$SettingsRevisionsTableOrderingComposer,
      $$SettingsRevisionsTableAnnotationComposer,
      $$SettingsRevisionsTableCreateCompanionBuilder,
      $$SettingsRevisionsTableUpdateCompanionBuilder,
      (SettingsRevisionRow, $$SettingsRevisionsTableReferences),
      SettingsRevisionRow,
      PrefetchHooks Function({
        bool checkoutSessionsRefs,
        bool appSettingsRefs,
        bool settingsRevisionEntriesRefs,
      })
    >;
typedef $$CheckoutSessionsTableCreateCompanionBuilder =
    CheckoutSessionsCompanion Function({
      required String sessionId,
      required String state,
      required int startedAtUs,
      Value<int?> terminalAtUs,
      Value<String?> terminalReason,
      required String catalogRevisionId,
      required String settingsRevisionId,
      required String detectorId,
      required String detectorSha256,
      required String repvitArtifactId,
      required String repvitSha256,
      required String repvitManifestSha256,
      required String repvitPrototypeSha256,
      required String dinov3ArtifactId,
      required String dinov3Sha256,
      required String dinov3SupportSha256,
      required String calibrationId,
      required String calibrationSha256,
      required String preprocessSha256,
      required String fusionPolicyId,
      required String fusionPolicySha256,
      required String configSnapshotJson,
      Value<int> rowid,
    });
typedef $$CheckoutSessionsTableUpdateCompanionBuilder =
    CheckoutSessionsCompanion Function({
      Value<String> sessionId,
      Value<String> state,
      Value<int> startedAtUs,
      Value<int?> terminalAtUs,
      Value<String?> terminalReason,
      Value<String> catalogRevisionId,
      Value<String> settingsRevisionId,
      Value<String> detectorId,
      Value<String> detectorSha256,
      Value<String> repvitArtifactId,
      Value<String> repvitSha256,
      Value<String> repvitManifestSha256,
      Value<String> repvitPrototypeSha256,
      Value<String> dinov3ArtifactId,
      Value<String> dinov3Sha256,
      Value<String> dinov3SupportSha256,
      Value<String> calibrationId,
      Value<String> calibrationSha256,
      Value<String> preprocessSha256,
      Value<String> fusionPolicyId,
      Value<String> fusionPolicySha256,
      Value<String> configSnapshotJson,
      Value<int> rowid,
    });

final class $$CheckoutSessionsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $CheckoutSessionsTable,
          CheckoutSessionRow
        > {
  $$CheckoutSessionsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $CatalogRevisionsTable _catalogRevisionIdTable(
    _$BakeryDatabase db,
  ) => db.catalogRevisions.createAlias(
    'checkout_sessions__catalog_revision_id__catalog_revisions__revision_id',
  );

  $$CatalogRevisionsTableProcessedTableManager get catalogRevisionId {
    final $_column = $_itemColumn<String>('catalog_revision_id')!;

    final manager = $$CatalogRevisionsTableTableManager(
      $_db,
      $_db.catalogRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_catalogRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $SettingsRevisionsTable _settingsRevisionIdTable(
    _$BakeryDatabase db,
  ) => db.settingsRevisions.createAlias(
    'checkout_sessions__settings_revision_id__settings_revisions__revision_id',
  );

  $$SettingsRevisionsTableProcessedTableManager get settingsRevisionId {
    final $_column = $_itemColumn<String>('settings_revision_id')!;

    final manager = $$SettingsRevisionsTableTableManager(
      $_db,
      $_db.settingsRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_settingsRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$ScanAttemptsTable, List<ScanAttemptRow>>
  _scanAttemptsRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.scanAttempts,
    aliasName: 'checkout_sessions__session_id__scan_attempts__session_id',
  );

  $$ScanAttemptsTableProcessedTableManager get scanAttemptsRefs {
    final manager = $$ScanAttemptsTableTableManager($_db, $_db.scanAttempts)
        .filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(_scanAttemptsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$ObjectResolutionsTable, List<ObjectResolutionRow>>
  _objectResolutionsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.objectResolutions,
        aliasName:
            'checkout_sessions__session_id__object_resolutions__session_id',
      );

  $$ObjectResolutionsTableProcessedTableManager get objectResolutionsRefs {
    final manager =
        $$ObjectResolutionsTableTableManager(
          $_db,
          $_db.objectResolutions,
        ).filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _objectResolutionsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$DraftOrderLinesTable, List<DraftOrderLineRow>>
  _draftOrderLinesRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.draftOrderLines,
        aliasName:
            'checkout_sessions__session_id__draft_order_lines__session_id',
      );

  $$DraftOrderLinesTableProcessedTableManager get draftOrderLinesRefs {
    final manager =
        $$DraftOrderLinesTableTableManager($_db, $_db.draftOrderLines).filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _draftOrderLinesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$FinalOrdersTable, List<FinalOrderRow>>
  _finalOrdersRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.finalOrders,
    aliasName: 'checkout_sessions__session_id__final_orders__session_id',
  );

  $$FinalOrdersTableProcessedTableManager get finalOrdersRefs {
    final manager = $$FinalOrdersTableTableManager($_db, $_db.finalOrders)
        .filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(_finalOrdersRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$SimulatedPaymentsTable, List<SimulatedPaymentRow>>
  _simulatedPaymentsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.simulatedPayments,
        aliasName:
            'checkout_sessions__session_id__simulated_payments__session_id',
      );

  $$SimulatedPaymentsTableProcessedTableManager get simulatedPaymentsRefs {
    final manager =
        $$SimulatedPaymentsTableTableManager(
          $_db,
          $_db.simulatedPayments,
        ).filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _simulatedPaymentsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$AuditEventsTable, List<AuditEventRow>>
  _auditEventsRefsTable(_$BakeryDatabase db) => MultiTypedResultKey.fromTable(
    db.auditEvents,
    aliasName: 'checkout_sessions__session_id__audit_events__session_id',
  );

  $$AuditEventsTableProcessedTableManager get auditEventsRefs {
    final manager = $$AuditEventsTableTableManager($_db, $_db.auditEvents)
        .filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(_auditEventsRefsTable($_db));
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<
    $AdminReviewAnnotationsTable,
    List<AdminReviewAnnotationRow>
  >
  _adminReviewAnnotationsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.adminReviewAnnotations,
    aliasName:
        'checkout_sessions__session_id__admin_review_annotations__session_id',
  );

  $$AdminReviewAnnotationsTableProcessedTableManager
  get adminReviewAnnotationsRefs {
    final manager =
        $$AdminReviewAnnotationsTableTableManager(
          $_db,
          $_db.adminReviewAnnotations,
        ).filter(
          (f) => f.sessionId.sessionId.sqlEquals(
            $_itemColumn<String>('session_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _adminReviewAnnotationsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$CheckoutSessionsTableFilterComposer
    extends Composer<_$BakeryDatabase, $CheckoutSessionsTable> {
  $$CheckoutSessionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get sessionId => $composableBuilder(
    column: $table.sessionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get startedAtUs => $composableBuilder(
    column: $table.startedAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get terminalAtUs => $composableBuilder(
    column: $table.terminalAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get terminalReason => $composableBuilder(
    column: $table.terminalReason,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get detectorId => $composableBuilder(
    column: $table.detectorId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get detectorSha256 => $composableBuilder(
    column: $table.detectorSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get repvitArtifactId => $composableBuilder(
    column: $table.repvitArtifactId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get repvitSha256 => $composableBuilder(
    column: $table.repvitSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get repvitManifestSha256 => $composableBuilder(
    column: $table.repvitManifestSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get repvitPrototypeSha256 => $composableBuilder(
    column: $table.repvitPrototypeSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get dinov3ArtifactId => $composableBuilder(
    column: $table.dinov3ArtifactId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get dinov3Sha256 => $composableBuilder(
    column: $table.dinov3Sha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get dinov3SupportSha256 => $composableBuilder(
    column: $table.dinov3SupportSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get calibrationId => $composableBuilder(
    column: $table.calibrationId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get calibrationSha256 => $composableBuilder(
    column: $table.calibrationSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get preprocessSha256 => $composableBuilder(
    column: $table.preprocessSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get fusionPolicyId => $composableBuilder(
    column: $table.fusionPolicyId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get fusionPolicySha256 => $composableBuilder(
    column: $table.fusionPolicySha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get configSnapshotJson => $composableBuilder(
    column: $table.configSnapshotJson,
    builder: (column) => ColumnFilters(column),
  );

  $$CatalogRevisionsTableFilterComposer get catalogRevisionId {
    final $$CatalogRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$SettingsRevisionsTableFilterComposer get settingsRevisionId {
    final $$SettingsRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.settingsRevisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> scanAttemptsRefs(
    Expression<bool> Function($$ScanAttemptsTableFilterComposer f) f,
  ) {
    final $$ScanAttemptsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableFilterComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> objectResolutionsRefs(
    Expression<bool> Function($$ObjectResolutionsTableFilterComposer f) f,
  ) {
    final $$ObjectResolutionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.objectResolutions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ObjectResolutionsTableFilterComposer(
            $db: $db,
            $table: $db.objectResolutions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> draftOrderLinesRefs(
    Expression<bool> Function($$DraftOrderLinesTableFilterComposer f) f,
  ) {
    final $$DraftOrderLinesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.draftOrderLines,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$DraftOrderLinesTableFilterComposer(
            $db: $db,
            $table: $db.draftOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> finalOrdersRefs(
    Expression<bool> Function($$FinalOrdersTableFilterComposer f) f,
  ) {
    final $$FinalOrdersTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableFilterComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> simulatedPaymentsRefs(
    Expression<bool> Function($$SimulatedPaymentsTableFilterComposer f) f,
  ) {
    final $$SimulatedPaymentsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.simulatedPayments,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SimulatedPaymentsTableFilterComposer(
            $db: $db,
            $table: $db.simulatedPayments,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> auditEventsRefs(
    Expression<bool> Function($$AuditEventsTableFilterComposer f) f,
  ) {
    final $$AuditEventsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.auditEvents,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$AuditEventsTableFilterComposer(
            $db: $db,
            $table: $db.auditEvents,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> adminReviewAnnotationsRefs(
    Expression<bool> Function($$AdminReviewAnnotationsTableFilterComposer f) f,
  ) {
    final $$AdminReviewAnnotationsTableFilterComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.sessionId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.sessionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableFilterComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$CheckoutSessionsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $CheckoutSessionsTable> {
  $$CheckoutSessionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get sessionId => $composableBuilder(
    column: $table.sessionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get startedAtUs => $composableBuilder(
    column: $table.startedAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get terminalAtUs => $composableBuilder(
    column: $table.terminalAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get terminalReason => $composableBuilder(
    column: $table.terminalReason,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get detectorId => $composableBuilder(
    column: $table.detectorId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get detectorSha256 => $composableBuilder(
    column: $table.detectorSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get repvitArtifactId => $composableBuilder(
    column: $table.repvitArtifactId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get repvitSha256 => $composableBuilder(
    column: $table.repvitSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get repvitManifestSha256 => $composableBuilder(
    column: $table.repvitManifestSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get repvitPrototypeSha256 => $composableBuilder(
    column: $table.repvitPrototypeSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get dinov3ArtifactId => $composableBuilder(
    column: $table.dinov3ArtifactId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get dinov3Sha256 => $composableBuilder(
    column: $table.dinov3Sha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get dinov3SupportSha256 => $composableBuilder(
    column: $table.dinov3SupportSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get calibrationId => $composableBuilder(
    column: $table.calibrationId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get calibrationSha256 => $composableBuilder(
    column: $table.calibrationSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get preprocessSha256 => $composableBuilder(
    column: $table.preprocessSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get fusionPolicyId => $composableBuilder(
    column: $table.fusionPolicyId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get fusionPolicySha256 => $composableBuilder(
    column: $table.fusionPolicySha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get configSnapshotJson => $composableBuilder(
    column: $table.configSnapshotJson,
    builder: (column) => ColumnOrderings(column),
  );

  $$CatalogRevisionsTableOrderingComposer get catalogRevisionId {
    final $$CatalogRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$SettingsRevisionsTableOrderingComposer get settingsRevisionId {
    final $$SettingsRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.settingsRevisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$CheckoutSessionsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $CheckoutSessionsTable> {
  $$CheckoutSessionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get sessionId =>
      $composableBuilder(column: $table.sessionId, builder: (column) => column);

  GeneratedColumn<String> get state =>
      $composableBuilder(column: $table.state, builder: (column) => column);

  GeneratedColumn<int> get startedAtUs => $composableBuilder(
    column: $table.startedAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<int> get terminalAtUs => $composableBuilder(
    column: $table.terminalAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get terminalReason => $composableBuilder(
    column: $table.terminalReason,
    builder: (column) => column,
  );

  GeneratedColumn<String> get detectorId => $composableBuilder(
    column: $table.detectorId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get detectorSha256 => $composableBuilder(
    column: $table.detectorSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get repvitArtifactId => $composableBuilder(
    column: $table.repvitArtifactId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get repvitSha256 => $composableBuilder(
    column: $table.repvitSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get repvitManifestSha256 => $composableBuilder(
    column: $table.repvitManifestSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get repvitPrototypeSha256 => $composableBuilder(
    column: $table.repvitPrototypeSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get dinov3ArtifactId => $composableBuilder(
    column: $table.dinov3ArtifactId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get dinov3Sha256 => $composableBuilder(
    column: $table.dinov3Sha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get dinov3SupportSha256 => $composableBuilder(
    column: $table.dinov3SupportSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get calibrationId => $composableBuilder(
    column: $table.calibrationId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get calibrationSha256 => $composableBuilder(
    column: $table.calibrationSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get preprocessSha256 => $composableBuilder(
    column: $table.preprocessSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get fusionPolicyId => $composableBuilder(
    column: $table.fusionPolicyId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get fusionPolicySha256 => $composableBuilder(
    column: $table.fusionPolicySha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get configSnapshotJson => $composableBuilder(
    column: $table.configSnapshotJson,
    builder: (column) => column,
  );

  $$CatalogRevisionsTableAnnotationComposer get catalogRevisionId {
    final $$CatalogRevisionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableAnnotationComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$SettingsRevisionsTableAnnotationComposer get settingsRevisionId {
    final $$SettingsRevisionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.settingsRevisionId,
          referencedTable: $db.settingsRevisions,
          getReferencedColumn: (t) => t.revisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SettingsRevisionsTableAnnotationComposer(
                $db: $db,
                $table: $db.settingsRevisions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return composer;
  }

  Expression<T> scanAttemptsRefs<T extends Object>(
    Expression<T> Function($$ScanAttemptsTableAnnotationComposer a) f,
  ) {
    final $$ScanAttemptsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableAnnotationComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> objectResolutionsRefs<T extends Object>(
    Expression<T> Function($$ObjectResolutionsTableAnnotationComposer a) f,
  ) {
    final $$ObjectResolutionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.sessionId,
          referencedTable: $db.objectResolutions,
          getReferencedColumn: (t) => t.sessionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$ObjectResolutionsTableAnnotationComposer(
                $db: $db,
                $table: $db.objectResolutions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> draftOrderLinesRefs<T extends Object>(
    Expression<T> Function($$DraftOrderLinesTableAnnotationComposer a) f,
  ) {
    final $$DraftOrderLinesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.draftOrderLines,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$DraftOrderLinesTableAnnotationComposer(
            $db: $db,
            $table: $db.draftOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> finalOrdersRefs<T extends Object>(
    Expression<T> Function($$FinalOrdersTableAnnotationComposer a) f,
  ) {
    final $$FinalOrdersTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> simulatedPaymentsRefs<T extends Object>(
    Expression<T> Function($$SimulatedPaymentsTableAnnotationComposer a) f,
  ) {
    final $$SimulatedPaymentsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.sessionId,
          referencedTable: $db.simulatedPayments,
          getReferencedColumn: (t) => t.sessionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SimulatedPaymentsTableAnnotationComposer(
                $db: $db,
                $table: $db.simulatedPayments,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> auditEventsRefs<T extends Object>(
    Expression<T> Function($$AuditEventsTableAnnotationComposer a) f,
  ) {
    final $$AuditEventsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.auditEvents,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$AuditEventsTableAnnotationComposer(
            $db: $db,
            $table: $db.auditEvents,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> adminReviewAnnotationsRefs<T extends Object>(
    Expression<T> Function($$AdminReviewAnnotationsTableAnnotationComposer a) f,
  ) {
    final $$AdminReviewAnnotationsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.sessionId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.sessionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableAnnotationComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$CheckoutSessionsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $CheckoutSessionsTable,
          CheckoutSessionRow,
          $$CheckoutSessionsTableFilterComposer,
          $$CheckoutSessionsTableOrderingComposer,
          $$CheckoutSessionsTableAnnotationComposer,
          $$CheckoutSessionsTableCreateCompanionBuilder,
          $$CheckoutSessionsTableUpdateCompanionBuilder,
          (CheckoutSessionRow, $$CheckoutSessionsTableReferences),
          CheckoutSessionRow,
          PrefetchHooks Function({
            bool catalogRevisionId,
            bool settingsRevisionId,
            bool scanAttemptsRefs,
            bool objectResolutionsRefs,
            bool draftOrderLinesRefs,
            bool finalOrdersRefs,
            bool simulatedPaymentsRefs,
            bool auditEventsRefs,
            bool adminReviewAnnotationsRefs,
          })
        > {
  $$CheckoutSessionsTableTableManager(
    _$BakeryDatabase db,
    $CheckoutSessionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$CheckoutSessionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$CheckoutSessionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$CheckoutSessionsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> sessionId = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<int> startedAtUs = const Value.absent(),
                Value<int?> terminalAtUs = const Value.absent(),
                Value<String?> terminalReason = const Value.absent(),
                Value<String> catalogRevisionId = const Value.absent(),
                Value<String> settingsRevisionId = const Value.absent(),
                Value<String> detectorId = const Value.absent(),
                Value<String> detectorSha256 = const Value.absent(),
                Value<String> repvitArtifactId = const Value.absent(),
                Value<String> repvitSha256 = const Value.absent(),
                Value<String> repvitManifestSha256 = const Value.absent(),
                Value<String> repvitPrototypeSha256 = const Value.absent(),
                Value<String> dinov3ArtifactId = const Value.absent(),
                Value<String> dinov3Sha256 = const Value.absent(),
                Value<String> dinov3SupportSha256 = const Value.absent(),
                Value<String> calibrationId = const Value.absent(),
                Value<String> calibrationSha256 = const Value.absent(),
                Value<String> preprocessSha256 = const Value.absent(),
                Value<String> fusionPolicyId = const Value.absent(),
                Value<String> fusionPolicySha256 = const Value.absent(),
                Value<String> configSnapshotJson = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => CheckoutSessionsCompanion(
                sessionId: sessionId,
                state: state,
                startedAtUs: startedAtUs,
                terminalAtUs: terminalAtUs,
                terminalReason: terminalReason,
                catalogRevisionId: catalogRevisionId,
                settingsRevisionId: settingsRevisionId,
                detectorId: detectorId,
                detectorSha256: detectorSha256,
                repvitArtifactId: repvitArtifactId,
                repvitSha256: repvitSha256,
                repvitManifestSha256: repvitManifestSha256,
                repvitPrototypeSha256: repvitPrototypeSha256,
                dinov3ArtifactId: dinov3ArtifactId,
                dinov3Sha256: dinov3Sha256,
                dinov3SupportSha256: dinov3SupportSha256,
                calibrationId: calibrationId,
                calibrationSha256: calibrationSha256,
                preprocessSha256: preprocessSha256,
                fusionPolicyId: fusionPolicyId,
                fusionPolicySha256: fusionPolicySha256,
                configSnapshotJson: configSnapshotJson,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String sessionId,
                required String state,
                required int startedAtUs,
                Value<int?> terminalAtUs = const Value.absent(),
                Value<String?> terminalReason = const Value.absent(),
                required String catalogRevisionId,
                required String settingsRevisionId,
                required String detectorId,
                required String detectorSha256,
                required String repvitArtifactId,
                required String repvitSha256,
                required String repvitManifestSha256,
                required String repvitPrototypeSha256,
                required String dinov3ArtifactId,
                required String dinov3Sha256,
                required String dinov3SupportSha256,
                required String calibrationId,
                required String calibrationSha256,
                required String preprocessSha256,
                required String fusionPolicyId,
                required String fusionPolicySha256,
                required String configSnapshotJson,
                Value<int> rowid = const Value.absent(),
              }) => CheckoutSessionsCompanion.insert(
                sessionId: sessionId,
                state: state,
                startedAtUs: startedAtUs,
                terminalAtUs: terminalAtUs,
                terminalReason: terminalReason,
                catalogRevisionId: catalogRevisionId,
                settingsRevisionId: settingsRevisionId,
                detectorId: detectorId,
                detectorSha256: detectorSha256,
                repvitArtifactId: repvitArtifactId,
                repvitSha256: repvitSha256,
                repvitManifestSha256: repvitManifestSha256,
                repvitPrototypeSha256: repvitPrototypeSha256,
                dinov3ArtifactId: dinov3ArtifactId,
                dinov3Sha256: dinov3Sha256,
                dinov3SupportSha256: dinov3SupportSha256,
                calibrationId: calibrationId,
                calibrationSha256: calibrationSha256,
                preprocessSha256: preprocessSha256,
                fusionPolicyId: fusionPolicyId,
                fusionPolicySha256: fusionPolicySha256,
                configSnapshotJson: configSnapshotJson,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$CheckoutSessionsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                catalogRevisionId = false,
                settingsRevisionId = false,
                scanAttemptsRefs = false,
                objectResolutionsRefs = false,
                draftOrderLinesRefs = false,
                finalOrdersRefs = false,
                simulatedPaymentsRefs = false,
                auditEventsRefs = false,
                adminReviewAnnotationsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (scanAttemptsRefs) db.scanAttempts,
                    if (objectResolutionsRefs) db.objectResolutions,
                    if (draftOrderLinesRefs) db.draftOrderLines,
                    if (finalOrdersRefs) db.finalOrders,
                    if (simulatedPaymentsRefs) db.simulatedPayments,
                    if (auditEventsRefs) db.auditEvents,
                    if (adminReviewAnnotationsRefs) db.adminReviewAnnotations,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (catalogRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.catalogRevisionId,
                                    referencedTable:
                                        $$CheckoutSessionsTableReferences
                                            ._catalogRevisionIdTable(db),
                                    referencedColumn:
                                        $$CheckoutSessionsTableReferences
                                            ._catalogRevisionIdTable(db)
                                            .revisionId,
                                  )
                                  as T;
                        }
                        if (settingsRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.settingsRevisionId,
                                    referencedTable:
                                        $$CheckoutSessionsTableReferences
                                            ._settingsRevisionIdTable(db),
                                    referencedColumn:
                                        $$CheckoutSessionsTableReferences
                                            ._settingsRevisionIdTable(db)
                                            .revisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (scanAttemptsRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          ScanAttemptRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._scanAttemptsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).scanAttemptsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (objectResolutionsRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          ObjectResolutionRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._objectResolutionsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).objectResolutionsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (draftOrderLinesRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          DraftOrderLineRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._draftOrderLinesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).draftOrderLinesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (finalOrdersRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          FinalOrderRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._finalOrdersRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).finalOrdersRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (simulatedPaymentsRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          SimulatedPaymentRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._simulatedPaymentsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).simulatedPaymentsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (auditEventsRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          AuditEventRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._auditEventsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).auditEventsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                      if (adminReviewAnnotationsRefs)
                        await $_getPrefetchedData<
                          CheckoutSessionRow,
                          $CheckoutSessionsTable,
                          AdminReviewAnnotationRow
                        >(
                          currentTable: table,
                          referencedTable: $$CheckoutSessionsTableReferences
                              ._adminReviewAnnotationsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$CheckoutSessionsTableReferences(
                                db,
                                table,
                                p0,
                              ).adminReviewAnnotationsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.sessionId == item.sessionId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$CheckoutSessionsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $CheckoutSessionsTable,
      CheckoutSessionRow,
      $$CheckoutSessionsTableFilterComposer,
      $$CheckoutSessionsTableOrderingComposer,
      $$CheckoutSessionsTableAnnotationComposer,
      $$CheckoutSessionsTableCreateCompanionBuilder,
      $$CheckoutSessionsTableUpdateCompanionBuilder,
      (CheckoutSessionRow, $$CheckoutSessionsTableReferences),
      CheckoutSessionRow,
      PrefetchHooks Function({
        bool catalogRevisionId,
        bool settingsRevisionId,
        bool scanAttemptsRefs,
        bool objectResolutionsRefs,
        bool draftOrderLinesRefs,
        bool finalOrdersRefs,
        bool simulatedPaymentsRefs,
        bool auditEventsRefs,
        bool adminReviewAnnotationsRefs,
      })
    >;
typedef $$ScanAttemptsTableCreateCompanionBuilder =
    ScanAttemptsCompanion Function({
      required String attemptId,
      required String sessionId,
      required int attemptNumber,
      required int capturedAtUs,
      required String imageRelativePath,
      required int imageByteSize,
      required String imageSha256,
      required String status,
      Value<int?> canonicalWidth,
      Value<int?> canonicalHeight,
      Value<String?> receiptRelativePath,
      Value<int?> receiptByteSize,
      Value<String?> receiptSha256,
      Value<String?> presentationState,
      Value<bool?> finalCountUsable,
      Value<String?> retakeScope,
      Value<String?> retakeReason,
      Value<String?> presentationPolicyId,
      Value<String?> presentationPolicySha256,
      Value<double?> decodePreprocessMs,
      Value<double?> detectorMs,
      Value<double?> repvitMs,
      Value<double?> dinov3Ms,
      Value<double?> postprocessMs,
      Value<double?> totalMs,
      Value<String?> startupDevice,
      Value<double?> startupLoadMs,
      Value<double?> startupWarmupMs,
      Value<String?> startupFallbackReason,
      Value<int> rowid,
    });
typedef $$ScanAttemptsTableUpdateCompanionBuilder =
    ScanAttemptsCompanion Function({
      Value<String> attemptId,
      Value<String> sessionId,
      Value<int> attemptNumber,
      Value<int> capturedAtUs,
      Value<String> imageRelativePath,
      Value<int> imageByteSize,
      Value<String> imageSha256,
      Value<String> status,
      Value<int?> canonicalWidth,
      Value<int?> canonicalHeight,
      Value<String?> receiptRelativePath,
      Value<int?> receiptByteSize,
      Value<String?> receiptSha256,
      Value<String?> presentationState,
      Value<bool?> finalCountUsable,
      Value<String?> retakeScope,
      Value<String?> retakeReason,
      Value<String?> presentationPolicyId,
      Value<String?> presentationPolicySha256,
      Value<double?> decodePreprocessMs,
      Value<double?> detectorMs,
      Value<double?> repvitMs,
      Value<double?> dinov3Ms,
      Value<double?> postprocessMs,
      Value<double?> totalMs,
      Value<String?> startupDevice,
      Value<double?> startupLoadMs,
      Value<double?> startupWarmupMs,
      Value<String?> startupFallbackReason,
      Value<int> rowid,
    });

final class $$ScanAttemptsTableReferences
    extends
        BaseReferences<_$BakeryDatabase, $ScanAttemptsTable, ScanAttemptRow> {
  $$ScanAttemptsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) => db
      .checkoutSessions
      .createAlias('scan_attempts__session_id__checkout_sessions__session_id');

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$InferenceObjectsTable, List<InferenceObjectRow>>
  _inferenceObjectsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.inferenceObjects,
        aliasName: 'scan_attempts__attempt_id__inference_objects__attempt_id',
      );

  $$InferenceObjectsTableProcessedTableManager get inferenceObjectsRefs {
    final manager =
        $$InferenceObjectsTableTableManager($_db, $_db.inferenceObjects).filter(
          (f) => f.attemptId.attemptId.sqlEquals(
            $_itemColumn<String>('attempt_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _inferenceObjectsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$RetentionEventsTable, List<RetentionEventRow>>
  _retentionEventsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.retentionEvents,
        aliasName: 'scan_attempts__attempt_id__retention_events__attempt_id',
      );

  $$RetentionEventsTableProcessedTableManager get retentionEventsRefs {
    final manager =
        $$RetentionEventsTableTableManager($_db, $_db.retentionEvents).filter(
          (f) => f.attemptId.attemptId.sqlEquals(
            $_itemColumn<String>('attempt_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _retentionEventsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<
    $AdminReviewAnnotationsTable,
    List<AdminReviewAnnotationRow>
  >
  _adminReviewAnnotationsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.adminReviewAnnotations,
        aliasName:
            'scan_attempts__attempt_id__admin_review_annotations__attempt_id',
      );

  $$AdminReviewAnnotationsTableProcessedTableManager
  get adminReviewAnnotationsRefs {
    final manager =
        $$AdminReviewAnnotationsTableTableManager(
          $_db,
          $_db.adminReviewAnnotations,
        ).filter(
          (f) => f.attemptId.attemptId.sqlEquals(
            $_itemColumn<String>('attempt_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _adminReviewAnnotationsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$ScanAttemptsTableFilterComposer
    extends Composer<_$BakeryDatabase, $ScanAttemptsTable> {
  $$ScanAttemptsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get attemptId => $composableBuilder(
    column: $table.attemptId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get attemptNumber => $composableBuilder(
    column: $table.attemptNumber,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get capturedAtUs => $composableBuilder(
    column: $table.capturedAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get imageRelativePath => $composableBuilder(
    column: $table.imageRelativePath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get imageByteSize => $composableBuilder(
    column: $table.imageByteSize,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get imageSha256 => $composableBuilder(
    column: $table.imageSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get canonicalWidth => $composableBuilder(
    column: $table.canonicalWidth,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get canonicalHeight => $composableBuilder(
    column: $table.canonicalHeight,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get presentationState => $composableBuilder(
    column: $table.presentationState,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get finalCountUsable => $composableBuilder(
    column: $table.finalCountUsable,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get retakeScope => $composableBuilder(
    column: $table.retakeScope,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get retakeReason => $composableBuilder(
    column: $table.retakeReason,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get presentationPolicyId => $composableBuilder(
    column: $table.presentationPolicyId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get presentationPolicySha256 => $composableBuilder(
    column: $table.presentationPolicySha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get decodePreprocessMs => $composableBuilder(
    column: $table.decodePreprocessMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get detectorMs => $composableBuilder(
    column: $table.detectorMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get repvitMs => $composableBuilder(
    column: $table.repvitMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get dinov3Ms => $composableBuilder(
    column: $table.dinov3Ms,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get postprocessMs => $composableBuilder(
    column: $table.postprocessMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get totalMs => $composableBuilder(
    column: $table.totalMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get startupDevice => $composableBuilder(
    column: $table.startupDevice,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get startupLoadMs => $composableBuilder(
    column: $table.startupLoadMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get startupWarmupMs => $composableBuilder(
    column: $table.startupWarmupMs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get startupFallbackReason => $composableBuilder(
    column: $table.startupFallbackReason,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> inferenceObjectsRefs(
    Expression<bool> Function($$InferenceObjectsTableFilterComposer f) f,
  ) {
    final $$InferenceObjectsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableFilterComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> retentionEventsRefs(
    Expression<bool> Function($$RetentionEventsTableFilterComposer f) f,
  ) {
    final $$RetentionEventsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.retentionEvents,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RetentionEventsTableFilterComposer(
            $db: $db,
            $table: $db.retentionEvents,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> adminReviewAnnotationsRefs(
    Expression<bool> Function($$AdminReviewAnnotationsTableFilterComposer f) f,
  ) {
    final $$AdminReviewAnnotationsTableFilterComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.attemptId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.attemptId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableFilterComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$ScanAttemptsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $ScanAttemptsTable> {
  $$ScanAttemptsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get attemptId => $composableBuilder(
    column: $table.attemptId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get attemptNumber => $composableBuilder(
    column: $table.attemptNumber,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get capturedAtUs => $composableBuilder(
    column: $table.capturedAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get imageRelativePath => $composableBuilder(
    column: $table.imageRelativePath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get imageByteSize => $composableBuilder(
    column: $table.imageByteSize,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get imageSha256 => $composableBuilder(
    column: $table.imageSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get canonicalWidth => $composableBuilder(
    column: $table.canonicalWidth,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get canonicalHeight => $composableBuilder(
    column: $table.canonicalHeight,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get presentationState => $composableBuilder(
    column: $table.presentationState,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get finalCountUsable => $composableBuilder(
    column: $table.finalCountUsable,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get retakeScope => $composableBuilder(
    column: $table.retakeScope,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get retakeReason => $composableBuilder(
    column: $table.retakeReason,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get presentationPolicyId => $composableBuilder(
    column: $table.presentationPolicyId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get presentationPolicySha256 => $composableBuilder(
    column: $table.presentationPolicySha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get decodePreprocessMs => $composableBuilder(
    column: $table.decodePreprocessMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get detectorMs => $composableBuilder(
    column: $table.detectorMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get repvitMs => $composableBuilder(
    column: $table.repvitMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get dinov3Ms => $composableBuilder(
    column: $table.dinov3Ms,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get postprocessMs => $composableBuilder(
    column: $table.postprocessMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get totalMs => $composableBuilder(
    column: $table.totalMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get startupDevice => $composableBuilder(
    column: $table.startupDevice,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get startupLoadMs => $composableBuilder(
    column: $table.startupLoadMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get startupWarmupMs => $composableBuilder(
    column: $table.startupWarmupMs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get startupFallbackReason => $composableBuilder(
    column: $table.startupFallbackReason,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ScanAttemptsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $ScanAttemptsTable> {
  $$ScanAttemptsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get attemptId =>
      $composableBuilder(column: $table.attemptId, builder: (column) => column);

  GeneratedColumn<int> get attemptNumber => $composableBuilder(
    column: $table.attemptNumber,
    builder: (column) => column,
  );

  GeneratedColumn<int> get capturedAtUs => $composableBuilder(
    column: $table.capturedAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get imageRelativePath => $composableBuilder(
    column: $table.imageRelativePath,
    builder: (column) => column,
  );

  GeneratedColumn<int> get imageByteSize => $composableBuilder(
    column: $table.imageByteSize,
    builder: (column) => column,
  );

  GeneratedColumn<String> get imageSha256 => $composableBuilder(
    column: $table.imageSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<int> get canonicalWidth => $composableBuilder(
    column: $table.canonicalWidth,
    builder: (column) => column,
  );

  GeneratedColumn<int> get canonicalHeight => $composableBuilder(
    column: $table.canonicalHeight,
    builder: (column) => column,
  );

  GeneratedColumn<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => column,
  );

  GeneratedColumn<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => column,
  );

  GeneratedColumn<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => column,
  );

  GeneratedColumn<String> get presentationState => $composableBuilder(
    column: $table.presentationState,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get finalCountUsable => $composableBuilder(
    column: $table.finalCountUsable,
    builder: (column) => column,
  );

  GeneratedColumn<String> get retakeScope => $composableBuilder(
    column: $table.retakeScope,
    builder: (column) => column,
  );

  GeneratedColumn<String> get retakeReason => $composableBuilder(
    column: $table.retakeReason,
    builder: (column) => column,
  );

  GeneratedColumn<String> get presentationPolicyId => $composableBuilder(
    column: $table.presentationPolicyId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get presentationPolicySha256 => $composableBuilder(
    column: $table.presentationPolicySha256,
    builder: (column) => column,
  );

  GeneratedColumn<double> get decodePreprocessMs => $composableBuilder(
    column: $table.decodePreprocessMs,
    builder: (column) => column,
  );

  GeneratedColumn<double> get detectorMs => $composableBuilder(
    column: $table.detectorMs,
    builder: (column) => column,
  );

  GeneratedColumn<double> get repvitMs =>
      $composableBuilder(column: $table.repvitMs, builder: (column) => column);

  GeneratedColumn<double> get dinov3Ms =>
      $composableBuilder(column: $table.dinov3Ms, builder: (column) => column);

  GeneratedColumn<double> get postprocessMs => $composableBuilder(
    column: $table.postprocessMs,
    builder: (column) => column,
  );

  GeneratedColumn<double> get totalMs =>
      $composableBuilder(column: $table.totalMs, builder: (column) => column);

  GeneratedColumn<String> get startupDevice => $composableBuilder(
    column: $table.startupDevice,
    builder: (column) => column,
  );

  GeneratedColumn<double> get startupLoadMs => $composableBuilder(
    column: $table.startupLoadMs,
    builder: (column) => column,
  );

  GeneratedColumn<double> get startupWarmupMs => $composableBuilder(
    column: $table.startupWarmupMs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get startupFallbackReason => $composableBuilder(
    column: $table.startupFallbackReason,
    builder: (column) => column,
  );

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<T> inferenceObjectsRefs<T extends Object>(
    Expression<T> Function($$InferenceObjectsTableAnnotationComposer a) f,
  ) {
    final $$InferenceObjectsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableAnnotationComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> retentionEventsRefs<T extends Object>(
    Expression<T> Function($$RetentionEventsTableAnnotationComposer a) f,
  ) {
    final $$RetentionEventsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.retentionEvents,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$RetentionEventsTableAnnotationComposer(
            $db: $db,
            $table: $db.retentionEvents,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> adminReviewAnnotationsRefs<T extends Object>(
    Expression<T> Function($$AdminReviewAnnotationsTableAnnotationComposer a) f,
  ) {
    final $$AdminReviewAnnotationsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.attemptId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.attemptId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableAnnotationComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$ScanAttemptsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $ScanAttemptsTable,
          ScanAttemptRow,
          $$ScanAttemptsTableFilterComposer,
          $$ScanAttemptsTableOrderingComposer,
          $$ScanAttemptsTableAnnotationComposer,
          $$ScanAttemptsTableCreateCompanionBuilder,
          $$ScanAttemptsTableUpdateCompanionBuilder,
          (ScanAttemptRow, $$ScanAttemptsTableReferences),
          ScanAttemptRow,
          PrefetchHooks Function({
            bool sessionId,
            bool inferenceObjectsRefs,
            bool retentionEventsRefs,
            bool adminReviewAnnotationsRefs,
          })
        > {
  $$ScanAttemptsTableTableManager(_$BakeryDatabase db, $ScanAttemptsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ScanAttemptsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ScanAttemptsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ScanAttemptsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> attemptId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<int> attemptNumber = const Value.absent(),
                Value<int> capturedAtUs = const Value.absent(),
                Value<String> imageRelativePath = const Value.absent(),
                Value<int> imageByteSize = const Value.absent(),
                Value<String> imageSha256 = const Value.absent(),
                Value<String> status = const Value.absent(),
                Value<int?> canonicalWidth = const Value.absent(),
                Value<int?> canonicalHeight = const Value.absent(),
                Value<String?> receiptRelativePath = const Value.absent(),
                Value<int?> receiptByteSize = const Value.absent(),
                Value<String?> receiptSha256 = const Value.absent(),
                Value<String?> presentationState = const Value.absent(),
                Value<bool?> finalCountUsable = const Value.absent(),
                Value<String?> retakeScope = const Value.absent(),
                Value<String?> retakeReason = const Value.absent(),
                Value<String?> presentationPolicyId = const Value.absent(),
                Value<String?> presentationPolicySha256 = const Value.absent(),
                Value<double?> decodePreprocessMs = const Value.absent(),
                Value<double?> detectorMs = const Value.absent(),
                Value<double?> repvitMs = const Value.absent(),
                Value<double?> dinov3Ms = const Value.absent(),
                Value<double?> postprocessMs = const Value.absent(),
                Value<double?> totalMs = const Value.absent(),
                Value<String?> startupDevice = const Value.absent(),
                Value<double?> startupLoadMs = const Value.absent(),
                Value<double?> startupWarmupMs = const Value.absent(),
                Value<String?> startupFallbackReason = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ScanAttemptsCompanion(
                attemptId: attemptId,
                sessionId: sessionId,
                attemptNumber: attemptNumber,
                capturedAtUs: capturedAtUs,
                imageRelativePath: imageRelativePath,
                imageByteSize: imageByteSize,
                imageSha256: imageSha256,
                status: status,
                canonicalWidth: canonicalWidth,
                canonicalHeight: canonicalHeight,
                receiptRelativePath: receiptRelativePath,
                receiptByteSize: receiptByteSize,
                receiptSha256: receiptSha256,
                presentationState: presentationState,
                finalCountUsable: finalCountUsable,
                retakeScope: retakeScope,
                retakeReason: retakeReason,
                presentationPolicyId: presentationPolicyId,
                presentationPolicySha256: presentationPolicySha256,
                decodePreprocessMs: decodePreprocessMs,
                detectorMs: detectorMs,
                repvitMs: repvitMs,
                dinov3Ms: dinov3Ms,
                postprocessMs: postprocessMs,
                totalMs: totalMs,
                startupDevice: startupDevice,
                startupLoadMs: startupLoadMs,
                startupWarmupMs: startupWarmupMs,
                startupFallbackReason: startupFallbackReason,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String attemptId,
                required String sessionId,
                required int attemptNumber,
                required int capturedAtUs,
                required String imageRelativePath,
                required int imageByteSize,
                required String imageSha256,
                required String status,
                Value<int?> canonicalWidth = const Value.absent(),
                Value<int?> canonicalHeight = const Value.absent(),
                Value<String?> receiptRelativePath = const Value.absent(),
                Value<int?> receiptByteSize = const Value.absent(),
                Value<String?> receiptSha256 = const Value.absent(),
                Value<String?> presentationState = const Value.absent(),
                Value<bool?> finalCountUsable = const Value.absent(),
                Value<String?> retakeScope = const Value.absent(),
                Value<String?> retakeReason = const Value.absent(),
                Value<String?> presentationPolicyId = const Value.absent(),
                Value<String?> presentationPolicySha256 = const Value.absent(),
                Value<double?> decodePreprocessMs = const Value.absent(),
                Value<double?> detectorMs = const Value.absent(),
                Value<double?> repvitMs = const Value.absent(),
                Value<double?> dinov3Ms = const Value.absent(),
                Value<double?> postprocessMs = const Value.absent(),
                Value<double?> totalMs = const Value.absent(),
                Value<String?> startupDevice = const Value.absent(),
                Value<double?> startupLoadMs = const Value.absent(),
                Value<double?> startupWarmupMs = const Value.absent(),
                Value<String?> startupFallbackReason = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ScanAttemptsCompanion.insert(
                attemptId: attemptId,
                sessionId: sessionId,
                attemptNumber: attemptNumber,
                capturedAtUs: capturedAtUs,
                imageRelativePath: imageRelativePath,
                imageByteSize: imageByteSize,
                imageSha256: imageSha256,
                status: status,
                canonicalWidth: canonicalWidth,
                canonicalHeight: canonicalHeight,
                receiptRelativePath: receiptRelativePath,
                receiptByteSize: receiptByteSize,
                receiptSha256: receiptSha256,
                presentationState: presentationState,
                finalCountUsable: finalCountUsable,
                retakeScope: retakeScope,
                retakeReason: retakeReason,
                presentationPolicyId: presentationPolicyId,
                presentationPolicySha256: presentationPolicySha256,
                decodePreprocessMs: decodePreprocessMs,
                detectorMs: detectorMs,
                repvitMs: repvitMs,
                dinov3Ms: dinov3Ms,
                postprocessMs: postprocessMs,
                totalMs: totalMs,
                startupDevice: startupDevice,
                startupLoadMs: startupLoadMs,
                startupWarmupMs: startupWarmupMs,
                startupFallbackReason: startupFallbackReason,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$ScanAttemptsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                sessionId = false,
                inferenceObjectsRefs = false,
                retentionEventsRefs = false,
                adminReviewAnnotationsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (inferenceObjectsRefs) db.inferenceObjects,
                    if (retentionEventsRefs) db.retentionEvents,
                    if (adminReviewAnnotationsRefs) db.adminReviewAnnotations,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (sessionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sessionId,
                                    referencedTable:
                                        $$ScanAttemptsTableReferences
                                            ._sessionIdTable(db),
                                    referencedColumn:
                                        $$ScanAttemptsTableReferences
                                            ._sessionIdTable(db)
                                            .sessionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (inferenceObjectsRefs)
                        await $_getPrefetchedData<
                          ScanAttemptRow,
                          $ScanAttemptsTable,
                          InferenceObjectRow
                        >(
                          currentTable: table,
                          referencedTable: $$ScanAttemptsTableReferences
                              ._inferenceObjectsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ScanAttemptsTableReferences(
                                db,
                                table,
                                p0,
                              ).inferenceObjectsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.attemptId == item.attemptId,
                              ),
                          typedResults: items,
                        ),
                      if (retentionEventsRefs)
                        await $_getPrefetchedData<
                          ScanAttemptRow,
                          $ScanAttemptsTable,
                          RetentionEventRow
                        >(
                          currentTable: table,
                          referencedTable: $$ScanAttemptsTableReferences
                              ._retentionEventsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ScanAttemptsTableReferences(
                                db,
                                table,
                                p0,
                              ).retentionEventsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.attemptId == item.attemptId,
                              ),
                          typedResults: items,
                        ),
                      if (adminReviewAnnotationsRefs)
                        await $_getPrefetchedData<
                          ScanAttemptRow,
                          $ScanAttemptsTable,
                          AdminReviewAnnotationRow
                        >(
                          currentTable: table,
                          referencedTable: $$ScanAttemptsTableReferences
                              ._adminReviewAnnotationsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$ScanAttemptsTableReferences(
                                db,
                                table,
                                p0,
                              ).adminReviewAnnotationsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.attemptId == item.attemptId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$ScanAttemptsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $ScanAttemptsTable,
      ScanAttemptRow,
      $$ScanAttemptsTableFilterComposer,
      $$ScanAttemptsTableOrderingComposer,
      $$ScanAttemptsTableAnnotationComposer,
      $$ScanAttemptsTableCreateCompanionBuilder,
      $$ScanAttemptsTableUpdateCompanionBuilder,
      (ScanAttemptRow, $$ScanAttemptsTableReferences),
      ScanAttemptRow,
      PrefetchHooks Function({
        bool sessionId,
        bool inferenceObjectsRefs,
        bool retentionEventsRefs,
        bool adminReviewAnnotationsRefs,
      })
    >;
typedef $$InferenceObjectsTableCreateCompanionBuilder =
    InferenceObjectsCompanion Function({
      required String inferenceObjectId,
      required String attemptId,
      required String objectId,
      Value<int?> skuId,
      required String skuName,
      required String decisionPath,
      required double confidence,
      required String bboxJson,
      required String detectorSource,
      required double detectorScore,
      required String provenanceJson,
      Value<String?> unknownReason,
      Value<int> rowid,
    });
typedef $$InferenceObjectsTableUpdateCompanionBuilder =
    InferenceObjectsCompanion Function({
      Value<String> inferenceObjectId,
      Value<String> attemptId,
      Value<String> objectId,
      Value<int?> skuId,
      Value<String> skuName,
      Value<String> decisionPath,
      Value<double> confidence,
      Value<String> bboxJson,
      Value<String> detectorSource,
      Value<double> detectorScore,
      Value<String> provenanceJson,
      Value<String?> unknownReason,
      Value<int> rowid,
    });

final class $$InferenceObjectsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $InferenceObjectsTable,
          InferenceObjectRow
        > {
  $$InferenceObjectsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $ScanAttemptsTable _attemptIdTable(_$BakeryDatabase db) => db
      .scanAttempts
      .createAlias('inference_objects__attempt_id__scan_attempts__attempt_id');

  $$ScanAttemptsTableProcessedTableManager get attemptId {
    final $_column = $_itemColumn<String>('attempt_id')!;

    final manager = $$ScanAttemptsTableTableManager(
      $_db,
      $_db.scanAttempts,
    ).filter((f) => f.attemptId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_attemptIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<
    $InferenceCandidatesTable,
    List<InferenceCandidateRow>
  >
  _inferenceCandidatesRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.inferenceCandidates,
    aliasName:
        'inference_objects__inference_object_id__inference_candidates__inference_object_id',
  );

  $$InferenceCandidatesTableProcessedTableManager get inferenceCandidatesRefs {
    final manager =
        $$InferenceCandidatesTableTableManager(
          $_db,
          $_db.inferenceCandidates,
        ).filter(
          (f) => f.inferenceObjectId.inferenceObjectId.sqlEquals(
            $_itemColumn<String>('inference_object_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _inferenceCandidatesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$ObjectResolutionsTable, List<ObjectResolutionRow>>
  _objectResolutionsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.objectResolutions,
    aliasName:
        'inference_objects__inference_object_id__object_resolutions__inference_object_id',
  );

  $$ObjectResolutionsTableProcessedTableManager get objectResolutionsRefs {
    final manager =
        $$ObjectResolutionsTableTableManager(
          $_db,
          $_db.objectResolutions,
        ).filter(
          (f) => f.inferenceObjectId.inferenceObjectId.sqlEquals(
            $_itemColumn<String>('inference_object_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _objectResolutionsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<
    $AdminReviewAnnotationsTable,
    List<AdminReviewAnnotationRow>
  >
  _adminReviewAnnotationsRefsTable(
    _$BakeryDatabase db,
  ) => MultiTypedResultKey.fromTable(
    db.adminReviewAnnotations,
    aliasName:
        'inference_objects__inference_object_id__admin_review_annotations__object_id',
  );

  $$AdminReviewAnnotationsTableProcessedTableManager
  get adminReviewAnnotationsRefs {
    final manager =
        $$AdminReviewAnnotationsTableTableManager(
          $_db,
          $_db.adminReviewAnnotations,
        ).filter(
          (f) => f.objectId.inferenceObjectId.sqlEquals(
            $_itemColumn<String>('inference_object_id')!,
          ),
        );

    final cache = $_typedResult.readTableOrNull(
      _adminReviewAnnotationsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$InferenceObjectsTableFilterComposer
    extends Composer<_$BakeryDatabase, $InferenceObjectsTable> {
  $$InferenceObjectsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get inferenceObjectId => $composableBuilder(
    column: $table.inferenceObjectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get objectId => $composableBuilder(
    column: $table.objectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get skuId => $composableBuilder(
    column: $table.skuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get skuName => $composableBuilder(
    column: $table.skuName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get decisionPath => $composableBuilder(
    column: $table.decisionPath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get confidence => $composableBuilder(
    column: $table.confidence,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get bboxJson => $composableBuilder(
    column: $table.bboxJson,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get detectorSource => $composableBuilder(
    column: $table.detectorSource,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get detectorScore => $composableBuilder(
    column: $table.detectorScore,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get provenanceJson => $composableBuilder(
    column: $table.provenanceJson,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get unknownReason => $composableBuilder(
    column: $table.unknownReason,
    builder: (column) => ColumnFilters(column),
  );

  $$ScanAttemptsTableFilterComposer get attemptId {
    final $$ScanAttemptsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableFilterComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> inferenceCandidatesRefs(
    Expression<bool> Function($$InferenceCandidatesTableFilterComposer f) f,
  ) {
    final $$InferenceCandidatesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceCandidates,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceCandidatesTableFilterComposer(
            $db: $db,
            $table: $db.inferenceCandidates,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> objectResolutionsRefs(
    Expression<bool> Function($$ObjectResolutionsTableFilterComposer f) f,
  ) {
    final $$ObjectResolutionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.objectResolutions,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ObjectResolutionsTableFilterComposer(
            $db: $db,
            $table: $db.objectResolutions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> adminReviewAnnotationsRefs(
    Expression<bool> Function($$AdminReviewAnnotationsTableFilterComposer f) f,
  ) {
    final $$AdminReviewAnnotationsTableFilterComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.inferenceObjectId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.objectId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableFilterComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$InferenceObjectsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $InferenceObjectsTable> {
  $$InferenceObjectsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get inferenceObjectId => $composableBuilder(
    column: $table.inferenceObjectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get objectId => $composableBuilder(
    column: $table.objectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get skuId => $composableBuilder(
    column: $table.skuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get skuName => $composableBuilder(
    column: $table.skuName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get decisionPath => $composableBuilder(
    column: $table.decisionPath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get confidence => $composableBuilder(
    column: $table.confidence,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get bboxJson => $composableBuilder(
    column: $table.bboxJson,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get detectorSource => $composableBuilder(
    column: $table.detectorSource,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get detectorScore => $composableBuilder(
    column: $table.detectorScore,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get provenanceJson => $composableBuilder(
    column: $table.provenanceJson,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get unknownReason => $composableBuilder(
    column: $table.unknownReason,
    builder: (column) => ColumnOrderings(column),
  );

  $$ScanAttemptsTableOrderingComposer get attemptId {
    final $$ScanAttemptsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableOrderingComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$InferenceObjectsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $InferenceObjectsTable> {
  $$InferenceObjectsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get inferenceObjectId => $composableBuilder(
    column: $table.inferenceObjectId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get objectId =>
      $composableBuilder(column: $table.objectId, builder: (column) => column);

  GeneratedColumn<int> get skuId =>
      $composableBuilder(column: $table.skuId, builder: (column) => column);

  GeneratedColumn<String> get skuName =>
      $composableBuilder(column: $table.skuName, builder: (column) => column);

  GeneratedColumn<String> get decisionPath => $composableBuilder(
    column: $table.decisionPath,
    builder: (column) => column,
  );

  GeneratedColumn<double> get confidence => $composableBuilder(
    column: $table.confidence,
    builder: (column) => column,
  );

  GeneratedColumn<String> get bboxJson =>
      $composableBuilder(column: $table.bboxJson, builder: (column) => column);

  GeneratedColumn<String> get detectorSource => $composableBuilder(
    column: $table.detectorSource,
    builder: (column) => column,
  );

  GeneratedColumn<double> get detectorScore => $composableBuilder(
    column: $table.detectorScore,
    builder: (column) => column,
  );

  GeneratedColumn<String> get provenanceJson => $composableBuilder(
    column: $table.provenanceJson,
    builder: (column) => column,
  );

  GeneratedColumn<String> get unknownReason => $composableBuilder(
    column: $table.unknownReason,
    builder: (column) => column,
  );

  $$ScanAttemptsTableAnnotationComposer get attemptId {
    final $$ScanAttemptsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableAnnotationComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<T> inferenceCandidatesRefs<T extends Object>(
    Expression<T> Function($$InferenceCandidatesTableAnnotationComposer a) f,
  ) {
    final $$InferenceCandidatesTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.inferenceObjectId,
          referencedTable: $db.inferenceCandidates,
          getReferencedColumn: (t) => t.inferenceObjectId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$InferenceCandidatesTableAnnotationComposer(
                $db: $db,
                $table: $db.inferenceCandidates,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> objectResolutionsRefs<T extends Object>(
    Expression<T> Function($$ObjectResolutionsTableAnnotationComposer a) f,
  ) {
    final $$ObjectResolutionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.inferenceObjectId,
          referencedTable: $db.objectResolutions,
          getReferencedColumn: (t) => t.inferenceObjectId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$ObjectResolutionsTableAnnotationComposer(
                $db: $db,
                $table: $db.objectResolutions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }

  Expression<T> adminReviewAnnotationsRefs<T extends Object>(
    Expression<T> Function($$AdminReviewAnnotationsTableAnnotationComposer a) f,
  ) {
    final $$AdminReviewAnnotationsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.inferenceObjectId,
          referencedTable: $db.adminReviewAnnotations,
          getReferencedColumn: (t) => t.objectId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$AdminReviewAnnotationsTableAnnotationComposer(
                $db: $db,
                $table: $db.adminReviewAnnotations,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$InferenceObjectsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $InferenceObjectsTable,
          InferenceObjectRow,
          $$InferenceObjectsTableFilterComposer,
          $$InferenceObjectsTableOrderingComposer,
          $$InferenceObjectsTableAnnotationComposer,
          $$InferenceObjectsTableCreateCompanionBuilder,
          $$InferenceObjectsTableUpdateCompanionBuilder,
          (InferenceObjectRow, $$InferenceObjectsTableReferences),
          InferenceObjectRow,
          PrefetchHooks Function({
            bool attemptId,
            bool inferenceCandidatesRefs,
            bool objectResolutionsRefs,
            bool adminReviewAnnotationsRefs,
          })
        > {
  $$InferenceObjectsTableTableManager(
    _$BakeryDatabase db,
    $InferenceObjectsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$InferenceObjectsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$InferenceObjectsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$InferenceObjectsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> inferenceObjectId = const Value.absent(),
                Value<String> attemptId = const Value.absent(),
                Value<String> objectId = const Value.absent(),
                Value<int?> skuId = const Value.absent(),
                Value<String> skuName = const Value.absent(),
                Value<String> decisionPath = const Value.absent(),
                Value<double> confidence = const Value.absent(),
                Value<String> bboxJson = const Value.absent(),
                Value<String> detectorSource = const Value.absent(),
                Value<double> detectorScore = const Value.absent(),
                Value<String> provenanceJson = const Value.absent(),
                Value<String?> unknownReason = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => InferenceObjectsCompanion(
                inferenceObjectId: inferenceObjectId,
                attemptId: attemptId,
                objectId: objectId,
                skuId: skuId,
                skuName: skuName,
                decisionPath: decisionPath,
                confidence: confidence,
                bboxJson: bboxJson,
                detectorSource: detectorSource,
                detectorScore: detectorScore,
                provenanceJson: provenanceJson,
                unknownReason: unknownReason,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String inferenceObjectId,
                required String attemptId,
                required String objectId,
                Value<int?> skuId = const Value.absent(),
                required String skuName,
                required String decisionPath,
                required double confidence,
                required String bboxJson,
                required String detectorSource,
                required double detectorScore,
                required String provenanceJson,
                Value<String?> unknownReason = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => InferenceObjectsCompanion.insert(
                inferenceObjectId: inferenceObjectId,
                attemptId: attemptId,
                objectId: objectId,
                skuId: skuId,
                skuName: skuName,
                decisionPath: decisionPath,
                confidence: confidence,
                bboxJson: bboxJson,
                detectorSource: detectorSource,
                detectorScore: detectorScore,
                provenanceJson: provenanceJson,
                unknownReason: unknownReason,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$InferenceObjectsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                attemptId = false,
                inferenceCandidatesRefs = false,
                objectResolutionsRefs = false,
                adminReviewAnnotationsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (inferenceCandidatesRefs) db.inferenceCandidates,
                    if (objectResolutionsRefs) db.objectResolutions,
                    if (adminReviewAnnotationsRefs) db.adminReviewAnnotations,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (attemptId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.attemptId,
                                    referencedTable:
                                        $$InferenceObjectsTableReferences
                                            ._attemptIdTable(db),
                                    referencedColumn:
                                        $$InferenceObjectsTableReferences
                                            ._attemptIdTable(db)
                                            .attemptId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (inferenceCandidatesRefs)
                        await $_getPrefetchedData<
                          InferenceObjectRow,
                          $InferenceObjectsTable,
                          InferenceCandidateRow
                        >(
                          currentTable: table,
                          referencedTable: $$InferenceObjectsTableReferences
                              ._inferenceCandidatesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$InferenceObjectsTableReferences(
                                db,
                                table,
                                p0,
                              ).inferenceCandidatesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.inferenceObjectId ==
                                    item.inferenceObjectId,
                              ),
                          typedResults: items,
                        ),
                      if (objectResolutionsRefs)
                        await $_getPrefetchedData<
                          InferenceObjectRow,
                          $InferenceObjectsTable,
                          ObjectResolutionRow
                        >(
                          currentTable: table,
                          referencedTable: $$InferenceObjectsTableReferences
                              ._objectResolutionsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$InferenceObjectsTableReferences(
                                db,
                                table,
                                p0,
                              ).objectResolutionsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) =>
                                    e.inferenceObjectId ==
                                    item.inferenceObjectId,
                              ),
                          typedResults: items,
                        ),
                      if (adminReviewAnnotationsRefs)
                        await $_getPrefetchedData<
                          InferenceObjectRow,
                          $InferenceObjectsTable,
                          AdminReviewAnnotationRow
                        >(
                          currentTable: table,
                          referencedTable: $$InferenceObjectsTableReferences
                              ._adminReviewAnnotationsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$InferenceObjectsTableReferences(
                                db,
                                table,
                                p0,
                              ).adminReviewAnnotationsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.objectId == item.inferenceObjectId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$InferenceObjectsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $InferenceObjectsTable,
      InferenceObjectRow,
      $$InferenceObjectsTableFilterComposer,
      $$InferenceObjectsTableOrderingComposer,
      $$InferenceObjectsTableAnnotationComposer,
      $$InferenceObjectsTableCreateCompanionBuilder,
      $$InferenceObjectsTableUpdateCompanionBuilder,
      (InferenceObjectRow, $$InferenceObjectsTableReferences),
      InferenceObjectRow,
      PrefetchHooks Function({
        bool attemptId,
        bool inferenceCandidatesRefs,
        bool objectResolutionsRefs,
        bool adminReviewAnnotationsRefs,
      })
    >;
typedef $$InferenceCandidatesTableCreateCompanionBuilder =
    InferenceCandidatesCompanion Function({
      required String inferenceCandidateId,
      required String inferenceObjectId,
      required int rank,
      required int skuId,
      required String skuName,
      required double score,
      Value<int> rowid,
    });
typedef $$InferenceCandidatesTableUpdateCompanionBuilder =
    InferenceCandidatesCompanion Function({
      Value<String> inferenceCandidateId,
      Value<String> inferenceObjectId,
      Value<int> rank,
      Value<int> skuId,
      Value<String> skuName,
      Value<double> score,
      Value<int> rowid,
    });

final class $$InferenceCandidatesTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $InferenceCandidatesTable,
          InferenceCandidateRow
        > {
  $$InferenceCandidatesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $InferenceObjectsTable _inferenceObjectIdTable(
    _$BakeryDatabase db,
  ) => db.inferenceObjects.createAlias(
    'inference_candidates__inference_object_id__inference_objects__inference_object_id',
  );

  $$InferenceObjectsTableProcessedTableManager get inferenceObjectId {
    final $_column = $_itemColumn<String>('inference_object_id')!;

    final manager = $$InferenceObjectsTableTableManager(
      $_db,
      $_db.inferenceObjects,
    ).filter((f) => f.inferenceObjectId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_inferenceObjectIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$InferenceCandidatesTableFilterComposer
    extends Composer<_$BakeryDatabase, $InferenceCandidatesTable> {
  $$InferenceCandidatesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get inferenceCandidateId => $composableBuilder(
    column: $table.inferenceCandidateId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get rank => $composableBuilder(
    column: $table.rank,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get skuId => $composableBuilder(
    column: $table.skuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get skuName => $composableBuilder(
    column: $table.skuName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<double> get score => $composableBuilder(
    column: $table.score,
    builder: (column) => ColumnFilters(column),
  );

  $$InferenceObjectsTableFilterComposer get inferenceObjectId {
    final $$InferenceObjectsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableFilterComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$InferenceCandidatesTableOrderingComposer
    extends Composer<_$BakeryDatabase, $InferenceCandidatesTable> {
  $$InferenceCandidatesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get inferenceCandidateId => $composableBuilder(
    column: $table.inferenceCandidateId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get rank => $composableBuilder(
    column: $table.rank,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get skuId => $composableBuilder(
    column: $table.skuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get skuName => $composableBuilder(
    column: $table.skuName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<double> get score => $composableBuilder(
    column: $table.score,
    builder: (column) => ColumnOrderings(column),
  );

  $$InferenceObjectsTableOrderingComposer get inferenceObjectId {
    final $$InferenceObjectsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableOrderingComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$InferenceCandidatesTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $InferenceCandidatesTable> {
  $$InferenceCandidatesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get inferenceCandidateId => $composableBuilder(
    column: $table.inferenceCandidateId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get rank =>
      $composableBuilder(column: $table.rank, builder: (column) => column);

  GeneratedColumn<int> get skuId =>
      $composableBuilder(column: $table.skuId, builder: (column) => column);

  GeneratedColumn<String> get skuName =>
      $composableBuilder(column: $table.skuName, builder: (column) => column);

  GeneratedColumn<double> get score =>
      $composableBuilder(column: $table.score, builder: (column) => column);

  $$InferenceObjectsTableAnnotationComposer get inferenceObjectId {
    final $$InferenceObjectsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableAnnotationComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$InferenceCandidatesTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $InferenceCandidatesTable,
          InferenceCandidateRow,
          $$InferenceCandidatesTableFilterComposer,
          $$InferenceCandidatesTableOrderingComposer,
          $$InferenceCandidatesTableAnnotationComposer,
          $$InferenceCandidatesTableCreateCompanionBuilder,
          $$InferenceCandidatesTableUpdateCompanionBuilder,
          (InferenceCandidateRow, $$InferenceCandidatesTableReferences),
          InferenceCandidateRow,
          PrefetchHooks Function({bool inferenceObjectId})
        > {
  $$InferenceCandidatesTableTableManager(
    _$BakeryDatabase db,
    $InferenceCandidatesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$InferenceCandidatesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$InferenceCandidatesTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer: () =>
              $$InferenceCandidatesTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> inferenceCandidateId = const Value.absent(),
                Value<String> inferenceObjectId = const Value.absent(),
                Value<int> rank = const Value.absent(),
                Value<int> skuId = const Value.absent(),
                Value<String> skuName = const Value.absent(),
                Value<double> score = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => InferenceCandidatesCompanion(
                inferenceCandidateId: inferenceCandidateId,
                inferenceObjectId: inferenceObjectId,
                rank: rank,
                skuId: skuId,
                skuName: skuName,
                score: score,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String inferenceCandidateId,
                required String inferenceObjectId,
                required int rank,
                required int skuId,
                required String skuName,
                required double score,
                Value<int> rowid = const Value.absent(),
              }) => InferenceCandidatesCompanion.insert(
                inferenceCandidateId: inferenceCandidateId,
                inferenceObjectId: inferenceObjectId,
                rank: rank,
                skuId: skuId,
                skuName: skuName,
                score: score,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$InferenceCandidatesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({inferenceObjectId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (inferenceObjectId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.inferenceObjectId,
                                referencedTable:
                                    $$InferenceCandidatesTableReferences
                                        ._inferenceObjectIdTable(db),
                                referencedColumn:
                                    $$InferenceCandidatesTableReferences
                                        ._inferenceObjectIdTable(db)
                                        .inferenceObjectId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$InferenceCandidatesTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $InferenceCandidatesTable,
      InferenceCandidateRow,
      $$InferenceCandidatesTableFilterComposer,
      $$InferenceCandidatesTableOrderingComposer,
      $$InferenceCandidatesTableAnnotationComposer,
      $$InferenceCandidatesTableCreateCompanionBuilder,
      $$InferenceCandidatesTableUpdateCompanionBuilder,
      (InferenceCandidateRow, $$InferenceCandidatesTableReferences),
      InferenceCandidateRow,
      PrefetchHooks Function({bool inferenceObjectId})
    >;
typedef $$ObjectResolutionsTableCreateCompanionBuilder =
    ObjectResolutionsCompanion Function({
      required String resolutionId,
      required String sessionId,
      Value<String?> inferenceObjectId,
      required String productRevisionId,
      required String productId,
      Value<int?> recognitionSkuId,
      required String productName,
      required int unitPriceKrw,
      required String source,
      required int resolvedAtUs,
      Value<int?> candidateRank,
      Value<String?> canonicalBboxJson,
      required bool isCurrent,
      Value<int> rowid,
    });
typedef $$ObjectResolutionsTableUpdateCompanionBuilder =
    ObjectResolutionsCompanion Function({
      Value<String> resolutionId,
      Value<String> sessionId,
      Value<String?> inferenceObjectId,
      Value<String> productRevisionId,
      Value<String> productId,
      Value<int?> recognitionSkuId,
      Value<String> productName,
      Value<int> unitPriceKrw,
      Value<String> source,
      Value<int> resolvedAtUs,
      Value<int?> candidateRank,
      Value<String?> canonicalBboxJson,
      Value<bool> isCurrent,
      Value<int> rowid,
    });

final class $$ObjectResolutionsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $ObjectResolutionsTable,
          ObjectResolutionRow
        > {
  $$ObjectResolutionsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) =>
      db.checkoutSessions.createAlias(
        'object_resolutions__session_id__checkout_sessions__session_id',
      );

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $InferenceObjectsTable _inferenceObjectIdTable(
    _$BakeryDatabase db,
  ) => db.inferenceObjects.createAlias(
    'object_resolutions__inference_object_id__inference_objects__inference_object_id',
  );

  $$InferenceObjectsTableProcessedTableManager? get inferenceObjectId {
    final $_column = $_itemColumn<String>('inference_object_id');
    if ($_column == null) return null;
    final manager = $$InferenceObjectsTableTableManager(
      $_db,
      $_db.inferenceObjects,
    ).filter((f) => f.inferenceObjectId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_inferenceObjectIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $ProductsTable _productRevisionIdTable(
    _$BakeryDatabase db,
  ) => db.products.createAlias(
    'object_resolutions__product_revision_id__products__product_revision_id',
  );

  $$ProductsTableProcessedTableManager get productRevisionId {
    final $_column = $_itemColumn<String>('product_revision_id')!;

    final manager = $$ProductsTableTableManager(
      $_db,
      $_db.products,
    ).filter((f) => f.productRevisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_productRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$ObjectResolutionsTableFilterComposer
    extends Composer<_$BakeryDatabase, $ObjectResolutionsTable> {
  $$ObjectResolutionsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get resolutionId => $composableBuilder(
    column: $table.resolutionId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get source => $composableBuilder(
    column: $table.source,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get resolvedAtUs => $composableBuilder(
    column: $table.resolvedAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get candidateRank => $composableBuilder(
    column: $table.candidateRank,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get canonicalBboxJson => $composableBuilder(
    column: $table.canonicalBboxJson,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isCurrent => $composableBuilder(
    column: $table.isCurrent,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableFilterComposer get inferenceObjectId {
    final $$InferenceObjectsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableFilterComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableFilterComposer get productRevisionId {
    final $$ProductsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableFilterComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ObjectResolutionsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $ObjectResolutionsTable> {
  $$ObjectResolutionsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get resolutionId => $composableBuilder(
    column: $table.resolutionId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get source => $composableBuilder(
    column: $table.source,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get resolvedAtUs => $composableBuilder(
    column: $table.resolvedAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get candidateRank => $composableBuilder(
    column: $table.candidateRank,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get canonicalBboxJson => $composableBuilder(
    column: $table.canonicalBboxJson,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isCurrent => $composableBuilder(
    column: $table.isCurrent,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableOrderingComposer get inferenceObjectId {
    final $$InferenceObjectsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableOrderingComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableOrderingComposer get productRevisionId {
    final $$ProductsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableOrderingComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ObjectResolutionsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $ObjectResolutionsTable> {
  $$ObjectResolutionsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get resolutionId => $composableBuilder(
    column: $table.resolutionId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productId =>
      $composableBuilder(column: $table.productId, builder: (column) => column);

  GeneratedColumn<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => column,
  );

  GeneratedColumn<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => column,
  );

  GeneratedColumn<String> get source =>
      $composableBuilder(column: $table.source, builder: (column) => column);

  GeneratedColumn<int> get resolvedAtUs => $composableBuilder(
    column: $table.resolvedAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<int> get candidateRank => $composableBuilder(
    column: $table.candidateRank,
    builder: (column) => column,
  );

  GeneratedColumn<String> get canonicalBboxJson => $composableBuilder(
    column: $table.canonicalBboxJson,
    builder: (column) => column,
  );

  GeneratedColumn<bool> get isCurrent =>
      $composableBuilder(column: $table.isCurrent, builder: (column) => column);

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableAnnotationComposer get inferenceObjectId {
    final $$InferenceObjectsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.inferenceObjectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableAnnotationComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableAnnotationComposer get productRevisionId {
    final $$ProductsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableAnnotationComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$ObjectResolutionsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $ObjectResolutionsTable,
          ObjectResolutionRow,
          $$ObjectResolutionsTableFilterComposer,
          $$ObjectResolutionsTableOrderingComposer,
          $$ObjectResolutionsTableAnnotationComposer,
          $$ObjectResolutionsTableCreateCompanionBuilder,
          $$ObjectResolutionsTableUpdateCompanionBuilder,
          (ObjectResolutionRow, $$ObjectResolutionsTableReferences),
          ObjectResolutionRow,
          PrefetchHooks Function({
            bool sessionId,
            bool inferenceObjectId,
            bool productRevisionId,
          })
        > {
  $$ObjectResolutionsTableTableManager(
    _$BakeryDatabase db,
    $ObjectResolutionsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ObjectResolutionsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ObjectResolutionsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ObjectResolutionsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> resolutionId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<String?> inferenceObjectId = const Value.absent(),
                Value<String> productRevisionId = const Value.absent(),
                Value<String> productId = const Value.absent(),
                Value<int?> recognitionSkuId = const Value.absent(),
                Value<String> productName = const Value.absent(),
                Value<int> unitPriceKrw = const Value.absent(),
                Value<String> source = const Value.absent(),
                Value<int> resolvedAtUs = const Value.absent(),
                Value<int?> candidateRank = const Value.absent(),
                Value<String?> canonicalBboxJson = const Value.absent(),
                Value<bool> isCurrent = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ObjectResolutionsCompanion(
                resolutionId: resolutionId,
                sessionId: sessionId,
                inferenceObjectId: inferenceObjectId,
                productRevisionId: productRevisionId,
                productId: productId,
                recognitionSkuId: recognitionSkuId,
                productName: productName,
                unitPriceKrw: unitPriceKrw,
                source: source,
                resolvedAtUs: resolvedAtUs,
                candidateRank: candidateRank,
                canonicalBboxJson: canonicalBboxJson,
                isCurrent: isCurrent,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String resolutionId,
                required String sessionId,
                Value<String?> inferenceObjectId = const Value.absent(),
                required String productRevisionId,
                required String productId,
                Value<int?> recognitionSkuId = const Value.absent(),
                required String productName,
                required int unitPriceKrw,
                required String source,
                required int resolvedAtUs,
                Value<int?> candidateRank = const Value.absent(),
                Value<String?> canonicalBboxJson = const Value.absent(),
                required bool isCurrent,
                Value<int> rowid = const Value.absent(),
              }) => ObjectResolutionsCompanion.insert(
                resolutionId: resolutionId,
                sessionId: sessionId,
                inferenceObjectId: inferenceObjectId,
                productRevisionId: productRevisionId,
                productId: productId,
                recognitionSkuId: recognitionSkuId,
                productName: productName,
                unitPriceKrw: unitPriceKrw,
                source: source,
                resolvedAtUs: resolvedAtUs,
                candidateRank: candidateRank,
                canonicalBboxJson: canonicalBboxJson,
                isCurrent: isCurrent,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$ObjectResolutionsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                sessionId = false,
                inferenceObjectId = false,
                productRevisionId = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (sessionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sessionId,
                                    referencedTable:
                                        $$ObjectResolutionsTableReferences
                                            ._sessionIdTable(db),
                                    referencedColumn:
                                        $$ObjectResolutionsTableReferences
                                            ._sessionIdTable(db)
                                            .sessionId,
                                  )
                                  as T;
                        }
                        if (inferenceObjectId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.inferenceObjectId,
                                    referencedTable:
                                        $$ObjectResolutionsTableReferences
                                            ._inferenceObjectIdTable(db),
                                    referencedColumn:
                                        $$ObjectResolutionsTableReferences
                                            ._inferenceObjectIdTable(db)
                                            .inferenceObjectId,
                                  )
                                  as T;
                        }
                        if (productRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.productRevisionId,
                                    referencedTable:
                                        $$ObjectResolutionsTableReferences
                                            ._productRevisionIdTable(db),
                                    referencedColumn:
                                        $$ObjectResolutionsTableReferences
                                            ._productRevisionIdTable(db)
                                            .productRevisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$ObjectResolutionsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $ObjectResolutionsTable,
      ObjectResolutionRow,
      $$ObjectResolutionsTableFilterComposer,
      $$ObjectResolutionsTableOrderingComposer,
      $$ObjectResolutionsTableAnnotationComposer,
      $$ObjectResolutionsTableCreateCompanionBuilder,
      $$ObjectResolutionsTableUpdateCompanionBuilder,
      (ObjectResolutionRow, $$ObjectResolutionsTableReferences),
      ObjectResolutionRow,
      PrefetchHooks Function({
        bool sessionId,
        bool inferenceObjectId,
        bool productRevisionId,
      })
    >;
typedef $$DraftOrderLinesTableCreateCompanionBuilder =
    DraftOrderLinesCompanion Function({
      required String draftLineId,
      required String sessionId,
      required String productRevisionId,
      required String productId,
      required String productName,
      Value<int?> recognitionSkuId,
      required int unitPriceKrw,
      required int quantity,
      Value<int> rowid,
    });
typedef $$DraftOrderLinesTableUpdateCompanionBuilder =
    DraftOrderLinesCompanion Function({
      Value<String> draftLineId,
      Value<String> sessionId,
      Value<String> productRevisionId,
      Value<String> productId,
      Value<String> productName,
      Value<int?> recognitionSkuId,
      Value<int> unitPriceKrw,
      Value<int> quantity,
      Value<int> rowid,
    });

final class $$DraftOrderLinesTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $DraftOrderLinesTable,
          DraftOrderLineRow
        > {
  $$DraftOrderLinesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) =>
      db.checkoutSessions.createAlias(
        'draft_order_lines__session_id__checkout_sessions__session_id',
      );

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $ProductsTable _productRevisionIdTable(_$BakeryDatabase db) =>
      db.products.createAlias(
        'draft_order_lines__product_revision_id__products__product_revision_id',
      );

  $$ProductsTableProcessedTableManager get productRevisionId {
    final $_column = $_itemColumn<String>('product_revision_id')!;

    final manager = $$ProductsTableTableManager(
      $_db,
      $_db.products,
    ).filter((f) => f.productRevisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_productRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$DraftOrderLinesTableFilterComposer
    extends Composer<_$BakeryDatabase, $DraftOrderLinesTable> {
  $$DraftOrderLinesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get draftLineId => $composableBuilder(
    column: $table.draftLineId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableFilterComposer get productRevisionId {
    final $$ProductsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableFilterComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$DraftOrderLinesTableOrderingComposer
    extends Composer<_$BakeryDatabase, $DraftOrderLinesTable> {
  $$DraftOrderLinesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get draftLineId => $composableBuilder(
    column: $table.draftLineId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableOrderingComposer get productRevisionId {
    final $$ProductsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableOrderingComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$DraftOrderLinesTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $DraftOrderLinesTable> {
  $$DraftOrderLinesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get draftLineId => $composableBuilder(
    column: $table.draftLineId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productId =>
      $composableBuilder(column: $table.productId, builder: (column) => column);

  GeneratedColumn<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => column,
  );

  GeneratedColumn<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => column,
  );

  GeneratedColumn<int> get quantity =>
      $composableBuilder(column: $table.quantity, builder: (column) => column);

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableAnnotationComposer get productRevisionId {
    final $$ProductsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableAnnotationComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$DraftOrderLinesTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $DraftOrderLinesTable,
          DraftOrderLineRow,
          $$DraftOrderLinesTableFilterComposer,
          $$DraftOrderLinesTableOrderingComposer,
          $$DraftOrderLinesTableAnnotationComposer,
          $$DraftOrderLinesTableCreateCompanionBuilder,
          $$DraftOrderLinesTableUpdateCompanionBuilder,
          (DraftOrderLineRow, $$DraftOrderLinesTableReferences),
          DraftOrderLineRow,
          PrefetchHooks Function({bool sessionId, bool productRevisionId})
        > {
  $$DraftOrderLinesTableTableManager(
    _$BakeryDatabase db,
    $DraftOrderLinesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$DraftOrderLinesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$DraftOrderLinesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$DraftOrderLinesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> draftLineId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<String> productRevisionId = const Value.absent(),
                Value<String> productId = const Value.absent(),
                Value<String> productName = const Value.absent(),
                Value<int?> recognitionSkuId = const Value.absent(),
                Value<int> unitPriceKrw = const Value.absent(),
                Value<int> quantity = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => DraftOrderLinesCompanion(
                draftLineId: draftLineId,
                sessionId: sessionId,
                productRevisionId: productRevisionId,
                productId: productId,
                productName: productName,
                recognitionSkuId: recognitionSkuId,
                unitPriceKrw: unitPriceKrw,
                quantity: quantity,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String draftLineId,
                required String sessionId,
                required String productRevisionId,
                required String productId,
                required String productName,
                Value<int?> recognitionSkuId = const Value.absent(),
                required int unitPriceKrw,
                required int quantity,
                Value<int> rowid = const Value.absent(),
              }) => DraftOrderLinesCompanion.insert(
                draftLineId: draftLineId,
                sessionId: sessionId,
                productRevisionId: productRevisionId,
                productId: productId,
                productName: productName,
                recognitionSkuId: recognitionSkuId,
                unitPriceKrw: unitPriceKrw,
                quantity: quantity,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$DraftOrderLinesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({sessionId = false, productRevisionId = false}) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (sessionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sessionId,
                                    referencedTable:
                                        $$DraftOrderLinesTableReferences
                                            ._sessionIdTable(db),
                                    referencedColumn:
                                        $$DraftOrderLinesTableReferences
                                            ._sessionIdTable(db)
                                            .sessionId,
                                  )
                                  as T;
                        }
                        if (productRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.productRevisionId,
                                    referencedTable:
                                        $$DraftOrderLinesTableReferences
                                            ._productRevisionIdTable(db),
                                    referencedColumn:
                                        $$DraftOrderLinesTableReferences
                                            ._productRevisionIdTable(db)
                                            .productRevisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$DraftOrderLinesTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $DraftOrderLinesTable,
      DraftOrderLineRow,
      $$DraftOrderLinesTableFilterComposer,
      $$DraftOrderLinesTableOrderingComposer,
      $$DraftOrderLinesTableAnnotationComposer,
      $$DraftOrderLinesTableCreateCompanionBuilder,
      $$DraftOrderLinesTableUpdateCompanionBuilder,
      (DraftOrderLineRow, $$DraftOrderLinesTableReferences),
      DraftOrderLineRow,
      PrefetchHooks Function({bool sessionId, bool productRevisionId})
    >;
typedef $$FinalOrdersTableCreateCompanionBuilder =
    FinalOrdersCompanion Function({
      required String orderId,
      required String sessionId,
      required String catalogRevisionId,
      required int createdAtUs,
      required int totalQuantity,
      required int totalAmountKrw,
      required String receiptRelativePath,
      required int receiptByteSize,
      required String receiptSha256,
      Value<int> rowid,
    });
typedef $$FinalOrdersTableUpdateCompanionBuilder =
    FinalOrdersCompanion Function({
      Value<String> orderId,
      Value<String> sessionId,
      Value<String> catalogRevisionId,
      Value<int> createdAtUs,
      Value<int> totalQuantity,
      Value<int> totalAmountKrw,
      Value<String> receiptRelativePath,
      Value<int> receiptByteSize,
      Value<String> receiptSha256,
      Value<int> rowid,
    });

final class $$FinalOrdersTableReferences
    extends BaseReferences<_$BakeryDatabase, $FinalOrdersTable, FinalOrderRow> {
  $$FinalOrdersTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) => db
      .checkoutSessions
      .createAlias('final_orders__session_id__checkout_sessions__session_id');

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $CatalogRevisionsTable _catalogRevisionIdTable(_$BakeryDatabase db) =>
      db.catalogRevisions.createAlias(
        'final_orders__catalog_revision_id__catalog_revisions__revision_id',
      );

  $$CatalogRevisionsTableProcessedTableManager get catalogRevisionId {
    final $_column = $_itemColumn<String>('catalog_revision_id')!;

    final manager = $$CatalogRevisionsTableTableManager(
      $_db,
      $_db.catalogRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_catalogRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static MultiTypedResultKey<$FinalOrderLinesTable, List<FinalOrderLineRow>>
  _finalOrderLinesRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.finalOrderLines,
        aliasName: 'final_orders__order_id__final_order_lines__order_id',
      );

  $$FinalOrderLinesTableProcessedTableManager get finalOrderLinesRefs {
    final manager =
        $$FinalOrderLinesTableTableManager($_db, $_db.finalOrderLines).filter(
          (f) => f.orderId.orderId.sqlEquals($_itemColumn<String>('order_id')!),
        );

    final cache = $_typedResult.readTableOrNull(
      _finalOrderLinesRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }

  static MultiTypedResultKey<$SimulatedPaymentsTable, List<SimulatedPaymentRow>>
  _simulatedPaymentsRefsTable(_$BakeryDatabase db) =>
      MultiTypedResultKey.fromTable(
        db.simulatedPayments,
        aliasName: 'final_orders__order_id__simulated_payments__order_id',
      );

  $$SimulatedPaymentsTableProcessedTableManager get simulatedPaymentsRefs {
    final manager =
        $$SimulatedPaymentsTableTableManager(
          $_db,
          $_db.simulatedPayments,
        ).filter(
          (f) => f.orderId.orderId.sqlEquals($_itemColumn<String>('order_id')!),
        );

    final cache = $_typedResult.readTableOrNull(
      _simulatedPaymentsRefsTable($_db),
    );
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: cache),
    );
  }
}

class $$FinalOrdersTableFilterComposer
    extends Composer<_$BakeryDatabase, $FinalOrdersTable> {
  $$FinalOrdersTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get orderId => $composableBuilder(
    column: $table.orderId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get totalQuantity => $composableBuilder(
    column: $table.totalQuantity,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get totalAmountKrw => $composableBuilder(
    column: $table.totalAmountKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CatalogRevisionsTableFilterComposer get catalogRevisionId {
    final $$CatalogRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<bool> finalOrderLinesRefs(
    Expression<bool> Function($$FinalOrderLinesTableFilterComposer f) f,
  ) {
    final $$FinalOrderLinesTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrderLines,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrderLinesTableFilterComposer(
            $db: $db,
            $table: $db.finalOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<bool> simulatedPaymentsRefs(
    Expression<bool> Function($$SimulatedPaymentsTableFilterComposer f) f,
  ) {
    final $$SimulatedPaymentsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.simulatedPayments,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SimulatedPaymentsTableFilterComposer(
            $db: $db,
            $table: $db.simulatedPayments,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }
}

class $$FinalOrdersTableOrderingComposer
    extends Composer<_$BakeryDatabase, $FinalOrdersTable> {
  $$FinalOrdersTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get orderId => $composableBuilder(
    column: $table.orderId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get totalQuantity => $composableBuilder(
    column: $table.totalQuantity,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get totalAmountKrw => $composableBuilder(
    column: $table.totalAmountKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CatalogRevisionsTableOrderingComposer get catalogRevisionId {
    final $$CatalogRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$FinalOrdersTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $FinalOrdersTable> {
  $$FinalOrdersTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get orderId =>
      $composableBuilder(column: $table.orderId, builder: (column) => column);

  GeneratedColumn<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<int> get totalQuantity => $composableBuilder(
    column: $table.totalQuantity,
    builder: (column) => column,
  );

  GeneratedColumn<int> get totalAmountKrw => $composableBuilder(
    column: $table.totalAmountKrw,
    builder: (column) => column,
  );

  GeneratedColumn<String> get receiptRelativePath => $composableBuilder(
    column: $table.receiptRelativePath,
    builder: (column) => column,
  );

  GeneratedColumn<int> get receiptByteSize => $composableBuilder(
    column: $table.receiptByteSize,
    builder: (column) => column,
  );

  GeneratedColumn<String> get receiptSha256 => $composableBuilder(
    column: $table.receiptSha256,
    builder: (column) => column,
  );

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CatalogRevisionsTableAnnotationComposer get catalogRevisionId {
    final $$CatalogRevisionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.catalogRevisionId,
      referencedTable: $db.catalogRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CatalogRevisionsTableAnnotationComposer(
            $db: $db,
            $table: $db.catalogRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  Expression<T> finalOrderLinesRefs<T extends Object>(
    Expression<T> Function($$FinalOrderLinesTableAnnotationComposer a) f,
  ) {
    final $$FinalOrderLinesTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrderLines,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrderLinesTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrderLines,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return f(composer);
  }

  Expression<T> simulatedPaymentsRefs<T extends Object>(
    Expression<T> Function($$SimulatedPaymentsTableAnnotationComposer a) f,
  ) {
    final $$SimulatedPaymentsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.orderId,
          referencedTable: $db.simulatedPayments,
          getReferencedColumn: (t) => t.orderId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SimulatedPaymentsTableAnnotationComposer(
                $db: $db,
                $table: $db.simulatedPayments,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return f(composer);
  }
}

class $$FinalOrdersTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $FinalOrdersTable,
          FinalOrderRow,
          $$FinalOrdersTableFilterComposer,
          $$FinalOrdersTableOrderingComposer,
          $$FinalOrdersTableAnnotationComposer,
          $$FinalOrdersTableCreateCompanionBuilder,
          $$FinalOrdersTableUpdateCompanionBuilder,
          (FinalOrderRow, $$FinalOrdersTableReferences),
          FinalOrderRow,
          PrefetchHooks Function({
            bool sessionId,
            bool catalogRevisionId,
            bool finalOrderLinesRefs,
            bool simulatedPaymentsRefs,
          })
        > {
  $$FinalOrdersTableTableManager(_$BakeryDatabase db, $FinalOrdersTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$FinalOrdersTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$FinalOrdersTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$FinalOrdersTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> orderId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<String> catalogRevisionId = const Value.absent(),
                Value<int> createdAtUs = const Value.absent(),
                Value<int> totalQuantity = const Value.absent(),
                Value<int> totalAmountKrw = const Value.absent(),
                Value<String> receiptRelativePath = const Value.absent(),
                Value<int> receiptByteSize = const Value.absent(),
                Value<String> receiptSha256 = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => FinalOrdersCompanion(
                orderId: orderId,
                sessionId: sessionId,
                catalogRevisionId: catalogRevisionId,
                createdAtUs: createdAtUs,
                totalQuantity: totalQuantity,
                totalAmountKrw: totalAmountKrw,
                receiptRelativePath: receiptRelativePath,
                receiptByteSize: receiptByteSize,
                receiptSha256: receiptSha256,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String orderId,
                required String sessionId,
                required String catalogRevisionId,
                required int createdAtUs,
                required int totalQuantity,
                required int totalAmountKrw,
                required String receiptRelativePath,
                required int receiptByteSize,
                required String receiptSha256,
                Value<int> rowid = const Value.absent(),
              }) => FinalOrdersCompanion.insert(
                orderId: orderId,
                sessionId: sessionId,
                catalogRevisionId: catalogRevisionId,
                createdAtUs: createdAtUs,
                totalQuantity: totalQuantity,
                totalAmountKrw: totalAmountKrw,
                receiptRelativePath: receiptRelativePath,
                receiptByteSize: receiptByteSize,
                receiptSha256: receiptSha256,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$FinalOrdersTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({
                sessionId = false,
                catalogRevisionId = false,
                finalOrderLinesRefs = false,
                simulatedPaymentsRefs = false,
              }) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [
                    if (finalOrderLinesRefs) db.finalOrderLines,
                    if (simulatedPaymentsRefs) db.simulatedPayments,
                  ],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (sessionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sessionId,
                                    referencedTable:
                                        $$FinalOrdersTableReferences
                                            ._sessionIdTable(db),
                                    referencedColumn:
                                        $$FinalOrdersTableReferences
                                            ._sessionIdTable(db)
                                            .sessionId,
                                  )
                                  as T;
                        }
                        if (catalogRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.catalogRevisionId,
                                    referencedTable:
                                        $$FinalOrdersTableReferences
                                            ._catalogRevisionIdTable(db),
                                    referencedColumn:
                                        $$FinalOrdersTableReferences
                                            ._catalogRevisionIdTable(db)
                                            .revisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [
                      if (finalOrderLinesRefs)
                        await $_getPrefetchedData<
                          FinalOrderRow,
                          $FinalOrdersTable,
                          FinalOrderLineRow
                        >(
                          currentTable: table,
                          referencedTable: $$FinalOrdersTableReferences
                              ._finalOrderLinesRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$FinalOrdersTableReferences(
                                db,
                                table,
                                p0,
                              ).finalOrderLinesRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.orderId == item.orderId,
                              ),
                          typedResults: items,
                        ),
                      if (simulatedPaymentsRefs)
                        await $_getPrefetchedData<
                          FinalOrderRow,
                          $FinalOrdersTable,
                          SimulatedPaymentRow
                        >(
                          currentTable: table,
                          referencedTable: $$FinalOrdersTableReferences
                              ._simulatedPaymentsRefsTable(db),
                          managerFromTypedResult: (p0) =>
                              $$FinalOrdersTableReferences(
                                db,
                                table,
                                p0,
                              ).simulatedPaymentsRefs,
                          referencedItemsForCurrentItem:
                              (item, referencedItems) => referencedItems.where(
                                (e) => e.orderId == item.orderId,
                              ),
                          typedResults: items,
                        ),
                    ];
                  },
                );
              },
        ),
      );
}

typedef $$FinalOrdersTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $FinalOrdersTable,
      FinalOrderRow,
      $$FinalOrdersTableFilterComposer,
      $$FinalOrdersTableOrderingComposer,
      $$FinalOrdersTableAnnotationComposer,
      $$FinalOrdersTableCreateCompanionBuilder,
      $$FinalOrdersTableUpdateCompanionBuilder,
      (FinalOrderRow, $$FinalOrdersTableReferences),
      FinalOrderRow,
      PrefetchHooks Function({
        bool sessionId,
        bool catalogRevisionId,
        bool finalOrderLinesRefs,
        bool simulatedPaymentsRefs,
      })
    >;
typedef $$FinalOrderLinesTableCreateCompanionBuilder =
    FinalOrderLinesCompanion Function({
      required String finalLineId,
      required String orderId,
      required String productRevisionId,
      required String productId,
      Value<int?> recognitionSkuId,
      required String productName,
      required int unitPriceKrw,
      required int quantity,
      required int lineAmountKrw,
      required String resolutionSource,
      Value<int> rowid,
    });
typedef $$FinalOrderLinesTableUpdateCompanionBuilder =
    FinalOrderLinesCompanion Function({
      Value<String> finalLineId,
      Value<String> orderId,
      Value<String> productRevisionId,
      Value<String> productId,
      Value<int?> recognitionSkuId,
      Value<String> productName,
      Value<int> unitPriceKrw,
      Value<int> quantity,
      Value<int> lineAmountKrw,
      Value<String> resolutionSource,
      Value<int> rowid,
    });

final class $$FinalOrderLinesTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $FinalOrderLinesTable,
          FinalOrderLineRow
        > {
  $$FinalOrderLinesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $FinalOrdersTable _orderIdTable(_$BakeryDatabase db) => db.finalOrders
      .createAlias('final_order_lines__order_id__final_orders__order_id');

  $$FinalOrdersTableProcessedTableManager get orderId {
    final $_column = $_itemColumn<String>('order_id')!;

    final manager = $$FinalOrdersTableTableManager(
      $_db,
      $_db.finalOrders,
    ).filter((f) => f.orderId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_orderIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $ProductsTable _productRevisionIdTable(_$BakeryDatabase db) =>
      db.products.createAlias(
        'final_order_lines__product_revision_id__products__product_revision_id',
      );

  $$ProductsTableProcessedTableManager get productRevisionId {
    final $_column = $_itemColumn<String>('product_revision_id')!;

    final manager = $$ProductsTableTableManager(
      $_db,
      $_db.products,
    ).filter((f) => f.productRevisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_productRevisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$FinalOrderLinesTableFilterComposer
    extends Composer<_$BakeryDatabase, $FinalOrderLinesTable> {
  $$FinalOrderLinesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get finalLineId => $composableBuilder(
    column: $table.finalLineId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get lineAmountKrw => $composableBuilder(
    column: $table.lineAmountKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get resolutionSource => $composableBuilder(
    column: $table.resolutionSource,
    builder: (column) => ColumnFilters(column),
  );

  $$FinalOrdersTableFilterComposer get orderId {
    final $$FinalOrdersTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableFilterComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableFilterComposer get productRevisionId {
    final $$ProductsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableFilterComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$FinalOrderLinesTableOrderingComposer
    extends Composer<_$BakeryDatabase, $FinalOrderLinesTable> {
  $$FinalOrderLinesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get finalLineId => $composableBuilder(
    column: $table.finalLineId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productId => $composableBuilder(
    column: $table.productId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get quantity => $composableBuilder(
    column: $table.quantity,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get lineAmountKrw => $composableBuilder(
    column: $table.lineAmountKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get resolutionSource => $composableBuilder(
    column: $table.resolutionSource,
    builder: (column) => ColumnOrderings(column),
  );

  $$FinalOrdersTableOrderingComposer get orderId {
    final $$FinalOrdersTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableOrderingComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableOrderingComposer get productRevisionId {
    final $$ProductsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableOrderingComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$FinalOrderLinesTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $FinalOrderLinesTable> {
  $$FinalOrderLinesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get finalLineId => $composableBuilder(
    column: $table.finalLineId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productId =>
      $composableBuilder(column: $table.productId, builder: (column) => column);

  GeneratedColumn<int> get recognitionSkuId => $composableBuilder(
    column: $table.recognitionSkuId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get productName => $composableBuilder(
    column: $table.productName,
    builder: (column) => column,
  );

  GeneratedColumn<int> get unitPriceKrw => $composableBuilder(
    column: $table.unitPriceKrw,
    builder: (column) => column,
  );

  GeneratedColumn<int> get quantity =>
      $composableBuilder(column: $table.quantity, builder: (column) => column);

  GeneratedColumn<int> get lineAmountKrw => $composableBuilder(
    column: $table.lineAmountKrw,
    builder: (column) => column,
  );

  GeneratedColumn<String> get resolutionSource => $composableBuilder(
    column: $table.resolutionSource,
    builder: (column) => column,
  );

  $$FinalOrdersTableAnnotationComposer get orderId {
    final $$FinalOrdersTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ProductsTableAnnotationComposer get productRevisionId {
    final $$ProductsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.productRevisionId,
      referencedTable: $db.products,
      getReferencedColumn: (t) => t.productRevisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ProductsTableAnnotationComposer(
            $db: $db,
            $table: $db.products,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$FinalOrderLinesTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $FinalOrderLinesTable,
          FinalOrderLineRow,
          $$FinalOrderLinesTableFilterComposer,
          $$FinalOrderLinesTableOrderingComposer,
          $$FinalOrderLinesTableAnnotationComposer,
          $$FinalOrderLinesTableCreateCompanionBuilder,
          $$FinalOrderLinesTableUpdateCompanionBuilder,
          (FinalOrderLineRow, $$FinalOrderLinesTableReferences),
          FinalOrderLineRow,
          PrefetchHooks Function({bool orderId, bool productRevisionId})
        > {
  $$FinalOrderLinesTableTableManager(
    _$BakeryDatabase db,
    $FinalOrderLinesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$FinalOrderLinesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$FinalOrderLinesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$FinalOrderLinesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> finalLineId = const Value.absent(),
                Value<String> orderId = const Value.absent(),
                Value<String> productRevisionId = const Value.absent(),
                Value<String> productId = const Value.absent(),
                Value<int?> recognitionSkuId = const Value.absent(),
                Value<String> productName = const Value.absent(),
                Value<int> unitPriceKrw = const Value.absent(),
                Value<int> quantity = const Value.absent(),
                Value<int> lineAmountKrw = const Value.absent(),
                Value<String> resolutionSource = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => FinalOrderLinesCompanion(
                finalLineId: finalLineId,
                orderId: orderId,
                productRevisionId: productRevisionId,
                productId: productId,
                recognitionSkuId: recognitionSkuId,
                productName: productName,
                unitPriceKrw: unitPriceKrw,
                quantity: quantity,
                lineAmountKrw: lineAmountKrw,
                resolutionSource: resolutionSource,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String finalLineId,
                required String orderId,
                required String productRevisionId,
                required String productId,
                Value<int?> recognitionSkuId = const Value.absent(),
                required String productName,
                required int unitPriceKrw,
                required int quantity,
                required int lineAmountKrw,
                required String resolutionSource,
                Value<int> rowid = const Value.absent(),
              }) => FinalOrderLinesCompanion.insert(
                finalLineId: finalLineId,
                orderId: orderId,
                productRevisionId: productRevisionId,
                productId: productId,
                recognitionSkuId: recognitionSkuId,
                productName: productName,
                unitPriceKrw: unitPriceKrw,
                quantity: quantity,
                lineAmountKrw: lineAmountKrw,
                resolutionSource: resolutionSource,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$FinalOrderLinesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({orderId = false, productRevisionId = false}) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (orderId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.orderId,
                                    referencedTable:
                                        $$FinalOrderLinesTableReferences
                                            ._orderIdTable(db),
                                    referencedColumn:
                                        $$FinalOrderLinesTableReferences
                                            ._orderIdTable(db)
                                            .orderId,
                                  )
                                  as T;
                        }
                        if (productRevisionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.productRevisionId,
                                    referencedTable:
                                        $$FinalOrderLinesTableReferences
                                            ._productRevisionIdTable(db),
                                    referencedColumn:
                                        $$FinalOrderLinesTableReferences
                                            ._productRevisionIdTable(db)
                                            .productRevisionId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$FinalOrderLinesTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $FinalOrderLinesTable,
      FinalOrderLineRow,
      $$FinalOrderLinesTableFilterComposer,
      $$FinalOrderLinesTableOrderingComposer,
      $$FinalOrderLinesTableAnnotationComposer,
      $$FinalOrderLinesTableCreateCompanionBuilder,
      $$FinalOrderLinesTableUpdateCompanionBuilder,
      (FinalOrderLineRow, $$FinalOrderLinesTableReferences),
      FinalOrderLineRow,
      PrefetchHooks Function({bool orderId, bool productRevisionId})
    >;
typedef $$SimulatedPaymentsTableCreateCompanionBuilder =
    SimulatedPaymentsCompanion Function({
      required String paymentId,
      required String orderId,
      required String sessionId,
      required int amountKrw,
      required String currency,
      required String provider,
      required String status,
      required String finalOrderSha256,
      required int paidAtUs,
      Value<int> rowid,
    });
typedef $$SimulatedPaymentsTableUpdateCompanionBuilder =
    SimulatedPaymentsCompanion Function({
      Value<String> paymentId,
      Value<String> orderId,
      Value<String> sessionId,
      Value<int> amountKrw,
      Value<String> currency,
      Value<String> provider,
      Value<String> status,
      Value<String> finalOrderSha256,
      Value<int> paidAtUs,
      Value<int> rowid,
    });

final class $$SimulatedPaymentsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $SimulatedPaymentsTable,
          SimulatedPaymentRow
        > {
  $$SimulatedPaymentsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $FinalOrdersTable _orderIdTable(_$BakeryDatabase db) => db.finalOrders
      .createAlias('simulated_payments__order_id__final_orders__order_id');

  $$FinalOrdersTableProcessedTableManager get orderId {
    final $_column = $_itemColumn<String>('order_id')!;

    final manager = $$FinalOrdersTableTableManager(
      $_db,
      $_db.finalOrders,
    ).filter((f) => f.orderId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_orderIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) =>
      db.checkoutSessions.createAlias(
        'simulated_payments__session_id__checkout_sessions__session_id',
      );

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$SimulatedPaymentsTableFilterComposer
    extends Composer<_$BakeryDatabase, $SimulatedPaymentsTable> {
  $$SimulatedPaymentsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get paymentId => $composableBuilder(
    column: $table.paymentId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get amountKrw => $composableBuilder(
    column: $table.amountKrw,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get currency => $composableBuilder(
    column: $table.currency,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get provider => $composableBuilder(
    column: $table.provider,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get finalOrderSha256 => $composableBuilder(
    column: $table.finalOrderSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get paidAtUs => $composableBuilder(
    column: $table.paidAtUs,
    builder: (column) => ColumnFilters(column),
  );

  $$FinalOrdersTableFilterComposer get orderId {
    final $$FinalOrdersTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableFilterComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$SimulatedPaymentsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $SimulatedPaymentsTable> {
  $$SimulatedPaymentsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get paymentId => $composableBuilder(
    column: $table.paymentId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get amountKrw => $composableBuilder(
    column: $table.amountKrw,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get currency => $composableBuilder(
    column: $table.currency,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get provider => $composableBuilder(
    column: $table.provider,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get finalOrderSha256 => $composableBuilder(
    column: $table.finalOrderSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get paidAtUs => $composableBuilder(
    column: $table.paidAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  $$FinalOrdersTableOrderingComposer get orderId {
    final $$FinalOrdersTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableOrderingComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$SimulatedPaymentsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $SimulatedPaymentsTable> {
  $$SimulatedPaymentsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get paymentId =>
      $composableBuilder(column: $table.paymentId, builder: (column) => column);

  GeneratedColumn<int> get amountKrw =>
      $composableBuilder(column: $table.amountKrw, builder: (column) => column);

  GeneratedColumn<String> get currency =>
      $composableBuilder(column: $table.currency, builder: (column) => column);

  GeneratedColumn<String> get provider =>
      $composableBuilder(column: $table.provider, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<String> get finalOrderSha256 => $composableBuilder(
    column: $table.finalOrderSha256,
    builder: (column) => column,
  );

  GeneratedColumn<int> get paidAtUs =>
      $composableBuilder(column: $table.paidAtUs, builder: (column) => column);

  $$FinalOrdersTableAnnotationComposer get orderId {
    final $$FinalOrdersTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.orderId,
      referencedTable: $db.finalOrders,
      getReferencedColumn: (t) => t.orderId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$FinalOrdersTableAnnotationComposer(
            $db: $db,
            $table: $db.finalOrders,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$SimulatedPaymentsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $SimulatedPaymentsTable,
          SimulatedPaymentRow,
          $$SimulatedPaymentsTableFilterComposer,
          $$SimulatedPaymentsTableOrderingComposer,
          $$SimulatedPaymentsTableAnnotationComposer,
          $$SimulatedPaymentsTableCreateCompanionBuilder,
          $$SimulatedPaymentsTableUpdateCompanionBuilder,
          (SimulatedPaymentRow, $$SimulatedPaymentsTableReferences),
          SimulatedPaymentRow,
          PrefetchHooks Function({bool orderId, bool sessionId})
        > {
  $$SimulatedPaymentsTableTableManager(
    _$BakeryDatabase db,
    $SimulatedPaymentsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SimulatedPaymentsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SimulatedPaymentsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SimulatedPaymentsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> paymentId = const Value.absent(),
                Value<String> orderId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<int> amountKrw = const Value.absent(),
                Value<String> currency = const Value.absent(),
                Value<String> provider = const Value.absent(),
                Value<String> status = const Value.absent(),
                Value<String> finalOrderSha256 = const Value.absent(),
                Value<int> paidAtUs = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => SimulatedPaymentsCompanion(
                paymentId: paymentId,
                orderId: orderId,
                sessionId: sessionId,
                amountKrw: amountKrw,
                currency: currency,
                provider: provider,
                status: status,
                finalOrderSha256: finalOrderSha256,
                paidAtUs: paidAtUs,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String paymentId,
                required String orderId,
                required String sessionId,
                required int amountKrw,
                required String currency,
                required String provider,
                required String status,
                required String finalOrderSha256,
                required int paidAtUs,
                Value<int> rowid = const Value.absent(),
              }) => SimulatedPaymentsCompanion.insert(
                paymentId: paymentId,
                orderId: orderId,
                sessionId: sessionId,
                amountKrw: amountKrw,
                currency: currency,
                provider: provider,
                status: status,
                finalOrderSha256: finalOrderSha256,
                paidAtUs: paidAtUs,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$SimulatedPaymentsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({orderId = false, sessionId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (orderId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.orderId,
                                referencedTable:
                                    $$SimulatedPaymentsTableReferences
                                        ._orderIdTable(db),
                                referencedColumn:
                                    $$SimulatedPaymentsTableReferences
                                        ._orderIdTable(db)
                                        .orderId,
                              )
                              as T;
                    }
                    if (sessionId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.sessionId,
                                referencedTable:
                                    $$SimulatedPaymentsTableReferences
                                        ._sessionIdTable(db),
                                referencedColumn:
                                    $$SimulatedPaymentsTableReferences
                                        ._sessionIdTable(db)
                                        .sessionId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$SimulatedPaymentsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $SimulatedPaymentsTable,
      SimulatedPaymentRow,
      $$SimulatedPaymentsTableFilterComposer,
      $$SimulatedPaymentsTableOrderingComposer,
      $$SimulatedPaymentsTableAnnotationComposer,
      $$SimulatedPaymentsTableCreateCompanionBuilder,
      $$SimulatedPaymentsTableUpdateCompanionBuilder,
      (SimulatedPaymentRow, $$SimulatedPaymentsTableReferences),
      SimulatedPaymentRow,
      PrefetchHooks Function({bool orderId, bool sessionId})
    >;
typedef $$AuditEventsTableCreateCompanionBuilder =
    AuditEventsCompanion Function({
      required String eventId,
      Value<String?> sessionId,
      required String eventType,
      required int occurredAtUs,
      Value<String?> detail,
      Value<int> rowid,
    });
typedef $$AuditEventsTableUpdateCompanionBuilder =
    AuditEventsCompanion Function({
      Value<String> eventId,
      Value<String?> sessionId,
      Value<String> eventType,
      Value<int> occurredAtUs,
      Value<String?> detail,
      Value<int> rowid,
    });

final class $$AuditEventsTableReferences
    extends BaseReferences<_$BakeryDatabase, $AuditEventsTable, AuditEventRow> {
  $$AuditEventsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) => db
      .checkoutSessions
      .createAlias('audit_events__session_id__checkout_sessions__session_id');

  $$CheckoutSessionsTableProcessedTableManager? get sessionId {
    final $_column = $_itemColumn<String>('session_id');
    if ($_column == null) return null;
    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$AuditEventsTableFilterComposer
    extends Composer<_$BakeryDatabase, $AuditEventsTable> {
  $$AuditEventsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get eventId => $composableBuilder(
    column: $table.eventId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get eventType => $composableBuilder(
    column: $table.eventType,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get occurredAtUs => $composableBuilder(
    column: $table.occurredAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get detail => $composableBuilder(
    column: $table.detail,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AuditEventsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $AuditEventsTable> {
  $$AuditEventsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get eventId => $composableBuilder(
    column: $table.eventId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get eventType => $composableBuilder(
    column: $table.eventType,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get occurredAtUs => $composableBuilder(
    column: $table.occurredAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get detail => $composableBuilder(
    column: $table.detail,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AuditEventsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $AuditEventsTable> {
  $$AuditEventsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get eventId =>
      $composableBuilder(column: $table.eventId, builder: (column) => column);

  GeneratedColumn<String> get eventType =>
      $composableBuilder(column: $table.eventType, builder: (column) => column);

  GeneratedColumn<int> get occurredAtUs => $composableBuilder(
    column: $table.occurredAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get detail =>
      $composableBuilder(column: $table.detail, builder: (column) => column);

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AuditEventsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $AuditEventsTable,
          AuditEventRow,
          $$AuditEventsTableFilterComposer,
          $$AuditEventsTableOrderingComposer,
          $$AuditEventsTableAnnotationComposer,
          $$AuditEventsTableCreateCompanionBuilder,
          $$AuditEventsTableUpdateCompanionBuilder,
          (AuditEventRow, $$AuditEventsTableReferences),
          AuditEventRow,
          PrefetchHooks Function({bool sessionId})
        > {
  $$AuditEventsTableTableManager(_$BakeryDatabase db, $AuditEventsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$AuditEventsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$AuditEventsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$AuditEventsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> eventId = const Value.absent(),
                Value<String?> sessionId = const Value.absent(),
                Value<String> eventType = const Value.absent(),
                Value<int> occurredAtUs = const Value.absent(),
                Value<String?> detail = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AuditEventsCompanion(
                eventId: eventId,
                sessionId: sessionId,
                eventType: eventType,
                occurredAtUs: occurredAtUs,
                detail: detail,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String eventId,
                Value<String?> sessionId = const Value.absent(),
                required String eventType,
                required int occurredAtUs,
                Value<String?> detail = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AuditEventsCompanion.insert(
                eventId: eventId,
                sessionId: sessionId,
                eventType: eventType,
                occurredAtUs: occurredAtUs,
                detail: detail,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$AuditEventsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({sessionId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (sessionId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.sessionId,
                                referencedTable: $$AuditEventsTableReferences
                                    ._sessionIdTable(db),
                                referencedColumn: $$AuditEventsTableReferences
                                    ._sessionIdTable(db)
                                    .sessionId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$AuditEventsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $AuditEventsTable,
      AuditEventRow,
      $$AuditEventsTableFilterComposer,
      $$AuditEventsTableOrderingComposer,
      $$AuditEventsTableAnnotationComposer,
      $$AuditEventsTableCreateCompanionBuilder,
      $$AuditEventsTableUpdateCompanionBuilder,
      (AuditEventRow, $$AuditEventsTableReferences),
      AuditEventRow,
      PrefetchHooks Function({bool sessionId})
    >;
typedef $$AppSettingsTableCreateCompanionBuilder =
    AppSettingsCompanion Function({
      required String settingsId,
      required String activeSettingsRevisionId,
      required String applicationVersionValue,
      required String lastMigrationResult,
      Value<int> rowid,
    });
typedef $$AppSettingsTableUpdateCompanionBuilder =
    AppSettingsCompanion Function({
      Value<String> settingsId,
      Value<String> activeSettingsRevisionId,
      Value<String> applicationVersionValue,
      Value<String> lastMigrationResult,
      Value<int> rowid,
    });

final class $$AppSettingsTableReferences
    extends
        BaseReferences<_$BakeryDatabase, $AppSettingsTable, AppSettingsRow> {
  $$AppSettingsTableReferences(super.$_db, super.$_table, super.$_typedResult);

  static $SettingsRevisionsTable _activeSettingsRevisionIdTable(
    _$BakeryDatabase db,
  ) => db.settingsRevisions.createAlias(
    'app_settings__active_settings_revision_id__settings_revisions__revision_id',
  );

  $$SettingsRevisionsTableProcessedTableManager get activeSettingsRevisionId {
    final $_column = $_itemColumn<String>('active_settings_revision_id')!;

    final manager = $$SettingsRevisionsTableTableManager(
      $_db,
      $_db.settingsRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(
      _activeSettingsRevisionIdTable($_db),
    );
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$AppSettingsTableFilterComposer
    extends Composer<_$BakeryDatabase, $AppSettingsTable> {
  $$AppSettingsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get settingsId => $composableBuilder(
    column: $table.settingsId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get applicationVersionValue => $composableBuilder(
    column: $table.applicationVersionValue,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get lastMigrationResult => $composableBuilder(
    column: $table.lastMigrationResult,
    builder: (column) => ColumnFilters(column),
  );

  $$SettingsRevisionsTableFilterComposer get activeSettingsRevisionId {
    final $$SettingsRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.activeSettingsRevisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AppSettingsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $AppSettingsTable> {
  $$AppSettingsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get settingsId => $composableBuilder(
    column: $table.settingsId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get applicationVersionValue => $composableBuilder(
    column: $table.applicationVersionValue,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get lastMigrationResult => $composableBuilder(
    column: $table.lastMigrationResult,
    builder: (column) => ColumnOrderings(column),
  );

  $$SettingsRevisionsTableOrderingComposer get activeSettingsRevisionId {
    final $$SettingsRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.activeSettingsRevisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AppSettingsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $AppSettingsTable> {
  $$AppSettingsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get settingsId => $composableBuilder(
    column: $table.settingsId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get applicationVersionValue => $composableBuilder(
    column: $table.applicationVersionValue,
    builder: (column) => column,
  );

  GeneratedColumn<String> get lastMigrationResult => $composableBuilder(
    column: $table.lastMigrationResult,
    builder: (column) => column,
  );

  $$SettingsRevisionsTableAnnotationComposer get activeSettingsRevisionId {
    final $$SettingsRevisionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.activeSettingsRevisionId,
          referencedTable: $db.settingsRevisions,
          getReferencedColumn: (t) => t.revisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SettingsRevisionsTableAnnotationComposer(
                $db: $db,
                $table: $db.settingsRevisions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return composer;
  }
}

class $$AppSettingsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $AppSettingsTable,
          AppSettingsRow,
          $$AppSettingsTableFilterComposer,
          $$AppSettingsTableOrderingComposer,
          $$AppSettingsTableAnnotationComposer,
          $$AppSettingsTableCreateCompanionBuilder,
          $$AppSettingsTableUpdateCompanionBuilder,
          (AppSettingsRow, $$AppSettingsTableReferences),
          AppSettingsRow,
          PrefetchHooks Function({bool activeSettingsRevisionId})
        > {
  $$AppSettingsTableTableManager(_$BakeryDatabase db, $AppSettingsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$AppSettingsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$AppSettingsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$AppSettingsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> settingsId = const Value.absent(),
                Value<String> activeSettingsRevisionId = const Value.absent(),
                Value<String> applicationVersionValue = const Value.absent(),
                Value<String> lastMigrationResult = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AppSettingsCompanion(
                settingsId: settingsId,
                activeSettingsRevisionId: activeSettingsRevisionId,
                applicationVersionValue: applicationVersionValue,
                lastMigrationResult: lastMigrationResult,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String settingsId,
                required String activeSettingsRevisionId,
                required String applicationVersionValue,
                required String lastMigrationResult,
                Value<int> rowid = const Value.absent(),
              }) => AppSettingsCompanion.insert(
                settingsId: settingsId,
                activeSettingsRevisionId: activeSettingsRevisionId,
                applicationVersionValue: applicationVersionValue,
                lastMigrationResult: lastMigrationResult,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$AppSettingsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({activeSettingsRevisionId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (activeSettingsRevisionId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.activeSettingsRevisionId,
                                referencedTable: $$AppSettingsTableReferences
                                    ._activeSettingsRevisionIdTable(db),
                                referencedColumn: $$AppSettingsTableReferences
                                    ._activeSettingsRevisionIdTable(db)
                                    .revisionId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$AppSettingsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $AppSettingsTable,
      AppSettingsRow,
      $$AppSettingsTableFilterComposer,
      $$AppSettingsTableOrderingComposer,
      $$AppSettingsTableAnnotationComposer,
      $$AppSettingsTableCreateCompanionBuilder,
      $$AppSettingsTableUpdateCompanionBuilder,
      (AppSettingsRow, $$AppSettingsTableReferences),
      AppSettingsRow,
      PrefetchHooks Function({bool activeSettingsRevisionId})
    >;
typedef $$RetentionEventsTableCreateCompanionBuilder =
    RetentionEventsCompanion Function({
      required String retentionEventId,
      required String attemptId,
      required String relativePath,
      required int originalByteSize,
      required String originalSha256,
      required int prunedAtUs,
      required String reason,
      Value<int> rowid,
    });
typedef $$RetentionEventsTableUpdateCompanionBuilder =
    RetentionEventsCompanion Function({
      Value<String> retentionEventId,
      Value<String> attemptId,
      Value<String> relativePath,
      Value<int> originalByteSize,
      Value<String> originalSha256,
      Value<int> prunedAtUs,
      Value<String> reason,
      Value<int> rowid,
    });

final class $$RetentionEventsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $RetentionEventsTable,
          RetentionEventRow
        > {
  $$RetentionEventsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $ScanAttemptsTable _attemptIdTable(_$BakeryDatabase db) => db
      .scanAttempts
      .createAlias('retention_events__attempt_id__scan_attempts__attempt_id');

  $$ScanAttemptsTableProcessedTableManager get attemptId {
    final $_column = $_itemColumn<String>('attempt_id')!;

    final manager = $$ScanAttemptsTableTableManager(
      $_db,
      $_db.scanAttempts,
    ).filter((f) => f.attemptId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_attemptIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$RetentionEventsTableFilterComposer
    extends Composer<_$BakeryDatabase, $RetentionEventsTable> {
  $$RetentionEventsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get retentionEventId => $composableBuilder(
    column: $table.retentionEventId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get relativePath => $composableBuilder(
    column: $table.relativePath,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get originalByteSize => $composableBuilder(
    column: $table.originalByteSize,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get originalSha256 => $composableBuilder(
    column: $table.originalSha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get prunedAtUs => $composableBuilder(
    column: $table.prunedAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get reason => $composableBuilder(
    column: $table.reason,
    builder: (column) => ColumnFilters(column),
  );

  $$ScanAttemptsTableFilterComposer get attemptId {
    final $$ScanAttemptsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableFilterComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RetentionEventsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $RetentionEventsTable> {
  $$RetentionEventsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get retentionEventId => $composableBuilder(
    column: $table.retentionEventId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get relativePath => $composableBuilder(
    column: $table.relativePath,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get originalByteSize => $composableBuilder(
    column: $table.originalByteSize,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get originalSha256 => $composableBuilder(
    column: $table.originalSha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get prunedAtUs => $composableBuilder(
    column: $table.prunedAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get reason => $composableBuilder(
    column: $table.reason,
    builder: (column) => ColumnOrderings(column),
  );

  $$ScanAttemptsTableOrderingComposer get attemptId {
    final $$ScanAttemptsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableOrderingComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RetentionEventsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $RetentionEventsTable> {
  $$RetentionEventsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get retentionEventId => $composableBuilder(
    column: $table.retentionEventId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get relativePath => $composableBuilder(
    column: $table.relativePath,
    builder: (column) => column,
  );

  GeneratedColumn<int> get originalByteSize => $composableBuilder(
    column: $table.originalByteSize,
    builder: (column) => column,
  );

  GeneratedColumn<String> get originalSha256 => $composableBuilder(
    column: $table.originalSha256,
    builder: (column) => column,
  );

  GeneratedColumn<int> get prunedAtUs => $composableBuilder(
    column: $table.prunedAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get reason =>
      $composableBuilder(column: $table.reason, builder: (column) => column);

  $$ScanAttemptsTableAnnotationComposer get attemptId {
    final $$ScanAttemptsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableAnnotationComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$RetentionEventsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $RetentionEventsTable,
          RetentionEventRow,
          $$RetentionEventsTableFilterComposer,
          $$RetentionEventsTableOrderingComposer,
          $$RetentionEventsTableAnnotationComposer,
          $$RetentionEventsTableCreateCompanionBuilder,
          $$RetentionEventsTableUpdateCompanionBuilder,
          (RetentionEventRow, $$RetentionEventsTableReferences),
          RetentionEventRow,
          PrefetchHooks Function({bool attemptId})
        > {
  $$RetentionEventsTableTableManager(
    _$BakeryDatabase db,
    $RetentionEventsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$RetentionEventsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$RetentionEventsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$RetentionEventsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> retentionEventId = const Value.absent(),
                Value<String> attemptId = const Value.absent(),
                Value<String> relativePath = const Value.absent(),
                Value<int> originalByteSize = const Value.absent(),
                Value<String> originalSha256 = const Value.absent(),
                Value<int> prunedAtUs = const Value.absent(),
                Value<String> reason = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => RetentionEventsCompanion(
                retentionEventId: retentionEventId,
                attemptId: attemptId,
                relativePath: relativePath,
                originalByteSize: originalByteSize,
                originalSha256: originalSha256,
                prunedAtUs: prunedAtUs,
                reason: reason,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String retentionEventId,
                required String attemptId,
                required String relativePath,
                required int originalByteSize,
                required String originalSha256,
                required int prunedAtUs,
                required String reason,
                Value<int> rowid = const Value.absent(),
              }) => RetentionEventsCompanion.insert(
                retentionEventId: retentionEventId,
                attemptId: attemptId,
                relativePath: relativePath,
                originalByteSize: originalByteSize,
                originalSha256: originalSha256,
                prunedAtUs: prunedAtUs,
                reason: reason,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$RetentionEventsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({attemptId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (attemptId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.attemptId,
                                referencedTable:
                                    $$RetentionEventsTableReferences
                                        ._attemptIdTable(db),
                                referencedColumn:
                                    $$RetentionEventsTableReferences
                                        ._attemptIdTable(db)
                                        .attemptId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$RetentionEventsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $RetentionEventsTable,
      RetentionEventRow,
      $$RetentionEventsTableFilterComposer,
      $$RetentionEventsTableOrderingComposer,
      $$RetentionEventsTableAnnotationComposer,
      $$RetentionEventsTableCreateCompanionBuilder,
      $$RetentionEventsTableUpdateCompanionBuilder,
      (RetentionEventRow, $$RetentionEventsTableReferences),
      RetentionEventRow,
      PrefetchHooks Function({bool attemptId})
    >;
typedef $$AdminReviewAnnotationsTableCreateCompanionBuilder =
    AdminReviewAnnotationsCompanion Function({
      required String annotationId,
      required String sessionId,
      Value<String?> attemptId,
      Value<String?> objectId,
      required String reviewStatus,
      Value<String?> correctProductId,
      Value<String> conclusionCode,
      required String reasonCode,
      Value<String?> note,
      required String authorLabel,
      required int createdAtUs,
      Value<int> rowid,
    });
typedef $$AdminReviewAnnotationsTableUpdateCompanionBuilder =
    AdminReviewAnnotationsCompanion Function({
      Value<String> annotationId,
      Value<String> sessionId,
      Value<String?> attemptId,
      Value<String?> objectId,
      Value<String> reviewStatus,
      Value<String?> correctProductId,
      Value<String> conclusionCode,
      Value<String> reasonCode,
      Value<String?> note,
      Value<String> authorLabel,
      Value<int> createdAtUs,
      Value<int> rowid,
    });

final class $$AdminReviewAnnotationsTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $AdminReviewAnnotationsTable,
          AdminReviewAnnotationRow
        > {
  $$AdminReviewAnnotationsTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $CheckoutSessionsTable _sessionIdTable(_$BakeryDatabase db) =>
      db.checkoutSessions.createAlias(
        'admin_review_annotations__session_id__checkout_sessions__session_id',
      );

  $$CheckoutSessionsTableProcessedTableManager get sessionId {
    final $_column = $_itemColumn<String>('session_id')!;

    final manager = $$CheckoutSessionsTableTableManager(
      $_db,
      $_db.checkoutSessions,
    ).filter((f) => f.sessionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_sessionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $ScanAttemptsTable _attemptIdTable(_$BakeryDatabase db) =>
      db.scanAttempts.createAlias(
        'admin_review_annotations__attempt_id__scan_attempts__attempt_id',
      );

  $$ScanAttemptsTableProcessedTableManager? get attemptId {
    final $_column = $_itemColumn<String>('attempt_id');
    if ($_column == null) return null;
    final manager = $$ScanAttemptsTableTableManager(
      $_db,
      $_db.scanAttempts,
    ).filter((f) => f.attemptId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_attemptIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }

  static $InferenceObjectsTable _objectIdTable(
    _$BakeryDatabase db,
  ) => db.inferenceObjects.createAlias(
    'admin_review_annotations__object_id__inference_objects__inference_object_id',
  );

  $$InferenceObjectsTableProcessedTableManager? get objectId {
    final $_column = $_itemColumn<String>('object_id');
    if ($_column == null) return null;
    final manager = $$InferenceObjectsTableTableManager(
      $_db,
      $_db.inferenceObjects,
    ).filter((f) => f.inferenceObjectId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_objectIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$AdminReviewAnnotationsTableFilterComposer
    extends Composer<_$BakeryDatabase, $AdminReviewAnnotationsTable> {
  $$AdminReviewAnnotationsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get annotationId => $composableBuilder(
    column: $table.annotationId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get reviewStatus => $composableBuilder(
    column: $table.reviewStatus,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get correctProductId => $composableBuilder(
    column: $table.correctProductId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get conclusionCode => $composableBuilder(
    column: $table.conclusionCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get reasonCode => $composableBuilder(
    column: $table.reasonCode,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get note => $composableBuilder(
    column: $table.note,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnFilters(column),
  );

  $$CheckoutSessionsTableFilterComposer get sessionId {
    final $$CheckoutSessionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableFilterComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ScanAttemptsTableFilterComposer get attemptId {
    final $$ScanAttemptsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableFilterComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableFilterComposer get objectId {
    final $$InferenceObjectsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.objectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableFilterComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AdminReviewAnnotationsTableOrderingComposer
    extends Composer<_$BakeryDatabase, $AdminReviewAnnotationsTable> {
  $$AdminReviewAnnotationsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get annotationId => $composableBuilder(
    column: $table.annotationId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get reviewStatus => $composableBuilder(
    column: $table.reviewStatus,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get correctProductId => $composableBuilder(
    column: $table.correctProductId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get conclusionCode => $composableBuilder(
    column: $table.conclusionCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get reasonCode => $composableBuilder(
    column: $table.reasonCode,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get note => $composableBuilder(
    column: $table.note,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  $$CheckoutSessionsTableOrderingComposer get sessionId {
    final $$CheckoutSessionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableOrderingComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ScanAttemptsTableOrderingComposer get attemptId {
    final $$ScanAttemptsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableOrderingComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableOrderingComposer get objectId {
    final $$InferenceObjectsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.objectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableOrderingComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AdminReviewAnnotationsTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $AdminReviewAnnotationsTable> {
  $$AdminReviewAnnotationsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get annotationId => $composableBuilder(
    column: $table.annotationId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get reviewStatus => $composableBuilder(
    column: $table.reviewStatus,
    builder: (column) => column,
  );

  GeneratedColumn<String> get correctProductId => $composableBuilder(
    column: $table.correctProductId,
    builder: (column) => column,
  );

  GeneratedColumn<String> get conclusionCode => $composableBuilder(
    column: $table.conclusionCode,
    builder: (column) => column,
  );

  GeneratedColumn<String> get reasonCode => $composableBuilder(
    column: $table.reasonCode,
    builder: (column) => column,
  );

  GeneratedColumn<String> get note =>
      $composableBuilder(column: $table.note, builder: (column) => column);

  GeneratedColumn<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => column,
  );

  GeneratedColumn<int> get createdAtUs => $composableBuilder(
    column: $table.createdAtUs,
    builder: (column) => column,
  );

  $$CheckoutSessionsTableAnnotationComposer get sessionId {
    final $$CheckoutSessionsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.sessionId,
      referencedTable: $db.checkoutSessions,
      getReferencedColumn: (t) => t.sessionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$CheckoutSessionsTableAnnotationComposer(
            $db: $db,
            $table: $db.checkoutSessions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$ScanAttemptsTableAnnotationComposer get attemptId {
    final $$ScanAttemptsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.attemptId,
      referencedTable: $db.scanAttempts,
      getReferencedColumn: (t) => t.attemptId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$ScanAttemptsTableAnnotationComposer(
            $db: $db,
            $table: $db.scanAttempts,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }

  $$InferenceObjectsTableAnnotationComposer get objectId {
    final $$InferenceObjectsTableAnnotationComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.objectId,
      referencedTable: $db.inferenceObjects,
      getReferencedColumn: (t) => t.inferenceObjectId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$InferenceObjectsTableAnnotationComposer(
            $db: $db,
            $table: $db.inferenceObjects,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$AdminReviewAnnotationsTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $AdminReviewAnnotationsTable,
          AdminReviewAnnotationRow,
          $$AdminReviewAnnotationsTableFilterComposer,
          $$AdminReviewAnnotationsTableOrderingComposer,
          $$AdminReviewAnnotationsTableAnnotationComposer,
          $$AdminReviewAnnotationsTableCreateCompanionBuilder,
          $$AdminReviewAnnotationsTableUpdateCompanionBuilder,
          (AdminReviewAnnotationRow, $$AdminReviewAnnotationsTableReferences),
          AdminReviewAnnotationRow,
          PrefetchHooks Function({
            bool sessionId,
            bool attemptId,
            bool objectId,
          })
        > {
  $$AdminReviewAnnotationsTableTableManager(
    _$BakeryDatabase db,
    $AdminReviewAnnotationsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$AdminReviewAnnotationsTableFilterComposer(
                $db: db,
                $table: table,
              ),
          createOrderingComposer: () =>
              $$AdminReviewAnnotationsTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer: () =>
              $$AdminReviewAnnotationsTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> annotationId = const Value.absent(),
                Value<String> sessionId = const Value.absent(),
                Value<String?> attemptId = const Value.absent(),
                Value<String?> objectId = const Value.absent(),
                Value<String> reviewStatus = const Value.absent(),
                Value<String?> correctProductId = const Value.absent(),
                Value<String> conclusionCode = const Value.absent(),
                Value<String> reasonCode = const Value.absent(),
                Value<String?> note = const Value.absent(),
                Value<String> authorLabel = const Value.absent(),
                Value<int> createdAtUs = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => AdminReviewAnnotationsCompanion(
                annotationId: annotationId,
                sessionId: sessionId,
                attemptId: attemptId,
                objectId: objectId,
                reviewStatus: reviewStatus,
                correctProductId: correctProductId,
                conclusionCode: conclusionCode,
                reasonCode: reasonCode,
                note: note,
                authorLabel: authorLabel,
                createdAtUs: createdAtUs,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String annotationId,
                required String sessionId,
                Value<String?> attemptId = const Value.absent(),
                Value<String?> objectId = const Value.absent(),
                required String reviewStatus,
                Value<String?> correctProductId = const Value.absent(),
                Value<String> conclusionCode = const Value.absent(),
                required String reasonCode,
                Value<String?> note = const Value.absent(),
                required String authorLabel,
                required int createdAtUs,
                Value<int> rowid = const Value.absent(),
              }) => AdminReviewAnnotationsCompanion.insert(
                annotationId: annotationId,
                sessionId: sessionId,
                attemptId: attemptId,
                objectId: objectId,
                reviewStatus: reviewStatus,
                correctProductId: correctProductId,
                conclusionCode: conclusionCode,
                reasonCode: reasonCode,
                note: note,
                authorLabel: authorLabel,
                createdAtUs: createdAtUs,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$AdminReviewAnnotationsTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback:
              ({sessionId = false, attemptId = false, objectId = false}) {
                return PrefetchHooks(
                  db: db,
                  explicitlyWatchedTables: [],
                  addJoins:
                      <
                        T extends TableManagerState<
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic,
                          dynamic
                        >
                      >(state) {
                        if (sessionId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.sessionId,
                                    referencedTable:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._sessionIdTable(db),
                                    referencedColumn:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._sessionIdTable(db)
                                            .sessionId,
                                  )
                                  as T;
                        }
                        if (attemptId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.attemptId,
                                    referencedTable:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._attemptIdTable(db),
                                    referencedColumn:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._attemptIdTable(db)
                                            .attemptId,
                                  )
                                  as T;
                        }
                        if (objectId) {
                          state =
                              state.withJoin(
                                    currentTable: table,
                                    currentColumn: table.objectId,
                                    referencedTable:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._objectIdTable(db),
                                    referencedColumn:
                                        $$AdminReviewAnnotationsTableReferences
                                            ._objectIdTable(db)
                                            .inferenceObjectId,
                                  )
                                  as T;
                        }

                        return state;
                      },
                  getPrefetchedDataCallback: (items) async {
                    return [];
                  },
                );
              },
        ),
      );
}

typedef $$AdminReviewAnnotationsTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $AdminReviewAnnotationsTable,
      AdminReviewAnnotationRow,
      $$AdminReviewAnnotationsTableFilterComposer,
      $$AdminReviewAnnotationsTableOrderingComposer,
      $$AdminReviewAnnotationsTableAnnotationComposer,
      $$AdminReviewAnnotationsTableCreateCompanionBuilder,
      $$AdminReviewAnnotationsTableUpdateCompanionBuilder,
      (AdminReviewAnnotationRow, $$AdminReviewAnnotationsTableReferences),
      AdminReviewAnnotationRow,
      PrefetchHooks Function({bool sessionId, bool attemptId, bool objectId})
    >;
typedef $$SettingsRevisionEntriesTableCreateCompanionBuilder =
    SettingsRevisionEntriesCompanion Function({
      required String revisionId,
      required String settingKey,
      required String valueType,
      required String valueJson,
      required int updatedAtUs,
      required String authorLabel,
      Value<int> rowid,
    });
typedef $$SettingsRevisionEntriesTableUpdateCompanionBuilder =
    SettingsRevisionEntriesCompanion Function({
      Value<String> revisionId,
      Value<String> settingKey,
      Value<String> valueType,
      Value<String> valueJson,
      Value<int> updatedAtUs,
      Value<String> authorLabel,
      Value<int> rowid,
    });

final class $$SettingsRevisionEntriesTableReferences
    extends
        BaseReferences<
          _$BakeryDatabase,
          $SettingsRevisionEntriesTable,
          SettingsRevisionEntryRow
        > {
  $$SettingsRevisionEntriesTableReferences(
    super.$_db,
    super.$_table,
    super.$_typedResult,
  );

  static $SettingsRevisionsTable _revisionIdTable(
    _$BakeryDatabase db,
  ) => db.settingsRevisions.createAlias(
    'settings_revision_entries__revision_id__settings_revisions__revision_id',
  );

  $$SettingsRevisionsTableProcessedTableManager get revisionId {
    final $_column = $_itemColumn<String>('revision_id')!;

    final manager = $$SettingsRevisionsTableTableManager(
      $_db,
      $_db.settingsRevisions,
    ).filter((f) => f.revisionId.sqlEquals($_column));
    final item = $_typedResult.readTableOrNull(_revisionIdTable($_db));
    if (item == null) return manager;
    return ProcessedTableManager(
      manager.$state.copyWith(prefetchedData: [item]),
    );
  }
}

class $$SettingsRevisionEntriesTableFilterComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionEntriesTable> {
  $$SettingsRevisionEntriesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get settingKey => $composableBuilder(
    column: $table.settingKey,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get valueType => $composableBuilder(
    column: $table.valueType,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get valueJson => $composableBuilder(
    column: $table.valueJson,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get updatedAtUs => $composableBuilder(
    column: $table.updatedAtUs,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => ColumnFilters(column),
  );

  $$SettingsRevisionsTableFilterComposer get revisionId {
    final $$SettingsRevisionsTableFilterComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableFilterComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$SettingsRevisionEntriesTableOrderingComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionEntriesTable> {
  $$SettingsRevisionEntriesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get settingKey => $composableBuilder(
    column: $table.settingKey,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get valueType => $composableBuilder(
    column: $table.valueType,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get valueJson => $composableBuilder(
    column: $table.valueJson,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get updatedAtUs => $composableBuilder(
    column: $table.updatedAtUs,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => ColumnOrderings(column),
  );

  $$SettingsRevisionsTableOrderingComposer get revisionId {
    final $$SettingsRevisionsTableOrderingComposer composer = $composerBuilder(
      composer: this,
      getCurrentColumn: (t) => t.revisionId,
      referencedTable: $db.settingsRevisions,
      getReferencedColumn: (t) => t.revisionId,
      builder:
          (
            joinBuilder, {
            $addJoinBuilderToRootComposer,
            $removeJoinBuilderFromRootComposer,
          }) => $$SettingsRevisionsTableOrderingComposer(
            $db: $db,
            $table: $db.settingsRevisions,
            $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
            joinBuilder: joinBuilder,
            $removeJoinBuilderFromRootComposer:
                $removeJoinBuilderFromRootComposer,
          ),
    );
    return composer;
  }
}

class $$SettingsRevisionEntriesTableAnnotationComposer
    extends Composer<_$BakeryDatabase, $SettingsRevisionEntriesTable> {
  $$SettingsRevisionEntriesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get settingKey => $composableBuilder(
    column: $table.settingKey,
    builder: (column) => column,
  );

  GeneratedColumn<String> get valueType =>
      $composableBuilder(column: $table.valueType, builder: (column) => column);

  GeneratedColumn<String> get valueJson =>
      $composableBuilder(column: $table.valueJson, builder: (column) => column);

  GeneratedColumn<int> get updatedAtUs => $composableBuilder(
    column: $table.updatedAtUs,
    builder: (column) => column,
  );

  GeneratedColumn<String> get authorLabel => $composableBuilder(
    column: $table.authorLabel,
    builder: (column) => column,
  );

  $$SettingsRevisionsTableAnnotationComposer get revisionId {
    final $$SettingsRevisionsTableAnnotationComposer composer =
        $composerBuilder(
          composer: this,
          getCurrentColumn: (t) => t.revisionId,
          referencedTable: $db.settingsRevisions,
          getReferencedColumn: (t) => t.revisionId,
          builder:
              (
                joinBuilder, {
                $addJoinBuilderToRootComposer,
                $removeJoinBuilderFromRootComposer,
              }) => $$SettingsRevisionsTableAnnotationComposer(
                $db: $db,
                $table: $db.settingsRevisions,
                $addJoinBuilderToRootComposer: $addJoinBuilderToRootComposer,
                joinBuilder: joinBuilder,
                $removeJoinBuilderFromRootComposer:
                    $removeJoinBuilderFromRootComposer,
              ),
        );
    return composer;
  }
}

class $$SettingsRevisionEntriesTableTableManager
    extends
        RootTableManager<
          _$BakeryDatabase,
          $SettingsRevisionEntriesTable,
          SettingsRevisionEntryRow,
          $$SettingsRevisionEntriesTableFilterComposer,
          $$SettingsRevisionEntriesTableOrderingComposer,
          $$SettingsRevisionEntriesTableAnnotationComposer,
          $$SettingsRevisionEntriesTableCreateCompanionBuilder,
          $$SettingsRevisionEntriesTableUpdateCompanionBuilder,
          (SettingsRevisionEntryRow, $$SettingsRevisionEntriesTableReferences),
          SettingsRevisionEntryRow,
          PrefetchHooks Function({bool revisionId})
        > {
  $$SettingsRevisionEntriesTableTableManager(
    _$BakeryDatabase db,
    $SettingsRevisionEntriesTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SettingsRevisionEntriesTableFilterComposer(
                $db: db,
                $table: table,
              ),
          createOrderingComposer: () =>
              $$SettingsRevisionEntriesTableOrderingComposer(
                $db: db,
                $table: table,
              ),
          createComputedFieldComposer: () =>
              $$SettingsRevisionEntriesTableAnnotationComposer(
                $db: db,
                $table: table,
              ),
          updateCompanionCallback:
              ({
                Value<String> revisionId = const Value.absent(),
                Value<String> settingKey = const Value.absent(),
                Value<String> valueType = const Value.absent(),
                Value<String> valueJson = const Value.absent(),
                Value<int> updatedAtUs = const Value.absent(),
                Value<String> authorLabel = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => SettingsRevisionEntriesCompanion(
                revisionId: revisionId,
                settingKey: settingKey,
                valueType: valueType,
                valueJson: valueJson,
                updatedAtUs: updatedAtUs,
                authorLabel: authorLabel,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String revisionId,
                required String settingKey,
                required String valueType,
                required String valueJson,
                required int updatedAtUs,
                required String authorLabel,
                Value<int> rowid = const Value.absent(),
              }) => SettingsRevisionEntriesCompanion.insert(
                revisionId: revisionId,
                settingKey: settingKey,
                valueType: valueType,
                valueJson: valueJson,
                updatedAtUs: updatedAtUs,
                authorLabel: authorLabel,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable(table),
                  $$SettingsRevisionEntriesTableReferences(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: ({revisionId = false}) {
            return PrefetchHooks(
              db: db,
              explicitlyWatchedTables: [],
              addJoins:
                  <
                    T extends TableManagerState<
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic,
                      dynamic
                    >
                  >(state) {
                    if (revisionId) {
                      state =
                          state.withJoin(
                                currentTable: table,
                                currentColumn: table.revisionId,
                                referencedTable:
                                    $$SettingsRevisionEntriesTableReferences
                                        ._revisionIdTable(db),
                                referencedColumn:
                                    $$SettingsRevisionEntriesTableReferences
                                        ._revisionIdTable(db)
                                        .revisionId,
                              )
                              as T;
                    }

                    return state;
                  },
              getPrefetchedDataCallback: (items) async {
                return [];
              },
            );
          },
        ),
      );
}

typedef $$SettingsRevisionEntriesTableProcessedTableManager =
    ProcessedTableManager<
      _$BakeryDatabase,
      $SettingsRevisionEntriesTable,
      SettingsRevisionEntryRow,
      $$SettingsRevisionEntriesTableFilterComposer,
      $$SettingsRevisionEntriesTableOrderingComposer,
      $$SettingsRevisionEntriesTableAnnotationComposer,
      $$SettingsRevisionEntriesTableCreateCompanionBuilder,
      $$SettingsRevisionEntriesTableUpdateCompanionBuilder,
      (SettingsRevisionEntryRow, $$SettingsRevisionEntriesTableReferences),
      SettingsRevisionEntryRow,
      PrefetchHooks Function({bool revisionId})
    >;

class $BakeryDatabaseManager {
  final _$BakeryDatabase _db;
  $BakeryDatabaseManager(this._db);
  $$CatalogRevisionsTableTableManager get catalogRevisions =>
      $$CatalogRevisionsTableTableManager(_db, _db.catalogRevisions);
  $$ProductsTableTableManager get products =>
      $$ProductsTableTableManager(_db, _db.products);
  $$SettingsRevisionsTableTableManager get settingsRevisions =>
      $$SettingsRevisionsTableTableManager(_db, _db.settingsRevisions);
  $$CheckoutSessionsTableTableManager get checkoutSessions =>
      $$CheckoutSessionsTableTableManager(_db, _db.checkoutSessions);
  $$ScanAttemptsTableTableManager get scanAttempts =>
      $$ScanAttemptsTableTableManager(_db, _db.scanAttempts);
  $$InferenceObjectsTableTableManager get inferenceObjects =>
      $$InferenceObjectsTableTableManager(_db, _db.inferenceObjects);
  $$InferenceCandidatesTableTableManager get inferenceCandidates =>
      $$InferenceCandidatesTableTableManager(_db, _db.inferenceCandidates);
  $$ObjectResolutionsTableTableManager get objectResolutions =>
      $$ObjectResolutionsTableTableManager(_db, _db.objectResolutions);
  $$DraftOrderLinesTableTableManager get draftOrderLines =>
      $$DraftOrderLinesTableTableManager(_db, _db.draftOrderLines);
  $$FinalOrdersTableTableManager get finalOrders =>
      $$FinalOrdersTableTableManager(_db, _db.finalOrders);
  $$FinalOrderLinesTableTableManager get finalOrderLines =>
      $$FinalOrderLinesTableTableManager(_db, _db.finalOrderLines);
  $$SimulatedPaymentsTableTableManager get simulatedPayments =>
      $$SimulatedPaymentsTableTableManager(_db, _db.simulatedPayments);
  $$AuditEventsTableTableManager get auditEvents =>
      $$AuditEventsTableTableManager(_db, _db.auditEvents);
  $$AppSettingsTableTableManager get appSettings =>
      $$AppSettingsTableTableManager(_db, _db.appSettings);
  $$RetentionEventsTableTableManager get retentionEvents =>
      $$RetentionEventsTableTableManager(_db, _db.retentionEvents);
  $$AdminReviewAnnotationsTableTableManager get adminReviewAnnotations =>
      $$AdminReviewAnnotationsTableTableManager(
        _db,
        _db.adminReviewAnnotations,
      );
  $$SettingsRevisionEntriesTableTableManager get settingsRevisionEntries =>
      $$SettingsRevisionEntriesTableTableManager(
        _db,
        _db.settingsRevisionEntries,
      );
}
