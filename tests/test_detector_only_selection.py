import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.detector_only_selection import (
    DetectorOnlyPolicy,
    DetectorOnlyReportProvenance,
    assert_locked_zero_error,
    cross_fit_detector_only_policies,
    write_detector_only_report,
)
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import OofArtifact, OofPrediction
from bakery_scanner.evaluation import (
    EvaluationReport,
    ScanMetrics,
    ThresholdEvaluation,
)


def _selection_fixture():
    experiments = {
        f"fold-{fold}": DetectorExperiment(
            "dfine_n_640", "dfine", 640, 20260724, fold
        )
        for fold in range(5)
    }
    predictions = []
    folds = {}
    ground_truth = {}
    for fold in range(5):
        image_id = fold + 1
        folds[image_id] = fold
        box = Box(10 + fold, 20, 15, 15)
        ground_truth[image_id] = (box,)
        predictions.append(
            OofPrediction(
                f"fold-{fold}",
                SceneKey("batch", image_id),
                BreadProposal(
                    image_id,
                    "dfine_n_640",
                    0.123456 if fold == 0 else 0.9,
                    box,
                    100,
                    100,
                ),
            )
        )
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        tuple(predictions),
        {},
        experiments,
        {
            run_id: f"{fold + 1:x}" * 64
            for fold, run_id in enumerate(experiments)
        },
        {
            run_id: f"{fold + 6:x}" * 64
            for fold, run_id in enumerate(experiments)
        },
    )
    fold_image_ids = {
        fold: frozenset({fold + 1})
        for fold in range(5)
    }
    return artifact, folds, fold_image_ids, ground_truth


def _metrics(*, duplicates=0):
    return ThresholdEvaluation(
        scan_count=1,
        exact_scans=0 if duplicates else 1,
        misses=0,
        false_positives=0,
        duplicates=duplicates,
        split_errors=0,
        merge_errors=0,
        scenarios={},
    )


def _report_with_duplicate_at_75():
    zero = _metrics()
    duplicate = _metrics(duplicates=1)
    return EvaluationReport(
        scan_count=1,
        exact_scans=1,
        misses=0,
        false_positives=0,
        duplicates=0,
        split_errors=0,
        merge_errors=0,
        sem_exact_75=0.0,
        sem_exact_90=0.0,
        scenarios={},
        by_iou={0.50: zero, 0.75: duplicate},
    )


def _report_provenance():
    return DetectorOnlyReportProvenance(
        staged_annotations_sha256="a" * 64,
        staged_manifest_sha256="b" * 64,
        fold_manifest_sha256={
            fold: f"{fold + 1:x}" * 64
            for fold in range(5)
        },
    )


def test_fold_zero_policy_excludes_fold_zero_candidates_and_labels():
    artifact, folds, fold_image_ids, ground_truth = _selection_fixture()

    policy = cross_fit_detector_only_policies(
        artifact,
        folds=folds,
        ground_truth=ground_truth,
    )[0]

    assert policy.calibration_image_ids.isdisjoint(fold_image_ids[0])
    assert policy.calibration_image_ids == frozenset({2, 3, 4, 5})
    assert policy.score_threshold != 0.123456


def test_equivalent_native_and_recall_candidates_prefer_native_label():
    artifact, folds, _, ground_truth = _selection_fixture()

    policies = cross_fit_detector_only_policies(
        artifact,
        folds=folds,
        ground_truth=ground_truth,
    )

    assert {policy.raw_source for policy in policies.values()} == {"native"}


def test_zero_error_gate_rejects_iou75_duplicate():
    with pytest.raises(ValueError, match="IoU 0.75"):
        assert_locked_zero_error(_report_with_duplicate_at_75())


