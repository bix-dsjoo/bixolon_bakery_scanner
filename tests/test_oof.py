import hashlib
import json
from dataclasses import dataclass

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import OofArtifact, _load_staged_images, collect_oof_predictions, load_complete_oof_artifact, select_complementary_pair

_HASH = "a" * 64


@dataclass(frozen=True)
class FakeRun:
    experiment: DetectorExperiment
    validation_scenes: tuple[SceneKey, ...]
    training_scenes: tuple[SceneKey, ...]
    receipt_hash: str = _HASH
    prediction_artifact_hash: str = _HASH


def _proposal(image_id: int, source: str, x: int = 0) -> BreadProposal:
    return BreadProposal(image_id, source, .5, Box(x, 0, 10, 10), 30, 20)


def _write_json(path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_required_staged_dataset(staged_root, *, scene_overrides: dict[int, tuple[str, int]] | None = None) -> None:
    """Create the fixed 299-image/1,410-box staging contract for disk-loader tests."""
    scene_overrides = scene_overrides or {}
    images = [{"height": 20, "id": image_id, "width": 30} for image_id in range(1, 300)]
    annotations = [
        {"bbox": [index, 0, 1, 1], "category_id": 1, "id": annotation_id, "image_id": image_id}
        for image_id in range(1, 300)
        for index, annotation_id in enumerate(range((image_id - 1) * 5 + 1, (image_id - 1) * 5 + 1 + (5 if image_id <= 214 else 4)))
    ]
    _write_json(staged_root / "annotations.json", {"annotations": annotations, "categories": [{"id": 1, "name": "bread"}], "images": images})
    _write_json(
        staged_root / "staged_manifest.json",
        [
            {
                "box_count": 5 if image_id <= 214 else 4,
                "file_name": f"{image_id}.png",
                "image_id": image_id,
                "overlap_proxy": False,
                "scene": {"capture_batch": scene_overrides.get(image_id, ("g15", image_id))[0], "scene_number": scene_overrides.get(image_id, ("g15", image_id))[1]},
                "source_sha256": _HASH,
            }
            for image_id in range(1, 300)
        ],
    )


def _write_complete_disk_run(tmp_path, *, scene_overrides: dict[int, tuple[str, int]] | None = None) -> tuple[DetectorExperiment, object, object, object]:
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    detector_root, fold_root, staged_root = tmp_path / "detectors", tmp_path / "folds", tmp_path / "staged"
    run_root, manifest = detector_root / experiment.run_id, fold_root / "fold-0" / "manifest.json"
    prediction, processed = run_root / "validation_predictions.json", run_root / "processed_validation_image_ids.json"
    scenes = scene_overrides or {}
    _write_required_staged_dataset(staged_root, scene_overrides=scenes)
    _write_json(prediction, [])
    _write_json(processed, [1])
    _write_json(
        manifest,
        {
            "training_image_ids": [3],
            "training_scenes": [{"capture_batch": scenes.get(3, ("g15", 3))[0], "scene_number": scenes.get(3, ("g15", 3))[1]}],
            "validation_image_ids": [1],
            "validation_scenes": [{"capture_batch": scenes.get(1, ("g15", 1))[0], "scene_number": scenes.get(1, ("g15", 1))[1]}],
        },
    )
    _write_json(run_root / "receipt.json", {"fold": 0, "fold_manifest_sha256": _sha256(manifest), "prediction_sha256": _sha256(prediction), "processed_images_sha256": _sha256(processed), "run_id": experiment.run_id, "seed": experiment.seed, "status": "completed", "variant": experiment.name})
    return experiment, detector_root, fold_root, staged_root


def test_load_complete_oof_artifact_rejects_split_capture_scene(tmp_path):
    """One capture scene cannot be partly held out while a sibling image is omitted."""
    experiment, detector_root, fold_root, staged_root = _write_complete_disk_run(
        tmp_path,
        scene_overrides={1: ("g15", 1), 2: ("g15", 1)},
    )

    with pytest.raises(ValueError, match="whole capture scene"):
        load_complete_oof_artifact(detector_root=detector_root, fold_root=fold_root, staged_root=staged_root, expected_experiments=(experiment,))


def test_load_complete_oof_artifact_rejects_non_frozen_staged_counts(tmp_path):
    """The loader must not treat a partial or annotation-empty staging tree as OOF evidence."""
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    detector_root, fold_root, staged_root = tmp_path / "detectors", tmp_path / "folds", tmp_path / "staged"
    run_root, manifest = detector_root / experiment.run_id, fold_root / "fold-0" / "manifest.json"
    prediction, processed = run_root / "validation_predictions.json", run_root / "processed_validation_image_ids.json"
    _write_json(staged_root / "annotations.json", {"annotations": [], "categories": [], "images": [{"height": 20, "id": 1, "width": 30}, {"height": 20, "id": 2, "width": 30}]})
    _write_json(staged_root / "staged_manifest.json", [{"box_count": 0, "file_name": "one.png", "image_id": 1, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 1}, "source_sha256": _HASH}, {"box_count": 0, "file_name": "two.png", "image_id": 2, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 2}, "source_sha256": _HASH}])
    _write_json(prediction, [])
    _write_json(processed, [1])
    _write_json(manifest, {"training_image_ids": [2], "training_scenes": [{"capture_batch": "g15", "scene_number": 2}], "validation_image_ids": [1], "validation_scenes": [{"capture_batch": "g15", "scene_number": 1}]})
    _write_json(run_root / "receipt.json", {"fold": 0, "fold_manifest_sha256": _sha256(manifest), "prediction_sha256": _sha256(prediction), "processed_images_sha256": _sha256(processed), "run_id": experiment.run_id, "seed": experiment.seed, "status": "completed", "variant": experiment.name})

    with pytest.raises(ValueError, match="299 images and 1410 annotations"):
        load_complete_oof_artifact(detector_root=detector_root, fold_root=fold_root, staged_root=staged_root, expected_experiments=(experiment,))


