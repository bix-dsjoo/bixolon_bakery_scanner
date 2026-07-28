"""Evaluate existing OOF detector/verifier boxes with existing SKU models only."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.config import ScannerConfig
from bakery_scanner.contracts import Box
from bakery_scanner.data.coco import load_staged_dataset
from bakery_scanner.data.preprocess import load_canonical_image
from bakery_scanner.e2e.contracts import FinalObject
from bakery_scanner.e2e.ground_truth import load_source_sku_ground_truth
from bakery_scanner.e2e.metrics import E2EImageResult, evaluate_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--classes", type=Path, default=Path("datasets/classes.json"))
    parser.add_argument("--detector-report", type=Path, default=Path("artifacts/box_system/reports/detector_only_development.json"))
    parser.add_argument("--classifier-config", type=Path, default=Path("configs/classifier_policy.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite report: {args.output}")

    config = ScannerConfig.load(args.config)
    labels = load_source_sku_ground_truth(config, classes_path=args.classes)
    report = json.loads(args.detector_report.read_text(encoding="utf-8"))
    images = report.get("images")
    if not isinstance(images, dict) or set(map(int, images)) != set(labels):
        raise ValueError("existing detector report must cover exactly the configured 299 images")
    staged = load_staged_dataset(config.artifact_root / "staged")
    staged_by_id = {row.image_id: row for row in staged.images}
    classifier = ClassifierPipeline.load(args.classifier_config)
    results: list[E2EImageResult] = []
    decisions: dict[str, list[dict[str, object]]] = {}
    for image_id in sorted(labels):
        row = images[str(image_id)]
        xyxy_boxes = row.get("prediction_boxes")
        if not isinstance(xyxy_boxes, list):
            raise ValueError("existing detector report prediction_boxes must be an array")
        image = load_canonical_image(staged.root / "images" / staged_by_id[image_id].file_name)
        started = time.perf_counter()
        final: list[FinalObject] = []
        image_decisions: list[dict[str, object]] = []
        for xyxy in xyxy_boxes:
            if not isinstance(xyxy, list) or len(xyxy) != 4:
                raise ValueError("existing detector report boxes must be xyxy")
            x1, y1, x2, y2 = (float(value) for value in xyxy)
            box = Box(x1, y1, x2 - x1, y2 - y1)
            decision = classifier.infer(image, box)
            path = getattr(decision.decision_path, "value", decision.decision_path)
            top3 = tuple(candidate.sku_id for candidate in decision.top3)
            final.append(FinalObject(decision.box, decision.sku_id, decision.confidence, path, top3))
            image_decisions.append({"box_xyxy": list(box.xyxy), "sku_id": decision.sku_id, "decision_path": path, "top3": list(top3), "classifier_ms": decision.timings.total_ms})
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        results.append(E2EImageResult(image_id, tuple(final), elapsed_ms))
        decisions[str(image_id)] = image_decisions
    evaluation = evaluate_run(labels, tuple(results))
    payload = {
        "schema_version": 1,
        "scope": "existing_detector_verifier_oof_classifier_replay",
        "limitations": [
            "Detector and verifier boxes are existing cached grouped-OOF outputs; they were not re-executed during this replay.",
            "Latency is classifier replay latency per image, not whole-pipeline E2E latency.",
            "The legacy detector report contains 1410 boxes while current source SKU truth contains 1409 boxes.",
        ],
        "metrics": {"iou_0.50": asdict(evaluation.iou50), "iou_0.75": asdict(evaluation.iou75)},
        "classifier_replay_latency_ms": asdict(evaluation.latency),
        "decisions": decisions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "images": len(results), "objects": sum(len(row.final_objects) for row in results)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
