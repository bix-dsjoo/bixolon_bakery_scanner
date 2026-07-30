import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../scanner/result_overlay.dart' hide confirmedTeal, unknownAmber;
import '../scanner/scanner_controller.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'canonical_camera_preview.dart';
import 'result_rail.dart';
import 'status_strip.dart';

final class ScannerScreen extends StatefulWidget {
  const ScannerScreen({super.key, required this.controller});

  final ScannerController controller;

  @override
  State<ScannerScreen> createState() => _ScannerScreenState();
}

final class _ScannerScreenState extends State<ScannerScreen> {
  final Stopwatch _startupStopwatch = Stopwatch();
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
    _startupStopwatch.start();
    _ticker = Timer.periodic(const Duration(milliseconds: 100), (_) {
      if (mounted) {
        setState(() {});
      }
    });
    unawaited(
      widget.controller.initialize().catchError((Object _) {
        // ScannerController records the actionable failure in its state.
      }),
    );
  }

  @override
  void didUpdateWidget(covariant ScannerScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onControllerChanged);
      widget.controller.addListener(_onControllerChanged);
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    widget.controller.removeListener(_onControllerChanged);
    unawaited(widget.controller.close());
    super.dispose();
  }

  void _onControllerChanged() {
    if (!mounted) {
      return;
    }
    setState(() {});
    if (widget.controller.state.awaitingRenderedResult) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          widget.controller.acknowledgeResultRendered();
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.controller.state;
    final activeElapsed =
        widget.controller.activePressElapsedMs ??
        state.pressToRenderedResultMs ??
        _startupStopwatch.elapsedMilliseconds.toDouble();
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            StatusStrip(
              state: state,
              startupElapsedMs: _startupStopwatch.elapsedMilliseconds
                  .toDouble(),
              onReconnectCamera: state.isAnalyzing
                  ? null
                  : () => unawaited(widget.controller.reconnectCamera()),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    const paneGap = 12.0;
                    final availableWidth = constraints.maxWidth - paneGap;
                    final resultWidth = availableWidth >= 720
                        ? (availableWidth * 0.36).clamp(
                            360.0,
                            availableWidth * 0.5,
                          )
                        : availableWidth * 0.5;
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(
                          key: const Key('camera-pane'),
                          child: _CameraStage(
                            controller: widget.controller,
                            state: state,
                          ),
                        ),
                        const SizedBox(width: paneGap),
                        SizedBox(
                          key: const Key('result-pane'),
                          width: resultWidth,
                          child: DecoratedBox(
                            key: const Key('result-surface'),
                            decoration: BoxDecoration(
                              color: resultPaper,
                              border: Border.all(
                                color: bixolonDivider,
                                width: bixolonControlBorderWidth,
                              ),
                              borderRadius: BorderRadius.circular(
                                bixolonControlRadius,
                              ),
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(
                                bixolonControlRadius,
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  Expanded(
                                    child: ResultRail(
                                      state: state,
                                      elapsedMs: activeElapsed,
                                      onSelectObject:
                                          widget.controller.selectObject,
                                    ),
                                  ),
                                  DecoratedBox(
                                    decoration: const BoxDecoration(
                                      color: resultPaper,
                                      border: Border(
                                        top: BorderSide(color: bixolonDivider),
                                      ),
                                    ),
                                    child: Padding(
                                      padding: const EdgeInsets.fromLTRB(
                                        16,
                                        12,
                                        16,
                                        16,
                                      ),
                                      child: _PrimaryAction(
                                        state: state,
                                        controller: widget.controller,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

final class _CameraStage extends StatelessWidget {
  const _CameraStage({required this.controller, required this.state});

  final ScannerController controller;
  final ScannerState state;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    key: const Key('camera-surface'),
    decoration: BoxDecoration(
      color: cameraInk,
      border: Border.all(
        color: bixolonDivider,
        width: bixolonControlBorderWidth,
      ),
      borderRadius: BorderRadius.circular(bixolonControlRadius),
    ),
    child: ClipRRect(
      borderRadius: BorderRadius.circular(bixolonControlRadius),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: 38,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                children: [
                  BixolonStatusDot(
                    label: state.cameraReady ? 'Live input' : 'Camera standby',
                    color: state.cameraReady
                        ? bixolonOrange
                        : const Color(0xFF777777),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    state.cameraReady ? 'LIVE INPUT' : 'CAMERA STANDBY',
                    style: const TextStyle(
                      color: Color(0xFFB9B9B9),
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.15,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Expanded(
            child: DecoratedBox(
              key: const Key('camera-viewport'),
              decoration: const BoxDecoration(
                color: Colors.black,
                border: Border(top: BorderSide(color: Color(0xFF2D2D2D))),
              ),
              child: _CameraViewport(controller: controller, state: state),
            ),
          ),
        ],
      ),
    ),
  );
}

final class _CameraViewport extends StatelessWidget {
  const _CameraViewport({required this.controller, required this.state});

  final ScannerController controller;
  final ScannerState state;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final result = state.result;
      final capturedPath = state.capturedImagePath;
      if (capturedPath != null) {
        final transform = result == null
            ? null
            : ContainedImageTransform(
                imageSize: Size(result.imageWidth, result.imageHeight),
                viewportSize: Size(constraints.maxWidth, constraints.maxHeight),
              );
        final overlayItems = result == null
            ? const <ResultOverlayItem>[]
            : [
                for (final entry in result.objects.asMap().entries)
                  ResultOverlayItem(
                    objectId: entry.value.objectId,
                    displayNumber: entry.key + 1,
                    imageBox: Rect.fromLTRB(
                      entry.value.bboxXyxy[0],
                      entry.value.bboxXyxy[1],
                      entry.value.bboxXyxy[2],
                      entry.value.bboxXyxy[3],
                    ),
                    displayName: entry.value.isUnknown
                        ? '알 수 없음'
                        : entry.value.skuName,
                    isUnknown: entry.value.isUnknown,
                  ),
              ];
        return Stack(
          fit: StackFit.expand,
          children: [
            Image.file(
              File(capturedPath),
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) => const _CapturedPlaceholder(),
            ),
            if (result != null && transform != null)
              GestureDetector(
                key: const Key('result-overlay-hit-region'),
                behavior: HitTestBehavior.translucent,
                onTapDown: (details) {
                  final objectId = ResultOverlayHitTester(
                    transform: transform,
                    items: overlayItems,
                    selectedObjectId: state.selectedObjectId,
                  ).hitTest(details.localPosition);
                  if (objectId != null) {
                    controller.selectObject(objectId);
                  }
                },
                child: CustomPaint(
                  painter: ResultOverlayPainter(
                    transform: transform,
                    items: overlayItems,
                    selectedObjectId: state.selectedObjectId,
                  ),
                ),
              ),
          ],
        );
      }
      final preview = controller.previewController;
      if (state.cameraReady && preview != null) {
        return CanonicalCameraPreview(child: CameraPreview(preview));
      }
      return Center(
        child: Text(
          state.cameraReady ? '카메라 준비됨' : '카메라 화면을 기다리고 있습니다',
          style: const TextStyle(color: Color(0xFFB9C0C8)),
        ),
      );
    },
  );
}

final class _CapturedPlaceholder extends StatelessWidget {
  const _CapturedPlaceholder();

  @override
  Widget build(BuildContext context) => const Center(
    child: Icon(Icons.image_outlined, color: Color(0xFF727B85), size: 44),
  );
}

final class _PrimaryAction extends StatelessWidget {
  const _PrimaryAction({required this.state, required this.controller});

  final ScannerState state;
  final ScannerController controller;

  @override
  Widget build(BuildContext context) {
    final isRetake =
        state.capturedImagePath != null ||
        state.result != null ||
        state.analysisError != null;
    final label = isRetake ? '다시 촬영' : '분석하기';
    final enabled = isRetake ? !state.isAnalyzing : state.canAnalyze;
    final onPressed = enabled
        ? () {
            if (isRetake) {
              unawaited(controller.resetCapture());
            } else {
              unawaited(
                controller.analyze().catchError((Object _) {
                  // The controller exposes the actionable failure state.
                }),
              );
            }
          }
        : null;
    return Semantics(
      button: true,
      label: label,
      child: isRetake
          ? OutlinedButton(
              key: const Key('primary-action'),
              style: ButtonStyle(
                minimumSize: const WidgetStatePropertyAll(Size(44, 52)),
                foregroundColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.disabled)
                      ? bixolonMutedInk
                      : cameraInk,
                ),
                backgroundColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.disabled)
                      ? bixolonCanvas
                      : Colors.white,
                ),
                shape: WidgetStatePropertyAll(
                  RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(bixolonControlRadius),
                  ),
                ),
                side: WidgetStateProperty.resolveWith(
                  (states) => BorderSide(
                    color: states.contains(WidgetState.disabled)
                        ? bixolonDivider
                        : states.contains(WidgetState.focused)
                        ? actionBlue
                        : cameraInk,
                    width:
                        !states.contains(WidgetState.disabled) &&
                            states.contains(WidgetState.focused)
                        ? 3
                        : bixolonControlBorderWidth,
                  ),
                ),
              ),
              onPressed: onPressed,
              child: Text(label),
            )
          : FilledButton(
              key: const Key('primary-action'),
              style: Theme.of(context).filledButtonTheme.style?.copyWith(
                backgroundColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.disabled)
                      ? bixolonDivider
                      : bixolonOrange,
                ),
                foregroundColor: WidgetStateProperty.resolveWith(
                  (states) => states.contains(WidgetState.disabled)
                      ? bixolonMutedInk
                      : Colors.white,
                ),
                side: WidgetStateProperty.resolveWith(
                  (states) => BorderSide(
                    color: states.contains(WidgetState.disabled)
                        ? bixolonDivider
                        : states.contains(WidgetState.focused)
                        ? actionBlue
                        : Colors.transparent,
                    width:
                        !states.contains(WidgetState.disabled) &&
                            states.contains(WidgetState.focused)
                        ? 3
                        : 0,
                  ),
                ),
              ),
              onPressed: onPressed,
              child: Text(label),
            ),
    );
  }
}
