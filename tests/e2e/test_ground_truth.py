from pathlib import Path
import json

import pytest

from bakery_scanner.config import ScannerConfig
from bakery_scanner.e2e.ground_truth import load_source_sku_ground_truth


def test_source_sku_loader_accepts_current_annotation_count():
    root = Path(__file__).resolve().parents[2]
    labels = load_source_sku_ground_truth(
        ScannerConfig.load(root / "configs" / "box_system.yaml"),
        classes_path=root / "datasets" / "classes.json",
    )

    assert sum(len(rows) for rows in labels.values()) == 1406


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


def test_current_e2e_annotation_contract_tracks_removed_merged_box():
    root = Path(__file__).resolve().parents[2]
    config = ScannerConfig.load(root / "configs" / "e2e_current_source.yaml")

    assert config.dataset.expected_boxes == 1406


def test_g20_b01_m_0619_sandwich_box_keeps_its_lower_edge_and_expands_upward():
    root = Path(__file__).resolve().parents[2]
    annotations_path = root / "datasets" / "detection" / "group_20class_batch01" / "annotations" / "instances.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))

    sandwich = next(annotation for annotation in annotations["annotations"] if annotation["id"] == 154)

    assert sandwich["image_id"] == 95
    assert sandwich["category_id"] == 15
    assert sandwich["bbox"] == [2230.0, 2450.0, 1320.0, 1800.0]
    assert sandwich["area"] == 2376000.0
