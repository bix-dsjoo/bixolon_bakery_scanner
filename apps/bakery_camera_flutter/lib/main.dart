import 'dart:io';

import 'package:flutter/material.dart';

import 'src/camera/camera_service.dart';
import 'src/inference/inference_launch_config.dart';
import 'src/inference/inference_worker_client.dart';
import 'src/scanner/scanner_controller.dart';
import 'src/ui/app_theme.dart';
import 'src/ui/scanner_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(BakeryCameraApp(controller: _createController()));
}

ScannerController _createController() {
  final config = InferenceLaunchConfig.fromEnvironment(Platform.environment);
  final worker = InferenceWorkerClient(config: config);
  return ScannerController(
    camera: CameraService(),
    worker: InferenceWorkerSession(worker),
  );
}

final class BakeryCameraApp extends StatelessWidget {
  const BakeryCameraApp({super.key, required this.controller});

  final ScannerController controller;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Bixolon Bakery Scan',
    debugShowCheckedModeBanner: false,
    theme: buildBakeryTheme(),
    home: ScannerScreen(controller: controller),
  );
}
