"""CPU evaluation helpers for the direct RF-DETR-L fusion path."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np


_STAGES = {
    "canonical": "canonical_ms",
    "detector": "detector_ms",
    "crop": "crop_ms",
    "repvit": "repvit_ms",
    "dinov3": "dinov3_ms",
    "fusion": "fusion_ms",
    "total": "elapsed_ms",
}


def summarize_profiles(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, float | int]]:
    """Return fixed E/M/H image counts and mean end-to-end milliseconds."""
    summary: dict[str, dict[str, float | int]] = {}
    for profile in ("E", "M", "H"):
        values = [float(row["elapsed_ms"]) for row in rows if row.get("profile") == profile]
        if values:
            summary[profile] = {"images": len(values), "mean_ms": sum(values) / len(values)}
    return summary


def summarize_profile_stages(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    """Summarize every measured stage for the fixed E/M/H CPU profiles."""
    summary: dict[str, dict[str, object]] = {}
    for profile in ("E", "M", "H"):
        profile_rows = tuple(row for row in rows if row.get("profile") == profile)
        if not profile_rows:
            raise ValueError(f"CPU benchmark is missing profile {profile}")
        objects = 0
        dino_objects = 0
        registered = 0
        unknown = 0
        stage_values: dict[str, list[float]] = {name: [] for name in _STAGES}
        for row in profile_rows:
            object_count = row.get("object_count")
            if type(object_count) is not int or object_count < 0:
                raise ValueError("object_count must be a non-negative integer")
            objects += object_count
            dino_object_count = _non_negative_count(
                row.get("dino_object_count"), "dino_object_count"
            )
            registered_count = _non_negative_count(
                row.get("registered_count"), "registered_count"
            )
            unknown_count = _non_negative_count(
                row.get("unknown_count"), "unknown_count"
            )
            if dino_object_count > registered_count + unknown_count:
                raise ValueError(
                    "DINO object count must not exceed registered and Unknown decisions"
                )
            dino_objects += dino_object_count
            registered += registered_count
            unknown += unknown_count
            for name, field in _STAGES.items():
                value = row.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"{field} must be finite and non-negative")
                stage_values[name].append(float(value))
        decision_count = registered + unknown
        summary[profile] = {
            "images": len(profile_rows),
            "objects": objects,
            "dino_objects": dino_objects,
            "dino_execution_rate": (
                dino_objects / decision_count if decision_count else 0.0
            ),
            "registered": registered,
            "unknown": unknown,
            **{
                name: {
                    "mean_ms": float(np.mean(values)),
                    "p50_ms": float(np.percentile(values, 50)),
                    "p95_ms": float(np.percentile(values, 95)),
                }
                for name, values in stage_values.items()
            },
        }
    if any(row.get("profile") not in {"E", "M", "H"} for row in rows):
        raise ValueError("CPU benchmark rows must use E, M, or H profiles")
    return summary


def _non_negative_count(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value
