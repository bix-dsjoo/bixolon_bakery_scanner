import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.detectors.rtmdet import RTMDetRunner, parse_rtmdet_output


def test_rtmdet_xyxy_is_normalized_to_source_xywh():
    rows = parse_rtmdet_output(3, (100, 80), [0], [[10, 20, 40, 60]], [.3], "rtmdet_tiny_768")
    assert rows[0].box == Box(10, 20, 30, 40)


def test_rtmdet_drops_scores_below_retention_floor_and_rejects_invalid_box():
    assert parse_rtmdet_output(3, (100, 80), [0], [[0, 0, 10, 10]], [.0009], "rtmdet_tiny_768") == ()
    with pytest.raises(ValueError, match="coordinates"):
        parse_rtmdet_output(3, (100, 80), [0], [[0, 0, 101, 10]], [.2], "rtmdet_tiny_768")


def test_runner_uses_injected_command_runner():
    calls = []
    runner = RTMDetRunner(command_runner=lambda command: calls.append(command) or {"labels": [], "boxes": [], "scores": []}, gpu_probe=lambda: (True, "NVIDIA RTX 5080"))
    assert runner.predict("model.pth", "image.png", image_id=1, image_size=(10, 10), source="rtmdet_tiny_640") == ()
    assert calls[0][0] == "rtmdet-predict"


def test_rtmdet_overlay_replaces_train_test_and_tta_resize_scales():
    overlay = __import__("pathlib").Path("configs/upstream/rtmdet_tiny_bread.py").read_text(encoding="utf-8")
    assert "train_pipeline" in overlay
    assert "test_pipeline" in overlay
    assert "tta_pipeline" in overlay
    assert overlay.count("input_size") >= 4
    assert "data_prefix=dict(img=\"images/\")" in overlay
    assert overlay.count("PackDetInputs") >= 2
    assert "val_evaluator" in overlay and "test_evaluator" in overlay
    assert "save_best=\"coco/bbox_mAP\"" in overlay and "rule=\"greater\"" in overlay
