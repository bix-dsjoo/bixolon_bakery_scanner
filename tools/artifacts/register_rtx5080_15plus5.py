"""Register verified external RTX 5080 artifacts and compact final evidence.

The tool deliberately separates registration from promotion: a development
receipt can never make the candidate a production pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from bakery_scanner.benchmarking.oof15plus5 import (
    FrozenOofReceipt,
    build_final_development_policy,
)
from bakery_scanner.benchmarking.rtx5080_acceptance import (
    PerformanceReceipt,
    require_completion_performance_admission,
)


_REQUIRED_PERFORMANCE_SLICES = frozenset(
    {
        "E", "M", "H", "overall", "dinov3", "needs_retake", "unknown",
        "count_1_2", "count_3_7", "count_8_plus",
    }
)
_REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "rfdetr_engine", "repvit_engine", "dinov3_engine", "fusion_policy",
    }
)
_LOWER_HEX = frozenset("0123456789abcdef")
_REGISTRATION_SEALS: dict[int, tuple[object, str, Path]] = {}


class RegistrationError(ValueError):
    """Raised when an artifact cannot be safely registered."""


def build_completion_receipt(
    quality_receipt: object,
    performance_receipt: object,
    artifacts: Mapping[str, str],
    *,
    completion_admission: object | None = None,
    final_policy_bytes: bytes | None = None,
) -> dict[str, object]:
    """Build a Git-safe final status without promoting production.

    Unverified upstream inputs short-circuit before any quality or latency
    summary is copied. This prevents an incomplete receipt from looking like a
    numeric quality/performance result.
    """
    if isinstance(quality_receipt, Mapping) and isinstance(performance_receipt, Mapping):
        quality = _receipt_identity(quality_receipt, "quality")
        performance = _receipt_identity(performance_receipt, "performance")
    else:
        quality = performance = None
    if quality is not None and performance is not None and (
        _is_unverified(quality["status"]) or _is_unverified(performance["status"])
    ):
        return _seal(
            {
                "schema_version": 1,
                "status": "unverified",
                "production_status": "unverified",
                "quality": quality,
                "performance": performance,
                "artifact_identities": _validated_artifacts(artifacts, allow_empty=True),
                "unverified_boundaries": _unverified_boundaries(quality, performance),
            }
        )
    if not isinstance(quality_receipt, FrozenOofReceipt):
        raise ValueError("development-complete requires a validated FrozenOofReceipt")
    if not isinstance(performance_receipt, PerformanceReceipt):
        raise ValueError("development-complete requires a PerformanceReceipt object")
    if not isinstance(final_policy_bytes, bytes):
        raise ValueError("development-complete requires final policy bytes")
    completion = require_completion_performance_admission(completion_admission)
    performance_receipt.__post_init__()
    if completion.performance_receipt_sha256 != performance_receipt.receipt_sha256:
        raise ValueError("completion admission performance receipt mismatch")
    if completion.quality_receipt_sha256 != performance_receipt.quality_receipt_sha256:
        raise ValueError("completion admission quality receipt mismatch")
    policy_bytes = build_final_development_policy(quality_receipt, final_policy_bytes)
    artifact_identities = _validated_artifacts(artifacts, allow_empty=False)
    if artifact_identities["fusion_policy"] != hashlib.sha256(policy_bytes).hexdigest():
        raise ValueError("final fusion policy artifact identity mismatch")
    for role, digest in artifact_identities.items():
        if performance_receipt.artifact_identities.get(role) != digest:
            raise ValueError(f"performance receipt artifact identity mismatch: {role}")
    if completion.artifact_identity_sha256 != performance_receipt.artifact_identity_sha256:
        raise ValueError("completion admission artifact identity mismatch")
    return _seal(
        {
            "schema_version": 1,
            "status": "development-complete",
            "production_status": "unverified",
            "quality": {"frozen_oof_receipt_sha256": quality_receipt.sha256},
            "performance": {"receipt_sha256": performance_receipt.receipt_sha256},
            "artifact_identities": artifact_identities,
            "unverified_boundaries": ["non_target_rejection", "production_promotion"],
        }
    )


def register_external_artifacts(
    *,
    artifact_specs: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Resolve exact external artifact identities, refusing repository payloads."""
    root = _canonical_repository_root()
    if not root.is_dir():
        raise RegistrationError("repository root is unavailable")
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for spec in artifact_specs:
        artifact_id = _text(spec.get("id"), "artifact id")
        if artifact_id in seen:
            raise RegistrationError("artifact IDs must be unique")
        seen.add(artifact_id)
        kind = _text(spec.get("kind"), f"{artifact_id} kind")
        source_value = spec.get("source")
        if not isinstance(source_value, Path):
            raise RegistrationError(f"{artifact_id}: source must be a Path")
        source = source_value.resolve()
        if not source.is_file():
            raise RegistrationError(f"{artifact_id}: external artifact is missing")
        if source.is_relative_to(root):
            raise RegistrationError(f"{artifact_id}: Git-local model/engine payload is forbidden")
        local_path = _repository_relative(spec.get("local_path"), artifact_id)
        uri_env = _text(spec.get("uri_env"), f"{artifact_id} uri_env")
        size, digest = _file_identity(source)
        record = {
            "id": artifact_id, "kind": kind, "local_path": str(local_path),
            "sha256": digest, "bytes": size, "storage": "external", "uri_env": uri_env,
        }
        _REGISTRATION_SEALS[id(record)] = (record, _canonical_sha256(record), source)
        records.append(record)
    return records


