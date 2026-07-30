from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bakery_scanner.artifacts.lock import ArtifactIntegrityError, ArtifactLock


def _write_lock(root: Path, *, sha256: str) -> Path:
    path = root / "artifacts.lock.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "canonical_pipeline": "test",
                "artifacts": [
                    {
                        "id": "model_v1",
                        "kind": "model",
                        "local_path": "models/model_v1/model.bin",
                        "sha256": sha256,
                        "bytes": 7,
                        "storage": "external",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_artifact_lock_verifies_declared_bytes_and_sha256(tmp_path: Path):
    payload = tmp_path / "models" / "model_v1" / "model.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"weights")
    lock_path = _write_lock(
        tmp_path,
        sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
    )

    report = ArtifactLock.load(lock_path).verify(tmp_path)

    assert report.complete is True
    assert report.items[0].status == "verified"


def test_artifact_lock_reports_missing_in_manifest_only_mode(tmp_path: Path):
    lock_path = _write_lock(tmp_path, sha256="0" * 64)

    report = ArtifactLock.load(lock_path).verify(tmp_path, require_all=False)

    assert report.complete is False
    assert report.items[0].status == "missing"


def test_artifact_lock_fails_closed_for_hash_mismatch(tmp_path: Path):
    payload = tmp_path / "models" / "model_v1" / "model.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"weights")
    lock_path = _write_lock(tmp_path, sha256="0" * 64)

    with pytest.raises(ArtifactIntegrityError, match="SHA-256"):
        ArtifactLock.load(lock_path).verify(tmp_path)
