"""Shared deterministic retention for raw detector proposals."""

from __future__ import annotations

from collections.abc import Iterable

from bakery_scanner.contracts import BreadProposal


RAW_SCORE_FLOOR = 0.001
RAW_PROPOSAL_LIMIT = 30


def retain_raw_proposals(proposals: Iterable[BreadProposal]) -> tuple[BreadProposal, ...]:
    """Keep the bounded raw evidence that all detector consumers evaluate.

    Retention happens before any calibrated score threshold.  Each image and
    detector source is ordered by the canonical raw proposal order before its
    independent cap is applied.
    """
    by_image_source: dict[tuple[int, str], list[BreadProposal]] = {}
    for proposal in proposals:
        if proposal.score >= RAW_SCORE_FLOOR:
            by_image_source.setdefault((proposal.image_id, proposal.source), []).append(proposal)
    retained: list[BreadProposal] = []
    for key in sorted(by_image_source):
        retained.extend(sorted(by_image_source[key], key=canonical_proposal_order)[:RAW_PROPOSAL_LIMIT])
    return tuple(retained)


def canonical_proposal_order(proposal: BreadProposal) -> tuple[float, float, float, float, float]:
    """Return the deterministic score and source-coordinate ordering key."""
    return (-proposal.score, proposal.box.y, proposal.box.x, proposal.box.height, proposal.box.width)
