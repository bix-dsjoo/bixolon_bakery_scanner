from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from bakery_scanner.benchmarking.rtx5080_acceptance import (
    REQUIRED_ARTIFACT_ROLES,
    ExecutionRecordIndexArtifact,
    PerformanceSample,
    build_benchmark_schedule,
    build_performance_receipt,
    canonical_sha256,
    summarize_latency_ms,
    validate_protocol,
)


RUNTIME = {
    "device": "cuda:0",
    "gpu_name": "NVIDIA GeForce RTX 5080",
    "compute_capability": "12.0",
    "driver_version": "580.88",
    "cuda_version": "13.0",
    "tensorrt_version": "10.13.2",
    "windows_build": "26100",
    "wddm_version": "3.2",
    "runtime_manifest_sha256": "a" * 64,
    "fallback_reason": None,
}
ARTIFACTS = {role: hashlib.sha256(role.encode()).hexdigest() for role in REQUIRED_ARTIFACT_ROLES}
QUALITY_SHA = "b" * 64
PROTOCOL_SHA = "c" * 64
RUNTIME_SHA = canonical_sha256(RUNTIME)
ARTIFACT_SHA = canonical_sha256(ARTIFACTS)
CURRENT_CROPS = frozenset({"d" * 64, "e" * 64})
EXECUTION_SHA = "9" * 64


def _sample(
    index: int,
    *,
    group: str,
    object_count: int = 4,
    dino: bool = False,
    retake: bool = False,
    unknown: bool = False,
    evidence_kind: str = "current_quality",
    total: float = 50.0,
) -> PerformanceSample:
    forced = evidence_kind == "forced_path_performance"
    return PerformanceSample(
        schema_version=3,
        request_id=f"request-{group}-{object_count}-{index}",
        image_id=f"image-{group}-{index % 100}",
        group=group,
        evidence_kind=evidence_kind,
        quality_eligible=not forced,
        input_sha256=hashlib.sha256(f"input-{group}-{index}".encode()).hexdigest(),
        source_crop_sha256s=("d" * 64,) * object_count if forced else (),
        object_count=object_count,
        dino_object_count=object_count if dino else 0,
        dino_executed=dino,
        needs_retake=retake,
        unknown=unknown,
        warmed=True,
        runtime_identity_sha256=RUNTIME_SHA,
        artifact_identity_sha256=ARTIFACT_SHA,
        quality_receipt_sha256=QUALITY_SHA,
        protocol_sha256=PROTOCOL_SHA,
        fallback_reason=None,
        thermal={
            "gpu_temperature_c": 62.0,
            "gpu_clock_mhz": 2700.0,
            "memory_clock_mhz": 15000.0,
            "power_w": 210.0,
            "thermal_throttled": False,
        },
        timings_ms={
            "decode_canonical": 5.0,
            "detector": 25.0,
            "completeness": 4.0,
            "crop": 3.0,
            "repvit": 8.0,
            "direct_gate": 1.0,
            "dinov3": 10.0 if dino else 0.0,
            "fusion_payload": 3.0,
            "total": total,
        },
    )


def _execution_record(
    scene_id: str, path_name: str, *, execution_sha256: str = EXECUTION_SHA,
    quality_sha256: str = QUALITY_SHA,
) -> dict[str, object]:
    dino = path_name in {"dinov3", "unknown"}
    retake = path_name == "needs_retake"
    unknown = path_name == "unknown"
    record: dict[str, object] = {
        "scene_id": scene_id,
        "input_sha256": hashlib.sha256(scene_id.encode()).hexdigest(),
        "execution_receipt_content_sha256": execution_sha256,
        "quality_receipt_content_sha256": quality_sha256,
        "state": "needs_retake" if retake else "accepted_scan",
        "dino_executed": dino,
        "dino_object_count": 4 if dino else 0,
        "needs_retake": retake,
        "unknown": unknown,
        "unknown_total": 1 if unknown else 0,
    }
    record["record_payload_sha256"] = canonical_sha256(record)
    return record


