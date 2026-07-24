from dataclasses import dataclass

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import collect_oof_predictions, select_complementary_pair


@dataclass(frozen=True)
class FakeRun:
    experiment: DetectorExperiment
    validation_scenes: tuple[SceneKey, ...]
    training_scenes: tuple[SceneKey, ...]


def _proposal(image_id: int, source: str) -> BreadProposal:
    return BreadProposal(image_id, source, .5, Box(0, 0, 10, 10), 20, 20)


def test_oof_never_contains_training_scene(tmp_path):
    scene = SceneKey("g15", 1)
    run = FakeRun(DetectorExperiment("dfine_n_768", "dfine", 768, 20260724, 0), (scene,), (SceneKey("g15", 2),))
    artifact = collect_oof_predictions((run,), lambda _: ((scene, _proposal(1, "dfine_n_768")),), tmp_path)
    assert all(row.scene not in artifact.training_scenes_by_run[row.run_id] for row in artifact.predictions)
    assert artifact.path.is_file()


def test_oof_rejects_prediction_from_training_scene(tmp_path):
    train_scene = SceneKey("g15", 1)
    run = FakeRun(DetectorExperiment("dfine_n_768", "dfine", 768, 20260724, 0), (SceneKey("g15", 2),), (train_scene,))
    with pytest.raises(ValueError, match="training scene"):
        collect_oof_predictions((run,), lambda _: ((train_scene, _proposal(1, "dfine_n_768")),), tmp_path)


def test_oof_allows_an_empty_validation_prediction_artifact(tmp_path):
    scene = SceneKey("g15", 1)
    run = FakeRun(DetectorExperiment("dfine_n_768", "dfine", 768, 20260724, 0), (scene,), (SceneKey("g15", 2),))
    artifact = collect_oof_predictions((run,), lambda _: (), tmp_path)
    assert artifact.predictions == ()


def test_pair_selection_is_lexicographic_and_preserves_alternatives():
    reports = (
        {"name": "dfine_n_768", "misses": 1, "merge_errors": 0, "false_proposals": 2, "primary_misses": 1, "sem_exact": .9, "latency_ms": 4},
        {"name": "rtmdet_tiny_768", "misses": 0, "merge_errors": 1, "false_proposals": 0, "primary_misses": 0, "sem_exact": .8, "latency_ms": 1},
        {"name": "rtmdet_tiny_640", "misses": 2, "merge_errors": 0, "false_proposals": 0, "primary_misses": 0, "sem_exact": .95, "latency_ms": 1},
    )
    selection = select_complementary_pair(reports)
    assert selection.primary == "dfine_n_768"
    assert selection.secondary == "rtmdet_tiny_768"
    assert len(selection.alternatives) == 2
