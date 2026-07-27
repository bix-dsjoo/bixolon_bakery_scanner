"""Evaluate one immutable calibration artifact on locked evidence exactly once."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.evidence import (
    EvaluatedRow,
    EvidenceRow,
    atomic_write_bytes,
    canonical_json_bytes,
    evaluate_rows,
    load_evidence_rows,
    policy_predictions,
    sha256_file,
)
from bakery_scanner.classification.policy import PolicyCalibration


def _empty_metrics() -> dict[str, object]:
    return {
        "assisted_correct": 0,
        "assisted_failures": 0,
        "assisted_success": None,
        "auto_correct": 0,
        "auto_count": 0,
        "auto_coverage": 0.0,
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
) -> dict[str, object]:
    """Build canonical locked-set slices without selecting any parameters."""
    if len(rows) != len(evaluated) or not rows:
        raise ValueError("report requires one evaluated result per evidence row")
    if any(row.role != "locked_acceptance" for row in rows):
        raise ValueError("locked evaluation accepts locked_acceptance rows only")
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
    }
    first = rows[0]
    return {
        "artifacts": {
            "calibration_sha256": calibration_sha256,
            "dinov3_artifact_id": first.dinov3_artifact_id,
            "evidence_sha256": evidence_sha256,
            "repvit_artifact_id": first.repvit_artifact_id,
        },
        "failures": {
            "assisted_failures": assisted_failures,
            "automatic_errors": automatic_errors,
            "fallback_top3_misses": fallback_misses,
        },
        "metrics": metrics,
        "release_passes": overall.release_passes,
        "schema_version": 1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate an existing policy once on locked acceptance evidence."
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load_evidence_rows(args.evidence)
    if any(row.role != "locked_acceptance" for row in rows):
        raise ValueError("locked evaluation accepts locked_acceptance rows only")
    calibration_payload = args.calibration.read_bytes()
    calibration = PolicyCalibration.from_json_bytes(calibration_payload)
    evaluated = policy_predictions(rows, calibration)
    report = build_evaluation_report(
        rows,
        evaluated,
        calibration_sha256=sha256_file(args.calibration),
        evidence_sha256=sha256_file(args.evidence),
    )
    atomic_write_bytes(args.output, canonical_json_bytes(report))
    return 0 if report["release_passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
