import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('customer typography follows the production POS hierarchy', () {
    final textTheme = buildBakeryTheme().textTheme;

    expect(textTheme.headlineSmall?.fontSize, 24);
    expect(textTheme.headlineSmall?.height, 1.35);
    expect(textTheme.headlineSmall?.fontWeight, FontWeight.w500);
    expect(textTheme.headlineSmall?.letterSpacing, 0);
    expect(textTheme.titleLarge?.fontSize, 18);
    expect(textTheme.titleLarge?.height, 1.35);
    expect(textTheme.titleLarge?.fontWeight, FontWeight.w600);
    expect(textTheme.titleLarge?.letterSpacing, 0);
    expect(
      textTheme.titleLarge?.fontFeatures,
      contains(const FontFeature.tabularFigures()),
    );
    expect(textTheme.titleMedium?.fontSize, 15);
    expect(textTheme.titleMedium?.height, 1.35);
    expect(textTheme.titleMedium?.fontWeight, FontWeight.w600);
    expect(textTheme.titleMedium?.letterSpacing, 0);
    expect(textTheme.bodyLarge?.fontSize, 14);
    expect(textTheme.bodyLarge?.height, 1.4);
    expect(textTheme.bodyLarge?.fontWeight, FontWeight.w500);
    expect(textTheme.bodyLarge?.letterSpacing, 0);
    expect(textTheme.bodyMedium?.fontSize, 13);
    expect(textTheme.bodyMedium?.height, 1.35);
    expect(textTheme.bodyMedium?.fontWeight, FontWeight.w400);
    expect(textTheme.bodyMedium?.letterSpacing, 0);
    expect(textTheme.labelLarge?.fontSize, 16);
    expect(textTheme.labelLarge?.height, 1.35);
    expect(textTheme.labelLarge?.fontWeight, FontWeight.w600);
    expect(textTheme.labelLarge?.letterSpacing, 0);
    expect(textTheme.labelMedium?.fontSize, 12);
    expect(textTheme.labelMedium?.height, 1.4);
    expect(textTheme.labelMedium?.fontWeight, FontWeight.w500);
    expect(textTheme.labelMedium?.letterSpacing, 0);
  });
}
