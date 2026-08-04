from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from bakery_scanner.benchmarking.oof15plus5 import (
    GroundTruthObject,
    OofEvaluationRow,
    PredictionObject,
    build_counterfactual_evidence,
    build_final_development_policy,
    evaluate_oof,
    freeze_oof_receipt,
    immutable_fusion_accepts,
)
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    build_counterfactuals,
)


PROVENANCE = {"split_sha256":"1" * 64,"source_evidence_sha256":"2" * 64,"source_image_sha256":"d" * 64,"detector_sha256":"3" * 64,"repvit_checkpoint_sha256":"4" * 64,"repvit_prototype_sha256":"5" * 64,"dinov3_weights_sha256":"6" * 64,"dinov3_support_sha256":"7" * 64,"dinov3_local_bank_sha256":"8" * 64,"preprocess_sha256":"9" * 64,"fold_policy_sha256":"a" * 64,"code_sha256":"b" * 64,"runtime_sha256":"c" * 64,"dino_global_fold_index":0,"dino_local_fold_index":0,"dino_global_split_sha256":"1" * 64,"dino_local_split_sha256":"1" * 64,"dino_global_source_evidence_sha256":"2" * 64,"dino_local_source_evidence_sha256":"2" * 64,"dino_global_runtime_sha256":"c" * 64,"dino_local_runtime_sha256":"c" * 64,"dino_local_model_sha256":"6" * 64,"dino_global_preprocess_sha256":"9" * 64,"dino_local_preprocess_sha256":"9" * 64}


