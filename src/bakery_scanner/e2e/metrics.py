"""Deterministic E2E quality and latency metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.optimize import linear_sum_assignment

from bakery_scanner.evaluation import match_boxes

from .contracts import FinalObject, SkuGroundTruth


@dataclass(frozen=True, slots=True)
class ImageMetrics:
    ground_truth_count: int
    final_count: int
    matched_count: int
    top1_correct_count: int
    top3_correct_count: int
    false_positive_count: int
    false_negative_count: int
    unknown_count: int
    misclassification_count: int
    duplicate_count: int
    non_target_count: int
    split_error_count: int
    merge_error_count: int

    @property
    def top1_accuracy(self) -> float:
        return self.top1_correct_count / self.ground_truth_count if self.ground_truth_count else 1.0

    @property
    def top3_accuracy(self) -> float:
        return self.top3_correct_count / self.ground_truth_count if self.ground_truth_count else 1.0


@dataclass(frozen=True, slots=True)
class LatencySummary:
    image_count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float


@dataclass(frozen=True, slots=True)
class E2EImageResult:
    image_id: int
    final_objects: tuple[FinalObject, ...]
    e2e_ms: float

    def __post_init__(self) -> None:
        if type(self.image_id) is not int or self.image_id <= 0:
            raise ValueError("image_id must be a positive integer")
        object.__setattr__(self, "final_objects", tuple(self.final_objects))
        if any(not isinstance(item, FinalObject) for item in self.final_objects):
            raise ValueError("final_objects must contain FinalObject values")
        value = float(self.e2e_ms)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("e2e_ms must be finite and non-negative")
        object.__setattr__(self, "e2e_ms", value)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    iou50: ImageMetrics
    iou75: ImageMetrics
    latency: LatencySummary


def evaluate_image(
    ground_truth: tuple[SkuGroundTruth, ...],
    predictions: tuple[FinalObject, ...],
    *,
    iou_threshold: float,
) -> ImageMetrics:
    """Measure final objects against SKU GT with maximum-cardinality IoU matching."""
    if not 0.0 < iou_threshold <= 1.0:
        raise ValueError("iou_threshold must be in (0, 1]")
    box_match = match_boxes(
        tuple(row.box for row in ground_truth),
        tuple(row.box for row in predictions),
        iou_threshold,
    )
    matches = box_match.pairs
    top1 = 0
    top3 = 0
    misclassification = 0
    for ground_truth_index, prediction_index in matches:
        expected = ground_truth[ground_truth_index].sku_id
        prediction = predictions[prediction_index]
        if prediction.sku_id == expected:
            top1 += 1
            top3 += 1
        elif prediction.sku_id is None and expected in prediction.top3:
            top3 += 1
        elif prediction.sku_id is not None:
            misclassification += 1
    return ImageMetrics(
        ground_truth_count=len(ground_truth),
        final_count=len(predictions),
        matched_count=len(matches),
        top1_correct_count=top1,
        top3_correct_count=top3,
        false_positive_count=len(predictions) - len(matches),
        false_negative_count=len(ground_truth) - len(matches),
        unknown_count=sum(prediction.sku_id is None for prediction in predictions),
        misclassification_count=misclassification,
        duplicate_count=len(box_match.duplicates),
        non_target_count=len(box_match.false_positives),
        split_error_count=box_match.split_errors,
        merge_error_count=box_match.merge_errors,
    )


def summarize_latency_ms(latencies_ms: tuple[float, ...]) -> LatencySummary:
    if not latencies_ms:
        raise ValueError("at least one image latency is required")
    values = np.asarray(latencies_ms, dtype=np.float64)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("latencies must be finite non-negative milliseconds")
    return LatencySummary(
        image_count=len(values),
        mean_ms=float(np.mean(values)),
        p50_ms=float(np.percentile(values, 50)),
        p95_ms=float(np.percentile(values, 95)),
    )


def evaluate_run(
    labels_by_image: Mapping[int, tuple[SkuGroundTruth, ...]],
    results: tuple[E2EImageResult, ...],
) -> EvaluationReport:
    """Aggregate exact-image-coverage metrics at the required IoU gates."""
    result_by_image = {result.image_id: result for result in results}
    if len(result_by_image) != len(results):
        raise ValueError("results must contain unique image IDs")
    if set(result_by_image) != set(labels_by_image):
        raise ValueError("results must cover exactly the labeled image IDs")
    return EvaluationReport(
        iou50=_aggregate(
            evaluate_image(labels_by_image[image_id], result_by_image[image_id].final_objects, iou_threshold=0.50)
            for image_id in sorted(result_by_image)
        ),
        iou75=_aggregate(
            evaluate_image(labels_by_image[image_id], result_by_image[image_id].final_objects, iou_threshold=0.75)
            for image_id in sorted(result_by_image)
        ),
        latency=summarize_latency_ms(tuple(result_by_image[image_id].e2e_ms for image_id in sorted(result_by_image))),
    )


def _match(
    ground_truth: tuple[SkuGroundTruth, ...],
    predictions: tuple[FinalObject, ...],
    threshold: float,
) -> tuple[tuple[int, int], ...]:
    if not ground_truth or not predictions:
        return ()
    ground_truth_count = len(ground_truth)
    prediction_count = len(predictions)
    size = ground_truth_count + prediction_count
    costs = np.zeros((size, size), dtype=np.float64)
    valid = np.zeros((ground_truth_count, prediction_count), dtype=bool)
    for ground_truth_index, expected in enumerate(ground_truth):
        for prediction_index, prediction in enumerate(predictions):
            overlap = _iou(expected.box.xyxy, prediction.box.xyxy)
            if overlap >= threshold:
                valid[ground_truth_index, prediction_index] = True
                # A complete match is worth more than the maximum possible IoU
                # difference, so cardinality wins before quality.
                costs[ground_truth_index, prediction_index] = -(2.0 + overlap)
            else:
                costs[ground_truth_index, prediction_index] = 1.0
    rows, columns = linear_sum_assignment(costs)
    return tuple(
        (int(row), int(column))
        for row, column in zip(rows, columns, strict=True)
        if row < ground_truth_count and column < prediction_count and valid[row, column]
    )


def _aggregate(values: object) -> ImageMetrics:
    rows = tuple(values)  # type: ignore[arg-type]
    return ImageMetrics(
        ground_truth_count=sum(row.ground_truth_count for row in rows),
        final_count=sum(row.final_count for row in rows),
        matched_count=sum(row.matched_count for row in rows),
        top1_correct_count=sum(row.top1_correct_count for row in rows),
        top3_correct_count=sum(row.top3_correct_count for row in rows),
        false_positive_count=sum(row.false_positive_count for row in rows),
        false_negative_count=sum(row.false_negative_count for row in rows),
        unknown_count=sum(row.unknown_count for row in rows),
        misclassification_count=sum(row.misclassification_count for row in rows),
        duplicate_count=sum(row.duplicate_count for row in rows),
        non_target_count=sum(row.non_target_count for row in rows),
        split_error_count=sum(row.split_error_count for row in rows),
        merge_error_count=sum(row.merge_error_count for row in rows),
    )


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (first_area + second_area - intersection)
