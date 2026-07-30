import 'package:bakery_camera_prototype/src/ui/app_theme.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('evaluator typography follows the compact desktop hierarchy', () {
    final textTheme = buildBakeryTheme().textTheme;

    expect(textTheme.titleLarge?.fontSize, 20);
    expect(textTheme.titleLarge?.fontWeight?.value, 700);
    expect(textTheme.titleMedium?.fontSize, 14);
    expect(textTheme.titleMedium?.fontWeight?.value, 600);
    expect(textTheme.bodyMedium?.fontSize, 13);
    expect(textTheme.bodyMedium?.fontWeight?.value, 400);
    expect(textTheme.labelMedium?.fontSize, 12);
    expect(textTheme.labelMedium?.fontWeight?.value, 500);
  });
}
