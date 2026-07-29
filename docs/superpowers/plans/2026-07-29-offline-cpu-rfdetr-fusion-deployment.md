# Offline CPU RF-DETR Fusion Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, and package an offline Windows CPU ZIP for the RF-DETR-L plus fusion classifier nine-image evaluation.

**Architecture:** A direct CPU runner will preserve the GPU evaluation's RF-DETR-to-classifier behavior while forcing CPU/FP32. A package builder will place an embedded CPython runtime, all CPU dependencies, source, models, data, launchers, and a SHA-256 manifest in a staging directory before producing an immutable ZIP.

**Tech Stack:** Python 3.11 embedded distribution, CPU PyTorch, RF-DETR, PowerShell, pytest.

## Global Constraints

- The ZIP must run without a preinstalled Python interpreter or network connection.
- The runner must force CPU and use canonical EXIF-corrected RGB coordinates.
- The exact fusion acceptance condition remains local agreement OR high-margin three-model global consensus; all other classifications are `Unknown`.
- The report must use one-to-one IoU 0.50 matching and include Top-1, Top-3, FP, FN, and E/M/H latency means.
- Generated package/report files are not committed; source, manifest templates, and tests are committed.

---

### Task 1: Add a CPU-direct RF-DETR/fusion evaluation runner

**Files:**
- Create: `src/bakery_scanner/e2e/rfdetr_cpu.py`
- Create: `scripts/run_cpu_rfdetr_fusion.py`
- Modify: `tests/test_rfdetr.py`

**Interfaces:**
- Consumes: `RFDetrRunner`, `ClassifierPipeline`, canonical samples, and labeled Batch2 JSONL.
- Produces: `summarize_profiles(rows) -> dict[str, dict[str, float]]` and a JSON-serializable report with detection and classification metrics.

- [ ] **Step 1: Write failing tests**

```python
assert summarize_profiles([{'profile': 'E', 'elapsed_ms': 8.0}, {'profile': 'E', 'elapsed_ms': 12.0}])['E']['mean_ms'] == 10.0
assert match_iou50(predictions, ground_truth).fp == 0
```

- [ ] **Step 2: Run the focused tests and verify they fail because the CPU runner module is absent**

Run: `PYTHONPATH=src pytest tests/test_rfdetr.py -q`

- [ ] **Step 3: Implement the CPU runner and CLI**

```python
def run_batch2_cpu(package_root: Path, output: Path) -> dict[str, object]: ...
```

Force `runtime.device=CPU`, load the RF-DETR calibration threshold from its manifest, evaluate all nine images after warm-up, write report/overlays, and reject a package whose model hashes do not match its manifest.

- [ ] **Step 4: Run the focused tests and a local CPU one-image smoke call**

Run: `PYTHONPATH=src pytest tests/test_rfdetr.py -q`

- [ ] **Step 5: Commit runner and tests**

```bash
git add src/bakery_scanner/e2e/rfdetr_cpu.py scripts/run_cpu_rfdetr_fusion.py tests/test_rfdetr.py
git commit -m "feat: add CPU RF-DETR fusion runner"
```

### Task 2: Add an offline package builder and launchers

**Files:**
- Create: `scripts/build_offline_cpu_rfdetr_package.ps1`
- Create: `portable_rfdetr_cpu/manifest.json`
- Create: `portable_rfdetr_cpu/Run-CPU-Batch2.ps1`
- Create: `portable_rfdetr_cpu/Verify-Package.ps1`
- Modify: `tests/test_rfdetr.py`

**Interfaces:**
- Consumes: a locally staged embedded Python runtime, CPU package directory, model assets, and manifest paths.
- Produces: a ZIP containing `package-manifest.json`, launcher scripts, and all SHA-256-verified contents.

- [ ] **Step 1: Write failing package-layout tests**

```python
manifest = json.loads(Path('portable_rfdetr_cpu/manifest.json').read_text())
assert 'runtime/python/python.exe' in manifest['required_paths']
assert 'scripts/run_cpu_rfdetr_fusion.py' in manifest['required_paths']
```

- [ ] **Step 2: Run the focused test and verify it fails because the offline manifest is absent**

Run: `PYTHONPATH=src pytest tests/test_rfdetr.py -q`

- [ ] **Step 3: Implement package staging, hashing, and offline launchers**

Use a fresh staging directory and refuse an existing output ZIP. Copy only manifest-listed paths; create a canonical SHA-256 manifest; use the embedded `runtime/python/python.exe` in both launchers. `Verify-Package.ps1` must reject missing, extra, or hash-mismatched files.

- [ ] **Step 4: Run tests and build the ZIP**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_offline_cpu_rfdetr_package.ps1 -OutputPath artifacts/portable/bakery-rfdetr-fusion-cpu-offline.zip`

- [ ] **Step 5: Commit source manifest, builder, launchers, and tests**

```bash
git add portable_rfdetr_cpu scripts/build_offline_cpu_rfdetr_package.ps1 tests/test_rfdetr.py
git commit -m "feat: package offline CPU RF-DETR runtime"
```

### Task 3: Verify a fresh offline extraction and record CPU results

**Files:**
- Create: `artifacts/evaluations/rfdetr_cpu_batch2_<timestamp>/report.json`
- Create: `artifacts/portable/bakery-rfdetr-fusion-cpu-offline.zip`

**Interfaces:**
- Consumes: the built ZIP only, extracted into a new directory.
- Produces: actual CPU E/M/H means, Top-1, Top-3, FP, FN, report JSON, and overlays.

- [ ] **Step 1: Extract to a fresh directory and verify hashes without network**

Run: `Expand-Archive ...; powershell -ExecutionPolicy Bypass -File Verify-Package.ps1`

- [ ] **Step 2: Run the nine-image CPU evaluation from the extracted package**

Run: `powershell -ExecutionPolicy Bypass -File Run-CPU-Batch2.ps1`

- [ ] **Step 3: Read the generated report and publish only its measured values**

Report the E/M/H means, Top-1, Top-3, FP, FN, ZIP size, ZIP SHA-256, and output/report location.

## Self-Review

- The plan includes a fully offline runtime, CPU-only execution, integrity verification, actual nine-image results, and fresh-extraction validation.
- No step changes the legacy D-FINE CPU smoke pipeline.
- Every new source interface has a failing test before implementation.
