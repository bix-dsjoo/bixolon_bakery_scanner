from __future__ import annotations

from dataclasses import replace

import pytest

from tools.train.calibrate_rtx5080_15plus5 import CalibrationRow, calibrate_fold


HASHES = {
    "split_sha256": "1" * 64,
    "source_evidence_sha256": "2" * 64,
    "repvit_checkpoint_sha256": "3" * 64,
    "repvit_prototype_sha256": "4" * 64,
    "dinov3_weights_sha256": "5" * 64,
    "dinov3_support_sha256": "6" * 64,
    "dinov3_local_bank_sha256": "7" * 64,
    "preprocess_sha256": "8" * 64,
    "code_sha256": "9" * 64,
    "runtime_sha256": "a" * 64,
    "dino_global_fold_index": 0,
    "dino_local_fold_index": 0,
    "dino_global_split_sha256": "1" * 64,
    "dino_local_split_sha256": "1" * 64,
    "dino_global_source_evidence_sha256": "2" * 64,
    "dino_local_source_evidence_sha256": "2" * 64,
    "dino_global_runtime_sha256": "a" * 64,
    "dino_local_runtime_sha256": "a" * 64,
    "dino_local_model_sha256": "5" * 64,
    "dino_global_preprocess_sha256": "8" * 64,
    "dino_local_preprocess_sha256": "8" * 64,
}


def _row(
    identity: str,
    *,
    sku: int = 4,
    predicted: int = 4,
    confidence: float = 0.9,
    **changes: object,
) -> CalibrationRow:
    ranking = (predicted, 4 if predicted != 4 else 5, 6)
    values = {
        "identity": identity,
        "scene_id": identity.split("#")[0],
        "object_id": identity,
        "fold_index": 0,
        "role": "calibration",
        "declared_calibration_scene_ids": ("cal-a", "cal-b"),
        "declared_evaluation_scene_ids": ("eval-a",),
        "expected_sku_id": sku,
        "predicted_sku_id": predicted,
        "confidence": confidence,
        "margin": 0.5,
        "prototype_distance": 0.1,
        "crop_disagreement": 0.01,
        "ranked_sku_ids": ranking,
        "ranked_scores": (0.9, 0.08, 0.02),
        **HASHES,
        **changes,
    }
    return CalibrationRow(**values)


def test_fold_policy_uses_exactly_declared_calibration_role():
    bundle = calibrate_fold((_row("cal-b#0"), _row("cal-a#0")), fold_index=0)

    assert bundle.source_scene_ids == ("cal-a", "cal-b")
    assert not set(bundle.source_scene_ids) & {"eval-a"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"role": "evaluation"}, "calibration role"),
        ({"scene_id": "undeclared"}, "declared calibration"),
        ({"fold_index": 1}, "fold"),
        ({"confidence": float("nan")}, "finite"),
        ({"ranked_sku_ids": (4, 4, 6)}, "ranking"),
        ({"preprocess_sha256": "a" * 64}, "evidence identity"),
    ],
)
def test_fold_calibration_rejects_leakage_and_malformed_evidence(change, message):
    if change == {"preprocess_sha256": "a" * 64}:
        rows = (
            _row("cal-a#0"),
            _row(
                "cal-b#0",
                **change,
                dino_global_preprocess_sha256="a" * 64,
                dino_local_preprocess_sha256="a" * 64,
            ),
        )
        with pytest.raises(ValueError, match=message):
            calibrate_fold(rows, fold_index=0)
    else:
        with pytest.raises(ValueError, match=message):
            _row("cal-b#0", **change)


def test_duplicate_scene_object_identity_is_rejected():
    row = _row("cal-a#0")
    with pytest.raises(ValueError, match="duplicate"):
        calibrate_fold((row, row), fold_index=0)


def test_direct_gate_search_has_zero_wrong_acceptance_and_deterministic_tie_order():
    correct_strict = replace(_row("cal-a#0"), confidence=0.95, margin=0.6)
    correct_loose = replace(_row("cal-b#0"), confidence=0.90, margin=0.5)
    wrong = replace(
        _row("cal-b#1", predicted=4, sku=5, confidence=0.92),
        margin=0.4,
    )
    bundle = calibrate_fold((correct_loose, wrong, correct_strict), fold_index=0)

    gate = bundle.direct_gates[4]
    assert gate.enabled is True
    assert gate.accepted_count == 2
    assert gate.wrong_accepted_count == 0
    assert gate.confidence_min == 0.9
    assert gate.margin_min == 0.5


def test_sku_without_any_correct_zero_error_region_disables_direct_gate():
    wrong = _row(
        "cal-a#0",
        sku=5,
        declared_calibration_scene_ids=("cal-a",),
    )

    bundle = calibrate_fold((wrong,), fold_index=0)

    assert bundle.direct_gates[4].enabled is False


def test_calibration_rejects_mixed_dino_global_and_local_evidence_identity():
    with pytest.raises(ValueError, match="DINO evidence identity"):
        _row("cal-a#0", dino_local_runtime_sha256="b" * 64)
