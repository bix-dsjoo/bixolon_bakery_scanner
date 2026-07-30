import 'dart:convert';
import 'dart:io';

import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_photo_store.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:crypto/crypto.dart';
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
    'rejects a save when a referenced catalog photo is not verified',
    () async {
      final root = await Directory.systemTemp.createTemp('product-save-photo-');
      addTearDown(() => root.delete(recursive: true));
      final guarded = ProductManagementService(
        database: database,
        createId: () => 'catalog-photo-missing',
        now: () => DateTime.utc(2026, 7, 31),
        photoStore: CatalogPhotoStore(root),
      );
      final before = await guarded.activeCatalog();
      final validPhotoMetadata = CatalogPhoto(
        relativePath: 'catalog-media/${_hash('a')}.png',
        byteSize: 42,
        sha256: _hash('a'),
        mediaType: 'image/png',
        provenanceNote: const CatalogPhotoProvenance.approvedLocalImport(
          sourceReference: 'operator-camera-roll-03',
        ).serialize(),
      );

      await expectLater(
        () => guarded.save(
          ProductDraft.add(
            productId: 'photo-without-membership',
            displayName: 'Unverified photo bread',
            unitPriceKrw: 1300,
            categoryId: 'bread',
            sortOrder: 99,
            photo: validPhotoMetadata,
          ),
        ),
        throwsStateError,
      );
      expect(
        (await guarded.activeCatalog()).revision.revisionId,
        before.revision.revisionId,
      );
    },
  );

  test(
    'imports an approved local photo before persisting its catalog revision',
    () async {
      final root = await Directory.systemTemp.createTemp(
        'product-import-photo-',
      );
      addTearDown(() => root.delete(recursive: true));
      final source = File('${root.path}${Platform.pathSeparator}sale.png');
      await source.writeAsBytes(
        base64Decode(
          'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8////fwYGBgYmEAHCAD34BABm6tHAAAAAAElFTkSuQmCC',
        ),
      );
      final guarded = ProductManagementService(
        database: database,
        createId: () => 'catalog-photo-imported',
        now: () => DateTime.utc(2026, 7, 31),
        photoStore: CatalogPhotoStore(root),
      );

      final photo = await guarded.importPhoto(
        source,
        provenance: const CatalogPhotoProvenance.approvedLocalImport(
          sourceReference: 'operator-camera-roll-06',
        ),
      );
      final saved = await guarded.save(
        ProductDraft.add(
          productId: 'verified-photo-bread',
          displayName: 'Verified photo bread',
          unitPriceKrw: 2500,
          categoryId: 'bread',
          sortOrder: 98,
          recognitionSkuId: 20,
          photo: photo,
        ),
      );

      final product = saved.products.singleWhere(
        (item) => item.productId == 'verified-photo-bread',
      );
      expect(product.photoSha256, photo.sha256);
      expect(product.photoByteSize, photo.byteSize);
      expect(product.photoMediaType, photo.mediaType);
      expect(
        CatalogPhotoProvenance.parse(
          product.photoProvenanceNote!,
        ).sourceReference,
        'operator-camera-roll-06',
      );
    },
  );

  test('rejects a copied checkout capture by its audit hash', () async {
    final root = await Directory.systemTemp.createTemp('product-scan-photo-');
    addTearDown(() => root.delete(recursive: true));
    final source = File('${root.path}${Platform.pathSeparator}copied.png');
    final bytes = base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8////fwYGBgYmEAHCAD34BABm6tHAAAAAAElFTkSuQmCC',
    );
    await source.writeAsBytes(bytes);
    await _insertStagedScanReference(
      database,
      catalogRevisionId: (await service.activeCatalog()).revision.revisionId,
      imageSha256: sha256.convert(bytes).toString(),
    );
    final guarded = ProductManagementService(
      database: database,
      createId: () => 'unused',
      now: () => DateTime.utc(2026),
      photoStore: CatalogPhotoStore(root),
    );

    await expectLater(
      () => guarded.importPhoto(
        source,
        provenance: const CatalogPhotoProvenance.approvedLocalImport(
          sourceReference: 'operator-camera-roll-07',
        ),
      ),
      throwsA(isA<ArgumentError>()),
    );
  });

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

Future<void> _insertStagedScanReference(
  BakeryDatabase database, {
  required String catalogRevisionId,
  required String imageSha256,
}) async {
  const sessionId = 'protected-photo-source-session';
  await database
      .into(database.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: sessionId,
          state: 'active',
          startedAtUs: 10,
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
      .into(database.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: 'protected-photo-source-attempt',
          sessionId: sessionId,
          attemptNumber: 1,
          capturedAtUs: 11,
          imageRelativePath: 'sessions/$sessionId/capture.jpg',
          imageByteSize: 1,
          imageSha256: imageSha256,
          status: 'staged',
        ),
      );
}

String _hash(String character) => character * 64;
