# Windows evaluator installer acceptance matrix

## Release under test

- Product: BIXOLON Bakery AI Evaluator
- Version: 1.0.0
- Architecture: Windows x64
- Distribution: single per-user Inno Setup EXE
- Runtime: CPython 3.11.9, PyTorch 2.13.0+cu130, CUDA 13.0 runtime,
  verified-reference CUDA mode and FP32 CPU-reference fallback
- Signature: unsigned internal application build; installer SHA-256 is the
  transfer integrity check

## Dual-runtime handoff status (2026-08-04)

The worker reports `execution_device`, `runtime_mode`, `fallback_reason`,
`scan_to_result_ms`, and `inference_ms` for every result. `runtime_mode` is
`gpu_fast_verified` only after an artifact-backed RF-DETR TensorRT parity
receipt is verified. The currently unverified engine is not packaged or
automatically routed: CUDA selection remains `gpu_reference` with
`fallback_reason = rfdetr_engine_parity_missing`. No CUDA uses
`cpu_reference` with its recorded fallback reason; an explicit CPU request is
`cpu_reference` with `forced_cpu`.

`inference_ms` is the warmed canonical-RGB inference boundary (non-decode
stages only). `scan_to_result_ms` includes decode and the complete worker
request. Neither field is an acceptance receipt here, and no 100 ms claim
applies to JPEG/scan-to-result or any CPU mode.

| Verification item | Status | Evidence / limitation |
|---|---|---|
| Production fast-path admission | passed | Hermetic CUDA-available fixture selected `gpu_reference` and `rfdetr_engine_parity_missing` without injecting an admitter. |
| CPU order/location and Unknown accounting | passed | `tests/prototype/test_camera_runtime.py::test_analyze_returns_deterministic_fail_closed_result_contract` verifies canonical object order/boxes, registered counts `{"6": 1, "10": 1}`, and `unknown_count = 1`. |
| Python cross-boundary suite | passed | `python -m pytest tests/prototype tests/deployment tests/e2e tests/integration/test_gpu_batch_parity.py -q`: 325 passed, 9 deselected (2026-08-04). |
| Real RTX 5080 / TensorRT parity | unverified | No artifact-backed parity receipt or accepted GPU run was available; exploratory benchmarks are not acceptance evidence. |
| Flutter/Dart tests and Windows release build | unavailable | `flutter` and `dart` were not on PATH. |
| Inno Setup installer build | unavailable | `ISCC.exe`, a verified payload root, and Flutter Windows Release payload were not locally discoverable. No build command was run and no installer was written. |

## Local isolated-install evidence

The local acceptance uses an installer-created directory outside the
repository. It proves installation layout, package-relative startup, bundled
runtime imports, model/policy hashes, GPU selection, forced CPU execution,
two analyses without model reload, and uninstall. It is not represented as a
clean external-PC result.

| Item | Value |
|---|---|
| OS | Microsoft Windows 11 Pro 10.0.26200 (build 26200) |
| CPU | Intel Core Ultra 9 285K, 24 cores / 24 logical processors |
| RAM | 63.6 GiB |
| GPU | NVIDIA GeForce RTX 5080 16,303 MiB |
| NVIDIA driver | 591.86 |
| Camera | ABKO APC925 QHD WEBCAM |
| Installer SHA-256 | `70f0c12d9ecdf689641d73498d642c9a8caef5e69b5e1e4c099c0dd54d4d8c71` |
| Installer size | 1,992,987,457 bytes (1.86 GiB) |
| Installed payload size | 3,719,455,534 bytes (3.46 GiB) |
| GPU ready/load/warm-up | `cuda:0`; 2,239.3 ms / 1,900.4 ms |
| GPU analysis 1/2 | 372.8 ms / 326.2 ms; 3 objects each |
| Forced CPU ready/load/warm-up | `cpu`; 2,354.6 ms / 1,380.8 ms |
| Forced CPU analysis 1/2 | 592.2 ms / 574.2 ms; 3 objects each |
| App launch | Product window responsive; bundled worker child started |
| Uninstall | Exit 0; application directory and Start-menu group removed |

## External CPU-only PC checklist

Use Windows 10/11 x64 with no Python, Flutter, Visual Studio, Git, NVIDIA
driver, or network after the installer is copied.

1. Compare the setup EXE SHA-256 with the distributed `.sha256` file.
2. Install without administrator elevation.
3. Start the evaluator from the Start menu.
4. Confirm the camera preview and `CPU` status.
5. Wait for one model load and warm-up.
6. Run two analyses and confirm the second does not reload models.
7. Confirm numbered boxes, confirmed/알 수 없음 rows, Top-3, decision path,
   model timing, and press-to-render timing.
8. Uninstall and confirm the application directory is removed.
9. Record OS build, CPU, RAM, camera, load/warm-up, both analysis timings,
   and any error/fallback code.

## External NVIDIA PC checklist

Use Windows 10/11 x64 with a CUDA 13-compatible NVIDIA driver and no Python,
Flutter, Visual Studio, or Git.

1. Repeat the CPU checklist.
2. While no accepted RF-DETR engine parity receipt exists, confirm
   `device = cuda:0`, `runtime_mode = gpu_reference`, and
   `fallback_reason = rfdetr_engine_parity_missing`. Do not require or enable
   `gpu_fast_verified` admission.
3. Run at least 20 warm analyses and record worker p50/p95.
4. Record GPU model, driver version, load/warm-up, and two real-camera
   press-to-render timings.

The external rows remain a transfer checklist until measured on the receiving
PC. Local evidence must not be relabeled as clean-PC evidence.
