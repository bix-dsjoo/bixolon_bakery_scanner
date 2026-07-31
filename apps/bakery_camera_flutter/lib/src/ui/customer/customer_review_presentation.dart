import 'package:flutter/material.dart';

import '../../checkout/checkout_models.dart';

enum CustomerReviewObjectState { confirmed, needsChoice, needsCatalog }

final class CustomerReviewObject {
  const CustomerReviewObject({
    required this.objectId,
    required this.displayNumber,
    required this.rect,
    required this.state,
    required this.label,
  });

  final String objectId;
  final int displayNumber;
  final Rect rect;
  final CustomerReviewObjectState state;
  final String label;

  String get numberLabel => displayNumber.toString().padLeft(2, '0');
  String get customerSemantics => '사진에서 $numberLabel번, $label';
}

final class CustomerReviewPresentation {
  CustomerReviewPresentation._(List<CustomerReviewObject> objects)
    : objects = List.unmodifiable(objects);

  factory CustomerReviewPresentation.fromDrafts(List<ObjectDraft> drafts) =>
      CustomerReviewPresentation._([
        for (var index = 0; index < drafts.length; index += 1)
          _item(drafts[index], index + 1),
      ]);

  final List<CustomerReviewObject> objects;
}

CustomerReviewObject _item(ObjectDraft draft, int displayNumber) {
  final inferenceObject = draft.inferenceObject;
  final product = draft.product;
  final state = product != null
      ? CustomerReviewObjectState.confirmed
      : draft.requiresCatalogSelection
      ? CustomerReviewObjectState.needsCatalog
      : CustomerReviewObjectState.needsChoice;
  final label = switch (state) {
    CustomerReviewObjectState.confirmed => product!.displayName,
    CustomerReviewObjectState.needsChoice => '확인이 필요해요',
    CustomerReviewObjectState.needsCatalog => '상품을 확인해 주세요',
  };

  return CustomerReviewObject(
    objectId: inferenceObject.objectId,
    displayNumber: displayNumber,
    rect: Rect.fromLTRB(
      inferenceObject.bboxXyxy[0],
      inferenceObject.bboxXyxy[1],
      inferenceObject.bboxXyxy[2],
      inferenceObject.bboxXyxy[3],
    ),
    state: state,
    label: label,
  );
}
