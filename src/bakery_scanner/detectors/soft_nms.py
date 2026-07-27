"""Deterministic Gaussian Soft-NMS for source-coordinate detector proposals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import math

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detectors.proposal_policy import canonical_proposal_order


@dataclass(frozen=True, slots=True)
class SoftNmsPolicy:
    score_threshold: float
    overlap_threshold: float
    sigma: float


def soft_nms(proposals: Sequence[BreadProposal], policy: SoftNmsPolicy) -> tuple[BreadProposal, ...]:
    """Return canonical score-decayed candidates without deleting overlap rows."""
    _validate_policy(policy)
    _reject_duplicate_coordinates(proposals)

    by_image_source: dict[tuple[int, str], list[BreadProposal]] = {}
    for proposal in proposals:
        by_image_source.setdefault((proposal.image_id, proposal.source), []).append(proposal)

    decayed: list[BreadProposal] = []
    for key in sorted(by_image_source):
        decayed.extend(_soft_nms_image(by_image_source[key], policy))
    return tuple(decayed)


def final_boxes(proposals: Sequence[BreadProposal], policy: SoftNmsPolicy) -> Mapping[int, tuple[Box, ...]]:
    """Apply the final score threshold after deterministic score decay."""
    result: dict[int, tuple[Box, ...]] = {}
    for proposal in soft_nms(proposals, policy):
        if proposal.score >= policy.score_threshold:
            result[proposal.image_id] = result.get(proposal.image_id, ()) + (proposal.box,)
    return result


def _soft_nms_image(proposals: Sequence[BreadProposal], policy: SoftNmsPolicy) -> tuple[BreadProposal, ...]:
    remaining = list(sorted(proposals, key=canonical_proposal_order))
    selected: list[BreadProposal] = []
    while remaining:
        remaining.sort(key=canonical_proposal_order)
        current = remaining.pop(0)
        selected.append(current)
        for index, candidate in enumerate(remaining):
            overlap = _iou(current.box, candidate.box)
            if overlap > policy.overlap_threshold:
                remaining[index] = replace(candidate, score=candidate.score * math.exp(-(overlap * overlap) / policy.sigma))
    return tuple(selected)


def _validate_policy(policy: SoftNmsPolicy) -> None:
    values = (policy.score_threshold, policy.overlap_threshold, policy.sigma)
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in values):
        raise ValueError("Soft-NMS policy values must be finite numbers")
    if not 0 <= policy.score_threshold <= 1:
        raise ValueError("score_threshold must be in [0, 1]")
    if not 0 <= policy.overlap_threshold <= 1:
        raise ValueError("overlap_threshold must be in [0, 1]")
    if policy.sigma <= 0:
        raise ValueError("sigma must be positive")


def _reject_duplicate_coordinates(proposals: Sequence[BreadProposal]) -> None:
    seen: set[tuple[int, str, float, float, float, float]] = set()
    for proposal in proposals:
        coordinate = (proposal.image_id, proposal.source, proposal.box.x, proposal.box.y, proposal.box.width, proposal.box.height)
        if coordinate in seen:
            raise ValueError("duplicate candidate coordinates")
        seen.add(coordinate)


def _iou(first: Box, second: Box) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union
