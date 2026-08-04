"""Deterministic, fail-closed OOF quality receipts for the 15+5 pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

import yaml
from scipy.stats import beta

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    CounterfactualCase,
    ForegroundEvidence,
    build_counterfactuals,
    evaluate_completeness,
)
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import RetakeReason


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HASH_FIELDS = (
    "split_sha256", "source_evidence_sha256", "detector_sha256",
    "repvit_checkpoint_sha256", "repvit_prototype_sha256", "dinov3_weights_sha256",
    "dinov3_support_sha256", "dinov3_local_bank_sha256", "preprocess_sha256",
    "fold_policy_sha256", "code_sha256",
)
_DINO_BINDING_HASH_FIELDS = (
    "runtime_sha256",
    "dino_global_split_sha256",
    "dino_local_split_sha256",
    "dino_global_source_evidence_sha256",
    "dino_local_source_evidence_sha256",
    "dino_global_runtime_sha256",
    "dino_local_runtime_sha256",
    "dino_local_model_sha256",
    "dino_global_preprocess_sha256",
    "dino_local_preprocess_sha256",
)
_EXPECTED_FOLDS = frozenset(range(5))
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_UTILITY_CONFIG = _REPOSITORY_ROOT / "configs" / "evaluation" / "rtx5080_15plus5_oof_v1.yaml"
_SPLIT_ROOT = _REPOSITORY_ROOT / "data" / "splits" / "rtx5080_15plus5_oof_v1"
_COUNTERFACTUAL_FAULT_CATEGORIES = frozenset({"missing", "split", "merge", "truncation"})


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")
    return float(value)


def _box(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError("box must contain four finite coordinates")
    result = tuple(_finite(item, "box coordinate") for item in value)
    if result[0] < 0 or result[1] < 0 or result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("box must be finite, non-negative, and non-empty")
    return result


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _policy_payload(policy: CompletenessPolicy) -> Mapping[str, object]:
    return {
        "max_uncovered_ratio": policy.max_uncovered_ratio,
        "max_pair_iou": policy.max_pair_iou,
        "border_margin_ratio": policy.border_margin_ratio,
        "min_blur_score": policy.min_blur_score,
        "exposure_range": list(policy.exposure_range),
        "max_reflection_ratio": policy.max_reflection_ratio,
        "max_risk_score": policy.max_risk_score,
    }


def _policy_payload_from_tuple(values: tuple[float, float, float, float, float, float, float, float]) -> Mapping[str, object]:
    return {
        "max_uncovered_ratio": values[0], "max_pair_iou": values[1],
        "border_margin_ratio": values[2], "min_blur_score": values[3],
        "exposure_range": [values[4], values[5]],
        "max_reflection_ratio": values[6], "max_risk_score": values[7],
    }


@dataclass(frozen=True, slots=True)
class GroundTruthObject:
    object_id: str
    sku_id: int
    box_xyxy: tuple[float, float, float, float]
    object_order: int

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("ground-truth object_id must not be empty")
        if type(self.sku_id) is not int or self.sku_id not in range(1, 21):
            raise ValueError("ground-truth SKU must be active")
        object.__setattr__(self, "box_xyxy", _box(self.box_xyxy))
        if type(self.object_order) is not int or self.object_order < 1:
            raise ValueError("object order must be positive")


@dataclass(frozen=True, slots=True)
class PredictionObject:
    object_id: str
    box_xyxy: tuple[float, float, float, float]
    object_order: int
    state: Literal["auto_approved", "unknown"]
    sku_id: int | None
    top3: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("prediction object_id must not be empty")
        object.__setattr__(self, "box_xyxy", _box(self.box_xyxy))
        if type(self.object_order) is not int or self.object_order < 1:
            raise ValueError("object order must be positive")
        if self.state == "auto_approved":
            if type(self.sku_id) is not int or self.sku_id not in range(1, 21) or self.top3:
                raise ValueError("auto-approved prediction contract is invalid")
        elif self.state == "unknown":
            if self.sku_id is not None or len(self.top3) != 3 or len(set(self.top3)) != 3 or any(type(sku) is not int or sku not in range(1, 21) for sku in self.top3):
                raise ValueError("Unknown requires exactly three unique active-catalog Top-3 candidates")
        else:
            raise ValueError("prediction state must be auto_approved or unknown")


@dataclass(frozen=True, slots=True)
class CounterfactualSourceEvidence:
    """Canonical accepted observed source from which Task 3 transforms derive."""

    source_scene_sha256: str
    source_image_sha256: str
    fold_index: int
    frame_size: tuple[int, int]
    proposals: tuple[BreadProposal, ...]
    foreground: ForegroundEvidence
    quality: CaptureQuality
    policy: CompletenessPolicy
    decision_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("source_scene_sha256", "source_image_sha256"):
            if not isinstance(getattr(self, name), str) or not _SHA256.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if type(self.fold_index) is not int or self.fold_index not in _EXPECTED_FOLDS:
            raise ValueError("counterfactual source fold is invalid")
        if (
            not isinstance(self.frame_size, tuple)
            or len(self.frame_size) != 2
            or any(type(value) is not int or value < 1 for value in self.frame_size)
            or not isinstance(self.proposals, tuple)
            or not self.proposals
        ):
            raise ValueError("counterfactual source canonical geometry is invalid")
        decision = evaluate_completeness(
            self.frame_size,
            self.proposals,
            self.foreground,
            self.quality,
            self.policy,
        )
        if not decision.accepted or decision.reasons:
            raise ValueError("counterfactuals require an accepted observed source without capture-quality faults")
        if self.decision_reasons != ():
            raise ValueError("counterfactual source decision reasons do not match canonical observed evidence")

    def canonical_payload(self) -> Mapping[str, object]:
        return {
            "schema_version": 1,
            "source_scene_sha256": self.source_scene_sha256,
            "source_image_sha256": self.source_image_sha256,
            "fold_index": self.fold_index,
            "frame_size": list(self.frame_size),
            "proposals": [
                {
                    "image_id": proposal.image_id,
                    "source_sha256": hashlib.sha256(proposal.source.encode("utf-8")).hexdigest(),
                    "score": proposal.score,
                    "box_xyxy": list(proposal.box.xyxy),
                    "image_width": proposal.image_width,
                    "image_height": proposal.image_height,
                    "class_id": proposal.class_id,
                    "class_name": proposal.class_name,
                }
                for proposal in self.proposals
            ],
            "foreground": {
                "uncovered_ratio": self.foreground.uncovered_ratio,
                "covered_ratio": self.foreground.covered_ratio,
                "problem_regions": [list(item) for item in self.foreground.problem_regions],
                "possible_split_regions": [list(item) for item in self.foreground.possible_split_regions],
                "possible_merge_regions": [list(item) for item in self.foreground.possible_merge_regions],
                "risk_score": self.foreground.risk_score,
            },
            "quality": asdict(self.quality),
            "policy": _policy_payload(self.policy),
            "policy_sha256": _canonical_sha256(_policy_payload(self.policy)),
            "decision_state": "accepted_scan",
            "decision_reasons": [],
        }

    @property
    def sha256(self) -> str:
        payload = self.canonical_payload()
        _reject_private_paths(payload)
        return _canonical_sha256(payload)


def build_counterfactual_source_evidence(
    *,
    source_scene_id: str,
    source_image_sha256: str,
    fold_index: int,
    frame_size: tuple[int, int],
    proposals: tuple[BreadProposal, ...],
    foreground: ForegroundEvidence,
    quality: CaptureQuality,
    policy: CompletenessPolicy,
) -> CounterfactualSourceEvidence:
    if not isinstance(source_scene_id, str) or not source_scene_id:
        raise ValueError("counterfactual source scene identity is required")
    if not isinstance(source_image_sha256, str) or not _SHA256.fullmatch(source_image_sha256):
        raise ValueError("counterfactual source image identity must be a lowercase SHA-256")
    return CounterfactualSourceEvidence(
        source_scene_sha256=hashlib.sha256(source_scene_id.encode("utf-8")).hexdigest(),
        source_image_sha256=source_image_sha256,
        fold_index=fold_index,
        frame_size=frame_size,
        proposals=proposals,
        foreground=foreground,
        quality=quality,
        policy=policy,
        decision_reasons=(),
    )


@dataclass(frozen=True, slots=True)
class CounterfactualEvidence:
    """Canonical Task 3 transformed evidence bound to one source scene."""

    source_scene_sha256: str
    source_image_sha256: str
    source_descriptor_sha256: str
    fold_index: int
    variant_id: str
    fault: Literal["missing", "merge", "split", "truncation"]
    target_indices: tuple[int, ...]
    intended_retake_reasons: tuple[str, ...]
    frame_size: tuple[int, int]
    proposals: tuple[tuple[int, str, float, tuple[float, float, float, float], int, int, int, str], ...]
    foreground: tuple[float, float, tuple[tuple[float, float, float, float], ...], tuple[tuple[float, float, float, float], ...], tuple[tuple[float, float, float, float], ...], float]
    quality: tuple[float, float, float]
    policy: tuple[float, float, float, float, float, float, float, float]
    policy_sha256: str
    decision_state: Literal["accepted_scan", "needs_retake"]
    decision_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("source_scene_sha256", "source_image_sha256", "source_descriptor_sha256", "policy_sha256"):
            if not isinstance(getattr(self, name), str) or not _SHA256.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase SHA-256")
        if type(self.fold_index) is not int or self.fold_index not in _EXPECTED_FOLDS:
            raise ValueError("counterfactual evidence fold is invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.variant_id):
            raise ValueError("counterfactual evidence variant is invalid")
        if self.fault not in _COUNTERFACTUAL_FAULT_CATEGORIES:
            raise ValueError("counterfactual evidence fault is invalid")
        if (
            not isinstance(self.target_indices, tuple)
            or not self.target_indices
            or any(type(index) is not int or index < 0 for index in self.target_indices)
            or tuple(sorted(set(self.target_indices))) != self.target_indices
        ):
            raise ValueError("counterfactual target indices are invalid")
        if not self.intended_retake_reasons or any(reason not in {item.value for item in RetakeReason} for reason in self.intended_retake_reasons):
            raise ValueError("counterfactual intended retake reasons are invalid")
        if (
            not isinstance(self.frame_size, tuple)
            or len(self.frame_size) != 2
            or any(type(value) is not int or value < 1 for value in self.frame_size)
        ):
            raise ValueError("counterfactual canonical frame size is invalid")
        if not isinstance(self.proposals, tuple) or any(
            not isinstance(row, tuple)
            or len(row) != 8
            or not isinstance(row[1], str)
            or not _SHA256.fullmatch(row[1])
            for row in self.proposals
        ):
            raise ValueError("counterfactual proposal evidence is invalid")
        try:
            policy = CompletenessPolicy(
                self.policy[0], self.policy[1], self.policy[2], self.policy[3],
                (self.policy[4], self.policy[5]), self.policy[6], self.policy[7],
            )
            quality = CaptureQuality(*self.quality)
            foreground = ForegroundEvidence(*self.foreground)
            proposals = tuple(
                BreadProposal(
                    row[0], f"source_sha256:{row[1]}", row[2],
                    Box(row[3][0], row[3][1], row[3][2] - row[3][0], row[3][3] - row[3][1]),
                    row[4], row[5], row[6], row[7],
                )
                for row in self.proposals
            )
        except (IndexError, TypeError, ValueError) as exc:
            raise ValueError("counterfactual evidence payload is invalid") from exc
        policy_payload = _policy_payload(policy)
        if _canonical_sha256(policy_payload) != self.policy_sha256:
            raise ValueError("counterfactual completeness policy hash mismatch")
        if any((proposal.image_width, proposal.image_height) != self.frame_size for proposal in proposals):
            raise ValueError("counterfactual proposal frame identity mismatch")
        decision = evaluate_completeness(self.frame_size, proposals, foreground, quality, policy)
        expected_state = "accepted_scan" if decision.accepted else "needs_retake"
        if expected_state != self.decision_state or tuple(reason.value for reason in decision.reasons) != self.decision_reasons:
            raise ValueError("counterfactual completeness result does not match transformed evidence")
        if self.decision_reasons != self.intended_retake_reasons:
            raise ValueError("counterfactual result does not match its intended fault reasons")

    def canonical_payload(self) -> Mapping[str, object]:
        return {
            "schema_version": 1,
            "source_scene_sha256": self.source_scene_sha256,
            "source_image_sha256": self.source_image_sha256,
            "source_descriptor_sha256": self.source_descriptor_sha256,
            "fold_index": self.fold_index,
            "variant_id": self.variant_id,
            "fault": self.fault,
            "target_indices": list(self.target_indices),
            "intended_retake_reasons": list(self.intended_retake_reasons),
            "frame_size": list(self.frame_size),
            "proposals": [
                {
                    "image_id": row[0], "source_sha256": row[1], "score": row[2],
                    "box_xyxy": list(row[3]), "image_width": row[4], "image_height": row[5],
                    "class_id": row[6], "class_name": row[7],
                }
                for row in self.proposals
            ],
            "foreground": {
                "uncovered_ratio": self.foreground[0], "covered_ratio": self.foreground[1],
                "problem_regions": [list(row) for row in self.foreground[2]],
                "possible_split_regions": [list(row) for row in self.foreground[3]],
                "possible_merge_regions": [list(row) for row in self.foreground[4]],
                "risk_score": self.foreground[5],
            },
            "quality": {"blur_score": self.quality[0], "exposure_score": self.quality[1], "reflection_ratio": self.quality[2]},
            "policy": _policy_payload_from_tuple(self.policy),
            "policy_sha256": self.policy_sha256,
            "decision_state": self.decision_state,
            "decision_reasons": list(self.decision_reasons),
        }

    def to_json_bytes(self) -> bytes:
        payload = self.canonical_payload()
        _reject_private_paths(payload)
        return _canonical_json(payload)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_json_bytes()).hexdigest()


def build_counterfactual_evidence(
    *,
    source: CounterfactualSourceEvidence,
    case: CounterfactualCase,
) -> CounterfactualEvidence:
    """Bind an immutable Task 3 case to its source and evaluated decision."""
    if not isinstance(source, CounterfactualSourceEvidence) or not isinstance(case, CounterfactualCase):
        raise ValueError("counterfactual evidence requires a canonical source and Task 3 case")
    expected = {item.variant_id: item for item in build_counterfactuals(source.proposals)}
    if expected.get(case.variant_id) != case:
        raise ValueError("counterfactual case is not the canonical source transform")
    frame_size = case.frame_size
    decision = evaluate_completeness(frame_size, case.proposals, case.foreground, source.quality, source.policy)
    if tuple(reason.value for reason in decision.reasons) != tuple(reason.value for reason in case.intended_retake_reasons):
        raise ValueError("counterfactual transform did not produce its intended retake reasons")
    policy = source.policy
    policy_values = (
        policy.max_uncovered_ratio, policy.max_pair_iou, policy.border_margin_ratio,
        policy.min_blur_score, policy.exposure_range[0], policy.exposure_range[1],
        policy.max_reflection_ratio, policy.max_risk_score,
    )
    proposals = tuple(
        (
            item.image_id, hashlib.sha256(item.source.encode("utf-8")).hexdigest(), item.score,
            item.box.xyxy, item.image_width, item.image_height, item.class_id, item.class_name,
        )
        for item in case.proposals
    )
    foreground = (
        case.foreground.uncovered_ratio, case.foreground.covered_ratio,
        case.foreground.problem_regions, case.foreground.possible_split_regions,
        case.foreground.possible_merge_regions, case.foreground.risk_score,
    )
    return CounterfactualEvidence(
        source_scene_sha256=source.source_scene_sha256,
        source_image_sha256=source.source_image_sha256,
        source_descriptor_sha256=source.sha256,
        fold_index=source.fold_index,
        variant_id=case.variant_id,
        fault=case.fault,
        target_indices=case.target_indices,
        intended_retake_reasons=tuple(reason.value for reason in case.intended_retake_reasons),
        frame_size=frame_size,
        proposals=proposals,
        foreground=foreground,
        quality=(source.quality.blur_score, source.quality.exposure_score, source.quality.reflection_ratio),
        policy=policy_values,
        policy_sha256=_canonical_sha256(_policy_payload(policy)),
        decision_state="accepted_scan" if decision.accepted else "needs_retake",
        decision_reasons=tuple(reason.value for reason in decision.reasons),
    )


@dataclass(frozen=True, slots=True)
class OofEvaluationRow:
    scene_id: str
    fold_index: int
    role: Literal["evaluation"]
    declared_evaluation_scene_ids: tuple[str, ...]
    state: Literal["accepted_scan", "needs_retake", "no_target_detected"]
    difficulty: Literal["E", "M", "H"]
    image_shape: str
    catalog_segment: Literal["base", "incremental"]
    evidence_kind: Literal["observed", "counterfactual"]
    ground_truth: tuple[GroundTruthObject, ...]
    predictions: tuple[PredictionObject, ...]
    seed: int
    split_sha256: str
    source_evidence_sha256: str
    source_image_sha256: str
    detector_sha256: str
    repvit_checkpoint_sha256: str
    repvit_prototype_sha256: str
    dinov3_weights_sha256: str
    dinov3_support_sha256: str
    dinov3_local_bank_sha256: str
    preprocess_sha256: str
    fold_policy_sha256: str
    code_sha256: str
    runtime_sha256: str
    dino_global_fold_index: int
    dino_local_fold_index: int
    dino_global_split_sha256: str
    dino_local_split_sha256: str
    dino_global_source_evidence_sha256: str
    dino_local_source_evidence_sha256: str
    dino_global_runtime_sha256: str
    dino_local_runtime_sha256: str
    dino_local_model_sha256: str
    dino_global_preprocess_sha256: str
    dino_local_preprocess_sha256: str
    final_policy_sha256: str | None = None
    expected_state: Literal["accepted_scan", "needs_retake", "no_target_detected"] | None = None
    evidence_status: Literal["verified"] = "verified"
    source_scene_id: str | None = None
    variant_id: str | None = None
    fault_category: Literal["missing", "split", "merge", "truncation"] | None = None
    counterfactual_evidence: CounterfactualEvidence | None = None
    counterfactual_evidence_sha256: str | None = None
    counterfactual_source_evidence: CounterfactualSourceEvidence | None = None
    actual_retake_reasons: tuple[str, ...] | None = None
    acceptance_config_sha256: str | None = None
    fold_manifest_file_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.evidence_kind not in {"observed", "counterfactual"}:
            raise ValueError("evaluation evidence kind is invalid")
        declared_identity = self.scene_id if self.evidence_kind == "observed" else self.source_scene_id
        if not self.scene_id or declared_identity not in self.declared_evaluation_scene_ids:
            raise ValueError("scene must be declared for evaluation")
        if type(self.fold_index) is not int or self.fold_index not in range(5):
            raise ValueError("evaluation fold is invalid")
        if self.role != "evaluation":
            raise ValueError("OOF row must have evaluation role")
        if self.state not in {"accepted_scan", "needs_retake", "no_target_detected"}:
            raise ValueError("scan state is invalid")
        if self.difficulty not in {"E", "M", "H"} or not self.image_shape:
            raise ValueError("reporting slice identity is invalid")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if len({item.object_id for item in self.ground_truth}) != len(self.ground_truth) or len({item.object_id for item in self.predictions}) != len(self.predictions):
            raise ValueError("duplicate scene/object row")
        for field_name in _HASH_FIELDS:
            if not isinstance(getattr(self, field_name), str) or not _SHA256.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256")
        if not isinstance(self.source_image_sha256, str) or not _SHA256.fullmatch(self.source_image_sha256):
            raise ValueError("source_image_sha256 must be a lowercase SHA-256")
        for field_name in ("acceptance_config_sha256", "fold_manifest_file_sha256"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not _SHA256.fullmatch(value)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256 when present")
        for field_name in _DINO_BINDING_HASH_FIELDS:
            if not isinstance(getattr(self, field_name), str) or not _SHA256.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256")
        if self.dino_global_fold_index != self.fold_index or self.dino_local_fold_index != self.fold_index:
            raise ValueError("DINO evidence identity fold mismatch")
        if (
            self.dino_global_split_sha256 != self.split_sha256
            or self.dino_local_split_sha256 != self.split_sha256
            or self.dino_global_source_evidence_sha256 != self.source_evidence_sha256
            or self.dino_local_source_evidence_sha256 != self.source_evidence_sha256
            or self.dino_global_runtime_sha256 != self.runtime_sha256
            or self.dino_local_runtime_sha256 != self.runtime_sha256
            or self.dino_local_model_sha256 != self.dinov3_weights_sha256
            or self.dino_global_preprocess_sha256 != self.preprocess_sha256
            or self.dino_local_preprocess_sha256 != self.preprocess_sha256
        ):
            raise ValueError("DINO evidence identity mismatch")
        if self.state == "accepted_scan" and not self.ground_truth:
            raise ValueError("accepted_scan requires at least one target; zero targets are no_target_detected")
        if self.state == "no_target_detected" and (self.ground_truth or self.predictions):
            raise ValueError("no_target_detected requires zero targets and predictions")
        if self.state == "needs_retake" and self.predictions:
            raise ValueError("needs_retake must not carry final predictions or objects")
        if self.expected_state is not None and self.expected_state not in {
            "accepted_scan",
            "needs_retake",
            "no_target_detected",
        }:
            raise ValueError("expected scan state is invalid")
        if self.evidence_status != "verified":
            raise ValueError("OOF evidence must have verified input status")
        if self.evidence_kind == "observed":
            if (
                self.source_scene_id != self.scene_id
                or self.variant_id is not None
                or self.fault_category is not None
                or self.counterfactual_evidence is not None
                or self.counterfactual_evidence_sha256 is not None
                or self.actual_retake_reasons is not None
            ):
                raise ValueError("observed evidence must bind its own source scene without a variant")
            source = self.counterfactual_source_evidence
            if source is not None:
                ordered_truth = tuple(sorted(self.ground_truth, key=lambda item: item.object_order))
                if (
                    not isinstance(source, CounterfactualSourceEvidence)
                    or source.source_scene_sha256 != hashlib.sha256(self.scene_id.encode("utf-8")).hexdigest()
                    or source.source_image_sha256 != self.source_image_sha256
                    or source.fold_index != self.fold_index
                    or tuple(proposal.box.xyxy for proposal in source.proposals)
                    != tuple(item.box_xyxy for item in ordered_truth)
                ):
                    raise ValueError("counterfactual source descriptor does not match observed proposal/GT evidence")
        elif self.evidence_kind == "counterfactual":
            if (
                not isinstance(self.source_scene_id, str)
                or not self.source_scene_id
                or not isinstance(self.variant_id, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.variant_id)
                or self.scene_id != f"{self.source_scene_id}::counterfactual::{self.variant_id}"
                or self.fault_category not in _COUNTERFACTUAL_FAULT_CATEGORIES
                or not isinstance(self.counterfactual_evidence, CounterfactualEvidence)
                or self.counterfactual_source_evidence is not None
                or not isinstance(self.actual_retake_reasons, tuple)
            ):
                raise ValueError("counterfactual evidence requires a distinct deterministic variant identity and fault category")
            evidence = self.counterfactual_evidence
            if (
                not isinstance(self.counterfactual_evidence_sha256, str)
                or not _SHA256.fullmatch(self.counterfactual_evidence_sha256)
                or self.counterfactual_evidence_sha256 != evidence.sha256
            ):
                raise ValueError("counterfactual evidence hash does not match its canonical payload")
            if (
                evidence.source_scene_sha256 != hashlib.sha256(self.source_scene_id.encode("utf-8")).hexdigest()
                or evidence.source_image_sha256 != self.source_image_sha256
                or evidence.fold_index != self.fold_index
                or evidence.variant_id != self.variant_id
                or evidence.fault != self.fault_category
            ):
                raise ValueError("counterfactual evidence source/fold/category/result identity mismatch")
            if (
                any(reason not in {item.value for item in RetakeReason} for reason in self.actual_retake_reasons)
                or len(set(self.actual_retake_reasons)) != len(self.actual_retake_reasons)
                or (self.state == "accepted_scan" and self.actual_retake_reasons)
                or (self.state == "needs_retake" and not self.actual_retake_reasons)
            ):
                raise ValueError("counterfactual actual retake result is invalid")
            if self.source_evidence_sha256 != evidence.sha256:
                raise ValueError("counterfactual transformed evidence hash must bind source evidence")
        if self.final_policy_sha256 is not None:
            raise ValueError("final policy/OOF receipt circularity is forbidden")


@dataclass(frozen=True, slots=True)
class OofQuality:
    miss_count: int
    duplicate_count: int
    non_target_detection_count: int
    split_count: int
    merge_count: int
    detected_count_mismatch_count: int
    object_order_mismatch_count: int
    wrong_auto_approval_count: int
    accepted_scan_critical_failure_count: int
    scan_error_upper_95: float
    object_error_upper_95: float
    scan_sample_size: int
    object_sample_size: int


@dataclass(frozen=True, slots=True)
class OofUtility:
    normal_scan_acceptance: Mapping[str, float | None]
    unnecessary_retake: Mapping[str, float | None]
    auto_sku_approval_coverage: Mapping[str, float | None]
    unknown_rate: Mapping[str, float | None]
    unknown_top3_recall: Mapping[str, float | None]
    incremental_auto_sku_approval_coverage: float | None
    counterfactual_completeness_block_rate: Mapping[str, float | None]
    counterfactual_expected_case_count: Mapping[str, int]
    counterfactual_submitted_case_count: Mapping[str, int]
    missing_required_slices: tuple[str, ...]
    has_violation: bool
    passes: bool


@dataclass(frozen=True, slots=True)
class AcceptanceSourceIdentity:
    utility_config_sha256: str
    fold_manifest_file_sha256: Mapping[int, str]
    fold_manifest_payload_sha256: Mapping[int, str]
    fold_evaluation_scene_set_sha256: Mapping[int, str]
    fold_source_sha256: Mapping[int, str]
    seed_by_fold: Mapping[int, int]
    combined_sha256: str

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.utility_config_sha256) or not _SHA256.fullmatch(self.combined_sha256):
            raise ValueError("canonical acceptance source hash is invalid")
        for name in (
            "fold_manifest_file_sha256",
            "fold_manifest_payload_sha256",
            "fold_evaluation_scene_set_sha256",
            "fold_source_sha256",
        ):
            value = getattr(self, name)
            if set(value) != _EXPECTED_FOLDS or any(not isinstance(item, str) or not _SHA256.fullmatch(item) for item in value.values()):
                raise ValueError(f"{name} must bind exactly five canonical hashes")
        if set(self.seed_by_fold) != _EXPECTED_FOLDS or any(type(item) is not int for item in self.seed_by_fold.values()):
            raise ValueError("canonical acceptance seeds must bind exactly five folds")
        if _canonical_sha256(self.canonical_payload(include_combined=False)) != self.combined_sha256:
            raise ValueError("canonical acceptance source combined hash mismatch")

    def canonical_payload(self, *, include_combined: bool = True) -> Mapping[str, object]:
        payload: dict[str, object] = {
            "utility_config_sha256": self.utility_config_sha256,
            "fold_manifest_file_sha256": {str(key): value for key, value in sorted(self.fold_manifest_file_sha256.items())},
            "fold_manifest_payload_sha256": {str(key): value for key, value in sorted(self.fold_manifest_payload_sha256.items())},
            "fold_evaluation_scene_set_sha256": {str(key): value for key, value in sorted(self.fold_evaluation_scene_set_sha256.items())},
            "fold_source_sha256": {str(key): value for key, value in sorted(self.fold_source_sha256.items())},
            "seed_by_fold": {str(key): value for key, value in sorted(self.seed_by_fold.items())},
        }
        if include_combined:
            payload["combined_sha256"] = self.combined_sha256
        return payload


@dataclass(frozen=True, slots=True)
class OofAcceptanceReceipt:
    status: Literal["quality-accepted", "quality-rejected", "utility-rejected", "unverified"]
    quality: OofQuality
    utility: OofUtility
    scene_count: int
    object_count: int
    registered_object_total: int
    unknown_count: int
    top3_rank_hits: Mapping[str, int]
    object_count_slices: Mapping[str, int]
    report_slices: Mapping[str, Mapping[str, int]]
    quality_claims_by_count: Mapping[str, str | None]
    policy_by_fold: Mapping[int, str]
    provenance_by_fold: Mapping[int, Mapping[str, Mapping[str, str]]]
    seed_by_fold: Mapping[int, int]
    acceptance_sources: AcceptanceSourceIdentity
    evaluation_input_sha256: str
    evaluation_row_count: int
    _evaluation_rows: tuple[OofEvaluationRow, ...]
    _evaluation_policy_by_fold: tuple[tuple[int, str], ...]
    unverified_reasons: tuple[str, ...] = ()
    sample_size_limit: str = "Exact one-sided 95% bounds describe only the observed OOF sample; they do not establish a 0.1% production-risk claim."
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.evaluation_input_sha256):
            raise ValueError("evaluation input identity must be a lowercase SHA-256")
        if type(self.evaluation_row_count) is not int or self.evaluation_row_count != len(self._evaluation_rows):
            raise ValueError("evaluation row count does not match authoritative evaluation input")
        if not isinstance(self._evaluation_rows, tuple) or not all(isinstance(row, OofEvaluationRow) for row in self._evaluation_rows):
            raise ValueError("authoritative evaluation rows are invalid")
        if not isinstance(self._evaluation_policy_by_fold, tuple):
            raise ValueError("authoritative evaluation policy identities are invalid")
        if self.evaluation_input_sha256 != _evaluation_input_sha256(
            self._evaluation_rows,
            self._evaluation_policy_by_fold,
        ):
            raise ValueError("evaluation input identity does not match authoritative evaluation bytes")

    def to_json_bytes(self) -> bytes:
        payload = asdict(self)
        payload.pop("_evaluation_rows")
        payload.pop("_evaluation_policy_by_fold")
        payload["policy_by_fold"] = {str(key): value for key, value in sorted(self.policy_by_fold.items())}
        payload["provenance_by_fold"] = {str(key): value for key, value in sorted(self.provenance_by_fold.items())}
        payload["seed_by_fold"] = {str(key): value for key, value in sorted(self.seed_by_fold.items())}
        payload["acceptance_sources"] = self.acceptance_sources.canonical_payload()
        _reject_private_paths(payload)
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True, slots=True)
class FrozenOofReceipt:
    payload: bytes
    sha256: str
    evaluation_input_sha256: str
    _evaluation_rows: tuple[OofEvaluationRow, ...]
    _evaluation_policy_by_fold: tuple[tuple[int, str], ...]

    def __post_init__(self) -> None:
        if hashlib.sha256(self.payload).hexdigest() != self.sha256:
            raise ValueError("frozen OOF receipt hash mismatch")
        if self.evaluation_input_sha256 != _evaluation_input_sha256(
            self._evaluation_rows,
            self._evaluation_policy_by_fold,
        ):
            raise ValueError("frozen OOF receipt evaluation input identity mismatch")


def immutable_fusion_accepts(
    fusion_sku: int,
    dino_local_top1: int,
    repvit_global_top1: int,
    dino_global_top1: int,
    fusion_margin: float,
) -> bool:
    margin = _finite(fusion_margin, "fusion margin")
    return fusion_sku == dino_local_top1 or (
        repvit_global_top1 == fusion_sku
        and dino_global_top1 == fusion_sku
        and margin >= 0.85
    )


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    return intersection / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection)


def _matches(row: OofEvaluationRow) -> tuple[tuple[int, int], ...]:
    candidates = sorted(
        ((-_iou(gt.box_xyxy, pred.box_xyxy), gi, pi)
         for gi, gt in enumerate(row.ground_truth)
         for pi, pred in enumerate(row.predictions)
         if _iou(gt.box_xyxy, pred.box_xyxy) >= 0.50),
    )
    used_gt: set[int] = set()
    used_pred: set[int] = set()
    result = []
    for _, gi, pi in candidates:
        if gi not in used_gt and pi not in used_pred:
            used_gt.add(gi)
            used_pred.add(pi)
            result.append((gi, pi))
    return tuple(sorted(result))


def _upper_bound(errors: int, sample_size: int) -> float:
    if sample_size == 0:
        return 1.0
    if errors == sample_size:
        return 1.0
    return float(beta.ppf(0.95, errors + 1, sample_size - errors))


def _count_slice(count: int) -> str:
    if count <= 2:
        return "count_1_2"
    if count <= 7:
        return "count_3_7"
    return "count_8_plus"


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _safe_identifier(value: str) -> str:
    """Expose reproducible identity without serializing a scene name/path."""
    return "scene_sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pipeline_identity(row: OofEvaluationRow) -> Mapping[str, str | None]:
    """The linked variant may have new source bytes, never a new static pipeline."""
    identity: dict[str, str | None] = {
        field: getattr(row, field)
        for field in (*_HASH_FIELDS, *_DINO_BINDING_HASH_FIELDS)
        if field not in {
            "source_evidence_sha256",
            "dino_global_source_evidence_sha256",
            "dino_local_source_evidence_sha256",
        }
    }
    identity["acceptance_config_sha256"] = row.acceptance_config_sha256
    identity["fold_manifest_file_sha256"] = row.fold_manifest_file_sha256
    return identity


def _evaluation_input_sha256(
    rows: tuple[OofEvaluationRow, ...],
    policy_items: tuple[tuple[int, str], ...],
) -> str:
    """Hash the exact full evaluation input without publishing private row data."""
    if (
        not isinstance(rows, tuple)
        or not all(isinstance(row, OofEvaluationRow) for row in rows)
        or not isinstance(policy_items, tuple)
        or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or type(item[0]) is not int
            or not isinstance(item[1], str)
            for item in policy_items
        )
    ):
        raise ValueError("authoritative evaluation input is invalid")
    payload = {
        "schema_version": 1,
        "rows": [asdict(row) for row in rows],
        "policy_by_fold": {str(fold): digest for fold, digest in policy_items},
    }
    return _canonical_sha256(payload)


@dataclass(frozen=True, slots=True)
class _CanonicalAcceptanceMaterial:
    utility_floors: Mapping[str, Mapping[str, float]]
    manifests: Mapping[int, tuple[tuple[str, ...], str, str, int, str]]
    identity: AcceptanceSourceIdentity


def _load_canonical_acceptance_material() -> _CanonicalAcceptanceMaterial:
    try:
        if _UTILITY_CONFIG.is_symlink() or _UTILITY_CONFIG.resolve().parent != (_REPOSITORY_ROOT / "configs" / "evaluation").resolve():
            raise ValueError("canonical utility configuration path is invalid")
        config_bytes = _UTILITY_CONFIG.read_bytes()
        value = yaml.safe_load(config_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError("OOF utility configuration is unavailable") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("seed") != 20260803
        or value.get("fold_count") != 5
        or value.get("iou_threshold") != 0.50
        or value.get("counterfactual_completeness_block_rate") != 1.0
    ):
        raise ValueError("OOF utility configuration is invalid")
    configured_floors = value.get("utility_floors")
    required = {
        "normal_scan_acceptance",
        "unnecessary_retake",
        "auto_sku_approval_coverage",
        "unknown_rate",
        "unknown_top3_recall",
    }
    if not isinstance(configured_floors, dict) or set(configured_floors) != required:
        raise ValueError("OOF utility floors are invalid")
    floors: dict[str, Mapping[str, float]] = {}
    for name in required:
        row = configured_floors[name]
        if (
            not isinstance(row, dict)
            or set(row) != {"overall", "each"}
            or any(not isinstance(item, (int, float)) or isinstance(item, bool) or not 0.0 <= float(item) <= 1.0 for item in row.values())
        ):
            raise ValueError("OOF utility floor values are invalid")
        floors[name] = {key: float(item) for key, item in row.items()}

    manifests: dict[int, tuple[tuple[str, ...], str, str, int, str]] = {}
    file_hashes: dict[int, str] = {}
    payload_hashes: dict[int, str] = {}
    scene_set_hashes: dict[int, str] = {}
    source_hashes: dict[int, str] = {}
    seeds: dict[int, int] = {}
    try:
        for fold in range(5):
            path = _SPLIT_ROOT / f"fold-{fold}.json"
            if path.is_symlink() or path.resolve().parent != _SPLIT_ROOT.resolve():
                raise ValueError("canonical split manifest path is invalid")
            manifest_bytes = path.read_bytes()
            decoded = json.loads(manifest_bytes.decode("utf-8"))
            if _canonical_json(decoded) != manifest_bytes:
                raise ValueError("canonical split manifest bytes are not canonical")
            if not isinstance(decoded, dict):
                raise ValueError("canonical split manifest payload is invalid")
            embedded_hash = decoded.get("manifest_sha256")
            unhashed = {key: item for key, item in decoded.items() if key != "manifest_sha256"}
            if (
                decoded.get("schema_version") != 1
                or decoded.get("fold_index") != fold
                or decoded.get("seed") != value["seed"]
                or not isinstance(embedded_hash, str)
                or not _SHA256.fullmatch(embedded_hash)
                or _canonical_sha256(unhashed) != embedded_hash
                or not isinstance(decoded.get("source_sha256"), str)
                or not _SHA256.fullmatch(decoded["source_sha256"])
                or not isinstance(decoded.get("scene_ids"), dict)
                or set(decoded["scene_ids"]) != {"train", "calibration", "evaluation"}
            ):
                raise ValueError("canonical split manifest identity is invalid")
            scenes_value = decoded["scene_ids"]["evaluation"]
            if (
                not isinstance(scenes_value, list)
                or not scenes_value
                or any(not isinstance(item, str) or not item for item in scenes_value)
                or scenes_value != sorted(scenes_value)
                or len(scenes_value) != len(set(scenes_value))
            ):
                raise ValueError("canonical evaluation scene identities are invalid")
            scenes = tuple(scenes_value)
            file_hash = hashlib.sha256(manifest_bytes).hexdigest()
            manifests[fold] = (scenes, embedded_hash, decoded["source_sha256"], decoded["seed"], file_hash)
            file_hashes[fold] = file_hash
            payload_hashes[fold] = embedded_hash
            scene_set_hashes[fold] = _canonical_sha256(scenes)
            source_hashes[fold] = decoded["source_sha256"]
            seeds[fold] = decoded["seed"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("canonical split manifests are unavailable or invalid") from exc
    evaluated = tuple(scene for fold in range(5) for scene in manifests[fold][0])
    if len(evaluated) != 299 or len(evaluated) != len(set(evaluated)) or len(set(source_hashes.values())) != 1:
        raise ValueError("canonical split manifests do not form one disjoint source identity")
    identity_without_combined = {
        "utility_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "fold_manifest_file_sha256": {str(key): item for key, item in sorted(file_hashes.items())},
        "fold_manifest_payload_sha256": {str(key): item for key, item in sorted(payload_hashes.items())},
        "fold_evaluation_scene_set_sha256": {str(key): item for key, item in sorted(scene_set_hashes.items())},
        "fold_source_sha256": {str(key): item for key, item in sorted(source_hashes.items())},
        "seed_by_fold": {str(key): item for key, item in sorted(seeds.items())},
    }
    identity = AcceptanceSourceIdentity(
        utility_config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        fold_manifest_file_sha256=file_hashes,
        fold_manifest_payload_sha256=payload_hashes,
        fold_evaluation_scene_set_sha256=scene_set_hashes,
        fold_source_sha256=source_hashes,
        seed_by_fold=seeds,
        combined_sha256=_canonical_sha256(identity_without_combined),
    )
    return _CanonicalAcceptanceMaterial(floors, manifests, identity)


def _manifest_missing_identities(
    rows: tuple[OofEvaluationRow, ...],
    material: _CanonicalAcceptanceMaterial,
) -> tuple[str, ...]:
    """Require the exact checked-in evaluation scene identity, not row claims."""
    missing: list[str] = []
    observed_by_fold = {
        fold: tuple(sorted(row.scene_id for row in rows if row.fold_index == fold and row.evidence_kind == "observed"))
        for fold in range(5)
    }
    for fold, (scene_ids, manifest_sha, source_sha, seed, manifest_file_sha) in material.manifests.items():
        fold_rows = tuple(row for row in rows if row.fold_index == fold and row.evidence_kind == "observed")
        expected_set = set(scene_ids)
        observed_set = set(observed_by_fold[fold])
        missing.extend(f"missing_observed_scene:{fold}:{_safe_identifier(scene_id)}" for scene_id in sorted(expected_set - observed_set))
        missing.extend(f"unexpected_observed_scene:{fold}:{_safe_identifier(scene_id)}" for scene_id in sorted(observed_set - expected_set))
        for row in fold_rows:
            if row.declared_evaluation_scene_ids != tuple(scene_ids):
                missing.append(f"declared_evaluation_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
            if row.split_sha256 != manifest_sha:
                missing.append(f"split_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
            if row.source_evidence_sha256 != source_sha:
                missing.append(f"source_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
            if row.seed != seed:
                missing.append(f"seed_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
            if row.acceptance_config_sha256 != material.identity.utility_config_sha256:
                missing.append(f"acceptance_config_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
            if row.fold_manifest_file_sha256 != manifest_file_sha:
                missing.append(f"manifest_file_identity_mismatch:{fold}:{_safe_identifier(row.scene_id)}")
    return tuple(sorted(set(missing)))


@dataclass(frozen=True, slots=True)
class _CounterfactualContract:
    block_rate: Mapping[str, float | None]
    expected_count: Mapping[str, int]
    submitted_count: Mapping[str, int]
    missing: tuple[str, ...]


def _counterfactual_contract(rows: tuple[OofEvaluationRow, ...]) -> _CounterfactualContract:
    observed = {
        (row.fold_index, row.scene_id): row
        for row in rows
        if row.evidence_kind == "observed"
    }
    expected: dict[tuple[int, str, str], CounterfactualEvidence] = {}
    missing: list[str] = []
    for key, row in sorted(observed.items()):
        source = row.counterfactual_source_evidence
        if source is None:
            missing.append(f"counterfactual_source_unavailable:{key[0]}:{_safe_identifier(key[1])}")
            continue
        for case in build_counterfactuals(source.proposals):
            evidence = build_counterfactual_evidence(source=source, case=case)
            variant_key = (row.fold_index, row.scene_id, case.variant_id)
            if variant_key in expected:
                raise ValueError("canonical counterfactual variant identity is not unique")
            expected[variant_key] = evidence

    submitted: dict[tuple[int, str, str], OofEvaluationRow] = {}
    for row in (item for item in rows if item.evidence_kind == "counterfactual"):
        key = (row.fold_index, row.source_scene_id or "", row.variant_id or "")
        if key in submitted:
            raise ValueError("counterfactual variant must be submitted exactly once")
        source_row = observed.get((row.fold_index, row.source_scene_id or ""))
        if source_row is None or source_row.counterfactual_source_evidence is None:
            raise ValueError("counterfactual source descriptor is unavailable")
        canonical = expected.get(key)
        if canonical is None or canonical.to_json_bytes() != row.counterfactual_evidence.to_json_bytes():
            raise ValueError("counterfactual evidence is not the canonical source transform")
        submitted[key] = row

    unexpected = sorted(set(submitted) - set(expected))
    if unexpected:
        raise ValueError("unexpected counterfactual variant was submitted")
    for fold, source_scene_id, variant_id in sorted(set(expected) - set(submitted)):
        missing.append(
            f"missing_counterfactual_variant:{fold}:{_safe_identifier(source_scene_id)}:{variant_id}"
        )

    expected_count: dict[str, int] = {}
    submitted_count: dict[str, int] = {}
    block_rate: dict[str, float | None] = {}
    for category in sorted(_COUNTERFACTUAL_FAULT_CATEGORIES):
        expected_keys = tuple(key for key, evidence in expected.items() if evidence.fault == category)
        submitted_rows = tuple(submitted[key] for key in expected_keys if key in submitted)
        expected_count[category] = len(expected_keys)
        submitted_count[category] = len(submitted_rows)
        block_rate[category] = _rate(
            sum(
                row.state in {"needs_retake", "no_target_detected"}
                and row.actual_retake_reasons == row.counterfactual_evidence.decision_reasons
                for row in submitted_rows
            ),
            len(expected_keys),
        )
        if not expected_keys:
            missing.append(f"counterfactual:{category}")
    return _CounterfactualContract(
        block_rate=block_rate,
        expected_count=expected_count,
        submitted_count=submitted_count,
        missing=tuple(sorted(set(missing))),
    )


def _utility_metrics(
    rows: tuple[OofEvaluationRow, ...],
    matched_by_scene: Mapping[str, tuple[tuple[int, int], ...]],
    floors: Mapping[str, Mapping[str, float]],
    counterfactual: _CounterfactualContract,
) -> OofUtility:
    slices = ("overall", "E", "M", "H")
    measurements: dict[str, dict[str, float | None]] = {
        name: {} for name in floors
    }
    missing: list[str] = []
    for slice_name in slices:
        subset = tuple(
            row for row in rows
            if row.evidence_kind == "observed" and (slice_name == "overall" or row.difficulty == slice_name)
        )
        expected_normal = tuple(row for row in subset if row.expected_state == "accepted_scan")
        expected_retake = tuple(row for row in subset if row.expected_state in {"needs_retake", "no_target_detected"})
        final_predictions = tuple(pred for row in expected_normal for pred in row.predictions)
        unknown_matches = tuple(
            (row, gi, pi)
            for row in expected_normal
            for gi, pi in matched_by_scene[row.scene_id]
            if row.predictions[pi].state == "unknown"
        )
        normal_acceptance = _rate(sum(row.state == "accepted_scan" for row in expected_normal), len(expected_normal))
        unnecessary_retake = _rate(sum(row.state == "needs_retake" for row in expected_normal), len(expected_normal))
        auto_coverage = _rate(sum(pred.state == "auto_approved" for pred in final_predictions), sum(len(row.ground_truth) for row in expected_normal))
        unknown_rate = _rate(sum(pred.state == "unknown" for pred in final_predictions), len(final_predictions))
        top3_recall = _rate(sum(row.ground_truth[gi].sku_id in row.predictions[pi].top3 for row, gi, pi in unknown_matches), len(unknown_matches))
        values = {
            "normal_scan_acceptance": normal_acceptance,
            "unnecessary_retake": unnecessary_retake,
            "auto_sku_approval_coverage": auto_coverage,
            "unknown_rate": unknown_rate,
            "unknown_top3_recall": top3_recall,
        }
        for name, value in values.items():
            measurements[name][slice_name] = value
            if value is None:
                missing.append(f"{name}:{slice_name}")
        if not expected_retake:
            missing.append(f"retake:{slice_name}")

    incremental = tuple(row for row in rows if row.evidence_kind == "observed" and row.expected_state == "accepted_scan" and row.catalog_segment == "incremental")
    incremental_auto = _rate(
        sum(pred.state == "auto_approved" for row in incremental for pred in row.predictions),
        sum(len(row.ground_truth) for row in incremental),
    )
    if incremental_auto is None:
        missing.append("incremental_auto_sku_approval_coverage")
    counterfactual_block = dict(counterfactual.block_rate)
    missing.extend(counterfactual.missing)

    has_violation = False
    for name, values in measurements.items():
        for slice_name, value in values.items():
            if value is None:
                continue
            floor = floors[name]["overall" if slice_name == "overall" else "each"]
            passed = value >= floor if name in {"normal_scan_acceptance", "auto_sku_approval_coverage", "unknown_top3_recall"} else value <= floor
            has_violation = has_violation or not passed
    if incremental_auto is not None:
        has_violation = has_violation or incremental_auto < 0.50
    for value in counterfactual_block.values():
        if value is not None:
            has_violation = has_violation or value < 1.0
    return OofUtility(
        normal_scan_acceptance=measurements["normal_scan_acceptance"],
        unnecessary_retake=measurements["unnecessary_retake"],
        auto_sku_approval_coverage=measurements["auto_sku_approval_coverage"],
        unknown_rate=measurements["unknown_rate"],
        unknown_top3_recall=measurements["unknown_top3_recall"],
        incremental_auto_sku_approval_coverage=incremental_auto,
        counterfactual_completeness_block_rate=counterfactual_block,
        counterfactual_expected_case_count=counterfactual.expected_count,
        counterfactual_submitted_case_count=counterfactual.submitted_count,
        missing_required_slices=tuple(sorted(set(missing))),
        has_violation=has_violation,
        passes=not missing and not has_violation,
    )


def evaluate_oof(rows: Sequence[OofEvaluationRow], policy_by_fold: Mapping[int, str]) -> OofAcceptanceReceipt:
    checked = tuple(rows)
    if not checked:
        raise ValueError("OOF evaluation rows must not be empty")
    acceptance_material = _load_canonical_acceptance_material()
    if len({row.scene_id for row in checked}) != len(checked):
        raise ValueError("duplicate evaluation scene/object rows")
    observed_sources = {
        (row.fold_index, row.scene_id)
        for row in checked
        if row.evidence_kind == "observed"
    }
    if any(
        row.evidence_kind == "counterfactual"
        and (row.fold_index, row.source_scene_id) not in observed_sources
        for row in checked
    ):
        raise ValueError("counterfactual source must reference an observed evaluation scene in the same fold")
    observed_pipeline = {
        (row.fold_index, row.scene_id): _pipeline_identity(row)
        for row in checked
        if row.evidence_kind == "observed"
    }
    if any(
        row.evidence_kind == "counterfactual"
        and observed_pipeline[(row.fold_index, row.source_scene_id)] != _pipeline_identity(row)
        for row in checked
    ):
        raise ValueError("linked counterfactual pipeline provenance does not match observed evidence")
    observed_rows = {
        (row.fold_index, row.scene_id): row
        for row in checked
        if row.evidence_kind == "observed"
    }
    counterfactual_rows = tuple(row for row in checked if row.evidence_kind == "counterfactual")
    if any(
        row.source_image_sha256 != observed_rows[(row.fold_index, row.source_scene_id)].source_image_sha256
        for row in counterfactual_rows
    ):
        raise ValueError("linked counterfactual source image identity does not match observed evidence")
    if any(
        observed_rows[(row.fold_index, row.source_scene_id)].counterfactual_source_evidence is None
        or row.counterfactual_evidence.source_descriptor_sha256
        != observed_rows[(row.fold_index, row.source_scene_id)].counterfactual_source_evidence.sha256
        for row in counterfactual_rows
    ):
        raise ValueError("linked counterfactual source descriptor does not match observed proposal/GT evidence")
    if any(
        row.source_evidence_sha256 == observed_rows[(row.fold_index, row.source_scene_id)].source_evidence_sha256
        for row in counterfactual_rows
    ):
        raise ValueError("counterfactual transformed evidence must not reuse observed evidence")
    counterfactual_hashes = tuple(row.counterfactual_evidence_sha256 for row in counterfactual_rows)
    if len(counterfactual_hashes) != len(set(counterfactual_hashes)):
        raise ValueError("counterfactual transformed evidence hash cannot be reused")
    for fold, digest in policy_by_fold.items():
        if type(fold) is not int or fold not in range(5) or not _SHA256.fullmatch(digest):
            raise ValueError("fold policy mapping is invalid")
    if any(row.role != "evaluation" for row in checked):
        raise ValueError("OOF evaluation accepts only evaluation role")
    if any(policy_by_fold.get(row.fold_index) != row.fold_policy_sha256 for row in checked):
        raise ValueError("fold policy identity mismatch")
    provenance_by_fold: dict[int, dict[str, dict[str, str]]] = {}
    seed_by_fold: dict[int, int] = {}
    for row in checked:
        identity = {
            field: value
            for field, value in _pipeline_identity(row).items()
            if field != "fold_policy_sha256" and value is not None
        }
        by_kind = provenance_by_fold.setdefault(row.fold_index, {})
        if row.evidence_kind in by_kind and by_kind[row.evidence_kind] != identity:
            raise ValueError("evaluation evidence identity mismatch")
        if row.fold_index in seed_by_fold and seed_by_fold[row.fold_index] != row.seed:
            raise ValueError("evaluation seed mismatch")
        by_kind[row.evidence_kind] = identity
        seed_by_fold[row.fold_index] = row.seed
    for fold, by_kind in provenance_by_fold.items():
        for evidence_kind in tuple(by_kind):
            evidence_rows = tuple(
                row for row in checked
                if row.fold_index == fold and row.evidence_kind == evidence_kind
            )
            source_images = sorted({row.source_image_sha256 for row in evidence_rows})
            by_kind[evidence_kind] = {
                **by_kind[evidence_kind],
                "evidence_row_count": str(len(evidence_rows)),
                "source_image_count": str(len(source_images)),
                "source_image_set_sha256": _canonical_sha256(source_images),
                "source_evidence_set_sha256": _canonical_sha256(sorted({row.source_evidence_sha256 for row in evidence_rows})),
            }
            if evidence_kind == "counterfactual":
                by_kind[evidence_kind] = {
                    **by_kind[evidence_kind],
                    "counterfactual_evidence_count": str(len(evidence_rows)),
                    "counterfactual_evidence_set_sha256": _canonical_sha256(
                        sorted(row.counterfactual_evidence_sha256 for row in evidence_rows)
                    ),
                }

    observed_checked = tuple(row for row in checked if row.evidence_kind == "observed")
    counts = {name: 0 for name in ("miss", "duplicate", "non_target", "split", "merge", "count", "order", "wrong")}
    unknown = registered = critical_scenes = 0
    top3 = {"rank_1": 0, "rank_2": 0, "rank_3": 0, "miss": 0}
    object_slices = {"count_1_2": 0, "count_3_7": 0, "count_8_plus": 0}
    report: dict[str, dict[str, int]] = {name: {} for name in ("difficulty", "sku", "object_count", "image_shape", "catalog_segment", "evidence_kind")}
    matched_by_scene: dict[str, tuple[tuple[int, int], ...]] = {}
    for row in sorted(observed_checked, key=lambda item: (item.fold_index, item.scene_id)):
        matches = _matches(row)
        matched_by_scene[row.scene_id] = matches
        matched_gt, matched_pred = {a for a, _ in matches}, {b for _, b in matches}
        miss = len(row.ground_truth) - len(matched_gt)
        extras = [pi for pi in range(len(row.predictions)) if pi not in matched_pred]
        duplicate = sum(any(_iou(row.ground_truth[gi].box_xyxy, row.predictions[pi].box_xyxy) >= 0.5 for gi in range(len(row.ground_truth))) for pi in extras)
        non_target = len(extras) - duplicate
        relations_gt = [sum(_iou(gt.box_xyxy, pred.box_xyxy) >= 0.5 for pred in row.predictions) for gt in row.ground_truth]
        relations_pred = [sum(_iou(gt.box_xyxy, pred.box_xyxy) >= 0.5 for gt in row.ground_truth) for pred in row.predictions]
        split = sum(value > 1 for value in relations_gt)
        merge = sum(value > 1 for value in relations_pred)
        count_mismatch = int(len(row.ground_truth) != len(row.predictions))
        order_mismatch = sum(row.ground_truth[gi].object_order != row.predictions[pi].object_order for gi, pi in matches)
        wrong = sum(
            row.predictions[pi].state == "auto_approved" and row.predictions[pi].sku_id != row.ground_truth[gi].sku_id
            for gi, pi in matches
        )
        for key, value in (("miss", miss), ("duplicate", duplicate), ("non_target", non_target), ("split", split), ("merge", merge), ("count", count_mismatch), ("order", order_mismatch), ("wrong", wrong)):
            counts[key] += value
        scene_critical = miss + duplicate + non_target + split + merge + count_mismatch + order_mismatch + wrong
        if row.state == "accepted_scan" and scene_critical:
            critical_scenes += 1
        for gi, pi in matches:
            gt, pred = row.ground_truth[gi], row.predictions[pi]
            if pred.state == "unknown":
                try:
                    rank = pred.top3.index(gt.sku_id) + 1
                    top3[f"rank_{rank}"] += 1
                except ValueError:
                    top3["miss"] += 1
        # Outcome aggregation reflects every final prediction, independently of
        # matching; unmatched automatic predictions remain non-target failures.
        unknown += sum(pred.state == "unknown" for pred in row.predictions)
        registered += sum(pred.state == "auto_approved" for pred in row.predictions)
        if row.ground_truth:
            object_slices[_count_slice(len(row.ground_truth))] += 1
        values = {
            "difficulty": row.difficulty,
            "object_count": _count_slice(len(row.ground_truth)),
            "image_shape": row.image_shape,
            "catalog_segment": row.catalog_segment,
            "evidence_kind": row.evidence_kind,
        }
        for category, value in values.items():
            report[category][value] = report[category].get(value, 0) + 1
        for gt in row.ground_truth:
            key = str(gt.sku_id)
            report["sku"][key] = report["sku"].get(key, 0) + 1
    report["evidence_kind"] = {
        kind: sum(row.evidence_kind == kind for row in checked)
        for kind in ("counterfactual", "observed")
        if any(row.evidence_kind == kind for row in checked)
    }

    quality = OofQuality(
        miss_count=counts["miss"], duplicate_count=counts["duplicate"],
        non_target_detection_count=counts["non_target"], split_count=counts["split"],
        merge_count=counts["merge"], detected_count_mismatch_count=counts["count"],
        object_order_mismatch_count=counts["order"], wrong_auto_approval_count=counts["wrong"],
        accepted_scan_critical_failure_count=critical_scenes,
        scan_error_upper_95=_upper_bound(critical_scenes, len(observed_checked)),
        object_error_upper_95=_upper_bound(counts["wrong"], sum(len(row.ground_truth) for row in observed_checked)),
        scan_sample_size=len(observed_checked), object_sample_size=sum(len(row.ground_truth) for row in observed_checked),
    )
    counterfactual_contract = _counterfactual_contract(checked)
    utility = _utility_metrics(
        checked,
        matched_by_scene,
        acceptance_material.utility_floors,
        counterfactual_contract,
    )
    manifest_missing = _manifest_missing_identities(checked, acceptance_material)
    complete_policy_set = set(policy_by_fold) == _EXPECTED_FOLDS
    if critical_scenes or counts["wrong"]:
        status = "quality-rejected"
    elif manifest_missing or not complete_policy_set or utility.missing_required_slices:
        status = "unverified"
    elif utility.has_violation:
        status = "utility-rejected"
    else:
        status = "quality-accepted"
    policy_items = tuple(sorted(policy_by_fold.items()))
    return OofAcceptanceReceipt(
        status=status, quality=quality, utility=utility, scene_count=len(observed_checked),
        object_count=sum(len(row.ground_truth) for row in observed_checked),
        registered_object_total=registered, unknown_count=unknown,
        top3_rank_hits=top3, object_count_slices=object_slices, report_slices=report,
        quality_claims_by_count={"count_1_2": None, "count_3_7": "current_oof_evidence", "count_8_plus": None},
        policy_by_fold=dict(policy_by_fold), provenance_by_fold=provenance_by_fold, seed_by_fold=seed_by_fold,
        acceptance_sources=acceptance_material.identity,
        evaluation_input_sha256=_evaluation_input_sha256(checked, policy_items),
        evaluation_row_count=len(checked),
        _evaluation_rows=checked,
        _evaluation_policy_by_fold=policy_items,
        unverified_reasons=tuple(sorted(
            (*manifest_missing, *utility.missing_required_slices,
             *(f"missing_policy_fold:{fold}" for fold in sorted(_EXPECTED_FOLDS - set(policy_by_fold))),
             *(f"unexpected_policy_fold:{fold}" for fold in sorted(set(policy_by_fold) - _EXPECTED_FOLDS)))
        )),
    )


def freeze_oof_receipt(receipt: OofAcceptanceReceipt) -> FrozenOofReceipt:
    if not isinstance(receipt, OofAcceptanceReceipt):
        raise ValueError("only a validated OOF receipt can be frozen")
    if receipt.acceptance_sources != _load_canonical_acceptance_material().identity:
        raise ValueError("OOF receipt canonical acceptance source identity is stale or forged")
    authoritative = evaluate_oof(
        receipt._evaluation_rows,
        dict(receipt._evaluation_policy_by_fold),
    )
    if authoritative.to_json_bytes() != receipt.to_json_bytes():
        raise ValueError("OOF receipt does not match authoritative evaluation")
    if set(receipt.policy_by_fold) != set(range(5)) or set(receipt.provenance_by_fold) != set(range(5)):
        raise ValueError("OOF receipt must contain exactly five folds before freezing")
    if receipt.status != "quality-accepted" or not receipt.utility.passes:
        raise ValueError("only a quality-accepted utility-passing OOF receipt may be frozen")
    payload = receipt.to_json_bytes()
    _reject_private_paths(json.loads(payload.decode("utf-8")))
    return FrozenOofReceipt(
        payload,
        hashlib.sha256(payload).hexdigest(),
        receipt.evaluation_input_sha256,
        receipt._evaluation_rows,
        receipt._evaluation_policy_by_fold,
    )


def build_final_development_policy(frozen_receipt: FrozenOofReceipt | None, fusion_policy_bytes: bytes) -> bytes:
    if not isinstance(frozen_receipt, FrozenOofReceipt):
        raise ValueError("a frozen OOF receipt hash is required before final policy creation")
    authoritative = evaluate_oof(
        frozen_receipt._evaluation_rows,
        dict(frozen_receipt._evaluation_policy_by_fold),
    )
    if (
        authoritative.to_json_bytes() != frozen_receipt.payload
        or authoritative.evaluation_input_sha256 != frozen_receipt.evaluation_input_sha256
    ):
        raise ValueError("frozen OOF receipt does not match authoritative evaluation")
    try:
        frozen_payload = json.loads(frozen_receipt.payload.decode("utf-8"))
        base = json.loads(fusion_policy_bytes)
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("fusion policy must be valid JSON") from exc
    canonical_acceptance_sources = _load_canonical_acceptance_material().identity.canonical_payload()
    if (
        not isinstance(frozen_payload, dict)
        or frozen_payload.get("schema_version") != 1
        or set(frozen_payload.get("policy_by_fold", {})) != {str(index) for index in range(5)}
        or set(frozen_payload.get("provenance_by_fold", {})) != {str(index) for index in range(5)}
        or frozen_payload.get("status") != "quality-accepted"
        or not isinstance(frozen_payload.get("utility"), dict)
        or frozen_payload.get("utility", {}).get("passes") is not True
        or frozen_payload.get("utility", {}).get("missing_required_slices") != []
        or frozen_payload.get("acceptance_sources") != canonical_acceptance_sources
        or json.dumps(frozen_payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode() != frozen_receipt.payload
    ):
        raise ValueError("frozen OOF receipt must be a canonical five-fold receipt")
    if (
        not isinstance(base, dict)
        or "frozen_oof_receipt_sha256" in base
        or base.get("schema_version") != 3
        or base.get("decision_rule") != "fusion_local_or_global_consensus_margin_v1"
        or base.get("consensus_margin_floor") != 0.85
    ):
        raise ValueError("fusion policy payload is invalid or circular")
    payload = {
        "schema_version": 1,
        "artifact_type": "rtx5080_15plus5_final_development_policy",
        "frozen_oof_receipt_sha256": frozen_receipt.sha256,
        "fusion_policy": base,
    }
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    _reject_private_paths(payload)
    return encoded


def _reject_private_paths(value: object) -> None:
    if isinstance(value, str):
        if value.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
            raise ValueError("receipt/policy must not contain private absolute paths")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _reject_private_paths(key)
            _reject_private_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_paths(item)
