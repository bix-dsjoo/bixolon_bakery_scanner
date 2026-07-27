"""Deterministic, fold-isolated crop metadata for verifier training."""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping, Sequence

from bakery_scanner.contracts import Box, VerifierState


CANONICAL_IMAGE_WIDTH = 1152
CANONICAL_IMAGE_HEIGHT = 1536
MAX_OTHER_GROUND_TRUTH_OVERLAP = 0.05


@dataclass(frozen=True, slots=True)
class VerifierExample:
    image_id: int
    crop_xywh: Box
    state: VerifierState


def build_verifier_examples(
    *,
    image_ids: frozenset[int],
    ground_truth: Mapping[int, Sequence[Box]],
    seed: int,
) -> Sequence[VerifierExample]:
    """Return deterministic four-state crop metadata restricted to ``image_ids``."""
    rng = random.Random(seed)
    examples: list[VerifierExample] = []
    for image_id in sorted(image_ids):
        boxes = tuple(ground_truth.get(image_id, ()))
        if not boxes:
            continue
        if any(not isinstance(box, Box) for box in boxes):
            raise ValueError("ground_truth must contain Box values")

        exact = _exactly_one_crop(boxes, rng)
        if exact is not None:
            examples.append(VerifierExample(image_id, exact, VerifierState.EXACTLY_ONE))

        partial = _partial_crop(boxes, rng)
        if partial is not None:
            examples.append(VerifierExample(image_id, partial, VerifierState.PARTIAL))

        multiple = _multiple_crop(boxes, rng)
        if multiple is not None:
            examples.append(VerifierExample(image_id, multiple, VerifierState.MULTIPLE))

        invalid = _invalid_crop(boxes, rng)
        if invalid is not None:
            examples.append(VerifierExample(image_id, invalid, VerifierState.INVALID))
    return tuple(examples)


def _exactly_one_crop(boxes: tuple[Box, ...], rng: random.Random) -> Box | None:
    candidates = list(boxes)
    rng.shuffle(candidates)
    for candidate in candidates:
        crop = _clamp(candidate)
        contained = sum(_fully_contains(crop, box) for box in boxes)
        if contained != 1:
            continue
        if all(
            box == candidate
            or _ground_truth_overlap(crop, box) <= MAX_OTHER_GROUND_TRUTH_OVERLAP
            for box in boxes
        ):
            return crop
    return None


def _partial_crop(boxes: tuple[Box, ...], rng: random.Random) -> Box | None:
    candidates = list(boxes)
    rng.shuffle(candidates)
    for box in candidates:
        crop = _clamp(Box(box.x + box.width / 2, box.y, box.width / 2, box.height))
        if 0 < _ground_truth_overlap(crop, box) < 1:
            return crop
    return None


def _multiple_crop(boxes: tuple[Box, ...], rng: random.Random) -> Box | None:
    pairs = list(combinations(boxes, 2))
    rng.shuffle(pairs)
    for first, second in pairs:
        left = min(first.x, second.x)
        top = min(first.y, second.y)
        right = max(first.x + first.width, second.x + second.width)
        bottom = max(first.y + first.height, second.y + second.height)
        crop = _clamp(Box(left, top, right - left, bottom - top))
        if (
            _ground_truth_overlap(crop, first) > MAX_OTHER_GROUND_TRUTH_OVERLAP
            and _ground_truth_overlap(crop, second) > MAX_OTHER_GROUND_TRUTH_OVERLAP
        ):
            return crop
    return None


def _invalid_crop(boxes: tuple[Box, ...], rng: random.Random) -> Box | None:
    edge = min(64.0, *(min(box.width, box.height) for box in boxes))
    positions = [
        (x, y)
        for y in range(0, CANONICAL_IMAGE_HEIGHT - int(edge) + 1, int(edge))
        for x in range(0, CANONICAL_IMAGE_WIDTH - int(edge) + 1, int(edge))
    ]
    rng.shuffle(positions)
    for x, y in positions:
        crop = Box(x, y, edge, edge)
        if all(_ground_truth_overlap(crop, box) == 0 for box in boxes):
            return crop
    return None


def _clamp(box: Box) -> Box:
    width = min(box.width, CANONICAL_IMAGE_WIDTH)
    height = min(box.height, CANONICAL_IMAGE_HEIGHT)
    x = min(max(box.x, 0.0), CANONICAL_IMAGE_WIDTH - width)
    y = min(max(box.y, 0.0), CANONICAL_IMAGE_HEIGHT - height)
    return Box(x, y, width, height)


def _fully_contains(outer: Box, inner: Box) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and inner.x + inner.width <= outer.x + outer.width
        and inner.y + inner.height <= outer.y + outer.height
    )


def _ground_truth_overlap(crop: Box, ground_truth: Box) -> float:
    left = max(crop.x, ground_truth.x)
    top = max(crop.y, ground_truth.y)
    right = min(crop.x + crop.width, ground_truth.x + ground_truth.width)
    bottom = min(crop.y + crop.height, ground_truth.y + ground_truth.height)
    return max(0.0, right - left) * max(0.0, bottom - top) / (
        ground_truth.width * ground_truth.height
    )