def test_report_marks_detector_only_failure_without_operational_claim(tmp_path):
    artifact, folds, _, ground_truth = _selection_fixture()
    policies = cross_fit_detector_only_policies(
        artifact,
        folds=folds,
        ground_truth=ground_truth,
    )
    policies = {
        **policies,
        0: replace(policies[0], score_threshold=1.0),
    }

    report = write_detector_only_report(
        output=tmp_path / "detector-only.json",
        detector_oof=artifact,
        folds=folds,
        ground_truth=ground_truth,
        scenarios={image_id: frozenset({"fixture"}) for image_id in folds},
        policies=policies,
        provenance=_report_provenance(),
        expected_staged_images=5,
        expected_staged_boxes=5,
    )
    payload = json.loads(report.read_text(encoding="utf-8"))

    assert payload["operational_guarantee"] is False
    assert payload["locked_zero_error_passed"] is False
    assert payload["data"]["count_gate"] == {
        "actual_boxes": 5,
        "actual_images": 5,
        "expected_boxes": 5,
        "expected_images": 5,
        "passed": True,
    }
    assert set(payload["metrics"]["overall"]["errors"]) == {"0.50", "0.75"}
    assert set(payload["metrics"]["overall"]["errors"]["0.75"]) == {
        "duplicates",
        "false_positives",
        "merge_errors",
        "misses",
        "split_errors",
    }
    assert payload["policies"]["0"]["calibration_image_ids"] == [2, 3, 4, 5]
    assert len(payload["artifacts"]["runs"]) == 5
    assert payload["artifacts"]["runs"]["0"]["candidate_counts"] == {
        "native": 1,
        "recall_top30": 1,
    }
    assert "path" not in payload["artifacts"]
    assert payload["provenance"] == {
        "fold_manifest_sha256": {
            str(fold): f"{fold + 1:x}" * 64
            for fold in range(5)
        },
        "staged": {
            "annotations.json": "a" * 64,
            "staged_manifest.json": "b" * 64,
        },
    }
    assert "independent acceptance" in payload["limitations"]["acceptance"].lower()
    assert "empty-tray" in payload["limitations"]["unobserved_conditions"]
    assert "overlap" in payload["limitations"]["unobserved_conditions"]
    assert "obstruction" in payload["limitations"]["unobserved_conditions"]
    assert payload["images"]["1"]["ground_truth_boxes"] == [
        [10.0, 20.0, 25.0, 35.0]
    ]
    assert payload["images"]["1"]["prediction_boxes"] == []

    with pytest.raises(FileExistsError):
        write_detector_only_report(
            output=report,
            detector_oof=artifact,
            folds=folds,
            ground_truth=ground_truth,
            scenarios={image_id: frozenset({"fixture"}) for image_id in folds},
            policies=policies,
            provenance=_report_provenance(),
            expected_staged_images=5,
            expected_staged_boxes=5,
        )


def test_report_rejects_policy_that_claims_target_fold_calibration(tmp_path):
    artifact, folds, _, ground_truth = _selection_fixture()
    policies = cross_fit_detector_only_policies(
        artifact,
        folds=folds,
        ground_truth=ground_truth,
    )
    policies = {
        **policies,
        0: replace(
            policies[0],
            calibration_image_ids=policies[0].calibration_image_ids | {1},
        ),
    }

    with pytest.raises(ValueError, match="calibration_image_ids"):
        write_detector_only_report(
            output=tmp_path / "leaked.json",
            detector_oof=artifact,
            folds=folds,
            ground_truth=ground_truth,
            scenarios={image_id: frozenset() for image_id in folds},
            policies=policies,
            provenance=_report_provenance(),
            expected_staged_images=5,
            expected_staged_boxes=5,
        )


@pytest.mark.parametrize(
    "provenance",
    (
        None,
        DetectorOnlyReportProvenance(
            staged_annotations_sha256="not-a-sha256",
            staged_manifest_sha256="b" * 64,
            fold_manifest_sha256={fold: f"{fold + 1:x}" * 64 for fold in range(5)},
        ),
        DetectorOnlyReportProvenance(
            staged_annotations_sha256="a" * 64,
            staged_manifest_sha256="b" * 64,
            fold_manifest_sha256=None,
        ),
    ),
)
def test_report_rejects_missing_or_invalid_provenance(tmp_path, provenance):
    artifact, folds, _, ground_truth = _selection_fixture()
    policies = cross_fit_detector_only_policies(
        artifact,
        folds=folds,
        ground_truth=ground_truth,
    )

    with pytest.raises(ValueError, match="provenance"):
        write_detector_only_report(
            output=tmp_path / "missing-provenance.json",
            detector_oof=artifact,
            folds=folds,
            ground_truth=ground_truth,
            scenarios={image_id: frozenset() for image_id in folds},
            policies=policies,
            provenance=provenance,
            expected_staged_images=5,
            expected_staged_boxes=5,
        )


def test_selection_requires_exact_five_receipt_validated_dfine_runs():
    artifact, folds, _, ground_truth = _selection_fixture()
    artifact = replace(
        artifact,
        run_receipt_hashes={
            **artifact.run_receipt_hashes,
            "fold-0": "not-a-sha256",
        },
    )

    with pytest.raises(ValueError, match="SHA-256"):
        cross_fit_detector_only_policies(
            artifact,
            folds=folds,
            ground_truth=ground_truth,
        )


def test_cli_help_exposes_config_and_output():
    environment = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [sys.executable, "scripts/select_detector_only.py", "--help"],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--config" in result.stdout
    assert "--output" in result.stdout
