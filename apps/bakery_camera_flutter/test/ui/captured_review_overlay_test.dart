import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:bakery_camera_prototype/src/ui/customer/captured_review_overlay.dart';
import 'package:bakery_camera_prototype/src/ui/customer/customer_review_presentation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'maps canonical boxes into the full retained image and selects them',
    (tester) async {
      String? selected;
      await pumpOverlay(tester, onSelectObject: (id) => selected = id);

      final box = tester.getRect(
        find.byKey(const Key('customer-review-overlay-object-2')),
      );
      final image = tester.getRect(
        find.byKey(const Key('captured-review-full-scene')),
      );
      expect(box.left, closeTo(image.left + image.width * 600 / 1920, 1));
      expect(box.top, closeTo(image.top + image.height * 100 / 1080, 1));
      await tester.tap(
        find.byKey(const Key('customer-review-overlay-object-2')),
      );
      expect(selected, 'object-2');
    },
  );

  testWidgets('announces selected attention object without model detail', (
    tester,
  ) async {
    await pumpOverlay(tester, selectedObjectId: 'object-2');

    expect(
      find.bySemanticsLabel(
        _korean(<int>[
          0xC0AC,
          0xC9C4,
          0xC5D0,
          0xC11C,
          0x20,
          0x30,
          0x32,
          0xBC88,
          0x2C,
          0x20,
          0xC0C1,
          0xD488,
          0xC744,
          0x20,
          0xD655,
          0xC778,
          0xD574,
          0x20,
          0xC8FC,
          0xC138,
          0xC694,
          0x20,
          0xC120,
          0xD0DD,
          0xB428,
        ]),
      ),
      findsOneWidget,
    );
    expect(find.textContaining('0.88'), findsNothing);
    expect(find.textContaining('confidence'), findsNothing);
  });
}

String _korean(List<int> codePoints) => String.fromCharCodes(codePoints);

Future<void> pumpOverlay(
  WidgetTester tester, {
  ValueChanged<String>? onSelectObject,
  String? selectedObjectId,
}) {
  final confirmedLabel = _korean(<int>[0xD655, 0xC778, 0xB428]);
  final attentionLabel = _korean(<int>[
    0xC0C1,
    0xD488,
    0xC744,
    0x20,
    0xD655,
    0xC778,
    0xD574,
    0x20,
    0xC8FC,
    0xC138,
    0xC694,
  ]);
  return tester.pumpWidget(
    MaterialApp(
      theme: buildBakeryTheme(),
      home: Scaffold(
        body: SizedBox(
          width: 400,
          child: CapturedReviewOverlay(
            imagePath: 'test/fixtures/missing-capture.jpg',
            imageWidth: 1920,
            imageHeight: 1080,
            objects: [
              CustomerReviewObject(
                objectId: 'object-1',
                displayNumber: 1,
                rect: const Rect.fromLTWH(200, 200, 400, 300),
                state: CustomerReviewObjectState.confirmed,
                label: confirmedLabel,
              ),
              CustomerReviewObject(
                objectId: 'object-2',
                displayNumber: 2,
                rect: const Rect.fromLTWH(600, 100, 440, 300),
                state: CustomerReviewObjectState.needsChoice,
                label: attentionLabel,
              ),
            ],
            selectedObjectId: selectedObjectId,
            onSelectObject: onSelectObject ?? (_) {},
          ),
        ),
      ),
    ),
  );
}
