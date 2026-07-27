"""Shared candidate reranking from full RepViT and DINO evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold

from .full_evidence import FullEvidenceRow


_FEATURE_COUNT = 9


@dataclass(frozen=True, slots=True)
class RankedCandidates:
    sample_id: str
    capture_group: str
    registered: bool
    sku_id: int | None
    sku_ids: tuple[int, ...]
    scores: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.sku_ids or len(self.sku_ids) != len(self.scores):
            raise ValueError("ranked candidates must have aligned scores")
        if tuple(sorted(set(self.sku_ids))) != tuple(sorted(self.sku_ids)):
            raise ValueError("ranked candidate SKU IDs must be unique")


@dataclass(frozen=True, slots=True)
class RankingFold:
    training_capture_groups: frozenset[str]
    held_out_capture_groups: frozenset[str]


@dataclass(frozen=True, slots=True)
class OofRankingResult:
    ranked_rows: tuple[RankedCandidates, ...]
    folds: tuple[RankingFold, ...]


@dataclass(frozen=True, slots=True)
class FusionRanker:
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float

    def __post_init__(self) -> None:
        if any(len(values) != _FEATURE_COUNT for values in (self.feature_mean, self.feature_scale, self.coefficients)):
            raise ValueError("fusion ranker feature shape is invalid")
        if any(not np.isfinite(value) for value in (*self.feature_mean, *self.feature_scale, *self.coefficients, self.intercept)):
            raise ValueError("fusion ranker values must be finite")
        if any(value <= 0.0 for value in self.feature_scale):
            raise ValueError("fusion ranker feature scales must be positive")

    def rank(self, row: FullEvidenceRow) -> RankedCandidates:
        matrix = np.asarray(
            [_candidate_features(row, index) for index in range(len(row.candidate_sku_ids))],
            dtype=np.float64,
        )
        normalized = (matrix - np.asarray(self.feature_mean)) / np.asarray(self.feature_scale)
        logits = normalized @ np.asarray(self.coefficients) + self.intercept
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -700, 700)))
        order = tuple(sorted(range(len(row.candidate_sku_ids)), key=lambda index: (-probabilities[index], row.candidate_sku_ids[index])))
        return RankedCandidates(
            sample_id=row.sample_id,
            capture_group=row.capture_group,
            registered=row.registered,
            sku_id=row.sku_id,
            sku_ids=tuple(row.candidate_sku_ids[index] for index in order),
            scores=tuple(float(probabilities[index]) for index in order),
        )


def fit_ranker(rows: Sequence[FullEvidenceRow], *, seed: int = 20260727) -> FusionRanker:
    matrix, labels = _training_matrix(rows)
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale[scale == 0.0] = 1.0
    model = LogisticRegression(
        C=0.1,
        class_weight="balanced",
        max_iter=2000,
        random_state=seed,
    ).fit((matrix - mean) / scale, labels)
    return FusionRanker(
        feature_mean=tuple(float(value) for value in mean),
        feature_scale=tuple(float(value) for value in scale),
        coefficients=tuple(float(value) for value in model.coef_[0]),
        intercept=float(model.intercept_[0]),
    )


def fit_oof_ranker(
    rows: Sequence[FullEvidenceRow],
    *,
    folds: int = 5,
    seed: int = 20260727,
) -> OofRankingResult:
    checked = tuple(rows)
    if type(folds) is not int or folds < 2:
        raise ValueError("folds must be an integer of at least 2")
    if any(row.role != "development" or not row.registered for row in checked):
        raise ValueError("OOF ranker requires registered development evidence")
    groups = np.asarray([row.capture_group for row in checked], dtype=object)
    labels = np.asarray([row.sku_id for row in checked], dtype=np.int64)
    if np.unique(groups).size < folds:
        raise ValueError("capture_group count must be at least folds")
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    ranked: list[RankedCandidates | None] = [None] * len(checked)
    fold_records: list[RankingFold] = []
    for training_indices, held_out_indices in splitter.split(np.zeros(len(checked)), labels, groups):
        ranker = fit_ranker(tuple(checked[index] for index in training_indices), seed=seed)
        fold_records.append(
            RankingFold(
                frozenset(groups[training_indices].tolist()),
                frozenset(groups[held_out_indices].tolist()),
            )
        )
        for index in held_out_indices:
            ranked[index] = ranker.rank(checked[index])
    if any(value is None for value in ranked):
        raise RuntimeError("OOF ranker did not rank every evidence row")
    return OofRankingResult(tuple(value for value in ranked if value is not None), tuple(fold_records))


def _training_matrix(rows: Sequence[FullEvidenceRow]) -> tuple[np.ndarray, np.ndarray]:
    checked = tuple(rows)
    if not checked:
        raise ValueError("fusion ranker requires at least one evidence row")
    features: list[tuple[float, ...]] = []
    labels: list[int] = []
    for row in checked:
        if not row.registered or row.sku_id is None:
            continue
        for index, candidate_sku_id in enumerate(row.candidate_sku_ids):
            features.append(_candidate_features(row, index))
            labels.append(int(candidate_sku_id == row.sku_id))
    if not features or len(set(labels)) != 2:
        raise ValueError("fusion ranker requires positive and negative candidate examples")
    return np.asarray(features, dtype=np.float64), np.asarray(labels, dtype=np.int64)


def _candidate_features(row: FullEvidenceRow, index: int) -> tuple[float, ...]:
    sku_id = row.candidate_sku_ids[index]
    score_index = sku_id - 1
    repvit = np.asarray(row.repvit_values, dtype=np.float64)
    dino = np.asarray(row.dinov3_values, dtype=np.float64)
    repvit_order = np.sort(repvit)[::-1]
    dino_order = np.sort(dino)[::-1]
    return (
        float(repvit[score_index]),
        float(dino[score_index]),
        float(row.local_values[index]),
        float(repvit_order[0] - repvit_order[1]),
        float(dino_order[0] - dino_order[1]),
        row.repvit_crop_disagreement,
        row.nearest_prototype_distance,
        float(row.local_product_patch_count),
        row.local_product_patch_ratio,
    )
