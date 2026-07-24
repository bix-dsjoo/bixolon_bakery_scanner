# Task 4 nvcc multi-line output repair report

## Scope

Make the CUDA 12.8 preflight treat the complete `nvcc -V` output as one
string, without changing the existing CUDA path, header/library, RTX 5080, or
GPU-only contracts.

## RED

Added `test_bootstrap_matches_release_in_multiline_nvcc_version_output` to
`tests/test_dfine.py`.  The test supplies a three-line `nvcc -V`-shaped value
whose final line alone contains `release 12.8`, verifies the joined value is
accepted by PowerShell, and requires the bootstrap script to join actual
`nvcc -V` output before applying `-notmatch`.

Command:

```powershell
py -3.11 -m pytest tests/test_dfine.py -k multiline_nvcc -q
```

Observed result before the production change:

```text
FAILED tests/test_dfine.py::test_bootstrap_matches_release_in_multiline_nvcc_version_output
AssertionError: assert '$NvccVersion = (& $Nvcc -V) -join [Environment]::NewLine' in bootstrap
1 failed, 7 deselected
```

## GREEN

Changed only the `nvcc` assignment in `scripts/bootstrap_training.ps1`:

```powershell
$NvccVersion = (& $Nvcc -V) -join [Environment]::NewLine
```

Focused verification:

```powershell
py -3.11 -m pytest tests/test_dfine.py -k multiline_nvcc -q
```

Result:

```text
1 passed, 7 deselected
```

Relevant detector verification:

```powershell
py -3.11 -m pytest tests/test_dfine.py tests/test_rtmdet.py -q
```

Result:

```text
13 passed
```
