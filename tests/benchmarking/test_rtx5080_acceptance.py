from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import tools.artifacts.register_rtx5080_15plus5 as completion_module
from bakery_scanner.benchmarking import rtx5080_acceptance as acceptance_module
from bakery_scanner.benchmarking.oof15plus5 import FrozenOofReceipt
from bakery_scanner.benchmarking.rtx5080_acceptance import (
    REQUIRED_ARTIFACT_ROLES,
    ExecutionIndexAdmissionError,
    PerformanceSample,
    admit_completion_performance,
    build_admitted_performance_receipt,
    build_benchmark_schedule,
    build_performance_receipt,
    admit_execution_record_index,
    canonical_sha256,
    require_completion_performance_admission,
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


def test_schedule_uses_only_verified_external_execution_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    admission = _admit(monkeypatch, repository, artifacts)

    schedule = build_benchmark_schedule(admission)

    assert len(tuple(item for item in schedule if item.warmup)) == 20
    measured = tuple(item for item in schedule if not item.warmup)
    assert len(measured) == 8000
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
    assert tuple(item.slice_name for item in measured[6000:7000]) == ("count_1_2",) * 1000
    assert tuple(item.slice_name for item in measured[7000:8000]) == ("count_8_plus",) * 1000


def test_completion_capability_requires_admitted_execution_and_passed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid_samples
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    admission = _admit(monkeypatch, repository, artifacts)
    quality_receipt_sha = admission.quality_receipt_sha256
    samples = tuple(
        replace(row, quality_receipt_sha256=quality_receipt_sha) for row in valid_samples
    )
    generic = build_performance_receipt(
        samples, RUNTIME, ARTIFACTS, quality_receipt_sha256=quality_receipt_sha,
        protocol_sha256=PROTOCOL_SHA, allowed_current_crop_sha256s=CURRENT_CROPS,
    )

    with pytest.raises(ValueError, match="canonical admitted performance"):
        admit_completion_performance(admission, generic, quality_receipt_sha)
    performance = build_admitted_performance_receipt(
        admission, _admitted_samples(admission), RUNTIME, ARTIFACTS,
        quality_receipt_sha256=quality_receipt_sha, protocol_sha256=PROTOCOL_SHA,
        allowed_current_crop_sha256s=CURRENT_CROPS,
    )

    sealed = admit_completion_performance(admission, performance, quality_receipt_sha)

    assert require_completion_performance_admission(sealed).performance_receipt_sha256 == performance.receipt_sha256
    with pytest.raises(ValueError, match="verified completion"):
        require_completion_performance_admission(object())
    with pytest.raises(ValueError, match="admitted quality"):
        admit_completion_performance(admission, performance, "f" * 64)


def test_admitted_count_slots_are_performance_only_not_normal_scan_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    admission = _admit(monkeypatch, repository, artifacts)
    schedule = tuple(item for item in build_benchmark_schedule(admission) if not item.warmup)
    rows = _admitted_samples(admission)
    count_rows = [
        (item, row) for item, row in zip(schedule, rows, strict=True)
        if item.slice_name in {"count_1_2", "count_8_plus"}
    ]

    assert len(count_rows) == 2000
    assert all(row.evidence_kind == "forced_path_performance" and not row.quality_eligible for _, row in count_rows)
    assert all(1 <= row.object_count <= 2 for item, row in count_rows if item.slice_name == "count_1_2")
    assert all(row.object_count >= 8 for item, row in count_rows if item.slice_name == "count_8_plus")


def test_sealed_completion_capability_permits_development_status_only_with_typed_frozen_oof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid_samples
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    admission = _admit(monkeypatch, repository, artifacts)
    quality_receipt_sha = admission.quality_receipt_sha256
    final_policy = b"final-fusion-policy"
    performance_artifacts = dict(ARTIFACTS)
    performance_artifacts["fusion_policy"] = hashlib.sha256(final_policy).hexdigest()
    performance_artifact_sha = canonical_sha256(performance_artifacts)
    performance = build_admitted_performance_receipt(
        admission, _admitted_samples(admission, artifact_identity_sha256=performance_artifact_sha),
        RUNTIME, performance_artifacts, quality_receipt_sha256=quality_receipt_sha,
        protocol_sha256=PROTOCOL_SHA, allowed_current_crop_sha256s=CURRENT_CROPS,
    )
    sealed = admit_completion_performance(admission, performance, quality_receipt_sha)
    frozen = object.__new__(FrozenOofReceipt)
    object.__setattr__(frozen, "sha256", "e" * 64)
    monkeypatch.setattr(
        completion_module, "build_final_development_policy", lambda receipt, policy: final_policy
    )
    artifact_identities = {
        role: performance_artifacts[role]
        for role in ("rfdetr_engine", "repvit_engine", "dinov3_engine", "fusion_policy")
    }

    receipt = completion_module.build_completion_receipt(
        frozen, performance, artifact_identities,
        completion_admission=sealed, final_policy_bytes=b"source-policy",
    )

    assert receipt["status"] == "development-complete"
    assert receipt["production_status"] == "unverified"


def test_self_consistent_forged_index_is_rejected_by_trusted_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, artifacts, index_path = _admission_files(tmp_path)
    forged = json.loads(index_path.read_text(encoding="utf-8"))
    forged["records"][0]["input_sha256"] = "f" * 64
    forged["records"][0]["record_payload_sha256"] = canonical_sha256(
        {key: value for key, value in forged["records"][0].items() if key != "record_payload_sha256"}
    )
    forged["records_payload_sha256"] = canonical_sha256(forged["records"])
    forged["index_payload_sha256"] = canonical_sha256(
        {key: value for key, value in forged.items() if key != "index_payload_sha256"}
    )
    _write_json(index_path, forged)

    with pytest.raises(ExecutionIndexAdmissionError, match="SHA-256"):
        _admit(monkeypatch, repository, artifacts)


def test_self_consistent_manifest_rewrite_is_rejected_by_repository_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, artifacts, index_path = _admission_files(tmp_path)
    forged = json.loads(index_path.read_text(encoding="utf-8"))
    forged["records"][0]["input_sha256"] = "f" * 64
    forged["records"][0]["record_payload_sha256"] = canonical_sha256(
        {key: value for key, value in forged["records"][0].items() if key != "record_payload_sha256"}
    )
    forged["records_payload_sha256"] = canonical_sha256(forged["records"])
    forged["index_payload_sha256"] = canonical_sha256(
        {key: value for key, value in forged.items() if key != "index_payload_sha256"}
    )
    _write_json(index_path, forged)
    manifest_path = (
        repository
        / "benchmarks/locked-manifests/rtx5080_15plus5_execution_evidence_v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["execution_index"] = _declared(
        "external", index_path, artifacts
    )
    manifest["manifest_payload_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_payload_sha256"}
    )
    _write_json(manifest_path, manifest)

    with pytest.raises(ExecutionIndexAdmissionError, match="trusted manifest.*SHA-256"):
        _admit(monkeypatch, repository, artifacts)


