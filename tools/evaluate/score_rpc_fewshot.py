"""Score existing, hash-bound RPC evidence; this tool never runs a model."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json
from bakery_scanner.experiments.rpc_metrics import (
    ResearchEvidenceRow,
    bootstrap_paired_deltas,
    condition_cohort,
    condition_provenance,
    forced_top1_summary,
    full_system_summary,
    passes_minimum_rule,
    validate_evidence_against_condition,
    validate_paired_evidence,
)


def load_canonical_json(path: Path) -> Mapping[str, object]:
    content = path.read_bytes()
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid canonical JSON: {path}") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise ValueError(f"JSON is not canonical: {path}")
    return value


def load_canonical_jsonl(path: Path) -> tuple[ResearchEvidenceRow, ...]:
    try:
        raw_lines = path.read_bytes().splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read evidence: {path}") from exc
    if not raw_lines:
        raise ValueError("evidence must not be empty")
    rows: list[ResearchEvidenceRow] = []
    for number, line in enumerate(raw_lines, start=1):
        if not line:
            raise ValueError(f"blank evidence line {number}")
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid evidence JSONL line {number}") from exc
        if not isinstance(value, dict) or canonical_json_bytes(value) != line:
            raise ValueError(f"evidence JSONL line {number} is not canonical")
        try:
            rows.append(ResearchEvidenceRow.from_dict(value))
        except ValueError as exc:
            raise ValueError(f"invalid evidence JSONL line {number}") from exc
    return tuple(rows)


def score(
    evidence_path: Path,
    reference_path: Path,
    condition_path: Path,
    reference_condition_path: Path,
    output: Path,
    *,
    bootstrap_seed: int,
    bootstrap_replicates: int,
) -> None:
    """Write one compact score receipt from existing evidence only."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    condition = load_canonical_json(condition_path)
    reference_condition = load_canonical_json(reference_condition_path)
    candidate_id, _ = condition_provenance(condition)
    reference_id, _ = condition_provenance(reference_condition)
    candidate_novel, candidate_base = condition_cohort(condition)
    reference_novel, reference_base = condition_cohort(reference_condition)
    if candidate_novel != reference_novel or candidate_base != reference_base:
        raise ValueError("candidate/reference condition cohort mismatch")
    if _cohort_manifest_sha256(condition) != _cohort_manifest_sha256(reference_condition):
        raise ValueError("candidate/reference cohort manifest mismatch")
    statuses = (condition.get("status"), reference_condition.get("status"))
    if statuses != ("completed", "completed"):
        write_new_json(output, {
            "schema_version": 1,
            "kind": "rpc-fewshot-score-receipt",
            "status": "unavailable",
            "reason": "candidate or reference condition is unavailable",
            "candidate_condition_id": candidate_id,
            "reference_condition_id": reference_id,
        })
        return
    candidate_rows = validate_evidence_against_condition(load_canonical_jsonl(evidence_path), condition)
    reference_rows = validate_evidence_against_condition(load_canonical_jsonl(reference_path), reference_condition)
    candidate_rows, reference_rows = validate_paired_evidence(candidate_rows, reference_rows)
    novel = candidate_novel
    candidate_summary = full_system_summary(candidate_rows, novel_category_ids=novel, reference_rows=reference_rows)
    reference_summary = full_system_summary(reference_rows, novel_category_ids=novel)
    candidate_forced = forced_top1_summary(candidate_rows, novel_category_ids=novel)
    reference_forced = forced_top1_summary(reference_rows, novel_category_ids=novel)
    interval = bootstrap_paired_deltas(candidate_rows, reference_rows, novel_category_ids=novel, seed=bootstrap_seed, replicates=bootstrap_replicates)
    write_new_json(output, {
        "schema_version": 1,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "candidate_condition_id": candidate_id,
        "reference_condition_id": reference_id,
        "cohort": {
            "base_category_ids": sorted(candidate_base),
            "novel_category_ids": sorted(novel),
        },
        "candidate_provenance": _provenance(condition, evidence_path),
        "reference_provenance": _provenance(reference_condition, reference_path),
        "candidate_forced_top1": asdict(candidate_forced),
        "reference_forced_top1": asdict(reference_forced),
        "candidate_full_system": asdict(candidate_summary),
        "reference_full_system": asdict(reference_summary),
        "paired_bootstrap_95": asdict(interval),
        "passes_minimum_rule": passes_minimum_rule(candidate_summary, reference_summary, interval),
    })


def _provenance(condition: Mapping[str, object], evidence_path: Path) -> dict[str, str]:
    condition_id, hashes = condition_provenance(condition)
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    return {
        "condition_id": condition_id,
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "cohort_manifest_sha256": cohort["manifest_sha256"],
        **dict(hashes),
    }


def _cohort_manifest_sha256(condition: Mapping[str, object]) -> str:
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    return cohort["manifest_sha256"]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--reference-evidence", required=True, type=Path)
    parser.add_argument("--condition", required=True, type=Path)
    parser.add_argument("--reference-condition", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-seed", required=True, type=int)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        score(
            args.evidence,
            args.reference_evidence,
            args.condition,
            args.reference_condition,
            args.output,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_replicates=args.bootstrap_replicates,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
