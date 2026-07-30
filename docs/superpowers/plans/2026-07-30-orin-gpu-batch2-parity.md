# Orin GPU Batch2 Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed Orin GPU runner for the fixed nine Batch2 images and a read-only CPU/GPU report comparator, without changing the CPU pipeline.

**Architecture:** A new `gpu_batch2` module owns runtime admission, environment evidence, GPU-synchronized inference, and atomic publication. A thin GPU CLI calls it. A separate comparator reads the supplied CPU `report.json` and the new GPU report and records latency deltas and decision parity.

**Tech Stack:** Python 3.11, PyTorch `>=2.8,<2.9` compiled with `sm_87`, CUDA, RF-DETR-L, RepViT-M1, DINOv3, Pydantic, pytest, tegrastats.

## Global Constraints

- Do not modify `scripts/run_cpu_rfdetr_fusion.py`, `portable_rfdetr_cpu/`, `portable_cpu_smoke/`, or their existing behavior.
- Use the nine fixed `batch2_e3_m3_h3` images in order, canonical EXIF-transposed RGB frames, and the RF-DETR manifest threshold.
- Keep FP32, serial reference execution, artifact checks, direct gate, conditional DINO global/local evidence, immutable fusion, and fail-closed `Unknown`.
- Admit only Python 3.11, PyTorch `>=2.8,<2.9`, an available Orin CUDA device with capability `(8, 7)`, and a compiled architecture list containing `sm_87`.
- Reject the installed Python 3.12 / PyTorch 2.13 environment before model loading; never fall back to CPU or an unsupported PTX/JIT path.
- CUDA-synchronize immediately before and after warm-up and every measured image. Time detector plus serial classification only.
- The GPU result may be called a speed comparison only when the nine ordered images and all CPU quality/Unknown outcomes have parity.
- Preserve user changes; stage only files named by each task.

---

## File Structure

- Create `src/bakery_scanner/e2e/gpu_batch2.py`: runtime admission, environment receipt, GPU execution, staging/telemetry.
- Create `scripts/run_gpu_rfdetr_fusion.py`: GPU runner CLI.
- Create `scripts/compare_batch2_reports.py`: read-only report comparator.
- Create `tests/e2e/test_gpu_batch2.py`: admission and runner contracts.
- Create `tests/test_compare_batch2_reports.py`: comparator contracts.
- Create `docs/orin-gpu-batch2.md`: target preflight and operator commands.

### Task 1: Implement fail-closed Orin runtime admission

**Files:**
- Create: `src/bakery_scanner/e2e/gpu_batch2.py`
- Create: `tests/e2e/test_gpu_batch2.py`

**Interfaces:**
- Produces `GpuRuntimeEvidence`, `RuntimeAdmissionError`, and `admit_orin_gpu_runtime(*, torch_module=torch) -> GpuRuntimeEvidence`.
- Consumed by `run_gpu_batch2()` in Task 2.

- [ ] **Step 1: Write failing admission tests**

```python
def test_admit_orin_gpu_runtime_returns_sm87_receipt(monkeypatch):
    monkeypatch.setattr("bakery_scanner.e2e.gpu_batch2.sys.version_info", (3, 11, 9, "final", 0))
    evidence = admit_orin_gpu_runtime(torch_module=FakeTorch(
        version="2.8.0", available=True, capability=(8, 7), arches=("sm_87",),
    ))
    assert evidence.compute_capability == (8, 7)
    assert evidence.compiled_arches == ("sm_87",)

@pytest.mark.parametrize("version, available, capability, arches, message", [
    ("2.13.0", True, (8, 7), ("sm_87",), "PyTorch"),
    ("2.8.0", False, (8, 7), ("sm_87",), "CUDA"),
    ("2.8.0", True, (8, 0), ("sm_87",), "compute capability"),
    ("2.8.0", True, (8, 7), ("sm_80",), "sm_87"),
])
def test_admission_rejects_unsupported_runtime(monkeypatch, version, available, capability, arches, message):
    monkeypatch.setattr("bakery_scanner.e2e.gpu_batch2.sys.version_info", (3, 11, 9, "final", 0))
    with pytest.raises(RuntimeAdmissionError, match=message):
        admit_orin_gpu_runtime(torch_module=FakeTorch(version, available, capability, arches))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/e2e/test_gpu_batch2.py -q`

Expected: collection fails because `gpu_batch2` is absent.

- [ ] **Step 3: Implement the admission boundary**

