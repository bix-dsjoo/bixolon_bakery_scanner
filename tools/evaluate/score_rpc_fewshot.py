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
    BranchName,
    FullSystemSummary,
    LockedGroundTruthRow,
    PairedConditionEvidence,
    ResearchEvidenceRow,
    branch_top1_agreement,
    branch_top1_summary,
    bootstrap_paired_condition_deltas,
    bootstrap_paired_deltas,
    condition_cohort,
    condition_provenance,
    full_system_summary,
    validate_evidence_against_condition,
    validate_evidence_completeness,
    validate_paired_evidence,
)
from bakery_scanner.experiments.rpc_protocol import (
    ExperimentCondition,
    ScoringPlan,
    StageFourSelection,
)


_SCORE_BRANCHES: tuple[BranchName, ...] = (
    "repvit_global",
    "dinov3_global",
    "dinov3_local",
)


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


@dataclass(frozen=True, slots=True)
class LoadedGroundTruth:
    """Validated locked object identities and the canonical file digest."""

    rows: tuple[LockedGroundTruthRow, ...]
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


def load_locked_ground_truth(path: Path) -> LoadedGroundTruth:
    value, digest = _load_canonical_json_with_digest(path)
    if (
        set(value) != {"schema_version", "kind", "objects"}
        or value.get("schema_version") != 1
        or value.get("kind") != "rpc-fewshot-locked-ground-truth"
        or not isinstance(value.get("objects"), list)
        or not value["objects"]
    ):
        raise ValueError("invalid locked ground-truth manifest")
    try:
        rows = tuple(
            LockedGroundTruthRow.from_dict(item)
            for item in value["objects"]  # type: ignore[union-attr]
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid locked ground-truth manifest") from exc
    identities = [row.identity for row in rows]
    object_ids = [row.object_id for row in rows]
    if (
        len(identities) != len(set(identities))
        or len(object_ids) != len(set(object_ids))
    ):
        raise ValueError("locked ground-truth manifest contains duplicate objects")
    return LoadedGroundTruth(rows, digest)


def score(
    evidence_path: Path,
    reference_path: Path,
    condition_path: Path,
    reference_condition_path: Path,
    ground_truth_manifest_path: Path,
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
    paired_stage = _paired_condition_stage(condition, reference_condition)
    stage_four_selection = None
    if paired_stage == "locked":
        stage_four_selection = _validate_locked_condition_receipt_pair(
            condition, reference_condition
        )
    candidate_id, _ = condition_provenance(condition)
    reference_id, _ = condition_provenance(reference_condition)
    candidate_novel, candidate_base = condition_cohort(condition)
    reference_novel, reference_base = condition_cohort(reference_condition)
    if candidate_novel != reference_novel or candidate_base != reference_base:
        raise ValueError("candidate/reference condition cohort mismatch")
    if _cohort_manifest_sha256(condition) != _cohort_manifest_sha256(reference_condition):
        raise ValueError("candidate/reference cohort manifest mismatch")
    ground_truth = load_locked_ground_truth(ground_truth_manifest_path)
    if ground_truth.sha256 != _cohort_manifest_sha256(condition):
        raise ValueError("locked ground-truth manifest SHA-256 mismatch")
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
    candidate_rows = validate_evidence_completeness(
        candidate_evidence.rows, ground_truth.rows
    )
    reference_rows = validate_evidence_completeness(
        reference_evidence.rows, ground_truth.rows
    )
    candidate_rows = validate_evidence_against_condition(candidate_rows, condition)
    reference_rows = validate_evidence_against_condition(
        reference_rows, reference_condition
    )
    candidate_rows, reference_rows = validate_paired_evidence(candidate_rows, reference_rows)
    novel = candidate_novel
    candidate_summary = full_system_summary(candidate_rows, novel_category_ids=novel, reference_rows=reference_rows)
    reference_summary = full_system_summary(reference_rows, novel_category_ids=novel)
    candidate_branches = _branch_top1_summaries(candidate_rows, novel)
    reference_branches = _branch_top1_summaries(reference_rows, novel)
    interval = bootstrap_paired_deltas(
        candidate_rows,
        reference_rows,
        novel_category_ids=novel,
        seed=candidate_plan.bootstrap_seed,
        replicates=candidate_plan.bootstrap_replicates,
    )
    score_receipt: dict[str, object] = {
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
        "candidate_branch_top1": candidate_branches,
        "reference_branch_top1": reference_branches,
        "candidate_full_system": asdict(candidate_summary),
        "reference_full_system": asdict(reference_summary),
        "paired_bootstrap_95": asdict(interval),
        "fold_base_checkpoint": {
            "base_macro_final_correct_recall": base_checkpoint_recall,
            "evidence_sha256": base_evidence_sha256,
            "checkpoint_sha256": base_checkpoint_evidence["checkpoint_sha256"],
            "fold": base_checkpoint_evidence["fold"],
        },
        "locked_ground_truth": _locked_ground_truth_summary(ground_truth),
        "minimum_rule_inputs": {
            "registered_coverage": candidate_summary.registered_coverage,
            "novel_macro_recall_lower_delta": interval.novel_macro_recall_lower_delta,
            "novel_wrong_registered_sku_rate_upper_delta": (
                interval.novel_wrong_registered_sku_rate_upper_delta
            ),
            "novel_loss_over_10pp_fraction": candidate_summary.novel_loss_over_10pp_fraction,
            "candidate_base_macro_final_correct_recall": (
                candidate_summary.base_macro_final_correct_recall
            ),
            "fold_base_checkpoint_macro_final_correct_recall": base_checkpoint_recall,
        },
    }
    if stage_four_selection is not None:
        score_receipt["stage_four_selection"] = stage_four_selection.to_dict()
    stage = paired_stage
    if stage == "stage1":
        score_receipt["stage1_global_top1_agreement"] = {
            "candidate": branch_top1_agreement(
                candidate_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
            "reference": branch_top1_agreement(
                reference_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
        }
    write_new_json(output, score_receipt)


def _branch_top1_summaries(
    rows: tuple[ResearchEvidenceRow, ...],
    novel_category_ids: set[int],
) -> dict[str, object]:
    return {
        branch: asdict(
            branch_top1_summary(
                rows,
                branch=branch,
                novel_category_ids=novel_category_ids,
            )
        )
        for branch in _SCORE_BRANCHES
    }


def _locked_ground_truth_summary(
    ground_truth: LoadedGroundTruth,
) -> dict[str, object]:
    return {
        "burst_count": len({row.burst_id for row in ground_truth.rows}),
        "manifest_sha256": ground_truth.sha256,
        "object_count": len(ground_truth.rows),
        "sample_count": len({row.sample_id for row in ground_truth.rows}),
    }


def _paired_condition_stage(
    candidate: Mapping[str, object],
    reference: Mapping[str, object],
) -> str:
    candidate_condition = candidate.get("condition")
    reference_condition = reference.get("condition")
    candidate_stage = (
        candidate_condition.get("stage")
        if isinstance(candidate_condition, Mapping)
        else None
    )
    reference_stage = (
        reference_condition.get("stage")
        if isinstance(reference_condition, Mapping)
        else None
    )
    return _paired_nested_condition_stage(
        candidate_stage,
        reference_stage,
    )


def _paired_nested_condition_stage(
    candidate_stage: object,
    reference_stage: object,
) -> str:
    if candidate_stage not in {"stage1", "ascending", "confirmation", "locked"} or (
        reference_stage != candidate_stage
    ):
        raise ValueError("candidate/reference condition stage mismatch")
    return candidate_stage


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


def aggregate_score_receipts(
    score_paths: Iterable[Path],
    output: Path,
    *,
    evidence_paths: Iterable[Path],
    reference_evidence_paths: Iterable[Path],
    ground_truth_manifest_path: Path,
) -> None:
    """Recompute one final decision from every declared raw evidence pair."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    candidate_evidence_paths = tuple(Path(path) for path in evidence_paths)
    frozen_reference_paths = tuple(Path(path) for path in reference_evidence_paths)
    loaded_receipts = tuple(
        _load_canonical_json_with_digest(Path(path)) for path in score_paths
    )
    receipts = tuple(item[0] for item in loaded_receipts)
    if not receipts:
        raise ValueError("aggregate requires score receipts")
    if (
        len(candidate_evidence_paths) != len(receipts)
        or len(frozen_reference_paths) != len(receipts)
    ):
        raise ValueError(
            "aggregate requires one candidate/reference evidence file per score receipt"
        )
    ground_truth = load_locked_ground_truth(ground_truth_manifest_path)
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
    aggregate_stage = _validated_aggregate_stage(
        candidate_conditions, reference_conditions
    )
    _validate_complete_condition_set(candidate_conditions, candidate_plan)
    _validate_complete_condition_set(reference_conditions, reference_plan)
    locked_selections: tuple[StageFourSelection, ...] = ()
    if aggregate_stage == "locked":
        locked_selections = tuple(
            _validate_locked_score_receipt_pair(receipt) for receipt in receipts
        )
        _validate_comparable_locked_selections(locked_selections, candidate_plan)
    aggregate_conditions: list[PairedConditionEvidence] = []
    candidate_summaries = []
    reference_summaries = []
    base_checkpoints: dict[int, tuple[str, str, float]] = {}
    evidence_receipts: list[dict[str, object]] = []
    branch_reports: list[dict[str, object]] = []
    for receipt, candidate_evidence_path, reference_evidence_path in zip(
        receipts,
        candidate_evidence_paths,
        frozen_reference_paths,
        strict=True,
    ):
        (
            paired,
            candidate_summary,
            reference_summary,
            base_checkpoint,
            evidence_record,
            branch_report,
        ) = _load_aggregate_evidence(
            receipt,
            candidate_plan,
            reference_plan,
            candidate_evidence_path,
            reference_evidence_path,
            ground_truth,
        )
        existing_base = base_checkpoints.setdefault(paired.fold, base_checkpoint)
        if existing_base != base_checkpoint:
            raise ValueError(
                "score receipts in one fold have inconsistent fold base checkpoint evidence"
            )
        aggregate_conditions.append(paired)
        candidate_summaries.append(candidate_summary)
        reference_summaries.append(reference_summary)
        evidence_receipts.append(evidence_record)
        branch_reports.append(branch_report)
    if set(base_checkpoints) != set(candidate_plan.folds):
        raise ValueError("aggregate lacks fold base checkpoint evidence")
    interval = bootstrap_paired_condition_deltas(
        aggregate_conditions,
        seed=candidate_plan.bootstrap_seed,
        replicates=candidate_plan.bootstrap_replicates,
    )
    minimum_rule_inputs = {
        "registered_coverage": _average(
            summary.registered_coverage for summary in candidate_summaries
        ),
        "novel_macro_recall_lower_delta": interval.novel_macro_recall_lower_delta,
        "novel_wrong_registered_sku_rate_upper_delta": (
            interval.novel_wrong_registered_sku_rate_upper_delta
        ),
        "novel_loss_over_10pp_fraction": _aggregate_novel_loss_fraction(
            aggregate_conditions,
            candidate_summaries,
            reference_summaries,
        ),
        "candidate_base_macro_final_correct_recall": _average(
            summary.base_macro_final_correct_recall for summary in candidate_summaries
        ),
        "fold_base_checkpoint_macro_final_correct_recall": _average(
            value[2] for value in base_checkpoints.values()
        ),
    }
    passes = _minimum_rule_inputs_pass(minimum_rule_inputs)
    decision_scope = (
        "complete_locked_fold_seed_aggregate"
        if aggregate_stage == "locked"
        else "complete_confirmation_fold_seed_aggregate"
    )
    decision: dict[str, object] = (
        {"decision_status": "final", "final_pass": passes}
        if aggregate_stage == "locked"
        else {"decision_status": "provisional", "provisional_pass": passes}
    )
    output_receipt: dict[str, object] = {
            "schema_version": 2,
            "kind": (
                "rpc-fewshot-final-score-receipt"
                if aggregate_stage == "locked"
                else "rpc-fewshot-confirmation-score-receipt"
            ),
            "status": "completed",
            "decision_scope": decision_scope,
            "aggregate_stage": aggregate_stage,
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
            "raw_evidence": sorted(
                evidence_receipts,
                key=lambda item: item["candidate_condition_id"],
            ),
            "condition_branch_top1": sorted(
                branch_reports,
                key=lambda item: item["candidate_condition_id"],
            ),
            "locked_ground_truth": _locked_ground_truth_summary(ground_truth),
            "paired_bootstrap_95": asdict(interval),
            "minimum_rule_inputs": minimum_rule_inputs,
            **decision,
        }
    if locked_selections:
        output_receipt["stage_four_selections"] = [
            selection.to_dict()
            for selection in sorted(
                locked_selections, key=lambda item: (item.fold, item.support_seed)
            )
        ]
    write_new_json(output, output_receipt)


def _load_aggregate_evidence(
    receipt: Mapping[str, object],
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
    candidate_path: Path,
    reference_path: Path,
    ground_truth: LoadedGroundTruth,
) -> tuple[
    PairedConditionEvidence,
    FullSystemSummary,
    FullSystemSummary,
    tuple[str, str, float],
    dict[str, object],
    dict[str, object],
]:
    candidate_condition = _score_receipt_condition(receipt, "candidate_condition")
    reference_condition = _score_receipt_condition(receipt, "reference_condition")
    fold = candidate_condition.get("fold")
    support_seed = candidate_condition.get("support_seed")
    if type(fold) is not int or type(support_seed) is not int:
        raise ValueError("score receipt has invalid fold/support-seed axes")
    if (
        receipt.get("candidate_condition_id") != candidate_condition.get("condition_id")
        or receipt.get("reference_condition_id")
        != reference_condition.get("condition_id")
    ):
        raise ValueError("score receipt top-level condition ID mismatch")
    _validate_score_receipt_locked_ground_truth(receipt, ground_truth)
    novel, base = _score_receipt_cohort(receipt, candidate_plan)
    candidate_provenance = _score_receipt_provenance(
        receipt,
        "candidate_provenance",
        candidate_condition,
        candidate_plan,
    )
    reference_provenance = _score_receipt_provenance(
        receipt,
        "reference_provenance",
        reference_condition,
        reference_plan,
    )
    if (
        candidate_provenance["cohort_manifest_sha256"]
        != reference_provenance["cohort_manifest_sha256"]
    ):
        raise ValueError("candidate/reference cohort manifest mismatch")
    if candidate_provenance["cohort_manifest_sha256"] != ground_truth.sha256:
        raise ValueError("locked ground-truth manifest SHA-256 mismatch")
    base_checkpoint = _score_receipt_base_checkpoint(
        receipt,
        fold,
        candidate_plan,
        reference_plan,
        candidate_provenance,
        reference_provenance,
    )
    loaded_candidate = load_canonical_jsonl(candidate_path)
    loaded_reference = load_canonical_jsonl(reference_path)
    if loaded_candidate.sha256 != candidate_provenance["evidence_sha256"]:
        raise ValueError("candidate evidence SHA-256 mismatch")
    if loaded_reference.sha256 != reference_provenance["evidence_sha256"]:
        raise ValueError("reference evidence SHA-256 mismatch")
    candidate_receipt = _reconstructed_condition_receipt(
        candidate_condition,
        candidate_plan,
        candidate_provenance,
        novel,
        base,
    )
    reference_receipt = _reconstructed_condition_receipt(
        reference_condition,
        reference_plan,
        reference_provenance,
        novel,
        base,
    )
    candidate_rows = validate_evidence_completeness(
        loaded_candidate.rows, ground_truth.rows
    )
    reference_rows = validate_evidence_completeness(
        loaded_reference.rows, ground_truth.rows
    )
    candidate_rows = validate_evidence_against_condition(
        candidate_rows, candidate_receipt
    )
    reference_rows = validate_evidence_against_condition(
        reference_rows, reference_receipt
    )
    candidate_rows, reference_rows = validate_paired_evidence(
        candidate_rows, reference_rows
    )
    candidate_summary = full_system_summary(
        candidate_rows,
        novel_category_ids=novel,
        reference_rows=reference_rows,
    )
    reference_summary = full_system_summary(
        reference_rows,
        novel_category_ids=novel,
    )
    branch_report: dict[str, object] = {
        "candidate_condition_id": candidate_condition["condition_id"],
        "reference_condition_id": reference_condition["condition_id"],
        "candidate": _branch_top1_summaries(candidate_rows, novel),
        "reference": _branch_top1_summaries(reference_rows, novel),
    }
    stage = _paired_nested_condition_stage(
        candidate_condition.get("stage"),
        reference_condition.get("stage"),
    )
    if stage == "stage1":
        branch_report["stage1_global_top1_agreement"] = {
            "candidate": branch_top1_agreement(
                candidate_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
            "reference": branch_top1_agreement(
                reference_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
        }
    return (
        PairedConditionEvidence(
            fold=fold,
            support_seed=support_seed,
            novel_category_ids=frozenset(novel),
            candidate=candidate_rows,
            reference=reference_rows,
        ),
        candidate_summary,
        reference_summary,
        base_checkpoint,
        {
            "candidate_condition_id": candidate_condition["condition_id"],
            "candidate_evidence_sha256": loaded_candidate.sha256,
            "reference_condition_id": reference_condition["condition_id"],
            "reference_evidence_sha256": loaded_reference.sha256,
        },
        branch_report,
    )


def _validate_score_receipt_locked_ground_truth(
    receipt: Mapping[str, object],
    ground_truth: LoadedGroundTruth,
) -> None:
    value = receipt.get("locked_ground_truth")
    expected = _locked_ground_truth_summary(ground_truth)
    count_names = ("burst_count", "object_count", "sample_count")
    if (
        not isinstance(value, Mapping)
        or set(value) != set(expected)
        or value.get("manifest_sha256") != expected["manifest_sha256"]
        or any(
            type(value.get(name)) is not int
            or value.get(name) != expected[name]
            for name in count_names
        )
    ):
        raise ValueError("score receipt lacks valid locked ground-truth provenance")


def _score_receipt_cohort(
    receipt: Mapping[str, object], plan: ScoringPlan
) -> tuple[set[int], set[int]]:
    raw = receipt.get("cohort")
    if not isinstance(raw, Mapping) or set(raw) != {
        "base_category_ids",
        "novel_category_ids",
    }:
        raise ValueError("score receipt lacks an immutable cohort")
    novel = _category_ids(raw.get("novel_category_ids"), "novel cohort")
    base = _category_ids(raw.get("base_category_ids"), "base cohort")
    if novel & base or novel | base != set(plan.registered_category_ids):
        raise ValueError("score receipt cohort does not match the scoring plan")
    return novel, base


def _score_receipt_provenance(
    receipt: Mapping[str, object],
    name: str,
    condition: Mapping[str, object],
    plan: ScoringPlan,
) -> Mapping[str, str]:
    value = receipt.get(name)
    expected = {
        "condition_id",
        "evidence_sha256",
        "cohort_manifest_sha256",
        "base_checkpoint_sha256",
        "base_checkpoint_evidence_sha256",
        "scoring_plan_sha256",
        "condition_manifest_sha256",
        "model_sha256",
        "support_sha256",
        "calibration_sha256",
        "policy_sha256",
        "preprocessing_sha256",
        "code_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"score receipt lacks complete {name}")
    condition_id = condition.get("condition_id")
    if value.get("condition_id") != condition_id:
        raise ValueError(f"{name} condition ID mismatch")
    for field in expected - {"condition_id"}:
        _require_sha256(field, value.get(field))
    if value.get("scoring_plan_sha256") != plan.sha256:
        raise ValueError(f"{name} scoring plan SHA-256 mismatch")
    return value  # type: ignore[return-value]


def _score_receipt_base_checkpoint(
    receipt: Mapping[str, object],
    fold: int,
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
    candidate_provenance: Mapping[str, str],
    reference_provenance: Mapping[str, str],
) -> tuple[str, str, float]:
    value = receipt.get("fold_base_checkpoint")
    if not isinstance(value, Mapping) or set(value) != {
        "base_macro_final_correct_recall",
        "checkpoint_sha256",
        "evidence_sha256",
        "fold",
    }:
        raise ValueError("score receipt lacks fold base checkpoint evidence")
    if value.get("fold") != fold:
        raise ValueError("score receipt fold base checkpoint fold mismatch")
    checkpoint_sha256 = value.get("checkpoint_sha256")
    evidence_sha256 = value.get("evidence_sha256")
    _require_sha256("fold base checkpoint_sha256", checkpoint_sha256)
    _require_sha256("fold base evidence_sha256", evidence_sha256)
    candidate_artifact = next(
        item for item in candidate_plan.fold_base_artifacts if item.fold == fold
    )
    reference_artifact = next(
        item for item in reference_plan.fold_base_artifacts if item.fold == fold
    )
    expected = (
        candidate_artifact.checkpoint_sha256,
        candidate_artifact.evidence_sha256,
    )
    if (
        expected
        != (
            reference_artifact.checkpoint_sha256,
            reference_artifact.evidence_sha256,
        )
        or expected != (checkpoint_sha256, evidence_sha256)
        or expected
        != (
            candidate_provenance["base_checkpoint_sha256"],
            candidate_provenance["base_checkpoint_evidence_sha256"],
        )
        or expected
        != (
            reference_provenance["base_checkpoint_sha256"],
            reference_provenance["base_checkpoint_evidence_sha256"],
        )
    ):
        raise ValueError(
            "score receipt fold base checkpoint does not match the scoring plan"
        )
    recall = value.get("base_macro_final_correct_recall")
    if (
        not isinstance(recall, (int, float))
        or isinstance(recall, bool)
        or not math.isfinite(float(recall))
        or not 0.0 <= float(recall) <= 1.0
    ):
        raise ValueError("fold base checkpoint recall must be finite and in [0, 1]")
    return str(checkpoint_sha256), str(evidence_sha256), float(recall)


def _reconstructed_condition_receipt(
    condition: Mapping[str, object],
    plan: ScoringPlan,
    provenance: Mapping[str, str],
    novel: set[int],
    base: set[int],
) -> Mapping[str, object]:
    return {
        "condition": dict(condition),
        "cohort": {
            "base_category_ids": sorted(base),
            "fold": condition["fold"],
            "manifest_sha256": provenance["cohort_manifest_sha256"],
            "novel_category_ids": sorted(novel),
        },
        "scoring": {
            "registered_category_ids": list(plan.registered_category_ids),
        },
        **{
            name: provenance[name]
            for name in (
                "condition_manifest_sha256",
                "model_sha256",
                "support_sha256",
                "calibration_sha256",
                "policy_sha256",
                "preprocessing_sha256",
                "code_sha256",
            )
        },
    }


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
    parsed = _parse_nested_condition(condition, "condition")
    if parsed.condition_id not in plan.expected_condition_ids:
        raise ValueError("condition ID is not declared by the scoring plan")
    if parsed.fold not in plan.folds or parsed.support_seed not in plan.support_seeds:
        raise ValueError("condition fold/seed is not declared by the scoring plan")
    scoring = condition.get("scoring")
    if not isinstance(scoring, Mapping) or scoring.get("registered_category_ids") != list(
        plan.registered_category_ids
    ):
        raise ValueError("condition scoring cohort does not match the scoring plan")
    binding = condition.get("fold_base_checkpoint")
    artifact = next(item for item in plan.fold_base_artifacts if item.fold == parsed.fold)
    if (
        not isinstance(binding, Mapping)
        or set(binding) != {"checkpoint_sha256", "evidence_sha256", "fold"}
        or binding.get("fold") != parsed.fold
        or binding.get("checkpoint_sha256") != artifact.checkpoint_sha256
        or binding.get("evidence_sha256") != artifact.evidence_sha256
    ):
        raise ValueError("condition fold base checkpoint does not match the scoring plan")
    _validate_condition_stage_four_selection(condition, parsed)
    return plan


def _parse_nested_condition(
    receipt: Mapping[str, object], name: str
) -> ExperimentCondition:
    """Treat a condition ID as a digest of every declared condition field."""
    nested = receipt.get(name)
    if not isinstance(nested, Mapping):
        raise ValueError(f"receipt lacks {name}")
    parsed = ExperimentCondition.from_dict(nested)
    if dict(nested) != parsed.to_dict():
        raise ValueError("receipt condition is not canonical")
    return parsed


def _validate_condition_stage_four_selection(
    receipt: Mapping[str, object], condition: ExperimentCondition
) -> None:
    selection_value = receipt.get("stage_four_selection")
    if condition.stage != "locked":
        if selection_value is not None:
            raise ValueError("only locked conditions may bind a Stage-4 selection")
        return
    if not isinstance(selection_value, Mapping):
        raise ValueError("locked condition lacks Stage-4 selection")
    selection = StageFourSelection.from_dict(selection_value)
    _validate_locked_condition_against_selection(condition, selection)


def _validate_locked_condition_against_selection(
    condition: ExperimentCondition, selection: StageFourSelection
) -> None:
    if (condition.method, condition.selector, condition.fold, condition.support_seed) != (
        selection.method,
        selection.selector,
        selection.fold,
        selection.support_seed,
    ):
        raise ValueError("locked condition does not match its Stage-4 selection")
    if condition.shot_count not in {selection.provisional_minimum_shot_count, 150}:
        raise ValueError("locked condition is not the selected provisional minimum or 150-shot reference")


def _validate_comparable_scoring_plans(candidate: ScoringPlan, reference: ScoringPlan) -> None:
    if (
        candidate.bootstrap_seed != reference.bootstrap_seed
        or candidate.bootstrap_replicates != reference.bootstrap_replicates
        or candidate.folds != reference.folds
        or candidate.support_seeds != reference.support_seeds
        or candidate.cohort_id != reference.cohort_id
        or candidate.registered_category_ids != reference.registered_category_ids
        or candidate.fold_base_artifacts != reference.fold_base_artifacts
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
    parsed = ExperimentCondition.from_dict(value)
    if dict(value) != parsed.to_dict():
        raise ValueError("score receipt condition is not canonical")
    return parsed.to_dict()


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
    if any(
        (candidate.get("method"), candidate.get("selector"))
        != (reference.get("method"), reference.get("selector"))
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    ):
        raise ValueError("candidate/reference conditions must share method and selector")


def _validated_aggregate_stage(
    candidate_conditions: tuple[Mapping[str, object], ...],
    reference_conditions: tuple[Mapping[str, object], ...],
) -> str:
    """Allow a decision only after the frozen full-system funnel stages."""
    stages = {
        _paired_nested_condition_stage(
            candidate.get("stage"), reference.get("stage")
        )
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    }
    if len(stages) != 1 or not stages <= {"confirmation", "locked"}:
        raise ValueError(
            "aggregate requires candidate/reference conditions in one confirmation or locked stage"
        )
    if any(reference.get("shot_count") != 150 for reference in reference_conditions):
        raise ValueError("aggregate requires an exact 150-shot reference condition")
    return stages.pop()


def _locked_selection_from_value(value: object) -> StageFourSelection:
    if not isinstance(value, Mapping):
        raise ValueError("locked score receipt lacks Stage-4 selection")
    return StageFourSelection.from_dict(value)


def _validate_locked_pair_against_selection(
    candidate_value: Mapping[str, object],
    reference_value: Mapping[str, object],
    selection: StageFourSelection,
) -> None:
    candidate = ExperimentCondition.from_dict(candidate_value)
    reference = ExperimentCondition.from_dict(reference_value)
    _validate_locked_condition_against_selection(candidate, selection)
    _validate_locked_condition_against_selection(reference, selection)
    if candidate.shot_count != selection.provisional_minimum_shot_count:
        raise ValueError("locked candidate is not the Stage-4 provisional minimum")
    if reference.shot_count != 150:
        raise ValueError("locked reference is not the balanced 150-shot condition")


def _validate_locked_condition_receipt_pair(
    candidate_receipt: Mapping[str, object], reference_receipt: Mapping[str, object]
) -> StageFourSelection:
    candidate = _score_receipt_condition(candidate_receipt, "condition")
    reference = _score_receipt_condition(reference_receipt, "condition")
    candidate_selection = _locked_selection_from_value(
        candidate_receipt.get("stage_four_selection")
    )
    reference_selection = _locked_selection_from_value(
        reference_receipt.get("stage_four_selection")
    )
    if candidate_selection != reference_selection:
        raise ValueError("candidate/reference locked conditions bind different Stage-4 selections")
    _validate_locked_pair_against_selection(candidate, reference, candidate_selection)
    return candidate_selection


def _validate_locked_score_receipt_pair(receipt: Mapping[str, object]) -> StageFourSelection:
    candidate = _score_receipt_condition(receipt, "candidate_condition")
    reference = _score_receipt_condition(receipt, "reference_condition")
    selection = _locked_selection_from_value(receipt.get("stage_four_selection"))
    _validate_locked_pair_against_selection(candidate, reference, selection)
    return selection


def _validate_comparable_locked_selections(
    selections: tuple[StageFourSelection, ...], plan: ScoringPlan
) -> None:
    """All fold/seed certificates must select the same frozen method and minimum."""
    if not selections:
        raise ValueError("locked aggregate lacks Stage-4 selections")
    coordinates = {(selection.fold, selection.support_seed) for selection in selections}
    if len(coordinates) != len(selections):
        raise ValueError("locked aggregate repeats a Stage-4 selection coordinate")
    if coordinates != {
        (fold, seed) for fold in plan.folds for seed in plan.support_seeds
    }:
        raise ValueError("locked Stage-4 selections do not cover the scoring plan matrix")
    first = selections[0]
    signature = (
        first.method,
        first.selector,
        first.provisional_minimum_shot_count,
        tuple(sorted(item.condition.shot_count for item in first.confirmation_receipts)),
    )
    if any(
        (
            selection.method,
            selection.selector,
            selection.provisional_minimum_shot_count,
            tuple(sorted(item.condition.shot_count for item in selection.confirmation_receipts)),
        )
        != signature
        for selection in selections[1:]
    ):
        raise ValueError("locked aggregate mixes incompatible Stage-4 selections")


def _minimum_rule_inputs_pass(value: object) -> bool:
    if not isinstance(value, Mapping):
        raise ValueError("score receipt lacks minimum-rule inputs")
    required = {
        "registered_coverage",
        "novel_macro_recall_lower_delta",
        "novel_wrong_registered_sku_rate_upper_delta",
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
        and numeric["novel_wrong_registered_sku_rate_upper_delta"] <= 0.005 + tolerance
        and numeric["novel_loss_over_10pp_fraction"] <= 0.05 + tolerance
        and (
            numeric["candidate_base_macro_final_correct_recall"]
            - numeric["fold_base_checkpoint_macro_final_correct_recall"]
        )
        >= -0.01 - tolerance
    )


def _category_ids(value: object, name: str) -> set[int]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a nonempty category ID sequence")
    try:
        frozen = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a nonempty category ID sequence") from exc
    if (
        not frozen
        or len(set(frozen)) != len(frozen)
        or any(type(item) is not int or item <= 0 for item in frozen)
    ):
        raise ValueError(f"{name} must be a nonempty unique category ID sequence")
    return set(frozen)


def _require_sha256(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _average(values: Iterable[float]) -> float:
    frozen = tuple(float(value) for value in values)
    if not frozen or not all(math.isfinite(value) for value in frozen):
        raise ValueError("aggregate metric inputs must be nonempty and finite")
    return sum(frozen) / len(frozen)


def _aggregate_novel_loss_fraction(
    conditions: Iterable[PairedConditionEvidence],
    candidate_summaries: Iterable[FullSystemSummary],
    reference_summaries: Iterable[FullSystemSummary],
) -> float:
    losses: dict[tuple[int, int], list[float]] = {}
    for condition, candidate, reference in zip(
        conditions,
        candidate_summaries,
        reference_summaries,
        strict=True,
    ):
        for category in condition.novel_category_ids:
            if (
                category not in candidate.per_category_final_correct_recall
                or category not in reference.per_category_final_correct_recall
            ):
                raise ValueError("aggregate summary lacks a declared novel category")
            losses.setdefault((condition.fold, category), []).append(
                reference.per_category_final_correct_recall[category]
                - candidate.per_category_final_correct_recall[category]
            )
    if not losses:
        raise ValueError("aggregate summary lacks novel categories")
    return (
        sum(sum(values) / len(values) > 0.10 for values in losses.values())
        / len(losses)
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
    parser.add_argument("--ground-truth-manifest", type=Path)
    parser.add_argument("--base-checkpoint-evidence", type=Path)
    parser.add_argument("--aggregate-score-receipt", action="append", type=Path)
    parser.add_argument("--aggregate-evidence", action="append", type=Path)
    parser.add_argument("--aggregate-reference-evidence", action="append", type=Path)
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
            if not args.aggregate_evidence or not args.aggregate_reference_evidence:
                raise ValueError(
                    "aggregate mode requires candidate and reference raw evidence"
                )
            if args.ground_truth_manifest is None:
                raise ValueError("aggregate mode requires locked ground truth")
            aggregate_score_receipts(
                tuple(args.aggregate_score_receipt),
                args.output,
                evidence_paths=tuple(args.aggregate_evidence),
                reference_evidence_paths=tuple(args.aggregate_reference_evidence),
                ground_truth_manifest_path=args.ground_truth_manifest,
            )
        else:
            if args.aggregate_evidence or args.aggregate_reference_evidence:
                raise ValueError(
                    "aggregate evidence inputs require aggregate score receipts"
                )
            single = (
                args.evidence,
                args.reference_evidence,
                args.condition,
                args.reference_condition,
                args.ground_truth_manifest,
                args.base_checkpoint_evidence,
            )
            if any(value is None for value in single):
                raise ValueError(
                    "single-condition scoring requires evidence, reference evidence, "
                    "condition, reference condition, locked ground truth, and fold "
                    "base checkpoint evidence"
                )
            score(*single, args.output)  # type: ignore[arg-type]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
