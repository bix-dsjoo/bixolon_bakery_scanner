from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject
from bakery_scanner.e2e.cpu_smoke import (
    run_cpu_smoke,
    select_smoke_images,
    validate_cpu_smoke_request,
)
from bakery_scanner.e2e.runtime import E2EInference


def test_select_smoke_images_is_stable_and_limited(tmp_path: Path):
    for name in ("z.JPG", "B.png", "a.jpg", "skip.txt"):
        (tmp_path / name).write_bytes(b"x")

    selected = select_smoke_images(tmp_path, limit=2)

    assert [path.name for path in selected] == ["a.jpg", "B.png"]


def test_validate_cpu_smoke_request_rejects_gpu_and_existing_output(tmp_path: Path):
    (tmp_path / "one.jpg").write_bytes(b"x")
    output = tmp_path / "report.json"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="device must be cpu"):
        validate_cpu_smoke_request(tmp_path, tmp_path / "new.json", "cuda:0", 10)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        validate_cpu_smoke_request(tmp_path, output, "cpu", 10)


def test_run_cpu_smoke_marks_unknowns_unaggregated(tmp_path: Path):
    input_path = tmp_path / "one.jpg"

    class Pipeline:
        def infer(self, image_id: int, image: object) -> E2EInference:
            return E2EInference(
                image_id,
                (
                    FinalObject(Box(0, 0, 10, 10), 1, 0.9, "repvit_direct", ()),
                    FinalObject(Box(20, 0, 10, 10), None, 0.4, "assurance_unknown", ()),
                ),
                convnext_invocations=1,
                dino_invocations=0,
                stage_timings_ms={
                    "detector": 1.0,
                    "mobile_assurance": 2.0,
                    "resolver": 3.0,
                    "repvit": 4.0,
                    "dinov3": 0.0,
                    "total": 10.0,
                },
            )

    report = run_cpu_smoke(
        Pipeline(),
        (input_path,),
        load_image=lambda _: object(),
        provenance={"device": "cpu"},
    )

    assert report["scope"] == "cpu_functional_smoke_only"
    assert report["aggregate"] == {"1": 1}
    assert report["images"][0]["final_objects"][1]["sku_id"] is None
    assert "not a release evaluation" in report["limitations"]


def test_run_cpu_smoke_summarizes_nine_stage_timings(tmp_path: Path):
    paths = tuple(tmp_path / f"{index}.jpg" for index in range(9))

    class ProfilePipeline:
        def infer(self, image_id: int, image: object) -> E2EInference:
            return E2EInference(
                image_id,
                (),
                convnext_invocations=0,
                stage_timings_ms={
                    "detector": float(image_id),
                    "mobile_assurance": float(image_id),
                    "resolver": float(image_id),
                    "repvit": float(image_id),
                    "dinov3": 0.0,
                    "total": float(image_id),
                },
            )

    report = run_cpu_smoke(
        ProfilePipeline(),
        paths,
        load_image=lambda _: object(),
        provenance={"device": "cpu"},
    )

    assert report["input_count"] == 9
    assert report["images"][8]["total_ms"] == pytest.approx(9.0)
    assert report["timing_summary_ms"]["total"] == {
        "count": 9,
        "mean": pytest.approx(5.0),
        "median": pytest.approx(5.0),
        "p95": pytest.approx(9.0),
    }


@pytest.mark.parametrize(
    "timing",
    [
        {"detector": -1.0},
        {"detector": float("inf")},
        {"detector": float("nan")},
        {},
    ],
)
def test_e2e_inference_rejects_missing_or_invalid_stage_timing(timing: dict[str, float]):
    with pytest.raises(ValueError, match="stage_timings_ms"):
        E2EInference(1, (), convnext_invocations=0, stage_timings_ms=timing)


@pytest.mark.parametrize(
    "stage_timings_ms",
    [
        {
            "detector": -1.0,
            "mobile_assurance": 0.0,
            "resolver": 0.0,
            "repvit": 0.0,
            "dinov3": 0.0,
            "total": 0.0,
        },
        {
            "detector": float("nan"),
            "mobile_assurance": 0.0,
            "resolver": 0.0,
            "repvit": 0.0,
            "dinov3": 0.0,
            "total": 0.0,
        },
        {
            "detector": float("inf"),
            "mobile_assurance": 0.0,
            "resolver": 0.0,
            "repvit": 0.0,
            "dinov3": 0.0,
            "total": 0.0,
        },
        {
            "detector": 0.0,
            "mobile_assurance": 0.0,
            "resolver": 0.0,
            "repvit": 0.0,
            "dinov3": 0.0,
        },
        {
            "detector": 0.0,
            "mobile_assurance": 0.0,
            "resolver": 0.0,
            "repvit": 0.0,
            "dinov3": 0.0,
            "total": 0.0,
            "unexpected": 1.0,
        },
    ],
)
def test_run_cpu_smoke_rejects_invalid_protocol_stage_timings(
    tmp_path: Path,
    stage_timings_ms: dict[str, float],
):
    class InvalidTimingPipeline:
        def infer(self, image_id: int, image: object) -> object:
            return SimpleNamespace(
                image_id=image_id,
                final_objects=(),
                convnext_invocations=0,
                dino_invocations=0,
                stage_timings_ms=stage_timings_ms,
            )

    with pytest.raises(ValueError, match="stage_timings_ms"):
        run_cpu_smoke(
            InvalidTimingPipeline(),
            (tmp_path / "one.jpg",),
            load_image=lambda _: object(),
            provenance={"device": "cpu"},
        )
