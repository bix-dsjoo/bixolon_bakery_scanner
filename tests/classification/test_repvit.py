from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch
from PIL import Image

from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.classification.repvit import RepVitM1Runner


class FixedLogitModel(torch.nn.Module):
    def __init__(self, logits: torch.Tensor) -> None:
        super().__init__()
        self.logits = logits
        self.saw_inference_mode = False

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape == (3, 3, 224, 224)
        self.saw_inference_mode = not torch.is_grad_enabled()
        return self.logits


def test_repvit_averages_three_softmax_vectors():
    logits = torch.stack([
        torch.arange(20, dtype=torch.float32),
        torch.arange(19, -1, -1, dtype=torch.float32),
        torch.zeros(20, dtype=torch.float32),
    ])
    model = FixedLogitModel(logits)
    runner = RepVitM1Runner(
        model=model,
        sku_ids=tuple(range(1, 21)),
        transform=build_transform(224),
        model_id="repvit_m1_15plus5_v1",
        device=torch.device("cpu"),
    )
    crops = tuple(Image.new("RGB", (32, 32), color) for color in ("red", "green", "blue"))
    result = runner.score(crops)
    assert result.model_id == "repvit_m1_15plus5_v1"
    assert result.score_kind == "probability"
    assert sum(result.values) == pytest.approx(1.0)
    expected = logits.softmax(dim=1).mean(dim=0).tolist()
    assert result.values == pytest.approx(expected)
    assert model.saw_inference_mode


def test_score_rejects_wrong_crop_count():
    runner = RepVitM1Runner(FixedLogitModel(torch.zeros(3, 20)), tuple(range(1, 21)), build_transform(224), "repvit_m1_15plus5_v1", torch.device("cpu"))
    with pytest.raises(ValueError, match="exactly three"):
        runner.score((Image.new("RGB", (32, 32)),))


def test_score_rejects_non_twenty_logit_output():
    runner = RepVitM1Runner(FixedLogitModel(torch.zeros(3, 19)), tuple(range(1, 21)), build_transform(224), "repvit_m1_15plus5_v1", torch.device("cpu"))
    with pytest.raises(ValueError, match="shape"):
        runner.score(tuple(Image.new("RGB", (32, 32)) for _ in range(3)))


def test_score_rejects_non_finite_logits():
    logits = torch.zeros(3, 20)
    logits[0, 0] = float("nan")
    runner = RepVitM1Runner(FixedLogitModel(logits), tuple(range(1, 21)), build_transform(224), "repvit_m1_15plus5_v1", torch.device("cpu"))
    with pytest.raises(ValueError, match="finite"):
        runner.score(tuple(Image.new("RGB", (32, 32)) for _ in range(3)))


def test_load_rejects_hash_mismatch_before_model_construction(monkeypatch):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    bad = config.model_copy(update={"repvit": config.repvit.model_copy(update={"checkpoint_sha256": "0" * 64})})
    monkeypatch.setattr("bakery_scanner.classification.repvit.timm.create_model", lambda *args, **kwargs: pytest.fail("model must not be constructed"))
    with pytest.raises(ValueError, match="SHA-256"):
        RepVitM1Runner.load(bad, device=torch.device("cpu"))


def test_load_rejects_checkpoint_class_index_order(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    checkpoint = tmp_path / "checkpoint.pt"
    manifest = tmp_path / "manifest.json"
    checkpoint.write_bytes(b"checkpoint")
    manifest.write_text(json.dumps({"class_map": [{"id": sku} for sku in range(1, 21)]}), encoding="utf-8")
    repvit = config.repvit.model_copy(update={
        "checkpoint": checkpoint,
        "checkpoint_sha256": __import__("hashlib").sha256(checkpoint.read_bytes()).hexdigest(),
        "manifest": manifest,
        "manifest_sha256": __import__("hashlib").sha256(manifest.read_bytes()).hexdigest(),
    })
    bad = config.model_copy(update={"repvit": repvit})
    monkeypatch.setattr("bakery_scanner.classification.repvit.torch.load", lambda *args, **kwargs: {"class_index": {1: 1}})
    monkeypatch.setattr("bakery_scanner.classification.repvit.timm.create_model", lambda *args, **kwargs: pytest.fail("model must not be constructed"))
    with pytest.raises(ValueError, match="class_index"):
        RepVitM1Runner.load(bad, device=torch.device("cpu"))


def test_load_rejects_manifest_checkpoint_class_map_mismatch(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    checkpoint = tmp_path / "checkpoint.pt"
    manifest = tmp_path / "manifest.json"
    checkpoint.write_bytes(b"checkpoint")
    manifest.write_text(json.dumps({"class_map": [{"id": sku} for sku in range(1, 20)] + [{"id": 99}]}), encoding="utf-8")
    repvit = config.repvit.model_copy(update={
        "checkpoint": checkpoint,
        "checkpoint_sha256": __import__("hashlib").sha256(checkpoint.read_bytes()).hexdigest(),
        "manifest": manifest,
        "manifest_sha256": __import__("hashlib").sha256(manifest.read_bytes()).hexdigest(),
    })
    bad = config.model_copy(update={"repvit": repvit})
    monkeypatch.setattr("bakery_scanner.classification.repvit.torch.load", lambda *args, **kwargs: {"class_index": {sku: sku - 1 for sku in range(1, 21)}})
    monkeypatch.setattr("bakery_scanner.classification.repvit.timm.create_model", lambda *args, **kwargs: pytest.fail("model must not be constructed"))
    with pytest.raises(ValueError, match="class_map"):
        RepVitM1Runner.load(bad, device=torch.device("cpu"))


@pytest.mark.integration
def test_real_repvit_artifact_loads_twenty_classes():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    if not config.repvit.checkpoint.is_file():
        pytest.skip("configured RepViT model file is absent")
    runner = RepVitM1Runner.load(config, device=torch.device("cpu"))
    assert runner.sku_ids == tuple(range(1, 21))
