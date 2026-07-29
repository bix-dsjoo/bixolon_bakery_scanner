"""Deterministic object regression records for CPU inference candidates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from bakery_scanner.classification.contracts import ClassificationDecision
from bakery_scanner.contracts import Box, BreadProposal

from .cpu_dataset import CpuEvaluationSample, CpuEvaluationTarget


_IOU_THRESHOLD = 0.50
_SKU_IDS = frozenset(range(1, 21))


class ObjectOutcome(str, Enum):
    CORRECT = "correct"
    TOP3_CANDIDATE = "top3_candidate"
    CANDIDATE_OUT_UNKNOWN = "candidate_out_unknown"
    MISCLASSIFIED = "misclassified"
    MISSED = "missed"


_ALLOWED = {
    ObjectOutcome.CORRECT: {ObjectOutcome.CORRECT},
    ObjectOutcome.TOP3_CANDIDATE: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
    },
    ObjectOutcome.CANDIDATE_OUT_UNKNOWN: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
    },
    ObjectOutcome.MISCLASSIFIED: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
        ObjectOutcome.MISCLASSIFIED,
    },
    ObjectOutcome.MISSED: {
        ObjectOutcome.CORRECT,
        ObjectOutcome.TOP3_CANDIDATE,
        ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
        ObjectOutcome.MISSED,
    },
}


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    sample_key: str
    annotation_id: int
    expected_sku: int
    outcome: ObjectOutcome
    predicted_sku: int | None
    top3_sku_ids: tuple[int, ...]
    matched_proposal_index: int | None
    iou: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.sample_key, str) or not self.sample_key:
            raise ValueError("sample_key must be non-empty")
        if type(self.annotation_id) is not int or self.annotation_id <= 0:
            raise ValueError("annotation_id must be a positive integer")
        if self.expected_sku not in _SKU_IDS:
            raise ValueError("expected_sku must be a registered SKU")
        if not isinstance(self.outcome, ObjectOutcome):
            raise ValueError("outcome must be an ObjectOutcome")
        if self.predicted_sku is not None and self.predicted_sku not in _SKU_IDS:
            raise ValueError("predicted_sku must be a registered SKU")
        if any(sku_id not in _SKU_IDS for sku_id in self.top3_sku_ids):
            raise ValueError("top3_sku_ids must contain registered SKUs")
        if len(set(self.top3_sku_ids)) != len(self.top3_sku_ids):
            raise ValueError("top3_sku_ids must be unique")
        if self.matched_proposal_index is None:
            if self.iou is not None:
                raise ValueError("unmatched records must not have IoU")
        else:
            if type(self.matched_proposal_index) is not int or self.matched_proposal_index < 0:
                raise ValueError("matched_proposal_index must be non-negative")
            if self.iou is None or not math.isfinite(self.iou) or not _IOU_THRESHOLD <= self.iou <= 1.0:
                raise ValueError("matched records require a finite IoU in [0.50, 1.00]")


@dataclass(frozen=True, slots=True)
class ImageRegressionRecord:
    sample_key: str
    objects: tuple[ObjectRecord, ...]
    false_positive_proposal_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sample_key, str) or not self.sample_key:
            raise ValueError("sample_key must be non-empty")
        object.__setattr__(self, "objects", tuple(self.objects))
        if any(record.sample_key != self.sample_key for record in self.objects):
            raise ValueError("object records must belong to their image record")
        annotation_ids = tuple(record.annotation_id for record in self.objects)
        if annotation_ids != tuple(sorted(annotation_ids)) or len(set(annotation_ids)) != len(annotation_ids):
            raise ValueError("object records must have unique annotation IDs in order")
        indices = tuple(self.false_positive_proposal_indices)
        if any(type(index) is not int or index < 0 for index in indices):
            raise ValueError("false-positive proposal indexes must be non-negative integers")
        if indices != tuple(sorted(indices)) or len(set(indices)) != len(indices):
            raise ValueError("false-positive proposal indexes must be unique and ordered")
        object.__setattr__(self, "false_positive_proposal_indices", indices)


@dataclass(frozen=True, slots=True)
class RunAggregate:
    top1: int
    top3: int
    false_positives: int
    false_negatives: int
    unknown: int
    misclassified: int

    def __post_init__(self) -> None:
        values = (
            self.top1,
            self.top3,
            self.false_positives,
            self.false_negatives,
            self.unknown,
            self.misclassified,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("aggregate counts must be non-negative integers")


@dataclass(frozen=True, slots=True)
class Regression:
    sample_key: str
    annotation_id: int
    reason: str
    reference: ObjectRecord | None
    candidate: ObjectRecord | None


@dataclass(frozen=True, slots=True)
class RegressionGateReport:
    reference: RunAggregate
    candidate: RunAggregate
    regressions: tuple[Regression, ...]
    passed: bool


def transition_is_allowed(before: ObjectOutcome | str, after: ObjectOutcome | str) -> bool:
    return ObjectOutcome(after) in _ALLOWED[ObjectOutcome(before)]


def build_image_regression_record(
    sample: CpuEvaluationSample,
    proposals: Sequence[BreadProposal],
    decisions: Sequence[ClassificationDecision],
) -> ImageRegressionRecord:
    """Match one image's detector candidates to its GT at canonical-frame IoU 0.50."""
    if len(proposals) != len(decisions):
        raise ValueError("proposals and decisions must have identical lengths")
    if any(not isinstance(proposal, BreadProposal) for proposal in proposals):
        raise ValueError("proposals must contain BreadProposal values")
    if any(not isinstance(decision, ClassificationDecision) for decision in decisions):
        raise ValueError("decisions must contain ClassificationDecision values")

    matches = _greedy_matches(sample.targets, proposals)
    records: list[ObjectRecord] = []
    matched_proposals: set[int] = set()
    for target in sorted(sample.targets, key=lambda item: item.annotation_id):
        match = matches.get(target.annotation_id)
        if match is None:
            records.append(
                ObjectRecord(
                    sample_key=sample.key,
                    annotation_id=target.annotation_id,
                    expected_sku=target.sku_id,
                    outcome=ObjectOutcome.MISSED,
                    predicted_sku=None,
                    top3_sku_ids=(),
                    matched_proposal_index=None,
                    iou=None,
                )
            )
            continue
        proposal_index, iou = match
        matched_proposals.add(proposal_index)
        decision = decisions[proposal_index]
        records.append(_object_record(sample.key, target, decision, proposal_index, iou))

    return ImageRegressionRecord(
        sample_key=sample.key,
        objects=tuple(records),
        false_positive_proposal_indices=tuple(
            index for index in range(len(proposals)) if index not in matched_proposals
        ),
    )


