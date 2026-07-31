"""Resolve immutable RPC source identities for few-shot research only."""

from __future__ import annotations

import argparse
from pathlib import Path

from bakery_scanner.experiments.rpc_manifest import RpcDatasetContract, load_rpc_index, write_new_json


def build_manifest(rpc_root: Path, output: Path) -> None:
    """Write one no-replace input manifest without decoding or copying pixels."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if rpc_root.resolve().name == "retail_product_checkout":
        raise ValueError("duplicate extracted RPC root")
    contract = RpcDatasetContract.default()
    index = load_rpc_index(contract, rpc_root)
    write_new_json(output, {
        "schema_version": 1,
        "kind": "rpc-fewshot-resolved-inputs",
        "source": contract.source,
        "annotation_sha256": dict(sorted(contract.annotation_sha256.items())),
        "image_counts": dict(sorted(contract.image_counts.items())),
        "images": [
            {
                "split": image.split,
                "image_id": image.image_id,
                "source_identity": image.source_identity,
                "source_path": str(image.source_path),
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "level": image.level,
            }
            for image in index.images
        ],
        "objects": [
            {
                "split": item.split,
                "annotation_id": item.annotation_id,
                "image_id": item.image_id,
                "category_id": item.category_id,
                "bbox_xywh": list(item.bbox_xywh),
            }
            for item in index.objects
        ],
        "categories": [
            {"category_id": item.category_id, "name": item.name, "supercategory": item.supercategory}
            for item in index.categories
        ],
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        build_manifest(args.rpc_root, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
