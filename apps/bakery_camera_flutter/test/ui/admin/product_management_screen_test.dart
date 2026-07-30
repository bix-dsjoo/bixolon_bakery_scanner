import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:bakery_camera_prototype/src/ui/admin/product_management_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'leads with customer sale facts and keeps technical mapping advanced',
    (tester) async {
      final database = openInMemoryBakeryDatabase();
      await CatalogSeed(database).installIfEmpty();
      addTearDown(database.close);
      final service = ProductManagementService(
        database: database,
        createId: () => 'unused',
        now: () => DateTime.utc(2026),
      );
      await tester.pumpWidget(
        MaterialApp(home: ProductManagementScreen(service: service)),
      );
      await tester.pumpAndSettle();

      expect(find.text('\uC0C1\uD488 \uCD94\uAC00'), findsOneWidget);
      expect(find.text('\uD310\uB9E4 \uAC00\uB2A5'), findsWidgets);
      expect(find.textContaining('AI \uC5F0\uACB0\uB428'), findsWidgets);
      expect(find.text('Model SKU mapping'), findsNothing);
      await tester.tap(find.text('\uC0C1\uC138 \uC815\uBCF4').first);
      await tester.pump();
      expect(find.text('Model SKU mapping'), findsOneWidget);
    },
  );
}
