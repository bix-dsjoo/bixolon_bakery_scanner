import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_ports.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/catalog_picker.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/order_review_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  testWidgets('catalog shows featured category search and stable active list', (
    tester,
  ) async {
    final catalog = _Catalog([
      _product('alpha', 'Alpha', 'sweet', 1),
      _product('beta', 'Beta', 'savory', 2),
      _product('gamma', 'Gamma', 'sweet', 3),
    ]);
    final snapshot = await catalog.activeCatalog();
    await _pump(
      tester,
      CatalogPicker(
        discovery: await catalog.customerDiscoveryFor(snapshot),
        search: (query) async => snapshot.search(query),
        onSelected: (_) {},
      ),
    );

    expect(find.text('Alpha'), findsWidgets);
    expect(find.text('Beta'), findsWidgets);
    expect(
      tester.getTopLeft(find.text('Alpha').last).dy,
      lessThan(tester.getTopLeft(find.text('Beta').last).dy),
    );
    await tester.tap(
      find.descendant(
        of: find.byType(ChoiceChip),
        matching: find.text('sweet'),
      ),
    );
    await tester.pump();
    expect(find.text('Gamma'), findsWidgets);
    await tester.enterText(find.byType(TextField), 'Gamma');
    await tester.pump();
    expect(find.text('Gamma'), findsWidgets);
    expect(find.text('Alpha'), findsNothing);
  });

  testWidgets(
    'catalog picker keeps featured search and selection on its supplied session snapshot',
    (tester) async {
      final catalog = _Catalog([
        _product('original', 'Original Bread', 'sweet', 1),
        _product('other', 'Other Bread', 'savory', 2),
      ]);
      final sessionSnapshot = await catalog.activeCatalog();
      final discovery = await catalog.customerDiscoveryFor(sessionSnapshot);
      catalog.activate([
        _product('replacement', 'Replacement Bread', 'sweet', 3),
      ]);
      Product? selected;

      await _pump(
        tester,
        CatalogPicker(
          discovery: discovery,
          search: (query) async => sessionSnapshot.search(query),
          onSelected: (product) => selected = product,
        ),
      );

      expect(find.text('Original Bread'), findsWidgets);
      expect(find.text('Replacement Bread'), findsNothing);
      await tester.enterText(find.byType(TextField), 'Original');
      await tester.pump();
      expect(find.text('Original Bread'), findsOneWidget);
      await tester.tap(find.text('Original Bread'));

      expect(selected?.productId, 'original');
    },
  );

  testWidgets('review exposes exact top3 and the full catalog escape hatch', (
    tester,
  ) async {
    final result = buildUiInferenceResult();
    final unknown = result.objects.last;
    final products = {
      10: _product('ten', 'Top 1', 'sweet', 10),
      11: _product('eleven', 'Top 2', 'sweet', 11),
      12: _product('twelve', 'Top 3', 'sweet', 12),
    };
    String? chosen;
    String? catalogObject;
    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [ObjectDraft.unresolved(unknown)],
          lines: const [],
        ),
        productForCandidate: (_, sku) => products[sku],
        onChooseTop3: (_, sku) => chosen = '$sku',
        onOpenCatalog: (id) => catalogObject = id,
        onContinue: () {},
      ),
    );
    await tester.tap(find.text('Top 2'));
    expect(chosen, '11');
    await tester.tap(find.byIcon(Icons.search));
    expect(catalogObject, unknown.objectId);
  });

  testWidgets(
    'order supports quantity remove mismatch and one payment action',
    (tester) async {
      final product = _product('manual', 'Manual', 'sweet', 1);
      final actions = <String>[];
      await _pump(
        tester,
        OrderReviewView(
          state: CheckoutState(
            phase: CheckoutPhase.orderReview,
            objectDrafts: const [],
            lines: [CheckoutLine(product: product, quantity: 1)],
          ),
          onSetQuantity: (_, quantity) => actions.add('quantity:$quantity'),
          onAddProduct: () => actions.add('add'),
          onOverrideObject: (_) => actions.add('override'),
          onCountMismatch: () => actions.add('mismatch'),
          onPay: () => actions.add('pay'),
          onRemoveProduct: (_) => actions.add('remove'),
        ),
      );
      await tester.tap(find.byIcon(Icons.add).first);
      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.tap(find.byIcon(Icons.restart_alt));
      await tester.tap(find.byType(FilledButton));
      expect(
        actions,
        containsAll(<String>['quantity:2', 'remove', 'mismatch', 'pay']),
      );
      expect(find.bySemanticsLabel('직접 담기 안내 그림'), findsOneWidget);
    },
  );

  testWidgets('completion supports policy auto reset and manual continuation', (
    tester,
  ) async {
    var automatic = 0;
    await _pump(
      tester,
      PaymentCompleteView(
        state: _completeState(),
        policy: const CustomerCompletionPolicy(
          duration: Duration(milliseconds: 50),
          autoReset: true,
        ),
        onNext: () async => automatic += 1,
      ),
    );
    await tester.pump(const Duration(milliseconds: 50));
    expect(automatic, 1);
    expect(find.bySemanticsLabel('결제 완료 안내 그림'), findsOneWidget);

    var manual = 0;
    await _pump(
      tester,
      PaymentCompleteView(
        state: _completeState(),
        policy: const CustomerCompletionPolicy(
          duration: Duration(milliseconds: 50),
          autoReset: false,
        ),
        onNext: () async => manual += 1,
      ),
    );
    await tester.pump(const Duration(milliseconds: 60));
    expect(manual, 0);
    await tester.tap(find.byType(FilledButton));
    expect(manual, 1);
  });

  testWidgets('customer surfaces contain no technical evaluator terms', (
    tester,
  ) async {
    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [
            ObjectDraft.unresolved(buildUiInferenceResult().objects.last),
          ],
          lines: const [],
        ),
        productForCandidate: (_, _) => null,
        onChooseTop3: (_, _) {},
        onOpenCatalog: (_) {},
        onContinue: () {},
      ),
    );
    for (final term in const [
      'GPU',
      'SHA',
      'ms',
      'confidence',
      'bbox',
      'detector',
    ]) {
      expect(find.textContaining(term), findsNothing);
    }
  });
}

