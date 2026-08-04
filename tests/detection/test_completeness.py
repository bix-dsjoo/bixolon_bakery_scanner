from __future__ import annotations

import math

import pytest

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import RetakeReason


FRAME = (100, 80)


def _proposal(x: float, y: float, width: float = 10.0, height: float = 10.0) -> BreadProposal:
    return BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(x, y, width, height), *FRAME)


def _policy(**changes: float | tuple[float, float]):
    from bakery_scanner.detection.completeness import CompletenessPolicy

    values: dict[str, object] = {
        "max_uncovered_ratio": 0.03,
        "max_pair_iou": 0.25,
        "border_margin_ratio": 0.05,
        "min_blur_score": 0.8,
        "exposure_range": (0.2, 0.8),
        "max_reflection_ratio": 0.1,
        "max_risk_score": 0.2,
    }
    values.update(changes)
    return CompletenessPolicy(**values)


def _foreground(**changes: object):
    from bakery_scanner.detection.completeness import ForegroundEvidence

    values: dict[str, object] = {
        "uncovered_ratio": 0.0,
        "covered_ratio": 1.0,
        "problem_regions": (),
        "possible_split_regions": (),
        "possible_merge_regions": (),
        "risk_score": 0.0,
    }
    values.update(changes)
    return ForegroundEvidence(**values)


def _quality(**changes: float):
    from bakery_scanner.detection.completeness import CaptureQuality

    values: dict[str, float] = {"blur_score": 1.0, "exposure_score": 0.5, "reflection_ratio": 0.0}
    values.update(changes)
    return CaptureQuality(**values)


def test_uncovered_foreground_requires_retake() -> None:
    from bakery_scanner.detection.completeness import evaluate_completeness

    decision = evaluate_completeness(
        frame_size=FRAME,
        proposals=(_proposal(10, 10), _proposal(30, 10), _proposal(50, 10)),
        foreground=_foreground(uncovered_ratio=0.08, problem_regions=((10, 10, 80, 80),)),
        quality=_quality(),
        policy=_policy(),
    )

    assert decision.accepted is False
    assert decision.reasons == (RetakeReason.UNCOVERED_FOREGROUND,)
    assert decision.problem_regions == ((10.0, 10.0, 80.0, 80.0),)


def test_zero_target_requires_retake() -> None:
    from bakery_scanner.detection.completeness import evaluate_completeness

    decision = evaluate_completeness(FRAME, (), _foreground(), _quality(), _policy())

    assert decision.accepted is False
    assert decision.reasons == (RetakeReason.NO_TARGET_DETECTED,)


@pytest.mark.parametrize("count", [1, 2, 8])
def test_nonzero_counts_are_not_completeness_failures(count: int) -> None:
    from bakery_scanner.detection.completeness import evaluate_completeness

    proposals = tuple(_proposal(10 + (index % 5) * 15, 10 + (index // 5) * 15) for index in range(count))

    decision = evaluate_completeness(FRAME, proposals, _foreground(), _quality(), _policy())

    assert decision.accepted is True
    assert decision.reasons == ()


def test_reasons_and_problem_regions_are_canonical_and_deduplicated() -> None:
    from bakery_scanner.detection.completeness import evaluate_completeness

    first = _proposal(0, 10)
    second = _proposal(5, 10)
    decision = evaluate_completeness(
        FRAME,
        (first, second),
        _foreground(
            uncovered_ratio=0.1,
            problem_regions=((30, 20, 40, 30), (20, 10, 30, 20), (30, 20, 40, 30)),
            possible_split_regions=((20, 10, 30, 20),),
            possible_merge_regions=((30, 20, 40, 30),),
            risk_score=0.3,
        ),
        _quality(blur_score=0.7, exposure_score=0.9, reflection_ratio=0.2),
        _policy(),
    )

    assert decision.reasons == (
        RetakeReason.UNCOVERED_FOREGROUND,
        RetakeReason.OVERLAP_OR_OCCLUSION,
        RetakeReason.POSSIBLE_SPLIT,
        RetakeReason.POSSIBLE_MERGE,
        RetakeReason.TRUNCATED_OBJECT,
        RetakeReason.CAPTURE_QUALITY_UNVERIFIED,
        RetakeReason.COMPLETENESS_RISK_EXCEEDED,
    )
    assert decision.problem_regions == (
        (0.0, 10.0, 10.0, 20.0),
        (5.0, 10.0, 10.0, 20.0),
        (5.0, 10.0, 15.0, 20.0),
        (20.0, 10.0, 30.0, 20.0),
        (30.0, 20.0, 40.0, 30.0),
    )


def test_quality_threshold_boundaries_are_accepted_outside_border_margin() -> None:
    from bakery_scanner.detection.completeness import evaluate_completeness

    decision = evaluate_completeness(
        FRAME,
        (_proposal(6, 6),),
        _foreground(risk_score=0.2),
        _quality(blur_score=0.8, exposure_score=0.2, reflection_ratio=0.1),
        _policy(),
    )

    assert decision.accepted is True


def test_detector_boundary_rejects_mismatched_frame_and_malformed_box() -> None:
    from bakery_scanner.detection.completeness import InvalidDetectorOutput, evaluate_completeness

    mismatched = BreadProposal(1, "rfdetr_large_bakery_v1", 0.9, Box(1, 1, 10, 10), 99, 80)
    with pytest.raises(InvalidDetectorOutput, match="dimensions"):
        evaluate_completeness(FRAME, (mismatched,), _foreground(), _quality(), _policy())

    malformed = object.__new__(BreadProposal)
    for field, value in {
        "image_id": 1, "source": "rfdetr_large_bakery_v1", "score": 0.9,
        "box": Box(1, 1, 10, 10), "image_width": 100, "image_height": 80,
        "class_id": 1, "class_name": "bread",
    }.items():
        object.__setattr__(malformed, field, value)
    object.__setattr__(malformed, "box", type("BadBox", (), {"xyxy": (0.0, 0.0, math.nan, 1.0)})())
    with pytest.raises(InvalidDetectorOutput, match="box"):
        evaluate_completeness(FRAME, (malformed,), _foreground(), _quality(), _policy())


def test_detector_boundary_normalizes_forged_proposal_missing_dimensions() -> None:
    from bakery_scanner.detection.completeness import InvalidDetectorOutput, evaluate_completeness

    malformed = object.__new__(BreadProposal)
    for field, value in {
        "image_id": 1, "source": "rfdetr_large_bakery_v1", "score": 0.9,
        "box": Box(1, 1, 10, 10), "image_height": 80, "class_id": 1, "class_name": "bread",
    }.items():
        object.__setattr__(malformed, field, value)

    with pytest.raises(InvalidDetectorOutput, match="dimensions"):
        evaluate_completeness(FRAME, (malformed,), _foreground(), _quality(), _policy())
