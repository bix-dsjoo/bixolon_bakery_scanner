"""Fail-closed, hash-bound scoring for RPC few-shot research evidence.

This module deliberately operates on RPC category identifiers only.  It has no
dependency on the bakery runtime taxonomy or any model adapter.
"""

from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from numbers import Real
from typing import Any, Iterable, Mapping, Sequence


_HASH_NAMES = (
    "condition_manifest_sha256",
    "model_sha256",
    "support_sha256",
    "calibration_sha256",
    "policy_sha256",
    "preprocessing_sha256",
    "code_sha256",
)
_BOUND_HASH_NAMES = _HASH_NAMES[:-1]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIFFICULTIES = ("E", "M", "H")
PairIdentity = tuple[str, int, str, int]


@dataclass(frozen=True, slots=True)
class ResearchEvidenceRow:
    """One score-bearing, reproducible research evaluation observation."""

    sample_id: str
    condition_id: str
    fold: int
    difficulty: str
    burst_id: str
    truth_category_id: int
    predicted_category_id: int | None
    score_category_ids: tuple[int, ...]
    scores: tuple[float, ...]
    condition_manifest_sha256: str
    model_sha256: str
    support_sha256: str
    calibration_sha256: str
    policy_sha256: str
    preprocessing_sha256: str
    code_sha256: str

    def __post_init__(self) -> None:
        for name in ("sample_id", "condition_id", "burst_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be nonempty")
        if type(self.fold) is not int or self.fold < 0:
            raise ValueError("fold must be a non-negative integer")
        if self.difficulty not in _DIFFICULTIES:
            raise ValueError("difficulty must be E, M, or H")
        if type(self.truth_category_id) is not int or self.truth_category_id <= 0:
            raise ValueError("truth category ID must be a positive integer")
        if self.predicted_category_id is not None and (
            type(self.predicted_category_id) is not int or self.predicted_category_id <= 0
        ):
            raise ValueError("predicted category ID must be a positive integer or None")
        category_ids = _integer_tuple(self.score_category_ids, "score category IDs")
        if not category_ids or len(set(category_ids)) != len(category_ids):
            raise ValueError("score category IDs must be a nonempty ordered unique sequence")
        scores = _finite_tuple(self.scores, "scores")
        if len(scores) != len(category_ids):
            raise ValueError("score category IDs and scores must have equal length")
        if self.truth_category_id not in category_ids:
            raise ValueError("truth category ID is missing from scores")
        if self.predicted_category_id is not None and self.predicted_category_id not in category_ids:
            raise ValueError("predicted category ID is missing from scores")
        object.__setattr__(self, "score_category_ids", category_ids)
        object.__setattr__(self, "scores", scores)
        for name in _HASH_NAMES:
            _validate_hash(name, getattr(self, name))

    @property
    def pair_identity(self) -> PairIdentity:
        return (self.sample_id, self.fold, self.burst_id, self.truth_category_id)

    @property
    def forced_top1_category_id(self) -> int:
        """Use the first maximum, preserving the producer's declared score order."""
        return self.score_category_ids[max(range(len(self.scores)), key=self.scores.__getitem__)]

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "condition_id": self.condition_id,
            "fold": self.fold,
            "difficulty": self.difficulty,
            "burst_id": self.burst_id,
            "truth_category_id": self.truth_category_id,
            "predicted_category_id": self.predicted_category_id,
            "score_category_ids": list(self.score_category_ids),
            "scores": list(self.scores),
            **{name: getattr(self, name) for name in _HASH_NAMES},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ResearchEvidenceRow":
        if not isinstance(value, Mapping):
            raise ValueError("evidence row must be an object")
        required = {
            "sample_id", "condition_id", "fold", "difficulty", "burst_id", "truth_category_id",
            "predicted_category_id", "score_category_ids", "scores", *_HASH_NAMES,
        }
        missing = required - set(value)
        extra = set(value) - required
        if missing or extra:
            raise ValueError("evidence row has missing or unrecognized fields")
        try:
            return cls(
                sample_id=value["sample_id"],  # type: ignore[arg-type]
                condition_id=value["condition_id"],  # type: ignore[arg-type]
                fold=value["fold"],  # type: ignore[arg-type]
                difficulty=value["difficulty"],  # type: ignore[arg-type]
                burst_id=value["burst_id"],  # type: ignore[arg-type]
                truth_category_id=value["truth_category_id"],  # type: ignore[arg-type]
                predicted_category_id=value["predicted_category_id"],  # type: ignore[arg-type]
                score_category_ids=tuple(value["score_category_ids"]),  # type: ignore[arg-type]
                scores=tuple(value["scores"]),  # type: ignore[arg-type]
                **{name: value[name] for name in _HASH_NAMES},  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid evidence row") from exc


@dataclass(frozen=True, slots=True)
class ForcedTop1Summary:
    sample_count: int
    novel_macro_recall: float
    base_macro_recall: float
    per_category_recall: Mapping[int, float]
    top1_agreement: float


@dataclass(frozen=True, slots=True)
class DifficultySummary:
    sample_count: int
    unknown_rate: float
    registered_coverage: float
    wrong_registered_sku_rate: float
    novel_macro_final_correct_recall: float
    base_macro_final_correct_recall: float


@dataclass(frozen=True, slots=True)
class FullSystemSummary:
    sample_count: int
    wrong_registered_sku_rate: float
    unknown_rate: float
    registered_coverage: float
    novel_macro_final_correct_recall: float
    base_macro_final_correct_recall: float
    per_category_final_correct_recall: Mapping[int, float]
    novel_loss_over_10pp_fraction: float
    by_difficulty: Mapping[str, DifficultySummary]


@dataclass(frozen=True, slots=True)
class PairedBootstrapInterval:
    replicates: int
    seed: int
    novel_macro_recall_lower_delta: float
    novel_macro_recall_upper_delta: float
    wrong_registered_sku_rate_lower_delta: float
    wrong_registered_sku_rate_upper_delta: float
    base_macro_recall_lower_delta: float
    base_macro_recall_upper_delta: float


def validate_evidence_rows(rows: Iterable[ResearchEvidenceRow]) -> tuple[ResearchEvidenceRow, ...]:
    """Reject duplicates and mixed condition/provenance within one evidence file."""
    frozen = tuple(rows)
    if not frozen:
        raise ValueError("evidence must not be empty")
    if not all(isinstance(row, ResearchEvidenceRow) for row in frozen):
        raise ValueError("evidence rows must be ResearchEvidenceRow instances")
    sample_ids = [row.sample_id for row in frozen]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("duplicate sample_id")
    first = frozen[0]
    provenance = _provenance_key(first)
    if any(row.condition_id != first.condition_id or _provenance_key(row) != provenance for row in frozen[1:]):
        raise ValueError("provenance mismatch within evidence")
    return frozen


def validate_evidence_against_condition(
    rows: Iterable[ResearchEvidenceRow], condition: Mapping[str, object]
) -> tuple[ResearchEvidenceRow, ...]:
    """Bind canonical rows to the immutable condition receipt's hashes."""
    frozen = validate_evidence_rows(rows)
    expected_id, expected_hashes = condition_provenance(condition)
    novel, base = condition_cohort(condition)
    permitted = novel | base
    for row in frozen:
        if row.condition_id != expected_id:
            raise ValueError("condition ID provenance mismatch")
        for name, expected in expected_hashes.items():
            if getattr(row, name) != expected:
                raise ValueError(f"{name} provenance mismatch")
        if row.truth_category_id not in permitted or (
            row.predicted_category_id is not None and row.predicted_category_id not in permitted
        ):
            raise ValueError("evidence category is outside the bound cohort")
    return frozen


def condition_provenance(condition: Mapping[str, object]) -> tuple[str, Mapping[str, str]]:
    """Read the score-binding fields from a completed immutable receipt JSON."""
    if not isinstance(condition, Mapping):
        raise ValueError("condition receipt must be an object")
    nested = condition.get("condition")
    condition_id = nested.get("condition_id") if isinstance(nested, Mapping) else None
    if not isinstance(condition_id, str) or not condition_id:
        raise ValueError("condition receipt lacks condition_id")
    hashes: dict[str, str] = {}
    for name in _HASH_NAMES:
        value = condition.get(name)
        _validate_hash(name, value)
        hashes[name] = value
    return condition_id, hashes


def condition_cohort(condition: Mapping[str, object]) -> tuple[set[int], set[int]]:
    """Return the receipt-bound novel/base cohorts, never an ambient override."""
    if not isinstance(condition, Mapping):
        raise ValueError("condition receipt must be an object")
    cohort = condition.get("cohort")
    nested = condition.get("condition")
    if not isinstance(cohort, Mapping) or not isinstance(nested, Mapping):
        raise ValueError("condition receipt lacks bound cohort")
    fold = cohort.get("fold")
    if type(fold) is not int or fold != nested.get("fold"):
        raise ValueError("condition receipt cohort fold mismatch")
    _validate_hash("cohort manifest_sha256", cohort.get("manifest_sha256"))
    novel = _category_set(cohort.get("novel_category_ids"), "novel cohort")
    base = _category_set(cohort.get("base_category_ids"), "base cohort")
    if novel & base:
        raise ValueError("novel and base cohorts overlap")
    return novel, base


def validate_paired_evidence(
    candidate: Iterable[ResearchEvidenceRow], reference: Iterable[ResearchEvidenceRow]
) -> tuple[tuple[ResearchEvidenceRow, ...], tuple[ResearchEvidenceRow, ...]]:
    """Require exact one-to-one pairing without conflating distinct conditions."""
    candidate_rows = validate_evidence_rows(candidate)
    reference_rows = validate_evidence_rows(reference)
    candidate_ids = {row.pair_identity for row in candidate_rows}
    reference_ids = {row.pair_identity for row in reference_rows}
    if candidate_ids != reference_ids:
        raise ValueError("paired identity mismatch")
    if len(candidate_ids) != len(candidate_rows) or len(reference_ids) != len(reference_rows):
        raise ValueError("duplicate paired identity")
    reference_by_identity = {row.pair_identity: row for row in reference_rows}
    if any(row.difficulty != reference_by_identity[row.pair_identity].difficulty for row in candidate_rows):
        raise ValueError("paired difficulty mismatch")
    return candidate_rows, reference_rows


def forced_top1_summary(
    rows: Iterable[ResearchEvidenceRow], *, novel_category_ids: set[int] | frozenset[int]
) -> ForcedTop1Summary:
    frozen = validate_evidence_rows(rows)
    _validate_observed_cohorts(frozen, frozenset(novel_category_ids))
    recalls = _category_recalls(frozen, lambda row: row.forced_top1_category_id == row.truth_category_id)
    agreement = _mean(row.predicted_category_id == row.forced_top1_category_id for row in frozen)
    return ForcedTop1Summary(
        sample_count=len(frozen),
        novel_macro_recall=_macro(recalls, novel_category_ids),
        base_macro_recall=_macro(recalls, _base_categories(frozen, novel_category_ids)),
        per_category_recall=recalls,
        top1_agreement=agreement,
    )


def full_system_summary(
    rows: Iterable[ResearchEvidenceRow], *, novel_category_ids: set[int] | frozenset[int], reference_rows: Iterable[ResearchEvidenceRow] | None = None
) -> FullSystemSummary:
    frozen = validate_evidence_rows(rows)
    _validate_observed_cohorts(frozen, frozenset(novel_category_ids))
    if reference_rows is not None:
        _, reference = validate_paired_evidence(frozen, reference_rows)
        reference_recalls = _category_recalls(reference, _final_correct)
    else:
        reference_recalls = None
    return _full_summary(frozen, frozenset(novel_category_ids), reference_recalls)


def bootstrap_paired_deltas(
    candidate: Iterable[ResearchEvidenceRow], reference: Iterable[ResearchEvidenceRow], *, novel_category_ids: set[int] | frozenset[int], seed: int, replicates: int
) -> PairedBootstrapInterval:
    """Deterministically resample category/fold then scene-burst/difficulty pairs."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(replicates) is not int or replicates <= 0:
        raise ValueError("replicates must be a positive integer")
    candidate_rows, reference_rows = validate_paired_evidence(candidate, reference)
    _validate_observed_cohorts(candidate_rows, frozenset(novel_category_ids))
    _validate_observed_cohorts(reference_rows, frozenset(novel_category_ids))
    reference_by_id = {row.pair_identity: row for row in reference_rows}
    paired = tuple((row, reference_by_id[row.pair_identity]) for row in candidate_rows)
    randomizer = random.Random(seed)
    deltas: list[tuple[float, float, float]] = []
    for _ in range(replicates):
        sampled = _hierarchical_sample(paired, randomizer, frozenset(novel_category_ids))
        sampled_candidate = tuple(pair[0] for pair in sampled)
        sampled_reference = tuple(pair[1] for pair in sampled)
        c_summary = _full_summary(sampled_candidate, frozenset(novel_category_ids), None)
        r_summary = _full_summary(sampled_reference, frozenset(novel_category_ids), None)
        deltas.append((
            c_summary.novel_macro_final_correct_recall - r_summary.novel_macro_final_correct_recall,
            c_summary.wrong_registered_sku_rate - r_summary.wrong_registered_sku_rate,
            c_summary.base_macro_final_correct_recall - r_summary.base_macro_final_correct_recall,
        ))
    return PairedBootstrapInterval(
        replicates=replicates,
        seed=seed,
        novel_macro_recall_lower_delta=_percentile([delta[0] for delta in deltas], 0.025),
        novel_macro_recall_upper_delta=_percentile([delta[0] for delta in deltas], 0.975),
        wrong_registered_sku_rate_lower_delta=_percentile([delta[1] for delta in deltas], 0.025),
        wrong_registered_sku_rate_upper_delta=_percentile([delta[1] for delta in deltas], 0.975),
        base_macro_recall_lower_delta=_percentile([delta[2] for delta in deltas], 0.025),
        base_macro_recall_upper_delta=_percentile([delta[2] for delta in deltas], 0.975),
    )


def passes_minimum_rule(candidate: FullSystemSummary, reference: FullSystemSummary, interval: PairedBootstrapInterval) -> bool:
    """Apply the preregistered fail-closed rule; Unknown-only output cannot pass."""
    if not isinstance(candidate, FullSystemSummary) or not isinstance(reference, FullSystemSummary):
        raise ValueError("candidate and reference must be full-system summaries")
    if not isinstance(interval, PairedBootstrapInterval):
        raise ValueError("interval must be a paired bootstrap interval")
    unknown_only = candidate.registered_coverage == 0.0
    base_delta = candidate.base_macro_final_correct_recall - reference.base_macro_final_correct_recall
    tolerance = 1e-12
    return (
        not unknown_only
        and interval.novel_macro_recall_lower_delta >= -0.02 - tolerance
        and interval.wrong_registered_sku_rate_upper_delta <= 0.005 + tolerance
        and candidate.novel_loss_over_10pp_fraction <= 0.05 + tolerance
        and base_delta >= -0.01 - tolerance
    )


def _full_summary(rows: Sequence[ResearchEvidenceRow], novel: frozenset[int], reference_recalls: Mapping[int, float] | None) -> FullSystemSummary:
    recalls = _category_recalls(rows, _final_correct)
    by_difficulty = {
        difficulty: _difficulty_summary(tuple(row for row in rows if row.difficulty == difficulty), novel)
        for difficulty in _DIFFICULTIES
    }
    losses = [
        category for category in novel if category in recalls and reference_recalls is not None
        and reference_recalls.get(category, 0.0) - recalls[category] > 0.10
    ]
    return FullSystemSummary(
        sample_count=len(rows),
        wrong_registered_sku_rate=_mean(_wrong_registered(row) for row in rows),
        unknown_rate=_mean(row.predicted_category_id is None for row in rows),
        registered_coverage=_mean(row.predicted_category_id is not None for row in rows),
        novel_macro_final_correct_recall=_macro(recalls, novel),
        base_macro_final_correct_recall=_macro(recalls, _base_categories(rows, novel)),
        per_category_final_correct_recall=recalls,
        novel_loss_over_10pp_fraction=(len(losses) / len(novel)) if novel else 0.0,
        by_difficulty=by_difficulty,
    )


def _difficulty_summary(rows: Sequence[ResearchEvidenceRow], novel: frozenset[int]) -> DifficultySummary:
    if not rows:
        return DifficultySummary(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    recalls = _category_recalls(rows, _final_correct)
    return DifficultySummary(
        sample_count=len(rows),
        unknown_rate=_mean(row.predicted_category_id is None for row in rows),
        registered_coverage=_mean(row.predicted_category_id is not None for row in rows),
        wrong_registered_sku_rate=_mean(_wrong_registered(row) for row in rows),
        novel_macro_final_correct_recall=_macro(recalls, novel),
        base_macro_final_correct_recall=_macro(recalls, _base_categories(rows, novel)),
    )


def _hierarchical_sample(
    pairs: Sequence[tuple[ResearchEvidenceRow, ResearchEvidenceRow]], randomizer: random.Random, novel: frozenset[int]
) -> tuple[tuple[ResearchEvidenceRow, ResearchEvidenceRow], ...]:
    by_fold: dict[int, dict[int, list[tuple[ResearchEvidenceRow, ResearchEvidenceRow]]]] = defaultdict(lambda: defaultdict(list))
    for pair in pairs:
        by_fold[pair[0].fold][pair[0].truth_category_id].append(pair)
    sampled: list[tuple[ResearchEvidenceRow, ResearchEvidenceRow]] = []
    for fold in sorted(by_fold):
        category_pairs = by_fold[fold]
        # Each cohort is sampled independently; this explicitly includes novel categories.
        for cohort in (
            sorted(category for category in category_pairs if category in novel),
            sorted(category for category in category_pairs if category not in novel),
        ):
            if not cohort:
                continue
            for category in (randomizer.choice(cohort) for _ in cohort):
                source = category_pairs[category]
                by_difficulty: dict[str, dict[str, list[tuple[ResearchEvidenceRow, ResearchEvidenceRow]]]] = defaultdict(lambda: defaultdict(list))
                for pair in source:
                    by_difficulty[pair[0].difficulty][pair[0].burst_id].append(pair)
                for difficulty in sorted(by_difficulty):
                    bursts = sorted(by_difficulty[difficulty])
                    for burst in (randomizer.choice(bursts) for _ in bursts):
                        sampled.extend(by_difficulty[difficulty][burst])
    return tuple(sampled)


def _category_recalls(rows: Sequence[ResearchEvidenceRow], predicate: Any) -> dict[int, float]:
    grouped: dict[int, list[ResearchEvidenceRow]] = defaultdict(list)
    for row in rows:
        grouped[row.truth_category_id].append(row)
    return {category: _mean(predicate(row) for row in items) for category, items in sorted(grouped.items())}


def _base_categories(rows: Sequence[ResearchEvidenceRow], novel: set[int] | frozenset[int]) -> set[int]:
    return {row.truth_category_id for row in rows} - set(novel)


def _macro(recalls: Mapping[int, float], categories: Iterable[int]) -> float:
    selected = [recalls[category] for category in sorted(set(categories)) if category in recalls]
    return sum(selected) / len(selected) if selected else 0.0


def _validate_observed_cohorts(rows: Sequence[ResearchEvidenceRow], novel: frozenset[int]) -> None:
    if not novel:
        raise ValueError("novel cohort must not be empty")
    observed = {row.truth_category_id for row in rows}
    absent_novel = novel - observed
    if absent_novel:
        raise ValueError("novel cohort is absent from evidence")
    if not observed - novel:
        raise ValueError("base cohort is absent from evidence")


def _category_set(value: object, name: str) -> set[int]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a nonempty category ID sequence")
    try:
        result = set(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a nonempty category ID sequence") from exc
    if not result or any(type(item) is not int or item <= 0 for item in result):
        raise ValueError(f"{name} must be a nonempty category ID sequence")
    return result


def _final_correct(row: ResearchEvidenceRow) -> bool:
    return row.predicted_category_id == row.truth_category_id


def _wrong_registered(row: ResearchEvidenceRow) -> bool:
    return row.predicted_category_id is not None and row.predicted_category_id != row.truth_category_id


def _mean(values: Iterable[bool]) -> float:
    frozen = tuple(values)
    return sum(frozen) / len(frozen) if frozen else 0.0


def _percentile(values: Sequence[float], proportion: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("bootstrap produced no values")
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _provenance_key(row: ResearchEvidenceRow) -> tuple[str, ...]:
    return tuple(getattr(row, name) for name in _HASH_NAMES)


def _validate_hash(name: str, value: object) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")


def _integer_tuple(values: object, name: str) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be an integer sequence")
    try:
        frozen = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer sequence") from exc
    if any(type(value) is not int or value <= 0 for value in frozen):
        raise ValueError(f"{name} must be positive integers")
    return frozen


def _finite_tuple(values: object, name: str) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a finite numeric sequence")
    try:
        frozen = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a finite numeric sequence") from exc
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in frozen):
        raise ValueError(f"{name} must be a finite numeric sequence")
    result = tuple(float(value) for value in frozen)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} must be finite")
    return result
