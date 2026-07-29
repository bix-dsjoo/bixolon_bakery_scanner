import math

import pytest

from bakery_scanner.e2e.cpu_latency import (
    ImageLatency,
    PairedPass,
    compare_paired_latency,
)


def _passes(
    *,
    reference: tuple[float, ...],
    candidate: tuple[float, ...],
    count: int,
) -> tuple[PairedPass, ...]:
    keys = tuple(f"image-{index:04d}" for index in range(len(reference)))
    reference_rows = tuple(
        ImageLatency(key, value) for key, value in zip(keys, reference, strict=True)
    )
    candidate_rows = tuple(
        ImageLatency(key, value) for key, value in zip(keys, candidate, strict=True)
    )
    return tuple(
        PairedPass(
            pass_index=index,
            order="AB" if index % 2 == 0 else "BA",
            reference=reference_rows,
            candidate=candidate_rows,
        )
        for index in range(count)
    )


def test_paired_latency_requires_both_mean_and_p95_ci_below_zero():
    passes = _passes(reference=(100, 110, 120, 130), candidate=(70, 80, 90, 100), count=3)

    report = compare_paired_latency(passes, seed=20260729, bootstrap_samples=2000)

    assert report.mean_delta_ms < 0
    assert report.p95_delta_ms < 0
    assert report.mean_ci_upper_ms < 0
    assert report.p95_ci_upper_ms < 0
    assert report.passed


def test_paired_latency_rejects_noise_overlap():
    passes = _passes(reference=(100, 101, 100, 101), candidate=(99, 102, 99, 102), count=3)
    assert not compare_paired_latency(
        passes, seed=20260729, bootstrap_samples=2000
    ).passed


def test_paired_latency_rejects_invalid_pass_contracts():
    rows = (ImageLatency("image-0000", 1.0),)
    with pytest.raises(ValueError, match="at least three"):
        compare_paired_latency(_passes(reference=(1.0,), candidate=(0.5,), count=2))
    with pytest.raises(ValueError, match="same image keys"):
        compare_paired_latency(
            (
                PairedPass(0, "AB", rows, (ImageLatency("other", 1.0),)),
                PairedPass(1, "BA", rows, rows),
                PairedPass(2, "AB", rows, rows),
            )
        )
    with pytest.raises(ValueError, match="unique"):
        compare_paired_latency(
            (
                PairedPass(0, "AB", (rows[0], rows[0]), (rows[0], rows[0])),
                PairedPass(1, "BA", rows, rows),
                PairedPass(2, "AB", rows, rows),
            )
        )
    with pytest.raises(ValueError, match="AB/BA"):
        compare_paired_latency(
            (
                PairedPass(0, "AB", rows, rows),
                PairedPass(1, "AB", rows, rows),
                PairedPass(2, "BA", rows, rows),
            )
        )
    with pytest.raises(ValueError, match="finite"):
        ImageLatency("image-0000", math.nan)
