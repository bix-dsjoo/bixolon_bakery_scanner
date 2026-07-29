from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PrepareCommand,
    ResolvedRuntime,
    RunPassCommand,
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
        ({"registered_count": 2, "unknown_count": 2}, "decision counts"),
    ],
)
def test_image_row_rejects_invalid_measurement(changes, message):
    with pytest.raises(ValueError, match=message):
        replace(_image_row(), **changes)


def test_run_pass_command_rejects_missing_duplicate_or_empty_keys():
    with pytest.raises(ValueError, match="non-empty"):
        RunPassCommand(pass_index=0, image_keys=())
    with pytest.raises(ValueError, match="unique"):
        RunPassCommand(pass_index=0, image_keys=("a", "a"))


def test_prepare_command_preserves_a_spawn_safe_specification():
    command = PrepareCommand(spec=_worker_spec())

    assert command.spec.role == "reference"
