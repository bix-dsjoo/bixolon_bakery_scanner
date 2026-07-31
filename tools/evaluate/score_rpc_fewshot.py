"""Score existing, hash-bound RPC evidence; this tool never runs a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json
from bakery_scanner.experiments.rpc_metrics import (
    ResearchEvidenceRow,
    bootstrap_paired_deltas,
    condition_cohort,
    condition_provenance,
    forced_top1_summary,
    full_system_summary,
    validate_evidence_against_condition,
    validate_paired_evidence,
)
from bakery_scanner.experiments.rpc_protocol import ScoringPlan


def load_canonical_json(path: Path) -> Mapping[str, object]:
    value, _ = _load_canonical_json_with_digest(path)
    return value


def _load_canonical_json_with_digest(path: Path) -> tuple[Mapping[str, object], str]:
    content = path.read_bytes()
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid canonical JSON: {path}") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise ValueError(f"JSON is not canonical: {path}")
    return value, hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class LoadedEvidence:
    """Rows and digest derived from one immutable read of canonical JSONL bytes."""

    rows: tuple[ResearchEvidenceRow, ...]
    sha256: str


def load_canonical_jsonl(path: Path) -> LoadedEvidence:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read evidence: {path}") from exc
    raw_lines = content.splitlines()
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
    return LoadedEvidence(tuple(rows), hashlib.sha256(content).hexdigest())


def score(
    evidence_path: Path,
    reference_path: Path,
    condition_path: Path,
    reference_condition_path: Path,
    base_checkpoint_evidence_path: Path,
    output: Path,
) -> None:
    """Write one non-final condition score; only complete aggregation can pass."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    condition = load_canonical_json(condition_path)
    reference_condition = load_canonical_json(reference_condition_path)
    candidate_plan = _condition_scoring_plan(condition)
    reference_plan = _condition_scoring_plan(reference_condition)
    _validate_comparable_scoring_plans(candidate_plan, reference_plan)
    _validate_paired_condition_axes(
        (_score_receipt_condition(condition, "condition"),),
        (_score_receipt_condition(reference_condition, "condition"),),
    )
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
            "schema_version": 2,
            "kind": "rpc-fewshot-score-receipt",
            "status": "unavailable",
            "decision_status": "unavailable",
            "reason": "candidate or reference condition is unavailable",
            "candidate_condition_id": candidate_id,
            "reference_condition_id": reference_id,
        })
        return
    base_checkpoint_evidence, base_evidence_sha256 = _load_canonical_json_with_digest(
        base_checkpoint_evidence_path
    )
    base_checkpoint_recall = validate_fold_base_checkpoint_evidence(
        condition,
        base_checkpoint_evidence,
        evidence_sha256=base_evidence_sha256,
    )
    reference_base_recall = validate_fold_base_checkpoint_evidence(
        reference_condition,
        base_checkpoint_evidence,
        evidence_sha256=base_evidence_sha256,
    )
    if reference_base_recall != base_checkpoint_recall:
        raise ValueError("candidate/reference fold base checkpoint evidence mismatch")
    candidate_evidence = load_canonical_jsonl(evidence_path)
    reference_evidence = load_canonical_jsonl(reference_path)
    candidate_rows = validate_evidence_against_condition(candidate_evidence.rows, condition)
    reference_rows = validate_evidence_against_condition(reference_evidence.rows, reference_condition)
    candidate_rows, reference_rows = validate_paired_evidence(candidate_rows, reference_rows)
    novel = candidate_novel
    candidate_summary = full_system_summary(candidate_rows, novel_category_ids=novel, reference_rows=reference_rows)
    reference_summary = full_system_summary(reference_rows, novel_category_ids=novel)
    candidate_forced = forced_top1_summary(candidate_rows, novel_category_ids=novel)
    reference_forced = forced_top1_summary(reference_rows, novel_category_ids=novel)
    interval = bootstrap_paired_deltas(
        candidate_rows,
        reference_rows,
        novel_category_ids=novel,
        seed=candidate_plan.bootstrap_seed,
        replicates=candidate_plan.bootstrap_replicates,
    )
    write_new_json(output, {
        "schema_version": 2,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "decision_status": "non_final",
        "candidate_condition_id": candidate_id,
        "reference_condition_id": reference_id,
        "candidate_condition": condition["condition"],
        "reference_condition": reference_condition["condition"],
        "candidate_scoring_plan": candidate_plan.to_dict(),
        "reference_scoring_plan": reference_plan.to_dict(),
        "cohort": {
            "base_category_ids": sorted(candidate_base),
            "novel_category_ids": sorted(novel),
        },
        "candidate_provenance": _provenance(condition, candidate_evidence.sha256),
        "reference_provenance": _provenance(reference_condition, reference_evidence.sha256),
        "candidate_forced_top1": asdict(candidate_forced),
        "reference_forced_top1": asdict(reference_forced),
        "candidate_full_system": asdict(candidate_summary),
        "reference_full_system": asdict(reference_summary),
        "paired_bootstrap_95": asdict(interval),
        "fold_base_checkpoint": {
            "base_macro_final_correct_recall": base_checkpoint_recall,
            "evidence_sha256": base_evidence_sha256,
            "checkpoint_sha256": base_checkpoint_evidence["checkpoint_sha256"],
            "fold": base_checkpoint_evidence["fold"],
        },
        "minimum_rule_inputs": {
            "registered_coverage": candidate_summary.registered_coverage,
            "novel_macro_recall_lower_delta": interval.novel_macro_recall_lower_delta,
            "wrong_registered_sku_rate_upper_delta": interval.wrong_registered_sku_rate_upper_delta,
            "novel_loss_over_10pp_fraction": candidate_summary.novel_loss_over_10pp_fraction,
            "candidate_base_macro_final_correct_recall": (
                candidate_summary.base_macro_final_correct_recall
            ),
            "fold_base_checkpoint_macro_final_correct_recall": base_checkpoint_recall,
        },
    })


