from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.cpu_benchmark_coordinator import (
    BenchmarkExecution,
    CoordinatedPass,
)
from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PassResult,
    ProtocolState,
    ResolvedRuntime,
    WarmupEvidence,
    WarmupImageEvidence,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerError,
    WorkerMetadata,
)
from bakery_scanner.e2e.cpu_benchmark_report import (
    CoordinatorSettings,
    build_benchmark_report,
    publish_benchmark_failure,
    publish_benchmark_report,
)
from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample, CpuEvaluationTarget
from bakery_scanner.e2e.cpu_regression import ObjectOutcome, ObjectRecord


_ROOT = Path(__file__).resolve().parents[2]
_STARTED = "2026-07-30T01:00:00+00:00"
_COMPLETED = "2026-07-30T02:00:00+00:00"


def _samples() -> tuple[CpuEvaluationSample, ...]:
    return (
        CpuEvaluationSample(
            key="fixture/e.jpg",
            source="fixture",
            source_image_id=1,
            image_path=Path("fixture/e.jpg"),
            profile="E",
            targets=(
                CpuEvaluationTarget(1, 1, Box(0, 0, 10, 10)),
                CpuEvaluationTarget(2, 2, Box(20, 20, 10, 10)),
            ),
        ),
        CpuEvaluationSample(
            key="fixture/m.jpg",
            source="fixture",
            source_image_id=2,
            image_path=Path("fixture/m.jpg"),
            profile="M",
            targets=(CpuEvaluationTarget(3, 3, Box(0, 0, 10, 10)),),
        ),
        CpuEvaluationSample(
            key="fixture/h.jpg",
            source="fixture",
            source_image_id=3,
            image_path=Path("fixture/h.jpg"),
            profile="H",
            targets=(CpuEvaluationTarget(4, 4, Box(0, 0, 10, 10)),),
        ),
    )


def _records(sample: CpuEvaluationSample) -> tuple[ObjectRecord, ...]:
    if sample.profile == "E":
        return (
            ObjectRecord(
                sample_key=sample.key,
                annotation_id=1,
                expected_sku=1,
                outcome=ObjectOutcome.CORRECT,
                predicted_sku=1,
                top3_sku_ids=(),
                matched_proposal_index=0,
                iou=1.0,
            ),
            ObjectRecord(
                sample_key=sample.key,
                annotation_id=2,
                expected_sku=2,
                outcome=ObjectOutcome.MISSED,
                predicted_sku=None,
                top3_sku_ids=(),
                matched_proposal_index=None,
                iou=None,
            ),
        )
    target = sample.targets[0]
    return (
        ObjectRecord(
            sample_key=sample.key,
            annotation_id=target.annotation_id,
            expected_sku=target.sku_id,
            outcome=ObjectOutcome.CORRECT,
            predicted_sku=target.sku_id,
            top3_sku_ids=(),
            matched_proposal_index=0,
            iou=1.0,
        ),
    )


def _row(
    sample: CpuEvaluationSample,
    *,
    total_ms: float,
    dino_object_count: int,
    timing_offset: float,
) -> BenchmarkImageRow:
    is_e = sample.profile == "E"
    return BenchmarkImageRow(
        key=sample.key,
        profile=sample.profile,
        object_count=len(sample.targets),
        total_ms=total_ms,
        records=_records(sample),
        false_positive_proposal_indices=(1, 2, 3) if is_e else (),
        canonical_ms=1.0 + timing_offset,
        detector_ms=2.0 + timing_offset,
        crop_ms=3.0 + timing_offset,
        repvit_ms=4.0 + timing_offset,
        dinov3_ms=5.0 + timing_offset,
        fusion_ms=6.0 + timing_offset,
        dino_object_count=dino_object_count if is_e else 0,
        registered_count=3 if is_e else 1,
        unknown_count=1 if is_e else 0,
    )


