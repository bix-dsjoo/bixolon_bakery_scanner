from __future__ import annotations

import pytest

from scripts.benchmark_camera_worker import (
    build_benchmark_report,
    summarize_ms,
    validate_run_count,
)


def _result(run: int, total_ms: float) -> dict[str, object]:
    return {
        "type": "result",
        "request_id": f"benchmark-{run:02d}",
        "device": "cpu",
        "timings_ms": {
            "decode_preprocess": 1.0,
            "detector": total_ms - 5.0,
            "repvit": 2.0,
            "dinov3": 0.0,
            "postprocess": 2.0,
            "total": total_ms,
        },
    }


def test_summarize_twenty_warm_runs_uses_nearest_rank_p95():
    values = tuple(float(value) for value in range(1, 21))

    summary = summarize_ms(values)

    assert summary == {"count": 20, "p50": 10.0, "p95": 19.0, "max": 20.0}


def test_validate_run_count_rejects_fewer_than_twenty_measured_runs():
    with pytest.raises(ValueError, match="at least 20"):
        validate_run_count(19)


def test_report_keeps_startup_and_warmup_out_of_measured_timings():
    ready = {
        "type": "ready",
        "device": "cpu",
        "startup_metrics": {
            "device": "cpu",
            "load_ms": 1000.0,
            "warmup_ms": 500.0,
            "fallback_reason": "cuda_unavailable",
            "detector_id": "rfdetr_large_bakery_v1",
            "repvit_id": "repvit_m1_15plus5_v1",
            "dinov3_id": "dinov3_vits16_15plus5_v1",
            "fusion_policy_id": "fusion_local_or_global_consensus_margin_v1",
            "detector_threshold": 0.5691395401954651,
        },
    }
    results = tuple(_result(run, float(run)) for run in range(20, 40))

    report = build_benchmark_report(ready, results)

    assert report["run_count"] == 20
    assert report["startup"] == {
        "load_ms": 1000.0,
        "warmup_ms": 500.0,
        "fallback_reason": "cuda_unavailable",
    }
    assert report["timings_ms"]["total"] == {
        "count": 20,
        "p50": 29.0,
        "p95": 38.0,
        "max": 39.0,
    }
    assert report["timings_ms"]["total"]["max"] != ready["startup_metrics"]["load_ms"]


def test_report_rejects_a_second_startup_event_in_measured_results():
    ready = {
        "type": "ready",
        "device": "cpu",
        "startup_metrics": {
            "device": "cpu",
            "load_ms": 1.0,
            "warmup_ms": 1.0,
            "fallback_reason": None,
            "detector_id": "rfdetr_large_bakery_v1",
            "repvit_id": "repvit_m1_15plus5_v1",
            "dinov3_id": "dinov3_vits16_15plus5_v1",
            "fusion_policy_id": "fusion_local_or_global_consensus_margin_v1",
            "detector_threshold": 0.5691395401954651,
        },
    }
    events = tuple(_result(run, float(run + 10)) for run in range(20))
    events = events[:5] + ({"type": "warming"},) + events[5:]

    with pytest.raises(ValueError, match="startup event"):
        build_benchmark_report(ready, events)
