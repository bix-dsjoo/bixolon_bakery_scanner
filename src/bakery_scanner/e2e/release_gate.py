"""Locked-set release criteria for measured E2E reports."""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import EvaluationReport, ImageMetrics


@dataclass(frozen=True, slots=True)
class ReleaseGateResult:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_release_gate(
    report: EvaluationReport,
    *,
    maximum_warm_p95_ms: float = 500.0,
) -> ReleaseGateResult:
    """Require zero E2E errors at both IoU gates and warm p95 at most 0.5 s."""
    if maximum_warm_p95_ms <= 0.0:
        raise ValueError("maximum_warm_p95_ms must be positive")
    reasons = [
        *_metric_failures("iou_0.50", report.iou50),
        *_metric_failures("iou_0.75", report.iou75),
    ]
    if report.latency.image_count != 299:
        reasons.append(f"latency_image_count={report.latency.image_count}")
    if report.latency.p95_ms > maximum_warm_p95_ms:
        reasons.append(
            f"warm_p95_ms={report.latency.p95_ms:.3f}>{maximum_warm_p95_ms:.3f}"
        )
    return ReleaseGateResult(not reasons, tuple(reasons))


def _metric_failures(label: str, metrics: ImageMetrics) -> tuple[str, ...]:
    fields = (
        "misclassification_count",
        "false_negative_count",
        "duplicate_count",
        "non_target_count",
        "split_error_count",
        "merge_error_count",
        "unknown_count",
    )
    failures = [
        f"{label}:ground_truth_count={metrics.ground_truth_count}"
        if metrics.ground_truth_count != 1409 else None,
        f"{label}:final_count={metrics.final_count}"
        if metrics.final_count != metrics.ground_truth_count else None,
    ]
    failures.extend(
        f"{label}:{field}={getattr(metrics, field)}"
        for field in fields
        if getattr(metrics, field) != 0
    )
    return tuple(value for value in failures if value is not None)
