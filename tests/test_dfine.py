import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.detectors.dfine import DFineRunner, parse_dfine_output


def test_dfine_xyxy_is_normalized_to_source_xywh():
    rows = parse_dfine_output(
        image_id=7,
        image_size=(100, 80),
        labels=[0],
        boxes=[[10, 20, 40, 60]],
        scores=[.2],
        source="dfine_n_768",
    )
    assert rows[0].box == Box(10, 20, 30, 40)
    assert rows[0].class_name == "bread"


def test_dfine_parser_rejects_unknown_classes_and_caps_canonical_candidates():
    with pytest.raises(ValueError, match="class"):
        parse_dfine_output(1, (100, 80), [1], [[0, 0, 10, 10]], [.5], "dfine_n_768")
    rows = parse_dfine_output(
        1, (100, 80), [0] * 31,
        [[index, 0, index + 1, 1] for index in range(31)],
        [0.5] * 31, "dfine_n_768",
    )
    assert len(rows) == 30
    assert rows[0].box == Box(0, 0, 1, 1)


def test_runner_uses_injected_command_runner(tmp_path):
    calls = []
    runner = DFineRunner(command_runner=lambda command: calls.append(command) or {"labels": [], "boxes": [], "scores": []})
    assert runner.predict("model.pt", "image.png", image_id=1, image_size=(10, 10), source="dfine_n_640") == ()
    assert calls[0][0] == "dfine-predict"


def test_dfine_overlay_exposes_injectable_640_and_768_input_size_contract():
    overlay = __import__("pathlib").Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    assert "__INJECTED_INPUT_SIZE__" in overlay
    assert "base_size" in overlay


def test_matrix_script_generates_every_variant_seed_fold_config_and_receipt():
    script = __import__("pathlib").Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    assert "foreach ($Variant in $Variants)" in script
    assert "foreach ($Seed in $Seeds)" in script
    assert "foreach ($Fold in 0..4)" in script
    assert "receipt.json" in script and "validation_predictions.json" in script
    assert "fold-$Fold/manifest.json" in script
    assert "--test-only" in script
    assert "__INJECTED_MMD_BASE__" in script
    assert "canonicalize_validation_predictions.py" in script
    assert "collect_oof_evidence.py" in script
    assert "DFINE_OOF_PREDICTIONS" in script
    overlay = __import__("pathlib").Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    assert "img_folder" in overlay and "ann_file" in overlay
    assert "dataset:" in overlay and "base_size:" in overlay
    assert "remap_mscoco_category: true" in overlay
    assert "processed-output" in __import__("pathlib").Path("scripts/canonicalize_validation_predictions.py").read_text(encoding="utf-8")
    assert overlay.count("type: Resize") == 2
