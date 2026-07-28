"""Measured full-image E2E execution with SKU-aware evaluation."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .benchmark import BenchmarkReport, BenchmarkSample, _cuda_synchronize, _require_rtx5080, aggregate_benchmark
from .contracts import SkuGroundTruth
from .metrics import E2EImageResult, EvaluationReport, evaluate_run


class _Pipeline(Protocol):
    def infer(self, image_id: int, image: object) -> object: ...


@dataclass(frozen=True, slots=True)
class E2EExecution:
    """One warm RTX 5080 evaluation across the complete labeled image set."""

    benchmark: BenchmarkReport
    evaluation: EvaluationReport
    results: tuple[E2EImageResult, ...]


def execute_e2e_evaluation(
    pipeline: _Pipeline,
    labels_by_image: Mapping[int, tuple[SkuGroundTruth, ...]],
    load_image: Callable[[int], object],
    *,
    warmup_count: int = 10,
    expected_image_count: int = 299,
    synchronize: Callable[[], None] | None = None,
) -> E2EExecution:
    """Warm, measure, and evaluate exactly the labeled image set once."""
    image_ids = tuple(sorted(labels_by_image))
    if len(image_ids) != expected_image_count or len(set(image_ids)) != expected_image_count:
        raise ValueError(f"E2E evaluation requires exactly {expected_image_count} labeled images")
    if any(type(image_id) is not int or image_id <= 0 for image_id in image_ids):
        raise ValueError("E2E evaluation image IDs must be unique positive integers")
    if warmup_count < 10:
        raise ValueError("E2E evaluation requires at least ten warmup iterations")
    _require_rtx5080()
    sync = synchronize or _cuda_synchronize
    for index in range(warmup_count):
        image_id = image_ids[index % len(image_ids)]
        _require_matching_result(pipeline.infer(image_id, load_image(image_id)), image_id)
    sync()

    samples: list[BenchmarkSample] = []
    results: list[E2EImageResult] = []
    for image_id in image_ids:
        image = load_image(image_id)
        sync()
        started = time.perf_counter()
        inference = _require_matching_result(pipeline.infer(image_id, image), image_id)
        sync()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        samples.append(
            BenchmarkSample(
                image_id=image_id,
                total_ms=elapsed_ms,
                convnext_invoked=bool(getattr(inference, "convnext_invocations", 0)),
                dino_invoked=bool(getattr(inference, "dino_invocations", 0)),
            )
        )
        results.append(E2EImageResult(image_id, tuple(inference.final_objects), elapsed_ms))
    frozen_results = tuple(results)
    return E2EExecution(
        benchmark=aggregate_benchmark(tuple(samples)),
        evaluation=evaluate_run(labels_by_image, frozen_results),
        results=frozen_results,
    )


def _require_matching_result(inference: object, image_id: int) -> object:
    if getattr(inference, "image_id", None) != image_id:
        raise ValueError("pipeline inference result image ID must match its requested image")
    if not isinstance(getattr(inference, "final_objects", None), tuple):
        raise TypeError("pipeline inference result must expose final_objects as a tuple")
    return inference
