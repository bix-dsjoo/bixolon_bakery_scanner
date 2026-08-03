import hashlib
import json
from pathlib import Path

import pytest
import yaml

from bakery_scanner.classification.config import ClassifierConfig


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_gpu_rfdetr_config_uses_all_object_pytorch_batching(repo_root: Path):
    cpu = yaml.safe_load(
        (repo_root / "configs/cpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )
    gpu = yaml.safe_load(
        (repo_root / "configs/gpu_rfdetr_classifier_policy.yaml").read_text("utf-8")
    )

    assert cpu["runtime"] == {"device": "CPU", "precision": "FP32"}
    assert gpu["runtime"] == {
        "device": "CUDA:0",
        "precision": "FP32",
        "mode": "batch_pytorch",
        "repvit_microbatch_objects": "all",
        "dinov3_microbatch_objects": "all",
    }
    cpu["runtime"] = {
        "device": "CUDA:0",
        "precision": "FP32",
        "mode": "batch_pytorch",
        "repvit_microbatch_objects": "all",
        "dinov3_microbatch_objects": "all",
    }
    assert cpu == gpu
    assert gpu["calibration"]["fusion_policy"].endswith(
        "fusion_local_or_global_consensus_margin_v1.json"
    )
    calibration_path = (
        repo_root
        / "policies"
        / "classification"
        / "policy_v2_manifest_rebound_cpu_smoke.json"
    )
    calibration = json.loads(calibration_path.read_text("utf-8"))
    assert cpu["calibration"]["artifact"].endswith(calibration_path.name)
    assert calibration["repvit_manifest_sha256"] == cpu["repvit"][
        "manifest_sha256"
    ]
    assert cpu["calibration"]["artifact_sha256"] == (
        hashlib.sha256(calibration_path.read_bytes()).hexdigest()
    )
    assert gpu["calibration"]["artifact_sha256"] == (
        hashlib.sha256(calibration_path.read_bytes()).hexdigest()
    )
    ClassifierConfig.load(
        repo_root / "configs/gpu_rfdetr_classifier_policy.yaml"
    )
