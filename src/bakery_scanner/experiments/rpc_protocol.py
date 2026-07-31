"""Preregistered, immutable conditions and receipts for RPC few-shot experiments."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Mapping

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json


_STAGE_ONE_PAIRS = (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
_STAGE_ONE_SHOTS = (1, 3, 5)
_ASCENDING_SHOTS = (1, 3, 5, 10, 20)
_EXTENDED_ASCENDING_SHOTS = (40, 80, 150)
_REFINEMENTS = {(3, 5): (4,), (5, 10): (6, 8), (10, 20): (12, 15, 18)}
_REFINEMENT_SHOTS = tuple(
    sorted({shot for shots in _REFINEMENTS.values() for shot in shots})
)
_CONFIRMATION_SHOTS = tuple(
    sorted(set(_ASCENDING_SHOTS + _EXTENDED_ASCENDING_SHOTS + _REFINEMENT_SHOTS))
)
_HASH_FIELDS = (
    "condition_manifest_sha256",
    "model_sha256",
    "support_sha256",
    "calibration_sha256",
    "policy_sha256",
    "preprocessing_sha256",
    "code_sha256",
)


@dataclass(frozen=True, slots=True)
class ExperimentCondition:
    method: str
    selector: str
    shot_count: int
    fold: int
    support_seed: int
    stage: str
    condition_id: str
    support_scope: Literal["fixed_k", "all_available"] = "fixed_k"

    def __post_init__(self) -> None:
        if (self.method, self.selector) not in _STAGE_ONE_PAIRS:
            raise ValueError("unsupported method/selector combination")
        if self.support_scope not in {"fixed_k", "all_available"}:
            raise ValueError("unsupported support scope")
        if self.support_scope == "fixed_k" and (type(self.shot_count) is not int or self.shot_count <= 0):
            raise ValueError("shot_count must be a positive integer")
        if self.support_scope == "all_available" and self.shot_count != 0:
            raise ValueError("all_available is not a normal shot count")
        if type(self.fold) is not int or self.fold < 0:
            raise ValueError("fold must be a non-negative integer")
        if type(self.support_seed) is not int:
            raise ValueError("support_seed must be an integer")
        if self.support_scope == "all_available" and self.stage != "ascending":
            raise ValueError("all_available diagnostic is allowed only in ascending stage")
        if self.support_scope == "fixed_k" and self.stage == "stage1" and self.shot_count not in _STAGE_ONE_SHOTS:
            raise ValueError("unsupported Stage-1 condition")
        if self.support_scope == "fixed_k" and self.stage == "ascending" and self.shot_count not in (
            _ASCENDING_SHOTS + _EXTENDED_ASCENDING_SHOTS
        ):
            raise ValueError("unsupported ascending condition")
        if self.support_scope == "fixed_k" and self.stage in {"confirmation", "locked"} and self.shot_count not in _CONFIRMATION_SHOTS:
            raise ValueError("unsupported confirmation or locked condition")
        if self.stage not in {"stage1", "ascending", "confirmation", "locked"}:
            raise ValueError("unsupported stage")
        expected = _condition_id(
            self.method, self.selector, self.shot_count, self.fold, self.support_seed, self.stage, self.support_scope
        )
        if self.condition_id != expected:
            raise ValueError("condition_id is not deterministic for condition contents")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "condition_id": self.condition_id,
            "fold": self.fold,
            "method": self.method,
            "selector": self.selector,
            "shot_count": self.shot_count,
            "stage": self.stage,
            "support_seed": self.support_seed,
        }
        if self.support_scope == "all_available":
            result["support_scope"] = self.support_scope
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ExperimentCondition":
        """Parse one canonical condition; an ID never authorizes altered fields."""
        expected = {
            "condition_id",
            "fold",
            "method",
            "selector",
            "shot_count",
            "stage",
            "support_seed",
        }
        if not isinstance(value, Mapping) or set(value) not in (expected, expected | {"support_scope"}):
            raise ValueError("condition has missing or unrecognized fields")
        try:
            return cls(
                method=value["method"],  # type: ignore[arg-type]
                selector=value["selector"],  # type: ignore[arg-type]
                shot_count=value["shot_count"],  # type: ignore[arg-type]
                fold=value["fold"],  # type: ignore[arg-type]
                support_seed=value["support_seed"],  # type: ignore[arg-type]
                stage=value["stage"],  # type: ignore[arg-type]
                condition_id=value["condition_id"],  # type: ignore[arg-type]
                support_scope=value.get("support_scope", "fixed_k"),  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid deterministic condition") from exc


@dataclass(frozen=True, slots=True)
class StageFourConfirmationReceipt:
    """One immutable Stage-4 score receipt used to select the locked pair."""

    condition: ExperimentCondition
    score_receipt_sha256: str
    provisional_pass: bool

    def __post_init__(self) -> None:
        if not isinstance(self.condition, ExperimentCondition) or self.condition.stage != "confirmation":
            raise ValueError("Stage-4 receipt requires a confirmation condition")
        _validate_sha256("Stage-4 score receipt SHA-256", self.score_receipt_sha256)
        if type(self.provisional_pass) is not bool:
            raise ValueError("Stage-4 provisional_pass must be boolean")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "condition": self.condition.to_dict(),
            "provisional_pass": self.provisional_pass,
            "score_receipt_sha256": self.score_receipt_sha256,
        }
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "StageFourConfirmationReceipt":
        if not isinstance(value, Mapping) or set(value) != {
            "condition", "provisional_pass", "score_receipt_sha256"
        }:
            raise ValueError("invalid Stage-4 confirmation receipt")
        condition = value["condition"]
        if not isinstance(condition, Mapping):
            raise ValueError("invalid Stage-4 confirmation receipt")
        return cls(
            condition=ExperimentCondition.from_dict(condition),
            provisional_pass=value["provisional_pass"],  # type: ignore[arg-type]
            score_receipt_sha256=value["score_receipt_sha256"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class StageFourSelection:
    """The only schedulable Stage-5 source: a frozen Stage-4 confirmation set."""

    confirmation_receipts: tuple[StageFourConfirmationReceipt, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.confirmation_receipts, tuple) or len(self.confirmation_receipts) not in {3, 4}:
            raise ValueError("Stage-4 selection requires four receipts, or the k=1 three-receipt special case")
        if any(not isinstance(item, StageFourConfirmationReceipt) for item in self.confirmation_receipts):
            raise ValueError("Stage-4 selection contains an invalid confirmation receipt")
        if len({item.score_receipt_sha256 for item in self.confirmation_receipts}) != len(self.confirmation_receipts):
            raise ValueError("Stage-4 selection requires distinct confirmation receipt hashes")
        conditions = tuple(item.condition for item in self.confirmation_receipts)
        first = conditions[0]
        if any(
            (condition.method, condition.selector, condition.fold, condition.support_seed)
            != (first.method, first.selector, first.fold, first.support_seed)
            for condition in conditions
        ):
            raise ValueError("Stage-4 confirmation receipts must share method, selector, fold, and seed")
        shots = tuple(condition.shot_count for condition in conditions)
        k1_special = len(shots) == 3 and set(shots) == {1, 3, 150}
        if (len(shots) != 4 or len(set(shots)) != 4 or 150 not in shots) and not k1_special:
            raise ValueError("Stage-4 selection requires four unique shots including 150, or k1/3/150")
        non_reference = tuple(sorted(shot for shot in shots if shot != 150))
        passed = {
            item.condition.shot_count: item.provisional_pass
            for item in self.confirmation_receipts
        }
        provisional = min(shot for shot in non_reference if passed[shot]) if any(
            passed[shot] for shot in non_reference
        ) else None
        if provisional is None:
            raise ValueError("Stage-4 selection has no provisional minimum")
        prior = tuple(shot for shot in non_reference if shot < provisional)
        later = tuple(shot for shot in non_reference if shot > provisional)
        if provisional == 1 and k1_special:
            if not passed[3]:
                raise ValueError("Stage-4 k=1 selection requires the next passing anchor")
        elif not prior or not later or passed[max(prior)] or not passed[min(later)]:
            raise ValueError("Stage-4 selection requires last failure and next passing anchor")
        if not passed[150]:
            raise ValueError("Stage-4 balanced 150-shot reference must pass")

    @property
    def method(self) -> str:
        return self.confirmation_receipts[0].condition.method

    @property
    def selector(self) -> str:
        return self.confirmation_receipts[0].condition.selector

    @property
    def fold(self) -> int:
        return self.confirmation_receipts[0].condition.fold

    @property
    def support_seed(self) -> int:
        return self.confirmation_receipts[0].condition.support_seed

    @property
    def provisional_minimum_shot_count(self) -> int:
        return min(
            item.condition.shot_count
            for item in self.confirmation_receipts
            if item.condition.shot_count != 150 and item.provisional_pass
        )

    @property
    def is_lowest_shot_special_case(self) -> bool:
        return tuple(sorted(item.condition.shot_count for item in self.confirmation_receipts)) == (1, 3, 150)

    def to_dict(self) -> dict[str, object]:
        return {
            "confirmation_receipts": [
                item.to_dict() for item in self.confirmation_receipts
            ],
            "schema_version": 1,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "StageFourSelection":
        if not isinstance(value, Mapping) or set(value) != {
            "confirmation_receipts", "schema_version"
        } or value.get("schema_version") != 1 or not isinstance(value.get("confirmation_receipts"), list):
            raise ValueError("invalid Stage-4 selection")
        try:
            return cls(
                confirmation_receipts=tuple(
                    StageFourConfirmationReceipt.from_dict(item)
                    for item in value["confirmation_receipts"]  # type: ignore[union-attr]
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Stage-4 selection") from exc


@dataclass(frozen=True, slots=True)
class StageFourConfirmationBinding:
    """Verified common provenance emitted by one Stage-4 aggregate quartet."""

    cohort_manifest_sha256: str
    novel_category_ids: tuple[int, ...]
    base_category_ids: tuple[int, ...]
    scoring_plan_fingerprint: tuple[object, ...]
    fold_base_artifact: FoldBaseArtifact

    def validate_locked_target(
        self,
        *,
        condition: ExperimentCondition,
        cohort_manifest_sha256: str,
        novel_category_ids: tuple[int, ...],
        base_category_ids: tuple[int, ...],
        scoring_plan: "ScoringPlan",
        base_checkpoint_sha256: str,
        base_checkpoint_evidence_sha256: str,
    ) -> None:
        """Require a locked target to use the exact Stage-4 decision universe."""
        if condition.stage != "locked":
            raise ValueError("Stage-4 binding can authorize only a locked condition")
        if cohort_manifest_sha256 != self.cohort_manifest_sha256:
            raise ValueError("locked target cohort does not match Stage-4 cohort")
        if (
            tuple(novel_category_ids) != self.novel_category_ids
            or tuple(base_category_ids) != self.base_category_ids
        ):
            raise ValueError("locked target category cohort does not match Stage-4 cohort")
        if _stage_four_plan_context(scoring_plan) != self.scoring_plan_fingerprint:
            raise ValueError("locked target scoring plan does not match Stage-4 scoring plan")
        if condition.fold != self.fold_base_artifact.fold or (
            base_checkpoint_sha256,
            base_checkpoint_evidence_sha256,
        ) != (
            self.fold_base_artifact.checkpoint_sha256,
            self.fold_base_artifact.evidence_sha256,
        ):
            raise ValueError("locked target base checkpoint does not match Stage-4 artifact")


def validate_stage_four_confirmation_score_receipts(
    selection: StageFourSelection,
    receipt_paths: Iterable[Path],
    *,
    trusted_source_root: Path,
) -> StageFourConfirmationBinding:
    """Resolve every Stage-4 claim to its canonical, immutable score receipt.

    A selection deliberately records digests rather than copying large score
    receipts.  It is therefore not an authorization by itself: every Stage-5
    entry point must resolve the four external paths and verify their exact
    bytes and confirmation decision before accepting the selection.
    """
    if not isinstance(selection, StageFourSelection):
        raise TypeError("Stage-4 receipt validation requires a StageFourSelection")
    try:
        paths = tuple(Path(path) for path in receipt_paths)
    except (TypeError, ValueError) as exc:
        raise ValueError("Stage-4 confirmation score receipt paths are invalid") from exc
    if len(paths) != len(selection.confirmation_receipts) or len(set(paths)) != len(paths):
        raise ValueError("Stage-4 selection requires one distinct confirmation score receipt path per receipt")
    loaded: dict[str, Mapping[str, object]] = {}
    for path in paths:
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"cannot read Stage-4 confirmation score receipt: {path}") from exc
        try:
            value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_json_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid Stage-4 confirmation score receipt: {path}") from exc
        if not isinstance(value, dict) or canonical_json_bytes(value) != content:
            raise ValueError(f"Stage-4 confirmation score receipt is not canonical: {path}")
        digest = hashlib.sha256(content).hexdigest()
        if digest in loaded:
            raise ValueError("Stage-4 confirmation score receipt paths have duplicate bytes")
        loaded[digest] = value
    expected_digests = {
        item.score_receipt_sha256 for item in selection.confirmation_receipts
    }
    if set(loaded) != expected_digests:
        raise ValueError("Stage-4 confirmation score receipt SHA-256 does not match selection")

    bindings: set[StageFourConfirmationBinding] = set()
    for claim in selection.confirmation_receipts:
        receipt = loaded[claim.score_receipt_sha256]
        bindings.add(
            _validate_stage_four_confirmation_score_receipt(
                receipt,
                claim,
                trusted_source_root=trusted_source_root,
            )
        )
    if len(bindings) != 1:
        raise ValueError("Stage-4 confirmation score receipts do not share cohort and scoring plan")
    return next(iter(bindings))


def validate_stage_four_binding_for_locked_target(
    selection: StageFourSelection,
    receipt_paths: Iterable[Path],
    *,
    condition: ExperimentCondition,
    cohort_manifest_sha256: str,
    novel_category_ids: tuple[int, ...],
    base_category_ids: tuple[int, ...],
    scoring_plan: "ScoringPlan",
    base_checkpoint_sha256: str,
    base_checkpoint_evidence_sha256: str,
    trusted_source_root: Path,
) -> StageFourConfirmationBinding:
    """Resolve Stage-4 bytes and bind their provenance to one Stage-5 target."""
    binding = validate_stage_four_confirmation_score_receipts(
        selection,
        receipt_paths,
        trusted_source_root=trusted_source_root,
    )
    binding.validate_locked_target(
        condition=condition,
        cohort_manifest_sha256=cohort_manifest_sha256,
        novel_category_ids=novel_category_ids,
        base_category_ids=base_category_ids,
        scoring_plan=scoring_plan,
        base_checkpoint_sha256=base_checkpoint_sha256,
        base_checkpoint_evidence_sha256=base_checkpoint_evidence_sha256,
    )
    return binding


def _validate_stage_four_confirmation_score_receipt(
    receipt: Mapping[str, object],
    claim: StageFourConfirmationReceipt,
    *,
    trusted_source_root: Path,
) -> StageFourConfirmationBinding:
    required = {
        "schema_version",
        "kind",
        "status",
        "decision_status",
        "aggregate_stage",
        "decision_scope",
        "provisional_pass",
        "condition_count",
        "candidate_conditions",
        "reference_conditions",
        "candidate_condition_ids",
        "reference_condition_ids",
        "candidate_scoring_plan",
        "reference_scoring_plan",
        "candidate_scoring_plan_sha256",
        "reference_scoring_plan_sha256",
        "cohort",
        "score_receipts",
        "raw_evidence",
        "condition_branch_top1",
        "candidate_full_system",
        "reference_full_system",
        "fold_base_checkpoint",
        "locked_ground_truth",
        "paired_bootstrap_95",
        "minimum_rule_inputs",
        "upstream_artifacts",
    }
    if set(receipt) != required:
        raise ValueError("Stage-4 confirmation score receipt does not use the strict aggregate schema")
    if (
        receipt.get("schema_version") != 2
        or receipt.get("kind") != "rpc-fewshot-confirmation-score-receipt"
        or receipt.get("status") != "completed"
        or receipt.get("decision_status") != "provisional"
        or receipt.get("aggregate_stage") != "confirmation"
        or receipt.get("decision_scope") != "complete_confirmation_fold_seed_aggregate"
        or type(receipt.get("provisional_pass")) is not bool
        or receipt.get("provisional_pass") is not claim.provisional_pass
        or receipt.get("condition_count") != 1
    ):
        raise ValueError("invalid Stage-4 confirmation score receipt decision")
    candidate = _one_stage_four_condition(
        receipt.get("candidate_conditions"), "candidate", claim.condition
    )
    reference = _one_stage_four_condition(
        receipt.get("reference_conditions"), "reference", None
    )
    if (
        reference.stage != "confirmation"
        or reference.shot_count != 150
        or (
            reference.method,
            reference.selector,
            reference.fold,
            reference.support_seed,
        )
        != (
            candidate.method,
            candidate.selector,
            candidate.fold,
            candidate.support_seed,
        )
    ):
        raise ValueError("Stage-4 confirmation score receipt has mismatched reference condition")
    if receipt.get("candidate_condition_ids") != [candidate.condition_id] or receipt.get(
        "reference_condition_ids"
    ) != [reference.condition_id]:
        raise ValueError("Stage-4 confirmation score receipt condition IDs do not match conditions")
    candidate_plan = _stage_four_scoring_plan(
        receipt.get("candidate_scoring_plan"), "candidate", candidate
    )
    reference_plan = _stage_four_scoring_plan(
        receipt.get("reference_scoring_plan"), "reference", reference
    )
    candidate_fingerprint = _stage_four_plan_fingerprint(candidate_plan)
    if candidate_fingerprint != _stage_four_plan_fingerprint(reference_plan):
        raise ValueError("Stage-4 confirmation receipt candidate/reference scoring plan mismatch")
    cohort = receipt.get("cohort")
    if not isinstance(cohort, Mapping) or set(cohort) != {
        "base_category_ids", "novel_category_ids"
    }:
        raise ValueError("Stage-4 confirmation score receipt lacks immutable cohort")
    base = _stage_four_category_ids(cohort.get("base_category_ids"), "base")
    novel = _stage_four_category_ids(cohort.get("novel_category_ids"), "novel")
    if base & novel or base | novel != set(candidate_plan.registered_category_ids):
        raise ValueError("Stage-4 confirmation score receipt cohort does not match scoring plan")
    if (
        receipt.get("candidate_scoring_plan_sha256") != candidate_plan.sha256
        or receipt.get("reference_scoring_plan_sha256") != reference_plan.sha256
    ):
        raise ValueError("Stage-4 confirmation score receipt scoring plan SHA-256 mismatch")
    _validate_stage_four_score_receipts(receipt.get("score_receipts"), candidate)
    _validate_stage_four_raw_evidence(receipt.get("raw_evidence"), candidate, reference)
    _validate_stage_four_branch_reports(
        receipt.get("condition_branch_top1"), candidate, reference
    )
    _validate_stage_four_full_system(
        receipt.get("candidate_full_system"), "candidate", candidate_plan
    )
    _validate_stage_four_full_system(
        receipt.get("reference_full_system"), "reference", reference_plan
    )
    locked_ground_truth = _validate_stage_four_locked_ground_truth(
        receipt.get("locked_ground_truth")
    )
    _validate_stage_four_fold_base_checkpoint(
        receipt.get("minimum_rule_inputs"),
        receipt.get("paired_bootstrap_95"),
        receipt.get("candidate_full_system"),
        receipt.get("fold_base_checkpoint"),
        candidate_plan,
        candidate,
        receipt.get("provisional_pass"),
    )
    _validate_stage_four_confirmation_derivation(
        receipt,
        trusted_source_root=trusted_source_root,
    )
    return StageFourConfirmationBinding(
        cohort_manifest_sha256=locked_ground_truth,
        novel_category_ids=tuple(sorted(novel)),
        base_category_ids=tuple(sorted(base)),
        scoring_plan_fingerprint=_stage_four_plan_context(candidate_plan),
        fold_base_artifact=next(
            item for item in candidate_plan.fold_base_artifacts if item.fold == candidate.fold
        ),
    )


def _validate_stage_four_confirmation_derivation(
    receipt: Mapping[str, object],
    *,
    trusted_source_root: Path,
) -> None:
    """Delegate byte-level Stage-4 reconstruction to the score-artifact verifier.

    The source-owned scorer owns metric aggregation; keeping this thin bridge
    avoids a duplicate implementation with subtly different safety semantics
    in the scheduler.  The import is intentionally delayed because that scorer
    also consumes this immutable protocol module.
    """
    try:
        from bakery_scanner.experiments.rpc_scoring import (
            validate_stage_four_confirmation_derivation,
        )

        validate_stage_four_confirmation_derivation(
            receipt,
            trusted_source_root=trusted_source_root,
        )
    except (ImportError, OSError, ValueError) as exc:
        raise ValueError("Stage-4 confirmation score receipt is not derivable from upstream artifacts") from exc


def _validate_stage_four_score_receipts(
    value: object, candidate: ExperimentCondition
) -> None:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], Mapping):
        raise ValueError("Stage-4 confirmation score receipt lacks aggregate score receipt provenance")
    item = value[0]
    if set(item) != {"candidate_condition_id", "sha256"} or (
        item.get("candidate_condition_id") != candidate.condition_id
    ):
        raise ValueError("Stage-4 confirmation score receipt has invalid aggregate score receipt provenance")
    _validate_sha256("Stage-4 aggregate score receipt SHA-256", item.get("sha256"))


def _validate_stage_four_raw_evidence(
    value: object, candidate: ExperimentCondition, reference: ExperimentCondition
) -> None:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], Mapping):
        raise ValueError("Stage-4 confirmation score receipt lacks raw evidence provenance")
    item = value[0]
    required = {
        "candidate_condition_id",
        "candidate_evidence_sha256",
        "reference_condition_id",
        "reference_evidence_sha256",
    }
    if (
        set(item) != required
        or item.get("candidate_condition_id") != candidate.condition_id
        or item.get("reference_condition_id") != reference.condition_id
    ):
        raise ValueError("Stage-4 confirmation score receipt has invalid raw evidence provenance")
    _validate_sha256("Stage-4 candidate raw evidence SHA-256", item.get("candidate_evidence_sha256"))
    _validate_sha256("Stage-4 reference raw evidence SHA-256", item.get("reference_evidence_sha256"))


def _validate_stage_four_branch_reports(
    value: object, candidate: ExperimentCondition, reference: ExperimentCondition
) -> None:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], Mapping):
        raise ValueError("Stage-4 confirmation score receipt lacks branch evidence")
    item = value[0]
    if set(item) != {
        "candidate_condition_id", "reference_condition_id", "candidate", "reference"
    } or (
        item.get("candidate_condition_id") != candidate.condition_id
        or item.get("reference_condition_id") != reference.condition_id
    ):
        raise ValueError("Stage-4 confirmation score receipt has invalid branch evidence")
    for name in ("candidate", "reference"):
        branches = item.get(name)
        if not isinstance(branches, Mapping) or set(branches) != {
            "repvit_global", "dinov3_global", "dinov3_local"
        }:
            raise ValueError("Stage-4 confirmation score receipt has incomplete branch evidence")
        for branch in branches.values():
            _validate_stage_four_branch_summary(branch)


def _validate_stage_four_branch_summary(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "sample_count", "novel_macro_recall", "base_macro_recall", "per_category_recall",
        "confusion_matrix", "fifth_percentile_sku_accuracy", "wrong_registered_sku_rate",
    }:
        raise ValueError("Stage-4 branch summary is invalid")
    _validate_positive_integer("Stage-4 branch sample_count", value.get("sample_count"))
    _validate_stage_four_metric("Stage-4 branch novel macro recall", value.get("novel_macro_recall"))
    _validate_stage_four_metric("Stage-4 branch base macro recall", value.get("base_macro_recall"))
    _validate_stage_four_category_metrics(value.get("per_category_recall"))
    _validate_stage_four_confusion_matrix(value.get("confusion_matrix"))
    _validate_stage_four_metric("Stage-4 branch fifth percentile SKU accuracy", value.get("fifth_percentile_sku_accuracy"))
    _validate_stage_four_metric("Stage-4 branch wrong registered-SKU rate", value.get("wrong_registered_sku_rate"))


def _validate_stage_four_full_system(
    value: object, name: str, plan: "ScoringPlan"
) -> None:
    required = {
        "sample_count",
        "wrong_registered_sku_rate",
        "novel_wrong_registered_sku_rate",
        "base_wrong_registered_sku_rate",
        "unknown_rate",
        "registered_coverage",
        "novel_macro_final_correct_recall",
        "base_macro_final_correct_recall",
        "per_category_final_correct_recall",
        "novel_loss_over_10pp_fraction",
        "conditional_dino_execution_rate",
        "by_difficulty",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"Stage-4 {name} full-system summary is invalid")
    _validate_positive_integer(f"Stage-4 {name} sample_count", value.get("sample_count"))
    for metric in required - {"sample_count", "per_category_final_correct_recall", "by_difficulty"}:
        _validate_stage_four_metric(f"Stage-4 {name} {metric}", value.get(metric))
    _validate_stage_four_category_metrics(
        value.get("per_category_final_correct_recall"), expected=plan.registered_category_ids
    )
    difficulties = value.get("by_difficulty")
    if not isinstance(difficulties, Mapping) or not difficulties:
        raise ValueError(f"Stage-4 {name} difficulty summary is invalid")
    for difficulty, summary in difficulties.items():
        if not isinstance(difficulty, str) or not difficulty:
            raise ValueError(f"Stage-4 {name} difficulty summary is invalid")
        _validate_stage_four_difficulty_summary(summary, name)


def _validate_stage_four_difficulty_summary(value: object, name: str) -> None:
    required = {
        "sample_count", "unknown_rate", "registered_coverage", "wrong_registered_sku_rate",
        "novel_macro_final_correct_recall", "base_macro_final_correct_recall",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"Stage-4 {name} difficulty summary is invalid")
    _validate_nonnegative_integer(
        f"Stage-4 {name} difficulty sample_count", value.get("sample_count")
    )
    for metric in required - {"sample_count"}:
        _validate_stage_four_metric(f"Stage-4 {name} difficulty {metric}", value.get(metric))


def _validate_stage_four_category_metrics(value: object, *, expected: tuple[int, ...] | None = None) -> None:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("Stage-4 category metrics are invalid")
    categories: set[int] = set()
    for category, metric in value.items():
        try:
            parsed = int(category)
        except (TypeError, ValueError) as exc:
            raise ValueError("Stage-4 category metrics are invalid") from exc
        if str(parsed) != str(category) or parsed <= 0 or parsed in categories:
            raise ValueError("Stage-4 category metrics are invalid")
        categories.add(parsed)
        _validate_stage_four_metric("Stage-4 category metric", metric)
    if expected is not None and categories != set(expected):
        raise ValueError("Stage-4 category metrics do not match the scoring plan")


def _validate_stage_four_confusion_matrix(value: object) -> None:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("Stage-4 branch confusion matrix is invalid")
    for truth, predictions in value.items():
        try:
            truth_id = int(truth)
        except (TypeError, ValueError) as exc:
            raise ValueError("Stage-4 branch confusion matrix is invalid") from exc
        if truth_id <= 0 or str(truth_id) != str(truth) or not isinstance(predictions, Mapping) or not predictions:
            raise ValueError("Stage-4 branch confusion matrix is invalid")
        for predicted, count in predictions.items():
            try:
                predicted_id = int(predicted)
            except (TypeError, ValueError) as exc:
                raise ValueError("Stage-4 branch confusion matrix is invalid") from exc
            if predicted_id <= 0 or str(predicted_id) != str(predicted):
                raise ValueError("Stage-4 branch confusion matrix is invalid")
            _validate_positive_integer("Stage-4 branch confusion count", count)


def _validate_stage_four_locked_ground_truth(value: object) -> str:
    if not isinstance(value, Mapping) or set(value) != {
        "burst_count", "manifest_sha256", "object_count", "sample_count",
        "source_manifest_sha256", "scene_role_manifest_sha256",
    }:
        raise ValueError("Stage-4 confirmation score receipt lacks locked ground-truth provenance")
    _validate_sha256("Stage-4 locked ground-truth manifest SHA-256", value.get("manifest_sha256"))
    _validate_sha256("Stage-4 locked source manifest SHA-256", value.get("source_manifest_sha256"))
    _validate_sha256("Stage-4 locked scene-role manifest SHA-256", value.get("scene_role_manifest_sha256"))
    for name in ("burst_count", "object_count", "sample_count"):
        _validate_positive_integer(f"Stage-4 locked ground-truth {name}", value.get(name))
    return value["manifest_sha256"]  # type: ignore[return-value]


def _validate_stage_four_fold_base_checkpoint(
    minimum_rule_inputs: object,
    paired_bootstrap: object,
    candidate_summary: object,
    fold_base_checkpoint: object,
    plan: "ScoringPlan",
    candidate: ExperimentCondition,
    provisional_pass: object,
) -> None:
    if not isinstance(fold_base_checkpoint, Mapping) or set(fold_base_checkpoint) != {
        "base_macro_final_correct_recall", "checkpoint_sha256", "evidence_sha256", "fold"
    }:
        raise ValueError("Stage-4 confirmation score receipt lacks fold base checkpoint")
    artifact = next(item for item in plan.fold_base_artifacts if item.fold == candidate.fold)
    if (
        fold_base_checkpoint.get("fold") != candidate.fold
        or fold_base_checkpoint.get("checkpoint_sha256") != artifact.checkpoint_sha256
        or fold_base_checkpoint.get("evidence_sha256") != artifact.evidence_sha256
    ):
        raise ValueError("Stage-4 fold base checkpoint does not match scoring plan")
    _validate_stage_four_metric(
        "Stage-4 fold base checkpoint recall",
        fold_base_checkpoint.get("base_macro_final_correct_recall"),
    )
    if not isinstance(paired_bootstrap, Mapping) or set(paired_bootstrap) != {
        "replicates", "seed", "novel_macro_recall_lower_delta", "novel_macro_recall_upper_delta",
        "novel_wrong_registered_sku_rate_lower_delta", "novel_wrong_registered_sku_rate_upper_delta",
        "base_macro_recall_lower_delta", "base_macro_recall_upper_delta",
    } or paired_bootstrap.get("seed") != plan.bootstrap_seed or (
        paired_bootstrap.get("replicates") != plan.bootstrap_replicates
    ):
        raise ValueError("Stage-4 paired bootstrap does not match scoring plan")
    for name in set(paired_bootstrap) - {"seed", "replicates"}:
        _validate_finite_metric(f"Stage-4 paired bootstrap {name}", paired_bootstrap.get(name))
    if any(
        float(paired_bootstrap[lower]) > float(paired_bootstrap[upper])
        for lower, upper in (
            ("novel_macro_recall_lower_delta", "novel_macro_recall_upper_delta"),
            ("novel_wrong_registered_sku_rate_lower_delta", "novel_wrong_registered_sku_rate_upper_delta"),
            ("base_macro_recall_lower_delta", "base_macro_recall_upper_delta"),
        )
    ):
        raise ValueError("Stage-4 paired bootstrap interval is invalid")
    required = {
        "registered_coverage", "novel_macro_recall_lower_delta",
        "novel_wrong_registered_sku_rate_upper_delta", "novel_loss_over_10pp_fraction",
        "candidate_base_macro_final_correct_recall", "fold_base_checkpoint_macro_final_correct_recall",
    }
    if not isinstance(minimum_rule_inputs, Mapping) or set(minimum_rule_inputs) != required:
        raise ValueError("Stage-4 confirmation score receipt lacks minimum-rule inputs")
    for name in required:
        validator = (
            _validate_finite_metric
            if name in {
                "novel_macro_recall_lower_delta",
                "novel_wrong_registered_sku_rate_upper_delta",
            }
            else _validate_stage_four_metric
        )
        validator(f"Stage-4 minimum-rule {name}", minimum_rule_inputs.get(name))
    if not isinstance(candidate_summary, Mapping) or (
        minimum_rule_inputs["registered_coverage"] != candidate_summary.get("registered_coverage")
        or minimum_rule_inputs["novel_loss_over_10pp_fraction"] != candidate_summary.get("novel_loss_over_10pp_fraction")
        or minimum_rule_inputs["candidate_base_macro_final_correct_recall"]
        != candidate_summary.get("base_macro_final_correct_recall")
        or minimum_rule_inputs["fold_base_checkpoint_macro_final_correct_recall"]
        != fold_base_checkpoint.get("base_macro_final_correct_recall")
        or minimum_rule_inputs["novel_macro_recall_lower_delta"]
        != paired_bootstrap.get("novel_macro_recall_lower_delta")
        or minimum_rule_inputs["novel_wrong_registered_sku_rate_upper_delta"]
        != paired_bootstrap.get("novel_wrong_registered_sku_rate_upper_delta")
        or _stage_four_minimum_rule_pass(minimum_rule_inputs) is not provisional_pass
    ):
        raise ValueError("Stage-4 confirmation decision does not match its aggregate inputs")


def _validate_positive_integer(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_nonnegative_integer(name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_finite_metric(name: str, value: object) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _validate_stage_four_metric(name: str, value: object) -> None:
    _validate_finite_metric(name, value)
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")


def _stage_four_minimum_rule_pass(value: Mapping[str, object]) -> bool:
    return (
        float(value["registered_coverage"]) > 0.0
        and float(value["novel_macro_recall_lower_delta"]) >= -0.02
        and float(value["novel_wrong_registered_sku_rate_upper_delta"]) <= 0.005
        and float(value["novel_loss_over_10pp_fraction"]) <= 0.05
        and (
            float(value["candidate_base_macro_final_correct_recall"])
            - float(value["fold_base_checkpoint_macro_final_correct_recall"])
        ) >= -0.01
    )


def _one_stage_four_condition(
    value: object,
    name: str,
    expected: ExperimentCondition | None,
) -> ExperimentCondition:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], Mapping):
        raise ValueError(f"Stage-4 confirmation score receipt requires one {name} condition")
    condition = ExperimentCondition.from_dict(value[0])
    if condition.to_dict() != dict(value[0]) or (expected is not None and condition != expected):
        raise ValueError(f"Stage-4 confirmation score receipt {name} condition does not match selection")
    return condition


def _stage_four_scoring_plan(
    value: object, name: str, condition: ExperimentCondition
) -> "ScoringPlan":
    if not isinstance(value, Mapping):
        raise ValueError(f"Stage-4 confirmation score receipt lacks {name} scoring plan")
    plan = ScoringPlan.from_dict(value)
    if plan.to_dict() != dict(value) or plan.expected_condition_ids != (condition.condition_id,):
        raise ValueError(f"Stage-4 confirmation score receipt {name} scoring plan does not bind condition")
    if plan.folds != (condition.fold,) or plan.support_seeds != (condition.support_seed,):
        raise ValueError(f"Stage-4 confirmation score receipt {name} scoring plan does not bind fold/seed")
    return plan


def _stage_four_plan_fingerprint(plan: "ScoringPlan") -> tuple[object, ...]:
    return (
        plan.bootstrap_seed,
        plan.bootstrap_replicates,
        plan.folds,
        plan.support_seeds,
        plan.cohort_id,
        plan.registered_category_ids,
        plan.fold_base_artifacts,
    )


def _stage_four_plan_context(plan: "ScoringPlan") -> tuple[object, ...]:
    """Plan dimensions that must survive confirmation-to-locked expansion."""
    return (
        plan.bootstrap_seed,
        plan.bootstrap_replicates,
        plan.cohort_id,
        plan.registered_category_ids,
    )


def _stage_four_category_ids(value: object, name: str) -> set[int]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"Stage-4 {name} cohort is invalid")
    try:
        categories = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"Stage-4 {name} cohort is invalid") from exc
    if not categories or len(categories) != len(set(categories)) or any(
        type(category) is not int or category <= 0 for category in categories
    ):
        raise ValueError(f"Stage-4 {name} cohort is invalid")
    return set(categories)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def stage_one_conditions(*, seeds: Iterable[int] = (101,), folds: Iterable[int] = range(5)) -> tuple[ExperimentCondition, ...]:
    """Return the complete preregistered Stage-1 matrix, never a Cartesian expansion."""
    return _conditions(_STAGE_ONE_PAIRS, _STAGE_ONE_SHOTS, seeds, folds, "stage1")


def ascending_conditions(
    methods: Iterable[str | tuple[str, str]], *, seeds: Iterable[int], folds: Iterable[int], extended: bool = False
) -> tuple[ExperimentCondition, ...]:
    """Return a preregistered ascending-shot comparison for one or two methods."""
    pairs = tuple(_method_pair(method) for method in methods)
    if not pairs or len(pairs) > 2:
        raise ValueError("ascending conditions require one or two selected methods")
    if len({method for method, _ in pairs}) != len(pairs):
        raise ValueError("ascending conditions cannot duplicate methods")
    if any(pair not in _STAGE_ONE_PAIRS for pair in pairs):
        raise ValueError("unsupported method/selector combination")
    shots = _ASCENDING_SHOTS + (_EXTENDED_ASCENDING_SHOTS if extended else ())
    return _conditions(pairs, shots, seeds, folds, "ascending")


def confirmation_conditions(
    method: str | tuple[str, str],
    *,
    shot_counts: Iterable[int],
    seeds: Iterable[int],
    folds: Iterable[int],
) -> tuple[ExperimentCondition, ...]:
    """Materialize the frozen Stage-4 full-subsystem confirmation quartet.

    The caller supplies the already selected last failure, provisional minimum,
    next passing anchor, and balanced reference.  Requiring exactly four unique
    values with a 150-shot reference prevents this scheduler being used as a
    second exploratory learning-curve sweep.
    """
    pair = _method_pair(method)
    if pair not in _STAGE_ONE_PAIRS:
        raise ValueError("unsupported method/selector combination")
    shots = tuple(shot_counts)
    k1_special = len(shots) == 3 and set(shots) == {1, 3, 150}
    if (len(shots) != 4 or len(set(shots)) != 4 or 150 not in shots) and not k1_special:
        raise ValueError("confirmation requires four unique shots including the 150-shot reference, or k1/3/150")
    if any(shot not in _CONFIRMATION_SHOTS for shot in shots):
        raise ValueError("unsupported confirmation condition")
    return _conditions((pair,), shots, seeds, folds, "confirmation")


def locked_conditions(
    selection: StageFourSelection,
    *,
    confirmation_score_receipt_paths: Iterable[Path],
    trusted_source_root: Path,
) -> tuple[ExperimentCondition, ...]:
    """Materialize only the Stage-5 pair proven by four immutable Stage-4 files."""
    if not isinstance(selection, StageFourSelection):
        raise TypeError("locked conditions require a StageFourSelection")
    validate_stage_four_confirmation_score_receipts(
        selection,
        confirmation_score_receipt_paths,
        trusted_source_root=trusted_source_root,
    )
    return _conditions(
        ((selection.method, selection.selector),),
        (selection.provisional_minimum_shot_count, 150),
        (selection.support_seed,),
        (selection.fold,),
        "locked",
    )


def refinement_shots(last_failure: int, first_pass: int) -> tuple[int, ...]:
    try:
        return _REFINEMENTS[(last_failure, first_pass)]
    except KeyError as exc:
        raise ValueError("refinement interval is not preregistered") from exc


def all_available_diagnostic_conditions(
    method: str | tuple[str, str], *, folds: Iterable[int]
) -> tuple[ExperimentCondition, ...]:
    """Schedule the one-time upper-bound diagnostic outside the minimum funnel."""
    pair = _method_pair(method)
    if pair not in _STAGE_ONE_PAIRS:
        raise ValueError("unsupported method/selector combination")
    frozen_folds = tuple(folds)
    if not frozen_folds or not all(type(fold) is int and fold >= 0 for fold in frozen_folds):
        raise ValueError("all_available diagnostic requires nonempty integer folds")
    return tuple(
        _new_condition(pair[0], pair[1], 0, fold, 0, "ascending", support_scope="all_available")
        for fold in frozen_folds
    )


@dataclass(frozen=True, slots=True)
class StageOneMethodEvidence:
    """Aggregate forced-Top-1 evidence for one preregistered method cell."""

    method: str
    selector: str
    repvit_novel_macro_top1: float
    dinov3_novel_macro_top1: float
    repvit_wrong_sku_rate: float
    dinov3_wrong_sku_rate: float

    def __post_init__(self) -> None:
        if (self.method, self.selector) not in _STAGE_ONE_PAIRS:
            raise ValueError("unsupported Stage-1 method/selector evidence")
        for name in (
            "repvit_novel_macro_top1", "dinov3_novel_macro_top1",
            "repvit_wrong_sku_rate", "dinov3_wrong_sku_rate",
        ):
            value = getattr(self, name)
            if type(value) not in {int, float} or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")

    @property
    def method_selector(self) -> tuple[str, str]:
        return self.method, self.selector


@dataclass(frozen=True, slots=True)
class StageOneSelectionDecision:
    """Frozen Stage-1 choice and declared seed-expansion evidence."""

    retained_methods: tuple[tuple[str, str], ...]
    removed_methods: tuple[tuple[str, str], ...]
    expand_to_ten_seeds: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "retained_methods": [list(item) for item in self.retained_methods],
            "removed_methods": [list(item) for item in self.removed_methods],
            "expand_to_ten_seeds": [list(item) for item in self.expand_to_ten_seeds],
            "dominance_rule": "both branches >2pp lower and no branch wrong-SKU improvement",
            "seed_expansion_rule": "within 1pp of best branch or non-dominated error trade-off expands to ten seeds",
        }


@dataclass(frozen=True, slots=True)
class StageOneSelectionReceipt:
    """Immutable screen-decision artifact; it cannot claim a minimum result."""

    evidence: tuple[StageOneMethodEvidence, ...]
    decision: StageOneSelectionDecision

    def __post_init__(self) -> None:
        if not self.evidence or any(not isinstance(item, StageOneMethodEvidence) for item in self.evidence):
            raise ValueError("Stage-1 selection receipt requires method evidence")
        if not isinstance(self.decision, StageOneSelectionDecision):
            raise ValueError("Stage-1 selection receipt requires a decision")
        if self.decision != select_stage_one_methods(self.evidence):
            raise ValueError("Stage-1 selection receipt decision does not reproduce frozen evidence")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "rpc-fewshot-stage1-selection-receipt",
            "decision_scope": "method_screen_only_not_a_minimum",
            "evidence": [
                {
                    "method": item.method,
                    "selector": item.selector,
                    "repvit_novel_macro_top1": item.repvit_novel_macro_top1,
                    "dinov3_novel_macro_top1": item.dinov3_novel_macro_top1,
                    "repvit_wrong_sku_rate": item.repvit_wrong_sku_rate,
                    "dinov3_wrong_sku_rate": item.dinov3_wrong_sku_rate,
                }
                for item in self.evidence
            ],
            "decision": self.decision.to_dict(),
        }


def select_stage_one_methods(
    evidence: Iterable[StageOneMethodEvidence],
) -> StageOneSelectionDecision:
    """Apply the declared two-branch dominance and seed-expansion rule.

    A method is removed only if another method beats it by >2pp on both
    branch macro Top-1 values while not worsening either branch wrong-SKU
    rate.  Surviving accuracy/error trade-offs are ranked deterministically;
    at most two continue.  Any non-dominated contender within 1pp of either
    best branch (or presenting an accuracy/error trade-off) expands from five
    to ten support seeds before the continuation decision is frozen.
    """
    rows = tuple(evidence)
    if not rows or any(not isinstance(item, StageOneMethodEvidence) for item in rows):
        raise ValueError("Stage-1 selection requires method evidence")
    if len({item.method_selector for item in rows}) != len(rows):
        raise ValueError("Stage-1 selection has duplicate method evidence")
    def dominates(left: StageOneMethodEvidence, right: StageOneMethodEvidence) -> bool:
        return (
            left.repvit_novel_macro_top1 > right.repvit_novel_macro_top1 + 0.02
            and left.dinov3_novel_macro_top1 > right.dinov3_novel_macro_top1 + 0.02
            and left.repvit_wrong_sku_rate <= right.repvit_wrong_sku_rate
            and left.dinov3_wrong_sku_rate <= right.dinov3_wrong_sku_rate
        )
    survivors = tuple(item for item in rows if not any(dominates(other, item) for other in rows if other != item))
    ranked = tuple(sorted(
        survivors,
        key=lambda item: (
            -(item.repvit_novel_macro_top1 + item.dinov3_novel_macro_top1),
            item.repvit_wrong_sku_rate + item.dinov3_wrong_sku_rate,
            item.method,
            item.selector,
        ),
    ))[:2]
    best_repvit = max(item.repvit_novel_macro_top1 for item in rows)
    best_dinov3 = max(item.dinov3_novel_macro_top1 for item in rows)
    def has_accuracy_error_tradeoff(item: StageOneMethodEvidence) -> bool:
        return any(
            (
                item.repvit_wrong_sku_rate < other.repvit_wrong_sku_rate
                or item.dinov3_wrong_sku_rate < other.dinov3_wrong_sku_rate
            )
            and (
                item.repvit_novel_macro_top1 < other.repvit_novel_macro_top1
                or item.dinov3_novel_macro_top1 < other.dinov3_novel_macro_top1
            )
            for other in rows
            if other != item
        )
    expanded = tuple(
        item.method_selector
        for item in survivors
        if (
            item.repvit_novel_macro_top1 >= best_repvit - 0.01
            or item.dinov3_novel_macro_top1 >= best_dinov3 - 0.01
            or has_accuracy_error_tradeoff(item)
        )
    )
    return StageOneSelectionDecision(
        retained_methods=tuple(item.method_selector for item in ranked),
        removed_methods=tuple(sorted(item.method_selector for item in rows if item not in survivors)),
        expand_to_ten_seeds=expanded,
    )


@dataclass(frozen=True, slots=True)
class FoldBaseArtifact:
    """Frozen fold-base checkpoint and its reviewed evidence receipt."""

    fold: int
    checkpoint_sha256: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        if type(self.fold) is not int or self.fold < 0:
            raise ValueError("fold base artifact fold must be a non-negative integer")
        _validate_sha256("fold base checkpoint_sha256", self.checkpoint_sha256)
        _validate_sha256("fold base evidence_sha256", self.evidence_sha256)

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "FoldBaseArtifact":
        if not isinstance(value, Mapping) or set(value) != {
            "fold",
            "checkpoint_sha256",
            "evidence_sha256",
        }:
            raise ValueError("invalid fold base artifact")
        return cls(
            fold=value["fold"],  # type: ignore[arg-type]
            checkpoint_sha256=value["checkpoint_sha256"],  # type: ignore[arg-type]
            evidence_sha256=value["evidence_sha256"],  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_sha256": self.checkpoint_sha256,
            "evidence_sha256": self.evidence_sha256,
            "fold": self.fold,
        }


@dataclass(frozen=True, slots=True)
class ScoringPlan:
    """Immutable decision universe shared by condition and score receipts."""

    bootstrap_seed: int
    bootstrap_replicates: int
    folds: tuple[int, ...]
    support_seeds: tuple[int, ...]
    expected_condition_ids: tuple[str, ...]
    cohort_id: str
    registered_category_ids: tuple[int, ...]
    fold_base_artifacts: tuple[FoldBaseArtifact, ...]
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported scoring plan schema_version")
        if type(self.bootstrap_seed) is not int:
            raise ValueError("bootstrap_seed must be an integer")
        if type(self.bootstrap_replicates) is not int or self.bootstrap_replicates <= 0:
            raise ValueError("bootstrap_replicates must be a positive integer")
        _validate_unique_tuple("folds", self.folds, lambda value: type(value) is int and value >= 0)
        _validate_unique_tuple("support_seeds", self.support_seeds, lambda value: type(value) is int)
        _validate_unique_tuple(
            "expected_condition_ids",
            self.expected_condition_ids,
            lambda value: isinstance(value, str) and bool(value),
        )
        coordinate_count = len(self.folds) * len(self.support_seeds)
        if (
            len(self.expected_condition_ids) < coordinate_count
            or len(self.expected_condition_ids) % coordinate_count != 0
        ):
            raise ValueError(
                "expected condition IDs must declare a complete fold/seed matrix"
            )
        if not isinstance(self.cohort_id, str) or not self.cohort_id:
            raise ValueError("cohort_id must be nonempty")
        _validate_unique_tuple(
            "registered_category_ids",
            self.registered_category_ids,
            lambda value: type(value) is int and value > 0,
        )
        _validate_unique_tuple(
            "fold_base_artifacts",
            self.fold_base_artifacts,
            lambda value: isinstance(value, FoldBaseArtifact),
        )
        if tuple(item.fold for item in self.fold_base_artifacts) != self.folds:
            raise ValueError("fold base artifacts must exactly cover declared folds")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ScoringPlan":
        if not isinstance(value, Mapping):
            raise ValueError("scoring plan must be an object")
        expected = {
            "bootstrap_seed",
            "bootstrap_replicates",
            "folds",
            "support_seeds",
            "expected_condition_ids",
            "cohort_id",
            "registered_category_ids",
            "fold_base_artifacts",
            "schema_version",
        }
        if set(value) != expected:
            raise ValueError("scoring plan has missing or unrecognized fields")
        try:
            return cls(
                bootstrap_seed=value["bootstrap_seed"],  # type: ignore[arg-type]
                bootstrap_replicates=value["bootstrap_replicates"],  # type: ignore[arg-type]
                folds=tuple(value["folds"]),  # type: ignore[arg-type]
                support_seeds=tuple(value["support_seeds"]),  # type: ignore[arg-type]
                expected_condition_ids=tuple(value["expected_condition_ids"]),  # type: ignore[arg-type]
                cohort_id=value["cohort_id"],  # type: ignore[arg-type]
                registered_category_ids=tuple(value["registered_category_ids"]),  # type: ignore[arg-type]
                fold_base_artifacts=tuple(
                    FoldBaseArtifact.from_dict(item)
                    for item in value["fold_base_artifacts"]  # type: ignore[union-attr]
                ),
                schema_version=value["schema_version"],  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid scoring plan") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "bootstrap_replicates": self.bootstrap_replicates,
            "bootstrap_seed": self.bootstrap_seed,
            "cohort_id": self.cohort_id,
            "expected_condition_ids": list(self.expected_condition_ids),
            "folds": list(self.folds),
            "fold_base_artifacts": [
                item.to_dict() for item in self.fold_base_artifacts
            ],
            "registered_category_ids": list(self.registered_category_ids),
            "schema_version": self.schema_version,
            "support_seeds": list(self.support_seeds),
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.to_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class ExperimentReceipt:
    condition: ExperimentCondition
    condition_manifest_sha256: str
    model_sha256: str
    support_sha256: str
    calibration_sha256: str
    policy_sha256: str
    preprocessing_sha256: str
    code_sha256: str
    cohort_manifest_sha256: str
    novel_category_ids: tuple[int, ...]
    base_category_ids: tuple[int, ...]
    scoring_plan: ScoringPlan
    base_checkpoint_sha256: str
    base_checkpoint_evidence_sha256: str
    environment_lock_digest: str
    output_uri: str
    status: Literal["completed", "failed", "unavailable"]
    reason: str = ""
    stage_four_selection: StageFourSelection | None = None
    stage_four_confirmation_score_receipt_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.condition, ExperimentCondition):
            raise ValueError("condition must be an ExperimentCondition")
        for name in _HASH_FIELDS:
            _validate_sha256(name, getattr(self, name))
        _validate_sha256("cohort_manifest_sha256", self.cohort_manifest_sha256)
        _validate_sha256("base_checkpoint_sha256", self.base_checkpoint_sha256)
        _validate_sha256("base_checkpoint_evidence_sha256", self.base_checkpoint_evidence_sha256)
        _validate_cohorts(self.novel_category_ids, self.base_category_ids)
        if not isinstance(self.scoring_plan, ScoringPlan):
            raise ValueError("scoring_plan must be an immutable ScoringPlan")
        if self.condition.condition_id not in self.scoring_plan.expected_condition_ids:
            raise ValueError("condition is not an expected condition in the scoring plan")
        if self.condition.fold not in self.scoring_plan.folds:
            raise ValueError("condition fold is not declared by the scoring plan")
        if self.condition.support_seed not in self.scoring_plan.support_seeds:
            raise ValueError("condition support seed is not declared by the scoring plan")
        fold_base = next(
            item
            for item in self.scoring_plan.fold_base_artifacts
            if item.fold == self.condition.fold
        )
        if (
            self.base_checkpoint_sha256 != fold_base.checkpoint_sha256
            or self.base_checkpoint_evidence_sha256 != fold_base.evidence_sha256
        ):
            raise ValueError("condition fold base artifacts do not match the scoring plan")
        receipt_categories = set(self.novel_category_ids) | set(self.base_category_ids)
        if receipt_categories != set(self.scoring_plan.registered_category_ids):
            raise ValueError("condition cohort does not equal the scoring plan registered cohort")
        if not isinstance(self.environment_lock_digest, str) or not self.environment_lock_digest:
            raise ValueError("environment_lock_digest must be nonempty")
        if not isinstance(self.output_uri, str) or not self.output_uri:
            raise ValueError("output_uri must be nonempty")
        if self.status not in {"completed", "failed", "unavailable"}:
            raise ValueError("status must be completed, failed, or unavailable")
        if self.status == "unavailable" and not self.reason:
            raise ValueError("unavailable receipt requires a reason")
        if self.condition.stage == "locked":
            if self.status == "completed":
                raise ValueError(
                    "locked ExperimentReceipt cannot be completed; only the re-derived scorer aggregate is authoritative"
                )
            if not isinstance(self.stage_four_selection, StageFourSelection):
                raise ValueError("locked receipt requires a Stage-4 selection")
            selection = self.stage_four_selection
            if (
                self.condition.method,
                self.condition.selector,
                self.condition.fold,
                self.condition.support_seed,
            ) != (
                selection.method,
                selection.selector,
                selection.fold,
                selection.support_seed,
            ) or self.condition.shot_count not in {
                selection.provisional_minimum_shot_count,
                150,
            }:
                raise ValueError("locked receipt condition does not match its Stage-4 selection")
        elif self.stage_four_selection is not None:
            raise ValueError("only locked receipts may bind a Stage-4 selection")
        elif self.stage_four_confirmation_score_receipt_paths:
            raise ValueError("only locked receipts may bind Stage-4 receipt paths")

    @classmethod
    def completed(cls, condition: ExperimentCondition, **values: object) -> "ExperimentReceipt":
        _validate_sha256("policy_sha256", values.get("policy_sha256"))
        return cls(condition=condition, status="completed", **values)

    @classmethod
    def unavailable(
        cls, condition: ExperimentCondition, *, reason: str, **values: object
    ) -> "ExperimentReceipt":
        return cls(condition=condition, status="unavailable", reason=reason, **values)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": "rpc-fewshot-experiment-receipt",
            "schema_version": 2,
            "calibration_sha256": self.calibration_sha256,
            "code_sha256": self.code_sha256,
            "cohort": {
                "base_category_ids": list(self.base_category_ids),
                "fold": self.condition.fold,
                "manifest_sha256": self.cohort_manifest_sha256,
                "novel_category_ids": list(self.novel_category_ids),
            },
            "fold_base_checkpoint": {
                "checkpoint_sha256": self.base_checkpoint_sha256,
                "evidence_sha256": self.base_checkpoint_evidence_sha256,
                "fold": self.condition.fold,
            },
            "scoring_plan": self.scoring_plan.to_dict(),
            "scoring_plan_sha256": self.scoring_plan.sha256,
            "scoring": {
                "registered_category_ids": list(self.scoring_plan.registered_category_ids),
            },
            "condition": self.condition.to_dict(),
            "condition_manifest_sha256": self.condition_manifest_sha256,
            "environment_lock_digest": self.environment_lock_digest,
            "model_sha256": self.model_sha256,
            "output_uri": self.output_uri,
            "policy_sha256": self.policy_sha256,
            "preprocessing_sha256": self.preprocessing_sha256,
            "reason": self.reason,
            "status": self.status,
            "stage_four_selection": (
                self.stage_four_selection.to_dict()
                if self.stage_four_selection is not None
                else None
            ),
            "stage_four_confirmation_score_receipt_paths": list(
                self.stage_four_confirmation_score_receipt_paths
            ),
            "support_sha256": self.support_sha256,
        }
        if self.condition.support_scope == "all_available":
            result["decision_scope"] = "upper_bound_diagnostic_not_a_minimum"
        return result


def write_experiment_receipt(path: Path, receipt: ExperimentReceipt) -> None:
    """Atomically create a receipt without ever replacing a prior record."""
    if not isinstance(receipt, ExperimentReceipt):
        raise ValueError("receipt must be an ExperimentReceipt")
    write_new_json(Path(path), receipt.to_dict())


def _conditions(
    pairs: tuple[tuple[str, str], ...], shots: tuple[int, ...], seeds: Iterable[int], folds: Iterable[int], stage: str
) -> tuple[ExperimentCondition, ...]:
    frozen_seeds = tuple(seeds)
    frozen_folds = tuple(folds)
    if not all(type(seed) is int for seed in frozen_seeds) or not all(
        type(fold) is int and fold >= 0 for fold in frozen_folds
    ):
        raise ValueError("seeds and folds must be integer values")
    return tuple(
        _new_condition(method, selector, shot, fold, seed, stage)
        for seed in frozen_seeds
        for fold in frozen_folds
        for method, selector in pairs
        for shot in shots
    )


def _new_condition(method: str, selector: str, shot: int, fold: int, seed: int, stage: str, *, support_scope: Literal["fixed_k", "all_available"] = "fixed_k") -> ExperimentCondition:
    return ExperimentCondition(method, selector, shot, fold, seed, stage, _condition_id(method, selector, shot, fold, seed, stage, support_scope), support_scope)


def _condition_id(method: str, selector: str, shot: int, fold: int, seed: int, stage: str, support_scope: str = "fixed_k") -> str:
    payload = {"fold": fold, "method": method, "selector": selector, "shot_count": shot, "stage": stage, "support_seed": seed}
    if support_scope != "fixed_k":
        payload["support_scope"] = support_scope
    return "rpc-" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _method_pair(method: str | tuple[str, str]) -> tuple[str, str]:
    if isinstance(method, str):
        return method, "div"
    if isinstance(method, tuple) and len(method) == 2 and all(isinstance(item, str) for item in method):
        return method
    raise ValueError("method must be a method name or method/selector pair")


def _validate_sha256(name: str, value: object) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase 64-character SHA-256")


def _validate_cohorts(novel: object, base: object) -> None:
    for name, values in (("novel_category_ids", novel), ("base_category_ids", base)):
        if not isinstance(values, tuple):
            raise ValueError(f"{name} must be a nonempty tuple of positive category IDs")
        frozen = values
        if not frozen or any(type(value) is not int or value <= 0 for value in frozen) or len(set(frozen)) != len(frozen):
            raise ValueError(f"{name} must be a nonempty tuple of unique positive category IDs")
    if set(novel) & set(base):
        raise ValueError("novel and base category cohorts must be disjoint")


def _validate_unique_tuple(
    name: str, values: object, predicate: Callable[[object], bool]
) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be a nonempty tuple")
    if not values:
        raise ValueError(f"{name} must be a nonempty tuple")
    if any(not predicate(value) for value in values):
        raise ValueError(f"{name} contains an invalid value")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must contain unique values")
