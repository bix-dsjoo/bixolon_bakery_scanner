import hashlib
from pathlib import Path

import torch
import pytest
from PIL import Image

from bakery_scanner.benchmarking.decision_parity import compare_decisions
from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.contracts import DecisionPath, ModelProvenance, ModelScoreVector
from bakery_scanner.classification.dinov3 import DinoGlobalLocalEvidence
from bakery_scanner.classification.policy import DecisionPolicy, PolicyCalibration
from bakery_scanner.classification.repvit import RepVitEvidence
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image


def test_serial_and_batch_decisions_match_distinct_ordered_box_evidence():
    pipeline, repvit, dino = _pipeline()
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
    assert serial[0].decision == "sku"
    assert serial[0].sku_id == 6
    assert serial[0].decision_path is DecisionPath.REPVIT_DIRECT
    assert serial[0].top3 == ()
    assert serial[0].unknown_reason is None
    assert serial[1].decision == "unknown"
    assert serial[1].sku_id is None
    assert serial[1].decision_path is DecisionPath.UNKNOWN_TOP3
    assert [(candidate.rank, candidate.sku_id) for candidate in serial[1].top3] == [
        (1, 5),
        (2, 6),
        (3, 19),
    ]
    assert [candidate.score for candidate in serial[1].top3] == pytest.approx(
        [0.5, 0.3, 0.1]
    )
    assert serial[1].unknown_reason == "dino_local_disagreement"
    assert [decision.provenance.exif_orientation for decision in serial] == [1, 1]
    assert tuple(decision.provenance for decision in batch.decisions) == tuple(
        decision.provenance for decision in serial
    )
    assert repvit.serial_crop_groups == list(_EXPECTED_CROP_GROUPS)
    assert repvit.batch_crop_groups == [_EXPECTED_CROP_GROUPS]
    assert dino.serial_crop_groups == [_EXPECTED_CROP_GROUPS[1]]
    assert dino.serial_product_boxes == [_EXPECTED_PRODUCT_BOXES[1]]
    assert dino.batch_crop_groups == [(_EXPECTED_CROP_GROUPS[1],)]
    assert dino.batch_product_boxes == [(_EXPECTED_PRODUCT_BOXES[1],)]
    assert receipt.passed is True
    assert receipt.mismatches == ()


def test_reordered_batch_evidence_fails_the_parity_receipt():
    reference_pipeline, _, _ = _pipeline()
    candidate_pipeline, _, _ = _pipeline(reorder_batch_evidence=True)
    frame = canonicalize_image(Image.new("RGB", (100, 80), "goldenrod"))
    boxes = (Box(5, 5, 20, 20), Box(30, 10, 25, 20))

    reference = tuple(reference_pipeline.infer(frame, box) for box in boxes)
    candidate = candidate_pipeline.infer_many(
        frame,
        boxes,
        repvit_max_objects=2,
        dino_max_objects=2,
    ).decisions
    receipt = compare_decisions(reference, candidate)

    assert receipt.passed is False
    assert receipt.mismatches[0].fields == (
        "decision",
        "sku_id",
        "confidence",
        "decision_path",
        "top3",
        "unknown_reason",
    )


_EXPECTED_CROP_GROUPS = (
    ((22, 22), (22, 22), (24, 24)),
    ((27, 22), (29, 22), (29, 24)),
)
_EXPECTED_PRODUCT_BOXES = (
    (Box(1, 1, 20, 20), Box(1, 1, 20, 20), Box(2, 2, 20, 20)),
    (Box(1, 1, 25, 20), Box(2, 1, 25, 20), Box(2, 2, 25, 20)),
)


