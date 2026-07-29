"""Immutable, spawn-safe messages for the CPU benchmark worker protocol."""

from __future__ import annotations

import math
import pickle
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Literal, Sequence

from .cpu_regression import ObjectRecord


BenchmarkMode = Literal["serial_reference", "batch_pytorch", "batch_pytorch_compile"]
WorkerRole = Literal["reference", "candidate"]
Profile = Literal["E", "M", "H"]

_MODES = frozenset(("serial_reference", "batch_pytorch", "batch_pytorch_compile"))
_ROLES = frozenset(("reference", "candidate"))
_PROFILES = frozenset(("E", "M", "H"))
_SAMPLE_PROFILES = frozenset(("all299", "batch2_e3_m3_h3"))
_COMPILE_MODELS = frozenset(("repvit", "dinov3"))


class ProtocolState(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING_PASS = "running_pass"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _require_exact_int(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise ValueError(f"{field} must be a {qualifier} integer")
    return value


def _require_finite_non_negative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite non-negative number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    if result < 0:
        raise ValueError(f"{field} must be non-negative")
    return result


def _normalize_key(value: object, field: str = "key") -> str:
    key = _require_string(value, field)
    path = PurePosixPath(key)
    if key != key.strip() or path.is_absolute() or not path.parts or any(
        part in {".", ".."} for part in path.parts
    ) or "\\" in key or path.as_posix() != key:
        raise ValueError(f"{field} must be a non-empty normalized image key")
    return key


def _freeze_protocol_value(value: object, field: str) -> object:
    """Normalize the protocol's deliberately small immutable value vocabulary."""
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field} protocol values must be finite")
        return value
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_protocol_value(item, field) for item in value)
    raise ValueError(
        f"{field} protocol values must be None, bool, int, float, str, or nested tuples"
    )


def _normalize_pairs(value: Sequence[tuple[str, object]], field: str) -> tuple[tuple[str, object], ...]:
    pairs: list[tuple[str, object]] = []
    for pair in value:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"{field} must contain key/value pairs")
        key = _require_string(pair[0], field)
        pairs.append((key, _freeze_protocol_value(pair[1], field)))
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError(f"{field} keys must be unique")
    return tuple(pairs)


def _require_pickle_safe(value: object, field: str) -> None:
    try:
        pickle.dumps(value)
    except (pickle.PickleError, TypeError, AttributeError) as exc:
        raise ValueError(f"{field} must be pickle-safe") from exc


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    role: WorkerRole
    mode: BenchmarkMode
    package_root: Path
    classifier_config: Path
    sample_profile: Literal["all299", "batch2_e3_m3_h3"]
    runtime_overrides: tuple[tuple[str, object], ...]
    expected_artifact_hashes: tuple[tuple[str, str], ...]
    warmup_repetitions: int = 2

    def __post_init__(self) -> None:
        if self.role not in _ROLES or self.mode not in _MODES:
            raise ValueError("role and mode must be recognized")
        if not isinstance(self.package_root, Path) or not isinstance(self.classifier_config, Path):
            raise ValueError("package_root and classifier_config must be Paths")
        if self.sample_profile not in _SAMPLE_PROFILES:
            raise ValueError("sample_profile must be recognized")
        if self.warmup_repetitions != 2:
            raise ValueError("warmup_repetitions must be exactly 2")
        object.__setattr__(self, "runtime_overrides", _normalize_pairs(self.runtime_overrides, "runtime_overrides"))
        hashes = _normalize_pairs(self.expected_artifact_hashes, "expected_artifact_hashes")
        if any(not isinstance(pair[1], str) or not pair[1] for pair in hashes):
            raise ValueError("expected_artifact_hashes must contain non-empty string hashes")
        object.__setattr__(self, "expected_artifact_hashes", hashes)
        _require_pickle_safe(self, "WorkerSpec")


