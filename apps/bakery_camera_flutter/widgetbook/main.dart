import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/components/bakery_primary_button.dart';
import 'package:bakery_camera_prototype/src/ui/components/bakery_status_banner.dart';
import 'package:bakery_camera_prototype/src/ui/components/checkout_scaffold.dart';
import 'package:bakery_camera_prototype/src/ui/components/price_text.dart';
import 'package:bakery_camera_prototype/src/ui/components/product_tile.dart';
import 'package:bakery_camera_prototype/src/ui/components/quantity_stepper.dart';
import 'package:flutter/material.dart';
import 'package:widgetbook/widgetbook.dart';

void main() => runApp(
  Widgetbook.material(
    addons: [
      MaterialThemeAddon(
        themes: [WidgetbookTheme(name: 'BIXOLON', data: buildBakeryTheme())],
      ),
    ],
    directories: [
      WidgetbookFolder(
        name: 'Checkout foundations',
        children: [
          WidgetbookComponent(
            name: 'Primary action',
            useCases: [
              WidgetbookUseCase(
                name: 'Ready',
                builder: (context) => _preview(
                  BakeryPrimaryButton(label: '결제하기', onPressed: () {}),
                ),
              ),
              WidgetbookUseCase(
                name: 'Disabled',
                builder: (context) => _preview(
                  const BakeryPrimaryButton(label: '결제하기', onPressed: null),
                ),
              ),
              WidgetbookUseCase(
                name: 'Long Korean text',
                builder: (context) => _preview(
                  BakeryPrimaryButton(
                    label: '상품과 수량을 확인하고 결제하기',
                    onPressed: () {},
                  ),
                ),
              ),
            ],
          ),
          WidgetbookComponent(
            name: 'Status',
            useCases: [
              for (final status in BakeryStatus.values)
                WidgetbookUseCase(
                  name: switch (status) {
                    BakeryStatus.ready => 'Ready',
                    BakeryStatus.loading => 'Loading',
                    BakeryStatus.uncertain => 'Uncertainty',
                    BakeryStatus.error => 'Error',
                  },
                  builder: (context) => _preview(
                    BakeryStatusBanner(
                      status: status,
                      title: switch (status) {
                        BakeryStatus.ready => '상품을 담았어요',
                        BakeryStatus.loading => '상품을 확인하고 있어요',
                        BakeryStatus.uncertain => '확인이 필요해요',
                        BakeryStatus.error => '결제할 수 없어요',
                      },
                      message: '다음 안내를 확인해 주세요.',
                    ),
                  ),
                ),
            ],
          ),
          WidgetbookComponent(
            name: 'Product availability',
            useCases: [
              for (final availability in ProductAvailability.values)
                WidgetbookUseCase(
                  name: availability.name,
                  builder: (context) => _preview(
                    ProductTile(
                      name: '우유 크림 소금빵',
                      price: 3200,
                      availability: availability,
                    ),
                  ),
                ),
            ],
          ),
          WidgetbookComponent(
            name: 'Quantity',
            useCases: [
              for (final quantity in [1, 9, 99])
                WidgetbookUseCase(
                  name: '$quantity items',
                  builder: (context) => _preview(
                    QuantityStepper(quantity: quantity, onChanged: (_) {}),
                  ),
                ),
            ],
          ),
          WidgetbookComponent(
            name: 'Prices',
            useCases: [
              for (final amount in [0, 123450])
                WidgetbookUseCase(
                  name: '${amount}KRW',
                  builder: (context) => _preview(PriceText(amount: amount)),
                ),
            ],
          ),
          WidgetbookComponent(
            name: 'Text scale',
            useCases: [
              WidgetbookUseCase(
                name: '200 percent',
                builder: (context) => MediaQuery(
                  data: const MediaQueryData(textScaler: TextScaler.linear(2)),
                  child: _preview(
                    const ProductTile(
                      name: '고소한 우유 크림이 든 소금빵',
                      price: 3200,
                      availability: ProductAvailability.available,
                    ),
                  ),
                ),
              ),
            ],
          ),
          WidgetbookComponent(
            name: 'Checkout shell',
            useCases: [
              WidgetbookUseCase(
                name: 'Focus',
                builder: (context) => CheckoutScaffold(
                  title: '결제 전 확인',
                  primaryAction: BakeryPrimaryButton(
                    label: '결제하기',
                    onPressed: () {},
                    autofocus: true,
                  ),
                  child: const ProductTile(
                    name: '소금빵',
                    price: 2800,
                    availability: ProductAvailability.available,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    ],
  ),
);

Widget _preview(Widget child) => Scaffold(
  body: Padding(padding: const EdgeInsets.all(24), child: child),
);
