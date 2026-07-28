"""Create the immutable detector-only grouped cross-fit development report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bakery_scanner.config import ScannerConfig
from bakery_scanner.detectors.detector_only_selection import (
    cross_fit_detector_only_policies,
    DetectorOnlyReportProvenance,
    write_detector_only_report,
)
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.oof import load_complete_oof_artifact
from bakery_scanner.detectors.selection import load_staged_ground_truth


_SEED = 20260724
_FOLD_COUNT = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = ScannerConfig.load(config_path)
    _require_detector_only_config(config)
    experiments = tuple(
        DetectorExperiment("dfine_n_640", "dfine", 640, _SEED, fold)
        for fold in range(_FOLD_COUNT)
    )
    detector_oof = load_complete_oof_artifact(
        detector_root=config.artifact_root / "detectors",
        fold_root=config.artifact_root / "folds",
        staged_root=config.artifact_root / "staged",
        config_root=config_path.parent / "generated" / "detector-matrix",
        expected_experiments=experiments,
    )
    staged = load_staged_ground_truth(config.artifact_root / "staged")
    folds = _load_image_folds(config.artifact_root / "folds")
    policies = cross_fit_detector_only_policies(
        detector_oof,
        folds=folds,
        ground_truth=staged.ground_truth,
    )
    report = write_detector_only_report(
        output=args.output,
        detector_oof=detector_oof,
        folds=folds,
        ground_truth=staged.ground_truth,
        scenarios=staged.scenarios,
        policies=policies,
        provenance=_report_provenance(
            staged_root=config.artifact_root / "staged",
            fold_root=config.artifact_root / "folds",
        ),
        expected_staged_images=config.dataset.expected_images,
        expected_staged_boxes=config.dataset.expected_boxes,
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "locked_zero_error_passed": payload[
                    "locked_zero_error_passed"
                ],
                "operational_guarantee": False,
                "path": str(report),
            },
            sort_keys=True,
        )
    )


def _require_detector_only_config(config: ScannerConfig) -> None:
    matching = tuple(
        variant
        for variant in config.detectors.variants
        if variant.name == "dfine_n_640"
        and variant.backend == "dfine"
        and variant.input_size == 640
    )
    if (
        config.seed != _SEED
        or config.dataset.folds != _FOLD_COUNT
        or config.runtime.proposal_limit != 30
        or len(matching) != 1
    ):
        raise ValueError(
            "detector-only selection requires D-FINE-N 640 seed 20260724, "
            "five folds, and top-30 raw proposals"
        )


def _load_image_folds(fold_root: Path) -> dict[int, int]:
    folds: dict[int, int] = {}
    for fold in range(_FOLD_COUNT):
        path = Path(fold_root) / f"fold-{fold}" / "manifest.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"fold manifest must be readable UTF-8 JSON: {path}") from exc
        if not isinstance(payload, dict) or payload.get("index") != fold:
            raise ValueError("fold manifest index does not match its path")
        image_ids = payload.get("validation_image_ids")
        if (
            not isinstance(image_ids, list)
            or not image_ids
            or any(
                isinstance(image_id, bool)
                or not isinstance(image_id, int)
                or image_id <= 0
                for image_id in image_ids
            )
            or len(set(image_ids)) != len(image_ids)
        ):
            raise ValueError(
                "fold validation_image_ids must contain unique positive ids"
            )
        for image_id in image_ids:
            if image_id in folds:
                raise ValueError("validation folds must not overlap")
            folds[image_id] = fold
    return folds


def _report_provenance(
    *,
    staged_root: Path,
    fold_root: Path,
) -> DetectorOnlyReportProvenance:
    return DetectorOnlyReportProvenance(
        staged_annotations_sha256=_sha256_file(staged_root / "annotations.json"),
        staged_manifest_sha256=_sha256_file(staged_root / "staged_manifest.json"),
        fold_manifest_sha256={
            fold: _sha256_file(fold_root / f"fold-{fold}" / "manifest.json")
            for fold in range(_FOLD_COUNT)
        },
    )


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"provenance artifact is unreadable: {path}") from exc


if __name__ == "__main__":
    main()
