# Batch2 CPU Smoke Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a portable Windows CPU package that runs the real fail-closed E2E pipeline on the fixed Batch2 E/M/H 3/3/3 image profile.

**Architecture:** A profile module owns the exact nine source images and copy validation. `cpu_factory` resolves package-relative, hash-pinned assets and builds a `MobileOnlyE2EPipeline` from a warm D-FINE JSONL worker, MobileNetV4 assurance, and the CPU classifier. The smoke CLI measures structured stage timing, produces a non-release report and overlays, and the PowerShell packaging scripts create and verify a ZIP containing only the required runtime assets and samples.

**Tech Stack:** Python 3.11, PyTorch CPU, torchvision, timm, Pillow, PyYAML, pytest, PowerShell.

## Global Constraints

- Process exactly these nine default samples: `e_0301/e_0306/e_0307`, `m_0307/m_0311/m_0315`, and `h_0306/h_0312/h_0315` from Batch2.
- Run real D-FINE, MobileNetV4, resolver, RepViT, and conditional DINOv3; never use cached boxes or classifier-only replay.
- Use CPU only. Every required path and checksum must be validated before a report, overlay, or partial output is created.
- Use `MobileOnlyE2EPipeline`; a candidate requiring unavailable ConvNeXt-Tiny recheck becomes `Unknown` and is excluded from SKU aggregation.
- Preserve canonical EXIF-transposed RGB coordinates and report boxes as `[x_min, y_min, x_max, y_max]`.
- Mark every report `cpu_functional_smoke_only`; do not claim the locked 299-image accuracy gate, production readiness, or RTX 5080-comparable performance.
- Preserve unrelated staged and unstaged workspace changes. Stage and commit only files named by a completed task.

---

### Task 1: Fixed Batch2 sample profile and CPU report timing contract

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_profile.py`
- Modify: `src/bakery_scanner/e2e/cpu_smoke.py`
- Modify: `src/bakery_scanner/e2e/__init__.py`
- Create: `tests/e2e/test_cpu_profile.py`
- Modify: `tests/e2e/test_cpu_smoke.py`

**Interfaces:**
- Produces `BATCH2_E3_M3_H3_NAMES: tuple[str, ...]` in E/M/H order.
- Produces `resolve_batch2_e3_m3_h3(source: Path) -> tuple[Path, ...]`, raising `FileNotFoundError` naming every missing image.
- Extends `run_cpu_smoke(..., warmup: Callable[[], None] | None = None) -> dict[str, object]` with timing-summary data supplied by each inference result.

- [ ] **Step 1: Write failing fixed-profile tests.**

```python
def test_batch2_profile_resolves_exact_e_m_h_three_each(tmp_path: Path):
    for name in BATCH2_E3_M3_H3_NAMES:
        (tmp_path / name).write_bytes(b"image")
    assert [path.name for path in resolve_batch2_e3_m3_h3(tmp_path)] == list(BATCH2_E3_M3_H3_NAMES)


def test_batch2_profile_reports_all_missing_paths(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="g20_b02_e_0301.jpg.*g20_b02_h_0315.jpg"):
        resolve_batch2_e3_m3_h3(tmp_path)
```

- [ ] **Step 2: Run the profile test to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_profile.py`

Expected: FAIL because `bakery_scanner.e2e.cpu_profile` does not exist.

- [ ] **Step 3: Implement immutable profile selection.**

```python
BATCH2_E3_M3_H3_NAMES = (
    "g20_b02_e_0301.jpg", "g20_b02_e_0306.jpg", "g20_b02_e_0307.jpg",
    "g20_b02_m_0307.jpg", "g20_b02_m_0311.jpg", "g20_b02_m_0315.jpg",
    "g20_b02_h_0306.jpg", "g20_b02_h_0312.jpg", "g20_b02_h_0315.jpg",
)

def resolve_batch2_e3_m3_h3(source: Path) -> tuple[Path, ...]:
    selected = tuple(source / name for name in BATCH2_E3_M3_H3_NAMES)
    missing = tuple(path.name for path in selected if not path.is_file())
    if missing:
        raise FileNotFoundError("Batch2 CPU profile is missing: " + ", ".join(missing))
    return selected
```

- [ ] **Step 4: Add a failing timing-report test.**

