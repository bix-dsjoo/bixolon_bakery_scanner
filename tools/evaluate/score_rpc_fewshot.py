"""Score existing, hash-bound RPC evidence; this tool never runs a model."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json
from bakery_scanner.experiments.rpc_metrics import (
    ResearchEvidenceRow,
    bootstrap_paired_deltas,
    condition_provenance,
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
    novel_category_ids: set[int] | None = None,
) -> None:
    """Write one compact score receipt from existing evidence only."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    condition = load_canonical_json(condition_path)
    reference_condition = load_canonical_json(reference_condition_path)
    candidate_id, _ = condition_provenance(condition)
    reference_id, _ = condition_provenance(reference_condition)
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
    novel = novel_category_ids if novel_category_ids is not None else _novel_categories(condition)
    candidate_summary = full_system_summary(candidate_rows, novel_category_ids=novel, reference_rows=reference_rows)
    reference_summary = full_system_summary(reference_rows, novel_category_ids=novel)
    interval = bootstrap_paired_deltas(candidate_rows, reference_rows, novel_category_ids=novel, seed=bootstrap_seed, replicates=bootstrap_replicates)
    write_new_json(output, {
        "schema_version": 1,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "candidate_condition_id": candidate_id,
        "reference_condition_id": reference_id,
        "novel_category_ids": sorted(novel),
        "candidate": asdict(candidate_summary),
        "reference": asdict(reference_summary),
        "paired_bootstrap_95": asdict(interval),
        "passes_minimum_rule": passes_minimum_rule(candidate_summary, reference_summary, interval),
    })


def _novel_categories(condition: Mapping[str, object]) -> set[int]:
    value: object = condition.get("novel_category_ids")
    if value is None and isinstance(condition.get("condition"), Mapping):
        value = condition["condition"].get("novel_category_ids")  # type: ignore[index]
    if not isinstance(value, list) or not value or any(type(item) is not int or item <= 0 for item in value):
        raise ValueError("condition receipt must declare nonempty novel_category_ids")
    if len(set(value)) != len(value):
        raise ValueError("condition receipt has duplicate novel_category_ids")
    return set(value)


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
    parser.add_argument("--novel-category-id", type=int, action="append")
    args = parser.parse_args(argv)
    try:
        explicit_novel = set(args.novel_category_id) if args.novel_category_id is not None else None
        if explicit_novel is not None and (not explicit_novel or any(item <= 0 for item in explicit_novel)):
            raise ValueError("novel category IDs must be positive")
        score(
            args.evidence,
            args.reference_evidence,
            args.condition,
            args.reference_condition,
            args.output,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_replicates=args.bootstrap_replicates,
            novel_category_ids=explicit_novel,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
