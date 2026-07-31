"""Resolve immutable RPC source identities for few-shot research only."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from bakery_scanner.experiments.rpc_manifest import RpcDatasetContract, load_rpc_index, write_new_json
from bakery_scanner.experiments.rpc_scoring import materialize_locked_ground_truth
from bakery_scanner.experiments.rpc_splits import build_scene_roles, write_scene_role_manifest


def build_manifest(
    rpc_root: Path,
    output: Path,
    *,
    scene_role_output: Path | None = None,
    locked_ground_truth_output: Path | None = None,
) -> None:
    """Write one no-replace input manifest without decoding or copying pixels."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if scene_role_output is not None and scene_role_output.exists():
        raise FileExistsError(f"output already exists: {scene_role_output}")
    if locked_ground_truth_output is not None and locked_ground_truth_output.exists():
        raise FileExistsError(f"output already exists: {locked_ground_truth_output}")
    if locked_ground_truth_output is not None and scene_role_output is None:
        raise ValueError("locked ground truth requires a scene-role output")
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
    if scene_role_output is not None:
        write_scene_role_manifest(
            scene_role_output,
            build_scene_roles(index, split_version="rpc-2019-five-fold-v1"),
            source_manifest_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        )
    if locked_ground_truth_output is not None:
        materialize_locked_ground_truth(
            output,
            scene_role_output,
            locked_ground_truth_output,
            trusted_source_root=rpc_root,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scene-role-output", type=Path)
    parser.add_argument("--locked-ground-truth-output", type=Path)
    args = parser.parse_args(argv)
    try:
        build_manifest(
            args.rpc_root,
            args.output,
            scene_role_output=args.scene_role_output,
            locked_ground_truth_output=args.locked_ground_truth_output,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
