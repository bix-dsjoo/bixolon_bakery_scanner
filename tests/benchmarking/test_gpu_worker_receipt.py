from __future__ import annotations

import pytest

from bakery_scanner.benchmarking.gpu_worker_receipt import (
    GROUPS,
    STAGES,
    GpuWorkerReceipt,
    build_receipt,
    summarize_ms,
)


_HASH_FIELDS = (
    "detector_checkpoint_sha256", "detector_calibration_sha256",
    "detector_manifest_sha256", "repvit_checkpoint_sha256",
    "repvit_manifest_sha256", "repvit_prototype_sha256",
    "dinov3_weights_sha256", "dinov3_support_sha256",
    "dinov3_local_bank_sha256", "classifier_calibration_sha256",
    "preprocess_sha256", "fusion_policy_sha256", "presentation_policy_sha256",
)


def _provenance() -> dict[str, str]:
    return {field: f"{index:064x}" for index, field in enumerate(_HASH_FIELDS, 1)}


def _ready(*, fallback_reason: str | None = None) -> dict[str, object]:
    return {
        "type": "ready",
        "device": "cuda:0",
        "startup_metrics": {
            "device": "cuda:0",
            "fallback_reason": fallback_reason,
            "detector_id": "rfdetr_large_bakery_v1",
            "repvit_id": "repvit_m1_15plus5_v1",
            "dinov3_id": "dinov3_vits16_15plus5_v1",
            "fusion_policy_id": "fusion_local_or_global_consensus_margin_v1",
            "detector_threshold": 0.5,
            "applied_artifact_hashes": _provenance(),
        },
    }


def _samples(group: str, count: int) -> list[dict[str, object]]:
    return [
        {
            "request_id": f"{group}-{index:03d}",
            "image_id": f"{group}-image-{index:03d}",
            "group": group,
            "image_sha256": f"{index:064x}",
            "object_count": 3,
            "dino_object_count": 1,
            "timings_ms": {stage: float(index + 1) for stage in STAGES},
        }
        for index in range(count)
    ]


def test_nearest_rank_summary_includes_p90_p95_p99():
    assert summarize_ms(range(1, 101)) == {
        "count": 100,
        "p50": 50.0,
        "p90": 90.0,
        "p95": 95.0,
        "p99": 99.0,
        "max": 100.0,
    }


def test_receipt_requires_one_hundred_observations_per_group():
    with pytest.raises(ValueError, match="100 observations"):
        build_receipt(
            _ready(),
            {"E": _samples("E", 99), "M": _samples("M", 100), "H": _samples("H", 100)},
            artifacts=_benchmark_provenance(),
        )


def test_receipt_summarizes_each_stage_groups_and_overall():
    receipt = build_receipt(
        _ready(),
        {group: _samples(group, 100) for group in GROUPS},
        artifacts={
            "benchmark_manifest_sha256": "a" * 64,
            "benchmark_protocol_sha256": "b" * 64,
            "code_commit": "c" * 40,
            "code_identity_sha256": "d" * 64,
        },
    )

    assert receipt.schema_version == 2
    assert receipt.summaries["groups"]["E"]["object_count"]["max"] == 3.0
    assert receipt.summaries["groups"]["H"]["dino_execution_rate"] == 1 / 3
    assert receipt.summaries["overall"]["timings_ms"]["total"]["p99"] == 99.0


@pytest.mark.parametrize("mutate", ["device", "fallback", "sha", "stage", "diagnostic"])
def test_receipt_rejects_invalid_cuda_provenance_or_sample(mutate: str):
    ready = _ready()
    grouped = {group: _samples(group, 100) for group in GROUPS}
    if mutate == "device":
        ready["device"] = "cpu"
    elif mutate == "fallback":
        ready["startup_metrics"]["fallback_reason"] = "cuda_load_failed"  # type: ignore[index]
    elif mutate == "sha":
        grouped["E"][0]["image_sha256"] = "A" * 64
    elif mutate == "stage":
        grouped["E"][0]["timings_ms"].pop("crop")  # type: ignore[index]
    else:
        grouped["E"][0]["dino_object_count"] = 4

    with pytest.raises(ValueError):
        build_receipt(ready, grouped, artifacts=_benchmark_provenance())


