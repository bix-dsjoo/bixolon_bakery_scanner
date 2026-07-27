"""One shared risk threshold for automatic classifier decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class RiskCalibrator:
    """A shared logistic error-risk model; it contains no SKU-specific rule."""

    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float

    def __post_init__(self) -> None:
        if not self.feature_mean or not (
            len(self.feature_mean) == len(self.feature_scale) == len(self.coefficients)
        ):
            raise ValueError("risk calibrator feature shape is invalid")
        values = (*self.feature_mean, *self.feature_scale, *self.coefficients, self.intercept)
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) for value in values):
            raise ValueError("risk calibrator values must be finite")
        if any(float(value) <= 0.0 for value in self.feature_scale):
            raise ValueError("risk calibrator feature scales must be positive")

    def predict_risk(self, features: Sequence[float]) -> float:
        if len(features) != len(self.feature_mean) or any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) for value in features):
            raise ValueError("risk features are invalid")
        normalized = (np.asarray(features, dtype=np.float64) - np.asarray(self.feature_mean)) / np.asarray(self.feature_scale)
        logit = float(normalized @ np.asarray(self.coefficients) + self.intercept)
        return float(1.0 / (1.0 + math.exp(-max(-700.0, min(700.0, logit)))))


@dataclass(frozen=True, slots=True)
class RiskPrediction:
    sample_id: str
    registered: bool
    expected_sku_id: int | None
    predicted_sku_id: int | None
    risk: float

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        if type(self.registered) is not bool:
            raise ValueError("registered must be a boolean")
        if self.registered:
            if self.expected_sku_id not in range(1, 21) or self.predicted_sku_id not in range(1, 21):
                raise ValueError("registered risk prediction requires canonical SKU IDs")
        if not isinstance(self.risk, (int, float)) or isinstance(self.risk, bool) or not math.isfinite(float(self.risk)) or not 0.0 <= float(self.risk) <= 1.0:
            raise ValueError("risk must be a finite value between 0 and 1")
        object.__setattr__(self, "risk", float(self.risk))

    @property
    def correct(self) -> bool:
        return self.registered and self.expected_sku_id == self.predicted_sku_id


def select_zero_error_threshold(
    predictions: Sequence[RiskPrediction],
    *,
    minimum_correct_coverage: float = 0.90,
) -> float | None:
    """Select the most permissive shared risk threshold meeting 90%/0-error."""
    checked = tuple(predictions)
    if not checked or any(not item.registered for item in checked):
        raise ValueError("threshold selection requires registered predictions")
    if not 0.0 < minimum_correct_coverage <= 1.0:
        raise ValueError("minimum_correct_coverage must be in (0, 1]")
    denominator = len(checked)
    selected: float | None = None
    for threshold in sorted({item.risk for item in checked}):
        accepted = tuple(item for item in checked if item.risk <= threshold)
        if any(not item.correct for item in accepted):
            continue
        if sum(item.correct for item in accepted) / denominator >= minimum_correct_coverage:
            selected = threshold
    return selected
