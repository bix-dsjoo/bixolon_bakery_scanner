import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import OofArtifact, OofPrediction
from bakery_scanner.detectors.dfine640_selection import (
    DevelopmentReportProvenance,
    FoldPolicy,
    VerifierOofArtifact,
    cross_fit_policies,
    load_complete_verifier_oof_artifact,
    write_cross_fit_development_report,
)
from bakery_scanner.verifier.model import VerifierPrediction


def _selection_fixture():
    experiments = {
        f"fold-{fold}": DetectorExperiment(
            "dfine_n_640", "dfine", 640, 20260724, fold
        )
        for fold in range(5)
    }
    predictions = []
    verifier_predictions = {}
    ground_truth = {}
    folds = {}
    for fold in range(5):
        image_id = fold + 1
        # Fold zero's verifier is deliberately much less confident.  Any
        # accidental self-calibration would lower its verifier threshold.
        score = 0.42
        box = Box(10, 10, 20, 20)
        invalid_box = Box(60, 10, 10, 10)
        predictions.extend(
            (
                OofPrediction(
                    f"fold-{fold}",
                    SceneKey("batch", fold + 1),
                    BreadProposal(
                        image_id, "dfine_n_640", score, box, 100, 100
                    ),
                ),
                OofPrediction(
                    f"fold-{fold}",
                    SceneKey("batch", fold + 1),
                    BreadProposal(
                        image_id, "dfine_n_640", 0.70, invalid_box, 100, 100
                    ),
                ),
            )
        )
        verifier_predictions[fold] = (
            VerifierPrediction(
                image_id,
                box,
                (0.10, 0.20, 0.35, 0.35)
                if fold == 0
                else (0.10, 0.80, 0.05, 0.05),
            ),
            VerifierPrediction(
                image_id, invalid_box, (0.85, 0.10, 0.03, 0.02)
            ),
        )
        ground_truth[image_id] = (box,)
        folds[image_id] = fold
    artifact = OofArtifact(
        Path("oof_predictions.json"),
        tuple(predictions),
        {},
        experiments,
        {run_id: str(fold) * 64 for fold, run_id in enumerate(experiments)},
        {run_id: f"{fold + 5:x}" * 64 for fold, run_id in enumerate(experiments)},
    )

    return artifact, verifier_predictions, folds, ground_truth


def _config_bytes():
    return {
        **{
            f"detector/fold-{fold}.yml": f"fold: {fold}\n".encode()
            for fold in range(5)
        },
        **{
            f"verifier/fold-{fold}.json": f'{{"fold":{fold}}}'.encode()
            for fold in range(5)
        },
    }


def test_fold_zero_policy_uses_only_other_four_folds():
    artifact, verifier_predictions, folds, ground_truth = _selection_fixture()

    policies = cross_fit_policies(
        detector_oof=artifact,
        verifier_predictions=verifier_predictions,
        folds=folds,
        ground_truth=ground_truth,
    )

    assert policies[0] == FoldPolicy(0.42, 0.80)


