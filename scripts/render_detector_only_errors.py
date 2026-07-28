"""Render immutable detector-only report failures on their source images."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from bakery_scanner.contracts import Box
from bakery_scanner.evaluation import MatchResult, match_boxes


_ERROR_FIELDS = (
    "misses",
    "false_positives",
    "duplicates",
    "split_errors",
    "merge_errors",
)
_THRESHOLDS = (0.50, 0.75)


@dataclass(frozen=True, slots=True)
class _OverlayJob:
    image_id: int
    fold: int
    threshold: float
    policy: Mapping[str, Any]
    error_categories: tuple[str, ...]
    source_image_path: str
    image: Path
    ground_truth: tuple[Box, ...]
    predictions: tuple[Box, ...]
    filename: str


@dataclass(frozen=True, slots=True)
class _StagedImage:
    file_name: str
    width: int
    height: int


def render_error_overlay(
    *,
    image: Path,
    ground_truth: Sequence[Box],
    predictions: Sequence[Box],
    output: Path,
    iou_threshold: float,
) -> None:
    """Render one real detector-only matching error without resizing pixels."""
    source = Path(image)
    destination = Path(output)
    if destination.suffix.lower() != ".png":
        raise ValueError("overlay output must be a PNG")
    gt = _validated_boxes(ground_truth, "ground_truth")
    predicted = _validated_boxes(predictions, "predictions")
    result = match_boxes(gt, predicted, iou_threshold)
    if not _has_error(result):
        raise ValueError("cannot render an image without a matching error")

    try:
        with Image.open(source) as opened:
            canvas = opened.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise ValueError(f"source image must be readable: {source}") from exc
    _validate_bounds(gt, canvas.width, canvas.height)
    _validate_bounds(predicted, canvas.width, canvas.height)

    draw = ImageDraw.Draw(canvas)
    _draw_boxes(draw, gt, (45, 156, 219, 255), "GT", width=1)
    _draw_boxes(
        draw,
        (predicted[prediction] for _, prediction in result.pairs),
        (46, 204, 113, 255),
        "MATCH",
        width=2,
    )
    _draw_boxes(
        draw,
        (gt[index] for index in result.misses),
        (231, 76, 60, 255),
        "MISS",
        width=3,
    )
    _draw_boxes(
        draw,
        (predicted[index] for index in result.duplicates),
        (243, 156, 18, 255),
        "DUPLICATE",
        width=3,
    )
    _draw_boxes(
        draw,
        (predicted[index] for index in result.false_positives),
        (155, 89, 182, 255),
        "FALSE POSITIVE",
        width=3,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--staged-root", type=Path)
    args = parser.parse_args()

    report_path = Path(args.report)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        parser.error(f"--output-dir already exists: {output_dir}")
    staged_root = (
        Path(args.staged_root)
        if args.staged_root is not None
        else report_path.parent.parent / "staged"
    )
    jobs = _overlay_jobs(report_path, staged_root)
    output_dir.mkdir(parents=True)
    records: list[dict[str, object]] = []
    for job in jobs:
        render_error_overlay(
            image=job.image,
            ground_truth=job.ground_truth,
            predictions=job.predictions,
            output=output_dir / job.filename,
            iou_threshold=job.threshold,
        )
        records.append(
            {
                "error_categories": list(job.error_categories),
                "fold": job.fold,
                "image_id": job.image_id,
                "iou_threshold": job.threshold,
                "overlay_filename": job.filename,
                "policy": dict(job.policy),
                "source_image_path": job.source_image_path,
            }
        )
    (output_dir / "index.json").write_text(
        json.dumps({"overlays": records}, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _overlay_jobs(report_path: Path, staged_root: Path) -> tuple[_OverlayJob, ...]:
    report = _read_json_object(report_path, "report")
    images = report.get("images")
    policies = report.get("policies")
    if not isinstance(images, dict) or not isinstance(policies, dict):
        raise ValueError("report must contain images and policies objects")
    annotations = _read_json_object(Path(staged_root) / "annotations.json", "staged annotations")
    staged_images = _annotation_images(annotations)
    jobs: list[_OverlayJob] = []
    for image_id in sorted(_report_image_id(key) for key in images):
        row = images[str(image_id)]
        if not isinstance(row, dict):
            raise ValueError("report image entries must be objects")
        fold = _nonnegative_int(row.get("fold"), "report fold")
        policy = policies.get(str(fold))
        if not isinstance(policy, dict):
            raise ValueError("report must contain a policy for every image fold")
        staged_image = staged_images.get(image_id)
        if staged_image is None:
            raise ValueError("staged annotations must contain every report image id")
        ground_truth = _report_boxes(row.get("ground_truth_boxes"), "ground_truth_boxes")
        predictions = _report_boxes(row.get("prediction_boxes"), "prediction_boxes")
        _validate_bounds(ground_truth, staged_image.width, staged_image.height)
        _validate_bounds(predictions, staged_image.width, staged_image.height)
        for threshold in _THRESHOLDS:
            reported = _reported_errors(row, threshold)
            actual = _error_counts(match_boxes(ground_truth, predictions, threshold))
            if reported != actual:
                raise ValueError(
                    f"report errors do not match boxes for image {image_id} at IoU {threshold:.2f}"
                )
            categories = tuple(sorted(field for field, count in actual.items() if count))
            if not categories:
                continue
            filename = f"image-{image_id:06d}-iou-{threshold:.2f}.png"
            jobs.append(
                _OverlayJob(
                    image_id=image_id,
                    fold=fold,
                    threshold=threshold,
                    policy=policy,
                    error_categories=categories,
                    source_image_path=staged_image.file_name,
                    image=Path(staged_root) / "images" / staged_image.file_name,
                    ground_truth=ground_truth,
                    predictions=predictions,
                    filename=filename,
                )
            )
    return tuple(jobs)


def _reported_errors(row: Mapping[str, object], threshold: float) -> dict[str, int]:
    errors = row.get("errors")
    if not isinstance(errors, dict):
        raise ValueError("report image errors must be an object")
    values = errors.get(f"{threshold:.2f}")
    if not isinstance(values, dict) or set(values) != set(_ERROR_FIELDS):
        raise ValueError(f"report errors must contain every category at IoU {threshold:.2f}")
    return {field: _nonnegative_int(values[field], f"{field} error count") for field in _ERROR_FIELDS}


def _annotation_images(annotations: Mapping[str, object]) -> dict[int, _StagedImage]:
    rows = annotations.get("images")
    if not isinstance(rows, list):
        raise ValueError("staged annotations images must be an array")
    files: dict[int, _StagedImage] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("staged annotation images must be objects")
        image_id = _positive_int(row.get("id"), "staged image id")
        file_name = row.get("file_name")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError("staged image file_name must be a non-empty string")
        path = Path(file_name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("staged image file_name must stay below staged images")
        if image_id in files:
            raise ValueError("staged annotation image ids must be unique")
        files[image_id] = _StagedImage(
            file_name=path.as_posix(),
            width=_positive_int(row.get("width"), "staged image width"),
            height=_positive_int(row.get("height"), "staged image height"),
        )
    return files


def _report_boxes(value: object, field: str) -> tuple[Box, ...]:
    if not isinstance(value, list):
        raise ValueError(f"report {field} must be an array")
    return tuple(_xyxy_box(row, field) for row in value)


def _xyxy_box(value: object, field: str) -> Box:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"report {field} boxes must be [x_min, y_min, x_max, y_max]")
    coordinates = tuple(_finite_number(item, field) for item in value)
    left, top, right, bottom = coordinates
    if right <= left or bottom <= top:
        raise ValueError(f"report {field} boxes must have positive xyxy extent")
    return Box(left, top, right - left, bottom - top)


def _validated_boxes(value: Sequence[Box], field: str) -> tuple[Box, ...]:
    boxes = tuple(value)
    if any(not isinstance(box, Box) for box in boxes):
        raise ValueError(f"{field} must contain Box values")
    return boxes


def _validate_bounds(boxes: Sequence[Box], width: int, height: int) -> None:
    for box in boxes:
        if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
            raise ValueError("source-coordinate boxes must stay within image bounds")


def _has_error(result: MatchResult) -> bool:
    return any(_error_counts(result).values())


def _error_counts(result: MatchResult) -> dict[str, int]:
    return {
        "misses": len(result.misses),
        "false_positives": len(result.false_positives),
        "duplicates": len(result.duplicates),
        "split_errors": result.split_errors,
        "merge_errors": result.merge_errors,
    }


def _draw_boxes(
    draw: ImageDraw.ImageDraw,
    boxes: Sequence[Box] | Any,
    color: tuple[int, int, int, int],
    label: str,
    *,
    width: int,
) -> None:
    for box in boxes:
        draw.rectangle(box.xyxy, outline=color, width=width)
        draw.text((box.x + 1, box.y + 1), label, fill=color)


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"report {field} coordinates must be finite numbers")
    return float(value)


def _positive_int(value: object, field: str) -> int:
    result = _nonnegative_int(value, field)
    if result <= 0:
        raise ValueError(f"{field} must be positive")
    return result


def _report_image_id(value: object) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("report image ids must be canonical positive integer strings")
    image_id = int(value)
    if image_id <= 0 or str(image_id) != value:
        raise ValueError("report image ids must be canonical positive integer strings")
    return image_id


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


if __name__ == "__main__":
    main()
