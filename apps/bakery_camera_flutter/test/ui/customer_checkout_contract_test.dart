import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_ports.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/catalog_picker.dart';
import 'package:bakery_camera_prototype/src/ui/customer/checkout_review_workspace.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/order_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/ready_view.dart';
import 'package:bakery_camera_prototype/src/ui/components/price_text.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  for (final scenario in ['candidate', 'automatic']) {
    testWidgets('$scenario review uses one retained-scene checkout workspace', (
      tester,
    ) async {
      final result = buildUiInferenceResult();
      final acceptedProduct = _product('croissant', 'Croissant', 'pastry', 6);
      final accepted = ObjectDraft.accepted(
        inferenceObject: result.objects.first,
        product: acceptedProduct,
      );
      final candidateProducts = {
        10: _product('ten', 'Candidate A', 'sweet', 10),
        11: _product('eleven', 'Candidate B', 'sweet', 11),
        12: _product('twelve', 'Candidate C', 'sweet', 12),
      };
      final automatic = scenario == 'automatic';
      final state = CheckoutState(
        phase: automatic
            ? CheckoutPhase.orderReview
            : CheckoutPhase.customerReview,
        objectDrafts: [
          accepted,
          if (!automatic) ObjectDraft.unresolved(result.objects.last),
        ],
        lines: [CheckoutLine(product: acceptedProduct, quantity: 1)],
        capturedEvidenceDisplayPath: 'test/fixtures/missing-capture.jpg',
        capturedImageWidth: 1920,
        capturedImageHeight: 1080,
      );

      await _pump(
        tester,
        automatic
            ? OrderReviewView(
                state: state,
                onSetQuantity: (_, _) {},
                onAddProduct: () {},
                onOverrideObject: (_) {},
                onCountMismatch: () {},
                onPay: () {},
                onRemoveProduct: (_) {},
              )
            : CustomerReviewView(
                state: state,
                productForCandidate: (_, sku) => candidateProducts[sku],
                onChooseTop3: (_, _) {},
                onOpenCatalog: (_) {},
                onContinue: () {},
              ),
      );

      expect(find.byType(CheckoutReviewWorkspace), findsOneWidget);
      expect(
        find.byKey(const Key('checkout-review-scene-pane')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('checkout-review-task-pane')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('checkout-review-workspace-divider')),
        findsOneWidget,
      );
      if (automatic) {
        expect(find.text('Top 1'), findsNothing);
        final action = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, '1,000원 결제하기'),
        );
        expect(action.onPressed, isNotNull);
      } else {
        expect(find.text('Top 1'), findsOneWidget);
        expect(find.text('Top 2'), findsOneWidget);
        expect(find.text('Top 3'), findsOneWidget);
        final action = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, '확인할 빵 1개 남음'),
        );
        expect(action.onPressed, isNull);
      }
    });
  }

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
        matching: find.text('달콤한 빵'),
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

  testWidgets('catalog has an explicit return and customer category labels', (
    tester,
  ) async {
    final catalog = _Catalog([
      _product('donut', 'Walnut Donut', 'donut', 1),
      _product('bread', 'Milk Bread', 'bread', 2),
      _product('sandwich', 'Ham Sandwich', 'sandwich', 3),
    ]);
    final snapshot = await catalog.activeCatalog();
    final discovery = await catalog.customerDiscoveryFor(snapshot);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => Scaffold(
                    body: CatalogPicker(
                      discovery: discovery,
                      search: (query) async => snapshot.search(query),
                      onSelected: (_) {},
                    ),
                  ),
                ),
              ),
              child: const Text('Open catalog'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open catalog'));
    await tester.pumpAndSettle();
    expect(find.text('도넛'), findsWidgets);
    expect(find.text('빵'), findsWidgets);
    expect(find.text('샌드위치'), findsWidgets);
    expect(find.byKey(const Key('customer-catalog-close')), findsOneWidget);

    await tester.tap(find.byKey(const Key('customer-catalog-close')));
    await tester.pumpAndSettle();
    expect(find.text('Open catalog'), findsOneWidget);
    expect(find.byType(CatalogPicker), findsNothing);
  });

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
    await tester.ensureVisible(find.text('Top 2'));
    await tester.tap(find.text('Top 2'));
    expect(chosen, '11');
    await tester.ensureVisible(find.text('다른 상품 찾기'));
    await tester.tap(find.text('다른 상품 찾기'));
    expect(catalogObject, unknown.objectId);
  });

  testWidgets('links numbered ledger row to the selected image box', (
    tester,
  ) async {
    final result = buildUiInferenceResult();
    final accepted = ObjectDraft.accepted(
      inferenceObject: result.objects.first,
      product: _product('croissant', 'Croissant', 'sweet', 6),
    );
    final unresolved = ObjectDraft.unresolved(result.objects.last);
    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [accepted, unresolved],
          lines: const [],
          capturedEvidenceDisplayPath: 'test/fixtures/missing-capture.jpg',
          capturedImageWidth: 1920,
          capturedImageHeight: 1080,
        ),
        productForCandidate: (_, sku) =>
            _product('$sku', 'Top $sku', 'sweet', sku),
        onChooseTop3: (_, _) {},
        onOpenCatalog: (_) {},
        onContinue: () {},
      ),
    );

    final sceneBefore = tester.getRect(
      find.byKey(const Key('captured-review-full-scene')),
    );
    await tester.tap(find.byKey(const Key('customer-review-overlay-object-1')));
    await tester.pumpAndSettle();
    final firstRow = find.byKey(const Key('customer-review-row-object-1'));
    expect(tester.widget<ListTile>(firstRow).selected, isTrue);

    await tester.tap(find.byKey(const Key('customer-review-overlay-object-2')));
    await tester.pumpAndSettle();
    expect(
      tester.getRect(find.byKey(const Key('captured-review-full-scene'))),
      sceneBefore,
    );
    expect(find.bySemanticsLabel('사진에서 02번, 확인이 필요해요 선택됨'), findsOneWidget);
    expect(
      find.byKey(const Key('customer-review-candidate-panel-object-2')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('customer-review-candidate-panel-object-1')),
      findsNothing,
    );
  });

  testWidgets(
    'review keeps the retained scene beside the selected exception at kiosk width',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final result = buildUiInferenceResult();
      final accepted = ObjectDraft.accepted(
        inferenceObject: result.objects.first,
        product: _product('croissant', 'Croissant', 'sweet', 6),
      );
      final unresolved = ObjectDraft.unresolved(result.objects.last);

      await _pump(
        tester,
        CustomerReviewView(
          state: CheckoutState(
            phase: CheckoutPhase.customerReview,
            objectDrafts: [accepted, unresolved],
            lines: const [],
            capturedEvidenceDisplayPath: 'test/fixtures/missing-capture.jpg',
            capturedImageWidth: 1920,
            capturedImageHeight: 1080,
          ),
          productForCandidate: (_, sku) =>
              _product('$sku', 'Top $sku', 'sweet', sku),
          onChooseTop3: (_, _) {},
          onOpenCatalog: (_) {},
          onContinue: () {},
        ),
      );
      await tester.pumpAndSettle();

      final scenePane = find.byKey(const Key('customer-review-scene-pane'));
      final taskPane = find.byKey(const Key('customer-review-task-pane'));
      expect(scenePane, findsOneWidget);
      expect(taskPane, findsOneWidget);
      expect(
        tester.getTopLeft(scenePane).dx,
        lessThan(tester.getTopLeft(taskPane).dx),
      );
      expect(
        tester.getSize(find.byType(FilledButton)).width,
        greaterThan(1000),
      );

      final sceneBefore = tester.getRect(
        find.byKey(const Key('captured-review-full-scene')),
      );
      await tester.tap(
        find.byKey(const Key('customer-review-overlay-object-2')),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('customer-review-candidate-panel-object-2')),
        findsOneWidget,
      );
      expect(
        tester.getRect(find.byKey(const Key('captured-review-full-scene'))),
        sceneBefore,
      );
    },
  );

  testWidgets(
    'review keeps five object selectors visible without strip scrolling',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 820);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final drafts = [
        for (var index = 1; index <= 5; index++)
          ObjectDraft.accepted(
            inferenceObject: InferenceObject.fromJson(
              buildInferenceObjectJson(
                id: 'object-$index',
                skuId: index,
                name: 'Product $index',
                confidence: 0.9,
                decisionPath: 'repvit_direct',
                box: [
                  10.0 + ((index - 1) * 200),
                  20.0,
                  190.0 + ((index - 1) * 200),
                  220.0,
                ],
              ),
              index: index,
              imageWidth: 1200,
              imageHeight: 600,
            ),
            product: _product(
              'product-$index',
              'Product $index',
              'bread',
              index,
            ),
          ),
      ];

      await _pump(
        tester,
        CustomerReviewView(
          state: CheckoutState(
            phase: CheckoutPhase.customerReview,
            objectDrafts: drafts,
            lines: const [],
          ),
          productForCandidate: (_, _) => null,
          onChooseTop3: (_, _) {},
          onOpenCatalog: (_) {},
          onContinue: () {},
        ),
      );

      final taskRect = tester.getRect(
        find.byKey(const Key('customer-review-task-pane')),
      );
      for (var index = 1; index <= 5; index++) {
        final row = find.byKey(Key('customer-review-row-object-$index'));
        expect(row, findsOneWidget);
        final rowRect = tester.getRect(row);
        expect(rowRect.left, greaterThanOrEqualTo(taskRect.left));
        expect(rowRect.right, lessThanOrEqualTo(taskRect.right));
      }
    },
  );

  testWidgets('preserves candidate order and routes catalog and retake', (
    tester,
  ) async {
    final result = buildUiInferenceResult();
    final calls = <String>[];
    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [ObjectDraft.unresolved(result.objects.last)],
          lines: const [],
        ),
        productForCandidate: (_, sku) =>
            _product('$sku', 'Top ${sku - 9}', 'sweet', sku),
        onChooseTop3: (_, sku) => calls.add('candidate:$sku'),
        onOpenCatalog: (id) => calls.add('catalog:$id'),
        onRetakeCapture: () => calls.add('retake'),
        onContinue: () {},
      ),
    );

    expect(
      tester.getTopLeft(find.text('Top 1')).dy,
      lessThan(tester.getTopLeft(find.text('Top 2')).dy),
    );
    expect(
      tester.getTopLeft(find.text('Top 2')).dy,
      lessThan(tester.getTopLeft(find.text('Top 3')).dy),
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('customer-review-candidate-panel-object-2')),
        matching: find.byType(PriceText),
      ),
      findsNWidgets(3),
    );
    await tester.ensureVisible(find.text('Top 2'));
    await tester.tap(find.text('Top 2'));
    await tester.ensureVisible(find.text('다른 상품 찾기'));
    await tester.tap(find.text('다른 상품 찾기'));
    await tester.ensureVisible(find.text('빵을 다시 놓고 촬영'));
    await tester.tap(find.text('빵을 다시 놓고 촬영'));

    expect(calls, ['candidate:11', 'catalog:object-2', 'retake']);
  });

  testWidgets('shows capture overlay only with valid retained dimensions', (
    tester,
  ) async {
    final unresolved = ObjectDraft.unresolved(
      buildUiInferenceResult().objects.last,
    );

    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [unresolved],
          lines: const [],
          capturedEvidenceDisplayPath: 'test/fixtures/missing-capture.jpg',
        ),
        productForCandidate: (_, _) => null,
        onChooseTop3: (_, _) {},
        onOpenCatalog: (_) {},
        onContinue: () {},
      ),
    );
    expect(find.byKey(const Key('captured-review-full-scene')), findsNothing);
    expect(
      find.byKey(const Key('customer-review-row-object-2')),
      findsOneWidget,
    );

    await _pump(
      tester,
      CustomerReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.customerReview,
          objectDrafts: [unresolved],
          lines: const [],
          capturedEvidenceDisplayPath: 'test/fixtures/missing-capture.jpg',
          capturedImageWidth: 1920,
          capturedImageHeight: 1080,
        ),
        productForCandidate: (_, _) => null,
        onChooseTop3: (_, _) {},
        onOpenCatalog: (_) {},
        onContinue: () {},
      ),
    );
    expect(find.byKey(const Key('captured-review-full-scene')), findsOneWidget);
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
      final exceptions = find.byKey(const Key('order-exception-actions'));
      expect(exceptions, findsOneWidget);
      expect(
        find.descendant(of: exceptions, matching: find.byType(OutlinedButton)),
        findsNWidgets(2),
      );
      expect(
        find.descendant(of: exceptions, matching: find.byType(TextButton)),
        findsNothing,
      );
      await tester.tap(find.byIcon(Icons.add).first);
      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.tap(find.text('상품 추가'));
      await tester.tap(find.text('다시 촬영'));
      await tester.tap(find.byType(FilledButton));
      expect(
        actions,
        containsAll(<String>['quantity:2', 'remove', 'add', 'mismatch', 'pay']),
      );
      expect(find.bySemanticsLabel('직접 담기 안내 그림'), findsOneWidget);
    },
  );

  testWidgets('ready preview preserves a useful tray aspect ratio', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 820);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pump(tester, const ReadyView(onScan: null));

    final camera = find.byKey(const Key('live-tray-placement-guide'));
    expect(
      find.descendant(
        of: camera,
        matching: find.byKey(const Key('ready-camera-focus-guide')),
      ),
      findsNothing,
    );
    final preview = tester.getRect(camera);
    expect(preview.width / preview.height, closeTo(16 / 9, 0.02));
  });

  testWidgets('recognized order rows own their single correction action', (
    tester,
  ) async {
    final result = buildUiInferenceResult();
    final product = _product('croissant', 'Croissant', 'pastry', 6);
    final accepted = ObjectDraft.accepted(
      inferenceObject: result.objects.first,
      product: product,
    );

    await _pump(
      tester,
      OrderReviewView(
        state: CheckoutState(
          phase: CheckoutPhase.orderReview,
          objectDrafts: [accepted],
          lines: [CheckoutLine(product: product, quantity: 1)],
        ),
        onSetQuantity: (_, _) {},
        onAddProduct: () {},
        onOverrideObject: (_) {},
        onCountMismatch: () {},
        onPay: () {},
        onRemoveProduct: (_) {},
      ),
    );

    expect(find.byTooltip('인식 상품 변경'), findsOneWidget);
    expect(find.textContaining('상품 변경'), findsNothing);
  });

  testWidgets(
    'duplicate recognized products use overlay numbers for correction',
    (tester) async {
      final objects = buildUiInferenceResult().objects;
      final product = _product('croissant', 'Croissant', 'pastry', 6);
      final selectedObjects = <String>[];

      await _pump(
        tester,
        OrderReviewView(
          state: CheckoutState(
            phase: CheckoutPhase.orderReview,
            objectDrafts: [
              ObjectDraft.accepted(
                inferenceObject: objects.first,
                product: product,
              ),
              ObjectDraft.accepted(
                inferenceObject: objects.last,
                product: product,
              ),
            ],
            lines: [CheckoutLine(product: product, quantity: 2)],
          ),
          onSetQuantity: (_, _) {},
          onAddProduct: () {},
          onOverrideObject: selectedObjects.add,
          onCountMismatch: () {},
          onPay: () {},
          onRemoveProduct: (_) {},
        ),
      );

      await tester.tap(find.byTooltip('인식 상품 변경'));
      await tester.pumpAndSettle();
      expect(find.text('01번 빵 변경'), findsOneWidget);
      expect(find.text('02번 빵 변경'), findsOneWidget);

      await tester.tap(find.text('02번 빵 변경'));
      await tester.pumpAndSettle();
      expect(selectedObjects, [objects.last.objectId]);
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
