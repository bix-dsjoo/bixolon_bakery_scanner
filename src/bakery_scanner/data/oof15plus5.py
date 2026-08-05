"""Deterministic five-way out-of-fold manifests for the immutable 15+5 inventory."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Literal

from PIL import Image, ImageOps

from bakery_scanner.data.sku_scene import OofFold, SceneRecord, SkuSceneInventory


_ROLE = Literal["train", "calibration", "evaluation"]
_FOLD_COUNT = 5


def build_oof_folds(inventory: SkuSceneInventory, seed: int = 20260803) -> tuple[OofFold, ...]:
    """Construct deterministic grouped rotations without leaking related captures."""
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    scenes_by_group: dict[str, list[SceneRecord]] = defaultdict(list)
    for scene in inventory.scenes:
        scenes_by_group[_capture_group(scene)].append(scene)
    components = _union_similar_groups(scenes_by_group, _dataset_root(inventory))
    split_by_component = _stratified_component_splits(components, scenes_by_group, seed)
    group_split = {
        group_id: split_index
        for split_index, component_ids in enumerate(split_by_component)
        for component_id in component_ids
        for group_id in components[component_id]
    }
    folds: list[OofFold] = []
    for fold_index in range(_FOLD_COUNT):
        role_by_group: dict[str, _ROLE] = {}
        role_scene_ids: dict[_ROLE, list[str]] = {"train": [], "calibration": [], "evaluation": []}
        for group_id, split_index in sorted(group_split.items()):
            role: _ROLE = "evaluation" if split_index == fold_index else "calibration" if split_index == (fold_index + 1) % _FOLD_COUNT else "train"
            role_by_group[group_id] = role
            role_scene_ids[role].extend(scene.scene_id for scene in scenes_by_group[group_id])
        payload = _fold_payload(
            fold_index=fold_index,
            seed=seed,
            source_sha256=inventory.source_sha256,
            role_scene_ids=role_scene_ids,
            role_by_group=role_by_group,
            scene_lookup={scene.scene_id: scene for scene in inventory.scenes},
        )
        digest = _payload_sha256(payload)
        folds.append(OofFold(
            fold_index=fold_index,
            training_scene_ids=tuple(sorted(role_scene_ids["train"])),
            calibration_scene_ids=tuple(sorted(role_scene_ids["calibration"])),
            evaluation_scene_ids=tuple(sorted(role_scene_ids["evaluation"])),
            group_roles=MappingProxyType(dict(sorted(role_by_group.items()))),
            manifest_sha256=digest,
            seed=seed,
        ))
    return tuple(folds)


def write_oof_manifests(folds: Iterable[OofFold], inventory: SkuSceneInventory, output: Path) -> None:
    """Write hashes-first manifests, accepting an existing directory only byte-for-byte."""
    fold_rows = tuple(sorted(folds, key=lambda fold: fold.fold_index))
    if len(fold_rows) != _FOLD_COUNT or tuple(fold.fold_index for fold in fold_rows) != tuple(range(_FOLD_COUNT)):
        raise ValueError("exactly five folds indexed 0 through 4 are required")
    expected = {"inventory.json": _canonical_json(_inventory_payload(inventory))}
    scene_lookup = {scene.scene_id: scene for scene in inventory.scenes}
    for fold in fold_rows:
        payload = _fold_payload_from_fold(fold, inventory.source_sha256, scene_lookup)
        if _payload_sha256(payload) != fold.manifest_sha256:
            raise ValueError(f"fold manifest hash mismatch: {fold.fold_index}")
        expected[f"fold-{fold.fold_index}.json"] = _canonical_json({**payload, "manifest_sha256": fold.manifest_sha256})
    output = Path(output)
    if output.exists():
        if output.is_dir() and {path.name for path in output.iterdir()} == set(expected) and all((output / name).is_file() and (output / name).read_bytes() == content for name, content in expected.items()):
            return
        raise FileExistsError(f"refusing to replace non-identical OOF manifests: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.write-", dir=output.parent))
    try:
        for name, content in expected.items():
            (temporary / name).write_bytes(content)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _capture_group(scene: SceneRecord) -> str:
    return f"{scene.source_name}:{scene.capture_number}"


def _union_similar_groups(scenes_by_group: dict[str, list[SceneRecord]], dataset_root: Path) -> dict[str, tuple[str, ...]]:
    groups_by_source: dict[str, list[str]] = defaultdict(list)
    for group_id, scenes in scenes_by_group.items():
        groups_by_source[scenes[0].source_name].append(group_id)
    parent = {group_id: group_id for group_id in scenes_by_group}

    def find(group_id: str) -> str:
        while parent[group_id] != group_id:
            parent[group_id] = parent[parent[group_id]]
            group_id = parent[group_id]
        return group_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for group_ids in groups_by_source.values():
        hashes = {group_id: tuple(_dhash(scene, dataset_root) for scene in scenes_by_group[group_id]) for group_id in group_ids}
        for index, left in enumerate(sorted(group_ids)):
            for right in sorted(group_ids)[index + 1:]:
                if any(_hamming(first, second) <= 4 for first in hashes[left] for second in hashes[right]):
                    union(left, right)
    components: dict[str, list[str]] = defaultdict(list)
    for group_id in sorted(scenes_by_group):
        components[find(group_id)].append(group_id)
    return {component_id: tuple(group_ids) for component_id, group_ids in sorted(components.items())}


def _dhash(scene: SceneRecord, dataset_root: Path) -> int:
    image_path = dataset_root / "detection" / scene.source_name / "images" / scene.file_name
    return _image_dhash(image_path)


@lru_cache(maxsize=None)
def _image_dhash(image_path: Path) -> int:
    with Image.open(image_path) as handle:
        image = ImageOps.exif_transpose(handle).convert("L").resize((9, 8))
        pixels = list(image.get_flattened_data())
    bits = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            bits = (bits << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    return bits


def _dataset_root(inventory: SkuSceneInventory) -> Path:
    first_sku = min(inventory.isolated_by_sku)
    first_image = inventory.isolated_by_sku[first_sku][0]
    return first_image.path.parents[3]


def _hamming(first: int, second: int) -> int:
    return (first ^ second).bit_count()


def _stratified_component_splits(
    components: dict[str, tuple[str, ...]], scenes_by_group: dict[str, list[SceneRecord]], seed: int
) -> tuple[tuple[str, ...], ...]:
    if len(components) < _FOLD_COUNT:
        raise ValueError("not enough independent groups for five folds")
    features = {component_id: _component_features(group_ids, scenes_by_group) for component_id, group_ids in components.items()}
    totals: Counter[str] = Counter()
    for feature in features.values():
        totals.update(feature)
    targets = {name: value / _FOLD_COUNT for name, value in totals.items()}
    split_features = [Counter() for _ in range(_FOLD_COUNT)]
    split_components: list[list[str]] = [[] for _ in range(_FOLD_COUNT)]
    ordered = sorted(components, key=lambda component_id: (-sum(features[component_id].values()), _seed_order(component_id, seed)))
    for position, component_id in enumerate(ordered):
        candidates = range(_FOLD_COUNT) if position >= _FOLD_COUNT else (position,)
        split_index = min(candidates, key=lambda index: (_assignment_cost(split_features, features[component_id], targets, index), len(split_components[index]), index))
        split_components[split_index].append(component_id)
        split_features[split_index].update(features[component_id])
    return tuple(tuple(sorted(component_ids)) for component_ids in split_components)


def _component_features(group_ids: tuple[str, ...], scenes_by_group: dict[str, list[SceneRecord]]) -> Counter[str]:
    scenes = [scene for group_id in group_ids for scene in scenes_by_group[group_id]]
    values: Counter[str] = Counter()
    values.update(f"sku:{sku_id}" for sku_id in sorted({box.sku_id for scene in scenes for box in scene.boxes}))
    values.update(f"difficulty:{scene.difficulty}" for scene in scenes)
    object_count = sum(len(scene.boxes) for scene in scenes)
    values[f"objects:{'1-4' if object_count <= 4 else '5-9' if object_count <= 9 else '10+'}"] = 1
    values.update(f"shape:{scene.width}x{scene.height}" for scene in scenes)
    return values


def _seed_order(value: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def _assignment_cost(current: list[Counter[str]], addition: Counter[str], targets: dict[str, float], candidate: int) -> float:
    return sum((current[index][feature] + (addition[feature] if index == candidate else 0) - target) ** 2 for index in range(_FOLD_COUNT) for feature, target in targets.items())


def _fold_payload_from_fold(fold: OofFold, source_sha256: str, scene_lookup: dict[str, SceneRecord]) -> dict[str, object]:
    scene_ids: dict[_ROLE, list[str]] = {
        "train": list(fold.training_scene_ids), "calibration": list(fold.calibration_scene_ids), "evaluation": list(fold.evaluation_scene_ids),
    }
    return _fold_payload(fold.fold_index, fold.seed, source_sha256, scene_ids, dict(fold.group_roles), scene_lookup)


def _fold_payload(
    fold_index: int, seed: int, source_sha256: str, role_scene_ids: dict[_ROLE, list[str]], role_by_group: dict[str, _ROLE], scene_lookup: dict[str, SceneRecord]
) -> dict[str, object]:
    group_ids = {role: sorted(group_id for group_id, assigned in role_by_group.items() if assigned == role) for role in ("train", "calibration", "evaluation")}
    sku_counts: dict[str, dict[str, int]] = {}
    difficulty_counts: dict[str, dict[str, int]] = {}
    for role, scene_ids in role_scene_ids.items():
        scenes = [scene_lookup[scene_id] for scene_id in scene_ids]
        sku_counts[role] = {str(sku_id): sum(box.sku_id == sku_id for scene in scenes for box in scene.boxes) for sku_id in range(1, 21)}
        difficulty_counts[role] = {difficulty: sum(scene.difficulty == difficulty for scene in scenes) for difficulty in ("E", "M", "H")}
    return {
        "schema_version": 1, "seed": seed, "source_sha256": source_sha256, "fold_index": fold_index,
        "scene_ids": {role: sorted(scene_ids) for role, scene_ids in role_scene_ids.items()},
        "group_ids": group_ids, "sku_counts": sku_counts, "difficulty_counts": difficulty_counts,
    }


def _inventory_payload(inventory: SkuSceneInventory) -> dict[str, object]:
    payload = {
        "schema_version": 1, "source_sha256": inventory.source_sha256, "scene_count": inventory.scene_count,
        "box_count": inventory.box_count, "difficulty_counts": dict(inventory.difficulty_counts),
        "isolated_counts": {str(sku_id): count for sku_id, count in inventory.isolated_counts.items()},
        "scene_ids": [scene.scene_id for scene in inventory.scenes],
    }
    return {**payload, "manifest_sha256": _payload_sha256(payload)}


def _payload_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