def validate_fold_base_checkpoint_evidence(
    condition: Mapping[str, object],
    evidence: Mapping[str, object],
    *,
    evidence_sha256: str,
) -> float:
    """Validate the immutable fold-base score evidence bound by a condition."""
    if not isinstance(evidence, Mapping):
        raise ValueError("fold base checkpoint evidence must be an object")
    expected_fields = {
        "schema_version",
        "kind",
        "fold",
        "checkpoint_sha256",
        "cohort_manifest_sha256",
        "base_category_ids",
        "sample_count",
        "base_macro_final_correct_recall",
    }
    if set(evidence) != expected_fields:
        raise ValueError("fold base checkpoint evidence has missing or unrecognized fields")
    nested = condition.get("condition")
    cohort = condition.get("cohort")
    binding = condition.get("fold_base_checkpoint")
    if not isinstance(nested, Mapping) or not isinstance(cohort, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("condition lacks fold base checkpoint binding")
    if evidence.get("schema_version") != 1 or evidence.get("kind") != "rpc-fewshot-fold-base-checkpoint-evidence":
        raise ValueError("invalid fold base checkpoint evidence schema")
    if evidence.get("fold") != nested.get("fold") or binding.get("fold") != nested.get("fold"):
        raise ValueError("fold base checkpoint evidence fold mismatch")
    if evidence.get("checkpoint_sha256") != binding.get("checkpoint_sha256"):
        raise ValueError("base checkpoint SHA-256 mismatch")
    if evidence_sha256 != binding.get("evidence_sha256"):
        raise ValueError("base checkpoint evidence SHA-256 mismatch")
    if evidence.get("cohort_manifest_sha256") != cohort.get("manifest_sha256"):
        raise ValueError("base checkpoint cohort manifest mismatch")
    base_category_ids = evidence.get("base_category_ids")
    if (
        not isinstance(base_category_ids, list)
        or base_category_ids != cohort.get("base_category_ids")
    ):
        raise ValueError("base checkpoint category cohort mismatch")
    sample_count = evidence.get("sample_count")
    if type(sample_count) is not int or sample_count <= 0:
        raise ValueError("base checkpoint sample_count must be a positive integer")
    recall = evidence.get("base_macro_final_correct_recall")
    if (
        not isinstance(recall, (int, float))
        or isinstance(recall, bool)
        or not math.isfinite(float(recall))
        or not 0.0 <= float(recall) <= 1.0
    ):
        raise ValueError("base checkpoint recall must be finite and in [0, 1]")
    return float(recall)


def aggregate_score_receipts(score_paths: Iterable[Path], output: Path) -> None:
    """Emit a final pass only for an exact, complete declared fold/seed matrix."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    loaded_receipts = tuple(
        _load_canonical_json_with_digest(Path(path)) for path in score_paths
    )
    receipts = tuple(item[0] for item in loaded_receipts)
    if not receipts:
        raise ValueError("aggregate requires score receipts")
    candidate_plan = _score_receipt_plan(receipts[0], "candidate_scoring_plan")
    reference_plan = _score_receipt_plan(receipts[0], "reference_scoring_plan")
    _validate_comparable_scoring_plans(candidate_plan, reference_plan)
    if len(candidate_plan.expected_condition_ids) < 2:
        raise ValueError("a single condition is non-final; no final pass is available")
    for receipt in receipts:
        if (
            receipt.get("schema_version") != 2
            or receipt.get("kind") != "rpc-fewshot-score-receipt"
            or receipt.get("status") != "completed"
            or receipt.get("decision_status") != "non_final"
        ):
            raise ValueError("aggregate accepts only completed non-final score receipts")
        if _score_receipt_plan(receipt, "candidate_scoring_plan") != candidate_plan:
            raise ValueError("candidate scoring plan mismatch")
        if _score_receipt_plan(receipt, "reference_scoring_plan") != reference_plan:
            raise ValueError("reference scoring plan mismatch")
    candidate_conditions = tuple(
        _score_receipt_condition(receipt, "candidate_condition") for receipt in receipts
    )
    reference_conditions = tuple(
        _score_receipt_condition(receipt, "reference_condition") for receipt in receipts
    )
    _validate_paired_condition_axes(candidate_conditions, reference_conditions)
    _validate_complete_condition_set(candidate_conditions, candidate_plan)
    _validate_complete_condition_set(reference_conditions, reference_plan)
    final_pass = all(_minimum_rule_inputs_pass(receipt.get("minimum_rule_inputs")) for receipt in receipts)
    write_new_json(
        output,
        {
            "schema_version": 1,
            "kind": "rpc-fewshot-final-score-receipt",
            "status": "completed",
            "decision_scope": "complete_declared_fold_seed_aggregate",
            "candidate_scoring_plan": candidate_plan.to_dict(),
            "reference_scoring_plan": reference_plan.to_dict(),
            "candidate_scoring_plan_sha256": candidate_plan.sha256,
            "reference_scoring_plan_sha256": reference_plan.sha256,
            "condition_count": len(receipts),
            "candidate_condition_ids": sorted(candidate_plan.expected_condition_ids),
            "reference_condition_ids": sorted(reference_plan.expected_condition_ids),
            "score_receipts": sorted(
                (
                    {
                        "candidate_condition_id": condition["condition_id"],
                        "sha256": digest,
                    }
                    for condition, (_, digest) in zip(
                        candidate_conditions, loaded_receipts, strict=True
                    )
                ),
                key=lambda item: item["candidate_condition_id"],
            ),
            "final_pass": final_pass,
        },
    )


def _provenance(condition: Mapping[str, object], evidence_sha256: str) -> dict[str, str]:
    condition_id, hashes = condition_provenance(condition)
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    binding = condition.get("fold_base_checkpoint")
    plan_sha256 = condition.get("scoring_plan_sha256")
    if not isinstance(binding, Mapping) or not isinstance(plan_sha256, str):
        raise ValueError("condition receipt lacks scoring/base-checkpoint provenance")
    return {
        "condition_id": condition_id,
        "evidence_sha256": evidence_sha256,
        "cohort_manifest_sha256": cohort["manifest_sha256"],
        "base_checkpoint_sha256": binding["checkpoint_sha256"],  # type: ignore[dict-item]
        "base_checkpoint_evidence_sha256": binding["evidence_sha256"],  # type: ignore[dict-item]
        "scoring_plan_sha256": plan_sha256,
        **dict(hashes),
    }


def _cohort_manifest_sha256(condition: Mapping[str, object]) -> str:
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    return cohort["manifest_sha256"]


def _condition_scoring_plan(condition: Mapping[str, object]) -> ScoringPlan:
    if (
        condition.get("schema_version") != 2
        or condition.get("kind") != "rpc-fewshot-experiment-receipt"
    ):
        raise ValueError("unsupported RPC experiment receipt schema")
    raw = condition.get("scoring_plan")
    if not isinstance(raw, Mapping):
        raise ValueError("condition receipt lacks immutable scoring plan")
    plan = ScoringPlan.from_dict(raw)
    if condition.get("scoring_plan_sha256") != plan.sha256:
        raise ValueError("condition scoring plan SHA-256 mismatch")
    nested = condition.get("condition")
    if not isinstance(nested, Mapping):
        raise ValueError("condition receipt lacks condition")
    condition_id = nested.get("condition_id")
    if condition_id not in plan.expected_condition_ids:
        raise ValueError("condition ID is not declared by the scoring plan")
    if nested.get("fold") not in plan.folds or nested.get("support_seed") not in plan.support_seeds:
        raise ValueError("condition fold/seed is not declared by the scoring plan")
    scoring = condition.get("scoring")
    if not isinstance(scoring, Mapping) or scoring.get("registered_category_ids") != list(
        plan.registered_category_ids
    ):
        raise ValueError("condition scoring cohort does not match the scoring plan")
    return plan


def _validate_comparable_scoring_plans(candidate: ScoringPlan, reference: ScoringPlan) -> None:
    if (
        candidate.bootstrap_seed != reference.bootstrap_seed
        or candidate.bootstrap_replicates != reference.bootstrap_replicates
        or candidate.folds != reference.folds
        or candidate.support_seeds != reference.support_seeds
        or candidate.cohort_id != reference.cohort_id
        or candidate.registered_category_ids != reference.registered_category_ids
    ):
        raise ValueError("candidate/reference scoring plan mismatch")


def _score_receipt_plan(receipt: Mapping[str, object], name: str) -> ScoringPlan:
    value = receipt.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"score receipt lacks {name}")
    return ScoringPlan.from_dict(value)


def _score_receipt_condition(receipt: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = receipt.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"score receipt lacks {name}")
    return value


def _validate_complete_condition_set(
    conditions: tuple[Mapping[str, object], ...], plan: ScoringPlan
) -> None:
    condition_ids = tuple(condition.get("condition_id") for condition in conditions)
    if (
        len(condition_ids) != len(set(condition_ids))
        or set(condition_ids) != set(plan.expected_condition_ids)
    ):
        raise ValueError("aggregate requires the complete declared fold/seed condition IDs")
    coordinates = {
        (condition.get("fold"), condition.get("support_seed")) for condition in conditions
    }
    declared = {(fold, seed) for fold in plan.folds for seed in plan.support_seeds}
    if coordinates != declared:
        raise ValueError("aggregate requires the complete declared fold/seed matrix")


def _validate_paired_condition_axes(
    candidate_conditions: tuple[Mapping[str, object], ...],
    reference_conditions: tuple[Mapping[str, object], ...],
) -> None:
    if len(candidate_conditions) != len(reference_conditions) or any(
        (
            candidate.get("fold"),
            candidate.get("support_seed"),
        )
        != (
            reference.get("fold"),
            reference.get("support_seed"),
        )
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    ):
        raise ValueError("candidate/reference score receipts must have paired fold/seed axes")


def _minimum_rule_inputs_pass(value: object) -> bool:
    if not isinstance(value, Mapping):
        raise ValueError("score receipt lacks minimum-rule inputs")
    required = {
        "registered_coverage",
        "novel_macro_recall_lower_delta",
        "wrong_registered_sku_rate_upper_delta",
        "novel_loss_over_10pp_fraction",
        "candidate_base_macro_final_correct_recall",
        "fold_base_checkpoint_macro_final_correct_recall",
    }
    if set(value) != required:
        raise ValueError("minimum-rule inputs have missing or unrecognized fields")
    numeric: dict[str, float] = {}
    for name in required:
        item = value[name]
        if (
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
        ):
            raise ValueError(f"{name} must be finite")
        numeric[name] = float(item)
    tolerance = 1e-12
    return (
        numeric["registered_coverage"] > 0.0
        and numeric["novel_macro_recall_lower_delta"] >= -0.02 - tolerance
        and numeric["wrong_registered_sku_rate_upper_delta"] <= 0.005 + tolerance
        and numeric["novel_loss_over_10pp_fraction"] <= 0.05 + tolerance
        and (
            numeric["candidate_base_macro_final_correct_recall"]
            - numeric["fold_base_checkpoint_macro_final_correct_recall"]
        )
        >= -0.01 - tolerance
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--reference-evidence", type=Path)
    parser.add_argument("--condition", type=Path)
    parser.add_argument("--reference-condition", type=Path)
    parser.add_argument("--base-checkpoint-evidence", type=Path)
    parser.add_argument("--aggregate-score-receipt", action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.aggregate_score_receipt:
            if any(
                value is not None
                for value in (
                    args.evidence,
                    args.reference_evidence,
                    args.condition,
                    args.reference_condition,
                    args.base_checkpoint_evidence,
                )
            ):
                raise ValueError("aggregate mode cannot accept single-condition inputs")
            aggregate_score_receipts(tuple(args.aggregate_score_receipt), args.output)
        else:
            single = (
                args.evidence,
                args.reference_evidence,
                args.condition,
                args.reference_condition,
                args.base_checkpoint_evidence,
            )
            if any(value is None for value in single):
                raise ValueError(
                    "single-condition scoring requires evidence, reference evidence, "
                    "condition, reference condition, and fold base checkpoint evidence"
                )
            score(*single, args.output)  # type: ignore[arg-type]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
