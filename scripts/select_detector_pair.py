"""Create an immutable development-only detector-pair selection report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from bakery_scanner.config import ScannerConfig
from bakery_scanner.detectors.experiments import experiment_matrix
from bakery_scanner.detectors.oof import load_complete_oof_artifact, select_complementary_pair
from bakery_scanner.detectors.selection import (
    calibrate_variant_score_thresholds,
    load_staged_ground_truth,
    write_development_selection_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/box_system.yaml"))
    parser.add_argument("--detector-root", type=Path, default=Path("artifacts/box_system/detectors"))
    parser.add_argument("--fold-root", type=Path, default=Path("artifacts/box_system/folds"))
    parser.add_argument("--staged-root", type=Path, default=Path("artifacts/box_system/staged"))
    parser.add_argument("--config-root", type=Path, default=Path("configs/generated/detector-matrix"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = ScannerConfig.load(args.config)
    expected = experiment_matrix(config)
    artifact = load_complete_oof_artifact(
        detector_root=args.detector_root,
        fold_root=args.fold_root,
        staged_root=args.staged_root,
        config_root=args.config_root,
        expected_experiments=expected,
    )
    staged = load_staged_ground_truth(args.staged_root)
    calibrations = calibrate_variant_score_thresholds(
        artifact,
        ground_truth=staged.ground_truth,
        scenarios=staged.scenarios,
    )
    thresholds = {name: value.threshold for name, value in calibrations.items()}
    # Measured end-to-end latency belongs to the later GPU performance audit;
    # use equal neutral values here rather than fabricating latency evidence.
    selection = select_complementary_pair(
        artifact,
        ground_truth=staged.ground_truth,
        scenarios=staged.scenarios,
        score_thresholds=thresholds,
        latency_ms={name: 0.0 for name in thresholds},
    )
    selection_payload = {
        "evidence": [asdict(row) for row in selection.evidence],
        "latency_ms": None,
        "latency_used_for_ranking": False,
        "primary": selection.primary,
        "secondary": selection.secondary,
    }
    report = write_development_selection_report(
        output=args.output,
        artifact=artifact,
        ground_truth=staged.ground_truth,
        scenarios=staged.scenarios,
        calibrations=calibrations,
        selection=selection_payload,
    )
    print(json.dumps({"report": str(report), "scope": "grouped_oof_development_only"}, sort_keys=True))


if __name__ == "__main__":
    main()
