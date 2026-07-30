import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart' hide isNull;
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late BakeryDatabase database;
  late ProductManagementService service;

  setUp(() async {
    database = openInMemoryBakeryDatabase();
    await CatalogSeed(database).installIfEmpty();
    service = ProductManagementService(
      database: database,
      createId: () => 'catalog-v2',
      now: () => DateTime.utc(2026, 7, 31),
    );
  });
  tearDown(() => database.close());

  test(
    'adds a directly selectable product in a copy-on-write revision',
    () async {
      final before = await service.activeCatalog();

      final after = await service.save(
        ProductDraft.add(
          productId: 'product-direct-only',
          displayName: 'Direct catalog bread',
          unitPriceKrw: 3200,
          categoryId: 'bread',
          sortOrder: 99,
        ),
      );

      expect(after.revision.revisionId, 'catalog-v2');
      expect(after.revision.revisionId, isNot(before.revision.revisionId));
      expect(
        after.products
            .singleWhere((item) => item.productId == 'product-direct-only')
            .recognitionSkuId,
        isNull,
      );
      expect((await service.activeCatalog()).revision.revisionId, 'catalog-v2');
      final revisions = await database.select(database.catalogRevisions).get();
      expect(
        revisions
            .singleWhere((row) => row.revisionId == before.revision.revisionId)
            .isActive,
        isFalse,
      );
      expect(
        revisions.singleWhere((row) => row.revisionId == 'catalog-v2').sha256,
        matches(RegExp(r'^[a-f0-9]{64}$')),
      );
      final event =
          await (database.select(
                database.auditEvents,
              )..where((row) => row.eventType.equals('catalog_revision_saved')))
              .getSingle();
      expect(event.detail, contains(before.revision.revisionId));
      expect(event.detail, contains('catalog-v2'));
    },
  );

  test(
    'edits by cloning and deactivates without deleting historical product IDs',
    () async {
      final original = await service.activeCatalog();
      final product = original.products.first;
      final edited = await service.save(
        ProductDraft.edit(
          productId: product.productId,
          displayName: '${product.displayName} ?곸꽭',
          unitPriceKrw: product.unitPriceKrw + 100,
          categoryId: product.categoryId,
          recognitionSkuId: product.recognitionSkuId,
          active: false,
          sortOrder: product.sortOrder,
        ),
      );

      final inOldRevision =
          await (database.select(database.products)..where(
                (row) =>
                    row.catalogRevisionId.equals(original.revision.revisionId) &
                    row.productId.equals(product.productId),
              ))
              .getSingle();
      expect(inOldRevision.displayName, product.displayName);
      final inNewRevision = edited.products.singleWhere(
        (item) => item.productId == product.productId,
      );
      expect(inNewRevision.active, isFalse);
      expect(inNewRevision.unitPriceKrw, product.unitPriceKrw + 100);
    },
  );

  test('rejects invalid changes before creating another revision', () async {
    final before = await service.activeCatalog();
    final existing = before.products.first;

    await expectLater(
      () => service.save(
        ProductDraft.add(
          productId: existing.productId,
          displayName: 'dup',
          unitPriceKrw: 100,
          categoryId: 'bread',
          sortOrder: 1,
        ),
      ),
      throwsA(isA<ArgumentError>()),
    );
    await expectLater(
      () => service.save(
        ProductDraft.add(
          productId: 'invalid-price',
          displayName: 'bad',
          unitPriceKrw: -1,
          categoryId: 'bread',
          sortOrder: 1,
        ),
      ),
      throwsA(isA<ArgumentError>()),
    );
    await expectLater(
      () => service.save(
        ProductDraft.add(
          productId: 'duplicate-sku',
          displayName: 'bad',
          unitPriceKrw: 100,
          categoryId: 'bread',
          sortOrder: 1,
          recognitionSkuId: existing.recognitionSkuId,
        ),
      ),
      throwsA(isA<ArgumentError>()),
    );
    expect(
      (await service.activeCatalog()).revision.revisionId,
      before.revision.revisionId,
    );
  });

  test(
    'completed order keeps its frozen name and price after a catalog edit',
    () async {
      final current = await service.activeCatalog();
      final product = current.products.first;
      await _insertCompletedOrder(
        database,
        product: product,
        catalogRevisionId: current.revision.revisionId,
      );
      final lineBefore = await database
          .select(database.finalOrderLines)
          .getSingle();

      await service.save(
        ProductDraft.edit(
          productId: product.productId,
          displayName: 'Renamed future product',
          unitPriceKrw: product.unitPriceKrw + 1000,
          categoryId: product.categoryId,
          recognitionSkuId: product.recognitionSkuId,
          active: product.active,
          sortOrder: product.sortOrder,
        ),
      );

      final lineAfter = await database
          .select(database.finalOrderLines)
          .getSingle();
      expect(lineAfter.productName, lineBefore.productName);
      expect(lineAfter.unitPriceKrw, lineBefore.unitPriceKrw);
    },
  );
}

Future<void> _insertCompletedOrder(
  BakeryDatabase database, {
  required ManagedCatalogProduct product,
  required String catalogRevisionId,
}) async {
  const sessionId = 'product-history-session';
  const orderId = 'product-history-order';
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
          totalQuantity: 1,
          totalAmountKrw: product.unitPriceKrw,
          receiptRelativePath: 'sessions/$sessionId/final-order.json',
          receiptByteSize: 1,
          receiptSha256: _hash('3'),
        ),
      );
  await database
      .into(database.finalOrderLines)
      .insert(
        FinalOrderLinesCompanion.insert(
          finalLineId: 'product-history-line',
          orderId: orderId,
          productRevisionId: '$catalogRevisionId/${product.productId}',
          productId: product.productId,
          recognitionSkuId: Value(product.recognitionSkuId),
          productName: product.displayName,
          unitPriceKrw: product.unitPriceKrw,
          quantity: 1,
          lineAmountKrw: product.unitPriceKrw,
          resolutionSource: 'customer_manual_cart',
        ),
      );
  await database
      .into(database.simulatedPayments)
      .insert(
        SimulatedPaymentsCompanion.insert(
          paymentId: 'product-history-payment',
          orderId: orderId,
          sessionId: sessionId,
          amountKrw: product.unitPriceKrw,
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
