# Final Remediation Report

## Implemented safeguards

- Grouped benchmarks now copy bytes re-verified against each external manifest
  digest into the run-owned staged snapshot before warm-up. The worker receives
  only those staged paths; receipt rows retain only manifest image IDs/groups/
  SHA-256 values. The existing Windows share-deny staged-tree lock now covers
  those inputs as well, and its pre- and post-worker digest/file-set checks
  fail closed on mutation.
- `RFDetrRunner.load` accepts the manifest checkpoint digest, verifies it
  immediately before construction, and verifies it again after path-based
  construction. The default camera backend supplies that digest and rechecks
  detector calibration after backend construction.
- Python and Dart customer-contract parsers reject non-descending Top3 scores
  and equal-score rankings whose SKU IDs are not ascending. Python now also
  validates the complete emitted object, detector, box, and provenance schema.
- Camera request timing no longer synchronizes CUDA at every timestamp. It
  synchronizes once after all request stages have been enqueued, at the result
  boundary. CPU uses the injected/perf-counter clock unchanged.

## Regression coverage

- external source mutation after staging cannot change the staged worker input;
- RF-DETR checkpoint replacement during model construction is rejected;
- Python and Dart Top3 ordering/tie-break validation;
- malformed registered object schema is rejected by the Python consumer;
- CUDA analysis performs one request-boundary synchronization.

## Verification

- `python -m pytest tests/test_rfdetr.py tests/prototype/test_camera_benchmark.py tests/prototype/test_camera_protocol.py tests/prototype/test_camera_runtime.py -q`
  - `102 passed`
- `python -m pytest`
  - `762 passed, 4 skipped, 15 deselected`
- Flutter was unavailable (`flutter` is not recognized), so Dart test execution
  is unverified. The source and regression test are included.
- Artifact/GPU suites remain unverified where their external artifacts or CUDA
  hardware are unavailable. No performance claim or checkpoint status changed.
