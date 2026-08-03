"""Contract tests for RF-DETR calibration and frozen evaluation."""

from __future__ import annotations

from tools.evaluate.evaluate_rfdetr_bread_oof import evaluate_detector, select_detector_policy


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
