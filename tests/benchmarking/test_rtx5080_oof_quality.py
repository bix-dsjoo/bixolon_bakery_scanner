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
    build_counterfactual_source_evidence,
    build_final_development_policy,
    evaluate_oof,
    freeze_oof_receipt,
    immutable_fusion_accepts,
)
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    ForegroundEvidence,
    build_counterfactuals,
)
from bakery_scanner.detection.completeness_evidence import (
    REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS,
    build_completeness_execution_record,
    write_completeness_evidence_bundle,
)


PROVENANCE = {"split_sha256":"1" * 64,"source_evidence_sha256":"2" * 64,"source_image_sha256":"d" * 64,"detector_sha256":"3" * 64,"repvit_checkpoint_sha256":"4" * 64,"repvit_prototype_sha256":"5" * 64,"dinov3_weights_sha256":"6" * 64,"dinov3_support_sha256":"7" * 64,"dinov3_local_bank_sha256":"8" * 64,"preprocess_sha256":"9" * 64,"fold_policy_sha256":"a" * 64,"code_sha256":"b" * 64,"runtime_sha256":"c" * 64,"dino_global_fold_index":0,"dino_local_fold_index":0,"dino_global_split_sha256":"1" * 64,"dino_local_split_sha256":"1" * 64,"dino_global_source_evidence_sha256":"2" * 64,"dino_local_source_evidence_sha256":"2" * 64,"dino_global_runtime_sha256":"c" * 64,"dino_local_runtime_sha256":"c" * 64,"dino_local_model_sha256":"6" * 64,"dino_global_preprocess_sha256":"9" * 64,"dino_local_preprocess_sha256":"9" * 64}


