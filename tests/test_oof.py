from dataclasses import dataclass

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import collect_oof_predictions, select_complementary_pair

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
    assert selection.evidence[0].receipt_hashes
