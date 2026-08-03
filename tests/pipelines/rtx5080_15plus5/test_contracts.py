from __future__ import annotations

import json

import pytest

from bakery_scanner.pipelines.rtx5080_15plus5.contracts import (
    CandidateConfidence,
    DecisionPath,
    FinalObject,
    ObjectLocation,
    ObjectProvenance,
    RetakeReason,
    ScanProvenance,
    ScanResult,
    ScanState,
    SkuCandidate,
    StageTimings,
)


_HASH = "a" * 64


def _registered_object(sku_id: int, *, order: int = 1) -> FinalObject:
    return FinalObject(
        object_id=f"scan-1:{order:03d}",
        sku_id=sku_id,
        sku_name=f"SKU {sku_id}",
        decision_path=DecisionPath.DIRECT,
        location=ObjectLocation((1.0, 2.0, 3.0, 4.0), (0.1, 0.2), order),
        confidence=CandidateConfidence(0.9, 0.8, None),
        top3=(
            SkuCandidate(1, sku_id, f"SKU {sku_id}", 0.8),
            SkuCandidate(2, 2, "SKU 2", 0.1),
            SkuCandidate(3, 3, "SKU 3", 0.05),
        ),
        provenance=_provenance(),
    )


def _unknown_object(top3_skus: tuple[int, int, int]) -> FinalObject:
    return FinalObject(
        object_id="scan-1:002",
        sku_id=None,
        sku_name="Unknown",
        decision_path=DecisionPath.UNKNOWN,
        location=ObjectLocation((5.0, 6.0, 9.0, 10.0), (0.5, 0.6), 2),
        confidence=CandidateConfidence(0.9, None, 0.1),
        top3=tuple(
            SkuCandidate(rank, sku_id, f"SKU {sku_id}", score)
            for rank, (sku_id, score) in enumerate(zip(top3_skus, (0.6, 0.3, 0.1)), 1)
        ),
        provenance=_provenance(),
    )


def _provenance() -> ObjectProvenance:
    return ObjectProvenance(
        detector_artifact_id="detector", detector_sha256=_HASH,
        repvit_artifact_id="repvit", repvit_sha256=_HASH,
        dinov3_artifact_id="dinov3", dinov3_sha256=_HASH,
        fusion_policy_id="policy", fusion_policy_sha256=_HASH,
        runtime_profile_id="rtx5080_trt_fp16_static7_v1",
    )


def _accepted_scan(objects: tuple[FinalObject, ...]) -> ScanResult:
    return ScanResult(
        scan_id="scan-1", retake_chain_id="chain-1", state=ScanState.ACCEPTED,
        objects=objects, reasons=(), timings_ms=StageTimings(*(1.0,) * 9),
        provenance=ScanProvenance("rtx5080_15plus5_single_frame_v1", "rtx5080_trt_fp16_static7_v1", _HASH, {"detector": _HASH}),
        manual_catalog_required=False,
    )


def test_unknown_is_excluded_from_sku_totals() -> None:
    result = _accepted_scan((_registered_object(15), _unknown_object((4, 6, 9))))

    assert result.object_total == 2
    assert result.registered_object_total == 1
    assert result.unknown_total == 1
    assert result.sku_totals == {15: 1}


def test_needs_retake_forbids_partial_objects() -> None:
    with pytest.raises(ValueError, match="must not contain final objects"):
        ScanResult.needs_retake(
            scan_id="scan-1", retake_chain_id="chain-1", attempt=1,
            reasons=(RetakeReason.UNCOVERED_FOREGROUND,), problem_regions=(),
            objects=(_registered_object(1),), timings_ms=StageTimings(*(1.0,) * 9),
            provenance=ScanProvenance("rtx5080_15plus5_single_frame_v1", "rtx5080_trt_fp16_static7_v1", _HASH, {"detector": _HASH}),
        )


def test_unknown_requires_exact_ranked_top3() -> None:
    with pytest.raises(ValueError, match="exact ranked Top3"):
        _unknown_object((4, 4, 9))


def test_json_is_sorted_compact_and_rejects_non_finite_timings() -> None:
    result = _accepted_scan((_registered_object(15),))
    encoded = result.to_json_bytes()

    assert encoded == json.dumps(json.loads(encoded), allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with pytest.raises(ValueError, match="finite"):
        ScanResult(
            scan_id="scan-1", retake_chain_id="chain-1", state=ScanState.ACCEPTED,
            objects=(), reasons=(), timings_ms=StageTimings(float("nan"), *(1.0,) * 8),
            provenance=result.provenance, manual_catalog_required=False,
        )


def test_scan_result_rejects_mutable_result_collections() -> None:
    result = _accepted_scan(())

    with pytest.raises(ValueError, match="reasons must be an immutable tuple"):
        ScanResult(
            scan_id=result.scan_id, retake_chain_id=result.retake_chain_id,
            state=result.state, objects=result.objects, reasons=[],
            timings_ms=result.timings_ms, provenance=result.provenance,
            manual_catalog_required=False,
        )
