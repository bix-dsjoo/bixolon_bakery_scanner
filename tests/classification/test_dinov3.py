from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
import torch
import torch.nn.functional as functional
from PIL import Image
from torchvision import transforms

from bakery_scanner.contracts import Box
from bakery_scanner.classification import DinoInferenceError
from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.contracts import ModelScoreVector
from bakery_scanner.classification.dinov3 import (
    DinoGlobalLocalEvidence,
    DinoV3Rechecker,
    _product_patch_mask,
    candidate_union,
)
from bakery_scanner.classification.local_bank import LocalPatchBank
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.classification.preprocess import ClassifierPreprocessDescriptor


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


class FeatureEncoder(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def forward_features(self, batch: torch.Tensor):
        self.calls += 1
        cls = torch.nn.functional.normalize(torch.ones((3, 384)), dim=1)
        patches = torch.nn.functional.normalize(torch.ones((3, 196, 384)), dim=2)
        return {"x_norm_clstoken": cls, "x_norm_patchtokens": patches}


class BatchFeatureEncoder(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.batch_sizes: list[int] = []

    def forward_features(self, batch: torch.Tensor):
        self.batch_sizes.append(batch.shape[0])
        return {
            "x_norm_clstoken": torch.nn.functional.normalize(
                torch.ones((batch.shape[0], 384)), dim=1
            ),
            "x_norm_patchtokens": torch.nn.functional.normalize(
                torch.ones((batch.shape[0], 196, 384)), dim=2
            ),
        }


def test_static_context_runner_executes_one_padded_seven_object_batch():
    encoder = BatchFeatureEncoder()
    prototypes = functional.normalize(torch.eye(384)[:20] + 1.0, dim=1)
    runner = DinoV3Rechecker(
        encoder, prototypes, _SKU_IDS, transforms.ToTensor(),
        "dinov3_vits16_15plus5_v1", torch.device("cpu"),
    )
    rows = tuple(Image.new("RGB", (224, 224), "white") for _ in range(7))
    boxes = tuple(Box(0, 0, 224, 224) for _ in range(7))
    repvit = ModelScoreVector("repvit_m1_15plus5_v1", _SKU_IDS, tuple([1.0] + [0.0] * 19), "probability")
    bank = LocalPatchBank({sku_id: functional.normalize(torch.ones((3, 384)), dim=1) for sku_id in _SKU_IDS}, "a" * 64)

    evidence = runner.score_context_chunk_global_and_local_evidence(
        rows, boxes, bank, repvit_scores=(repvit,) * 7,
        valid_mask=(True,) + (False,) * 6,
    )

    assert len(evidence) == 1
    assert encoder.batch_sizes == [7]


def test_candidate_union_keeps_dino_top_five_then_appends_missing_repvit_top_two():
    dino = ModelScoreVector(
        "dinov3_vits16_15plus5_v1",
        _SKU_IDS,
        (0.99, 0.98, 0.97, 0.96, 0.95, 0.94) + (0.0,) * 14,
        "similarity",
    )
    repvit = ModelScoreVector(
        "repvit_m1_15plus5_v1",
        _SKU_IDS,
        (0.01,) * 5 + (0.80, 0.02, 0.70) + (0.01,) * 12,
        "probability",
    )

    assert candidate_union(dino, repvit) == (1, 2, 3, 4, 5, 6, 8)


def test_local_patch_mask_erodes_the_verified_box_when_no_foreground_mask_exists():
    mask = _product_patch_mask(
        Box(0, 0, 224, 224),
        (224, 224),
        196,
        torch.device("cpu"),
    )

    assert int(mask.sum()) == 144


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


def test_dinov3_local_scores_only_global_top_five_candidates(tmp_path):
    patches = {sku_id: torch.nn.functional.normalize(torch.ones((1, 384)) * sku_id, dim=1) for sku_id in _SKU_IDS}
    bank_path = tmp_path / "local.pt"
    torch.save({"artifact_type": "dinov3_vits16_15plus5_local_patch_bank", "schema_version": 1, "dino_weights_sha256": "a" * 64, "preprocess_sha256": "b" * 64, "canonical_frame_version": "exif_visual_rgb_v1", "patches": patches}, bank_path)
    bank = LocalPatchBank.load(bank_path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)
    encoder = FeatureEncoder()
    runner = DinoV3Rechecker(encoder, torch.eye(384, dtype=torch.float32)[:20], _SKU_IDS, build_transform(224), "dinov3_vits16_15plus5_v1", torch.device("cpu"))

    global_scores, local_scores = runner.score_global_and_local(
        tuple(Image.new("RGB", (32, 32)) for _ in range(3)),
        (Box(0, 0, 32, 32),) * 3,
        bank,
    )

    assert encoder.calls == 1
    assert len(local_scores) == 5
    assert tuple(local_scores) == tuple(sorted(range(1, 6)))
    assert global_scores.score_kind == "similarity"


def test_dinov3_local_evidence_reports_selected_product_patch_count_and_ratio(tmp_path):
    patches = {sku_id: torch.nn.functional.normalize(torch.ones((1, 384)) * sku_id, dim=1) for sku_id in _SKU_IDS}
    bank_path = tmp_path / "local.pt"
    torch.save({"artifact_type": "dinov3_vits16_15plus5_local_patch_bank", "schema_version": 1, "dino_weights_sha256": "a" * 64, "preprocess_sha256": "b" * 64, "canonical_frame_version": "exif_visual_rgb_v1", "patches": patches}, bank_path)
    bank = LocalPatchBank.load(bank_path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)
    runner = DinoV3Rechecker(FeatureEncoder(), torch.eye(384, dtype=torch.float32)[:20], _SKU_IDS, build_transform(224), "dinov3_vits16_15plus5_v1", torch.device("cpu"))

    _, _, count, ratio = runner.score_global_and_local_evidence(
        tuple(Image.new("RGB", (32, 32)) for _ in range(3)),
        (Box(0, 0, 32, 32),) * 3,
        bank,
    )

    assert count == 432
    assert ratio == pytest.approx(432 / 588)


def test_dinov3_local_scores_the_union_of_global_and_repvit_candidates(tmp_path):
    patches = {sku_id: torch.nn.functional.normalize(torch.ones((1, 384)) * sku_id, dim=1) for sku_id in _SKU_IDS}
    bank_path = tmp_path / "local.pt"
    torch.save({"artifact_type": "dinov3_vits16_15plus5_local_patch_bank", "schema_version": 1, "dino_weights_sha256": "a" * 64, "preprocess_sha256": "b" * 64, "canonical_frame_version": "exif_visual_rgb_v1", "patches": patches}, bank_path)
    bank = LocalPatchBank.load(bank_path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)
    runner = DinoV3Rechecker(FeatureEncoder(), torch.eye(384, dtype=torch.float32)[:20], _SKU_IDS, build_transform(224), "dinov3_vits16_15plus5_v1", torch.device("cpu"))
    repvit = ModelScoreVector(
        "repvit_m1_15plus5_v1", _SKU_IDS,
        (0.01,) * 5 + (0.80, 0.02, 0.70) + (0.01,) * 12,
        "probability",
    )

    _, local_scores = runner.score_global_and_local(
        tuple(Image.new("RGB", (32, 32)) for _ in range(3)),
        (Box(0, 0, 32, 32),) * 3,
        bank,
        repvit_scores=repvit,
    )

    assert tuple(local_scores) == (1, 2, 3, 4, 5, 6, 8)


def test_many_local_evidence_matches_serial_and_batches_encoder_calls(tmp_path):
    bank = _local_bank(tmp_path)
    encoder = BatchFeatureEncoder()
    runner = _runner_with_encoder(encoder)
    crop_groups = tuple(_dino_crops(color) for color in ("red", "green", "blue"))
    boxes = ((_full_box(),) * 3,) * 3
    repvit = (_repvit_scores(1), _repvit_scores(2), _repvit_scores(3))

    expected = tuple(
        DinoGlobalLocalEvidence(
            *runner.score_global_and_local_evidence(
                crops, product_boxes, bank, repvit_scores=scores
            )
        )
        for crops, product_boxes, scores in zip(crop_groups, boxes, repvit, strict=True)
    )
    actual = runner.score_many_global_and_local_evidence(
        crop_groups, boxes, bank, repvit_scores=repvit, max_objects=2
    )

    assert _evidence_payload(actual) == pytest.approx(_evidence_payload(expected))
    assert encoder.batch_sizes[-2:] == [6, 3]


def test_many_local_evidence_preserves_per_object_candidate_unions_and_alignment(tmp_path):
    bank = _local_bank(tmp_path)
    runner = _runner_with_encoder(BatchFeatureEncoder())
    groups = (_dino_crops("red"), _dino_crops("blue"))
    boxes = ((_full_box(),) * 3,) * 2

    evidence = runner.score_many_global_and_local_evidence(
        groups,
        boxes,
        bank,
        repvit_scores=(_repvit_scores(6), _repvit_scores(7)),
        max_objects=2,
    )

    assert 6 in evidence[0].local_scores and 7 not in evidence[0].local_scores
    assert 7 in evidence[1].local_scores and 6 not in evidence[1].local_scores
    with pytest.raises(ValueError, match="align"):
        runner.score_many_global_and_local_evidence(
            groups, boxes, bank, repvit_scores=(_repvit_scores(6),), max_objects=2
        )


def _dino_crops(color: str) -> tuple[Image.Image, Image.Image, Image.Image]:
    return tuple(Image.new("RGB", (224, 224), color) for _ in range(3))


def _full_box() -> Box:
    return Box(0, 0, 224, 224)


def _repvit_scores(top_sku: int) -> ModelScoreVector:
    values = [0.0] * 20
    values[top_sku - 1] = 1.0
    return ModelScoreVector("repvit_m1_15plus5_v1", _SKU_IDS, tuple(values), "probability")


def _evidence_payload(rows) -> tuple[float, ...]:
    return tuple(
        value
        for row in rows
        for value in (
            *row.global_scores.values,
            *(row.local_scores.get(sku_id, -1.0) for sku_id in _SKU_IDS),
            float(row.product_patch_count),
            row.product_patch_ratio,
        )
    )


def _local_bank(tmp_path: Path) -> LocalPatchBank:
    patches = {
        sku_id: torch.nn.functional.normalize(torch.ones((1, 384)) * sku_id, dim=1)
        for sku_id in _SKU_IDS
    }
    path = tmp_path / "batched-local.pt"
    torch.save(
        {
            "artifact_type": "dinov3_vits16_15plus5_local_patch_bank",
            "schema_version": 1,
            "dino_weights_sha256": "a" * 64,
            "preprocess_sha256": "b" * 64,
            "canonical_frame_version": "exif_visual_rgb_v1",
            "patches": patches,
        },
        path,
    )
    return LocalPatchBank.load(
        path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64
    )


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
    tmp_path,
    section,
    field,
    message,
):
    config = _write_fake_artifacts(tmp_path, _valid_support())
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


@pytest.mark.parametrize("value", (None, "legacy"))
def test_static_load_rejects_missing_or_mismatched_oof_preprocess(monkeypatch, tmp_path, value):
    descriptor = ClassifierPreprocessDescriptor()
    support = _valid_support()
    if value is not None:
        support["oof_metadata"] = {
            "preprocessing_descriptor": descriptor.to_payload(),
            "preprocessing_sha256": "0" * 64,
        }
    config = _write_fake_artifacts(tmp_path, support)
    _fail_on_model_construction(monkeypatch)

    with pytest.raises(ValueError, match="OOF preprocessing"):
        DinoV3Rechecker.load(
            config,
            device=torch.device("cpu"),
            expected_preprocess_sha256=descriptor.sha256(),
        )


def test_load_canonicalizes_default_cuda_device(monkeypatch, tmp_path):
    config = _write_fake_artifacts(tmp_path, _valid_support())
    encoder = RecordingEncoder()
    monkeypatch.setattr(
        "bakery_scanner.classification.dinov3.vit_small",
        lambda **kwargs: encoder,
    )

    def record_initialization(
        self,
        loaded_encoder,
        _prototypes,
        _sku_ids,
        _transform,
        _model_id,
        device,
    ):
        self.encoder = loaded_encoder
        self.device = device

    monkeypatch.setattr(DinoV3Rechecker, "__init__", record_initialization)

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
