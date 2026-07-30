import 'package:bakery_camera_prototype/src/catalog/product.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_models.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_state.dart';
import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_checkout_screen.dart';
import 'package:bakery_camera_prototype/src/ui/customer/catalog_picker.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/order_review_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/ready_view.dart';
import 'package:bakery_camera_prototype/src/ui/customer/retake_required_view.dart';
import 'package:bakery_camera_prototype/src/ui/components/checkout_scaffold.dart';
import 'package:bakery_camera_prototype/src/persistence/app_database.dart';
import 'package:bakery_camera_prototype/src/persistence/database_catalog_repository.dart';
import 'package:bakery_camera_prototype/src/persistence/database_factory.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/inference_fixtures.dart';

void main() {
  setUpAll(_loadVisualFonts);

  testWidgets(
    'customer checkout states remain usable at kiosk sizes and 200 percent text',
    (tester) async {
      for (final size in const [Size(1024, 720), Size(1280, 820)]) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        for (final scale in const [1.0, 2.0]) {
          for (final screen in _screens) {
            await tester.pumpWidget(_app(screen, scale: scale));
            await tester.pumpAndSettle();
            expect(tester.takeException(), isNull, reason: '$size at $scale');
            final controls = find
                .byWidgetPredicate(
                  (widget) =>
                      widget is FilledButton ||
                      widget is TextButton ||
                      widget is IconButton,
                )
                .evaluate();
            for (final element in controls) {
              expect(
                tester
                    .getSize(
                      find.byElementPredicate(
                        (candidate) => identical(candidate, element),
                      ),
                    )
                    .shortestSide,
                greaterThanOrEqualTo(48),
              );
            }
          }
        }
      }
    },
  );

  testWidgets(
    'seeded full catalog keeps Korean controls and touch targets accessible at kiosk sizes',
    (tester) async {
      final database = openInMemoryBakeryDatabase();
      addTearDown(database.close);
      await _seedFullCatalog(database);
      final catalog = DatabaseCatalogRepository(database);
      final sessionCatalog = await catalog.activeCatalog();
      final discovery = await catalog.customerDiscoveryFor(sessionCatalog);
      final semantics = tester.ensureSemantics();

      for (final size in const [Size(1024, 720), Size(1280, 820)]) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        for (final scale in const [1.0, 2.0]) {
          await tester.pumpWidget(
            _app(
              CheckoutScaffold(
                title: '상품 찾기',
                primaryAction: const SizedBox(height: 56),
                child: Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: CatalogPicker(
                    key: UniqueKey(),
                    discovery: discovery,
                    search: (query) async => sessionCatalog.search(query),
                    onSelected: (_) {},
                  ),
                ),
              ),
              scale: scale,
              highContrast: true,
            ),
          );
          await tester.pumpAndSettle();

          expect(tester.takeException(), isNull, reason: '$size at $scale');
          expect(find.text('전체 상품'), findsOneWidget);
          expect(find.bySemanticsLabel('상품 이름 검색'), findsOneWidget);
          _expectMinimumTouchTarget(tester, find.byType(ActionChip));
          _expectMinimumTouchTarget(tester, find.byType(ChoiceChip));
          _expectMinimumTouchTarget(tester, find.byType(ListTile));

          await tester.sendKeyEvent(LogicalKeyboardKey.tab);
          await tester.pump();
          final firstFocus = tester.binding.focusManager.primaryFocus;
          expect(firstFocus, isNotNull);
          await tester.sendKeyEvent(LogicalKeyboardKey.tab);
          await tester.pump();
          expect(tester.binding.focusManager.primaryFocus, isNot(firstFocus));
        }
      }
      semantics.dispose();
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    },
  );

  testWidgets(
    'ready action has Korean screen-reader semantics and keyboard focus',
    (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(_app(const ReadyView(onScan: _noop)));

      expect(
        tester.getSemantics(find.byType(FilledButton)),
        matchesSemantics(
          label: '빵 확인하기',
          isButton: true,
          hasEnabledState: true,
          isEnabled: true,
          isFocusable: true,
          hasFocusAction: true,
          hasTapAction: true,
        ),
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      expect(tester.binding.focusManager.primaryFocus, isNotNull);
      semantics.dispose();
    },
  );

  testWidgets(
    'high-contrast keyboard focus retains a visible primary outline',
    (tester) async {
      await tester.pumpWidget(
        _app(const ReadyView(onScan: _noop), highContrast: true),
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();

      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      final side = button.style!.side!.resolve({WidgetState.focused});
      expect(side!.color, const Color(0xFF176BFF));
      expect(side.width, greaterThanOrEqualTo(2));
    },
  );

  testWidgets('customer ready state matches the approved 1280 kiosk layout', (
    tester,
  ) async {
    await _golden(
      tester,
      const ReadyView(onScan: _noop),
      'customer_ready_1280x820.png',
    );
  });

  testWidgets('customer retake state matches the approved 1280 kiosk layout', (
    tester,
  ) async {
    await _golden(
      tester,
      RetakeRequiredView(
        state: _retakeState,
        manualCartEligible: true,
        onRetake: _noop,
        onManualEntry: _noop,
      ),
      'customer_retake_1280x820.png',
    );
  });

  testWidgets('customer review state matches the approved 1280 kiosk layout', (
    tester,
  ) async {
    await _golden(
      tester,
      CustomerReviewView(
        state: _reviewState,
        productForCandidate: (_, skuId) => skuId == 10 ? _sugarDonut : null,
        onChooseTop3: (_, _) {},
        onOpenCatalog: (_) {},
        onContinue: _noop,
      ),
      'customer_review_1280x820.png',
    );
  });

  testWidgets('customer order state matches the approved 1280 kiosk layout', (
    tester,
  ) async {
    await _golden(
      tester,
      OrderReviewView(
        state: _orderState,
        onSetQuantity: (_, _) {},
        onAddProduct: _noop,
        onOverrideObject: (_) {},
        onCountMismatch: _noop,
        onPay: _noop,
        onRemoveProduct: (_) {},
      ),
      'customer_order_1280x820.png',
    );
  });

  testWidgets(
    'customer completion state matches the approved 1280 kiosk layout',
    (tester) async {
      await _golden(
        tester,
        PaymentCompleteView(
          state: _completeState,
          policy: const CustomerCompletionPolicy(
            duration: Duration(hours: 1),
            autoReset: false,
          ),
          onNext: () async {},
        ),
        'customer_complete_1280x820.png',
      );
    },
  );
}

Future<void> _loadVisualFonts() async {
  final pretendard = FontLoader('Pretendard')
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Regular.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Medium.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-SemiBold.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Bold.otf'));
  final materialIcons = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  await Future.wait([pretendard.load(), materialIcons.load()]);
}

Widget _app(Widget child, {double scale = 1, bool highContrast = false}) =>
    MaterialApp(
      theme: buildBakeryTheme(),
      home: MediaQuery(
        data: MediaQueryData(
          textScaler: TextScaler.linear(scale),
          highContrast: highContrast,
        ),
        child: child,
      ),
    );

Future<void> _golden(WidgetTester tester, Widget screen, String name) async {
  tester.view.physicalSize = const Size(1280, 820);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(_app(screen));
  await tester.pumpAndSettle();
  await expectLater(find.byType(Scaffold), matchesGoldenFile('goldens/$name'));
}

void _noop() {}

void _expectMinimumTouchTarget(WidgetTester tester, Finder finder) {
  expect(finder, findsWidgets);
  for (final element in finder.evaluate()) {
    expect(
      tester
          .getSize(
            find.byElementPredicate(
              (candidate) => identical(candidate, element),
            ),
          )
          .shortestSide,
      greaterThanOrEqualTo(48),
      reason: '${element.widget.runtimeType} must provide a 48px touch target',
    );
  }
}

Future<void> _seedFullCatalog(BakeryDatabase database) async {
  const revisionId = 'accessibility-catalog-v1';
  await database
      .into(database.catalogRevisions)
      .insert(
        CatalogRevisionsCompanion.insert(
          revisionId: revisionId,
          sha256: 'c' * 64,
          createdAtUs: DateTime.utc(2026, 7, 30).microsecondsSinceEpoch,
          isActive: true,
        ),
      );
  const names = [
    '소금빵',
    '크루아상',
    '우유식빵',
    '앙버터',
    '단팥빵',
    '치즈빵',
    '슈크림빵',
    '고구마빵',
    '카스텔라',
    '마늘바게트',
    '모카번',
    '피자빵',
  ];
  for (var index = 0; index < names.length; index += 1) {
    await database
        .into(database.products)
        .insert(
          ProductsCompanion.insert(
            productRevisionId: '$revisionId/product-$index',
            catalogRevisionId: revisionId,
            productId: 'product-$index',
            displayName: names[index],
            unitPriceKrw: 1000 + index * 100,
            recognitionSkuId: Value(index < 11 ? index + 1 : null),
            categoryId: index.isEven ? '식사빵' : '간식빵',
            active: true,
            sortOrder: index,
          ),
        );
  }
}

final _sugarDonut = Product(
  productId: 'sugar-donut',
  displayName: '슈가 도넛',
  unitPrice: 2500,
  recognitionSkuId: 10,
  categoryId: 'donut',
  photoAssetPath: null,
  active: true,
  sortOrder: 1,
);

final _reviewState = CheckoutState(
  phase: CheckoutPhase.customerReview,
  objectDrafts: [ObjectDraft.unresolved(buildUiInferenceResult().objects.last)],
  lines: const [],
);

final _retakeState = CheckoutState(
  phase: CheckoutPhase.retakeRequired,
  objectDrafts: const [],
  lines: const [],
  failure: const CheckoutFailure(
    code: 'no_bread_detected',
    message: 'customer action required',
    recoverable: true,
  ),
);

final _orderState = CheckoutState(
  phase: CheckoutPhase.orderReview,
  objectDrafts: const [],
  lines: [CheckoutLine(product: _sugarDonut, quantity: 2)],
);

final _completeState = CheckoutState(
  phase: CheckoutPhase.paymentComplete,
  objectDrafts: const [],
  lines: const [],
  paymentReceipt: PaymentReceipt(
    paymentId: 'payment-1',
    orderId: 'order-1',
    sessionId: 'session-1',
    amount: 5000,
    currency: 'KRW',
    provider: 'simulated',
    status: 'approved',
    paidAt: DateTime.utc(2026, 7, 30),
  ),
);

final _screens = <Widget>[
  const ReadyView(onScan: _noop),
  RetakeRequiredView(
    state: _retakeState,
    manualCartEligible: true,
    onRetake: _noop,
    onManualEntry: _noop,
  ),
  CustomerReviewView(
    state: _reviewState,
    productForCandidate: (_, skuId) => skuId == 10 ? _sugarDonut : null,
    onChooseTop3: (_, _) {},
    onOpenCatalog: (_) {},
    onContinue: _noop,
  ),
  OrderReviewView(
    state: _orderState,
    onSetQuantity: (_, _) {},
    onAddProduct: _noop,
    onOverrideObject: (_) {},
    onCountMismatch: _noop,
    onPay: _noop,
    onRemoveProduct: (_) {},
  ),
  PaymentCompleteView(
    state: _completeState,
    policy: const CustomerCompletionPolicy(
      duration: Duration(hours: 1),
      autoReset: false,
    ),
    onNext: () async {},
  ),
];
