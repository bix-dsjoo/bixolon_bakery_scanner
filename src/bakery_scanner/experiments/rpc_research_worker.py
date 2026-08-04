"""External-only, deterministic oracle feature extraction for RPC research."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from numbers import Real
from typing import Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image, ImageOps

from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.experiments.rpc_manifest import (
    RpcImage,
    RpcIndex,
    canonical_json_bytes,
    write_new_json,
)


_DINO_SHA256 = "08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d"
_REPVIT_SHA256 = "217aca2b9a9149ebbab4faac93719036a227fd2fbde623cd51f780f49b7610a4"
_FEATURE_DIMENSION = 384
_DINO_PATCH_COUNT = 196
_CANONICAL_FRAME = "exif_visual_rgb_v1"
_RESEARCH_RUNS_ROOT = Path(r"C:\workspace\rpc_fewshot_runs")
_RPC_CATEGORY_IDS = tuple(range(1, 201))
_M0_BASE_SHOTS = 150
_M0_TRAINING_STEPS = 40
_M0_LEARNING_RATE = 0.1
_M2_KERNEL_SCALE = 1.0
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRAIN_CAPTURE_SOURCE = re.compile(
    r"^train2019:[0-9]+:(?P<product>.+)_camera(?P<camera>[0-9]+)-(?P<side>[^_]+)\.jpg$"
)


@dataclass(frozen=True, slots=True)
class ResearchArtifacts:
    """The two independently hash-verified research backbone artifacts."""

    repvit_path: Path
    dino_path: Path
    repvit_sha256: str
    dino_sha256: str

    @classmethod
    def from_paths(cls, repvit_path: Path, dino_path: Path) -> "ResearchArtifacts":
        repvit = Path(repvit_path)
        dino = Path(dino_path)
        # DINO first makes a missing or substituted DINO checkpoint fail closed
        # before a caller can use any partially accepted artifact bundle.
        dino_digest = _sha256_file(dino)
        if dino_digest != _DINO_SHA256:
            raise ValueError("DINOv3 SHA-256 mismatch")
        repvit_digest = _sha256_file(repvit)
        if repvit_digest != _REPVIT_SHA256:
            raise ValueError("RepViT SHA-256 mismatch")
        return cls(repvit.resolve(), dino.resolve(), repvit_digest, dino_digest)


@dataclass(frozen=True, slots=True)
class OracleFeatureRow:
    """One COCO oracle annotation whose features are source-bound."""

    source_identity: str
    annotation_id: int
    category_id: int
    bbox_xywh: tuple[float, float, float, float]
    difficulty: str
    source_byte_size: int | None = None
    source_sha256: str | None = None
    dino_global: tuple[float, ...] | None = None
    capture_stratum: str | None = None
    feature_array_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, str) or not self.source_identity:
            raise ValueError("source identity must be non-empty")
        if type(self.annotation_id) is not int or self.annotation_id < 0:
            raise ValueError("annotation ID must be non-negative")
        if type(self.category_id) is not int or self.category_id <= 0:
            raise ValueError("category ID must be positive")
        if not isinstance(self.difficulty, str) or len(self.difficulty) != 1:
            raise ValueError("difficulty must be one character")
        values = tuple(float(value) for value in self.bbox_xywh)
        if len(values) != 4 or not all(math.isfinite(value) for value in values):
            raise ValueError("oracle bbox must contain four finite coordinates")
        if values[2] <= 0.0 or values[3] <= 0.0:
            raise ValueError("oracle bbox must have positive width and height")
        object.__setattr__(self, "bbox_xywh", values)
        if self.source_byte_size is not None and (
            type(self.source_byte_size) is not int or self.source_byte_size <= 0
        ):
            raise ValueError("source byte size must be positive")
        if self.source_sha256 is not None and (
            not isinstance(self.source_sha256, str) or _SHA256.fullmatch(self.source_sha256) is None
        ):
            raise ValueError("source SHA-256 must be lowercase SHA-256")
        if self.capture_stratum is not None and (
            not isinstance(self.capture_stratum, str) or not self.capture_stratum
        ):
            raise ValueError("capture stratum must be non-empty")
        if self.feature_array_sha256 is not None and (
            not isinstance(self.feature_array_sha256, str)
            or _SHA256.fullmatch(self.feature_array_sha256) is None
        ):
            raise ValueError("feature-array SHA-256 must be lowercase SHA-256")
        if self.dino_global is not None:
            if isinstance(self.dino_global, (str, bytes)):
                raise ValueError("DINO global feature must be a finite numeric vector")
            values = tuple(self.dino_global)
            if (
                not values
                or len(values) != _FEATURE_DIMENSION
                or any(isinstance(value, bool) or not isinstance(value, Real) for value in values)
                or not all(math.isfinite(float(value)) for value in values)
            ):
                raise ValueError("DINO global feature must have dimension 384 and finite numeric values")
            object.__setattr__(self, "dino_global", tuple(float(value) for value in values))

    @property
    def identity(self) -> str:
        return f"{self.source_identity}:{self.annotation_id}"


@dataclass(frozen=True, slots=True)
class SupportExample:
    """One selected, source- and feature-array-bound oracle support example."""

    source_identity: str
    annotation_id: int
    category_id: int
    source_byte_size: int
    source_sha256: str
    dino_global: tuple[float, ...]
    capture_stratum: str
    feature_array_sha256: str


@dataclass(frozen=True, slots=True)
class SupportBank:
    """A class-complete immutable support order with only prefix access."""

    selector: str
    seed: int
    maximum_shots: int
    class_orders: tuple[tuple[SupportExample, ...], ...]
    feature_array_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if self.selector not in {"rnd", "div"}:
            raise ValueError("unsupported support selector")
        if type(self.seed) is not int:
            raise ValueError("support seed must be an integer")
        if type(self.maximum_shots) is not int or self.maximum_shots <= 0:
            raise ValueError("maximum shots must be positive")
        if not self.class_orders:
            raise ValueError("support bank requires complete class orders")
        categories: list[int] = []
        for order in self.class_orders:
            if len(order) < self.maximum_shots:
                raise ValueError("insufficient support candidates")
            category_ids = {example.category_id for example in order}
            if len(category_ids) != 1:
                raise ValueError("support order must contain one class")
            categories.append(next(iter(category_ids)))
        if categories != sorted(categories) or len(categories) != len(set(categories)):
            raise ValueError("support bank classes must be unique and sorted")
        identities = [example.source_identity for order in self.class_orders for example in order]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate source identity")
        if not isinstance(self.feature_array_sha256, str) or _SHA256.fullmatch(self.feature_array_sha256) is None:
            raise ValueError("feature-array SHA-256 must be lowercase SHA-256")
        if self.sha256 != _support_bank_digest(
            self.selector, self.seed, self.maximum_shots, self.class_orders, self.feature_array_sha256
        ):
            raise ValueError("support bank SHA-256 mismatch")

    @property
    def ordered_support_identities(self) -> tuple[tuple[int, tuple[str, ...]], ...]:
        """Record every materialized candidate identity, not a resampled draw."""
        return tuple(
            (order[0].category_id, tuple(example.source_identity for example in order))
            for order in self.class_orders
        )

    @property
    def feature_array_digest(self) -> str:
        """Compatibility-neutral name for the bound DINO-global array SHA-256."""
        return self.feature_array_sha256

    def prefix(self, shot_count: int) -> tuple[SupportExample, ...]:
        """Return the class-complete prefix without extending or resampling the bank."""
        if type(shot_count) is not int or shot_count <= 0:
            raise ValueError("shot count must be positive")
        if shot_count > self.maximum_shots:
            raise ValueError("non-prefix support extension is not allowed")
        return tuple(
            order[rank]
            for rank in range(shot_count)
            for order in self.class_orders
        )


@dataclass(frozen=True, slots=True)
class FeatureProvenance:
    """Immutable source and Task-1 array identities for one scoring feature."""

    source_identity: str
    annotation_id: int
    source_sha256: str
    repvit_global_array_sha256: str
    dinov3_global_array_sha256: str
    dinov3_patches_array_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, str) or not self.source_identity:
            raise ValueError("feature source identity must be non-empty")
        if type(self.annotation_id) is not int or self.annotation_id < 0:
            raise ValueError("feature annotation ID must be non-negative")
        for name in (
            "source_sha256",
            "repvit_global_array_sha256",
            "dinov3_global_array_sha256",
            "dinov3_patches_array_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class FeatureExample:
    """One source-bound feature bundle shared by all research score branches."""

    category_id: int
    provenance: FeatureProvenance
    repvit_global: tuple[float, ...]
    dinov3_global: tuple[float, ...]
    dinov3_patches: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if type(self.category_id) is not int or self.category_id <= 0:
            raise ValueError("feature category ID must be positive")
        if not isinstance(self.provenance, FeatureProvenance):
            raise ValueError("feature provenance must be FeatureProvenance")
        object.__setattr__(self, "repvit_global", _feature_vector(self.repvit_global, "RepViT global feature"))
        object.__setattr__(self, "dinov3_global", _feature_vector(self.dinov3_global, "DINO global feature"))
        patches = tuple(
            _feature_vector(patch, "DINO local patch feature") for patch in self.dinov3_patches
        )
        if not patches:
            raise ValueError("DINO local patch features must not be empty")
        object.__setattr__(self, "dinov3_patches", patches)


@dataclass(frozen=True, slots=True)
class ScoreProvenance:
    """The query and exact support provenance behind one branch prediction."""

    method: str
    query: FeatureProvenance
    repvit_support: tuple[FeatureProvenance, ...]
    dinov3_support: tuple[FeatureProvenance, ...]

    def __post_init__(self) -> None:
        if self.method not in {"m0", "m1", "m2"}:
            raise ValueError("unsupported research scoring method")
        if not isinstance(self.query, FeatureProvenance):
            raise ValueError("query provenance must be FeatureProvenance")
        for name in ("repvit_support", "dinov3_support"):
            supports = tuple(getattr(self, name))
            if not supports or not all(isinstance(item, FeatureProvenance) for item in supports):
                raise ValueError(f"{name} must contain feature provenance")
            object.__setattr__(self, name, supports)


@dataclass(frozen=True, slots=True)
class BranchPrediction:
    """Three score vectors in the one immutable RPC 200-class catalog order."""

    score_category_ids: tuple[int, ...]
    repvit_global_scores: tuple[float, ...]
    dinov3_global_scores: tuple[float, ...]
    dinov3_local_scores: tuple[float, ...]
    provenance: ScoreProvenance

    def __post_init__(self) -> None:
        if tuple(self.score_category_ids) != _RPC_CATEGORY_IDS:
            raise ValueError("scores must use the sorted registered 200-class catalog")
        for name in ("repvit_global_scores", "dinov3_global_scores", "dinov3_local_scores"):
            scores = tuple(float(value) for value in getattr(self, name))
            if len(scores) != len(_RPC_CATEGORY_IDS) or not all(math.isfinite(value) for value in scores):
                raise ValueError(f"{name} must contain 200 finite scores")
            object.__setattr__(self, name, scores)
        if not isinstance(self.provenance, ScoreProvenance):
            raise ValueError("prediction provenance must be ScoreProvenance")

    @property
    def repvit_top1(self) -> int:
        return _top1_category(self.repvit_global_scores)

    @property
    def dinov3_global_top1(self) -> int:
        return _top1_category(self.dinov3_global_scores)

    @property
    def dinov3_local_top1(self) -> int:
        return _top1_category(self.dinov3_local_scores)

    @property
    def repvit_scores(self) -> dict[int, float]:
        """Compatibility-friendly RepViT score lookup keyed by category ID."""
        return dict(zip(self.score_category_ids, self.repvit_global_scores, strict=True))

    @property
    def dino_scores(self) -> dict[int, float]:
        """Compatibility-friendly DINO global score lookup keyed by category ID."""
        return dict(zip(self.score_category_ids, self.dinov3_global_scores, strict=True))

    @property
    def dino_local_scores(self) -> dict[int, float]:
        """Compatibility-friendly DINO local score lookup keyed by category ID."""
        return dict(zip(self.score_category_ids, self.dinov3_local_scores, strict=True))


@dataclass(frozen=True, slots=True)
class LinearHead:
    """M0's immutable base rows and fixed-recipe novel rows plus DINO means."""

    base_category_ids: tuple[int, ...]
    novel_category_ids: tuple[int, ...]
    base_rows: torch.Tensor
    novel_rows: torch.Tensor
    dinov3_global_prototypes: torch.Tensor
    dinov3_local_prototypes: torch.Tensor
    support_provenance: tuple[FeatureProvenance, ...]

    def score(self, query: FeatureExample) -> BranchPrediction:
        """Emit M0's three branch score vectors for a source-disjoint query."""
        _validate_query_against_support(query, self.support_provenance)
        repvit_rows = _catalog_rows(
            self.base_category_ids, self.base_rows, self.novel_category_ids, self.novel_rows
        )
        query_repvit = _unit_tensor(query.repvit_global, "query RepViT global feature")
        query_dino = _unit_tensor(query.dinov3_global, "query DINO global feature")
        query_patches = _unit_patch_tensor(query.dinov3_patches, "query DINO local patch features")
        return _prediction(
            "m0",
            query,
            self.support_provenance,
            self.support_provenance,
            torch.mv(repvit_rows, query_repvit),
            torch.mv(self.dinov3_global_prototypes, query_dino),
            (query_patches @ self.dinov3_local_prototypes.T).mean(dim=0),
        )