def aggregate_records(
    records: Sequence[ObjectRecord] | Sequence[ImageRegressionRecord],
) -> RunAggregate:
    objects, false_positives = _flatten_records(records)
    return RunAggregate(
        top1=sum(record.outcome is ObjectOutcome.CORRECT for record in objects),
        top3=sum(
            record.outcome in {ObjectOutcome.CORRECT, ObjectOutcome.TOP3_CANDIDATE}
            for record in objects
        ),
        false_positives=false_positives,
        false_negatives=sum(record.outcome is ObjectOutcome.MISSED for record in objects),
        unknown=sum(
            record.outcome in {ObjectOutcome.TOP3_CANDIDATE, ObjectOutcome.CANDIDATE_OUT_UNKNOWN}
            for record in objects
        ),
        misclassified=sum(record.outcome is ObjectOutcome.MISCLASSIFIED for record in objects),
    )


def aggregate_meets_quality_floors(aggregate: RunAggregate) -> bool:
    return (
        aggregate.top1 >= 1349
        and aggregate.top3 >= 1390
        and aggregate.false_positives == 0
        and aggregate.false_negatives <= 5
        and aggregate.unknown <= 48
        and aggregate.misclassified <= 4
    )


def compare_run(
    reference: Sequence[ObjectRecord] | Sequence[ImageRegressionRecord],
    candidate: Sequence[ObjectRecord] | Sequence[ImageRegressionRecord],
) -> RegressionGateReport:
    """Reject forbidden object transitions and every candidate aggregate floor breach."""
    reference_objects, _ = _flatten_records(reference)
    candidate_objects, _ = _flatten_records(candidate)
    reference_by_key = _records_by_key(reference_objects)
    candidate_by_key = _records_by_key(candidate_objects)
    if set(reference_by_key) != set(candidate_by_key):
        raise ValueError("reference and candidate must cover identical annotation identities")

    regressions: list[Regression] = []
    for key in sorted(reference_by_key):
        before = reference_by_key[key]
        after = candidate_by_key[key]
        if before.expected_sku != after.expected_sku:
            raise ValueError("reference and candidate expected SKU identities must match")
        reason = _transition_regression_reason(before, after)
        if reason is not None:
            regressions.append(Regression(key[0], key[1], reason, before, after))

    reference_aggregate = aggregate_records(reference)
    candidate_aggregate = aggregate_records(candidate)
    return RegressionGateReport(
        reference=reference_aggregate,
        candidate=candidate_aggregate,
        regressions=tuple(regressions),
        passed=not regressions and aggregate_meets_quality_floors(candidate_aggregate),
    )


