import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('customer typography follows the production POS hierarchy', () {
    final textTheme = buildBakeryTheme().textTheme;

    expect(textTheme.headlineSmall?.fontSize, 24);
    expect(textTheme.headlineSmall?.fontWeight, FontWeight.w500);
    expect(textTheme.titleLarge?.fontSize, 18);
    expect(textTheme.titleLarge?.fontWeight, FontWeight.w600);
    expect(textTheme.titleMedium?.fontSize, 15);
    expect(textTheme.titleMedium?.fontWeight, FontWeight.w600);
    expect(textTheme.bodyLarge?.fontSize, 14);
    expect(textTheme.bodyLarge?.fontWeight, FontWeight.w500);
    expect(textTheme.bodyMedium?.fontSize, 13);
    expect(textTheme.bodyMedium?.fontWeight, FontWeight.w400);
    expect(textTheme.labelLarge?.fontSize, 16);
    expect(textTheme.labelLarge?.fontWeight, FontWeight.w600);
    expect(textTheme.labelMedium?.fontSize, 12);
    expect(textTheme.labelMedium?.fontWeight, FontWeight.w500);
  });
}
