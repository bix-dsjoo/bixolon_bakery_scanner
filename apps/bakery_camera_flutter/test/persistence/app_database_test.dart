import 'dart:io';

import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late BakeryDatabase db;

  setUp(() {
    db = openInMemoryBakeryDatabase();
  });

  tearDown(() async {
    await db.close();
  });

  test('schema version 1 installs immutable operational settings', () async {
    final settings = await db.select(db.settingsRevisions).getSingle();
    final pointer = await db.select(db.appSettings).getSingle();
    final diagnostics = await db.diagnostics();

    expect(db.schemaVersion, 1);
    expect(settings.revisionId, 'settings-v1');
    expect(settings.retryLimit, 2);
    expect(settings.paymentCompleteDurationSeconds, 4);
    expect(settings.customerAutoReset, isTrue);
    expect(settings.evidenceRetentionDays, 90);
    expect(settings.locale, 'ko-KR');
    expect(settings.kioskDisplayName, 'BIXOLON Bakery');
    expect(settings.adminAuthorLabel, 'prototype-admin');
    expect(pointer.activeSettingsRevisionId, 'settings-v1');
    expect(diagnostics.schemaVersion, 1);
    expect(diagnostics.applicationVersion, '1.1.0+4');
    expect(diagnostics.lastMigrationResult, 'created_schema_v1');
  });

  test(
    'schema rejects a registered inference object without provenance',
    () async {
      await _seedAttempt(db);

      await expectLater(
        db
            .into(db.inferenceObjects)
            .insert(
              InferenceObjectsCompanion.insert(
                inferenceObjectId: 'attempt-1/object-1',
                attemptId: 'attempt-1',
                objectId: 'object-1',
                skuId: const Value(7),
                skuName: '소금빵',
                decisionPath: 'repvit_direct',
                confidence: 0.97,
                bboxJson: '[10,20,100,150]',
                detectorSource: 'rfdetr_large_bakery_v1',
                detectorScore: 0.95,
                provenanceJson: '{}',
                unknownReason: const Value(null),
              ),
            ),
        throwsA(isA<InvalidDataException>()),
      );
    },
  );

  test('schema enforces all-or-none product photo provenance', () async {
    await db
        .into(db.catalogRevisions)
        .insert(
          CatalogRevisionsCompanion.insert(
            revisionId: 'catalog-v1',
            sha256: _hash('a'),
            createdAtUs: 1,
            isActive: true,
          ),
        );

    await expectLater(
      db
          .into(db.products)
          .insert(
            ProductsCompanion.insert(
              productRevisionId: 'catalog-v1/product-1',
              catalogRevisionId: 'catalog-v1',
              productId: 'product-1',
              displayName: '소금빵',
              unitPriceKrw: 2800,
              recognitionSkuId: const Value(7),
              categoryId: 'bread',
              photoRelativePath: const Value('products/salt-bread.jpg'),
              active: true,
              sortOrder: 1,
            ),
          ),
      throwsA(isA<Exception>()),
    );
  });

  test('catalog repository reads only the active immutable revision', () async {
    await db
        .into(db.catalogRevisions)
        .insert(
          CatalogRevisionsCompanion.insert(
            revisionId: 'catalog-v1',
            sha256: _hash('a'),
            createdAtUs: 1,
            isActive: true,
          ),
        );
    await db
        .into(db.products)
        .insert(
          ProductsCompanion.insert(
            productRevisionId: 'catalog-v1/product-1',
            catalogRevisionId: 'catalog-v1',
            productId: 'product-1',
            displayName: '소금빵',
            unitPriceKrw: 2800,
            recognitionSkuId: const Value(7),
            categoryId: 'bread',
            active: true,
            sortOrder: 1,
          ),
        );
    final repository = DatabaseCatalogRepository(db);

    final catalog = await repository.activeCatalog();

    expect(catalog.revision.revisionId, 'catalog-v1');
    expect(catalog.products.single.productId, 'product-1');
    expect((await repository.productForRecognitionSku(7))?.displayName, '소금빵');
    expect(await repository.search('소금'), hasLength(1));
    expect(
      (await repository.customerDiscovery()).featuredProducts,
      hasLength(1),
    );
  });

  test('opening a newer database schema fails closed', () async {
    final previousWarningSetting =
        driftRuntimeOptions.dontWarnAboutMultipleDatabases;
    driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
    addTearDown(() {
      driftRuntimeOptions.dontWarnAboutMultipleDatabases =
          previousWarningSetting;
    });
    final directory = await Directory.systemTemp.createTemp(
      'bakery-newer-schema-',
    );
    final file = File('${directory.path}${Platform.pathSeparator}scanner.db');
    addTearDown(() async {
      if (directory.existsSync()) {
        await directory.delete(recursive: true);
      }
    });
    final original = BakeryDatabase(NativeDatabase(file));
    await original.select(original.appSettings).getSingle();
    await original.customStatement('PRAGMA user_version = 2');
    await original.close();
    final newer = BakeryDatabase(NativeDatabase(file));
    addTearDown(newer.close);

    await expectLater(
      newer.select(newer.appSettings).getSingle(),
      throwsA(isA<StateError>()),
    );
  });
}

Future<void> _seedAttempt(BakeryDatabase db) async {
  await db
      .into(db.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: 'catalog-v1',
          sha256: _hash('a'),
          createdAtUs: 1,
          isActive: true,
        ),
      );
  await db
      .into(db.checkoutSessions)
      .insert(
        CheckoutSessionsCompanion.insert(
          sessionId: 'session-1',
          state: 'active',
          startedAtUs: 2,
          catalogRevisionId: 'catalog-v1',
          settingsRevisionId: 'settings-v1',
          detectorId: 'rfdetr_large_bakery_v1',
          detectorSha256: _hash('b'),
          repvitArtifactId: 'repvit_m1_15plus5_v1',
          repvitSha256: _hash('c'),
          repvitManifestSha256: _hash('d'),
          repvitPrototypeSha256: _hash('e'),
          dinov3ArtifactId: 'dinov3_vits16_15plus5_v1',
          dinov3Sha256: _hash('f'),
          dinov3SupportSha256: _hash('0'),
          calibrationId: 'calibration-v1',
          calibrationSha256: _hash('1'),
          preprocessSha256: _hash('2'),
          fusionPolicyId: 'fusion-v1',
          fusionPolicySha256: _hash('3'),
          configSnapshotJson: '{"pipeline":"canonical_cpu"}',
        ),
      );
  await db
      .into(db.scanAttempts)
      .insert(
        ScanAttemptsCompanion.insert(
          attemptId: 'attempt-1',
          sessionId: 'session-1',
          attemptNumber: 1,
          capturedAtUs: 3,
          imageRelativePath: 'sessions/session-1/attempt-001.jpg',
          imageByteSize: 42,
          imageSha256: _hash('4'),
          status: 'staged',
        ),
      );
}

String _hash(String character) => character * 64;
