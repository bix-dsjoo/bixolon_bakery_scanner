import 'package:bakery_camera_prototype/src/inference/inference_models.dart';
import 'package:bakery_camera_prototype/src/scanner/scanner_controller.dart';
import 'package:bakery_camera_prototype/src/ui/status_strip.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows CPU reference as neutral runtime status', (tester) async {
    final state = const ScannerState.initial().copyWith(
      cameraReady: true,
      workerStatus: WorkerStatus.ready,
      device: 'cpu',
      startupMetrics: StartupMetrics(
        device: 'cpu',
        runtimeMode: RuntimeMode.cpuReference,
        loadMs: 12,
        warmupMs: 7,
        fallbackReason: 'forced_cpu',
        detectorId: 'rfdetr_large_bakery_v1',
        repvitId: 'repvit_m1_15plus5_v1',
        dinov3Id: 'dinov3_vits16_15plus5_v1',
        fusionPolicyId: 'fusion_local_or_global_v1',
        detectorThreshold: .42,
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: StatusStrip(
          state: state,
          startupElapsedMs: 0,
          onReconnectCamera: null,
        ),
      ),
    );

    expect(find.text('CPU \uc815\ud655\uc131 \uc6b0\uc120'), findsOneWidget);
    expect(find.text('forced_cpu'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsNothing);
  });

  testWidgets('shows exact GPU runtime labels without narrow-header overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(768, 600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    for (final scenario in [
      (RuntimeMode.gpuFastVerified, null, 'GPU \uac80\uc99d \uac00\uc18d'),
      (RuntimeMode.gpuReference, 'rfdetr_engine_parity_missing', 'GPU \ucc38\uc870 \ubaa8\ub4dc'),
    ]) {
      final state = _readyState(
        device: 'cuda:0',
        runtimeMode: scenario.$1,
        fallbackReason: scenario.$2,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: StatusStrip(
            state: state,
            startupElapsedMs: 0,
            onReconnectCamera: null,
          ),
        ),
      );

      expect(find.text(scenario.$3), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
  });
}

ScannerState _readyState({
  required String device,
  required RuntimeMode runtimeMode,
  required String? fallbackReason,
}) => const ScannerState.initial().copyWith(
  cameraReady: true,
  workerStatus: WorkerStatus.ready,
  device: device,
  startupMetrics: StartupMetrics(
    device: device,
    runtimeMode: runtimeMode,
    loadMs: 12,
    warmupMs: 7,
    fallbackReason: fallbackReason,
    detectorId: 'rfdetr_large_bakery_v1',
    repvitId: 'repvit_m1_15plus5_v1',
    dinov3Id: 'dinov3_vits16_15plus5_v1',
    fusionPolicyId: 'fusion_local_or_global_v1',
    detectorThreshold: .42,
  ),
);
