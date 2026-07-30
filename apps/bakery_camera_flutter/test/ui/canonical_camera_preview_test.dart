import 'package:bakery_camera_prototype/src/ui/canonical_camera_preview.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('cancels the camera_windows horizontal mirror', (tester) async {
    await tester.pumpWidget(
      const Directionality(
        textDirection: TextDirection.ltr,
        child: CanonicalCameraPreview(
          platform: TargetPlatform.windows,
          child: SizedBox(key: Key('camera-preview-child')),
        ),
      ),
    );

    final transform = tester.widget<Transform>(
      find.byKey(const Key('canonical-camera-preview-transform')),
    );
    expect(transform.transform.storage[0], -1);
    expect(find.byKey(const Key('camera-preview-child')), findsOneWidget);
  });

  testWidgets('does not transform previews on other platforms', (tester) async {
    await tester.pumpWidget(
      const Directionality(
        textDirection: TextDirection.ltr,
        child: CanonicalCameraPreview(
          platform: TargetPlatform.linux,
          child: SizedBox(key: Key('camera-preview-child')),
        ),
      ),
    );

    expect(
      find.byKey(const Key('canonical-camera-preview-transform')),
      findsNothing,
    );
    expect(find.byKey(const Key('camera-preview-child')), findsOneWidget);
  });
}
