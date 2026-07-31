import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/bixolon_theme_extension.dart';
import 'package:bakery_camera_prototype/src/ui/components/bakery_primary_button.dart';
import 'package:bakery_camera_prototype/src/ui/components/bakery_status_banner.dart';
import 'package:bakery_camera_prototype/src/ui/components/checkout_scaffold.dart';
import 'package:bakery_camera_prototype/src/ui/components/price_text.dart';
import 'package:bakery_camera_prototype/src/ui/components/product_tile.dart';
import 'package:bakery_camera_prototype/src/ui/components/quantity_stepper.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

final Future<void> _pretendardFontsLoaded = _loadPretendardFonts();
final Future<void> _materialIconsFontLoaded = _loadMaterialIconsFont();

void main() {
  setUpAll(() async {
    await _pretendardFontsLoaded;
    await _materialIconsFontLoaded;
  });

  test('bundled Pretendard fonts load in the visual test renderer', () async {
    await _pretendardFontsLoaded;
  });

  test('Material Icons font loads in the visual test renderer', () async {
    await _materialIconsFontLoaded;
  });

  test('theme exposes the approved Material 3 BIXOLON token contract', () {
    final theme = buildBakeryTheme();
    final tokens = theme.extension<BixolonThemeExtension>();

    expect(theme.useMaterial3, isTrue);
    expect(theme.textTheme.bodyMedium?.fontFamily, 'Pretendard');
    expect(tokens, isNotNull);
    expect(tokens!.canvas, const Color(0xFFFFFFFF));
    expect(tokens.ink, const Color(0xFF000000));
    expect(tokens.mutedInk, const Color(0xFF5C5C5C));
    expect(tokens.divider, const Color(0xFFE8E8E8));
    expect(tokens.action, const Color(0xFFEE7203));
    expect(tokens.selectedSurface, const Color(0xFFFCEAD9));
    expect(tokens.controlBorder, const Color(0xFFD8D8D8));
    expect(tokens.disabledAction, const Color(0xFFFAD5B3));
    expect(theme.colorScheme.primary, tokens.action);
    expect(tokens.focus, const Color(0xFF184C9F));
    expect(tokens.confirmed, const Color(0xFF268B20));
    expect(tokens.uncertainty, const Color(0xFFC76B00));
    expect(tokens.error, const Color(0xFFCC2427));
    expect(tokens.controlRadius, 5);
    expect(tokens.surfaceRadius, 5);
    expect(tokens.modalRadius, 10);
  });

  testWidgets('primary action and stepper controls meet kiosk touch targets', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(
          body: Column(
            children: [
              BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
              QuantityStepper(quantity: 9, onChanged: (_) {}),
            ],
          ),
        ),
      ),
    );

    expect(tester.getSize(find.byType(BakeryPrimaryButton)).height, 56);
    expect(tester.getSize(find.byTooltip('수량 줄이기')).shortestSide, 48);
    expect(tester.getSize(find.byTooltip('수량 늘리기')).shortestSide, 48);
  });

  testWidgets('price has tabular numerals and status is never color-only', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: const Scaffold(
          body: Column(
            children: [
              PriceText(amount: 123450),
              BakeryStatusBanner(
                status: BakeryStatus.uncertain,
                title: '확인이 필요해요',
                message: '상품을 다시 확인해 주세요.',
              ),
            ],
          ),
        ),
      ),
    );

    final price = tester.widget<Text>(find.text('123,450원'));
    expect(
      price.style!.fontFeatures,
      contains(const FontFeature.tabularFigures()),
    );
    expect(find.byIcon(Icons.help_outline), findsOneWidget);
    expect(find.byKey(const ValueKey('status-message')), findsOneWidget);
    expect(find.text('확인이 필요해요'), findsOneWidget);
    expect(find.text('상품을 다시 확인해 주세요.'), findsOneWidget);
  });

  test('price formatter rejects a negative checkout amount', () {
    expect(() => PriceText.formatKrw(-1), throwsArgumentError);
  });

  testWidgets('customer controls expose Korean action and status semantics', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(
          body: Column(
            children: [
              BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
              const BakeryStatusBanner(
                status: BakeryStatus.error,
                title: '결제할 수 없어요',
                message: '직원에게 알려 주세요.',
              ),
            ],
          ),
        ),
      ),
    );

    expect(
      tester.getSemantics(find.byType(BakeryPrimaryButton)),
      matchesSemantics(
        label: '결제하기',
        isButton: true,
        hasEnabledState: true,
        isEnabled: true,
        hasTapAction: true,
      ),
    );
    expect(
      tester.getSemantics(find.byType(BakeryStatusBanner)),
      matchesSemantics(label: '결제할 수 없어요. 직원에게 알려 주세요.'),
    );
    semantics.dispose();
  });

  testWidgets('long Korean copy remains usable at 200 percent text scale', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(2)),
          child: CheckoutScaffold(
            title: '상품과 수량을 확인한 뒤 결제해 주세요',
            primaryAction: BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
            child: const ProductTile(
              name: '고소한 우유 크림이 든 소금빵',
              price: 3200,
              availability: ProductAvailability.available,
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(OverflowBar), findsNothing);
    expect(find.byKey(const ValueKey('customer-page-title')), findsOneWidget);
  });

  testWidgets('focused primary action has a visible focus outline', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBakeryTheme(),
        home: Scaffold(
          body: BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
        ),
      ),
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();

    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    final side = button.style!.side!.resolve(<WidgetState>{
      WidgetState.focused,
    });
    expect(side!.color, const Color(0xFF184C9F));
    expect(side.width, greaterThanOrEqualTo(2));
  });

  testWidgets(
    'keyboard-focused quantity actions have a visible focus outline',
    (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildBakeryTheme(),
          home: Scaffold(body: QuantityStepper(quantity: 2, onChanged: (_) {})),
        ),
      );

      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();

      final decrement = tester.widget<IconButton>(
        find.byType(IconButton).first,
      );
      final side = decrement.style!.side!.resolve(<WidgetState>{
        WidgetState.focused,
      });
      expect(side!.color, const Color(0xFF184C9F));
      expect(side.width, greaterThanOrEqualTo(2));
      expect(
        tester.getSemantics(find.byType(IconButton).first),
        matchesSemantics(
          isFocused: true,
          isButton: true,
          isFocusable: true,
          hasEnabledState: true,
          isEnabled: true,
          hasFocusAction: true,
          hasTapAction: true,
        ),
      );
      semantics.dispose();
    },
  );

  testWidgets('design-system catalog matches the kiosk receipt layout', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 820);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const _DesignSystemCatalog());

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/design_system_1280x820.png'),
    );
  });
}

