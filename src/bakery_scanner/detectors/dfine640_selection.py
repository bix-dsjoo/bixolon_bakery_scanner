"""Leakage-safe cross-fit policy selection for D-FINE-N 640 and its verifier."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from bakery_scanner.contracts import Box
from bakery_scanner.detectors.oof import OofArtifact
from bakery_scanner.detectors.proposal_policy import (
    RAW_PROPOSAL_LIMIT,
    RAW_SCORE_FLOOR,
    retain_raw_proposals,
)
from bakery_scanner.detectors.selection import _write_immutable_json
from bakery_scanner.evaluation import EvaluationReport, evaluate_scans
from bakery_scanner.verifier.model import (
    MODEL_NAME,
    VerifierPrediction,
    validate_completed_verifier_fold,
)


_FOLDS = frozenset(range(5))
_CONFIG_NAMES = frozenset(
    {
        *(f"detector/fold-{fold}.yml" for fold in range(5)),
        *(f"verifier/fold-{fold}.json" for fold in range(5)),
    }
)


@dataclass(frozen=True, slots=True)
class FoldPolicy:
    detector_score_threshold: float
    minimum_exactly_one_probability: float


@dataclass(frozen=True, slots=True)
class VerifierOofArtifact:
    predictions_by_fold: Mapping[int, Sequence[VerifierPrediction]]
    receipt_hashes: Mapping[int, str]
    prediction_artifact_hashes: Mapping[int, str]


@dataclass(frozen=True, slots=True)
class DevelopmentReportProvenance:
    staged_hashes: Mapping[str, str]
    fold_manifest_hashes: Mapping[int, str]
    detector_raw_prediction_hashes: Mapping[int, str]
    config_bytes: Mapping[str, bytes]


def load_complete_verifier_oof_artifact(
    *,
    verifier_root: Path,
    detector_root: Path,
    fold_root: Path,
    staged_root: Path,
    seed: int = 20260724,
) -> VerifierOofArtifact:
    """Load only the complete, revalidated five-fold verifier OOF set."""
    verifier_root = Path(verifier_root)
    detector_root = Path(detector_root)
    fold_root = Path(fold_root)
    staged_root = Path(staged_root)
    annotations = staged_root / "annotations.json"
    required_by_fold: dict[int, tuple[Path, ...]] = {}
    for fold in range(5):
        verifier_run = (
            verifier_root / f"{MODEL_NAME}-seed{seed}-fold{fold}"
        )
        detector_run = (
            detector_root / f"dfine_n_640-seed{seed}-fold{fold}"
        )
        required_by_fold[fold] = (
            verifier_run / "receipt.json",
            verifier_run / "verifier_predictions.json",
            verifier_run / "verifier.pt",
            verifier_run / "verifier_config.json",
            detector_run / "validation_predictions.json",
            fold_root / f"fold-{fold}" / "manifest.json",
            annotations,
        )
    if any(
        not path.is_file()
        for paths in required_by_fold.values()
        for path in paths
    ):
        raise ValueError(
            "all five completed immutable detector/verifier OOF artifacts are required"
        )

    predictions: dict[int, tuple[VerifierPrediction, ...]] = {}
    receipts: dict[int, str] = {}
    artifacts: dict[int, str] = {}
    for fold in range(5):
        verifier_run = (
            verifier_root / f"{MODEL_NAME}-seed{seed}-fold{fold}"
        )
        detector_predictions = (
            detector_root
            / f"dfine_n_640-seed{seed}-fold{fold}"
            / "validation_predictions.json"
        )
        manifest = fold_root / f"fold-{fold}" / "manifest.json"
        validate_completed_verifier_fold(
            run_root=verifier_run,
            fold_manifest=manifest,
            annotations=annotations,
            detector_predictions=detector_predictions,
        )
        receipt_path = verifier_run / "receipt.json"
        prediction_path = verifier_run / "verifier_predictions.json"
        values = _read_json_array(prediction_path, "verifier predictions")
        predictions[fold] = tuple(
            VerifierPrediction(
                image_id=value["image_id"],
                crop_xywh=Box(*value["bbox"]),
                probabilities=tuple(value["probabilities"]),
            )
            for value in values
        )
        receipts[fold] = _sha256_file(receipt_path)
        artifacts[fold] = _sha256_file(prediction_path)
    return VerifierOofArtifact(predictions, receipts, artifacts)


@dataclass(frozen=True, slots=True)
class _Candidate:
    fold: int
    image_id: int
    box: Box
    detector_score: float
    exactly_one_probability: float
    exactly_one: bool
    unresolved: bool


def cross_fit_policies(
    *,
    detector_oof: OofArtifact,
    verifier_predictions: Mapping[int, Sequence[VerifierPrediction]],
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
) -> Mapping[int, FoldPolicy]:
    """Select each target fold's policy using only the other four folds.

    Ground truth is explicit because detector/verifier predictions are evidence,
    not labels.  Candidate retention is always delegated to the shared raw
    proposal policy before detector or verifier thresholds are considered.
    """
    candidates = _validated_candidates(
        detector_oof=detector_oof,
        verifier_predictions=verifier_predictions,
        folds=folds,
        ground_truth=ground_truth,
    )
    policies: dict[int, FoldPolicy] = {}
    for target_fold in range(5):
        calibration = tuple(row for row in candidates if row.fold != target_fold)
        detector_thresholds = tuple(
            sorted({0.0, *(row.detector_score for row in calibration)}, reverse=True)
        )
        verifier_thresholds = tuple(
            sorted(
                {0.0, *(row.exactly_one_probability for row in calibration)},
                reverse=True,
            )
        )
        calibration_ids = frozenset(
            image_id for image_id, fold in folds.items() if fold != target_fold
        )
        calibration_ground_truth = {
            image_id: tuple(ground_truth[image_id])
            for image_id in sorted(calibration_ids)
        }
        scenarios = {
            image_id: frozenset() for image_id in sorted(calibration_ids)
        }
        ranked: list[tuple[tuple[object, ...], FoldPolicy]] = []
        for detector_threshold in detector_thresholds:
            for verifier_threshold in verifier_thresholds:
                predictions = _accepted_boxes(
                    calibration, detector_threshold, verifier_threshold
                )
                report = evaluate_scans(
                    calibration_ground_truth, predictions, scenarios
                )
                unresolved = sum(
                    row.unresolved
                    and row.detector_score >= detector_threshold
                    for row in calibration
                )
                policy = FoldPolicy(detector_threshold, verifier_threshold)
                rank = (
                    report.misses + unresolved,
                    report.merge_errors,
                    report.false_positives,
                    report.duplicates,
                    -report.sem_exact,
                    -detector_threshold,
                    -verifier_threshold,
                )
                ranked.append((rank, policy))
        policies[target_fold] = min(ranked, key=lambda item: item[0])[1]
    return policies


def write_cross_fit_development_report(
    *,
    output: Path,
    detector_oof: OofArtifact,
    verifier_oof: VerifierOofArtifact,
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
    scenarios: Mapping[int, frozenset[str]],
    policies: Mapping[int, FoldPolicy],
    provenance: DevelopmentReportProvenance,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> Path:
    """Write complete immutable OOF evidence without an operational claim."""
    candidates = _validated_candidates(
        detector_oof=detector_oof,
        verifier_predictions=verifier_oof.predictions_by_fold,
        folds=folds,
        ground_truth=ground_truth,
    )
    if set(policies) != _FOLDS:
        raise ValueError("policies must contain exactly folds 0 through 4")
    if set(scenarios) != set(ground_truth):
        raise ValueError("scenario strata must cover exactly every staged image")
    image_count = len(ground_truth)
    box_count = sum(len(boxes) for boxes in ground_truth.values())
    if image_count != expected_staged_images or box_count != expected_staged_boxes:
        raise ValueError(
            "staged count does not match the immutable development-report contract"
        )
    _require_fold_mapping(
        verifier_oof.receipt_hashes, "verifier receipt hashes"
    )
    _require_fold_mapping(
        verifier_oof.prediction_artifact_hashes,
        "verifier prediction artifact hashes",
    )
    _require_fold_mapping(
        provenance.fold_manifest_hashes, "fold manifest hashes"
    )
    _require_fold_mapping(
        provenance.detector_raw_prediction_hashes,
        "raw detector prediction hashes",
    )
    if set(provenance.staged_hashes) != {
        "annotations.json",
        "staged_manifest.json",
    } or any(
        not _is_sha256(value) for value in provenance.staged_hashes.values()
    ):
        raise ValueError(
            "staged annotations and manifest SHA-256 hashes are required"
        )
    if set(provenance.config_bytes) != _CONFIG_NAMES or any(
        not isinstance(value, bytes) for value in provenance.config_bytes.values()
    ):
        raise ValueError(
            "exact configuration bytes are required for all five detector and verifier folds"
        )

    predictions = _accepted_cross_fit_boxes(candidates, policies)
    overall = evaluate_scans(
        {image_id: tuple(boxes) for image_id, boxes in ground_truth.items()},
        predictions,
        scenarios,
    )
    fold_metrics = {}
    for fold in range(5):
        image_ids = tuple(
            sorted(image_id for image_id, value in folds.items() if value == fold)
        )
        fold_payload = _evaluation_payload(
            evaluate_scans(
                {
                    image_id: tuple(ground_truth[image_id])
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
        fold_payload["unresolved_candidates"] = _unresolved_count(
            candidates, policies, fold=fold
        )
        fold_metrics[str(fold)] = fold_payload
    run_to_fold = {
        run_id: experiment.fold
        for run_id, experiment in detector_oof.experiments_by_run.items()
    }
    payload = {
        "artifacts": {
            "detector": {
                "canonical_prediction_hashes": {
                    str(run_to_fold[run_id]): digest
                    for run_id, digest in sorted(
                        detector_oof.prediction_artifact_hashes.items(),
                        key=lambda item: run_to_fold[item[0]],
                    )
                },
                "raw_prediction_hashes": _string_fold_mapping(
                    provenance.detector_raw_prediction_hashes
                ),
                "receipt_hashes": {
                    str(run_to_fold[run_id]): digest
                    for run_id, digest in sorted(
                        detector_oof.run_receipt_hashes.items(),
                        key=lambda item: run_to_fold[item[0]],
                    )
                },
            },
            "verifier": {
                "canonical_prediction_hashes": _string_fold_mapping(
                    verifier_oof.prediction_artifact_hashes
                ),
                "receipt_hashes": _string_fold_mapping(
                    verifier_oof.receipt_hashes
                ),
            },
        },
        "configs": {
            name: {
                "bytes_base64": base64.b64encode(bytes(value)).decode("ascii"),
                "sha256": hashlib.sha256(bytes(value)).hexdigest(),
            }
            for name, value in sorted(provenance.config_bytes.items())
        },
        "data": {
            "fold_manifest_hashes": _string_fold_mapping(
                provenance.fold_manifest_hashes
            ),
            "staged_count": {"boxes": box_count, "images": image_count},
            "staged_hashes": dict(sorted(provenance.staged_hashes.items())),
        },
        "limitations": {
            "independent_acceptance": (
                "No locked independent acceptance set is available; all metrics "
                "are grouped cross-fit development evidence."
            ),
            "observed_scope": (
                "The existing staged data does not establish performance for "
                "empty trays, tray corners, or actual physical obstruction."
            ),
            "unresolved": (
                "PARTIAL and MULTIPLE verifier outcomes remain unresolved and "
                "are not silently counted as bread."
            ),
        },
        "metrics": {
            "folds": fold_metrics,
            "overall": {
                **_evaluation_payload(overall),
                "unresolved_candidates": _unresolved_count(
                    candidates, policies
                ),
            },
        },
        "operational_guarantee": False,
        "policies": {
            str(fold): {
                "detector_score_threshold": policies[fold].detector_score_threshold,
                "minimum_exactly_one_probability": policies[
                    fold
                ].minimum_exactly_one_probability,
            }
            for fold in range(5)
        },
        "proposal_policy": {
            "raw_proposal_limit_per_image": RAW_PROPOSAL_LIMIT,
            "raw_score_floor": RAW_SCORE_FLOOR,
        },
        "scope": "grouped_cross_fit_development_only",
    }
    return _write_immutable_json(output, payload)


def _validated_candidates(
    *,
    detector_oof: OofArtifact,
    verifier_predictions: Mapping[int, Sequence[VerifierPrediction]],
    folds: Mapping[int, int],
    ground_truth: Mapping[int, Sequence[Box]],
) -> tuple[_Candidate, ...]:
    if set(folds.values()) != _FOLDS or set(folds) != set(ground_truth):
        raise ValueError(
            "folds and ground truth must cover the same images across folds 0 through 4"
        )
    experiments = tuple(detector_oof.experiments_by_run.items())
    if (
        len(experiments) != 5
        or {experiment.fold for _, experiment in experiments} != _FOLDS
        or any(
            experiment.name != "dfine_n_640"
            or experiment.backend != "dfine"
            or experiment.input_size != 640
            for _, experiment in experiments
        )
    ):
        raise ValueError("selection requires exactly five D-FINE-N 640 OOF runs")
    run_ids = {run_id for run_id, _ in experiments}
    if (
        set(detector_oof.run_receipt_hashes) != run_ids
        or set(detector_oof.prediction_artifact_hashes) != run_ids
        or any(
            not _is_sha256(value)
            for value in detector_oof.run_receipt_hashes.values()
        )
        or any(
            not _is_sha256(value)
            for value in detector_oof.prediction_artifact_hashes.values()
        )
    ):
        raise ValueError(
            "selection requires all five immutable detector receipt and prediction SHA-256 hashes"
        )
    if set(verifier_predictions) != _FOLDS or any(
        not verifier_predictions[fold] for fold in range(5)
    ):
        raise ValueError(
            "selection requires all five completed verifier OOF prediction artifacts"
        )

    verifier_by_identity: dict[tuple[int, Box], VerifierPrediction] = {}
    for fold in range(5):
        for prediction in verifier_predictions[fold]:
            if not isinstance(prediction, VerifierPrediction):
                raise ValueError(
                    "verifier predictions must contain VerifierPrediction values"
                )
            if folds.get(prediction.image_id) != fold:
                raise ValueError(
                    "verifier prediction must belong to its target fold"
                )
            identity = (prediction.image_id, prediction.crop_xywh)
            if identity in verifier_by_identity:
                raise ValueError("duplicate verifier prediction candidate")
            verifier_by_identity[identity] = prediction

    retained = []
    for run_id, experiment in sorted(experiments):
        rows = tuple(
            row.proposal
            for row in detector_oof.predictions
            if row.run_id == run_id
        )
        for proposal in retain_raw_proposals(rows):
            if folds.get(proposal.image_id) != experiment.fold:
                raise ValueError(
                    "detector prediction must belong to its experiment fold"
                )
            prediction = verifier_by_identity.pop(
                (proposal.image_id, proposal.box), None
            )
            if prediction is None:
                raise ValueError(
                    "verifier predictions must exactly cover retained detector proposals"
                )
            probabilities = prediction.probabilities
            predicted_state = max(
                range(4), key=probabilities.__getitem__
            )
            retained.append(
                _Candidate(
                    fold=experiment.fold,
                    image_id=proposal.image_id,
                    box=proposal.box,
                    detector_score=proposal.score,
                    exactly_one_probability=probabilities[1],
                    exactly_one=predicted_state == 1,
                    unresolved=predicted_state in (2, 3),
                )
            )
    if verifier_by_identity:
        raise ValueError(
            "verifier predictions must exactly cover retained detector proposals"
        )
    return tuple(
        sorted(
            retained,
            key=lambda row: (
                row.fold,
                row.image_id,
                -row.detector_score,
                row.box,
            ),
        )
    )


def _accepted_cross_fit_boxes(
    candidates: Sequence[_Candidate], policies: Mapping[int, FoldPolicy]
) -> Mapping[int, tuple[Box, ...]]:
    boxes: dict[int, list[Box]] = {}
    for row in candidates:
        policy = policies[row.fold]
        if (
            row.exactly_one
            and row.detector_score >= policy.detector_score_threshold
            and row.exactly_one_probability
            >= policy.minimum_exactly_one_probability
        ):
            boxes.setdefault(row.image_id, []).append(row.box)
    return {
        image_id: tuple(sorted(values))
        for image_id, values in sorted(boxes.items())
    }


def _unresolved_count(
    candidates: Sequence[_Candidate],
    policies: Mapping[int, FoldPolicy],
    *,
    fold: int | None = None,
) -> int:
    return sum(
        row.unresolved
        and (fold is None or row.fold == fold)
        and row.detector_score >= policies[row.fold].detector_score_threshold
        for row in candidates
    )


def _evaluation_payload(report: EvaluationReport) -> dict[str, object]:
    thresholds = {"0.50": 0.50, "0.75": 0.75, "0.90": 0.90}
    scenario_names = sorted(
        {
            name
            for threshold in thresholds.values()
            for name in report.by_iou[threshold].scenarios
        }
    )

    def errors(metrics: object) -> dict[str, int]:
        return {
            "duplicates": metrics.duplicates,
            "false_positives": metrics.false_positives,
            "merge_errors": metrics.merge_errors,
            "misses": metrics.misses,
            "split_errors": metrics.split_errors,
        }

    return {
        "errors": {
            label: errors(report.by_iou[threshold])
            for label, threshold in thresholds.items()
        },
        "scenario_strata": {
            name: {
                "errors": {
                    label: errors(report.by_iou[threshold].scenarios[name])
                    for label, threshold in thresholds.items()
                },
                "scan_count": report.by_iou[0.50].scenarios[name].scan_count,
                "semr": {
                    label: report.by_iou[threshold].scenarios[name].sem_exact
                    for label, threshold in thresholds.items()
                },
            }
            for name in scenario_names
        },
        "scan_count": report.scan_count,
        "semr": {
            label: report.by_iou[threshold].sem_exact
            for label, threshold in thresholds.items()
        },
    }


def _require_fold_mapping(values: Mapping[int, str], label: str) -> None:
    if set(values) != _FOLDS or any(
        not _is_sha256(value)
        for value in values.values()
    ):
        raise ValueError(f"{label} must contain one SHA-256 for each fold")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _string_fold_mapping(values: Mapping[int, str]) -> dict[str, str]:
    return {str(fold): values[fold] for fold in range(5)}


def _read_json_array(path: Path, label: str) -> list[dict[str, object]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc
    if not isinstance(value, list) or any(
        not isinstance(row, dict) for row in value
    ):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _accepted_boxes(
    candidates: Sequence[_Candidate],
    detector_threshold: float,
    verifier_threshold: float,
) -> Mapping[int, tuple[Box, ...]]:
    boxes: dict[int, list[Box]] = {}
    for row in candidates:
        if (
            row.exactly_one
            and row.detector_score >= detector_threshold
            and row.exactly_one_probability >= verifier_threshold
        ):
            boxes.setdefault(row.image_id, []).append(row.box)
    return {
        image_id: tuple(sorted(values))
        for image_id, values in sorted(boxes.items())
    }