def score_m1(
    repvit_support: Mapping[int, Sequence[FeatureExample]],
    dino_support: Mapping[int, Sequence[FeatureExample]],
    query: FeatureExample,
) -> BranchPrediction:
    """Score frozen, independently normalized class means for all 200 RPC SKUs."""
    repvit = _validated_supports(repvit_support, "RepViT")
    dino = _validated_supports(dino_support, "DINO")
    _validate_matching_support_provenance(repvit, dino)
    repvit_provenance = _flatten_provenance(repvit)
    dino_provenance = _flatten_provenance(dino)
    _validate_query_against_support(query, (*repvit_provenance, *dino_provenance))
    repvit_prototypes = _mean_prototypes(repvit, "repvit_global")
    dino_prototypes = _mean_prototypes(dino, "dinov3_global")
    local_prototypes = _mean_local_prototypes(dino)
    return _prediction(
        "m1",
        query,
        repvit_provenance,
        dino_provenance,
        torch.mv(repvit_prototypes, _unit_tensor(query.repvit_global, "query RepViT global feature")),
        torch.mv(dino_prototypes, _unit_tensor(query.dinov3_global, "query DINO global feature")),
        (_unit_patch_tensor(query.dinov3_patches, "query DINO local patch features") @ local_prototypes.T).mean(dim=0),
    )