def _index_fixture(
    records: tuple[dict[str, object], ...] | None = None,
    *,
    execution_sha256: str = EXECUTION_SHA,
    quality_sha256: str = QUALITY_SHA,
) -> tuple[ExecutionRecordIndexArtifact, object]:
    rows = records or (
        _execution_record("e-001", "dinov3", execution_sha256=execution_sha256, quality_sha256=quality_sha256),
        _execution_record("m-001", "needs_retake", execution_sha256=execution_sha256, quality_sha256=quality_sha256),
        _execution_record("h-001", "unknown", execution_sha256=execution_sha256, quality_sha256=quality_sha256),
    )
    index: dict[str, object] = {
        "schema_version": 3,
        "artifact_id": "rtx5080_actual_path_execution_index_v1",
        "execution_receipt_content_sha256": execution_sha256,
        "quality_receipt_content_sha256": quality_sha256,
        "records": list(rows),
        "records_payload_sha256": canonical_sha256(list(rows)),
    }
    index["index_payload_sha256"] = canonical_sha256(index)
    raw = json.dumps(
        index, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    artifact = ExecutionRecordIndexArtifact(
        artifact_id="rtx5080_actual_path_execution_index_v1",
        path=Path("external/actual-path-index.json"),
        bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    return artifact, lambda _artifact: raw


@pytest.fixture(scope="module")
def valid_samples() -> tuple[PerformanceSample, ...]:
    rows: list[PerformanceSample] = []
    rows.extend(_sample(i, group="E") for i in range(1001))
    rows.extend(_sample(i, group="M") for i in range(1001))
    rows.extend(_sample(i, group="H") for i in range(1001))
    rows.extend(
        _sample(
            i, group="E", dino=True, evidence_kind="forced_path_performance"
        )
        for i in range(2000, 3000)
    )
    rows.extend(
        _sample(
            i,
            group="E",
            dino=True,
            unknown=True,
            evidence_kind="forced_path_performance",
        )
        for i in range(3000, 4000)
    )
    rows.extend(
        _sample(
            i, group="M", retake=True, evidence_kind="forced_path_performance"
        )
        for i in range(2000, 3000)
    )
    rows.extend(
        _sample(i, group="E", object_count=1, evidence_kind="forced_path_performance")
        for i in range(1000, 2000)
    )
    rows.extend(
        _sample(i, group="H", object_count=8, evidence_kind="forced_path_performance")
        for i in range(1000, 2000)
    )
    return tuple(rows)


def _build(samples: tuple[PerformanceSample, ...]):
    return build_performance_receipt(
        samples,
        RUNTIME,
        ARTIFACTS,
        quality_receipt_sha256=QUALITY_SHA,
        protocol_sha256=PROTOCOL_SHA,
        allowed_current_crop_sha256s=CURRENT_CROPS,
    )


def test_schema_v3_receipt_passes_only_complete_under_100ms_evidence(valid_samples) -> None:
    receipt = _build(valid_samples)

    assert receipt.schema_version == 3
    assert receipt.status == "performance-passed"
    assert receipt.summaries["overall"]["sample_count"] == 3003
    assert receipt.summaries["count_1_2"]["quality_eligible"] is False
    assert receipt.summaries["count_8_plus"]["evidence_kind"] == "forced_path_performance"
    assert receipt.summaries["count_3_7"]["quality_eligible"] is True
    assert len(receipt.receipt_sha256) == 64


def test_receipt_hash_cannot_be_replaced_after_build(valid_samples) -> None:
    receipt = _build(valid_samples)

    with pytest.raises(ValueError, match="receipt hash"):
        replace(receipt, receipt_sha256="f" * 64)


@pytest.mark.parametrize(
    "slice_name",
    [
        "E", "M", "H", "dinov3", "needs_retake", "unknown",
        "count_1_2", "count_3_7", "count_8_plus",
    ],
)
def test_each_required_slice_needs_one_thousand_samples(slice_name, valid_samples) -> None:
    matching = [row for row in valid_samples if row.belongs_to(slice_name)]
    if slice_name in {"E", "M", "H"}:
        removed_ids = {row.request_id for row in matching[:2]}
        samples = tuple(row for row in valid_samples if row.request_id not in removed_ids)
    elif slice_name == "dinov3":
        removed_ids = {row.request_id for row in matching[:1001]}
        samples = tuple(row for row in valid_samples if row.request_id not in removed_ids)
    elif slice_name == "count_3_7":
        changed: list[PerformanceSample] = []
        remaining = 999
        for row in valid_samples:
            if row.belongs_to(slice_name) and remaining > 0:
                remaining -= 1
            elif row.belongs_to(slice_name):
                row = replace(row, object_count=0)
            changed.append(row)
        samples = tuple(changed)
    else:
        removed = matching[0]
        samples = tuple(row for row in valid_samples if row.request_id != removed.request_id)

    with pytest.raises(ValueError, match=rf"{slice_name} requires 1000"):
        _build(samples)


def test_one_path_over_one_hundred_ms_rejects_receipt(valid_samples) -> None:
    changed = []
    for row in valid_samples:
        if row.dino_executed and not row.unknown:
            timings = dict(row.timings_ms)
            timings["total"] = 100.01
            row = replace(row, timings_ms=timings)
        changed.append(row)

    receipt = _build(tuple(changed))

    assert receipt.status == "performance-rejected"
    assert receipt.violations == ("dinov3:p95_ms=100.01",)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: replace(row, runtime_identity_sha256="f" * 64), "runtime identity"),
        (lambda row: replace(row, artifact_identity_sha256="f" * 64), "artifact identity"),
        (lambda row: replace(row, fallback_reason="pytorch"), "fallback"),
        (
            lambda row: replace(row, thermal={**dict(row.thermal), "thermal_throttled": True}),
            "throttl",
        ),
        (
            lambda row: replace(row, timings_ms={**dict(row.timings_ms), "detector": 51.0}),
            "total must cover",
        ),
    ],
)
def test_untrusted_runtime_or_sample_evidence_is_rejected(
    valid_samples, mutation, message
) -> None:
    with pytest.raises(ValueError, match=message):
        changed = (mutation(valid_samples[0]), *valid_samples[1:])
        _build(changed)


