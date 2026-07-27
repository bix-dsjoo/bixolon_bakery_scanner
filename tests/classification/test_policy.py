from __future__ import annotations

import hashlib
import json
import math

import pytest

from bakery_scanner.classification.contracts import (
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
)
from bakery_scanner.classification.policy import (
    DecisionPolicy,
    PolicyCalibration,
    calibrate_dinov3,
    calibrate_repvit,
    fuse_probabilities,
)
from bakery_scanner.contracts import Box


SKU_IDS = tuple(range(1, 21))
BOX = Box(10.0, 20.0, 30.0, 40.0)


def calibration(**overrides: object) -> PolicyCalibration:
    values: dict[str, object] = {
        "schema_version": 1,
        "calibration_id": "policy_v1",
        "repvit_artifact_id": "repvit_m1_15plus5_v1",
        "dinov3_artifact_id": "dinov3_vits16_15plus5_v1",
        "repvit_temperature": 1.0,
        "dinov3_temperature": 1.0,
        "alpha": 0.60,
        "direct_threshold": 0.70,
        "direct_margin": 0.30,
        "dino_threshold": 0.50,
        "fused_margin": 0.20,
        "evidence_sha256": "0" * 64,
        "repvit_checkpoint_sha256": "1" * 64,
        "repvit_manifest_sha256": "0" * 64,
        "dinov3_weights_sha256": "2" * 64,
        "dinov3_support_sha256": "3" * 64,
        "preprocess_sha256": "0" * 64,
    }
    values.update(overrides)
    return PolicyCalibration(**values)


def policy(cal: PolicyCalibration | None = None) -> DecisionPolicy:
    selected = cal or calibration()
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id,
        repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id,
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    return DecisionPolicy(selected, provenance=provenance)


def test_policy_rejects_calibration_from_different_checkpoint_with_same_model_id():
    with pytest.raises(ValueError, match="repvit_sha256"):
        policy(calibration(repvit_checkpoint_sha256="9" * 64))


def probabilities(values: dict[int, float]) -> ModelScoreVector:
    remaining = 1.0 - sum(values.values())
    unassigned = 20 - len(values)
    fill = remaining / unassigned if unassigned else 0.0
    scores = tuple(values.get(sku_id, fill) for sku_id in SKU_IDS)
    return ModelScoreVector(
        "repvit_m1_15plus5_v1",
        SKU_IDS,
        scores,
        "probability",
    )


def similarities_from_probabilities(values: dict[int, float]) -> ModelScoreVector:
    remaining = 1.0 - sum(values.values())
    unassigned = 20 - len(values)
    fill = remaining / unassigned if unassigned else 0.0
    probabilities_ = tuple(values.get(sku_id, fill) for sku_id in SKU_IDS)
    similarities = tuple(math.log(value) for value in probabilities_)
    return ModelScoreVector(
        "dinov3_vits16_15plus5_v1",
        SKU_IDS,
        similarities,
        "similarity",
    )


def test_calibration_is_canonical_and_bound_to_artifacts():
    selected = calibration(
        repvit_temperature=1.25,
        dinov3_temperature=0.75,
        alpha=0.60,
        direct_threshold=0.92,
        direct_margin=0.30,
        dino_threshold=0.85,
        fused_margin=0.20,
    )

    assert PolicyCalibration.from_json_bytes(selected.to_json_bytes()) == selected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("repvit_artifact_id", "repvit_other", "repvit_artifact_id"),
        ("dinov3_artifact_id", "dinov3_other", "dinov3_artifact_id"),
        ("evidence_sha256", "ABC", "evidence_sha256"),
        ("repvit_temperature", 0.0, "greater than zero"),
        ("dinov3_temperature", -1.0, "greater than zero"),
        ("alpha", 1.01, "between 0 and 1"),
        ("direct_threshold", -0.01, "between 0 and 1"),
        ("direct_margin", float("nan"), "finite"),
        ("dino_threshold", float("inf"), "finite"),
        ("fused_margin", 1.01, "between 0 and 1"),
    ],
)
def test_calibration_rejects_invalid_fields(field: str, value: object, message: str):
    with pytest.raises(ValueError, match=message):
        calibration(**{field: value})


