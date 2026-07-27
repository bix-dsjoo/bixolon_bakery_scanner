import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PIL import Image

from bakery_scanner.classification.contracts import ModelProvenance, StageTimings
import scripts.benchmark_classifier_pipeline as benchmark_module
from scripts.benchmark_classifier_pipeline import (
    BenchmarkReport,
    aggregate_benchmark,
    main,
)


def _timing(*, total: float, repvit: float, dino: float) -> StageTimings:
    return StageTimings(
        repvit_ms=repvit,
        dinov3_ms=dino,
        total_ms=total,
    )


def test_benchmark_reports_percentiles_and_conditional_rate():
    report = aggregate_benchmark(
        (
            _timing(total=10, repvit=4, dino=0),
            _timing(total=20, repvit=4, dino=12),
            _timing(total=30, repvit=5, dino=18),
        )
    )

    assert report.dino_invocation_rate == pytest.approx(2 / 3)
    assert report.total_p50_ms == 20
    assert report.total_p95_ms == pytest.approx(29)
    assert report.dinov3_p50_ms == 15
    assert report.dinov3_p95_ms == pytest.approx(17.7)
    assert report.direct_path_count == 1
    assert report.direct_path_p50_ms == 10
    assert report.direct_path_p95_ms == 10
    assert report.dino_recheck_path_count == 2
    assert report.dino_recheck_path_p50_ms == 25
    assert report.dino_recheck_path_p95_ms == pytest.approx(29.5)


def test_benchmark_excludes_warmup_rows_from_every_statistic():
    report = aggregate_benchmark(
        (
            _timing(total=1_000, repvit=900, dino=800),
            _timing(total=10, repvit=4, dino=0),
            _timing(total=20, repvit=6, dino=12),
        ),
        warmup_count=1,
    )

    assert report.warmup_count == 1
    assert report.image_count == 2
    assert report.total_p50_ms == 15
    assert report.repvit_p50_ms == 5
    assert report.dino_invocation_rate == 0.5
    assert report.dinov3_p50_ms == 12
    assert report.direct_path_count == 1
    assert report.dino_recheck_path_count == 1


def test_benchmark_reports_missing_path_percentiles_as_null():
    report = aggregate_benchmark(
        (
            _timing(total=10, repvit=4, dino=0),
            _timing(total=20, repvit=6, dino=0),
        )
    )

    assert report.direct_path_count == 2
    assert report.direct_path_p50_ms == 15
    assert report.dino_recheck_path_count == 0
    assert report.dino_recheck_path_p50_ms is None
    assert report.dino_recheck_path_p95_ms is None


