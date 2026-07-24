# Task 4 D-FINE Windows YAML path repair report

## Scope

Only the D-FINE generated YAML overlay path contract changed. RTMDet keeps its
existing raw Windows absolute-path injection branch. GPU configuration, model
parameters, and fold selection were not changed.

## RED

Before the repair, this focused regression failed as expected:

```text
py -3.11 -m pytest tests\\test_dfine.py -k "matrix_writes_dfine_include" -q
FAILED: expected '__include__:\\n  - __INJECTED_DFINE_BASE__'
```

The old scalar `__include__: C:\\...` is iterated by pinned D-FINE
`yaml_utils.load_config` character-by-character. The regression explicitly
loads that scalar form and records the resulting missing path ending in
`detector-matrix\\\\C`.

## GREEN

- Changed the D-FINE template include to a YAML list.
- Added a Windows PowerShell 5-compatible URI relative-path helper which
  produces forward-slash paths from `configs/generated/detector-matrix`.
- Applied that helper only in the D-FINE injection branch; RTMDet still uses
  its existing `Resolve-Path` Windows-path injection branch.

Focused verification:

```text
py -3.11 -m pytest tests\\test_dfine.py -q
14 passed in 10.28s
```

`git diff --check` passed and PowerShell parsed `scripts/run_detector_matrix.ps1`
without syntax errors.

## Real pinned-loader evidence

The regression extracts the actual matrix-script helper, generates a
representative D-FINE overlay, and loads it via the pinned checkout's
`src.core.yaml_utils.load_config` in `.venvs/dfine`.

It confirms all of the following:

- the inherited base resolves (`DFINE.backbone == 'HGNetv2'`), rather than an
  attempted `.../C` include;
- staged image, train fold JSON, and validation fold JSON are forward-slash
  relative paths from the generated config directory;
- `__include__` is a list;
- the scalar Windows absolute-path control fails at `detector-matrix\\\\C`.

## Broader test note

`py -3.11 -m pytest -q` was stopped after it recursively collected unowned
third-party D-FINE/MMDeploy/MMDetection suites (246 collection errors from
their missing optional dependencies, e.g. `tensorboard`, `mmengine`, `onnx`).
This is outside this project's test scope; the repository's own `tests/`
suite was started but stopped at the requested 120-second cap. The focused
D-FINE suite above is complete and green.
