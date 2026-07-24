# Task 4: D-FINE matplotlib bootstrap repair

## Scope

The pinned D-FINE requirements are left unchanged.  The local GPU bootstrap now
installs `matplotlib==3.10.6` into only the D-FINE environment and verifies its
import and version alongside the existing CUDA 12.8 / RTX 5080 checks.

## RED

Command:

```powershell
python -m pytest tests/test_dfine.py::test_bootstrap_installs_and_verifies_pinned_dfine_matplotlib -q
```

Result before the implementation: `1 failed`; the expected failed assertion was
`'"matplotlib==3.10.6"' in bootstrap`.

## GREEN

Commands:

```powershell
python -m pytest tests/test_dfine.py::test_bootstrap_installs_and_verifies_pinned_dfine_matplotlib -q
python -m pytest tests/test_dfine.py tests/test_rtmdet.py tests/test_oof.py -q
```

Results: `1 passed` and `21 passed`, respectively.
