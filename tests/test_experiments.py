import pytest

from bakery_scanner.config import ScannerConfig
from bakery_scanner.detectors.experiments import (
    ExperimentIntegrationUnavailable,
    experiment_matrix,
    write_experiment_receipt,
)


def test_matrix_has_four_variants_three_seeds_five_folds(config):
    rows = experiment_matrix(config)

    assert len(rows) == 60
    assert {(r.backend, r.input_size) for r in rows} == {
        ("dfine", 640), ("dfine", 768),
        ("rtmdet", 640), ("rtmdet", 768),
    }
    assert len({row.run_id for row in rows}) == 60


@pytest.fixture
def config() -> ScannerConfig:
    return ScannerConfig.load(__import__("pathlib").Path("configs/box_system.yaml"))


def test_receipt_is_deterministic_and_records_required_hashes(config, tmp_path):
    experiment = experiment_matrix(config)[0]
    receipt = write_experiment_receipt(
        experiment,
        config_bytes=b"seed: 20260724\n",
        fold_hash="a" * 64,
        upstream_commit="b" * 40,
        command=("python", "train.py"),
        environment={"python": "3.11"},
        checkpoint_hash="c" * 64,
        prediction_hash="d" * 64,
        started_at="2026-07-24T00:00:00+00:00",
        ended_at="2026-07-24T00:01:00+00:00",
        status="completed",
        output=tmp_path / "receipt.json",
    )

    assert receipt.config_hash == "c24043dc75b93d90476186f96d158d329d25840bff84f7cbcac8a324d79cc6ea"
    assert receipt.config_text == "seed: 20260724\n"
    assert (tmp_path / "receipt.json").read_bytes() == receipt.to_json_bytes()


def test_training_dependency_failure_is_actionable(config):
    experiment = experiment_matrix(config)[0]

    with pytest.raises(ExperimentIntegrationUnavailable, match="D-FINE-N"):
        experiment.require_training_integration()
