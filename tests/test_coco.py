import json
from pathlib import Path

from bakery_scanner.config import ScannerConfig
from bakery_scanner.data.coco import load_sources, stage_single_class_dataset


def test_real_sources_merge_to_one_bread_class(tmp_path: Path):
    config = ScannerConfig.load(Path("configs/box_system.yaml"))

    staged = stage_single_class_dataset(
        load_sources(config),
        (config.canonical_frame.width, config.canonical_frame.height),
        tmp_path,
        expected_images=config.dataset.expected_images,
        expected_boxes=config.dataset.expected_boxes,
    )

    assert staged.image_count == 299
    assert staged.box_count == 1410
    payload = json.loads(staged.annotations.read_text(encoding="utf-8"))
    assert payload["categories"] == [
        {"id": 1, "name": "bread", "supercategory": "object"}
    ]
    assert {image["width"] for image in payload["images"]} == {1152}
    assert {image["height"] for image in payload["images"]} == {1536}
