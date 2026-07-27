"""Convert documented D-FINE COCO JSON or MMDetection pickle outputs to JSON."""

from __future__ import annotations

import argparse
import json
import math
import pickle
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("dfine", "rtmdet"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-format", choices=("dfine-coco-json", "mmdet-pickle"), required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--processed-output", type=Path, required=True)
    args = parser.parse_args()
    if args.backend == "dfine" and args.input_format != "dfine-coco-json":
        raise ValueError("D-FINE OOF adapter requires the evaluator's COCO JSON result")
    if args.backend == "rtmdet" and args.input_format != "mmdet-pickle":
        raise ValueError("MMDetection OOF adapter requires tools/test.py --out pickle")
    dimensions = _image_dimensions(args.annotations)
    rows, processed = _dfine_rows(args.input, args.source) if args.backend == "dfine" else _mmdet_rows(args.input, args.source)
    rows = _clip_rows(rows, dimensions)
    if not processed <= dimensions.keys():
        raise ValueError("processed image id is not present in annotations")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sorted(rows, key=lambda row: (row["image_id"], -row["score"], row["bbox"])), sort_keys=True, separators=(",", ":")), encoding="utf-8")
    args.processed_output.write_text(json.dumps(sorted(processed), separators=(",", ":")), encoding="utf-8")


def _dfine_rows(path: Path, source: str) -> tuple[list[dict[str, object]], set[int]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("predictions"), list) or not isinstance(value.get("processed_image_ids"), list):
        raise ValueError("D-FINE export must include predictions and actual processed_image_ids")
    return ([_row(item["image_id"], item["bbox"], item["score"], source, item.get("category_id", 1)) for item in value["predictions"]], {int(value) for value in value["processed_image_ids"]})


def _mmdet_rows(path: Path, source: str) -> tuple[list[dict[str, object]], set[int]]:
    # The file is produced locally by the pinned MMDetection tools/test.py.
    with path.open("rb") as handle:
        samples = pickle.load(handle)
    rows: list[dict[str, object]] = []
    processed: set[int] = set()
    for sample in samples:
        instances = _get(sample, "pred_instances")
        image_id = _get(_get(sample, "metainfo"), "img_id")
        processed.add(int(image_id))
        for bbox, score, label in zip(_tolist(_get(instances, "bboxes")), _tolist(_get(instances, "scores")), _tolist(_get(instances, "labels")), strict=True):
            x1, y1, x2, y2 = bbox
            rows.append(_row(image_id, [x1, y1, x2 - x1, y2 - y1], score, source, label + 1))
    return rows, processed


def _get(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)


def _tolist(value: object) -> list[object]:
    return value.tolist() if hasattr(value, "tolist") else list(value)  # type: ignore[arg-type]


def _row(image_id: object, bbox: object, score: object, source: str, category_id: object) -> dict[str, object]:
    # D-FINE postprocessor labels are zero-based model labels; canonical COCO
    # category id for the one bread class is always one.
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("only four-value bread COCO boxes are valid")
    if int(category_id) not in {0, 1}:
        raise ValueError("only the single bread model class is valid")
    return {"image_id": int(image_id), "source": source, "score": float(score), "bbox": [float(value) for value in bbox]}


def _image_dimensions(path: Path) -> dict[int, tuple[int, int]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    images = value.get("images") if isinstance(value, dict) else None
    if not isinstance(images, list):
        raise ValueError("annotations must contain an images array")
    dimensions: dict[int, tuple[int, int]] = {}
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("annotation image must be an object")
        image_id, width, height = image.get("id"), image.get("width"), image.get("height")
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or isinstance(width, bool)
            or not isinstance(width, int)
            or isinstance(height, bool)
            or not isinstance(height, int)
            or image_id <= 0
            or width <= 0
            or height <= 0
            or image_id in dimensions
        ):
            raise ValueError("annotation images must have unique positive ids and dimensions")
        dimensions[image_id] = (width, height)
    return dimensions


def _clip_rows(rows: list[dict[str, object]], dimensions: dict[int, tuple[int, int]]) -> list[dict[str, object]]:
    clipped: list[dict[str, object]] = []
    for row in rows:
        image_id = row["image_id"]
        if image_id not in dimensions:
            raise ValueError("prediction image id is not present in annotations")
        bbox = row["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("canonical prediction bbox must be xywh")
        x, y, width, height = (float(value) for value in bbox)
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            raise ValueError("canonical prediction coordinates must be finite")
        image_width, image_height = dimensions[image_id]
        left, top = min(max(x, 0.0), image_width), min(max(y, 0.0), image_height)
        right, bottom = min(max(x + width, 0.0), image_width), min(max(y + height, 0.0), image_height)
        if right <= left or bottom <= top:
            continue
        clipped.append({**row, "bbox": [left, top, right - left, bottom - top]})
    return clipped


if __name__ == "__main__":
    main()
