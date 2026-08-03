# Final Remediation 2 Report

## Implemented boundaries

- CUDA GPU diagnostics now use active-stream CUDA Event pairs and NVTX ranges.
  `CudaTimingCollector` defers synchronization until its one request/result
  boundary finalization.  `ClassifierPipeline.infer_many` owns that finalization
  only for standalone CUDA use; the default camera runtime supplies the shared
  collector, records RF-DETR detector timing in it, and owns the single final
  synchronization.  PIL crop, fusion, decode, and postprocess remain host-clock
  diagnostics.  DINO has no events when it is not executed.
- The batch path now takes host crop/fusion/total boundaries without calling
  the synchronizing serial clock helper.  A supplied camera collector is never
  finalized inside the classifier; standalone CUDA batch inference finalizes
  its injected clock exactly once.
- Python result validation now rejects malformed result envelopes and requires
  exact image/device/count/unknown-count/object/presentation/timing/diagnostic
  fields.  Object IDs must be `object-1..N`, boxes must be finite and inside the
  declared image, registered counts and `unknown_count` must exactly agree with
  final objects, and Unknown Top3 evidence follows the Dart-compatible v2
  schema and ordering rules.
- Every `Unknown` object now requires an exact, ranked Top3 regardless of its
  presentation state or retake context.
- On Windows, RF-DETR acquires a kernel share-deny handle before the verified
  digest adjacent to model construction and holds it through the post-load
  digest.  Writes/deletes are denied while the path-based factory runs.  On
  non-Windows, CPU retains adjacent digest validation; CUDA evidence loading
  fails closed because pathname share-deny semantics are unavailable.
- Direct CUDA RF-DETR loading also fails closed before model construction when
  no expected checkpoint digest is supplied.
- Dart `StartupMetrics` now requires the exact 13-key applied-artifact hash
  map emitted by Python and exposes a detached immutable copy. CUDA classifier
  startup binds the classifier config and every declared RepViT/DINO,
  calibration, and fusion-policy path together for the complete model load.
- The transferred CUDA classifier binding remains held through detector/classifier
  preflight, lazy DINO/local-bank loading, and startup synchronization. It
  rehashes and releases only after successful warm-up; failure and close paths
  release handles safely, so normal inference retains no artifact locks.
- RF-DETR's own binding likewise remains held through detector warm-up and
  releases only after final verification. Python startup metrics now require
  the same exact applied-artifact hash map as Dart, including custom backends.
  A shared CUDA timing collector is finalized on classifier failure before the
  error propagates.
- Startup provenance is now copied into an immutable mapping before warm-up,
  and invalid custom provenance fails during the guarded load phase. RF-DETR
  binding acquisition and runner construction release handles on every error.

## Verification

- Focused: `PYTHONPATH=src python -m pytest tests/classification/test_runtime.py tests/test_rfdetr.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py tests/contract/test_repository_policy.py -q`
  - `163 passed`
- Classifier/runtime/worker/receipt/policy: `PYTHONPATH=src python -m pytest tests/classification/test_config.py tests/classification/test_runtime.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py tests/benchmarking/test_gpu_worker_receipt.py tests/contract/test_repository_policy.py -q`
  - `148 passed`
- Full Python: `PYTHONPATH=src python -m pytest -q`
  - `781 passed, 4 skipped, 15 deselected`
- `git diff --check` completed without output.
- Flutter was unavailable, so Dart execution remains unverified. CUDA/artifact
  suites remain unverified where required hardware or external model files are
  absent. No performance receipt, p95 claim, or checkpoint status changed.
