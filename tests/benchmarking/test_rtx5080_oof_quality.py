from __future__ import annotations

from dataclasses import replace

import pytest

from bakery_scanner.benchmarking.oof15plus5 import GroundTruthObject, OofEvaluationRow, PredictionObject, build_final_development_policy, evaluate_oof, freeze_oof_receipt, immutable_fusion_accepts


PROVENANCE = {"split_sha256":"1" * 64,"source_evidence_sha256":"2" * 64,"detector_sha256":"3" * 64,"repvit_checkpoint_sha256":"4" * 64,"repvit_prototype_sha256":"5" * 64,"dinov3_weights_sha256":"6" * 64,"dinov3_support_sha256":"7" * 64,"dinov3_local_bank_sha256":"8" * 64,"preprocess_sha256":"9" * 64,"fold_policy_sha256":"a" * 64,"code_sha256":"b" * 64,"runtime_sha256":"c" * 64,"dino_global_fold_index":0,"dino_local_fold_index":0,"dino_global_split_sha256":"1" * 64,"dino_local_split_sha256":"1" * 64,"dino_global_source_evidence_sha256":"2" * 64,"dino_local_source_evidence_sha256":"2" * 64,"dino_global_runtime_sha256":"c" * 64,"dino_local_runtime_sha256":"c" * 64,"dino_local_model_sha256":"6" * 64,"dino_global_preprocess_sha256":"9" * 64,"dino_local_preprocess_sha256":"9" * 64}


