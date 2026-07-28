"""Create the immutable D-FINE-N 640 plus verifier development report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from bakery_scanner.config import ScannerConfig
from bakery_scanner.detectors.dfine640_selection import (
    DevelopmentReportProvenance,
    cross_fit_policies,
    load_complete_verifier_oof_artifact,
    write_cross_fit_development_report,
)
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import load_complete_oof_artifact
from bakery_scanner.detectors.selection import load_staged_ground_truth


SEED = 20260724


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detector-root",
        type=Path,
        default=Path("artifacts/box_system/detectors"),
    )
    parser.add_argument(
        "--verifier-root",
        type=Path,
        default=Path("artifacts/box_system/verifiers"),
    )
    parser.add_argument(
        "--fold-root",
        type=Path,
        default=Path("artifacts/box_system/folds"),
    )
    parser.add_argument(
        "--staged-root",
        type=Path,
        default=Path("artifacts/box_system/staged"),
    )
    parser.add_argument(
        "--detector-config-root",
        type=Path,
        default=Path("configs/generated/detector-matrix"),
    )
    parser.add_argument("--expected-images", type=int, default=299)
    parser.add_argument("--expected-boxes", type=int, default=1410)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--validate-detector-fold", type=int, choices=range(5))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.validate_detector_fold is not None:
        if args.config is None:
            parser.error("--validate-detector-fold requires --config")
        validate_detector_fold(args.config, args.validate_detector_fold)
        print(
            json.dumps(
                {
                    "fold": args.validate_detector_fold,
                    "status": "detector_fold_validated",
                },
                sort_keys=True,
            )
        )
        return
    if args.output is None:
        parser.error("--output is required unless --validate-detector-fold is used")

    experiments = tuple(
        DetectorExperiment("dfine_n_640", "dfine", 640, SEED, fold)
        for fold in range(5)
    )
    detector_oof = load_complete_oof_artifact(
        detector_root=args.detector_root,
        fold_root=args.fold_root,
        staged_root=args.staged_root,
        config_root=args.detector_config_root,
        expected_experiments=experiments,
        expected_images=args.expected_images,
        expected_boxes=args.expected_boxes,
    )
    verifier_oof = load_complete_verifier_oof_artifact(
        verifier_root=args.verifier_root,
        detector_root=args.detector_root,
        fold_root=args.fold_root,
        staged_root=args.staged_root,
        seed=SEED,
    )
    staged = load_staged_ground_truth(args.staged_root)
    folds = _load_image_folds(args.fold_root)
    policies = cross_fit_policies(
        detector_oof=detector_oof,
        verifier_predictions=verifier_oof.predictions_by_fold,
        folds=folds,
        ground_truth=staged.ground_truth,
    )
    report = write_cross_fit_development_report(
        output=args.output,
        detector_oof=detector_oof,
        verifier_oof=verifier_oof,
        folds=folds,
        ground_truth=staged.ground_truth,
        scenarios=staged.scenarios,
        policies=policies,
        provenance=_load_provenance(args),
    )
    print(
        json.dumps(
            {
                "operational_guarantee": False,
                "report": str(report),
                "scope": "grouped_cross_fit_development_only",
            },
            sort_keys=True,
        )
    )


def _load_image_folds(fold_root: Path) -> dict[int, int]:
    folds: dict[int, int] = {}
    for fold in range(5):
        path = Path(fold_root) / f"fold-{fold}" / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for image_id in payload["validation_image_ids"]:
            if image_id in folds:
                raise ValueError("validation folds must not overlap")
            folds[image_id] = fold
    return folds


def validate_detector_fold(config_path: Path, fold: int) -> None:
    """Validate one completed D-FINE-N 640 fold from config-resolved paths."""
    config_path = Path(config_path).resolve()
    config = ScannerConfig.load(config_path)
    if fold not in range(config.dataset.folds):
        raise ValueError("detector fold is outside the configured fold range")
    experiment = DetectorExperiment("dfine_n_640", "dfine", 640, config.seed, fold)
    run_root = config.artifact_root / "detectors" / experiment.run_id
    manifest_path = config.artifact_root / "folds" / f"fold-{fold}" / "manifest.json"
    prediction_path = run_root / "validation_predictions.json"
    processed_path = run_root / "processed_validation_image_ids.json"
    detector_config = (
        config_path.parent
        / "generated"
        / "detector-matrix"
        / f"{experiment.run_id}.yml"
    )
    receipt = _read_json_object(run_root / "receipt.json", "detector receipt")
    required = {
        "config_sha256": _sha256(detector_config),
        "fold": fold,
        "fold_manifest_sha256": _sha256(manifest_path),
        "prediction_sha256": _sha256(prediction_path),
        "processed_images_sha256": _sha256(processed_path),
        "run_id": experiment.run_id,
        "seed": config.seed,
        "status": "completed",
        "variant": experiment.name,
    }
    if any(receipt.get(name) != value for name, value in required.items()):
        raise ValueError("detector receipt identity or artifact hash mismatch")

    manifest = _read_json_object(manifest_path, "fold manifest")
    if manifest.get("index") != fold:
        raise ValueError("fold manifest index does not match requested fold")
    validation_ids = _positive_unique_ids(
        manifest.get("validation_image_ids"), "validation image ids"
    )
    training_ids = _positive_unique_ids(
        manifest.get("training_image_ids"), "training image ids"
    )
    if validation_ids & training_ids:
        raise ValueError("fold training and validation image ids must be disjoint")
    processed_ids = _positive_unique_ids(
        _read_json_array(processed_path, "processed validation image ids"),
        "processed validation image ids",
    )
    if processed_ids != validation_ids:
        raise ValueError("processed validation image ids do not exactly match the fold")
    for prediction in _read_json_array(prediction_path, "validation predictions"):
        if not isinstance(prediction, dict):
            raise ValueError("validation prediction must be an object")
        image_id = prediction.get("image_id")
        if type(image_id) is not int or image_id not in validation_ids:
            raise ValueError("validation prediction image id must belong to the held-out fold")
        if prediction.get("source") != experiment.name:
            raise ValueError("validation prediction source must match D-FINE-N 640")
        score = prediction.get("score")
        bbox = prediction.get("bbox")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 <= score <= 1
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in bbox
            )
        ):
            raise ValueError("validation prediction score or bbox is invalid")


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_json_array(path: Path, label: str) -> list[object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _positive_unique_ids(value: object, label: str) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    values = frozenset(
        item
        for item in value
        if isinstance(item, int) and not isinstance(item, bool) and item > 0
    )
    if not values or len(values) != len(value):
        raise ValueError(f"{label} must contain unique positive ids")
    return values


def _load_provenance(args: argparse.Namespace) -> DevelopmentReportProvenance:
    staged_paths = {
        "annotations.json": args.staged_root / "annotations.json",
        "staged_manifest.json": args.staged_root / "staged_manifest.json",
    }
    fold_paths = {
        fold: args.fold_root / f"fold-{fold}" / "manifest.json"
        for fold in range(5)
    }
    raw_paths = {
        fold: args.detector_root
        / f"dfine_n_640-seed{SEED}-fold{fold}"
        / "validation_predictions.raw.json"
        for fold in range(5)
    }
    config_paths = {
        f"detector/fold-{fold}.yml": args.detector_config_root
        / f"dfine_n_640-seed{SEED}-fold{fold}.yml"
        for fold in range(5)
    }
    config_paths.update(
        {
            f"verifier/fold-{fold}.json": args.verifier_root
            / f"mobilenetv4_conv_small-seed{SEED}-fold{fold}"
            / "verifier_config.json"
            for fold in range(5)
        }
    )
    return DevelopmentReportProvenance(
        staged_hashes={
            name: _sha256(path) for name, path in staged_paths.items()
        },
        fold_manifest_hashes={
            fold: _sha256(path) for fold, path in fold_paths.items()
        },
        detector_raw_prediction_hashes={
            fold: _sha256(path) for fold, path in raw_paths.items()
        },
        config_bytes={
            name: path.read_bytes() for name, path in config_paths.items()
        },
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
