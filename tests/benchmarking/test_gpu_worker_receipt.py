from __future__ import annotations

import pytest

from bakery_scanner.benchmarking.gpu_worker_receipt import (
    GROUPS,
    STAGES,
    build_receipt,
    summarize_ms,
)


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
        )


def test_receipt_summarizes_each_stage_groups_and_overall():
    receipt = build_receipt(
        _ready(),
        {group: _samples(group, 100) for group in GROUPS},
        artifacts={"manifest_sha256": "a" * 64},
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
        build_receipt(ready, grouped)
