import 'dart:io';

import 'package:flutter/material.dart';

import '../../admin/product_management_service.dart';
import '../../catalog/catalog_photo_store.dart';
import '../../catalog/product.dart';

/// Product edits are intentionally explicit: the customer-facing sale facts
/// are visible first, while model mapping and photo evidence are separately
/// labelled administrator controls.
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
  late final TextEditingController _photoSourcePath;
  late final TextEditingController _photoSourceReference;
  bool _active = true;
  bool _saving = false;
  bool _importingPhoto = false;
  bool _removePhoto = false;
  int? _recognitionSkuId;
  CatalogPhoto? _photo;
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
    _photoSourcePath = TextEditingController();
    _photoSourceReference = TextEditingController();
    _active = product?.active ?? true;
    _recognitionSkuId = product?.recognitionSkuId;
    if (product?.photoAssetPath != null &&
        product?.photoByteSize != null &&
        product?.photoSha256 != null &&
        product?.photoMediaType != null &&
        product?.photoProvenanceNote != null) {
      _photo = CatalogPhoto(
        relativePath: product!.photoAssetPath!,
        byteSize: product.photoByteSize!,
        sha256: product.photoSha256!,
        mediaType: product.photoMediaType!,
        provenanceNote: product.photoProvenanceNote!,
      );
      try {
        _photoSourceReference.text = CatalogPhotoProvenance.parse(
          _photo!.provenanceNote,
        ).sourceReference;
      } on FormatException {
        // The service remains the authority for a corrupted persisted photo.
      }
    }
  }

  @override
  void dispose() {
    _id.dispose();
    _name.dispose();
    _price.dispose();
    _category.dispose();
    _sortOrder.dispose();
    _photoSourcePath.dispose();
    _photoSourceReference.dispose();
    super.dispose();
  }

  bool get _busy => _saving || _importingPhoto;

  Future<void> _importPhoto() async {
    final sourcePath = _photoSourcePath.text.trim();
    final sourceReference = _photoSourceReference.text.trim();
    if (sourcePath.isEmpty || sourceReference.isEmpty) {
      setState(() => _error = '사진 파일 경로와 승인된 원본 기록 ID를 모두 입력해 주세요.');
      return;
    }
    setState(() {
      _importingPhoto = true;
      _error = null;
    });
    try {
      final photo = await widget.service.importPhoto(
        File(sourcePath),
        provenance: CatalogPhotoProvenance.approvedLocalImport(
          sourceReference: sourceReference,
        ),
      );
      if (!mounted) return;
      setState(() {
        _photo = photo;
        _removePhoto = false;
      });
    } on ArgumentError catch (error) {
      if (mounted) {
        setState(() => _error = error.message?.toString() ?? '사진 파일을 확인해 주세요.');
      }
    } on FormatException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on StateError catch (error) {
      if (mounted) setState(() => _error = '사진 무결성 오류: ${error.message}');
    } finally {
      if (mounted) setState(() => _importingPhoto = false);
    }
  }

  void _removeSelectedPhoto() {
    setState(() {
      _photo = null;
      _removePhoto = widget.product?.photoAssetPath != null;
      _photoSourcePath.clear();
      _photoSourceReference.clear();
      _error = null;
    });
  }

  Future<void> _save() async {
    final price = int.tryParse(_price.text.trim());
    final sortOrder = int.tryParse(_sortOrder.text.trim());
    if (price == null || price < 0 || sortOrder == null || sortOrder < 0) {
      setState(() => _error = '가격과 진열 순서는 0 이상의 숫자로 입력해 주세요.');
      return;
    }
    if (_id.text.trim().isEmpty ||
        _name.text.trim().isEmpty ||
        _category.text.trim().isEmpty) {
      setState(() => _error = '상품 ID, 이름, 카테고리를 모두 입력해 주세요.');
      return;
    }
    if (_photoSourcePath.text.trim().isNotEmpty && _photo == null) {
      setState(() => _error = '사진을 저장하기 전에 사진 가져오기를 완료해 주세요.');
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
                recognitionSkuId: _recognitionSkuId,
                active: _active,
                photo: _photo,
              )
            : ProductDraft.edit(
                productId: existing.productId,
                displayName: _name.text,
                unitPriceKrw: price,
                categoryId: _category.text,
                sortOrder: sortOrder,
                recognitionSkuId: _recognitionSkuId,
                active: _active,
                photo: _photo,
                removePhoto: _removePhoto,
              ),
      );
      if (mounted) Navigator.of(context).pop();
    } on ArgumentError catch (error) {
      if (mounted) {
        setState(() => _error = error.message?.toString() ?? '입력 값을 확인해 주세요.');
      }
    } on StateError catch (error) {
      if (mounted) setState(() => _error = '사진 무결성 오류: ${error.message}');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.product == null ? '상품 추가' : '상품 수정')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          TextField(
            key: const Key('product-id'),
            controller: _id,
            enabled: widget.product == null && !_busy,
            decoration: const InputDecoration(labelText: '상품 ID'),
          ),
          TextField(
            key: const Key('product-display-name'),
            controller: _name,
            enabled: !_busy,
            decoration: const InputDecoration(labelText: '고객에게 보이는 이름'),
          ),
          TextField(
            key: const Key('product-price'),
            controller: _price,
            enabled: !_busy,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '가격 (원)'),
          ),
          TextField(
            key: const Key('product-category'),
            controller: _category,
            enabled: !_busy,
            decoration: const InputDecoration(labelText: '카테고리'),
          ),
          TextField(
            key: const Key('product-sort-order'),
            controller: _sortOrder,
            enabled: !_busy,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '진열 순서'),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<int?>(
            key: const Key('product-recognition-sku'),
            initialValue: _recognitionSkuId,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'AI 모델 SKU 연결 (선택)',
              helperText: '비워 두면 고객이 상품 목록에서 직접 선택합니다.',
            ),
            items: [
              const DropdownMenuItem<int?>(
                value: null,
                child: Text('직접 선택 전용'),
              ),
              for (var sku = 1; sku <= 20; sku++)
                DropdownMenuItem<int?>(value: sku, child: Text('SKU $sku')),
            ],
            onChanged: _busy
                ? null
                : (value) => setState(() => _recognitionSkuId = value),
          ),
          const SizedBox(height: 20),
          Text('상품 사진', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          const Text(
            '승인된 현장 사진만 가져올 수 있습니다. AI 생성 이미지, 계산·추론 증거, 모델 학습 자료는 사용할 수 없습니다.',
          ),
          const SizedBox(height: 12),
          TextField(
            key: const Key('product-photo-source-path'),
            controller: _photoSourcePath,
            enabled: !_busy,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: '원본 사진 파일 경로',
              helperText: 'JPEG 또는 PNG, 최대 8MB',
            ),
          ),
          TextField(
            key: const Key('product-photo-source-reference'),
            controller: _photoSourceReference,
            enabled: !_busy,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: '승인된 원본 기록 ID',
              helperText: '파일명이 아닌 촬영·입수 기록 식별자를 입력하세요.',
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            key: const Key('product-import-photo'),
            onPressed: _busy ? null : _importPhoto,
            child: Text(_importingPhoto ? '사진 확인 중' : '사진 가져오기'),
          ),
          if (_photo != null) ...[
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              label: '검증된 상품 사진이 등록되었습니다',
              child: Row(
                children: [
                  const Icon(Icons.verified_outlined),
                  const SizedBox(width: 8),
                  const Expanded(child: Text('사진 등록됨')),
                  TextButton(
                    onPressed: _busy ? null : _removeSelectedPhoto,
                    child: const Text('사진 삭제'),
                  ),
                ],
              ),
            ),
          ],
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('판매 가능'),
            value: _active,
            onChanged: _busy
                ? null
                : (value) => setState(() => _active = value),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              label: '입력 또는 무결성 오류: $_error',
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton(
            key: const Key('product-save'),
            onPressed: _busy ? null : _save,
            child: Text(_saving ? '저장 중' : '변경 저장'),
          ),
        ],
      ),
    ),
  );
}