def update_lock_with_registered_artifacts(
    *, lock_path: Path, records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Return a lock update only when every appended record is external.

    Callers own review and writing of the repository lock. This function never
    copies a model or engine into Git and refuses to overwrite an existing ID.
    """
    payload = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("artifacts"), list):
        raise RegistrationError("artifact lock schema is invalid")
    existing = {item.get("id") for item in payload["artifacts"] if isinstance(item, Mapping)}
    appended = []
    for record in records:
        sealed = _REGISTRATION_SEALS.get(id(record))
        if sealed is None or sealed[0] is not record:
            raise RegistrationError("lock updates require sealed external registrations")
        _, fingerprint, source = sealed
        if _canonical_sha256(record) != fingerprint:
            raise RegistrationError("sealed external registration was mutated")
        if source.is_relative_to(_canonical_repository_root()):
            raise RegistrationError("Git-local model/engine payload is forbidden")
        size, digest = _file_identity(source)
        if record.get("bytes") != size or record.get("sha256") != digest:
            raise RegistrationError("registered external artifact changed before lock update")
        if record.get("storage") != "external":
            raise RegistrationError("registered artifacts must remain external")
        artifact_id = _text(record.get("id"), "artifact id")
        if artifact_id in existing:
            raise RegistrationError(f"artifact ID already exists: {artifact_id}")
        _repository_relative(record.get("local_path"), artifact_id)
        _sha256(record.get("sha256"), f"{artifact_id} sha256")
        if type(record.get("bytes")) is not int or record["bytes"] < 0:
            raise RegistrationError(f"{artifact_id}: bytes must be non-negative")
        appended.append(dict(record))
    return {**payload, "artifacts": [*payload["artifacts"], *appended]}


def _receipt_identity(value: Mapping[str, object], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} receipt must be a mapping")
    expected_schema = 1 if label == "quality" else 3
    if value.get("schema_version") != expected_schema:
        raise ValueError(f"{label} receipt schema is invalid")
    status = _text(value.get("status"), f"{label} status")
    digest = value.get("receipt_sha256")
    _sha256(digest, f"{label} receipt SHA-256")
    identity = dict(value)
    del identity["receipt_sha256"]
    if digest != hashlib.sha256(_canonical_bytes(identity)).hexdigest():
        raise ValueError(f"{label} receipt hash mismatch")
    return {"status": status, "receipt_sha256": digest}


def _require_performance_paths(value: Mapping[str, object]) -> None:
    summaries = value.get("summaries")
    if not isinstance(summaries, Mapping):
        raise ValueError("performance receipt paths are missing")
    missing = _REQUIRED_PERFORMANCE_SLICES - set(summaries)
    if "dinov3" in missing:
        raise ValueError("DINO path is missing from performance receipt")
    if missing:
        raise ValueError("performance receipt paths are incomplete")
    try:
        PerformanceReceipt(**dict(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("performance receipt is not an admitted Task 11 receipt") from exc
    for name in _REQUIRED_PERFORMANCE_SLICES:
        row = summaries[name]
        try:
            p95 = row["timings_ms"]["total"]["p95"]  # type: ignore[index]
        except (KeyError, TypeError):
            raise ValueError(f"performance path {name} has no p95")
        if isinstance(p95, bool) or not isinstance(p95, (int, float)) or not math.isfinite(float(p95)):
            raise ValueError(f"performance path {name} has invalid p95")
        if float(p95) > 100.0:
            raise ValueError(f"performance path {name} exceeds 100ms")


def _validated_artifacts(value: Mapping[str, str], *, allow_empty: bool) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("artifact identities must be a mapping")
    if not value and allow_empty:
        return {}
    if set(value) != _REQUIRED_ARTIFACT_ROLES:
        raise ValueError("final artifact identities are incomplete")
    checked = dict(sorted(value.items()))
    for name, digest in checked.items():
        _sha256(digest, f"artifact {name}")
    return checked


def _unverified_boundaries(quality: Mapping[str, str], performance: Mapping[str, str]) -> list[str]:
    result = ["external_artifacts", "final_train_all_artifacts", "non_target_rejection", "production_promotion"]
    if _is_unverified(quality["status"]):
        result.append("quality_receipt")
    if _is_unverified(performance["status"]):
        result.extend(("rtx5080_runtime", "performance_receipt"))
    return sorted(set(result))


def _seal(payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    result["receipt_sha256"] = hashlib.sha256(_canonical_bytes(result)).hexdigest()
    return result


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _file_identity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _repository_relative(value: object, artifact_id: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise RegistrationError(f"{artifact_id}: local_path must be a non-empty POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise RegistrationError(f"{artifact_id}: local_path must be repository-relative POSIX")
    return path


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistrationError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _LOWER_HEX for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")


def _is_unverified(status: str) -> bool:
    return status.startswith("unverified")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-receipt", required=True, type=Path)
    parser.add_argument("--performance-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    quality = json.loads(arguments.quality_receipt.read_text(encoding="utf-8"))
    performance = json.loads(arguments.performance_receipt.read_text(encoding="utf-8"))
    receipt = build_completion_receipt(quality, performance, {})
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(receipt))
    print(json.dumps({"status": receipt["status"], "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    return 0 if receipt["status"] == "development-complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RegistrationError",
    "build_completion_receipt",
    "register_external_artifacts",
    "update_lock_with_registered_artifacts",
]
