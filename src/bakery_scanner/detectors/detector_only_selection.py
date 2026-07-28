"""Leakage-safe cross-fit selection for detector-only D-FINE postprocessing."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Literal

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detectors.oof import OofArtifact, OofPrediction
from bakery_scanner.detectors.proposal_policy import (
    RAW_PROPOSAL_LIMIT,
    RAW_SCORE_FLOOR,
    canonical_proposal_order,
    retain_raw_proposals,
)
from bakery_scanner.detectors.selection import _write_immutable_json
from bakery_scanner.detectors.soft_nms import SoftNmsPolicy, final_boxes, soft_nms
from bakery_scanner.evaluation import EvaluationReport, evaluate_scans


_FOLDS = frozenset(range(5))
_RAW_SOURCES = ("native", "recall_top30")
_GRID_LIMIT = 9
_OVERLAP_SAMPLE_LIMIT = 30
_ERROR_FIELDS = (
    "misses",
    "false_positives",
    "duplicates",
    "split_errors",
    "merge_errors",
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class DetectorOnlyPolicy:
    raw_source: Literal["native", "recall_top30"]
    score_threshold: float
    overlap_threshold: float
    sigma: float
    calibration_image_ids: frozenset[int]

    def __post_init__(self) -> None:
        if self.raw_source not in _RAW_SOURCES:
            raise ValueError("raw_source must be native or recall_top30")
        values = (self.score_threshold, self.overlap_threshold, self.sigma)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError("detector-only policy values must be finite numbers")
        if not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold must be in [0, 1]")
        if not 0 <= self.overlap_threshold <= 1:
            raise ValueError("overlap_threshold must be in [0, 1]")
        if self.sigma <= 0:
            raise ValueError("sigma must be positive")
        if not isinstance(self.calibration_image_ids, frozenset) or any(
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            for image_id in self.calibration_image_ids
        ):
            raise ValueError(
                "calibration_image_ids must be a frozenset of positive image ids"
            )


def cross_fit_detector_only_policies(
    detector_oof: OofArtifact,
    *,
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
) -> Mapping[int, DetectorOnlyPolicy]:
    """Select each target fold's policy using only the other four folds."""
    candidates = _validated_candidates(
        detector_oof=detector_oof,
        folds=folds,
        ground_truth=ground_truth,
    )
    policies: dict[int, DetectorOnlyPolicy] = {}
    for target_fold in range(5):
        calibration_image_ids = frozenset(
            image_id for image_id, fold in folds.items() if fold != target_fold
        )
        calibration_ground_truth = {
            image_id: tuple(ground_truth[image_id])
            for image_id in sorted(calibration_image_ids)
        }
        calibration_scenarios = {
            image_id: frozenset() for image_id in sorted(calibration_image_ids)
        }
        ranked: list[tuple[tuple[object, ...], DetectorOnlyPolicy]] = []
        for raw_source in _RAW_SOURCES:
            proposals = tuple(
                proposal
                for fold, values in candidates[raw_source].items()
                if fold != target_fold
                for proposal in values
            )
            score_thresholds, overlap_thresholds, sigmas = _policy_grid(proposals)
            for overlap_threshold in overlap_thresholds:
                for sigma in sigmas:
                    decayed = soft_nms(
                        proposals,
                        SoftNmsPolicy(0.0, overlap_threshold, sigma),
                    )
                    for score_threshold in score_thresholds:
                        soft_nms_policy = SoftNmsPolicy(
                            score_threshold,
                            overlap_threshold,
                            sigma,
                        )
                        report = evaluate_scans(
                            calibration_ground_truth,
                            _boxes_at_threshold(
                                decayed,
                                soft_nms_policy.score_threshold,
                            ),
                            calibration_scenarios,
                        )
                        policy = DetectorOnlyPolicy(
                            raw_source=raw_source,
                            score_threshold=score_threshold,
                            overlap_threshold=overlap_threshold,
                            sigma=sigma,
                            calibration_image_ids=calibration_image_ids,
                        )
                        rank = (
                            _total_errors(report, 0.75),
                            _total_errors(report, 0.50),
                            raw_source,
                            -score_threshold,
                            overlap_threshold,
                            sigma,
                        )
                        ranked.append((rank, policy))
        policies[target_fold] = min(ranked, key=lambda item: item[0])[1]
    return policies


