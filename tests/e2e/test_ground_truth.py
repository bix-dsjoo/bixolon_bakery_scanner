from pathlib import Path
import json

import pytest

from bakery_scanner.config import ScannerConfig
from bakery_scanner.e2e.ground_truth import load_source_sku_ground_truth


def test_source_sku_loader_rejects_staging_and_sku_annotation_count_mismatch():
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="source SKU annotations contain 1409 boxes but staging expects 1410"):
        load_source_sku_ground_truth(
            ScannerConfig.load(root / "configs" / "box_system.yaml"),
            classes_path=root / "datasets" / "classes.json",
        )


def test_source_sku_loader_uses_staged_canonical_coordinates():
    root = Path(__file__).resolve().parents[2]
    config = ScannerConfig.load(root / "configs" / "e2e_current_source.yaml")

    labels = load_source_sku_ground_truth(config, classes_path=root / "datasets" / "classes.json")

    annotations = json.loads((config.artifact_root / "staged" / "annotations.json").read_text(encoding="utf-8"))
    expected = {
        tuple(annotation["bbox"])
        for annotation in annotations["annotations"]
        if annotation["image_id"] == 1
    }
    actual = {
        (label.box.x, label.box.y, label.box.width, label.box.height)
        for label in labels[1]
    }
    assert actual == expected