Future<void> _loadPretendardFonts() async {
  final fontLoader = FontLoader('Pretendard')
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Regular.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Medium.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-SemiBold.otf'))
    ..addFont(rootBundle.load('assets/fonts/Pretendard-Bold.otf'));
  await fontLoader.load();
}

Future<void> _loadMaterialIconsFont() async {
  final fontLoader = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  await fontLoader.load();
}

class _DesignSystemCatalog extends StatelessWidget {
  const _DesignSystemCatalog();

  @override
  Widget build(BuildContext context) => MaterialApp(
    theme: buildBakeryTheme(),
    home: CheckoutScaffold(
      title: '결제 전 확인',
      primaryAction: BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          BakeryStatusBanner(
            status: BakeryStatus.ready,
            title: '상품을 담았어요',
            message: '수량을 확인한 뒤 결제해 주세요.',
          ),
          SizedBox(height: 16),
          ProductTile(
            name: '소금빵',
            price: 2800,
            availability: ProductAvailability.available,
            trailing: QuantityStepper(quantity: 1),
          ),
          SizedBox(height: 8),
          ProductTile(
            name: '우유 크림 소금빵',
            price: 0,
            availability: ProductAvailability.lowStock,
            trailing: QuantityStepper(quantity: 9),
          ),
          SizedBox(height: 8),
          ProductTile(
            name: '오늘의 식빵',
            price: 123450,
            availability: ProductAvailability.unavailable,
            trailing: QuantityStepper(quantity: 99),
          ),
        ],
      ),
    ),
  );
}
