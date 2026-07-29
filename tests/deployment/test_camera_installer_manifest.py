from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_camera_installer_payload import (
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