def test_receipt_rejects_total_shorter_than_any_stage():
    grouped = {group: _samples(group, 100) for group in GROUPS}
    grouped["E"][0]["timings_ms"].update({"detector": 200.0, "total": 1.0})

    with pytest.raises(ValueError, match="total"):
        build_receipt(_ready(), grouped, artifacts=_benchmark_provenance())


def _benchmark_provenance() -> dict[str, str]:
    return {
        "benchmark_manifest_sha256": "a" * 64,
        "benchmark_protocol_sha256": "b" * 64,
        "code_commit": "c" * 40,
        "code_identity_sha256": "d" * 64,
    }


def test_receipt_deep_freezes_inputs_and_returns_detached_payload():
    ready = _ready()
    grouped = {group: _samples(group, 100) for group in GROUPS}
    receipt = build_receipt(ready, grouped, artifacts=_benchmark_provenance())
    ready["startup_metrics"]["applied_artifact_hashes"]["detector_checkpoint_sha256"] = "f" * 64  # type: ignore[index]
    grouped["E"][0]["timings_ms"]["detector"] = 999.0  # type: ignore[index]

    assert receipt.runtime["startup_metrics"]["applied_artifact_hashes"]["detector_checkpoint_sha256"] == "0" * 63 + "1"  # type: ignore[index]
    assert receipt.samples[0].timings_ms["detector"] == 1.0
    with pytest.raises(TypeError):
        receipt.samples[0].timings_ms["detector"] = 3.0  # type: ignore[index]
    payload = receipt.to_payload()
    payload["runtime"]["startup_metrics"]["applied_artifact_hashes"]["detector_checkpoint_sha256"] = "f" * 64  # type: ignore[index]
    assert receipt.runtime["startup_metrics"]["applied_artifact_hashes"]["detector_checkpoint_sha256"] != "f" * 64  # type: ignore[index]


def test_receipt_rejects_forged_summary_and_unbound_provenance():
    receipt = build_receipt(
        _ready(), {group: _samples(group, 100) for group in GROUPS}, artifacts=_benchmark_provenance()
    )
    with pytest.raises(ValueError, match="summaries"):
        GpuWorkerReceipt(2, receipt.runtime, receipt.artifacts, receipt.samples, {})
    ready = _ready()
    ready["startup_metrics"]["applied_artifact_hashes"].pop("fusion_policy_sha256")  # type: ignore[index]
    with pytest.raises(ValueError, match="provenance"):
        build_receipt(ready, {group: _samples(group, 100) for group in GROUPS}, artifacts=_benchmark_provenance())


def test_receipt_binds_ready_applied_hashes_and_rejects_forged_or_uppercase_values():
    ready = _ready()
    receipt = build_receipt(
        ready, {group: _samples(group, 100) for group in GROUPS}, artifacts=_benchmark_provenance()
    )
    assert receipt.artifacts["detector_checkpoint_sha256"] == ready["startup_metrics"]["applied_artifact_hashes"]["detector_checkpoint_sha256"]  # type: ignore[index]
    uppercase = _ready()
    uppercase["startup_metrics"]["applied_artifact_hashes"]["repvit_checkpoint_sha256"] = "A" * 64  # type: ignore[index]
    with pytest.raises(ValueError, match="SHA-256"):
        build_receipt(uppercase, {group: _samples(group, 100) for group in GROUPS}, artifacts=_benchmark_provenance())
    forged = _benchmark_provenance() | {"detector_checkpoint_sha256": "f" * 64}
    with pytest.raises(ValueError, match="evidence provenance"):
        build_receipt(_ready(), {group: _samples(group, 100) for group in GROUPS}, artifacts=forged)