Future<void> _pump(WidgetTester tester, Widget child) => tester.pumpWidget(
  MaterialApp(
    theme: buildBakeryTheme(),
    home: Scaffold(body: child),
  ),
);

CheckoutState _completeState() => CheckoutState(
  phase: CheckoutPhase.paymentComplete,
  objectDrafts: const [],
  lines: const [],
  paymentReceipt: PaymentReceipt(
    paymentId: 'payment',
    orderId: 'order',
    sessionId: 'session',
    amount: 1000,
    currency: 'KRW',
    provider: 'simulated',
    status: 'approved',
    paidAt: DateTime.utc(2026),
  ),
);

Product _product(String id, String name, String category, int sku) => Product(
  productId: id,
  displayName: name,
  unitPrice: 1000,
  recognitionSkuId: sku,
  categoryId: category,
  photoAssetPath: null,
  active: true,
  sortOrder: sku,
);

class _Catalog implements CatalogRepository {
  _Catalog(this.products);
  List<Product> products;

  void activate(List<Product> replacement) => products = replacement;

  @override
  Future<CatalogSnapshot> activeCatalog() async => CatalogSnapshot(
    revision: CatalogRevision(
      revisionId: 'catalog',
      sha256: 'a' * 64,
      createdAt: DateTime.utc(2026),
    ),
    products: products,
  );

  @override
  Future<CustomerCatalogDiscovery> customerDiscoveryFor(
    CatalogSnapshot catalog,
  ) async => CustomerCatalogDiscovery(
    catalog: catalog,
    featuredProducts: catalog.products.take(2).toList(),
  );

  @override
  Future<Product?> productForRecognitionSku(int recognitionSkuId) async =>
      products
          .where((item) => item.recognitionSkuId == recognitionSkuId)
          .firstOrNull;

  Future<List<Product>> search(String query) async => products
      .where(
        (item) => item.displayName.toLowerCase().contains(query.toLowerCase()),
      )
      .toList();
}
