from __future__ import annotations

import json
import os
from pathlib import Path
from itertools import cycle

import pytest
from PIL import Image

from bakery_scanner.data.sku_scene import SceneRecord, SkuBox, SkuSceneInventory, _assert_exact_counts, _load_isolated, load_inventory


BASE_SKUS = {1, 2, 3, 5, 7, 8, 10, 11, 12, 13, 14, 17, 18, 19, 20}
SKU_NAMES = {
    1: "Walnut Donut", 2: "Croffle", 3: "Waffle", 4: "Scon", 5: "Half-moon Croissant",
    6: "Croissant", 7: "Flower Bread", 8: "Almond Scon", 9: "Dinner Roll", 10: "Sugar Donut",
    11: "Bagel", 12: "Egg Tart", 13: "Muffin", 14: "Burger", 15: "Sandwich",
    16: "Grain Campagne", 17: "Almond Campagne", 18: "Mini Bread", 19: "Pastry Bread", 20: "Plain Bread",
}


@pytest.fixture(scope="module")
def dataset_fixture() -> Path:
    configured_root = os.environ.get("BAKERY_SCANNER_DATASET_ROOT")
    if configured_root is None:
        pytest.fail("set BAKERY_SCANNER_DATASET_ROOT to run external-data inventory tests")
    root = Path(configured_root)
    if not root.is_dir():
        pytest.fail(f"configured external dataset is unavailable: {root}")
    return root


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
                        {"id": sku_id, "name": SKU_NAMES[sku_id]}
                        for sku_id in sorted(category_ids)
                    ],
                }
            ),
            encoding="utf-8",
        )
    return root


@pytest.mark.artifact
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


def build_isolated_fixture(root: Path) -> Path:
    for collection, sku_ids, image_count in (("base", BASE_SKUS, 84), ("incremental", set(SKU_NAMES) - BASE_SKUS, 5)):
        for sku_id in sku_ids:
            directory = root / "classifier" / collection / f"Bread{sku_id:02d}_{SKU_NAMES[sku_id]}"
            directory.mkdir(parents=True)
            for image_index in range(image_count):
                (directory / f"image-{image_index:03d}.jpg").write_bytes(b"fixture")
    return root


def test_isolated_inventory_rejects_relabeled_sku_directory(tmp_path: Path) -> None:
    root = build_isolated_fixture(tmp_path)
    expected = root / "classifier" / "base" / "Bread01_Walnut Donut"
    expected.rename(expected.with_name("Bread01_Waffle"))

    with pytest.raises(ValueError, match="exact isolated class map"):
        _load_isolated(root)


def test_isolated_inventory_rejects_incorrect_sku_image_count(tmp_path: Path) -> None:
    root = build_isolated_fixture(tmp_path)
    (root / "classifier" / "incremental" / "Bread04_Scon" / "image-000.jpg").unlink()

    with pytest.raises(ValueError, match="exact isolated image count mismatch: SKU 4"):
        _load_isolated(root)


def test_inventory_rejects_missing_sku_box_coverage() -> None:
    sku_ids = cycle(range(1, 20))
    boxes_remaining = 1406
    scenes = []
    for scene_index in range(299):
        box_count = 5 if scene_index < 210 else 4
        boxes_remaining -= box_count
        difficulty = "E" if scene_index < 100 else "M" if scene_index < 199 else "H"
        scenes.append(SceneRecord(
            scene_id=f"scene-{scene_index:03d}", source_name="fixture", file_name=f"scene-{scene_index:03d}.jpg",
            difficulty=difficulty, capture_number=scene_index, width=100, height=100, image_sha256="0" * 64,
            boxes=tuple(SkuBox(next(sku_ids), (0.0, 0.0, 1.0, 1.0)) for _ in range(box_count)),
        ))
    assert boxes_remaining == 0
    inventory = SkuSceneInventory(tuple(scenes), {sku_id: () for sku_id in SKU_NAMES}, "0" * 64)

    with pytest.raises(ValueError, match="exact SKU box coverage mismatch"):
        _assert_exact_counts(inventory)
