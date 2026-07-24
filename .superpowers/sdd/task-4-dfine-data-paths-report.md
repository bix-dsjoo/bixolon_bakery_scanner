# Task 4 D-FINE data-path resolution repair report

## Scope

Changed only D-FINE generated-overlay path injection in
`scripts/run_detector_matrix.ps1` and its focused regression coverage in
`tests/test_dfine.py`. RTMDet injection and all GPU/CUDA behavior are
unchanged.

## RED

Added `test_matrix_writes_dfine_include_and_data_paths_relative_to_their_consumers`.
It requires a config-directory-relative POSIX `__include__` path and separate
repository-working-directory-relative POSIX paths for D-FINE's image and COCO
fields. It also renders the overlay, loads it with the pinned D-FINE loader,
checks inherited `HGNetv2`, and resolves the data paths from the repository
root.

Command:

```powershell
python -m pytest tests/test_dfine.py -k matrix_writes_dfine_include_and_data_paths -q
```

Observed expected failure before production change:

```text
assert 'function Convert-ToPosixRepositoryPath' in script
```

The existing script only converted all four values from
`configs/generated/detector-matrix`, producing `../../../artifacts/...` for
data fields that D-FINE subsequently resolves from the repository process
working directory.

## GREEN

Added `Convert-ToPosixRepositoryPath`, which derives a POSIX relative path from
the current repository working directory. D-FINE now uses it only for
`img_folder`, train COCO, and validation COCO. Its `__include__` still uses
`Convert-ToPosixRelativePath $GeneratedConfigRoot`, because D-FINE resolves
includes next to the generated config.

Focused command result:

```text
1 passed, 13 deselected
```

Full D-FINE regression result:

```powershell
python -m pytest tests/test_dfine.py -q
```

```text
14 passed
```

## Resolution evidence

The regression constructs a representative rendered overlay and invokes the
pinned `.venvs/dfine/Scripts/python.exe` loader. It proves the inherited base
contains `DFINE.backbone == 'HGNetv2'`, retains list-form `__include__`, and
checks the rendered data fields resolve from repository root to existing:

- `artifacts/box_system/staged/images/`
- `artifacts/box_system/detectors/dfine_n_640-seed20260724-fold0/fold-data/train.json`
- `artifacts/box_system/detectors/dfine_n_640-seed20260724-fold0/fold-data/validation.json`

The existing no-BOM generated-artifact test remains in the same 14-test D-FINE
suite and passed.
