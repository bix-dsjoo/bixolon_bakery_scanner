from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
import torch
import torch.nn.functional as functional
from PIL import Image

from bakery_scanner.classification import DinoInferenceError
from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.dinov3 import DinoV3Rechecker
from bakery_scanner.classification.preprocess import build_transform


_SKU_IDS = tuple(range(1, 21))
_CLASS_MAP = [{"id": sku_id, "name": f"SKU {sku_id}"} for sku_id in _SKU_IDS]


class FixedEncoder(torch.nn.Module):
    def __init__(self, embeddings: torch.Tensor) -> None:
        super().__init__()
        self.embeddings = embeddings
        self.saw_inference_mode = False

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape == (3, 3, 224, 224)
        self.saw_inference_mode = not torch.is_grad_enabled()
        return self.embeddings


class RecordingEncoder(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.register_buffer("weight", torch.zeros(1))
        self.received_device: torch.device | None = None

    def to(self, device: torch.device | str, *args, **kwargs) -> "RecordingEncoder":
        self.received_device = torch.device(device)
        return self

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return torch.zeros((batch.shape[0], 384), dtype=torch.float32)


class FailingEncoder(torch.nn.Module):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        raise self.error


def test_dinov3_averages_normalized_embeddings_then_scores_prototypes():
    embeddings = torch.zeros((3, 384), dtype=torch.float32)
    embeddings[0, 0] = 1
    embeddings[1, 1] = 1
    embeddings[2, 0:2] = 1
    prototypes = torch.eye(384, dtype=torch.float32)[:20]
    encoder = FixedEncoder(embeddings)
    runner = DinoV3Rechecker(
        encoder=encoder,
        prototypes=prototypes,
        sku_ids=_SKU_IDS,
        transform=build_transform(224),
        model_id="dinov3_vits16_15plus5_v1",
        device=torch.device("cpu"),
    )
    crops = tuple(Image.new("RGB", (32, 32), color) for color in ("red", "green", "blue"))

    result = runner.score(crops)

    assert result.model_id == "dinov3_vits16_15plus5_v1"
    assert result.score_kind == "similarity"
    expected_embedding = functional.normalize(
        functional.normalize(embeddings, dim=1).mean(dim=0),
        dim=0,
    )
    assert result.values == pytest.approx((prototypes @ expected_embedding).tolist())
    assert encoder.saw_inference_mode


@pytest.mark.parametrize("shape", [(19, 384), (20, 383)])
def test_dinov3_rejects_wrong_prototype_shape(shape):
    with pytest.raises(ValueError, match=r"\(20, 384\)"):
        DinoV3Rechecker(
            FixedEncoder(torch.zeros((3, 384))),
            torch.zeros(shape),
            _SKU_IDS,
            build_transform(224),
            "dinov3_vits16_15plus5_v1",
            torch.device("cpu"),
        )


def test_dinov3_rejects_non_unit_prototypes():
    prototypes = torch.eye(384, dtype=torch.float32)[:20]
    prototypes[0] *= 2
    with pytest.raises(ValueError, match="unit-length"):
        DinoV3Rechecker(
            FixedEncoder(torch.zeros((3, 384))),
            prototypes,
            _SKU_IDS,
            build_transform(224),
            "dinov3_vits16_15plus5_v1",
            torch.device("cpu"),
        )


def test_dinov3_rejects_non_finite_embeddings():
    embeddings = torch.ones((3, 384), dtype=torch.float32)
    embeddings[0, 0] = float("nan")
    runner = _runner(embeddings)
    with pytest.raises(ValueError, match="finite"):
        runner.score(tuple(Image.new("RGB", (32, 32)) for _ in range(3)))


def test_dinov3_classifies_out_of_memory_as_recoverable_inference_failure():
    runner = _runner_with_encoder(
        FailingEncoder(torch.OutOfMemoryError("backend allocation detail"))
    )

    with pytest.raises(DinoInferenceError) as captured:
        runner.score(tuple(Image.new("RGB", (32, 32)) for _ in range(3)))

    assert captured.value.code == "dino_out_of_memory"
    assert isinstance(captured.value.__cause__, torch.OutOfMemoryError)


def test_dinov3_preserves_unclassified_runtime_errors():
    runner = _runner_with_encoder(FailingEncoder(RuntimeError("bad operator")))

    with pytest.raises(RuntimeError, match="bad operator") as captured:
        runner.score(tuple(Image.new("RGB", (32, 32)) for _ in range(3)))

    assert not isinstance(captured.value, DinoInferenceError)


def test_dinov3_rejects_non_finite_prototypes():
    prototypes = torch.eye(384, dtype=torch.float32)[:20]
    prototypes[0, 0] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        DinoV3Rechecker(
            FixedEncoder(torch.zeros((3, 384))),
            prototypes,
            _SKU_IDS,
            build_transform(224),
            "dinov3_vits16_15plus5_v1",
            torch.device("cpu"),
        )


@pytest.mark.parametrize(
    ("section", "field", "message"),
    [
        ("dinov3", "weights_sha256", "weights SHA-256"),
        ("dinov3", "support_sha256", "support SHA-256"),
        ("repvit", "manifest_sha256", "RepViT manifest SHA-256"),
    ],
)
def test_load_rejects_hash_mismatch_before_model_construction(
    monkeypatch,
    section,
    field,
    message,
):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    bad_section = getattr(config, section).model_copy(update={field: "0" * 64})
    bad = config.model_copy(update={section: bad_section})
    monkeypatch.setattr(
        "bakery_scanner.classification.dinov3.vit_small",
        lambda *args, **kwargs: pytest.fail("model must not be constructed"),
    )
    with pytest.raises(ValueError, match=message):
        DinoV3Rechecker.load(bad, device=torch.device("cpu"))


def test_load_rejects_support_repvit_class_map_mismatch(monkeypatch, tmp_path):
    support = _valid_support()
    support["class_map"] = [*_CLASS_MAP[:-1], {"id": 20, "name": "different"}]
    config = _write_fake_artifacts(tmp_path, support)
    _fail_on_model_construction(monkeypatch)
    with pytest.raises(ValueError, match="RepViT class_map"):
        DinoV3Rechecker.load(config, device=torch.device("cpu"))


def test_load_rejects_support_checkpoint_hash_mismatch(monkeypatch, tmp_path):
    support = _valid_support()
    support["dino_checkpoint"]["sha256"] = "f" * 64
    config = _write_fake_artifacts(tmp_path, support)
    _fail_on_model_construction(monkeypatch)
    with pytest.raises(ValueError, match="checkpoint SHA-256"):
        DinoV3Rechecker.load(config, device=torch.device("cpu"))


def test_load_rejects_transform_metadata_mismatch(monkeypatch, tmp_path):
    support = _valid_support()
    support["transform"]["antialias"] = False
    config = _write_fake_artifacts(tmp_path, support)
    _fail_on_model_construction(monkeypatch)
    with pytest.raises(ValueError, match="transform metadata"):
        DinoV3Rechecker.load(config, device=torch.device("cpu"))


def test_load_rejects_unknown_support_schema(monkeypatch, tmp_path):
    support = _valid_support()
    support["schema_version"] = 2
    config = _write_fake_artifacts(tmp_path, support)
    _fail_on_model_construction(monkeypatch)
    with pytest.raises(ValueError, match="schema_version"):
        DinoV3Rechecker.load(config, device=torch.device("cpu"))


def test_load_canonicalizes_default_cuda_device(monkeypatch, tmp_path):
    config = _write_fake_artifacts(tmp_path, _valid_support())
    encoder = RecordingEncoder()
    monkeypatch.setattr(
        "bakery_scanner.classification.dinov3.vit_small",
        lambda **kwargs: encoder,
    )

    runner = DinoV3Rechecker.load(config)

    assert runner.device == torch.device("cuda:0")
    assert encoder.received_device == torch.device("cuda:0")


def test_real_dinov3_artifact_loads_and_scores_twenty_classes():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    if not config.dinov3.weights.is_file() or not config.dinov3.support.is_file():
        pytest.skip("configured DINOv3 model files are absent")
    runner = DinoV3Rechecker.load(config, device=torch.device("cpu"))
    image = Image.new("RGB", (64, 64), "goldenrod")

    result = runner.score((image, image, image))

    assert runner.prototypes.shape == (20, 384)
    assert result.sku_ids == _SKU_IDS
    assert len(result.values) == 20
    assert all(math.isfinite(value) for value in result.values)


def _runner(embeddings: torch.Tensor) -> DinoV3Rechecker:
    return _runner_with_encoder(FixedEncoder(embeddings))


def _runner_with_encoder(encoder: torch.nn.Module) -> DinoV3Rechecker:
    return DinoV3Rechecker(
        encoder,
        torch.eye(384, dtype=torch.float32)[:20],
        _SKU_IDS,
        build_transform(224),
        "dinov3_vits16_15plus5_v1",
        torch.device("cpu"),
    )


def _valid_support() -> dict[str, object]:
    return {
        "artifact_type": "dinov3_vits16_15plus5_global_support",
        "schema_version": 1,
        "class_map": [dict(row) for row in _CLASS_MAP],
        "prototypes": torch.eye(384, dtype=torch.float32)[:20],
        "dino_checkpoint": {
            "architecture": "vit_small_patch16_dinov3_storage4",
            "file": "weights.pt",
            "key_count": 1,
            "sha256": "",
            "storage_token_shape": [1, 4, 384],
        },
        "transform": {
            "antialias": True,
            "image_mode": "RGB",
            "input_size": [224, 224],
            "mean": [0.485, 0.456, 0.406],
            "resize_interpolation": "bilinear",
            "std": [0.229, 0.224, 0.225],
        },
    }


def _write_fake_artifacts(
    tmp_path: Path,
    support: dict[str, object],
) -> ClassifierConfig:
    weights_path = tmp_path / "weights.pt"
    support_path = tmp_path / "support.pt"
    manifest_path = tmp_path / "manifest.json"
    torch.save({"weight": torch.zeros(1)}, weights_path)
    weights_sha256 = _sha256(weights_path)
    support["dino_checkpoint"]["sha256"] = (
        support["dino_checkpoint"]["sha256"] or weights_sha256
    )
    torch.save(support, support_path)
    manifest_path.write_text(json.dumps({"class_map": _CLASS_MAP}), encoding="utf-8")

    base = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    return base.model_copy(
        update={
            "repvit": base.repvit.model_copy(
                update={
                    "manifest": manifest_path,
                    "manifest_sha256": _sha256(manifest_path),
                }
            ),
            "dinov3": base.dinov3.model_copy(
                update={
                    "weights": weights_path,
                    "weights_sha256": weights_sha256,
                    "support": support_path,
                    "support_sha256": _sha256(support_path),
                }
            ),
        }
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail_on_model_construction(monkeypatch) -> None:
    monkeypatch.setattr(
        "bakery_scanner.classification.dinov3.vit_small",
        lambda *args, **kwargs: pytest.fail("model must not be constructed"),
    )
