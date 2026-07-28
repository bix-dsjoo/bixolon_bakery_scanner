import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

from bakery_scanner.contracts import Box
from scripts.render_detector_only_errors import render_error_overlay


def _write_source(path: Path) -> Path:
    Image.new("RGB", (64, 48), color=(240, 230, 210)).save(path)
    return path


def test_renderer_writes_original_size_png_for_iou75_error(tmp_path):
    source = _write_source(tmp_path / "source.png")
    output = tmp_path / "overlay.png"
    gt = Box(10, 10, 20, 16)
    bad_box = Box(28, 10, 20, 16)

    render_error_overlay(
        image=source,
        ground_truth=(gt,),
        predictions=(bad_box,),
        output=output,
        iou_threshold=0.75,
    )

    assert Image.open(output).size == Image.open(source).size


def test_renderer_refuses_exact_image_without_error(tmp_path):
    source = _write_source(tmp_path / "source.png")
    output = tmp_path / "overlay.png"
    gt = Box(10, 10, 20, 16)

    with pytest.raises(ValueError, match="error"):
        render_error_overlay(
            image=source,
            ground_truth=(gt,),
            predictions=(gt,),
            output=output,
            iou_threshold=0.75,
        )


def test_renderer_rejects_source_coordinate_box_outside_image(tmp_path):
    source = _write_source(tmp_path / "source.png")

    with pytest.raises(ValueError, match="bounds"):
        render_error_overlay(
            image=source,
            ground_truth=(Box(50, 10, 20, 16),),
            predictions=(),
            output=tmp_path / "overlay.png",
            iou_threshold=0.75,
        )


def test_cli_writes_deterministic_error_index_from_immutable_report(tmp_path):
    staged = tmp_path / "staged"
    images = staged / "images"
    images.mkdir(parents=True)
    _write_source(images / "receipt-1.png")
    (staged / "annotations.json").write_text(
        json.dumps(
            {
                "images": [
                    {
                        "id": 1,
                        "file_name": "receipt-1.png",
                        "width": 64,
                        "height": 48,
                    }
                ],
                "annotations": [],
                "categories": [{"id": 1, "name": "bread"}],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "reports" / "detector_only_development.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "images": {
                    "1": {
                        "errors": {
                            "0.50": {
                                "misses": 0,
                                "false_positives": 0,
                                "duplicates": 0,
                                "split_errors": 0,
                                "merge_errors": 0,
                            },
                            "0.75": {
                                "misses": 1,
                                "false_positives": 1,
                                "duplicates": 0,
                                "split_errors": 0,
                                "merge_errors": 0,
                            },
                        },
                        "fold": 0,
                        "ground_truth_boxes": [[10.0, 10.0, 30.0, 26.0]],
                        "prediction_boxes": [[15.0, 10.0, 35.0, 26.0]],
                    }
                },
                "policies": {"0": {"raw_source": "native", "score_threshold": 0.5}},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "detector_only_errors"
    environment = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_detector_only_errors.py",
            "--report",
            str(report),
            "--output-dir",
            str(output),
            "--staged-root",
            str(staged),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    assert index == {
        "overlays": [
            {
                "error_categories": ["false_positives", "misses"],
                "fold": 0,
                "image_id": 1,
                "iou_threshold": 0.75,
                "overlay_filename": "image-000001-iou-0.75.png",
                "policy": {"raw_source": "native", "score_threshold": 0.5},
                "source_image_path": "receipt-1.png",
            }
        ]
    }
    assert Image.open(output / "image-000001-iou-0.75.png").size == (64, 48)


def test_cli_refuses_existing_output_directory(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    environment = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_detector_only_errors.py",
            "--report",
            str(tmp_path / "report.json"),
            "--output-dir",
            str(output),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "already exists" in result.stderr


def _write_zero_error_inputs(tmp_path: Path, boxes: list[object]) -> tuple[Path, Path]:
    staged = tmp_path / "staged"
    images = staged / "images"
    images.mkdir(parents=True)
    _write_source(images / "receipt-1.png")
    (staged / "annotations.json").write_text(
        json.dumps(
            {
                "images": [
                    {
                        "id": 1,
                        "file_name": "receipt-1.png",
                        "width": 64,
                        "height": 48,
                    }
                ],
                "annotations": [],
                "categories": [{"id": 1, "name": "bread"}],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "reports" / "detector_only_development.json"
    report.parent.mkdir()
    report.write_text(
        json.dumps(
            {
                "images": {
                    "1": {
                        "errors": {
                            threshold: {
                                "misses": 0,
                                "false_positives": 0,
                                "duplicates": 0,
                                "split_errors": 0,
                                "merge_errors": 0,
                            }
                            for threshold in ("0.50", "0.75")
                        },
                        "fold": 0,
                        "ground_truth_boxes": boxes,
                        "prediction_boxes": boxes,
                    }
                },
                "policies": {"0": {"raw_source": "native", "score_threshold": 0.5}},
            }
        ),
        encoding="utf-8",
    )
    return report, staged


def test_cli_writes_empty_index_for_valid_all_zero_error_report(tmp_path):
    report, staged = _write_zero_error_inputs(
        tmp_path,
        [[10.0, 10.0, 30.0, 26.0]],
    )
    output = tmp_path / "detector_only_errors"
    environment = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_detector_only_errors.py",
            "--report",
            str(report),
            "--output-dir",
            str(output),
            "--staged-root",
            str(staged),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((output / "index.json").read_text(encoding="utf-8")) == {
        "overlays": []
    }


@pytest.mark.parametrize(
    ("box", "message"),
    [
        ([10.0, 10.0, 30.0], "xyxy"),
        ([float("nan"), 10.0, 30.0, 26.0], "finite"),
        ([50.0, 10.0, 70.0, 26.0], "bounds"),
    ],
)
def test_cli_rejects_invalid_zero_error_report_boxes(tmp_path, box, message):
    report, staged = _write_zero_error_inputs(tmp_path, [box])
    output = tmp_path / "detector_only_errors"
    environment = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_detector_only_errors.py",
            "--report",
            str(report),
            "--output-dir",
            str(output),
            "--staged-root",
            str(staged),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert not output.exists()