def test_nonfinite_timing_is_rejected_before_summary(valid_samples) -> None:
    with pytest.raises(ValueError, match="finite"):
        replace(
            valid_samples[0],
            timings_ms={**dict(valid_samples[0].timings_ms), "total": float("nan")},
        )


def test_forced_count_fixture_must_use_only_current_crop_identities(valid_samples) -> None:
    row = next(item for item in valid_samples if item.belongs_to("count_1_2"))
    changed = replace(row, source_crop_sha256s=("f" * 64,))
    samples = tuple(changed if item.request_id == row.request_id else item for item in valid_samples)

    with pytest.raises(ValueError, match="current crop identities"):
        _build(samples)


def test_nearest_rank_and_bootstrap_are_deterministic() -> None:
    first = summarize_latency_ms((1.0, 2.0, 3.0, 4.0, 5.0), seed=20260803)
    second = summarize_latency_ms((5.0, 1.0, 4.0, 2.0, 3.0), seed=20260803)

    assert first == second
    assert first["p50"] == 3.0
    assert first["p90"] == 5.0
    assert first["p95"] == 5.0
    assert first["p99"] == 5.0
    assert first["max"] == 5.0
    assert first["p95_bootstrap_ci95_ms"] == (3.0, 5.0)


def test_protocol_thresholds_and_evidence_kinds_are_immutable() -> None:
    protocol = {
        "schema_version": 3,
        "minimum_warmups": 20,
        "total_p95_limit_ms": 100.01,
    }

    with pytest.raises(ValueError, match="protocol"):
        validate_protocol(protocol)


def test_schedule_has_twenty_warmups_then_sorted_deterministic_repeats() -> None:
    index, loader = _index_fixture(
        (
            _execution_record("e-010", "dinov3"),
            _execution_record("e-001", "dinov3"),
            _execution_record("m-010", "needs_retake"),
            _execution_record("m-001", "needs_retake"),
            _execution_record("h-010", "unknown"),
            _execution_record("h-001", "unknown"),
        )
    )
    schedule = build_benchmark_schedule(
        {
            "E": tuple(f"e-{index:03d}" for index in range(100, 0, -1)),
            "M": tuple(f"m-{index:03d}" for index in range(99, 0, -1)),
            "H": tuple(f"h-{index:03d}" for index in range(100, 0, -1)),
        },
        execution_index_artifact=index,
        index_loader=loader,
        execution_receipt_sha256=EXECUTION_SHA,
        quality_receipt_sha256=QUALITY_SHA,
        warmup_count=20,
        observations_per_group=1000,
        observations_per_path=1000,
    )

    assert len(tuple(item for item in schedule if item.warmup)) == 20
    measured = tuple(item for item in schedule if not item.warmup)
    assert len(measured) == 6000
    assert tuple(item.scene_id for item in measured[:4]) == (
        "e-001", "e-002", "e-003", "e-004"
    )
    assert tuple(item.group for item in measured[:1001])[-1] == "M"
    assert tuple(item.scene_id for item in measured[3000:3004]) == (
        "e-001", "e-010", "h-001", "h-010"
    )
    assert tuple(item.slice_name for item in measured[3000:4000]) == ("dinov3",) * 1000
    assert tuple(item.slice_name for item in measured[4000:5000]) == (
        "needs_retake",
    ) * 1000
    assert tuple(item.slice_name for item in measured[5000:6000]) == ("unknown",) * 1000