def test_development_report_is_complete_canonical_and_immutable(tmp_path):
    artifact, predictions, folds, ground_truth = _selection_fixture()
    policies = cross_fit_policies(
        detector_oof=artifact,
        verifier_predictions=predictions,
        folds=folds,
        ground_truth=ground_truth,
    )
    verifier_oof = VerifierOofArtifact(
        predictions_by_fold=predictions,
        receipt_hashes={fold: f"{fold + 10:x}" * 64 for fold in range(5)},
        prediction_artifact_hashes={
            fold: f"{fold + 11:x}" * 64 for fold in range(5)
        },
    )
    provenance = DevelopmentReportProvenance(
        staged_hashes={
            "annotations.json": "a" * 64,
            "staged_manifest.json": "b" * 64,
        },
        fold_manifest_hashes={fold: f"{fold + 1:x}" * 64 for fold in range(5)},
        detector_raw_prediction_hashes={
            fold: f"{fold + 5:x}" * 64 for fold in range(5)
        },
        config_bytes=_config_bytes(),
    )
    output = tmp_path / "dfine640-verifier-development.json"

    write_cross_fit_development_report(
        output=output,
        detector_oof=artifact,
        verifier_oof=verifier_oof,
        folds=folds,
        ground_truth=ground_truth,
        scenarios={image_id: frozenset({"fixture"}) for image_id in folds},
        policies=policies,
        provenance=provenance,
        expected_staged_images=5,
        expected_staged_boxes=5,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["operational_guarantee"] is False
    assert payload["data"]["staged_count"] == {"boxes": 5, "images": 5}
    assert len(payload["artifacts"]["detector"]["receipt_hashes"]) == 5
    assert len(payload["artifacts"]["verifier"]["receipt_hashes"]) == 5
    assert payload["policies"]["0"] == {
        "detector_score_threshold": 0.42,
        "minimum_exactly_one_probability": 0.8,
    }
    assert payload["metrics"]["overall"]["semr"]["0.50"] == 0.8
    assert payload["metrics"]["overall"]["unresolved_candidates"] == 1
    for metrics in (
        payload["metrics"]["overall"],
        *payload["metrics"]["folds"].values(),
    ):
        assert set(metrics["errors"]) == {"0.50", "0.75", "0.90"}
        for threshold_errors in metrics["errors"].values():
            assert set(threshold_errors) == {
                "duplicates",
                "false_positives",
                "merge_errors",
                "misses",
                "split_errors",
            }
    assert payload["metrics"]["overall"]["scenario_strata"]["fixture"][
        "semr"
    ]["0.50"] == 0.8
    assert len(payload["configs"]) == 10
    config = payload["configs"]["detector/fold-0.yml"]
    assert config["sha256"] == hashlib.sha256(b"fold: 0\n").hexdigest()
    assert output.read_bytes() == json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with pytest.raises(FileExistsError):
        write_cross_fit_development_report(
            output=output,
            detector_oof=artifact,
            verifier_oof=verifier_oof,
            folds=folds,
            ground_truth=ground_truth,
            scenarios={
                image_id: frozenset({"fixture"}) for image_id in folds
            },
            policies=policies,
            provenance=provenance,
            expected_staged_images=5,
            expected_staged_boxes=5,
        )
    with pytest.raises(ValueError, match="configuration bytes"):
        write_cross_fit_development_report(
            output=tmp_path / "incomplete-config-report.json",
            detector_oof=artifact,
            verifier_oof=verifier_oof,
            folds=folds,
            ground_truth=ground_truth,
            scenarios={
                image_id: frozenset({"fixture"}) for image_id in folds
            },
            policies=policies,
            provenance=DevelopmentReportProvenance(
                staged_hashes=provenance.staged_hashes,
                fold_manifest_hashes=provenance.fold_manifest_hashes,
                detector_raw_prediction_hashes=(
                    provenance.detector_raw_prediction_hashes
                ),
                config_bytes={"detector/fold-0.yml": b"incomplete"},
            ),
            expected_staged_images=5,
            expected_staged_boxes=5,
        )


def test_selection_cli_exposes_only_artifact_and_report_inputs():
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"

    result = subprocess.run(
        [sys.executable, "scripts/select_dfine640_verifier.py", "--help"],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--detector-root" in result.stdout
    assert "--verifier-root" in result.stdout
    assert "--output" in result.stdout


def test_detector_fold_audit_uses_config_paths_without_report_output(tmp_path):
    config_path = tmp_path / "configs" / "box_system.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """seed: 20260724
artifact_root: ../artifacts
canonical_frame: {width: 1152, height: 1536}
dataset:
  sources:
    - {name: fixture, images: ../images, annotations: ../annotations.json}
  expected_images: 299
  expected_boxes: 1410
  folds: 5
detectors:
  seeds: [20260724]
  variants:
    - {name: dfine_n_640, backend: dfine, input_size: 640, role: audit}
    - {name: dfine_n_768, backend: dfine, input_size: 768, role: primary}
    - {name: rtmdet_tiny_640, backend: rtmdet, input_size: 640, role: audit}
    - {name: rtmdet_tiny_768, backend: rtmdet, input_size: 768, role: secondary}
runtime: {device: 'CUDA:0', precision: FP32, proposal_limit: 30}
""",
        encoding="utf-8",
    )
    artifact_root = tmp_path / "artifacts"
    run_id = "dfine_n_640-seed20260724-fold0"
    run_root = artifact_root / "detectors" / run_id
    manifest = artifact_root / "folds" / "fold-0" / "manifest.json"
    prediction = run_root / "validation_predictions.json"
    processed = run_root / "processed_validation_image_ids.json"
    detector_config = (
        config_path.parent
        / "generated"
        / "detector-matrix"
        / f"{run_id}.yml"
    )
    for path, value in (
        (
            manifest,
            {
                "index": 0,
                "training_image_ids": [3],
                "validation_image_ids": [1, 2],
            },
        ),
        (
            prediction,
            [
                {
                    "bbox": [1, 2, 3, 4],
                    "image_id": 1,
                    "score": 0.9,
                    "source": "dfine_n_640",
                }
            ],
        ),
        (processed, [1, 2]),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    detector_config.parent.mkdir(parents=True, exist_ok=True)
    detector_config.write_text("seed: 20260724\n", encoding="utf-8")
    receipt = {
        "config_sha256": hashlib.sha256(detector_config.read_bytes()).hexdigest(),
        "fold": 0,
        "fold_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "prediction_sha256": hashlib.sha256(prediction.read_bytes()).hexdigest(),
        "processed_images_sha256": hashlib.sha256(processed.read_bytes()).hexdigest(),
        "run_id": run_id,
        "seed": 20260724,
        "status": "completed",
        "variant": "dfine_n_640",
    }
    (run_root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/select_dfine640_verifier.py",
            "--validate-detector-fold",
            "0",
            "--config",
            str(config_path),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "fold": 0,
        "status": "detector_fold_validated",
    }


def test_verifier_loader_requires_all_five_completed_artifacts(tmp_path):
    with pytest.raises(ValueError, match="all five completed"):
        load_complete_verifier_oof_artifact(
            verifier_root=tmp_path / "verifiers",
            detector_root=tmp_path / "detectors",
            fold_root=tmp_path / "folds",
            staged_root=tmp_path / "staged",
        )


def test_zero_threshold_never_accepts_a_non_exactly_one_verifier_state(tmp_path):
    artifact, predictions, folds, ground_truth = _selection_fixture()
    output = tmp_path / "zero-threshold-report.json"

    write_cross_fit_development_report(
        output=output,
        detector_oof=artifact,
        verifier_oof=VerifierOofArtifact(
            predictions_by_fold=predictions,
            receipt_hashes={fold: f"{fold + 10:x}" * 64 for fold in range(5)},
            prediction_artifact_hashes={
                fold: f"{fold + 11:x}" * 64 for fold in range(5)
            },
        ),
        folds=folds,
        ground_truth=ground_truth,
        scenarios={image_id: frozenset() for image_id in folds},
        policies={fold: FoldPolicy(0.0, 0.0) for fold in range(5)},
        provenance=DevelopmentReportProvenance(
            staged_hashes={
                "annotations.json": "a" * 64,
                "staged_manifest.json": "b" * 64,
            },
            fold_manifest_hashes={
                fold: f"{fold + 1:x}" * 64 for fold in range(5)
            },
            detector_raw_prediction_hashes={
                fold: f"{fold + 5:x}" * 64 for fold in range(5)
            },
            config_bytes=_config_bytes(),
        ),
        expected_staged_images=5,
        expected_staged_boxes=5,
    )

    metrics = json.loads(output.read_text(encoding="utf-8"))["metrics"][
        "overall"
    ]
    assert metrics["errors"]["0.50"]["false_positives"] == 0
    assert metrics["errors"]["0.50"]["misses"] == 1
    assert metrics["unresolved_candidates"] == 1


def test_cross_fit_rejects_non_immutable_detector_hashes():
    artifact, predictions, folds, ground_truth = _selection_fixture()
    artifact = replace(
        artifact,
        run_receipt_hashes={
            **artifact.run_receipt_hashes,
            "fold-0": "not-a-sha256",
        },
    )

    with pytest.raises(ValueError, match="SHA-256"):
        cross_fit_policies(
            detector_oof=artifact,
            verifier_predictions=predictions,
            folds=folds,
            ground_truth=ground_truth,
        )
