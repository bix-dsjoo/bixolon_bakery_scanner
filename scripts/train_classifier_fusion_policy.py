"""Fit one immutable, common classifier fusion policy from Batch 1 evidence."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.evidence import atomic_write_bytes
from bakery_scanner.classification.full_evidence import load_full_evidence_rows
from bakery_scanner.classification.fusion_policy import FusionPolicyArtifact, select_fusion_threshold
from bakery_scanner.classification.fusion_ranker import fit_oof_ranker, fit_ranker
from bakery_scanner.classification.risk_calibrator import fit_risk_calibrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit one shared fusion/risk classifier policy.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument(
        "--decision-rule",
        choices=(
            "risk_threshold_v1",
            "fusion_local_agree_v1",
            "fusion_local_or_global_consensus_margin_v1",
        ),
        default="risk_threshold_v1",
        help="Immutable SKU acceptance rule to encode in the generated policy artifact.",
    )
    parser.add_argument(
        "--consensus-margin-floor",
        type=float,
        help="Required first-to-second fusion-score floor for the global-consensus rule.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.decision_rule == "fusion_local_or_global_consensus_margin_v1":
        if args.consensus_margin_floor is None:
            raise ValueError("the global-consensus rule requires --consensus-margin-floor")
        schema_version = 3
    else:
        if args.consensus_margin_floor is not None:
            raise ValueError("--consensus-margin-floor only applies to the global-consensus rule")
        schema_version = 2
    config = ClassifierConfig.load(args.config)
    rows = load_full_evidence_rows(args.evidence)
    if any(row.role != "development" or not row.registered for row in rows):
        raise ValueError("fusion policy fitting requires registered development evidence only")
    oof = fit_oof_ranker(rows, folds=args.folds, seed=args.seed)
    risk = fit_risk_calibrator(oof.ranked_rows, seed=args.seed)
    threshold = select_fusion_threshold(oof.ranked_rows, risk)
    if threshold is None:
        raise ValueError("no common fusion threshold meets Batch 1 acceptance targets")
    policy = FusionPolicyArtifact(
        ranker=fit_ranker(rows, seed=args.seed),
        risk_calibrator=risk,
        risk_threshold=threshold,
        development_evidence_sha256=hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "repvit_prototype_sha256": config.repvit.prototype_bank_sha256 or "0" * 64,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256 or "0" * 64,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
        decision_rule=args.decision_rule,
        schema_version=schema_version,
        consensus_margin_floor=args.consensus_margin_floor,
    )
    atomic_write_bytes(args.output, policy.to_json_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