def assert_locked_zero_error(report: EvaluationReport) -> None:
    """Reject any locked-gate error at IoU 0.50 or 0.75."""
    if not isinstance(report, EvaluationReport):
        raise ValueError("report must be an EvaluationReport")
    for threshold in (0.50, 0.75):
        metrics = report.by_iou.get(threshold)
        if metrics is None:
            raise ValueError(f"locked evaluation is missing IoU {threshold:.2f}")
        errors = {
            field: getattr(metrics, field)
            for field in _ERROR_FIELDS
            if getattr(metrics, field) != 0
        }
        if errors:
            detail = ", ".join(
                f"{field}={value}" for field, value in errors.items()
            )
            raise ValueError(f"locked zero-error gate failed at IoU {threshold:.2f}: {detail}")


def write_detector_only_report(
    *,
    output: Path,
    detector_oof: OofArtifact,
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
    scenarios: Mapping[int, frozenset[str]],
    policies: Mapping[int, DetectorOnlyPolicy],
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> Path:
    """Write immutable detector-only development evidence without an operational claim."""
    candidates = _validated_candidates(
        detector_oof=detector_oof,
        folds=folds,
        ground_truth=ground_truth,
    )
    if set(scenarios) != set(ground_truth):
        raise ValueError("scenarios must cover exactly every staged image")
    _validate_policies(policies, folds)
    image_count = len(ground_truth)
    box_count = sum(len(boxes) for boxes in ground_truth.values())
    if image_count != expected_staged_images or box_count != expected_staged_boxes:
        raise ValueError(
            "staged count does not match the immutable detector-only report contract"
        )

    predictions = _held_out_predictions(candidates, policies)
    normalized_ground_truth = {
        image_id: tuple(boxes) for image_id, boxes in ground_truth.items()
    }
    overall = evaluate_scans(normalized_ground_truth, predictions, scenarios)
    try:
        assert_locked_zero_error(overall)
    except ValueError:
        locked_zero_error_passed = False
    else:
        locked_zero_error_passed = True

    fold_metrics: dict[str, object] = {}
    for fold in range(5):
        image_ids = tuple(
            sorted(image_id for image_id, value in folds.items() if value == fold)
        )
        fold_metrics[str(fold)] = _evaluation_payload(
            evaluate_scans(
                {
                    image_id: normalized_ground_truth[image_id]
                    for image_id in image_ids
                },
                {
                    image_id: predictions[image_id]
                    for image_id in image_ids
                    if image_id in predictions
                },
                {image_id: scenarios[image_id] for image_id in image_ids},
            )
        )

    run_by_fold = {
        experiment.fold: run_id
        for run_id, experiment in detector_oof.experiments_by_run.items()
    }
    payload = {
        "artifacts": {
            "path": str(detector_oof.path),
            "runs": {
                str(fold): {
                    "candidate_counts": {
                        raw_source: len(candidates[raw_source][fold])
                        for raw_source in _RAW_SOURCES
                    },
                    "canonical_prediction_sha256": (
                        detector_oof.prediction_artifact_hashes[run_by_fold[fold]]
                    ),
                    "receipt_sha256": (
                        detector_oof.run_receipt_hashes[run_by_fold[fold]]
                    ),
                    "run_id": run_by_fold[fold],
                }
                for fold in range(5)
            },
        },
        "data": {
            "count_gate": {
                "actual_boxes": box_count,
                "actual_images": image_count,
                "expected_boxes": expected_staged_boxes,
                "expected_images": expected_staged_images,
                "passed": True,
            }
        },
        "images": {
            str(image_id): {
                "errors": _evaluation_payload(
                    evaluate_scans(
                        {image_id: normalized_ground_truth[image_id]},
                        (
                            {image_id: predictions[image_id]}
                            if image_id in predictions
                            else {}
                        ),
                        {image_id: scenarios[image_id]},
                    )
                )["errors"],
                "fold": folds[image_id],
                "ground_truth_boxes": [
                    _box_payload(box)
                    for box in normalized_ground_truth[image_id]
                ],
                "prediction_boxes": [
                    _box_payload(box)
                    for box in predictions.get(image_id, ())
                ],
                "scenarios": sorted(scenarios[image_id]),
            }
            for image_id in sorted(ground_truth)
        },
        "limitations": {
            "acceptance": (
                "No locked independent acceptance data is available; this report "
                "contains grouped cross-fit development evidence only."
            ),
            "unobserved_conditions": (
                "The current data has no real empty-tray, overlap, or obstruction "
                "images, so this report makes no claim for those conditions."
            ),
        },
        "locked_zero_error_passed": locked_zero_error_passed,
        "metrics": {
            "folds": fold_metrics,
            "overall": _evaluation_payload(overall),
        },
        "operational_guarantee": False,
        "policies": {
            str(fold): {
                "calibration_image_ids": sorted(
                    policies[fold].calibration_image_ids
                ),
                "overlap_threshold": policies[fold].overlap_threshold,
                "raw_source": policies[fold].raw_source,
                "score_threshold": policies[fold].score_threshold,
                "sigma": policies[fold].sigma,
            }
            for fold in range(5)
        },
        "proposal_policy": {
            "raw_proposal_limit_per_image_source": RAW_PROPOSAL_LIMIT,
            "raw_score_floor": RAW_SCORE_FLOOR,
        },
        "scope": "detector_only_grouped_cross_fit_development_only",
    }
    return _write_immutable_json(output, payload)


def _validated_candidates(
    *,
    detector_oof: OofArtifact,
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
) -> Mapping[str, Mapping[int, tuple[BreadProposal, ...]]]:
    if not isinstance(detector_oof, OofArtifact):
        raise ValueError("detector_oof must be an OofArtifact")
    if (
        set(folds) != set(ground_truth)
        or set(folds.values()) != _FOLDS
        or any(
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or isinstance(fold, bool)
            or not isinstance(fold, int)
            for image_id, fold in folds.items()
        )
    ):
        raise ValueError(
            "folds and ground truth must cover the same images across folds 0 through 4"
        )
    if any(
        not isinstance(box, Box)
        for boxes in ground_truth.values()
        for box in boxes
    ):
        raise ValueError("ground truth must contain Box values")

    experiments = tuple(detector_oof.experiments_by_run.items())
    if (
        len(experiments) != 5
        or {experiment.fold for _, experiment in experiments} != _FOLDS
        or any(
            experiment.name != "dfine_n_640"
            or experiment.backend != "dfine"
            or experiment.input_size != 640
            or experiment.seed != 20260724
            for _, experiment in experiments
        )
    ):
        raise ValueError(
            "selection requires exactly D-FINE-N 640 seed 20260724 folds 0 through 4"
        )
    run_ids = {run_id for run_id, _ in experiments}
    if (
        set(detector_oof.run_receipt_hashes) != run_ids
        or set(detector_oof.prediction_artifact_hashes) != run_ids
        or any(
            not isinstance(value, str) or _SHA256.fullmatch(value) is None
            for value in (
                *detector_oof.run_receipt_hashes.values(),
                *detector_oof.prediction_artifact_hashes.values(),
            )
        )
    ):
        raise ValueError(
            "selection requires all five receipt and canonical prediction SHA-256 hashes"
        )

    experiment_by_run = dict(experiments)
    native: dict[int, list[BreadProposal]] = {fold: [] for fold in range(5)}
    for row in detector_oof.predictions:
        if not isinstance(row, OofPrediction) or row.run_id not in experiment_by_run:
            raise ValueError("OOF predictions must belong to one expected detector run")
        experiment = experiment_by_run[row.run_id]
        proposal = row.proposal
        if (
            not isinstance(proposal, BreadProposal)
            or proposal.source != experiment.name
            or folds.get(proposal.image_id) != experiment.fold
        ):
            raise ValueError(
                "detector predictions must belong to their receipt-validated held-out fold"
            )
        native[experiment.fold].append(proposal)

    native_by_fold = {
        fold: tuple(native[fold])
        for fold in range(5)
    }
    recall_by_fold = {
        fold: retain_raw_proposals(native_by_fold[fold])
        for fold in range(5)
    }
    return {
        "native": native_by_fold,
        "recall_top30": recall_by_fold,
    }


def _policy_grid(
    proposals: Sequence[BreadProposal],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    overlaps = _candidate_overlaps(proposals)
    return (
        _bounded_grid(
            (proposal.score for proposal in proposals),
            fixed=(0.0, 1.0),
        ),
        _bounded_grid(overlaps, fixed=(0.0, 1.0)),
        _bounded_grid(
            (overlap for overlap in overlaps if overlap > 0),
            fixed=(1e-6, 1.0),
        ),
    )


def _bounded_grid(
    values: Iterable[float],
    *,
    fixed: tuple[float, ...],
) -> tuple[float, ...]:
    ordered = tuple(sorted({*fixed, *(float(value) for value in values)}))
    if len(ordered) <= _GRID_LIMIT:
        return ordered
    indices = {
        round(index * (len(ordered) - 1) / (_GRID_LIMIT - 1))
        for index in range(_GRID_LIMIT)
    }
    return tuple(ordered[index] for index in sorted(indices))


def _candidate_overlaps(
    proposals: Sequence[BreadProposal],
) -> tuple[float, ...]:
    by_image_source: dict[tuple[int, str], list[BreadProposal]] = {}
    for proposal in proposals:
        by_image_source.setdefault(
            (proposal.image_id, proposal.source), []
        ).append(proposal)
    return tuple(
        _iou(first.box, second.box)
        for key in sorted(by_image_source)
        for first, second in combinations(
            sorted(
                by_image_source[key],
                key=canonical_proposal_order,
            )[:_OVERLAP_SAMPLE_LIMIT],
            2,
        )
    )


def _iou(first: Box, second: Box) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union


def _total_errors(report: EvaluationReport, threshold: float) -> int:
    metrics = report.by_iou[threshold]
    return sum(getattr(metrics, field) for field in _ERROR_FIELDS)


def _boxes_at_threshold(
    proposals: Sequence[BreadProposal],
    score_threshold: float,
) -> dict[int, tuple[Box, ...]]:
    result: dict[int, tuple[Box, ...]] = {}
    for proposal in proposals:
        if proposal.score >= score_threshold:
            result[proposal.image_id] = result.get(proposal.image_id, ()) + (
                proposal.box,
            )
    return result


def _validate_policies(
    policies: Mapping[int, DetectorOnlyPolicy],
    folds: Mapping[int, int],
) -> None:
    if set(policies) != _FOLDS or any(
        not isinstance(policy, DetectorOnlyPolicy)
        for policy in policies.values()
    ):
        raise ValueError("policies must contain DetectorOnlyPolicy values for folds 0 through 4")
    for target_fold, policy in policies.items():
        expected = frozenset(
            image_id for image_id, fold in folds.items() if fold != target_fold
        )
        if policy.calibration_image_ids != expected:
            raise ValueError(
                "policy calibration_image_ids must equal the four non-target folds"
            )


def _held_out_predictions(
    candidates: Mapping[str, Mapping[int, tuple[BreadProposal, ...]]],
    policies: Mapping[int, DetectorOnlyPolicy],
) -> dict[int, tuple[Box, ...]]:
    predictions: dict[int, tuple[Box, ...]] = {}
    for fold in range(5):
        policy = policies[fold]
        selected = final_boxes(
            candidates[policy.raw_source][fold],
            SoftNmsPolicy(
                policy.score_threshold,
                policy.overlap_threshold,
                policy.sigma,
            ),
        )
        for image_id, boxes in selected.items():
            if image_id in predictions:
                raise ValueError("held-out prediction images must belong to one fold")
            predictions[image_id] = boxes
    return predictions


def _evaluation_payload(report: EvaluationReport) -> dict[str, object]:
    return {
        "errors": {
            f"{threshold:.2f}": {
                field: getattr(report.by_iou[threshold], field)
                for field in _ERROR_FIELDS
            }
            for threshold in (0.50, 0.75)
        },
        "scan_count": report.scan_count,
        "semr": {
            f"{threshold:.2f}": report.by_iou[threshold].sem_exact
            for threshold in (0.50, 0.75)
        },
    }


def _box_payload(box: Box) -> list[float]:
    return list(box.xyxy)
