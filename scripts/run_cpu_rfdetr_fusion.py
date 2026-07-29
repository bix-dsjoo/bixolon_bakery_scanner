"""Run the fixed nine Batch2 images through packaged RF-DETR-L and fusion on CPU."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from PIL import Image, ImageDraw

from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import load_canonical_image
from bakery_scanner.detectors.rfdetr import RFDetrRunner
from bakery_scanner.e2e.cpu_profile import resolve_batch2_e3_m3_h3
from bakery_scanner.e2e.rfdetr_cpu import summarize_profiles


def _iou(left: Box, right: Box) -> float:
    x1 = max(left.x, right.x)
    y1 = max(left.y, right.y)
    x2 = min(left.x + left.width, right.x + right.width)
    y2 = min(left.y + left.height, right.y + right.height)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection == 0.0:
        return 0.0
    return intersection / (left.width * left.height + right.width * right.height - intersection)


def _ground_truth(path: Path) -> dict[str, list[tuple[Box, int]]]:
    result: dict[str, list[tuple[Box, int]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        image_name = Path(row["image_path"]).name
        x1, y1, x2, y2 = row["box_xyxy"]
        result.setdefault(image_name, []).append((Box(x1, y1, x2 - x1, y2 - y1), int(row["sku_id"])))
    return result


def _match(proposals, decisions, targets: list[tuple[Box, int]]) -> tuple[dict[str, int], list[dict[str, object]]]:
    pairs = sorted(
        ((_iou(proposal.box, target[0]), proposal_index, target_index)
         for proposal_index, proposal in enumerate(proposals)
         for target_index, target in enumerate(targets)),
        reverse=True,
    )
    used_proposals: set[int] = set()
    used_targets: set[int] = set()
    records: list[dict[str, object]] = []
    top1 = top3 = 0
    for overlap, proposal_index, target_index in pairs:
        if overlap < 0.5 or proposal_index in used_proposals or target_index in used_targets:
            continue
        used_proposals.add(proposal_index)
        used_targets.add(target_index)
        decision = decisions[proposal_index]
        expected = targets[target_index][1]
        candidates = [decision.sku_id] if decision.decision == "sku" else [item.sku_id for item in decision.top3]
        correct_top1 = decision.decision == "sku" and decision.sku_id == expected
        correct_top3 = expected in candidates
        top1 += int(correct_top1)
        top3 += int(correct_top3)
        records.append({
            "box_xyxy": list(proposals[proposal_index].box.xyxy),
            "decision": decision.decision,
            "predicted_sku_id": decision.sku_id,
            "top3": candidates,
            "ground_truth_sku_id": expected,
            "iou": overlap,
            "top1_correct": correct_top1,
            "top3_correct": correct_top3,
            "unknown_reason": decision.unknown_reason,
        })
    return {
        "gt": len(targets), "predictions": len(proposals), "matched": len(used_targets),
        "fp": len(proposals) - len(used_proposals), "fn": len(targets) - len(used_targets),
        "top1": top1, "top3": top3,
    }, records


def _write_overlay(frame, records: list[dict[str, object]], path: Path) -> None:
    image = frame.image.copy()
    draw = ImageDraw.Draw(image)
    for record in records:
        x1, y1, x2, y2 = record["box_xyxy"]
        label = str(record["predicted_sku_id"] if record["predicted_sku_id"] is not None else "Unknown")
        draw.rectangle((x1, y1, x2, y2), outline="lime" if record["decision"] == "sku" else "red", width=3)
        draw.text((x1, max(0, y1 - 16)), label, fill="lime" if record["decision"] == "sku" else "red")
    image.save(path, format="PNG")


def run(package_root: Path, output: Path) -> dict[str, object]:
    root = package_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    manifest = json.loads((root / "models" / "rfdetr_large_bakery_v1" / "manifest.json").read_text(encoding="utf-8"))
    classifier = ClassifierPipeline.load(root / "configs" / "cpu_rfdetr_classifier_policy.yaml")
    detector = RFDetrRunner.load(
        root / "models" / "rfdetr_large_bakery_v1" / manifest["checkpoint"]["file"],
        score_threshold=float(manifest["score_threshold"]),
        device="cpu",
    )
    images = resolve_batch2_e3_m3_h3(root / "samples" / "batch2_e3_m3_h3")
    targets = _ground_truth(root / "artifacts" / "e2e_current_source" / "classification" / "evidence-parts" / "group_20class_batch02.jsonl")
    first = load_canonical_image(images[0])
    warm_proposals = detector.predict(1, first.image)
    if not warm_proposals:
        raise RuntimeError("RF-DETR CPU warm-up produced no proposals")
    classifier.infer(first, warm_proposals[0].box)

    staging = output.parent / f".{output.name}.staging-{uuid4().hex}"
    staging.mkdir(parents=True)
    overlays = staging / "overlays"
    overlays.mkdir()
    totals = {"gt": 0, "predictions": 0, "matched": 0, "fp": 0, "fn": 0, "top1": 0, "top3": 0}
    rows: list[dict[str, object]] = []
    try:
        for image_id, image_path in enumerate(images, start=1):
            frame = load_canonical_image(image_path)
            started = time.perf_counter()
            proposals = detector.predict(image_id, frame.image)
            decisions = [classifier.infer(frame, proposal.box) for proposal in proposals]
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            metric, records = _match(proposals, decisions, targets[image_path.name])
            for key in totals:
                totals[key] += metric[key]
            profile = image_path.stem.split("_")[2].upper()
            row = {"image": image_path.name, "profile": profile, "elapsed_ms": elapsed_ms, "objects": records, **metric}
            rows.append(row)
            _write_overlay(frame, records, overlays / f"{image_path.stem}.png")
        report = {
            "schema_version": 1,
            "device": "CPU",
            "detector": manifest["source_label"],
            "fusion_policy": classifier.fusion_policy.decision_rule if classifier.fusion_policy else None,
            "iou_threshold": 0.5,
            "profiles": summarize_profiles(rows),
            "metrics": {**totals, "top1_rate": totals["top1"] / totals["gt"], "top3_rate": totals["top3"] / totals["gt"]},
            "images": rows,
        }
        (staging / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.replace(output)
        return report
    except Exception:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(args.package_root, args.output.resolve())
    print(json.dumps({"profiles": report["profiles"], "metrics": report["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
