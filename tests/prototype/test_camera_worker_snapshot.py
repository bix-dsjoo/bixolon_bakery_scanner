from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from scripts.benchmark_camera_worker import _STAGED_BOOTSTRAP, _compute_code_identity
from scripts.run_camera_inference_worker import (
    compute_deployed_worker_code_identity,
    compute_worker_code_identity,
    resolve_worker_execution_root,
    stage_worker_snapshot,
)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_attested_worker_tree(root: Path) -> None:
    _write(root / "pyproject.toml", "[project]\nname='snapshot'\n")
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'before'\n")
    _write(root / "dino" / "dinov3" / "__init__.py", "VALUE = 'before'\n")
    _write(root / "data" / "catalogs" / "classes.json", "[]\n")
    _write(root / "configs" / "gpu_rfdetr_classifier_policy.yaml", "gpu: before\n")
    _write(root / "configs" / "cpu_rfdetr_classifier_policy.yaml", "cpu: before\n")
    _write(root / "policies" / "presentation" / "camera_action_state_v2.json", "{}\n")
    _write(root / "policies" / "classification" / "policy_v2_manifest_rebound_cpu_smoke.json", "{}\n")
    _write(root / "policies" / "classification" / "fusion_local_or_global_consensus_margin_v1.json", "{}\n")
    _write(root / "models" / "rfdetr_large_bakery_v1" / "manifest.json", "{}\n")
    _write(root / "scripts" / "run_camera_inference_worker.py", "print('worker')\n")


def test_staged_child_snapshot_keeps_pre_import_source_bytes_immutable(tmp_path):
    root = tmp_path / "checkout"
    _write_attested_worker_tree(root)
    entrypoint = root / "scripts" / "run_camera_inference_worker.py"
    _write(entrypoint, "print('staged-entrypoint')\n")

    snapshot = stage_worker_snapshot(root, tmp_path / "snapshot")
    expected = compute_worker_code_identity(snapshot, commit="a" * 40)
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'changed'\n")

    assert (
        snapshot / "src" / "bakery_scanner" / "module.py"
    ).read_text(encoding="utf-8") == "VALUE = 'before'\n"
    assert compute_worker_code_identity(snapshot, commit="a" * 40) == expected
    assert _compute_code_identity(root, commit="a" * 40) != expected
    assert _compute_code_identity(snapshot, commit="a" * 40) == expected

    staged_entrypoint = snapshot / "scripts" / "run_camera_inference_worker.py"
    _write(entrypoint, "raise RuntimeError('live entrypoint must not execute')\n")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _STAGED_BOOTSTRAP,
            str(staged_entrypoint),
            hashlib.sha256(staged_entrypoint.read_bytes()).hexdigest(),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "staged-entrypoint\n"


def test_deployed_worker_identity_runs_from_packaged_root_without_git(tmp_path):
    """Catch a package worker reverting to the developer Git-snapshot path."""
    root = tmp_path / "pipeline"
    _write_attested_worker_tree(root)
    identity = compute_deployed_worker_code_identity(root, commit="b" * 40)
    _write(
        root / "worker-identity.json",
        '{"schema_version":1,"code_commit":"%s","code_identity_sha256":"%s"}\n'
        % (identity["code_commit"], identity["code_identity_sha256"]),
    )

    execution_root, observed = resolve_worker_execution_root(root, tmp_path / "temporary")

    assert execution_root == root.resolve()
    assert observed == identity


def test_deployed_worker_identity_rejects_tampered_packaged_source(tmp_path):
    """Catch execution of a payload whose attested worker source was changed."""
    root = tmp_path / "pipeline"
    _write_attested_worker_tree(root)
    identity = compute_deployed_worker_code_identity(root, commit="c" * 40)
    _write(
        root / "worker-identity.json",
        '{"schema_version":1,"code_commit":"%s","code_identity_sha256":"%s"}\n'
        % (identity["code_commit"], identity["code_identity_sha256"]),
    )
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'tampered'\n")

    import pytest

    with pytest.raises(ValueError, match="deployed worker code identity does not match"):
        resolve_worker_execution_root(root, tmp_path / "temporary")
