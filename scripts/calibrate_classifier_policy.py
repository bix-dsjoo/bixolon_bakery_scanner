"""Select a classifier policy using grouped development evidence only."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.evidence import (
    atomic_write_bytes,
    load_evidence_rows,
    load_dinov3_support_training_hashes,
    load_repvit_training_hashes,
    select_policy,
    validate_evidence_provenance,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-fit and select classifier abstention policy parameters."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--dino-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260727)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ClassifierConfig.load(args.config)
    training_hashes = load_repvit_training_hashes(
        config.repvit.manifest,
        expected_sha256=config.repvit.manifest_sha256,
    ) | load_dinov3_support_training_hashes(
        config.dinov3.support, args.dino_source_manifest
    )
    rows = load_evidence_rows(
        args.evidence,
        training_image_hashes=training_hashes,
    )
    validate_evidence_provenance(rows, config)
    calibration = select_policy(
        rows,
        folds=args.folds,
        seed=args.seed,
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
    )
    atomic_write_bytes(args.output, calibration.to_json_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
