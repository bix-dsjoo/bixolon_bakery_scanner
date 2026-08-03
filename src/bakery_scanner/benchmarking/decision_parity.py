"""Fail-closed serial-versus-batch classifier decision comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from bakery_scanner.classification.contracts import ClassificationDecision


_PARITY_FIELDS = (
    "decision",
    "sku_id",
    "confidence",
    "box",
    "decision_path",
    "top3",
    "provenance",
    "unknown_reason",
)


@dataclass(frozen=True, slots=True)
class DecisionMismatch:
    index: int
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionParityReceipt:
    reference_count: int
    candidate_count: int
    mismatches: tuple[DecisionMismatch, ...]

    @property
    def passed(self) -> bool:
        return self.reference_count == self.candidate_count and not self.mismatches


def compare_decisions(
    reference: Sequence[ClassificationDecision],
    candidate: Sequence[ClassificationDecision],
) -> DecisionParityReceipt:
    """Compare immutable decisions while deliberately excluding timings only."""
    mismatches: list[DecisionMismatch] = []
    for index in range(max(len(reference), len(candidate))):
        if index >= len(reference):
            mismatches.append(DecisionMismatch(index, ("missing_reference",)))
            continue
        if index >= len(candidate):
            mismatches.append(DecisionMismatch(index, ("missing_candidate",)))
            continue
        fields = tuple(
            field
            for field in _PARITY_FIELDS
            if getattr(reference[index], field) != getattr(candidate[index], field)
        )
        if fields:
            mismatches.append(DecisionMismatch(index, fields))
    return DecisionParityReceipt(
        reference_count=len(reference),
        candidate_count=len(candidate),
        mismatches=tuple(mismatches),
    )
