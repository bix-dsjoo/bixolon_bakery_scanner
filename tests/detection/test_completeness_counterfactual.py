from __future__ import annotations

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import RetakeReason

from test_completeness import FRAME, _foreground, _policy, _quality


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
