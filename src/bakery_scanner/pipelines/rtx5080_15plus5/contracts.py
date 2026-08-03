"""Immutable public result contracts for the RTX 5080 candidate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import math
import re
from types import MappingProxyType
from typing import Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CENTER_TOLERANCE = 1e-6
CANONICAL_SKUS = MappingProxyType({
    1: "Walnut Donut", 2: "Croffle", 3: "Waffle", 4: "Scon",
    5: "Half-moon Croissant", 6: "Croissant", 7: "Flower Bread",
    8: "Almond Scon", 9: "Dinner Roll", 10: "Sugar Donut", 11: "Bagel",
    12: "Egg Tart", 13: "Muffin", 14: "Burger", 15: "Sandwich",
    16: "Grain Campagne", 17: "Almond Campagne", 18: "Mini Bread",
    19: "Pastry Bread", 20: "Plain Bread",
})


class ScanState(str, Enum):
    ACCEPTED = "accepted_scan"
    NEEDS_RETAKE = "needs_retake"
    ADMISSION_FAILED = "admission_failed"


class DecisionPath(str, Enum):
    DIRECT = "direct_approved"
    CONSENSUS = "consensus_approved"
    UNKNOWN = "unknown_top3"


class RetakeReason(str, Enum):
    NO_TARGET_DETECTED = "no_target_detected"
    OBJECT_COUNT_OUT_OF_PROFILE = "object_count_out_of_profile"
    UNCOVERED_FOREGROUND = "uncovered_foreground"
    OVERLAP_OR_OCCLUSION = "overlap_or_occlusion"
    POSSIBLE_SPLIT = "possible_split"
    POSSIBLE_MERGE = "possible_merge"
    TRUNCATED_OBJECT = "truncated_object"
    CAPTURE_QUALITY_UNVERIFIED = "capture_quality_unverified"
    COMPLETENESS_RISK_EXCEEDED = "completeness_risk_exceeded"


@dataclass(frozen=True, slots=True)
class ObjectLocation:
    box_xyxy: tuple[float, float, float, float]
    center_normalized: tuple[float, float]
    object_order: int

    def __post_init__(self) -> None:
        _finite_tuple(self.box_xyxy, 4, "box_xyxy")
        _finite_tuple(self.center_normalized, 2, "center_normalized")
        x_min, y_min, x_max, y_max = self.box_xyxy
        if x_min < 0 or y_min < 0 or x_max <= x_min or y_max <= y_min:
            raise ValueError("box_xyxy must be finite, non-negative, and ordered")
        if any(value < 0 or value > 1 for value in self.center_normalized):
            raise ValueError("center_normalized must be within [0, 1]")
        if not isinstance(self.object_order, int) or isinstance(self.object_order, bool) or self.object_order < 1:
            raise ValueError("object_order must be a positive integer")


@dataclass(frozen=True, slots=True)
class CanonicalFrame:
    """Canonical EXIF-transposed RGB frame used by every object coordinate."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or isinstance(self.width, bool) or self.width < 1:
            raise ValueError("canonical frame width must be a positive integer")
        if not isinstance(self.height, int) or isinstance(self.height, bool) or self.height < 1:
            raise ValueError("canonical frame height must be a positive integer")


@dataclass(frozen=True, slots=True)
class CandidateConfidence:
    detector_calibrated: float
    sku_acceptance_calibrated: float | None
    fusion_margin: float | None

    def __post_init__(self) -> None:
        _unit_interval(self.detector_calibrated, "detector_calibrated")
        if self.sku_acceptance_calibrated is not None:
            _unit_interval(self.sku_acceptance_calibrated, "sku_acceptance_calibrated")
        if self.fusion_margin is not None:
            _finite(self.fusion_margin, "fusion_margin")
            if self.fusion_margin < 0:
                raise ValueError("fusion_margin must be non-negative")


@dataclass(frozen=True, slots=True)
class SkuCandidate:
    rank: int
    sku_id: int
    sku_name: str
    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        _canonical_sku(self.sku_id, self.sku_name, "SkuCandidate")
        _unit_interval(self.score, "score")