def test_benchmark_report_json_is_canonical_and_records_scope_and_hashes():
    aggregate = aggregate_benchmark(
        (_timing(total=10, repvit=4, dino=0),),
        warmup_count=0,
    )
    report = BenchmarkReport(
        aggregate=aggregate,
        device="CUDA:0",
        precision="FP32",
        artifact_hashes={
            "calibration_sha256": "0" * 64,
            "dinov3_support_sha256": "1" * 64,
            "dinov3_weights_sha256": "2" * 64,
            "repvit_checkpoint_sha256": "3" * 64,
            "repvit_manifest_sha256": "4" * 64,
        },
        artifact_ids={
            "dinov3": "dinov3_vits16_15plus5_v1",
            "repvit": "repvit_m1_15plus5_v1",
        },
        manifest_sha256="5" * 64,
    )

    payload = report.to_json_bytes()
    decoded = json.loads(payload)

    assert payload == json.dumps(
        decoded,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert decoded["scope"] == "classifier_only"
    assert decoded["model_preflight_count"] == 1
    assert decoded["artifacts"]["repvit_checkpoint_sha256"] == "3" * 64
    assert decoded["latency_ms"]["total"]["p95"] == 10
    assert decoded["path_latency_ms"] == {
        "dino_recheck": {
            "image_count": 0,
            "total": {"p50": None, "p95": None},
        },
        "repvit_direct": {
            "image_count": 1,
            "total": {"p50": 10, "p95": 10},
        },
    }


@pytest.mark.parametrize(
    ("timings", "warmup_count", "message"),
    [
        ((), 0, "measured"),
        ((_timing(total=1, repvit=1, dino=0),), 1, "measured"),
        ((_timing(total=1, repvit=1, dino=0),), -1, "warmup"),
    ],
)
def test_benchmark_rejects_missing_measurements(
    timings: tuple[StageTimings, ...],
    warmup_count: int,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        aggregate_benchmark(timings, warmup_count=warmup_count)


def test_benchmark_command_runs_warmups_and_writes_canonical_report(
    monkeypatch,
    tmp_path,
):
    for name in ("one.png", "two.png"):
        Image.new("RGB", (20, 20), "white").save(tmp_path / name)
    manifest = tmp_path / "benchmark.jsonl"
    manifest.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "box_xyxy": [0, 0, 20, 20],
                        "image_path": "one.png",
                        "sample_id": "bench-1",
                    }
                ),
                json.dumps(
                    {
                        "box_xyxy": [1, 1, 19, 19],
                        "image_path": "two.png",
                        "registered": True,
                        "sample_id": "bench-2",
                        "sku_id": 6,
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    provenance = ModelProvenance(
        repvit_artifact_id="repvit_m1_15plus5_v1",
        repvit_sha256="3" * 64,
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="1" * 64,
        calibration_id="policy_v1",
        calibration_sha256="0" * 64,
        repvit_manifest_sha256="4" * 64,
    )

    class _Pipeline:
        def __init__(self):
            self.calls = 0
            self.events = []
            self.config = SimpleNamespace(
                runtime=SimpleNamespace(device="CUDA:0", precision="FP32"),
                repvit=SimpleNamespace(
                    artifact_id="repvit_m1_15plus5_v1",
                    checkpoint_sha256="3" * 64,
                    manifest_sha256="4" * 64,
                ),
                dinov3=SimpleNamespace(
                    artifact_id="dinov3_vits16_15plus5_v1",
                    weights_sha256="2" * 64,
                    support_sha256="1" * 64,
                ),
            )

        def preflight_models(self, image, box):
            assert image.image.mode == "RGB"
            assert image.frame_version == "exif_visual_rgb_v1"
            assert box.xyxy == (0.0, 0.0, 20.0, 20.0)
            self.events.append("preflight_models")

        def infer(self, image, box):
            self.calls += 1
            self.events.append("infer")
            assert image.image.mode == "RGB"
            assert image.frame_version == "exif_visual_rgb_v1"
            assert box.xyxy in ((0.0, 0.0, 20.0, 20.0), (1.0, 1.0, 19.0, 19.0))
            timings = (
                _timing(total=1_000, repvit=900, dino=800)
                if self.calls <= 2
                else _timing(
                    total=10 * (self.calls - 2),
                    repvit=4,
                    dino=12 if self.calls == 4 else 0,
                )
            )
            row_provenance = (
                replace(provenance, failure_code="dino_inference_failed")
                if self.calls == 4
                else provenance
            )
            return SimpleNamespace(
                timings=timings,
                provenance=row_provenance,
            )

    pipeline = _Pipeline()
    monkeypatch.setattr(
        benchmark_module.ClassifierPipeline,
        "load",
        lambda _path: pipeline,
    )
    output = tmp_path / "benchmark.json"

    exit_code = main(
        [
            "--config",
            str(tmp_path / "classifier.yaml"),
            "--manifest",
            str(manifest),
            "--warmup",
            "2",
            "--output",
            str(output),
        ]
    )

    payload = output.read_bytes()
    report = json.loads(payload)
    assert exit_code == 0
    assert pipeline.calls == 4
    assert pipeline.events == ["preflight_models", "infer", "infer", "infer", "infer"]
    assert report["warmup_count"] == 2
    assert report["image_count"] == 2
    assert report["latency_ms"]["total"]["p50"] == 15
    assert report["dino_invocation_rate"] == 0.5
    assert payload == json.dumps(
        report,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_benchmark_does_not_write_report_when_dino_preflight_fails(
    monkeypatch,
    tmp_path,
):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (20, 20), "white").save(image_path)
    manifest = tmp_path / "benchmark.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "box_xyxy": [0, 0, 20, 20],
                "image_path": image_path.name,
                "sample_id": "bench-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _InvalidDinoPipeline:
        def preflight_models(self, image, box):
            raise ValueError("DINO artifact hash mismatch")

        def infer(self, image, box):
            pytest.fail("measurement must not start after failed DINO preflight")

    monkeypatch.setattr(
        benchmark_module.ClassifierPipeline,
        "load",
        lambda _path: _InvalidDinoPipeline(),
    )
    output = tmp_path / "benchmark.json"

    with pytest.raises(ValueError, match="DINO artifact hash mismatch"):
        main(
            [
                "--config",
                str(tmp_path / "classifier.yaml"),
                "--manifest",
                str(manifest),
                "--warmup",
                "2",
                "--output",
                str(output),
            ]
        )

    assert not output.exists()