def score_m2(
    repvit_cache: Mapping[int, Sequence[FeatureExample]],
    dino_cache: Mapping[int, Sequence[FeatureExample]],
    query: FeatureExample,
) -> BranchPrediction:
    """Score class-normalized frozen exemplar kernels for all 200 RPC SKUs."""
    repvit = _validated_supports(repvit_cache, "RepViT")
    dino = _validated_supports(dino_cache, "DINO")
    _validate_matching_support_provenance(repvit, dino)
    repvit_provenance = _flatten_provenance(repvit)
    dino_provenance = _flatten_provenance(dino)
    _validate_query_against_support(query, (*repvit_provenance, *dino_provenance))
    return _prediction(
        "m2",
        query,
        repvit_provenance,
        dino_provenance,
        _cache_scores(repvit, "repvit_global", _unit_tensor(query.repvit_global, "query RepViT global feature")),
        _cache_scores(dino, "dinov3_global", _unit_tensor(query.dinov3_global, "query DINO global feature")),
        _local_cache_scores(dino, _unit_patch_tensor(query.dinov3_patches, "query DINO local patch features")),
    )


def fit_m0_base_rows_from_embeddings(
    category_ids: Sequence[int], repvit_embeddings: torch.Tensor
) -> torch.Tensor:
    """Fit an immutable M0 base head from one CPU, balanced feature matrix."""
    categories = tuple(category_ids)
    if (
        not isinstance(repvit_embeddings, torch.Tensor)
        or repvit_embeddings.device.type != "cpu"
        or repvit_embeddings.ndim != 2
        or repvit_embeddings.shape != (len(categories), _FEATURE_DIMENSION)
        or not repvit_embeddings.is_floating_point()
    ):
        raise ValueError("M0 base embeddings must be a CPU floating-point [N, 384] tensor")
    if len(categories) != 160 * _M0_BASE_SHOTS:
        raise ValueError(
            f"M0 base classes must contain exactly {_M0_BASE_SHOTS} support examples"
        )
    if (
        any(type(category_id) is not int or category_id not in _RPC_CATEGORY_IDS for category_id in categories)
        or not torch.isfinite(repvit_embeddings).all().item()
        or (torch.linalg.vector_norm(repvit_embeddings, dim=1) == 0).any().item()
    ):
        raise ValueError("M0 base embeddings must be finite and have non-zero length")
    ordered_categories = tuple(sorted(set(categories)))
    if len(ordered_categories) != 160 or any(categories.count(category_id) != _M0_BASE_SHOTS for category_id in ordered_categories):
        raise ValueError(
            f"M0 base classes must contain exactly {_M0_BASE_SHOTS} support examples"
        )
    values = functional.normalize(repvit_embeddings.detach().to(dtype=torch.float32), dim=1)
    rows = torch.stack(
        [functional.normalize(values[[index for index, value in enumerate(categories) if value == category_id]].mean(dim=0), dim=0)
         for category_id in ordered_categories]
    ).detach().clone()
    rows.requires_grad_(True)
    category_to_index = {category_id: index for index, category_id in enumerate(ordered_categories)}
    targets = torch.tensor([category_to_index[category_id] for category_id in categories], dtype=torch.long)
    weights = torch.tensor([1.0 / _M0_BASE_SHOTS] * len(categories), dtype=torch.float32)
    optimizer = torch.optim.SGD((rows,), lr=_M0_LEARNING_RATE)
    for _ in range(_M0_TRAINING_STEPS):
        optimizer.zero_grad(set_to_none=True)
        losses = functional.cross_entropy(values @ rows.T, targets, reduction="none")
        (losses * weights).sum().div(weights.sum()).backward()
        optimizer.step()
    return rows.detach().clone().contiguous()


def fit_m0_base_rows(base_features: Sequence[FeatureExample]) -> torch.Tensor:
    """Train one deterministic frozen RepViT head for a 160-SKU base fold.

    The caller persists this tensor before any novel support is selected.  It
    deliberately has no seed or novel input: all base classes use their fixed,
    balanced 150-shot training set and subsequent ``fit_m0_head`` calls cannot
    update these rows.
    """
    rows: list[FeatureExample] = []
    seen: set[tuple[str, int]] = set()
    for feature in base_features:
        if not isinstance(feature, FeatureExample):
            raise ValueError("M0 base features must be FeatureExample values")
        if feature.category_id not in _RPC_CATEGORY_IDS:
            raise ValueError("M0 base features use an unregistered category")
        identity = (feature.provenance.source_identity, feature.provenance.annotation_id)
        if identity in seen:
            raise ValueError("M0 base support provenance contains duplicate examples")
        seen.add(identity)
        rows.append(feature)
    return fit_m0_base_rows_from_embeddings(
        tuple(feature.category_id for feature in rows),
        torch.tensor([feature.repvit_global for feature in rows], dtype=torch.float32),
    )


def fit_m0_head(
    base_features: Sequence[FeatureExample],
    novel_features: Sequence[FeatureExample],
    frozen_base_rows: torch.Tensor,
) -> LinearHead:
    """Fit only M0 novel rows with deterministic class-balanced frozen features."""
    base, novel = _validated_m0_training_features(base_features, novel_features)
    if not isinstance(frozen_base_rows, torch.Tensor) or frozen_base_rows.ndim != 2:
        raise ValueError("frozen base rows must be a two-dimensional tensor")
    if (
        frozen_base_rows.shape != (len(base), _FEATURE_DIMENSION)
        or not frozen_base_rows.is_floating_point()
        or not torch.isfinite(frozen_base_rows).all().item()
    ):
        raise ValueError("frozen base rows must match sorted base classes and feature dimension 384")
    base_rows = frozen_base_rows.detach().clone().contiguous()
    base_rows.requires_grad_(False)
    novel_rows = _mean_prototypes(novel, "repvit_global", tuple(novel)).detach().clone().requires_grad_(True)
    base_categories = tuple(base)
    novel_categories = tuple(novel)
    training_vectors, training_targets, training_weights = _m0_training_batch(novel, base_categories, novel_categories)
    optimizer = torch.optim.SGD((novel_rows,), lr=_M0_LEARNING_RATE)
    for _ in range(_M0_TRAINING_STEPS):
        optimizer.zero_grad(set_to_none=True)
        rows = _catalog_rows(base_categories, base_rows.detach(), novel_categories, novel_rows)
        logits = training_vectors @ rows.T
        losses = functional.cross_entropy(logits, training_targets, reduction="none")
        (losses * training_weights).sum().div(training_weights.sum()).backward()
        optimizer.step()
    trained_novel_rows = novel_rows.detach().clone().contiguous()
    combined = {**base, **novel}
    support_provenance = _flatten_provenance(combined)
    return LinearHead(
        base_categories,
        novel_categories,
        base_rows,
        trained_novel_rows,
        _mean_prototypes(combined, "dinov3_global"),
        _mean_local_prototypes(combined),
        support_provenance,
    )


