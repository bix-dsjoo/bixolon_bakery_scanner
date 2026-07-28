from bakery_scanner.classification.full_evidence import FullEvidenceRow
from bakery_scanner.classification.fusion_ranker import RankedCandidates, RankedEvidence
from bakery_scanner.classification.risk_calibrator import RiskCalibrator, RiskPrediction, fit_risk_calibrator, select_zero_error_threshold


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


def test_selector_treats_an_accepted_unregistered_product_as_an_automatic_error():
    predictions = tuple(
        RiskPrediction(f"correct-{index}", True, 6, 6, 0.10 + index * 0.01)
        for index in range(9)
    ) + (RiskPrediction("unregistered", False, None, 6, 0.15),)

    assert select_zero_error_threshold(predictions) is None


def test_selector_allows_one_registered_error_only_when_it_is_strictly_below_five_percent():
    predictions = tuple(
        RiskPrediction(f"correct-{index}", True, 6, 6, 0.10 + index * 0.01)
        for index in range(20)
    ) + (RiskPrediction("wrong", True, 6, 5, 0.31),)

    assert select_zero_error_threshold(predictions) == 0.31


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


def test_fitted_risk_calibrator_scores_ranked_evidence_without_sku_specific_rules():
    def item(sample_id: str, predicted_sku_id: int) -> RankedEvidence:
        row = FullEvidenceRow(
            sample_id=sample_id, capture_group=sample_id, registered=True, sku_id=1,
            role="development", image_sha256=f"{int(sample_id[-1]):064x}",
            repvit_values=(0.7, 0.2) + (0.1 / 18,) * 18,
            dinov3_values=(0.8, 0.5) + (0.0,) * 18,
            candidate_sku_ids=(1, 2), local_values=(0.9, 0.2),
            repvit_crop_disagreement=0.02, nearest_prototype_distance=0.1,
            local_product_patch_count=420, local_product_patch_ratio=0.71,
            repvit_checkpoint_sha256="1" * 64, repvit_manifest_sha256="2" * 64,
            repvit_prototype_sha256="3" * 64, dinov3_weights_sha256="4" * 64,
            dinov3_support_sha256="5" * 64, dinov3_local_bank_sha256="6" * 64,
            preprocess_sha256="7" * 64,
        )
        ordered = (predicted_sku_id, 2 if predicted_sku_id == 1 else 1)
        return RankedEvidence(row, RankedCandidates(sample_id, sample_id, True, 1, ordered, (0.9, 0.1)))

    calibrator = fit_risk_calibrator((item("sample-1", 1), item("sample-2", 1), item("sample-3", 2)), seed=7)

    assert 0.0 <= calibrator.predict_ranked_risk(item("sample-4", 1)) <= 1.0
