"""Fixed-threshold metrics for the common fusion classifier policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


@dataclass(frozen=True, slots=True)
class FusionDecision:
    sample_id: str
    registered: bool
    expected_sku_id: int | None
    decision: Literal["sku", "unknown"]
    predicted_sku_id: int | None
    top3: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        if type(self.registered) is not bool:
            raise ValueError("registered must be a boolean")
        if self.registered and self.expected_sku_id not in range(1, 21):
            raise ValueError("registered decision requires expected SKU")
        if self.decision == "sku":
            if self.predicted_sku_id not in range(1, 21) or self.top3:
                raise ValueError("SKU decision contract is invalid")
        elif self.decision == "unknown":
            if self.predicted_sku_id is not None or len(self.top3) != 3 or len(set(self.top3)) != 3 or any(sku_id not in range(1, 21) for sku_id in self.top3):
                raise ValueError("Unknown decision contract is invalid")
        else:
            raise ValueError("decision must be sku or unknown")


@dataclass(frozen=True, slots=True)
class FusionMetrics:
    registered_count: int
    auto_count: int
    auto_correct: int
    auto_errors: int
    correct_top1_coverage: float
    auto_error_rate: float
    unknown_count: int
    unknown_top3_correct: int
    unknown_top3_recall: float

    @property
    def target_passes(self) -> bool:
        return (
            self.correct_top1_coverage >= 0.95
            and self.auto_error_rate < 0.05
            and self.unknown_top3_recall >= 0.90
        )


def evaluate_fusion_decisions(decisions: Sequence[FusionDecision]) -> FusionMetrics:
    checked = tuple(decisions)
    if not checked or any(not item.registered for item in checked):
        raise ValueError("fusion evaluation requires registered decisions")
    sample_ids = [item.sample_id for item in checked]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("fusion evaluation has duplicate sample IDs")
    automatic = tuple(item for item in checked if item.decision == "sku")
    unknown = tuple(item for item in checked if item.decision == "unknown")
    auto_correct = sum(item.predicted_sku_id == item.expected_sku_id for item in automatic)
    auto_errors = len(automatic) - auto_correct
    unknown_top3_correct = sum(item.expected_sku_id in item.top3 for item in unknown)
    return FusionMetrics(
        registered_count=len(checked),
        auto_count=len(automatic),
        auto_correct=auto_correct,
        auto_errors=auto_errors,
        correct_top1_coverage=auto_correct / len(checked),
        auto_error_rate=auto_errors / len(automatic) if automatic else 0.0,
        unknown_count=len(unknown),
        unknown_top3_correct=unknown_top3_correct,
        # A threshold that emits no Unknown decisions cannot violate the
        # conditional Top-3 contract.
        unknown_top3_recall=unknown_top3_correct / len(unknown) if unknown else 1.0,
    )