def _feature_vector(values: Sequence[float], label: str) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    if len(vector) != _FEATURE_DIMENSION or not all(math.isfinite(value) for value in vector):
        raise ValueError(f"{label} must contain 384 finite values")
    if not any(vector):
        raise ValueError(f"{label} must have non-zero length")
    return vector


def _unit_tensor(values: Sequence[float], label: str) -> torch.Tensor:
    vector = torch.tensor(_feature_vector(values, label), dtype=torch.float32)
    return functional.normalize(vector, dim=0)


def _unit_patch_tensor(values: Sequence[Sequence[float]], label: str) -> torch.Tensor:
    patches = tuple(_feature_vector(item, label) for item in values)
    if not patches:
        raise ValueError(f"{label} must not be empty")
    return functional.normalize(torch.tensor(patches, dtype=torch.float32), dim=1)


def _validated_supports(
    supports: Mapping[int, Sequence[FeatureExample]], label: str
) -> dict[int, tuple[FeatureExample, ...]]:
    if not isinstance(supports, Mapping) or set(supports) != set(_RPC_CATEGORY_IDS):
        raise ValueError("supports must cover the registered 200-class catalog")
    validated: dict[int, tuple[FeatureExample, ...]] = {}
    identities: set[tuple[str, int]] = set()
    for category_id in _RPC_CATEGORY_IDS:
        examples = tuple(supports[category_id])
        if not examples or any(not isinstance(item, FeatureExample) or item.category_id != category_id for item in examples):
            raise ValueError(f"{label} support class is malformed")
        for item in examples:
            identity = (item.provenance.source_identity, item.provenance.annotation_id)
            if identity in identities:
                raise ValueError("support provenance contains a duplicate example")
            identities.add(identity)
        validated[category_id] = examples
    return validated


def _flatten_provenance(supports: Mapping[int, Sequence[FeatureExample]]) -> tuple[FeatureProvenance, ...]:
    return tuple(
        example.provenance
        for category_id in _RPC_CATEGORY_IDS
        for example in supports[category_id]
    )


def _validate_matching_support_provenance(
    repvit: Mapping[int, Sequence[FeatureExample]], dino: Mapping[int, Sequence[FeatureExample]]
) -> None:
    if _flatten_provenance(repvit) != _flatten_provenance(dino):
        raise ValueError("RepViT and DINO supports must have identical provenance")


def _validate_query_against_support(query: FeatureExample, supports: Sequence[FeatureProvenance]) -> None:
    if not isinstance(query, FeatureExample):
        raise ValueError("query must be a FeatureExample")
    query_identity = (query.provenance.source_identity, query.provenance.annotation_id)
    if query_identity in {(item.source_identity, item.annotation_id) for item in supports}:
        raise ValueError("query provenance is present in support")


def _mean_prototypes(
    supports: Mapping[int, Sequence[FeatureExample]], attribute: str, category_ids: Sequence[int] = _RPC_CATEGORY_IDS
) -> torch.Tensor:
    rows: list[torch.Tensor] = []
    for category_id in category_ids:
        vectors = torch.stack([
            _unit_tensor(getattr(example, attribute), f"{attribute} support feature")
            for example in supports[category_id]
        ])
        rows.append(functional.normalize(vectors.mean(dim=0), dim=0))
    return torch.stack(rows)


def _mean_local_prototypes(
    supports: Mapping[int, Sequence[FeatureExample]], category_ids: Sequence[int] = _RPC_CATEGORY_IDS
) -> torch.Tensor:
    rows: list[torch.Tensor] = []
    for category_id in category_ids:
        patches = torch.cat([
            _unit_patch_tensor(example.dinov3_patches, "DINO local support feature")
            for example in supports[category_id]
        ])
        rows.append(functional.normalize(patches.mean(dim=0), dim=0))
    return torch.stack(rows)


def _cache_scores(
    supports: Mapping[int, Sequence[FeatureExample]], attribute: str, query: torch.Tensor
) -> torch.Tensor:
    scores = []
    for category_id in _RPC_CATEGORY_IDS:
        vectors = torch.stack([
            _unit_tensor(getattr(example, attribute), f"{attribute} cache feature")
            for example in supports[category_id]
        ])
        scores.append(torch.exp(_M2_KERNEL_SCALE * (vectors @ query)).mean())
    return torch.stack(scores)


def _local_cache_scores(supports: Mapping[int, Sequence[FeatureExample]], query_patches: torch.Tensor) -> torch.Tensor:
    scores = []
    for category_id in _RPC_CATEGORY_IDS:
        support_patches = torch.cat([
            _unit_patch_tensor(example.dinov3_patches, "DINO local cache feature")
            for example in supports[category_id]
        ])
        patch_scores = torch.exp(_M2_KERNEL_SCALE * (query_patches @ support_patches.T)).mean(dim=1)
        scores.append(patch_scores.mean())
    return torch.stack(scores)


def _prediction(
    method: str,
    query: FeatureExample,
    repvit_support: tuple[FeatureProvenance, ...],
    dino_support: tuple[FeatureProvenance, ...],
    repvit_scores: torch.Tensor,
    dino_scores: torch.Tensor,
    local_scores: torch.Tensor,
) -> BranchPrediction:
    vectors = (repvit_scores, dino_scores, local_scores)
    if any(tuple(vector.shape) != (len(_RPC_CATEGORY_IDS),) or not torch.isfinite(vector).all().item() for vector in vectors):
        raise ValueError("branch scores must be finite 200-class vectors")
    return BranchPrediction(
        _RPC_CATEGORY_IDS,
        tuple(float(value) for value in repvit_scores.tolist()),
        tuple(float(value) for value in dino_scores.tolist()),
        tuple(float(value) for value in local_scores.tolist()),
        ScoreProvenance(method, query.provenance, repvit_support, dino_support),
    )


def _top1_category(scores: Sequence[float]) -> int:
    return _RPC_CATEGORY_IDS[max(range(len(scores)), key=lambda index: (scores[index], -index))]


def _validated_m0_training_features(
    base_features: Sequence[FeatureExample], novel_features: Sequence[FeatureExample]
) -> tuple[dict[int, tuple[FeatureExample, ...]], dict[int, tuple[FeatureExample, ...]]]:
    def grouped(items: Sequence[FeatureExample], label: str) -> dict[int, tuple[FeatureExample, ...]]:
        result: dict[int, list[FeatureExample]] = {}
        for item in items:
            if not isinstance(item, FeatureExample):
                raise ValueError(f"{label} features must be FeatureExample values")
            result.setdefault(item.category_id, []).append(item)
        return {category_id: tuple(examples) for category_id, examples in sorted(result.items())}
    base, novel = grouped(base_features, "base"), grouped(novel_features, "novel")
    if not base or not novel or set(base) & set(novel) or set(base) | set(novel) != set(_RPC_CATEGORY_IDS):
        raise ValueError("base and novel features must be disjoint and cover the registered 200-class catalog")
    if len(_flatten_provenance({**base, **novel})) != len(set(_flatten_provenance({**base, **novel}))):
        raise ValueError("M0 support provenance contains duplicate examples")
    return base, novel


