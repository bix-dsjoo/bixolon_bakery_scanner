"""Hermetic acceptance tests for fail-closed RPC evidence scoring."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import random

import pytest

from bakery_scanner.experiments import rpc_metrics
from bakery_scanner.experiments.rpc_metrics import (
    ResearchEvidenceRow,
    bootstrap_paired_deltas,
    branch_top1_summary,
    full_system_summary,
    passes_minimum_rule,
    validate_evidence_against_condition,
    validate_paired_evidence,
    _hierarchical_sample,
)


_HASHES = {
    "condition_manifest_sha256": "a" * 64,
    "model_sha256": "b" * 64,
    "support_sha256": "c" * 64,
    "calibration_sha256": "d" * 64,
    "policy_sha256": "e" * 64,
    "preprocessing_sha256": "f" * 64,
    "code_sha256": "0" * 64,
}


def _row(
    sample_id: str,
    *,
    object_id: int | None = None,
    truth: int = 1,
    predicted: int | None = 1,
    repvit_global_scores: tuple[float, ...] = (0.9, 0.1),
    dinov3_global_scores: tuple[float, ...] | None = None,
    dinov3_local_scores: tuple[float, ...] | None = None,
    category_ids: tuple[int, ...] = (1, 2),
    fold: int = 0,
    difficulty: str = "E",
    burst_id: str = "burst-a",
    condition_id: str = "candidate",
    conditional_dino_executed: bool = False,
) -> ResearchEvidenceRow:
    resolved_object_id = object_id
    if resolved_object_id is None:
        resolved_object_id = (
            int.from_bytes(hashlib.sha256(sample_id.encode("utf-8")).digest()[:8], "big")
            + 1
        )
    return ResearchEvidenceRow(
        sample_id=sample_id,
        object_id=resolved_object_id,
        condition_id=condition_id,
        fold=fold,
        difficulty=difficulty,
        burst_id=burst_id,
        truth_category_id=truth,
        predicted_category_id=predicted,
        score_category_ids=category_ids,
        repvit_global_scores=repvit_global_scores,
        dinov3_global_scores=(
            repvit_global_scores
            if dinov3_global_scores is None
            else dinov3_global_scores
        ),
        dinov3_local_scores=(
            repvit_global_scores if dinov3_local_scores is None else dinov3_local_scores
        ),
        conditional_dino_executed=conditional_dino_executed,
        **_HASHES,
    )


def test_unknown_only_candidate_cannot_pass_despite_safety_gain():
    reference = (_row("n", truth=1, predicted=2), _row("b", truth=2, predicted=2))
    candidate = (_row("n", truth=1, predicted=None), _row("b", truth=2, predicted=None))
    candidate_summary = full_system_summary(candidate, novel_category_ids={1})
    reference_summary = full_system_summary(reference, novel_category_ids={1})
    interval = bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=9, replicates=20)

    assert candidate_summary.wrong_registered_sku_rate == 0.0
    assert not passes_minimum_rule(
        candidate_summary,
        reference_summary,
        interval,
        base_checkpoint_macro_recall=1.0,
    )


def test_branch_and_full_summaries_report_selection_and_conditional_dino_metrics():
    rows = (
        _row("novel-ok", truth=1, predicted=1, conditional_dino_executed=True),
        _row("base-wrong", truth=2, predicted=1, conditional_dino_executed=False),
    )

    branch = branch_top1_summary(rows, branch="repvit_global", novel_category_ids={1})
    full = full_system_summary(rows, novel_category_ids={1})

    assert branch.confusion_matrix == {1: {1: 1}, 2: {1: 1}}
    assert branch.fifth_percentile_sku_accuracy == 0.05
    assert branch.wrong_registered_sku_rate == 0.5
    assert full.conditional_dino_execution_rate == 0.5


def test_evidence_row_requires_a_boolean_conditional_dino_execution_value():
    payload = _row("dino").to_dict()
    payload.pop("conditional_dino_executed")
    with pytest.raises(ValueError, match="missing or unrecognized"):
        ResearchEvidenceRow.from_dict(payload)
    payload = _row("dino-two").to_dict()
    payload["conditional_dino_executed"] = "yes"
    with pytest.raises(ValueError, match="invalid evidence row"):
        ResearchEvidenceRow.from_dict(payload)


def test_minimum_rule_accepts_exact_boundaries():
    reference = tuple(_row(f"n-{index}", truth=1, predicted=1, burst_id=str(index)) for index in range(100)) + tuple(
        _row(f"b-{index}", truth=2, predicted=2, burst_id=str(index)) for index in range(100)
    )
    candidate = tuple(
        _row(f"n-{index}", truth=1, predicted=1 if index < 98 else 2, burst_id=str(index))
        for index in range(100)
    ) + tuple(
        _row(f"b-{index}", truth=2, predicted=2 if index < 99 else 1, burst_id=str(index))
        for index in range(100)
    )
    candidate_summary = full_system_summary(candidate, novel_category_ids={1})
    reference_summary = full_system_summary(reference, novel_category_ids={1})
    interval = replace(
        bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=8, replicates=10),
        novel_macro_recall_lower_delta=-0.02,
        novel_wrong_registered_sku_rate_upper_delta=0.005,
    )

    assert candidate_summary.novel_loss_over_10pp_fraction == 0.0
    assert passes_minimum_rule(
        candidate_summary,
        reference_summary,
        interval,
        base_checkpoint_macro_recall=1.0,
    )


def test_minimum_rule_compares_base_recall_to_frozen_fold_checkpoint_not_reference():
    reference = (_row("n", truth=1, predicted=1), _row("b", truth=2, predicted=1))
    candidate = (_row("n", truth=1, predicted=1), _row("b", truth=2, predicted=1))
    candidate_summary = full_system_summary(candidate, novel_category_ids={1})
    reference_summary = full_system_summary(reference, novel_category_ids={1})
    interval = bootstrap_paired_deltas(
        candidate,
        reference,
        novel_category_ids={1},
        seed=9,
        replicates=10,
    )

    assert not passes_minimum_rule(
        candidate_summary,
        reference_summary,
        interval,
        base_checkpoint_macro_recall=1.0,
    )


def test_paired_validation_rejects_identity_and_provenance_mismatches():
    candidate = (_row("same"),)
    reference = (_row("same", condition_id="reference"),)
    validate_paired_evidence(candidate, reference)

    with pytest.raises(ValueError, match="paired identity"):
        validate_paired_evidence(candidate, (_row("other", condition_id="reference"),))
    with pytest.raises(ValueError, match="provenance"):
        validate_paired_evidence(
            candidate
            + (replace(_row("same-2"), policy_sha256="1" * 64),),
            reference + (_row("same-2", condition_id="reference"),),
        )
    with pytest.raises(ValueError, match="duplicate object_id"):
        validate_paired_evidence(candidate + candidate, reference + reference)


def test_evidence_schema_binds_each_prediction_to_a_ground_truth_object():
    payload = _row("scene").to_dict()
    payload["object_id"] = 17

    row = ResearchEvidenceRow.from_dict(payload)

    assert row.object_id == 17
    assert row.to_dict()["object_id"] == 17


def _three_branch_payload(
    sample_id: str,
    *,
    object_id: int,
    truth_category_id: int,
    repvit_global_scores: list[float],
    dinov3_global_scores: list[float],
    dinov3_local_scores: list[float],
) -> dict[str, object]:
    payload = _row(
        sample_id,
        object_id=object_id,
        truth=truth_category_id,
        predicted=truth_category_id,
        category_ids=(1, 2, 3),
        repvit_global_scores=tuple(repvit_global_scores),
        dinov3_global_scores=tuple(dinov3_global_scores),
        dinov3_local_scores=tuple(dinov3_local_scores),
    ).to_dict()
    return payload


def test_evidence_requires_three_branch_vectors_and_has_no_generic_fallback():
    complete = _three_branch_payload(
        "novel",
        object_id=1,
        truth_category_id=1,
        repvit_global_scores=[0.9, 0.05, 0.05],
        dinov3_global_scores=[0.1, 0.8, 0.1],
        dinov3_local_scores=[0.1, 0.2, 0.7],
    )

    parsed = ResearchEvidenceRow.from_dict(complete)

    assert parsed.to_dict()["repvit_global_scores"] == [0.9, 0.05, 0.05]
    generic = dict(complete)
    generic["scores"] = generic.pop("repvit_global_scores")
    with pytest.raises(ValueError, match="missing or unrecognized"):
        ResearchEvidenceRow.from_dict(generic)
    missing = dict(complete)
    del missing["dinov3_local_scores"]
    with pytest.raises(ValueError, match="missing or unrecognized"):
        ResearchEvidenceRow.from_dict(missing)
    wrong_length = dict(complete)
    wrong_length["dinov3_global_scores"] = [1.0]
    with pytest.raises(ValueError):
        ResearchEvidenceRow.from_dict(wrong_length)


def test_branch_top1_summaries_are_independent_and_report_global_agreement():
    rows = tuple(
        ResearchEvidenceRow.from_dict(payload)
        for payload in (
            _three_branch_payload(
                "novel",
                object_id=1,
                truth_category_id=1,
                repvit_global_scores=[0.9, 0.05, 0.05],
                dinov3_global_scores=[0.1, 0.8, 0.1],
                dinov3_local_scores=[0.1, 0.2, 0.7],
            ),
            _three_branch_payload(
                "base",
                object_id=2,
                truth_category_id=2,
                repvit_global_scores=[0.1, 0.8, 0.1],
                dinov3_global_scores=[0.1, 0.8, 0.1],
                dinov3_local_scores=[0.8, 0.1, 0.1],
            ),
        )
    )

    repvit = rpc_metrics.branch_top1_summary(
        rows, branch="repvit_global", novel_category_ids={1}
    )
    dino_global = rpc_metrics.branch_top1_summary(
        rows, branch="dinov3_global", novel_category_ids={1}
    )
    dino_local = rpc_metrics.branch_top1_summary(
        rows, branch="dinov3_local", novel_category_ids={1}
    )

    assert (repvit.novel_macro_recall, repvit.base_macro_recall) == (1.0, 1.0)
    assert (dino_global.novel_macro_recall, dino_global.base_macro_recall) == (
        0.0,
        1.0,
    )
    assert (dino_local.novel_macro_recall, dino_local.base_macro_recall) == (
        0.0,
        0.0,
    )
    assert (
        rpc_metrics.branch_top1_agreement(
            rows, first="repvit_global", second="dinov3_global"
        )
        == 0.5
    )


def test_locked_ground_truth_allows_multiple_objects_per_sample_and_exact_coverage():
    expected = (
        rpc_metrics.LockedGroundTruthRow("scene", 11, "burst-a", "E", 1),
        rpc_metrics.LockedGroundTruthRow("scene", 12, "burst-a", "E", 2),
    )
    rows = (
        _row("scene", object_id=11, truth=1),
        _row("scene", object_id=12, truth=2, predicted=2),
    )

    assert rpc_metrics.validate_evidence_completeness(rows, expected) == rows


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:1],
        lambda rows: rows + (_row("scene", object_id=13, truth=1),),
        lambda rows: (rows[0], replace(rows[1], burst_id="burst-b")),
        lambda rows: (rows[0], replace(rows[1], difficulty="H")),
        lambda rows: (rows[0], replace(rows[1], truth_category_id=1)),
    ],
)
def test_locked_ground_truth_rejects_omitted_extra_or_changed_object_identity(mutate):
    expected = (
        rpc_metrics.LockedGroundTruthRow("scene", 11, "burst-a", "E", 1),
        rpc_metrics.LockedGroundTruthRow("scene", 12, "burst-a", "E", 2),
    )
    complete = (
        _row("scene", object_id=11, truth=1),
        _row("scene", object_id=12, truth=2, predicted=2),
    )

    with pytest.raises(ValueError, match="locked ground-truth identity"):
        rpc_metrics.validate_evidence_completeness(mutate(complete), expected)


def test_paired_validation_rejects_difficulty_mismatch_for_same_identity():
    candidate = (_row("same", difficulty="E"),)
    reference = (_row("same", condition_id="reference", difficulty="H"),)

    with pytest.raises(ValueError, match="difficulty mismatch"):
        validate_paired_evidence(candidate, reference)


def test_full_system_summary_rejects_an_absent_novel_cohort():
    with pytest.raises(ValueError, match="novel cohort"):
        full_system_summary((_row("only-base", truth=2, predicted=2),), novel_category_ids={1})


def test_condition_binding_rejects_a_declared_base_category_absent_from_truth_rows():
    condition = {
        "condition": {"condition_id": "candidate", "fold": 0},
        "cohort": {
            "fold": 0,
            "manifest_sha256": "1" * 64,
            "novel_category_ids": [1],
            "base_category_ids": [2, 3],
        },
        "scoring": {"registered_category_ids": [1, 2]},
        **_HASHES,
    }
    rows = (_row("novel", truth=1), _row("observed-base", truth=2))

    with pytest.raises(ValueError, match="base cohort is absent"):
        validate_evidence_against_condition(rows, condition)


def test_condition_binding_rejects_evidence_from_another_declared_fold():
    condition = {
        "condition": {"condition_id": "candidate", "fold": 0},
        "cohort": {
            "fold": 0,
            "manifest_sha256": "1" * 64,
            "novel_category_ids": [1],
            "base_category_ids": [2],
        },
        "scoring": {"registered_category_ids": [1, 2]},
        **_HASHES,
    }
    rows = (_row("novel", truth=1, fold=1), _row("base", truth=2, fold=1))

    with pytest.raises(ValueError, match="fold provenance"):
        validate_evidence_against_condition(rows, condition)


def test_full_system_summary_reports_wrong_registered_rates_per_cohort():
    summary = full_system_summary(
        (_row("novel", truth=1, predicted=2), _row("base", truth=2, predicted=1)),
        novel_category_ids={1},
    )

    assert summary.novel_wrong_registered_sku_rate == 1.0
    assert summary.base_wrong_registered_sku_rate == 1.0


def test_condition_binding_requires_the_complete_receipt_score_category_order():
    condition = {
        "condition": {"condition_id": "candidate", "fold": 0},
        "cohort": {"fold": 0, "manifest_sha256": "1" * 64, "novel_category_ids": [1], "base_category_ids": [2]},
        "scoring": {"registered_category_ids": [1, 2, 3]},
        **_HASHES,
    }

    with pytest.raises(ValueError, match="complete registered cohort"):
        validate_evidence_against_condition((_row("novel", truth=1), _row("base", truth=2)), condition)


def test_bootstrap_is_repeatable_and_rejects_zero_replicates():
    reference = (
        _row("n-e", truth=1, predicted=1, difficulty="E", burst_id="e"),
        _row("n-m", truth=1, predicted=1, difficulty="M", burst_id="m"),
        _row("b-h", truth=2, predicted=2, difficulty="H", burst_id="h"),
    )
    candidate = (
        _row("n-e", truth=1, predicted=1, difficulty="E", burst_id="e"),
        _row("n-m", truth=1, predicted=2, difficulty="M", burst_id="m"),
        _row("b-h", truth=2, predicted=2, difficulty="H", burst_id="h"),
    )
    first = bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=13, replicates=50)
    second = bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=13, replicates=50)

    assert first == second
    with pytest.raises(ValueError, match="replicates"):
        bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=13, replicates=0)


def test_bootstrap_wrong_sku_interval_uses_novel_truth_rows_only():
    reference = (
        _row("novel", truth=1, predicted=1),
        _row("base", truth=2, predicted=2),
    )
    candidate = (
        _row("novel", truth=1, predicted=1),
        _row("base", truth=2, predicted=1),
    )

    interval = bootstrap_paired_deltas(
        candidate,
        reference,
        novel_category_ids={1},
        seed=13,
        replicates=20,
    )

    assert interval.novel_wrong_registered_sku_rate_lower_delta == 0.0
    assert interval.novel_wrong_registered_sku_rate_upper_delta == 0.0


def test_hierarchical_sampler_keeps_bursts_intact_without_resampling_base_categories():
    candidate = tuple(
        _row(
            f"{burst}-{category}",
            truth=category,
            predicted=category,
            category_ids=(1, 2, 3),
            repvit_global_scores=(0.9, 0.05, 0.05),
            burst_id=burst,
        )
        for burst in ("burst-a", "burst-b")
        for category in (1, 2, 3)
    )
    reference = tuple(replace(row, condition_id="reference") for row in candidate)
    pairs = tuple(zip(candidate, reference, strict=True))

    sampled = _hierarchical_sample(pairs, random.Random(0), frozenset({1, 2}))
    counts = {
        (burst, category): sum(
            pair[0].burst_id == burst and pair[0].truth_category_id == category
            for pair in sampled
        )
        for burst in ("burst-a", "burst-b")
        for category in (1, 2, 3)
    }

    assert len(set(counts[("burst-a", category)] for category in (1, 2, 3))) == 1
    assert len(set(counts[("burst-b", category)] for category in (1, 2, 3))) == 1


def test_bootstrap_preserves_novel_category_draw_multiplicity_in_macro_delta():
    reference = tuple(
        _row(
            f"category-{category}",
            truth=category,
            predicted=category,
            category_ids=(1, 2, 3, 4),
            repvit_global_scores=(0.7, 0.1, 0.1, 0.1),
        )
        for category in (1, 2, 3, 4)
    )
    candidate = tuple(
        replace(row, predicted_category_id=4 if row.truth_category_id == 2 else row.truth_category_id)
        for row in reference
    )

    interval = bootstrap_paired_deltas(
        candidate,
        reference,
        novel_category_ids={1, 2, 3},
        seed=4,
        replicates=1,
    )

    # Seed 4 draws novel categories [1, 2, 1], so category 2 contributes
    # exactly one of the three macro terms.
    assert interval.novel_macro_recall_lower_delta == pytest.approx(-1 / 3)
    assert interval.novel_macro_recall_upper_delta == pytest.approx(-1 / 3)


def test_summaries_account_for_branch_top1_full_system_and_each_difficulty():
    rows = (
        _row("e", truth=1, predicted=1, difficulty="E"),
        _row("m", truth=1, predicted=None, difficulty="M"),
        _row(
            "h",
            truth=2,
            predicted=1,
            difficulty="H",
            repvit_global_scores=(0.8, 0.2),
        ),
    )
    repvit = branch_top1_summary(
        rows, branch="repvit_global", novel_category_ids={1}
    )
    final = full_system_summary(rows, novel_category_ids={1})

    assert repvit.novel_macro_recall == 1.0
    assert final.unknown_rate == pytest.approx(1 / 3)
    assert final.wrong_registered_sku_rate == pytest.approx(1 / 3)
    assert final.by_difficulty["E"].sample_count == 1
    assert final.by_difficulty["M"].unknown_rate == 1.0
    assert final.by_difficulty["H"].wrong_registered_sku_rate == 1.0


@pytest.mark.parametrize("bad", [(float("nan"), 0.0), (float("inf"), 0.0)])
def test_row_rejects_non_finite_scores(bad: tuple[float, float]):
    with pytest.raises(ValueError, match="finite"):
        _row("bad", repvit_global_scores=bad)
