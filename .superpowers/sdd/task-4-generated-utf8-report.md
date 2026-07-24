# Task 4 generated training-file UTF-8 report

## Scope

Repaired only `scripts/run_detector_matrix.ps1` output encoding. Generated
fold train/validation COCO JSON, generated D-FINE/RTMDet configs, and run
receipts now use one Windows PowerShell 5-compatible UTF-8-without-BOM writer.
GPU-only checks, model commands, data split logic, and artifact contents are
unchanged.

## TDD evidence

RED, before the production helper existed:

```text
python -m pytest tests/test_dfine.py::test_matrix_generated_artifacts_use_a_reusable_utf8_without_bom_writer -q
FAILED: matrix script needs a reusable Write-Utf8NoBom helper
1 failed
```

GREEN, after adding `Write-Utf8NoBom` with
`System.Text.UTF8Encoding($false)` and routing all four artifact types through
it:

```text
python -m pytest tests/test_dfine.py::test_matrix_generated_artifacts_use_a_reusable_utf8_without_bom_writer -q
1 passed

python -m pytest tests/test_dfine.py -q
13 passed
```

The focused test extracts and invokes the real PowerShell helper. Its smoke
script writes a Korean JSON sample, reads its actual bytes, and fails if the
first three bytes are `EF BB BF`. The smoke passed.

## Suite note

`python -m pytest -q` is not a repository-suite command: it recursively
collects vendored D-FINE/MMDetection/MMDeploy upstream tests and fails during
collection because their optional upstream dependencies are intentionally not
installed in the project interpreter. `python -m pytest tests -q` was started
for the project suite but exceeded the 120-second command limit while existing
unrelated image/preprocessing work continued; it was not treated as a passing
result. The directly affected test module is green.
