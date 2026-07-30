import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import '../support/inference_fixtures.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('product identity is independent from recognition SKU identity', () {
    final product = Product(
      productId: 'product-cream-bun',
      displayName: 'Cream bun',
      unitPrice: 2800,
      recognitionSkuId: null,
      categoryId: 'filled-bread',
      photoAssetPath: null,
      active: true,
      sortOrder: 20,
    );

    expect(product.productId, 'product-cream-bun');
    expect(product.recognitionSkuId, isNull);
  });

  test('customer resolution source parses only the five audited values', () {
    expect(
      CustomerResolutionSource.values
          .map((value) => value.storageValue)
          .toSet(),
      {
        'ai_auto_customer_accepted',
        'customer_top3',
        'customer_catalog',
        'customer_overrode_auto',
        'customer_manual_cart',
      },
    );
    expect(
      () => CustomerResolutionSource.parse('model_autocorrected'),
      throwsFormatException,
    );
  });

  test('unresolved draft retains the inference candidate evidence exactly', () {
    final inferenceObject = buildUiInferenceResult().objects.last;
    final draft = ObjectDraft.unresolved(inferenceObject);

    expect(draft.acceptedProduct, isNull);
    expect(draft.candidates, hasLength(3));
    expect(draft.candidates.map((candidate) => candidate.rank), [1, 2, 3]);
    expect(draft.candidates.map((candidate) => candidate.skuId), [10, 11, 12]);
    expect(draft.candidates.map((candidate) => candidate.skuName), [
      'Sugar Donut',
      'Cream Donut',
      'Glazed Donut',
    ]);
    expect(draft.candidates.map((candidate) => candidate.score), [
      0.88,
      0.76,
      0.62,
    ]);
  });

  test(
    'registered object without an active product remains catalog selectable',
    () {
      final inferenceObject = buildUiInferenceResult().objects.first;
      final draft = ObjectDraft.unresolvedCatalog(inferenceObject);

      expect(draft.inferenceObject, same(inferenceObject));
      expect(draft.acceptedProduct, isNull);
      expect(draft.candidates, isEmpty);
      expect(draft.requiresCatalogSelection, isTrue);
      expect(draft.isResolved, isFalse);
    },
  );

  test(
    'checkout state can pay only for a reviewed resolved nonempty order',
    () {
      final product = Product(
        productId: 'product-croissant',
        displayName: 'Croissant',
        unitPrice: 2800,
        recognitionSkuId: 6,
        categoryId: 'pastry',
        photoAssetPath: null,
        active: true,
        sortOrder: 1,
      );
      final line = CheckoutLine(product: product, quantity: 1);
      final unresolved = ObjectDraft.unresolved(
        buildUiInferenceResult().objects.last,
      );

      expect(
        CheckoutState(
          phase: CheckoutPhase.orderReview,
          objectDrafts: [unresolved],
          lines: [line],
        ).canPay,
        isFalse,
      );
      expect(
        CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [],
          lines: [line],
        ).canPay,
        isFalse,
      );
      expect(
        CheckoutState(
          phase: CheckoutPhase.orderReview,
          objectDrafts: [],
          lines: [line],
        ).canPay,
        isTrue,
      );
    },
  );

  test('domain contracts reject invalid money and quantities at runtime', () {
    expect(
      () => Product(
        productId: 'product-invalid',
        displayName: 'Invalid',
        unitPrice: -1,
        recognitionSkuId: null,
        categoryId: 'test',
        photoAssetPath: null,
        active: true,
        sortOrder: 0,
      ),
      throwsA(isA<ArgumentError>()),
    );
    for (final quantity in [0, -1]) {
      expect(
        () => CheckoutLine(
          product: Product(
            productId: 'product-croissant',
            displayName: 'Croissant',
            unitPrice: 2800,
            recognitionSkuId: 6,
            categoryId: 'pastry',
            photoAssetPath: null,
            active: true,
            sortOrder: 1,
          ),
          quantity: quantity,
        ),
        throwsA(isA<ArgumentError>()),
      );
    }
    expect(
      () => PaymentReceipt(
        paymentId: 'payment-invalid',
        sessionId: 'session-1',
        amount: -1,
        paidAt: DateTime.utc(2026, 7, 30),
      ),
      throwsA(isA<ArgumentError>()),
    );
  });
}
