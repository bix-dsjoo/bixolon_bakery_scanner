"""Fail-fast global receipt/artifact inventory for the 60 grouped OOF runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector-root", type=Path, required=True)
    parser.add_argument("--fold-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipts = sorted(args.detector_root.glob("*-seed*-fold*/receipt.json"))
    if len(receipts) != 60:
        raise ValueError(f"expected 60 detector receipts, got {len(receipts)}")
    expected = {f"{name}-seed{seed}-fold{fold}" for name in ("dfine_n_640", "dfine_n_768", "rtmdet_tiny_640", "rtmdet_tiny_768") for seed in (20260724, 20260725, 20260726) for fold in range(5)}
    output = []
    seen_runs = set()
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["run_id"] in seen_runs or receipt["run_id"] not in expected:
            raise ValueError("unexpected or duplicate detector run ID")
        seen_runs.add(receipt["run_id"])
        prediction = receipt_path.parent / "validation_predictions.json"
        manifest = args.fold_root / f"fold-{receipt['fold']}" / "manifest.json"
        if not prediction.is_file() or not manifest.is_file():
            raise FileNotFoundError("every receipt needs canonical predictions and its fold manifest")
        if receipt["prediction_sha256"] != _hash(prediction) or receipt["fold_manifest_sha256"] != _hash(manifest):
            raise ValueError(f"receipt hash mismatch: {receipt['run_id']}")
        fold = json.loads(manifest.read_text(encoding="utf-8"))
        validation_ids = {int(value) for value in fold["validation_image_ids"]}
        validation_scenes = {(row["capture_batch"], row["scene_number"]) for row in fold["validation_scenes"]}
        training_scenes = {(row["capture_batch"], row["scene_number"]) for row in fold["training_scenes"]}
        if validation_scenes & training_scenes:
            raise ValueError("train/validation scene leakage in fold manifest")
        predictions = json.loads(prediction.read_text(encoding="utf-8"))
        for row in predictions:
            if int(row["image_id"]) not in validation_ids:
                raise ValueError("prediction image is not in its held-out fold")
            output.append({"run_id": receipt["run_id"], "image_id": int(row["image_id"]), "source": row["source"], "score": row["score"], "bbox": row["bbox"], "receipt_sha256": _hash(receipt_path), "prediction_sha256": _hash(prediction), "fold_manifest_sha256": _hash(manifest)})
    if seen_runs != expected:
        raise ValueError("incomplete 4x3x5 detector matrix")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