def _object_record(
    sample_key: str,
    target: CpuEvaluationTarget,
    decision: ClassificationDecision,
    proposal_index: int,
    iou: float,
) -> ObjectRecord:
    if decision.decision == "sku":
        outcome = ObjectOutcome.CORRECT if decision.sku_id == target.sku_id else ObjectOutcome.MISCLASSIFIED
        return ObjectRecord(
            sample_key,
            target.annotation_id,
            target.sku_id,
            outcome,
            decision.sku_id,
            (),
            proposal_index,
            iou,
        )
    top3 = tuple(candidate.sku_id for candidate in decision.top3)
    return ObjectRecord(
        sample_key,
        target.annotation_id,
        target.sku_id,
        ObjectOutcome.TOP3_CANDIDATE if target.sku_id in top3 else ObjectOutcome.CANDIDATE_OUT_UNKNOWN,
        None,
        top3,
        proposal_index,
        iou,
    )


def _greedy_matches(
    targets: Sequence[CpuEvaluationTarget], proposals: Sequence[BreadProposal]
) -> dict[int, tuple[int, float]]:
    edges: list[tuple[float, int, float, float, float, float, float, int, int]] = []
    for target in targets:
        for proposal_index, proposal in enumerate(proposals):
            iou = _iou(target.box, proposal.box)
            if iou >= _IOU_THRESHOLD:
                edges.append(
                    (
                        -iou,
                        target.annotation_id,
                        -proposal.score,
                        *proposal.box.xyxy,
                        proposal_index,
                        target.annotation_id,
                    )
                )
    matches: dict[int, tuple[int, float]] = {}
    used_proposals: set[int] = set()
    for edge in sorted(edges):
        neg_iou, _, _, _, _, _, _, proposal_index, annotation_id = edge
        if annotation_id not in matches and proposal_index not in used_proposals:
            matches[annotation_id] = (proposal_index, -neg_iou)
            used_proposals.add(proposal_index)
    return matches


def _iou(left: Box, right: Box) -> float:
    x_min = max(left.x, right.x)
    y_min = max(left.y, right.y)
    x_max = min(left.x + left.width, right.x + right.width)
    y_max = min(left.y + left.height, right.y + right.height)
    intersection = max(0.0, x_max - x_min) * max(0.0, y_max - y_min)
    union = left.width * left.height + right.width * right.height - intersection
    return intersection / union


def _flatten_records(
    records: Sequence[ObjectRecord] | Sequence[ImageRegressionRecord],
) -> tuple[tuple[ObjectRecord, ...], int]:
    values = tuple(records)
    if not values:
        return (), 0
    if all(isinstance(value, ObjectRecord) for value in values):
        return tuple(values), 0
    if all(isinstance(value, ImageRegressionRecord) for value in values):
        image_records = tuple(values)
        return (
            tuple(record for image in image_records for record in image.objects),
            sum(len(image.false_positive_proposal_indices) for image in image_records),
        )
    raise ValueError("records must be all ObjectRecord or all ImageRegressionRecord values")


def _records_by_key(records: Iterable[ObjectRecord]) -> dict[tuple[str, int], ObjectRecord]:
    indexed: dict[tuple[str, int], ObjectRecord] = {}
    for record in records:
        key = (record.sample_key, record.annotation_id)
        if key in indexed:
            raise ValueError("object records must have unique sample and annotation identities")
        indexed[key] = record
    return indexed


def _transition_regression_reason(before: ObjectRecord, after: ObjectRecord) -> str | None:
    if not transition_is_allowed(before.outcome, after.outcome):
        if before.outcome is ObjectOutcome.CORRECT:
            return "correct_object_regressed"
        return "forbidden_outcome_transition"
    if before.outcome is ObjectOutcome.CORRECT and (
        before.predicted_sku != before.expected_sku
        or after.predicted_sku != after.expected_sku
        or after.predicted_sku != before.predicted_sku
    ):
        return "correct_sku_changed"
    if before.outcome is ObjectOutcome.MISCLASSIFIED and after.outcome is ObjectOutcome.MISCLASSIFIED:
        if before.predicted_sku != after.predicted_sku:
            return "misclassification_mapping_changed"
    return None
