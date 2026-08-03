import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late BakeryDatabase database;
  late CatalogSeed seed;
  late DatabaseCatalogRepository repository;

  setUp(() {
    database = openInMemoryBakeryDatabase();
    seed = CatalogSeed(database);
    repository = DatabaseCatalogRepository(database);
  });

  tearDown(() => database.close());

  test(
    'seed import creates one immutable revision and active products',
    () async {
      await seed.installIfEmpty();
      await seed.installIfEmpty();

      final snapshot = await repository.activeCatalog();
      final revisions = await database.select(database.catalogRevisions).get();

      expect(snapshot.revision.revisionId, 'catalog-v1.1.0-r4');
      expect(snapshot.products, hasLength(20));
      expect(
        snapshot.products.every((product) => product.unitPrice >= 0),
        isTrue,
      );
      expect(snapshot.products.every((product) => product.active), isTrue);
      expect(
        snapshot.products.every((product) => product.photoAssetPath == null),
        isTrue,
      );
      expect(revisions, hasLength(1));
      expect(snapshot.products.map((product) => product.productId), [
        'product-walnut-donut',
        'product-croffle',
        'product-waffle',
        'product-scon',
        'product-half-moon-croissant',
        'product-croissant',
        'product-flower-bread',
        'product-almond-scon',
        'product-dinner-roll',
        'product-sugar-donut',
        'product-bagel',
        'product-egg-tart',
        'product-muffin',
        'product-burger',
        'product-sandwich',
        'product-grain-campagne',
        'product-almond-campagne',
        'product-mini-bread',
        'product-pastry-bread',
        'product-plain-bread',
      ]);
    },
  );

  test(
    'seed recognition IDs match the locked five-product camera receipt',
    () async {
      await seed.installIfEmpty();

      final products = (await repository.activeCatalog()).products;
      expect(
        {
          for (final product in products)
            product.productId: product.recognitionSkuId,
        },
        {
          'product-walnut-donut': 1,
          'product-croffle': 2,
          'product-waffle': 3,
          'product-scon': 4,
          'product-half-moon-croissant': 5,
          'product-croissant': 6,
          'product-flower-bread': 7,
          'product-almond-scon': 8,
          'product-dinner-roll': 9,
          'product-sugar-donut': 10,
          'product-bagel': 11,
          'product-egg-tart': 12,
          'product-muffin': 13,
          'product-burger': 14,
          'product-sandwich': 15,
          'product-grain-campagne': 16,
          'product-almond-campagne': 17,
          'product-pastry-bread': 19,
          'product-mini-bread': 18,
          'product-plain-bread': 20,
        },
      );
    },
  );

  test(
    'seed installs and activates r2 over the prior immutable revision',
    () async {
      await database
          .into(database.catalogRevisions)
          .insert(
            CatalogRevisionsCompanion.insert(
              revisionId: 'catalog-v1.1.0',
              sha256: 'a' * 64,
              createdAtUs: 0,
              isActive: true,
            ),
          );

      await seed.installIfEmpty();

      final revisions = await database.select(database.catalogRevisions).get();
      expect(revisions, hasLength(2));
      expect(
        revisions
            .singleWhere((row) => row.revisionId == 'catalog-v1.1.0')
            .isActive,
        isFalse,
      );
      expect(
        revisions
            .singleWhere((row) => row.revisionId == 'catalog-v1.1.0-r4')
            .isActive,
        isTrue,
      );
    },
  );
}
