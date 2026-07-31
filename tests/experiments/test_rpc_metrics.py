"""Hermetic acceptance tests for fail-closed RPC evidence scoring."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bakery_scanner.experiments.rpc_metrics import (
    ResearchEvidenceRow,
    bootstrap_paired_deltas,
    forced_top1_summary,
    full_system_summary,
    passes_minimum_rule,
    validate_paired_evidence,
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
    truth: int = 1,
    predicted: int | None = 1,
    scores: tuple[float, float] = (0.9, 0.1),
    category_ids: tuple[int, int] = (1, 2),
    fold: int = 0,
    difficulty: str = "E",
    burst_id: str = "burst-a",
    condition_id: str = "candidate",
) -> ResearchEvidenceRow:
    return ResearchEvidenceRow(
        sample_id=sample_id,
        condition_id=condition_id,
        fold=fold,
        difficulty=difficulty,
        burst_id=burst_id,
        truth_category_id=truth,
        predicted_category_id=predicted,
        score_category_ids=category_ids,
        scores=scores,
        **_HASHES,
    )


def test_unknown_only_candidate_cannot_pass_despite_safety_gain():
    reference = (_row("n", truth=1, predicted=2), _row("b", truth=2, predicted=2))
    candidate = (_row("n", truth=1, predicted=None), _row("b", truth=2, predicted=None))
    candidate_summary = full_system_summary(candidate, novel_category_ids={1})
    reference_summary = full_system_summary(reference, novel_category_ids={1})
    interval = bootstrap_paired_deltas(candidate, reference, novel_category_ids={1}, seed=9, replicates=20)

    assert candidate_summary.wrong_registered_sku_rate == 0.0
    assert not passes_minimum_rule(candidate_summary, reference_summary, interval)


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
        wrong_registered_sku_rate_upper_delta=0.005,
    )

    assert candidate_summary.novel_loss_over_10pp_fraction == 0.0
    assert passes_minimum_rule(candidate_summary, reference_summary, interval)


def test_paired_validation_rejects_identity_and_provenance_mismatches():
    candidate = (_row("same"),)
    reference = (_row("same", condition_id="reference"),)
    validate_paired_evidence(candidate, reference)

    with pytest.raises(ValueError, match="paired identity"):
        validate_paired_evidence(candidate, (_row("other", condition_id="reference"),))
    with pytest.raises(ValueError, match="provenance"):
        validate_paired_evidence(
            candidate + (replace(candidate[0], sample_id="same-2", policy_sha256="1" * 64),),
            reference + (replace(reference[0], sample_id="same-2"),),
        )
    with pytest.raises(ValueError, match="duplicate sample_id"):
        validate_paired_evidence(candidate + candidate, reference + reference)


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


def test_summaries_account_for_forced_top1_full_system_and_each_difficulty():
    rows = (
        _row("e", truth=1, predicted=1, difficulty="E"),
        _row("m", truth=1, predicted=None, difficulty="M"),
        _row("h", truth=2, predicted=1, difficulty="H", scores=(0.8, 0.2)),
    )
    forced = forced_top1_summary(rows, novel_category_ids={1})
    final = full_system_summary(rows, novel_category_ids={1})

    assert forced.novel_macro_recall == 1.0
    assert forced.top1_agreement == pytest.approx(2 / 3)
    assert final.unknown_rate == pytest.approx(1 / 3)
    assert final.wrong_registered_sku_rate == pytest.approx(1 / 3)
    assert final.by_difficulty["E"].sample_count == 1
    assert final.by_difficulty["M"].unknown_rate == 1.0
    assert final.by_difficulty["H"].wrong_registered_sku_rate == 1.0


@pytest.mark.parametrize("bad", [(float("nan"), 0.0), (float("inf"), 0.0)])
def test_row_rejects_non_finite_scores(bad: tuple[float, float]):
    with pytest.raises(ValueError, match="finite"):
        _row("bad", scores=bad)
