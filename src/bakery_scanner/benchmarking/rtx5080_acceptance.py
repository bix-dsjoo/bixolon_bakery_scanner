"""Fail-closed path-aware RTX 5080 latency evidence and acceptance."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
import stat
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
_TRUSTED_EXECUTION_MANIFEST = Path(
    "benchmarks/locked-manifests/rtx5080_15plus5_execution_evidence_v1.json"
)
_TRUSTED_EXECUTION_MANIFEST_POSIX = (
    "benchmarks/locked-manifests/rtx5080_15plus5_execution_evidence_v1.json"
)
_TRUSTED_EXECUTION_MANIFEST_LOCK_ID = (
    "rtx5080_15plus5_execution_evidence_manifest_v1"
)
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


class ExecutionIndexAdmissionError(ValueError):
    """Raised when immutable external execution evidence cannot be admitted."""


_ADMISSION_TOKEN = object()


@dataclass(frozen=True, slots=True)
class _VerifiedExecutionIndexAdmission:
    scenes_by_group: Mapping[str, tuple[str, ...]]
    scene_input_sha256: Mapping[str, str]
    records: tuple[_ActualExecutionRecord, ...]
    execution_receipt_sha256: str
    quality_receipt_sha256: str
    _token: object

    def __post_init__(self) -> None:
        if self._token is not _ADMISSION_TOKEN:
            raise ValueError("verified execution-index admission token is invalid")


_ADMISSION_REGISTRY: dict[int, tuple[_VerifiedExecutionIndexAdmission, str]] = {}


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


def admit_execution_record_index(
    repository_root: Path, artifact_root: Path
) -> object:
    """Admit only evidence anchored by the repository's fixed trusted manifest."""
    try:
        return _admit_execution_record_index(repository_root, artifact_root)
    except ExecutionIndexAdmissionError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ExecutionIndexAdmissionError(str(exc)) from exc


def _admit_execution_record_index(
    repository_root: Path, artifact_root: Path
) -> _VerifiedExecutionIndexAdmission:
    if not isinstance(repository_root, Path) or not isinstance(artifact_root, Path):
        raise ValueError("repository and external artifact roots must be paths")
    repository_lexical = repository_root.absolute()
    if _is_link_or_reparse(repository_lexical):
        raise ValueError("repository root may not be a symlink or reparse point")
    repository = repository_lexical.resolve()
    external = artifact_root.resolve()
    manifest_path = repository / _TRUSTED_EXECUTION_MANIFEST
    if not manifest_path.is_file():
        raise ExecutionIndexAdmissionError("trusted manifest is missing")
    _require_unlinked_contained_path(repository, manifest_path, "trusted manifest")
    manifest_raw = _verify_trusted_manifest_lock(repository, manifest_path)
    manifest = _parse_canonical_json(manifest_raw, "trusted manifest")
    expected_manifest_keys = {
        "schema_version",
        "manifest_id",
        "artifacts",
        "fold_manifests",
        "manifest_payload_sha256",
    }
    if (
        set(manifest) != expected_manifest_keys
        or manifest["schema_version"] != 1
        or manifest["manifest_id"] != "rtx5080_15plus5_execution_evidence_v1"
    ):
        raise ValueError("trusted manifest schema or identity is invalid")
    _verify_internal_hash(manifest, "manifest_payload_sha256", "trusted manifest")
    declarations = manifest["artifacts"]
    expected_roles = {
        "execution_index",
        "execution_receipt",
        "quality_receipt",
        "scene_input_identities",
        "split_inventory",
    }
    if not isinstance(declarations, Mapping) or set(declarations) != expected_roles:
        raise ValueError("trusted manifest artifact declarations are incomplete")
    fold_declarations = manifest["fold_manifests"]
    if not isinstance(fold_declarations, list) or len(fold_declarations) != 5:
        raise ValueError("trusted manifest must declare five fold manifests")

    verified = {
        role: _read_declared_json(
            declarations[role], repository, external, role.replace("_", " ")
        )
        for role in sorted(expected_roles)
    }
    folds = tuple(
        _read_declared_json(item, repository, external, f"fold manifest {index}")
        for index, item in enumerate(fold_declarations)
    )
    inventory, inventory_sha, scene_ids = _validate_inventory(
        verified["split_inventory"]
    )
    fold_hashes = _validate_folds(folds, inventory, scene_ids)
    scenes_by_group = _group_inventory(scene_ids)
    scene_inputs = _validate_scene_input_map(
        verified["scene_input_identities"], inventory_sha, fold_hashes, scene_ids
    )
    execution_sha = _validate_receipt(
        verified["execution_receipt"], "verified_actual_execution", "execution receipt"
    )
    quality_sha = _validate_receipt(
        verified["quality_receipt"],
        "quality-passed-performance-unverified",
        "quality receipt",
    )
    records = _load_execution_index(
        verified["execution_index"],
        execution_receipt_sha256=execution_sha,
        quality_receipt_sha256=quality_sha,
    )
    if any(record.scene_id not in scene_inputs for record in records):
        raise ValueError("actual execution evidence must bind current scenes")
    for record in records:
        if record.input_sha256 != scene_inputs[record.scene_id]:
            raise ValueError(
                f"record scene input identity mismatch for {record.scene_id}"
            )
    admission = _VerifiedExecutionIndexAdmission(
        scenes_by_group=MappingProxyType(scenes_by_group),
        scene_input_sha256=MappingProxyType(scene_inputs),
        records=records,
        execution_receipt_sha256=execution_sha,
        quality_receipt_sha256=quality_sha,
        _token=_ADMISSION_TOKEN,
    )
    _ADMISSION_REGISTRY[id(admission)] = (admission, _admission_fingerprint(admission))
    return admission


