import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';
import 'customer_review_presentation.dart';

typedef CustomerReviewImageProviderFactory =
    ImageProvider<Object> Function(File file);

ImageProvider<Object> customerReviewFileImageProvider(File file) =>
    FileImage(file);

/// Shows all recognized objects over the retained capture without altering its
/// aspect ratio, framing, or canonical coordinate system.
class CapturedReviewOverlay extends StatelessWidget {
  const CapturedReviewOverlay({
    required this.imagePath,
    required this.imageWidth,
    required this.imageHeight,
    required this.objects,
    required this.selectedObjectId,
    required this.onSelectObject,
    this.imageProviderFactory = customerReviewFileImageProvider,
    this.objectVisibilityKeys = const {},
    super.key,
  });

  final String imagePath;
  final int imageWidth;
  final int imageHeight;
  final List<CustomerReviewObject> objects;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;
  final Map<String, GlobalKey> objectVisibilityKeys;

  ImageProvider<Object> imageProviderForDisplayPath() =>
      imageProviderFactory(File(imagePath));

  @override
  Widget build(BuildContext context) {
    final safeWidth = imageWidth > 0 ? imageWidth.toDouble() : 1.0;
    final safeHeight = imageHeight > 0 ? imageHeight.toDouble() : 1.0;
    final tokens = BixolonThemeExtension.of(context);
    final selectedObjects = objects
        .where((item) => item.objectId == selectedObjectId)
        .toList(growable: false);
    final paintOrder = [
      for (final item in objects)
        if (item.objectId != selectedObjectId) item,
      ...selectedObjects,
    ];

    return AspectRatio(
      aspectRatio: safeWidth / safeHeight,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(tokens.surfaceRadius),
        child: Stack(
          key: const Key('captured-review-full-scene'),
          fit: StackFit.expand,
          children: [
            Image(
              image: imageProviderForDisplayPath(),
              fit: BoxFit.fill,
              errorBuilder: (_, _, _) => const ColoredBox(
                color: Color(0xFFE9E7E2),
                child: Center(child: Icon(Icons.image_outlined)),
              ),
            ),
            const IgnorePointer(child: ColoredBox(color: Color(0x12000000))),
            LayoutBuilder(
              builder: (context, constraints) => Stack(
                fit: StackFit.expand,
                children: [
                  for (final item in paintOrder)
                    _ObjectOverlay(
                      item: item,
                      selected: item.objectId == selectedObjectId,
                      imageWidth: safeWidth,
                      imageHeight: safeHeight,
                      displayWidth: constraints.maxWidth,
                      displayHeight: constraints.maxHeight,
                      onSelectObject: onSelectObject,
                      visibilityKey: objectVisibilityKeys[item.objectId],
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ObjectOverlay extends StatelessWidget {
  const _ObjectOverlay({
    required this.item,
    required this.selected,
    required this.imageWidth,
    required this.imageHeight,
    required this.displayWidth,
    required this.displayHeight,
    required this.onSelectObject,
    required this.visibilityKey,
  });

  final CustomerReviewObject item;
  final bool selected;
  final double imageWidth;
  final double imageHeight;
  final double displayWidth;
  final double displayHeight;
  final ValueChanged<String> onSelectObject;
  final GlobalKey? visibilityKey;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final color = selected
        ? tokens.action
        : item.state == CustomerReviewObjectState.confirmed
        ? tokens.mutedInk
        : tokens.uncertainty;
    final borderLeft = item.rect.left / imageWidth * displayWidth;
    final borderTop = item.rect.top / imageHeight * displayHeight;
    final borderWidth = item.rect.width / imageWidth * displayWidth;
    final borderHeight = item.rect.height / imageHeight * displayHeight;
    final targetWidth = math.min(displayWidth, math.max(48.0, borderWidth));
    final targetHeight = math.min(displayHeight, math.max(48.0, borderHeight));
    final targetLeft = (borderLeft + borderWidth / 2 - targetWidth / 2)
        .clamp(0.0, math.max(0.0, displayWidth - targetWidth))
        .toDouble();
    final targetTop = (borderTop + borderHeight / 2 - targetHeight / 2)
        .clamp(0.0, math.max(0.0, displayHeight - targetHeight))
        .toDouble();
    final labelMaxWidth = math.min(180.0, displayWidth);
    final labelOnRight = borderLeft + labelMaxWidth <= displayWidth;
    final labelAboveBottom = borderTop + 28 <= displayHeight;
    final selectedSuffix = String.fromCharCodes(const [0xC120, 0xD0DD, 0xB428]);
    final semanticsLabel = selected
        ? '${item.customerSemantics} $selectedSuffix'
        : item.customerSemantics;

    return Positioned.fill(
      child: Stack(
        children: [
          Positioned(
            key: Key('customer-review-border-${item.objectId}'),
            left: borderLeft,
            top: borderTop,
            width: borderWidth,
            height: borderHeight,
            child: IgnorePointer(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  border: Border.all(color: color, width: selected ? 4 : 2),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ),
          Positioned(
            left: labelOnRight ? borderLeft : null,
            right: labelOnRight
                ? null
                : math.max(0.0, displayWidth - borderLeft - borderWidth),
            top: labelAboveBottom ? borderTop : null,
            bottom: labelAboveBottom
                ? null
                : math.max(0.0, displayHeight - borderTop - borderHeight),
            child: IgnorePointer(
              child: Container(
                constraints: BoxConstraints(maxWidth: labelMaxWidth),
                color: color,
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                child: Text(
                  '${item.numberLabel} ${item.label}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ),
          Positioned(
            key: visibilityKey,
            left: targetLeft,
            top: targetTop,
            width: targetWidth,
            height: targetHeight,
            child: Semantics(
              label: semanticsLabel,
              button: true,
              selected: selected,
              excludeSemantics: true,
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  key: Key('customer-review-overlay-${item.objectId}'),
                  onTap: () => onSelectObject(item.objectId),
                  child: const SizedBox.expand(),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