class _EvidenceRepVit:
    def __init__(self, *, reorder_batch_evidence: bool = False) -> None:
        self.reorder_batch_evidence = reorder_batch_evidence
        self.serial_crop_groups: list[tuple[tuple[int, int], ...]] = []
        self.batch_crop_groups: list[tuple[tuple[tuple[int, int], ...], ...]] = []
        self._evidence_by_group = {
            _EXPECTED_CROP_GROUPS[0]: _repvit_evidence({6: 0.8}),
            _EXPECTED_CROP_GROUPS[1]: _repvit_evidence({5: 0.5, 6: 0.3, 19: 0.1}),
        }

    def score_with_evidence(self, crops):
        group = _crop_group(crops)
        self.serial_crop_groups.append(group)
        return self._evidence_by_group[group]

    def score_many_with_evidence(self, crop_groups, *, max_objects):
        assert max_objects == 2
        groups = tuple(_crop_group(crops) for crops in crop_groups)
        assert groups == _EXPECTED_CROP_GROUPS
        self.batch_crop_groups.append(groups)
        evidence_groups = tuple(reversed(groups)) if self.reorder_batch_evidence else groups
        return tuple(self._evidence_by_group[group] for group in evidence_groups)


class _EvidenceDino:
    def __init__(self) -> None:
        self.serial_crop_groups: list[tuple[tuple[int, int], ...]] = []
        self.serial_product_boxes: list[tuple[Box, ...]] = []
        self.batch_crop_groups: list[tuple[tuple[tuple[int, int], ...], ...]] = []
        self.batch_product_boxes: list[tuple[tuple[Box, ...], ...]] = []
        self._evidence_by_group = {
            _EXPECTED_CROP_GROUPS[0]: _dino_evidence({6: 0.8}, {6: 0.9, 5: 0.1}),
            _EXPECTED_CROP_GROUPS[1]: _dino_evidence({5: 0.5, 6: 0.3, 19: 0.1}, {5: 0.1, 6: 0.9}),
        }

    def score(self, crops):
        raise AssertionError("local DINO evidence path is required")

    def score_global_and_local(self, crops, product_boxes, local_bank, *, repvit_scores):
        group = _crop_group(crops)
        products = tuple(product_boxes)
        self.serial_crop_groups.append(group)
        self.serial_product_boxes.append(products)
        evidence = self._evidence_by_group[group]
        return (
            evidence.global_scores,
            evidence.local_scores,
        )

    def score_many_global_and_local_evidence(
        self, crop_groups, product_box_groups, local_bank, *, repvit_scores, max_objects
    ):
        assert max_objects == 2
        groups = tuple(_crop_group(crops) for crops in crop_groups)
        products = tuple(tuple(boxes) for boxes in product_box_groups)
        assert groups in ((_EXPECTED_CROP_GROUPS[0],), (_EXPECTED_CROP_GROUPS[1],))
        self.batch_crop_groups.append(groups)
        self.batch_product_boxes.append(products)
        return tuple(self._evidence_by_group[group] for group in groups)


class _PrototypeBank:
    def distances(self, feature):
        return (0.02,) + (1.0,) * 19


def _pipeline(*, reorder_batch_evidence: bool = False) -> tuple[ClassifierPipeline, _EvidenceRepVit, _EvidenceDino]:
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
    repvit = _EvidenceRepVit(reorder_batch_evidence=reorder_batch_evidence)
    dino = _EvidenceDino()
    return ClassifierPipeline(
        config=ClassifierConfig.load(Path("configs/classifier_policy.yaml")),
        repvit=repvit,
        dino_loader=lambda: dino,
        policy=DecisionPolicy(calibration, provenance=provenance),
        prototype_bank=_PrototypeBank(),
        local_bank=object(),
    ), repvit, dino


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


def _crop_group(crops) -> tuple[tuple[int, int], ...]:
    return tuple(crop.size for crop in crops)


def _repvit_evidence(values: dict[int, float]) -> RepVitEvidence:
    return RepVitEvidence(_repvit_scores(values), torch.ones(384), 0.01)


def _dino_evidence(values: dict[int, float], local_scores: dict[int, float]) -> DinoGlobalLocalEvidence:
    return DinoGlobalLocalEvidence(_dino_scores(values), local_scores, 32, 0.5)


def _repvit_scores(values: dict[int, float]) -> ModelScoreVector:
    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "repvit_m1_15plus5_v1",
        tuple(range(1, 21)),
        tuple(values.get(sku_id, fill) for sku_id in range(1, 21)),
        "probability",
    )


def _dino_scores(values: dict[int, float]) -> ModelScoreVector:
    import math

    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "dinov3_vits16_15plus5_v1",
        tuple(range(1, 21)),
        tuple(math.log(values.get(sku_id, fill)) for sku_id in range(1, 21)),
        "similarity",
    )
