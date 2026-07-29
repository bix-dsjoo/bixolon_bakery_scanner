import pytest
import json
from pathlib import Path

from bakery_scanner.e2e.rfdetr_cpu import summarize_profiles


def test_summarize_profiles_reports_each_fixed_batch2_group_mean():
    summary = summarize_profiles((
        {"profile": "E", "elapsed_ms": 8.0},
        {"profile": "E", "elapsed_ms": 12.0},
        {"profile": "M", "elapsed_ms": 30.0},
        {"profile": "H", "elapsed_ms": 40.0},
    ))

    assert summary == {
        "E": {"images": 2, "mean_ms": pytest.approx(10.0)},
        "M": {"images": 1, "mean_ms": pytest.approx(30.0)},
        "H": {"images": 1, "mean_ms": pytest.approx(40.0)},
    }


def test_offline_package_manifest_includes_embedded_runtime_and_cpu_runner():
    manifest = json.loads(Path("portable_rfdetr_cpu/manifest.json").read_text(encoding="utf-8"))

    assert "runtime/python/python.exe" in manifest["required_paths"]
    assert "scripts/run_cpu_rfdetr_fusion.py" in manifest["required_paths"]
    assert "README.md" in manifest["required_paths"]


def test_offline_builder_keeps_runtime_preparation_separate_from_offline_zip_creation():
    builder = Path("scripts/build_offline_cpu_rfdetr_package.ps1").read_text(encoding="utf-8")
    preparer = Path("scripts/prepare_offline_cpu_runtime.ps1").read_text(encoding="utf-8")

    assert "RuntimeRoot" in builder
    assert "Compress-Archive" in builder
    assert "https://www.python.org/ftp/python" in preparer
    assert "download.pytorch.org/whl/cpu" in preparer