```python
@dataclass(frozen=True, slots=True)
class GpuRuntimeEvidence:
    python_version: str
    torch_version: str
    cuda_version: str
    device_name: str
    compute_capability: tuple[int, int]
    compiled_arches: tuple[str, ...]

class RuntimeAdmissionError(RuntimeError):
    pass

def admit_orin_gpu_runtime(*, torch_module: Any = torch) -> GpuRuntimeEvidence:
    if (sys.version_info.major, sys.version_info.minor) != (3, 11):
        raise RuntimeAdmissionError("GPU Batch2 requires Python 3.11")
    version = Version(str(torch_module.__version__).split("+", 1)[0])
    if not Version("2.8") <= version < Version("2.9"):
        raise RuntimeAdmissionError("GPU Batch2 requires PyTorch >=2.8,<2.9")
    if not torch_module.cuda.is_available():
        raise RuntimeAdmissionError("GPU Batch2 requires CUDA")
    capability = tuple(torch_module.cuda.get_device_capability(0))
    if capability != (8, 7):
        raise RuntimeAdmissionError("GPU Batch2 requires Orin compute capability (8, 7)")
    arches = tuple(str(value) for value in torch_module.cuda.get_arch_list())
    if "sm_87" not in arches:
        raise RuntimeAdmissionError("GPU Batch2 requires an sm_87 PyTorch build")
    return GpuRuntimeEvidence(...)
```

Add `collect_environment()` that returns JSON-safe evidence for the above fields, platform, L4T release when present, `nvpmodel -q` output, and caller-provided artifact hashes.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/e2e/test_gpu_batch2.py -q`

Expected: PASS for the valid receipt and all rejection cases.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- src/bakery_scanner/e2e/gpu_batch2.py tests/e2e/test_gpu_batch2.py
git diff --cached --check
git commit -m "feat: admit supported Orin GPU benchmark runtimes"
```

### Task 2: Implement GPU Batch2 execution and report publication

**Files:**
- Modify: `src/bakery_scanner/e2e/gpu_batch2.py`
- Create: `scripts/run_gpu_rfdetr_fusion.py`
- Modify: `tests/e2e/test_gpu_batch2.py`

**Interfaces:**
- Produces `run_gpu_batch2(package_root: Path, output: Path, *, dependencies: GpuBatch2Dependencies | None = None) -> dict[str, object]`.
- Emits `report.json`, `environment.json`, `tegrastats.log`, and overlays under the requested output.

- [ ] **Step 1: Write failing runner tests**

```python
def test_run_gpu_batch2_publishes_cpu_compatible_report(tmp_path):
    report = run_gpu_batch2(tmp_path, tmp_path / "gpu", dependencies=_dependencies())
    assert report["schema_version"] == 1
    assert report["device"] == "CUDA:0"
    assert [row["profile"] for row in report["images"]] == ["E", "E", "E", "M", "M", "M", "H", "H", "H"]
    assert (tmp_path / "gpu" / "report.json").is_file()
    assert (tmp_path / "gpu" / "environment.json").is_file()
    assert (tmp_path / "gpu" / "tegrastats.log").is_file()

def test_run_gpu_batch2_synchronizes_warmup_and_every_image(tmp_path):
    calls = []
    run_gpu_batch2(tmp_path, tmp_path / "gpu", dependencies=_dependencies(synchronize=lambda: calls.append(None)))
    assert len(calls) == 20

def test_admission_failure_writes_only_environment_receipt(tmp_path):
    with pytest.raises(RuntimeAdmissionError):
        run_gpu_batch2(tmp_path, tmp_path / "gpu", dependencies=_dependencies(admit=_reject))
    assert (tmp_path / "gpu" / "environment.json").is_file()
    assert not (tmp_path / "gpu" / "report.json").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/e2e/test_gpu_batch2.py -q`

Expected: FAIL because `run_gpu_batch2` does not exist.

- [ ] **Step 3: Implement runner dependencies and live composition**

```python
@dataclass(frozen=True, slots=True)
class GpuBatch2Dependencies:
    admit: Callable[[], GpuRuntimeEvidence]
    collect_environment: Callable[[Path, ClassifierConfig, GpuRuntimeEvidence], dict[str, object]]
    load_classifier: Callable[[Path, ClassifierRuntimeConfig], ClassifierPipeline]
    load_detector: Callable[[Path, float], RFDetrRunner]
    load_frame: Callable[[Path], CanonicalImage]
    resolve_images: Callable[[Path], tuple[Path, ...]]
    load_targets: Callable[[Path], dict[str, list[tuple[Box, int]]]]
    synchronize: Callable[[], None]
    start_tegrastats: Callable[[Path], Callable[[], None]]
```

