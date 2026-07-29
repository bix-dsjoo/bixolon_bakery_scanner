import pytest
import json
from pathlib import Path

from bakery_scanner.e2e.rfdetr_cpu import summarize_profile_stages, summarize_profiles


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


def test_typed_profile_summary_records_all_stage_percentiles():
    summary = summarize_profile_stages(
        (
            {
                "profile": "E",
                "object_count": 2,
                "canonical_ms": 1.0,
                "detector_ms": 2.0,
                "crop_ms": 3.0,
                "repvit_ms": 4.0,
                "dinov3_ms": 5.0,
                "fusion_ms": 6.0,
                "elapsed_ms": 21.0,
            },
            {
                "profile": "E",
                "object_count": 3,
                "canonical_ms": 3.0,
                "detector_ms": 4.0,
                "crop_ms": 5.0,
                "repvit_ms": 6.0,
                "dinov3_ms": 7.0,
                "fusion_ms": 8.0,
                "elapsed_ms": 33.0,
            },
            {
                "profile": "M",
                "object_count": 0,
                "canonical_ms": 1.0,
                "detector_ms": 1.0,
                "crop_ms": 1.0,
                "repvit_ms": 1.0,
                "dinov3_ms": 1.0,
                "fusion_ms": 1.0,
                "elapsed_ms": 1.0,
            },
            {
                "profile": "H",
                "object_count": 0,
                "canonical_ms": 1.0,
                "detector_ms": 1.0,
                "crop_ms": 1.0,
                "repvit_ms": 1.0,
                "dinov3_ms": 1.0,
                "fusion_ms": 1.0,
                "elapsed_ms": 1.0,
            },
        )
    )

    assert summary["E"]["images"] == 2
    assert summary["E"]["objects"] == 5
    assert summary["E"]["total"]["mean_ms"] == pytest.approx(27.0)
    assert summary["E"]["detector"]["p95_ms"] == pytest.approx(3.9)


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
