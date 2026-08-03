from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from bakery_scanner.data.sku_scene import load_inventory


DATASET_ROOT = Path(r"C:\workspace\bixolon_bakery_scanner\datasets")
BASE_SKUS = {1, 2, 3, 5, 7, 8, 10, 11, 12, 13, 14, 17, 18, 19, 20}


@pytest.fixture(scope="module")
def dataset_fixture() -> Path:
    if not DATASET_ROOT.is_dir():
        pytest.skip(f"external dataset is unavailable: {DATASET_ROOT}")
    return DATASET_ROOT


def build_dataset_fixture(root: Path, *, bbox: list[float]) -> Path:
    """Create the smallest malformed COCO source needed to reach box validation."""
    for source_name in ("group_15class", "group_20class_batch01", "group_20class_batch02"):
        images = root / "detection" / source_name / "images"
        annotations = root / "detection" / source_name / "annotations"
        images.mkdir(parents=True, exist_ok=True)
        annotations.mkdir(parents=True, exist_ok=True)
        if source_name == "group_15class":
            file_name = "g15_e_0001.jpg"
        elif source_name == "group_20class_batch01":
            file_name = "g20_b01_e_0001.jpg"
        else:
            file_name = "g20_b02_e_0001.jpg"
        Image.new("RGB", (100, 100), color="white").save(images / file_name)
        category_ids = BASE_SKUS if source_name == "group_15class" else set(range(1, 21))
        (annotations / "instances.json").write_text(
            json.dumps(
                {
                    "images": [{"id": 1, "file_name": file_name, "width": 100, "height": 100}],
                    "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": bbox}],
                    "categories": [
                        {"id": sku_id, "name": {
                            1: "Walnut Donut", 2: "Croffle", 3: "Waffle", 4: "Scon", 5: "Half-moon Croissant",
                            6: "Croissant", 7: "Flower Bread", 8: "Almond Scon", 9: "Dinner Roll", 10: "Sugar Donut",
                            11: "Bagel", 12: "Egg Tart", 13: "Muffin", 14: "Burger", 15: "Sandwich",
                            16: "Grain Campagne", 17: "Almond Campagne", 18: "Mini Bread", 19: "Pastry Bread", 20: "Plain Bread",
                        }[sku_id]}
                        for sku_id in sorted(category_ids)
                    ],
                }
            ),
            encoding="utf-8",
        )
    return root


def test_inventory_preserves_twenty_sku_labels(dataset_fixture: Path) -> None:
    inventory = load_inventory(dataset_fixture)

    assert inventory.scene_count == 299
    assert inventory.box_count == 1406
    assert inventory.difficulty_counts == {"E": 100, "M": 99, "H": 100}
    assert inventory.isolated_counts[4] == 5
    assert inventory.isolated_counts[1] == 84
    assert {box.sku_id for scene in inventory.scenes for box in scene.boxes} == set(range(1, 21))


def test_inventory_rejects_coco_box_outside_declared_image(tmp_path: Path) -> None:
    root = build_dataset_fixture(tmp_path, bbox=[10, 10, 9999, 10])

    with pytest.raises(ValueError, match="canonical image bounds"):
        load_inventory(root)
