import json
from pathlib import Path

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import OofArtifact, OofPrediction
from bakery_scanner.detectors.selection import (
    ScoreCalibrationEvidence,
    VariantScoreCalibration,
    calibrate_variant_score_thresholds,
    load_staged_ground_truth,
    write_development_selection_report,
)


def test_staged_coco_ground_truth_and_scenarios_are_deterministic(tmp_path):
    """Selection must evaluate every staged image with reproducible data strata."""
    (tmp_path / "annotations.json").write_text(
        json.dumps(
            {
                "images": [
                    {"id": 2, "file_name": "two.png", "width": 100, "height": 80},
                    {"id": 1, "file_name": "one.png", "width": 100, "height": 80},
                ],
                "annotations": [
                    {"id": 3, "image_id": 2, "category_id": 1, "bbox": [20, 10, 5, 6]},
                    {"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 2, 3, 4]},
                    {"id": 2, "image_id": 2, "category_id": 1, "bbox": [10, 11, 12, 13]},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "staged_manifest.json").write_text(
        json.dumps(
            [
                {"image_id": 2, "box_count": 2, "overlap_proxy": True, "scene": {"capture_batch": "g20_b01", "scene_number": 7}},
                {"image_id": 1, "box_count": 1, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 3}},
            ]
        ),
        encoding="utf-8",
    )

    first = load_staged_ground_truth(tmp_path)
    second = load_staged_ground_truth(tmp_path)

    assert first == second
    assert first.ground_truth == {
        1: (Box(1, 2, 3, 4),),
        2: (Box(10, 11, 12, 13), Box(20, 10, 5, 6)),
    }
    assert first.scenarios == {
        1: frozenset({"capture_batch:g15", "overlap_proxy:false", "box_count:0-2"}),
        2: frozenset({"capture_batch:g20_b01", "overlap_proxy:true", "box_count:0-2"}),
    }


def test_variant_score_calibration_keeps_the_highest_zero_miss_threshold_or_zero():
    """Threshold search is limited to observed scores plus the zero fallback."""
    dfine = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    rtmdet = DetectorExperiment("rtmdet_tiny_640", "rtmdet", 640, 20260724, 0)
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        (
            OofPrediction("dfine", SceneKey("g15", 1), BreadProposal(1, dfine.name, 0.60, Box(0, 0, 10, 10), 30, 20)),
            OofPrediction("dfine", SceneKey("g15", 2), BreadProposal(2, dfine.name, 0.95, Box(20, 0, 5, 5), 30, 20)),
            OofPrediction("rtmdet", SceneKey("g15", 2), BreadProposal(2, rtmdet.name, 0.90, Box(20, 0, 5, 5), 30, 20)),
        ),
        {},
        {"dfine": dfine, "rtmdet": rtmdet},
        {},
        {},
    )

    calibration = calibrate_variant_score_thresholds(
        artifact,
        ground_truth={1: (Box(0, 0, 10, 10),)},
        scenarios={1: frozenset(), 2: frozenset()},
    )

    assert calibration[dfine.name].threshold == 0.60
    assert calibration[dfine.name].evidence.misses == 0
    assert calibration[rtmdet.name].threshold == 0.0
    assert calibration[rtmdet.name].evidence.misses == 1


def test_development_selection_report_is_canonical_limited_and_never_overwritten(tmp_path):
    """Development OOF evidence must not be represented as an operational guarantee."""
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, 20260724, 0)
    artifact = OofArtifact(Path("oof_predictions.json"), (), {}, {"dfine": experiment}, {}, {})
    calibrations = {
        experiment.name: VariantScoreCalibration(
            0.0,
            ScoreCalibrationEvidence(0.0, 1, 1, 0, 0, 0.0),
        )
    }
    output = tmp_path / "development-selection.json"

    write_development_selection_report(
        output=output,
        artifact=artifact,
        ground_truth={1: (Box(0, 0, 10, 10),)},
        scenarios={1: frozenset({"overlap_proxy:false"})},
        calibrations=calibrations,
        selection={"primary": experiment.name, "secondary": None, "evidence": []},
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scope"] == "grouped_oof_development_only"
    assert payload["operational_guarantee"] is False
    limitation = payload["limitations"]["overlap_obstruction"].lower()
    assert "overlap" in limitation and "obstruction" in limitation
    assert output.read_bytes() == json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with pytest.raises(FileExistsError):
        write_development_selection_report(
            output=output,
            artifact=artifact,
            ground_truth={1: (Box(0, 0, 10, 10),)},
            scenarios={1: frozenset({"overlap_proxy:false"})},
            calibrations=calibrations,
            selection={"primary": experiment.name, "secondary": None, "evidence": []},
        )
