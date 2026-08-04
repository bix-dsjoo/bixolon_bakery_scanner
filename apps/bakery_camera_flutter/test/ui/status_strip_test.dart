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

    expect(find.text('CPU ?뺥솗???곗꽑'), findsOneWidget);
    expect(find.text('forced_cpu'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsNothing);
  });
}
