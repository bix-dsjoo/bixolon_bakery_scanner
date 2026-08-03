import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart' hide isNull;
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late BakeryDatabase database;
  late DatabaseCatalogRepository repository;

  setUp(() async {
    database = openInMemoryBakeryDatabase();
    repository = DatabaseCatalogRepository(database);
    await CatalogSeed(database).installIfEmpty();
  });

  tearDown(() => database.close());

  test(
    'search uses normalized display name and stable sort order',
    () async {
      final result = await repository.search('  E g G  ');
      final sorted = List<Product>.of(result)..sort(Product.customerSort);

      expect(result.map((product) => product.displayName), contains('Egg Tart'));
      expect(result, orderedEquals(sorted));
    },
  );

  test(
    'search returns only active products and SKU lookup never substitutes',
    () async {
      await (database.update(database.products)
            ..where((row) => row.productId.equals('product-croissant')))
          .write(const ProductsCompanion(active: Value(false)));

      final result = await repository.search('크루아상');

      expect(result, isEmpty);
      expect(await repository.productForRecognitionSku(6), isNull);
      expect(await repository.productForRecognitionSku(0), isNull);
    },
  );

  test(
    'featured products count completed orders only and sort by frequency',
    () async {
      final snapshot = await repository.activeCatalog();
      final ignoredActiveOrderProduct = snapshot.products.first;
      final completedOrderProduct = snapshot.products[1];
      await _insertOrder(
        database,
        sessionId: 'session-open',
        orderId: 'order-open',
        product: ignoredActiveOrderProduct,
        quantity: 99,
        completed: false,
        catalogRevisionId: snapshot.revision.revisionId,
      );
      await _insertOrder(
        database,
        sessionId: 'session-completed',
        orderId: 'order-completed',
        product: completedOrderProduct,
        quantity: 2,
        completed: true,
        catalogRevisionId: snapshot.revision.revisionId,
      );

      final discovery = await repository.customerDiscoveryFor(snapshot);

      expect(
        discovery.featuredProducts.first.productId,
        completedOrderProduct.productId,
      );
    },
  );

  test(
    'customer discovery orders equal completed counts by customer sort and excludes open orders',
    () async {
      final initialCatalog = await repository.activeCatalog();
      await (database.update(database.products)..where(
            (row) => row.productId.equals(initialCatalog.products[1].productId),
          ))
          .write(
            ProductsCompanion(
              sortOrder: Value(initialCatalog.products.first.sortOrder),
            ),
          );
      final snapshot = await repository.activeCatalog();
      final firstTiedProduct = snapshot.products[0];
      final secondTiedProduct = snapshot.products[1];
      final openOrderProduct = snapshot.products[2];
      final laterTiedProduct = snapshot.products[3];
      expect(firstTiedProduct.sortOrder, secondTiedProduct.sortOrder);
      expect(firstTiedProduct.productId, isNot(secondTiedProduct.productId));
      expect(
        laterTiedProduct.sortOrder,
        greaterThan(firstTiedProduct.sortOrder),
      );

      await _insertOrder(
        database,
        sessionId: 'session-tied-first',
        orderId: 'order-tied-first',
        product: firstTiedProduct,
        quantity: 4,
        completed: true,
        catalogRevisionId: snapshot.revision.revisionId,
      );
      await _insertOrder(
        database,
        sessionId: 'session-tied-second',
        orderId: 'order-tied-second',
        product: secondTiedProduct,
        quantity: 4,
        completed: true,
        catalogRevisionId: snapshot.revision.revisionId,
      );
      await _insertOrder(
        database,
        sessionId: 'session-tied-later',
        orderId: 'order-tied-later',
        product: laterTiedProduct,
        quantity: 4,
        completed: true,
        catalogRevisionId: snapshot.revision.revisionId,
      );
      await _insertOrder(
        database,
        sessionId: 'session-open-high-count',
        orderId: 'order-open-high-count',
        product: openOrderProduct,
        quantity: 99,
        completed: false,
        catalogRevisionId: snapshot.revision.revisionId,
      );

      final discovery = await repository.customerDiscoveryFor(snapshot);
      final expectedTiedOrder = [
        firstTiedProduct,
        secondTiedProduct,
        laterTiedProduct,
      ]..sort(Product.customerSort);

      expect(
        discovery.featuredProducts.take(3).map((product) => product.productId),
        orderedEquals(expectedTiedOrder.map((product) => product.productId)),
      );
      expect(
        discovery.featuredProducts.indexWhere(
          (product) => product.productId == openOrderProduct.productId,
        ),
        greaterThanOrEqualTo(3),
      );
    },
  );

  test(
    'customer product ordering resolves exact sort-order ties by product ID',
    () {
      final laterId = _product('product-z', sortOrder: 7);
      final earlierId = _product('product-a', sortOrder: 7);
      final sorted = [laterId, earlierId]..sort(Product.customerSort);

      expect(sorted.map((product) => product.productId), [
        'product-a',
        'product-z',
      ]);
    },
  );
}