def _scene(*, count: int = 1, unknown: bool = False, wrong: bool = False, fold_index: int = 0, scene_id: str | None = None, state: str = "accepted_scan", expected_state: str | None = "accepted_scan", evidence_kind: str = "observed", source_scene_id: str | None = None, variant_id: str | None = None, fault_category: str | None = None, counterfactual_evidence: object | None = None, counterfactual_evidence_sha256: str | None = None, actual_retake_reasons: tuple[str, ...] | None = None, provenance_changes: dict[str, object] | None = None) -> OofEvaluationRow:
    truth = tuple(GroundTruthObject(f"g{i}", i + 1, (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1) for i in range(count))
    predictions = () if state == "needs_retake" else tuple(PredictionObject(f"p{i}", (i * 20.0, 0.0, i * 20.0 + 10.0, 10.0), i + 1, "unknown" if unknown else "auto_approved", None if unknown else (20 if wrong and i == 0 else i + 1), (1, 2, 3) if unknown else ()) for i in range(count))
    resolved_scene_id = scene_id or f"scene-{fold_index}-{count}"
    provenance = {**PROVENANCE, "dino_global_fold_index": fold_index, "dino_local_fold_index": fold_index, **(provenance_changes or {})}
    return OofEvaluationRow(scene_id=resolved_scene_id, fold_index=fold_index, role="evaluation", declared_evaluation_scene_ids=(resolved_scene_id,) if evidence_kind == "observed" else (source_scene_id or f"scene-{fold_index}-{count}",), state=state, difficulty="E", image_shape="landscape", catalog_segment="base", evidence_kind=evidence_kind, ground_truth=truth, predictions=predictions, seed=20260803, expected_state=expected_state, source_scene_id=source_scene_id or resolved_scene_id, variant_id=variant_id, fault_category=fault_category, counterfactual_evidence=counterfactual_evidence, counterfactual_evidence_sha256=counterfactual_evidence_sha256, actual_retake_reasons=actual_retake_reasons, **provenance)


def _counterfactual_scene(fault: str, *, source_image_sha256: str = "d" * 64) -> OofEvaluationRow:
    source, _ = _canonical_counterfactual_source(source_image_sha256=source_image_sha256)
    case = next(item for item in build_counterfactuals(source.proposals) if item.fault == fault)
    evidence = build_counterfactual_evidence(source=source, case=case)
    variant_id = evidence.variant_id
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
        actual_retake_reasons=evidence.decision_reasons,
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
    _, observed = _canonical_counterfactual_source()
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


def test_counterfactual_requires_each_fault_category_and_does_not_aggregate_one_category(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    split = next(row for row in counterfactuals if row.fault_category == "split")
    receipt = evaluate_oof(
        (observed, split),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

    assert receipt.status == "unverified"
    assert receipt.utility.counterfactual_expected_case_count["merge"] == 1
    assert receipt.utility.counterfactual_completeness_block_rate["merge"] == 0.0
    assert any("merge-0-1" in reason for reason in receipt.utility.missing_required_slices)
    with pytest.raises(ValueError, match="fault category"):
        replace(split, fault_category="non_target")


def test_linked_counterfactual_rejects_mixed_static_pipeline_provenance():
    _, observed = _canonical_counterfactual_source()
    counterfactual = _counterfactual_scene("merge")

    with pytest.raises(ValueError, match="linked counterfactual pipeline provenance"):
        evaluate_oof((observed, replace(counterfactual, repvit_checkpoint_sha256="d" * 64)), {0: "a" * 64})


def test_task3_counterfactual_payload_is_hash_bound_end_to_end(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path, count=1)
    counterfactual = next(row for row in counterfactuals if row.fault_category == "missing")

    receipt = evaluate_oof(
        (observed, counterfactual),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

    assert receipt.utility.counterfactual_completeness_block_rate["missing"] == 1.0
    assert "counterfactual:missing" not in receipt.utility.missing_required_slices
    with pytest.raises(ValueError, match="counterfactual evidence hash"):
        replace(counterfactual, counterfactual_evidence_sha256="e" * 64)


def test_counterfactual_cannot_reuse_observed_source_or_source_image_identity():
    proposals = (BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),)
    case = next(item for item in build_counterfactuals(proposals) if item.fault == "truncation")
    evidence = build_counterfactual_evidence(
        source=build_counterfactual_source_evidence(
            source_scene_id="source-0",
            source_image_sha256="e" * 64,
            fold_index=0,
            frame_size=(100, 80),
            proposals=proposals,
            foreground=ForegroundEvidence(0.0, 1.0, (), (), (), 0.0),
            quality=CaptureQuality(100.0, 0.5, 0.0),
            policy=CompletenessPolicy(0.1, 0.5, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5),
        ),
        case=case,
    )
    observed = _scene(scene_id="source-0")
    counterfactual = _scene(
        scene_id=f"source-0::counterfactual::{evidence.variant_id}",
        evidence_kind="counterfactual",
        source_scene_id="source-0",
        variant_id=evidence.variant_id,
        fault_category="truncation",
        state="needs_retake",
        expected_state="needs_retake",
        counterfactual_evidence=evidence,
        counterfactual_evidence_sha256=evidence.sha256,
        actual_retake_reasons=evidence.decision_reasons,
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


def test_four_task3_faults_have_four_independent_block_rates(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)

    receipt = evaluate_oof(
        (observed, *counterfactuals),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

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


def test_forged_partial_receipt_cannot_be_promoted_and_frozen():
    receipt = evaluate_oof((_scene(),), {0: "a" * 64})
    forged = replace(
        receipt,
        status="quality-accepted",
        utility=replace(
            receipt.utility,
            missing_required_slices=(),
            has_violation=False,
            passes=True,
        ),
        policy_by_fold={fold: "a" * 64 for fold in range(5)},
        provenance_by_fold={fold: receipt.provenance_by_fold[0] for fold in range(5)},
    )

    with pytest.raises(ValueError, match="authoritative evaluation"):
        freeze_oof_receipt(forged)


def test_counterfactual_rows_cannot_change_observed_primary_quality_or_bounds():
    _, observed = _canonical_counterfactual_source()
    baseline = evaluate_oof((observed,), {0: "a" * 64})
    with_stress = evaluate_oof((observed, _counterfactual_scene("missing")), {0: "a" * 64})

    assert with_stress.quality == baseline.quality
    assert with_stress.scene_count == baseline.scene_count == 1
    assert with_stress.object_count == baseline.object_count == 2
    assert with_stress.top3_rank_hits == baseline.top3_rank_hits
    assert with_stress.object_count_slices == baseline.object_count_slices


def _canonical_counterfactual_source(*, source_image_sha256: str = "d" * 64):
    proposals = (
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.8, Box(20, 10, 20, 20), 100, 80),
    )
    source = build_counterfactual_source_evidence(
        source_scene_id="source-0",
        source_image_sha256=source_image_sha256,
        fold_index=0,
        frame_size=(100, 80),
        proposals=proposals,
        foreground=ForegroundEvidence(0.0, 1.0, (), (), (), 0.0),
        quality=CaptureQuality(100.0, 0.5, 0.0),
        policy=CompletenessPolicy(0.1, 0.6, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5),
    )
    truth = (
        GroundTruthObject("g0", 1, (10.0, 10.0, 30.0, 30.0), 1),
        GroundTruthObject("g1", 2, (20.0, 10.0, 40.0, 30.0), 2),
    )
    predictions = (
        PredictionObject("p0", truth[0].box_xyxy, 1, "auto_approved", 1, ()),
        PredictionObject("p1", truth[1].box_xyxy, 2, "auto_approved", 2, ()),
    )
    observed = replace(
        _scene(count=2, scene_id="source-0"),
        ground_truth=truth,
        predictions=predictions,
        source_image_sha256=source_image_sha256,
        counterfactual_source_evidence=source,
    )
    return source, observed


def _canonical_counterfactual_row(source, case, *, state="needs_retake"):
    evidence = build_counterfactual_evidence(source=source, case=case)
    return _scene(
        scene_id=f"source-0::counterfactual::{evidence.variant_id}",
        evidence_kind="counterfactual",
        source_scene_id="source-0",
        variant_id=evidence.variant_id,
        fault_category=evidence.fault,
        state=state,
        expected_state="needs_retake",
        counterfactual_evidence=evidence,
        counterfactual_evidence_sha256=evidence.sha256,
        actual_retake_reasons=evidence.decision_reasons if state == "needs_retake" else (),
        provenance_changes={
            "source_image_sha256": "d" * 64,
            "source_evidence_sha256": evidence.sha256,
            "dino_global_source_evidence_sha256": evidence.sha256,
            "dino_local_source_evidence_sha256": evidence.sha256,
        },
    )


def test_counterfactual_builder_rejects_unrelated_transform_and_capture_quality_masquerade():
    source, _ = _canonical_counterfactual_source()
    unrelated = build_counterfactuals((
        BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(50, 40, 10, 10), 100, 80),
    ))[0]

    with pytest.raises(ValueError, match="canonical source transform"):
        build_counterfactual_evidence(source=source, case=unrelated)
    with pytest.raises(ValueError, match="capture-quality|accepted observed source"):
        build_counterfactual_source_evidence(
            source_scene_id="source-0",
            source_image_sha256="d" * 64,
            fold_index=0,
            frame_size=(100, 80),
            proposals=(BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(10, 10, 20, 20), 100, 80),),
            foreground=ForegroundEvidence(0.0, 1.0, (), (), (), 0.0),
            quality=CaptureQuality(0.0, 0.5, 0.0),
            policy=CompletenessPolicy(0.1, 0.6, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5),
        )


def test_counterfactual_completeness_uses_all_expected_source_variants_as_denominator(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    submitted = next(row for row in counterfactuals if row.variant_id == "missing-0")

    receipt = evaluate_oof(
        (observed, submitted),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

    assert receipt.status == "unverified"
    assert receipt.utility.counterfactual_expected_case_count == {
        "merge": 1,
        "missing": 2,
        "split": 2,
        "truncation": 2,
    }
    assert receipt.utility.counterfactual_submitted_case_count["missing"] == 1
    assert receipt.utility.counterfactual_completeness_block_rate["missing"] == 0.5
    assert any(reason.startswith("missing_counterfactual_variant:") for reason in receipt.unverified_reasons)


def test_missing_counterfactual_source_descriptor_is_explicitly_unverified():
    receipt = evaluate_oof((_scene(scene_id="source-without-proposals"),), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert any(reason.startswith("counterfactual_source_unavailable:") for reason in receipt.unverified_reasons)


def test_counterfactual_actual_result_and_reason_determine_stress_success_without_touching_quality(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    missing = next(row for row in counterfactuals if row.variant_id == "missing-0")
    accepted = replace(missing, state="accepted_scan", actual_retake_reasons=())
    wrong_reason = replace(
        missing,
        actual_retake_reasons=("capture_quality_unverified",),
    )

    accepted_receipt = evaluate_oof(
        (observed, accepted),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )
    assert accepted_receipt.utility.counterfactual_completeness_block_rate["missing"] == 0.0
    assert accepted_receipt.quality.wrong_auto_approval_count == 0
    wrong_reason_receipt = evaluate_oof(
        (observed, wrong_reason),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )
    assert wrong_reason_receipt.utility.counterfactual_completeness_block_rate["missing"] == 0.0


def _execution_artifacts(provenance: dict[str, object] | None = None) -> dict[str, str]:
    resolved = {
        **PROVENANCE,
        "acceptance_config_sha256": "0" * 64,
        "fold_manifest_file_sha256": "f" * 64,
        **(provenance or {}),
    }
    return {
        key: resolved[key]  # type: ignore[return-value]
        for key in REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS
    }


def _admitted_counterfactual_context(tmp_path, *, count: int = 2):
    proposals = tuple(
        BreadProposal(
            index + 1,
            "rfdetr_large_bakery_v1",
            0.99 - index * 0.01,
            Box(100.0 + index * 40.0, 120.0, 60.0, 60.0),
            1000,
            800,
        )
        for index in range(count)
    )
    foreground = ForegroundEvidence(0.0, 1.0, (), (), (), 0.0)
    quality = CaptureQuality(100.0, 0.5, 0.0)
    policy = CompletenessPolicy(0.1, 0.6, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5)
    record = build_completeness_execution_record(
        source_scene_identity="admitted-source-0",
        source_image_sha256="d" * 64,
        fold_index=0,
        canonical_frame_version="exif_transposed_rgb_v1",
        canonical_frame_mode="RGB",
        frame_size=(1000, 800),
        proposals=proposals,
        foreground=foreground,
        quality=quality,
        policy=policy,
        completeness_policy_id="completeness_15plus5_oof_fold_0_v1",
        completeness_policy_artifact_sha256="e" * 64,
        code_sha256=PROVENANCE["code_sha256"],
        input_artifact_sha256=_execution_artifacts(),
    )
    evidence_root = tmp_path / f"completeness-{count}"
    index_sha256 = write_completeness_evidence_bundle((record,), evidence_root)
    source = build_counterfactual_source_evidence(
        source_scene_id="admitted-source-0",
        source_image_sha256="d" * 64,
        fold_index=0,
        frame_size=(1000, 800),
        proposals=proposals,
        foreground=foreground,
        quality=quality,
        policy=policy,
        execution_record_sha256=record.sha256,
        completeness_policy_id="completeness_15plus5_oof_fold_0_v1",
        completeness_policy_artifact_sha256="e" * 64,
    )
    truth = tuple(
        GroundTruthObject(f"g{index}", index + 1, proposal.box.xyxy, index + 1)
        for index, proposal in enumerate(proposals)
    )
    predictions = tuple(
        PredictionObject(f"p{index}", item.box_xyxy, index + 1, "auto_approved", index + 1, ())
        for index, item in enumerate(truth)
    )
    binding = {
        "completeness_evidence_index_sha256": index_sha256,
        "completeness_execution_record_sha256": record.sha256,
        "canonical_frame_version": "exif_transposed_rgb_v1",
        "canonical_frame_mode": "RGB",
        "canonical_frame_size": (1000, 800),
        "acceptance_config_sha256": "0" * 64,
        "fold_manifest_file_sha256": "f" * 64,
    }
    observed = replace(
        _scene(count=count, scene_id="admitted-source-0"),
        ground_truth=truth,
        predictions=predictions,
        counterfactual_source_evidence=source,
        **binding,
    )
    counterfactuals = tuple(
        replace(
            _scene(
                scene_id=f"admitted-source-0::counterfactual::{case.variant_id}",
                evidence_kind="counterfactual",
                source_scene_id="admitted-source-0",
                variant_id=case.variant_id,
                fault_category=case.fault,
                state="needs_retake",
                expected_state="needs_retake",
                counterfactual_evidence=(evidence := build_counterfactual_evidence(source=source, case=case)),
                counterfactual_evidence_sha256=evidence.sha256,
                actual_retake_reasons=evidence.decision_reasons,
                provenance_changes={
                    "source_image_sha256": "d" * 64,
                    "source_evidence_sha256": evidence.sha256,
                    "dino_global_source_evidence_sha256": evidence.sha256,
                    "dino_local_source_evidence_sha256": evidence.sha256,
                },
            ),
            **binding,
        )
        for case in build_counterfactuals(proposals)
    )
    return evidence_root, index_sha256, record, source, observed, counterfactuals


def test_hash_admitted_actual_completeness_execution_is_the_only_counterfactual_source(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)

    receipt = evaluate_oof(
        (observed, *counterfactuals),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

    assert receipt.utility.counterfactual_completeness_block_rate == {
        "merge": 1.0,
        "missing": 1.0,
        "split": 1.0,
        "truncation": 1.0,
    }
    assert receipt.completeness_evidence_index_sha256 == hashlib.sha256(
        (root / "index.json").read_bytes()
    ).hexdigest()
    assert str(root) not in receipt.to_json_bytes().decode("utf-8")


@pytest.mark.parametrize("count", (1, 2, 8))
def test_oof_admits_positive_source_counts_without_a_static_capacity_limit(tmp_path, count: int):
    root, _, _, _, observed, _ = _admitted_counterfactual_context(tmp_path, count=count)

    receipt = evaluate_oof(
        (observed,),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )

    assert not any(
        reason.startswith("counterfactual_source_unavailable")
        for reason in receipt.unverified_reasons
    )
    assert receipt.utility.counterfactual_expected_case_count["missing"] == count


def test_self_declared_hash_consistent_descriptor_without_external_record_is_unverified(tmp_path):
    _, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)

    receipt = evaluate_oof((observed, *counterfactuals), {0: "a" * 64})

    assert receipt.status == "unverified"
    assert receipt.utility.counterfactual_expected_case_count == {
        "merge": 0,
        "missing": 0,
        "split": 0,
        "truncation": 0,
    }
    assert any(
        reason.startswith("completeness_evidence_unavailable")
        for reason in receipt.unverified_reasons
    )


def test_nonaccepted_observed_source_is_rejected_before_counterfactual_denominators(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    nonaccepted = replace(observed, state="needs_retake", expected_state="needs_retake", predictions=())

    with pytest.raises(ValueError, match="accepted_scan"):
        evaluate_oof(
            (nonaccepted, *counterfactuals),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )


def test_execution_or_index_hash_mismatch_is_rejected_before_counting(tmp_path):
    root, _, _, source, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    wrong_record = replace(
        observed,
        completeness_execution_record_sha256="a" * 64,
        counterfactual_source_evidence=replace(source, execution_record_sha256="a" * 64),
    )

    with pytest.raises(ValueError, match="record SHA-256"):
        evaluate_oof(
            (wrong_record, *counterfactuals),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )
    with pytest.raises(ValueError, match="index SHA-256"):
        evaluate_oof(
            (replace(observed, completeness_evidence_index_sha256="a" * 64), *counterfactuals),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )


def test_absent_index_record_is_rejected_before_counterfactual_denominators(tmp_path):
    root, _, record, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    other_record = replace(
        record,
        source_scene_sha256=hashlib.sha256(b"other-source").hexdigest(),
    )
    other_root = tmp_path / "other-completeness"
    other_index_sha256 = write_completeness_evidence_bundle((other_record,), other_root)
    absent = replace(observed, completeness_evidence_index_sha256=other_index_sha256)

    with pytest.raises(ValueError, match="absent from admitted index"):
        evaluate_oof(
            (absent, *counterfactuals),
            {0: "a" * 64},
            completeness_evidence_root=other_root,
        )


def test_actual_needs_retake_execution_record_can_never_be_a_counterfactual_source(tmp_path):
    _, _, accepted_record, source, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    retake_record = build_completeness_execution_record(
        source_scene_identity="admitted-source-0",
        source_image_sha256="d" * 64,
        fold_index=0,
        canonical_frame_version="exif_transposed_rgb_v1",
        canonical_frame_mode="RGB",
        frame_size=accepted_record.frame_size,
        proposals=tuple(item.to_proposal() for item in accepted_record.proposals),
        foreground=accepted_record.foreground,
        quality=replace(accepted_record.quality, blur_score=0.0),
        policy=accepted_record.policy,
        completeness_policy_id=accepted_record.completeness_policy_id,
        completeness_policy_artifact_sha256=accepted_record.completeness_policy_artifact_sha256,
        code_sha256=accepted_record.code_sha256,
        input_artifact_sha256=dict(accepted_record.input_artifact_sha256),
    )
    assert retake_record.decision_state == "needs_retake"
    root = tmp_path / "retake-completeness"
    index_sha256 = write_completeness_evidence_bundle((retake_record,), root)
    forged = replace(
        observed,
        completeness_evidence_index_sha256=index_sha256,
        completeness_execution_record_sha256=retake_record.sha256,
        counterfactual_source_evidence=replace(
            source,
            execution_record_sha256=retake_record.sha256,
        ),
    )

    with pytest.raises(ValueError, match="accepted_scan"):
        evaluate_oof(
            (forged, *counterfactuals),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )


@pytest.mark.parametrize("target", ("record", "index"))
def test_freeze_reloads_external_completeness_bytes_and_detects_post_evaluation_mutation(tmp_path, target: str):
    root, _, record, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    receipt = evaluate_oof(
        (observed, *counterfactuals),
        {0: "a" * 64},
        completeness_evidence_root=root,
    )
    path = (
        root / "records" / f"{record.source_scene_sha256}.json"
        if target == "record"
        else root / "index.json"
    )
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="(record byte size|index SHA-256)"):
        freeze_oof_receipt(receipt)


def test_counterfactual_row_cannot_change_its_admitted_source_binding(tmp_path):
    root, _, _, _, observed, counterfactuals = _admitted_counterfactual_context(tmp_path)
    changed = replace(
        counterfactuals[0],
        completeness_execution_record_sha256="a" * 64,
    )

    with pytest.raises(ValueError, match="binding does not match observed source"):
        evaluate_oof(
            (observed, changed),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "image",
        "frame",
        "proposal_source",
        "proposal_id",
        "proposal_score",
        "proposal_box",
        "foreground",
        "quality",
        "policy",
        "policy_identity",
        "static_pipeline",
    ),
)
def test_observed_descriptor_must_exactly_equal_loaded_execution_evidence(tmp_path, mutation: str):
    root, _, record, source, observed, _ = _admitted_counterfactual_context(tmp_path)
    proposals = source.proposals
    foreground = source.foreground
    quality = source.quality
    policy = source.policy
    source_image_sha256 = source.source_image_sha256
    frame_size = source.frame_size
    policy_id = source.completeness_policy_id
    policy_artifact_sha256 = source.completeness_policy_artifact_sha256
    row_changes: dict[str, object] = {}
    if mutation == "image":
        source_image_sha256 = "a" * 64
        row_changes["source_image_sha256"] = source_image_sha256
    elif mutation == "frame":
        frame_size = (2000, 1600)
        proposals = tuple(replace(item, image_width=2000, image_height=1600) for item in proposals)
        row_changes["canonical_frame_size"] = frame_size
    elif mutation == "proposal_source":
        proposals = (replace(proposals[0], source="different-detector"), *proposals[1:])
    elif mutation == "proposal_id":
        proposals = (replace(proposals[0], image_id=999), *proposals[1:])
    elif mutation == "proposal_score":
        proposals = (replace(proposals[0], score=0.1), *proposals[1:])
    elif mutation == "proposal_box":
        proposals = (replace(proposals[0], box=Box(110.0, 120.0, 60.0, 60.0)), *proposals[1:])
        ordered_truth = tuple(sorted(observed.ground_truth, key=lambda item: item.object_order))
        row_changes["ground_truth"] = (
            replace(ordered_truth[0], box_xyxy=proposals[0].box.xyxy),
            *ordered_truth[1:],
        )
    elif mutation == "foreground":
        foreground = replace(foreground, covered_ratio=0.9)
    elif mutation == "quality":
        quality = replace(quality, blur_score=101.0)
    elif mutation == "policy":
        policy = replace(policy, max_uncovered_ratio=0.2)
    elif mutation == "policy_identity":
        policy_id = "different_policy_v1"
        policy_artifact_sha256 = "a" * 64
    elif mutation == "static_pipeline":
        row_changes["detector_sha256"] = "a" * 64
    fake_source = build_counterfactual_source_evidence(
        source_scene_id="admitted-source-0",
        source_image_sha256=source_image_sha256,
        fold_index=0,
        frame_size=frame_size,
        proposals=proposals,
        foreground=foreground,
        quality=quality,
        policy=policy,
        execution_record_sha256=record.sha256,
        completeness_policy_id=policy_id,
        completeness_policy_artifact_sha256=policy_artifact_sha256,
    )
    forged = replace(observed, counterfactual_source_evidence=fake_source, **row_changes)

    with pytest.raises(ValueError, match="completeness execution evidence"):
        evaluate_oof(
            (forged,),
            {0: "a" * 64},
            completeness_evidence_root=root,
        )
