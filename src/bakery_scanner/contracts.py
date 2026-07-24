"""Strict immutable records shared across scanner pipeline stages."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any


class DetectorKind(str, Enum):
    DFINE = "dfine"
    RTMDET = "rtmdet"


class VerifierState(IntEnum):
    INVALID = 0
    EXACTLY_ONE = 1
    PARTIAL = 2
    MULTIPLE = 3


def _finite(value: float, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _positive_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: str, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True, slots=True, order=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))
        object.__setattr__(self, "width", _finite(self.width, "width"))
        object.__setattr__(self, "height", _finite(self.height, "height"))
        if self.width <= 0 or self.height <= 0:
            raise ValueError("box width and height must be positive")

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass(frozen=True, slots=True, order=True)
class SceneKey:
    capture_batch: str
    scene_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.capture_batch, str) or not self.capture_batch:
            raise ValueError("capture_batch must be non-empty")
        object.__setattr__(self, "scene_number", _positive_int(self.scene_number, "scene_number"))


@dataclass(frozen=True, slots=True)
class BreadProposal:
    image_id: int
    source: str
    score: float
    box: Box
    image_width: int
    image_height: int
    class_id: int = 1
    class_name: str = "bread"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", _positive_int(self.image_id, "image_id"))
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("source must be non-empty")
        score = _finite(self.score, "score")
        if not 0 <= score <= 1:
            raise ValueError("score must be in [0, 1]")
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "image_width", _positive_int(self.image_width, "image_width"))
        object.__setattr__(self, "image_height", _positive_int(self.image_height, "image_height"))
        if self.class_id != 1 or self.class_name != "bread":
            raise ValueError("bread proposals must use exact class 1/bread")
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        if self.box.x < 0 or self.box.y < 0 or self.box.x + self.box.width > self.image_width or self.box.y + self.box.height > self.image_height:
            raise ValueError("box must stay within source image bounds")


@dataclass(frozen=True, slots=True)
class VerifiedBreadBox:
    object_id: str
    box: Box
    score: float
    verifier_state: VerifierState
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not re.fullmatch(r"bread-\d{4}", self.object_id):
            raise ValueError("object_id must be formatted as bread-0001")
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        score = _finite(self.score, "score")
        if not 0 <= score <= 1:
            raise ValueError("score must be in [0, 1]")
        object.__setattr__(self, "score", score)
        if not isinstance(self.verifier_state, VerifierState):
            raise ValueError("verifier_state must be VerifierState")
        if self.verifier_state is not VerifierState.EXACTLY_ONE:
            raise ValueError("final boxes must be verified as exactly one bread")
        if not self.sources or any(not isinstance(source, str) or not source for source in self.sources):
            raise ValueError("sources must contain non-empty names")
        if tuple(sorted(self.sources)) != self.sources or len(set(self.sources)) != len(self.sources):
            raise ValueError("sources must be unique and canonically ordered")


@dataclass(frozen=True, slots=True)
class BoxSystemResult:
    source_id: str
    source_sha256: str
    boxes: tuple[VerifiedBreadBox, ...]
    audit_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be non-empty")
        object.__setattr__(self, "source_sha256", _sha256(self.source_sha256, "source_sha256"))
        # Accept sequence-like caller input only at the boundary, then freeze it.
        # This prevents a mutable list supplied by a caller from altering an
        # already-created result and its canonical JSON audit output.
        object.__setattr__(self, "boxes", tuple(self.boxes))
        if any(not isinstance(box, VerifiedBreadBox) for box in self.boxes):
            raise ValueError("boxes must contain VerifiedBreadBox values")
        expected_ids = tuple(f"bread-{index:04d}" for index in range(1, len(self.boxes) + 1))
        if tuple(box.object_id for box in self.boxes) != expected_ids:
            raise ValueError("boxes must have contiguous canonical object ids")
        coordinates = tuple((box.box.y, box.box.x, box.box.height, box.box.width) for box in self.boxes)
        if coordinates != tuple(sorted(coordinates)):
            raise ValueError("boxes must be sorted top-to-bottom then left-to-right")
        hashes = tuple(_sha256(value, "audit_hash") for value in self.audit_hashes)
        if hashes != tuple(sorted(hashes)) or len(set(hashes)) != len(hashes):
            raise ValueError("audit_hashes must be unique and canonically ordered")
        object.__setattr__(self, "audit_hashes", hashes)

    def to_json_bytes(self) -> bytes:
        payload = {
            "audit_hashes": list(self.audit_hashes),
            "boxes": [
                {
                    "box": {"height": box.box.height, "width": box.box.width, "x": box.box.x, "y": box.box.y},
                    "object_id": box.object_id,
                    "score": box.score,
                    "sources": list(box.sources),
                    "verifier_state": int(box.verifier_state),
                }
                for box in self.boxes
            ],
            "source_id": self.source_id,
            "source_sha256": self.source_sha256,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "BoxSystemResult":
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("result payload must be valid UTF-8 JSON") from exc
        _require_exact_keys(decoded, {"audit_hashes", "boxes", "source_id", "source_sha256"}, "result")
        if not isinstance(decoded["boxes"], list) or not isinstance(decoded["audit_hashes"], list):
            raise ValueError("boxes and audit_hashes must be arrays")
        boxes = tuple(_verified_box_from_dict(row) for row in decoded["boxes"])
        result = cls(
            source_id=decoded["source_id"],
            source_sha256=decoded["source_sha256"],
            boxes=boxes,
            audit_hashes=tuple(decoded["audit_hashes"]),
        )
        if result.to_json_bytes() != payload:
            raise ValueError("result payload is not canonical")
        return result


def _require_exact_keys(value: Any, expected: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{context} fields must be exactly {sorted(expected)}")


def _verified_box_from_dict(value: Any) -> VerifiedBreadBox:
    _require_exact_keys(value, {"box", "object_id", "score", "sources", "verifier_state"}, "box")
    _require_exact_keys(value["box"], {"height", "width", "x", "y"}, "box coordinates")
    if not isinstance(value["sources"], list):
        raise ValueError("box sources must be an array")
    try:
        state = VerifierState(value["verifier_state"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid verifier state") from exc
    coordinates = value["box"]
    return VerifiedBreadBox(
        object_id=value["object_id"],
        box=Box(coordinates["x"], coordinates["y"], coordinates["width"], coordinates["height"]),
        score=value["score"],
        verifier_state=state,
        sources=tuple(value["sources"]),
    )
