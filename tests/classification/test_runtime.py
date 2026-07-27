from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest
import torch
from PIL import Image

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.contracts import (
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
)
from bakery_scanner.classification.dinov3 import DinoV3Rechecker
from bakery_scanner.classification.policy import DecisionPolicy, PolicyCalibration
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.classification.repvit import RepVitEvidence
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import Box


SKU_IDS = tuple(range(1, 21))


class RecordingRunner:
    def __init__(self, scores: ModelScoreVector, *, crop_disagreement: float = 0.01) -> None:
        self.scores = scores
        self.crop_disagreement = crop_disagreement
        self.received_crops: tuple[Image.Image, ...] | None = None
        self.call_count = 0

    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector:
        self.call_count += 1
        self.received_crops = crops
        return self.scores

    def score_with_evidence(self, crops: tuple[Image.Image, ...]) -> RepVitEvidence:
        scores = self.score(crops)
        return RepVitEvidence(
            scores=scores,
            feature=torch.ones(384),
            crop_disagreement=self.crop_disagreement,
        )


class FixedPrototypeBank:
    def __init__(self, distance: float = 0.02) -> None:
        self.distance = distance

    def distances(self, feature: torch.Tensor) -> tuple[float, ...]:
        assert tuple(feature.shape) == (384,)
        return (self.distance,) + (1.0,) * 19


class OutOfMemoryEncoder(torch.nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        raise torch.OutOfMemoryError("sensitive backend detail")


class ProgrammingErrorDino:
    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector:
        raise ValueError("wrong tensor shape")


class StepClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self._values = iter(values)
        self.sync_count = 0

    def synchronize(self) -> None:
        self.sync_count += 1

    def __call__(self) -> float:
        return next(self._values)


def test_direct_repvit_confirmation_never_loads_or_calls_dino():
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.8, 5: 0.2}))

    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    original_box = _box()
    result = _pipeline(repvit=repvit, dino_loader=load_dino).infer(
        _image(), original_box
    )

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.80)
    assert result.box is original_box
    assert dino_loads == 0


def test_runtime_interprets_exif_oriented_input_in_visual_coordinates():
    encoded = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20), "white").save(encoded, format="JPEG", exif=exif)
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))

    result = _pipeline(repvit=repvit, dino_loader=lambda: pytest.fail("DINO must stay lazy")).infer(
        Image.open(BytesIO(encoded.getvalue())),
        Box(1, 2, 10, 20),
    )

    assert result.box == Box(1, 2, 10, 20)
    assert result.provenance.canonical_frame_version == "exif_visual_rgb_v1"
    assert result.provenance.exif_orientation == 6
    assert tuple(crop.size for crop in repvit.received_crops or ()) == (
        (12, 22),
        (12, 22),
        (12, 24),
    )


def test_preflight_models_loads_and_scores_dino_before_all_direct_inference():
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino = RecordingRunner(_dino_scores({6: 0.70, 5: 0.20}))
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return dino

    pipeline = _pipeline(repvit=repvit, dino_loader=load_dino)

    pipeline.preflight_models(_image(), _box())
    result = pipeline.infer(_image(), _box())

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert dino_loads == 1
    assert repvit.call_count == 2
    assert dino.call_count == 1
    assert repvit.received_crops is not dino.received_crops
    assert tuple(crop.size for crop in dino.received_crops) == (
        (42, 22),
        (44, 22),
        (46, 24),
    )


def test_ambiguous_repvit_loads_dino_once_and_reuses_the_same_crops():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}))
    dino = RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10}))
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return dino

    pipeline = _pipeline(repvit=repvit, dino_loader=load_dino)
    first = pipeline.infer(_image(), _box())
    second = pipeline.infer(_image(), _box())

    assert first.decision_path is DecisionPath.UNKNOWN_TOP3
    assert len(first.top3) == 3
    assert dino_loads == 1
    assert dino.call_count == 2
    assert repvit.received_crops is dino.received_crops
    payload = first.to_json_bytes()
    assert (
        json.dumps(
            json.loads(payload),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        == payload
    )
    assert second.decision_path is DecisionPath.UNKNOWN_TOP3
    assert first.box == _box()
    assert second.box == _box()


def test_unsafe_repvit_prototype_distance_defers_to_dino():
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.70, 5: 0.20}))

    result = _pipeline(
        repvit=repvit,
        dino_loader=load_dino,
        prototype_bank=FixedPrototypeBank(0.21),
    ).infer(_image(), _box())

    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert dino_loads == 1


