from pathlib import Path

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.dfine import parse_dfine_output
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import OofArtifact, OofPrediction, _predictions_for
from bakery_scanner.detectors.proposal_policy import retain_raw_proposals
from bakery_scanner.detectors.selection import _threshold_evidence, calibrate_variant_score_thresholds


def _proposal(score: float, x: int) -> BreadProposal:
    return BreadProposal(1, "dfine_n_640", score, Box(x, 0, 1, 1), 100, 20)


def _raw_rows() -> tuple[BreadProposal, ...]:
    """A deliberately reversed raw stream with 31 retained-score boxes."""
    rows = [_proposal(0.90, 20), _proposal(0.90, 10)]
    rows.extend(_proposal(0.89 - index * 0.01, 30 + index) for index in range(29))
    rows.append(_proposal(0.0009, 99))
    return tuple(reversed(rows))


def test_raw_proposal_policy_drops_floor_caps_and_canonically_orders_input():
    """Changing detector emission order must not change its bounded raw evidence."""
    retained = retain_raw_proposals(_raw_rows())

    assert len(retained) == 30
    assert tuple(row.box.x for row in retained) == (10, 20, *range(30, 58))
    assert retained == retain_raw_proposals(tuple(reversed(_raw_rows())))
    assert all(row.score >= 0.001 for row in retained)


def test_oof_calibration_and_selection_apply_raw_policy_before_zero_threshold():
    """A calibrated zero threshold must still see only parser-equivalent raw rows."""
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        tuple(OofPrediction("dfine", SceneKey("g15", 1), proposal) for proposal in _raw_rows()),
        {},
        {"dfine": experiment},
        {},
        {},
    )

    selected = _predictions_for(artifact, (experiment.name,), {experiment.name: 0.0}, experiment.seed)
    calibration = _threshold_evidence(
        artifact,
        experiment.name,
        0.0,
        {1: (Box(10, 0, 1, 1),)},
        {1: frozenset()},
    )

    assert tuple(box.x for box in selected[1]) == (10, 20, *range(30, 58))
    assert calibration.false_proposals == 29


def test_calibration_never_selects_a_below_floor_raw_score():
    """The raw floor precedes calibration-candidate generation as well."""
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        (OofPrediction("dfine", SceneKey("g15", 1), _proposal(0.0009, 10)),),
        {},
        {"dfine": experiment},
        {},
        {},
    )

    calibration = calibrate_variant_score_thresholds(
        artifact,
        ground_truth={1: (Box(10, 0, 1, 1),)},
        scenarios={1: frozenset()},
    )

    assert calibration[experiment.name].threshold == 0.0
    assert calibration[experiment.name].evidence.misses == 1


def test_calibration_unions_raw_threshold_candidates_after_per_run_caps():
    """A seed's 30th retained box must not be displaced by another seed's boxes."""
    first = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    second = DetectorExperiment("dfine_n_640", "dfine", 640, 20260725, 0)
    first_rows = tuple(
        OofPrediction(
            first.run_id,
            SceneKey("g15", 1),
            BreadProposal(1, first.name, round(0.80 - index * 0.01, 2), Box(index, 0, 1, 1), 100, 20),
        )
        for index in range(30)
    )
    second_rows = tuple(
        OofPrediction(
            second.run_id,
            SceneKey("g15", 1),
            BreadProposal(1, second.name, round(0.99 - index * 0.01, 2), Box(index, 0, 1, 1), 100, 20),
        )
        for index in range(30)
    )
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        first_rows + second_rows,
        {},
        {first.run_id: first, second.run_id: second},
        {},
        {},
    )

    calibration = calibrate_variant_score_thresholds(
        artifact,
        ground_truth={1: (Box(29, 0, 1, 1),)},
        scenarios={1: frozenset()},
    )

    assert calibration[first.name].threshold == 0.51
    assert calibration[first.name].evidence.misses == 0


def test_parser_rejects_retained_score_duplicates_even_when_top_cap_excludes_them():
    """The cap must not weaken the parser's established duplicate contract."""
    boxes = [[index, 0, index + 1, 1] for index in range(31)]
    boxes.extend(([80, 2, 81, 3], [80, 2, 81, 3]))
    scores = [0.90 - index * 0.01 for index in range(31)] + [0.50, 0.50]

    with pytest.raises(ValueError, match="duplicate prediction coordinates"):
        parse_dfine_output(1, (100, 80), [0] * len(boxes), boxes, scores, "dfine_n_640")
