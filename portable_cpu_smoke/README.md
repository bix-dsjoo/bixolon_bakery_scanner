# Batch2 CPU functional smoke package

This package runs a fixed, functional CPU smoke check on Windows 10 or 11. It
requires a network connection during installation and Python 3.11 available as
`py -3.11`. It does not support CUDA.

From the extracted package root, run:

```powershell
.\portable_cpu_smoke\install_cpu_smoke.ps1
.\portable_cpu_smoke\run_batch2_cpu_smoke.ps1
```

The runner creates a timestamped directory below `results`. `report.json`
contains only the average E, M, and H timings. `inference.json` preserves the
full audit fields (objects, boxes, decision paths, provenance, and stage
timings); overlay PNGs are under `overlays`.

The package contains exactly nine fixed Batch2 images: three each from E, M,
and H. It is not a release or accuracy certification. The policy metadata is
rebound solely for this CPU smoke package, and its historical MobileNetV4
assurance model uses the legacy four-state, zero-delta adapter. CPU timings are
not RTX 5080 release metrics.