Load `configs/cpu_rfdetr_classifier_policy.yaml`, copy only its runtime with `device="CUDA:0"`, `mode="serial_reference"`, and `compile_models=()`; then load the classifier with `runtime_override`. Load RF-DETR with `device="cuda"` and its manifest threshold.

For the one-image warm-up and every measured image, use:

```python
synchronize()
started = time.perf_counter()
proposals = detector.predict(image_id, frame.image)
decisions = [classifier.infer(frame, proposal.box) for proposal in proposals]
synchronize()
elapsed_ms = (time.perf_counter() - started) * 1000.0
```

Load frames before the timer. Use the same Batch2 resolver, ground-truth JSONL matching, boxes, IoU 0.50, object records, and overlay semantics as the CPU runner. If pure helpers cannot be reused without altering the CPU runner, duplicate only those helpers in this new module.

Start `tegrastats --interval 500 --logfile <staging>/tegrastats.log` through `subprocess.Popen` with no shell. Always terminate and wait for it. Write all output to a UUID staging directory; atomically rename only after the report, receipt, log, and overlays are complete.

The published report must be:

```python
{
    "schema_version": 1,
    "device": "CUDA:0",
    "detector": manifest["source_label"],
    "fusion_policy": classifier.fusion_policy.decision_rule if classifier.fusion_policy else None,
    "iou_threshold": 0.5,
    "profiles": summarize_profiles(rows),
    "metrics": {**totals, "top1_rate": totals["top1"] / totals["gt"], "top3_rate": totals["top3"] / totals["gt"]},
    "images": rows,
}
```

- [ ] **Step 4: Run CPU-preservation and GPU tests**

Run: `python -m pytest tests/e2e/test_gpu_batch2.py tests/test_rfdetr_cpu.py tests/test_package_cpu_smoke.py -q`

Expected: PASS without CPU test expectation changes.

- [ ] **Step 5: Commit Task 2**

```powershell
git add -- src/bakery_scanner/e2e/gpu_batch2.py scripts/run_gpu_rfdetr_fusion.py tests/e2e/test_gpu_batch2.py
git diff --cached --check
git commit -m "feat: run fixed Batch2 inference on supported Orin GPU"
```

### Task 3: Implement read-only CPU/GPU comparator

**Files:**
- Create: `scripts/compare_batch2_reports.py`
- Create: `tests/test_compare_batch2_reports.py`

**Interfaces:**
- Produces `compare_reports(cpu_report: Path, gpu_report: Path, output: Path) -> dict[str, object]`.
- Never modifies its two source reports.

- [ ] **Step 1: Write failing comparator tests**

```python
def test_comparator_records_speedup_and_preserves_inputs(tmp_path):
    cpu_path = _write(tmp_path / "cpu.json", _report("CPU", 2600.0))
    gpu_path = _write(tmp_path / "gpu.json", _report("CUDA:0", 260.0))
    result = compare_reports(cpu_path, gpu_path, tmp_path / "comparison.json")
    assert result["valid_for_speed_comparison"] is True
    assert result["profiles"]["E"]["speedup"] == 10.0
    assert result["images"][0]["cpu_elapsed_ms"] == 2600.0
    assert json.loads(cpu_path.read_text())["device"] == "CPU"

def test_comparator_marks_order_or_quality_change_invalid(tmp_path):
    cpu = _report("CPU", 2600.0)
    gpu = _report("CUDA:0", 260.0)
    gpu["images"][0]["image"] = "wrong.jpg"
    result = compare_reports(_write(tmp_path / "cpu.json", cpu), _write(tmp_path / "gpu.json", gpu), tmp_path / "comparison.json")
    assert result["valid_for_speed_comparison"] is False
    assert any("image order" in reason for reason in result["reasons"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compare_batch2_reports.py -q`

Expected: collection fails because the comparator module is absent.

- [ ] **Step 3: Implement strict parsing and result generation**

Require schema version 1, expected device, exactly nine ordered names, E/M/H profiles, finite positive timings, and integer metrics. Refuse an existing output path.

Always publish a new comparison JSON after valid source parsing:

