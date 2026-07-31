"""Preregistered, immutable conditions and receipts for RPC few-shot experiments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json


_STAGE_ONE_PAIRS = (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
_STAGE_ONE_SHOTS = (1, 3, 5)
_ASCENDING_SHOTS = (1, 3, 5, 10, 20)
_EXTENDED_ASCENDING_SHOTS = (40, 80, 150)
_REFINEMENTS = {(3, 5): (4,), (5, 10): (6, 8), (10, 20): (12, 15, 18)}
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
        if self.stage not in {"stage1", "ascending"}:
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


def refinement_shots(last_failure: int, first_pass: int) -> tuple[int, ...]:
    try:
        return _REFINEMENTS[(last_failure, first_pass)]
    except KeyError as exc:
        raise ValueError("refinement interval is not preregistered") from exc


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
        _validate_cohorts(self.novel_category_ids, self.base_category_ids)
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
            "calibration_sha256": self.calibration_sha256,
            "code_sha256": self.code_sha256,
            "cohort": {
                "base_category_ids": list(self.base_category_ids),
                "fold": self.condition.fold,
                "manifest_sha256": self.cohort_manifest_sha256,
                "novel_category_ids": list(self.novel_category_ids),
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
