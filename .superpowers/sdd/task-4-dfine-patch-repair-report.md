# Task 4 D-FINE OOF patch repair report

## Scope

- Replaced `third_party_patches/dfine_oof_predictions.patch` with a context-rich
  patch for pinned D-FINE `7fe2f8889f0b7b817f20c315b40fc15a4fb64ae6`.
- Repaired the generated `third_party/D-FINE` checkout with `apply_patch` only.
  Its prior checkout had six identical OOF blocks appended after `evaluate`'s
  return statement, causing the observed `IndentationError`.
- Added a regression test for zero-context hunks, single OOF initialization,
  batch-result placement, distributed gathering, and export before the
  evaluation metrics/return path.

## TDD evidence

### RED

```text
python -m pytest tests/test_dfine.py::test_dfine_oof_patch_is_context_rich_and_exports_once_before_evaluate_return -q
FAILED tests/test_dfine.py::test_dfine_oof_patch_is_context_rich_and_exports_once_before_evaluate_return
AssertionError: '@@ -8,0' is contained in the old patch
1 failed
```

### GREEN

```text
git -C third_party/D-FINE apply --check ../../third_party_patches/dfine_oof_predictions.patch
forward_check=0
git -C third_party/D-FINE apply ../../third_party_patches/dfine_oof_predictions.patch
apply=0
python -m py_compile third_party/D-FINE/src/solver/det_engine.py
compile=0
git -C third_party/D-FINE apply --reverse --check ../../third_party_patches/dfine_oof_predictions.patch
reverse_check=0
python -m pytest tests/test_dfine.py::test_dfine_oof_patch_is_context_rich_and_exports_once_before_evaluate_return -q
1 passed
```

The forward check occurred only after the checkout was restored to the pinned
source form; it proves the replacement patch applies once. On the resulting
patched checkout, `git apply --reverse --check` succeeds and a second forward
check fails, proving the bootstrap's reverse probe recognizes the applied
state and cannot append another block.

## Focused verification

```text
python -m pytest tests/test_dfine.py -q
10 passed in 0.27s

git -C third_party/D-FINE diff --check
exit 0

python -m py_compile third_party/D-FINE/src/solver/det_engine.py
exit 0
```

`python -m pytest -q` was intentionally not used as a completion gate: it
collects vendored `third_party` suites (including pre-existing
`D-FINE-clean`, `D-FINE-inspect`, `mmdeploy`, and `mmdetection` checkouts) in
the root Python environment. It stopped at collection with missing unrelated
packages such as `tensorboard`, `mmengine`, and `onnx` (246 collection errors).
The project-owned `tests/test_dfine.py` suite above is the relevant scope and
passes.