def _catalog_rows(
    base_categories: Sequence[int], base_rows: torch.Tensor, novel_categories: Sequence[int], novel_rows: torch.Tensor
) -> torch.Tensor:
    by_category = {
        **{category_id: base_rows[index] for index, category_id in enumerate(base_categories)},
        **{category_id: novel_rows[index] for index, category_id in enumerate(novel_categories)},
    }
    if set(by_category) != set(_RPC_CATEGORY_IDS):
        raise ValueError("M0 rows must cover the registered 200-class catalog")
    return torch.stack([by_category[category_id] for category_id in _RPC_CATEGORY_IDS])


def _m0_training_batch(
    novel: Mapping[int, Sequence[FeatureExample]], base_categories: Sequence[int], novel_categories: Sequence[int]
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    vectors, targets, weights = [], [], []
    category_to_index = {category_id: index for index, category_id in enumerate(_RPC_CATEGORY_IDS)}
    for category_id in novel_categories:
        examples = novel[category_id]
        for example in examples:
            vectors.append(_unit_tensor(example.repvit_global, "M0 novel feature"))
            targets.append(category_to_index[category_id])
            weights.append(1.0 / len(examples))
    return torch.stack(vectors), torch.tensor(targets, dtype=torch.long), torch.tensor(weights, dtype=torch.float32)


def materialize_support_bank(
    rows: Sequence[OracleFeatureRow], *, selector: str, seed: int, maximum_shots: int
) -> SupportBank:
    """Create source/hash-bound, nested RND or DINO-global DIV support prefixes."""
    if selector not in {"rnd", "div"}:
        raise ValueError("unsupported support selector")
    if type(seed) is not int:
        raise ValueError("support seed must be an integer")
    if type(maximum_shots) is not int or maximum_shots <= 0:
        raise ValueError("maximum shots must be positive")
    if not isinstance(rows, Sequence) or not rows:
        raise ValueError("support rows must be a non-empty sequence")
    if not all(isinstance(row, OracleFeatureRow) for row in rows):
        raise ValueError("support rows must be OracleFeatureRow instances")
    source_identities = [row.source_identity for row in rows]
    if len(source_identities) != len(set(source_identities)):
        raise ValueError("duplicate source identity")
    examples = tuple(_support_example(row) for row in rows)
    feature_digests = {example.feature_array_sha256 for example in examples}
    if len(feature_digests) != 1:
        raise ValueError("support rows must bind one feature-array SHA-256")
    dimensions = {len(example.dino_global) for example in examples}
    if len(dimensions) != 1:
        raise ValueError("DINO global feature dimensions must agree")
    by_category: dict[int, list[SupportExample]] = {}
    for example in examples:
        by_category.setdefault(example.category_id, []).append(example)
    orders: list[tuple[SupportExample, ...]] = []
    for category_id, candidates in sorted(by_category.items()):
        if len(candidates) < maximum_shots:
            raise ValueError(f"insufficient support candidates for category {category_id}")
        if selector == "rnd":
            order = tuple(
                sorted(
                    candidates,
                    key=lambda item: (_seeded_digest(seed, item.source_identity), item.source_identity),
                )[:maximum_shots]
            )
        else:
            order = _diverse_support_order(tuple(candidates), seed, maximum_shots)
        orders.append(order)
    feature_digest = next(iter(feature_digests))
    frozen_orders = tuple(orders)
    return SupportBank(
        selector,
        seed,
        maximum_shots,
        frozen_orders,
        feature_digest,
        _support_bank_digest(selector, seed, maximum_shots, frozen_orders, feature_digest),
    )


def materialize_support_banks(
    rows: Sequence[OracleFeatureRow], *, selector: str, seeds: Sequence[int], maximum_shots: int
) -> tuple[SupportBank, ...]:
    """Materialize independent declared seed draws and reject duplicate DIV evidence."""
    frozen_seeds = tuple(seeds)
    if not frozen_seeds or len(frozen_seeds) != len(set(frozen_seeds)) or any(
        type(seed) is not int for seed in frozen_seeds
    ):
        raise ValueError("support seeds must be distinct integers")
    banks = tuple(
        materialize_support_bank(rows, selector=selector, seed=seed, maximum_shots=maximum_shots)
        for seed in frozen_seeds
    )
    if selector == "div":
        observed: set[tuple[tuple[int, tuple[str, ...]], ...]] = set()
        for bank in banks:
            order = bank.ordered_support_identities
            if order in observed:
                raise ValueError("distinct DIV seeds produced the same ordered support draw")
            observed.add(order)
    return banks


def materialize_support_bank_from_feature_manifest(
    feature_manifest_path: Path,
    *,
    selector: str,
    seed: int,
    maximum_shots: int,
    source_split: str | None = None,
) -> SupportBank:
    """Build a bank only from canonical, hash-verified train feature rows.

    A mixed support/query cache requires an explicit ``train2019`` selector;
    default behavior remains strict and accepts only all-train manifests.
    """
    manifest_path = Path(feature_manifest_path).resolve()
    root = _RESEARCH_RUNS_ROOT.resolve()
    if not manifest_path.is_relative_to(root):
        raise ValueError(f"feature manifest must be under {root}")
    try:
        content = manifest_path.read_bytes()
        manifest = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read Task 1 feature manifest") from exc
    if not isinstance(manifest, dict) or canonical_json_bytes(manifest) != content:
        raise ValueError("Task 1 feature manifest is not canonical")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != "rpc-research-oracle-features"
        or manifest.get("canonical_frame") != _CANONICAL_FRAME
        or manifest.get("feature_dtype") != "float16"
    ):
        raise ValueError("invalid Task 1 feature manifest")
    raw_rows = manifest.get("rows")
    raw_images = manifest.get("images")
    arrays = manifest.get("arrays")
    if not isinstance(raw_rows, list) or not raw_rows or not isinstance(raw_images, list) or not isinstance(arrays, dict):
        raise ValueError("invalid Task 1 feature manifest")
    selected_indices = _support_feature_row_indices(raw_rows, source_split)
    dino_entry = arrays.get("dinov3_global")
    if not isinstance(dino_entry, dict) or set(dino_entry) != {"file", "byte_size", "sha256", "shape"}:
        raise ValueError("invalid Task 1 DINO global array manifest")
    file_name, byte_size, array_digest, shape = (
        dino_entry["file"], dino_entry["byte_size"], dino_entry["sha256"], dino_entry["shape"]
    )
    if (
        file_name != "dinov3_global.float16.npy"
        or type(byte_size) is not int
        or byte_size <= 0
        or not isinstance(array_digest, str)
        or _SHA256.fullmatch(array_digest) is None
        or shape != [len(raw_rows), _FEATURE_DIMENSION]
    ):
        raise ValueError("invalid Task 1 DINO global array manifest")
    array_path = (manifest_path.parent / file_name).resolve()
    if not array_path.is_relative_to(manifest_path.parent):
        raise ValueError("Task 1 DINO global array escapes feature manifest directory")
    if not array_path.is_file():
        raise ValueError("Task 1 DINO global feature array changed")
    if _sha256_file(array_path) != array_digest:
        raise ValueError("DINO global feature array SHA-256 mismatch")
    if array_path.stat().st_size != byte_size:
        raise ValueError("Task 1 DINO global feature array byte size mismatch")
    try:
        dino_globals = np.load(array_path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as exc:
        raise ValueError("cannot load Task 1 DINO global feature array") from exc
    if (
        not isinstance(dino_globals, np.ndarray)
        or dino_globals.dtype != np.float16
        or dino_globals.shape != (len(raw_rows), _FEATURE_DIMENSION)
        or not np.isfinite(dino_globals[list(selected_indices)]).all()
    ):
        raise ValueError("invalid Task 1 DINO global feature array")
    images = _task1_images_by_identity(raw_images)
    rows = tuple(
        _support_row_from_task1_manifest(raw, images, dino_globals[index], array_digest)
        for index in selected_indices
        for raw in (raw_rows[index],)
    )
    return materialize_support_bank(rows, selector=selector, seed=seed, maximum_shots=maximum_shots)


def _support_feature_row_indices(raw_rows: list[object], source_split: str | None) -> tuple[int, ...]:
    if source_split not in {None, "train2019"}:
        raise ValueError("support feature source split must be train2019")
    selected: list[int] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict) or set(raw) != {
            "identity", "source_identity", "annotation_id", "category_id", "bbox_xywh", "difficulty"
        }:
            raise ValueError("invalid Task 1 feature row")
        identity, annotation_id, category_id, bbox, difficulty = (
            raw.get("source_identity"), raw.get("annotation_id"), raw.get("category_id"),
            raw.get("bbox_xywh"), raw.get("difficulty"),
        )
        if (
            not isinstance(identity, str)
            or not identity
            or raw.get("identity") != f"{identity}:{annotation_id}"
            or type(annotation_id) is not int
            or annotation_id < 0
            or type(category_id) is not int
            or category_id <= 0
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or not isinstance(difficulty, str)
            or len(difficulty) != 1
        ):
            raise ValueError("invalid Task 1 feature row")
        is_train = identity.startswith("train2019:")
        if source_split == "train2019":
            if is_train:
                selected.append(index)
        elif not is_train:
            raise ValueError("Task 1 support rows must be train2019 capture sources")
        else:
            selected.append(index)
    if not selected:
        raise ValueError("Task 1 feature manifest has no selected support rows")
    return tuple(selected)


