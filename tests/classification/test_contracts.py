import json
import math

import pytest

from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
    SkuCandidate,
    StageTimings,
)
from bakery_scanner.contracts import Box


VALID_BOX = Box(10.0, 20.0, 30.0, 40.0)


def valid_provenance():
    return ModelProvenance(
        repvit_artifact_id="repvit_m1_15plus5_v1",
        repvit_sha256="0" * 64,
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        dinov3_sha256="1" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id="policy_v1",
        calibration_sha256="2" * 64,
    )


def test_unknown_requires_exactly_three_unique_candidates():
    with pytest.raises(ValueError, match="three unique"):
        ClassificationDecision(
            decision="unknown",
            sku_id=None,
            confidence=0.4,
            box=VALID_BOX,
            decision_path=DecisionPath.UNKNOWN_TOP3,
            top3=(SkuCandidate(1, 6, 0.7), SkuCandidate(2, 6, 0.6)),
            provenance=valid_provenance(),
            timings=StageTimings(1.0, 2.0, 3.0),
        )


def test_sku_decision_has_no_top3_and_matching_path():
    result = ClassificationDecision(
        decision="sku",
        sku_id=6,
        confidence=0.98,
        box=VALID_BOX,
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=valid_provenance(),
        timings=StageTimings(1.0, 0.0, 1.0),
    )
    assert result.sku_id == 6
    assert result.box is VALID_BOX


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_scores_must_be_finite(score):
    with pytest.raises(ValueError, match="finite"):
        SkuCandidate(1, 1, score)


def test_score_vector_requires_all_skus_in_canonical_order():
    with pytest.raises(ValueError, match="canonical"):
        ModelScoreVector(
            model_id="repvit",
            sku_ids=tuple(range(2, 21)) + (1,),
            values=(0.05,) * 20,
            score_kind="probability",
        )


def test_candidate_rank_and_score_are_bounded():
    with pytest.raises(ValueError, match="rank"):
        SkuCandidate(4, 1, 0.5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        SkuCandidate(1, 1, 1.01)


def test_provenance_requires_dino_support_hash():
    with pytest.raises(ValueError, match="dinov3_support_sha256"):
        ModelProvenance(
            repvit_artifact_id="repvit_m1_15plus5_v1",
            repvit_sha256="0" * 64,
            dinov3_artifact_id="dinov3_vits16_15plus5_v1",
            dinov3_sha256="1" * 64,
            dinov3_support_sha256="invalid",
            calibration_id="policy_v1",
            calibration_sha256="2" * 64,
        )


def test_decision_rejects_box_outside_nonnegative_original_coordinates():
    with pytest.raises(ValueError, match="non-negative"):
        ClassificationDecision(
            decision="sku",
            sku_id=6,
            confidence=0.98,
            box=Box(-1.0, 20.0, 30.0, 40.0),
            decision_path=DecisionPath.REPVIT_DIRECT,
            top3=(),
            provenance=valid_provenance(),
            timings=StageTimings(1.0, 0.0, 1.0),
        )


def test_json_output_is_canonical_utf8():
    payload = ClassificationDecision(
        decision="unknown",
        sku_id=None,
        confidence=0.4,
        box=VALID_BOX,
        decision_path=DecisionPath.UNKNOWN_TOP3,
        top3=(SkuCandidate(1, 1, 0.7), SkuCandidate(2, 2, 0.2), SkuCandidate(3, 3, 0.1)),
        provenance=valid_provenance(),
        timings=StageTimings(1.0, 2.0, 3.0),
    ).to_json_bytes()
    assert payload == json.dumps(json.loads(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    decoded = json.loads(payload)
    assert decoded["box"] == [10.0, 20.0, 40.0, 60.0]
    assert decoded["provenance"]["dinov3_support_sha256"] == "3" * 64


def test_provenance_serializes_versioned_preprocess_digest():
    provenance = ModelProvenance(
        repvit_artifact_id="repvit_m1_15plus5_v1",
        repvit_sha256="0" * 64,
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        dinov3_sha256="1" * 64,
        dinov3_support_sha256="2" * 64,
        calibration_id="policy_v1",
        calibration_sha256="3" * 64,
        preprocess_sha256="4" * 64,
    )
    result = ClassificationDecision(
        decision="sku",
        sku_id=1,
        confidence=1.0,
        box=VALID_BOX,
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=provenance,
        timings=StageTimings(0.0, 0.0, 0.0),
    )

    assert json.loads(result.to_json_bytes())["provenance"]["preprocess_sha256"] == "4" * 64
