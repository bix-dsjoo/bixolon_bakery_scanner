from __future__ import annotations

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import RetakeReason

from test_completeness import FRAME, _policy, _quality


def _proposal(x: float, y: float, width: float = 10.0, height: float = 10.0) -> BreadProposal:
    return BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(x, y, width, height), *FRAME)


def test_counterfactual_cases_are_separate_and_rejected_for_their_intended_fault() -> None:
    from bakery_scanner.detection.completeness import build_counterfactuals, evaluate_completeness

    boxes = (_proposal(10, 10), _proposal(15, 10), _proposal(40, 10))
    cases = build_counterfactuals(boxes)

    assert {case.evidence_kind for case in cases} == {"counterfactual"}
    assert {case.fault for case in cases} == {"missing", "merge", "split", "truncation"}
    for case in cases:
        decision = evaluate_completeness(FRAME, case.proposals, case.foreground, _quality(), _policy())
        expected = {
            "missing": RetakeReason.UNCOVERED_FOREGROUND,
            "merge": RetakeReason.POSSIBLE_MERGE,
            "split": RetakeReason.POSSIBLE_SPLIT,
            "truncation": RetakeReason.TRUNCATED_OBJECT,
        }[case.fault]
        assert decision.accepted is False
        assert expected in decision.reasons


def test_single_object_missing_case_preserves_canonical_frame_without_proposals() -> None:
    from bakery_scanner.detection.completeness import build_counterfactuals

    missing = next(case for case in build_counterfactuals((_proposal(10, 10),)) if case.fault == "missing")

    assert missing.proposals == ()
    assert missing.frame_size == FRAME
    assert missing.target_indices == (0,)
    assert missing.variant_id == "missing-0"
    assert missing.intended_retake_reasons == (
        RetakeReason.NO_TARGET_DETECTED,
        RetakeReason.UNCOVERED_FOREGROUND,
    )


def test_counterfactual_transform_identity_is_deterministic_and_source_indexed() -> None:
    from bakery_scanner.detection.completeness import build_counterfactuals

    cases = build_counterfactuals((_proposal(10, 10), _proposal(15, 10)))

    assert len({case.variant_id for case in cases}) == len(cases)
    assert {(case.fault, case.target_indices) for case in cases} == {
        ("missing", (0,)),
        ("missing", (1,)),
        ("merge", (0, 1)),
        ("split", (0,)),
        ("split", (1,)),
        ("truncation", (0,)),
        ("truncation", (1,)),
    }
