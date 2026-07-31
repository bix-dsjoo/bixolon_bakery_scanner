import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../canonical_camera_preview.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
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
    return CheckoutScaffold(
      title: '셀프 계산',
      scrollable: false,
      primaryAction: BakeryPrimaryButton(
        label: '빵 확인하기',
        onPressed: onScan,
        autofocus: true,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const BakeryStatusBanner(
              status: BakeryStatus.ready,
              title: '빵을 트레이에 올려주세요',
              message: '빵이 겹치지 않도록 펼쳐 놓으면 더 잘 확인할 수 있어요.',
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Center(
                child: AspectRatio(
                  key: const Key('live-tray-placement-guide'),
                  aspectRatio: previewAspectRatio,
                  child: ClipRRect(
                    borderRadius: const BorderRadius.all(Radius.circular(8)),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        if (previewController != null)
                          CanonicalCameraPreview(
                            child: CameraPreview(previewController!),
                          )
                        else
                          const ColoredBox(color: Color(0xFF2B2B2B)),
                        Center(
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: const Color(0xFFFFFFFF),
                                width: 2,
                              ),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const SizedBox(width: 190, height: 120),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            const Text('트레이를 카메라 아래에 맞춰주세요.'),
          ],
        ),
      ),
    );
  }
}
