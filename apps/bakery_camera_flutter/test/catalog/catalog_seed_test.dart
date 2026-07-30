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

      expect(snapshot.revision.revisionId, 'catalog-v1');
      expect(snapshot.products, hasLength(6));
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
        'product-almond-campagne',
        'product-walnut-donut',
        'product-croissant',
        'product-pastry-bread',
        'product-mini-bread',
        'product-cream-bun',
      ]);
    },
  );

  test(
    'seed preserves commercial identity independently from recognition SKU',
    () async {
      await seed.installIfEmpty();

      final creamBun = (await repository.activeCatalog()).products.singleWhere(
        (product) => product.productId == 'product-cream-bun',
      );

      expect(creamBun.displayName, '크림빵');
      expect(creamBun.recognitionSkuId, isNull);
      expect(await repository.productForRecognitionSku(20), isNull);
    },
  );
}
