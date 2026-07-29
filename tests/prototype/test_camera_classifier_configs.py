from pathlib import Path

import pytest
import yaml

from bakery_scanner.classification.config import ClassifierConfig


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_gpu_and_cpu_rfdetr_configs_differ_only_by_device(repo_root: Path):
    cpu = yaml.safe_load(
        (repo_root / "configs/cpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )
    gpu = yaml.safe_load(
        (repo_root / "configs/gpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )

    assert cpu["runtime"] == {"device": "CPU", "precision": "FP32"}
    assert gpu["runtime"] == {"device": "CUDA:0", "precision": "FP32"}
    cpu["runtime"] = gpu["runtime"]
    assert cpu == gpu
    assert gpu["calibration"]["fusion_policy"].endswith(
        "fusion_local_or_global_consensus_margin_v1_reference_rebound.json"
    )
    ClassifierConfig.load(
        repo_root / "configs/gpu_rfdetr_classifier_policy.yaml"
    )
