"""Fixed source-image profile for the Batch2 CPU smoke run."""

from __future__ import annotations

from pathlib import Path


BATCH2_E3_M3_H3_NAMES = (
    "g20_b02_e_0301.jpg", "g20_b02_e_0306.jpg", "g20_b02_e_0307.jpg",
    "g20_b02_m_0307.jpg", "g20_b02_m_0311.jpg", "g20_b02_m_0315.jpg",
    "g20_b02_h_0306.jpg", "g20_b02_h_0312.jpg", "g20_b02_h_0315.jpg",
)


def resolve_batch2_e3_m3_h3(source: Path) -> tuple[Path, ...]:
    """Resolve every fixed Batch2 sample, preserving its prescribed order."""
    selected = tuple(source / name for name in BATCH2_E3_M3_H3_NAMES)
    missing = tuple(path.name for path in selected if not path.is_file())
    if missing:
        raise FileNotFoundError("Batch2 CPU profile is missing: " + ", ".join(missing))
    return selected
