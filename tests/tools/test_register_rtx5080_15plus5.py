from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.artifacts.register_rtx5080_15plus5 as registration_module
from tools.artifacts.register_rtx5080_15plus5 import (
    RegistrationError,
    build_completion_receipt,
    register_external_artifacts,
    update_lock_with_registered_artifacts,
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sealed(payload: dict[str, object]) -> dict[str, object]:
    return {**payload, "receipt_sha256": _sha(payload)}


QUALITY_PASSED = _sealed(
    {"schema_version": 1, "status": "quality-passed-performance-unverified"}
)
ARTIFACTS = {
    "rfdetr_engine": _sha("rfdetr"),
    "repvit_engine": _sha("repvit"),
    "dinov3_engine": _sha("dinov3"),
    "fusion_policy": _sha("policy"),
}


def _performance_passed() -> dict[str, object]:
    runtime = {
        "device": "cuda:0", "gpu_name": "NVIDIA GeForce RTX 5080",
        "compute_capability": "12.0", "driver_version": "591", "cuda_version": "13",
        "tensorrt_version": "10.14", "windows_build": "26100", "wddm_version": "3.2",
        "runtime_manifest_sha256": _sha("runtime"), "fallback_reason": None,
    }
    artifact_identities = {
        name: _sha(name)
        for name in (
            "rfdetr_engine", "repvit_engine", "dinov3_engine", "detector_calibration",
            "repvit_prototype", "dinov3_support", "dinov3_local_bank", "preprocess",
            "fusion_policy", "catalog", "code", "admission_receipt",
        )
    }
    summaries = {
        name: {"timings_ms": {"total": {"p95": 99.0}}}
        for name in (
            "E", "M", "H", "overall", "dinov3", "needs_retake", "unknown",
            "count_1_2", "count_3_7", "count_8_plus",
        )
    }
    payload = {
        "schema_version": 3, "status": "performance-passed", "runtime_identity": runtime,
        "runtime_identity_sha256": _sha(runtime), "artifact_identities": artifact_identities,
        "artifact_identity_sha256": _sha(artifact_identities),
        "quality_receipt_sha256": QUALITY_PASSED["receipt_sha256"],
        "protocol_sha256": _sha("protocol"), "bootstrap_seed": 20260803,
        "summaries": summaries, "violations": [], "sample_count": 3000,
        "samples_sha256": _sha("samples"),
    }
    return _sealed(payload)


def test_public_completion_builder_rejects_incomplete_performance_dict() -> None:
    performance_passed = _performance_passed()
    without_dino = dict(performance_passed)
    summaries = dict(performance_passed["summaries"])
    del summaries["dinov3"]
    without_dino["summaries"] = summaries
    without_dino = _sealed({key: value for key, value in without_dino.items() if key != "receipt_sha256"})

    with pytest.raises(ValueError, match="FrozenOofReceipt"):
        build_completion_receipt(QUALITY_PASSED, without_dino, ARTIFACTS)


def test_completion_rejects_self_sealed_compact_quality_dict() -> None:
    with pytest.raises(ValueError, match="FrozenOofReceipt"):
        build_completion_receipt(QUALITY_PASSED, _performance_passed(), ARTIFACTS)


def test_completion_rejects_caller_authored_receipt_hash() -> None:
    forged_quality = {**QUALITY_PASSED, "status": "quality-rejected"}

    with pytest.raises(ValueError, match="quality receipt hash mismatch"):
        build_completion_receipt(forged_quality, _performance_passed(), ARTIFACTS)


def test_unverified_input_never_carries_numeric_quality_or_latency() -> None:
    quality = _sealed({"schema_version": 1, "status": "unverified_missing_artifacts"})
    performance = _sealed({"schema_version": 3, "status": "unverified_missing_artifacts"})
    receipt = build_completion_receipt(quality, performance, {})

    assert receipt["status"] == "unverified"
    assert receipt["quality"] == {
        "status": "unverified_missing_artifacts",
        "receipt_sha256": quality["receipt_sha256"],
    }
    assert receipt["performance"] == {
        "status": "unverified_missing_artifacts",
        "receipt_sha256": performance["receipt_sha256"],
    }
    assert "p95" not in json.dumps(receipt)


def test_registers_verified_external_identity_and_rejects_git_local_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setattr(registration_module, "_canonical_repository_root", lambda: repository)
    payload = external / "rfdetr.engine"
    payload.write_bytes(b"rfdetr-engine")

    records = register_external_artifacts(
        artifact_specs=(
            {
                "id": "rtx5080_rfdetr_engine_v1",
                "kind": "engine",
                "source": payload,
                "local_path": "external/rtx5080/rfdetr.engine",
                "uri_env": "BAKERY_ARTIFACT_BASE_URI",
            },
        ),
    )

    assert records == [{
        "id": "rtx5080_rfdetr_engine_v1",
        "kind": "engine",
        "local_path": "external/rtx5080/rfdetr.engine",
        "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        "bytes": len(payload.read_bytes()),
        "storage": "external",
        "uri_env": "BAKERY_ARTIFACT_BASE_URI",
    }]

    git_local = repository / "engine.plan"
    git_local.write_bytes(b"forbidden")
    with pytest.raises(RegistrationError, match="Git-local"):
        register_external_artifacts(
            artifact_specs=(
                {
                    "id": "forbidden_engine",
                    "kind": "engine",
                    "source": git_local,
                    "local_path": "external/rtx5080/forbidden.plan",
                    "uri_env": "BAKERY_ARTIFACT_BASE_URI",
                },
            ),
        )


def test_lock_update_requires_sealed_external_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    source = external / "engine.plan"
    source.write_bytes(b"engine")
    monkeypatch.setattr(registration_module, "_canonical_repository_root", lambda: repository)
    records = register_external_artifacts(
        artifact_specs=({
            "id": "rtx5080_engine", "kind": "engine", "source": source,
            "local_path": "external/rtx5080/engine.plan", "uri_env": "BAKERY_ARTIFACT_BASE_URI",
        },),
    )
    lock = repository / "artifacts.lock.json"
    lock.write_text(json.dumps({"schema_version": 1, "canonical_pipeline": "test", "artifacts": []}), encoding="utf-8")

    with pytest.raises(RegistrationError, match="sealed"):
        update_lock_with_registered_artifacts(lock_path=lock, records=(dict(records[0]),))

    updated = update_lock_with_registered_artifacts(lock_path=lock, records=records)
    assert updated["artifacts"] == records

    source.write_bytes(b"substituted")
    with pytest.raises(RegistrationError, match="changed"):
        update_lock_with_registered_artifacts(lock_path=lock, records=records)