@dataclass(frozen=True, slots=True)
class ObjectProvenance:
    detector_artifact_id: str
    detector_sha256: str
    repvit_artifact_id: str
    repvit_sha256: str
    dinov3_artifact_id: str
    dinov3_sha256: str
    fusion_policy_id: str
    fusion_policy_sha256: str
    runtime_profile_id: str

    def __post_init__(self) -> None:
        for name in (
            "detector_artifact_id", "repvit_artifact_id", "dinov3_artifact_id",
            "fusion_policy_id", "runtime_profile_id",
        ):
            _non_empty(getattr(self, name), name)
        for name in (
            "detector_sha256", "repvit_sha256", "dinov3_sha256", "fusion_policy_sha256",
        ):
            _sha256(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class FinalObject:
    object_id: str
    sku_id: int | None
    sku_name: str
    decision_path: DecisionPath
    location: ObjectLocation
    confidence: CandidateConfidence
    top3: tuple[SkuCandidate, ...]
    provenance: ObjectProvenance

    def __post_init__(self) -> None:
        _non_empty(self.object_id, "object_id")
        if not isinstance(self.decision_path, DecisionPath):
            raise ValueError("decision_path must be a DecisionPath")
        if not isinstance(self.location, ObjectLocation) or not isinstance(self.confidence, CandidateConfidence):
            raise ValueError("location and confidence must use immutable contracts")
        if not isinstance(self.provenance, ObjectProvenance):
            raise ValueError("provenance must use ObjectProvenance")
        _validate_top3(self.top3)
        if self.decision_path is DecisionPath.UNKNOWN:
            if self.sku_id is not None or self.sku_name != "Unknown":
                raise ValueError("Unknown requires sku_id None and sku_name Unknown")
            if self.confidence.sku_acceptance_calibrated is not None:
                raise ValueError("Unknown requires null SKU acceptance confidence")
        else:
            _canonical_sku(self.sku_id, self.sku_name, "FinalObject")
            if self.confidence.sku_acceptance_calibrated is None:
                raise ValueError("approved SKU requires SKU acceptance confidence")


@dataclass(frozen=True, slots=True)
class StageTimings:
    decode_canonical: float
    detector: float
    completeness: float
    crop: float
    repvit: float
    direct_gate: float
    dinov3: float
    fusion_payload: float
    total: float

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _finite(value, f"timings_ms.{name}")
            if value < 0:
                raise ValueError(f"timings_ms.{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class ScanProvenance:
    pipeline_id: str
    runtime_profile_id: str
    admission_receipt_sha256: str
    artifact_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        _non_empty(self.pipeline_id, "pipeline_id")
        _non_empty(self.runtime_profile_id, "runtime_profile_id")
        _sha256(self.admission_receipt_sha256, "admission_receipt_sha256")
        if not isinstance(self.artifact_hashes, Mapping) or not self.artifact_hashes:
            raise ValueError("artifact_hashes must be a non-empty mapping")
        normalized = dict(sorted(self.artifact_hashes.items()))
        for artifact_id, digest in normalized.items():
            _non_empty(artifact_id, "artifact_hashes key")
            _sha256(digest, f"artifact_hashes[{artifact_id}]")
        object.__setattr__(self, "artifact_hashes", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class ScanResult:
    scan_id: str
    retake_chain_id: str
    state: ScanState
    objects: tuple[FinalObject, ...]
    reasons: tuple[RetakeReason, ...]
    timings_ms: StageTimings
    provenance: ScanProvenance
    canonical_frame: CanonicalFrame
    manual_catalog_required: bool
    attempt: int | None = None
    problem_regions: tuple[ObjectLocation, ...] = ()

    def __post_init__(self) -> None:
        _non_empty(self.scan_id, "scan_id")
        _non_empty(self.retake_chain_id, "retake_chain_id")
        if not isinstance(self.state, ScanState):
            raise ValueError("state must be a ScanState")
        if not isinstance(self.timings_ms, StageTimings) or not isinstance(self.provenance, ScanProvenance):
            raise ValueError("timings_ms and provenance must use immutable contracts")
        if not isinstance(self.canonical_frame, CanonicalFrame):
            raise ValueError("canonical_frame must use CanonicalFrame")
        if not isinstance(self.manual_catalog_required, bool):
            raise ValueError("manual_catalog_required must be boolean")
        if not isinstance(self.objects, tuple):
            raise ValueError("objects must be an immutable tuple")
        if not isinstance(self.reasons, tuple):
            raise ValueError("reasons must be an immutable tuple")
        if not isinstance(self.problem_regions, tuple):
            raise ValueError("problem_regions must be an immutable tuple")
        if not all(isinstance(item, FinalObject) for item in self.objects):
            raise ValueError("objects must contain FinalObject values")
        _validate_locations((item.location for item in self.objects), self.canonical_frame)
        _validate_object_order(self.objects)
        if len({item.object_id for item in self.objects}) != len(self.objects):
            raise ValueError("object_id values must be unique")
        if not all(isinstance(reason, RetakeReason) for reason in self.reasons):
            raise ValueError("reasons must contain RetakeReason values")
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError("reasons must be unique")
        if not all(isinstance(region, ObjectLocation) for region in self.problem_regions):
            raise ValueError("problem_regions must contain ObjectLocation values")
        _validate_locations(self.problem_regions, self.canonical_frame)
        if self.state is ScanState.NEEDS_RETAKE:
            if self.objects:
                raise ValueError("needs_retake must not contain final objects")
            if not self.reasons:
                raise ValueError("needs_retake requires a reason")
            if not isinstance(self.attempt, int) or isinstance(self.attempt, bool) or self.attempt < 1:
                raise ValueError("needs_retake attempt must be a positive integer")
            if self.manual_catalog_required != (self.attempt >= 3):
                raise ValueError("manual_catalog_required is true only for needs_retake attempt 3 and later")
        elif self.state is ScanState.ACCEPTED:
            if not 3 <= len(self.objects) <= 7:
                raise ValueError("accepted_scan must contain 3 through 7 final objects")
            if self.reasons or self.problem_regions or self.attempt is not None or self.manual_catalog_required:
                raise ValueError("accepted_scan must not carry retake fields")
        else:
            raise ValueError("admission_failed does not produce a ScanResult")

    @property
    def object_total(self) -> int:
        return len(self.objects)

    @property
    def registered_object_total(self) -> int:
        return sum(item.sku_id is not None for item in self.objects)

    @property
    def unknown_total(self) -> int:
        return sum(item.sku_id is None for item in self.objects)

    @property
    def sku_totals(self) -> dict[int, int]:
        totals: dict[int, int] = {}
        for item in self.objects:
            if item.sku_id is not None:
                totals[item.sku_id] = totals.get(item.sku_id, 0) + 1
        return dict(sorted(totals.items()))

    @classmethod
    def needs_retake(
        cls, *, scan_id: str, retake_chain_id: str, attempt: int,
        reasons: tuple[RetakeReason, ...], problem_regions: tuple[ObjectLocation, ...],
        objects: tuple[FinalObject, ...] = (), timings_ms: StageTimings,
        provenance: ScanProvenance, canonical_frame: CanonicalFrame,
    ) -> "ScanResult":
        return cls(
            scan_id=scan_id, retake_chain_id=retake_chain_id, state=ScanState.NEEDS_RETAKE,
            objects=objects, reasons=reasons, timings_ms=timings_ms, provenance=provenance,
            canonical_frame=canonical_frame, manual_catalog_required=attempt >= 3, attempt=attempt, problem_regions=problem_regions,
        )

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            scan_result_payload(self), allow_nan=False, ensure_ascii=False,
            separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")


def scan_result_payload(result: ScanResult) -> dict[str, object]:
    """Return the fully validated, JSON-ready scan result payload."""
    if not isinstance(result, ScanResult):
        raise ValueError("result must be a ScanResult")
    result.__post_init__()
    payload: dict[str, object] = {
        "scan_id": result.scan_id,
        "retake_chain_id": result.retake_chain_id,
        "state": result.state.value,
        "object_total": result.object_total,
        "registered_object_total": result.registered_object_total,
        "unknown_total": result.unknown_total,
        "sku_totals": {str(sku_id): total for sku_id, total in result.sku_totals.items()},
        "objects": [_object_payload(item) for item in result.objects],
        "reasons": [reason.value for reason in result.reasons],
        "problem_regions": [_location_payload(region) for region in result.problem_regions],
        "attempt": result.attempt,
        "canonical_frame": {"width": result.canonical_frame.width, "height": result.canonical_frame.height},
        "timings_ms": asdict(result.timings_ms),
        "provenance": {
            "pipeline_id": result.provenance.pipeline_id,
            "runtime_profile_id": result.provenance.runtime_profile_id,
            "admission_receipt_sha256": result.provenance.admission_receipt_sha256,
            "artifact_hashes": dict(result.provenance.artifact_hashes),
        },
        "manual_catalog_required": result.manual_catalog_required,
    }
    json.dumps(payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return payload


def _object_payload(item: FinalObject) -> dict[str, object]:
    return {
        "object_id": item.object_id,
        "sku_id": item.sku_id,
        "sku_name": item.sku_name,
        "decision_path": item.decision_path.value,
        "location": _location_payload(item.location),
        "confidence": asdict(item.confidence),
        "top3": [asdict(candidate) for candidate in item.top3],
        "provenance": asdict(item.provenance),
    }


def _location_payload(location: ObjectLocation) -> dict[str, object]:
    return {"box_xyxy": list(location.box_xyxy), "center_normalized": list(location.center_normalized), "object_order": location.object_order}


def _validate_top3(top3: tuple[SkuCandidate, ...]) -> None:
    if not isinstance(top3, tuple) or len(top3) != 3 or not all(isinstance(item, SkuCandidate) for item in top3):
        raise ValueError("top3 must be exact ranked Top3")
    if tuple(item.rank for item in top3) != (1, 2, 3) or len({item.sku_id for item in top3}) != 3:
        raise ValueError("top3 must be exact ranked Top3")
    if any(top3[index].score < top3[index + 1].score for index in range(2)):
        raise ValueError("top3 scores must be ranked descending")


def _validate_object_order(objects: tuple[FinalObject, ...]) -> None:
    expected = tuple(sorted(objects, key=lambda item: (
        item.location.center_normalized[1], item.location.center_normalized[0],
        item.location.box_xyxy[0], item.location.box_xyxy[1],
    )))
    if objects != expected:
        raise ValueError("objects must use deterministic lexicographic location order")
    if tuple(item.location.object_order for item in objects) != tuple(range(1, len(objects) + 1)):
        raise ValueError("object_order must match deterministic object sequence")


def _validate_locations(locations: object, frame: CanonicalFrame) -> None:
    """Require in-bounds coordinates and center agreement within 1e-6 normalized units."""
    for location in locations:
        x_min, y_min, x_max, y_max = location.box_xyxy
        if x_max > frame.width or y_max > frame.height:
            raise ValueError("box_xyxy must remain in bounds of the canonical frame")
        expected_x = (x_min + x_max) / (2 * frame.width)
        expected_y = (y_min + y_max) / (2 * frame.height)
        actual_x, actual_y = location.center_normalized
        if abs(actual_x - expected_x) > _CENTER_TOLERANCE or abs(actual_y - expected_y) > _CENTER_TOLERANCE:
            raise ValueError("center_normalized must agree with the canonical box center")


def _finite_tuple(value: tuple[float, ...], length: int, name: str) -> None:
    if not isinstance(value, tuple) or len(value) != length:
        raise ValueError(f"{name} must be a tuple of length {length}")
    for item in value:
        _finite(item, name)


def _finite(value: object, name: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _unit_interval(value: object, name: str) -> None:
    _finite(value, name)
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be within [0, 1]")


def _canonical_sku(value: object, sku_name: object, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value not in CANONICAL_SKUS:
        raise ValueError(f"{name} must use a canonical SKU ID")
    if sku_name != CANONICAL_SKUS[value]:
        raise ValueError(f"{name} must use the canonical SKU name")


def _non_empty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _sha256(value: object, name: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 hash")
