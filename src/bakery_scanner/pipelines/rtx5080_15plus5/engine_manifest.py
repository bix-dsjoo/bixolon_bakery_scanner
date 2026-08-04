"""Strict identities and FP16 admission for the RTX 5080 engine set."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = {
    "schema_version", "runtime_id", "build_host", "gpu", "driver",
    "cuda_runtime", "tensorrt_python_wheel", "trtexec", "onnx_python_wheel",
}
_FILE_KEYS = {"path", "bytes", "sha256"}
_VERSIONED_FILE_KEYS = _FILE_KEYS | {"version"}


class EngineAdmissionError(ValueError):
    """Raised before an unverified runtime or engine can be used."""


@dataclass(frozen=True, slots=True)
class VerifiedFile:
    path: Path
    bytes: int
    sha256: str
    version: str | None = None


@dataclass(frozen=True, slots=True)
class EngineRuntimeManifest:
    path: Path
    sha256: str
    runtime_id: str
    build_host: Mapping[str, str]
    gpu_name: str
    compute_capability: str
    gpu_uuid: str
    driver: VerifiedFile
    cuda_runtime: VerifiedFile
    tensorrt_python_wheel: VerifiedFile
    trtexec_identity: VerifiedFile
    onnx_python_wheel: VerifiedFile

    @property
    def trtexec(self) -> Path:
        return self.trtexec_identity.path

    def receipt_payload(self) -> dict[str, object]:
        return {
            "runtime_id": self.runtime_id,
            "runtime_manifest": _file_payload(VerifiedFile(self.path, self.path.stat().st_size, self.sha256)),
            "build_host": dict(self.build_host),
            "gpu": {"name": self.gpu_name, "compute_capability": self.compute_capability, "uuid": self.gpu_uuid},
            "driver": _file_payload(self.driver),
            "cuda_runtime": _file_payload(self.cuda_runtime),
            "tensorrt_python_wheel": _file_payload(self.tensorrt_python_wheel),
            "trtexec": _file_payload(self.trtexec_identity),
            "onnx_python_wheel": _file_payload(self.onnx_python_wheel),
        }


_CANONICAL_BINDINGS: dict[str, tuple[dict[str, object], ...]] = {
    "rfdetr": (
        {"name": "images", "mode": "input", "dtype": "float16", "shape": [1, 3, 640, 640], "semantic": "canonical_rgb"},
        {"name": "boxes", "mode": "output", "dtype": "float16", "shape": [1, 300, 4], "semantic": "normalized_xyxy"},
        {"name": "scores", "mode": "output", "dtype": "float16", "shape": [1, 300], "semantic": "objectness"},
    ),
    "repvit": (
        {"name": "crops", "mode": "input", "dtype": "float16", "shape": [14, 3, 224, 224], "semantic": "tight_context_rows"},
        {"name": "logits", "mode": "output", "dtype": "float16", "shape": [14, 20], "semantic": "sku_logits"},
    ),
    "dinov3": (
        {"name": "crops", "mode": "input", "dtype": "float16", "shape": [7, 3, 224, 224], "semantic": "context_rows"},
        {"name": "global_embeddings", "mode": "output", "dtype": "float16", "shape": [7, 384], "semantic": "global_cls_embedding"},
        {"name": "local_patch_tokens", "mode": "output", "dtype": "float16", "shape": [7, 196, 384], "semantic": "local_patch_embedding"},
    ),
}

_MODEL_IDS = {
    "rfdetr": "rfdetr_l_bread_gpu_fp16_v1",
    "repvit": "repvit_m1_15plus5_gpu_fp16_v1",
    "dinov3": "dinov3_vits16_15plus5_gpu_fp16_v1",
}


def canonical_engine_bindings(role: str) -> tuple[dict[str, object], ...]:
    try:
        return tuple({**item, "shape": list(item["shape"])} for item in _CANONICAL_BINDINGS[role])
    except KeyError as exc:
        raise EngineAdmissionError(f"unknown engine role: {role}") from exc


def load_engine_runtime_manifest(path: Path) -> EngineRuntimeManifest:
    """Load and byte-verify every build/runtime identity before use."""
    manifest_path = Path(path).resolve()
    try:
        raw = manifest_path.read_bytes()
        payload = json.loads(raw)
    except FileNotFoundError as exc:
        raise EngineAdmissionError(f"runtime manifest is missing: {manifest_path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineAdmissionError("runtime manifest is unreadable or invalid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _RUNTIME_KEYS:
        raise EngineAdmissionError("runtime manifest has unknown or missing fields")
    if payload["schema_version"] != 1:
        raise EngineAdmissionError("runtime manifest schema_version must be 1")
    runtime_id = _nonempty(payload["runtime_id"], "runtime_id")
    build_host = _exact_text_mapping(payload["build_host"], {"hostname", "os", "architecture"}, "build_host")
    gpu = _exact_text_mapping(payload["gpu"], {"name", "compute_capability", "uuid"}, "gpu")
    if gpu["name"] != "NVIDIA GeForce RTX 5080":
        raise EngineAdmissionError("runtime manifest GPU must be NVIDIA GeForce RTX 5080")
    if gpu["compute_capability"] != "12.0":
        raise EngineAdmissionError("runtime manifest GPU compute capability must be 12.0")
    return EngineRuntimeManifest(
        manifest_path, hashlib.sha256(raw).hexdigest(), runtime_id, build_host,
        gpu["name"], gpu["compute_capability"], gpu["uuid"],
        _verified_file(payload["driver"], "driver", version=True),
        _verified_file(payload["cuda_runtime"], "cuda_runtime", version=True),
        _verified_file(payload["tensorrt_python_wheel"], "tensorrt_python_wheel", version=True),
        _verified_file(payload["trtexec"], "trtexec", version=True),
        _verified_file(payload["onnx_python_wheel"], "onnx_python_wheel", version=True),
    )


def require_engine_manifest(path: Path, *, model_role: str) -> dict[str, object]:
    """Verify one published FP16 engine manifest and all referenced bytes."""
    if model_role not in _MODEL_IDS:
        raise EngineAdmissionError(f"unknown engine role: {model_role}")
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineAdmissionError(f"{model_role} engine manifest is missing or invalid") from exc
    required = {
        "schema_version", "model_id", "precision", "onnx", "engine",
        "runtime_manifest_sha256", "build_receipt", "fp16_calibration", "bindings",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise EngineAdmissionError(f"{model_role} engine manifest has unknown or missing fields")
    if payload["schema_version"] != 1 or payload["model_id"] != _MODEL_IDS[model_role] or payload["precision"] != "fp16":
        raise EngineAdmissionError(f"{model_role} engine manifest identity mismatch")
    _require_sha(payload["runtime_manifest_sha256"], "runtime_manifest_sha256")
    for field in ("onnx", "engine", "build_receipt"):
        _verified_file(payload[field], field, version=False)
    calibration = payload["fp16_calibration"]
    if not isinstance(calibration, dict) or set(calibration) != _FILE_KEYS | {"calibration_id"}:
        raise EngineAdmissionError("FP16 calibration has unknown or missing fields")
    _nonempty(calibration["calibration_id"], "fp16 calibration_id")
    _verified_file({key: calibration[key] for key in _FILE_KEYS}, "fp16 calibration", version=False)
    require_canonical_bindings(model_role, payload["bindings"])
    return payload


def require_canonical_bindings(role: str, bindings: object) -> None:
    """Reject dynamic, reordered, renamed, or semantically different bindings."""
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        raise EngineAdmissionError(f"{role} binding schema must be a sequence")
    normalized: list[dict[str, object]] = []
    for index, value in enumerate(bindings):
        if not isinstance(value, Mapping) or set(value) != {"name", "mode", "dtype", "shape", "semantic"}:
            raise EngineAdmissionError(f"{role} binding {index} has unknown or missing fields")
        shape = value["shape"]
        if not isinstance(shape, (list, tuple)) or not shape or any(type(item) is not int or item < 1 for item in shape):
            raise EngineAdmissionError(f"{role} binding {index} must have a fully static positive shape")
        normalized.append({
            "name": value["name"], "mode": value["mode"], "dtype": value["dtype"],
            "shape": list(shape), "semantic": value["semantic"],
        })
    if tuple(normalized) != _CANONICAL_BINDINGS.get(role):
        raise EngineAdmissionError(f"{role} binding schema mismatch")


def compare_fp32_fp16_evidence(
    fp32: Mapping[str, object],
    fp16: Mapping[str, object],
    *,
    expected_scene_count: int = 299,
) -> dict[str, object]:
    """Fail closed on unsafe FP16 drift while permitting score-value drift."""
    reference = _evidence_root(fp32, "fp32", expected_scene_count)
    candidate = _evidence_root(fp16, "fp16", expected_scene_count)
    if reference["calibration"] == candidate["calibration"]:
        raise EngineAdmissionError("FP16 candidate must use its own calibration")
    if reference["bindings_sha256"] != candidate["bindings_sha256"]:
        raise EngineAdmissionError("FP16 candidate binding mismatch")
    reference_scenes = reference["scenes"]
    candidate_scenes = candidate["scenes"]
    if [scene["scene_id"] for scene in reference_scenes] != [scene["scene_id"] for scene in candidate_scenes]:
        raise EngineAdmissionError("FP16 candidate scene identity/order mismatch")
    max_score_delta = 0.0
    max_box_delta = 0.0
    object_count = 0
    for ref_scene, cand_scene in zip(reference_scenes, candidate_scenes, strict=True):
        if ref_scene["provenance"] != cand_scene["provenance"]:
            raise EngineAdmissionError("FP16 candidate non-timing provenance mismatch")
        ref_objects = ref_scene["objects"]
        cand_objects = cand_scene["objects"]
        if len(ref_objects) != len(cand_objects):
            raise EngineAdmissionError("FP16 candidate object loss or duplication")
        for ref_obj, cand_obj in zip(ref_objects, cand_objects, strict=True):
            _validate_evidence_object(ref_obj, "FP32")
            _validate_evidence_object(cand_obj, "FP16")
            if ref_obj["object_id"] != cand_obj["object_id"]:
                raise EngineAdmissionError("FP16 candidate object identity/order mismatch")
            if ref_obj["ground_truth_sku"] != cand_obj["ground_truth_sku"]:
                raise EngineAdmissionError("FP16 candidate ground-truth identity mismatch")
            if ref_obj["top3"] != cand_obj["top3"]:
                raise EngineAdmissionError("FP16 candidate Top3 ordering mismatch")
            if cand_obj["auto_approved"] and cand_obj["decision"] != cand_obj["ground_truth_sku"]:
                raise EngineAdmissionError("FP16 candidate has a wrong auto approval")
            if len(ref_obj["raw_scores"]) != len(cand_obj["raw_scores"]):
                raise EngineAdmissionError("FP16 candidate raw score vector length mismatch")
            max_score_delta = max(max_score_delta, max(abs(a - b) for a, b in zip(ref_obj["raw_scores"], cand_obj["raw_scores"], strict=True)))
            max_box_delta = max(max_box_delta, max(abs(a - b) for a, b in zip(ref_obj["box"], cand_obj["box"], strict=True)))
            object_count += 1
    return {
        "schema_version": 1,
        "status": "admitted_fp16_parity",
        "scene_count": len(reference_scenes),
        "object_count": object_count,
        "max_abs_raw_score_delta": max_score_delta,
        "max_abs_box_delta": max_box_delta,
        "fp32_calibration": dict(reference["calibration"]),
        "fp16_calibration": dict(candidate["calibration"]),
    }


def _evidence_root(value: Mapping[str, object], precision: str, expected_scene_count: int) -> dict[str, object]:
    required = {"schema_version", "precision", "calibration", "bindings_sha256", "scenes"}
    if not isinstance(value, Mapping) or set(value) != required or value["schema_version"] != 1 or value["precision"] != precision:
        raise EngineAdmissionError(f"{precision} parity evidence schema mismatch")
    calibration = value["calibration"]
    if not isinstance(calibration, Mapping) or set(calibration) != {"calibration_id", "sha256"}:
        raise EngineAdmissionError(f"{precision} calibration identity is invalid")
    _nonempty(calibration["calibration_id"], f"{precision} calibration_id")
    _require_sha(calibration["sha256"], f"{precision} calibration sha256")
    _require_sha(value["bindings_sha256"], f"{precision} bindings_sha256")
    scenes = value["scenes"]
    if type(expected_scene_count) is not int or expected_scene_count < 1:
        raise EngineAdmissionError("expected_scene_count must be positive")
    if not isinstance(scenes, list) or len(scenes) != expected_scene_count:
        raise EngineAdmissionError(f"{precision} evidence must contain exactly {expected_scene_count} scenes")
    if any(not isinstance(scene, dict) or set(scene) != {"scene_id", "provenance", "objects"} for scene in scenes):
        raise EngineAdmissionError(f"{precision} scene evidence schema mismatch")
    if len({_nonempty(scene["scene_id"], f"{precision} scene_id") for scene in scenes}) != len(scenes):
        raise EngineAdmissionError(f"{precision} scene identities must be unique")
    if any(not isinstance(scene["provenance"], dict) or not scene["provenance"] or not isinstance(scene["objects"], list) for scene in scenes):
        raise EngineAdmissionError(f"{precision} scene evidence values are invalid")
    return dict(value)


def _validate_evidence_object(value: object, label: str) -> None:
    keys = {"object_id", "ground_truth_sku", "box", "raw_scores", "top3", "decision", "auto_approved"}
    if not isinstance(value, dict) or set(value) != keys:
        raise EngineAdmissionError(f"{label} object evidence schema mismatch")
    _nonempty(value["object_id"], f"{label} object_id")
    if type(value["ground_truth_sku"]) is not int or not 1 <= value["ground_truth_sku"] <= 20:
        raise EngineAdmissionError(f"{label} ground_truth_sku is invalid")
    if not isinstance(value["box"], list) or len(value["box"]) != 4 or not all(_finite_number(item) for item in value["box"]):
        raise EngineAdmissionError(f"{label} box contains non-finite or invalid values")
    if not isinstance(value["raw_scores"], list) or len(value["raw_scores"]) != 20 or not all(_finite_number(item) for item in value["raw_scores"]):
        raise EngineAdmissionError(f"{label} raw scores contain non-finite or invalid values")
    if not isinstance(value["top3"], list) or len(value["top3"]) != 3 or len(set(value["top3"])) != 3 or not all(type(item) is int and 1 <= item <= 20 for item in value["top3"]):
        raise EngineAdmissionError(f"{label} Top3 is invalid")
    decision = value["decision"]
    if decision != "Unknown" and (type(decision) is not int or not 1 <= decision <= 20):
        raise EngineAdmissionError(f"{label} decision is invalid")
    if type(value["auto_approved"]) is not bool or (value["auto_approved"] and decision == "Unknown"):
        raise EngineAdmissionError(f"{label} auto approval is invalid")


def _verified_file(value: object, name: str, *, version: bool) -> VerifiedFile:
    required = _VERSIONED_FILE_KEYS if version else _FILE_KEYS
    if not isinstance(value, Mapping) or set(value) != required:
        raise EngineAdmissionError(f"{name} file identity has unknown or missing fields")
    path_value = value["path"]
    if not isinstance(path_value, str) or not path_value:
        raise EngineAdmissionError(f"{name} path must be a non-empty absolute path")
    path = Path(path_value)
    if not path.is_absolute():
        raise EngineAdmissionError(f"{name} path must be absolute")
    path = path.resolve()
    expected_bytes = value["bytes"]
    if type(expected_bytes) is not int or expected_bytes < 1:
        raise EngineAdmissionError(f"{name} bytes must be a positive integer")
    expected_sha = _require_sha(value["sha256"], f"{name} sha256")
    try:
        actual_bytes = path.stat().st_size
        actual_sha = _sha256_file(path)
    except OSError as exc:
        raise EngineAdmissionError(f"{name} file is missing: {path}") from exc
    if actual_bytes != expected_bytes:
        raise EngineAdmissionError(f"{name} byte size mismatch")
    if actual_sha != expected_sha:
        raise EngineAdmissionError(f"{name} SHA-256 mismatch")
    version_value = _nonempty(value["version"], f"{name} version") if version else None
    return VerifiedFile(path, expected_bytes, expected_sha, version_value)


def _exact_text_mapping(value: object, keys: set[str], name: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EngineAdmissionError(f"{name} has unknown or missing fields")
    return {key: _nonempty(value[key], f"{name}.{key}") for key in sorted(keys)}


def _file_payload(value: VerifiedFile) -> dict[str, object]:
    payload: dict[str, object] = {"path": str(value.path), "bytes": value.bytes, "sha256": value.sha256}
    if value.version is not None:
        payload["version"] = value.version
    return payload


def _nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EngineAdmissionError(f"{name} must be a non-empty string")
    return value


def _require_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise EngineAdmissionError(f"{name} must be a lowercase SHA-256")
    return value


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "EngineAdmissionError", "EngineRuntimeManifest", "VerifiedFile",
    "canonical_engine_bindings", "compare_fp32_fp16_evidence",
    "load_engine_runtime_manifest", "require_canonical_bindings",
    "require_engine_manifest",
]
