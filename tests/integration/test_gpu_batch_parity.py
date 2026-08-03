import hashlib
from pathlib import Path

import torch
from PIL import Image

from bakery_scanner.benchmarking.decision_parity import compare_decisions
from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.contracts import ModelProvenance, ModelScoreVector
from bakery_scanner.classification.policy import DecisionPolicy, PolicyCalibration
from bakery_scanner.classification.repvit import RepVitEvidence
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image


def test_serial_and_batch_decisions_match_for_one_canonical_frame_and_ordered_boxes():
    pipeline = _pipeline()
    frame = canonicalize_image(Image.new("RGB", (100, 80), "goldenrod"))
    boxes = (Box(5, 5, 20, 20), Box(30, 10, 25, 20))

    serial = tuple(pipeline.infer(frame, box) for box in boxes)
    batch = pipeline.infer_many(
        frame,
        boxes,
        repvit_max_objects=2,
        dino_max_objects=2,
    )
    receipt = compare_decisions(serial, batch.decisions)

    assert tuple(decision.box for decision in serial) == boxes
    assert tuple(decision.box for decision in batch.decisions) == boxes
    assert receipt.passed is True
    assert receipt.mismatches == ()


class _DirectRepVit:
    def __init__(self) -> None:
        self._scores = ModelScoreVector(
            model_id="repvit_m1_15plus5_v1",
            sku_ids=tuple(range(1, 21)),
            values=(0.8,) + (0.2 / 19,) * 19,
            score_kind="probability",
        )

    def score_with_evidence(self, crops):
        return RepVitEvidence(self._scores, torch.ones(384), 0.01)

    def score_many_with_evidence(self, crop_groups, *, max_objects):
        assert max_objects == 2
        return tuple(self.score_with_evidence(crops) for crops in crop_groups)


class _PrototypeBank:
    def distances(self, feature):
        return (0.02,) + (1.0,) * 19


def _pipeline() -> ClassifierPipeline:
    calibration = _calibration()
    provenance = ModelProvenance(
        repvit_artifact_id=calibration.repvit_artifact_id,
        repvit_sha256=calibration.repvit_checkpoint_sha256,
        dinov3_artifact_id=calibration.dinov3_artifact_id,
        dinov3_sha256=calibration.dinov3_weights_sha256,
        dinov3_support_sha256=calibration.dinov3_support_sha256,
        calibration_id=calibration.calibration_id,
        calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
        preprocess_sha256=calibration.preprocess_sha256,
        repvit_manifest_sha256=calibration.repvit_manifest_sha256,
        repvit_prototype_sha256=calibration.repvit_prototype_sha256,
    )
    return ClassifierPipeline(
        config=ClassifierConfig.load(Path("configs/classifier_policy.yaml")),
        repvit=_DirectRepVit(),
        dino_loader=lambda: AssertionError("DINO must remain lazy for direct decisions"),
        policy=DecisionPolicy(calibration, provenance=provenance),
        prototype_bank=_PrototypeBank(),
    )


def _calibration() -> PolicyCalibration:
    return PolicyCalibration(
        schema_version=2,
        calibration_id="policy_v1",
        repvit_artifact_id="repvit_m1_15plus5_v1",
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        repvit_temperature=1.0,
        dinov3_temperature=1.0,
        alpha=0.60,
        direct_threshold=0.70,
        direct_margin=0.30,
        direct_max_crop_disagreement=0.30,
        direct_max_prototype_distance=0.20,
        dino_threshold=0.50,
        fused_margin=0.20,
        evidence_sha256="0" * 64,
        repvit_checkpoint_sha256="1" * 64,
        repvit_manifest_sha256="0" * 64,
        repvit_prototype_sha256="0" * 64,
        dinov3_weights_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        preprocess_sha256="0" * 64,
    )
