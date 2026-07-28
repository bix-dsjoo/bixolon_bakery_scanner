"""Apply a fixed classifier fusion policy to a locked evidence set."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.evidence import atomic_write_bytes
from bakery_scanner.classification.full_evidence import load_full_evidence_rows
from bakery_scanner.classification.fusion_evaluation import evaluate_fusion_decisions
from bakery_scanner.classification.fusion_policy import FusionPolicyArtifact, validate_evidence_hashes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate one fixed classifier fusion policy.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--development-evidence", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _config_hashes(config: ClassifierConfig) -> dict[str, str]:
    return {
        "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
        "repvit_manifest_sha256": config.repvit.manifest_sha256,
        "repvit_prototype_sha256": config.repvit.prototype_bank_sha256 or "0" * 64,
        "dinov3_weights_sha256": config.dinov3.weights_sha256,
        "dinov3_support_sha256": config.dinov3.support_sha256,
        "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256 or "0" * 64,
        "preprocess_sha256": preprocess_sha256(config.preprocess),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ClassifierConfig.load(args.config)
    policy_bytes = args.policy.read_bytes()
    policy = FusionPolicyArtifact.from_json_bytes(policy_bytes)
    if policy.development_evidence_sha256 != hashlib.sha256(args.development_evidence.read_bytes()).hexdigest():
        raise ValueError("development evidence does not match the policy artifact")
    expected_hashes = _config_hashes(config)
    if policy.artifact_hashes != expected_hashes:
        raise ValueError("config artifacts do not match the policy artifact")
    rows = load_full_evidence_rows(args.evidence)
    if any(row.role != "locked_acceptance" or not row.registered for row in rows):
        raise ValueError("evaluation requires registered locked_acceptance evidence only")
    validate_evidence_hashes(rows, expected_hashes)
    decided = tuple(policy.decide(row) for row in rows)
    decisions = tuple(value[0] for value in decided)
    metrics = evaluate_fusion_decisions(decisions)
    payload = {
        "schema_version": 1,
        "evidence_sha256": hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
        "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "metrics": asdict(metrics),
        "target_passes": metrics.target_passes,
        "decisions": [
            {
                "sample_id": decision.sample_id,
                "decision": decision.decision,
                "predicted_sku_id": decision.predicted_sku_id,
                "top3": list(decision.top3),
                "risk": risk,
            }
            for decision, risk in decided
        ],
    }
    atomic_write_bytes(
        args.output,
        json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    return 0 if metrics.target_passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
