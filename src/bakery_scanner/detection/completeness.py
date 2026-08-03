"""Pure, fail-closed scene-completeness evidence and retake decisions.

This module consumes canonical detector and foreground evidence before any SKU
classification.  It never creates proposals or makes classification decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Literal, Protocol

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import RetakeReason


BoxXYXY = tuple[float, float, float, float]


class InvalidDetectorOutput(ValueError):
    """Raised when detector evidence cannot be trusted as canonical geometry."""


@dataclass(frozen=True, slots=True)
class ForegroundEvidence:
    """Independent tray-foreground evidence; it contains neither SKUs nor boxes."""

    uncovered_ratio: float
    covered_ratio: float
    problem_regions: tuple[BoxXYXY, ...]
    possible_split_regions: tuple[BoxXYXY, ...]
    possible_merge_regions: tuple[BoxXYXY, ...]
    risk_score: float

    def __post_init__(self) -> None:
        _unit_interval(self.uncovered_ratio, "uncovered_ratio")
        _unit_interval(self.covered_ratio, "covered_ratio")
        _unit_interval(self.risk_score, "risk_score")
        _regions(self.problem_regions, "problem_regions")
        _regions(self.possible_split_regions, "possible_split_regions")
        _regions(self.possible_merge_regions, "possible_merge_regions")


@dataclass(frozen=True, slots=True)
class CompletenessPolicy:
    """Immutable, externally calibrated thresholds for the pure gate."""

    max_uncovered_ratio: float
    max_pair_iou: float
    border_margin_ratio: float
    min_blur_score: float
    exposure_range: tuple[float, float]
    max_reflection_ratio: float
    max_risk_score: float

    def __post_init__(self) -> None:
        _unit_interval(self.max_uncovered_ratio, "max_uncovered_ratio")
        _unit_interval(self.max_pair_iou, "max_pair_iou")
        _finite(self.border_margin_ratio, "border_margin_ratio")
        if not 0.0 <= self.border_margin_ratio < 0.5:
            raise ValueError("border_margin_ratio must be within [0, 0.5)")
        _finite(self.min_blur_score, "min_blur_score")
        _finite_tuple(self.exposure_range, 2, "exposure_range")
        if self.exposure_range[0] > self.exposure_range[1]:
            raise ValueError("exposure_range must be ordered")
        _unit_interval(self.max_reflection_ratio, "max_reflection_ratio")
        _unit_interval(self.max_risk_score, "max_risk_score")


@dataclass(frozen=True, slots=True)
class CaptureQuality:
    blur_score: float
    exposure_score: float
    reflection_ratio: float

    def __post_init__(self) -> None:
        _finite(self.blur_score, "blur_score")
        _finite(self.exposure_score, "exposure_score")
        _unit_interval(self.reflection_ratio, "reflection_ratio")


@dataclass(frozen=True, slots=True)
class CompletenessDecision:
    accepted: bool
    reasons: tuple[RetakeReason, ...]
    problem_regions: tuple[BoxXYXY, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ValueError("accepted must be boolean")
        if not isinstance(self.reasons, tuple) or not all(isinstance(reason, RetakeReason) for reason in self.reasons):
            raise ValueError("reasons must be an immutable RetakeReason tuple")
        if tuple(reason for reason in RetakeReason if reason in self.reasons) != self.reasons:
            raise ValueError("reasons must be unique and in fixed RetakeReason order")
        if self.accepted != (not self.reasons):
            raise ValueError("accepted must agree with reasons")
        _regions(self.problem_regions, "problem_regions")
        if _canonical_regions(self.problem_regions) != self.problem_regions:
            raise ValueError("problem_regions must be unique and canonically ordered")


@dataclass(frozen=True, slots=True)
class CounterfactualCase:
    evidence_kind: Literal["counterfactual"]
    fault: Literal["missing", "merge", "split", "truncation"]
    proposals: tuple[BreadProposal, ...]
    foreground: ForegroundEvidence

    def __post_init__(self) -> None:
        if self.evidence_kind != "counterfactual":
            raise ValueError("counterfactual cases must have evidence_kind='counterfactual'")
        if self.fault not in {"missing", "merge", "split", "truncation"}:
            raise ValueError("counterfactual fault is invalid")
        if not isinstance(self.proposals, tuple) or not all(isinstance(item, BreadProposal) for item in self.proposals):
            raise ValueError("counterfactual proposals must be an immutable BreadProposal tuple")
        if not isinstance(self.foreground, ForegroundEvidence):
            raise ValueError("counterfactual foreground must use ForegroundEvidence")


class ForegroundAnalyzer(Protocol):
    """Injected foreground boundary; it may emit evidence but never detector rows."""

    def analyze(
        self,
        canonical_rgb: object,
        tray_roi: BoxXYXY,
        proposals: tuple[BreadProposal, ...],
    ) -> ForegroundEvidence: ...


@dataclass(frozen=True, slots=True)
class ReferenceForegroundAnalyzerConfig:
    """Manifest-bound inputs required before a calibrated Lab analyzer is usable.

    The pixel implementation is intentionally not supplied until the calibrated
    tray assets and component policy are admitted with the runtime artifacts.
    """

    analysis_size: tuple[int, int]
    tray_background_lab: tuple[float, float, float]
    lab_distance_threshold: float
    morphology_kernel_size: int
    minimum_component_area: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.analysis_size, tuple)
            or len(self.analysis_size) != 2
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in self.analysis_size)
        ):
            raise ValueError("analysis_size must be two positive integers")
        _finite_tuple(self.tray_background_lab, 3, "tray_background_lab")
        _finite(self.lab_distance_threshold, "lab_distance_threshold")
        if self.lab_distance_threshold < 0:
            raise ValueError("lab_distance_threshold must be non-negative")
        if not isinstance(self.morphology_kernel_size, int) or isinstance(self.morphology_kernel_size, bool) or self.morphology_kernel_size < 1:
            raise ValueError("morphology_kernel_size must be a positive integer")
        if not isinstance(self.minimum_component_area, int) or isinstance(self.minimum_component_area, bool) or self.minimum_component_area < 1:
            raise ValueError("minimum_component_area must be a positive integer")


def evaluate_completeness(
    frame_size: tuple[int, int],
    proposals: tuple[BreadProposal, ...],
    foreground: ForegroundEvidence,
    quality: CaptureQuality,
    policy: CompletenessPolicy,
) -> CompletenessDecision:
    """Return a deterministic retake decision using only non-SKU evidence."""
    width, height = _canonical_frame_size(frame_size)
    _validate_proposals(proposals, width, height)
    if not isinstance(foreground, ForegroundEvidence):
        raise ValueError("foreground must use ForegroundEvidence")
    if not isinstance(quality, CaptureQuality):
        raise ValueError("quality must use CaptureQuality")
    if not isinstance(policy, CompletenessPolicy):
        raise ValueError("policy must use CompletenessPolicy")
    _validate_regions_in_frame(
        foreground.problem_regions + foreground.possible_split_regions + foreground.possible_merge_regions,
        width,
        height,
    )

    reasons: set[RetakeReason] = set()
    regions: list[BoxXYXY] = []
    if not proposals:
        reasons.add(RetakeReason.NO_TARGET_DETECTED)
    if foreground.uncovered_ratio > policy.max_uncovered_ratio:
        reasons.add(RetakeReason.UNCOVERED_FOREGROUND)
        regions.extend(foreground.problem_regions)
    for left_index, left in enumerate(proposals):
        if _enters_border_margin(left.box, width, height, policy.border_margin_ratio):
            reasons.add(RetakeReason.TRUNCATED_OBJECT)
            regions.append(left.box.xyxy)
        for right in proposals[left_index + 1:]:
            if _box_iou(left.box, right.box) > policy.max_pair_iou:
                reasons.add(RetakeReason.OVERLAP_OR_OCCLUSION)
                regions.append(_intersection(left.box, right.box))
    if foreground.possible_split_regions:
        reasons.add(RetakeReason.POSSIBLE_SPLIT)
        regions.extend(foreground.possible_split_regions)
    if foreground.possible_merge_regions:
        reasons.add(RetakeReason.POSSIBLE_MERGE)
        regions.extend(foreground.possible_merge_regions)
    if (
        quality.blur_score < policy.min_blur_score
        or not policy.exposure_range[0] <= quality.exposure_score <= policy.exposure_range[1]
        or quality.reflection_ratio > policy.max_reflection_ratio
    ):
        reasons.add(RetakeReason.CAPTURE_QUALITY_UNVERIFIED)
    if foreground.risk_score > policy.max_risk_score:
        reasons.add(RetakeReason.COMPLETENESS_RISK_EXCEEDED)

    ordered_reasons = tuple(reason for reason in RetakeReason if reason in reasons)
    return CompletenessDecision(not ordered_reasons, ordered_reasons, _canonical_regions(tuple(regions)))


def build_counterfactuals(gt_boxes: tuple[BreadProposal, ...]) -> tuple[CounterfactualCase, ...]:
    """Build deterministic synthetic misses without relabeling them as observed data."""
    if not isinstance(gt_boxes, tuple) or not all(isinstance(item, BreadProposal) for item in gt_boxes):
        raise InvalidDetectorOutput("counterfactual GT boxes must be an immutable BreadProposal tuple")
    if not gt_boxes:
        return ()
    width, height = _proposal_frame_dimensions(gt_boxes[0])
    _validate_proposals(gt_boxes, width, height)
    cases: list[CounterfactualCase] = []
    clear = _clear_foreground()
    for index, proposal in enumerate(gt_boxes):
        cases.append(CounterfactualCase(
            "counterfactual", "missing", gt_boxes[:index] + gt_boxes[index + 1:],
            replace(clear, uncovered_ratio=1.0, problem_regions=(proposal.box.xyxy,)),
        ))
    for left_index, left in enumerate(gt_boxes):
        for right_index in range(left_index + 1, len(gt_boxes)):
            right = gt_boxes[right_index]
            if _box_iou(left.box, right.box) == 0.0:
                continue
            merged = replace(left, box=_union(left.box, right.box))
            proposals = tuple(item for index, item in enumerate(gt_boxes) if index not in {left_index, right_index}) + (merged,)
            cases.append(CounterfactualCase(
                "counterfactual", "merge", proposals,
                replace(clear, possible_merge_regions=(_union(left.box, right.box).xyxy,)),
            ))
    for index, proposal in enumerate(gt_boxes):
        left, right = _split(proposal)
        cases.append(CounterfactualCase(
            "counterfactual", "split", gt_boxes[:index] + (left, right) + gt_boxes[index + 1:],
            replace(clear, possible_split_regions=(proposal.box.xyxy,)),
        ))
    for index, proposal in enumerate(gt_boxes):
        truncated = replace(proposal, box=Box(0.0, proposal.box.y, proposal.box.width, proposal.box.height))
        cases.append(CounterfactualCase("counterfactual", "truncation", gt_boxes[:index] + (truncated,) + gt_boxes[index + 1:], clear))
    return tuple(cases)


def _canonical_frame_size(frame_size: object) -> tuple[int, int]:
    if (
        not isinstance(frame_size, tuple)
        or len(frame_size) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in frame_size)
    ):
        raise InvalidDetectorOutput("canonical frame dimensions must be positive integers")
    return frame_size


def _validate_proposals(proposals: object, width: int, height: int) -> None:
    if not isinstance(proposals, tuple):
        raise InvalidDetectorOutput("detector proposals must be an immutable tuple")
    for proposal in proposals:
        if not isinstance(proposal, BreadProposal):
            raise InvalidDetectorOutput("detector proposals must contain BreadProposal values")
        proposal_width, proposal_height = _proposal_frame_dimensions(proposal)
        if proposal_width != width or proposal_height != height:
            raise InvalidDetectorOutput("detector proposal dimensions must equal the canonical frame")
        try:
            box = proposal.box
        except AttributeError as exc:
            raise InvalidDetectorOutput("detector proposal box is missing") from exc
        if not isinstance(box, Box):
            raise InvalidDetectorOutput("detector box must be a canonical Box")
        try:
            x_min, y_min, x_max, y_max = box.xyxy
        except (AttributeError, TypeError, ValueError) as exc:
            raise InvalidDetectorOutput("detector box is malformed") from exc
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (x_min, y_min, x_max, y_max)):
            raise InvalidDetectorOutput("detector box coordinates must be finite")
        if x_min < 0 or y_min < 0 or x_max <= x_min or y_max <= y_min or x_max > width or y_max > height:
            raise InvalidDetectorOutput("detector box must remain in canonical frame bounds")


def _proposal_frame_dimensions(proposal: BreadProposal) -> tuple[int, int]:
    try:
        proposal_width = proposal.image_width
        proposal_height = proposal.image_height
    except AttributeError as exc:
        raise InvalidDetectorOutput("detector proposal dimensions are missing") from exc
    if (
        not isinstance(proposal_width, int)
        or isinstance(proposal_width, bool)
        or proposal_width < 1
        or not isinstance(proposal_height, int)
        or isinstance(proposal_height, bool)
        or proposal_height < 1
    ):
        raise InvalidDetectorOutput("detector proposal dimensions must be positive integers")
    return proposal_width, proposal_height


def _regions(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be an immutable tuple")
    for region in value:
        _region(region, name)


def _region(value: object, name: str) -> BoxXYXY:
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError(f"{name} entries must be xyxy tuples")
    _finite_tuple(value, 4, name)
    x_min, y_min, x_max, y_max = value
    if x_min < 0 or y_min < 0 or x_max <= x_min or y_max <= y_min:
        raise ValueError(f"{name} entries must be non-negative ordered xyxy boxes")
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def _validate_regions_in_frame(regions: tuple[BoxXYXY, ...], width: int, height: int) -> None:
    for region in regions:
        _, _, x_max, y_max = region
        if x_max > width or y_max > height:
            raise ValueError("foreground problem regions must remain in canonical frame bounds")


def _canonical_regions(regions: tuple[BoxXYXY, ...]) -> tuple[BoxXYXY, ...]:
    normalized = {_region(region, "problem_regions") for region in regions}
    return tuple(sorted(normalized, key=lambda region: (region[1], region[0], region[3], region[2])))


def _box_iou(left: Box, right: Box) -> float:
    intersection = _intersection(left, right)
    if intersection == (0.0, 0.0, 0.0, 0.0):
        return 0.0
    x_min, y_min, x_max, y_max = intersection
    intersection_area = (x_max - x_min) * (y_max - y_min)
    return intersection_area / (left.width * left.height + right.width * right.height - intersection_area)


def _intersection(left: Box, right: Box) -> BoxXYXY:
    x_min, y_min = max(left.x, right.x), max(left.y, right.y)
    x_max, y_max = min(left.x + left.width, right.x + right.width), min(left.y + left.height, right.y + right.height)
    return (x_min, y_min, x_max, y_max) if x_max > x_min and y_max > y_min else (0.0, 0.0, 0.0, 0.0)


def _enters_border_margin(box: Box, width: int, height: int, margin_ratio: float) -> bool:
    margin_x, margin_y = width * margin_ratio, height * margin_ratio
    return box.x <= margin_x or box.y <= margin_y or box.x + box.width >= width - margin_x or box.y + box.height >= height - margin_y


def _union(left: Box, right: Box) -> Box:
    x_min, y_min = min(left.x, right.x), min(left.y, right.y)
    x_max, y_max = max(left.x + left.width, right.x + right.width), max(left.y + left.height, right.y + right.height)
    return Box(x_min, y_min, x_max - x_min, y_max - y_min)


def _split(proposal: BreadProposal) -> tuple[BreadProposal, BreadProposal]:
    if proposal.box.width >= proposal.box.height:
        first_width = proposal.box.width / 2.0
        return replace(proposal, box=Box(proposal.box.x, proposal.box.y, first_width, proposal.box.height)), replace(proposal, box=Box(proposal.box.x + first_width, proposal.box.y, proposal.box.width - first_width, proposal.box.height))
    first_height = proposal.box.height / 2.0
    return replace(proposal, box=Box(proposal.box.x, proposal.box.y, proposal.box.width, first_height)), replace(proposal, box=Box(proposal.box.x, proposal.box.y + first_height, proposal.box.width, proposal.box.height - first_height))


def _clear_foreground() -> ForegroundEvidence:
    return ForegroundEvidence(0.0, 1.0, (), (), (), 0.0)


def _finite(value: object, name: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _finite_tuple(value: object, length: int, name: str) -> None:
    if not isinstance(value, tuple) or len(value) != length:
        raise ValueError(f"{name} must be a tuple of length {length}")
    for item in value:
        _finite(item, name)


def _unit_interval(value: object, name: str) -> None:
    _finite(value, name)
    if value < 0 or value > 1:
        raise ValueError(f"{name} must be within [0, 1]")
