"""Exact-match evaluation for one-class bread boxes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.optimize import linear_sum_assignment

from bakery_scanner.contracts import Box


IOU_THRESHOLDS = (0.50, 0.75, 0.90)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """One-to-one box matches for a single image at one IoU threshold."""

    iou_threshold: float
    pairs: tuple[tuple[int, int], ...]
    misses: tuple[int, ...]
    false_positives: tuple[int, ...]
    duplicates: tuple[int, ...]
    split_errors: int
    merge_errors: int


@dataclass(frozen=True, slots=True)
class ScanMetrics:
    scan_count: int
    exact_scans: int
    misses: int
    false_positives: int
    duplicates: int
    split_errors: int
    merge_errors: int

    @property
    def sem_exact(self) -> float:
        return self.exact_scans / self.scan_count if self.scan_count else 0.0


@dataclass(frozen=True, slots=True)
class EvaluationReport(ScanMetrics):
    sem_exact_75: float
    sem_exact_90: float
    scenarios: Mapping[str, ScanMetrics]


def match_boxes(
    gt: tuple[Box, ...], predictions: tuple[Box, ...], iou_threshold: float
) -> MatchResult:
    """Return a maximum-cardinality valid bipartite matching.

    Dummy rows and columns permit unmatched boxes.  Every valid edge has a
    lower cost than every dummy edge, so assignment maximizes valid matches
    before using IoU as a deterministic tie-breaker.
    """
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold must be in (0, 1]")
    ious = _iou_matrix(gt, predictions)
    valid = ious >= iou_threshold
    gt_count, prediction_count = len(gt), len(predictions)
    size = gt_count + prediction_count
    if size == 0:
        return MatchResult(iou_threshold, (), (), (), (), 0, 0)
    cost = np.zeros((size, size), dtype=np.float64)
    # Valid matches are preferred over all dummy and invalid assignments.
    # A small IoU term makes equivalent-cardinality assignments stable.
    if gt_count and prediction_count:
        cost[:gt_count, :prediction_count] = np.where(valid, -1.0 - ious * 1e-6, 0.0)
    rows, columns = linear_sum_assignment(cost)
    pairs = tuple(
        sorted(
            (int(row), int(column))
            for row, column in zip(rows, columns, strict=True)
            if row < gt_count and column < prediction_count and valid[row, column]
        )
    )
    matched_gt = {row for row, _ in pairs}
    matched_predictions = {column for _, column in pairs}
    misses = tuple(index for index in range(gt_count) if index not in matched_gt)
    unmatched_predictions = tuple(index for index in range(prediction_count) if index not in matched_predictions)
    duplicates = tuple(index for index in unmatched_predictions if gt_count and bool(valid[:, index].any()))
    false_positives = tuple(index for index in unmatched_predictions if index not in set(duplicates))
    split_errors = sum(int(valid[row, :].sum()) > 1 for row in range(gt_count))
    merge_errors = sum(int(valid[:, column].sum()) > 1 for column in range(prediction_count))
    return MatchResult(iou_threshold, pairs, misses, false_positives, duplicates, split_errors, merge_errors)


def evaluate_scans(
    gt: Mapping[int, tuple[Box, ...]],
    predictions: Mapping[int, tuple[Box, ...]],
    scenarios: Mapping[int, frozenset[str]],
) -> EvaluationReport:
    """Evaluate all scan IDs at 0.50, 0.75, and 0.90 without silent omission."""
    scan_ids = tuple(sorted(set(gt) | set(predictions)))
    if set(scenarios) != set(scan_ids):
        raise ValueError("scenarios must be supplied for exactly every evaluated scan")
    matches = {
        threshold: {
            scan_id: match_boxes(tuple(gt.get(scan_id, ())), tuple(predictions.get(scan_id, ())), threshold)
            for scan_id in scan_ids
        }
        for threshold in IOU_THRESHOLDS
    }
    overall = _metrics(matches[0.50])
    scenario_metrics: dict[str, ScanMetrics] = {}
    for scenario in sorted({name for labels in scenarios.values() for name in labels}):
        subset = {scan_id: result for scan_id, result in matches[0.50].items() if scenario in scenarios[scan_id]}
        scenario_metrics[scenario] = _metrics(subset)
    return EvaluationReport(
        scan_count=overall.scan_count,
        exact_scans=overall.exact_scans,
        misses=overall.misses,
        false_positives=overall.false_positives,
        duplicates=overall.duplicates,
        split_errors=overall.split_errors,
        merge_errors=overall.merge_errors,
        sem_exact_75=_metrics(matches[0.75]).sem_exact,
        sem_exact_90=_metrics(matches[0.90]).sem_exact,
        scenarios=scenario_metrics,
    )


def _metrics(results: Mapping[int, MatchResult]) -> ScanMetrics:
    values = tuple(results.values())
    return ScanMetrics(
        scan_count=len(values),
        exact_scans=sum(not (row.misses or row.false_positives or row.duplicates) for row in values),
        misses=sum(len(row.misses) for row in values),
        false_positives=sum(len(row.false_positives) for row in values),
        duplicates=sum(len(row.duplicates) for row in values),
        split_errors=sum(row.split_errors for row in values),
        merge_errors=sum(row.merge_errors for row in values),
    )


def _iou_matrix(gt: tuple[Box, ...], predictions: tuple[Box, ...]) -> np.ndarray:
    matrix = np.zeros((len(gt), len(predictions)), dtype=np.float64)
    for gt_index, expected in enumerate(gt):
        for prediction_index, actual in enumerate(predictions):
            left = max(expected.x, actual.x)
            top = max(expected.y, actual.y)
            right = min(expected.x + expected.width, actual.x + actual.width)
            bottom = min(expected.y + expected.height, actual.y + actual.height)
            intersection = max(0.0, right - left) * max(0.0, bottom - top)
            union = expected.width * expected.height + actual.width * actual.height - intersection
            matrix[gt_index, prediction_index] = intersection / union if union else 0.0
    return matrix
