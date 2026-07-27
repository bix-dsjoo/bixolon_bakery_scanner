"""Deterministic inputs for development-only detector OOF selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from bakery_scanner.contracts import Box
from bakery_scanner.detectors.oof import OofArtifact
from bakery_scanner.detectors.proposal_policy import retain_raw_proposals
from bakery_scanner.evaluation import evaluate_scans


@dataclass(frozen=True, slots=True)
class StagedGroundTruth:
    """COCO ground truth and documented, dataset-derived diagnostic strata."""

    ground_truth: Mapping[int, tuple[Box, ...]]
    scenarios: Mapping[int, frozenset[str]]


@dataclass(frozen=True, slots=True)
class ScoreCalibrationEvidence:
    """Aggregate OOF proposal outcome at one candidate score threshold."""

    threshold: float
    seed_count: int
    misses: int
    false_proposals: int
    merge_errors: int
    sem_exact: float


@dataclass(frozen=True, slots=True)
class VariantScoreCalibration:
    threshold: float
    evidence: ScoreCalibrationEvidence


def load_staged_ground_truth(staged_root: Path) -> StagedGroundTruth:
    """Load every staged image without inventing overlap or obstruction labels.

    ``overlap_proxy`` is a dataset-derived proxy, not a human annotation of
    physical overlap or obstruction.  It is retained only for diagnostics.
    """
    staged_root = Path(staged_root)
    coco = _read_object(staged_root / "annotations.json", "staged annotations")
    images = coco.get("images")
    annotations = coco.get("annotations")
    if not isinstance(images, list) or not isinstance(annotations, list):
        raise ValueError("staged annotations require images and annotations arrays")
    dimensions: dict[int, tuple[int, int]] = {}
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("staged image must be an object")
        image_id, width, height = image.get("id"), image.get("width"), image.get("height")
        if not _positive_int(image_id) or not _positive_int(width) or not _positive_int(height) or image_id in dimensions:
            raise ValueError("staged images must have unique positive ids and sizes")
        dimensions[image_id] = (width, height)

    boxes: dict[int, list[Box]] = {image_id: [] for image_id in dimensions}
    for annotation in annotations:
        if not isinstance(annotation, dict) or annotation.get("category_id") != 1:
            raise ValueError("staged annotations must contain only bread category 1")
        image_id, bbox = annotation.get("image_id"), annotation.get("bbox")
        if image_id not in dimensions or not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("annotation must reference a staged image with xywh bbox")
        box = Box(*bbox)
        width, height = dimensions[image_id]
        if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
            raise ValueError("annotation bbox must stay within its staged image")
        boxes[image_id].append(box)

    manifest = _read_array(staged_root / "staged_manifest.json", "staged manifest")
    scenarios: dict[int, frozenset[str]] = {}
    for entry in manifest:
        if not isinstance(entry, dict):
            raise ValueError("staged manifest entry must be an object")
        image_id, scene, overlap_proxy, box_count = entry.get("image_id"), entry.get("scene"), entry.get("overlap_proxy"), entry.get("box_count")
        if image_id not in dimensions or image_id in scenarios or not isinstance(scene, dict) or not isinstance(overlap_proxy, bool) or not isinstance(box_count, int) or box_count < 0:
            raise ValueError("staged manifest entry is invalid")
        batch = scene.get("capture_batch")
        if not isinstance(batch, str) or not batch:
            raise ValueError("staged manifest capture batch must be non-empty")
        if box_count != len(boxes[image_id]):
            raise ValueError("staged manifest box count must match annotations")
        scenarios[image_id] = frozenset({f"capture_batch:{batch}", f"overlap_proxy:{str(overlap_proxy).lower()}", f"box_count:{_box_count_bin(box_count)}"})
    if set(scenarios) != set(dimensions):
        raise ValueError("staged manifest must cover exactly every staged image")
    return StagedGroundTruth(
        ground_truth={image_id: tuple(sorted(boxes[image_id])) for image_id in sorted(boxes)},
        scenarios={image_id: scenarios[image_id] for image_id in sorted(scenarios)},
    )


def calibrate_variant_score_thresholds(
    artifact: OofArtifact,
    *,
    ground_truth: Mapping[int, tuple[Box, ...]],
    scenarios: Mapping[int, frozenset[str]],
) -> Mapping[str, VariantScoreCalibration]:
    """Keep recall first: choose each variant's highest zero-miss OOF score.

    When no observed score can attain zero misses, retain the zero-score
    fallback and preserve its misses in the evidence instead of concealing the
    failure with an arbitrary threshold.
    """
    names = tuple(sorted({experiment.name for experiment in artifact.experiments_by_run.values()}))
    if not names:
        raise ValueError("OOF artifact must contain detector experiments")
    calibrated: dict[str, VariantScoreCalibration] = {}
    for name in names:
        # The raw cap belongs to an individual detector invocation.  Pooling
        # different seeds first would allow one seed's high-score rows to evict
        # another seed's retained evidence before threshold candidates exist.
        raw = tuple(
            proposal
            for run_id, experiment in artifact.experiments_by_run.items()
            if experiment.name == name
            for proposal in retain_raw_proposals(
                row.proposal for row in artifact.predictions if row.run_id == run_id
            )
        )
        candidates = tuple(sorted({0.0, *(proposal.score for proposal in raw)}, reverse=True))
        evidence_by_threshold = {
            threshold: _threshold_evidence(artifact, name, threshold, ground_truth, scenarios)
            for threshold in candidates
        }
        zero_miss = next((threshold for threshold in candidates if evidence_by_threshold[threshold].misses == 0), None)
        selected = zero_miss if zero_miss is not None else 0.0
        calibrated[name] = VariantScoreCalibration(selected, evidence_by_threshold[selected])
    return calibrated


def write_development_selection_report(
    *,
    output: Path,
    artifact: OofArtifact,
    ground_truth: Mapping[int, tuple[Box, ...]],
    scenarios: Mapping[int, frozenset[str]],
    calibrations: Mapping[str, VariantScoreCalibration],
    selection: Mapping[str, object],
) -> Path:
    """Write immutable development evidence, never an operational-quality claim."""
    if set(scenarios) != set(ground_truth):
        raise ValueError("scenarios must cover exactly the ground-truth images")
    output = Path(output)
    scenario_counts: dict[str, int] = {}
    for labels in scenarios.values():
        for label in labels:
            scenario_counts[label] = scenario_counts.get(label, 0) + 1
    payload = {
        "artifact": {
            "path": str(artifact.path),
            "prediction_artifact_hashes": dict(sorted(artifact.prediction_artifact_hashes.items())),
            "receipt_hashes": dict(sorted(artifact.run_receipt_hashes.items())),
            "run_ids": sorted(artifact.experiments_by_run),
        },
        "calibrations": {
            name: {
                "evidence": {
                    "false_proposals": value.evidence.false_proposals,
                    "merge_errors": value.evidence.merge_errors,
                    "misses": value.evidence.misses,
                    "seed_count": value.evidence.seed_count,
                    "sem_exact": value.evidence.sem_exact,
                    "threshold": value.evidence.threshold,
                },
                "threshold": value.threshold,
            }
            for name, value in sorted(calibrations.items())
        },
        "data": {
            "ground_truth_boxes": sum(len(boxes) for boxes in ground_truth.values()),
            "images": len(ground_truth),
            "scenario_counts": dict(sorted(scenario_counts.items())),
        },
        "limitations": {
            "independent_acceptance": "No locked independent acceptance set is available for this development OOF selection.",
            "overlap_obstruction": "The dataset has no actual overlap or obstruction labels; overlap_proxy is a derived diagnostic only.",
            "result_scope": "Detector candidates still require the verifier and downstream pipeline before final object decisions.",
        },
        "operational_guarantee": False,
        "scope": "grouped_oof_development_only",
        "selection": selection,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(encoded)
    return output


def _read_object(path: Path, label: str) -> dict[str, object]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_array(path: Path, label: str) -> list[object]:
    value = _read_json(path, label)
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _box_count_bin(value: int) -> str:
    if value <= 2:
        return "0-2"
    if value <= 5:
        return "3-5"
    return "6+"


def _threshold_evidence(
    artifact: OofArtifact,
    name: str,
    threshold: float,
    ground_truth: Mapping[int, tuple[Box, ...]],
    scenarios: Mapping[int, frozenset[str]],
) -> ScoreCalibrationEvidence:
    seeds = tuple(sorted({experiment.seed for experiment in artifact.experiments_by_run.values() if experiment.name == name}))
    if not seeds:
        raise ValueError(f"no OOF experiments for variant {name}")
    reports = []
    for seed in seeds:
        predictions: dict[int, list[Box]] = {}
        raw = retain_raw_proposals(
            row.proposal
            for row in artifact.predictions
            if artifact.experiments_by_run[row.run_id].name == name and artifact.experiments_by_run[row.run_id].seed == seed
        )
        for proposal in raw:
            if proposal.score >= threshold:
                predictions.setdefault(proposal.image_id, []).append(proposal.box)
        reports.append(evaluate_scans(ground_truth, {image_id: tuple(boxes) for image_id, boxes in predictions.items()}, scenarios))
    return ScoreCalibrationEvidence(
        threshold=threshold,
        seed_count=len(seeds),
        misses=sum(report.misses for report in reports),
        false_proposals=sum(report.false_positives + report.duplicates for report in reports),
        merge_errors=sum(report.merge_errors for report in reports),
        sem_exact=sum(report.sem_exact for report in reports) / len(reports),
    )
