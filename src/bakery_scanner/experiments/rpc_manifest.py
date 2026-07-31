"""Immutable source and index contract for the RPC 2019 dataset."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_SPLITS = ("train2019", "val2019", "test2019")
_DEFAULT_DIGESTS = {
    "train2019": "2fe6891a1f33d54104116940bd2b6167d2e20b846c66808ad33e98cc3775125a",
    "val2019": "25afdfed91bc09bff595399e0876a5707708a7061be3fa4121d13385abd1bde7",
    "test2019": "2a1cb518b202c7e13a74b4ca742aad76f6246cba788288bac6423c7d4a97ba58",
}
_DEFAULT_COUNTS = {"train2019": 53739, "val2019": 6000, "test2019": 24000}


@dataclass(frozen=True, slots=True)
class RpcDatasetContract:
    annotation_sha256: Mapping[str, str]
    image_counts: Mapping[str, int]
    schema_version: int = 1
    source: str = "RPC 2019"

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.source != "RPC 2019":
            raise ValueError("RPC contract schema or source is invalid")
        if set(self.annotation_sha256) != set(_SPLITS):
            raise ValueError("RPC contract must declare exactly the three splits")
        if set(self.image_counts) != set(_SPLITS):
            raise ValueError("RPC contract must declare exactly the three split counts")
        for split in _SPLITS:
            digest = self.annotation_sha256[split]
            count = self.image_counts[split]
            if not isinstance(digest, str) or len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                raise ValueError(f"{split} annotation digest must be lowercase SHA-256")
            if type(count) is not int or count <= 0:
                raise ValueError(f"{split} image count must be positive")

    @classmethod
    def default(cls) -> "RpcDatasetContract":
        return cls(dict(_DEFAULT_DIGESTS), dict(_DEFAULT_COUNTS))


@dataclass(frozen=True, slots=True)
class RpcObject:
    split: str
    annotation_id: int
    image_id: int
    category_id: int
    bbox_xywh: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class RpcImage:
    split: str
    image_id: int
    source_identity: str
    source_path: Path
    category_id: int
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class RpcIndex:
    contract: RpcDatasetContract
    images: tuple[RpcImage, ...]
    objects: tuple[RpcObject, ...]


def load_rpc_index(contract: RpcDatasetContract, root: Path) -> RpcIndex:
    """Verify and index the immutable RPC annotations without materializing pixels."""
    if not isinstance(contract, RpcDatasetContract):
        raise ValueError("contract must be an RpcDatasetContract")
    source_root = Path(root).resolve()
    if source_root.name == "retail_product_checkout":
        raise ValueError("duplicate extracted RPC root")
    if not source_root.is_dir():
        raise ValueError("RPC source root must be a directory")

    images: list[RpcImage] = []
    objects: list[RpcObject] = []
    for split in _SPLITS:
        annotation_path = source_root / f"instances_{split}.json"
        content = _read_and_verify_annotation(annotation_path, contract.annotation_sha256[split])
        payload = _parse_coco(content, split)
        split_images, split_objects, source_image_count = _index_split(
            source_root, split, payload
        )
        if source_image_count != contract.image_counts[split]:
            raise ValueError(f"{split} image count mismatch")
        if split == "train2019" and len(split_images) != source_image_count:
            raise ValueError("train2019 images must have exactly one object")
        images.extend(split_images)
        objects.extend(split_objects)
    return RpcIndex(contract, tuple(images), tuple(objects))


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def write_new_json(path: Path, payload: object) -> None:
    """Atomically create one canonical JSON receipt, never replacing an existing one."""
    output = Path(path)
    content = canonical_json_bytes(payload)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError:
            raise
    finally:
        temporary.unlink(missing_ok=True)


def _read_and_verify_annotation(path: Path, expected_digest: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read RPC annotation: {path}") from exc
    if hashlib.sha256(content).hexdigest() != expected_digest:
        raise ValueError(f"RPC annotation digest mismatch: {path.name}")
    return content


def _parse_coco(content: bytes, split: str) -> dict[str, Any]:
    try:
        payload = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{split} malformed COCO records") from exc
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(key), list) for key in ("images", "annotations", "categories")
    ):
        raise ValueError(f"{split} malformed COCO records")
    return payload


def _index_split(
    source_root: Path, split: str, payload: dict[str, Any]
) -> tuple[list[RpcImage], list[RpcObject], int]:
    image_records: dict[int, dict[str, Any]] = {}
    for record in payload["images"]:
        if not isinstance(record, dict) or type(record.get("id")) is not int:
            raise ValueError(f"{split} malformed image record")
        image_id = record["id"]
        file_name, width, height = (
            record.get("file_name"),
            record.get("width"),
            record.get("height"),
        )
        if image_id in image_records:
            raise ValueError(f"{split} duplicate image ID")
        if (
            not isinstance(file_name, str)
            or not file_name
            or type(width) is not int
            or type(height) is not int
            or width <= 0
            or height <= 0
        ):
            raise ValueError(f"{split} malformed image record")
        image_records[image_id] = record

    category_ids: set[int] = set()
    for record in payload["categories"]:
        if not isinstance(record, dict) or type(record.get("id")) is not int:
            raise ValueError(f"{split} malformed category record")
        if record["id"] in category_ids:
            raise ValueError(f"{split} duplicate category ID")
        category_ids.add(record["id"])

    annotation_ids: set[int] = set()
    objects: list[RpcObject] = []
    annotation_counts: dict[int, int] = {}
    for record in payload["annotations"]:
        if not isinstance(record, dict):
            raise ValueError(f"{split} malformed annotation record")
        annotation_id, image_id, category_id = (
            record.get("id"), record.get("image_id"), record.get("category_id")
        )
        if any(type(value) is not int for value in (annotation_id, image_id, category_id)):
            raise ValueError(f"{split} malformed annotation record")
        if annotation_id in annotation_ids:
            raise ValueError(f"{split} duplicate annotation ID")
        annotation_ids.add(annotation_id)
        if image_id not in image_records or category_id not in category_ids:
            raise ValueError(f"{split} invalid category or image link")
        image_record = image_records[image_id]
        bbox = _parse_bbox(
            record.get("bbox"), split, image_record["width"], image_record["height"]
        )
        annotation_counts[image_id] = annotation_counts.get(image_id, 0) + 1
        objects.append(RpcObject(split, annotation_id, image_id, category_id, bbox))

    indexed: list[RpcImage] = []
    source_details: dict[int, tuple[Path, int, str]] = {}
    for image_id, record in image_records.items():
        if image_id not in annotation_counts:
            raise ValueError(f"{split} image is missing checkout annotation")
        source_path = (source_root / record["file_name"]).resolve()
        try:
            source_path.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(f"{split} image path escapes source root") from exc
        if not source_path.is_file():
            raise ValueError(f"{split} source image is missing")
        source_bytes = source_path.read_bytes()
        source_details[image_id] = (
            source_path,
            len(source_bytes),
            hashlib.sha256(source_bytes).hexdigest(),
        )

    for item in objects:
        record = image_records[item.image_id]
        source_path, byte_size, source_sha256 = source_details[item.image_id]
        indexed.append(
            RpcImage(
                split=split,
                image_id=item.image_id,
                source_identity=f"{split}:{item.image_id}:{record['file_name']}",
                source_path=source_path,
                category_id=item.category_id,
                byte_size=byte_size,
                sha256=source_sha256,
            )
        )
    return indexed, objects, len(image_records)


def _parse_bbox(
    value: object, split: str, image_width: int, image_height: int
) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{split} malformed bbox")
    checked: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise ValueError(f"{split} malformed bbox")
        checked.append(float(coordinate))
    if not all(math.isfinite(coordinate) for coordinate in checked):
        raise ValueError(f"{split} non-finite bbox")
    if checked[2] <= 0 or checked[3] <= 0:
        raise ValueError(f"{split} non-positive bbox")
    x, y, width, height = checked
    if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
        raise ValueError(f"{split} bbox outside image bounds")
    return tuple(checked)  # type: ignore[return-value]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
