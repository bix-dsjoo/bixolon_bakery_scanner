import json
from pathlib import Path

from scripts.build_classifier_evidence_manifest import main


def test_evidence_manifest_source_id_keeps_sample_ids_unique_across_coco_sources(tmp_path: Path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    (image_root / "one.jpg").write_bytes(b"image")
    coco = tmp_path / "instances.json"
    coco.write_text(json.dumps({
        "images": [{"id": 1, "file_name": "one.jpg"}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 3, "bbox": [1, 2, 3, 4]}],
    }), encoding="utf-8")
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"

    main(["--coco", str(coco), "--images", str(image_root), "--role", "development", "--source-id", "batch_a", "--output", str(first)])
    main(["--coco", str(coco), "--images", str(image_root), "--role", "development", "--source-id", "batch_b", "--output", str(second)])

    assert json.loads(first.read_text(encoding="utf-8"))["sample_id"] != json.loads(second.read_text(encoding="utf-8"))["sample_id"]
