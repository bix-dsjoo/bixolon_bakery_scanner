from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject
from scripts.run_e2e_smoke import main


def test_cli_rejects_cuda_before_loading_models(monkeypatch, tmp_path: Path, capsys):
    """A non-CPU request must return structured failure without constructing assets."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_e2e_smoke.py",
            "--profile",
            "batch2_e3_m3_h3",
            "--output",
            str(tmp_path / "out"),
            "--device",
            "cuda:0",
        ],
    )

    assert main() == 2
    assert json.loads(capsys.readouterr().err)["stage"] == "arguments"


def test_cli_writes_only_e_m_h_means_after_all_nine_inputs(monkeypatch, tmp_path: Path):
    """A successful run publishes only three group means in report.json."""
    samples = tuple(tmp_path / f"g20_b02_{group}_{index:04d}.jpg" for group in "emh" for index in range(1, 4))
    for sample in samples:
        sample.write_bytes(b"image")
    output = tmp_path / "out"

    class Pipeline:
        def infer(self, image_id: int, image: object):
            return SimpleNamespace(
                image_id=image_id,
                final_objects=(FinalObject(Box(0, 0, 1, 1), 1, 0.9, "repvit_direct", ()),),
                convnext_invocations=0,
                dino_invocations=0,
                stage_timings_ms={
                    "detector": 1.0,
                    "mobile_assurance": 2.0,
                    "resolver": 3.0,
                    "repvit": 4.0,
                    "dinov3": 0.0,
                    "total": float(image_id),
                },
            )

    monkeypatch.setattr("scripts.run_e2e_smoke.CpuSmokeAssets.from_root", lambda root: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr(
        "scripts.run_e2e_smoke.preflight_cpu_assets",
        lambda assets: {"device": "cpu", "assurance_mode": "legacy_four_state_zero_delta"},
    )
    monkeypatch.setattr("scripts.run_e2e_smoke.build_cpu_pipeline", lambda assets: (Pipeline(), lambda: None))
    monkeypatch.setattr("scripts.run_e2e_smoke.resolve_batch2_e3_m3_h3", lambda source: samples)
    monkeypatch.setattr("scripts.run_e2e_smoke._load_image", lambda path: object())
    monkeypatch.setattr("scripts.run_e2e_smoke._write_overlay", lambda image, objects, path: path.write_bytes(b"png"))
    monkeypatch.setattr(sys, "argv", ["run_e2e_smoke.py", "--package-root", str(tmp_path), "--output", str(output)])

    assert main() == 0
    assert json.loads((output / "report.json").read_text(encoding="utf-8")) == {"E": 2.0, "M": 5.0, "H": 8.0}
    inference = json.loads((output / "inference.json").read_text(encoding="utf-8"))
    assert inference["provenance"]["assurance_mode"] == "legacy_four_state_zero_delta"
    assert "legacy_four_state_zero_delta" in inference["limitations"]
    assert "accuracy certification" in inference["limitations"]
    assert len(tuple((output / "overlays").glob("*.png"))) == 9


def test_cli_failure_leaves_no_requested_output_directory(monkeypatch, tmp_path: Path, capsys):
    """A measured inference failure must roll back the newly created output tree."""
    samples = tuple(tmp_path / f"g20_b02_{group}_{index:04d}.jpg" for group in "emh" for index in range(1, 4))
    for sample in samples:
        sample.write_bytes(b"image")
    output = tmp_path / "out"

    class FailingPipeline:
        def infer(self, image_id: int, image: object):
            raise RuntimeError("boom")

    monkeypatch.setattr("scripts.run_e2e_smoke.CpuSmokeAssets.from_root", lambda root: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr("scripts.run_e2e_smoke.preflight_cpu_assets", lambda assets: {"device": "cpu"})
    monkeypatch.setattr("scripts.run_e2e_smoke.build_cpu_pipeline", lambda assets: (FailingPipeline(), lambda: None))
    monkeypatch.setattr("scripts.run_e2e_smoke.resolve_batch2_e3_m3_h3", lambda source: samples)
    monkeypatch.setattr("scripts.run_e2e_smoke._load_image", lambda path: object())
    monkeypatch.setattr(sys, "argv", ["run_e2e_smoke.py", "--package-root", str(tmp_path), "--output", str(output)])

    assert main() == 1
    assert not output.exists()
    assert json.loads(capsys.readouterr().err)["stage"] == "inference"