```python
def test_run_cpu_smoke_summarizes_nine_stage_timings(tmp_path: Path):
    paths = tuple(tmp_path / f"{index}.jpg" for index in range(9))
    report = run_cpu_smoke(ProfilePipeline(), paths, load_image=lambda _: object(), provenance={"device": "cpu"})
    assert report["input_count"] == 9
    assert report["timing_summary_ms"]["total"]["count"] == 9
    assert report["timing_summary_ms"]["total"]["p95"] == pytest.approx(9.0)
```

`ProfilePipeline.infer` returns an `E2EInference` whose `stage_timings_ms` mapping has `detector`, `mobile_assurance`, `resolver`, `repvit`, `dinov3`, and `total` values.

- [ ] **Step 5: Extend the report implementation and run focused tests.**

Add an optional `stage_timings_ms: Mapping[str, float]` field to `E2EInference`, validate the six non-negative finite timing keys, preserve it in `run_cpu_smoke`, and calculate nearest-rank p95 with `ceil(0.95 * count) - 1`. Keep current `total_ms` as the exact `total` value for compatibility.

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_profile.py tests/e2e/test_cpu_smoke.py tests/e2e/test_runtime.py`

Expected: PASS.

- [ ] **Step 6: Commit only Task 1 files.**

```powershell
git add src/bakery_scanner/e2e/cpu_profile.py src/bakery_scanner/e2e/cpu_smoke.py src/bakery_scanner/e2e/__init__.py tests/e2e/test_cpu_profile.py tests/e2e/test_cpu_smoke.py
git commit --only -m "feat: define Batch2 CPU smoke profile" -- src/bakery_scanner/e2e/cpu_profile.py src/bakery_scanner/e2e/cpu_smoke.py src/bakery_scanner/e2e/__init__.py tests/e2e/test_cpu_profile.py tests/e2e/test_cpu_smoke.py
```

### Task 2: CPU asset factory, fail-closed pipeline instrumentation, and CLI

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_factory.py`
- Modify: `src/bakery_scanner/e2e/runtime.py`
- Create: `scripts/run_e2e_smoke.py`
- Create: `tests/e2e/test_cpu_factory.py`
- Create: `tests/test_run_e2e_smoke.py`

**Interfaces:**
- Produces `CpuSmokeAssets.from_root(root: Path) -> CpuSmokeAssets` with fold-0 D-FINE, fold-0 MobileNetV4, classifier config, and all artifact paths.
- Produces `preflight_cpu_assets(assets: CpuSmokeAssets) -> dict[str, str]` containing resolved paths and SHA-256 values.
- Produces `build_cpu_pipeline(assets: CpuSmokeAssets) -> tuple[MobileOnlyE2EPipeline, Callable[[], None]]`.
- CLI command: `python scripts/run_e2e_smoke.py --package-root . --profile batch2_e3_m3_h3 --output <new-directory> --device cpu`.

- [ ] **Step 1: Write failing asset and CLI preflight tests.**

```python
def test_preflight_names_package_relative_missing_repvit(tmp_path: Path):
    assets = CpuSmokeAssets.from_root(tmp_path)
    with pytest.raises(FileNotFoundError, match="models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt"):
        preflight_cpu_assets(assets)


def test_cli_rejects_cuda_before_loading_models(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "argv", ["run_e2e_smoke.py", "--profile", "batch2_e3_m3_h3", "--output", str(tmp_path / "out"), "--device", "cuda:0"])
    assert main() == 2
```

