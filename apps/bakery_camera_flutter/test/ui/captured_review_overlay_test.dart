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

  testWidgets(
    'keeps the painted canonical border exact and clamps a separate edge hit target',
    (tester) async {
      await pumpOverlay(
        tester,
        objects: const [
          CustomerReviewObject(
            objectId: 'edge-object',
            displayNumber: 1,
            rect: Rect.fromLTRB(1910, 1070, 1920, 1080),
            state: CustomerReviewObjectState.needsChoice,
            label: 'attention',
          ),
        ],
      );

      final image = tester.getRect(
        find.byKey(const Key('captured-review-full-scene')),
      );
      final border = tester.getRect(
        find.byKey(const Key('customer-review-border-edge-object')),
      );
      final target = tester.getRect(
        find.byKey(const Key('customer-review-overlay-edge-object')),
      );

      expect(
        border.left,
        closeTo(image.left + image.width * 1910 / 1920, 0.01),
      );
      expect(border.top, closeTo(image.top + image.height * 1070 / 1080, 0.01));
      expect(border.width, closeTo(image.width * 10 / 1920, 0.01));
      expect(border.height, closeTo(image.height * 10 / 1080, 0.01));
      expect(target.size, const Size(48, 48));
      expect(target.right, closeTo(image.right, 0.01));
      expect(target.bottom, closeTo(image.bottom, 0.01));
    },
  );

  testWidgets(
    'uses deterministic overlap order and renders the selected object last',
    (tester) async {
      final selections = <String>[];
      const overlappingObjects = [
        CustomerReviewObject(
          objectId: 'object-1',
          displayNumber: 1,
          rect: Rect.fromLTWH(300, 300, 300, 300),
          state: CustomerReviewObjectState.needsChoice,
          label: 'first',
        ),
        CustomerReviewObject(
          objectId: 'object-2',
          displayNumber: 2,
          rect: Rect.fromLTWH(300, 300, 300, 300),
          state: CustomerReviewObjectState.needsChoice,
          label: 'second',
        ),
      ];
      await pumpOverlay(
        tester,
        objects: overlappingObjects,
        onSelectObject: selections.add,
      );

      await tester.tapAt(
        tester.getCenter(
          find.byKey(const Key('customer-review-overlay-object-2')),
        ),
      );
      expect(selections, ['object-2']);

      selections.clear();
      await pumpOverlay(
        tester,
        objects: overlappingObjects,
        selectedObjectId: 'object-1',
        onSelectObject: selections.add,
      );
      await tester.tapAt(
        tester.getCenter(
          find.byKey(const Key('customer-review-overlay-object-1')),
        ),
      );
      expect(selections, ['object-1']);
    },
  );

  testWidgets('announces selected attention object without model detail', (
    tester,
  ) async {
    await pumpOverlay(tester, selectedObjectId: 'object-2');

    expect(find.bySemanticsLabel('사진에서 02번, 확인이 필요해요 선택됨'), findsOneWidget);
    expect(find.textContaining('0.88'), findsNothing);
    expect(find.textContaining('confidence'), findsNothing);
  });
}

String _korean(List<int> codePoints) => String.fromCharCodes(codePoints);

Future<void> pumpOverlay(
  WidgetTester tester, {
  ValueChanged<String>? onSelectObject,
  String? selectedObjectId,
  List<CustomerReviewObject>? objects,
}) {
  final confirmedLabel = _korean(<int>[0xD655, 0xC778, 0xB428]);
  const attentionLabel = '확인이 필요해요';
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
            objects:
                objects ??
                [
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
