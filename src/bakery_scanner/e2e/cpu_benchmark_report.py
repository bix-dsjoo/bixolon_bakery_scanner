"""Schema-v3 evidence construction for isolated CPU benchmark workers."""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .cpu_benchmark_coordinator import BenchmarkExecution, CoordinatedPass
from .cpu_benchmark_protocol import (
    BenchmarkImageRow,
    ResolvedRuntime,
    WarmupEvidence,
    WorkerEnvironment,
    WorkerError,
    WorkerMetadata,
)
from .cpu_dataset import CpuEvaluationSample
from .cpu_latency import ImageLatency, PairedPass, compare_paired_latency
from .cpu_regression import (
    ImageRegressionRecord,
    ObjectRecord,
    Regression,
    RunAggregate,
    compare_run,
)
from .rfdetr_cpu import summarize_profile_stages


@dataclass(frozen=True, slots=True)
class CoordinatorSettings:
    ready_timeout_s: float
    pass_timeout_s: float
    shutdown_timeout_s: float

    def __post_init__(self) -> None:
        for field in (
            "ready_timeout_s",
            "pass_timeout_s",
            "shutdown_timeout_s",
        ):
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise ValueError(f"{field} must be a finite positive number")
            object.__setattr__(self, field, float(value))


def build_benchmark_report(
    *,
    execution: BenchmarkExecution,
    samples: tuple[CpuEvaluationSample, ...],
    detector: dict[str, object],
    artifacts: dict[str, str],
    sample_profile: Literal["all299", "batch2_e3_m3_h3"],
    bootstrap_seed: int,
    coordinator_settings: CoordinatorSettings,
) -> dict[str, object]:
    """Build fail-closed schema-v3 quality and paired CPU latency evidence."""
    _validate_build_inputs(
        execution,
        samples,
        detector,
        artifacts,
        sample_profile,
        bootstrap_seed,
        coordinator_settings,
    )
    (
        paired_passes,
        reference_rows,
        candidate_rows,
        first_reference_records,
        first_candidate_records,
    ) = _validated_pass_evidence(execution, samples)

    quality = compare_run(first_reference_records, first_candidate_records)
    latency = compare_paired_latency(paired_passes, seed=bootstrap_seed)
    quality_passed = (
        quality.passed
        if sample_profile == "all299"
        else not quality.regressions
    )
    report: dict[str, object] = {
        "schema_version": 3,
        "created_at_utc": execution.started_at_utc,
        "completed_at_utc": execution.completed_at_utc,
        "dataset": {
            "sample_profile": sample_profile,
            "images": len(samples),
            "objects": sum(len(sample.targets) for sample in samples),
            "image_keys": [sample.key for sample in samples],
        },
        "detector": dict(detector),
        "artifacts": dict(artifacts),
        "coordinator": {
            "started_at_utc": execution.started_at_utc,
            "completed_at_utc": execution.completed_at_utc,
            "ready_timeout_s": coordinator_settings.ready_timeout_s,
            "pass_timeout_s": coordinator_settings.pass_timeout_s,
            "shutdown_timeout_s": coordinator_settings.shutdown_timeout_s,
        },
        "workers": {
            "reference": _serialize_worker(execution.reference_worker),
            "candidate": _serialize_worker(execution.candidate_worker),
        },
        "passes": [
            _serialize_pass(value)
            for value in execution.passes
        ],
        "profiles": {
            "reference": summarize_profile_stages(
                tuple(_summary_row(row) for row in reference_rows)
            ),
            "candidate": summarize_profile_stages(
                tuple(_summary_row(row) for row in candidate_rows)
            ),
        },
        "quality_gate": {
            "scope": sample_profile,
            "quality_floors_enforced": sample_profile == "all299",
            "reference": _serialize_aggregate(quality.reference),
            "candidate": _serialize_aggregate(quality.candidate),
            "regressions": [
                _serialize_regression(regression)
                for regression in quality.regressions
            ],
            "passed": quality_passed,
        },
        "latency_gate": {
            "pass_count": latency.pass_count,
            "image_count": latency.image_count,
            "bootstrap_seed": latency.bootstrap_seed,
            "bootstrap_samples": latency.bootstrap_samples,
            "mean_delta_ms": latency.mean_delta_ms,
            "p95_delta_ms": latency.p95_delta_ms,
            "mean_ci_upper_ms": latency.mean_ci_upper_ms,
            "p95_ci_upper_ms": latency.p95_ci_upper_ms,
            "passed": latency.passed,
        },
    }
    _canonical_json(report)
    return report