@dataclass(frozen=True, slots=True)
class ResolvedRuntime:
    mode: BenchmarkMode
    device: Literal["CPU"]
    precision: Literal["FP32"]
    intra_op_threads: int
    inter_op_threads: int
    cpu_affinity: tuple[int, ...]
    repvit_microbatch_objects: int | Literal["all"]
    dinov3_microbatch_objects: int | Literal["all"]
    compile_models: tuple[Literal["repvit", "dinov3"], ...]

    def __post_init__(self) -> None:
        if self.mode not in _MODES or self.device != "CPU" or self.precision != "FP32":
            raise ValueError("resolved runtime must use CPU/FP32")
        _require_exact_int(self.intra_op_threads, "intra_op_threads", minimum=1)
        _require_exact_int(self.inter_op_threads, "inter_op_threads", minimum=1)
        affinity = tuple(self.cpu_affinity)
        if not affinity or len(set(affinity)) != len(affinity):
            raise ValueError("cpu_affinity must be non-empty and unique")
        for cpu in affinity:
            _require_exact_int(cpu, "cpu_affinity")
        object.__setattr__(self, "cpu_affinity", affinity)
        for field, value in (("repvit_microbatch_objects", self.repvit_microbatch_objects), ("dinov3_microbatch_objects", self.dinov3_microbatch_objects)):
            if value != "all":
                _require_exact_int(value, field, minimum=1)
        models = tuple(self.compile_models)
        if len(set(models)) != len(models) or any(model not in _COMPILE_MODELS for model in models):
            raise ValueError("compile_models must be unique recognized models")
        object.__setattr__(self, "compile_models", models)


@dataclass(frozen=True, slots=True)
class WorkerEnvironment:
    python_version: str
    pytorch_version: str
    torchvision_version: str
    numpy_version: str
    os_name: str
    os_version: str
    logical_cpu_count: int
    inherited_affinity: tuple[int, ...]
    filesystem_encoding: str
    default_encoding: str
    utf8_mode: int
    gc_enabled: bool

    def __post_init__(self) -> None:
        for field in ("python_version", "pytorch_version", "torchvision_version", "numpy_version", "os_name", "os_version", "filesystem_encoding", "default_encoding"):
            _require_string(getattr(self, field), field)
        _require_exact_int(self.logical_cpu_count, "logical_cpu_count", minimum=1)
        affinity = tuple(self.inherited_affinity)
        for cpu in affinity:
            _require_exact_int(cpu, "inherited_affinity")
        object.__setattr__(self, "inherited_affinity", affinity)
        _require_exact_int(self.utf8_mode, "utf8_mode")
        if type(self.gc_enabled) is not bool:
            raise ValueError("gc_enabled must be a boolean")


@dataclass(frozen=True, slots=True)
class WarmupStageCounts:
    canonical: int
    detector: int
    repvit: int
    dinov3_global_local: int
    fusion: int

    def __post_init__(self) -> None:
        for field in ("canonical", "detector", "repvit", "dinov3_global_local", "fusion"):
            _require_exact_int(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class WarmupImageEvidence:
    key: str
    profile: Profile
    repetition: int
    started_at_utc: str
    completed_at_utc: str
    stage_counts: WarmupStageCounts

    def __post_init__(self) -> None:
        _normalize_key(self.key)
        if self.profile not in _PROFILES:
            raise ValueError("profile must be E, M, or H")
        _require_exact_int(self.repetition, "repetition", minimum=1)
        if self.repetition > 2:
            raise ValueError("repetition must be between 1 and 2")
        _require_string(self.started_at_utc, "started_at_utc")
        _require_string(self.completed_at_utc, "completed_at_utc")
        if not isinstance(self.stage_counts, WarmupStageCounts):
            raise ValueError("stage_counts must be WarmupStageCounts")


@dataclass(frozen=True, slots=True)
class WarmupEvidence:
    repetitions: int
    images: tuple[WarmupImageEvidence, ...]

    def __post_init__(self) -> None:
        if self.repetitions != 2:
            raise ValueError("repetitions must be exactly 2")
        images = tuple(self.images)
        if any(not isinstance(image, WarmupImageEvidence) for image in images):
            raise ValueError("images must contain WarmupImageEvidence")
        object.__setattr__(self, "images", images)


@dataclass(frozen=True, slots=True)
class WorkerMetadata:
    role: WorkerRole
    pid: int
    resolved_runtime: ResolvedRuntime
    environment: WorkerEnvironment
    detector_metadata: tuple[tuple[str, object], ...]
    artifact_hashes: tuple[tuple[str, str], ...]
    warmup: WarmupEvidence
    stderr_path: Path

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise ValueError("role must be recognized")
        _require_exact_int(self.pid, "pid", minimum=1)
        if not isinstance(self.resolved_runtime, ResolvedRuntime) or not isinstance(self.environment, WorkerEnvironment) or not isinstance(self.warmup, WarmupEvidence) or not isinstance(self.stderr_path, Path):
            raise ValueError("worker metadata contains invalid values")
        object.__setattr__(self, "detector_metadata", _normalize_pairs(self.detector_metadata, "detector_metadata"))
        hashes = _normalize_pairs(self.artifact_hashes, "artifact_hashes")
        if any(not isinstance(pair[1], str) or not pair[1] for pair in hashes):
            raise ValueError("artifact_hashes must contain non-empty string hashes")
        object.__setattr__(self, "artifact_hashes", hashes)
        _require_pickle_safe(self, "WorkerMetadata")


@dataclass(frozen=True, slots=True)
class BenchmarkImageRow:
    key: str
    profile: Profile
    object_count: int
    total_ms: float
    records: tuple[ObjectRecord, ...]
    canonical_ms: float
    detector_ms: float
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    dino_object_count: int
    registered_count: int
    unknown_count: int

    def __post_init__(self) -> None:
        _normalize_key(self.key)
        if self.profile not in _PROFILES:
            raise ValueError("profile must be E, M, or H")
        _require_exact_int(self.object_count, "object_count")
        records = tuple(self.records)
        if any(not isinstance(record, ObjectRecord) for record in records):
            raise ValueError("records must contain ObjectRecord values")
        if self.object_count != len(records):
            raise ValueError("object_count must equal the number of records")
        object.__setattr__(self, "records", records)
        for field in ("total_ms", "canonical_ms", "detector_ms", "crop_ms", "repvit_ms", "dinov3_ms", "fusion_ms"):
            _require_finite_non_negative(getattr(self, field), field)
        _require_exact_int(self.dino_object_count, "dino_object_count")
        if self.dino_object_count > len(records):
            raise ValueError("DINO object count must not exceed records")
        _require_exact_int(self.registered_count, "registered_count")
        _require_exact_int(self.unknown_count, "unknown_count")
        if self.registered_count + self.unknown_count != len(records):
            raise ValueError("decision counts must equal the number of records")


@dataclass(frozen=True, slots=True)
class PrepareCommand:
    spec: WorkerSpec

    def __post_init__(self) -> None:
        if not isinstance(self.spec, WorkerSpec):
            raise ValueError("spec must be WorkerSpec")


@dataclass(frozen=True, slots=True)
class RunPassCommand:
    pass_index: int
    image_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_exact_int(self.pass_index, "pass_index")
        keys = tuple(self.image_keys)
        if not keys:
            raise ValueError("image_keys must be non-empty")
        normalized = tuple(_normalize_key(key, "image_keys") for key in keys)
        if len(set(normalized)) != len(normalized):
            raise ValueError("image_keys must be unique")
        object.__setattr__(self, "image_keys", normalized)


@dataclass(frozen=True, slots=True)
class ShutdownCommand:
    pass


@dataclass(frozen=True, slots=True)
class ReadyMessage:
    metadata: WorkerMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, WorkerMetadata):
            raise ValueError("metadata must be WorkerMetadata")