```python
{
    "schema_version": 1,
    "cpu_report": str(cpu_report.resolve()),
    "gpu_report": str(gpu_report.resolve()),
    "valid_for_speed_comparison": reasons == [],
    "reasons": reasons,
    "quality": {"cpu": cpu["metrics"], "gpu": gpu["metrics"]},
    "profiles": {
        "E": {"cpu_mean_ms": cpu_e, "gpu_mean_ms": gpu_e, "delta_ms": gpu_e - cpu_e, "speedup": cpu_e / gpu_e},
        "M": {"cpu_mean_ms": cpu_m, "gpu_mean_ms": gpu_m, "delta_ms": gpu_m - cpu_m, "speedup": cpu_m / gpu_m},
        "H": {"cpu_mean_ms": cpu_h, "gpu_mean_ms": gpu_h, "delta_ms": gpu_h - cpu_h, "speedup": cpu_h / gpu_h},
    },
    "images": [...],
}
```

Add a reason for each differing aggregate metric and every object-level difference in decision, predicted SKU, ground-truth SKU, or IoU classification.

- [ ] **Step 4: Run comparator tests**

Run: `python -m pytest tests/test_compare_batch2_reports.py -q`

Expected: PASS for valid parity, wrong device, wrong ordering, quality mismatch, and overwrite refusal.

- [ ] **Step 5: Commit Task 3**

```powershell
git add -- scripts/compare_batch2_reports.py tests/test_compare_batch2_reports.py
git diff --cached --check
git commit -m "feat: compare CPU and Orin GPU Batch2 reports"
```

### Task 4: Document operation and validate the target

**Files:**
- Create: `docs/orin-gpu-batch2.md`
- Modify: `tests/e2e/test_gpu_batch2.py`

**Interfaces:**
- Documents the Task 1 preflight, Task 2 runner, and Task 3 comparator.

- [ ] **Step 1: Write a failing guide-contract test**

```python
def test_operator_guide_requires_sm87_preflight_and_report_comparison():
    guide = (ROOT / "docs" / "orin-gpu-batch2.md").read_text(encoding="utf-8")
    assert "torch.cuda.get_arch_list()" in guide
    assert "sm_87" in guide
    assert "scripts/run_gpu_rfdetr_fusion.py" in guide
    assert "scripts/compare_batch2_reports.py" in guide
    assert "tegrastats.log" in guide
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/e2e/test_gpu_batch2.py::test_operator_guide_requires_sm87_preflight_and_report_comparison -q`

Expected: FAIL because the guide is absent.

- [ ] **Step 3: Write exact operator commands**

Include this preflight command and state that the current Python 3.12 / PyTorch 2.13 environment is rejected:

```bash
python -c 'import sys, torch; print(sys.version); print(torch.__version__); print(torch.version.cuda); print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_capability(0)); print(torch.cuda.get_arch_list())'
```

After a passing preflight, include:

```bash
python scripts/run_gpu_rfdetr_fusion.py --package-root /path/to/bixolon_bakery_scanner --output /path/to/orin-gpu-batch2
python scripts/compare_batch2_reports.py --cpu-report /path/to/cpu/report.json --gpu-report /path/to/orin-gpu-batch2/report.json --output /path/to/cpu-gpu-comparison.json
```

Require retaining `report.json`, `environment.json`, `tegrastats.log`, and overlays together. Declare `valid_for_speed_comparison: false` a failed parity run, not a speed result.

- [ ] **Step 4: Run local and target verification**

Run locally:

```powershell
python -m pytest tests/e2e/test_gpu_batch2.py tests/test_compare_batch2_reports.py tests/test_rfdetr_cpu.py tests/test_package_cpu_smoke.py -q
```

Run on the Orin only after Task 1 admission passes:

```bash
python scripts/run_gpu_rfdetr_fusion.py --package-root ~/bixolon_bakery_scanner --output ~/orin-gpu-batch2
python scripts/compare_batch2_reports.py --cpu-report ~/cpu-report.json --gpu-report ~/orin-gpu-batch2/report.json --output ~/cpu-gpu-comparison.json
```

- [ ] **Step 5: Commit Task 4**

```powershell
git add -- docs/orin-gpu-batch2.md tests/e2e/test_gpu_batch2.py
git diff --cached --check
git commit -m "docs: document Orin GPU Batch2 parity operation"
```

## Plan self-review

- Task 1 covers runtime admission and evidence; Task 2 covers same-input GPU execution, telemetry, atomic output, and CPU preservation; Task 3 covers comparison; Task 4 covers reproducible operation.
- No task changes a CPU portable file.
- Task 2 consumes the Task 1 types; Task 3 consumes JSON only, so its interface is independent and testable.
- Every task contains file paths, failing tests, focused commands, exact interfaces, and a commit scope.