def _task1_images_by_identity(raw_images: list[object]) -> dict[str, tuple[int, str]]:
    images: dict[str, tuple[int, str]] = {}
    for raw in raw_images:
        if not isinstance(raw, dict) or set(raw) != {"source_identity", "source_byte_size", "source_sha256"}:
            raise ValueError("invalid Task 1 source manifest")
        identity, byte_size, digest = raw.get("source_identity"), raw.get("source_byte_size"), raw.get("source_sha256")
        if (
            not isinstance(identity, str)
            or not identity
            or type(byte_size) is not int
            or byte_size <= 0
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            or identity in images
        ):
            raise ValueError("invalid Task 1 source manifest")
        images[identity] = (byte_size, digest)
    return images


def _support_row_from_task1_manifest(
    raw: object,
    images: Mapping[str, tuple[int, str]],
    dino_global: np.ndarray,
    feature_array_sha256: str,
) -> OracleFeatureRow:
    if not isinstance(raw, dict) or set(raw) != {
        "identity", "source_identity", "annotation_id", "category_id", "bbox_xywh", "difficulty"
    }:
        raise ValueError("invalid Task 1 feature row")
    identity = raw.get("source_identity")
    annotation_id, category_id, bbox, difficulty = (
        raw.get("annotation_id"), raw.get("category_id"), raw.get("bbox_xywh"), raw.get("difficulty")
    )
    if (
        not isinstance(identity, str)
        or raw.get("identity") != f"{identity}:{annotation_id}"
        or identity not in images
        or not isinstance(bbox, list)
    ):
        raise ValueError("invalid Task 1 feature row")
    match = _TRAIN_CAPTURE_SOURCE.fullmatch(identity)
    if match is None:
        raise ValueError("Task 1 support rows must be train2019 capture sources")
    source_byte_size, source_sha256 = images[identity]
    capture_stratum = f"{match['product']}:camera{match['camera']}-{match['side']}"
    return OracleFeatureRow(
        identity,
        annotation_id,  # type: ignore[arg-type]
        category_id,  # type: ignore[arg-type]
        tuple(bbox),  # type: ignore[arg-type]
        difficulty,  # type: ignore[arg-type]
        source_byte_size=source_byte_size,
        source_sha256=source_sha256,
        dino_global=tuple(float(value) for value in dino_global),
        capture_stratum=capture_stratum,
        feature_array_sha256=feature_array_sha256,
    )


def _support_example(row: OracleFeatureRow) -> SupportExample:
    if (
        row.source_byte_size is None
        or row.source_sha256 is None
        or row.dino_global is None
        or row.capture_stratum is None
        or row.feature_array_sha256 is None
    ):
        raise ValueError("support row lacks source/hash-bound DINO feature provenance")
    return SupportExample(
        row.source_identity,
        row.annotation_id,
        row.category_id,
        row.source_byte_size,
        row.source_sha256,
        row.dino_global,
        row.capture_stratum,
        row.feature_array_sha256,
    )