def _verify_trusted_manifest_lock(repository: Path, manifest_path: Path) -> bytes:
    lock_path = repository / "artifacts.lock.json"
    _require_unlinked_contained_path(repository, lock_path, "artifact lock")
    if not lock_path.is_file():
        raise ValueError("trusted manifest artifact lock is missing")
    lock_raw = _read_stable_bytes(lock_path, "artifact lock")
    try:
        lock = json.loads(lock_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("trusted manifest artifact lock is invalid JSON") from exc
    if not isinstance(lock, Mapping) or lock.get("schema_version") != 1:
        raise ValueError("trusted manifest artifact lock schema is invalid")
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("trusted manifest artifact lock entries are invalid")
    matching = [
        item
        for item in artifacts
        if isinstance(item, Mapping)
        and item.get("id") == _TRUSTED_EXECUTION_MANIFEST_LOCK_ID
    ]
    if len(matching) != 1:
        raise ValueError("trusted manifest artifact lock entry is missing or duplicated")
    declaration = matching[0]
    if set(declaration) != {
        "id",
        "kind",
        "local_path",
        "sha256",
        "bytes",
        "storage",
    }:
        raise ValueError("trusted manifest artifact lock entry schema is invalid")
    if (
        declaration["kind"] != "benchmark-evidence-manifest"
        or declaration["local_path"] != _TRUSTED_EXECUTION_MANIFEST_POSIX
        or declaration["storage"] != "git"
    ):
        raise ValueError("trusted manifest artifact lock identity is invalid")
    expected_bytes = declaration["bytes"]
    if type(expected_bytes) is not int or expected_bytes < 1:
        raise ValueError("trusted manifest artifact lock byte size is invalid")
    expected_sha = _sha256(
        declaration["sha256"], "trusted manifest artifact lock SHA-256"
    )
    raw = _read_stable_bytes(manifest_path, "trusted manifest")
    if len(raw) != expected_bytes:
        raise ValueError("trusted manifest byte size mismatch against artifact lock")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("trusted manifest SHA-256 mismatch against artifact lock")
    return raw


def _require_unlinked_contained_path(root: Path, path: Path, label: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} path escapes repository root") from exc
    current = root
    if _is_link_or_reparse(current):
        raise ValueError(f"{label} path may not traverse a symlink or reparse point")
    for part in relative.parts:
        current /= part
        if _is_link_or_reparse(current):
            raise ValueError(f"{label} path may not traverse a symlink or reparse point")
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} path escapes repository root")


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _read_stable_bytes(path: Path, label: str) -> bytes:
    if _is_link_or_reparse(path) or not path.is_file():
        raise ValueError(f"{label} must be a regular immutable file")
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"{label} changed while reading")
    return raw


def _read_canonical_json(path: Path, label: str) -> Mapping[str, object]:
    return _parse_canonical_json(_read_stable_bytes(path, label), label)