def _scene(*, count: int = 1, unknown: bool = False, wrong: bool = False, fold_index: int = 0, scene_id: str | None = None, state: str = "accepted_scan", expected_state: str | None = "accepted_scan", evidence_kind: str = "observed", source_scene_id: str | None = None, variant_id: str | None = None, fault_category: str | None = None, counterfactual_evidence: object | None = None, counterfactual_evidence_sha256: str | None = None, provenance_changes: dict[str, object] | None = None) -> OofEvaluationRow:
    truth = tuple(GroundTruthObject(f"g{i}", i + 1, (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1) for i in range(count))
    predictions = () if state == "needs_retake" else tuple(PredictionObject(f"p{i}", (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1, "unknown" if unknown else "auto_approved", None if unknown else (20 if wrong and i == 0 else i + 1), (1, 2, 3) if unknown else ()) for i in range(count))
    resolved_scene_id = scene_id or f"scene-{fold_index}-{count}"
    provenance = {**PROVENANCE, "dino_global_fold_index": fold_index, "dino_local_fold_index": fold_index, **(provenance_changes or {})}
    return OofEvaluationRow(scene_id=resolved_scene_id, fold_index=fold_index, role="evaluation", declared_evaluation_scene_ids=(resolved_scene_id,) if evidence_kind == "observed" else (source_scene_id or f"scene-{fold_index}-{count}",), state=state, difficulty="E", image_shape="landscape", catalog_segment="base", evidence_kind=evidence_kind, ground_truth=truth, predictions=predictions, seed=20260803, expected_state=expected_state, source_scene_id=source_scene_id or resolved_scene_id, variant_id=variant_id, fault_category=fault_category, counterfactual_evidence=counterfactual_evidence, counterfactual_evidence_sha256=counterfactual_evidence_sha256, **provenance)


def _counterfactual_scene(fault: str, *, source_image_sha256: str = "d" * 64) -> OofEvaluationRow:
    proposals = (
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.8, Box(20, 10, 20, 20), 100, 80),
    )
    case = next(item for item in build_counterfactuals(proposals) if item.fault == fault)
    variant_id = f"{fault}-v1"
    evidence = build_counterfactual_evidence(
        source_scene_id="source-0",
        source_image_sha256=source_image_sha256,
        fold_index=0,
        variant_id=variant_id,
        case=case,
        quality=CaptureQuality(100.0, 0.5, 0.0),
        policy=CompletenessPolicy(0.1, 0.5, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5),
    )
    return _scene(
        scene_id=f"source-0::counterfactual::{variant_id}",
        evidence_kind="counterfactual",
        source_scene_id="source-0",
        variant_id=variant_id,
        fault_category=fault,
        state="needs_retake",
        expected_state="needs_retake",
        counterfactual_evidence=evidence,
        counterfactual_evidence_sha256=evidence.sha256,
        provenance_changes={
            "source_image_sha256": source_image_sha256,
            "source_evidence_sha256": evidence.sha256,
            "dino_global_source_evidence_sha256": evidence.sha256,
            "dino_local_source_evidence_sha256": evidence.sha256,
        },
    )


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
    assert receipt.status == "unverified"
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
    receipt = evaluate_oof(rows, policy_by_fold)
    assert receipt.status == "unverified"
    with pytest.raises(ValueError, match="quality-accepted"):
        freeze_oof_receipt(receipt)
    with pytest.raises(ValueError, match="frozen"):
        build_final_development_policy(None, b"{}")


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


def test_missing_required_evidence_precedes_a_known_utility_floor_violation():
    base = _scene(count=10)
    predictions = tuple(
        PredictionObject(
            f"p{index}",
            (index * 20.0, 0.0, index * 20.0 + 10.0, 10.0),
            index + 1,
            "auto_approved" if index == 0 else "unknown",
            index + 1 if index == 0 else None,
            () if index == 0 else (1, 2, 3),
        )
        for index in range(10)
    )

    receipt = evaluate_oof((replace(base, predictions=predictions),), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert "counterfactual:split" in receipt.utility.missing_required_slices


def test_freeze_rejects_a_quality_rejected_five_fold_receipt():
    rows = tuple(
        _scene(wrong=fold == 0, fold_index=fold, scene_id=f"quality-{fold}")
        for fold in range(5)
    )
    receipt = evaluate_oof(rows, {fold: "a" * 64 for fold in range(5)})

    assert receipt.status == "quality-rejected"
    with pytest.raises(ValueError, match="quality-accepted"):
        freeze_oof_receipt(receipt)


def test_partial_self_declared_fold_receipt_is_unverified():
    receipt = evaluate_oof((_scene(),), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert "missing_policy_fold:1" in receipt.unverified_reasons
    assert any(reason.startswith("missing_observed_scene:0:scene_sha256:") for reason in receipt.unverified_reasons)


def test_needs_retake_cannot_carry_partial_final_predictions():
    with pytest.raises(ValueError, match="needs_retake"):
        replace(_scene(), state="needs_retake")


def test_counterfactual_requires_a_distinct_deterministic_variant_of_an_observed_scene():
    observed = _scene(scene_id="source-0")
    with pytest.raises(ValueError, match="counterfactual"):
        _scene(
        scene_id="source-0",
        count=0,
            evidence_kind="counterfactual",
            source_scene_id="source-0",
            variant_id="missing",
            fault_category="split",
            state="needs_retake",
            expected_state="needs_retake",
        )
    counterfactual = _counterfactual_scene("split")
    receipt = evaluate_oof((observed, counterfactual), {0: "a" * 64})

    assert receipt.report_slices["evidence_kind"] == {"counterfactual": 1, "observed": 1}
    assert receipt.status == "unverified"


def test_unverified_reasons_and_receipt_bytes_do_not_expose_absolute_scene_paths():
    receipt = evaluate_oof((_scene(scene_id=r"C:\private\scan.jpg"),), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert all(r"C:\private" not in reason for reason in receipt.unverified_reasons)
    assert r"C:\private" not in receipt.to_json_bytes().decode("utf-8")


def test_counterfactual_requires_each_fault_category_and_does_not_aggregate_one_category():
    observed = _scene(scene_id="source-0")
    split = _counterfactual_scene("split")
    receipt = evaluate_oof((observed, split), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert "counterfactual:merge" in receipt.utility.missing_required_slices
    with pytest.raises(ValueError, match="fault category"):
        replace(split, fault_category="non_target")


def test_linked_counterfactual_rejects_mixed_static_pipeline_provenance():
    observed = _scene(scene_id="source-0")
    counterfactual = _counterfactual_scene("merge")

    with pytest.raises(ValueError, match="linked counterfactual pipeline provenance"):
        evaluate_oof((observed, replace(counterfactual, repvit_checkpoint_sha256="d" * 64)), {0: "a" * 64})


def test_task3_counterfactual_payload_is_hash_bound_end_to_end():
    proposals = (
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),
    )
    case = next(item for item in build_counterfactuals(proposals) if item.fault == "missing")
    quality = CaptureQuality(100.0, 0.5, 0.0)
    policy = CompletenessPolicy(0.1, 0.5, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5)
    evidence = build_counterfactual_evidence(
        source_scene_id="source-0",
        source_image_sha256="d" * 64,
        fold_index=0,
        variant_id="missing-v1",
        case=case,
        quality=quality,
        policy=policy,
    )
    observed = _scene(scene_id="source-0")
    counterfactual = _scene(
        scene_id="source-0::counterfactual::missing-v1",
        evidence_kind="counterfactual",
        source_scene_id="source-0",
        variant_id="missing-v1",
        fault_category="missing",
        state="needs_retake",
        expected_state="needs_retake",
        counterfactual_evidence=evidence,
        counterfactual_evidence_sha256=evidence.sha256,
        provenance_changes={
            "source_image_sha256": "d" * 64,
            "source_evidence_sha256": evidence.sha256,
            "dino_global_source_evidence_sha256": evidence.sha256,
            "dino_local_source_evidence_sha256": evidence.sha256,
        },
    )

    receipt = evaluate_oof((observed, counterfactual), {0: "a" * 64})

    assert receipt.utility.counterfactual_completeness_block_rate["missing"] == 1.0
    assert "counterfactual:missing" not in receipt.utility.missing_required_slices
    with pytest.raises(ValueError, match="counterfactual evidence hash"):
        replace(counterfactual, counterfactual_evidence_sha256="e" * 64)


def test_counterfactual_cannot_reuse_observed_source_or_source_image_identity():
    proposals = (BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),)
    case = next(item for item in build_counterfactuals(proposals) if item.fault == "truncation")
    evidence = build_counterfactual_evidence(
        source_scene_id="source-0",
        source_image_sha256="e" * 64,
        fold_index=0,
        variant_id="truncation-v1",
        case=case,
        quality=CaptureQuality(100.0, 0.5, 0.0),
        policy=CompletenessPolicy(0.1, 0.5, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5),
    )
    observed = _scene(scene_id="source-0")
    counterfactual = _scene(
        scene_id="source-0::counterfactual::truncation-v1",
        evidence_kind="counterfactual",
        source_scene_id="source-0",
        variant_id="truncation-v1",
        fault_category="truncation",
        state="needs_retake",
        expected_state="needs_retake",
        counterfactual_evidence=evidence,
        counterfactual_evidence_sha256=evidence.sha256,
        provenance_changes={
            "source_image_sha256": "e" * 64,
            "source_evidence_sha256": evidence.sha256,
            "dino_global_source_evidence_sha256": evidence.sha256,
            "dino_local_source_evidence_sha256": evidence.sha256,
        },
    )

    with pytest.raises(ValueError, match="source image identity"):
        evaluate_oof((observed, counterfactual), {0: "a" * 64})
    with pytest.raises(ValueError, match="transformed evidence"):
        replace(
            counterfactual,
            source_evidence_sha256=observed.source_evidence_sha256,
            dino_global_source_evidence_sha256=observed.source_evidence_sha256,
            dino_local_source_evidence_sha256=observed.source_evidence_sha256,
        )


def test_four_task3_faults_have_four_independent_block_rates():
    observed = _scene(scene_id="source-0")
    counterfactuals = tuple(
        _counterfactual_scene(fault)
        for fault in ("missing", "merge", "split", "truncation")
    )

    receipt = evaluate_oof((observed, *counterfactuals), {0: "a" * 64})

    assert receipt.utility.counterfactual_completeness_block_rate == {
        "merge": 1.0,
        "missing": 1.0,
        "split": 1.0,
        "truncation": 1.0,
    }
    assert not any(reason.startswith("counterfactual:") for reason in receipt.utility.missing_required_slices)


def test_cwd_shadow_config_and_manifests_cannot_change_acceptance_sources(tmp_path, monkeypatch):
    baseline = evaluate_oof((_scene(),), {0: "a" * 64})
    shadow_config = tmp_path / "configs" / "evaluation" / "rtx5080_15plus5_oof_v1.yaml"
    shadow_config.parent.mkdir(parents=True)
    shadow_config.write_text("schema_version: 1\nutility_floors: {}\n", encoding="utf-8")
    shadow_split = tmp_path / "data" / "splits" / "rtx5080_15plus5_oof_v1"
    shadow_split.mkdir(parents=True)
    for fold in range(5):
        (shadow_split / f"fold-{fold}.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    shadowed = evaluate_oof((_scene(),), {0: "a" * 64})

    canonical_config = Path(__file__).resolve().parents[2] / "configs" / "evaluation" / "rtx5080_15plus5_oof_v1.yaml"
    assert shadowed.acceptance_sources == baseline.acceptance_sources
    assert shadowed.utility == baseline.utility
    assert shadowed.acceptance_sources.utility_config_sha256 == hashlib.sha256(canonical_config.read_bytes()).hexdigest()


def test_freeze_rejects_receipt_whose_canonical_acceptance_source_hash_was_forged():
    receipt = evaluate_oof((_scene(),), {0: "a" * 64})
    source_payload = dict(receipt.acceptance_sources.canonical_payload(include_combined=False))
    source_payload["utility_config_sha256"] = "f" * 64
    combined_sha256 = hashlib.sha256(
        json.dumps(source_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    forged = replace(
        receipt,
        acceptance_sources=replace(
            receipt.acceptance_sources,
            utility_config_sha256="f" * 64,
            combined_sha256=combined_sha256,
        ),
    )

    with pytest.raises(ValueError, match="canonical acceptance source"):
        freeze_oof_receipt(forged)


def test_evaluation_row_must_cross_bind_canonical_config_and_manifest_file_hashes():
    baseline = evaluate_oof((_scene(),), {0: "a" * 64})
    sources = baseline.acceptance_sources
    bound = replace(
        _scene(),
        acceptance_config_sha256=sources.utility_config_sha256,
        fold_manifest_file_sha256=sources.fold_manifest_file_sha256[0],
    )

    receipt = evaluate_oof((bound,), {0: "a" * 64})

    assert not any(reason.startswith("acceptance_config_identity_mismatch") for reason in receipt.unverified_reasons)
    assert not any(reason.startswith("manifest_file_identity_mismatch") for reason in receipt.unverified_reasons)
    assert any(reason.startswith("split_identity_mismatch") for reason in receipt.unverified_reasons)
