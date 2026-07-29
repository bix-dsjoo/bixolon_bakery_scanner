# Flutter Windows Camera Prototype Design

## Status

Original architecture and revised evaluation-focused UI approved on 2026-07-29.

## Goal

Build a minimal Windows-only Flutter desktop prototype that previews a connected
camera, captures one frame when the operator presses `분석하기`, runs the current
RF-DETR-L plus RepViT/DINOv3 fusion pipeline locally, and displays object boxes,
SKU decisions, counts, Unknown outcomes, three ranked candidates for every
Unknown, and measured latency. The prototype is an evaluation viewer for deciding
whether the pipeline is responsive and legible enough for a bakery POS workflow;
it is not a checkout application.

## Scope

The prototype lives in `apps/bakery_camera_flutter`. It supports Windows desktop
only. It does not stream every camera frame into inference, train models, change
classification policy, convert models to ONNX, or alter detector post-processing.
The detector uses the threshold pinned by
`models/rfdetr_large_bakery_v1/manifest.json`.

The prototype does not provide operator confirmation, manual product correction,
cart management, payment, or historical session analytics. A live camera image
has no ground truth, so the screen must not label confidence or Top-3 output as
accuracy. Accuracy remains a separately measured property of the locked approval
dataset. The live screen exposes the evidence needed to inspect behavior:
locations, decisions, Unknown outcomes, candidates, device, and latency.

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
7. Flutter shows model and camera readiness independently and enables
   `분석하기` only after both are ready.

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
      "object_id": "object-1",
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
    "decode_preprocess": 0.0,
    "detector": 0.0,
    "repvit": 0.0,
    "dinov3": 0.0,
    "postprocess": 0.0,
    "total": 0.0
  }
}
```

Unknown objects use `sku_id: null`, `sku_name: "Unknown"`, preserve exactly
three ranked registered-product candidates, and are not included in
registered-SKU counts. Each candidate has `rank`, `sku_id`, `sku_name`, and
`score`; confirmed objects use an empty `top3` array.
`object_id` is unique within one result and deterministically follows the
top-to-bottom, left-to-right sorted object order so the result rail can highlight
the corresponding overlay without using floating-point coordinates as identity.
Every response preserves bounding boxes in the captured image's
EXIF-transposed visual coordinate frame.

The worker's `timings_ms.total` measures canonical image load through final
aggregation and excludes application startup, model loading, and warm-up.
Flutter separately measures capture time and `분석하기` press-to-rendered-result
latency. The screen shows press-to-result as the POS-facing headline and worker
total plus stage timings as diagnostic detail. Conditional DINOv3 time is zero
when no object invokes it.

During one request, the worker emits request-correlated `progress` events for
`detecting`, `classifying`, conditional `rechecking`, and `aggregating`. Flutter
owns the preceding `capturing` phase. Progress messages are factual pipeline
states rather than a simulated percentage.

The worker also supports `ping` and `shutdown`. Malformed input produces an
`error` response without terminating the process. A model-integrity or model-load
failure produces a fatal error and disables analysis.

## User Interface

### Product principle adaptation

The interface adapts, rather than visually copies, principles documented by the
official Toss development blog:

- **One thing per one page:** the only primary task is capturing and inspecting
  one analysis. Cart, payment, correction, history, charts, and configuration
  stay out of the scanner screen.
- **Easy to answer:** actions state their outcome: `분석하기`, `다시 촬영`, and
  `카메라 다시 연결`. The operator never chooses between technical pipeline
  modes.
- **Visible waiting:** the screen always names the current startup or request
  phase and shows elapsed time. It never presents a motionless screen while the
  worker is busy.
- **Real counter context:** the preview and decision evidence dominate. Decorative
  animation, dense dashboard chrome, and interactions that resemble clickable
  elements without being actionable are excluded.
- **Patterned states and accessibility:** loading, ready, result, Unknown, and
  failure states use consistent components, keyboard focus, semantic labels,
  scalable text, and minimum 44-pixel targets.

References:

- https://toss.tech/article/design-motivation
- https://toss.tech/article/insurance-claim-process
- https://toss.tech/article/tablecenter
- https://toss.tech/article/34897
- https://toss.tech/article/toss-design-system

### Visual direction

The initial window is `1280x820` and remains usable at `1024x720`. It resembles
a calm inspection instrument for a bright bakery counter, not a generic dark
analytics dashboard:

- `Counter Canvas` `#EEF1F4` surrounds the workspace;
- `Camera Ink` `#111417` frames the image without competing with it;
- `Result Paper` `#FFFFFF` forms the receipt-like result rail;
- `Action Blue` `#176BFF` is reserved for the primary action and focus;
- `Confirmed Teal` `#0E8A72` identifies registered decisions;
- `Unknown Amber` `#C76B00` identifies review-required results;
- `Failure Red` `#C43A3A` is reserved for actionable failures.

