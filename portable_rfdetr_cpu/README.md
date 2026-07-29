# RF-DETR-L + Fusion CPU offline package

This package needs no Python installation, package installation, internet connection, or GPU.

1. Extract the ZIP to a local drive.
2. In PowerShell, run `powershell -ExecutionPolicy Bypass -File .\Verify-Package.ps1`.
3. Run `powershell -ExecutionPolicy Bypass -File .\Run-CPU-Batch2.ps1`.

The nine fixed Batch2 images are evaluated with RF-DETR-L and
`fusion_local_or_global_consensus_margin_v1`.  The report and overlay images are
written to `results\batch2-<timestamp>`.  A product is retained as `Unknown`
unless the configured fusion consensus rule confirms it.