@pytest.mark.parametrize("mutation", ["missing", "extra", "whitespace", "reordered"])
def test_calibration_rejects_noncanonical_or_wrong_schema_json(mutation: str):
    canonical = calibration().to_json_bytes()
    parsed = json.loads(canonical)
    if mutation == "missing":
        parsed.pop("alpha")
        payload = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    elif mutation == "extra":
        parsed["unexpected"] = 1
        payload = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    elif mutation == "whitespace":
        payload = b" " + canonical
    else:
        payload = json.dumps(
            dict(reversed(tuple(parsed.items()))),
            sort_keys=False,
            separators=(",", ":"),
        ).encode()

    with pytest.raises(ValueError, match="canonical|keys"):
        PolicyCalibration.from_json_bytes(payload)


def test_calibration_functions_use_float64_and_normalize():
    repvit = calibrate_repvit((0.8, 0.2), 2.0)
    dino = calibrate_dinov3((2.0, 0.0), 2.0)

    assert repvit == pytest.approx((2.0 / 3.0, 1.0 / 3.0))
    assert dino == pytest.approx((0.7310585786300049, 0.2689414213699951))
    assert all(type(value) is float for value in repvit + dino)


def test_fusion_supports_alpha_endpoints():
    repvit = (0.7, 0.2, 0.1)
    dino = (0.1, 0.3, 0.6)

    assert fuse_probabilities(repvit, dino, 1.0) == pytest.approx(repvit)
    assert fuse_probabilities(repvit, dino, 0.0) == pytest.approx(dino)


def test_direct_gate_skips_top3_when_threshold_and_margin_pass():
    result = policy().direct(probabilities({6: 0.80, 5: 0.20}), box=BOX)

    assert result is not None
    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.80)
    assert result.top3 == ()
    assert result.box is BOX


def test_direct_gate_accepts_threshold_and_margin_equality():
    result = policy(calibration(direct_threshold=0.05, direct_margin=0.0)).direct(
        probabilities({}), box=BOX
    )

    assert result is not None
    assert result.sku_id == 1


def test_direct_gate_requires_both_threshold_and_margin():
    assert policy().direct(probabilities({6: 0.69, 5: 0.10}), box=BOX) is None
    assert (
        policy(calibration(direct_threshold=0.50, direct_margin=0.30)).direct(
            probabilities({6: 0.55, 5: 0.40}), box=BOX
        )
        is None
    )


def test_disagreement_abstains_with_three_fused_candidates():
    result = policy(calibration(dino_threshold=0.20, fused_margin=0.0)).after_recheck(
        probabilities({6: 0.50, 5: 0.30, 19: 0.10}),
        similarities_from_probabilities({5: 0.50, 6: 0.30, 19: 0.10}),
        box=BOX,
    )

    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert [candidate.sku_id for candidate in result.top3] == [6, 5, 19]


def test_recheck_accepts_threshold_and_margin_equality():
    result = policy(
        calibration(
            alpha=0.5,
            dino_threshold=0.40,
            fused_margin=0.10,
        )
    ).after_recheck(
        probabilities({6: 0.40, 5: 0.30}),
        similarities_from_probabilities({6: 0.40, 5: 0.30}),
        box=BOX,
    )

    assert result.decision == "sku"
    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.40)
    assert result.box is BOX


def test_recheck_agreement_with_weak_dino_abstains():
    result = policy(calibration(dino_threshold=0.51, fused_margin=0.0)).after_recheck(
        probabilities({6: 0.60, 5: 0.20}),
        similarities_from_probabilities({6: 0.50, 5: 0.20}),
        box=BOX,
    )

    assert result.decision == "unknown"


def test_recheck_agreement_with_weak_fused_margin_abstains():
    result = policy(calibration(dino_threshold=0.20, fused_margin=0.25)).after_recheck(
        probabilities({6: 0.45, 5: 0.35}),
        similarities_from_probabilities({6: 0.45, 5: 0.35}),
        box=BOX,
    )

    assert result.decision == "unknown"


def test_ties_are_ranked_by_ascending_sku_id():
    result = policy(calibration(dino_threshold=1.0, fused_margin=1.0)).after_recheck(
        probabilities({}),
        similarities_from_probabilities({}),
        box=BOX,
    )

    assert [candidate.sku_id for candidate in result.top3] == [1, 2, 3]
    assert [candidate.rank for candidate in result.top3] == [1, 2, 3]


def test_dino_failure_returns_exactly_three_repvit_candidates():
    result = policy().dino_failure(
        probabilities({19: 0.40, 6: 0.30, 5: 0.20}),
        box=BOX,
    )

    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert result.confidence == pytest.approx(0.40)
    assert [(item.rank, item.sku_id) for item in result.top3] == [
        (1, 19),
        (2, 6),
        (3, 5),
    ]
    assert len({item.sku_id for item in result.top3}) == 3
    assert result.box is BOX