Use `Segoe UI Variable` with `Malgun Gothic` fallback. Numeric latency and
confidence values use tabular figures. There are no gradients, glass effects, or
continuous ambient animations. The single signature element is the result rail:
it reads like a clean POS receipt aligned with the boxed objects rather than a
collection of dashboard cards.

### Layout and information hierarchy

- A quiet top strip shows camera readiness, model readiness, selected `GPU` or
  `CPU`, and model/policy identity behind an optional details disclosure.
- The left 70 percent is the dominant live camera preview. After analysis it
  freezes the exact captured image and draws coordinate-correct labeled boxes.
- The right rail begins with the scan headline:
  `총 8개 · 412 ms · GPU`. This is followed by SKU counts and then the object
  list.
- Confirmed rows show product name, confidence, and decision path.
- Unknown rows are amber, explicitly say `Unknown`, and always expand the three
  candidates as rank, product name, and score. They are never added to registered
  SKU counts.
- The bottom action area contains one full-width `분석하기` button in live mode
  or one full-width `다시 촬영` button in result mode. Diagnostic details remain
  secondary and never compete with the primary action.

While analyzing, the captured image remains visible and a restrained status line
advances through `이미지 촬영 중`, `빵 위치 찾는 중`, `품목 확인 중`,
`DINOv3 재확인 중` when invoked, and `결과 정리 중`. Elapsed press-to-result
time remains visible. The button is single-flight and disabled until the matching
result or error arrives.

The result timing disclosure contains:

- `버튼→화면 표시`: Flutter press-to-rendered-result time;
- `촬영`: still-capture time;
- `전체 추론`: worker canonical-load-to-aggregation time;
- `전처리`, `Detector`, `RepViT`, conditional `DINOv3`, and `후처리`;
- startup model load and warm-up times in a separate `모델 정보` disclosure,
  never mixed into per-image inference.

Overlay geometry uses the exact rendered `BoxFit.contain` rectangle, including
letterbox offsets, so captured-image coordinates do not drift on window resize.
Selecting an object row highlights only the corresponding box; this is inspection
navigation and does not alter the result.

### Failure and empty states

- No camera: `카메라를 찾지 못했습니다` with `카메라 다시 연결`.
- Worker loading: `모델을 준비하고 있습니다` with the current load or warm-up
  phase and elapsed time.
- Worker fatal: `모델을 준비하지 못했습니다` with a collapsed diagnostic
  disclosure; `분석하기` remains disabled.
- Capture failure: `이미지를 촬영하지 못했습니다` with `다시 촬영`.
- No detected objects: `감지된 빵이 없습니다` with the captured image and
  timing retained. It is not presented as an application error.

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
- progress-event request correlation and legal phase ordering;
- worker model-state transitions and GPU-to-CPU initialization fallback;
- SHA-256 failure preventing readiness;
- single-flight analysis state;
- overlay coordinate mapping with letterboxing and window resize;
- registered SKU aggregation and separate Unknown counts;
- exactly three ranked candidates for every Unknown;
- uniqueness and deterministic ordering of result `object_id` values;
- separation of startup/warm-up, worker inference, capture, and
  press-to-rendered-result timing;
- keyboard focus, semantic action labels, minimum target size, and `1024x720`
  overflow behavior.

Integration tests use a fake camera capture and fake worker process. A local
Windows smoke test uses the real camera and current models and records:

- camera preview and still-capture success;
- model load and warm-up times;
- selected device;
- two consecutive analyses without model reload;
- capture, worker-stage, worker-total, and press-to-result latency;
- visual agreement between returned boxes and the captured image.

The prototype is accepted when the second analysis reuses the loaded models,
GPU is selected on the RTX 5080 PC, CPU fallback can complete the same request,
and the displayed SKU/count/location/confidence/path values match the worker
response exactly. A scripted warm run of at least 20 analyses on one fixed
captured image records p50 and p95 worker-total latency without model reload; a
separate real-camera smoke confirms the full press-to-result path. These values
inform POS suitability but do not replace locked-dataset accuracy evaluation.
