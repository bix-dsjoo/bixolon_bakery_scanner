"""Contract tests for the portable Batch2 CPU-smoke package."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ROOT / "portable_cpu_smoke"


def _manifest() -> dict[str, object]:
    return json.loads((PORTABLE / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_scopes_real_cpu_runtime_and_exactly_nine_samples() -> None:
    """Catch a package that omits live assets or silently bundles a dataset."""
    manifest = _manifest()

    assert manifest["scope"] == "cpu_functional_smoke_only"
    assert set(manifest) == {"schema_version", "scope", "required_paths", "sample_paths"}
    assert "scripts/run_e2e_smoke.py" in manifest["required_paths"]
    assert "src/bakery_scanner" in manifest["required_paths"]
    assert "third_party/D-FINE/src" in manifest["required_paths"]
    assert "third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml" in manifest["required_paths"]
    assert "datasets" not in manifest["required_paths"]
    assert len(manifest["sample_paths"]) == 9
    assert manifest["sample_paths"] == [
        "samples/batch2_e3_m3_h3/g20_b02_e_0301.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_e_0306.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_e_0307.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_m_0307.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_m_0311.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_m_0315.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_h_0306.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_h_0312.jpg",
        "samples/batch2_e3_m3_h3/g20_b02_h_0315.jpg",
    ]


def test_manifest_paths_exist_and_do_not_include_full_datasets() -> None:
    """Catch stale manifest entries before an operator receives an unusable ZIP."""
    manifest = _manifest()
    paths = [*manifest["required_paths"], *manifest["sample_paths"]]

    assert all((ROOT / path).exists() for path in paths)
    assert all(not path.startswith("datasets/") for path in paths)


def test_requirements_pin_cpu_runtime_and_dfine_import_dependencies() -> None:
    """Catch an installer that cannot satisfy the D-FINE preflight import probe."""
    requirements = (PORTABLE / "requirements-cpu.txt").read_text(encoding="utf-8").splitlines()

    assert requirements == [
        "torch==2.13.0+cpu",
        "torchvision==0.28.0+cpu",
        "Pillow==12.2.0",
        "timm==1.0.28",
        "PyYAML==6.0.3",
        "pydantic==2.13.4",
        "tensorboard==2.20.0",
        "numpy==2.4.4",
        "scipy==1.17.1",
        "faster-coco-eval==1.7.0",
    ]
    installer = (PORTABLE / "install_cpu_smoke.ps1").read_text(encoding="utf-8")
    assert "function Invoke-Checked" in installer


def test_packager_writes_hash_coverage_and_refuses_an_existing_zip(tmp_path: Path) -> None:
    """Catch broken staging paths, missing payload hashes, or destructive ZIP output."""
    project = tmp_path / "project"
    package_script = project / "scripts" / "package_cpu_smoke.ps1"
    package_script.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "package_cpu_smoke.ps1", package_script)
    portable = project / "portable_cpu_smoke"
    portable.mkdir()
    (project / "runtime" / "nested").mkdir(parents=True)
    (project / "runtime" / "nested" / "asset.txt").write_text("runtime", encoding="utf-8")
    (project / "samples").mkdir()
    (project / "samples" / "one.jpg").write_bytes(b"sample")
    (portable / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "cpu_functional_smoke_only",
                "required_paths": ["runtime"],
                "sample_paths": ["samples/one.jpg"],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "smoke.zip"
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(package_script),
        "-OutputPath",
        str(output),
    ]

    completed = subprocess.run(command, cwd=project, text=True, capture_output=True, check=False)

    assert completed.returncode == 0, completed.stderr
    with zipfile.ZipFile(output) as archive:
        payload = json.loads(archive.read("package-manifest.json"))
    assert set(payload["file_sha256"]) == {"runtime/nested/asset.txt", "samples/one.jpg"}

    repeat = subprocess.run(command, cwd=project, text=True, capture_output=True, check=False)
    assert repeat.returncode != 0
    assert "refusing to overwrite existing ZIP" in repeat.stderr
