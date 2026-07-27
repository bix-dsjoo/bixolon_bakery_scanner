"""One shared risk threshold for automatic classifier decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression

from .fusion_ranker import RankedEvidence


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

    def predict_ranked_risk(self, item: RankedEvidence) -> float:
        return self.predict_risk(_ranked_features(item))


def fit_risk_calibrator(
    ranked_rows: Sequence[RankedEvidence],
    *,
    seed: int = 20260727,
) -> RiskCalibrator:
    """Fit one SKU-agnostic error-risk model over ranked evidence rows."""
    checked = tuple(ranked_rows)
    if not checked or any(not item.row.registered or item.row.sku_id is None for item in checked):
        raise ValueError("risk calibration requires registered evidence")
    matrix = np.asarray([_ranked_features(item) for item in checked], dtype=np.float64)
    labels = np.asarray(
        [int(item.ranked.sku_ids[0] != item.row.sku_id) for item in checked], dtype=np.int64
    )
    if len(set(labels.tolist())) != 2:
        raise ValueError("risk calibration requires both correct and wrong ranked rows")
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale[scale == 0.0] = 1.0
    model = LogisticRegression(
        C=0.1,
        class_weight="balanced",
        max_iter=2000,
        random_state=seed,
    ).fit((matrix - mean) / scale, labels)
    return RiskCalibrator(
        tuple(float(value) for value in mean),
        tuple(float(value) for value in scale),
        tuple(float(value) for value in model.coef_[0]),
        float(model.intercept_[0]),
    )


def _ranked_features(item: RankedEvidence) -> tuple[float, ...]:
    ranked = item.ranked
    row = item.row
    top_sku_id = ranked.sku_ids[0]
    top_index = top_sku_id - 1
    local_index = row.candidate_sku_ids.index(top_sku_id)
    margin = ranked.scores[0] - ranked.scores[1] if len(ranked.scores) > 1 else ranked.scores[0]
    return (
        ranked.scores[0],
        margin,
        row.repvit_values[top_index],
        row.dinov3_values[top_index],
        row.local_values[local_index],
        row.repvit_crop_disagreement,
        row.nearest_prototype_distance,
        row.local_product_patch_ratio,
        float(row.local_product_patch_count),
    )


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
        elif self.expected_sku_id is not None or self.predicted_sku_id not in range(1, 21):
            raise ValueError("unregistered risk prediction requires null expected and canonical predicted SKU IDs")
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
    maximum_registered_auto_error_rate: float = 0.05,
) -> float | None:
    """Select one shared threshold with coverage, error-rate, and OOD guarantees."""
    checked = tuple(predictions)
    if not checked:
        raise ValueError("threshold selection requires predictions")
    if not 0.0 < minimum_correct_coverage <= 1.0:
        raise ValueError("minimum_correct_coverage must be in (0, 1]")
    if not 0.0 <= maximum_registered_auto_error_rate < 1.0:
        raise ValueError("maximum_registered_auto_error_rate must be in [0, 1)")
    registered_count = sum(item.registered for item in checked)
    if registered_count == 0:
        raise ValueError("threshold selection requires registered predictions")
    selected: float | None = None
    for threshold in sorted({item.risk for item in checked}):
        accepted = tuple(item for item in checked if item.risk <= threshold)
        if any(not item.registered for item in accepted):
            continue
        automatic_errors = sum(not item.correct for item in accepted)
        if accepted and automatic_errors / len(accepted) >= maximum_registered_auto_error_rate:
            continue
        if sum(item.correct for item in accepted) / registered_count >= minimum_correct_coverage:
            selected = threshold
    return selected
