import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:bakery_camera_prototype/src/scanner/result_overlay.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('maps image coordinates through BoxFit.contain offsets', () {
    final transform = ContainedImageTransform(
      imageSize: const Size(400, 200),
      viewportSize: const Size(300, 300),
    );

    expect(transform.imageRect, const Rect.fromLTWH(0, 75, 300, 150));
    expect(
      transform.mapBox(const Rect.fromLTRB(100, 50, 300, 150)),
      const Rect.fromLTRB(75, 112.5, 225, 187.5),
    );
  });

  test('clips source boxes to the canonical image before mapping', () {
    final transform = ContainedImageTransform(
      imageSize: const Size(200, 100),
      viewportSize: const Size(400, 400),
    );

    expect(
      transform.mapBox(const Rect.fromLTRB(-20, -10, 220, 120)),
      const Rect.fromLTWH(0, 100, 400, 200),
    );
  });

  testWidgets(
    'paints confirmed teal, Unknown amber, and only selected box thicker',
    (tester) async {
      const viewportSize = Size(120, 100);
      final transform = ContainedImageTransform(
        imageSize: viewportSize,
        viewportSize: viewportSize,
      );
      final painter = ResultOverlayPainter(
        transform: transform,
        items: const [
          ResultOverlayItem(
            objectId: 'object-1',
            displayNumber: 1,
            imageBox: Rect.fromLTRB(20, 30, 50, 70),
            displayName: 'Croissant',
            isUnknown: false,
          ),
          ResultOverlayItem(
            objectId: 'object-2',
            displayNumber: 2,
            imageBox: Rect.fromLTRB(70, 30, 100, 70),
            displayName: '알 수 없음',
            isUnknown: true,
          ),
        ],
        selectedObjectId: 'object-1',
      );

      final rgba = (await tester.runAsync(
        () => _paintRgba(painter, viewportSize),
      ))!;
      const teal = Color(0xFF0E8A72);
      const amber = Color(0xFFC76B00);

      final selectedTealWidth = _coloredRunWidth(
        rgba,
        imageWidth: viewportSize.width.toInt(),
        y: 50,
        xStart: 15,
        xEnd: 25,
        color: teal,
      );
      final unknownAmberWidth = _coloredRunWidth(
        rgba,
        imageWidth: viewportSize.width.toInt(),
        y: 50,
        xStart: 65,
        xEnd: 75,
        color: amber,
      );

      expect(selectedTealWidth, greaterThan(0));
      expect(unknownAmberWidth, greaterThan(0));
      expect(selectedTealWidth, greaterThan(unknownAmberWidth));
    },
  );

  testWidgets('keeps the compact number visible inside a shallow image', (
    tester,
  ) async {
    const viewportSize = Size(120, 20);
    final painter = ResultOverlayPainter(
      transform: ContainedImageTransform(
        imageSize: viewportSize,
        viewportSize: viewportSize,
      ),
      items: const [
        ResultOverlayItem(
          objectId: 'object-1',
          displayNumber: 1,
          imageBox: Rect.fromLTRB(20, 2, 80, 18),
          displayName: 'Croissant',
          isUnknown: false,
        ),
      ],
      selectedObjectId: null,
    );

    final rgba = (await tester.runAsync(
      () => _paintRgba(painter, viewportSize),
    ))!;
    expect(
      _coloredRunWidth(
        rgba,
        imageWidth: viewportSize.width.toInt(),
        y: 10,
        xStart: 15,
        xEnd: 25,
        color: const Color(0xFF0E8A72),
      ),
      greaterThan(0),
    );
    expect(
      rgba.getUint8((10 * viewportSize.width.toInt() + 30) * 4 + 3),
      greaterThan(0),
    );
  });

  test('hit testing maps letterboxed viewport points to object identity', () {
    final transform = ContainedImageTransform(
      imageSize: const Size(400, 200),
      viewportSize: const Size(300, 300),
    );
    final hitTester = ResultOverlayHitTester(
      transform: transform,
      items: const [
        ResultOverlayItem(
          objectId: 'object-1',
          displayNumber: 1,
          imageBox: Rect.fromLTRB(100, 50, 300, 150),
          displayName: 'Croissant',
          isUnknown: false,
        ),
      ],
      selectedObjectId: null,
    );

    expect(hitTester.hitTest(const Offset(150, 150)), 'object-1');
    expect(hitTester.hitTest(const Offset(150, 50)), isNull);
  });

  test('overlap hit testing prefers selected then smallest canonical box', () {
    const items = [
      ResultOverlayItem(
        objectId: 'object-1',
        displayNumber: 1,
        imageBox: Rect.fromLTRB(10, 10, 90, 90),
        displayName: 'Large',
        isUnknown: false,
      ),
      ResultOverlayItem(
        objectId: 'object-2',
        displayNumber: 2,
        imageBox: Rect.fromLTRB(30, 30, 70, 70),
        displayName: 'Small',
        isUnknown: true,
      ),
    ];
    final transform = ContainedImageTransform(
      imageSize: const Size(100, 100),
      viewportSize: const Size(100, 100),
    );

    expect(
      ResultOverlayHitTester(
        transform: transform,
        items: items,
        selectedObjectId: null,
      ).hitTest(const Offset(50, 50)),
      'object-2',
    );
    expect(
      ResultOverlayHitTester(
        transform: transform,
        items: items,
        selectedObjectId: 'object-1',
      ).hitTest(const Offset(50, 50)),
      'object-1',
    );
  });
}

Future<ByteData> _paintRgba(CustomPainter painter, Size size) async {
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder);
  painter.paint(canvas, size);
  final picture = recorder.endRecording();
  final image = await picture.toImage(size.width.toInt(), size.height.toInt());
  try {
    final bytes = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    return bytes!;
  } finally {
    image.dispose();
    picture.dispose();
  }
}

int _coloredRunWidth(
  ByteData rgba, {
  required int imageWidth,
  required int y,
  required int xStart,
  required int xEnd,
  required Color color,
}) {
  var count = 0;
  final argb = color.toARGB32();
  for (var x = xStart; x <= xEnd; x += 1) {
    final offset = (y * imageWidth + x) * 4;
    if (rgba.getUint8(offset) == (argb >> 16) & 0xff &&
        rgba.getUint8(offset + 1) == (argb >> 8) & 0xff &&
        rgba.getUint8(offset + 2) == argb & 0xff &&
        rgba.getUint8(offset + 3) == (argb >> 24) & 0xff) {
      count += 1;
    }
  }
  return count;
}
