"""Hash-bound evidence emitted by the exact runtime ranking path."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


_SKU_IDS = tuple(range(1, 21))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEYS = frozenset(
    {
        "sample_id", "capture_group", "registered", "sku_id", "role",
        "image_sha256", "repvit_values", "dinov3_values", "candidate_sku_ids",
        "local_values", "repvit_crop_disagreement", "nearest_prototype_distance",
        "local_product_patch_count", "local_product_patch_ratio",
        "repvit_artifact_id", "dinov3_artifact_id", "repvit_checkpoint_sha256",
        "repvit_manifest_sha256", "repvit_prototype_sha256", "dinov3_weights_sha256",
        "dinov3_support_sha256", "dinov3_local_bank_sha256", "preprocess_sha256",
        "scenario_schema_version", "scenarios",
    }
)


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _vector(value: object, field: str, *, probabilities: bool = False) -> tuple[float, ...]:
    if not isinstance(value, tuple) or len(value) != 20:
        raise ValueError(f"{field} must contain 20 scores")
    result = tuple(_finite(item, field) for item in value)
    if probabilities and any(not 0.0 <= item <= 1.0 for item in result):
        raise ValueError(f"{field} must contain probabilities")
    return result


@dataclass(frozen=True, slots=True)
class FullEvidenceRow:
    sample_id: str
    capture_group: str
    registered: bool
    sku_id: int | None
    role: Literal["development", "locked_acceptance"]
    image_sha256: str
    repvit_values: tuple[float, ...]
    dinov3_values: tuple[float, ...]
    candidate_sku_ids: tuple[int, ...]
    local_values: tuple[float, ...]
    repvit_crop_disagreement: float
    nearest_prototype_distance: float
    local_product_patch_count: int
    local_product_patch_ratio: float
    repvit_checkpoint_sha256: str
    repvit_manifest_sha256: str
    repvit_prototype_sha256: str
    dinov3_weights_sha256: str
    dinov3_support_sha256: str
    dinov3_local_bank_sha256: str
    preprocess_sha256: str
    repvit_artifact_id: str = "repvit_m1_15plus5_v1"
    dinov3_artifact_id: str = "dinov3_vits16_15plus5_v1"
    scenario_schema_version: int = 1
    scenarios: tuple[str, ...] = ("general",)

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        if not isinstance(self.capture_group, str) or not self.capture_group.strip():
            raise ValueError("capture_group must not be empty")
        if type(self.registered) is not bool:
            raise ValueError("registered must be a boolean")
        if self.role not in ("development", "locked_acceptance"):
            raise ValueError("role is invalid")
        if self.registered:
            if type(self.sku_id) is not int or self.sku_id not in _SKU_IDS:
                raise ValueError("registered evidence requires a canonical sku_id")
        elif self.sku_id is not None:
            raise ValueError("unregistered evidence must not have a sku_id")
        if not isinstance(self.image_sha256, str) or not _SHA256.fullmatch(self.image_sha256):
            raise ValueError("image_sha256 must be a lowercase SHA-256 hash")
        object.__setattr__(self, "repvit_values", _vector(self.repvit_values, "repvit_values", probabilities=True))
        object.__setattr__(self, "dinov3_values", _vector(self.dinov3_values, "dinov3_values"))
        candidates = tuple(self.candidate_sku_ids)
        if not 1 <= len(candidates) <= 8 or len(set(candidates)) != len(candidates) or any(type(sku_id) is not int or sku_id not in _SKU_IDS for sku_id in candidates):
            raise ValueError("candidate_sku_ids must contain one to eight unique canonical SKU IDs")
        object.__setattr__(self, "candidate_sku_ids", candidates)
        if not isinstance(self.local_values, tuple) or len(self.local_values) != len(candidates):
            raise ValueError("local_values must align with candidate_sku_ids")
        object.__setattr__(self, "local_values", tuple(_finite(value, "local_values") for value in self.local_values))
        disagreement = _finite(self.repvit_crop_disagreement, "repvit_crop_disagreement")
        distance = _finite(self.nearest_prototype_distance, "nearest_prototype_distance")
        ratio = _finite(self.local_product_patch_ratio, "local_product_patch_ratio")
        if not 0.0 <= disagreement <= 1.0 or not 0.0 <= distance <= 2.0 or not 0.0 <= ratio <= 1.0:
            raise ValueError("full evidence scalar is outside its valid range")
        if type(self.local_product_patch_count) is not int or self.local_product_patch_count <= 0:
            raise ValueError("local_product_patch_count must be positive")
        for field in (
            "repvit_checkpoint_sha256", "repvit_manifest_sha256", "repvit_prototype_sha256",
            "dinov3_weights_sha256", "dinov3_support_sha256", "dinov3_local_bank_sha256", "preprocess_sha256",
        ):
            if not isinstance(getattr(self, field), str) or not _SHA256.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be a lowercase SHA-256 hash")
        if self.repvit_artifact_id != "repvit_m1_15plus5_v1" or self.dinov3_artifact_id != "dinov3_vits16_15plus5_v1":
            raise ValueError("full evidence model artifact ID is invalid")
        if type(self.scenario_schema_version) is not int or self.scenario_schema_version != 1:
            raise ValueError("scenario_schema_version must be 1")
        if not isinstance(self.scenarios, tuple) or not self.scenarios or any(not isinstance(value, str) or not value for value in self.scenarios):
            raise ValueError("scenarios must be a non-empty tuple of names")

    def to_json_bytes(self) -> bytes:
        payload = asdict(self)
        for field in ("repvit_values", "dinov3_values", "candidate_sku_ids", "local_values", "scenarios"):
            payload[field] = list(payload[field])
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "FullEvidenceRow":
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("full evidence must be valid UTF-8 JSON") from exc
        if not isinstance(value, dict) or set(value) != _KEYS:
            raise ValueError("full evidence has missing or extra keys")
        try:
            result = cls(
                **{
                    **value,
                    "repvit_values": tuple(value["repvit_values"]),
                    "dinov3_values": tuple(value["dinov3_values"]),
                    "candidate_sku_ids": tuple(value["candidate_sku_ids"]),
                    "local_values": tuple(value["local_values"]),
                    "scenarios": tuple(value["scenarios"]),
                }
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("full evidence field types are invalid") from exc
        if result.to_json_bytes() != payload:
            raise ValueError("full evidence must use canonical JSON")
        return result


def load_full_evidence_rows(path: Path) -> tuple[FullEvidenceRow, ...]:
    """Load canonical JSONL evidence and preserve the one-row-per-sample rule."""
    rows: list[FullEvidenceRow] = []
    sample_ids: set[str] = set()
    try:
        lines = Path(path).read_bytes().splitlines()
    except OSError as exc:
        raise ValueError("full evidence file is not readable") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line:
            raise ValueError(f"line {line_number}: full evidence must not be empty")
        try:
            row = FullEvidenceRow.from_json_bytes(line)
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
        if row.sample_id in sample_ids:
            raise ValueError(f"line {line_number}: duplicate sample_id")
        sample_ids.add(row.sample_id)
        rows.append(row)
    if not rows:
        raise ValueError("full evidence file must contain at least one row")
    return tuple(rows)