def test_staged_loader_accepts_explicit_current_source_box_count(tmp_path):
    staged_root = tmp_path / "staged"
    _write_required_staged_dataset(staged_root)
    annotations = json.loads((staged_root / "annotations.json").read_text(encoding="utf-8"))
    annotations["annotations"].pop()
    (staged_root / "annotations.json").write_text(json.dumps(annotations), encoding="utf-8")

    sizes, scenes = _load_staged_images(staged_root, expected_images=299, expected_boxes=1409)

    assert len(sizes) == len(scenes) == 299


def _matrix_runs() -> tuple[FakeRun, ...]:
    variants = (("dfine_n_640", "dfine", 640), ("dfine_n_768", "dfine", 768), ("rtmdet_tiny_640", "rtmdet", 640), ("rtmdet_tiny_768", "rtmdet", 768))
    return tuple(
        FakeRun(DetectorExperiment(name, backend, size, seed, fold), (SceneKey("g15", fold + 1),), (SceneKey("g15", 99),))
        for name, backend, size in variants for seed in (20260724, 20260725, 20260726) for fold in range(5)
    )


def test_oof_requires_complete_expected_matrix_and_records_hashes(tmp_path):
    runs = _matrix_runs()
    artifact = collect_oof_predictions(
        runs, lambda run: ((run.validation_scenes[0], _proposal(run.experiment.fold + 1, run.experiment.name)),), tmp_path,
        expected_experiments=tuple(run.experiment for run in runs),
    )
    assert len(artifact.run_receipt_hashes) == 60
    assert artifact.path.is_file()