@pytest.mark.parametrize("path_name", ("dinov3", "needs_retake", "unknown"))
def test_schedule_rejects_empty_required_actual_path_ids(path_name: str) -> None:
    rows = tuple(
        _execution_record(scene_id, kind)
        for scene_id, kind in (
            ("e-001", "dinov3"),
            ("m-001", "needs_retake"),
            ("h-001", "unknown"),
        )
        if kind != path_name and not (path_name == "dinov3" and kind == "unknown")
    )
    index, loader = _index_fixture(rows)

    with pytest.raises(ValueError, match=rf"{path_name}.*actual path"):
        build_benchmark_schedule(
            {
                "E": tuple(f"e-{index:03d}" for index in range(1, 101)),
                "M": tuple(f"m-{index:03d}" for index in range(1, 100)),
                "H": tuple(f"h-{index:03d}" for index in range(1, 101)),
            },
            execution_index_artifact=index,
            index_loader=loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )


def test_schedule_rejects_arbitrary_current_id_without_execution_evidence() -> None:
    index, loader = _index_fixture((_execution_record("e-001", "direct"),))
    with pytest.raises(ValueError, match="actual path execution evidence"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=index,
            index_loader=loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )


def test_schedule_rejects_path_flag_or_canonical_record_hash_mismatch() -> None:
    malformed = _execution_record("e-001", "dinov3")
    malformed["dino_object_count"] = 0
    malformed["record_payload_sha256"] = canonical_sha256(
        {key: value for key, value in malformed.items() if key != "record_payload_sha256"}
    )
    malformed_index, malformed_loader = _index_fixture((malformed,))
    tampered = _execution_record("e-001", "dinov3")
    tampered["input_sha256"] = "f" * 64
    tampered_index, tampered_loader = _index_fixture((tampered,))

    with pytest.raises(ValueError, match="DINO flag|object count"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=malformed_index,
            index_loader=malformed_loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )
    with pytest.raises(ValueError, match="record hash"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=tampered_index,
            index_loader=tampered_loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )


def test_schedule_rejects_execution_or_quality_receipt_identity_mismatch() -> None:
    index, loader = _index_fixture()
    with pytest.raises(ValueError, match="execution receipt identity"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=index,
            index_loader=loader,
            execution_receipt_sha256="8" * 64,
            quality_receipt_sha256=QUALITY_SHA,
        )
    quality_index, quality_loader = _index_fixture(quality_sha256="8" * 64)
    with pytest.raises(ValueError, match="quality receipt identity"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=quality_index,
            index_loader=quality_loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )


def test_schedule_rejects_index_artifact_byte_or_payload_hash_mismatch() -> None:
    index, loader = _index_fixture()
    wrong_artifact = replace(index, sha256="f" * 64)

    with pytest.raises(ValueError, match="index artifact SHA-256"):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=wrong_artifact,
            index_loader=loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
        )


def test_scheduler_forbids_caller_authored_path_records_as_authority() -> None:
    index, loader = _index_fixture()
    with pytest.raises(TypeError):
        build_benchmark_schedule(
            _schedule_groups(),
            execution_index_artifact=index,
            index_loader=loader,
            execution_receipt_sha256=EXECUTION_SHA,
            quality_receipt_sha256=QUALITY_SHA,
            path_evidence={"dinov3": (_execution_record("e-001", "dinov3"),)},
        )


def _schedule_groups() -> dict[str, tuple[str, ...]]:
    return {
        "E": tuple(f"e-{index:03d}" for index in range(1, 101)),
        "M": tuple(f"m-{index:03d}" for index in range(1, 100)),
        "H": tuple(f"h-{index:03d}" for index in range(1, 101)),
    }
