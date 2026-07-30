from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_camera_installer_payload import (
    _copy_tree,
    build_package_manifest,
    load_pipeline_allowlist,
)
from scripts.verify_camera_installation import verify_package_manifest


def test_manifest_uses_relative_paths_sizes_and_sha256(tmp_path: Path) -> None:
    (tmp_path / "pipeline" / "configs").mkdir(parents=True)
    policy = tmp_path / "pipeline" / "configs" / "gpu.yaml"
    policy.write_text("schema_version: 1\n", encoding="utf-8")

    manifest = build_package_manifest(tmp_path, app_version="1.0.0")

    assert manifest["schema_version"] == 1
    assert manifest["app_version"] == "1.0.0"
    entry = manifest["files"]["pipeline/configs/gpu.yaml"]
    assert entry["bytes"] == policy.stat().st_size
    assert len(entry["sha256"]) == 64
    assert not any(Path(path).is_absolute() for path in manifest["files"])


def test_manifest_verifier_rejects_hash_mismatch_and_extra_file(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    tracked = payload / "app.exe"
    tracked.write_bytes(b"original")
    manifest = build_package_manifest(payload, app_version="1.0.0")
    (payload / "package-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    tracked.write_bytes(b"changed!")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_package_manifest(payload)

    tracked.write_bytes(b"original")
    (payload / "undeclared.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="extra"):
        verify_package_manifest(payload)


def test_manifest_verifier_rejects_tampered_presentation_policy_at_its_path(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload"
    policy = payload / "pipeline" / "configs" / "camera_presentation_policy.json"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b'{"policy_id":"camera_action_state_v1"}')
    manifest = build_package_manifest(payload, app_version="1.0.2")
    (payload / "package-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    policy.write_bytes(b'{"policy_id":"camera_action_state_v2"}')

    with pytest.raises(
        ValueError,
        match="hash mismatch: pipeline/configs/camera_presentation_policy.json",
    ):
        verify_package_manifest(payload)


def test_manifest_verifier_allows_inno_uninstaller_metadata(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "installed"
    payload.mkdir()
    (payload / "app.exe").write_bytes(b"app")
    manifest = build_package_manifest(payload, app_version="1.0.0")
    (payload / "package-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (payload / "unins000.exe").write_bytes(b"uninstaller")
    (payload / "unins000.dat").write_bytes(b"metadata")

    verify_package_manifest(payload)


def test_payload_tree_copy_excludes_generated_python_bytecode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    package = source / "demo"
    cache = package / "__pycache__"
    cache.mkdir(parents=True)
    (package / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (cache / "module.cpython-311.pyc").write_bytes(b"generated")

    destination = tmp_path / "destination"
    _copy_tree(source, destination)

    assert (destination / "demo" / "module.py").is_file()
    assert not (destination / "demo" / "__pycache__").exists()


def test_installer_allowlist_bundles_dinov3_source_and_license() -> None:
    repo_root = Path(__file__).parents[2]
    payload = json.loads(
        (
            repo_root / "deployment" / "camera_installer" / "payload-paths.json"
        ).read_text(encoding="utf-8")
    )

    assert "dino/dinov3" in payload["pipeline_directories"]
    assert "dino/LICENSE.md" in payload["pipeline_files"]


def test_installer_allowlist_bundles_sku_class_map() -> None:
    repo_root = Path(__file__).parents[2]
    payload = json.loads(
        (
            repo_root / "deployment" / "camera_installer" / "payload-paths.json"
        ).read_text(encoding="utf-8")
    )

    assert "datasets/classes.json" in payload["pipeline_files"]


def test_allowlist_rejects_missing_file_absolute_path_and_symlink(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    allowlist = tmp_path / "payload-paths.json"
    allowlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pipeline_directories": [],
                "pipeline_files": ["models/missing.pth"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        load_pipeline_allowlist(repo, allowlist)

    allowlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pipeline_directories": [],
                "pipeline_files": [str((repo / "absolute.pth").resolve())],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="relative"):
        load_pipeline_allowlist(repo, allowlist)

    source = repo / "real.txt"
    source.write_text("model", encoding="utf-8")
    link = repo / "linked.txt"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows account")
    allowlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pipeline_directories": [],
                "pipeline_files": ["linked.txt"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reparse|symlink"):
        load_pipeline_allowlist(repo, allowlist)