def test_recheck_confirmation_keeps_fused_confidence_meaning():
    calibration = _calibration(
        alpha=0.5,
        dino_threshold=0.40,
        fused_margin=0.10,
    )
    repvit = RecordingRunner(_repvit_scores({6: 0.40, 5: 0.30}))
    dino = RecordingRunner(_dino_scores({6: 0.40, 5: 0.30}))

    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        calibration=calibration,
    ).infer(_image(), _box())

    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.40)
    assert result.box == _box()


def test_runtime_records_provenance_stage_timings_and_synchronizes():
    clock = StepClock((10.000, 10.001, 10.004, 10.005, 10.011, 10.012))
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}))
    dino = RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10}))
    pipeline = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        clock=clock,
    )

    result = pipeline.infer(_image(), _box())

    assert result.provenance == pipeline.policy.provenance
    assert result.provenance.repvit_sha256 == "1" * 64
    assert result.provenance.dinov3_sha256 == "2" * 64
    assert result.provenance.dinov3_support_sha256 == "3" * 64
    assert result.timings.repvit_ms == pytest.approx(3.0)
    assert result.timings.dinov3_ms == pytest.approx(6.0)
    assert result.timings.total_ms == pytest.approx(12.0)
    assert clock.sync_count == 6


def test_dino_failure_returns_unknown_repvit_top3_and_safe_failure_code():
    repvit = RecordingRunner(_repvit_scores({19: 0.40, 6: 0.30, 5: 0.20}))
    real_dino = DinoV3Rechecker(
        OutOfMemoryEncoder(),
        torch.eye(384, dtype=torch.float32)[:20],
        SKU_IDS,
        build_transform(224),
        "dinov3_vits16_15plus5_v1",
        torch.device("cpu"),
    )

    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: real_dino,
    ).infer(_image(), _box())

    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert [(candidate.rank, candidate.sku_id) for candidate in result.top3] == [
        (1, 19),
        (2, 6),
        (3, 5),
    ]
    assert result.provenance.failure_code == "dino_out_of_memory"
    assert b"sensitive backend detail" not in result.to_json_bytes()
    assert result.box == _box()


def test_dino_programming_error_is_not_converted_to_unknown():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30}))

    with pytest.raises(ValueError, match="wrong tensor shape"):
        _pipeline(
            repvit=repvit,
            dino_loader=ProgrammingErrorDino,
        ).infer(_image(), _box())


@pytest.mark.parametrize(
    "box",
    [
        Box(-1, 10, 40, 20),
        Box(10, -1, 40, 20),
        Box(61, 10, 40, 20),
        Box(10, 61, 40, 20),
    ],
)
def test_runtime_rejects_box_outside_canonical_visual_image(box):
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))

    with pytest.raises(ValueError, match="canonical visual"):
        _pipeline(
            repvit=repvit,
            dino_loader=lambda: pytest.fail("DINO must not load"),
        ).infer(_image(), box)


def test_lazy_dino_initialization_failure_is_not_converted_to_unknown():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30}))

    def load_dino() -> RecordingRunner:
        raise ValueError("DINO artifact hash mismatch")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        _pipeline(repvit=repvit, dino_loader=load_dino).infer(_image(), _box())


