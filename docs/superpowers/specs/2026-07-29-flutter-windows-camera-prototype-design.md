# Flutter Windows Camera Prototype Design

## Status

Approved on 2026-07-29.

## Goal

Build a minimal Windows-only Flutter desktop prototype that previews a connected
camera, captures one frame when the operator presses `분석`, runs the current
RF-DETR-L plus RepViT/DINOv3 fusion pipeline locally, and displays object boxes,
SKU decisions, counts, Unknown outcomes, and measured inference time.

## Scope

The prototype lives in `apps/bakery_camera_flutter`. It supports Windows desktop
only. It does not stream every camera frame into inference, train models, change
classification policy, convert models to ONNX, or alter detector post-processing.
The detector uses the threshold pinned by
`models/rfdetr_large_bakery_v1/manifest.json`.

The current checkpoint, detector calibration, RepViT checkpoint and prototype
bank, DINOv3 weights and support banks, fusion policy, preprocessing, and
canonical EXIF-transposed RGB coordinate contract remain unchanged.

## Architecture

The Flutter process owns the window, camera preview, capture action, result
overlay, and operator-facing state. A persistent Python subprocess owns model
integrity verification, device selection, model loading, warm-up, inference,
aggregation, and structured logging.

Flutter starts the subprocess once and communicates over UTF-8 JSON Lines using
stdin and stdout. Each line is one complete object. stderr is reserved for
diagnostic logs and never carries protocol messages. This avoids a localhost
port, firewall configuration, and repeated Python/model startup.

## Runtime Lifecycle

On application startup:

1. Flutter enumerates Windows cameras and initializes the first available
   device.
2. Flutter starts the packaged Python executable with the inference worker
   entrypoint and repository/package root.
3. The worker validates all configured SHA-256 values before loading models.
4. The worker tries `cuda:0` when CUDA is available. If CUDA initialization,
   model loading, or warm-up fails, it disposes partial GPU state and performs
   one clean CPU initialization.
5. The worker loads RF-DETR-L, RepViT-M1, and DINOv3 exactly once.
6. The worker performs one warm-up inference using a bundled representative
   image and reports the selected device, load time, warm-up time, model IDs,
   threshold, and policy ID in a `ready` event.
7. Flutter enables `분석` only after both camera and worker are ready.

The initial implementation uses FP32 on both GPU and CPU. FP16 or exported
runtime optimization is outside this prototype because it requires a separate
accuracy regression.

## Inference Protocol

Flutter captures a JPEG to a per-session temporary directory and sends:

```json
{"type":"analyze","request_id":"1","image_path":"C:\\...\\capture.jpg"}
```

The worker returns one response with the same request ID:

```json
{
  "type": "result",
  "request_id": "1",
  "image": {"width": 4284, "height": 5712},
  "device": "cuda:0",
  "objects": [
    {
      "sku_id": 10,
      "sku_name": "Sugar Donut",
      "bbox_xyxy": [100.0, 120.0, 500.0, 620.0],
      "confidence": 0.97,
      "decision_path": "repvit_direct",
      "top3": []
    }
  ],
  "counts": {"10": 1},
  "unknown_count": 0,
  "timings_ms": {
    "capture_to_request": 0.0,
    "detector": 0.0,
    "repvit": 0.0,
    "dinov3": 0.0,
    "total": 0.0
  }
}
```

Unknown objects use `sku_id: null`, `sku_name: "Unknown"`, preserve three ranked
candidates where available, and are not included in registered-SKU counts.
Every response preserves bounding boxes in the captured image's
EXIF-transposed visual coordinate frame.

The worker also supports `ping` and `shutdown`. Malformed input produces an
`error` response without terminating the process. A model-integrity or model-load
failure produces a fatal error and disables analysis.

## User Interface

The window uses a restrained dark industrial style at an initial size of
1280x820:

- top status strip: camera name, model state, selected `GPU` or `CPU`, and most
  recent total inference time;
- left main panel: live camera preview, frozen analyzed capture while results
  are shown, and coordinate-correct object overlays;
- right result panel: SKU totals followed by an object list with confidence,
  decision path, and explicit Unknown entries;
- bottom action area: one large `분석` button and a smaller `다시 촬영` action.

Overlay geometry uses the exact rendered `BoxFit.contain` rectangle, including
letterbox offsets, so captured-image coordinates do not drift on window resize.
Analysis is single-flight: the action is disabled from capture start until the
matching result or error arrives.

## Camera Integration

Use Flutter's `camera` API with the explicit `camera_windows` implementation.
The Windows implementation supports preview and still capture but not image
streaming. This matches the requested press-to-analyze workflow.

The app listens for camera errors and provides `카메라 다시 연결`. If no camera
is available, the UI remains open and the model may continue loading, but
`분석` stays disabled.

## Process and Device Handling

Use `dart:io` `Process.start` directly rather than a shell wrapper. Arguments
are passed as an array, paths are absolute, and no command line is assembled
from user-controlled text.

The worker reports one of `loading`, `warming`, `ready`, or `fatal`. Flutter
keeps a bounded diagnostic log in memory. When the window closes, Flutter sends
`shutdown`, waits briefly for a clean exit, and then terminates only the exact
child process if necessary.

GPU selection is evidence-based:

- choose `cuda:0` only when `torch.cuda.is_available()` is true and a small
  allocation succeeds;
- run the same configured FP32 pipeline on GPU;
- retry initialization once on CPU after any GPU initialization or warm-up
  failure;
- do not switch devices in the middle of a request.

## Packaging

The first prototype is built and validated on the current Windows PC. The app
bundle contains the Flutter release output, inference worker source, configs,
model artifacts, a Python runtime, and a package manifest.

A portable release can use a CUDA-capable PyTorch runtime that falls back to CPU,
or separate GPU and CPU runtime directories selected by the launcher. Runtime
packaging is a follow-up deliverable after local camera and inference validation;
the prototype does not overwrite the existing CPU-only ZIP.

## Verification

Automated tests cover:

- JSON Lines parsing, request ID correlation, and malformed worker output;
- worker model-state transitions and GPU-to-CPU initialization fallback;
- SHA-256 failure preventing readiness;
- single-flight analysis state;
- overlay coordinate mapping with letterboxing and window resize;
- registered SKU aggregation and separate Unknown counts.

Integration tests use a fake camera capture and fake worker process. A local
Windows smoke test uses the real camera and current models and records:

- camera preview and still-capture success;
- model load and warm-up times;
- selected device;
- two consecutive analyses without model reload;
- per-stage and total latency;
- visual agreement between returned boxes and the captured image.

The prototype is accepted when the second analysis reuses the loaded models,
GPU is selected on the RTX 5080 PC, CPU fallback can complete the same request,
and the displayed SKU/count/location/confidence/path values match the worker
response exactly.