def _runtime(role: str) -> ResolvedRuntime:
    return ResolvedRuntime(
        mode="serial_reference" if role == "reference" else "batch_pytorch",
        device="CPU",
        precision="FP32",
        intra_op_threads=8,
        inter_op_threads=1,
        cpu_affinity=tuple(range(8)),
        repvit_microbatch_objects=1 if role == "reference" else 4,
        dinov3_microbatch_objects=1 if role == "reference" else 2,
        compile_models=(),
    )


def _environment() -> WorkerEnvironment:
    return WorkerEnvironment(
        python_version="3.12.4",
        pytorch_version="2.7.1",
        torchvision_version="0.22.1",
        numpy_version="2.2.6",
        os_name="nt",
        os_version="Windows 11",
        logical_cpu_count=16,
        inherited_affinity=tuple(range(8)),
        filesystem_encoding="utf-8",
        default_encoding="utf-8",
        utf8_mode=1,
        gc_enabled=False,
    )


def _warmup() -> WarmupEvidence:
    images = tuple(
        WarmupImageEvidence(
            key=f"warmup/{profile.lower()}.jpg",
            profile=profile,
            repetition=repetition,
            started_at_utc=_STARTED,
            completed_at_utc=_COMPLETED,
            stage_counts=WarmupStageCounts(1, 1, 1, 1, 1),
        )
        for repetition in (1, 2)
        for profile in ("E", "M", "H")
    )
    return WarmupEvidence(repetitions=2, images=images)


def _worker(role: str) -> WorkerMetadata:
    return WorkerMetadata(
        role=role,
        pid=101 if role == "reference" else 202,
        resolved_runtime=_runtime(role),
        environment=_environment(),
        detector_metadata=tuple(_detector_metadata().items()),
        artifact_hashes=tuple(_artifact_hashes().items()),
        warmup=_warmup(),
        stderr_path=Path(f"logs/{role}.stderr.log"),
    )


def _execution() -> BenchmarkExecution:
    samples = _samples()
    reference_totals = (100.0, 110.0, 120.0)
    candidate_totals = (
        (130.0, 140.0, 150.0),
        (50.0, 60.0, 70.0),
        (50.0, 60.0, 70.0),
    )
    passes = []
    for pass_index, order in enumerate(("AB", "BA", "AB")):
        reference_rows = tuple(
            _row(
                sample,
                total_ms=reference_totals[index],
                dino_object_count=2,
                timing_offset=float(pass_index),
            )
            for index, sample in enumerate(samples)
        )
        candidate_rows = tuple(
            _row(
                sample,
                total_ms=candidate_totals[pass_index][index],
                dino_object_count=1,
                timing_offset=float(10 + pass_index),
            )
            for index, sample in enumerate(samples)
        )
        passes.append(
            CoordinatedPass(
                pass_index=pass_index,
                order=order,
                reference=PassResult(
                    role="reference",
                    worker_pid=101,
                    pass_index=pass_index,
                    rows=reference_rows,
                ),
                candidate=PassResult(
                    role="candidate",
                    worker_pid=202,
                    pass_index=pass_index,
                    rows=candidate_rows,
                ),
            )
        )
    return BenchmarkExecution(
        reference_worker=_worker("reference"),
        candidate_worker=_worker("candidate"),
        passes=tuple(passes),
        started_at_utc=_STARTED,
        completed_at_utc=_COMPLETED,
    )


def _detector_metadata() -> dict[str, object]:
    return {
        "artifact_id": "rfdetr_large_bakery_v1",
        "score_threshold": 0.5691395401954651,
        "manifest_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "calibration_sha256": "c" * 64,
    }


def _artifact_hashes() -> dict[str, str]:
    return {
        "classifier_config_sha256": "d" * 64,
        "ordered_image_list_sha256": "e" * 64,
    }


def _settings() -> CoordinatorSettings:
    return CoordinatorSettings(900.0, 7200.0, 30.0)