def test_load_requires_calibration_before_loading_repvit(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    missing = tmp_path / "missing-policy.json"
    configured = config.model_copy(
        update={
            "calibration": config.calibration.model_copy(update={"artifact": missing})
        }
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.ClassifierConfig.load",
        lambda path: configured,
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.RepVitM1Runner.load",
        lambda config: pytest.fail("RepViT must not load without calibration"),
    )

    with pytest.raises(FileNotFoundError):
        ClassifierPipeline.load(tmp_path / "classifier.yaml")


def test_load_builds_provenance_and_defers_dino_model_load(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    calibration = _calibration(
        repvit_checkpoint_sha256=config.repvit.checkpoint_sha256,
        repvit_manifest_sha256=config.repvit.manifest_sha256,
        dinov3_weights_sha256=config.dinov3.weights_sha256,
        dinov3_support_sha256=config.dinov3.support_sha256,
        preprocess_sha256=preprocess_sha256(config.preprocess),
        repvit_prototype_sha256=config.repvit.prototype_bank_sha256,
        direct_max_prototype_distance=2.0,
    )
    calibration_path = tmp_path / "policy.json"
    calibration_path.write_bytes(calibration.to_json_bytes())
    configured = config.model_copy(
        update={
            "calibration": config.calibration.model_copy(
                update={"artifact": calibration_path}
            )
        }
    )
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino_loads = 0

    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.ClassifierConfig.load",
        lambda path: configured,
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.RepVitM1Runner.load",
        lambda loaded_config: repvit,
    )

    def load_dino(loaded_config):
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.7, 5: 0.2}))

    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.DinoV3Rechecker.load",
        load_dino,
    )

    pipeline = ClassifierPipeline.load(tmp_path / "classifier.yaml")

    assert dino_loads == 0
    assert pipeline.policy.provenance == ModelProvenance(
        repvit_artifact_id=config.repvit.artifact_id,
        repvit_sha256=config.repvit.checkpoint_sha256,
        dinov3_artifact_id=config.dinov3.artifact_id,
        dinov3_sha256=config.dinov3.weights_sha256,
        dinov3_support_sha256=config.dinov3.support_sha256,
        calibration_id=calibration.calibration_id,
        calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
        preprocess_sha256=preprocess_sha256(config.preprocess),
        repvit_manifest_sha256=config.repvit.manifest_sha256,
        repvit_prototype_sha256=config.repvit.prototype_bank_sha256,
    )
    pipeline.infer(_image(), _box())
    assert dino_loads == 0


def _pipeline(
    *,
    repvit: RecordingRunner,
    dino_loader,
    calibration: PolicyCalibration | None = None,
    clock=None,
    prototype_bank: FixedPrototypeBank | None = None,
) -> ClassifierPipeline:
    selected = calibration or _calibration()
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id,
        repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id,
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    return ClassifierPipeline(
        config=config,
        repvit=repvit,
        dino_loader=dino_loader,
        policy=DecisionPolicy(selected, provenance=provenance),
        clock=clock,
        prototype_bank=prototype_bank or FixedPrototypeBank(),
    )


def _calibration(**overrides: object) -> PolicyCalibration:
    values: dict[str, object] = {
        "schema_version": 2,
        "calibration_id": "policy_v1",
        "repvit_artifact_id": "repvit_m1_15plus5_v1",
        "dinov3_artifact_id": "dinov3_vits16_15plus5_v1",
        "repvit_temperature": 1.0,
        "dinov3_temperature": 1.0,
        "alpha": 0.60,
        "direct_threshold": 0.70,
        "direct_margin": 0.30,
        "direct_max_crop_disagreement": 0.30,
        "direct_max_prototype_distance": 0.20,
        "dino_threshold": 0.50,
        "fused_margin": 0.20,
        "evidence_sha256": "0" * 64,
        "repvit_checkpoint_sha256": "1" * 64,
        "repvit_manifest_sha256": "0" * 64,
        "repvit_prototype_sha256": "0" * 64,
        "dinov3_weights_sha256": "2" * 64,
        "dinov3_support_sha256": "3" * 64,
        "preprocess_sha256": "0" * 64,
    }
    values.update(overrides)
    return PolicyCalibration(**values)


def _repvit_scores(values: dict[int, float]) -> ModelScoreVector:
    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "repvit_m1_15plus5_v1",
        SKU_IDS,
        tuple(values.get(sku_id, fill) for sku_id in SKU_IDS),
        "probability",
    )


def _dino_scores(values: dict[int, float]) -> ModelScoreVector:
    import math

    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "dinov3_vits16_15plus5_v1",
        SKU_IDS,
        tuple(math.log(values.get(sku_id, fill)) for sku_id in SKU_IDS),
        "similarity",
    )


def _image() -> Image.Image:
    return Image.new("RGB", (100, 80), "goldenrod")


def _box() -> Box:
    return Box(x=10, y=10, width=40, height=20)
