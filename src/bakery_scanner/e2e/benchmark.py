"""Warm, synchronized whole-image E2E benchmarking."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
import torch


class _Pipeline(Protocol):
    def infer(self, image_id: int, image: object): ...


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    image_id: int
    total_ms: float
    convnext_invoked: bool
    dino_invoked: bool

    def __post_init__(self) -> None:
        if type(self.image_id) is not int or self.image_id <= 0:
            raise ValueError("image_id must be a positive integer")
        total_ms = float(self.total_ms)
        if not math.isfinite(total_ms) or total_ms < 0.0:
            raise ValueError("total_ms must be finite and non-negative")
        object.__setattr__(self, "total_ms", total_ms)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    image_count: int
    total_mean_ms: float
    total_p50_ms: float
    total_p95_ms: float
    convnext_rate: float
    dino_rate: float


def aggregate_benchmark(samples: tuple[BenchmarkSample, ...]) -> BenchmarkReport:
    if not samples:
        raise ValueError("at least one benchmark sample is required")
    values = np.asarray([sample.total_ms for sample in samples], dtype=np.float64)
    return BenchmarkReport(
        image_count=len(samples),
        total_mean_ms=float(values.mean()),
        total_p50_ms=float(np.percentile(values, 50)),
        total_p95_ms=float(np.percentile(values, 95)),
        convnext_rate=sum(sample.convnext_invoked for sample in samples) / len(samples),
        dino_rate=sum(sample.dino_invoked for sample in samples) / len(samples),
    )


def benchmark_e2e(
    pipeline: _Pipeline,
    image_ids: tuple[int, ...],
    load_image: Callable[[int], object],
    *,
    warmup_count: int = 10,
    expected_image_count: int = 299,
    synchronize: Callable[[], None] | None = None,
) -> tuple[BenchmarkReport, tuple[BenchmarkSample, ...]]:
    """Require exact coverage and measure full-image latency after warmup."""
    if len(image_ids) != expected_image_count or len(set(image_ids)) != expected_image_count:
        raise ValueError(f"benchmark requires exactly {expected_image_count} unique images")
    if warmup_count < 10:
        raise ValueError("benchmark requires at least ten warmup iterations")
    sync = synchronize or _cuda_synchronize
    _require_rtx5080()
    for index in range(warmup_count):
        image_id = image_ids[index % len(image_ids)]
        pipeline.infer(image_id, load_image(image_id))
    sync()
    samples: list[BenchmarkSample] = []
    for image_id in image_ids:
        image = load_image(image_id)
        sync()
        started = time.perf_counter()
        result = pipeline.infer(image_id, image)
        sync()
        elapsed = (time.perf_counter() - started) * 1000.0
        samples.append(BenchmarkSample(
            image_id,
            elapsed,
            bool(getattr(result, "convnext_invocations", 0)),
            bool(getattr(result, "dino_invocations", 0)),
        ))
    frozen = tuple(samples)
    return aggregate_benchmark(frozen), frozen


def _cuda_synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _require_rtx5080() -> None:
    if not torch.cuda.is_available() or "RTX 5080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("benchmark requires RTX 5080 cuda:0")
