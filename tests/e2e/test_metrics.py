import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject, SkuGroundTruth
from bakery_scanner.e2e.metrics import E2EImageResult, evaluate_run, evaluate_image, summarize_latency_ms


def test_evaluation_reports_top1_fp_unknown_and_top3_at_iou_threshold():
    ground_truth = (
        SkuGroundTruth(1, Box(0, 0, 10, 10), 1),
        SkuGroundTruth(1, Box(20, 0, 10, 10), 2),
    )
    predictions = (
        FinalObject(Box(0, 0, 10, 10), 1, 0.9, "repvit_direct", ()),
        FinalObject(Box(20, 0, 10, 10), None, 0.6, "unknown_top3", (2, 5, 8)),
        FinalObject(Box(40, 0, 10, 10), 3, 0.8, "repvit_direct", ()),
    )

    metrics = evaluate_image(ground_truth, predictions, iou_threshold=0.5)

    assert metrics.ground_truth_count == 2
    assert metrics.final_count == 3
    assert metrics.matched_count == 2
    assert metrics.top1_correct_count == 1
    assert metrics.false_positive_count == 1
    assert metrics.unknown_count == 1
    assert metrics.top3_correct_count == 2
    assert metrics.top1_accuracy == pytest.approx(0.5)
    assert metrics.top3_accuracy == pytest.approx(1.0)


def test_latency_summary_returns_mean_and_p95():
    latency = summarize_latency_ms((10.0, 20.0, 30.0, 40.0))

    assert latency.image_count == 4
    assert latency.mean_ms == pytest.approx(25.0)
    assert latency.p95_ms == pytest.approx(38.5)


def test_run_evaluation_aggregates_both_required_iou_gates():
    labels = {
        1: (SkuGroundTruth(1, Box(0, 0, 10, 10), 1),),
        2: (SkuGroundTruth(2, Box(0, 0, 10, 10), 2),),
    }
    results = (
        E2EImageResult(1, (FinalObject(Box(0, 0, 10, 10), 1, 0.9, "repvit_direct", ()),), 120.0),
        E2EImageResult(2, (FinalObject(Box(0, 0, 6, 10), None, 0.6, "unknown_top3", (2, 5, 8)),), 180.0),
    )

    report = evaluate_run(labels, results)

    assert report.iou50.top1_correct_count == 1
    assert report.iou50.unknown_count == 1
    assert report.iou50.top3_correct_count == 2
    assert report.iou75.matched_count == 1
    assert report.iou75.false_negative_count == 1
    assert report.latency.mean_ms == pytest.approx(150.0)
