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
    'search uses normalized Korean display name and stable sort order',
    () async {
      final result = await repository.search('  크 림  ');
      final sorted = List<Product>.of(result)..sort(Product.customerSort);

      expect(result.map((product) => product.displayName), contains('크림빵'));
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
      expect(await repository.productForRecognitionSku(3), isNull);
      expect(await repository.productForRecognitionSku(0), isNull);
    },
  );
}
