"""Select RF-DETR thresholds on calibration rows and freeze evaluation metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from tools.train.train_rfdetr_bread_oof import _is_sha256, _load_manifest


_ERRORS = ("miss", "duplicate", "non_target", "split", "merge")


@dataclass(frozen=True, slots=True)
class DetectorMetrics:
    matched: int
    error_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class DetectorPolicyReceipt:
    score_threshold: float
    selected_from_image_ids: tuple[int, ...]
    calibration_metrics: DetectorMetrics
    non_target_rejection: str = "unverified_without_negative_scenes"


def evaluate_bound_detector(
    calibration_rows: Sequence[Mapping[str, object]],
    evaluation_rows: Sequence[Mapping[str, object]],
    *,
    split_manifest: Mapping[str, object] | Path,
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Select on the exact calibration role, then evaluate the frozen policy once."""
    manifest = _load_manifest(split_manifest)
    calibration = _normalise_bound_rows(calibration_rows, manifest["scene_ids"]["calibration"], "calibration")
    evaluation = _normalise_bound_rows(evaluation_rows, manifest["scene_ids"]["evaluation"], "evaluation")
    verified_provenance = _verify_provenance(provenance, manifest)
    policy = select_detector_policy(calibration, evaluation)
    frozen_threshold = policy.score_threshold
    frozen = evaluate_detector(
        [target for row in evaluation for target in row["ground_truth"]],
        [prediction for row in evaluation for prediction in row["predictions"] if prediction["score"] >= frozen_threshold],
    )
    receipt = {
        "evaluation": {"matched": frozen.matched, "error_counts": frozen.error_counts},
        "policy": {
            "calibration_metrics": {"matched": policy.calibration_metrics.matched, "error_counts": policy.calibration_metrics.error_counts},
            "non_target_rejection": policy.non_target_rejection,
            "score_threshold": frozen_threshold,
            "selected_from_image_ids": list(policy.selected_from_image_ids),
        },
        "provenance": verified_provenance,
        "role_scene_ids": {"calibration": list(manifest["scene_ids"]["calibration"]), "evaluation": list(manifest["scene_ids"]["evaluation"])},
        "status": "verified_success",
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def evaluate_artifact_bound_detector(
    *, split_manifest: Path, artifacts: Mapping[str, Mapping[str, object]], allowed_root: Path
) -> dict[str, object]:
    """Load and verify every external evaluation input before detector policy selection."""
    required = {"staged_manifest", "staged_annotations", "detector_checkpoint", "calibration_predictions", "evaluation_predictions", "evaluation_config", "code_identity", "runtime_identity"}
    if set(artifacts) != required:
        raise ValueError("evaluation artifacts must contain the exact required semantic roles")
    verified = {role: _verify_artifact_descriptor(artifacts[role], role, allowed_root) for role in sorted(required)}
    code_path = verified["code_identity"]["path"]
    if code_path != Path(__file__).resolve():
        raise ValueError("code identity artifact must identify this evaluator implementation")
    json.loads(verified["staged_manifest"]["bytes_data"].decode("utf-8"))
    json.loads(verified["staged_annotations"]["bytes_data"].decode("utf-8"))
    json.loads(verified["evaluation_config"]["bytes_data"].decode("utf-8"))
    runtime_payload = json.loads(verified["runtime_identity"]["bytes_data"].decode("utf-8"))
    from tools.train.train_rfdetr_bread_oof import _verify_runtime_identity
    _verify_runtime_identity(runtime_payload)
    calibration_rows = json.loads(verified["calibration_predictions"]["bytes_data"].decode("utf-8"))
    evaluation_rows = json.loads(verified["evaluation_predictions"]["bytes_data"].decode("utf-8"))
    provenance = {
        "fold_manifest_sha256": _load_manifest(split_manifest)["manifest_sha256"],
        "source_sha256": _load_manifest(split_manifest)["source_sha256"],
        "staged_annotations_sha256": verified["staged_annotations"]["sha256"],
        "staged_manifest_sha256": verified["staged_manifest"]["sha256"],
        "detector_checkpoint_sha256": verified["detector_checkpoint"]["sha256"],
        "calibration_predictions_sha256": verified["calibration_predictions"]["sha256"],
        "evaluation_predictions_sha256": verified["evaluation_predictions"]["sha256"],
        "config_sha256": verified["evaluation_config"]["sha256"],
        "code_sha256": verified["code_identity"]["sha256"],
        "runtime_identity_sha256": verified["runtime_identity"]["sha256"],
    }
    receipt = evaluate_bound_detector(calibration_rows, evaluation_rows, split_manifest=split_manifest, provenance=provenance)
    receipt["verified_artifacts"] = {role: {"bytes": item["bytes"], "sha256": item["sha256"]} for role, item in verified.items()}
    receipt["receipt_sha256"] = _canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    return receipt


def _verify_artifact_descriptor(descriptor: Mapping[str, object], role: str, allowed_root: Path) -> dict[str, object]:
    if set(descriptor) != {"role", "path", "bytes", "sha256"} or descriptor.get("role") != role or not isinstance(descriptor.get("path"), str) or not isinstance(descriptor.get("bytes"), int) or not _is_sha256(descriptor.get("sha256")):
        raise ValueError(f"{role} artifact descriptor is invalid")
    root = allowed_root.resolve()
    path = Path(str(descriptor["path"])).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError(f"{role} artifact is missing or outside allowed root")
    with path.open("rb") as handle:
        bytes_data = handle.read()
    if len(bytes_data) != descriptor["bytes"] or hashlib.sha256(bytes_data).hexdigest() != descriptor["sha256"]:
        raise ValueError(f"{role} artifact byte identity mismatch")
    return {"path": path, "bytes": descriptor["bytes"], "sha256": descriptor["sha256"], "bytes_data": bytes_data}


def _canonical_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_detector_policy(calibration_rows: Sequence[Mapping[str, object]], evaluation_rows: Sequence[Mapping[str, object]]) -> DetectorPolicyReceipt:
    """Choose a threshold solely from calibration rows; evaluation is leak-checked only."""
    calibration = tuple(_normalise_rows(calibration_rows))
    evaluation_ids = {row["image_id"] for row in _normalise_rows(evaluation_rows)}
    calibration_ids = tuple(sorted(row["image_id"] for row in calibration))
    if len(set(calibration_ids)) != len(calibration_ids):
        raise ValueError("calibration image IDs must be unique")
    if set(calibration_ids) & evaluation_ids:
        raise ValueError("calibration and evaluation image IDs must be disjoint")
    if not calibration:
        raise ValueError("calibration rows are required to select detector policy")
    thresholds = sorted({prediction["score"] for row in calibration for prediction in row["predictions"]})
    if not thresholds:
        raise ValueError("calibration predictions are required to select detector policy")
    candidates = []
    for threshold in thresholds:
        metrics = evaluate_detector(
            [ground_truth for row in calibration for ground_truth in row["ground_truth"]],
            [prediction for row in calibration for prediction in row["predictions"] if prediction["score"] >= threshold],
        )
        critical = sum(metrics.error_counts[name] for name in ("miss", "duplicate", "split", "merge"))
        retakes = metrics.error_counts["non_target"]
        candidates.append((critical, retakes, -threshold, metrics, threshold))
    _, _, _, metrics, threshold = min(candidates)
    return DetectorPolicyReceipt(threshold, calibration_ids, metrics)


def evaluate_detector(
    ground_truth: Iterable[Mapping[str, object]], predictions: Iterable[Mapping[str, object]], *, iou_threshold: float = 0.50
) -> DetectorMetrics:
    """Deterministically match detection boxes one-to-one at the requested IoU."""
    if iou_threshold != 0.50:
        raise ValueError("RF-DETR OOF evaluation uses immutable IoU 0.50")
    gt = tuple(_normalise_objects(ground_truth, require_score=False))
    predicted = tuple(_normalise_objects(predictions, require_score=True))
    by_image_gt = _by_image(gt)
    by_image_predicted = _by_image(predicted)
    counts = {name: 0 for name in _ERRORS}
    matched = 0
    for image_id in sorted(set(by_image_gt) | set(by_image_predicted)):
        image_gt = by_image_gt.get(image_id, ())
        image_predictions = by_image_predicted.get(image_id, ())
        overlaps = [
            (index_predicted, index_gt, _iou(prediction["box"], target["box"]))
            for index_predicted, prediction in enumerate(image_predictions)
            for index_gt, target in enumerate(image_gt)
        ]
        eligible = [row for row in overlaps if row[2] >= iou_threshold]
        used_predictions: set[int] = set()
        used_gt: set[int] = set()
        for index_predicted, index_gt, _ in sorted(eligible, key=lambda row: (-row[2], row[0], row[1])):
            if index_predicted not in used_predictions and index_gt not in used_gt:
                used_predictions.add(index_predicted)
                used_gt.add(index_gt)
                matched += 1
        counts["miss"] += len(image_gt) - len(used_gt)
        for index_predicted, _prediction in enumerate(image_predictions):
            if index_predicted in used_predictions:
                continue
            overlapping_gt = [index_gt for candidate_prediction, index_gt, _ in eligible if candidate_prediction == index_predicted]
            if overlapping_gt:
                counts["duplicate"] += 1
            else:
                counts["non_target"] += 1
        counts["split"] += sum(1 for index_gt in range(len(image_gt)) if sum(index_gt == candidate_gt for _, candidate_gt, _ in eligible) > 1)
        counts["merge"] += sum(1 for index_predicted in range(len(image_predictions)) if sum(index_predicted == candidate_prediction for candidate_prediction, _, _ in eligible) > 1)
    return DetectorMetrics(matched, counts)


def _normalise_rows(rows: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    output = []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("image_id"), int):
            raise ValueError("detector row must contain integer image_id")
        output.append({
            "image_id": row["image_id"],
            "ground_truth": tuple(_normalise_objects(row.get("ground_truth", ()), require_score=False, image_id=row["image_id"])),
            "predictions": tuple(_normalise_objects(row.get("predictions", ()), require_score=True, image_id=row["image_id"])),
        })
    return tuple(output)


def _normalise_bound_rows(rows: Sequence[Mapping[str, object]], expected_scene_ids: Sequence[str], role: str) -> tuple[dict[str, object], ...]:
    normalised = _normalise_rows(rows)
    scenes: list[str] = []
    for original in rows:
        scene_id = original.get("scene_id") if isinstance(original, Mapping) else None
        if not isinstance(scene_id, str) or not scene_id:
            raise ValueError(f"{role} row must contain scene_id")
        scenes.append(scene_id)
    if len(set(scenes)) != len(scenes) or set(scenes) != set(expected_scene_ids) or len(scenes) != len(expected_scene_ids):
        raise ValueError(f"{role} rows must exactly match declared split role scene IDs")
    if len({row["image_id"] for row in normalised}) != len(normalised):
        raise ValueError(f"{role} image IDs must be unique")
    return normalised


def _verify_provenance(provenance: Mapping[str, object], manifest: Mapping[str, object]) -> dict[str, str]:
    required = (
        "fold_manifest_sha256", "source_sha256", "staged_annotations_sha256", "staged_manifest_sha256",
        "detector_checkpoint_sha256", "calibration_predictions_sha256", "evaluation_predictions_sha256",
        "config_sha256", "code_sha256", "runtime_identity_sha256",
    )
    if set(provenance) != set(required):
        raise ValueError("detector provenance must contain the complete declared hash set")
    result = {key: str(provenance[key]) for key in required}
    if any(not _is_sha256(value) for value in result.values()):
        raise ValueError("detector provenance values must be SHA-256")
    if result["fold_manifest_sha256"] != manifest["manifest_sha256"] or result["source_sha256"] != manifest["source_sha256"]:
        raise ValueError("detector provenance does not bind the verified split manifest")
    return result


def _canonical_sha256(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_json_new_atomic(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing evaluation receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise FileExistsError(f"refusing to replace evaluation receipt temporary file: {temporary}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def _normalise_objects(rows: Iterable[Mapping[str, object]], *, require_score: bool, image_id: int | None = None) -> tuple[dict[str, object], ...]:
    output = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("detector object must be a mapping")
        actual_image_id = image_id if image_id is not None else row.get("image_id")
        if not isinstance(actual_image_id, int):
            raise ValueError("detector object must contain integer image_id")
        box = row.get("box")
        if not isinstance(box, Sequence) or isinstance(box, (str, bytes)) or len(box) != 4 or any(not isinstance(value, (int, float)) for value in box):
            raise ValueError("detector object box must be four numeric xywh values")
        x, y, width, height = (float(value) for value in box)
        if width <= 0 or height <= 0:
            raise ValueError("detector object box must have positive area")
        value = {"image_id": actual_image_id, "box": (x, y, width, height)}
        if require_score:
            score = row.get("score")
            if not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
                raise ValueError("prediction score must be within [0, 1]")
            value["score"] = float(score)
        output.append(value)
    return tuple(output)


def _by_image(rows: Sequence[dict[str, object]]) -> dict[int, tuple[dict[str, object], ...]]:
    output: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        output.setdefault(row["image_id"], []).append(row)
    return {image_id: tuple(values) for image_id, values in output.items()}


def _iou(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[0] + first[2], second[0] + second[2]), min(first[1] + first[3], second[1] + second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    return intersection / (first[2] * first[3] + second[2] * second[3] - intersection)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--allowed-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evaluation receipt: {output}")
    if arguments.artifacts is None or arguments.allowed_root is None:
        raise ValueError("--artifacts and --allowed-root are required for verified evaluation")
    receipt = evaluate_artifact_bound_detector(split_manifest=arguments.split_manifest, artifacts=json.loads(arguments.artifacts.read_text(encoding="utf-8")), allowed_root=arguments.allowed_root)
    _write_json_new_atomic(output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
