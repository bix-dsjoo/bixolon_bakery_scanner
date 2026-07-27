from bakery_scanner.classification.risk_calibrator import RiskCalibrator, RiskPrediction, select_zero_error_threshold


def test_selector_keeps_90_percent_correct_coverage_without_any_automatic_error():
    predictions = tuple(
        RiskPrediction(f"correct-{index}", True, 6, 6, 0.10 + index * 0.01)
        for index in range(9)
    ) + (RiskPrediction("wrong", True, 6, 5, 0.30),)

    threshold = select_zero_error_threshold(predictions)

    assert threshold == 0.18


def test_selector_returns_none_when_zero_error_cannot_reach_90_percent_coverage():
    predictions = tuple(
        RiskPrediction(f"correct-{index}", True, 6, 6, 0.10 + index * 0.01)
        for index in range(8)
    ) + tuple(
        RiskPrediction(f"wrong-{index}", True, 6, 5, 0.20 + index * 0.01)
        for index in range(2)
    )

    assert select_zero_error_threshold(predictions) is None


def test_common_risk_calibrator_assigns_higher_risk_to_a_lower_rank_score():
    calibrator = RiskCalibrator(
        feature_mean=(0.0, 0.0),
        feature_scale=(1.0, 1.0),
        coefficients=(-4.0, -2.0),
        intercept=3.0,
    )

    safe = calibrator.predict_risk((0.90, 0.50))
    risky = calibrator.predict_risk((0.20, 0.01))

    assert 0.0 <= safe < risky <= 1.0
