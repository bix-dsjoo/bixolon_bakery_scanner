# CPU E2E Smoke Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a portable Windows ZIP that runs a deterministic CPU-only, ten-image MobileNetV4-only functional smoke test and produces an explicitly non-release report.

**Architecture:** `bakery_scanner.e2e.cpu_smoke` owns deterministic input selection, CPU-only preflight, dependency-injected pipeline execution, and report construction. A MobileNetV4-only adapter converts every candidate that would require ConvNeXt-Tiny recheck to assurance `Unknown`. `scripts/run_e2e_smoke.py` is a thin CLI that resolves all package-relative paths. `scripts/package_cpu_smoke.ps1` creates a ZIP containing code, pinned dependency metadata, required CPU assets, and launch documentation without an input image directory.

**Tech Stack:** Python 3.11, PyTorch CPU, Pillow, PyYAML, PowerShell `Compress-Archive`, pytest.

## Global Constraints

- CPU mode is a functional smoke test only; it must never present CPU latency or partial data as a release result.
- At most 10 supported images may be processed, in stable case-insensitive filename order.
- The detector, MobileNetV4 assurance, resolver, RepViT, and conditional DINO path must be supplied as one pipeline; cached OOF boxes and classifier-only replay are forbidden.
- ConvNeXt-Tiny is intentionally absent. A candidate requiring recheck must become `Unknown`; the report must state this limitation.
- A missing runtime, model, or artifact must fail before output creation with a stable diagnostic.
- The ZIP contains no user image directory and resolves all supplied paths relative to its extracted root or command-line arguments.

---

### Task 1: CPU smoke domain API and report contract

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_smoke.py`
- Create: `tests/e2e/test_cpu_smoke.py`
- Modify: `src/bakery_scanner/e2e/__init__.py`

**Interfaces:**
- Produces `select_smoke_images(images_dir: Path, limit: int = 10) -> tuple[Path, ...]`.
- Produces `run_cpu_smoke(pipeline: E2EPipeline, images: tuple[Path, ...], *, load_image: Callable[[Path], CanonicalImage], provenance: Mapping[str, str]) -> dict[str, object]`.
- Produces `validate_cpu_smoke_request(images_dir: Path, output: Path, device: str, limit: int) -> tuple[Path, ...]`.

- [ ] **Step 1: Write the failing selection and validation tests.**

```python
def test_select_smoke_images_is_stable_and_limited(tmp_path: Path):
    for name in ("z.JPG", "B.png", "a.jpg", "skip.txt"):
        (tmp_path / name).write_bytes(b"x")
    assert [path.name for path in select_smoke_images(tmp_path)] == ["a.jpg", "B.png", "z.JPG"]


def test_validate_cpu_smoke_request_rejects_gpu_and_existing_output(tmp_path: Path):
    (tmp_path / "one.jpg").write_bytes(b"x")
    output = tmp_path / "report.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="device must be cpu"):
        validate_cpu_smoke_request(tmp_path, tmp_path / "new.json", "cuda:0", 10)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        validate_cpu_smoke_request(tmp_path, output, "cpu", 10)
```

- [ ] **Step 2: Run the tests to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_smoke.py`

Expected: FAIL because `bakery_scanner.e2e.cpu_smoke` does not exist.

- [ ] **Step 3: Implement the minimal deterministic selection and validation API.**

```python
_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png"}

def select_smoke_images(images_dir: Path, limit: int = 10) -> tuple[Path, ...]:
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    selected = sorted(
        (path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES),
        key=lambda path: (path.name.casefold(), path.name),
    )[:limit]
    if not selected:
        raise ValueError("images directory contains no supported raster images")
    return tuple(selected)
```

- [ ] **Step 4: Extend the failing test with report scope and Unknown aggregation.**

```python
def test_run_cpu_smoke_marks_unknowns_unaggregated(tmp_path: Path):
    report = run_cpu_smoke(FakePipeline(), (tmp_path / "one.jpg",), load_image=lambda _: object(), provenance={"device": "cpu"})
    assert report["scope"] == "cpu_functional_smoke_only"
    assert report["aggregate"] == {"1": 1}
    assert report["images"][0]["final_objects"][1]["sku_id"] is None
```

- [ ] **Step 5: Implement report construction and execute the focused tests.**

Use `time.perf_counter()` around each `pipeline.infer`; serialize `FinalObject` boxes as `xyxy`; count only non-`None` SKU IDs; include `limitations` with the exact CPU-only non-release statement.

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_smoke.py`

Expected: PASS.

- [ ] **Step 6: Commit Task 1.**

```powershell
git add src/bakery_scanner/e2e/cpu_smoke.py src/bakery_scanner/e2e/__init__.py tests/e2e/test_cpu_smoke.py
git commit -m "feat: add CPU E2E smoke contract"
```

### Task 2: CLI, CPU pipeline factory, and preflight

**Files:**
- Create: `src/bakery_scanner/e2e/cpu_factory.py`
- Create: `scripts/run_e2e_smoke.py`
- Create: `tests/e2e/test_cpu_factory.py`
- Create: `tests/test_run_e2e_smoke.py`

**Interfaces:**
- Produces `CpuSmokeAssets.from_root(root: Path) -> CpuSmokeAssets`.
- Produces `preflight_cpu_assets(assets: CpuSmokeAssets) -> Mapping[str, str]`.
- Produces `build_cpu_pipeline(assets: CpuSmokeAssets) -> E2EPipeline`.
- CLI consumes `--images`, `--output`, `--limit`, `--device`, and optional `--package-root`.

- [ ] **Step 1: Write failing preflight tests.**

```python
def test_preflight_reports_missing_asset_with_package_relative_path(tmp_path: Path):
    assets = CpuSmokeAssets.from_root(tmp_path)
    with pytest.raises(FileNotFoundError, match="models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt"):
        preflight_cpu_assets(assets)