def test_admission_rejects_record_input_hash_not_in_admitted_scene_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path, mismatched_scene_input=True)

    with pytest.raises(ExecutionIndexAdmissionError, match="scene input identity"):
        _admit(monkeypatch, repository, artifacts)


def test_scheduler_rejects_non_admission_and_missing_external_evidence(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="verified execution-index admission"):
        build_benchmark_schedule(object())
    with pytest.raises(ExecutionIndexAdmissionError, match="trusted manifest.*missing"):
        admit_execution_record_index(tmp_path / "external")


def test_caller_cannot_supply_a_forged_repository_trust_root(tmp_path: Path) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)

    with pytest.raises(TypeError):
        admit_execution_record_index(repository, artifacts)


def test_scheduler_rejects_post_admission_record_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    admission = _admit(monkeypatch, repository, artifacts)
    object.__setattr__(admission.records[0], "input_sha256", "f" * 64)

    with pytest.raises(ValueError, match="verified execution-index admission"):
        build_benchmark_schedule(admission)


def test_admission_rejects_trusted_manifest_parent_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, artifacts, _ = _admission_files(tmp_path)
    locked_root = repository / "benchmarks/locked-manifests"
    actual_root = repository / "benchmarks/actual-locked-manifests"
    locked_root.rename(actual_root)
    try:
        locked_root.symlink_to(actual_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(ExecutionIndexAdmissionError, match="symlink|reparse"):
        _admit(monkeypatch, repository, artifacts)


def _schedule_groups() -> dict[str, tuple[str, ...]]:
    return {
        "E": tuple(f"e-{index:03d}" for index in range(1, 101)),
        "M": tuple(f"m-{index:03d}" for index in range(1, 100)),
        "H": tuple(f"h-{index:03d}" for index in range(1, 101)),
    }


def _admit(
    monkeypatch: pytest.MonkeyPatch, repository: Path, artifacts: Path
) -> object:
    monkeypatch.setattr(
        acceptance_module, "_canonical_repository_root", lambda: repository
    )
    return admit_execution_record_index(artifacts)


def _admitted_samples(
    admission: object, *, artifact_identity_sha256: str = ARTIFACT_SHA
) -> tuple[PerformanceSample, ...]:
    schedule = tuple(item for item in build_benchmark_schedule(admission) if not item.warmup)
    rows: list[PerformanceSample] = []
    for item in schedule:
        if item.slice_name in {"E", "M", "H"}:
            row = _sample(item.ordinal, group=item.group)
        elif item.slice_name == "dinov3":
            row = _sample(item.ordinal, group=item.group, dino=True, evidence_kind="forced_path_performance")
        elif item.slice_name == "needs_retake":
            row = _sample(item.ordinal, group=item.group, retake=True, evidence_kind="forced_path_performance")
        elif item.slice_name == "unknown":
            row = _sample(item.ordinal, group=item.group, dino=True, unknown=True, evidence_kind="forced_path_performance")
        elif item.slice_name == "count_1_2":
            row = _sample(item.ordinal, group=item.group, object_count=1, evidence_kind="forced_path_performance")
        else:
            assert item.slice_name == "count_8_plus"
            row = _sample(item.ordinal, group=item.group, object_count=8, evidence_kind="forced_path_performance")
        rows.append(
            replace(
                row, image_id=item.scene_id,
                input_sha256=admission.scene_input_sha256[item.scene_id],
                quality_receipt_sha256=admission.quality_receipt_sha256,
                artifact_identity_sha256=artifact_identity_sha256,
            )
        )
    return tuple(rows)


def _admission_files(
    tmp_path: Path, *, mismatched_scene_input: bool = False
) -> tuple[Path, Path, Path]:
    repository = tmp_path / "repository"
    artifacts = tmp_path / "external"
    split_root = repository / "data/splits/rtx5080_15plus5_oof_v1"
    locked_root = repository / "benchmarks/locked-manifests"
    split_root.mkdir(parents=True)
    locked_root.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    groups = _schedule_groups()
    scene_ids = tuple(scene for group in ("E", "M", "H") for scene in groups[group])
    inventory_base = {
        "schema_version": 1,
        "source_sha256": "1" * 64,
        "scene_count": 299,
        "box_count": 0,
        "difficulty_counts": {"E": 100, "H": 100, "M": 99},
        "isolated_counts": {},
        "scene_ids": list(scene_ids),
    }
    inventory = {**inventory_base, "manifest_sha256": canonical_sha256(inventory_base)}
    inventory_path = split_root / "inventory.json"
    _write_json(inventory_path, inventory)
    fold_paths: list[Path] = []
    for fold in range(5):
        evaluation = list(scene_ids[fold::5])
        fold_base = {
            "schema_version": 1,
            "fold_index": fold,
            "seed": 20260803,
            "source_sha256": "1" * 64,
            "scene_ids": {"train": [], "calibration": [], "evaluation": evaluation},
        }
        path = split_root / f"fold-{fold}.json"
        _write_json(path, {**fold_base, "manifest_sha256": canonical_sha256(fold_base)})
        fold_paths.append(path)
    execution_path = artifacts / "execution-receipt.json"
    quality_path = artifacts / "quality-receipt.json"
    _write_sealed_receipt(execution_path, "verified_actual_execution")
    _write_sealed_receipt(quality_path, "quality-passed-performance-unverified")
    execution_sha = hashlib.sha256(execution_path.read_bytes()).hexdigest()
    quality_sha = hashlib.sha256(quality_path.read_bytes()).hexdigest()
    input_identities = {
        scene_id: hashlib.sha256(scene_id.encode()).hexdigest() for scene_id in scene_ids
    }
    scene_map_base = {
        "schema_version": 1,
        "inventory_manifest_sha256": inventory["manifest_sha256"],
        "fold_manifest_sha256": {
            str(index): json.loads(path.read_text(encoding="utf-8"))["manifest_sha256"]
            for index, path in enumerate(fold_paths)
        },
        "scene_input_sha256": input_identities,
    }
    scene_map = {**scene_map_base, "payload_sha256": canonical_sha256(scene_map_base)}
    scene_map_path = artifacts / "scene-input-identities.json"
    _write_json(scene_map_path, scene_map)
    records = (
        _execution_record("e-001", "dinov3", execution_sha256=execution_sha, quality_sha256=quality_sha),
        _execution_record("e-010", "dinov3", execution_sha256=execution_sha, quality_sha256=quality_sha),
        _execution_record("m-001", "needs_retake", execution_sha256=execution_sha, quality_sha256=quality_sha),
        _execution_record("m-010", "needs_retake", execution_sha256=execution_sha, quality_sha256=quality_sha),
        _execution_record("h-001", "unknown", execution_sha256=execution_sha, quality_sha256=quality_sha),
        _execution_record("h-010", "unknown", execution_sha256=execution_sha, quality_sha256=quality_sha),
    )
    if mismatched_scene_input:
        records[0]["input_sha256"] = "f" * 64
        records[0]["record_payload_sha256"] = canonical_sha256(
            {key: value for key, value in records[0].items() if key != "record_payload_sha256"}
        )
    index_base = {
        "schema_version": 3,
        "artifact_id": "rtx5080_actual_path_execution_index_v1",
        "execution_receipt_content_sha256": execution_sha,
        "quality_receipt_content_sha256": quality_sha,
        "records": list(records),
        "records_payload_sha256": canonical_sha256(list(records)),
    }
    index = {**index_base, "index_payload_sha256": canonical_sha256(index_base)}
    index_path = artifacts / "execution-index.json"
    _write_json(index_path, index)
    manifest_base = {
        "schema_version": 1,
        "manifest_id": "rtx5080_15plus5_execution_evidence_v1",
        "artifacts": {
            "execution_index": _declared("external", index_path, artifacts),
            "execution_receipt": _declared("external", execution_path, artifacts),
            "quality_receipt": _declared("external", quality_path, artifacts),
            "scene_input_identities": _declared("external", scene_map_path, artifacts),
            "split_inventory": _declared("repository", inventory_path, repository),
        },
        "fold_manifests": [
            _declared("repository", path, repository) for path in fold_paths
        ],
    }
    manifest = {**manifest_base, "manifest_payload_sha256": canonical_sha256(manifest_base)}
    manifest_path = locked_root / "rtx5080_15plus5_execution_evidence_v1.json"
    _write_json(manifest_path, manifest)
    manifest_raw = manifest_path.read_bytes()
    _write_json(
        repository / "artifacts.lock.json",
        {
            "schema_version": 1,
            "canonical_pipeline": "rfdetr_l_repvit_m1_dinov3_vits16_cpu",
            "artifacts": [
                {
                    "id": "rtx5080_15plus5_execution_evidence_manifest_v1",
                    "kind": "benchmark-evidence-manifest",
                    "local_path": "benchmarks/locked-manifests/rtx5080_15plus5_execution_evidence_v1.json",
                    "sha256": hashlib.sha256(manifest_raw).hexdigest(),
                    "bytes": len(manifest_raw),
                    "storage": "git",
                }
            ],
        },
    )
    return repository, artifacts, index_path


def _declared(root: str, path: Path, base: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "root": root,
        "local_path": path.relative_to(base).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_sealed_receipt(path: Path, status: str) -> None:
    base = {"schema_version": 3, "status": status}
    _write_json(path, {**base, "receipt_sha256": canonical_sha256(base)})


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
