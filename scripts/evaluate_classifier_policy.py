"""Evaluate one immutable calibration artifact on locked evidence exactly once."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping, Sequence

from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.classification.evidence import (
    EvaluatedRow,
    EvidenceRow,
    LockedCoverageContract,
    atomic_write_bytes,
    canonical_json_bytes,
    evaluate_rows,
    load_evidence_rows,
    load_dinov3_support_training_hashes,
    load_repvit_training_hashes,
    policy_predictions,
    sha256_file,
    hash_evidence_rows,
    hash_evidence_identities,
    validate_evidence_provenance,
)
from bakery_scanner.classification.policy import PolicyCalibration


_ARTIFACT_HASH_KEYS = frozenset(
    {
        "repvit_checkpoint_sha256",
        "repvit_manifest_sha256",
        "dinov3_weights_sha256",
        "dinov3_support_sha256",
    }
)


def _empty_metrics() -> dict[str, object]:
    return {
        "assisted_correct": 0,
        "assisted_failures": 0,
        "assisted_success": None,
        "auto_correct": 0,
        "auto_count": 0,
        "auto_coverage": None,
        "auto_errors": 0,
        "auto_precision": None,
        "failure_sample_ids": [],
        "fallback_top3_correct": 0,
        "fallback_top3_denominator": 0,
        "fallback_top3_misses": 0,
        "fallback_top3_recall": None,
        "registered_count": 0,
        "sample_count": 0,
        "unknown_count": 0,
        "unregistered_count": 0,
    }


def _slice_metrics(
    rows: Sequence[EvidenceRow],
    evaluated: Sequence[EvaluatedRow],
    predicate,
) -> dict[str, object]:
    selected = tuple(
        outcome for row, outcome in zip(rows, evaluated, strict=True) if predicate(row)
    )
    if not selected:
        return _empty_metrics()
    return evaluate_rows(selected).to_dict()


def build_evaluation_report(
    rows: Sequence[EvidenceRow],
    evaluated: Sequence[EvaluatedRow],
    *,
    calibration_sha256: str,
    evidence_sha256: str,
    artifact_hashes: Mapping[str, str],
    coverage_contract: LockedCoverageContract | None = None,
) -> dict[str, object]:
    """Build canonical locked-set slices without selecting any parameters."""
    if len(rows) != len(evaluated) or not rows:
        raise ValueError("report requires one evaluated result per evidence row")
    if any(row.role != "locked_acceptance" for row in rows):
        raise ValueError("locked evaluation accepts locked_acceptance rows only")
    if set(artifact_hashes) != _ARTIFACT_HASH_KEYS or any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in artifact_hashes.values()
    ):
        raise ValueError("artifact_hashes must contain exact lowercase SHA-256 values")
    overall = evaluate_rows(tuple(evaluated))
    automatic_errors = [
        outcome.sample_id
        for outcome in evaluated
        if outcome.decision == "sku"
        and (not outcome.registered or outcome.predicted_sku_id != outcome.sku_id)
    ]
    fallback_misses = [
        outcome.sample_id
        for outcome in evaluated
        if outcome.decision == "unknown"
        and outcome.registered
        and outcome.sku_id not in outcome.top3
    ]
    assisted_failures = sorted(
        set(automatic_errors).union(fallback_misses),
        key=lambda sample_id: next(
            index
            for index, outcome in enumerate(evaluated)
            if outcome.sample_id == sample_id
        ),
    )
    metrics = {
        "overall": overall.to_dict(),
        "per_sku": {
            str(sku_id): _slice_metrics(
                rows,
                evaluated,
                lambda row, sku_id=sku_id: row.registered and row.sku_id == sku_id,
            )
            for sku_id in range(1, 21)
        },
        "base_15": _slice_metrics(
            rows,
            evaluated,
            lambda row: (
                row.registered and row.sku_id is not None and 1 <= row.sku_id <= 15
            ),
        ),
        "incremental_5": _slice_metrics(
            rows,
            evaluated,
            lambda row: (
                row.registered and row.sku_id is not None and 16 <= row.sku_id <= 20
            ),
        ),
        "registered": _slice_metrics(
            rows,
            evaluated,
            lambda row: row.registered,
        ),
        "unregistered": _slice_metrics(
            rows,
            evaluated,
            lambda row: not row.registered,
        ),
        "scenarios": {
            scenario: _slice_metrics(
                rows,
                evaluated,
                lambda row, scenario=scenario: scenario in row.scenarios,
            )
            for scenario in (
                coverage_contract.required_scenarios if coverage_contract else ()
            )
        },
    }
    coverage = (
        coverage_contract.report(rows) if coverage_contract else {"complete": False}
    )
    scenario_passes = all(
        values["auto_errors"] == 0
        and values["fallback_top3_misses"] == 0
        and values["assisted_failures"] == 0
        for values in metrics["scenarios"].values()
    )
    first = rows[0]
    return {
        "artifacts": {
            "calibration_sha256": calibration_sha256,
            "dinov3_artifact_id": first.dinov3_artifact_id,
            "dinov3_support_sha256": artifact_hashes["dinov3_support_sha256"],
            "dinov3_weights_sha256": artifact_hashes["dinov3_weights_sha256"],
            "evidence_sha256": evidence_sha256,
            "repvit_artifact_id": first.repvit_artifact_id,
            "repvit_checkpoint_sha256": artifact_hashes["repvit_checkpoint_sha256"],
            "repvit_manifest_sha256": artifact_hashes["repvit_manifest_sha256"],
        },
        "failures": {
            "assisted_failures": assisted_failures,
            "automatic_errors": automatic_errors,
            "fallback_top3_misses": fallback_misses,
        },
        "metrics": metrics,
        "coverage": coverage,
        "release_passes": overall.release_passes
        and coverage["complete"]
        and scenario_passes,
        "schema_version": 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an existing policy once on locked acceptance evidence."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--development-evidence", type=Path, required=True)
    parser.add_argument("--dino-source-manifest", type=Path, required=True)
    parser.add_argument("--coverage-contract", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ClassifierConfig.load(args.config)
    coverage_contract = LockedCoverageContract.load(args.coverage_contract)
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
    if any(row.role != "locked_acceptance" for row in rows):
        raise ValueError("locked evaluation accepts locked_acceptance rows only")
    development_rows = load_evidence_rows(
        args.development_evidence, training_image_hashes=training_hashes
    )
    if any(row.role != "development" for row in development_rows):
        raise ValueError("development evidence must contain development rows only")
    if {row.image_sha256 for row in rows}.intersection(
        row.image_sha256 for row in development_rows
    ):
        raise ValueError("development and locked evidence image identities overlap")
    validate_evidence_provenance(rows, config)
    validate_evidence_provenance(development_rows, config)
    calibration_payload = args.calibration.read_bytes()
    calibration = PolicyCalibration.from_json_bytes(calibration_payload)
    if calibration.evidence_sha256 != hash_evidence_rows(development_rows):
        raise ValueError(
            "calibration is not bound to the supplied development evidence"
        )
    if calibration.development_identity_sha256 != hash_evidence_identities(
        development_rows
    ):
        raise ValueError(
            "calibration development identity does not match supplied evidence"
        )
    evaluated = policy_predictions(rows, calibration)
    report = build_evaluation_report(
        rows,
        evaluated,
        calibration_sha256=sha256_file(args.calibration),
        evidence_sha256=sha256_file(args.evidence),
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
        },
        coverage_contract=coverage_contract,
    )
    atomic_write_bytes(args.output, canonical_json_bytes(report))
    return 0 if report["release_passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
