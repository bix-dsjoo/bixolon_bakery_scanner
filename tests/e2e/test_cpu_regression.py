from pathlib import Path

import pytest

from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    SkuCandidate,
    StageTimings,
)
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample, CpuEvaluationTarget
from bakery_scanner.e2e.cpu_regression import (
    ObjectOutcome,
    ObjectRecord,
    RunAggregate,
    aggregate_meets_quality_floors,
    build_image_regression_record,
    compare_run,
    transition_is_allowed,
)


def _record(
    outcome: str,
    *,
    expected: int,
    predicted: int | None,
    top3: tuple[int, ...] = (),
) -> ObjectRecord:
    return ObjectRecord(
        sample_key="fixture/e_0001.jpg",
        annotation_id=1,
        expected_sku=expected,
        outcome=ObjectOutcome(outcome),
        predicted_sku=predicted,
        top3_sku_ids=top3,
        matched_proposal_index=0 if outcome != "missed" else None,
        iou=1.0 if outcome != "missed" else None,
    )


def test_monotonic_gate_rejects_a_correct_object_becoming_unknown():
    reference = _record("correct", expected=6, predicted=6)
    candidate = _record("top3_candidate", expected=6, predicted=None, top3=(6, 5, 8))

    report = compare_run((reference,), (candidate,))

    assert not report.passed
    assert report.regressions[0].reason == "correct_object_regressed"


@pytest.mark.parametrize(
    ("before", "after", "allowed"),
    [
        ("correct", "correct", True),
        ("top3_candidate", "correct", True),
        ("candidate_out_unknown", "top3_candidate", True),
        ("misclassified", "candidate_out_unknown", True),
        ("missed", "candidate_out_unknown", True),
        ("top3_candidate", "candidate_out_unknown", False),
        ("candidate_out_unknown", "misclassified", False),
        ("correct", "misclassified", False),
    ],
)
def test_transition_table(before, after, allowed):
    assert transition_is_allowed(before, after) is allowed


def test_same_outcome_records_require_the_same_correct_or_wrong_sku_mapping():
    correct = _record("correct", expected=6, predicted=6)
    changed_correct = _record("correct", expected=6, predicted=5)
    wrong = _record("misclassified", expected=6, predicted=5)
    changed_wrong = _record("misclassified", expected=6, predicted=19)

    assert not compare_run((correct,), (changed_correct,)).passed
    assert not compare_run((wrong,), (changed_wrong,)).passed


def test_matching_is_stable_when_equal_iou_predictions_are_permuted():
    sample = CpuEvaluationSample(
        key="fixture/e_0001.jpg",
        source="fixture",
        source_image_id=1,
        image_path=Path("fixture/e_0001.jpg"),
        profile="E",
        targets=(
            CpuEvaluationTarget(10, 1, Box(0, 0, 10, 10)),
            CpuEvaluationTarget(20, 2, Box(0, 0, 10, 10)),
        ),
    )
    lower_score = _proposal(score=0.7)
    higher_score = _proposal(score=0.9)

    first = build_image_regression_record(
        sample,
        (lower_score, higher_score),
        (_decision(2), _decision(1)),
    )
    second = build_image_regression_record(
        sample,
        (higher_score, lower_score),
        (_decision(1), _decision(2)),
    )

    assert [(record.annotation_id, record.predicted_sku) for record in first.objects] == [
        (10, 1),
        (20, 2),
    ]
    assert [(record.annotation_id, record.predicted_sku) for record in second.objects] == [
        (10, 1),
        (20, 2),
    ]


def test_quality_floors_accept_exact_baseline_and_reject_each_worse_metric():
    baseline = RunAggregate(
        top1=1349,
        top3=1390,
        false_positives=0,
        false_negatives=5,
        unknown=48,
        misclassified=4,
    )

    assert aggregate_meets_quality_floors(baseline)
    for changed in (
        RunAggregate(1348, 1390, 0, 5, 48, 4),
        RunAggregate(1349, 1389, 0, 5, 48, 4),
        RunAggregate(1349, 1390, 1, 5, 48, 4),
        RunAggregate(1349, 1390, 0, 6, 48, 4),
        RunAggregate(1349, 1390, 0, 5, 49, 4),
        RunAggregate(1349, 1390, 0, 5, 48, 5),
    ):
        assert not aggregate_meets_quality_floors(changed)


def _proposal(*, score: float) -> BreadProposal:
    return BreadProposal(
        image_id=1,
        source="rfdetr_large_bakery_v1",
        score=score,
        box=Box(0, 0, 10, 10),
        image_width=100,
        image_height=100,
    )


def _decision(sku_id: int) -> ClassificationDecision:
    return ClassificationDecision(
        decision="sku",
        sku_id=sku_id,
        confidence=0.9,
        box=Box(0, 0, 10, 10),
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=ModelProvenance(
            repvit_artifact_id="repvit_m1_15plus5_v1",
            repvit_sha256="0" * 64,
            dinov3_artifact_id="dinov3_vits16_15plus5_v1",
            dinov3_sha256="1" * 64,
            dinov3_support_sha256="2" * 64,
            calibration_id="fixture",
            calibration_sha256="3" * 64,
        ),
        timings=StageTimings(repvit_ms=0.0, dinov3_ms=0.0, total_ms=0.0),
    )
