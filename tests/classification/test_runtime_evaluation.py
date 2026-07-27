from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    StageTimings,
)
from bakery_scanner.contracts import Box
from scripts.evaluate_classifier_runtime import build_parser, evaluated_row_from_decision


def test_runtime_sku_decision_preserves_exact_runtime_prediction():
    decision = ClassificationDecision(
        decision="sku",
        sku_id=6,
        confidence=0.8,
        box=Box(0, 0, 10, 10),
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=ModelProvenance(
            repvit_artifact_id="repvit",
            repvit_sha256="0" * 64,
            dinov3_artifact_id="dino",
            dinov3_sha256="0" * 64,
            dinov3_support_sha256="0" * 64,
            calibration_id="test",
            calibration_sha256="0" * 64,
        ),
        timings=StageTimings(0.0, 0.0, 0.0),
    )

    result = evaluated_row_from_decision(
        sample_id="sample", registered=True, sku_id=6, decision=decision
    )

    assert result.decision == "sku"
    assert result.predicted_sku_id == 6
    assert result.top3 == ()


def test_runtime_evaluator_accepts_an_exploratory_calibration_override():
    args = build_parser().parse_args(
        [
            "--config", "config.yaml",
            "--manifest", "manifest.jsonl",
            "--dino-source-manifest", "sources.json",
            "--calibration", "policy.json",
            "--output", "report.json",
        ]
    )

    assert args.calibration.name == "policy.json"
