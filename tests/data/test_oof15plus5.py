from __future__ import annotations

from pathlib import Path

import pytest

from bakery_scanner.data.oof15plus5 import build_oof_folds, write_oof_manifests
from bakery_scanner.data.sku_scene import SkuSceneInventory, load_inventory


DATASET_ROOT = Path(r"C:\workspace\bixolon_bakery_scanner\datasets")


@pytest.fixture(scope="module")
def inventory() -> SkuSceneInventory:
    if not DATASET_ROOT.is_dir():
        pytest.skip(f"external dataset is unavailable: {DATASET_ROOT}")
    return load_inventory(DATASET_ROOT)


def test_same_batch_capture_number_never_crosses_fold(inventory: SkuSceneInventory) -> None:
    folds = build_oof_folds(inventory, seed=20260803)

    for fold in folds:
        roles = fold.group_roles
        assert len(roles) == len(set(roles))
        assert set(roles.values()) == {"train", "calibration", "evaluation"}
        for scene in inventory.scenes:
            group_id = f"{scene.source_name}:{scene.capture_number}"
            role_scene_ids = {
                "train": set(fold.training_scene_ids),
                "calibration": set(fold.calibration_scene_ids),
                "evaluation": set(fold.evaluation_scene_ids),
            }
            assert scene.scene_id in role_scene_ids[roles[group_id]]


def test_every_scene_is_evaluated_exactly_once(inventory: SkuSceneInventory) -> None:
    folds = build_oof_folds(inventory, seed=20260803)
    evaluated = [scene_id for fold in folds for scene_id in fold.evaluation_scene_ids]

    assert sorted(evaluated) == sorted(scene.scene_id for scene in inventory.scenes)


def test_oof_manifests_refuse_nonidentical_replacement(inventory: SkuSceneInventory, tmp_path: Path) -> None:
    folds = build_oof_folds(inventory, seed=20260803)
    output = tmp_path / "oof"

    write_oof_manifests(folds, inventory, output)
    original = {path.name: path.read_bytes() for path in output.iterdir()}
    write_oof_manifests(folds, inventory, output)
    assert {path.name: path.read_bytes() for path in output.iterdir()} == original

    (output / "fold-0.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(FileExistsError, match="identical"):
        write_oof_manifests(folds, inventory, output)


def test_oof_manifests_refuse_existing_extra_directory(inventory: SkuSceneInventory, tmp_path: Path) -> None:
    folds = build_oof_folds(inventory, seed=20260803)
    output = tmp_path / "oof"
    write_oof_manifests(folds, inventory, output)
    (output / "unexpected").mkdir()

    with pytest.raises(FileExistsError, match="identical"):
        write_oof_manifests(folds, inventory, output)
