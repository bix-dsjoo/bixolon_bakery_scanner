"""Deterministic paired AB/BA CPU latency comparison."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class ImageLatency:
    image_key: str
    total_ms: float

    def __post_init__(self) -> None:
        if not isinstance(self.image_key, str) or not self.image_key:
            raise ValueError("image_key must be non-empty")
        latency = float(self.total_ms)
        if not math.isfinite(latency) or latency < 0.0:
            raise ValueError("total_ms must be finite and non-negative")
        object.__setattr__(self, "total_ms", latency)


@dataclass(frozen=True, slots=True)
class PairedPass:
    pass_index: int
    order: Literal["AB", "BA"]
    reference: tuple[ImageLatency, ...]
    candidate: tuple[ImageLatency, ...]

    def __post_init__(self) -> None:
        if type(self.pass_index) is not int or self.pass_index < 0:
            raise ValueError("pass_index must be a non-negative integer")
        if self.order not in ("AB", "BA"):
            raise ValueError("order must be AB or BA")
        reference = tuple(self.reference)
        candidate = tuple(self.candidate)
        _validate_rows(reference, "reference")
        _validate_rows(candidate, "candidate")
        if {row.image_key for row in reference} != {row.image_key for row in candidate}:
            raise ValueError("reference and candidate must contain the same image keys")
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "candidate", candidate)


@dataclass(frozen=True, slots=True)
class PairedLatencyReport:
    pass_count: int
    image_count: int
    bootstrap_seed: int
    bootstrap_samples: int
    mean_delta_ms: float
    p95_delta_ms: float
    mean_ci_upper_ms: float
    p95_ci_upper_ms: float
    passed: bool


def compare_paired_latency(
    passes: Sequence[PairedPass], *, seed: int = 20260729, bootstrap_samples: int = 10000
) -> PairedLatencyReport:
    """Accept only candidates whose paired mean and p95 are conclusively faster."""
    ordered = _validate_passes(passes)
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(bootstrap_samples) is not int or bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be a positive integer")

    keys = tuple(row.image_key for row in ordered[0].reference)
    reference, candidate = _latency_matrices(ordered, keys)
    mean_delta = float(np.mean(candidate) - np.mean(reference))
    p95_delta = float(np.percentile(candidate, 95) - np.percentile(reference, 95))

    mean_upper, p95_upper = _bootstrap_upper_bounds(
        reference, candidate, seed=seed, bootstrap_samples=bootstrap_samples
    )
    passed = (
        mean_delta < 0.0
        and p95_delta < 0.0
        and mean_upper < 0.0
        and p95_upper < 0.0
    )
    return PairedLatencyReport(
        pass_count=len(ordered),
        image_count=len(keys),
        bootstrap_seed=seed,
        bootstrap_samples=bootstrap_samples,
        mean_delta_ms=mean_delta,
        p95_delta_ms=p95_delta,
        mean_ci_upper_ms=mean_upper,
        p95_ci_upper_ms=p95_upper,
        passed=passed,
    )


def _validate_rows(rows: tuple[ImageLatency, ...], label: str) -> None:
    if not rows:
        raise ValueError(f"{label} rows must not be empty")
    if any(not isinstance(row, ImageLatency) for row in rows):
        raise ValueError(f"{label} rows must contain ImageLatency values")
    keys = tuple(row.image_key for row in rows)
    if len(set(keys)) != len(keys):
        raise ValueError(f"{label} image keys must be unique")


def _validate_passes(passes: Sequence[PairedPass]) -> tuple[PairedPass, ...]:
    values = tuple(passes)
    if len(values) < 3:
        raise ValueError("paired latency requires at least three passes")
    if any(not isinstance(value, PairedPass) for value in values):
        raise ValueError("passes must contain PairedPass values")
    ordered = tuple(sorted(values, key=lambda value: value.pass_index))
    if tuple(value.pass_index for value in ordered) != tuple(range(len(ordered))):
        raise ValueError("pass indexes must be contiguous from zero")
    expected = ordered[0].order
    for value in ordered:
        if value.order != expected:
            raise ValueError("passes must alternate AB/BA order")
        expected = "BA" if expected == "AB" else "AB"
    first_keys = {row.image_key for row in ordered[0].reference}
    for value in ordered[1:]:
        if {row.image_key for row in value.reference} != first_keys:
            raise ValueError("all passes must contain the same image keys")
    return ordered


def _latency_matrices(
    passes: tuple[PairedPass, ...], keys: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    reference_rows: list[list[float]] = []
    candidate_rows: list[list[float]] = []
    for value in passes:
        reference = {row.image_key: row.total_ms for row in value.reference}
        candidate = {row.image_key: row.total_ms for row in value.candidate}
        reference_rows.append([reference[key] for key in keys])
        candidate_rows.append([candidate[key] for key in keys])
    return np.asarray(reference_rows, dtype=np.float64), np.asarray(candidate_rows, dtype=np.float64)


def _bootstrap_upper_bounds(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    seed: int,
    bootstrap_samples: int,
) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    image_count = reference.shape[1]
    mean_deltas = np.empty(bootstrap_samples, dtype=np.float64)
    p95_deltas = np.empty(bootstrap_samples, dtype=np.float64)
    for index in range(bootstrap_samples):
        sampled_indexes = generator.integers(0, image_count, size=image_count)
        sampled_reference = reference[:, sampled_indexes]
        sampled_candidate = candidate[:, sampled_indexes]
        mean_deltas[index] = np.mean(sampled_candidate) - np.mean(sampled_reference)
        p95_deltas[index] = np.percentile(sampled_candidate, 95) - np.percentile(
            sampled_reference, 95
        )
    return float(np.percentile(mean_deltas, 95)), float(np.percentile(p95_deltas, 95))
