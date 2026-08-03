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

## Verification

- Focused: `PYTHONPATH=src python -m pytest tests/classification/test_runtime.py tests/test_rfdetr.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py tests/prototype/test_camera_worker.py tests/contract/test_repository_policy.py -q`
  - `163 passed`
- Full Python: `PYTHONPATH=src python -m pytest -q`
  - `777 passed, 4 skipped, 15 deselected`
- `git diff --check` completed without output.
- Flutter was unavailable, so Dart execution remains unverified. CUDA/artifact
  suites remain unverified where required hardware or external model files are
  absent. No performance receipt, p95 claim, or checkpoint status changed.
