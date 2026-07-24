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
    output = []
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        prediction = receipt_path.parent / "validation_predictions.json"
        manifest = args.fold_root / f"fold-{receipt['fold']}" / "manifest.json"
        if not prediction.is_file() or not manifest.is_file():
            raise FileNotFoundError("every receipt needs canonical predictions and its fold manifest")
        if receipt["prediction_sha256"] != _hash(prediction) or receipt["fold_manifest_sha256"] != _hash(manifest):
            raise ValueError(f"receipt hash mismatch: {receipt['run_id']}")
        output.append({"run_id": receipt["run_id"], "receipt_sha256": _hash(receipt_path), "prediction_sha256": _hash(prediction), "fold_manifest_sha256": _hash(manifest)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
