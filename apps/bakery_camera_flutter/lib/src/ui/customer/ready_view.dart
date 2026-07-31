import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../bixolon_theme_extension.dart';
import '../canonical_camera_preview.dart';
import '../components/bakery_primary_button.dart';
import '../components/checkout_scaffold.dart';

class ReadyView extends StatelessWidget {
  const ReadyView({required this.onScan, this.previewController, super.key});

  final VoidCallback? onScan;
  final CameraController? previewController;

  @override
  Widget build(BuildContext context) {
    final cameraAspectRatio = previewController?.value.aspectRatio;
    final previewAspectRatio =
        cameraAspectRatio != null &&
            cameraAspectRatio.isFinite &&
            cameraAspectRatio > 0
        ? cameraAspectRatio
        : 16 / 9;
    final tokens = BixolonThemeExtension.of(context);

    return CheckoutScaffold(
      title: '셀프 계산',
      scrollable: false,
      primaryAction: BakeryPrimaryButton(
        label: '빵 확인하기',
        onPressed: onScan,
        autofocus: true,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '트레이를 카메라 아래에 맞춰주세요.',
              key: const Key('ready-placement-instruction'),
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Center(
                child: AspectRatio(
                  key: const Key('live-tray-placement-guide'),
                  aspectRatio: previewAspectRatio,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(tokens.surfaceRadius),
                    child: previewController != null
                        ? CanonicalCameraPreview(
                            child: CameraPreview(previewController!),
                          )
                        : const ColoredBox(color: Color(0xFF2B2B2B)),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
