"""Deterministic scene-grouped folds for development evaluation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from bakery_scanner.contracts import SceneKey
from bakery_scanner.data.coco import StagedDataset


@dataclass(frozen=True, slots=True)
class FoldManifest:
    index: int
    training_scenes: tuple[SceneKey, ...]
    validation_scenes: tuple[SceneKey, ...]
    training_image_ids: tuple[int, ...]
    validation_image_ids: tuple[int, ...]
    source_hashes: tuple[str, ...]
    manifest_hash: str


def build_scene_folds(dataset: StagedDataset, fold_count: int = 5, seed: int = 20260724) -> tuple[FoldManifest, ...]:
    if fold_count < 2:
        raise ValueError("fold_count must be at least two")
    rows = tuple(sorted(dataset.images, key=lambda row: row.image_id))
    if len(dataset.scenes) < fold_count:
        raise ValueError("not enough scenes for requested fold count")
    labels = np.asarray([_stratum(row.box_count, row.overlap_proxy) for row in rows])
    groups = np.asarray([f"{row.scene.capture_batch}:{row.scene.scene_number:04d}" for row in rows])
    splitter = StratifiedGroupKFold(n_splits=fold_count, shuffle=True, random_state=seed)
    manifests = []
    for index, (train_indices, validation_indices) in enumerate(splitter.split(np.zeros(len(rows)), labels, groups)):
        train_rows = tuple(rows[position] for position in train_indices)
        validation_rows = tuple(rows[position] for position in validation_indices)
        manifest = {
            "index": index,
            "source_hashes": sorted({row.source_sha256 for row in rows}),
            "training_image_ids": sorted(row.image_id for row in train_rows),
            "training_scenes": _scene_payload(train_rows),
            "validation_image_ids": sorted(row.image_id for row in validation_rows),
            "validation_scenes": _scene_payload(validation_rows),
        }
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        manifests.append(FoldManifest(index, tuple(SceneKey(**item) for item in manifest["training_scenes"]), tuple(SceneKey(**item) for item in manifest["validation_scenes"]), tuple(manifest["training_image_ids"]), tuple(manifest["validation_image_ids"]), tuple(manifest["source_hashes"]), digest))
    return tuple(manifests)


def write_fold_manifests(folds: tuple[FoldManifest, ...], output: Path) -> None:
    """Persist complete fold manifests without replacing an existing run."""
    if not folds:
        raise ValueError("at least one fold manifest is required")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to replace existing fold manifests: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.write-", dir=output.parent))
    try:
        for fold in folds:
            fold_directory = temporary / f"fold-{fold.index}"
            fold_directory.mkdir()
            payload = {
                "index": fold.index,
                "manifest_hash": fold.manifest_hash,
                "source_hashes": list(fold.source_hashes),
                "training_image_ids": list(fold.training_image_ids),
                "training_scenes": _scene_payload_from_scenes(fold.training_scenes),
                "validation_image_ids": list(fold.validation_image_ids),
                "validation_scenes": _scene_payload_from_scenes(fold.validation_scenes),
            }
            (fold_directory / "manifest.json").write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _stratum(box_count: int, overlap_proxy: bool) -> str:
    count_bin = "0-2" if box_count <= 2 else "3-5" if box_count <= 5 else "6+"
    return f"{count_bin}:{int(overlap_proxy)}"


def _scene_payload(rows: tuple[object, ...]) -> list[dict[str, object]]:
    scenes = sorted({row.scene for row in rows})  # type: ignore[attr-defined]
    return _scene_payload_from_scenes(scenes)


def _scene_payload_from_scenes(scenes: tuple[SceneKey, ...] | list[SceneKey]) -> list[dict[str, object]]:
    return [{"capture_batch": scene.capture_batch, "scene_number": scene.scene_number} for scene in scenes]
