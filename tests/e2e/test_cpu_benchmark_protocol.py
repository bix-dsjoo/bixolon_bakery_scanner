from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PrepareCommand,
    ResolvedRuntime,
    RunPassCommand,
    WarmupEvidence,
    WarmupImageEvidence,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerMetadata,
    WorkerSpec,
)
from bakery_scanner.e2e.cpu_regression import ObjectOutcome, ObjectRecord


def _worker_spec() -> WorkerSpec:
    return WorkerSpec(
        role="reference",
        mode="serial_reference",
        package_root=Path("C:/workspace/bixolon_bakery_scanner"),
        classifier_config=Path("configs/cpu_rfdetr_classifier_policy.yaml"),
        sample_profile="all299",
        runtime_overrides=(("threads", 1),),
        expected_artifact_hashes=(("policy", "a" * 64),),
    )


def _resolved_runtime() -> ResolvedRuntime:
    return ResolvedRuntime(
        mode="serial_reference",
        device="CPU",
        precision="FP32",
        intra_op_threads=1,
        inter_op_threads=1,
        cpu_affinity=(0,),
        repvit_microbatch_objects="all",
        dinov3_microbatch_objects="all",
        compile_models=(),
    )


def _record() -> ObjectRecord:
    return ObjectRecord(
        sample_key="fixtures/e_0001.jpg",
        annotation_id=1,
        expected_sku=1,
        outcome=ObjectOutcome.CORRECT,
        predicted_sku=1,
        top3_sku_ids=(),
        matched_proposal_index=0,
        iou=1.0,
    )


def _image_row() -> BenchmarkImageRow:
    return BenchmarkImageRow(
        key="fixtures/e_0001.jpg",
        profile="E",
        object_count=1,
        total_ms=10.0,
        records=(_record(),),
        false_positive_proposal_indices=(),
        canonical_ms=1.0,
        detector_ms=2.0,
        crop_ms=1.0,
        repvit_ms=3.0,
        dinov3_ms=2.0,
        fusion_ms=1.0,
        dino_object_count=0,
        registered_count=1,
        unknown_count=0,
    )


def _warmup_image(repetition: int = 1) -> WarmupImageEvidence:
    return WarmupImageEvidence(
        key="fixtures/e_0001.jpg",
        profile="E",
        repetition=repetition,
        started_at_utc="2026-07-30T00:00:00Z",
        completed_at_utc="2026-07-30T00:00:01Z",
        stage_counts=WarmupStageCounts(1, 1, 1, 0, 1),
    )


def _worker_metadata() -> WorkerMetadata:
    return WorkerMetadata(
        role="reference",
        pid=123,
        resolved_runtime=_resolved_runtime(),
        environment=WorkerEnvironment(
            python_version="3.11",
            pytorch_version="2.0",
            torchvision_version="0.15",
            numpy_version="1.0",
            os_name="Windows",
            os_version="11",
            logical_cpu_count=8,
            inherited_affinity=(0,),
            filesystem_encoding="utf-8",
            default_encoding="utf-8",
            utf8_mode=1,
            gc_enabled=True,
        ),
        detector_metadata=(("version", "v1"),),
        artifact_hashes=(("detector", "a" * 64),),
        warmup=WarmupEvidence(repetitions=2, images=(_warmup_image(),)),
        stderr_path=Path("logs/worker.stderr"),
    )


class _PickleableModel:
    pass


def test_worker_spec_is_immutable_and_requires_fixed_warmup():
    spec = _worker_spec()

    assert spec.warmup_repetitions == 2
    with pytest.raises(AttributeError):
        spec.mode = "batch_pytorch"  # type: ignore[misc]
    with pytest.raises(ValueError, match="exactly 2"):
        replace(spec, warmup_repetitions=1)


def test_resolved_runtime_rejects_null_and_non_cpu_values():
    runtime = _resolved_runtime()

    assert runtime.device == "CPU"
    assert runtime.precision == "FP32"
    with pytest.raises(ValueError, match="intra_op_threads"):
        replace(runtime, intra_op_threads=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="CPU/FP32"):
        replace(runtime, device="CUDA:0")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"total_ms": float("nan")}, "finite"),
        ({"detector_ms": -1.0}, "non-negative"),
        ({"dino_object_count": 3}, "DINO"),
        ({"registered_count": -1}, "non-negative"),
    ],
)
def test_image_row_rejects_invalid_measurement(changes, message):
    with pytest.raises(ValueError, match=message):
        replace(_image_row(), **changes)


