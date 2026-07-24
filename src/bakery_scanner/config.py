"""Validated, path-stable project configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CanonicalFrameConfig(_StrictModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DatasetSourceConfig(_StrictModel):
    name: str = Field(min_length=1)
    images: Path
    annotations: Path


class DatasetConfig(_StrictModel):
    sources: tuple[DatasetSourceConfig, ...] = Field(min_length=1)
    expected_images: int = Field(gt=0)
    expected_boxes: int = Field(gt=0)
    folds: int = Field(ge=2)

    @model_validator(mode="after")
    def _source_names_are_unique(self) -> "DatasetConfig":
        names = [source.name for source in self.sources]
        if len(names) != len(set(names)):
            raise ValueError("dataset source names must be unique")
        return self


class DetectorVariantConfig(_StrictModel):
    name: str = Field(min_length=1)
    backend: Literal["dfine", "rtmdet"]
    input_size: int = Field(gt=0)
    role: Literal["audit", "primary", "secondary"]


class DetectorsConfig(_StrictModel):
    seeds: tuple[int, ...] = Field(min_length=1)
    variants: tuple[DetectorVariantConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _variant_names_are_unique(self) -> "DetectorsConfig":
        names = [variant.name for variant in self.variants]
        if len(names) != len(set(names)):
            raise ValueError("detector variant names must be unique")
        return self


class RuntimeConfig(_StrictModel):
    device: Literal["CUDA:0"]
    precision: Literal["FP32"]
    proposal_limit: int = Field(gt=0)


class ScannerConfig(_StrictModel):
    seed: int
    artifact_root: Path
    canonical_frame: CanonicalFrameConfig
    dataset: DatasetConfig
    detectors: DetectorsConfig
    runtime: RuntimeConfig

    @field_validator("artifact_root")
    @classmethod
    def _artifact_root_is_relative_or_absolute(cls, value: Path) -> Path:
        if not str(value):
            raise ValueError("artifact_root must not be empty")
        return value

    @classmethod
    def load(cls, path: Path) -> "ScannerConfig":
        """Load YAML and resolve all configured paths relative to its file."""
        config_path = path.resolve()
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError("configuration root must be a mapping")

        base = config_path.parent
        payload = dict(payload)
        payload["artifact_root"] = _resolve_path(base, payload.get("artifact_root"))
        dataset = dict(payload.get("dataset") or {})
        dataset["sources"] = [
            {
                **dict(source),
                "images": _resolve_path(base, source.get("images")),
                "annotations": _resolve_path(base, source.get("annotations")),
            }
            for source in dataset.get("sources", [])
        ]
        payload["dataset"] = dataset
        return cls.model_validate(payload)


def _resolve_path(base: Path, raw: object) -> Path:
    if not isinstance(raw, (str, Path)) or not str(raw):
        raise ValueError("configured path must be a non-empty string")
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else base / candidate
