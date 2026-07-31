"""Preregistered, immutable conditions and receipts for RPC few-shot experiments."""

from __future__ import annotations

import hashlib
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

    def __post_init__(self) -> None:
        if (self.method, self.selector) not in _STAGE_ONE_PAIRS:
            raise ValueError("unsupported method/selector combination")
        if type(self.shot_count) is not int or self.shot_count <= 0:
            raise ValueError("shot_count must be a positive integer")
        if type(self.fold) is not int or self.fold < 0:
            raise ValueError("fold must be a non-negative integer")
        if type(self.support_seed) is not int:
            raise ValueError("support_seed must be an integer")
        if self.stage == "stage1" and self.shot_count not in _STAGE_ONE_SHOTS:
            raise ValueError("unsupported Stage-1 condition")
        if self.stage == "ascending" and self.shot_count not in (
            _ASCENDING_SHOTS + _EXTENDED_ASCENDING_SHOTS
        ):
            raise ValueError("unsupported ascending condition")
        if self.stage in {"confirmation", "locked"} and self.shot_count not in _CONFIRMATION_SHOTS:
            raise ValueError("unsupported confirmation or locked condition")
        if self.stage not in {"stage1", "ascending", "confirmation", "locked"}:
            raise ValueError("unsupported stage")
        expected = _condition_id(
            self.method, self.selector, self.shot_count, self.fold, self.support_seed, self.stage
        )
        if self.condition_id != expected:
            raise ValueError("condition_id is not deterministic for condition contents")

    def to_dict(self) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "fold": self.fold,
            "method": self.method,
            "selector": self.selector,
            "shot_count": self.shot_count,
            "stage": self.stage,
            "support_seed": self.support_seed,
        }


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
    if len(shots) != 4 or len(set(shots)) != 4 or 150 not in shots:
        raise ValueError("confirmation requires four unique shots including the 150-shot reference")
    if any(shot not in _CONFIRMATION_SHOTS for shot in shots):
        raise ValueError("unsupported confirmation condition")
    return _conditions((pair,), shots, seeds, folds, "confirmation")


def locked_conditions(
    method: str | tuple[str, str],
    *,
    candidate_shot_count: int,
    seeds: Iterable[int],
    folds: Iterable[int],
) -> tuple[ExperimentCondition, ...]:
    """Materialize the Stage-5 provisional-minimum versus 150-shot comparison."""
    pair = _method_pair(method)
    if pair not in _STAGE_ONE_PAIRS:
        raise ValueError("unsupported method/selector combination")
    if candidate_shot_count not in _CONFIRMATION_SHOTS:
        raise ValueError("unsupported locked candidate condition")
    shots = (candidate_shot_count,) if candidate_shot_count == 150 else (
        candidate_shot_count,
        150,
    )
    return _conditions((pair,), shots, seeds, folds, "locked")


def refinement_shots(last_failure: int, first_pass: int) -> tuple[int, ...]:
    try:
        return _REFINEMENTS[(last_failure, first_pass)]
    except KeyError as exc:
        raise ValueError("refinement interval is not preregistered") from exc


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
        return {
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
            "support_sha256": self.support_sha256,
        }


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


def _new_condition(method: str, selector: str, shot: int, fold: int, seed: int, stage: str) -> ExperimentCondition:
    return ExperimentCondition(method, selector, shot, fold, seed, stage, _condition_id(method, selector, shot, fold, seed, stage))


def _condition_id(method: str, selector: str, shot: int, fold: int, seed: int, stage: str) -> str:
    payload = {"fold": fold, "method": method, "selector": selector, "shot_count": shot, "stage": stage, "support_seed": seed}
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
