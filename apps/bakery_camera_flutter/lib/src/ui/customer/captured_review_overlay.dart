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
    super.key,
  });

  final String imagePath;
  final int imageWidth;
  final int imageHeight;
  final List<CustomerReviewObject> objects;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;
  final CustomerReviewImageProviderFactory imageProviderFactory;

  ImageProvider<Object> imageProviderForDisplayPath() =>
      imageProviderFactory(File(imagePath));

  @override
  Widget build(BuildContext context) {
    final safeWidth = imageWidth > 0 ? imageWidth.toDouble() : 1.0;
    final safeHeight = imageHeight > 0 ? imageHeight.toDouble() : 1.0;
    final tokens = BixolonThemeExtension.of(context);

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
                  for (final item in objects)
                    _ObjectOverlay(
                      item: item,
                      selected: item.objectId == selectedObjectId,
                      imageWidth: safeWidth,
                      imageHeight: safeHeight,
                      displayWidth: constraints.maxWidth,
                      displayHeight: constraints.maxHeight,
                      onSelectObject: onSelectObject,
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
  });

  final CustomerReviewObject item;
  final bool selected;
  final double imageWidth;
  final double imageHeight;
  final double displayWidth;
  final double displayHeight;
  final ValueChanged<String> onSelectObject;

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final color = selected
        ? tokens.action
        : item.state == CustomerReviewObjectState.confirmed
        ? tokens.mutedInk
        : tokens.uncertainty;
    final width = math.max(48.0, item.rect.width / imageWidth * displayWidth);
    final height = math.max(
      48.0,
      item.rect.height / imageHeight * displayHeight,
    );
    final selectedSuffix = String.fromCharCodes(const [0xC120, 0xD0DD, 0xB428]);
    final semanticsLabel = selected
        ? '${item.customerSemantics} $selectedSuffix'
        : item.customerSemantics;

    return Positioned(
      left: item.rect.left / imageWidth * displayWidth,
      top: item.rect.top / imageHeight * displayHeight,
      width: width,
      height: height,
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
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.14),
                border: Border.all(color: color, width: selected ? 4 : 2),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Align(
                alignment: Alignment.topLeft,
                child: Container(
                  color: color,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 4,
                  ),
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
          ),
        ),
      ),
    );
  }
}
