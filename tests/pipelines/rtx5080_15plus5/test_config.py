from __future__ import annotations

from pathlib import Path

from bakery_scanner.pipelines.rtx5080_15plus5.config import load_candidate_config


CONFIG = Path("configs/pipelines/rtx5080_15plus5_single_frame_v1.yaml")


def test_config_requires_static_limits_and_hard_p95() -> None:
    candidate_config = load_candidate_config(CONFIG)

    assert candidate_config.pipeline_id == "rtx5080_15plus5_single_frame_v1"
    assert candidate_config.runtime.device == "CUDA:0"
    assert candidate_config.runtime.min_objects == 3
    assert candidate_config.runtime.max_objects == 7
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
    assert evaluation.latency_paths == ("E", "M", "H", "overall", "dinov3", "needs_retake", "unknown")