def publish_benchmark_report(
    output: Path, report: dict[str, object]
) -> None:
    """Publish canonical JSON through a unique sibling staging directory."""
    destination = _output_path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite output: {destination}")
    if not isinstance(report, dict):
        raise TypeError("report must be a dictionary")
    encoded = _canonical_json(report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (
        f".{destination.name}.staging-{uuid4().hex}"
    )
    staging.mkdir()
    try:
        (staging / "report.json").write_text(encoded, encoding="utf-8")
        if destination.exists():
            raise FileExistsError(
                f"refusing to overwrite output: {destination}"
            )
        staging.rename(destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def publish_benchmark_failure(
    output: Path,
    failure: WorkerError,
    *,
    coordinator_settings: CoordinatorSettings,
) -> Path:
    """Write sanitized worker diagnostics without traceback or process locals."""
    destination = _output_path(output)
    if not isinstance(failure, WorkerError):
        raise TypeError("failure must be WorkerError")
    if not isinstance(coordinator_settings, CoordinatorSettings):
        raise TypeError("coordinator_settings must be CoordinatorSettings")
    failure_id = uuid4().hex
    failed_output = destination.parent / (
        f"{destination.name}.failed.{failure_id}"
    )
    payload: dict[str, object] = {
        "schema_version": 3,
        "failed_at_utc": datetime.now(UTC).isoformat(),
        "coordinator": {
            "ready_timeout_s": coordinator_settings.ready_timeout_s,
            "pass_timeout_s": coordinator_settings.pass_timeout_s,
            "shutdown_timeout_s": coordinator_settings.shutdown_timeout_s,
        },
        "failure": {
            "exception_type": failure.exception_type,
            "message": _sanitize_message(failure.message),
            "role": failure.role,
            "pid": failure.pid,
            "protocol_state": failure.protocol_state.value,
            "pass_index": failure.pass_index,
            "stderr_path": (
                None
                if failure.stderr_path is None
                else str(failure.stderr_path)
            ),
        },
    }
    encoded = _canonical_json(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (
        f".{destination.name}.failure-staging-{uuid4().hex}"
    )
    staging.mkdir()
    try:
        (staging / "failure.json").write_text(encoded, encoding="utf-8")
        staging.rename(failed_output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return failed_output


def _validate_build_inputs(
    execution: BenchmarkExecution,
    samples: tuple[CpuEvaluationSample, ...],
    detector: dict[str, object],
    artifacts: dict[str, str],
    sample_profile: str,
    bootstrap_seed: int,
    coordinator_settings: CoordinatorSettings,
) -> None:
    if not isinstance(execution, BenchmarkExecution):
        raise TypeError("execution must be BenchmarkExecution")
    if not isinstance(samples, tuple) or not samples:
        raise ValueError("samples must be a non-empty tuple")
    if any(not isinstance(sample, CpuEvaluationSample) for sample in samples):
        raise ValueError("samples must contain CpuEvaluationSample values")
    keys = tuple(sample.key for sample in samples)
    if len(set(keys)) != len(keys):
        raise ValueError("sample keys must be unique")
    if sample_profile not in {"all299", "batch2_e3_m3_h3"}:
        raise ValueError("sample_profile must be recognized")
    if type(bootstrap_seed) is not int:
        raise ValueError("bootstrap_seed must be an integer")
    if not isinstance(coordinator_settings, CoordinatorSettings):
        raise TypeError("coordinator_settings must be CoordinatorSettings")
    if not isinstance(detector, dict) or any(
        not isinstance(key, str) or not key for key in detector
    ):
        raise ValueError("detector metadata must be a string-keyed dictionary")
    if not isinstance(artifacts, dict) or any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or not value
        for key, value in artifacts.items()
    ):
        raise ValueError(
            "artifacts must be a non-empty-string dictionary"
        )
    if not execution.started_at_utc or not execution.completed_at_utc:
        raise ValueError("execution timestamps must be non-empty")
    if execution.reference_worker.role != "reference":
        raise ValueError("reference worker metadata role is invalid")
    if execution.candidate_worker.role != "candidate":
        raise ValueError("candidate worker metadata role is invalid")


def _validated_pass_evidence(
    execution: BenchmarkExecution,
    samples: tuple[CpuEvaluationSample, ...],
) -> tuple[
    tuple[PairedPass, ...],
    tuple[BenchmarkImageRow, ...],
    tuple[BenchmarkImageRow, ...],
    tuple[ImageRegressionRecord, ...],
    tuple[ImageRegressionRecord, ...],
]:
    if not execution.passes:
        raise ValueError("benchmark execution must contain measured passes")
    expected_keys = tuple(sample.key for sample in samples)
    paired: list[PairedPass] = []
    all_reference_rows: list[BenchmarkImageRow] = []
    all_candidate_rows: list[BenchmarkImageRow] = []
    first_reference: tuple[ImageRegressionRecord, ...] | None = None
    first_candidate: tuple[ImageRegressionRecord, ...] | None = None

    for expected_index, coordinated in enumerate(execution.passes):
        if not isinstance(coordinated, CoordinatedPass):
            raise ValueError("execution passes must contain CoordinatedPass values")
        if coordinated.pass_index != expected_index:
            raise ValueError("pass indexes must be contiguous from zero")
        _validate_pass_side(
            coordinated,
            "reference",
            execution.reference_worker,
            samples,
            expected_keys,
        )
        _validate_pass_side(
            coordinated,
            "candidate",
            execution.candidate_worker,
            samples,
            expected_keys,
        )
        reference_rows = tuple(coordinated.reference.rows)
        candidate_rows = tuple(coordinated.candidate.rows)
        reference_records = _image_records(reference_rows)
        candidate_records = _image_records(candidate_rows)
        if first_reference is None:
            first_reference = reference_records
            first_candidate = candidate_records
        elif (
            reference_records != first_reference
            or candidate_records != first_candidate
        ):
            raise ValueError(
                "object regression records must remain deterministic "
                "across every measured pass"
            )
        paired.append(
            PairedPass(
                pass_index=coordinated.pass_index,
                order=coordinated.order,
                reference=tuple(
                    ImageLatency(row.key, row.total_ms)
                    for row in reference_rows
                ),
                candidate=tuple(
                    ImageLatency(row.key, row.total_ms)
                    for row in candidate_rows
                ),
            )
        )
        all_reference_rows.extend(reference_rows)
        all_candidate_rows.extend(candidate_rows)

    assert first_reference is not None and first_candidate is not None
    return (
        tuple(paired),
        tuple(all_reference_rows),
        tuple(all_candidate_rows),
        first_reference,
        first_candidate,
    )


def _validate_pass_side(
    coordinated: CoordinatedPass,
    role: Literal["reference", "candidate"],
    worker: WorkerMetadata,
    samples: tuple[CpuEvaluationSample, ...],
    expected_keys: tuple[str, ...],
) -> None:
    result = getattr(coordinated, role)
    if (
        result.role != role
        or result.worker_pid != worker.pid
        or result.pass_index != coordinated.pass_index
    ):
        raise ValueError(f"{role} pass provenance is inconsistent")
    rows = tuple(result.rows)
    if tuple(row.key for row in rows) != expected_keys:
        raise ValueError(
            f"{role} pass rows must preserve ordered sample keys"
        )
    for row, sample in zip(rows, samples, strict=True):
        if row.profile != sample.profile:
            raise ValueError("benchmark row profile did not match its sample")
        if row.object_count != len(sample.targets):
            raise ValueError(
                "benchmark row object_count did not match its sample"
            )
        expected_objects = tuple(
            (target.annotation_id, target.sku_id)
            for target in sample.targets
        )
        actual_objects = tuple(
            (record.annotation_id, record.expected_sku)
            for record in row.records
        )
        if actual_objects != expected_objects:
            raise ValueError(
                "benchmark row records did not match sample annotations"
            )


def _image_records(
    rows: tuple[BenchmarkImageRow, ...],
) -> tuple[ImageRegressionRecord, ...]:
    return tuple(
        ImageRegressionRecord(
            sample_key=row.key,
            objects=row.records,
            false_positive_proposal_indices=(
                row.false_positive_proposal_indices
            ),
        )
        for row in rows
    )


def _summary_row(row: BenchmarkImageRow) -> dict[str, object]:
    return {
        "profile": row.profile,
        "object_count": row.object_count,
        "dino_object_count": row.dino_object_count,
        "registered_count": row.registered_count,
        "unknown_count": row.unknown_count,
        "canonical_ms": row.canonical_ms,
        "detector_ms": row.detector_ms,
        "crop_ms": row.crop_ms,
        "repvit_ms": row.repvit_ms,
        "dinov3_ms": row.dinov3_ms,
        "fusion_ms": row.fusion_ms,
        "elapsed_ms": row.total_ms,
    }


def _serialize_pass(value: CoordinatedPass) -> dict[str, object]:
    return {
        "pass_index": value.pass_index,
        "order": value.order,
        "image_keys": [row.key for row in value.reference.rows],
        "reference": [_serialize_row(row) for row in value.reference.rows],
        "candidate": [_serialize_row(row) for row in value.candidate.rows],
    }


def _serialize_row(row: BenchmarkImageRow) -> dict[str, object]:
    return {
        "key": row.key,
        "profile": row.profile,
        "object_count": row.object_count,
        "total_ms": row.total_ms,
        "canonical_ms": row.canonical_ms,
        "detector_ms": row.detector_ms,
        "crop_ms": row.crop_ms,
        "repvit_ms": row.repvit_ms,
        "dinov3_ms": row.dinov3_ms,
        "fusion_ms": row.fusion_ms,
        "dino_object_count": row.dino_object_count,
        "registered_count": row.registered_count,
        "unknown_count": row.unknown_count,
        "records": [_serialize_object(record) for record in row.records],
        "false_positive_proposal_indices": list(
            row.false_positive_proposal_indices
        ),
    }


def _serialize_object(record: ObjectRecord | None) -> dict[str, object] | None:
    if record is None:
        return None
    return {
        "sample_key": record.sample_key,
        "annotation_id": record.annotation_id,
        "expected_sku": record.expected_sku,
        "outcome": record.outcome.value,
        "predicted_sku": record.predicted_sku,
        "top3_sku_ids": list(record.top3_sku_ids),
        "matched_proposal_index": record.matched_proposal_index,
        "iou": record.iou,
    }


def _serialize_worker(metadata: WorkerMetadata) -> dict[str, object]:
    return {
        "role": metadata.role,
        "pid": metadata.pid,
        "resolved_runtime": _serialize_runtime(metadata.resolved_runtime),
        "environment": _serialize_environment(metadata.environment),
        "detector_metadata": dict(metadata.detector_metadata),
        "artifact_hashes": dict(metadata.artifact_hashes),
        "warmup": _serialize_warmup(metadata.warmup),
        "stderr_path": str(metadata.stderr_path),
    }


def _serialize_runtime(runtime: ResolvedRuntime) -> dict[str, object]:
    return {
        "mode": runtime.mode,
        "device": runtime.device,
        "precision": runtime.precision,
        "intra_op_threads": runtime.intra_op_threads,
        "inter_op_threads": runtime.inter_op_threads,
        "cpu_affinity": list(runtime.cpu_affinity),
        "repvit_microbatch_objects": runtime.repvit_microbatch_objects,
        "dinov3_microbatch_objects": runtime.dinov3_microbatch_objects,
        "compile_models": list(runtime.compile_models),
    }


def _serialize_environment(
    environment: WorkerEnvironment,
) -> dict[str, object]:
    return {
        "python_version": environment.python_version,
        "pytorch_version": environment.pytorch_version,
        "torchvision_version": environment.torchvision_version,
        "numpy_version": environment.numpy_version,
        "os_name": environment.os_name,
        "os_version": environment.os_version,
        "logical_cpu_count": environment.logical_cpu_count,
        "inherited_affinity": list(environment.inherited_affinity),
        "filesystem_encoding": environment.filesystem_encoding,
        "default_encoding": environment.default_encoding,
        "utf8_mode": environment.utf8_mode,
        "gc_enabled": environment.gc_enabled,
    }


def _serialize_warmup(warmup: WarmupEvidence) -> dict[str, object]:
    return {
        "repetitions": warmup.repetitions,
        "images": [
            {
                "key": image.key,
                "profile": image.profile,
                "repetition": image.repetition,
                "started_at_utc": image.started_at_utc,
                "completed_at_utc": image.completed_at_utc,
                "stage_counts": {
                    "canonical": image.stage_counts.canonical,
                    "detector": image.stage_counts.detector,
                    "repvit": image.stage_counts.repvit,
                    "dinov3_global_local": (
                        image.stage_counts.dinov3_global_local
                    ),
                    "fusion": image.stage_counts.fusion,
                },
            }
            for image in warmup.images
        ],
    }


def _serialize_aggregate(aggregate: RunAggregate) -> dict[str, object]:
    return {
        "top1": aggregate.top1,
        "top3": aggregate.top3,
        "false_positives": aggregate.false_positives,
        "false_negatives": aggregate.false_negatives,
        "unknown": aggregate.unknown,
        "misclassified": aggregate.misclassified,
    }


def _serialize_regression(regression: Regression) -> dict[str, object]:
    return {
        "sample_key": regression.sample_key,
        "annotation_id": regression.annotation_id,
        "reason": regression.reason,
        "reference": _serialize_object(regression.reference),
        "candidate": _serialize_object(regression.candidate),
    }


def _canonical_json(payload: object) -> str:
    try:
        return json.dumps(payload, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "benchmark evidence must contain JSON-safe finite values"
        ) from exc


def _output_path(output: Path) -> Path:
    if not isinstance(output, Path):
        raise TypeError("output must be a Path")
    return output


def _sanitize_message(message: str) -> str:
    sanitized = " ".join(message.split())[:500]
    return sanitized or "worker failed"
