"""Deterministic, fold-isolated crop metadata for verifier training."""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
import json
from typing import Mapping, Sequence

from bakery_scanner.contracts import Box, VerifierState


ALGORITHM = "deterministic_four_state_verifier_crops"
ALGORITHM_VERSION = 1


@dataclass(frozen=True, slots=True)
class VerifierExample:
    image_id: int
    crop_xywh: Box
    state: VerifierState


@dataclass(frozen=True, slots=True)
class VerifierGenerationMetadata:
    """Canonical, serializable receipt for verifier crop generation."""

    algorithm: str
    version: int
    seed: int
    canonical_image_width: int
    canonical_image_height: int
    overlap_measure: str
    overlap_threshold: float
    exactly_one_strategy: str
    partial_strategy: str
    partial_fraction: float
    multiple_strategy: str
    invalid_strategy: str
    invalid_crop_cap: float
    invalid_grid_minimum_step: int

    def to_dict(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "canonical_image_height": self.canonical_image_height,
            "canonical_image_width": self.canonical_image_width,
            "exactly_one_strategy": self.exactly_one_strategy,
            "invalid_crop_cap": self.invalid_crop_cap,
            "invalid_grid_minimum_step": self.invalid_grid_minimum_step,
            "invalid_strategy": self.invalid_strategy,
            "multiple_strategy": self.multiple_strategy,
            "overlap_measure": self.overlap_measure,
            "overlap_threshold": self.overlap_threshold,
            "partial_fraction": self.partial_fraction,
            "partial_strategy": self.partial_strategy,
            "seed": self.seed,
            "version": self.version,
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def verifier_generation_metadata(*, seed: int) -> VerifierGenerationMetadata:
    """Return the complete, stable generation receipt for ``seed``."""
    return VerifierGenerationMetadata(
        algorithm=ALGORITHM,
        version=ALGORITHM_VERSION,
        seed=seed,
        canonical_image_width=1152,
        canonical_image_height=1536,
        overlap_measure="intersection_over_ground_truth_area",
        overlap_threshold=0.05,
        exactly_one_strategy="clamped_target_box",
        partial_strategy="right_half_without_full_or_multiple_overlap",
        partial_fraction=0.5,
        multiple_strategy="clamped_pair_envelope",
        invalid_strategy="seeded_grid_first_non_overlapping",
        invalid_crop_cap=64.0,
        invalid_grid_minimum_step=1,
    )


def build_verifier_examples(
    *,
    image_ids: frozenset[int],
    ground_truth: Mapping[int, Sequence[Box]],
    seed: int,
) -> Sequence[VerifierExample]:
    """Return deterministic four-state crop metadata restricted to ``image_ids``."""
    metadata = verifier_generation_metadata(seed=seed)
    rng = random.Random(metadata.seed)
    examples: list[VerifierExample] = []
    for image_id in sorted(image_ids):
        boxes = tuple(ground_truth.get(image_id, ()))
        if not boxes:
            continue
        if any(not isinstance(box, Box) for box in boxes):
            raise ValueError("ground_truth must contain Box values")

        exact = _exactly_one_crop(boxes, rng, metadata)
        if exact is not None:
            examples.append(VerifierExample(image_id, exact, VerifierState.EXACTLY_ONE))

        partial = _partial_crop(boxes, rng, metadata)
        if partial is not None:
            examples.append(VerifierExample(image_id, partial, VerifierState.PARTIAL))

        multiple = _multiple_crop(boxes, rng, metadata)
        if multiple is not None:
            examples.append(VerifierExample(image_id, multiple, VerifierState.MULTIPLE))

        invalid = _invalid_crop(boxes, rng, metadata)
        if invalid is not None:
            examples.append(VerifierExample(image_id, invalid, VerifierState.INVALID))
    return tuple(examples)


def _exactly_one_crop(
    boxes: tuple[Box, ...], rng: random.Random, metadata: VerifierGenerationMetadata
) -> Box | None:
    candidates = list(boxes)
    rng.shuffle(candidates)
    for candidate in candidates:
        crop = _clamp(candidate, metadata)
        if _state_for_crop(crop, boxes, metadata) is VerifierState.EXACTLY_ONE:
            return crop
    return None


def _partial_crop(
    boxes: tuple[Box, ...], rng: random.Random, metadata: VerifierGenerationMetadata
) -> Box | None:
    candidates = list(boxes)
    rng.shuffle(candidates)
    for box in candidates:
        crop = _clamp(
            Box(
                box.x + box.width * (1 - metadata.partial_fraction),
                box.y,
                box.width * metadata.partial_fraction,
                box.height,
            ),
            metadata,
        )
        if _state_for_crop(crop, boxes, metadata) is VerifierState.PARTIAL:
            return crop
    return None


def _multiple_crop(
    boxes: tuple[Box, ...], rng: random.Random, metadata: VerifierGenerationMetadata
) -> Box | None:
    pairs = list(combinations(boxes, 2))
    rng.shuffle(pairs)
    for first, second in pairs:
        left = min(first.x, second.x)
        top = min(first.y, second.y)
        right = max(first.x + first.width, second.x + second.width)
        bottom = max(first.y + first.height, second.y + second.height)
        crop = _clamp(Box(left, top, right - left, bottom - top), metadata)
        if _state_for_crop(crop, boxes, metadata) is VerifierState.MULTIPLE:
            return crop
    return None


def _invalid_crop(
    boxes: tuple[Box, ...], rng: random.Random, metadata: VerifierGenerationMetadata
) -> Box | None:
    edge = min(metadata.invalid_crop_cap, *(min(box.width, box.height) for box in boxes))
    step = max(metadata.invalid_grid_minimum_step, int(edge))
    positions = [
        (x, y)
        for y in range(0, metadata.canonical_image_height - step + 1, step)
        for x in range(0, metadata.canonical_image_width - step + 1, step)
    ]
    rng.shuffle(positions)
    for x, y in positions:
        crop = Box(x, y, edge, edge)
        if _state_for_crop(crop, boxes, metadata) is VerifierState.INVALID:
            return crop
    return None


def _clamp(box: Box, metadata: VerifierGenerationMetadata) -> Box:
    width = min(box.width, metadata.canonical_image_width)
    height = min(box.height, metadata.canonical_image_height)
    x = min(max(box.x, 0.0), metadata.canonical_image_width - width)
    y = min(max(box.y, 0.0), metadata.canonical_image_height - height)
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


def _state_for_crop(
    crop: Box, boxes: tuple[Box, ...], metadata: VerifierGenerationMetadata
) -> VerifierState | None:
    overlaps = tuple(_ground_truth_overlap(crop, box) for box in boxes)
    contained = tuple(_fully_contains(crop, box) for box in boxes)
    if all(overlap == 0 for overlap in overlaps):
        return VerifierState.INVALID
    if sum(contained) == 1 and all(
        overlap <= metadata.overlap_threshold
        for overlap, is_contained in zip(overlaps, contained)
        if not is_contained
    ):
        return VerifierState.EXACTLY_ONE
    if sum(overlap > metadata.overlap_threshold for overlap in overlaps) >= 2:
        return VerifierState.MULTIPLE
    if not any(contained) and any(overlap > 0 for overlap in overlaps):
        return VerifierState.PARTIAL
    return None