def _parse_canonical_json(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError(f"{label} bytes must be canonical JSON")
    return value


def _read_declared_json(
    declaration: object, repository: Path, external: Path, label: str
) -> Mapping[str, object]:
    if not isinstance(declaration, Mapping) or set(declaration) != {
        "root",
        "local_path",
        "bytes",
        "sha256",
    }:
        raise ValueError(f"{label} descriptor schema is invalid")
    root_name = declaration["root"]
    if root_name not in {"repository", "external"}:
        raise ValueError(f"{label} descriptor root is invalid")
    relative_text = declaration["local_path"]
    if not isinstance(relative_text, str) or not relative_text:
        raise ValueError(f"{label} descriptor path is invalid")
    relative = PurePosixPath(relative_text)
    if (
        relative.is_absolute()
        or relative_text != relative.as_posix()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"{label} descriptor path is invalid")
    declared_bytes = declaration["bytes"]
    if type(declared_bytes) is not int or declared_bytes < 1:
        raise ValueError(f"{label} descriptor byte size is invalid")
    declared_sha = _sha256(declaration["sha256"], f"{label} descriptor SHA-256")
    root = repository if root_name == "repository" else external
    candidate = root.joinpath(*relative.parts)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} descriptor escapes its declared root")
    current = root
    for part in relative.parts:
        current /= part
        if _is_link_or_reparse(current):
            raise ValueError(
                f"{label} descriptor may not traverse a symlink or reparse point"
            )
    if not resolved.is_file():
        raise ValueError(f"{label} declared artifact is missing")
    before = resolved.stat()
    raw = resolved.read_bytes()
    after = resolved.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"{label} changed while reading")
    if len(raw) != declared_bytes:
        raise ValueError(f"{label} byte size mismatch")
    if hashlib.sha256(raw).hexdigest() != declared_sha:
        raise ValueError(f"{label} SHA-256 mismatch")
    return _parse_canonical_json(raw, label)


def _verify_internal_hash(
    value: Mapping[str, object], hash_field: str, label: str
) -> str:
    digest = _sha256(value.get(hash_field), f"{label} {hash_field}")
    identity = dict(value)
    del identity[hash_field]
    if digest != canonical_sha256(identity):
        raise ValueError(f"{label} payload hash mismatch")
    return digest


def _validate_receipt(
    value: Mapping[str, object], expected_status: str, label: str
) -> str:
    if value.get("schema_version") != 3 or value.get("status") != expected_status:
        raise ValueError(f"{label} status or schema is invalid")
    _verify_internal_hash(value, "receipt_sha256", label)
    return canonical_sha256(value)


def _validate_inventory(
    value: Mapping[str, object],
) -> tuple[Mapping[str, object], str, tuple[str, ...]]:
    inventory_sha = _verify_internal_hash(value, "manifest_sha256", "split inventory")
    scene_values = value.get("scene_ids")
    expected_counts = {"E": 100, "M": 99, "H": 100}
    if (
        value.get("schema_version") != 1
        or value.get("scene_count") != 299
        or value.get("difficulty_counts") != expected_counts
        or not isinstance(scene_values, list)
    ):
        raise ValueError("split inventory schema or counts are invalid")
    source_sha = _sha256(value.get("source_sha256"), "split inventory source SHA-256")
    del source_sha
    scene_ids = tuple(scene_values)
    if len(scene_ids) != 299 or len(set(scene_ids)) != 299:
        raise ValueError("split inventory must contain 299 unique scenes")
    for scene_id in scene_ids:
        _text(scene_id, "split inventory scene ID")
    return value, inventory_sha, scene_ids


def _validate_folds(
    folds: tuple[Mapping[str, object], ...],
    inventory: Mapping[str, object],
    scene_ids: tuple[str, ...],
) -> dict[str, str]:
    source_sha = inventory["source_sha256"]
    fold_by_index: dict[int, tuple[Mapping[str, object], str]] = {}
    for value in folds:
        digest = _verify_internal_hash(value, "manifest_sha256", "fold manifest")
        index = value.get("fold_index")
        if (
            type(index) is not int
            or index not in range(5)
            or index in fold_by_index
            or value.get("schema_version") != 1
            or value.get("seed") != _BOOTSTRAP_SEED
            or value.get("source_sha256") != source_sha
        ):
            raise ValueError("fold manifest identity is invalid")
        fold_by_index[index] = (value, digest)
    if set(fold_by_index) != set(range(5)):
        raise ValueError("fold manifests must contain indices zero through four")
    evaluation: list[str] = []
    for index in range(5):
        assignments = fold_by_index[index][0].get("scene_ids")
        if not isinstance(assignments, Mapping):
            raise ValueError("fold scene assignments are invalid")
        rows = assignments.get("evaluation")
        if not isinstance(rows, list):
            raise ValueError("fold evaluation scenes are invalid")
        evaluation.extend(rows)
    if len(evaluation) != len(set(evaluation)) or set(evaluation) != set(scene_ids):
        raise ValueError("fold evaluation scenes must partition the current inventory")
    return {str(index): fold_by_index[index][1] for index in range(5)}


