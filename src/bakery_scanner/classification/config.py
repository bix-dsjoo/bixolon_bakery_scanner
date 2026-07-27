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
_PREPROCESS_SCHEMA_VERSION = 1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepViTConfig(_StrictModel):
    artifact_id: Literal["repvit_m1_15plus5_v1"]
    checkpoint: Path
    checkpoint_sha256: str
    manifest: Path
    manifest_sha256: str

    @field_validator("checkpoint_sha256", "manifest_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("must be a lowercase SHA-256 hash")
        return value


class DINOv3Config(_StrictModel):
    artifact_id: Literal["dinov3_vits16_15plus5_v1"]
    weights: Path
    weights_sha256: str
    support: Path
    support_sha256: str

    @field_validator("weights_sha256", "support_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("must be a lowercase SHA-256 hash")
        return value


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
    device: Literal["CUDA:0"]
    precision: Literal["FP32"]


class CalibrationConfig(_StrictModel):
    artifact: Path


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
            "repvit": ("checkpoint", "manifest"),
            "dinov3": ("weights", "support"),
            "calibration": ("artifact",),
        }.items():
            values = dict(payload.get(section) or {})
            for name in names:
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