- [ ] **Step 2: Run the tests to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py`

Expected: FAIL because the factory and executable do not exist.

- [ ] **Step 3: Implement the strict asset manifest and preflight.**

`CpuSmokeAssets.from_root` must resolve all paths from the provided root: `scripts/dfine_jsonl_server.py`, `third_party/D-FINE`, generated fold-0 640 config, `artifacts/e2e_current_source/detectors/dfine_n_640-seed20260724-fold0/best_stg1.pth`, fold-0 MobileNetV4 `verifier.pt`, classifier YAML, RepViT checkpoint/manifest/prototype bank, DINO weights/support/local bank, and calibration. Preflight must verify regular files, SHA-256 values declared by classifier config, the D-FINE checkout path, Python imports, and the absence of an output directory before starting a worker.

- [ ] **Step 4: Implement live CPU pipeline construction and timing.**

Build the detector from `JsonLineDFineTransport` and `PersistentDFineRunner(device="cpu")`; load the MobileNetV4 assurance checkpoint with `torch.load(..., map_location="cpu")`, call `.eval()`, and wrap it in `TorchAssuranceRunner(..., device="cpu")`. Create a package-relative classifier YAML with `runtime.device: CPU`, then call `ClassifierPipeline.load`. Use `MobileOnlyE2EPipeline` only.

Instrument `MobileOnlyE2EPipeline.infer` with `time.perf_counter()` around detector, MobileNetV4, resolver, and classifier calls. Sum the returned classifier `StageTimings.repvit_ms` and `dinov3_ms`; record the complete wall time as `total`. Do not add a synthetic timing or reload models per input.

- [ ] **Step 5: Implement the CLI output transaction.**

Load the fixed profile from `samples/batch2_e3_m3_h3`; run one non-reported warm-up inference; run exactly nine measured inferences; render each final box into `overlays/<input-stem>.png`; write `report.json` and `summary.txt` only after all nine succeed. On an exception, remove only the explicitly created temporary output directory and emit structured JSON to stderr with `stage`, exception type, and message.

- [ ] **Step 6: Run focused tests and commit only Task 2 files.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py tests/e2e/test_runtime.py`

Expected: PASS.

```powershell
git add src/bakery_scanner/e2e/cpu_factory.py src/bakery_scanner/e2e/runtime.py scripts/run_e2e_smoke.py tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py
git commit --only -m "feat: add live CPU smoke pipeline" -- src/bakery_scanner/e2e/cpu_factory.py src/bakery_scanner/e2e/runtime.py scripts/run_e2e_smoke.py tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py
```

### Task 3: Portable installer, package manifest, and Batch2 sample bundle

**Files:**
- Create: `portable_cpu_smoke/manifest.json`
- Create: `portable_cpu_smoke/requirements-cpu.txt`
- Create: `portable_cpu_smoke/install_cpu_smoke.ps1`
- Create: `portable_cpu_smoke/run_batch2_cpu_smoke.ps1`
- Create: `portable_cpu_smoke/README.md`
- Create: `scripts/package_cpu_smoke.ps1`
- Create: `tests/test_package_cpu_smoke.py`
- Modify: `README.md`

**Interfaces:**
- `scripts/package_cpu_smoke.ps1 -OutputPath <new-zip>` creates a ZIP and prints its SHA-256.
- `portable_cpu_smoke/manifest.json` lists every package-relative required file plus the nine samples.
- `portable_cpu_smoke/install_cpu_smoke.ps1` creates `.venv`, installs the pinned CPU requirements, and installs the local package without downloading model weights.

- [ ] **Step 1: Write failing manifest and sample-membership tests.**

```python
def test_portable_manifest_contains_runner_assets_and_nine_samples():
    manifest = json.loads((ROOT / "portable_cpu_smoke" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["scope"] == "cpu_functional_smoke_only"
    assert "scripts/run_e2e_smoke.py" in manifest["required_paths"]
    assert len(manifest["sample_paths"]) == 9
    assert manifest["sample_paths"][0].endswith("g20_b02_e_0301.jpg")
```

- [ ] **Step 2: Run the test to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/test_package_cpu_smoke.py`

Expected: FAIL because the portable manifest does not exist.

- [ ] **Step 3: Implement manifest and installer scripts.**

Pin every Python dependency to the versions validated in the CPU verification environment. The installer must check `py -3.11`, create `.venv` only when absent, install CPU PyTorch wheels from the official CPU index, install the remaining pinned requirements, and install the extracted project with `--no-deps`. It must stop on a failing command and never write outside the extracted package root.

The launch script must derive its root from `$PSScriptRoot`, create `results/<UTC timestamp>` with `New-Item -ItemType Directory`, call `.venv\Scripts\python.exe scripts\run_e2e_smoke.py --package-root . --profile batch2_e3_m3_h3 --output <result-directory> --device cpu`, then print the report path.

- [ ] **Step 4: Implement ZIP construction with manifest verification.**

The packager must refuse an existing output ZIP, construct an explicitly named temporary staging directory under the requested output parent, copy only `manifest.required_paths` and `manifest.sample_paths`, verify all copied paths with `Test-Path -LiteralPath`, write a staged manifest containing file SHA-256 values, archive staging with `Compress-Archive`, calculate the archive SHA-256, and remove only that staging directory in a `finally` block.

- [ ] **Step 5: Add usage documentation and run packaging tests.**

Document Windows 10/11, Python 3.11, expected network installation, the two PowerShell commands, expected `report.json` and overlay locations, the fixed nine inputs, and every non-release limitation.

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/test_package_cpu_smoke.py`

