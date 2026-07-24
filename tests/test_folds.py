from pathlib import Path

from bakery_scanner.config import ScannerConfig
from bakery_scanner.data.coco import load_sources, stage_single_class_dataset
from bakery_scanner.data.folds import build_scene_folds


def test_same_batch_and_scene_never_cross_folds(tmp_path: Path):
    config = ScannerConfig.load(Path("configs/box_system.yaml"))
    staged = stage_single_class_dataset(
        load_sources(config),
        (config.canonical_frame.width, config.canonical_frame.height),
        tmp_path,
        expected_images=config.dataset.expected_images,
        expected_boxes=config.dataset.expected_boxes,
    )

    first = build_scene_folds(staged, fold_count=5, seed=20260724)
    second = build_scene_folds(staged, fold_count=5, seed=20260724)
    owners = {}
    for fold in first:
        for scene in fold.validation_scenes:
            assert scene not in owners
            owners[scene] = fold.index

    assert [fold.manifest_hash for fold in first] == [fold.manifest_hash for fold in second]
    assert len(owners) == len(staged.scenes)
