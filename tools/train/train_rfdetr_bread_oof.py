"""Train class-agnostic RF-DETR-L folds without leaking held-out scenes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from bakery_scanner.data.coco import load_staged_dataset


_BASE_SEED = 20260803
_CATEGORY_MAP = {"1": "bread"}
_RECEIPT_NAME = "receipt.json"


def run_fold_training(
    split_manifest: Mapping[str, object] | Path,
    *,
    fold_index: int,
    model_factory: Callable[[], Any],
    staged_root: Path,
    output_root: Path,
    pretrain_weights_sha256: str | None = None,
) -> dict[str, object]:
    """Materialize one train-only fold and invoke the supplied RF-DETR model.

    This function deliberately has no inference or threshold-selection path.
    Calibration and evaluation identities are recorded for audit but never staged
    into the directory handed to ``RFDETRLarge.train``.
    """
    manifest = _load_manifest(split_manifest)
    if manifest["fold_index"] != fold_index:
        raise ValueError("requested fold does not match split manifest")
    run_root = Path(output_root).resolve() / f"fold-{fold_index}"
    receipt_path = run_root / _RECEIPT_NAME
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {receipt_path}")
    if run_root.exists():
        raise FileExistsError(f"refusing to reuse existing run directory: {run_root}")

    staged = load_staged_dataset(Path(staged_root))
    selected = _select_training_images(staged, manifest["scene_ids"]["train"])
    train_root = run_root / "train"
    _write_train_subset(staged.root, staged.annotations, selected, train_root, fold_index=fold_index)
    notes = _training_notes(manifest, staged.root, pretrain_weights_sha256=pretrain_weights_sha256)
    model = model_factory()
    if not hasattr(model, "train"):
        raise TypeError("RF-DETR model factory must return a model with train()")
    model.train(
        dataset_dir=str(train_root),
        device="cuda:0",
        num_classes=1,
        dataset_file="coco",
        class_names=["bread"],
        amp_dtype="fp16",
        seed=notes["training_seed"],
        output_dir=str(run_root / "checkpoint"),
        notes=notes,
    )
    return notes


def _load_manifest(source: Mapping[str, object] | Path) -> dict[str, object]:
    if isinstance(source, Path):
        payload = json.loads(source.read_text(encoding="utf-8"))
    else:
        payload = dict(source)
    if payload.get("schema_version") != 1:
        raise ValueError("split manifest schema_version must be 1")
    if not isinstance(payload.get("fold_index"), int) or not isinstance(payload.get("seed"), int):
        raise ValueError("split manifest must identify fold and seed")
    for key in ("source_sha256", "manifest_sha256"):
        if not _is_sha256(payload.get(key)):
            raise ValueError(f"split manifest {key} must be SHA-256")
    raw_roles = payload.get("scene_ids")
    if not isinstance(raw_roles, dict) or set(raw_roles) != {"train", "calibration", "evaluation"}:
        raise ValueError("split manifest must provide exactly train, calibration, and evaluation scene roles")
    roles: dict[str, tuple[str, ...]] = {}
    for role in ("train", "calibration", "evaluation"):
        rows = raw_roles[role]
        if not isinstance(rows, list) or not rows or any(not isinstance(row, str) or not row for row in rows):
            raise ValueError(f"split manifest {role} scenes are invalid")
        roles[role] = tuple(sorted(rows))
    if len(set().union(*[set(value) for value in roles.values()])) != sum(len(value) for value in roles.values()):
        raise ValueError("split manifest roles must be disjoint")
    return {
        "fold_index": payload["fold_index"],
        "seed": payload["seed"],
        "source_sha256": payload["source_sha256"],
        "manifest_sha256": payload["manifest_sha256"],
        "scene_ids": roles,
    }


def _select_training_images(staged: Any, train_scene_ids: tuple[str, ...]) -> tuple[Any, ...]:
    by_scene = {_staged_scene_id(row.file_name): row for row in staged.images}
    if len(by_scene) != len(staged.images):
        raise ValueError("staged dataset has duplicate scene identities")
    missing = sorted(set(train_scene_ids) - set(by_scene))
    if missing:
        raise ValueError(f"staged dataset is missing train scenes: {missing[:3]}")
    return tuple(by_scene[scene_id] for scene_id in train_scene_ids)


def _staged_scene_id(file_name: str) -> str:
    try:
        source, staged_name = file_name.split("__", 1)
    except ValueError as error:
        raise ValueError(f"staged file name does not preserve source identity: {file_name}") from error
    return f"{source}:{Path(staged_name).stem}.jpg"


def _write_train_subset(staged_root: Path, annotation_path: Path, selected: tuple[Any, ...], train_root: Path, *, fold_index: int) -> None:
    train_root.mkdir(parents=True)
    train_images_root = train_root / "train2017"
    validation_images_root = train_root / "val2017"
    annotations_root = train_root / "annotations"
    train_images_root.mkdir()
    validation_images_root.mkdir()
    annotations_root.mkdir()
    selected_ids = {row.image_id for row in selected}
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    images = [row for row in payload["images"] if row.get("id") in selected_ids]
    annotations = [row for row in payload["annotations"] if row.get("image_id") in selected_ids]
    categories = payload.get("categories")
    if categories != [{"id": 1, "name": "bread", "supercategory": "object"}]:
        raise ValueError("staged COCO must have exact class map {1: bread}")
    if {row["id"] for row in images} != selected_ids:
        raise ValueError("staged annotations do not cover selected train scenes")
    validation_row = min(selected, key=lambda row: hashlib.sha256(f"{_BASE_SEED + fold_index}:{row.file_name}".encode("utf-8")).hexdigest())
    train_ids = selected_ids - {validation_row.image_id} or {validation_row.image_id}
    validation_ids = {validation_row.image_id}
    for row in selected:
        source = staged_root / "images" / row.file_name
        if row.image_id in train_ids:
            shutil.copy2(source, train_images_root / row.file_name)
        if row.image_id in validation_ids:
            shutil.copy2(source, validation_images_root / row.file_name)
    all_payload = {"images": images, "annotations": annotations, "categories": categories}
    (train_root / "annotations.json").write_text(json.dumps(all_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    _write_coco_split(annotations_root / "instances_train2017.json", images, annotations, categories, train_ids)
    _write_coco_split(annotations_root / "instances_val2017.json", images, annotations, categories, validation_ids)


def _write_coco_split(path: Path, images: list[dict[str, object]], annotations: list[dict[str, object]], categories: object, image_ids: set[int]) -> None:
    payload = {
        "images": [row for row in images if row["id"] in image_ids],
        "annotations": [row for row in annotations if row["image_id"] in image_ids],
        "categories": categories,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _training_notes(manifest: Mapping[str, object], staged_root: Path, *, pretrain_weights_sha256: str | None) -> dict[str, object]:
    notes = {
        "base_seed": _BASE_SEED,
        "category_map": dict(_CATEGORY_MAP),
        "config_sha256": _sha256(Path(__file__)),
        "fold_manifest_sha256": manifest["manifest_sha256"],
        "fold_index": manifest["fold_index"],
        "seed": _BASE_SEED,
        "training_seed": _BASE_SEED + int(manifest["fold_index"]),
        "source_sha256": manifest["source_sha256"],
        "staged_annotations_sha256": _sha256(staged_root / "annotations.json"),
        "staged_manifest_sha256": _sha256(staged_root / "staged_manifest.json"),
    }
    if pretrain_weights_sha256 is not None:
        if not _is_sha256(pretrain_weights_sha256):
            raise ValueError("pretrain checkpoint SHA-256 is invalid")
        notes["pretrain_weights_sha256"] = pretrain_weights_sha256
    return notes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _write_unverified_receipt(run_root: Path, *, fold_index: int, status: str, detail: str) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    receipt_path = run_root / _RECEIPT_NAME
    if receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {receipt_path}")
    receipt_path.write_text(
        json.dumps({"fold_index": fold_index, "status": status, "detail": detail}, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--fold", choices=("0", "1", "2", "3", "4", "all"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--pretrain-weights", type=Path)
    parser.add_argument("--pretrain-sha256")
    arguments = parser.parse_args()
    output_root = arguments.output.resolve()
    selected_folds = range(5) if arguments.fold == "all" else (int(arguments.fold),)
    if output_root.exists() and any((output_root / f"fold-{index}" / _RECEIPT_NAME).exists() for index in selected_folds):
        raise FileExistsError("refusing to overwrite an existing fold receipt")
    staged_root = arguments.staged_root
    if staged_root is None:
        configured_staged_root = os.environ.get("BIXOLON_RFDETR_STAGED_ROOT")
        staged_root = Path(configured_staged_root) if configured_staged_root else None
    if staged_root is None or not staged_root.is_dir():
        for index in selected_folds:
            _write_unverified_receipt(output_root / f"fold-{index}", fold_index=index, status="unverified_missing_staged_coco", detail="supply --staged-root or BIXOLON_RFDETR_STAGED_ROOT")
        return 2
    try:
        from rfdetr import RFDETRLarge
    except ImportError as error:
        for index in selected_folds:
            _write_unverified_receipt(output_root / f"fold-{index}", fold_index=index, status="unverified_missing_rfdetr_train_runtime", detail=str(error))
        return 2
    if arguments.pretrain_weights is None or arguments.pretrain_sha256 is None:
        for index in selected_folds:
            _write_unverified_receipt(output_root / f"fold-{index}", fold_index=index, status="unverified_missing_rfdetr_pretrain_checkpoint", detail="supply --pretrain-weights and --pretrain-sha256")
        return 2
    pretrain_weights = arguments.pretrain_weights.resolve()
    if not pretrain_weights.is_file() or not _is_sha256(arguments.pretrain_sha256) or _sha256(pretrain_weights) != arguments.pretrain_sha256:
        for index in selected_folds:
            _write_unverified_receipt(output_root / f"fold-{index}", fold_index=index, status="unverified_invalid_rfdetr_pretrain_checkpoint", detail="checkpoint is missing or SHA-256 does not match")
        return 2
    pending_folds = tuple(selected_folds)
    for position, index in enumerate(pending_folds):
        try:
            run_fold_training(
                arguments.splits / f"fold-{index}.json",
                fold_index=index,
                model_factory=lambda: RFDETRLarge(pretrain_weights=str(pretrain_weights), num_classes=1, device="cuda:0"),
                staged_root=staged_root,
                output_root=output_root,
                pretrain_weights_sha256=arguments.pretrain_sha256,
            )
        except ImportError as error:
            for remaining in pending_folds[position:]:
                _write_unverified_receipt(output_root / f"fold-{remaining}", fold_index=remaining, status="unverified_missing_rfdetr_train_runtime", detail=str(error))
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
