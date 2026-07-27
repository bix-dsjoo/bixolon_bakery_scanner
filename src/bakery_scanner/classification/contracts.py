"""Immutable records shared by all classifier pipeline stages."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from bakery_scanner.contracts import Box


_SKU_IDS = tuple(range(1, 21))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DecisionPath(str, Enum):
    REPVIT_DIRECT = "repvit_direct"
    DINOV3_CONFIRMED = "dinov3_confirmed"
    UNKNOWN_TOP3 = "unknown_top3"


def _require_finite(value: float, field: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")


def _require_sku_id(sku_id: int, field: str = "sku_id") -> None:
    if sku_id not in _SKU_IDS:
        raise ValueError(f"{field} must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class ModelScoreVector:
    model_id: str
    sku_ids: tuple[int, ...]
    values: tuple[float, ...]
    score_kind: Literal["probability", "similarity"]

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must not be empty")
        if self.sku_ids != _SKU_IDS:
            raise ValueError("sku_ids must contain all 20 SKU IDs in canonical order")
        if len(self.values) != len(_SKU_IDS):
            raise ValueError("values must contain one score for each SKU ID")
        if self.score_kind not in ("probability", "similarity"):
            raise ValueError("score_kind must be probability or similarity")
        for value in self.values:
            _require_finite(value, "score")
            if self.score_kind == "probability" and not 0.0 <= value <= 1.0:
                raise ValueError("probability scores must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SkuCandidate:
    rank: int
    sku_id: int
    score: float

    def __post_init__(self) -> None:
        if self.rank not in (1, 2, 3):
            raise ValueError("rank must be 1, 2, or 3")
        _require_sku_id(self.sku_id)
        _require_finite(self.score, "score")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    repvit_artifact_id: str
    repvit_sha256: str
    dinov3_artifact_id: str
    dinov3_sha256: str
    dinov3_support_sha256: str
    calibration_id: str
    calibration_sha256: str
    preprocess_sha256: str = "0" * 64
    repvit_manifest_sha256: str = "0" * 64
    failure_code: str | None = None

    def __post_init__(self) -> None:
        for field in ("repvit_artifact_id", "dinov3_artifact_id", "calibration_id"):
            if not getattr(self, field):
                raise ValueError(f"{field} must not be empty")
        for field in (
            "repvit_sha256",
            "dinov3_sha256",
            "dinov3_support_sha256",
            "calibration_sha256",
            "preprocess_sha256",
            "repvit_manifest_sha256",
        ):
            if not _SHA256.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be a lowercase SHA-256 hash")


@dataclass(frozen=True, slots=True)
class StageTimings:
    repvit_ms: float
    dinov3_ms: float
    total_ms: float

    def __post_init__(self) -> None:
        for field in ("repvit_ms", "dinov3_ms", "total_ms"):
            value = getattr(self, field)
            _require_finite(value, field)
            if value < 0.0:
                raise ValueError(f"{field} must not be negative")


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    decision: Literal["sku", "unknown"]
    sku_id: int | None
    confidence: float
    box: Box
    decision_path: DecisionPath
    top3: tuple[SkuCandidate, ...]
    provenance: ModelProvenance
    timings: StageTimings

    def __post_init__(self) -> None:
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        if self.box.x < 0.0 or self.box.y < 0.0:
            raise ValueError("box coordinates must be non-negative")
        _require_finite(self.confidence, "confidence")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.decision == "sku":
            if self.sku_id is None:
                raise ValueError("sku decision requires sku_id")
            _require_sku_id(self.sku_id)
            if self.decision_path not in (
                DecisionPath.REPVIT_DIRECT,
                DecisionPath.DINOV3_CONFIRMED,
            ):
                raise ValueError("sku decision requires a SKU decision path")
            if self.top3:
                raise ValueError("sku decision must not include top3 candidates")
        elif self.decision == "unknown":
            if self.sku_id is not None:
                raise ValueError("unknown decision must not include sku_id")
            if self.decision_path is not DecisionPath.UNKNOWN_TOP3:
                raise ValueError("unknown decision requires unknown_top3 path")
            if (
                len(self.top3) != 3
                or {candidate.sku_id for candidate in self.top3}.__len__() != 3
            ):
                raise ValueError("unknown decision requires three unique candidates")
            if tuple(candidate.rank for candidate in self.top3) != (1, 2, 3):
                raise ValueError("unknown candidates must have ranks 1, 2, 3")
        else:
            raise ValueError("decision must be sku or unknown")

    def to_json_bytes(self) -> bytes:
        """Return deterministic UTF-8 JSON safe for result persistence."""
        payload = {
            "box": list(self.box.xyxy),
            "confidence": self.confidence,
            "decision": self.decision,
            "decision_path": self.decision_path.value,
            "provenance": {
                "calibration_id": self.provenance.calibration_id,
                "calibration_sha256": self.provenance.calibration_sha256,
                "dinov3_artifact_id": self.provenance.dinov3_artifact_id,
                "dinov3_sha256": self.provenance.dinov3_sha256,
                "dinov3_support_sha256": self.provenance.dinov3_support_sha256,
                "failure_code": self.provenance.failure_code,
                "preprocess_sha256": self.provenance.preprocess_sha256,
                "repvit_manifest_sha256": self.provenance.repvit_manifest_sha256,
                "repvit_artifact_id": self.provenance.repvit_artifact_id,
                "repvit_sha256": self.provenance.repvit_sha256,
            },
            "sku_id": self.sku_id,
            "timings": {
                "dinov3_ms": self.timings.dinov3_ms,
                "repvit_ms": self.timings.repvit_ms,
                "total_ms": self.timings.total_ms,
            },
            "top3": [
                {
                    "rank": candidate.rank,
                    "score": candidate.score,
                    "sku_id": candidate.sku_id,
                }
                for candidate in self.top3
            ],
        }
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
