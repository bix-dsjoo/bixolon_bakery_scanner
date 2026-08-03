from dataclasses import replace

from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    SkuCandidate,
    StageTimings,
)
from bakery_scanner.benchmarking.decision_parity import compare_decisions
from bakery_scanner.contracts import Box


def test_compare_decisions_rejects_top3_order_change():
    reference = (_decision(top3=(_candidate(1, 1), _candidate(2, 2), _candidate(3, 3))),)
    candidate = (_decision(top3=(_candidate(2, 1), _candidate(1, 2), _candidate(3, 3))),)

    receipt = compare_decisions(reference, candidate)

    assert receipt.passed is False
    assert receipt.mismatches[0].fields == ("top3",)


def test_compare_decisions_ignores_timing_schedule_only():
    reference = (_decision(),)
    candidate = (
        replace(
            reference[0],
            timings=StageTimings(repvit_ms=2.0, dinov3_ms=3.0, total_ms=8.0),
        ),
    )

    receipt = compare_decisions(reference, candidate)

    assert receipt.passed is True
    assert receipt.mismatches == ()


def test_compare_decisions_fails_closed_for_every_non_timing_field_and_count():
    reference = (_decision(),)
    changed = _decision()
    candidate = (
        replace(
            changed,
            confidence=0.61,
            box=Box(11, 10, 20, 15),
            provenance=replace(changed.provenance, failure_code="dino_inference_failed"),
            unknown_reason="dino_low_confidence",
        ),
        _decision(),
    )

    receipt = compare_decisions(reference, candidate)

    assert receipt.passed is False
    assert receipt.reference_count == 1
    assert receipt.candidate_count == 2
    assert receipt.mismatches[0].fields == (
        "confidence",
        "box",
        "provenance",
        "unknown_reason",
    )
    assert receipt.mismatches[1].fields == ("missing_reference",)


def _decision(*, top3: tuple[SkuCandidate, ...] | None = None) -> ClassificationDecision:
    candidates = top3 or (_candidate(1, 1), _candidate(2, 2), _candidate(3, 3))
    return ClassificationDecision(
        decision="unknown",
        sku_id=None,
        confidence=0.5,
        box=Box(10, 10, 20, 15),
        decision_path=DecisionPath.UNKNOWN_TOP3,
        top3=candidates,
        provenance=ModelProvenance(
            repvit_artifact_id="repvit_m1_15plus5_v1",
            repvit_sha256="1" * 64,
            dinov3_artifact_id="dinov3_vits16_15plus5_v1",
            dinov3_sha256="2" * 64,
            dinov3_support_sha256="3" * 64,
            calibration_id="policy_v1",
            calibration_sha256="4" * 64,
        ),
        timings=StageTimings(repvit_ms=1.0, dinov3_ms=2.0, total_ms=4.0),
        unknown_reason="cross_model_disagreement",
    )


def _candidate(sku_id: int, rank: int) -> SkuCandidate:
    return SkuCandidate(rank=rank, sku_id=sku_id, score=0.5 - sku_id / 100)
