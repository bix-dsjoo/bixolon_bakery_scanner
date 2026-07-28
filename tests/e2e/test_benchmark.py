import pytest

from bakery_scanner.e2e.benchmark import BenchmarkSample, aggregate_benchmark, benchmark_e2e
from bakery_scanner.e2e.runtime import E2EInference


def test_reports_mean_percentiles_and_conditional_rates():
    report = aggregate_benchmark((
        BenchmarkSample(1, 10.0, False, False),
        BenchmarkSample(2, 20.0, True, True),
        BenchmarkSample(3, 30.0, False, True),
    ))

    assert (report.total_mean_ms, report.total_p50_ms, report.total_p95_ms) == pytest.approx((20.0, 20.0, 29.0))
    assert report.convnext_rate == pytest.approx(1 / 3)
    assert report.dino_rate == pytest.approx(2 / 3)


def test_rejects_partial_299_image_coverage():
    class Pipeline:
        def infer(self, image_id, image):
            return E2EInference(image_id, (), 0)

    with pytest.raises(ValueError, match="299"):
        benchmark_e2e(Pipeline(), tuple(range(1, 299)), lambda image_id: object())