def _scene(*, count: int = 1, unknown: bool = False, wrong: bool = False, fold_index: int = 0, scene_id: str | None = None, state: str = "accepted_scan") -> OofEvaluationRow:
    truth = tuple(GroundTruthObject(f"g{i}", i + 1, (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1) for i in range(count))
    predictions = tuple(PredictionObject(f"p{i}", (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1, "unknown" if unknown else "auto_approved", None if unknown else (20 if wrong and i == 0 else i + 1), (1, 2, 3) if unknown else ()) for i in range(count))
    return OofEvaluationRow(scene_id=scene_id or f"scene-{fold_index}-{count}", fold_index=fold_index, role="evaluation", declared_evaluation_scene_ids=(scene_id or f"scene-{fold_index}-{count}",), state=state, difficulty="E", image_shape="landscape", catalog_segment="base", evidence_kind="observed", ground_truth=truth, predictions=predictions, seed=20260803, **{**PROVENANCE, "dino_global_fold_index": fold_index, "dino_local_fold_index": fold_index})


@pytest.mark.parametrize(("fusion", "local", "repvit", "dino", "margin", "accepted"), [(4, 4, 1, 2, 0.0, True), (4, 2, 4, 4, 0.85, True), (4, 2, 4, 4, 0.849999, False), (4, 2, 4, 3, 0.99, False)])
def test_immutable_fusion_rule_truth_table(fusion, local, repvit, dino, margin, accepted):
    assert immutable_fusion_accepts(fusion, local, repvit, dino, margin) is accepted


def test_one_wrong_auto_approval_quality_rejects():
    receipt = evaluate_oof((_scene(wrong=True),), {0: "a" * 64})
    assert receipt.status == "quality-rejected"
    assert receipt.quality.wrong_auto_approval_count == 1


def test_all_unknown_cannot_pass_utility_and_is_not_a_wrong_sku():
    receipt = evaluate_oof((_scene(unknown=True),), {0: "a" * 64})
    assert receipt.quality.wrong_auto_approval_count == 0
    assert receipt.status == "utility-rejected"
    assert receipt.unknown_count == 1


def test_iou_matching_reports_miss_duplicate_split_merge_count_and_order():
    changed = replace(_scene(count=2), predictions=(PredictionObject("p0", (0.0, 0.0, 10.0, 10.0), 2, "auto_approved", 1, ()), PredictionObject("z-duplicate", (0.0, 0.0, 10.0, 10.0), 1, "auto_approved", 1, ())))
    receipt = evaluate_oof((changed,), {0: "a" * 64})
    assert receipt.quality.miss_count == 1
    assert receipt.quality.duplicate_count == 1
    assert receipt.quality.detected_count_mismatch_count == 0
    assert receipt.quality.object_order_mismatch_count == 1


def test_positive_object_counts_are_reporting_slices_not_acceptance_limits():
    receipt = evaluate_oof(tuple(_scene(count=count, scene_id=f"scene-{count}") for count in (1, 3, 8)), {0: "a" * 64})
    assert receipt.object_count_slices == {"count_1_2": 1, "count_3_7": 1, "count_8_plus": 1}
    assert receipt.quality.accepted_scan_critical_failure_count == 0


def test_invalid_top3_nonfinite_box_and_evidence_mismatch_fail_closed():
    with pytest.raises(ValueError, match="Top-3"):
        replace(_scene(unknown=True).predictions[0], top3=(1, 1, 2))
    with pytest.raises(ValueError, match="finite"):
        replace(_scene().ground_truth[0], box_xyxy=(0.0, 0.0, float("nan"), 1.0))
    row = replace(_scene(scene_id="different-scene"), preprocess_sha256="c" * 64, dino_global_preprocess_sha256="c" * 64, dino_local_preprocess_sha256="c" * 64)
    with pytest.raises(ValueError, match="evidence identity"):
        evaluate_oof((_scene(), row), {0: "a" * 64})


def test_receipt_freeze_is_canonical_and_required_before_final_policy():
    rows = tuple(_scene(count=count, fold_index=fold, scene_id=f"scene-{fold}") for fold, count in enumerate((3, 1, 3, 1, 8)))
    policy_by_fold = {fold: "a" * 64 for fold in range(5)}
    frozen_a = freeze_oof_receipt(evaluate_oof(rows, policy_by_fold))
    frozen_b = freeze_oof_receipt(evaluate_oof(tuple(reversed(rows)), policy_by_fold))
    assert frozen_a.sha256 == frozen_b.sha256
    assert b"C:\\\\" not in frozen_a.payload
    with pytest.raises(ValueError, match="frozen"):
        build_final_development_policy(None, b"{}")
    policy = build_final_development_policy(frozen_a, b'{"consensus_margin_floor":0.85,"decision_rule":"fusion_local_or_global_consensus_margin_v1","schema_version":3}')
    assert frozen_a.sha256.encode() in policy


def test_evaluation_role_fold_duplicate_and_policy_circularity_are_rejected():
    with pytest.raises(ValueError, match="evaluation role"):
        evaluate_oof((replace(_scene(), role="calibration"),), {0: "a" * 64})
    with pytest.raises(ValueError, match="fold policy"):
        evaluate_oof((_scene(),), {0: "c" * 64})
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_oof((_scene(), _scene()), {0: "a" * 64})
    with pytest.raises(ValueError, match="circular"):
        replace(_scene(), final_policy_sha256="d" * 64)


def test_no_target_state_requires_zero_targets_and_positive_accepted_scan_is_not_count_limited():
    with pytest.raises(ValueError, match="no_target_detected"):
        replace(_scene(), state="no_target_detected")
    with pytest.raises(ValueError, match="accepted_scan"):
        _scene(count=0)
    assert _scene(count=0, state="no_target_detected").state == "no_target_detected"
    assert _scene(count=9).state == "accepted_scan"


def test_oof_receipt_requires_all_five_fold_policies_before_freezing():
    with pytest.raises(ValueError, match="five folds"):
        freeze_oof_receipt(evaluate_oof((_scene(),), {0: "a" * 64}))


def test_global_and_local_dino_evidence_cannot_mix_fold_or_source_identity():
    with pytest.raises(ValueError, match="DINO evidence identity"):
        replace(_scene(scene_id="different-scene"), dino_local_preprocess_sha256="d" * 64)
