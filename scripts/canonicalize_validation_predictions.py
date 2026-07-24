"""Convert documented D-FINE COCO JSON or MMDetection pickle outputs to JSON."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("dfine", "rtmdet"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-format", choices=("dfine-coco-json", "mmdet-pickle"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.backend == "dfine" and args.input_format != "dfine-coco-json":
        raise ValueError("D-FINE OOF adapter requires the evaluator's COCO JSON result")
    if args.backend == "rtmdet" and args.input_format != "mmdet-pickle":
        raise ValueError("MMDetection OOF adapter requires tools/test.py --out pickle")
    rows = _dfine_rows(args.input, args.source) if args.backend == "dfine" else _mmdet_rows(args.input, args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sorted(rows, key=lambda row: (row["image_id"], -row["score"], row["bbox"])), sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _dfine_rows(path: Path, source: str) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("D-FINE evaluator output must be a COCO result list")
    return [_row(item["image_id"], item["bbox"], item["score"], source, item.get("category_id", 1)) for item in value]


def _mmdet_rows(path: Path, source: str) -> list[dict[str, object]]:
    # The file is produced locally by the pinned MMDetection tools/test.py.
    with path.open("rb") as handle:
        samples = pickle.load(handle)
    rows: list[dict[str, object]] = []
    for sample in samples:
        instances = _get(sample, "pred_instances")
        image_id = _get(_get(sample, "metainfo"), "img_id")
        for bbox, score, label in zip(_tolist(_get(instances, "bboxes")), _tolist(_get(instances, "scores")), _tolist(_get(instances, "labels")), strict=True):
            x1, y1, x2, y2 = bbox
            rows.append(_row(image_id, [x1, y1, x2 - x1, y2 - y1], score, source, label + 1))
    return rows


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


if __name__ == "__main__":
    main()