Expected: PASS.

- [ ] **Step 6: Commit only Task 3 files.**

```powershell
git add portable_cpu_smoke scripts/package_cpu_smoke.ps1 tests/test_package_cpu_smoke.py README.md
git commit --only -m "feat: package Batch2 CPU smoke runtime" -- portable_cpu_smoke scripts/package_cpu_smoke.ps1 tests/test_package_cpu_smoke.py README.md
```

### Task 4: End-to-end package verification and measured CPU handoff

**Files:**
- Create at runtime: `artifacts/portable/bakery-scanner-batch2-cpu-smoke.zip`
- Create at runtime: `artifacts/cpu-smoke-results/<UTC timestamp>/report.json`
- Create at runtime: `artifacts/cpu-smoke-results/<UTC timestamp>/overlays/*.png`

**Interfaces:**
- Consumes the ZIP output of Task 3.
- Produces a nine-row report and nine overlay images with timing summary and fail-closed limitations.

- [ ] **Step 1: Run the full targeted automated test suite.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_profile.py tests/e2e/test_cpu_smoke.py tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py tests/test_package_cpu_smoke.py`

Expected: PASS with no skipped test treated as runtime proof.

- [ ] **Step 2: Build the portable ZIP.**

Run: `powershell -ExecutionPolicy Bypass -File scripts/package_cpu_smoke.ps1 -OutputPath artifacts/portable/bakery-scanner-batch2-cpu-smoke.zip`

Expected: ZIP exists, its SHA-256 is printed, and the script reports nine bundled sample paths.

- [ ] **Step 3: Install and run in a clean CPU environment.**

Extract the ZIP into a new temporary directory. Run its `install_cpu_smoke.ps1`, then `run_batch2_cpu_smoke.ps1`. Do not use the repository Python environment for this final check.

Expected: exit code 0; output has one `report.json`, one `summary.txt`, and exactly nine overlay PNG files.

- [ ] **Step 4: Validate report invariants and record measured output.**

```powershell
$report = Get-Content -Raw <result-directory>\report.json | ConvertFrom-Json
if ($report.scope -ne 'cpu_functional_smoke_only') { throw 'unexpected report scope' }
if ($report.input_count -ne 9 -or $report.images.Count -ne 9) { throw 'expected exactly nine results' }
if ($report.timing_summary_ms.total.count -ne 9) { throw 'expected nine measured timings' }
if ((Get-ChildItem <result-directory>\overlays -Filter *.png).Count -ne 9) { throw 'expected nine overlays' }
```

Report the measured mean/median/p95 E2E times, stage means, DINO invocation count, ConvNeXt invocation count (always zero for this package), SKU aggregate, and `Unknown` object count. State that this is CPU smoke evidence only, not an accuracy or release claim.

- [ ] **Step 5: Commit only source/documentation changes, never generated ZIPs or reports.**

```powershell
git status --short
git add docs/superpowers/specs/2026-07-28-batch2-cpu-smoke-deployment-design.md docs/superpowers/plans/2026-07-28-batch2-cpu-smoke-deployment.md
git commit --only -m "docs: specify Batch2 CPU smoke deployment" -- docs/superpowers/specs/2026-07-28-batch2-cpu-smoke-deployment-design.md docs/superpowers/plans/2026-07-28-batch2-cpu-smoke-deployment.md
```

## Plan self-review

- Spec coverage: Task 1 fixes the required 3/3/3 set and report contract; Task 2 supplies real CPU pipeline execution, preflight, timing, overlays, and transactional output; Task 3 supplies reproducible installation and ZIP creation; Task 4 verifies the external-package flow and reports results.
- Placeholder scan: no unresolved file names, dependencies, test commands, or validation rules remain.
- Type consistency: `CpuSmokeAssets` is defined and consumed within Task 2; `stage_timings_ms` is added to `E2EInference` in Task 1 before Task 2 writes it; the CLI and profile names are identical in Tasks 2 through 4.