def test_load_complete_oof_artifact_rehydrates_prediction_with_held_out_scene(tmp_path):
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    detector_root = tmp_path / "detectors"
    run_root = detector_root / experiment.run_id
    prediction = run_root / "validation_predictions.json"
    processed = run_root / "processed_validation_image_ids.json"
    fold_root = tmp_path / "folds"
    manifest = fold_root / "fold-0" / "manifest.json"
    staged_root = tmp_path / "staged"
    config_root = tmp_path / "generated-configs"
    config = config_root / f"{experiment.run_id}.yml"
    _write_json(prediction, [{"bbox": [1, 2, 3, 4], "image_id": 1, "score": .9, "source": experiment.name}])
    _write_json(processed, [1])
    _write_json(manifest, {"training_image_ids": [2], "training_scenes": [{"capture_batch": "g15", "scene_number": 2}], "validation_image_ids": [1], "validation_scenes": [{"capture_batch": "g15", "scene_number": 1}]})
    _write_required_staged_dataset(staged_root)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("model: dfine\n", encoding="utf-8")
    _write_json(run_root / "receipt.json", {"config_sha256": _sha256(config), "fold": 0, "fold_manifest_sha256": _sha256(manifest), "prediction_sha256": _sha256(prediction), "processed_images_sha256": _sha256(processed), "run_id": experiment.run_id, "seed": experiment.seed, "status": "completed", "variant": experiment.name})

    artifact = load_complete_oof_artifact(detector_root=detector_root, fold_root=fold_root, staged_root=staged_root, config_root=config_root, expected_experiments=(experiment,))

    assert isinstance(artifact, OofArtifact)
    assert len(artifact.predictions) == 1
    assert artifact.predictions[0].scene == SceneKey("g15", 1)


def test_load_complete_oof_artifact_rejects_retained_canonical_prediction_duplicates(tmp_path):
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    detector_root = tmp_path / "detectors"
    run_root = detector_root / experiment.run_id
    prediction = run_root / "validation_predictions.json"
    processed = run_root / "processed_validation_image_ids.json"
    fold_root = tmp_path / "folds"
    manifest = fold_root / "fold-0" / "manifest.json"
    staged_root = tmp_path / "staged"
    duplicate = {"bbox": [1, 2, 3, 4], "image_id": 1, "score": .9, "source": experiment.name}
    _write_json(prediction, [duplicate, duplicate])
    _write_json(processed, [1])
    _write_json(manifest, {"training_image_ids": [2], "training_scenes": [{"capture_batch": "g15", "scene_number": 2}], "validation_image_ids": [1], "validation_scenes": [{"capture_batch": "g15", "scene_number": 1}]})
    _write_required_staged_dataset(staged_root)
    _write_json(run_root / "receipt.json", {"fold": 0, "fold_manifest_sha256": _sha256(manifest), "prediction_sha256": _sha256(prediction), "processed_images_sha256": _sha256(processed), "run_id": experiment.run_id, "seed": experiment.seed, "status": "completed", "variant": experiment.name})

    with pytest.raises(ValueError, match="duplicate canonical prediction coordinates"):
        load_complete_oof_artifact(detector_root=detector_root, fold_root=fold_root, staged_root=staged_root, expected_experiments=(experiment,))


def test_load_complete_oof_artifact_rejects_duplicate_fold_coverage(tmp_path):
    detector_root, fold_root, staged_root = tmp_path / "detectors", tmp_path / "folds", tmp_path / "staged"
    experiments = tuple(DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, fold) for fold in range(5))
    _write_required_staged_dataset(staged_root)
    for experiment in experiments:
        run_root, manifest = detector_root / experiment.run_id, fold_root / f"fold-{experiment.fold}" / "manifest.json"
        prediction, processed = run_root / "validation_predictions.json", run_root / "processed_validation_image_ids.json"
        _write_json(prediction, [])
        _write_json(processed, [1])
        _write_json(manifest, {"training_image_ids": [2, 3, 4, 5], "training_scenes": [{"capture_batch": "g15", "scene_number": image_id} for image_id in range(2, 6)], "validation_image_ids": [1], "validation_scenes": [{"capture_batch": "g15", "scene_number": 1}]})
        _write_json(run_root / "receipt.json", {"fold": experiment.fold, "fold_manifest_sha256": _sha256(manifest), "prediction_sha256": _sha256(prediction), "processed_images_sha256": _sha256(processed), "run_id": experiment.run_id, "seed": experiment.seed, "status": "completed", "variant": experiment.name})

    with pytest.raises(ValueError, match="cover each staged image exactly once"):
        load_complete_oof_artifact(detector_root=detector_root, fold_root=fold_root, staged_root=staged_root, expected_experiments=experiments)


