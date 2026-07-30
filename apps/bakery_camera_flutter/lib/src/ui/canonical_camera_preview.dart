import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

/// Restores the captured image's left-to-right orientation on Windows.
///
/// `camera_windows` 0.2.6+4 mirrors its preview texture in software while the
/// still image used for inference is not mirrored. Applying a second horizontal
/// flip keeps the live preview, captured result, and canonical overlay frame
/// aligned.
final class CanonicalCameraPreview extends StatelessWidget {
  const CanonicalCameraPreview({
    super.key,
    required this.child,
    this.platform,
  });

  final Widget child;
  final TargetPlatform? platform;

  @override
  Widget build(BuildContext context) {
    final targetPlatform = platform ?? defaultTargetPlatform;
    if (targetPlatform != TargetPlatform.windows) {
      return child;
    }
    return Transform.flip(
      key: const Key('canonical-camera-preview-transform'),
      flipX: true,
      child: child,
    );
  }
}
