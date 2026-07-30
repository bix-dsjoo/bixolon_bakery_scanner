import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

const confirmedTeal = Color(0xFF0E8A72);
const unknownAmber = Color(0xFFC76B00);

String overlayLabel(ResultOverlayItem item) =>
    '${item.displayNumber.toString().padLeft(2, '0')}  ${item.statusLabel}';

@immutable
final class ContainedImageTransform {
  ContainedImageTransform({required this.imageSize, required this.viewportSize})
    : assert(imageSize.width > 0 && imageSize.height > 0),
      assert(viewportSize.width > 0 && viewportSize.height > 0),
      scale = math.min(
        viewportSize.width / imageSize.width,
        viewportSize.height / imageSize.height,
      ) {
    if (!_isFinitePositiveSize(imageSize) ||
        !_isFinitePositiveSize(viewportSize)) {
      throw ArgumentError(
        'image and viewport sizes must be finite and positive',
      );
    }
  }

  final Size imageSize;
  final Size viewportSize;
  final double scale;

  Rect get imageRect {
    final displayedSize = Size(
      imageSize.width * scale,
      imageSize.height * scale,
    );
    final offset = Offset(
      (viewportSize.width - displayedSize.width) / 2,
      (viewportSize.height - displayedSize.height) / 2,
    );
    return offset & displayedSize;
  }

  Rect mapBox(Rect imageBox) {
    if (!imageBox.left.isFinite ||
        !imageBox.top.isFinite ||
        !imageBox.right.isFinite ||
        !imageBox.bottom.isFinite) {
      throw ArgumentError.value(imageBox, 'imageBox', 'must be finite');
    }
    if (imageBox.left > imageBox.right || imageBox.top > imageBox.bottom) {
      throw ArgumentError.value(
        imageBox,
        'imageBox',
        'must use left/top/right/bottom ordering',
      );
    }

    final clipped = Rect.fromLTRB(
      imageBox.left.clamp(0.0, imageSize.width),
      imageBox.top.clamp(0.0, imageSize.height),
      imageBox.right.clamp(0.0, imageSize.width),
      imageBox.bottom.clamp(0.0, imageSize.height),
    );
    final origin = imageRect.topLeft;
    return Rect.fromLTRB(
      origin.dx + clipped.left * scale,
      origin.dy + clipped.top * scale,
      origin.dx + clipped.right * scale,
      origin.dy + clipped.bottom * scale,
    );
  }

  static bool _isFinitePositiveSize(Size size) =>
      size.width.isFinite &&
      size.height.isFinite &&
      size.width > 0 &&
      size.height > 0;
}

@immutable
final class ResultOverlayItem {
  const ResultOverlayItem({
    required this.objectId,
    required this.displayNumber,
    required this.imageBox,
    required this.displayName,
    required this.isUnknown,
    this.isRetake = false,
    String? statusLabel,
  }) : statusLabel = statusLabel ?? displayName;

  final String objectId;
  final int displayNumber;
  final Rect imageBox;
  final String displayName;
  final bool isUnknown;
  final bool isRetake;
  final String statusLabel;

  @override
  bool operator ==(Object other) =>
      other is ResultOverlayItem &&
      objectId == other.objectId &&
      displayNumber == other.displayNumber &&
      imageBox == other.imageBox &&
      displayName == other.displayName &&
      isUnknown == other.isUnknown &&
      isRetake == other.isRetake &&
      statusLabel == other.statusLabel;

  @override
  int get hashCode => Object.hash(
    objectId,
    displayNumber,
    imageBox,
    displayName,
    isUnknown,
    isRetake,
    statusLabel,
  );
}

final class ResultOverlayHitTester {
  const ResultOverlayHitTester({
    required this.transform,
    required this.items,
    required this.selectedObjectId,
  });

  final ContainedImageTransform transform;
  final List<ResultOverlayItem> items;
  final String? selectedObjectId;

