"""Deterministic CPU-only functional smoke execution for the E2E pipeline."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from math import ceil
import math
from numbers import Real
from pathlib import Path
from statistics import mean, median
from typing import Protocol


_IMAGE_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png"})
_LIMITATION = (
    "CPU functional smoke output is not a release evaluation and CPU timings "
    "are not comparable to RTX 5080 E2E release metrics."
)
_STAGE_TIMING_KEYS = (
    "detector",
    "mobile_assurance",
    "resolver",
    "repvit",
    "dinov3",
    "total",
)


class _Pipeline(Protocol):
    def infer(self, image_id: int, image: object) -> object: ...


def select_smoke_images(images_dir: Path, limit: int = 10) -> tuple[Path, ...]:
    """Select no more than ten raster images in a portable deterministic order."""
    if not images_dir.is_dir():
        raise ValueError("images directory must exist")
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    selected = sorted(
        (path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES),
        key=lambda path: (path.name.casefold(), path.name),
    )[:limit]
    if not selected:
        raise ValueError("images directory contains no supported raster images")
    return tuple(selected)


def validate_cpu_smoke_request(
    images_dir: Path,
    output: Path,
    device: str,
    limit: int = 10,
) -> tuple[Path, ...]:
    """Reject non-portable invocation errors before model loading begins."""
    if device != "cpu":
        raise ValueError("device must be cpu")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    return select_smoke_images(images_dir, limit)


def run_cpu_smoke(
    pipeline: _Pipeline,
    images: tuple[Path, ...],
    *,
    load_image: Callable[[Path], object],
    provenance: Mapping[str, str],
) -> dict[str, object]:
    """Run the supplied real E2E pipeline and construct a non-release report."""
    if not images or len(images) > 10:
        raise ValueError("CPU smoke run requires between 1 and 10 selected images")

    aggregate: Counter[int] = Counter()
    rows: list[dict[str, object]] = []
    stage_values = {key: [] for key in _STAGE_TIMING_KEYS}
    total_convnext = 0
    total_dino = 0
    for image_id, path in enumerate(images, start=1):
        image = load_image(path)
        inference = pipeline.infer(image_id, image)
        if getattr(inference, "image_id", None) != image_id:
            raise ValueError("pipeline result image ID must match CPU smoke input")
        stage_timings = getattr(inference, "stage_timings_ms", None)
        timings = _validate_stage_timings(stage_timings)
        for key, value in timings.items():
            stage_values[key].append(value)
        final_objects = tuple(getattr(inference, "final_objects", ()))
        objects: list[dict[str, object]] = []
        for item in final_objects:
            box = getattr(item, "box", None)
            sku_id = getattr(item, "sku_id", None)
            if box is None:
                raise TypeError("pipeline final object must expose a box")
            if sku_id is not None:
                aggregate[int(sku_id)] += 1
            objects.append(
                {
                    "box_xyxy": list(box.xyxy),
                    "sku_id": sku_id,
                    "confidence": float(getattr(item, "confidence")),
                    "decision_path": getattr(item, "decision_path"),
                    "top3": list(getattr(item, "top3", ())),
                }
            )
        convnext_count = int(getattr(inference, "convnext_invocations", 0))
        dino_count = int(getattr(inference, "dino_invocations", 0))
        total_convnext += convnext_count
        total_dino += dino_count
        rows.append(
            {
                "image_id": image_id,
                "input_name": path.name,
                "final_objects": objects,
                "stage_timings_ms": timings,
                "total_ms": timings["total"],
                "convnext_invocations": convnext_count,
                "dino_invocations": dino_count,
            }
        )

    return {
        "schema_version": 1,
        "scope": "cpu_functional_smoke_only",
        "limitations": _LIMITATION,
        "provenance": dict(sorted(provenance.items())),
        "input_count": len(images),
        "images": rows,
        "timing_summary_ms": {
            key: _summarize_timings(values) for key, values in stage_values.items()
        },
        "aggregate": {str(sku_id): count for sku_id, count in sorted(aggregate.items())},
        "conditional_invocations": {
            "convnext": total_convnext,
            "dinov3": total_dino,
        },
    }


def _summarize_timings(values: list[float]) -> dict[str, float | int]:
    """Summarize measured timings with the nearest-rank p95 convention."""
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "mean": mean(ordered),
        "median": median(ordered),
        "p95": ordered[ceil(0.95 * len(ordered)) - 1],
    }


def _validate_stage_timings(stage_timings: object) -> dict[str, float]:
    """Validate the timing contract even for protocol-conforming foreign results."""
    if not isinstance(stage_timings, Mapping):
        raise ValueError("stage_timings_ms must be a mapping with required stage timings")
    if set(stage_timings) != set(_STAGE_TIMING_KEYS):
        raise ValueError("stage_timings_ms must contain exactly the required stage timings")
    if any(
        isinstance(value, bool) or not isinstance(value, Real) or value < 0 or not math.isfinite(value)
        for value in stage_timings.values()
    ):
        raise ValueError("stage_timings_ms values must be finite non-negative numbers")
    return {key: float(stage_timings[key]) for key in _STAGE_TIMING_KEYS}
