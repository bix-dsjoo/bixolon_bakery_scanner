from pathlib import Path
import json

from bakery_scanner.config import ScannerConfig
from bakery_scanner.data.coco import load_sources, load_staged_dataset, stage_single_class_dataset
from bakery_scanner.contracts import SceneKey
from bakery_scanner.data.folds import FoldManifest, build_scene_folds, write_fold_manifests


def test_same_batch_and_scene_never_cross_folds(tmp_path: Path):
    config = ScannerConfig.load(Path("configs/e2e_current_source.yaml"))
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


def test_fold_manifests_are_written_atomically_with_hashes(tmp_path: Path):
    folds = (
        FoldManifest(
            index=0,
            training_scenes=(SceneKey("batch_a", 1),),
            validation_scenes=(SceneKey("batch_b", 2),),
            training_image_ids=(1, 2),
            validation_image_ids=(3,),
            source_hashes=("source-hash",),
            manifest_hash="manifest-hash",
        ),
    )

    output = tmp_path / "folds"
    write_fold_manifests(folds, output)

    paths = sorted(output.glob("fold-*/manifest.json"))
    assert len(paths) == 1
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert payload["index"] == 0
    assert payload["manifest_hash"] == folds[0].manifest_hash
    assert payload["validation_image_ids"] == list(folds[0].validation_image_ids)


def test_load_staged_dataset_reconstructs_fold_inputs(tmp_path: Path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "one.png").write_bytes(b"placeholder")
    (tmp_path / "staged_manifest.json").write_text(json.dumps([{
        "box_count": 2,
        "file_name": "one.png",
        "image_id": 1,
        "overlap_proxy": False,
        "scene": {"capture_batch": "batch", "scene_number": 1},
        "source_sha256": "hash",
    }]), encoding="utf-8")
    (tmp_path / "annotations.json").write_text(json.dumps({
        "images": [{"id": 1, "file_name": "one.png"}],
        "annotations": [{"id": 1, "image_id": 1}, {"id": 2, "image_id": 1}],
    }), encoding="utf-8")

    staged = load_staged_dataset(tmp_path)

    assert staged.image_count == 1
    assert staged.box_count == 2
    assert staged.images[0].scene == SceneKey("batch", 1)
