import 'dart:ui';

import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_presentation.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  final croissant = Product(
    productId: 'product-croissant',
    displayName: 'Croissant',
    unitPrice: 2800,
    recognitionSkuId: 6,
    categoryId: 'pastry',
    photoAssetPath: null,
    active: true,
    sortOrder: 1,
  );

  test('keeps inference order, canonical boxes, and customer-safe labels', () {
    final result = buildUiInferenceResult();
    final registered = result.objects.first;
    final unknown = result.objects.last;

    final presentation = CustomerReviewPresentation.fromDrafts([
      ObjectDraft.accepted(inferenceObject: registered, product: croissant),
      ObjectDraft.unresolved(unknown),
    ]);

    expect(presentation.objects.map((item) => item.displayNumber), [1, 2]);
    expect(presentation.objects[0].rect, const Rect.fromLTRB(10, 20, 500, 500));
    expect(presentation.objects[0].state, CustomerReviewObjectState.confirmed);
    expect(presentation.objects[0].label, 'Croissant');
    expect(
      presentation.objects[1].state,
      CustomerReviewObjectState.needsChoice,
    );
    expect(presentation.objects[1].label, '확인이 필요해요');
  });

  test('does not leak scores, decision paths, or model identifiers', () {
    final unknown = buildUiInferenceResult().objects.last;

    final item = CustomerReviewPresentation.fromDrafts([
      ObjectDraft.unresolved(unknown),
    ]).objects.single;

    expect(item.customerSemantics, isNot(contains('0.88')));
    expect(item.customerSemantics, isNot(contains('DINO')));
    expect(item.customerSemantics, contains('사진에서 01번, 확인이 필요해요'));
  });

  test('does not expose the inference-backed draft through its public API', () {
    final unknown = buildUiInferenceResult().objects.last;

    final item = CustomerReviewPresentation.fromDrafts([
      ObjectDraft.unresolved(unknown),
    ]).objects.single;

    expect(() => (item as dynamic).draft, throwsNoSuchMethodError);
  });

  test('marks a registered object without a product as needing catalog', () {
    final registered = buildUiInferenceResult().objects.first;

    final item = CustomerReviewPresentation.fromDrafts([
      ObjectDraft.unresolvedCatalog(registered),
    ]).objects.single;

    expect(item.state, CustomerReviewObjectState.needsCatalog);
    expect(item.label, '상품을 확인해 주세요');
  });
}
