# GPU/CPU dual-runtime evaluator EXE design

**Status:** approved design, pending implementation plan  
**Scope:** the existing Windows Flutter evaluator, its bundled Python worker, and
the single offline installer.

## Goal

Ship one evaluator EXE that gives the same risk-controlled bakery inference
contract on both GPU and CPU computers. GPU acceleration is used only after
runtime admission proves its artifacts and numerical behavior are valid. CPU is
the correctness-preserving fallback, not a degraded decision policy.

The RTX 5080 `100 ms` target applies only to the warmed worker from an already
EXIF-transposed RGB frame. It does not apply to camera capture, UI rendering,
file I/O, or JPEG decoding. The app must report those times separately so a
user cannot mistake a core inference measurement for scan-to-result latency.

## Runtime selection

At worker start, evaluate the runtime modes in this order:

1. `gpu_fast_verified`: requires a supported NVIDIA GPU, approved driver and
   runtime versions, verified hashes for every model/engine/policy artifact,
   matching engine bindings, and a committed output-parity receipt for every
   score-affecting accelerated component.
2. `gpu_reference`: uses the verified CUDA/PyTorch reference composition when
   CUDA is available but the fast path is not admitted.
3. `cpu_reference`: uses the existing CPU/FP32 reference composition whenever
   CUDA is unavailable or GPU initialization fails.

An admission failure never changes a calibrated threshold, gate, fusion rule,
or `Unknown` outcome. It only selects a reference mode and records a stable
fallback reason. The known RF-DETR TensorRT export is explicitly excluded from
`gpu_fast_verified` until its output parity is independently accepted.

## Common inference contract

All admitted modes preserve:

- EXIF-transposed RGB as the one canonical frame;
- calibrated RF-DETR threshold and normalized in-bounds canonical boxes;
- complete object processing without a scan-count cap;
- RepViT direct gate, conditional DINO global/local evidence, immutable fusion,
  and fail-closed `Unknown`;
- SKU totals that exclude `Unknown`, deterministic object order, location, and
  provenance.

The worker continues to accept the existing image request protocol. A later
GPU decode implementation may be enabled only through the same parity and
artifact-admission rules; it is not implied by GPU availability.

## Result and UI observability

The worker result and audit receipt add the following fields:

- `execution_device`: `cuda:0` or `cpu`;
- `runtime_mode`: `gpu_fast_verified`, `gpu_reference`, or `cpu_reference`;
- `fallback_reason`: null only for admitted GPU modes, otherwise a stable
  machine-readable reason;
- `scan_to_result_ms`: end-to-end worker timing for the supplied request;
- `inference_ms`: canonical-RGB-frame inference timing.

Flutter presents the selected device and a concise fallback reason. CPU mode is
labelled as correctness-first CPU mode. The 100 ms status is shown only for an
admitted GPU fast path and only for the `inference_ms` scope; it is never shown
for CPU or raw-JPEG scan-to-result timing.

## Failure behavior

- Missing, altered, or mismatched artifacts fail GPU admission.
- An unavailable driver, CUDA error, or model initialization error selects CPU
  reference when it can be initialized; otherwise worker startup fails with a
  diagnostic event.
- A request never silently switches decision policies after a GPU failure.
- A GPU fast-path runtime error aborts that request with a diagnostic error;
  it does not rerun the request through an unverified accelerated component.

## Verification

Tests and release evidence must cover:

1. CPU and admitted GPU modes produce the same result contract and preserve
   `Unknown` on shared deterministic fixtures.
2. Each failed GPU-admission condition chooses the documented reference mode
   and exposes its reason to Flutter.
3. The unvalidated RF-DETR TensorRT engine cannot be selected for automatic
   inference.
4. Flutter decodes and displays the new diagnostics without treating CPU as an
   error.
5. The offline installer contains the worker changes and still passes its
   payload, launch, GPU, forced-CPU, and uninstall checks.

## Non-goals

- This change does not claim raw-JPEG scan-to-result p95 below 100 ms.
- It does not enable the current non-parity RF-DETR TensorRT export.
- It does not modify model thresholds, policies, registered SKUs, or legacy
  portable CPU smoke behavior.
