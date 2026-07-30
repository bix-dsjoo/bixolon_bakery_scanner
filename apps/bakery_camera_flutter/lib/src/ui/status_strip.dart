import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';

final class StatusStrip extends StatelessWidget {
  const StatusStrip({
    super.key,
    required this.state,
    required this.startupElapsedMs,
    required this.onReconnectCamera,
  });

  final ScannerState state;
  final double startupElapsedMs;
  final VoidCallback? onReconnectCamera;

  @override
  Widget build(BuildContext context) {
    final workerReady = state.workerStatus == WorkerStatus.ready;
    final workerFatal = state.workerStatus == WorkerStatus.fatal;
    final cameraFailure = !state.cameraReady && state.cameraError != null;
    return DecoratedBox(
      key: const Key('bixolon-header'),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(
            color: bixolonDivider,
            width: bixolonControlBorderWidth,
          ),
        ),
      ),
      child: Semantics(
        container: true,
        label: 'Bakery AI Scanner · 카메라와 모델 상태',
        child: SizedBox(
          height: 60,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final showProductTitle = constraints.maxWidth >= 1180;
              final horizontalPadding = showProductTitle ? 24.0 : 16.0;
              final statusGap = showProductTitle ? 16.0 : 12.0;
              return Padding(
                padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
                child: Row(
                  children: [
                    const BixolonWordmark(),
                    if (showProductTitle) ...[
                      const SizedBox(width: 18),
                      Container(width: 1, height: 24, color: bixolonDivider),
                      const SizedBox(width: 18),
                      Text(
                        'Bakery AI Scanner',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(
                              color: bixolonInk,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                    ],
                    const Spacer(),
                    _StatusDot(
                      label: state.cameraReady
                          ? '카메라 연결됨'
                          : cameraFailure
                          ? '카메라 연결 안 됨'
                          : '카메라 연결 중',
                      color: state.cameraReady
                          ? bixolonOrange
                          : cameraFailure
                          ? failureRed
                          : bixolonMutedInk,
                    ),
                    SizedBox(width: statusGap),
                    _StatusDot(
                      label: workerReady
                          ? '모델 준비됨'
                          : workerFatal
                          ? '모델 준비 실패'
                          : '모델 준비 중 · ${startupElapsedMs.round()} ms',
                      color: workerReady
                          ? bixolonOrange
                          : workerFatal
                          ? failureRed
                          : bixolonMutedInk,
                    ),
                    if (state.device != null) ...[
                      SizedBox(width: statusGap),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          border: Border.all(color: bixolonDivider),
                          borderRadius: BorderRadius.circular(
                            bixolonControlRadius,
                          ),
                        ),
                        child: Text(
                          _deviceLabel(state.device!),
                          style: const TextStyle(
                            fontSize: 12,
                            fontFeatures: tabularFigures,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                    if (cameraFailure) ...[
                      const SizedBox(width: 8),
                      TextButton(
                        onPressed: onReconnectCamera,
                        child: const Text('카메라 다시 연결'),
                      ),
                    ],
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

final class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      BixolonStatusDot(label: label, color: color),
      const SizedBox(width: 7),
      Text(label, style: Theme.of(context).textTheme.bodyMedium),
    ],
  );
}

String _deviceLabel(String device) =>
    device.toLowerCase().startsWith('cuda') ? 'GPU' : 'CPU';
