from __future__ import annotations

import json

import pytest

from bakery_scanner.pipelines.rtx5080_15plus5.contracts import (
    CANONICAL_SKUS,
    CandidateConfidence,
    CanonicalFrame,
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
_FRAME = CanonicalFrame(width=100, height=100)


def _location(order: int) -> ObjectLocation:
    x_min, y_min = float(order * 10), float(order * 10)
    x_max, y_max = x_min + 8.0, y_min + 6.0
    return ObjectLocation(
        (x_min, y_min, x_max, y_max),
        ((x_min + x_max) / 2 / _FRAME.width, (y_min + y_max) / 2 / _FRAME.height),
        order,
    )


def _top3(sku_id: int) -> tuple[SkuCandidate, ...]:
    sku_ids = (sku_id,) + tuple(candidate for candidate in CANONICAL_SKUS if candidate != sku_id)[:2]
    return tuple(
        SkuCandidate(rank, candidate, CANONICAL_SKUS[candidate], score)
        for rank, (candidate, score) in enumerate(zip(sku_ids, (0.8, 0.1, 0.05)), 1)
    )


def _registered_object(sku_id: int, *, order: int = 1) -> FinalObject:
    return FinalObject(
        object_id=f"scan-1:{order:03d}", sku_id=sku_id, sku_name=CANONICAL_SKUS[sku_id],
        decision_path=DecisionPath.DIRECT, location=_location(order),
        confidence=CandidateConfidence(0.9, 0.8, None), top3=_top3(sku_id),
        provenance=_provenance(),
    )


def _unknown_object(top3_skus: tuple[int, int, int], *, order: int = 2) -> FinalObject:
    return FinalObject(
        object_id=f"scan-1:{order:03d}", sku_id=None, sku_name="Unknown",
        decision_path=DecisionPath.UNKNOWN, location=_location(order),
        confidence=CandidateConfidence(0.9, None, 0.1),
        top3=tuple(
            SkuCandidate(rank, sku_id, CANONICAL_SKUS[sku_id], score)
            for rank, (sku_id, score) in enumerate(zip(top3_skus, (0.6, 0.3, 0.1)), 1)
        ), provenance=_provenance(),
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
        canonical_frame=_FRAME, manual_catalog_required=False,
    )


def test_unknown_is_excluded_from_sku_totals() -> None:
    result = _accepted_scan((_registered_object(15), _unknown_object((4, 6, 9)), _registered_object(1, order=3)))

    assert result.object_total == 3
    assert result.registered_object_total == 2
    assert result.unknown_total == 1
    assert result.sku_totals == {1: 1, 15: 1}


def test_needs_retake_forbids_partial_objects() -> None:
    with pytest.raises(ValueError, match="must not contain final objects"):
        ScanResult.needs_retake(
            scan_id="scan-1", retake_chain_id="chain-1", attempt=1,
            reasons=(RetakeReason.UNCOVERED_FOREGROUND,), problem_regions=(),
            objects=(_registered_object(1),), timings_ms=StageTimings(*(1.0,) * 9),
            provenance=ScanProvenance("rtx5080_15plus5_single_frame_v1", "rtx5080_trt_fp16_static7_v1", _HASH, {"detector": _HASH}),
            canonical_frame=_FRAME,
        )


@pytest.mark.parametrize("sku_id,sku_name", [(21, "Not a SKU"), (999, "Not a SKU"), (15, "Croffle")])
def test_sku_candidates_reject_unknown_or_mismatched_catalog_identity(sku_id: int, sku_name: str) -> None:
    with pytest.raises(ValueError, match="canonical SKU"):
        SkuCandidate(1, sku_id, sku_name, 0.9)


def test_accepted_object_rejects_mismatched_catalog_name() -> None:
    with pytest.raises(ValueError, match="canonical SKU"):
        FinalObject(
            object_id="scan-1:001", sku_id=15, sku_name="Croffle", decision_path=DecisionPath.DIRECT,
            location=_location(1), confidence=CandidateConfidence(.9, .8, None), top3=_top3(15), provenance=_provenance(),
        )


def test_accepted_object_rejects_noncanonical_sku_id() -> None:
    with pytest.raises(ValueError, match="canonical SKU"):
        FinalObject(
            object_id="scan-1:001", sku_id=999, sku_name="Not a SKU", decision_path=DecisionPath.DIRECT,
            location=_location(1), confidence=CandidateConfidence(.9, .8, None), top3=_top3(1), provenance=_provenance(),
        )


@pytest.mark.parametrize("count", [1, 2, 8])
def test_accepted_scan_allows_every_nonempty_object_count(count: int) -> None:
    objects = tuple(_registered_object((index % 20) + 1, order=index + 1) for index in range(count))
    assert _accepted_scan(objects).object_total == count


def test_accepted_scan_rejects_empty_objects_and_zero_target_returns_retake() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _accepted_scan(())
    result = ScanResult.needs_retake(
        scan_id="scan-1", retake_chain_id="chain-1", attempt=1,
        reasons=(RetakeReason.NO_TARGET_DETECTED,), problem_regions=(), timings_ms=StageTimings(*(1.0,) * 9),
        provenance=ScanProvenance("rtx5080_15plus5_single_frame_v1", "rtx5080_trt_fp16_static7_v1", _HASH, {"detector": _HASH}),
        canonical_frame=_FRAME,
    )
    assert result.state is ScanState.NEEDS_RETAKE
    assert result.objects == ()
    assert result.reasons == (RetakeReason.NO_TARGET_DETECTED,)


def test_scan_rejects_out_of_bounds_box_and_inconsistent_normalized_center() -> None:
    out_of_bounds = FinalObject(
        object_id="scan-1:001", sku_id=1, sku_name=CANONICAL_SKUS[1], decision_path=DecisionPath.DIRECT,
        location=ObjectLocation((10.0, 10.0, 101.0, 20.0), (0.555, 0.15), 1), confidence=CandidateConfidence(.9, .8, None), top3=_top3(1), provenance=_provenance(),
    )
    inconsistent_center = FinalObject(
        object_id="scan-1:002", sku_id=2, sku_name=CANONICAL_SKUS[2], decision_path=DecisionPath.DIRECT,
        location=ObjectLocation((20.0, 20.0, 28.0, 26.0), (0.99, 0.99), 2), confidence=CandidateConfidence(.9, .8, None), top3=_top3(2), provenance=_provenance(),
    )
    third = _registered_object(3, order=3)
    with pytest.raises(ValueError, match="in bounds"):
        _accepted_scan((out_of_bounds, _registered_object(2, order=2), third))
    with pytest.raises(ValueError, match="center_normalized"):
        _accepted_scan((_registered_object(1), inconsistent_center, third))


def test_unknown_requires_exact_ranked_top3() -> None:
    with pytest.raises(ValueError, match="exact ranked Top3"):
        _unknown_object((4, 4, 9))


def test_json_is_sorted_compact_and_rejects_non_finite_timings() -> None:
    result = _accepted_scan((_registered_object(15), _registered_object(1, order=2), _registered_object(2, order=3)))
    encoded = result.to_json_bytes()

    assert encoded == json.dumps(json.loads(encoded), allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert json.loads(encoded)["canonical_frame"] == {"width": 100, "height": 100}
    with pytest.raises(ValueError, match="finite"):
        ScanResult(
            scan_id="scan-1", retake_chain_id="chain-1", state=ScanState.ACCEPTED,
            objects=(_registered_object(1), _registered_object(2, order=2), _registered_object(3, order=3)), reasons=(), timings_ms=StageTimings(float("nan"), *(1.0,) * 8),
            provenance=result.provenance, canonical_frame=_FRAME, manual_catalog_required=False,
        )


def test_scan_result_rejects_mutable_result_collections() -> None:
    result = _accepted_scan((_registered_object(1), _registered_object(2, order=2), _registered_object(3, order=3)))

    with pytest.raises(ValueError, match="reasons must be an immutable tuple"):
        ScanResult(
            scan_id=result.scan_id, retake_chain_id=result.retake_chain_id,
            state=result.state, objects=result.objects, reasons=[],
            timings_ms=result.timings_ms, provenance=result.provenance,
            canonical_frame=_FRAME, manual_catalog_required=False,
        )
