"""Strict staging of the project's three COCO sources into one bread class."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

from bakery_scanner.config import ScannerConfig
from bakery_scanner.contracts import Box, SceneKey
from bakery_scanner.data.preprocess import normalize_capture


@dataclass(frozen=True, slots=True)
class CocoSource:
    name: str
    images: Path
    annotations: Path


@dataclass(frozen=True, slots=True)
class StagedImage:
    image_id: int
    file_name: str
    scene: SceneKey
    source_sha256: str
    box_count: int
    overlap_proxy: bool


@dataclass(frozen=True, slots=True)
class StagedDataset:
    root: Path
    annotations: Path
    images: tuple[StagedImage, ...]
    image_count: int
    box_count: int

    @property
    def scenes(self) -> tuple[SceneKey, ...]:
        return tuple(sorted({row.scene for row in self.images}))


def load_sources(config: ScannerConfig) -> tuple[CocoSource, ...]:
    return tuple(CocoSource(row.name, row.images, row.annotations) for row in config.dataset.sources)


def stage_single_class_dataset(
    sources: Iterable[CocoSource],
    target_size: tuple[int, int],
    output: Path,
    *,
    expected_images: int | None = None,
    expected_boxes: int | None = None,
) -> StagedDataset:
    """Validate, normalize, and merge sources; write only after a complete pass."""
    source_rows = tuple(sources)
    output = Path(output)
    parent = output.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=parent))
    try:
        images_dir = temporary / "images"
        images_dir.mkdir()
        coco_images: list[dict[str, object]] = []
        coco_annotations: list[dict[str, object]] = []
        staged_rows: list[StagedImage] = []
        next_image_id = 1
        next_annotation_id = 1
        for source in source_rows:
            payload = _read_coco(source.annotations)
            records = _validate_source(source, payload)
            annotations_by_image: dict[int, list[dict[str, object]]] = {}
            for annotation in payload["annotations"]:
                annotations_by_image.setdefault(int(annotation["image_id"]), []).append(annotation)
            for source_image in records:
                source_path = source.images / str(source_image["file_name"])
                source_hash = _file_sha256(source_path)
                with Image.open(source_path) as handle:
                    normalized = normalize_capture(handle, target_size)
                output_name = f"{source.name}__{Path(str(source_image['file_name'])).stem}.png"
                # Fast deterministic PNG compression keeps repeatable staging tests practical.
                normalized.image.save(images_dir / output_name, format="PNG", compress_level=1)
                boxes = [_box_from_annotation(annotation) for annotation in annotations_by_image[int(source_image["id"])]]
                transformed = [normalized.source_box_to_canonical(box) for box in boxes]
                scene = _scene_from_name(source.name, str(source_image["file_name"]))
                coco_images.append({"id": next_image_id, "file_name": output_name, "width": target_size[0], "height": target_size[1]})
                for transformed_box in transformed:
                    _assert_inside(transformed_box, target_size)
                    coco_annotations.append({
                        "id": next_annotation_id,
                        "image_id": next_image_id,
                        "category_id": 1,
                        "bbox": [transformed_box.x, transformed_box.y, transformed_box.width, transformed_box.height],
                        "area": transformed_box.width * transformed_box.height,
                        "iscrowd": 0,
                    })
                    next_annotation_id += 1
                staged_rows.append(StagedImage(next_image_id, output_name, scene, source_hash, len(transformed), _has_overlap(transformed)))
                next_image_id += 1
        if expected_images is not None and len(coco_images) != expected_images:
            raise ValueError(f"expected {expected_images} images, got {len(coco_images)}")
        if expected_boxes is not None and len(coco_annotations) != expected_boxes:
            raise ValueError(f"expected {expected_boxes} boxes, got {len(coco_annotations)}")
        annotation_path = temporary / "annotations.json"
        annotation_path.write_text(json.dumps({"images": coco_images, "annotations": coco_annotations, "categories": [{"id": 1, "name": "bread", "supercategory": "object"}]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        manifest = temporary / "staged_manifest.json"
        manifest.write_text(json.dumps([_staged_row_dict(row) for row in staged_rows], sort_keys=True, separators=(",", ":")), encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        os.replace(temporary, output)
        return StagedDataset(output, output / "annotations.json", tuple(staged_rows), len(coco_images), len(coco_annotations))
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _read_coco(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid COCO JSON: {path}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("images"), list) or not isinstance(value.get("annotations"), list):
        raise ValueError(f"COCO source must contain images and annotations arrays: {path}")
    return value


def _validate_source(source: CocoSource, payload: dict[str, object]) -> list[dict[str, object]]:
    images = payload["images"]
    assert isinstance(images, list)
    image_ids = set()
    records: list[dict[str, object]] = []
    for image in images:
        if not isinstance(image, dict) or not isinstance(image.get("id"), int) or not isinstance(image.get("file_name"), str):
            raise ValueError(f"invalid image record in {source.name}")
        if image["id"] in image_ids:
            raise ValueError(f"duplicate image id in {source.name}")
        image_ids.add(image["id"])
        if not (source.images / image["file_name"]).is_file():
            raise FileNotFoundError(source.images / image["file_name"])
        records.append(image)
    annotation_ids = set()
    annotations = payload["annotations"]
    assert isinstance(annotations, list)
    for annotation in annotations:
        if not isinstance(annotation, dict) or not isinstance(annotation.get("id"), int) or annotation.get("image_id") not in image_ids:
            raise ValueError(f"invalid annotation identity in {source.name}")
        if annotation["id"] in annotation_ids:
            raise ValueError(f"duplicate annotation id in {source.name}")
        annotation_ids.add(annotation["id"])
        _box_from_annotation(annotation)
    return sorted(records, key=lambda record: str(record["file_name"]))


def _box_from_annotation(annotation: dict[str, object]) -> Box:
    box = annotation.get("bbox")
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("COCO annotation bbox must contain four values")
    return Box(*box)


def _scene_from_name(source_name: str, file_name: str) -> SceneKey:
    stem = Path(file_name).stem
    parts = stem.split("_")
    if source_name == "group_15class" and len(parts) == 3 and parts[0] == "g15":
        return SceneKey("g15", int(parts[2]))
    if source_name in {"group_20class_batch01", "group_20class_batch02"} and len(parts) == 4 and parts[0] == "g20":
        return SceneKey(f"{parts[0]}_{parts[1]}", int(parts[3]))
    raise ValueError(f"unexpected source image naming scheme: {file_name}")


def _has_overlap(boxes: list[Box]) -> bool:
    for index, first in enumerate(boxes):
        for second in boxes[index + 1:]:
            left = max(first.x, second.x)
            top = max(first.y, second.y)
            right = min(first.x + first.width, second.x + second.width)
            bottom = min(first.y + first.height, second.y + second.height)
            if right > left and bottom > top:
                return True
    return False


def _assert_inside(box: Box, target_size: tuple[int, int]) -> None:
    if box.x < -0.01 or box.y < -0.01 or box.x + box.width > target_size[0] + 0.01 or box.y + box.height > target_size[1] + 0.01:
        raise ValueError("normalized box falls outside canonical frame")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _staged_row_dict(row: StagedImage) -> dict[str, object]:
    return {"box_count": row.box_count, "file_name": row.file_name, "image_id": row.image_id, "overlap_proxy": row.overlap_proxy, "scene": {"capture_batch": row.scene.capture_batch, "scene_number": row.scene.scene_number}, "source_sha256": row.source_sha256}