@dataclass(frozen=True, slots=True)
class PassResult:
    role: WorkerRole
    worker_pid: int
    pass_index: int
    rows: tuple[BenchmarkImageRow, ...]

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise ValueError("role must be recognized")
        _require_exact_int(self.worker_pid, "worker_pid", minimum=1)
        _require_exact_int(self.pass_index, "pass_index")
        rows = tuple(self.rows)
        if any(not isinstance(row, BenchmarkImageRow) for row in rows):
            raise ValueError("rows must contain BenchmarkImageRow values")
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True, slots=True)
class PassResultMessage:
    result: PassResult

    def __post_init__(self) -> None:
        if not isinstance(self.result, PassResult):
            raise ValueError("result must be PassResult")


@dataclass(frozen=True, slots=True)
class StoppedMessage:
    role: WorkerRole
    pid: int

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise ValueError("role must be recognized")
        _require_exact_int(self.pid, "pid", minimum=1)


@dataclass(frozen=True, slots=True)
class WorkerError:
    exception_type: str
    message: str
    role: WorkerRole | None
    pid: int
    protocol_state: ProtocolState
    pass_index: int | None
    stderr_path: Path | None

    def __post_init__(self) -> None:
        _require_string(self.exception_type, "exception_type")
        _require_string(self.message, "message")
        if self.role is not None and self.role not in _ROLES:
            raise ValueError("role must be recognized")
        _require_exact_int(self.pid, "pid", minimum=1)
        if not isinstance(self.protocol_state, ProtocolState):
            raise ValueError("protocol_state must be ProtocolState")
        if self.pass_index is not None:
            _require_exact_int(self.pass_index, "pass_index")
        if self.stderr_path is not None and not isinstance(self.stderr_path, Path):
            raise ValueError("stderr_path must be a Path or None")


@dataclass(frozen=True, slots=True)
class ErrorMessage:
    error: WorkerError

    def __post_init__(self) -> None:
        if not isinstance(self.error, WorkerError):
            raise ValueError("error must be WorkerError")
