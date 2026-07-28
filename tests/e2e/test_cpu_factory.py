from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

import bakery_scanner.e2e.cpu_factory as cpu_factory
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.classification.policy import PolicyCalibration
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.e2e.runtime import MobileOnlyE2EPipeline
from bakery_scanner.verifier.assurance import AssuranceBackend
from bakery_scanner.e2e.cpu_factory import (
    CpuSmokeAssets,
    LegacyFourStateAssuranceRunner,
    preflight_cpu_assets,
)


class _FourLogitModel(torch.nn.Module):
    def __init__(self, logits: tuple[float, float, float, float]) -> None:
        super().__init__()
        self.logits = torch.tensor(logits, dtype=torch.float32)

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.logits.unsqueeze(0).expand(len(batch), -1)


def _candidate() -> BreadProposal:
    return BreadProposal(1, "dfine_n_640", 0.9, Box(10, 10, 20, 20), 64, 64)


def test_legacy_four_state_adapter_maps_logits_to_exactly_one_quality_and_zero_delta():
    """The legacy checkpoint contributes only its four trained state logits."""
    runner = LegacyFourStateAssuranceRunner(_FourLogitModel((0.0, 2.0, 1.0, 0.0)), device="cpu")

    prediction, = runner.predict((_candidate(),), Image.new("RGB", (64, 64)))

    assert prediction.backend is AssuranceBackend.MOBILENETV4
    assert prediction.quality == pytest.approx(prediction.state_probabilities[1])
    assert prediction.box_delta == (0.0, 0.0, 0.0, 0.0)


def test_legacy_four_state_adapter_partial_candidate_is_unknown_without_classifier_call():
    """Legacy state-only evidence must not bypass the ConvNeXt recheck gate."""
    proposal = _candidate()

    class Detector:
        def predict(self, image_id: int, image: object):
            return (proposal,)

    class Classifier:
        calls = 0

        def infer(self, image: object, box: Box):
            self.calls += 1
            raise AssertionError("recheck-required legacy candidate must remain unknown")

    classifier = Classifier()
    pipeline = MobileOnlyE2EPipeline(
        Detector(),
        LegacyFourStateAssuranceRunner(_FourLogitModel((0.0, 0.0, 2.0, 0.0)), device="cpu"),
        classifier,
    )

    output = pipeline.infer(1, Image.new("RGB", (64, 64)))

    assert classifier.calls == 0
    assert output.final_objects[0].sku_id is None
    assert output.final_objects[0].decision_path == "assurance_unknown"


def test_preflight_names_package_relative_missing_repvit(tmp_path: Path):
    """Removing the primary classifier checkpoint must prevent worker startup."""
    assets = CpuSmokeAssets.from_root(tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="models/repvit_m1_15plus5_v1/repvit_m1_15plus5_v1.pt",
    ):
        preflight_cpu_assets(assets)


def test_preflight_rejects_missing_dfine_worker_dependency_before_worker_starts(monkeypatch):
    """D-FINE worker imports are checked before the JSONL worker can be created."""
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(
        cpu_factory,
        "subprocess",
        SimpleNamespace(run=lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="ModuleNotFoundError: No module named 'torchvision'")),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="D-FINE worker imports"):
        preflight_cpu_assets(CpuSmokeAssets.from_root(root))


def test_rebound_cpu_smoke_policy_changes_only_manifest_metadata(monkeypatch):
    """The rebind preserves threshold semantics while fixing only stale metadata."""
    root = Path(__file__).resolve().parents[2]
    original_path = root / "artifacts" / "e2e_current_source" / "classification" / "policy_fail_closed.json"
    rebound_path = root / "artifacts" / "e2e_current_source" / "classification" / "policy_v2_manifest_rebound_cpu_smoke.json"
    original = json.loads(original_path.read_text(encoding="utf-8"))
    rebound = json.loads(rebound_path.read_text(encoding="utf-8"))

    assert rebound["calibration_id"] == "policy_v2_manifest_rebound_cpu_smoke"
    assert rebound["repvit_manifest_sha256"] == "cb0c8594c723461e11b7e8db8fffffe2d7249b0d5f3d07f3e5503ae040798d18"
    assert {
        key: value for key, value in rebound.items()
        if key not in {"calibration_id", "repvit_manifest_sha256"}
    } == {
        key: value for key, value in original.items()
        if key not in {"calibration_id", "repvit_manifest_sha256"}
    }

    with pytest.raises(ValueError, match="RepViT manifest SHA-256 mismatch"):
        ClassifierPipeline.load(root / "configs" / "classifier_policy.yaml")

    monkeypatch.setattr(cpu_factory, "_validate_dfine_worker_imports", lambda assets: None)
    provenance = preflight_cpu_assets(CpuSmokeAssets.from_root(root))

    assert provenance["calibration_id"] == rebound["calibration_id"]
    canonical = PolicyCalibration.from_json_bytes(rebound_path.read_bytes()).to_json_bytes()
    assert provenance["calibration_sha256"] == hashlib.sha256(canonical).hexdigest()
