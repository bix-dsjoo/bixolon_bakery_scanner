from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_profile import (
    BATCH2_E3_M3_H3_NAMES,
    resolve_batch2_e3_m3_h3,
)


def test_batch2_profile_resolves_exact_e_m_h_three_each(tmp_path: Path):
    for name in BATCH2_E3_M3_H3_NAMES:
        (tmp_path / name).write_bytes(b"image")

    selected = resolve_batch2_e3_m3_h3(tmp_path)

    assert [path.name for path in selected] == [
        "g20_b02_e_0301.jpg",
        "g20_b02_e_0306.jpg",
        "g20_b02_e_0307.jpg",
        "g20_b02_m_0307.jpg",
        "g20_b02_m_0311.jpg",
        "g20_b02_m_0315.jpg",
        "g20_b02_h_0306.jpg",
        "g20_b02_h_0312.jpg",
        "g20_b02_h_0315.jpg",
    ]


def test_batch2_profile_reports_every_missing_path(tmp_path: Path):
    with pytest.raises(
        FileNotFoundError,
        match=(
            "Batch2 CPU profile is missing: g20_b02_e_0301.jpg.*"
            "g20_b02_h_0315.jpg"
        ),
    ):
        resolve_batch2_e3_m3_h3(tmp_path)
