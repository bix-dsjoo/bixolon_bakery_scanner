"""Strict, reproducible evidence receipts for CUDA camera-worker benchmarks."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal


GROUPS = ("E", "M", "H")
MINIMUM_GROUP_OBSERVATIONS = 100
STAGES = (
    "decode_preprocess",
    "detector",
    "crop",
    "repvit",
    "dinov3",
    "fusion",
    "postprocess",
    "total",
)
_LOWER_HEX = frozenset("0123456789abcdef")
_APPLIED_HASH_FIELDS = frozenset(
    {
        "detector_checkpoint_sha256", "detector_calibration_sha256",
        "detector_manifest_sha256", "repvit_checkpoint_sha256",
        "repvit_manifest_sha256", "repvit_prototype_sha256",
        "dinov3_weights_sha256", "dinov3_support_sha256",
        "dinov3_local_bank_sha256", "classifier_calibration_sha256",
        "preprocess_sha256", "fusion_policy_sha256", "presentation_policy_sha256",
    }
)
_EVIDENCE_HASH_FIELDS = frozenset(
    {"benchmark_manifest_sha256", "benchmark_protocol_sha256", "code_identity_sha256"}
)


def summarize_ms(values: Iterable[float]) -> dict[str, int | float]:
    """Return deterministic nearest-rank timing percentiles."""
    ordered = sorted(_finite_non_negative(value, "timing") for value in values)
    if not ordered:
        raise ValueError("timing values must not be empty")
    count = len(ordered)
    return {
        "count": count,
        "p50": _nearest_rank(ordered, 0.50),
        "p90": _nearest_rank(ordered, 0.90),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
    }


@dataclass(frozen=True, slots=True)
class GpuSample:
    request_id: str
    image_id: str
    group: str
    image_sha256: str
    object_count: int
    dino_object_count: int
    timings_ms: Mapping[str, float]

    def __post_init__(self) -> None:
        _non_empty_string(self.request_id, "request_id")
        _non_empty_string(self.image_id, "image_id")
        if self.group not in GROUPS:
            raise ValueError("sample group must be E, M, or H")
        _sha256(self.image_sha256, "image_sha256")
        _non_negative_int(self.object_count, "object_count")
        _non_negative_int(self.dino_object_count, "dino_object_count")
        if self.dino_object_count > self.object_count:
            raise ValueError("dino_object_count must not exceed object_count")
        if not isinstance(self.timings_ms, Mapping) or set(self.timings_ms) != set(STAGES):
            raise ValueError("sample timings_ms stages do not match worker contract")
        normalized = {
            stage: _finite_non_negative(self.timings_ms[stage], f"{stage} timing")
            for stage in STAGES
        }
        _validate_total(normalized, "sample timings_ms")
        object.__setattr__(self, "timings_ms", _freeze(normalized))

    def to_payload(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "image_id": self.image_id,
            "group": self.group,
            "image_sha256": self.image_sha256,
            "object_count": self.object_count,
            "dino_object_count": self.dino_object_count,
            "timings_ms": dict(self.timings_ms),
        }


@dataclass(frozen=True, slots=True)
class GpuWorkerReceipt:
    schema_version: Literal[2]
    runtime: Mapping[str, object]
    artifacts: Mapping[str, str]
    samples: tuple[GpuSample, ...]
    summaries: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.schema_version != 2:
            raise ValueError("GPU worker receipt schema_version must be 2")
        _validate_runtime(self.runtime)
        _validate_artifacts(self.artifacts)
        if not isinstance(self.samples, tuple) or not self.samples:
            raise ValueError("GPU worker receipt samples must be a non-empty tuple")
        if any(not isinstance(sample, GpuSample) for sample in self.samples):
            raise ValueError("GPU worker receipt samples must be GpuSample values")
        request_ids = tuple(sample.request_id for sample in self.samples)
        if len(set(request_ids)) != len(request_ids):
            raise ValueError("GPU worker receipt request IDs must be unique")
        _validate_group_observations(self.samples)
        if not isinstance(self.summaries, Mapping):
            raise ValueError("GPU worker receipt summaries must be an object")
        expected_summaries = _summaries(self.samples)
        if dict(self.summaries) != expected_summaries:
            raise ValueError("GPU worker receipt summaries do not match samples")
        object.__setattr__(self, "runtime", _freeze(self.runtime))
        object.__setattr__(self, "artifacts", _freeze(self.artifacts))
        object.__setattr__(self, "summaries", _freeze(expected_summaries))

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "runtime": _thaw(self.runtime),
            "artifacts": _thaw(self.artifacts),
            "samples": [sample.to_payload() for sample in self.samples],
            "summaries": _thaw(self.summaries),
        }


def build_receipt(
    ready_event: Mapping[str, object],
    grouped_samples: Mapping[str, Sequence[GpuSample | Mapping[str, object]]],
    *,
    artifacts: Mapping[str, str] | None = None,
) -> GpuWorkerReceipt:
    """Build a schema-v2 receipt without allowing CUDA fallback evidence."""
    runtime = _runtime_from_ready(ready_event)
    if not isinstance(grouped_samples, Mapping) or set(grouped_samples) != set(GROUPS):
        raise ValueError("GPU receipt groups must be exactly E, M, and H")
    samples: list[GpuSample] = []
    for group in GROUPS:
        rows = grouped_samples[group]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValueError("GPU receipt group samples must be a sequence")
        for row in rows:
            sample = row if isinstance(row, GpuSample) else _sample_from_mapping(row)
            if sample.group != group:
                raise ValueError("GPU receipt sample group does not match its bucket")
            samples.append(sample)
    _validate_group_observations(tuple(samples))
    receipt_artifacts = _receipt_artifacts(ready_event, artifacts)
    summaries = _summaries(tuple(samples))
    return GpuWorkerReceipt(
        schema_version=2,
        runtime=runtime,
        artifacts=receipt_artifacts,
        samples=tuple(samples),
        summaries=summaries,
    )


def _sample_from_mapping(value: Mapping[str, object]) -> GpuSample:
    if not isinstance(value, Mapping) or set(value) != {
        "request_id", "image_id", "group", "image_sha256", "object_count",
        "dino_object_count", "timings_ms",
    }:
        raise ValueError("GPU receipt sample schema is invalid")
    timings = value["timings_ms"]
    if not isinstance(timings, Mapping):
        raise ValueError("GPU receipt sample timings_ms must be an object")
    return GpuSample(
        request_id=value["request_id"],  # type: ignore[arg-type]
        image_id=value["image_id"],  # type: ignore[arg-type]
        group=value["group"],  # type: ignore[arg-type]
        image_sha256=value["image_sha256"],  # type: ignore[arg-type]
        object_count=value["object_count"],  # type: ignore[arg-type]
        dino_object_count=value["dino_object_count"],  # type: ignore[arg-type]
        timings_ms=timings,  # type: ignore[arg-type]
    )


def _runtime_from_ready(ready_event: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(ready_event, Mapping) or ready_event.get("type") != "ready":
        raise ValueError("GPU receipt requires a ready event")
    device = ready_event.get("device")
    startup = ready_event.get("startup_metrics")
    if device != "cuda:0" or not isinstance(startup, Mapping):
        raise ValueError("GPU receipt requires CUDA device cuda:0")
    if startup.get("device") != "cuda:0":
        raise ValueError("GPU receipt startup device must be cuda:0")
    if startup.get("fallback_reason") is not None:
        raise ValueError("GPU receipt rejects CUDA fallback")
    return {"device": "cuda:0", "startup_metrics": _thaw(startup)}


def _receipt_artifacts(
    ready_event: Mapping[str, object], artifacts: Mapping[str, str] | None
) -> dict[str, str]:
    startup = ready_event["startup_metrics"]
    assert isinstance(startup, Mapping)
    applied = startup.get("applied_artifact_hashes")
    if not isinstance(applied, Mapping) or set(applied) != _APPLIED_HASH_FIELDS:
        raise ValueError("GPU receipt applied provenance is invalid")
    metadata = dict(applied)
    if not isinstance(artifacts, Mapping) or set(artifacts) != (
        _EVIDENCE_HASH_FIELDS | {"code_commit"}
    ):
        raise ValueError("GPU receipt evidence provenance is invalid")
    metadata.update(artifacts)
    _validate_artifacts(metadata)
    return metadata


def _summaries(samples: tuple[GpuSample, ...]) -> dict[str, object]:
    by_group = {
        group: tuple(sample for sample in samples if sample.group == group)
        for group in GROUPS
    }
    return {
        "groups": {group: _summary(by_group[group]) for group in GROUPS},
        "overall": _summary(samples),
    }


def _summary(samples: Sequence[GpuSample]) -> dict[str, object]:
    object_counts = [float(sample.object_count) for sample in samples]
    dino_counts = [float(sample.dino_object_count) for sample in samples]
    total_objects = sum(object_counts)
    return {
        "sample_count": len(samples),
        "timings_ms": {
            stage: summarize_ms(sample.timings_ms[stage] for sample in samples)
            for stage in STAGES
        },
        "object_count": summarize_ms(object_counts),
        "dino_object_count": summarize_ms(dino_counts),
        "dino_execution_rate": 0.0 if total_objects == 0.0 else sum(dino_counts) / total_objects,
    }


def _validate_group_observations(samples: Sequence[GpuSample]) -> None:
    for group in GROUPS:
        count = sum(sample.group == group for sample in samples)
        if count < MINIMUM_GROUP_OBSERVATIONS:
            raise ValueError(
                f"GPU receipt group {group} requires at least "
                f"{MINIMUM_GROUP_OBSERVATIONS} observations"
            )


def _validate_runtime(runtime: Mapping[str, object]) -> None:
    if not isinstance(runtime, Mapping) or set(runtime) != {"device", "startup_metrics"}:
        raise ValueError("GPU worker receipt runtime schema is invalid")
    if runtime["device"] != "cuda:0":
        raise ValueError("GPU worker receipt runtime must use cuda:0")
    startup = runtime["startup_metrics"]
    if not isinstance(startup, Mapping) or startup.get("fallback_reason") is not None:
        raise ValueError("GPU worker receipt runtime fallback is invalid")


def _validate_artifacts(artifacts: Mapping[str, str]) -> None:
    if not isinstance(artifacts, Mapping) or set(artifacts) != (
        _APPLIED_HASH_FIELDS | _EVIDENCE_HASH_FIELDS | {"code_commit"}
    ):
        raise ValueError("GPU worker receipt provenance is incomplete")
    for key, value in artifacts.items():
        if key == "code_commit":
            if not isinstance(value, str) or len(value) not in (40, 64) or any(
                character not in _LOWER_HEX for character in value
            ):
                raise ValueError("GPU worker receipt code_commit is invalid")
        else:
            _sha256(value, f"artifact {key}")


def _nearest_rank(ordered: Sequence[float], percentile: float) -> float:
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _non_empty_string(value: object, label: str) -> str:
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
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _finite_non_negative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number


def _validate_total(timings: Mapping[str, float], label: str) -> None:
    if timings["total"] < max(timings[stage] for stage in STAGES if stage != "total"):
        raise ValueError(f"{label} total must cover every stage")


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list) or isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value