def test_cli_refuses_non_cpu_device_before_factory(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sys, "argv", ["run_e2e_smoke.py", "--images", str(tmp_path), "--output", str(tmp_path / "out.json"), "--device", "cuda:0"])
    assert main() == 2
```

- [ ] **Step 2: Run the tests to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py`

Expected: FAIL because the CPU factory and CLI do not exist.

- [ ] **Step 3: Implement package-relative asset discovery and preflight.**

`CpuSmokeAssets` must name the detector checkpoint, D-FINE worker command, MobileNetV4 checkpoint, ConvNeXt checkpoint, classifier config, RepViT checkpoint, DINO weights/support/local bank, and policy artifact. `preflight_cpu_assets` must verify all files, set `torch.set_num_threads` only from an explicit CLI option, and reject CUDA devices.

- [ ] **Step 4: Implement the CPU factory with the real pipeline components.**

Load every Torch model with `map_location="cpu"`, call `.eval()`, and construct the MobileNetV4-only pipeline with the D-FINE CPU adapter, `TorchAssuranceRunner` MobileNetV4 adapter, and `ClassifierPipeline.load` configured with `runtime.device: cpu`. Candidates that require ConvNeXt-Tiny become `assurance_unknown`; do not use cached boxes. Make the D-FINE worker command explicit in the asset manifest so a missing compatible worker produces preflight failure rather than a fallback prediction.

- [ ] **Step 5: Implement the CLI and verify GREEN.**

The CLI must write JSON only after a fully successful run, write structured JSON errors to stderr, and return 0 on success or 2 for validation/preflight failures.

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py`

Expected: PASS.

- [ ] **Step 6: Commit Task 2.**

```powershell
git add src/bakery_scanner/e2e/cpu_factory.py scripts/run_e2e_smoke.py tests/e2e/test_cpu_factory.py tests/test_run_e2e_smoke.py
git commit -m "feat: add CPU smoke CLI and pipeline factory"
```

### Task 3: Portable ZIP build and handoff documentation

**Files:**
- Create: `scripts/package_cpu_smoke.ps1`
- Create: `portable_cpu_smoke/README.md`
- Create: `portable_cpu_smoke/manifest.json`
- Create: `tests/test_package_cpu_smoke.py`
- Modify: `README.md`

**Interfaces:**
- `scripts/package_cpu_smoke.ps1 -OutputPath <zip>` creates the archive and returns its SHA-256.
- The archive root contains `scripts/run_e2e_smoke.py`, `src/`, `configs/`, `models/`, required `artifacts/e2e_current_source/` assets, `third_party/D-FINE/`, `pyproject.toml`, and `portable_cpu_smoke/README.md`.

- [ ] **Step 1: Write the failing archive manifest test.**

```python
def test_portable_manifest_lists_required_runtime_paths():
    manifest = json.loads((ROOT / "portable_cpu_smoke" / "manifest.json").read_text(encoding="utf-8"))
    assert "scripts/run_e2e_smoke.py" in manifest["required_paths"]
    assert "models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt" in manifest["required_paths"]
    assert manifest["scope"] == "cpu_functional_smoke_only"
```

- [ ] **Step 2: Run the test to verify RED.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/test_package_cpu_smoke.py`

Expected: FAIL because the portable manifest does not exist.

- [ ] **Step 3: Implement the packaging script and manifest.**

The PowerShell script must create a temporary staging directory, copy only manifest-listed required files, calculate SHA-256 for each copied file, generate `portable_cpu_smoke/manifest.json`, create a ZIP with `Compress-Archive`, verify that every manifest path exists inside the archive staging directory, and remove only its explicitly-created temporary staging directory. It must refuse an existing output ZIP.

- [ ] **Step 4: Write portable setup instructions.**

Document Windows 10/11, Python 3.11, CPU PyTorch installation, extraction, `py -3.11 -m pip install .[verifier]`, and the exact ten-image command. State that the runtime can be slow and that the output is not a release certification.

- [ ] **Step 5: Run tests and build the archive.**

Run: `$env:PYTHONPATH='src'; py -3.11 -m pytest --import-mode=importlib -q tests/test_package_cpu_smoke.py`

Run: `powershell -ExecutionPolicy Bypass -File scripts/package_cpu_smoke.ps1 -OutputPath artifacts/portable/bakery-scanner-cpu-smoke.zip`

Expected: test PASS; archive exists; its SHA-256 is printed; archive contains every manifest entry.

- [ ] **Step 6: Commit Task 3.**

```powershell
git add scripts/package_cpu_smoke.ps1 portable_cpu_smoke tests/test_package_cpu_smoke.py README.md
git commit -m "feat: package portable CPU smoke runner"
```

## Plan review

- Scope coverage: Tasks 1-2 implement deterministic CPU execution, validation, complete-pipeline construction, output, and non-release limitations. Task 3 creates and verifies the ZIP plus external-PC instructions.
- Placeholder scan: no deferred implementation markers or unresolved paths remain; all required runtime assets are explicitly named.
- Type consistency: Task 1 exposes the report API consumed by Task 2; Task 2 exposes the CLI consumed by Task 3's package manifest.
