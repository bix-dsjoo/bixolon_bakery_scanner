from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.pipelines.rtx5080_15plus5.config import (
    CandidateConfig,
    CandidateRuntimeConfig,
    load_candidate_config,
)


CONFIG = Path("configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml")


def test_config_requires_static_chunk_capacities_and_hard_p95() -> None:
    candidate_config = load_candidate_config(CONFIG)

    assert candidate_config.pipeline_id == "rtx5080_15plus5_single_frame_v1"
    assert candidate_config.runtime.device == "CUDA:0"
    assert candidate_config.runtime.repvit_chunk_capacity_objects == 7
    assert candidate_config.runtime.dinov3_chunk_capacity_objects == 7
    assert candidate_config.runtime.p95_limit_ms == 100.0
    assert candidate_config.runtime.precision == "FP16"
    assert candidate_config.runtime.stage_budgets_ms == {
        "decode_canonical": 10.0, "detector": 36.0, "completeness": 6.0,
        "crop": 4.0, "repvit": 12.0, "direct_gate": 2.0, "dinov3": 18.0,
        "fusion_payload": 6.0, "headroom": 8.0,
    }
    assert candidate_config.repvit_batch_size == 14
    assert candidate_config.dinov3_batch_size == 7
    assert candidate_config.fusion_margin == 0.85


def test_evaluation_config_fixes_oof_and_all_latency_paths() -> None:
    candidate_config = load_candidate_config(CONFIG)

    evaluation = candidate_config.evaluation
    assert evaluation.iou_threshold == 0.50
    assert evaluation.seed == 20260803
    assert evaluation.fold_count == 5
    assert evaluation.role_counts == {"train": 3, "calibration": 1, "evaluation": 1}
    assert evaluation.utility_floors["normal_scan_acceptance"] == {"overall": 0.80, "each": 0.70}
    assert evaluation.latency_paths == ("E", "M", "H", "overall", "dinov3", "needs_retake", "unknown", "count_1_2", "count_3_7", "count_8_plus")


def test_direct_constructors_cannot_bypass_static_candidate_values() -> None:
    valid = load_candidate_config(CONFIG)
    with pytest.raises(ValueError, match="CUDA:0 FP16"):
        CandidateRuntimeConfig("CPU", "FP16", 7, 7, 100.0, valid.runtime.stage_budgets_ms)
    with pytest.raises(ValueError, match="stage_budgets_ms"):
        CandidateRuntimeConfig("CUDA:0", "FP16", 7, 7, 100.0, {**valid.runtime.stage_budgets_ms, "detector": 35.0})
    with pytest.raises(ValueError, match="stage_budgets_ms keys must be strings"):
        CandidateRuntimeConfig("CUDA:0", "FP16", 7, 7, 100.0, {**valid.runtime.stage_budgets_ms, 42: 0.0})
    with pytest.raises(ValueError, match="pipeline_id"):
        CandidateConfig(
            "arbitrary_pipeline", valid.admission_manifest, valid.evaluation_config, valid.runtime,
            14, 7, .85, valid.evaluation,
        )
    with pytest.raises(ValueError, match="batch sizes"):
        replace(valid, repvit_batch_size=13)
    with pytest.raises(ValueError, match="fusion_margin"):
        replace(valid, fusion_margin=.84)