def _report(*, sample_profile="all299") -> dict[str, object]:
    return build_benchmark_report(
        execution=_execution(),
        samples=_samples(),
        detector=_detector_metadata(),
        artifacts=_artifact_hashes(),
        sample_profile=sample_profile,
        bootstrap_seed=20260729,
        coordinator_settings=_settings(),
    )


def test_v3_report_contains_resolved_workers_and_bilateral_profiles():
    report = _report()

    assert report["schema_version"] == 3
    assert (
        report["workers"]["reference"]["resolved_runtime"]["intra_op_threads"]
        == 8
    )
    assert (
        report["workers"]["candidate"]["resolved_runtime"][
            "repvit_microbatch_objects"
        ]
        == 4
    )
    assert report["profiles"]["reference"]["E"][
        "dino_execution_rate"
    ] == pytest.approx(0.5)
    assert report["profiles"]["candidate"]["E"][
        "dino_execution_rate"
    ] == pytest.approx(0.25)
    assert report["profiles"]["candidate"]["E"]["images"] == 3
    assert report["profiles"]["candidate"]["E"]["total"][
        "mean_ms"
    ] == pytest.approx(230.0 / 3.0)
    assert report["created_at_utc"] == _STARTED
    assert report["completed_at_utc"] == _COMPLETED


def test_v3_report_has_no_null_resolved_runtime_or_environment_values():
    report = _report()

    assert all(
        value is not None
        for worker in report["workers"].values()
        for section in ("resolved_runtime", "environment")
        for value in worker[section].values()
    )
    assert report["workers"]["reference"]["warmup"]["repetitions"] == 2
    assert len(report["workers"]["candidate"]["warmup"]["images"]) == 6
    assert report["coordinator"] == {
        "started_at_utc": _STARTED,
        "completed_at_utc": _COMPLETED,
        "ready_timeout_s": 900.0,
        "pass_timeout_s": 7200.0,
        "shutdown_timeout_s": 30.0,
    }


def test_v3_report_serializes_every_pass_stage_and_uses_all_paired_latency():
    report = _report()

    assert tuple(value["order"] for value in report["passes"]) == (
        "AB",
        "BA",
        "AB",
    )
    assert report["passes"][0]["image_keys"] == [
        "fixture/e.jpg",
        "fixture/m.jpg",
        "fixture/h.jpg",
    ]
    first_candidate = report["passes"][0]["candidate"][0]
    assert first_candidate["total_ms"] == 130.0
    assert first_candidate["canonical_ms"] == 11.0
    assert first_candidate["detector_ms"] == 12.0
    assert first_candidate["crop_ms"] == 13.0
    assert first_candidate["repvit_ms"] == 14.0
    assert first_candidate["dinov3_ms"] == 15.0
    assert first_candidate["fusion_ms"] == 16.0
    assert first_candidate["dino_object_count"] == 1
    assert first_candidate["registered_count"] == 3
    assert first_candidate["unknown_count"] == 1
    assert report["latency_gate"]["pass_count"] == 3
    assert report["latency_gate"]["mean_delta_ms"] == pytest.approx(-70.0 / 3.0)


def test_quality_uses_image_records_and_all299_floors_without_losing_misses_or_fp():
    report = _report()

    assert report["quality_gate"]["reference"]["false_positives"] == 3
    assert report["quality_gate"]["candidate"]["false_positives"] == 3
    assert report["quality_gate"]["candidate"]["false_negatives"] == 1
    assert report["quality_gate"]["regressions"] == []
    assert report["quality_gate"]["passed"] is False
    first_e = report["passes"][0]["candidate"][0]
    assert first_e["false_positive_proposal_indices"] == [1, 2, 3]
    assert [record["outcome"] for record in first_e["records"]] == [
        "correct",
        "missed",
    ]


