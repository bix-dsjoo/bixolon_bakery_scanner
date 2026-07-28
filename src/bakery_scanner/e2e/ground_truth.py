"""Load original COCO SKU annotations into staged scanner image identities."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Mapping

from bakery_scanner.config import ScannerConfig
from bakery_scanner.contracts import Box

from .contracts import SkuGroundTruth


def load_source_sku_ground_truth(
    config: ScannerConfig,
    *,
    classes_path: Path,
) -> Mapping[int, tuple[SkuGroundTruth, ...]]:
    """Return original SKU labels keyed by the immutable staged image IDs.

    The staging annotation intentionally replaces source categories with the
    single detector class. Its manifest still retains `source__stem` image
    identities, which lets evaluation recover source category IDs without
    changing detector inputs.
    """
    expected_categories = _load_categories(classes_path)
    staged_root = config.artifact_root / "staged"
    staged_rows = _read_array(staged_root / "staged_manifest.json", "staged manifest")
    staged_ids = _stage_ids(staged_rows, configured_sources={source.name for source in config.dataset.sources})
    labels: dict[int, list[SkuGroundTruth]] = defaultdict(list)
    for source in config.dataset.sources:
        coco = _read_object(source.annotations, f"{source.name} annotations")
        category_ids = _validate_categories(coco.get("categories"), expected_categories, source.name)
        image_stems = _source_image_stems(coco.get("images"), source.name)
        for row in _require_rows(coco.get("annotations"), f"{source.name} annotations"):
            image_id = row.get("image_id")
            category_id = row.get("category_id")
            bbox = row.get("bbox")
            if type(image_id) is not int or image_id not in image_stems:
                raise ValueError(f"{source.name} annotation image_id is invalid")
            if type(category_id) is not int or category_id not in category_ids:
                raise ValueError(f"{source.name} annotation category_id is invalid")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError(f"{source.name} annotation bbox must be xywh")
            staged_id = staged_ids.get((source.name, image_stems[image_id]))
            if staged_id is None:
                raise ValueError(f"{source.name} annotation has no staged image identity")
            try:
                labels[staged_id].append(SkuGroundTruth(staged_id, Box(*bbox), category_id))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{source.name} annotation geometry is invalid") from exc
    result = {image_id: tuple(rows) for image_id, rows in labels.items()}
    if set(result) != set(staged_ids.values()) or any(not rows for rows in result.values()):
        raise ValueError("source SKU labels must cover every staged image")
    source_count = sum(len(rows) for rows in result.values())
    if len(result) != config.dataset.expected_images:
        raise ValueError(
            "source SKU annotations contain "
            f"{len(result)} images but staging expects {config.dataset.expected_images}"
        )
    if source_count != config.dataset.expected_boxes:
        raise ValueError(
            "source SKU annotations contain "
            f"{source_count} boxes but staging expects {config.dataset.expected_boxes}"
        )
    return result


def _load_categories(path: Path) -> dict[int, str]:
    value = _read_json(path, "classes")
    if not isinstance(value, list):
        raise ValueError("classes must be an array")
    result: dict[int, str] = {}
    for row in value:
        if not isinstance(row, dict) or type(row.get("id")) is not int or not isinstance(row.get("name"), str):
            raise ValueError("classes entries require integer id and name")
        if row["id"] in result or not row["name"]:
            raise ValueError("classes entries must have unique non-empty IDs and names")
        result[row["id"]] = row["name"]
    if set(result) != set(range(1, 21)):
        raise ValueError("classes must define exactly SKU IDs 1 through 20")
    return result


def _validate_categories(value: object, expected: Mapping[int, str], source: str) -> set[int]:
    ids: set[int] = set()
    for row in _require_rows(value, f"{source} categories"):
        category_id, name = row.get("id"), row.get("name")
        if type(category_id) is not int or not isinstance(name, str) or expected.get(category_id) != name:
            raise ValueError(f"{source} categories do not match classes")
        if category_id in ids:
            raise ValueError(f"{source} categories contain duplicate IDs")
        ids.add(category_id)
    return ids


def _source_image_stems(value: object, source: str) -> dict[int, str]:
    result: dict[int, str] = {}
    for row in _require_rows(value, f"{source} images"):
        image_id, file_name = row.get("id"), row.get("file_name")
        if type(image_id) is not int or image_id <= 0 or not isinstance(file_name, str) or not Path(file_name).stem:
            raise ValueError(f"{source} image identity is invalid")
        if image_id in result:
            raise ValueError(f"{source} images contain duplicate IDs")
        result[image_id] = Path(file_name).stem
    return result


def _stage_ids(rows: list[object], *, configured_sources: set[str]) -> dict[tuple[str, str], int]:
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("staged manifest rows must be objects")
        image_id, file_name = row.get("image_id"), row.get("file_name")
        if type(image_id) is not int or image_id <= 0 or not isinstance(file_name, str):
            raise ValueError("staged manifest image identity is invalid")
        source, marker, stem = Path(file_name).stem.partition("__")
        if marker != "__" or source not in configured_sources or not stem:
            raise ValueError("staged manifest file_name must retain source__stem identity")
        key = (source, stem)
        if key in result or image_id in result.values():
            raise ValueError("staged manifest image identities must be unique")
        result[key] = image_id
    return result


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc


def _read_object(path: Path, label: str) -> dict[str, object]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _read_array(path: Path, label: str) -> list[object]:
    value = _read_json(path, label)
    return _require_rows(value, label)


def _require_rows(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value