def _group_inventory(scene_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {group: [] for group in GROUPS}
    for scene_id in scene_ids:
        matches = [
            group
            for group in GROUPS
            if scene_id.lower().startswith(f"{group.lower()}-")
            or f"_{group.lower()}_" in scene_id.lower()
        ]
        if len(matches) != 1:
            raise ValueError(f"scene difficulty identity is invalid for {scene_id}")
        grouped[matches[0]].append(scene_id)
    result = {group: tuple(sorted(grouped[group])) for group in GROUPS}
    if {group: len(result[group]) for group in GROUPS} != {"E": 100, "M": 99, "H": 100}:
        raise ValueError("current scene difficulty groups do not match inventory counts")
    return result


def _validate_scene_input_map(
    value: Mapping[str, object],
    inventory_sha: str,
    fold_hashes: Mapping[str, str],
    scene_ids: tuple[str, ...],
) -> dict[str, str]:
    if value.get("schema_version") != 1:
        raise ValueError("scene input identity map schema is invalid")
    _verify_internal_hash(value, "payload_sha256", "scene input identity map")
    if value.get("inventory_manifest_sha256") != inventory_sha:
        raise ValueError("scene input identity inventory binding mismatch")
    if value.get("fold_manifest_sha256") != dict(fold_hashes):
        raise ValueError("scene input identity fold bindings mismatch")
    identities = value.get("scene_input_sha256")
    if not isinstance(identities, Mapping) or set(identities) != set(scene_ids):
        raise ValueError("scene input identity map must bind the current inventory")
    return {
        scene_id: _sha256(identities[scene_id], f"scene input identity for {scene_id}")
        for scene_id in scene_ids
    }


def _load_execution_index(
    value: Mapping[str, object],
    *,
    execution_receipt_sha256: str,
    quality_receipt_sha256: str,
) -> tuple[_ActualExecutionRecord, ...]:
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
    if value["artifact_id"] != "rtx5080_actual_path_execution_index_v1":
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


def _admission_fingerprint(admission: _VerifiedExecutionIndexAdmission) -> str:
    return canonical_sha256(
        {
            "scenes_by_group": {
                group: list(admission.scenes_by_group[group]) for group in GROUPS
            },
            "scene_input_sha256": dict(sorted(admission.scene_input_sha256.items())),
            "records": [
                {
                    **record._identity_payload(),
                    "record_payload_sha256": record.record_payload_sha256,
                }
                for record in admission.records
            ],
            "execution_receipt_sha256": admission.execution_receipt_sha256,
            "quality_receipt_sha256": admission.quality_receipt_sha256,
        }
    )


def _require_verified_admission(value: object) -> _VerifiedExecutionIndexAdmission:
    message = "verified execution-index admission is required"
    if not isinstance(value, _VerifiedExecutionIndexAdmission):
        raise ValueError(message)
    registered = _ADMISSION_REGISTRY.get(id(value))
    if registered is None or registered[0] is not value:
        raise ValueError(message)
    try:
        value.__post_init__()
        _sha256(value.execution_receipt_sha256, "execution receipt identity")
        _sha256(value.quality_receipt_sha256, "quality receipt identity")
        if (
            not isinstance(value.records, tuple)
            or not value.records
            or any(not isinstance(record, _ActualExecutionRecord) for record in value.records)
        ):
            raise ValueError("admission records are invalid")
        for record in value.records:
            record.__post_init__()
            if (
                record.execution_receipt_content_sha256
                != value.execution_receipt_sha256
                or record.quality_receipt_content_sha256
                != value.quality_receipt_sha256
                or value.scene_input_sha256.get(record.scene_id) != record.input_sha256
            ):
                raise ValueError("admission record identity binding mismatch")
        if _admission_fingerprint(value) != registered[1]:
            raise ValueError("admission seal mismatch")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(message) from exc
    return value


def build_benchmark_schedule(
    admission: object,
    *,
    warmup_count: int = 20,
    observations_per_group: int = 1000,
    observations_per_path: int = 1000,
) -> tuple[BenchmarkScheduleItem, ...]:
    """Schedule only paths proven by an immutable external evidence admission."""
    admission = _require_verified_admission(admission)
    scenes_by_group = admission.scenes_by_group
    if not isinstance(scenes_by_group, Mapping) or set(scenes_by_group) != set(GROUPS):
        raise ValueError("benchmark scenes must contain exactly E, M, and H")
    if type(warmup_count) is not int or warmup_count < 20:
        raise ValueError("benchmark requires at least 20 warm-up runs")
    if type(observations_per_group) is not int or observations_per_group < 1000:
        raise ValueError("benchmark requires at least 1000 observations per group")
    if type(observations_per_path) is not int or observations_per_path < 1000:
        raise ValueError("benchmark requires at least 1000 observations per path")
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
    records = admission.records
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
    "ExecutionIndexAdmissionError",
    "PerformanceReceipt",
    "PerformanceSample",
    "admit_execution_record_index",
    "build_benchmark_schedule",
    "build_performance_receipt",
    "canonical_sha256",
    "summarize_latency_ms",
    "validate_protocol",
]