def test_non_acceptance_profile_applies_transition_gate_without_all299_floors():
    report = _report(sample_profile="batch2_e3_m3_h3")

    assert report["quality_gate"]["scope"] == "batch2_e3_m3_h3"
    assert report["quality_gate"]["passed"] is True


def test_v3_report_rejects_record_or_false_positive_drift_across_passes():
    execution = _execution()
    second_pass = execution.passes[1]
    changed_row = replace(
        second_pass.candidate.rows[0],
        false_positive_proposal_indices=(1, 2),
    )
    changed_result = replace(
        second_pass.candidate,
        rows=(changed_row, *second_pass.candidate.rows[1:]),
    )
    execution = replace(
        execution,
        passes=(
            execution.passes[0],
            replace(second_pass, candidate=changed_result),
            execution.passes[2],
        ),
    )

    with pytest.raises(ValueError, match="deterministic"):
        build_benchmark_report(
            execution=execution,
            samples=_samples(),
            detector=_detector_metadata(),
            artifacts=_artifact_hashes(),
            sample_profile="all299",
            bootstrap_seed=20260729,
            coordinator_settings=_settings(),
        )


def test_publish_refuses_overwrite_and_rejects_non_finite_json(tmp_path):
    output = tmp_path / "report"
    output.mkdir()

    with pytest.raises(FileExistsError, match="overwrite"):
        publish_benchmark_report(output, {"schema_version": 3})
    with pytest.raises(ValueError, match="finite"):
        publish_benchmark_report(tmp_path / "new", {"value": float("nan")})

    assert not (tmp_path / "new").exists()


@pytest.mark.artifact
def test_publish_is_canonical_atomic_and_leaves_v2_fixture_bytes_unchanged(
    tmp_path,
):
    fixture = (
        _ROOT
        / "artifacts"
        / "evaluations"
        / "cpu-monotonic-serial-20260729-185954"
        / "report.json"
    )
    before = fixture.read_bytes()
    report = _report()
    output = tmp_path / "published"

    publish_benchmark_report(output, report)

    encoded = (output / "report.json").read_text(encoding="utf-8")
    assert encoded == json.dumps(report, allow_nan=False, sort_keys=True)
    assert fixture.read_bytes() == before
    assert not tuple(tmp_path.glob(".published.staging-*"))


def test_failure_publication_is_sanitized_and_records_coordinator_settings(
    tmp_path,
):
    raw_message = (
        "worker failed\nwithout traceback locals "
        + "x" * 500
        + " SECRET_AFTER_LIMIT"
    )
    failure = WorkerError(
        exception_type="RuntimeError",
        message=raw_message,
        role="candidate",
        pid=202,
        protocol_state=ProtocolState.RUNNING_PASS,
        pass_index=1,
        stderr_path=Path("logs/candidate.stderr.log"),
    )

    failure_path = publish_benchmark_failure(
        tmp_path / "report",
        failure,
        coordinator_settings=_settings(),
    )

    assert failure_path.parent == tmp_path
    assert failure_path.name.startswith("report.failed.")
    payload = json.loads(
        (failure_path / "failure.json").read_text(encoding="utf-8")
    )
    assert payload["failure"] == {
        "exception_type": "RuntimeError",
        "message": " ".join(raw_message.split())[:500],
        "role": "candidate",
        "pid": 202,
        "protocol_state": "running_pass",
        "pass_index": 1,
        "stderr_path": str(Path("logs/candidate.stderr.log")),
    }
    assert payload["coordinator"]["pass_timeout_s"] == 7200.0
    assert "\n" not in payload["failure"]["message"]
    assert "SECRET_AFTER_LIMIT" not in payload["failure"]["message"]


@pytest.mark.parametrize("value", (0.0, -1.0, float("nan"), float("inf")))
def test_coordinator_settings_require_finite_positive_timeouts(value):
    with pytest.raises(ValueError, match="finite positive"):
        CoordinatorSettings(value, 7200.0, 30.0)
