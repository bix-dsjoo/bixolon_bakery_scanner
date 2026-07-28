"""Immutable contracts at the SKU-aware end-to-end boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bakery_scanner.contracts import Box

_SKU_IDS = frozenset(range(1, 21))
_SKU_PATHS = frozenset(("repvit_direct", "dinov3_confirmed", "fusion_ranked"))


def _require_sku_id(value: int, *, field: str) -> None:
    if type(value) is not int or value not in _SKU_IDS:
        raise ValueError(f"{field} must be an integer SKU ID from 1 through 20")


@dataclass(frozen=True, slots=True)
class SkuGroundTruth:
    """One registered SKU box in the original visual image coordinate system."""

    image_id: int
    box: Box
    sku_id: int

    def __post_init__(self) -> None:
        if type(self.image_id) is not int or self.image_id <= 0:
            raise ValueError("image_id must be a positive integer")
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        _require_sku_id(self.sku_id, field="sku_id")


@dataclass(frozen=True, slots=True)
class FinalObject:
    """A final E2E object after resolution and optional SKU classification."""

    box: Box
    sku_id: int | None
    confidence: float
    decision_path: str
    top3: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite in [0, 1]")
        object.__setattr__(self, "confidence", confidence)
        top3 = tuple(self.top3)
        if self.sku_id is None:
            if self.decision_path == "unknown_top3":
                if len(top3) != 3 or len(set(top3)) != 3:
                    raise ValueError("classifier Unknown requires three distinct ranked SKUs")
                for sku_id in top3:
                    _require_sku_id(sku_id, field="top3 SKU")
            elif self.decision_path == "assurance_unknown":
                if top3:
                    raise ValueError("assurance Unknown must not invent classifier Top-3 evidence")
            else:
                raise ValueError("Unknown decision requires a recognized unknown path")
        else:
            _require_sku_id(self.sku_id, field="sku_id")
            if self.decision_path not in _SKU_PATHS or top3:
                raise ValueError("SKU decision requires a SKU decision path and no Top-3")
        object.__setattr__(self, "top3", top3)
