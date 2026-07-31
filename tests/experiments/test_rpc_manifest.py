"""Hermetic contract tests for immutable RPC source indexing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bakery_scanner.experiments.rpc_manifest import (
    RpcDatasetContract,
    canonical_json_bytes,
    load_rpc_index,
    write_new_json,
)


def _write_coco(root: Path, split: str, *, bbox: list[float] | None = None) -> bytes:
    image_path = root / f"{split}.jpg"
    image_path.write_bytes(f"pixels:{split}".encode("ascii"))
    payload = {
        "images": [
            {
                "id": 1,
                "file_name": image_path.name,
                "width": 12,
                "height": 9,
                "level": "easy" if split != "train2019" else "",
            }
        ],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 7,
                "bbox": bbox if bbox is not None else [1, 2, 3, 4],
            }
        ],
        "categories": [{"id": 7, "name": "bread"}],
    }
    content = canonical_json_bytes(payload)
    (root / f"instances_{split}.json").write_bytes(content)
    return content


def _synthetic_contract(root: Path, *, bbox: list[float] | None = None) -> RpcDatasetContract:
    digests = {
        split: hashlib.sha256(_write_coco(root, split, bbox=bbox)).hexdigest()
        for split in ("train2019", "val2019", "test2019")
    }
    return RpcDatasetContract(annotation_sha256=digests, image_counts={split: 1 for split in digests})


def test_load_rpc_index_rejects_duplicate_extracted_root(tmp_path: Path):
    contract = RpcDatasetContract.default()
    duplicate = tmp_path / "retail_product_checkout"
    duplicate.mkdir()
    with pytest.raises(ValueError, match="duplicate extracted RPC root"):
        load_rpc_index(contract, duplicate)


def test_write_new_json_refuses_to_replace_receipt(tmp_path: Path):
    output = tmp_path / "manifest.json"
    write_new_json(output, {"schema_version": 1})
    with pytest.raises(FileExistsError):
        write_new_json(output, {"schema_version": 1})


def test_load_rpc_index_rejects_annotation_digest_mismatch(tmp_path: Path):
    contract = _synthetic_contract(tmp_path)
    (tmp_path / "instances_val2019.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        load_rpc_index(contract, tmp_path)


def test_load_rpc_index_rejects_invalid_val_level(tmp_path: Path):
    contract = _synthetic_contract(tmp_path)
    annotation_path = tmp_path / "instances_val2019.json"
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    payload["images"][0]["level"] = "unknown"
    content = canonical_json_bytes(payload)
    annotation_path.write_bytes(content)
    invalid_level_contract = RpcDatasetContract(
        annotation_sha256={**contract.annotation_sha256, "val2019": hashlib.sha256(content).hexdigest()},
        image_counts=contract.image_counts,
    )

    with pytest.raises(ValueError, match="level must be easy, medium, or hard"):
        load_rpc_index(invalid_level_contract, tmp_path)


def test_load_rpc_index_rejects_non_positive_coco_box(tmp_path: Path):
    contract = _synthetic_contract(tmp_path, bbox=[1, 2, 0, 4])

    with pytest.raises(ValueError, match="non-positive bbox"):
        load_rpc_index(contract, tmp_path)


@pytest.mark.parametrize("bbox", [[-1, 2, 3, 4], [10, 2, 3, 4], [1, 7, 3, 3]])
def test_load_rpc_index_rejects_coco_box_outside_declared_image_bounds(
    tmp_path: Path, bbox: list[float]
):
    contract = _synthetic_contract(tmp_path, bbox=bbox)

    with pytest.raises(ValueError, match="outside image bounds"):
        load_rpc_index(contract, tmp_path)


def test_load_rpc_index_accepts_and_indexes_multiple_val_and_test_annotations(
    tmp_path: Path,
):
    contract = _synthetic_contract(tmp_path)
    digests = dict(contract.annotation_sha256)
    for split in ("val2019", "test2019"):
        annotation_path = tmp_path / f"instances_{split}.json"
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        payload["annotations"].append(
            {"id": 2, "image_id": 1, "category_id": 7, "bbox": [5, 2, 3, 4]}
        )
        content = canonical_json_bytes(payload)
        annotation_path.write_bytes(content)
        digests[split] = hashlib.sha256(content).hexdigest()
    multi_object_contract = RpcDatasetContract(
        annotation_sha256=digests,
        image_counts=contract.image_counts,
    )

    index = load_rpc_index(multi_object_contract, tmp_path)

    assert [(item.split, item.annotation_id) for item in index.objects] == [
        ("train2019", 1),
        ("val2019", 1),
        ("val2019", 2),
        ("test2019", 1),
        ("test2019", 2),
    ]
    assert [(item.split, item.category_id) for item in index.images] == [
        ("train2019", 7),
        ("val2019", 7),
        ("val2019", 7),
        ("test2019", 7),
        ("test2019", 7),
    ]


def test_load_rpc_index_indexes_source_file_identity_and_digest(tmp_path: Path):
    contract = _synthetic_contract(tmp_path)

    index = load_rpc_index(contract, tmp_path)

    image = next(item for item in index.images if item.split == "train2019")
    assert image.source_path == tmp_path / "train2019.jpg"
    assert image.source_identity == "train2019:1:train2019.jpg"
    assert image.category_id == 7
    assert image.byte_size == len(b"pixels:train2019")
    assert image.sha256 == hashlib.sha256(b"pixels:train2019").hexdigest()
    assert next(item for item in index.images if item.split == "val2019").level == "easy"
