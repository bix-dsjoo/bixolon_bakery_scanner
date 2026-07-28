"""Canonical persisted reports for SKU-aware E2E evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from .metrics import EvaluationReport, ImageMetrics


def evaluation_payload(report: EvaluationReport, *, scope: str) -> dict[str, object]:
    if scope != "grouped_oof_development_only":
        raise ValueError("only grouped_oof_development_only evaluation scope is supported")
    return {
        "schema_version": 1,
        "scope": scope,
        "metrics": {
            "iou_0.50": _metrics_payload(report.iou50),
            "iou_0.75": _metrics_payload(report.iou75),
        },
        "latency_ms": {
            "image_count": report.latency.image_count,
            "mean": report.latency.mean_ms,
            "p50": report.latency.p50_ms,
            "p95": report.latency.p95_ms,
        },
    }


def write_evaluation_report(output: Path, payload: dict[str, object]) -> Path:
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to replace existing evaluation report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(json.dumps(payload, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return output


def _metrics_payload(metrics: ImageMetrics) -> dict[str, object]:
    return {
        "final_count": metrics.final_count,
        "false_negative_count": metrics.false_negative_count,
        "false_positive_count": metrics.false_positive_count,
        "ground_truth_count": metrics.ground_truth_count,
        "duplicate_count": metrics.duplicate_count,
        "merge_error_count": metrics.merge_error_count,
        "misclassification_count": metrics.misclassification_count,
        "non_target_count": metrics.non_target_count,
        "matched_count": metrics.matched_count,
        "split_error_count": metrics.split_error_count,
        "top1_accuracy": metrics.top1_accuracy,
        "top1_correct_count": metrics.top1_correct_count,
        "top3_accuracy": metrics.top3_accuracy,
        "top3_correct_count": metrics.top3_correct_count,
        "unknown_count": metrics.unknown_count,
    }
