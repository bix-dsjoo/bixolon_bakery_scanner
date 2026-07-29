"""CPU evaluation helpers for the direct RF-DETR-L fusion path."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def summarize_profiles(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, float | int]]:
    """Return fixed E/M/H image counts and mean end-to-end milliseconds."""
    summary: dict[str, dict[str, float | int]] = {}
    for profile in ("E", "M", "H"):
        values = [float(row["elapsed_ms"]) for row in rows if row.get("profile") == profile]
        if values:
            summary[profile] = {"images": len(values), "mean_ms": sum(values) / len(values)}
    return summary
