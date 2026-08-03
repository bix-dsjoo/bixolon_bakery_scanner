"""Strict JSON Lines protocol for the camera evaluation worker."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, TypeAlias

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
    if not isinstance(result, Mapping) or result.get("type") != "result":
        raise ValueError("runtime result type must be result")
    object_ids, unknown_ids = _result_object_ids(result.get("objects"))
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
        ranks = tuple(item.get("rank") for item in raw_top3)
        sku_ids = tuple(item.get("sku_id") for item in raw_top3)
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
        if any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 0.0 <= float(score) <= 1.0
            for score in scores
        ):
            raise ValueError("runtime result candidate Top3 scores are invalid")


def _result_object_ids(value: object) -> tuple[set[str], set[str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("runtime result objects must be a sequence")
    object_ids: set[str] = set()
    unknown_ids: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("runtime result objects must be mappings")
        object_id = item.get("object_id")
        if (
            not isinstance(object_id, str)
            or not object_id
            or object_id in object_ids
            or "sku_id" not in item
        ):
            raise ValueError("runtime result object identity is invalid")
        sku_id = item["sku_id"]
        if sku_id is not None and (
            isinstance(sku_id, bool) or not isinstance(sku_id, int)
        ):
            raise ValueError("runtime result object sku_id is invalid")
        object_ids.add(object_id)
        if sku_id is None:
            unknown_ids.add(object_id)
    return object_ids, unknown_ids


def _object_id_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"runtime result {field} must be a list")
    object_ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item in object_ids:
            raise ValueError(f"runtime result {field} is invalid")
        object_ids.append(item)
    return tuple(object_ids)


def encode_event(event: Mapping[str, object]) -> str:
    """Encode one event as deterministic UTF-8 JSON Lines text."""
    return json.dumps(
        event,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
