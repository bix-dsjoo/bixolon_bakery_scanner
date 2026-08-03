from __future__ import annotations

from pathlib import Path

from scripts.benchmark_camera_worker import _compute_code_identity
from scripts.run_camera_inference_worker import (
    compute_worker_code_identity,
    stage_worker_snapshot,
)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_staged_child_snapshot_keeps_pre_import_source_bytes_immutable(tmp_path):
    root = tmp_path / "checkout"
    _write(root / "pyproject.toml", "[project]\nname='snapshot'\n")
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'before'\n")
    _write(root / "dino" / "dinov3" / "__init__.py", "VALUE = 'before'\n")
    _write(root / "data" / "catalogs" / "classes.json", "[]\n")
    _write(root / "configs" / "gpu_rfdetr_classifier_policy.yaml", "gpu: before\n")
    _write(root / "configs" / "cpu_rfdetr_classifier_policy.yaml", "cpu: before\n")
    _write(root / "policies" / "presentation" / "camera_action_state_v2.json", "{}\n")
    _write(root / "models" / "rfdetr_large_bakery_v1" / "manifest.json", "{}\n")
    _write(root / "scripts" / "run_camera_inference_worker.py", "# entrypoint\n")

    snapshot = stage_worker_snapshot(root, tmp_path / "snapshot")
    expected = compute_worker_code_identity(snapshot, commit="a" * 40)
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'changed'\n")

    assert (
        snapshot / "src" / "bakery_scanner" / "module.py"
    ).read_text(encoding="utf-8") == "VALUE = 'before'\n"
    assert compute_worker_code_identity(snapshot, commit="a" * 40) == expected
    assert _compute_code_identity(root, commit="a" * 40) != expected
    assert _compute_code_identity(snapshot, commit="a" * 40) == expected