def test_oof_rejects_missing_or_mismatched_expected_run(tmp_path):
    runs = _matrix_runs()
    with pytest.raises(ValueError, match="expected detector matrix"):
        collect_oof_predictions(runs[:-1], lambda _: (), tmp_path, expected_experiments=tuple(run.experiment for run in runs))
    mismatched = FakeRun(DetectorExperiment("dfine_n_768", "dfine", 768, 20260724, 0), (SceneKey("g15", 1),), (SceneKey("g15", 2),))
    with pytest.raises(ValueError, match="expected detector matrix"):
        collect_oof_predictions((mismatched,), lambda _: (), tmp_path, expected_experiments=(runs[0].experiment,))


def test_oof_rejects_prediction_from_training_scene(tmp_path):
    run = _matrix_runs()[0]
    with pytest.raises(ValueError, match="training scene"):
        collect_oof_predictions((run,), lambda _: ((run.training_scenes[0], _proposal(1, run.experiment.name)),), tmp_path, expected_experiments=(run.experiment,))


def test_pair_selection_uses_union_predictions_calibrated_semr_and_hashes(tmp_path):
    runs = tuple(run for run in _matrix_runs() if run.experiment.seed == 20260724 and run.experiment.fold == 0)
    artifact = collect_oof_predictions(
        runs,
        lambda run: ((run.validation_scenes[0], _proposal(1, run.experiment.name)),) if run.experiment.name == "dfine_n_768" else (),
        tmp_path, expected_experiments=tuple(run.experiment for run in runs),
    )
    selection = select_complementary_pair(
        artifact,
        ground_truth={1: (Box(0, 0, 10, 10),)},
        scenarios={1: frozenset()},
        score_thresholds={name: .001 for name in ("dfine_n_640", "dfine_n_768", "rtmdet_tiny_640", "rtmdet_tiny_768")},
        latency_ms={name: 1.0 for name in ("dfine_n_640", "dfine_n_768", "rtmdet_tiny_640", "rtmdet_tiny_768")},
    )
    assert selection.primary.startswith("dfine")
    assert selection.evidence[0].sem_exact == 1.0
    assert selection.evidence[0].seed_count == 1


def test_pair_selection_averages_seeds_instead_of_pooling_duplicate_boxes(tmp_path):
    runs = tuple(run for run in _matrix_runs() if run.experiment.seed in {20260724, 20260725} and run.experiment.fold == 0)
    artifact = collect_oof_predictions(
        runs,
        lambda run: ((run.validation_scenes[0], _proposal(1, run.experiment.name)),) if run.experiment.name == "dfine_n_768" else (),
        tmp_path, expected_experiments=tuple(run.experiment for run in runs),
    )
    names = ("dfine_n_640", "dfine_n_768", "rtmdet_tiny_640", "rtmdet_tiny_768")
    selection = select_complementary_pair(artifact, ground_truth={1: (Box(0, 0, 10, 10),)}, scenarios={1: frozenset()}, score_thresholds={name: .001 for name in names}, latency_ms={name: 1.0 for name in names})
    assert selection.evidence[0].seed_count == 2
    assert selection.evidence[0].sem_exact == 1.0
    assert selection.evidence[0].receipt_hashes