Product _product(String productId, {required int sortOrder}) => Product(
  productId: productId,
  displayName: productId,
  unitPrice: 1000,
  recognitionSkuId: null,
  categoryId: 'test',
  photoAssetPath: null,
  active: true,
  sortOrder: sortOrder,
);

Future<void> _insertOrder(
  BakeryDatabase database, {
  required String sessionId,
  required String orderId,
  required Product product,
  required int quantity,
  required bool completed,
  required String catalogRevisionId,
}) async {
  await database
      .into(database.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: sessionId,
          state: 'active',
          startedAtUs: 1,
          catalogRevisionId: catalogRevisionId,
          settingsRevisionId: 'settings-v1',
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _hash('a'),
          repvitArtifactId: 'repvit_m1_15plus5_v1',
          repvitSha256: _hash('b'),
          repvitManifestSha256: _hash('c'),
          repvitPrototypeSha256: _hash('d'),
          dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _hash('e'),
          dinov3SupportSha256: _hash('f'),
          calibrationId: 'calibration-v1',
          calibrationSha256: _hash('0'),
          preprocessSha256: _hash('1'),
          fusionPolicyId: 'fusion-v1',
          fusionPolicySha256: _hash('2'),
          configSnapshotJson: '{"pipeline":"canonical_cpu"}',
        ),
      );
  await database
      .into(database.finalOrders)
      .insert(
        FinalOrdersCompanion.insert(
          orderId: orderId,
          sessionId: sessionId,
          catalogRevisionId: catalogRevisionId,
          createdAtUs: 2,
          totalQuantity: quantity,
          totalAmountKrw: product.unitPrice * quantity,
          receiptRelativePath: 'sessions/$sessionId/final-order.json',
          receiptByteSize: 1,
          receiptSha256: _hash('3'),
        ),
      );
  await database
      .into(database.finalOrderLines)
      .insert(
        FinalOrderLinesCompanion.insert(
          finalLineId: 'line-$orderId',
          orderId: orderId,
          productRevisionId: '$catalogRevisionId/${product.productId}',
          productId: product.productId,
          recognitionSkuId: Value(product.recognitionSkuId),
          productName: product.displayName,
          unitPriceKrw: product.unitPrice,
          quantity: quantity,
          lineAmountKrw: product.unitPrice * quantity,
          resolutionSource: 'customer_manual_cart',
        ),
      );
  if (!completed) return;
  await database
      .into(database.simulatedPayments)
      .insert(
        SimulatedPaymentsCompanion.insert(
          paymentId: 'payment-$orderId',
          orderId: orderId,
          sessionId: sessionId,
          amountKrw: product.unitPrice * quantity,
          currency: 'KRW',
          provider: 'simulated',
          status: 'approved',
          finalOrderSha256: _hash('4'),
          paidAtUs: 3,
        ),
      );
  await (database.update(
    database.checkoutSessions,
  )..where((row) => row.sessionId.equals(sessionId))).write(
    const CheckoutSessionsCompanion(
      state: Value('completed'),
      terminalAtUs: Value(3),
      terminalReason: Value('payment_committed'),
    ),
  );
}

String _hash(String character) => character * 64;