def test_image_row_deeply_freezes_false_positive_proposal_indices():
    mutable_indices = [0]
    row = replace(
        _image_row(),
        false_positive_proposal_indices=mutable_indices,
    )

    mutable_indices.append(1)

    assert row.false_positive_proposal_indices == (0,)


def test_image_row_preserves_missed_gt_record_without_a_decision():
    missed = replace(
        _record(),
        outcome=ObjectOutcome.MISSED,
        predicted_sku=None,
        matched_proposal_index=None,
        iou=None,
    )

    row = replace(
        _image_row(),
        records=(missed,),
        registered_count=0,
        unknown_count=0,
    )

    assert row.object_count == 1
    assert row.records == (missed,)
    assert row.registered_count + row.unknown_count == 0


@pytest.mark.parametrize(
    "indices, message",
    [
        ((0, 0), "unique"),
        ((1,), "decision count"),
        ((-1,), "non-negative"),
        ((False,), "non-negative"),
    ],
)
def test_image_row_rejects_invalid_false_positive_proposal_indices(
    indices, message
):
    with pytest.raises(ValueError, match=message):
        replace(_image_row(), false_positive_proposal_indices=indices)


def test_run_pass_command_rejects_missing_duplicate_or_empty_keys():
    with pytest.raises(ValueError, match="non-empty"):
        RunPassCommand(pass_index=0, image_keys=())
    with pytest.raises(ValueError, match="unique"):
        RunPassCommand(pass_index=0, image_keys=("a", "a"))


def test_prepare_command_preserves_a_spawn_safe_specification():
    command = PrepareCommand(spec=_worker_spec())

    assert command.spec.role == "reference"


def test_metadata_values_are_deeply_frozen_and_reject_pickleable_models():
    mutable_value = ["fixed"]
    spec = replace(_worker_spec(), runtime_overrides=(("labels", mutable_value),))
    metadata = replace(_worker_metadata(), detector_metadata=(("labels", mutable_value),))

    mutable_value.append("mutated")

    assert spec.runtime_overrides == (("labels", ("fixed",)),)
    assert metadata.detector_metadata == (("labels", ("fixed",)),)
    with pytest.raises(ValueError, match="protocol values"):
        replace(spec, runtime_overrides=(("model", _PickleableModel()),))
    with pytest.raises(ValueError, match="protocol values"):
        replace(metadata, detector_metadata=(("model", _PickleableModel()),))


@pytest.mark.parametrize(
    "factory, changes",
    [
        (_worker_spec, {"runtime_overrides": (("threads", 1), ("threads", 2))}),
        (_worker_spec, {"expected_artifact_hashes": (("policy", "a"), ("policy", "b"))}),
        (_worker_metadata, {"detector_metadata": (("version", "a"), ("version", "b"))}),
        (_worker_metadata, {"artifact_hashes": (("policy", "a"), ("policy", "b"))}),
    ],
)
def test_metadata_pairs_reject_duplicate_keys(factory, changes):
    with pytest.raises(ValueError, match="unique"):
        replace(factory(), **changes)


def test_warmup_evidence_requires_exactly_two_repetitions():
    with pytest.raises(ValueError, match="exactly 2"):
        WarmupEvidence(repetitions=1, images=(_warmup_image(),))
    with pytest.raises(ValueError, match="exactly 2"):
        WarmupEvidence(repetitions=2.0, images=(_warmup_image(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exactly 2"):
        WarmupEvidence(repetitions=True, images=(_warmup_image(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="1 and 2"):
        _warmup_image(repetition=3)


def test_compile_mode_keeps_empty_compile_models_compatible_with_runtime_config():
    runtime = replace(_resolved_runtime(), mode="batch_pytorch_compile", compile_models=())

    assert runtime.compile_models == ()
