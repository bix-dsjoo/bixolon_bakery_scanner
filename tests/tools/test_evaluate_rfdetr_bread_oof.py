"""Contract tests for RF-DETR calibration and frozen evaluation."""

from __future__ import annotations

import hashlib
import json

import pytest

from tools.evaluate.evaluate_rfdetr_bread_oof import evaluate_bound_detector, evaluate_detector, select_detector_policy


CAL_ROWS = (
    {
        "image_id": 10,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.90, "box": [0, 0, 10, 10]}],
    },
    {
        "image_id": 11,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.75, "box": [0, 0, 10, 10]}],
    },
)
EVAL_ROWS = (
    {
        "image_id": 20,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.10, "box": [0, 0, 10, 10]}],
    },
)


def test_threshold_selection_uses_calibration_only():
    """Using evaluation scores to choose a threshold would leak held-out scenes."""
    receipt = select_detector_policy(CAL_ROWS, EVAL_ROWS)

    assert receipt.selected_from_image_ids == (10, 11)
    assert not set(receipt.selected_from_image_ids) & {20}
    assert receipt.score_threshold == 0.75


def test_detector_receipt_reports_every_primary_error():
    """Dropping any taxonomy branch would hide a detector error from the receipt."""
    ground_truth = [
        {"image_id": 1, "box": [0, 0, 10, 10]},
        {"image_id": 1, "box": [5, 0, 10, 10]},
        {"image_id": 2, "box": [0, 0, 10, 10]},
    ]
    predictions = [
        {"image_id": 1, "score": 0.9, "box": [0, 0, 10, 10]},
        {"image_id": 1, "score": 0.8, "box": [0, 0, 10, 10]},
        {"image_id": 1, "score": 0.7, "box": [0, 0, 15, 10]},
        {"image_id": 1, "score": 0.6, "box": [50, 0, 10, 10]},
    ]

    metrics = evaluate_detector(ground_truth, predictions, iou_threshold=0.50)

    assert set(metrics.error_counts) == {"miss", "duplicate", "non_target", "split", "merge"}
    assert metrics.error_counts == {"miss": 1, "duplicate": 1, "non_target": 1, "split": 1, "merge": 1}


def _bound_manifest() -> dict[str, object]:
    payload = {
        "schema_version": 1, "fold_index": 2, "seed": 20260803, "source_sha256": "b" * 64,
        "scene_ids": {"train": ["source:train.jpg"], "calibration": ["source:cal.jpg"], "evaluation": ["source:eval.jpg"]},
        "group_ids": {"train": ["source:1"], "calibration": ["source:2"], "evaluation": ["source:3"]},
        "sku_counts": {role: {str(index): 0 for index in range(1, 21)} for role in ("train", "calibration", "evaluation")},
        "difficulty_counts": {role: {difficulty: 0 for difficulty in ("E", "M", "H")} for role in ("train", "calibration", "evaluation")},
    }
    payload["manifest_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def _provenance(manifest: dict[str, object]) -> dict[str, str]:
    return {
        "fold_manifest_sha256": str(manifest["manifest_sha256"]), "source_sha256": "b" * 64,
        "staged_annotations_sha256": "c" * 64, "staged_manifest_sha256": "d" * 64,
        "detector_checkpoint_sha256": "e" * 64, "calibration_predictions_sha256": "f" * 64,
        "evaluation_predictions_sha256": "0" * 64, "config_sha256": "1" * 64,
        "code_sha256": "2" * 64, "runtime_identity_sha256": "3" * 64,
    }


def test_bound_evaluation_requires_exact_split_roles_and_receipt_provenance():
    """Missing, extra, or cross-role rows must not yield a detector receipt."""
    manifest = _bound_manifest()
    calibration = [{"image_id": 10, "scene_id": "source:cal.jpg", "ground_truth": [{"box": [0, 0, 10, 10]}], "predictions": [{"score": 0.8, "box": [0, 0, 10, 10]}]}]
    evaluation = [{"image_id": 20, "scene_id": "source:eval.jpg", "ground_truth": [{"box": [0, 0, 10, 10]}], "predictions": [{"score": 0.7, "box": [0, 0, 10, 10]}]}]

    receipt = evaluate_bound_detector(calibration, evaluation, split_manifest=manifest, provenance=_provenance(manifest))

    assert receipt["provenance"] == _provenance(manifest)
    assert receipt["role_scene_ids"] == {"calibration": ["source:cal.jpg"], "evaluation": ["source:eval.jpg"]}
    with pytest.raises(ValueError, match="exactly match"):
        evaluate_bound_detector(calibration, [{**evaluation[0], "scene_id": "source:cal.jpg"}], split_manifest=manifest, provenance=_provenance(manifest))
