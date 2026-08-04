# Task 5 report: cross-boundary verification and package handoff

## Scope and implementation

- Added `tests/integration/test_rtx5080_15plus5_gpu.py`.
  `test_production_default_keeps_unverified_rfdetr_engine_out_of_automatic_routing`
  invokes `CameraInferenceRuntime.initialize` without a test admitter, with a
  simulated available CUDA probe and a minimal validated backend. It verifies
  the production default retains `gpu_reference` and
  `rfdetr_engine_parity_missing`.
- Identified the existing hermetic CPU fixture
  `tests/prototype/test_camera_runtime.py::test_analyze_returns_deterministic_fail_closed_result_contract`.
  It asserts stable object order and canonical locations, registered totals
  `{"6": 1, "10": 1}`, and one separately counted `Unknown` object.
- Updated the installer matrix and 1.1.0 release record with the precise
  runtime-mode and latency-scope contract plus local verification limits.
- No production files are part of this task. The integration test uses a
  minimal backend because runtime initialization validates and warms a backend;
  this is test-only plumbing, not a production accessibility seam.

## TDD evidence

1. Initial test harness run failed because its first minimal backend did not
   provide `detector.predict`; the fixture was completed to satisfy the public
   runtime backend contract.
2. With the fixture complete, the safety test passed against the existing
   fail-closed production default.
3. To demonstrate the regression is sensitive to the protected behavior, the
   default admitter was temporarily changed from
   `"rfdetr_engine_parity_missing"` to `None` and the test was run. It failed
   as intended: expected `gpu_reference`, got `gpu_fast_verified`.
4. The production source was restored exactly. Focused verification then
   passed:

   ```text
   $env:PYTHONPATH = (Join-Path (Get-Location) 'src'); python -m pytest tests/integration/test_rtx5080_15plus5_gpu.py tests/integration/test_gpu_batch_parity.py tests/prototype/test_camera_runtime.py -q
   45 passed in 6.71s
   ```

## Complete Python verification

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src'); python -m pytest tests/prototype tests/deployment tests/e2e tests/integration/test_gpu_batch_parity.py -q
325 passed, 9 deselected in 22.68s
```

The specified command does not include the new RTX admission test; it is
covered by the focused result above. The nine deselections are the repository
default excluded markers, so they are unverified rather than passed.

## Installer prerequisite evidence

Read-only checks found only:

```text
python.exe C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe
```

`flutter`, `dart`, and `ISCC.exe` were not on PATH. No verified payload root
or Flutter Windows Release directory was discoverable. Therefore the required
build inputs for `scripts/build_camera_installer.ps1` were absent; the build
was not invoked, no tools were installed or downloaded, and no installer was
written. Flutter/Dart and installer verification remain unavailable.

## Commit

This report is included in commit `docs(release): 이중 런타임 검증 근거 기록`;
the commit identifier is provided in the task handoff because a Git commit
cannot embed its own final hash.

## Self-review

- The unverified RF-DETR TensorRT engine remains outside automatic routing and
  outside the package scope.
- Documentation distinguishes `inference_ms` (warmed canonical-RGB,
  non-decode) from `scan_to_result_ms`; it makes no 100 ms claim for JPEG,
  scan-to-result, or CPU paths.
- `Unknown` remains fail-closed and is excluded from registered SKU totals.
- No external artifacts, models, engines, datasets, raw benchmarks, or
  installer payloads were added.

## Review round 1 fix

- Corrected the External NVIDIA PC checklist: without an accepted RF-DETR
  engine parity receipt, it now requires `cuda:0`, `gpu_reference`, and
  `rfdetr_engine_parity_missing`; it explicitly does not require or enable
  `gpu_fast_verified`.
- Wrapped the production-default safety test's initialized runtime in
  `try`/`finally` and calls `runtime.close()` even though its fake backend is a
  no-op.
- Verification: `$env:PYTHONPATH = (Join-Path (Get-Location) 'src'); python
  -m pytest tests/integration/test_rtx5080_15plus5_gpu.py -q` passed: 1
  passed in 4.71s.
- Commit evidence: `fix(review): GPU 참조 모드 점검 보정` (the task handoff
  provides its immutable commit identifier).

## Review round 2 evidence correction

All Python evidence commands above explicitly set `PYTHONPATH` from the
current PowerShell worktree location, rather than relying on an inherited path
that could resolve the primary checkout. The focused command below was rerun
from `C:\workspace\bixolon_bakery_scanner\.worktrees\dual-runtime-exe`:

```text
$env:PYTHONPATH = (Join-Path (Get-Location) 'src'); python -m pytest tests/integration/test_rtx5080_15plus5_gpu.py tests/integration/test_gpu_batch_parity.py tests/prototype/test_camera_runtime.py -q
45 passed in 7.24s
```
