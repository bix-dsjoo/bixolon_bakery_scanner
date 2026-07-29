import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import '../scanner/scanner_controller.dart';
import 'app_theme.dart';

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
    return Semantics(
      container: true,
      label: '카메라와 모델 상태',
      child: SizedBox(
        height: 56,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              const Text(
                'BAKERY SCAN',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(width: 24),
              _StatusDot(
                label: state.cameraReady ? '카메라 연결됨' : '카메라 연결 안 됨',
                color: state.cameraReady ? confirmedTeal : failureRed,
              ),
              const SizedBox(width: 18),
              _StatusDot(
                label: workerReady
                    ? '모델 준비됨'
                    : workerFatal
                    ? '모델 준비 실패'
                    : '모델 준비 중 · ${startupElapsedMs.round()} ms',
                color: workerReady
                    ? confirmedTeal
                    : workerFatal
                    ? failureRed
                    : const Color(0xFF7A8490),
              ),
              if (state.device != null) ...[
                const SizedBox(width: 18),
                Text(
                  _deviceLabel(state.device!),
                  style: const TextStyle(
                    fontFeatures: tabularFigures,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const Spacer(),
              if (!state.cameraReady)
                TextButton(
                  onPressed: onReconnectCamera,
                  child: const Text('카메라 다시 연결'),
                ),
            ],
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
      Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 7),
      Text(label, style: Theme.of(context).textTheme.bodyMedium),
    ],
  );
}

String _deviceLabel(String device) =>
    device.toLowerCase().startsWith('cuda') ? 'GPU' : 'CPU';
