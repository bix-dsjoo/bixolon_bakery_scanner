import 'package:bakery_camera_prototype/src/admin/product_management_service.dart';
import 'package:bakery_camera_prototype/src/catalog/catalog_seed.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:bakery_camera_prototype/src/ui/admin/product_editor_screen.dart';
import 'package:bakery_camera_prototype/src/ui/admin/product_management_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'leads with customer sale facts and keeps technical mapping advanced',
    (tester) async {
      final database = (await tester.runAsync(() async {
        final database = openInMemoryBakeryDatabase();
        await CatalogSeed(database).installIfEmpty();
        return database;
      }))!;
      addTearDown(() => tester.runAsync(database.close));
      final service = ProductManagementService(
        database: database,
        createId: () => 'unused',
        now: () => DateTime.utc(2026),
      );
      await tester.pumpWidget(
        MaterialApp(home: ProductManagementScreen(service: service)),
      );
      await tester.pumpAndSettle();

      expect(find.text('상품 추가'), findsOneWidget);
      expect(find.text('판매 가능'), findsWidgets);
      expect(find.textContaining('AI 연결됨'), findsWidgets);
      expect(find.text('Model SKU mapping'), findsNothing);
      expect(find.byKey(const ValueKey('product-list')), findsOneWidget);
      await tester.tap(find.text('상세 정보').first);
      await tester.pumpAndSettle();
      expect(find.text('Model SKU mapping'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    },
  );

  testWidgets('editor exposes SKU and trusted-photo intake controls', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final database = (await tester.runAsync(() async {
      final database = openInMemoryBakeryDatabase();
      await CatalogSeed(database).installIfEmpty();
      return database;
    }))!;
    addTearDown(() => tester.runAsync(database.close));
    final service = ProductManagementService(
      database: database,
      createId: () => 'unused',
      now: () => DateTime.utc(2026),
    );
    await tester.pumpWidget(
      MaterialApp(home: ProductEditorScreen(service: service)),
    );

    expect(find.byKey(const Key('product-recognition-sku')), findsOneWidget);
    expect(find.byKey(const Key('product-photo-source-path')), findsOneWidget);
    expect(
      find.byKey(const Key('product-photo-source-reference')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('product-import-photo')), findsOneWidget);
    await tester.tap(find.byKey(const Key('product-recognition-sku')));
    await tester.pumpAndSettle();
    expect(find.text('직접 선택 전용'), findsWidgets);
    expect(find.text('SKU 20'), findsOneWidget);
    await tester.tap(find.text('SKU 20'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
