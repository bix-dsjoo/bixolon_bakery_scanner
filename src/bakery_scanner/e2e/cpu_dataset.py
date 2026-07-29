"""Immutable CPU-regression dataset records loaded from the source COCO files."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from bakery_scanner.contracts import Box


_SOURCES = (
    "group_15class",
    "group_20class_batch01",
    "group_20class_batch02",
)
_PROFILES = frozenset({"e", "m", "h"})
_EXPECTED_IMAGE_COUNT = 299
_EXPECTED_TARGET_COUNT = 1406


@dataclass(frozen=True, slots=True)
class CpuEvaluationTarget:
    annotation_id: int
    sku_id: int
    box: Box


@dataclass(frozen=True, slots=True)
class CpuEvaluationSample:
    key: str
    source: str
    source_image_id: int
    image_path: Path
    profile: Literal["E", "M", "H"]
    targets: tuple[CpuEvaluationTarget, ...]


def _profile_from_name(name: str) -> Literal["E", "M", "H"]:
    tokens = Path(name).stem.lower().split("_")
    matches = tuple(token.upper() for token in tokens if token in _PROFILES)
    if len(matches) != 1:
        raise ValueError(f"image name must contain exactly one E/M/H token: {name}")
    return cast(Literal["E", "M", "H"], matches[0])


def load_cpu_evaluation_samples(root: Path) -> tuple[CpuEvaluationSample, ...]:
    """Load the fixed source order used by CPU quality and latency regression."""
    package_root = Path(root)
    samples: list[CpuEvaluationSample] = []
    seen_keys: set[str] = set()
    target_count = 0

    for source in _SOURCES:
        source_root = package_root / "datasets" / "detection" / source
        coco = _read_coco(source_root / "annotations" / "instances.json", source)
        category_ids = _category_ids(coco, source)
        images = _images(coco, source)
        targets_by_image = _targets(coco, source, images, category_ids)

        for image_id in sorted(images):
            file_name, width, height = images[image_id]
            image_path = source_root / "images" / file_name
            if not image_path.is_file():
                raise ValueError(f"{source} image is missing: {image_path}")
            key = f"{source}/{file_name}"
            if key in seen_keys:
                raise ValueError(f"duplicate CPU evaluation sample key: {key}")
            seen_keys.add(key)
            targets = tuple(sorted(targets_by_image[image_id], key=lambda target: target.annotation_id))
            samples.append(
                CpuEvaluationSample(
                    key=key,
                    source=source,
                    source_image_id=image_id,
                    image_path=image_path,
                    profile=_profile_from_name(file_name),
                    targets=targets,
                )
            )
            target_count += len(targets)

    if len(samples) != _EXPECTED_IMAGE_COUNT or target_count != _EXPECTED_TARGET_COUNT:
        raise ValueError(
            "CPU evaluation dataset must contain exactly "
            f"{_EXPECTED_IMAGE_COUNT} images and {_EXPECTED_TARGET_COUNT} targets; "
            f"got {len(samples)} images and {target_count} targets"
        )
    return tuple(samples)


def _read_coco(path: Path, source: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{source} COCO annotations must be readable UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{source} COCO annotations must be an object")
    return payload


def _rows(coco: dict[str, object], field: str, source: str) -> list[dict[str, object]]:
    value = coco.get(field)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{source} {field} must be an array of objects")
    return cast(list[dict[str, object]], value)


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return float(value)


def _category_ids(coco: dict[str, object], source: str) -> set[int]:
    category_ids: set[int] = set()
    for row in _rows(coco, "categories", source):
        category_id = _positive_int(row.get("id"), f"{source} category id")
        if category_id > 20 or category_id in category_ids:
            raise ValueError(f"{source} category IDs must be unique registered SKUs")
        category_ids.add(category_id)
    if not category_ids:
        raise ValueError(f"{source} categories must not be empty")
    return category_ids


def _images(coco: dict[str, object], source: str) -> dict[int, tuple[str, int, int]]:
    images: dict[int, tuple[str, int, int]] = {}
    for row in _rows(coco, "images", source):
        image_id = _positive_int(row.get("id"), f"{source} image id")
        file_name = row.get("file_name")
        if not isinstance(file_name, str) or not file_name or Path(file_name).is_absolute() or ".." in Path(file_name).parts:
            raise ValueError(f"{source} image file_name is invalid")
        if image_id in images:
            raise ValueError(f"{source} image IDs must be unique")
        images[image_id] = (
            file_name,
            _positive_int(row.get("width"), f"{source} image width"),
            _positive_int(row.get("height"), f"{source} image height"),
        )
    return images


def _targets(
    coco: dict[str, object],
    source: str,
    images: dict[int, tuple[str, int, int]],
    category_ids: set[int],
) -> dict[int, list[CpuEvaluationTarget]]:
    targets: dict[int, list[CpuEvaluationTarget]] = defaultdict(list)
    annotation_ids: set[int] = set()
    for row in _rows(coco, "annotations", source):
        annotation_id = _positive_int(row.get("id"), f"{source} annotation id")
        image_id = _positive_int(row.get("image_id"), f"{source} annotation image_id")
        sku_id = _positive_int(row.get("category_id"), f"{source} annotation category_id")
        if annotation_id in annotation_ids:
            raise ValueError(f"{source} annotation IDs must be unique")
        if image_id not in images:
            raise ValueError(f"{source} annotation image_id is unknown")
        if sku_id not in category_ids:
            raise ValueError(f"{source} annotation category_id is unknown")
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"{source} annotation bbox must be xywh")
        x, y, width, height = (_finite_number(value, f"{source} annotation bbox") for value in bbox)
        _, image_width, image_height = images[image_id]
        if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
            raise ValueError(f"{source} annotation bbox must remain within its image")
        try:
            box = Box(x, y, width, height)
        except ValueError as exc:
            raise ValueError(f"{source} annotation bbox is invalid") from exc
        annotation_ids.add(annotation_id)
        targets[image_id].append(CpuEvaluationTarget(annotation_id, sku_id, box))
    if set(targets) != set(images) or any(not rows for rows in targets.values()):
        raise ValueError(f"{source} annotations must cover every image")
    return targets
