from bakery_scanner.classification.fusion_evaluation import FusionDecision, evaluate_fusion_decisions


def test_fusion_metrics_enforce_95_coverage_five_percent_error_and_unknown_top3_target():
    decisions = tuple(
        FusionDecision(f"auto-{index}", True, 6, "sku", 6, ())
        for index in range(95)
    ) + tuple(
        FusionDecision(f"unknown-{index}", True, 6, "unknown", None, (6, 5, 19))
        for index in range(5)
    )

    metrics = evaluate_fusion_decisions(decisions)

    assert metrics.correct_top1_coverage == 0.95
    assert metrics.auto_error_rate == 0.0
    assert metrics.unknown_top3_recall == 1.0
    assert metrics.target_passes


def test_fusion_metrics_reject_unknown_top3_recall_below_ninety_percent():
    decisions = tuple(
        FusionDecision(f"auto-{index}", True, 6, "sku", 6, ())
        for index in range(95)
    ) + (
        FusionDecision("unknown-good", True, 6, "unknown", None, (6, 5, 19)),
        FusionDecision("unknown-miss", True, 6, "unknown", None, (5, 19, 4)),
        FusionDecision("unknown-good-2", True, 6, "unknown", None, (6, 5, 19)),
        FusionDecision("unknown-good-3", True, 6, "unknown", None, (6, 5, 19)),
        FusionDecision("unknown-good-4", True, 6, "unknown", None, (6, 5, 19)),
    )

    assert not evaluate_fusion_decisions(decisions).target_passes
