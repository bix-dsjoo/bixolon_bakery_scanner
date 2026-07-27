"""Create the immutable D-FINE-N 640 plus verifier development report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

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
