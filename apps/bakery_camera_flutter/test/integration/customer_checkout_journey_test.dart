import 'package:flutter_test/flutter_test.dart';

import '../support/customer_checkout_journey_fixture.dart';

void main() {
  test(
    'customer checkout retains immutable inference separately from paid choices',
    () async {
      final journey = await CustomerCheckoutJourneyFixture.create();
      addTearDown(journey.dispose);

      await journey.completeRegisteredUnknownAndManualCartPurchase();

      final attempt = await journey.database
          .select(journey.database.scanAttempts)
          .getSingle();
      final objects = await journey.database
          .select(journey.database.inferenceObjects)
          .get();
      final resolutions = await journey.database
          .select(journey.database.objectResolutions)
          .get();
      final orders = await journey.database
          .select(journey.database.finalOrders)
          .get();
      final payments = await journey.database
          .select(journey.database.simulatedPayments)
          .get();
      final lines = await journey.database
          .select(journey.database.finalOrderLines)
          .get();

      expect(objects.where((object) => object.skuId == null), hasLength(1));
      expect(objects.where((object) => object.skuId != null), hasLength(1));
      expect(resolutions.map((row) => row.source).toSet(), {
        'ai_auto_customer_accepted',
        'customer_top3',
      });
      expect(
        lines.map((line) => '${line.productId}:${line.quantity}').toSet(),
        {'croissant:1', 'sugar-donut:1', 'milk-bread:2'},
      );
      expect(
        lines
            .map((line) => '${line.productId}:${line.resolutionSource}')
            .toSet(),
        {
          'croissant:ai_auto_customer_accepted',
          'sugar-donut:customer_top3',
          'milk-bread:customer_manual_cart',
        },
      );
      expect(orders.single.totalQuantity, 4);
      expect(orders.single.totalAmountKrw, 7900);
      expect(payments.single.amountKrw, 7900);
      expect(attempt.imageSha256, journey.captureSha256);
      expect(attempt.receiptSha256, journey.inferenceReceiptSha256);
      expect(await journey.hasVerifiedAuditEvidence(attempt), isTrue);
      expect(journey.customerReturnedToReady, isTrue);
    },
  );
}
