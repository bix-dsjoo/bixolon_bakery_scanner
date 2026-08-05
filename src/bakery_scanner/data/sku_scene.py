"""Immutable 15+5 SKU source inventory for leak-safe training workflows."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from PIL import Image, ImageOps


Difficulty = Literal["E", "M", "H"]

_SOURCE_NAMES = ("group_15class", "group_20class_batch01", "group_20class_batch02")
_SKU_NAMES = {
    1: "Walnut Donut", 2: "Croffle", 3: "Waffle", 4: "Scon", 5: "Half-moon Croissant",
    6: "Croissant", 7: "Flower Bread", 8: "Almond Scon", 9: "Dinner Roll", 10: "Sugar Donut",
    11: "Bagel", 12: "Egg Tart", 13: "Muffin", 14: "Burger", 15: "Sandwich",
    16: "Grain Campagne", 17: "Almond Campagne", 18: "Mini Bread", 19: "Pastry Bread",
    20: "Plain Bread",
}
_BASE_SKUS = frozenset({1, 2, 3, 5, 7, 8, 10, 11, 12, 13, 14, 17, 18, 19, 20})
_INCREMENTAL_SKUS = frozenset({4, 6, 9, 15, 16})
_EXPECTED_COUNTS = {"group_15class": (90, 379), "group_20class_batch01": (103, 506), "group_20class_batch02": (106, 521)}
_SCENE_PATTERN = re.compile(r"^(?:g15|g20_b(?:01|02))_([emh])_(\d{4})\.jpg$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SkuBox:
    sku_id: int
    box_xywh: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class SourceImage:
    sku_id: int
    identity: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class SceneRecord:
    scene_id: str
    source_name: str
    file_name: str
    difficulty: Difficulty
    capture_number: int
    width: int
    height: int
    image_sha256: str
    boxes: tuple[SkuBox, ...]


@dataclass(frozen=True, slots=True)
class SkuSceneInventory:
    scenes: tuple[SceneRecord, ...]
    isolated_by_sku: Mapping[int, tuple[SourceImage, ...]]
    source_sha256: str

    @property
    def scene_count(self) -> int:
        return len(self.scenes)

    @property
    def box_count(self) -> int:
        return sum(len(scene.boxes) for scene in self.scenes)

    @property
    def difficulty_counts(self) -> Mapping[Difficulty, int]:
        return MappingProxyType({difficulty: sum(scene.difficulty == difficulty for scene in self.scenes) for difficulty in ("E", "M", "H")})

    @property
    def isolated_counts(self) -> Mapping[int, int]:
        return MappingProxyType({sku_id: len(images) for sku_id, images in self.isolated_by_sku.items()})


@dataclass(frozen=True, slots=True)
class OofFold:
    fold_index: int
    training_scene_ids: tuple[str, ...]
    calibration_scene_ids: tuple[str, ...]
    evaluation_scene_ids: tuple[str, ...]
    group_roles: Mapping[str, Literal["train", "calibration", "evaluation"]]
    manifest_sha256: str
    seed: int = 20260803


def load_inventory(root: Path) -> SkuSceneInventory:
    """Read and strictly validate the external 15+5 data without writing to it."""
    root = Path(root).resolve()
    sources = tuple(_load_source(root, source_name) for source_name in _SOURCE_NAMES)
    scenes = tuple(scene for source_scenes in sources for scene in source_scenes)
    if len({scene.scene_id for scene in scenes}) != len(scenes):
        raise ValueError("duplicate scene identity")
    isolated = _load_isolated(root)
    inventory = SkuSceneInventory(
        scenes=tuple(sorted(scenes, key=lambda scene: scene.scene_id)),
        isolated_by_sku=MappingProxyType(isolated),
        source_sha256="",
    )
    _assert_exact_counts(inventory)
    return SkuSceneInventory(inventory.scenes, inventory.isolated_by_sku, _inventory_sha256(inventory))


def _load_source(root: Path, source_name: str) -> tuple[SceneRecord, ...]:
    source_root = root / "detection" / source_name
    annotation_path = source_root / "annotations" / "instances.json"
    try:
        payload = json.loads(annotation_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid COCO JSON: {annotation_path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("images"), list) or not isinstance(payload.get("annotations"), list) or not isinstance(payload.get("categories"), list):
        raise ValueError(f"invalid COCO structure: {annotation_path}")
    expected_categories = {sku_id: _SKU_NAMES[sku_id] for sku_id in (_BASE_SKUS if source_name == "group_15class" else _SKU_NAMES)}
    actual_categories: dict[int, str] = {}
    for category in payload["categories"]:
        if not isinstance(category, dict) or not isinstance(category.get("id"), int) or not isinstance(category.get("name"), str) or category["id"] in actual_categories:
            raise ValueError(f"invalid category record: {source_name}")
        actual_categories[category["id"]] = category["name"]
    if actual_categories != expected_categories:
        raise ValueError(f"exact class map mismatch: {source_name}")

    images: dict[int, tuple[str, int, int]] = {}
    for image in payload["images"]:
        if not isinstance(image, dict) or not isinstance(image.get("id"), int) or not isinstance(image.get("file_name"), str) or not isinstance(image.get("width"), int) or not isinstance(image.get("height"), int):
            raise ValueError(f"invalid image record: {source_name}")
        image_id, file_name, width, height = image["id"], image["file_name"], image["width"], image["height"]
        if image_id in images or width <= 0 or height <= 0 or Path(file_name).name != file_name:
            raise ValueError(f"invalid image identity: {source_name}")
        images[image_id] = (file_name, width, height)
    boxes_by_image: dict[int, list[SkuBox]] = {image_id: [] for image_id in images}
    annotation_ids: set[int] = set()
    for annotation in payload["annotations"]:
        if not isinstance(annotation, dict) or not isinstance(annotation.get("id"), int) or annotation["id"] in annotation_ids or annotation.get("image_id") not in images or annotation.get("category_id") not in expected_categories:
            raise ValueError(f"invalid annotation identity: {source_name}")
        annotation_ids.add(annotation["id"])
        bbox = annotation.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in bbox):
            raise ValueError(f"invalid COCO bbox: {source_name}")
        x, y, width, height = (float(value) for value in bbox)
        declared_width, declared_height = images[annotation["image_id"]][1:]
        if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > declared_width or y + height > declared_height:
            raise ValueError("COCO bbox exceeds canonical image bounds")
        boxes_by_image[annotation["image_id"]].append(SkuBox(annotation["category_id"], (x, y, width, height)))

    records: list[SceneRecord] = []
    for image_id, (file_name, declared_width, declared_height) in sorted(images.items()):
        match = _SCENE_PATTERN.fullmatch(file_name)
        if match is None:
            raise ValueError(f"invalid scene file name: {file_name}")
        image_path = source_root / "images" / file_name
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as handle:
            canonical = ImageOps.exif_transpose(handle)
            actual_width, actual_height = canonical.size
        if (declared_width, declared_height) != (actual_width, actual_height):
            raise ValueError(f"declared dimensions differ from EXIF-transposed image: {image_path}")
        difficulty = match.group(1).upper()
        records.append(SceneRecord(
            scene_id=f"{source_name}:{file_name}", source_name=source_name, file_name=file_name,
            difficulty=difficulty, capture_number=int(match.group(2)), width=actual_width, height=actual_height,
            image_sha256=_file_sha256(image_path), boxes=tuple(sorted(boxes_by_image[image_id], key=lambda box: (box.sku_id, box.box_xywh))),
        ))
    expected_scene_count, expected_box_count = _EXPECTED_COUNTS[source_name]
    if len(records) != expected_scene_count or sum(len(record.boxes) for record in records) != expected_box_count:
        raise ValueError(f"exact source counts mismatch: {source_name}")
    return tuple(records)


def _load_isolated(root: Path) -> dict[int, tuple[SourceImage, ...]]:
    found: dict[int, tuple[SourceImage, ...]] = {}
    for collection, sku_ids, expected_count in (("base", _BASE_SKUS, 84), ("incremental", _INCREMENTAL_SKUS, 5)):
        collection_root = root / "classifier" / collection
        actual_directories = {path.name: path for path in collection_root.iterdir() if path.is_dir()}
        expected_directories = {f"Bread{sku_id:02d}_{_SKU_NAMES[sku_id]}": sku_id for sku_id in sku_ids}
        if set(actual_directories) != set(expected_directories):
            raise ValueError(f"exact isolated class map mismatch: {collection}")
        for directory_name, sku_id in sorted(expected_directories.items(), key=lambda item: item[1]):
            directory = actual_directories[directory_name]
            images = tuple(sorted(path for path in directory.iterdir() if path.is_file()))
            if len(images) != expected_count:
                raise ValueError(f"exact isolated image count mismatch: SKU {sku_id}")
            rows = tuple(SourceImage(sku_id, path.relative_to(root).as_posix(), path, _file_sha256(path)) for path in images)
            if len({row.identity for row in rows}) != len(rows):
                raise ValueError(f"duplicate isolated identity: SKU {sku_id}")
            found[sku_id] = rows
    return found


def _assert_exact_counts(inventory: SkuSceneInventory) -> None:
    if inventory.scene_count != 299 or inventory.box_count != 1406:
        raise ValueError("exact inventory counts mismatch")
    if dict(inventory.difficulty_counts) != {"E": 100, "M": 99, "H": 100}:
        raise ValueError("exact inventory difficulty counts mismatch")
    if set(inventory.isolated_by_sku) != set(_SKU_NAMES):
        raise ValueError("exact isolated SKU identities mismatch")
    if {box.sku_id for scene in inventory.scenes for box in scene.boxes} != set(_SKU_NAMES):
        raise ValueError("exact SKU box coverage mismatch")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_sha256(inventory: SkuSceneInventory) -> str:
    payload = {
        "isolated": {str(sku_id): [{"identity": row.identity, "sha256": row.sha256} for row in rows] for sku_id, rows in inventory.isolated_by_sku.items()},
        "scenes": [{"id": scene.scene_id, "image_sha256": scene.image_sha256, "boxes": [{"sku_id": box.sku_id, "box_xywh": list(box.box_xywh)} for box in scene.boxes]} for scene in inventory.scenes],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
