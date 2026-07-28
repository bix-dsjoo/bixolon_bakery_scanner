from bakery_scanner.e2e.metrics import EvaluationReport, ImageMetrics, LatencySummary
from bakery_scanner.e2e.release_gate import evaluate_release_gate


def _metrics(**changes):
    values = dict(
        ground_truth_count=1409,
        final_count=1409,
        matched_count=1409,
        top1_correct_count=1409,
        top3_correct_count=1409,
        false_positive_count=0,
        false_negative_count=0,
        unknown_count=0,
        misclassification_count=0,
        duplicate_count=0,
        non_target_count=0,
        split_error_count=0,
        merge_error_count=0,
    )
    values.update(changes)
    return ImageMetrics(**values)


def test_release_gate_requires_all_error_classes_and_warm_p95():
    passing = EvaluationReport(
        _metrics(), _metrics(), LatencySummary(299, 300.0, 290.0, 500.0)
    )
    failing = EvaluationReport(
        _metrics(unknown_count=1), _metrics(), LatencySummary(299, 300.0, 290.0, 500.1)
    )

    assert evaluate_release_gate(passing).passed is True
    result = evaluate_release_gate(failing)
    assert result.passed is False
    assert result.reasons == ("iou_0.50:unknown_count=1", "warm_p95_ms=500.100>500.000")