def _diverse_support_order(
    candidates: tuple[SupportExample, ...], seed: int, maximum_shots: int
) -> tuple[SupportExample, ...]:
    vectors = np.asarray([candidate.dino_global for candidate in candidates], dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(norms).all() or (norms == 0.0).any():
        raise ValueError("DINO global feature must have non-zero length")
    normalized = vectors / norms[:, np.newaxis]
    digests = tuple(_seeded_digest(seed, candidate.source_identity) for candidate in candidates)
    centroid_distances = np.linalg.norm(normalized - normalized.mean(axis=0), axis=1)
    first = min(
        range(len(candidates)),
        key=lambda item: (
            float(centroid_distances[item]),
            digests[item],
            candidates[item].source_sha256,
            candidates[item].source_identity,
        ),
    )
    selected = [first]
    remaining = set(range(len(candidates)))
    remaining.remove(first)
    stratum_counts = {candidates[first].capture_stratum: 1}
    all_strata = {candidate.capture_stratum for candidate in candidates}
    nearest_distances = np.linalg.norm(normalized - normalized[first], axis=1)
    while remaining and len(selected) < maximum_shots:
        pool = tuple(sorted(remaining))
        unrepresented = all_strata - set(stratum_counts)
        if unrepresented:
            next_stratum = min(unrepresented, key=lambda item: (_seeded_digest(seed, item), item))
            pool = tuple(index for index in pool if candidates[index].capture_stratum == next_stratum)
        else:
            fewest = min(stratum_counts.get(candidates[index].capture_stratum, 0) for index in pool)
            pool = tuple(
                index
                for index in pool
                if stratum_counts.get(candidates[index].capture_stratum, 0) == fewest
            )
        next_index = min(
            pool,
            key=lambda item: (
                -float(nearest_distances[item]),
                digests[item],
                candidates[item].source_sha256,
                candidates[item].source_identity,
            ),
        )
        selected.append(next_index)
        remaining.remove(next_index)
        stratum = candidates[next_index].capture_stratum
        stratum_counts[stratum] = stratum_counts.get(stratum, 0) + 1
        nearest_distances = np.minimum(
            nearest_distances,
            np.linalg.norm(normalized - normalized[next_index], axis=1),
        )
    return tuple(candidates[index] for index in selected)


def _normalized_vector(values: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("DINO global feature must have non-zero length")
    return tuple(value / norm for value in values)


def _vector_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(sum((first - second) ** 2 for first, second in zip(left, right, strict=True)))


def _seeded_digest(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def _support_bank_digest(
    selector: str,
    seed: int,
    maximum_shots: int,
    class_orders: tuple[tuple[SupportExample, ...], ...],
    feature_array_sha256: str,
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "selector": selector,
                "seed": seed,
                "maximum_shots": maximum_shots,
                "feature_array_sha256": feature_array_sha256,
                "class_orders": [
                    [
                        {
                            "source_identity": example.source_identity,
                            "annotation_id": example.annotation_id,
                            "category_id": example.category_id,
                            "source_byte_size": example.source_byte_size,
                            "source_sha256": example.source_sha256,
                            "capture_stratum": example.capture_stratum,
                        }
                        for example in order
                    ]
                    for order in class_orders
                ],
            }
        )
    ).hexdigest()


def support_bank_manifest(bank: SupportBank) -> dict[str, object]:
    """Return the compact, canonical receipt for an immutable support bank."""
    if not isinstance(bank, SupportBank):
        raise ValueError("support bank must be a SupportBank")
    return {
        "schema_version": 1,
        "kind": "rpc-research-support-bank",
        "selector": bank.selector,
        "seed": bank.seed,
        "maximum_shots": bank.maximum_shots,
        "feature_array_sha256": bank.feature_array_sha256,
        "classes": [
            {
                "category_id": order[0].category_id,
                "ordered_support_identities": [example.source_identity for example in order],
                "examples": [
                    {
                        "identity": f"{example.source_identity}:{example.annotation_id}",
                        "source_identity": example.source_identity,
                        "annotation_id": example.annotation_id,
                        "source_byte_size": example.source_byte_size,
                        "source_sha256": example.source_sha256,
                        "capture_stratum": example.capture_stratum,
                    }
                    for example in order
                ],
            }
            for order in bank.class_orders
        ],
        "sha256": bank.sha256,
    }


def write_support_bank(path: Path, bank: SupportBank) -> Path:
    """Write a no-replace compact support receipt outside the repository."""
    destination = Path(path).resolve()
    root = _RESEARCH_RUNS_ROOT.resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"output must be under {root}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_new_json(destination, support_bank_manifest(bank))
    return destination


def extract_oracle_features(
    index: RpcIndex,
    artifacts: ResearchArtifacts,
    output: Path,
    *,
    batch_size: int = 1,
) -> Path:
    """Materialize no-replace float16 oracle features and their canonical manifest.

    The output is a fresh directory containing one `manifest.json` and exactly
    three `.npy` arrays.  It intentionally does not create crops or any Git
    payload: generated data remains an external research artifact.
    """
    if not isinstance(index, RpcIndex):
        raise ValueError("index must be an RpcIndex")
    if not isinstance(artifacts, ResearchArtifacts):
        raise ValueError("artifacts must be ResearchArtifacts")
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("feature batch_size must be a positive integer")
    root = _RESEARCH_RUNS_ROOT.resolve()
    destination = Path(output).resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"output must be under {root}")
    artifacts = _revalidate_artifacts(artifacts)
    if destination.exists():
        raise FileExistsError(f"output already exists: {destination}")
    rows = _oracle_rows(index)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        repvit_array = np.lib.format.open_memmap(
            temporary / "repvit_global.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _FEATURE_DIMENSION),
        )
        dino_array = np.lib.format.open_memmap(
            temporary / "dinov3_global.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _FEATURE_DIMENSION),
        )
        patch_array = np.lib.format.open_memmap(
            temporary / "dinov3_patches.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _DINO_PATCH_COUNT, _FEATURE_DIMENSION),
        )
        repvit_model, dino_model = _load_feature_models(artifacts)
        transform = build_transform(224)
        device = _model_device(repvit_model)
        if _model_device(dino_model) != device:
            raise ValueError("research encoders must share one device")
        image_by_identity = {image.source_identity: image for image in index.images}
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            batch = torch.stack(
                [
                    transform(
                        _canonical_oracle_crop(
                            image_by_identity[row.source_identity], row.bbox_xywh
                        )
                    )
                    for row in batch_rows
                ]
            ).to(device)
            repvit, dino, patches = _feature_vectors(repvit_model, dino_model, batch)
            stop = start + len(batch_rows)
            repvit_array[start:stop] = repvit.cpu().numpy().astype(np.float16, copy=False)
            dino_array[start:stop] = dino.cpu().numpy().astype(np.float16, copy=False)
            patch_array[start:stop] = patches.cpu().numpy().astype(np.float16, copy=False)
        del repvit_array, dino_array, patch_array
        manifest = _feature_manifest(
            rows, image_by_identity, artifacts, temporary, batch_size=batch_size
        )
        manifest_path = temporary / "manifest.json"
        write_new_json(manifest_path, manifest)
        os.rename(temporary, destination)
        return destination / "manifest.json"
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _oracle_rows(index: RpcIndex) -> tuple[OracleFeatureRow, ...]:
    image_by_coordinate = {(item.split, item.image_id): item for item in index.images}
    if len(image_by_coordinate) != len(index.images):
        raise ValueError("RPC index contains duplicate source images")
    rows: list[OracleFeatureRow] = []
    for item in index.objects:
        image = image_by_coordinate.get((item.split, item.image_id))
        if image is None:
            raise ValueError("RPC object is not bound to an indexed source image")
        difficulty = image.level[:1].upper() if image.level else "U"
        rows.append(
            OracleFeatureRow(
                image.source_identity, item.annotation_id, item.category_id,
                item.bbox_xywh, difficulty,
            )
        )
    identities = [row.identity for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("RPC index contains duplicate oracle annotation identities")
    return tuple(sorted(rows, key=lambda row: (row.source_identity, row.annotation_id)))


def _canonical_oracle_crop(
    image: RpcImage, bbox_xywh: tuple[float, float, float, float]
) -> Image.Image:
    _verify_indexed_source(image)
    try:
        with Image.open(image.source_path) as source:
            orientation = source.getexif().get(274, 1)
            if type(orientation) is not int or orientation not in range(1, 9):
                raise ValueError("RPC source image has an invalid EXIF orientation")
            _validate_bbox_bounds(bbox_xywh, source.width, source.height)
            canonical_bbox = _transpose_bbox_for_exif(
                bbox_xywh, orientation, source.width, source.height
            )
            canonical = ImageOps.exif_transpose(source).convert("RGB")
    except OSError as exc:
        raise ValueError(f"cannot decode RPC source image: {image.source_identity}") from exc
    x, y, width, height = canonical_bbox
    left, top = math.floor(x), math.floor(y)
    right, bottom = math.ceil(x + width), math.ceil(y + height)
    if left < 0 or top < 0 or right > canonical.width or bottom > canonical.height or right <= left or bottom <= top:
        raise ValueError("oracle bbox lies outside canonical RGB image")
    return canonical.crop((left, top, right, bottom))


def _transpose_bbox_for_exif(
    bbox_xywh: tuple[float, float, float, float], orientation: int, width: int, height: int
) -> tuple[float, float, float, float]:
    """Map raw-file COCO coordinates into Pillow's EXIF-transposed frame."""
    x, y, box_width, box_height = bbox_xywh
    if orientation == 1:
        return bbox_xywh
    if orientation == 2:
        return (width - x - box_width, y, box_width, box_height)
    if orientation == 3:
        return (width - x - box_width, height - y - box_height, box_width, box_height)
    if orientation == 4:
        return (x, height - y - box_height, box_width, box_height)
    if orientation == 5:
        return (y, x, box_height, box_width)
    if orientation == 6:
        return (height - y - box_height, x, box_height, box_width)
    if orientation == 7:
        return (height - y - box_height, width - x - box_width, box_height, box_width)
    return (y, width - x - box_width, box_height, box_width)


def _validate_bbox_bounds(
    bbox_xywh: tuple[float, float, float, float], width: int, height: int
) -> None:
    x, y, box_width, box_height = bbox_xywh
    if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
        raise ValueError("oracle bbox lies outside raw EXIF image")


def _feature_vectors(
    repvit_model: torch.nn.Module, dino_model: torch.nn.Module, batch: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    with torch.inference_mode():
        repvit_raw = repvit_model.forward_features(batch)
        if not isinstance(repvit_raw, torch.Tensor) or tuple(repvit_raw.shape[:2]) != (batch.shape[0], _FEATURE_DIMENSION):
            raise ValueError("RepViT features must have shape (N, 384, H, W)")
        if repvit_raw.ndim != 4 or not torch.isfinite(repvit_raw).all().item():
            raise ValueError("RepViT features must be finite spatial tensors")
        repvit = _l2_normalize(repvit_raw.mean(dim=(2, 3)), "RepViT global feature")
        dino_raw = dino_model.forward_features(batch)
        if not isinstance(dino_raw, Mapping):
            raise ValueError("DINOv3 forward_features must return a mapping")
        dino_global = dino_raw.get("x_norm_clstoken")
        patches = dino_raw.get("x_norm_patchtokens")
        if not isinstance(dino_global, torch.Tensor) or tuple(dino_global.shape) != (batch.shape[0], _FEATURE_DIMENSION):
            raise ValueError("DINOv3 global features must have shape (N, 384)")
        if not isinstance(patches, torch.Tensor) or tuple(patches.shape) != (batch.shape[0], _DINO_PATCH_COUNT, _FEATURE_DIMENSION):
            raise ValueError("DINOv3 patch features must have shape (N, 196, 384)")
        if not torch.isfinite(dino_global).all().item() or not torch.isfinite(patches).all().item():
            raise ValueError("DINOv3 features must be finite")
        return (
            repvit,
            _l2_normalize(dino_global, "DINOv3 global feature"),
            _l2_normalize(patches, "DINOv3 patch feature"),
        )


def _l2_normalize(value: torch.Tensor, label: str) -> torch.Tensor:
    norms = value.norm(dim=-1, keepdim=True)
    if (norms == 0).any().item():
        raise ValueError(f"{label} must have non-zero length")
    return functional.normalize(value, dim=-1)


def _load_feature_models(artifacts: ResearchArtifacts) -> tuple[torch.nn.Module, torch.nn.Module]:
    """Load exact research encoders; imported lazily so contracts stay hermetic."""
    import timm
    from dinov3.models.vision_transformer import vit_small
    from safetensors.torch import load_file

    # CPU/float32 is the explicitly documented reproducibility contract for
    # this research cache.  Do not silently alter its bytes by choosing CUDA.
    device = torch.device("cpu")
    repvit = timm.create_model("repvit_m1", pretrained=False)
    repvit.load_state_dict(load_file(str(artifacts.repvit_path), device="cpu"), strict=True)
    dino = vit_small(patch_size=16, n_storage_tokens=4, mask_k_bias=True, layerscale_init=1e-5)
    weights = torch.load(artifacts.dino_path, map_location="cpu", weights_only=True)
    if not isinstance(weights, Mapping):
        raise ValueError("DINOv3 weights must be a state dictionary")
    dino.load_state_dict(weights, strict=True)
    return repvit.to(device).eval(), dino.to(device).eval()


def _revalidate_artifacts(artifacts: ResearchArtifacts) -> ResearchArtifacts:
    """Reject forged or stale dataclass values immediately before model loading."""
    verified = ResearchArtifacts.from_paths(artifacts.repvit_path, artifacts.dino_path)
    if (
        artifacts.repvit_path.resolve() != verified.repvit_path
        or artifacts.dino_path.resolve() != verified.dino_path
        or artifacts.repvit_sha256 != verified.repvit_sha256
        or artifacts.dino_sha256 != verified.dino_sha256
    ):
        raise ValueError("research artifact provenance mismatch")
    return verified


def _model_device(model: torch.nn.Module) -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def _feature_manifest(
    rows: tuple[OracleFeatureRow, ...],
    image_by_identity: dict[str, RpcImage],
    artifacts: ResearchArtifacts,
    directory: Path,
    *,
    batch_size: int,
) -> dict[str, object]:
    arrays = {
        "repvit_global": _array_manifest(directory / "repvit_global.float16.npy", [len(rows), _FEATURE_DIMENSION]),
        "dinov3_global": _array_manifest(directory / "dinov3_global.float16.npy", [len(rows), _FEATURE_DIMENSION]),
        "dinov3_patches": _array_manifest(directory / "dinov3_patches.float16.npy", [len(rows), _DINO_PATCH_COUNT, _FEATURE_DIMENSION]),
    }
    return {
        "schema_version": 1,
        "kind": "rpc-research-oracle-features",
        "canonical_frame": _CANONICAL_FRAME,
        "feature_dtype": "float16",
        "execution": {
            "batch_size": batch_size,
            "device": "cpu",
            "determinism": "cpu-float32-inference-mode-model-eval-v1",
        },
        "preprocessing": {
            "canonical_frame": _CANONICAL_FRAME,
            "bbox_coordinate_frame": "raw-exif-source-v1",
            "exif_bbox_transform": "raw-to-visual-v1",
            "image_mode": "RGB",
            "input_size": [224, 224],
            "resize_interpolation": "bilinear",
            "antialias": True,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "code_sha256": _sha256_file(Path(__file__)),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pillow": Image.__version__,
            "torch": torch.__version__,
        },
        "artifacts": {
            "repvit": {"path": str(artifacts.repvit_path), "sha256": artifacts.repvit_sha256},
            "dinov3": {"path": str(artifacts.dino_path), "sha256": artifacts.dino_sha256},
        },
        "arrays": arrays,
        "images": [
            {
                "source_identity": image.source_identity,
                "source_byte_size": image.byte_size,
                "source_sha256": image.sha256,
            }
            for image in sorted(image_by_identity.values(), key=lambda item: item.source_identity)
        ],
        "rows": [
            {
                "identity": row.identity,
                "source_identity": row.source_identity,
                "annotation_id": row.annotation_id,
                "category_id": row.category_id,
                "bbox_xywh": list(row.bbox_xywh),
                "difficulty": row.difficulty,
            }
            for row in rows
        ],
    }


def _array_manifest(path: Path, shape: list[int]) -> dict[str, object]:
    return {
        "file": path.name,
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "shape": shape,
    }


def _verify_indexed_source(image: RpcImage) -> None:
    if not image.source_path.is_file() or image.source_path.stat().st_size != image.byte_size:
        raise ValueError(f"RPC source image changed: {image.source_identity}")
    if _sha256_file(image.source_path) != image.sha256:
        raise ValueError(f"RPC source image changed: {image.source_identity}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    except OSError:
        return ""
    return digest.hexdigest()