  String? hitTest(Offset viewportPoint) {
    final matches = [
      for (final item in items)
        if (transform.mapBox(item.imageBox).contains(viewportPoint)) item,
    ];
    if (matches.isEmpty) {
      return null;
    }
    matches.sort((a, b) {
      final aSelected = a.objectId == selectedObjectId;
      final bSelected = b.objectId == selectedObjectId;
      if (aSelected != bSelected) {
        return aSelected ? -1 : 1;
      }
      final aArea = a.imageBox.width * a.imageBox.height;
      final bArea = b.imageBox.width * b.imageBox.height;
      final areaOrder = aArea.compareTo(bArea);
      if (areaOrder != 0) {
        return areaOrder;
      }
      return a.displayNumber.compareTo(b.displayNumber);
    });
    return matches.first.objectId;
  }
}

final class ResultOverlayPainter extends CustomPainter {
  const ResultOverlayPainter({
    required this.transform,
    required this.items,
    required this.selectedObjectId,
  });

  final ContainedImageTransform transform;
  final List<ResultOverlayItem> items;
  final String? selectedObjectId;

  @override
  void paint(Canvas canvas, Size size) {
    final viewportBounds = Offset.zero & size;
    final visibleImageBounds = transform.imageRect.intersect(viewportBounds);
    if (visibleImageBounds.isEmpty) {
      return;
    }

    canvas.save();
    canvas.clipRect(visibleImageBounds);
    final paintItems = [
      ...items.where((item) => item.objectId != selectedObjectId),
      ...items.where((item) => item.objectId == selectedObjectId),
    ];
    for (final item in paintItems) {
      final box = transform.mapBox(item.imageBox).intersect(visibleImageBounds);
      if (box.isEmpty) {
        continue;
      }
      final color = item.isRetake || item.isUnknown
          ? unknownAmber
          : confirmedTeal;
      final selected = item.objectId == selectedObjectId;
      canvas.drawRect(
        box,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..isAntiAlias = false
          ..strokeWidth = selected ? 3 : 1.5,
      );
      _paintLabel(
        canvas,
        visibleImageBounds: visibleImageBounds,
        box: box,
        label: overlayLabel(item),
        color: color,
      );
    }
    canvas.restore();
  }

  static void _paintLabel(
    Canvas canvas, {
    required Rect visibleImageBounds,
    required Rect box,
    required String label,
    required Color color,
  }) {
    const horizontalPadding = 8.0;
    const verticalPadding = 4.0;
    const edgeGap = 4.0;
    final availableWidth = math.max(
      0.0,
      math.min(180.0, visibleImageBounds.width - edgeGap * 2),
    );
    if (availableWidth <= horizontalPadding * 2) {
      return;
    }

    final textPainter = TextPainter(
      text: TextSpan(
        text: label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
      maxLines: 1,
      ellipsis: '…',
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: availableWidth - horizontalPadding * 2);

    final labelSize = Size(
      textPainter.width + horizontalPadding * 2,
      textPainter.height + verticalPadding * 2,
    );
    if (labelSize.height + edgeGap * 2 > visibleImageBounds.height) {
      return;
    }
    final minX = visibleImageBounds.left + edgeGap;
    final maxX = math.max(
      minX,
      visibleImageBounds.right - edgeGap - labelSize.width,
    );
    final x = box.left.clamp(minX, maxX).toDouble();
    final aboveY = box.top - edgeGap - labelSize.height;
    final minY = visibleImageBounds.top + edgeGap;
    final maxY = math.max(
      minY,
      visibleImageBounds.bottom - edgeGap - labelSize.height,
    );
    final y = (aboveY >= minY ? aboveY : box.top + edgeGap)
        .clamp(minY, maxY)
        .toDouble();
    final labelRect = Offset(x, y) & labelSize;

    canvas.drawRRect(
      RRect.fromRectAndRadius(labelRect, const Radius.circular(4)),
      Paint()..color = color,
    );
    textPainter.paint(
      canvas,
      labelRect.topLeft + const Offset(horizontalPadding, verticalPadding),
    );
  }

  @override
  bool shouldRepaint(covariant ResultOverlayPainter oldDelegate) =>
      oldDelegate.transform.imageSize != transform.imageSize ||
      oldDelegate.transform.viewportSize != transform.viewportSize ||
      !listEquals(oldDelegate.items, items) ||
      oldDelegate.selectedObjectId != selectedObjectId;
}
