"""Strict JSON Lines protocol for the camera evaluation worker."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, TypeAlias

from bakery_scanner.pipelines.rtx5080_15plus5.contracts import (
    CANONICAL_SKUS,
    RetakeReason,
    ScanResult,
    scan_result_payload,
)

_PRESENTATION_FIELDS = {
    "state",
    "final_count_usable",
    "retake_scope",
    "retake_object_ids",
    "instruction_code",
    "candidate_object_ids",
    "policy_id",
    "policy_sha256",
}
_V1_POLICY_ID = "camera_action_state_v1"
_V2_POLICY_ID = "camera_action_state_v2"
_POLICY_IDS = frozenset({_V1_POLICY_ID, _V2_POLICY_ID})
_LOWER_HEX = frozenset("0123456789abcdef")
_TIMING_STAGES = frozenset(
    {
        "decode_preprocess",
        "detector",
        "crop",
        "repvit",
        "dinov3",
        "fusion",
        "postprocess",
        "total",
    }
)
_RUNTIME_MODES = frozenset(
    {"gpu_fast_verified", "gpu_reference", "cpu_reference"}
)
_OBJECT_FIELDS = frozenset(
    {
        "object_id", "sku_id", "sku_name", "bbox_xyxy", "confidence",
        "decision_path", "top3", "unknown_reason", "detector", "provenance",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "type", "request_id", "image", "device", "objects", "counts",
        "unknown_count", "execution_device", "runtime_mode", "fallback_reason",
        "scan_to_result_ms", "inference_ms", "presentation", "timings_ms",
        "diagnostics",
    }
)
_CANDIDATE_RESULT_FIELDS = frozenset(
    {
        "type", "request_id", "scan_id", "retake_chain_id", "state", "object_total",
        "registered_object_total", "unknown_total", "sku_totals", "objects",
        "reasons", "problem_regions", "attempt", "canonical_frame",
        "timings_ms", "provenance", "manual_catalog_required",
        "runtime_profile_id", "receipt_id",
    }
)
_CANDIDATE_TIMING_STAGES = frozenset(
    {
        "decode_canonical", "detector", "completeness", "crop", "repvit",
        "direct_gate", "dinov3", "fusion_payload", "total",
    }
)
_CANDIDATE_OBJECT_FIELDS = frozenset(
    {
        "object_id", "sku_id", "sku_name", "decision_path", "location",
        "confidence", "top3", "provenance",
    }
)
_CANDIDATE_PROVENANCE_FIELDS = frozenset(
    {
        "pipeline_id", "runtime_profile_id", "admission_receipt_sha256",
        "artifact_hashes",
    }
)
_CANDIDATE_OBJECT_PROVENANCE_FIELDS = frozenset(
    {
        "detector_artifact_id", "detector_sha256", "repvit_artifact_id",
        "repvit_sha256", "dinov3_artifact_id", "dinov3_sha256",
        "fusion_policy_id", "fusion_policy_sha256", "runtime_profile_id",
    }
)
_LOCATION_FIELDS = frozenset({"box_xyxy", "center_normalized", "object_order"})
_CONFIDENCE_FIELDS = frozenset(
    {"detector_calibrated", "sku_acceptance_calibrated", "fusion_margin"}
)
_REGISTERED_PATHS = frozenset({"repvit_direct", "dinov3_confirmed", "fusion_ranked"})
_PROVENANCE_FIELDS = frozenset(
    {
        "detector_id", "repvit_artifact_id", "repvit_sha256", "repvit_manifest_sha256",
        "repvit_prototype_sha256", "dinov3_artifact_id", "dinov3_sha256",
        "dinov3_support_sha256", "calibration_id", "calibration_sha256",
        "preprocess_sha256", "canonical_frame_version", "exif_orientation", "failure_code",
    }
)


@dataclass(frozen=True)
class AnalyzeRequest:
    request_id: str
    image_path: Path


@dataclass(frozen=True)
class PingRequest:
    request_id: str


@dataclass(frozen=True)
class ShutdownRequest:
    request_id: str


Request: TypeAlias = AnalyzeRequest | PingRequest | ShutdownRequest


class WorkerPhase(str, Enum):
    DETECTING = "detecting"
    CLASSIFYING = "classifying"
    RECHECKING = "rechecking"
    AGGREGATING = "aggregating"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_object(line: str) -> dict[str, object]:
    if not isinstance(line, str):
        raise ValueError("request line must be a string")
    try:
        request = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("request must be valid JSON with unique keys") from exc
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    return request


def _request_id(request: Mapping[str, object]) -> str:
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")
    return request_id


def _require_fields(request: Mapping[str, object], expected: set[str]) -> None:
    if set(request) != expected:
        raise ValueError("request fields do not match request type")


def parse_request(line: str) -> Request:
    """Parse one JSON Lines request while rejecting ambiguous input."""
    request = _parse_object(line)
    request_type = request.get("type")
    if not isinstance(request_type, str):
        raise ValueError("request type must be a string")

    if request_type == "ping":
        _require_fields(request, {"type", "request_id"})
        return PingRequest(_request_id(request))
    if request_type == "shutdown":
        _require_fields(request, {"type", "request_id"})
        return ShutdownRequest(_request_id(request))
    if request_type != "analyze":
        raise ValueError(f"unsupported request type: {request_type}")

    _require_fields(request, {"type", "request_id", "image_path"})
    image_path = request["image_path"]
    if not isinstance(image_path, str):
        raise ValueError("image_path must be a string")
    path = Path(image_path)
    if not path.is_absolute():
        raise ValueError("image_path must be absolute")
    if not path.is_file():
        raise ValueError("image_path must refer to an existing file")
    return AnalyzeRequest(_request_id(request), path.resolve())


def progress_event(request_id: str, phase: WorkerPhase) -> dict[str, object]:
    """Return a canonical correlated progress event."""
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")
    if not isinstance(phase, WorkerPhase):
        raise ValueError("phase must be a WorkerPhase")
    return {"type": "progress", "request_id": request_id, "phase": phase.value}


def validate_result_event(result: Mapping[str, object]) -> None:
    """Reject malformed or internally inconsistent presentation routing."""
    if isinstance(result, Mapping) and set(result) == _CANDIDATE_RESULT_FIELDS:
        _validate_candidate_result_event(result)
        return
    if (
        not isinstance(result, Mapping)
        or set(result) != _RESULT_FIELDS
        or result.get("type") != "result"
    ):
        raise ValueError("runtime result envelope is invalid")
    request_id = result["request_id"]
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("runtime result request_id is invalid")
    if result["device"] not in {"cpu", "cuda:0"}:
        raise ValueError("runtime result device is invalid")
    _validate_runtime_scope(result)
    width, height = _validate_result_image(result["image"])
    object_ids, unknown_ids, registered_counts = _result_object_ids(
        result["objects"], width, height
    )
    _validate_counts(result["counts"], registered_counts, result["unknown_count"], len(unknown_ids))
    _validate_timings(result.get("timings_ms"))
    _validate_diagnostics(result.get("diagnostics"), len(object_ids))
    presentation = result.get("presentation")
    if (
        not isinstance(presentation, Mapping)
        or set(presentation) != _PRESENTATION_FIELDS
    ):
        raise ValueError("runtime result presentation schema is invalid")

    state = presentation["state"]
    final_count_usable = presentation["final_count_usable"]
    retake_scope = presentation["retake_scope"]
    instruction_code = presentation["instruction_code"]
    if not isinstance(state, str) or state not in (
        "normal",
        "unknown",
        "needs_retake",
    ):
        raise ValueError("runtime result presentation state is invalid")
    if not isinstance(final_count_usable, bool):
        raise ValueError("runtime result final_count_usable is invalid")
    if retake_scope is not None and retake_scope not in ("scan", "object"):
        raise ValueError("runtime result retake_scope is invalid")
    policy_id = presentation["policy_id"]
    if policy_id not in _POLICY_IDS:
        raise ValueError("runtime result presentation policy ID is invalid")
    policy_sha256 = presentation["policy_sha256"]
    if (
        not isinstance(policy_sha256, str)
        or len(policy_sha256) != 64
        or any(character not in _LOWER_HEX for character in policy_sha256)
    ):
        raise ValueError("runtime result presentation policy SHA-256 is invalid")

    retake_ids = _object_id_list(
        presentation["retake_object_ids"], "retake_object_ids"
    )
    candidate_ids = _object_id_list(
        presentation["candidate_object_ids"], "candidate_object_ids"
    )
    if state == "normal":
        if (
            final_count_usable is not True
            or retake_scope is not None
            or instruction_code is not None
            or retake_ids
            or candidate_ids
        ):
            raise ValueError("normal presentation state is inconsistent")
        return
    if state == "unknown":
        if (
            final_count_usable is not True
            or retake_scope is not None
            or instruction_code is not None
            or retake_ids
            or not candidate_ids
            or not set(candidate_ids).issubset(unknown_ids)
        ):
            raise ValueError("unknown presentation state is inconsistent")
        _require_exact_ranked_top3(result.get("objects"), candidate_ids)
        return
    if final_count_usable is not False or candidate_ids or retake_scope not in (
        "scan",
        "object",
    ):
        raise ValueError("needs_retake presentation state is inconsistent")
    if retake_scope == "scan":
        if retake_ids or instruction_code != "no_bread_detected":
            raise ValueError("scan retake presentation state is inconsistent")
        return
    if (
        not retake_ids
        or not set(retake_ids).issubset(object_ids)
        or (
            policy_id == _V2_POLICY_ID
            and instruction_code != "separate_breads"
        )
        or (
            policy_id == _V1_POLICY_ID
            and instruction_code
            not in {"separate_breads", "candidate_evidence_weak"}
        )
    ):
        raise ValueError("object retake presentation state is inconsistent")


def encode_scan_result(result: ScanResult) -> dict[str, object]:
    """Wrap the immutable candidate ScanResult as a strict worker event."""
    payload = scan_result_payload(result)
    provenance = payload["provenance"]
    assert isinstance(provenance, Mapping)
    event = {
        "type": "result",
        "request_id": payload["scan_id"],
        **payload,
        "runtime_profile_id": provenance["runtime_profile_id"],
        "receipt_id": provenance["admission_receipt_sha256"],
    }
    validate_result_event(event)
    return event


def _validate_candidate_result_event(result: Mapping[str, object]) -> None:
    if result.get("type") != "result":
        raise ValueError("candidate runtime result type is invalid")
    scan_id = _required_text(result["scan_id"], "candidate scan_id")
    if _required_text(result["request_id"], "candidate request_id") != scan_id:
        raise ValueError("candidate request_id must equal scan_id")
    _required_text(result["retake_chain_id"], "candidate retake_chain_id")
    frame = result["canonical_frame"]
    if not isinstance(frame, Mapping) or set(frame) != {"width", "height"}:
        raise ValueError("candidate canonical_frame is invalid")
    width = _positive_integer(frame["width"], "candidate frame width")
    height = _positive_integer(frame["height"], "candidate frame height")

    provenance = result["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != _CANDIDATE_PROVENANCE_FIELDS:
        raise ValueError("candidate result provenance is invalid")
    if provenance["pipeline_id"] != "rtx5080_15plus5_single_frame_v1":
        raise ValueError("candidate pipeline identity is invalid")
    profile = _required_text(provenance["runtime_profile_id"], "candidate runtime profile")
    receipt = _candidate_sha(provenance["admission_receipt_sha256"], "candidate admission receipt")
    if result["runtime_profile_id"] != profile or result["receipt_id"] != receipt:
        raise ValueError("candidate runtime profile or receipt identity mismatch")
    artifacts = provenance["artifact_hashes"]
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise ValueError("candidate artifact provenance is invalid")
    for artifact_id, digest in artifacts.items():
        _required_text(artifact_id, "candidate artifact ID")
        _candidate_sha(digest, "candidate artifact SHA-256")

    _validate_candidate_timings(result["timings_ms"])
    objects = result["objects"]
    if not isinstance(objects, list):
        raise ValueError("candidate objects must be a list")
    state = result["state"]
    if state == "needs_retake" and objects:
        raise ValueError("candidate retake must not contain partial inference")
    registered_counts: dict[str, int] = {}
    unknown_count = 0
    locations: list[tuple[float, float, float, float, float, float]] = []
    for index, value in enumerate(objects, start=1):
        sku_id, location = _validate_candidate_object(
            value, index=index, scan_id=scan_id, width=width, height=height,
            runtime_profile_id=profile,
        )
        locations.append(location)
        if sku_id is None:
            unknown_count += 1
        else:
            key = str(sku_id)
            registered_counts[key] = registered_counts.get(key, 0) + 1
    if locations != sorted(locations, key=lambda row: (row[5], row[4], row[0], row[1])):
        raise ValueError("candidate object order is invalid")

    object_total = _non_negative_integer(result["object_total"], "candidate object_total")
    registered_total = _non_negative_integer(
        result["registered_object_total"], "candidate registered_object_total"
    )
    reported_unknown = _non_negative_integer(result["unknown_total"], "candidate unknown_total")
    if (
        object_total != len(objects)
        or registered_total != len(objects) - unknown_count
        or reported_unknown != unknown_count
    ):
        raise ValueError("candidate result totals do not match objects")
    totals = result["sku_totals"]
    if not isinstance(totals, Mapping) or dict(totals) != registered_counts:
        raise ValueError("candidate SKU totals do not match registered objects")

    reasons = result["reasons"]
    regions = result["problem_regions"]
    if not isinstance(reasons, list) or len(reasons) != len(set(reasons)):
        raise ValueError("candidate retake reasons are invalid")
    allowed_reasons = {reason.value for reason in RetakeReason}
    if any(reason not in allowed_reasons for reason in reasons):
        raise ValueError("candidate retake reasons are invalid")
    if not isinstance(regions, list):
        raise ValueError("candidate problem regions are invalid")
    for index, region in enumerate(regions, start=1):
        _candidate_location(region, index, width, height)

    manual = result["manual_catalog_required"]
    if type(manual) is not bool:
        raise ValueError("candidate manual_catalog_required must be boolean")
    attempt = result["attempt"]
    if state == "needs_retake":
        if objects or registered_counts or object_total or registered_total or reported_unknown:
            raise ValueError("candidate retake must not contain partial inference")
        attempt_value = _positive_integer(attempt, "candidate retake attempt")
        if not reasons or manual is not (attempt_value >= 3):
            raise ValueError("candidate retake attempt or manual escalation is invalid")
    elif state == "accepted_scan":
        if not objects or reasons or regions or attempt is not None or manual:
            raise ValueError("candidate accepted scan carries invalid retake fields")
    else:
        raise ValueError("candidate result state is invalid")


def _validate_candidate_object(
    value: object,
    *,
    index: int,
    scan_id: str,
    width: int,
    height: int,
    runtime_profile_id: str,
) -> tuple[int | None, tuple[float, float, float, float, float, float]]:
    if not isinstance(value, Mapping) or set(value) != _CANDIDATE_OBJECT_FIELDS:
        raise ValueError("candidate object schema is invalid")
    object_id = _required_text(value["object_id"], "candidate object_id")
    if object_id != f"{scan_id}#{index:04d}":
        raise ValueError("candidate object identity or order is invalid")
    location = _candidate_location(value["location"], index, width, height)
    confidence = value["confidence"]
    if not isinstance(confidence, Mapping) or set(confidence) != _CONFIDENCE_FIELDS:
        raise ValueError("candidate object confidence is invalid")
    _candidate_probability(confidence["detector_calibrated"], "detector confidence")
    acceptance = confidence["sku_acceptance_calibrated"]
    margin = confidence["fusion_margin"]
    if acceptance is not None:
        _candidate_probability(acceptance, "SKU acceptance confidence")
    if margin is not None:
        _candidate_non_negative_finite(margin, "fusion margin")

    object_provenance = value["provenance"]
    if (
        not isinstance(object_provenance, Mapping)
        or set(object_provenance) != _CANDIDATE_OBJECT_PROVENANCE_FIELDS
        or object_provenance["runtime_profile_id"] != runtime_profile_id
    ):
        raise ValueError("candidate object provenance is invalid")
    for field in (
        "detector_artifact_id", "repvit_artifact_id", "dinov3_artifact_id",
        "fusion_policy_id", "runtime_profile_id",
    ):
        _required_text(object_provenance[field], f"candidate object {field}")
    for field in (
        "detector_sha256", "repvit_sha256", "dinov3_sha256",
        "fusion_policy_sha256",
    ):
        _candidate_sha(object_provenance[field], f"candidate object {field}")

    sku_id = value["sku_id"]
    path = value["decision_path"]
    name = value["sku_name"]
    if sku_id is None:
        if name != "Unknown" or path != "unknown_top3" or acceptance is not None:
            raise ValueError("candidate Unknown object is invalid")
    else:
        if type(sku_id) is not int or sku_id not in CANONICAL_SKUS:
            raise ValueError("candidate registered SKU is invalid")
        if name != CANONICAL_SKUS[sku_id] or path not in {"direct_approved", "consensus_approved"} or acceptance is None:
            raise ValueError("candidate registered object is invalid")
    _candidate_top3(value["top3"])
    return sku_id, location


def _candidate_location(
    value: object, order: int, width: int, height: int
) -> tuple[float, float, float, float, float, float]:
    if not isinstance(value, Mapping) or set(value) != _LOCATION_FIELDS:
        raise ValueError("candidate object location is invalid")
    box = value["box_xyxy"]
    center = value["center_normalized"]
    if not isinstance(box, list) or len(box) != 4 or not isinstance(center, list) or len(center) != 2:
        raise ValueError("candidate object location is invalid")
    try:
        x1, y1, x2, y2 = (float(item) for item in box)
        cx, cy = (float(item) for item in center)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate object location is invalid") from exc
    if (
        any(isinstance(item, bool) for item in (*box, *center))
        or not all(math.isfinite(item) for item in (x1, y1, x2, y2, cx, cy))
        or x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1
        or x2 > width or y2 > height or not 0 <= cx <= 1 or not 0 <= cy <= 1
        or abs(cx - (x1 + x2) / (2 * width)) > 1e-6
        or abs(cy - (y1 + y2) / (2 * height)) > 1e-6
        or value["object_order"] != order
        or type(value["object_order"]) is not int
    ):
        raise ValueError("candidate object location is invalid")
    return (x1, y1, x2, y2, cx, cy)


def _candidate_top3(value: object) -> None:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("candidate exact Top3 is invalid")
    parsed: list[tuple[int, int, float]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"rank", "sku_id", "sku_name", "score"}:
            raise ValueError("candidate exact Top3 is invalid")
        rank = item["rank"]
        sku_id = item["sku_id"]
        if type(rank) is not int or type(sku_id) is not int or sku_id not in CANONICAL_SKUS or item["sku_name"] != CANONICAL_SKUS[sku_id]:
            raise ValueError("candidate exact Top3 is invalid")
        score = _candidate_probability(item["score"], "candidate Top3 score")
        parsed.append((rank, sku_id, score))
    if (
        tuple(row[0] for row in parsed) != (1, 2, 3)
        or len({row[1] for row in parsed}) != 3
        or any(parsed[index][2] < parsed[index + 1][2] for index in range(2))
    ):
        raise ValueError("candidate exact Top3 is invalid")


def _validate_candidate_timings(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != _CANDIDATE_TIMING_STAGES:
        raise ValueError("candidate timings_ms schema is invalid")
    for stage, timing in value.items():
        _candidate_non_negative_finite(timing, f"candidate timing {stage}")
    if float(value["total"]) < max(float(value[stage]) for stage in _CANDIDATE_TIMING_STAGES - {"total"}):
        raise ValueError("candidate total timing is invalid")


def _candidate_probability(value: object, name: str) -> float:
    numeric = _candidate_non_negative_finite(value, name)
    if numeric > 1:
        raise ValueError(f"{name} is invalid")
    return numeric


def _candidate_non_negative_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise ValueError(f"{name} is invalid")
    return float(value)


def _candidate_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in _LOWER_HEX for character in value):
        raise ValueError(f"{name} is invalid")
    return value


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is invalid")
    return value


def _positive_integer(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} is invalid")
    return value


def _non_negative_integer(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} is invalid")
    return value


def _validate_runtime_scope(result: Mapping[str, object]) -> None:
    execution_device = result["execution_device"]
    if execution_device not in {"cpu", "cuda:0"}:
        raise ValueError("runtime result execution device is invalid")
    if execution_device != result["device"]:
        raise ValueError("runtime result execution device must match device")

    runtime_mode = result["runtime_mode"]
    if runtime_mode not in _RUNTIME_MODES:
        raise ValueError("runtime result runtime mode is invalid")
    if runtime_mode == "cpu_reference":
        if execution_device != "cpu":
            raise ValueError("runtime result CPU mode requires cpu device")
    elif execution_device != "cuda:0":
        raise ValueError("runtime result GPU mode requires cuda:0 device")

    fallback_reason = result["fallback_reason"]
    if runtime_mode == "gpu_fast_verified":
        if fallback_reason is not None:
            raise ValueError("runtime result verified GPU fallback reason is invalid")
    elif not isinstance(fallback_reason, str) or not fallback_reason:
        raise ValueError("runtime result reference fallback reason is invalid")

    scan_to_result_ms = _validate_runtime_latency(
        result["scan_to_result_ms"], "scan_to_result_ms"
    )
    inference_ms = _validate_runtime_latency(result["inference_ms"], "inference_ms")
    if inference_ms > scan_to_result_ms:
        raise ValueError("runtime result inference_ms exceeds scan_to_result_ms")


def _validate_runtime_latency(value: object, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0.0
    ):
        raise ValueError(f"runtime result {field} is invalid")
    return float(value)


def _require_exact_ranked_top3(
    value: object, candidate_ids: tuple[str, ...]
) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("runtime result objects must be a sequence")
    objects = {
        item.get("object_id"): item
        for item in value
        if isinstance(item, Mapping)
    }
    for object_id in candidate_ids:
        raw_top3 = objects[object_id].get("top3")
        if (
            not isinstance(raw_top3, list)
            or len(raw_top3) != 3
            or any(not isinstance(item, Mapping) for item in raw_top3)
        ):
            raise ValueError("runtime result candidate Top3 is invalid")
        if any(set(item) != {"rank", "sku_id", "sku_name", "score"} for item in raw_top3):
            raise ValueError("runtime result candidate Top3 schema is invalid")
        ranks = tuple(item.get("rank") for item in raw_top3)
        sku_ids = tuple(item.get("sku_id") for item in raw_top3)
        sku_names = tuple(item.get("sku_name") for item in raw_top3)
        scores = tuple(item.get("score") for item in raw_top3)
        if ranks != (1, 2, 3):
            raise ValueError("runtime result candidate Top3 ranks are invalid")
        if (
            any(
                isinstance(sku_id, bool)
                or not isinstance(sku_id, int)
                or not 1 <= sku_id <= 20
                for sku_id in sku_ids
            )
            or len(set(sku_ids)) != 3
        ):
            raise ValueError("runtime result candidate Top3 SKUs are invalid")
        if any(not isinstance(name, str) or not name for name in sku_names):
            raise ValueError("runtime result candidate Top3 names are invalid")
        if any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 0.0 <= float(score) <= 1.0
            for score in scores
        ):
            raise ValueError("runtime result candidate Top3 scores are invalid")
        ordered = tuple(zip(scores, sku_ids, strict=True))
        if tuple(
            sorted(ordered, key=lambda item: (-float(item[0]), int(item[1])))
        ) != ordered:
            raise ValueError(
                "runtime result candidate Top3 scores must descend with SKU-ID ties ascending"
            )


def _result_object_ids(
    value: object, image_width: int, image_height: int
) -> tuple[set[str], set[str], dict[str, int]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("runtime result objects must be a sequence")
    object_ids: set[str] = set()
    unknown_ids: set[str] = set()
    registered_counts: dict[str, int] = {}
    for position, item in enumerate(value, start=1):
        if not isinstance(item, Mapping) or set(item) != _OBJECT_FIELDS:
            raise ValueError("runtime result objects must be mappings")
        object_id = item.get("object_id")
        if (
            not isinstance(object_id, str)
            or object_id != f"object-{position}"
            or object_id in object_ids
            or "sku_id" not in item
        ):
            raise ValueError("runtime result object identity is invalid")
        sku_id = item["sku_id"]
        if sku_id is not None and (
            isinstance(sku_id, bool) or not isinstance(sku_id, int) or not 1 <= sku_id <= 20
        ):
            raise ValueError("runtime result object sku_id is invalid")
        sku_name = item["sku_name"]
        path = item["decision_path"]
        if not isinstance(sku_name, str) or not sku_name or not isinstance(path, str):
            raise ValueError("runtime result object identity is invalid")
        _validate_object_box(item["bbox_xyxy"], image_width, image_height)
        _validate_probability(item["confidence"], "runtime result object confidence")
        _validate_detector(item["detector"])
        _validate_provenance(item["provenance"])
        unknown_reason = item["unknown_reason"]
        top3 = item["top3"]
        if not isinstance(top3, list):
            raise ValueError("runtime result object top3 is invalid")
        if sku_id is None:
            if sku_name != "Unknown" or path != "unknown_top3":
                raise ValueError("runtime result Unknown object identity is invalid")
            if unknown_reason is not None and (
                not isinstance(unknown_reason, str) or not unknown_reason
            ):
                raise ValueError("runtime result Unknown object reason is invalid")
            _require_exact_ranked_top3((item,), (object_id,))
        elif (
            sku_name == "Unknown" or path not in _REGISTERED_PATHS or top3 or unknown_reason is not None
        ):
            raise ValueError("runtime result registered object is invalid")
        object_ids.add(object_id)
        if sku_id is None:
            unknown_ids.add(object_id)
        else:
            key = str(sku_id)
            registered_counts[key] = registered_counts.get(key, 0) + 1
    return object_ids, unknown_ids, registered_counts


def _validate_object_box(value: object, image_width: int, image_height: int) -> None:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("runtime result object box is invalid")
    try:
        x1, y1, x2, y2 = (float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("runtime result object box is invalid") from exc
    if (
        not all(math.isfinite(item) for item in (x1, y1, x2, y2))
        or x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1
        or x2 > image_width or y2 > image_height
    ):
        raise ValueError("runtime result object box is invalid")


def _validate_result_image(value: object) -> tuple[int, int]:
    if not isinstance(value, Mapping) or set(value) != {"width", "height"}:
        raise ValueError("runtime result image is invalid")
    width, height = value["width"], value["height"]
    if (
        isinstance(width, bool) or isinstance(height, bool)
        or not isinstance(width, int) or not isinstance(height, int)
        or width <= 0 or height <= 0
    ):
        raise ValueError("runtime result image is invalid")
    return width, height


def _validate_counts(
    value: object,
    expected: Mapping[str, int],
    unknown_count: object,
    expected_unknown: int,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("runtime result counts is invalid")
    normalized: dict[str, int] = {}
    for sku_id, count in value.items():
        if (
            not isinstance(sku_id, str) or not sku_id.isascii() or not sku_id.isdecimal()
            or str(int(sku_id)) != sku_id or not 1 <= int(sku_id) <= 20
            or isinstance(count, bool) or not isinstance(count, int) or count < 0
        ):
            raise ValueError("runtime result counts is invalid")
        normalized[sku_id] = count
    if normalized != dict(expected):
        raise ValueError("runtime result counts do not match objects")
    if isinstance(unknown_count, bool) or not isinstance(unknown_count, int) or unknown_count != expected_unknown:
        raise ValueError("runtime result unknown_count does not match objects")


def _validate_probability(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
        raise ValueError(f"{label} is invalid")


def _validate_detector(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"source", "score"} or not isinstance(value["source"], str) or not value["source"]:
        raise ValueError("runtime result object detector is invalid")
    _validate_probability(value["score"], "runtime result object detector score")


def _validate_provenance(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != _PROVENANCE_FIELDS:
        raise ValueError("runtime result object provenance is invalid")
    for field in {"detector_id", "repvit_artifact_id", "dinov3_artifact_id", "calibration_id"}:
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError("runtime result object provenance is invalid")
    for field in {"repvit_sha256", "repvit_manifest_sha256", "repvit_prototype_sha256", "dinov3_sha256", "dinov3_support_sha256", "calibration_sha256", "preprocess_sha256"}:
        hash_value = value[field]
        if not isinstance(hash_value, str) or len(hash_value) != 64 or any(character not in _LOWER_HEX for character in hash_value):
            raise ValueError("runtime result object provenance is invalid")
    if value["canonical_frame_version"] != "exif_visual_rgb_v1" or isinstance(value["exif_orientation"], bool) or not isinstance(value["exif_orientation"], int) or not 1 <= value["exif_orientation"] <= 8:
        raise ValueError("runtime result object provenance is invalid")
    if value["failure_code"] is not None and (not isinstance(value["failure_code"], str) or not value["failure_code"]):
        raise ValueError("runtime result object provenance is invalid")


def _object_id_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"runtime result {field} must be a list")
    object_ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item in object_ids:
            raise ValueError(f"runtime result {field} is invalid")
        object_ids.append(item)
    return tuple(object_ids)


def _validate_diagnostics(value: object, object_count: int) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "object_count", "dino_object_count"
    }:
        raise ValueError("runtime result diagnostics schema is invalid")
    reported_objects = value["object_count"]
    dino_objects = value["dino_object_count"]
    if (
        isinstance(reported_objects, bool)
        or not isinstance(reported_objects, int)
        or reported_objects != object_count
        or isinstance(dino_objects, bool)
        or not isinstance(dino_objects, int)
        or not 0 <= dino_objects <= object_count
    ):
        raise ValueError("runtime result diagnostics are invalid")


def _validate_timings(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != _TIMING_STAGES:
        raise ValueError("runtime result timings_ms schema is invalid")
    for stage in _TIMING_STAGES:
        timing = value[stage]
        if (
            isinstance(timing, bool)
            or not isinstance(timing, (int, float))
            or not math.isfinite(float(timing))
            or timing < 0.0
        ):
            raise ValueError("runtime result timings_ms values are invalid")
    if value["total"] < max(value[stage] for stage in _TIMING_STAGES - {"total"}):
        raise ValueError("runtime result timings_ms total must cover every stage")


def encode_event(event: Mapping[str, object]) -> str:
    """Encode one event as deterministic UTF-8 JSON Lines text."""
    return json.dumps(
        event,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
