"""Deterministic candidate relation graph; it never suppresses proposals."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bakery_scanner.contracts import Box, BreadProposal


@dataclass(frozen=True, slots=True)
class ProposalComponent:
    image_id: int
    members: tuple[BreadProposal, ...]

    def __post_init__(self) -> None:
        if not self.members or any(row.image_id != self.image_id for row in self.members):
            raise ValueError("component members must be non-empty and share an image")
        if self.members != tuple(sorted(self.members, key=_proposal_key)):
            raise ValueError("component members must use canonical ordering")


def build_proposal_components(
    proposals: tuple[BreadProposal, ...],
    *,
    normalized_center_distance: float = 0.65,
) -> tuple[ProposalComponent, ...]:
    """Group related candidates as resolver evidence without applying NMS."""
    if not math.isfinite(normalized_center_distance) or normalized_center_distance < 0.0:
        raise ValueError("normalized_center_distance must be finite and non-negative")
    rows = tuple(sorted(proposals, key=_proposal_key))
    parents = list(range(len(rows)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            parents[max(root_first, root_second)] = min(root_first, root_second)

    for first, left in enumerate(rows):
        for second in range(first + 1, len(rows)):
            right = rows[second]
            if left.image_id != right.image_id:
                continue
            if _related(left.box, right.box, normalized_center_distance):
                union(first, second)
    grouped: dict[int, list[BreadProposal]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(find(index), []).append(row)
    components = tuple(
        ProposalComponent(members[0].image_id, tuple(members))
        for _, members in sorted(grouped.items(), key=lambda item: _proposal_key(item[1][0]))
    )
    return components


def box_iou(first: Box, second: Box) -> float:
    left, top = max(first.x, second.x), max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    return intersection / (first.width * first.height + second.width * second.height - intersection)


def _related(first: Box, second: Box, center_limit: float) -> bool:
    if box_iou(first, second) > 0.0 or _contains(first, second) or _contains(second, first):
        return True
    first_center = (first.x + first.width / 2.0, first.y + first.height / 2.0)
    second_center = (second.x + second.width / 2.0, second.y + second.height / 2.0)
    scale = max(math.hypot(first.width, first.height), math.hypot(second.width, second.height))
    return math.dist(first_center, second_center) / scale <= center_limit


def _contains(outer: Box, inner: Box) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.x + outer.width >= inner.x + inner.width
        and outer.y + outer.height >= inner.y + inner.height
    )


def _proposal_key(row: BreadProposal) -> tuple[float | str, ...]:
    return (row.image_id, row.box.y, row.box.x, row.box.height, row.box.width, -row.score, row.source)
