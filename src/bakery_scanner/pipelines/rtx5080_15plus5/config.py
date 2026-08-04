"""Strict static configuration for the RTX 5080 candidate."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml


_STAGE_BUDGETS = {
    "decode_canonical": 10.0, "detector": 36.0, "completeness": 6.0,
    "crop": 4.0, "repvit": 12.0, "direct_gate": 2.0, "dinov3": 18.0,
    "fusion_payload": 6.0, "headroom": 8.0,
}
_LATENCY_PATHS = ("E", "M", "H", "overall", "dinov3", "needs_retake", "unknown", "count_1_2", "count_3_7", "count_8_plus")
_UTILITY_FLOORS = {
    "normal_scan_acceptance": {"overall": 0.80, "each": 0.70},
    "unnecessary_retake": {"overall": 0.20, "each": 0.30},
    "auto_sku_approval_coverage": {"overall": 0.70, "each": 0.60},
    "unknown_rate": {"overall": 0.30, "each": 0.40},
    "unknown_top3_recall": {"overall": 0.95, "each": 0.90},
}


@dataclass(frozen=True, slots=True)
class CandidateRuntimeConfig:
    device: str
    precision: str
    repvit_chunk_capacity_objects: int
    dinov3_chunk_capacity_objects: int
    p95_limit_ms: float
    stage_budgets_ms: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.device != "CUDA:0" or self.precision != "FP16":
            raise ValueError("candidate runtime must be CUDA:0 FP16")
        if self.repvit_chunk_capacity_objects != 7 or self.dinov3_chunk_capacity_objects != 7:
            raise ValueError("candidate chunk capacities must be seven objects")
        if _finite_float(self.p95_limit_ms, "p95_limit_ms") != 100.0:
            raise ValueError("candidate p95_limit_ms must be 100.0")
        if not isinstance(self.stage_budgets_ms, Mapping):
            raise ValueError("candidate stage_budgets_ms must be a mapping")
        budgets = _float_mapping(dict(self.stage_budgets_ms), "runtime.stage_budgets_ms")
        if budgets != _STAGE_BUDGETS:
            raise ValueError("candidate stage_budgets_ms must match the immutable static budget")
        object.__setattr__(self, "stage_budgets_ms", MappingProxyType(budgets))


@dataclass(frozen=True, slots=True)
class EvaluationConfig:
    iou_threshold: float
    seed: int
    fold_count: int
    role_counts: Mapping[str, int]
    utility_floors: Mapping[str, Mapping[str, float]]
    incremental_auto_sku_approval_coverage_floor: float
    counterfactual_completeness_block_rate: float
    latency_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if _finite_float(self.iou_threshold, "iou_threshold") != 0.50 or self.seed != 20260803 or self.fold_count != 5:
            raise ValueError("evaluation configuration has noncanonical static values")
        if not isinstance(self.role_counts, Mapping) or dict(self.role_counts) != {"train": 3, "calibration": 1, "evaluation": 1}:
            raise ValueError("evaluation configuration requires 3/1/1 fold roles")
        if not isinstance(self.utility_floors, Mapping):
            raise ValueError("evaluation configuration utility floors must be a mapping")
        floors = _nested_float_mapping(dict(self.utility_floors), "utility_floors")
        if floors != _UTILITY_FLOORS or _finite_float(self.incremental_auto_sku_approval_coverage_floor, "incremental coverage floor") != .5 or _finite_float(self.counterfactual_completeness_block_rate, "counterfactual completeness block rate") != 1.0 or self.latency_paths != _LATENCY_PATHS:
            raise ValueError("evaluation configuration has noncanonical static values")
        object.__setattr__(self, "role_counts", MappingProxyType(dict(self.role_counts)))
        object.__setattr__(self, "utility_floors", MappingProxyType({key: MappingProxyType(value) for key, value in floors.items()}))


@dataclass(frozen=True, slots=True)
class CandidateConfig:
    pipeline_id: str
    admission_manifest: Path
    evaluation_config: Path
    runtime: CandidateRuntimeConfig
    repvit_batch_size: int
    dinov3_batch_size: int
    fusion_margin: float
    evaluation: EvaluationConfig

    def __post_init__(self) -> None:
        if self.pipeline_id != "rtx5080_15plus5_single_frame_v1":
            raise ValueError("candidate pipeline_id must be rtx5080_15plus5_single_frame_v1")
        if not isinstance(self.admission_manifest, Path) or not isinstance(self.evaluation_config, Path):
            raise ValueError("candidate paths must be Path values")
        if not isinstance(self.runtime, CandidateRuntimeConfig) or not isinstance(self.evaluation, EvaluationConfig):
            raise ValueError("candidate nested configuration is invalid")
        self.runtime.__post_init__()
        self.evaluation.__post_init__()
        if self.repvit_batch_size != 14 or self.dinov3_batch_size != 7:
            raise ValueError("candidate static batch sizes must be RepViT 14 and DINOv3 7")
        if _finite_float(self.fusion_margin, "fusion_margin") != .85:
            raise ValueError("candidate fusion_margin must be 0.85")


def load_candidate_config(path: Path) -> CandidateConfig:
    """Load only the static profile; identity declarations are checked at admission."""
    config_path = Path(path).resolve()
    payload = _mapping(_load_yaml(config_path), "candidate configuration")
    _exact_keys(payload, {
        "schema_version", "pipeline_id", "admission_manifest", "evaluation_config", "runtime",
        "repvit_batch_size", "dinov3_batch_size", "fusion_margin",
    }, "candidate configuration")
    if payload["schema_version"] != 1:
        raise ValueError("candidate configuration schema_version must be 1")
    if payload["pipeline_id"] != "rtx5080_15plus5_single_frame_v1":
        raise ValueError("candidate pipeline_id must be rtx5080_15plus5_single_frame_v1")
    runtime = _load_runtime(_mapping(payload["runtime"], "runtime"))
    repvit_batch_size = _positive_int(payload["repvit_batch_size"], "repvit_batch_size")
    dinov3_batch_size = _positive_int(payload["dinov3_batch_size"], "dinov3_batch_size")
    if repvit_batch_size != 14 or dinov3_batch_size != 7:
        raise ValueError("candidate static batch sizes must be RepViT 14 and DINOv3 7")
    fusion_margin = _finite_float(payload["fusion_margin"], "fusion_margin")
    if fusion_margin != 0.85:
        raise ValueError("candidate fusion_margin must be 0.85")
    admission_manifest = _configured_path(config_path.parent, payload["admission_manifest"], "admission_manifest")
    evaluation_path = _configured_path(config_path.parent, payload["evaluation_config"], "evaluation_config")
    return CandidateConfig(
        pipeline_id=payload["pipeline_id"], admission_manifest=admission_manifest,
        evaluation_config=evaluation_path, runtime=runtime,
        repvit_batch_size=repvit_batch_size, dinov3_batch_size=dinov3_batch_size,
        fusion_margin=fusion_margin, evaluation=_load_evaluation(evaluation_path),
    )


def _load_runtime(payload: dict[str, object]) -> CandidateRuntimeConfig:
    _exact_keys(payload, {"device", "precision", "repvit_chunk_capacity_objects", "dinov3_chunk_capacity_objects", "p95_limit_ms", "stage_budgets_ms"}, "runtime")
    stage_budgets = _float_mapping(payload["stage_budgets_ms"], "runtime.stage_budgets_ms")
    if payload["device"] != "CUDA:0" or payload["precision"] != "FP16":
        raise ValueError("candidate runtime must be CUDA:0 FP16")
    if _positive_int(payload["repvit_chunk_capacity_objects"], "repvit_chunk_capacity_objects") != 7 or _positive_int(payload["dinov3_chunk_capacity_objects"], "dinov3_chunk_capacity_objects") != 7:
        raise ValueError("candidate chunk capacities must be seven objects")
    if _finite_float(payload["p95_limit_ms"], "p95_limit_ms") != 100.0:
        raise ValueError("candidate p95_limit_ms must be 100.0")
    if dict(stage_budgets) != _STAGE_BUDGETS:
        raise ValueError("candidate stage_budgets_ms must match the immutable static budget")
    return CandidateRuntimeConfig("CUDA:0", "FP16", 7, 7, 100.0, MappingProxyType(stage_budgets))


def _load_evaluation(path: Path) -> EvaluationConfig:
    payload = _mapping(_load_yaml(path), "evaluation configuration")
    _exact_keys(payload, {
        "schema_version", "iou_threshold", "seed", "fold_count", "role_counts", "utility_floors",
        "incremental_auto_sku_approval_coverage_floor", "counterfactual_completeness_block_rate", "latency_paths",
    }, "evaluation configuration")
    if payload["schema_version"] != 1 or _finite_float(payload["iou_threshold"], "iou_threshold") != 0.50:
        raise ValueError("evaluation configuration requires schema version 1 and IoU 0.50")
    if payload["seed"] != 20260803 or payload["fold_count"] != 5:
        raise ValueError("evaluation configuration requires seed 20260803 and five folds")
    roles = _int_mapping(payload["role_counts"], "role_counts")
    if roles != {"train": 3, "calibration": 1, "evaluation": 1}:
        raise ValueError("evaluation configuration requires 3/1/1 fold roles")
    floors = _nested_float_mapping(payload["utility_floors"], "utility_floors")
    if floors != _UTILITY_FLOORS:
        raise ValueError("evaluation configuration utility floors differ from the approved specification")
    incremental = _finite_float(payload["incremental_auto_sku_approval_coverage_floor"], "incremental coverage floor")
    counterfactual = _finite_float(payload["counterfactual_completeness_block_rate"], "counterfactual completeness block rate")
    if incremental != 0.50 or counterfactual != 1.0:
        raise ValueError("evaluation configuration requires approved incremental and completeness floors")
    paths = tuple(payload["latency_paths"]) if isinstance(payload["latency_paths"], list) else ()
    if paths != _LATENCY_PATHS:
        raise ValueError("evaluation configuration must declare all seven latency paths")
    return EvaluationConfig(0.5, 20260803, 5, MappingProxyType(roles), MappingProxyType({key: MappingProxyType(value) for key, value in floors.items()}), incremental, counterfactual, paths)


def _load_yaml(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"configuration file is missing: {path}") from exc


def _configured_path(base: Path, value: object, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty path")
    return (base / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return dict(value)


def _exact_keys(payload: dict[str, object], expected: set[str], name: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"{name} has unknown or missing fields")


def _positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _finite_float(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _float_mapping(value: object, name: str) -> dict[str, float]:
    raw = _mapping(value, name)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} keys must be strings")
    return {key: _finite_float(item, f"{name}.{key}") for key, item in raw.items()}


def _int_mapping(value: object, name: str) -> dict[str, int]:
    raw = _mapping(value, name)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} keys must be strings")
    return {key: _positive_int(item, f"{name}.{key}") for key, item in raw.items()}


def _nested_float_mapping(value: object, name: str) -> dict[str, dict[str, float]]:
    raw = _mapping(value, name)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} keys must be strings")
    return {key: _float_mapping(item, f"{name}.{key}") for key, item in raw.items()}
