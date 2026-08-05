from __future__ import annotations

import json
from pathlib import Path

from tools.benchmark.run_rtx5080_15plus5 import main, write_unverified_checkpoint


def test_unverified_checkpoint_has_no_timings_or_performance_pass(tmp_path: Path) -> None:
    compact = tmp_path / "result.json"
    summary = tmp_path / "summary.md"

    payload = write_unverified_checkpoint(
        compact,
        summary,
        status="unverified_missing_artifacts",
        missing_inputs=("artifact_root", "runtime_manifest"),
    )

    assert payload == json.loads(compact.read_text(encoding="utf-8"))
    assert payload["performance_status"] == "unverified"
    assert "summaries" not in payload
    assert "timings" not in payload
    assert "100ms passed" not in summary.read_text(encoding="utf-8")


def test_cli_missing_external_runtime_writes_unverified_not_fake_receipt(tmp_path: Path) -> None:
    compact = tmp_path / "result.json"
    summary = tmp_path / "summary.md"
    raw = tmp_path / "external" / "raw.json"

    exit_code = main(
        [
            "--dataset-root", str(tmp_path / "dataset"),
            "--splits", str(tmp_path / "splits"),
            "--config", str(tmp_path / "candidate.yaml"),
            "--runtime-manifest", str(tmp_path / "runtime.json"),
            "--artifact-root", str(tmp_path / "artifacts"),
            "--protocol", str(tmp_path / "protocol.json"),
            "--quality-receipt", str(tmp_path / "quality.json"),
            "--raw-output", str(raw),
            "--compact-output", str(compact),
            "--summary", str(summary),
        ]
    )

    assert exit_code == 2
    payload = json.loads(compact.read_text(encoding="utf-8"))
    assert payload["status"] == "unverified_missing_artifacts"
    assert payload["performance_status"] == "unverified"
    assert "samples" not in payload
    assert not raw.exists()
