"""Fail-closed path-aware RTX 5080 latency evidence and acceptance."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from types import MappingProxyType
from typing import Literal


GROUPS = ("E", "M", "H")
REQUIRED_SLICES = (
    "E",
    "M",
    "H",
    "overall",
    "dinov3",
    "needs_retake",
    "unknown",
    "count_1_2",
    "count_3_7",
    "count_8_plus",
)
MINIMUM_SAMPLES = MappingProxyType(
    {slice_name: (3000 if slice_name == "overall" else 1000) for slice_name in REQUIRED_SLICES}
)
STAGES = (
    "decode_canonical",
    "detector",
    "completeness",
    "crop",
    "repvit",
    "direct_gate",
    "dinov3",
    "fusion_payload",
    "total",
)
THERMAL_FIELDS = frozenset(
    {
        "gpu_temperature_c",
        "gpu_clock_mhz",
        "memory_clock_mhz",
        "power_w",
        "thermal_throttled",
    }
)
RUNTIME_FIELDS = frozenset(
    {
        "device",
        "gpu_name",
        "compute_capability",
        "driver_version",
        "cuda_version",
        "tensorrt_version",
        "windows_build",
        "wddm_version",
        "runtime_manifest_sha256",
        "fallback_reason",
    }
)
REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "rfdetr_engine",
        "repvit_engine",
        "dinov3_engine",
        "detector_calibration",
        "repvit_prototype",
        "dinov3_support",
        "dinov3_local_bank",
        "preprocess",
        "fusion_policy",
        "catalog",
        "code",
        "admission_receipt",
    }
)
_EVIDENCE_KINDS = frozenset(
    {"current_quality", "observed_path_performance", "forced_path_performance"}
)
_LOWER_HEX = frozenset("0123456789abcdef")
_BOOTSTRAP_SEED = 20260803
_BOOTSTRAP_ITERATIONS = 2000
_EXPECTED_PROTOCOL = {
    "bootstrap": {
        "confidence": 0.95,
        "iterations": 2000,
        "seed": 20260803,
        "statistic": "nearest_rank_p95",
    },
    "device": {
        "cuda_device": "cuda:0",
        "gpu_name": "NVIDIA GeForce RTX 5080",
        "thermal_throttling_allowed": False,
    },
    "forced_count_evidence": {
        "count_1_2": "forced_path_performance",
        "count_8_plus": "forced_path_performance",
        "quality_eligible": False,
        "source": "current_crop_identities_only",
    },
    "latency_boundary": (
        "encoded_jpeg_bytes_in_worker_memory_to_validated_in_memory_result_payload"
    ),
    "minimum_warmups": 20,
    "required_slices": dict(MINIMUM_SAMPLES),
    "sample_order": (
        "warmup_then_group_E_M_H_and_path_ids_in_canonical_sorted_repeat_order"
    ),
    "schema_version": 3,
    "stages": list(STAGES),
    "total_p95_limit_ms": 100.0,
}


def canonical_sha256(value: object) -> str:
    """Hash one JSON-compatible identity with strict canonical encoding."""
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("identity must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_protocol(value: Mapping[str, object]) -> dict[str, object]:
    """Require the reviewed schema-v3 performance protocol without drift."""
    if not isinstance(value, Mapping) or dict(value) != _EXPECTED_PROTOCOL:
        raise ValueError("RTX 5080 performance protocol is noncanonical")
    return json.loads(json.dumps(_EXPECTED_PROTOCOL))


@dataclass(frozen=True, slots=True)
class PerformanceSample:
    """One warmed, validated in-memory worker-boundary observation."""

    schema_version: Literal[3]
    request_id: str
    image_id: str
    group: Literal["E", "M", "H"]
    evidence_kind: str
    quality_eligible: bool
    input_sha256: str
    source_crop_sha256s: tuple[str, ...]
    object_count: int
    dino_object_count: int
    dino_executed: bool
    needs_retake: bool
    unknown: bool
    warmed: bool
    runtime_identity_sha256: str
    artifact_identity_sha256: str
    quality_receipt_sha256: str
    protocol_sha256: str
    fallback_reason: str | None
    thermal: Mapping[str, object]
    timings_ms: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.schema_version != 3:
            raise ValueError("performance sample schema_version must be 3")
        _text(self.request_id, "request_id")
        _text(self.image_id, "image_id")
        if self.group not in GROUPS:
            raise ValueError("sample group must be E, M, or H")
        if self.evidence_kind not in _EVIDENCE_KINDS:
            raise ValueError("sample evidence_kind is invalid")
        if type(self.quality_eligible) is not bool:
            raise ValueError("quality_eligible must be boolean")
        if self.evidence_kind == "current_quality" and not self.quality_eligible:
            raise ValueError("current_quality evidence must be quality eligible")
        if self.evidence_kind != "current_quality" and self.quality_eligible:
            raise ValueError("performance-only evidence must not be quality eligible")
        for value, label in (
            (self.input_sha256, "input_sha256"),
            (self.runtime_identity_sha256, "runtime_identity_sha256"),
            (self.artifact_identity_sha256, "artifact_identity_sha256"),
            (self.quality_receipt_sha256, "quality_receipt_sha256"),
            (self.protocol_sha256, "protocol_sha256"),
        ):
            _sha256(value, label)
        if not isinstance(self.source_crop_sha256s, tuple):
            raise ValueError("source_crop_sha256s must be an immutable tuple")
        for digest in self.source_crop_sha256s:
            _sha256(digest, "source crop identity")
        _non_negative_int(self.object_count, "object_count")
        _non_negative_int(self.dino_object_count, "dino_object_count")
        if self.dino_object_count > self.object_count:
            raise ValueError("dino_object_count must not exceed object_count")
        for value, label in (
            (self.dino_executed, "dino_executed"),
            (self.needs_retake, "needs_retake"),
            (self.unknown, "unknown"),
            (self.warmed, "warmed"),
        ):
            if type(value) is not bool:
                raise ValueError(f"{label} must be boolean")
        if not self.warmed:
            raise ValueError("performance samples must be warmed")
        if self.dino_executed != (self.dino_object_count > 0):
            raise ValueError("DINO flag and object count disagree")
        if self.needs_retake and (self.dino_executed or self.unknown):
            raise ValueError("needs_retake cannot claim classification paths")
        if self.unknown and not self.dino_executed:
            raise ValueError("Unknown path requires DINO evidence")
        if self.fallback_reason is not None:
            raise ValueError("performance evidence rejects fallback")
        thermal = _validated_thermal(self.thermal)
        timings = _validated_timings(self.timings_ms)
        object.__setattr__(self, "thermal", MappingProxyType(thermal))
        object.__setattr__(self, "timings_ms", MappingProxyType(timings))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PerformanceSample":
        fields = frozenset(cls.__dataclass_fields__)
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("performance sample schema is invalid")
        source_crops = value["source_crop_sha256s"]
        if not isinstance(source_crops, list):
            raise ValueError("source_crop_sha256s JSON value must be a list")
        thermal = value["thermal"]
        timings = value["timings_ms"]
        if not isinstance(thermal, Mapping) or not isinstance(timings, Mapping):
            raise ValueError("thermal and timings_ms must be objects")
        return cls(
            schema_version=value["schema_version"],  # type: ignore[arg-type]
            request_id=value["request_id"],  # type: ignore[arg-type]
            image_id=value["image_id"],  # type: ignore[arg-type]
            group=value["group"],  # type: ignore[arg-type]
            evidence_kind=value["evidence_kind"],  # type: ignore[arg-type]
            quality_eligible=value["quality_eligible"],  # type: ignore[arg-type]
            input_sha256=value["input_sha256"],  # type: ignore[arg-type]
            source_crop_sha256s=tuple(source_crops),  # type: ignore[arg-type]
            object_count=value["object_count"],  # type: ignore[arg-type]
            dino_object_count=value["dino_object_count"],  # type: ignore[arg-type]
            dino_executed=value["dino_executed"],  # type: ignore[arg-type]
            needs_retake=value["needs_retake"],  # type: ignore[arg-type]
            unknown=value["unknown"],  # type: ignore[arg-type]
            warmed=value["warmed"],  # type: ignore[arg-type]
            runtime_identity_sha256=value["runtime_identity_sha256"],  # type: ignore[arg-type]
            artifact_identity_sha256=value["artifact_identity_sha256"],  # type: ignore[arg-type]
            quality_receipt_sha256=value["quality_receipt_sha256"],  # type: ignore[arg-type]
            protocol_sha256=value["protocol_sha256"],  # type: ignore[arg-type]
            fallback_reason=value["fallback_reason"],  # type: ignore[arg-type]
            thermal=thermal,
            timings_ms=timings,  # type: ignore[arg-type]
        )

    def belongs_to(self, slice_name: str) -> bool:
        """Return membership in a named acceptance slice."""
        current = self.evidence_kind == "current_quality"
        if slice_name in GROUPS:
            return current and self.group == slice_name
        if slice_name == "overall":
            return current
        if slice_name == "dinov3":
            return self.dino_executed
        if slice_name == "needs_retake":
            return self.needs_retake
        if slice_name == "unknown":
            return self.unknown
        if slice_name == "count_1_2":
            return 1 <= self.object_count <= 2
        if slice_name == "count_3_7":
            return current and 3 <= self.object_count <= 7
        if slice_name == "count_8_plus":
            return self.object_count >= 8
        raise ValueError(f"unknown performance slice: {slice_name}")

    def to_payload(self) -> dict[str, object]:
        return {
            field: (
                list(value)
                if field == "source_crop_sha256s"
                else dict(value)
                if field in {"thermal", "timings_ms"}
                else value
            )
            for field, value in ((name, getattr(self, name)) for name in self.__dataclass_fields__)
        }


@dataclass(frozen=True, slots=True)
class ExecutionRecordIndexArtifact:
    """Hash-admitted immutable external execution-record index artifact."""

    artifact_id: Literal["rtx5080_actual_path_execution_index_v1"]
    path: Path
    bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if self.artifact_id != "rtx5080_actual_path_execution_index_v1":
            raise ValueError("execution index artifact identity is invalid")
        if not isinstance(self.path, Path) or self.path == Path("."):
            raise ValueError("execution index artifact path is invalid")
        if type(self.bytes) is not int or self.bytes < 1:
            raise ValueError("execution index artifact bytes must be positive")
        _sha256(self.sha256, "execution index artifact SHA-256")


@dataclass(frozen=True, slots=True)
class _ActualExecutionRecord:
    scene_id: str
    input_sha256: str
    execution_receipt_content_sha256: str
    quality_receipt_content_sha256: str
    state: Literal["accepted_scan", "needs_retake"]
    dino_executed: bool
    dino_object_count: int
    needs_retake: bool
    unknown: bool
    unknown_total: int
    record_payload_sha256: str

    def __post_init__(self) -> None:
        _text(self.scene_id, "actual path scene_id")
        for value, label in (
            (self.input_sha256, "actual path input_sha256"),
            (
                self.execution_receipt_content_sha256,
                "actual path execution receipt content identity",
            ),
            (
                self.quality_receipt_content_sha256,
                "actual path quality receipt content identity",
            ),
            (self.record_payload_sha256, "actual path record hash"),
        ):
            _sha256(value, label)
        if self.state not in {"accepted_scan", "needs_retake"}:
            raise ValueError("actual path state is invalid")
        for value, label in (
            (self.dino_executed, "dino_executed"),
            (self.needs_retake, "needs_retake"),
            (self.unknown, "unknown"),
        ):
            if type(value) is not bool:
                raise ValueError(f"actual path {label} must be boolean")
        _non_negative_int(self.dino_object_count, "actual path dino_object_count")
        _non_negative_int(self.unknown_total, "actual path unknown_total")
        if self.dino_executed != (self.dino_object_count > 0):
            raise ValueError("actual path DINO flag and object count disagree")
        if self.needs_retake != (self.state == "needs_retake"):
            raise ValueError("actual path retake flag and state disagree")
        if self.unknown != (self.unknown_total > 0):
            raise ValueError("actual path Unknown flag and total disagree")
        if self.needs_retake and (self.dino_executed or self.unknown):
            raise ValueError("actual needs_retake evidence cannot claim classification paths")
        if self.unknown and (not self.dino_executed or self.state != "accepted_scan"):
            raise ValueError("actual Unknown evidence requires accepted DINO execution")
        if self.dino_executed and self.state != "accepted_scan":
            raise ValueError("actual DINO evidence requires accepted_scan state")
        if self.record_payload_sha256 != canonical_sha256(self._identity_payload()):
            raise ValueError("actual path record hash does not match canonical evidence")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "_ActualExecutionRecord":
        if not isinstance(value, Mapping) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("actual execution evidence record schema is invalid")
        return cls(**dict(value))  # type: ignore[arg-type]

    def _identity_payload(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "record_payload_sha256"
        }


@dataclass(frozen=True, slots=True)
class BenchmarkScheduleItem:
    ordinal: int
    scene_id: str
    group: Literal["E", "M", "H"]
    slice_name: str
    warmup: bool


@dataclass(frozen=True, slots=True)
class PerformanceReceipt:
    schema_version: Literal[3]
    status: Literal["performance-passed", "performance-rejected"]
    runtime_identity: Mapping[str, object]
    runtime_identity_sha256: str
    artifact_identities: Mapping[str, str]
    artifact_identity_sha256: str
    quality_receipt_sha256: str
    protocol_sha256: str
    bootstrap_seed: int
    summaries: Mapping[str, object]
    violations: tuple[str, ...]
    sample_count: int
    samples_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != 3:
            raise ValueError("performance receipt schema_version must be 3")
        if self.status not in {"performance-passed", "performance-rejected"}:
            raise ValueError("performance receipt status is invalid")
        _validate_runtime_identity(self.runtime_identity)
        _validate_artifacts(self.artifact_identities)
        for value, label in (
            (self.runtime_identity_sha256, "runtime_identity_sha256"),
            (self.artifact_identity_sha256, "artifact_identity_sha256"),
            (self.quality_receipt_sha256, "quality_receipt_sha256"),
            (self.protocol_sha256, "protocol_sha256"),
            (self.samples_sha256, "samples_sha256"),
            (self.receipt_sha256, "receipt_sha256"),
        ):
            _sha256(value, label)
        if self.runtime_identity_sha256 != canonical_sha256(dict(self.runtime_identity)):
            raise ValueError("runtime identity hash does not match")
        if self.artifact_identity_sha256 != canonical_sha256(dict(self.artifact_identities)):
            raise ValueError("artifact identity hash does not match")
        if self.bootstrap_seed != _BOOTSTRAP_SEED:
            raise ValueError("performance receipt bootstrap seed is invalid")
        _non_negative_int(self.sample_count, "sample_count")
        if set(self.summaries) != set(REQUIRED_SLICES):
            raise ValueError("performance receipt summaries are incomplete")
        if self.status == "performance-passed" and self.violations:
            raise ValueError("performance-passed receipt cannot contain violations")
        if self.status == "performance-rejected" and not self.violations:
            raise ValueError("performance-rejected receipt requires violations")
        identity_payload = {
            "schema_version": self.schema_version,
            "status": self.status,
            "runtime_identity": _thaw(self.runtime_identity),
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "artifact_identities": _thaw(self.artifact_identities),
            "artifact_identity_sha256": self.artifact_identity_sha256,
            "quality_receipt_sha256": self.quality_receipt_sha256,
            "protocol_sha256": self.protocol_sha256,
            "bootstrap_seed": self.bootstrap_seed,
            "summaries": _thaw(self.summaries),
            "violations": list(self.violations),
            "sample_count": self.sample_count,
            "samples_sha256": self.samples_sha256,
        }
        if self.receipt_sha256 != canonical_sha256(identity_payload):
            raise ValueError("performance receipt hash does not match its payload")
        object.__setattr__(self, "runtime_identity", _freeze(self.runtime_identity))
        object.__setattr__(self, "artifact_identities", _freeze(self.artifact_identities))
        object.__setattr__(self, "summaries", _freeze(self.summaries))

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "runtime_identity": _thaw(self.runtime_identity),
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "artifact_identities": _thaw(self.artifact_identities),
            "artifact_identity_sha256": self.artifact_identity_sha256,
            "quality_receipt_sha256": self.quality_receipt_sha256,
            "protocol_sha256": self.protocol_sha256,
            "bootstrap_seed": self.bootstrap_seed,
            "summaries": _thaw(self.summaries),
            "violations": list(self.violations),
            "sample_count": self.sample_count,
            "samples_sha256": self.samples_sha256,
            "receipt_sha256": self.receipt_sha256,
        }


def summarize_latency_ms(
    values: Iterable[float],
    *,
    seed: int = _BOOTSTRAP_SEED,
    bootstrap_iterations: int = _BOOTSTRAP_ITERATIONS,
) -> dict[str, object]:
    """Return nearest-rank statistics and a deterministic empirical-bootstrap CI."""
    ordered = sorted(_finite_non_negative(value, "latency") for value in values)
    if not ordered:
        raise ValueError("latency values must not be empty")
    if type(seed) is not int or type(bootstrap_iterations) is not int or bootstrap_iterations < 100:
        raise ValueError("bootstrap configuration is invalid")
    bootstrap = _bootstrap_p95_order_statistics(
        ordered, seed=seed, iterations=bootstrap_iterations
    )
    return {
        "count": len(ordered),
        "p50": _nearest_rank(ordered, 0.50),
        "p90": _nearest_rank(ordered, 0.90),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
        "p95_bootstrap_ci95_ms": (
            _nearest_rank(bootstrap, 0.025),
            _nearest_rank(bootstrap, 0.975),
        ),
    }


def build_performance_receipt(
    samples: Sequence[PerformanceSample | Mapping[str, object]],
    runtime_identity: Mapping[str, object],
    artifact_identities: Mapping[str, str],
    *,
    quality_receipt_sha256: str,
    protocol_sha256: str,
    allowed_current_crop_sha256s: Iterable[str],
) -> PerformanceReceipt:
    """Validate all warmed observations and enforce every 100 ms hard slice."""
    runtime = _validate_runtime_identity(runtime_identity)
    artifacts = _validate_artifacts(artifact_identities)
    _sha256(quality_receipt_sha256, "quality_receipt_sha256")
    _sha256(protocol_sha256, "protocol_sha256")
    runtime_sha = canonical_sha256(runtime)
    artifact_sha = canonical_sha256(artifacts)
    allowed_crops = frozenset(allowed_current_crop_sha256s)
    for digest in allowed_crops:
        _sha256(digest, "allowed current crop identity")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError("performance samples must be a sequence")
    normalized = tuple(
        row if isinstance(row, PerformanceSample) else PerformanceSample.from_mapping(row)
        for row in samples
    )
    if not normalized:
        raise ValueError("performance samples must not be empty")
    request_ids = tuple(row.request_id for row in normalized)
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("performance request IDs must be unique")
    for row in normalized:
        row.__post_init__()
        if row.runtime_identity_sha256 != runtime_sha:
            raise ValueError("sample runtime identity changed mid-run")
        if row.artifact_identity_sha256 != artifact_sha:
            raise ValueError("sample artifact identity changed mid-run")
        if row.quality_receipt_sha256 != quality_receipt_sha256:
            raise ValueError("sample quality receipt identity changed mid-run")
        if row.protocol_sha256 != protocol_sha256:
            raise ValueError("sample protocol identity changed mid-run")
        if 1 <= row.object_count <= 2 or row.object_count >= 8:
            if row.evidence_kind != "forced_path_performance" or row.quality_eligible:
                raise ValueError("outer count evidence must be forced performance-only")
            if len(row.source_crop_sha256s) != row.object_count:
                raise ValueError("forced count fixture must bind every source crop")
            if not set(row.source_crop_sha256s).issubset(allowed_crops):
                raise ValueError("forced count fixture must use current crop identities")

    summaries: dict[str, object] = {}
    violations: list[str] = []
    for position, slice_name in enumerate(REQUIRED_SLICES):
        rows = tuple(row for row in normalized if row.belongs_to(slice_name))
        required = MINIMUM_SAMPLES[slice_name]
        if len(rows) < required:
            raise ValueError(f"{slice_name} requires {required} warmed samples")
        timing_summaries = {
            stage: summarize_latency_ms(
                (row.timings_ms[stage] for row in rows),
                seed=_BOOTSTRAP_SEED + position * 100 + STAGES.index(stage),
            )
            for stage in STAGES
        }
        evidence_kinds = sorted({row.evidence_kind for row in rows})
        summary = {
            "sample_count": len(rows),
            "evidence_kind": evidence_kinds[0] if len(evidence_kinds) == 1 else "mixed",
            "quality_eligible": all(row.quality_eligible for row in rows),
            "timings_ms": timing_summaries,
            "object_count": _count_range(rows),
            "dino_execution_rate": sum(row.dino_executed for row in rows) / len(rows),
        }
        summaries[slice_name] = summary
        p95 = timing_summaries["total"]["p95"]
        assert isinstance(p95, float)
        if p95 > 100.0:
            violations.append(f"{slice_name}:p95_ms={p95:g}")

    sample_payload = [row.to_payload() for row in normalized]
    samples_sha = canonical_sha256(sample_payload)
    base = {
        "schema_version": 3,
        "status": "performance-rejected" if violations else "performance-passed",
        "runtime_identity": runtime,
        "runtime_identity_sha256": runtime_sha,
        "artifact_identities": artifacts,
        "artifact_identity_sha256": artifact_sha,
        "quality_receipt_sha256": quality_receipt_sha256,
        "protocol_sha256": protocol_sha256,
        "bootstrap_seed": _BOOTSTRAP_SEED,
        "summaries": summaries,
        "violations": violations,
        "sample_count": len(normalized),
        "samples_sha256": samples_sha,
    }
    receipt_sha = canonical_sha256(base)
    return PerformanceReceipt(
        schema_version=3,
        status=base["status"],  # type: ignore[arg-type]
        runtime_identity=runtime,
        runtime_identity_sha256=runtime_sha,
        artifact_identities=artifacts,
        artifact_identity_sha256=artifact_sha,
        quality_receipt_sha256=quality_receipt_sha256,
        protocol_sha256=protocol_sha256,
        bootstrap_seed=_BOOTSTRAP_SEED,
        summaries=summaries,
        violations=tuple(violations),
        sample_count=len(normalized),
        samples_sha256=samples_sha,
        receipt_sha256=receipt_sha,
    )


def _read_execution_index_bytes(artifact: ExecutionRecordIndexArtifact) -> bytes:
    artifact.__post_init__()
    path = artifact.path.resolve()
    if artifact.path.is_symlink() or not path.is_file():
        raise ValueError("execution index artifact must be a regular immutable file")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("execution index artifact changed while reading")
    return raw


def _load_execution_index(
    artifact: ExecutionRecordIndexArtifact,
    loader: Callable[[ExecutionRecordIndexArtifact], bytes],
    *,
    execution_receipt_sha256: str,
    quality_receipt_sha256: str,
) -> tuple[_ActualExecutionRecord, ...]:
    if not isinstance(artifact, ExecutionRecordIndexArtifact):
        raise ValueError("hash-admitted execution index artifact is required")
    artifact.__post_init__()
    if not callable(loader):
        raise ValueError("verified execution index loader is required")
    raw = loader(artifact)
    if not isinstance(raw, bytes):
        raise ValueError("execution index loader must return immutable bytes")
    if len(raw) != artifact.bytes:
        raise ValueError("execution index artifact byte size mismatch")
    if hashlib.sha256(raw).hexdigest() != artifact.sha256:
        raise ValueError("execution index artifact SHA-256 mismatch")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("execution index artifact is invalid JSON") from exc
    if not isinstance(value, Mapping) or canonical_sha256(value) != artifact.sha256:
        raise ValueError("execution index artifact payload identity mismatch")
    if json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") != raw:
        raise ValueError("execution index artifact bytes must be canonical JSON")
    expected_keys = {
        "schema_version",
        "artifact_id",
        "execution_receipt_content_sha256",
        "quality_receipt_content_sha256",
        "records",
        "records_payload_sha256",
        "index_payload_sha256",
    }
    if set(value) != expected_keys or value["schema_version"] != 3:
        raise ValueError("execution index artifact schema is invalid")
    if value["artifact_id"] != artifact.artifact_id:
        raise ValueError("execution index artifact ID mismatch")
    for field in (
        "execution_receipt_content_sha256",
        "quality_receipt_content_sha256",
        "records_payload_sha256",
        "index_payload_sha256",
    ):
        _sha256(value[field], f"execution index {field}")
    if value["execution_receipt_content_sha256"] != execution_receipt_sha256:
        raise ValueError("execution receipt identity mismatch")
    if value["quality_receipt_content_sha256"] != quality_receipt_sha256:
        raise ValueError("quality receipt identity mismatch")
    records_value = value["records"]
    if not isinstance(records_value, list) or not records_value:
        raise ValueError("execution index requires actual execution evidence records")
    if value["records_payload_sha256"] != canonical_sha256(records_value):
        raise ValueError("execution index records payload hash mismatch")
    index_identity = dict(value)
    del index_identity["index_payload_sha256"]
    if value["index_payload_sha256"] != canonical_sha256(index_identity):
        raise ValueError("execution index payload hash mismatch")
    records = tuple(_ActualExecutionRecord.from_mapping(item) for item in records_value)
    if len({record.scene_id for record in records}) != len(records):
        raise ValueError("execution index scene IDs must be unique")
    for record in records:
        if record.execution_receipt_content_sha256 != execution_receipt_sha256:
            raise ValueError("record execution receipt identity mismatch")
        if record.quality_receipt_content_sha256 != quality_receipt_sha256:
            raise ValueError("record quality receipt identity mismatch")
    return records


def build_benchmark_schedule(
    scenes_by_group: Mapping[str, Sequence[str]],
    *,
    execution_index_artifact: ExecutionRecordIndexArtifact,
    execution_receipt_sha256: str,
    quality_receipt_sha256: str,
    index_loader: Callable[[ExecutionRecordIndexArtifact], bytes] = (
        _read_execution_index_bytes
    ),
    warmup_count: int = 20,
    observations_per_group: int = 1000,
    observations_per_path: int = 1000,
) -> tuple[BenchmarkScheduleItem, ...]:
    """Schedule only paths proven by a hash-admitted external execution index."""
    if not isinstance(scenes_by_group, Mapping) or set(scenes_by_group) != set(GROUPS):
        raise ValueError("benchmark scenes must contain exactly E, M, and H")
    if type(warmup_count) is not int or warmup_count < 20:
        raise ValueError("benchmark requires at least 20 warm-up runs")
    if type(observations_per_group) is not int or observations_per_group < 1000:
        raise ValueError("benchmark requires at least 1000 observations per group")
    if type(observations_per_path) is not int or observations_per_path < 1000:
        raise ValueError("benchmark requires at least 1000 observations per path")
    _sha256(execution_receipt_sha256, "execution receipt identity")
    _sha256(quality_receipt_sha256, "quality receipt identity")
    normalized: dict[str, tuple[str, ...]] = {}
    all_ids: list[str] = []
    for group in GROUPS:
        values = scenes_by_group[group]
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ValueError("benchmark scene IDs must be sequences")
        ordered = tuple(sorted(values))
        if not ordered or len(set(ordered)) != len(ordered):
            raise ValueError("benchmark scene IDs must be non-empty and unique")
        for value in ordered:
            _text(value, "scene_id")
        normalized[group] = ordered
        all_ids.extend(ordered)
    expected_inventory_counts = {"E": 100, "M": 99, "H": 100}
    if {group: len(values) for group, values in normalized.items()} != expected_inventory_counts:
        raise ValueError("benchmark schedule must bind the exact E/M/H inventory")
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("benchmark scene IDs cannot appear in multiple groups")
    records = _load_execution_index(
        execution_index_artifact,
        index_loader,
        execution_receipt_sha256=execution_receipt_sha256,
        quality_receipt_sha256=quality_receipt_sha256,
    )
    required_paths = ("dinov3", "needs_retake", "unknown")
    group_by_scene = {
        scene_id: group for group in GROUPS for scene_id in normalized[group]
    }
    if any(record.scene_id not in group_by_scene for record in records):
        raise ValueError("actual execution evidence must bind current scenes")
    normalized_paths: dict[str, tuple[_ActualExecutionRecord, ...]] = {}
    for path_name in required_paths:
        ordered = tuple(
            sorted(
                (record for record in records if _path_predicate(path_name, record)),
                key=lambda item: item.scene_id,
            )
        )
        if not ordered:
            raise ValueError(
                f"{path_name} actual path execution evidence must not be empty"
            )
        normalized_paths[path_name] = ordered
    flattened = tuple((group, scene_id) for group in GROUPS for scene_id in normalized[group])
    schedule: list[BenchmarkScheduleItem] = []
    for index in range(warmup_count):
        group, scene_id = flattened[index % len(flattened)]
        schedule.append(BenchmarkScheduleItem(index, scene_id, group, "warmup", True))
    ordinal = warmup_count
    for group in GROUPS:
        scenes = normalized[group]
        for index in range(observations_per_group):
            schedule.append(
                BenchmarkScheduleItem(
                    ordinal, scenes[index % len(scenes)], group, group, False
                )
            )
            ordinal += 1
    for path_name in required_paths:
        records = normalized_paths[path_name]
        for index in range(observations_per_path):
            scene_id = records[index % len(records)].scene_id
            schedule.append(
                BenchmarkScheduleItem(
                    ordinal, scene_id, group_by_scene[scene_id], path_name, False
                )
            )
            ordinal += 1
    return tuple(schedule)


def _path_predicate(path_name: str, record: _ActualExecutionRecord) -> bool:
    if path_name == "dinov3":
        return record.dino_executed and record.dino_object_count > 0
    if path_name == "needs_retake":
        return record.needs_retake and record.state == "needs_retake"
    if path_name == "unknown":
        return record.unknown and record.unknown_total > 0 and record.dino_executed
    return False


def _validate_runtime_identity(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != RUNTIME_FIELDS:
        raise ValueError("runtime identity schema is invalid")
    if value["device"] != "cuda:0" or value["gpu_name"] != "NVIDIA GeForce RTX 5080":
        raise ValueError("performance requires actual RTX 5080 on cuda:0")
    if value["fallback_reason"] is not None:
        raise ValueError("runtime identity rejects fallback")
    for field in (
        "compute_capability",
        "driver_version",
        "cuda_version",
        "tensorrt_version",
        "windows_build",
        "wddm_version",
    ):
        _text(value[field], f"runtime {field}")
    _sha256(value["runtime_manifest_sha256"], "runtime_manifest_sha256")
    return {key: value[key] for key in sorted(value)}


def _validate_artifacts(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != REQUIRED_ARTIFACT_ROLES:
        raise ValueError("artifact identities are incomplete")
    result = dict(sorted(value.items()))
    for role, digest in result.items():
        _sha256(digest, f"artifact {role}")
    return result


def _validated_thermal(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != THERMAL_FIELDS:
        raise ValueError("thermal state schema is invalid")
    result = {
        field: _finite_non_negative(value[field], f"thermal {field}")
        for field in THERMAL_FIELDS - {"thermal_throttled"}
    }
    if type(value["thermal_throttled"]) is not bool:
        raise ValueError("thermal_throttled must be boolean")
    if value["thermal_throttled"]:
        raise ValueError("thermal throttling requires a clean rerun")
    result["thermal_throttled"] = False
    return {key: result[key] for key in sorted(result)}


def _validated_timings(value: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(STAGES):
        raise ValueError("timing stages do not match the performance contract")
    result = {stage: _finite_non_negative(value[stage], f"timing {stage}") for stage in STAGES}
    if result["total"] < max(result[stage] for stage in STAGES if stage != "total"):
        raise ValueError("total must cover every stage timing")
    return result


def _count_range(rows: Sequence[PerformanceSample]) -> dict[str, int]:
    counts = tuple(row.object_count for row in rows)
    return {"min": min(counts), "max": max(counts)}


def _bootstrap_p95_order_statistics(
    ordered: Sequence[float], *, seed: int, iterations: int
) -> list[float]:
    """Sample the empirical bootstrap p95 order statistic in O(iterations)."""
    count = len(ordered)
    order = math.ceil(0.95 * count)
    rng = random.Random(seed)
    result: list[float] = []
    for _ in range(iterations):
        quantile = rng.betavariate(order, count + 1 - order)
        index = min(count - 1, math.floor(quantile * count))
        result.append(ordered[index])
    result.sort()
    return result


def _nearest_rank(ordered: Sequence[float], percentile: float) -> float:
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWER_HEX for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _finite_non_negative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "GROUPS",
    "MINIMUM_SAMPLES",
    "REQUIRED_ARTIFACT_ROLES",
    "REQUIRED_SLICES",
    "STAGES",
    "BenchmarkScheduleItem",
    "ExecutionRecordIndexArtifact",
    "PerformanceReceipt",
    "PerformanceSample",
    "build_benchmark_schedule",
    "build_performance_receipt",
    "canonical_sha256",
    "summarize_latency_ms",
    "validate_protocol",
]
