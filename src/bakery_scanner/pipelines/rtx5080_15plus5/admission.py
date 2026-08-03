"""Fail-closed artifact, runtime, and TensorRT binding admission."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Callable, Literal, Mapping

from .config import CandidateConfig


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STORAGE = {"external", "git", "git-lfs", "github-release"}
_REQUIRED_KINDS = frozenset({"model", "onnx", "engine", "preprocessing", "support", "policy", "catalog", "calibration"})


class AdmissionError(ValueError):
    """Raised when the candidate cannot be safely admitted."""


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    device: Literal["cuda:0"]
    gpu_name: Literal["NVIDIA GeForce RTX 5080"]
    compute_capability: str
    driver_version: str
    cuda_version: str
    tensorrt_version: str


@dataclass(frozen=True, slots=True)
class ArtifactDeclaration:
    artifact_id: str
    kind: str
    local_path: PurePosixPath
    bytes: int
    sha256: str
    storage: str


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    artifact_id: str
    kind: str
    path: Path
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class EngineBinding:
    name: str
    mode: Literal["input", "output"]
    dtype: str
    shape: tuple[int, ...]
    semantic: str


_CANONICAL_ENGINE_BINDINGS = MappingProxyType({
    "rfdetr_engine": (EngineBinding("images", "input", "float16", (1, 3, 640, 640), "canonical_rgb"),),
    "repvit_engine": (EngineBinding("crops", "input", "float16", (14, 3, 224, 224), "repvit_crops"),),
    "dinov3_engine": (EngineBinding("crops", "input", "float16", (7, 3, 224, 224), "dinov3_crops"),),
})


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    pipeline_id: str
    artifacts: tuple[VerifiedArtifact, ...]
    runtime: RuntimeIdentity
    admitted: Literal[True]


@dataclass(frozen=True, slots=True)
class _AdmissionManifest:
    pipeline_id: str
    artifacts: tuple[ArtifactDeclaration, ...]
    runtime: RuntimeIdentity
    engines: Mapping[str, tuple[EngineBinding, ...]]


BindingInspector = Callable[[RuntimeIdentity], Mapping[str, tuple[Mapping[str, object], ...]]]


def admit_candidate(
    config: CandidateConfig,
    content_root: Path,
    runtime: RuntimeIdentity,
    *,
    inspect_bindings: BindingInspector | None = None,
) -> AdmissionReceipt:
    """Verify every identity before any engine session can be constructed."""
    if not isinstance(config, CandidateConfig):
        raise AdmissionError("candidate configuration is invalid")
    try:
        config.__post_init__()
    except ValueError as exc:
        raise AdmissionError("candidate configuration is noncanonical") from exc
    root = Path(content_root).resolve()
    if not root.is_dir():
        raise AdmissionError(f"content root is missing: {root}")
    manifest = _load_manifest(config.admission_manifest, root, config.pipeline_id)
    verified = tuple(verify_declared_artifact(root, item) for item in manifest.artifacts)
    require_runtime_match(manifest.runtime, runtime)
    if inspect_bindings is None:
        raise AdmissionError("TensorRT binding inspection is required; no fallback is available")
    try:
        observed = inspect_bindings(runtime)
    except AdmissionError:
        raise
    except Exception as exc:
        raise AdmissionError("TensorRT binding inspection failed") from exc
    require_exact_bindings(manifest.engines, observed)
    return AdmissionReceipt(config.pipeline_id, verified, runtime, admitted=True)


def verify_declared_artifact(content_root: Path, item: ArtifactDeclaration) -> VerifiedArtifact:
    root = Path(content_root).resolve()
    path = root.joinpath(*item.local_path.parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AdmissionError(f"{item.artifact_id}: artifact path escapes content_root") from exc
    if not path.is_file():
        raise AdmissionError(f"{item.artifact_id}: artifact is missing: {item.local_path}")
    actual_bytes = path.stat().st_size
    if actual_bytes != item.bytes:
        raise AdmissionError(f"{item.artifact_id}: byte size mismatch (expected {item.bytes}, got {actual_bytes})")
    actual_hash = _sha256_file(path)
    if actual_hash != item.sha256:
        raise AdmissionError(f"{item.artifact_id}: SHA-256 mismatch (expected {item.sha256}, got {actual_hash})")
    return VerifiedArtifact(item.artifact_id, item.kind, path, actual_bytes, actual_hash)


def require_runtime_match(expected: RuntimeIdentity, actual: RuntimeIdentity) -> None:
    _validate_runtime(expected, "declared runtime")
    _validate_runtime(actual, "active runtime")
    if expected != actual:
        raise AdmissionError("runtime identity mismatch")


def require_exact_bindings(
    expected: Mapping[str, tuple[EngineBinding, ...]],
    observed: Mapping[str, tuple[Mapping[str, object], ...]],
) -> None:
    if dict(expected) != dict(_CANONICAL_ENGINE_BINDINGS):
        raise AdmissionError("canonical engine binding schema mismatch")
    if not isinstance(observed, Mapping):
        raise AdmissionError("TensorRT binding inspection returned an invalid schema")
    normalized_observed: dict[str, tuple[EngineBinding, ...]] = {}
    try:
        for engine_id, bindings in observed.items():
            if not isinstance(engine_id, str) or not isinstance(bindings, tuple):
                raise AdmissionError("TensorRT binding inspection returned an invalid schema")
            normalized_observed[engine_id] = tuple(_binding(binding, f"observed {engine_id}") for binding in bindings)
    except AdmissionError:
        raise
    if dict(_CANONICAL_ENGINE_BINDINGS) != normalized_observed:
        raise AdmissionError("canonical engine binding schema mismatch")


def _load_manifest(path: Path, content_root: Path, pipeline_id: str) -> _AdmissionManifest:
    manifest_path = Path(path).resolve()
    try:
        manifest_path.relative_to(content_root)
    except ValueError as exc:
        raise AdmissionError("admission manifest must remain under content_root") from exc
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdmissionError(f"admission manifest is missing: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise AdmissionError("admission manifest is invalid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "pipeline_id", "artifacts", "runtime", "engines"}:
        raise AdmissionError("admission manifest has unknown or missing fields")
    if payload["schema_version"] != 1 or payload["pipeline_id"] != pipeline_id:
        raise AdmissionError("admission manifest identity mismatch")
    artifacts = _artifacts(payload["artifacts"])
    runtime = _runtime(payload["runtime"], "declared runtime")
    engines = _engines(payload["engines"], artifacts)
    return _AdmissionManifest(pipeline_id, artifacts, runtime, engines)


def _artifacts(value: object) -> tuple[ArtifactDeclaration, ...]:
    if not isinstance(value, list) or not value:
        raise AdmissionError("admission manifest artifacts must be a non-empty list")
    artifacts = tuple(sorted((_artifact(row) for row in value), key=lambda item: item.artifact_id))
    if len({item.artifact_id for item in artifacts}) != len(artifacts):
        raise AdmissionError("admission manifest artifact IDs must be unique")
    kinds = {item.kind for item in artifacts}
    if not _REQUIRED_KINDS.issubset(kinds):
        raise AdmissionError("admission manifest lacks required identity-bearing artifact kinds")
    return artifacts


def _artifact(value: object) -> ArtifactDeclaration:
    if not isinstance(value, dict) or set(value) != {"artifact_id", "kind", "local_path", "bytes", "sha256", "storage"}:
        raise AdmissionError("artifact declaration has unknown or missing fields")
    artifact_id = _text(value["artifact_id"], "artifact_id")
    kind = _text(value["kind"], f"{artifact_id}.kind")
    local_path = _relative_path(value["local_path"], artifact_id)
    size = value["bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise AdmissionError(f"{artifact_id}: bytes must be a non-negative integer")
    digest = value["sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise AdmissionError(f"{artifact_id}: sha256 must be a lowercase SHA-256 hash")
    storage = value["storage"]
    if storage not in _STORAGE:
        raise AdmissionError(f"{artifact_id}: unsupported storage class")
    return ArtifactDeclaration(artifact_id, kind, local_path, size, digest, storage)


def _runtime(value: object, name: str) -> RuntimeIdentity:
    if not isinstance(value, dict) or set(value) != {"device", "gpu_name", "compute_capability", "driver_version", "cuda_version", "tensorrt_version"}:
        raise AdmissionError(f"{name} has unknown or missing fields")
    runtime = RuntimeIdentity(
        device=value["device"], gpu_name=value["gpu_name"], compute_capability=value["compute_capability"],
        driver_version=value["driver_version"], cuda_version=value["cuda_version"], tensorrt_version=value["tensorrt_version"],
    )
    _validate_runtime(runtime, name)
    return runtime


def _validate_runtime(runtime: RuntimeIdentity, name: str) -> None:
    if not isinstance(runtime, RuntimeIdentity):
        raise AdmissionError(f"{name} is invalid")
    if runtime.device != "cuda:0" or runtime.gpu_name != "NVIDIA GeForce RTX 5080":
        raise AdmissionError(f"{name} GPU identity mismatch")
    for field in ("compute_capability", "driver_version", "cuda_version", "tensorrt_version"):
        _text(getattr(runtime, field), f"{name}.{field}")


def _engines(value: object, artifacts: tuple[ArtifactDeclaration, ...]) -> Mapping[str, tuple[EngineBinding, ...]]:
    if not isinstance(value, dict):
        raise AdmissionError("engines must be a mapping")
    engine_ids = {item.artifact_id for item in artifacts if item.kind == "engine"}
    canonical_engine_ids = set(_CANONICAL_ENGINE_BINDINGS)
    if engine_ids != canonical_engine_ids or set(value) != canonical_engine_ids:
        raise AdmissionError("canonical engine roles must be exactly RF-DETR, RepViT, and DINOv3")
    parsed: dict[str, tuple[EngineBinding, ...]] = {}
    for engine_id in sorted(engine_ids):
        raw_bindings = value[engine_id]
        if not isinstance(raw_bindings, list) or not raw_bindings:
            raise AdmissionError(f"{engine_id}: binding schema must be a non-empty list")
        bindings = tuple(_binding(item, engine_id) for item in raw_bindings)
        if len({binding.name for binding in bindings}) != len(bindings):
            raise AdmissionError(f"{engine_id}: binding names must be unique")
        parsed[engine_id] = bindings
    if parsed != dict(_CANONICAL_ENGINE_BINDINGS):
        raise AdmissionError("canonical engine binding schema mismatch")
    return MappingProxyType(parsed)


def _binding(value: object, name: str) -> EngineBinding:
    if not isinstance(value, Mapping) or set(value) != {"name", "mode", "dtype", "shape", "semantic"}:
        raise AdmissionError(f"{name}: binding has unknown or missing fields")
    binding_name = _text(value["name"], f"{name}.name")
    mode = value["mode"]
    if mode not in {"input", "output"}:
        raise AdmissionError(f"{name}.{binding_name}: binding mode must be input or output")
    dtype = _text(value["dtype"], f"{name}.{binding_name}.dtype")
    if dtype != "float16":
        raise AdmissionError(f"{name}.{binding_name}: candidate binding dtype must be float16")
    raw_shape = value["shape"]
    if not isinstance(raw_shape, (list, tuple)) or not raw_shape or any(not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1 for dimension in raw_shape):
        raise AdmissionError(f"{name}.{binding_name}: binding shape must be static positive integers")
    return EngineBinding(binding_name, mode, dtype, tuple(raw_shape), _text(value["semantic"], f"{name}.{binding_name}.semantic"))


def _relative_path(value: object, artifact_id: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise AdmissionError(f"{artifact_id}: local_path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise AdmissionError(f"{artifact_id}: local_path must be content-root-relative POSIX")
    return path


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdmissionError(f"{name} must be a non-empty string")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
