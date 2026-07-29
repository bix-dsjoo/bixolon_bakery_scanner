"""Strict JSON Lines protocol for the camera evaluation worker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, TypeAlias


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


def encode_event(event: Mapping[str, object]) -> str:
    """Encode one event as deterministic UTF-8 JSON Lines text."""
    return json.dumps(
        event,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
