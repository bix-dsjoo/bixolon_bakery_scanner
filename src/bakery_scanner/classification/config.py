"""Strict, standalone configuration for classifier artifacts and policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PREPROCESS_SCHEMA_VERSION = 2


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepViTConfig(_StrictModel):
    artifact_id: Literal["repvit_m1_15plus5_v1"]
    checkpoint: Path
    checkpoint_sha256: str
    manifest: Path
    manifest_sha256: str
    prototype_bank: Path | None = None
    prototype_bank_sha256: str | None = None

    @field_validator("checkpoint_sha256", "manifest_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("must be a lowercase SHA-256 hash")
        return value

    @model_validator(mode="after")
    def _prototype_pair(self) -> "RepViTConfig":
        if (self.prototype_bank is None) != (self.prototype_bank_sha256 is None):
            raise ValueError("prototype_bank and prototype_bank_sha256 must be supplied together")
        if self.prototype_bank_sha256 is not None and not _SHA256.fullmatch(self.prototype_bank_sha256):
            raise ValueError("prototype_bank_sha256 must be a lowercase SHA-256 hash")
        return self


class DINOv3Config(_StrictModel):
    artifact_id: Literal["dinov3_vits16_15plus5_v1"]
    weights: Path
    weights_sha256: str
    support: Path
    support_sha256: str
    local_bank: Path | None = None
    local_bank_sha256: str | None = None

    @field_validator("weights_sha256", "support_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("must be a lowercase SHA-256 hash")
        return value

    @model_validator(mode="after")
    def _local_bank_pair(self) -> "DINOv3Config":
        if (self.local_bank is None) != (self.local_bank_sha256 is None):
            raise ValueError("local_bank and local_bank_sha256 must be supplied together")
        if self.local_bank_sha256 is not None and not _SHA256.fullmatch(self.local_bank_sha256):
            raise ValueError("local_bank_sha256 must be a lowercase SHA-256 hash")
        return self


class PreprocessConfig(_StrictModel):
    input_size: Literal[224]
    paddings: tuple[float, float, float]

    @model_validator(mode="after")
    def _paddings_are_canonical(self) -> "PreprocessConfig":
        if len(set(self.paddings)) != len(self.paddings):
            raise ValueError("paddings must be unique")
        if self.paddings != tuple(sorted(self.paddings)):
            raise ValueError("paddings must be in ascending order")
        if self.paddings != (0.05, 0.10, 0.15):
            raise ValueError("paddings must be 0.05, 0.10, 0.15")
        return self


def preprocess_sha256(config: PreprocessConfig) -> str:
    """Return the versioned identity of every score-affecting image transform."""
    payload = {
        "schema_version": _PREPROCESS_SCHEMA_VERSION,
        "canonical_frame": "exif_visual_rgb_v1",
        "crop_rule": "total_padding_split_floor_ceil_clip_rgb",
        "input_size": config.input_size,
        "paddings": list(config.paddings),
        "resize": "torchvision_resize_antialias_true",
        "normalization": {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ClassifierRuntimeConfig(_StrictModel):
    device: Literal["CPU", "CUDA:0"]
    precision: Literal["FP32"]


class CalibrationConfig(_StrictModel):
    artifact: Path
    artifact_sha256: str | None = None
    fusion_policy: Path | None = None
    fusion_policy_sha256: str | None = None

    @field_validator("artifact_sha256")
    @classmethod
    def _artifact_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256.fullmatch(value):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 hash")
        return value

    @model_validator(mode="after")
    def _fusion_policy_pair(self) -> "CalibrationConfig":
        if (self.fusion_policy is None) != (self.fusion_policy_sha256 is None):
            raise ValueError("fusion_policy and fusion_policy_sha256 must be supplied together")
        if self.fusion_policy_sha256 is not None and not _SHA256.fullmatch(self.fusion_policy_sha256):
            raise ValueError("fusion_policy_sha256 must be a lowercase SHA-256 hash")
        return self


class ClassifierConfig(_StrictModel):
    schema_version: Literal[1]
    repvit: RepViTConfig
    dinov3: DINOv3Config
    preprocess: PreprocessConfig
    runtime: ClassifierRuntimeConfig
    calibration: CalibrationConfig

    @classmethod
    def load(cls, path: Path) -> "ClassifierConfig":
        config_path = path.resolve()
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError("configuration root must be a mapping")
        base = config_path.parent
        payload = dict(payload)
        for section, names in {
            "repvit": ("checkpoint", "manifest", "prototype_bank"),
            "dinov3": ("weights", "support", "local_bank"),
            "calibration": ("artifact", "fusion_policy"),
        }.items():
            values = dict(payload.get(section) or {})
            for name in names:
                if values.get(name) is not None:
                    values[name] = _resolve_path(base, values.get(name))
            payload[section] = values
        result = cls.model_validate(payload)
        if "locked_acceptance" in result.calibration.artifact.parts:
            raise ValueError(
                "calibration artifact must not be inside locked acceptance directory"
            )
        return result


def _resolve_path(base: Path, raw: object) -> Path:
    if not isinstance(raw, (str, Path)) or not str(raw):
        raise ValueError("configured path must be a non-empty string")
    candidate = Path(raw)
    return (
        candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    )
