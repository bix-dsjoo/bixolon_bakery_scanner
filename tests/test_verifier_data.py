import json

from bakery_scanner.contracts import Box
from bakery_scanner.verifier import data as verifier_data
from bakery_scanner.verifier.data import VerifierState, build_verifier_examples


def _ground_truth_overlap(crop: Box, ground_truth: Box) -> float:
    left = max(crop.x, ground_truth.x)
    top = max(crop.y, ground_truth.y)
    right = min(crop.x + crop.width, ground_truth.x + ground_truth.width)
    bottom = min(crop.y + crop.height, ground_truth.y + ground_truth.height)
    return max(0.0, right - left) * max(0.0, bottom - top) / (
        ground_truth.width * ground_truth.height
    )


def _is_fully_contained(inner: Box, outer: Box) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and inner.x + inner.width <= outer.x + outer.width
        and inner.y + inner.height <= outer.y + outer.height
    )


def _matching_states(crop: Box, ground_truth: tuple[Box, ...]) -> set[VerifierState]:
    overlaps = [_ground_truth_overlap(crop, box) for box in ground_truth]
    contained = [_is_fully_contained(box, crop) for box in ground_truth]
    states: set[VerifierState] = set()
    if all(overlap == 0 for overlap in overlaps):
        states.add(VerifierState.INVALID)
    if sum(contained) == 1 and all(
        overlap <= 0.05 for overlap, is_contained in zip(overlaps, contained)
        if not is_contained
    ):
        states.add(VerifierState.EXACTLY_ONE)
    if (
        not any(contained)
        and any(overlap > 0 for overlap in overlaps)
        and sum(overlap > 0.05 for overlap in overlaps) < 2
    ):
        states.add(VerifierState.PARTIAL)
    if sum(overlap > 0.05 for overlap in overlaps) >= 2:
        states.add(VerifierState.MULTIPLE)
    return states


def test_examples_cover_four_states_deterministically():
    boxes = {
        1: (
            Box(100, 100, 40, 40),
            Box(300, 300, 50, 50),
        )
    }

    first = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )
    second = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )

    assert first == second
    assert {row.state for row in first} == set(VerifierState)


def test_examples_respect_the_four_state_crop_contract_and_canonical_bounds():
    boxes = {
        1: (
            Box(100, 100, 40, 40),
            Box(300, 300, 50, 50),
        )
    }

    examples = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )
    by_state = {row.state: row for row in examples}
    ground_truth = boxes[1]

    assert all(
        0 <= row.crop_xywh.x
        and 0 <= row.crop_xywh.y
        and row.crop_xywh.x + row.crop_xywh.width <= 1152
        and row.crop_xywh.y + row.crop_xywh.height <= 1536
        for row in examples
    )
    exactly_one = by_state[VerifierState.EXACTLY_ONE].crop_xywh
    assert sum(_is_fully_contained(box, exactly_one) for box in ground_truth) == 1
    assert all(
        _ground_truth_overlap(exactly_one, box) <= 0.05
        for box in ground_truth
        if not _is_fully_contained(box, exactly_one)
    )
    partial = by_state[VerifierState.PARTIAL].crop_xywh
    assert any(
        _ground_truth_overlap(partial, box) > 0
        and not _is_fully_contained(box, partial)
        for box in ground_truth
    )
    multiple = by_state[VerifierState.MULTIPLE].crop_xywh
    assert sum(_ground_truth_overlap(multiple, box) > 0.05 for box in ground_truth) >= 2
    invalid = by_state[VerifierState.INVALID].crop_xywh
    assert all(_ground_truth_overlap(invalid, box) == 0 for box in ground_truth)


def test_training_examples_never_include_validation_image():
    boxes = {
        1: (Box(100, 100, 40, 40), Box(300, 300, 50, 50)),
        2: (Box(500, 100, 40, 40), Box(700, 300, 50, 50)),
    }
    validation_ids = frozenset({2})

    train_examples = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )

    assert {row.image_id for row in train_examples}.isdisjoint(validation_ids)


def test_partial_examples_reject_overlapping_multiple_boxes():
    boxes = {
        1: (
            Box(100, 100, 80, 80),
            Box(130, 105, 80, 80),
        )
    }

    examples = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )

    assert VerifierState.PARTIAL not in {row.state for row in examples}
    assert all(
        _matching_states(row.crop_xywh, boxes[row.image_id]) == {row.state}
        for row in examples
    )


def test_generation_metadata_is_canonical_and_seed_specific():
    first = verifier_data.verifier_generation_metadata(seed=7)
    second = verifier_data.verifier_generation_metadata(seed=7)
    expected = {
        "algorithm": "deterministic_four_state_verifier_crops",
        "canonical_image_height": 1536,
        "canonical_image_width": 1152,
        "exactly_one_strategy": "clamped_target_box",
        "invalid_crop_cap": 64.0,
        "invalid_grid_minimum_step": 1,
        "invalid_strategy": "seeded_grid_first_non_overlapping",
        "multiple_strategy": "clamped_pair_envelope",
        "overlap_measure": "intersection_over_ground_truth_area",
        "overlap_threshold": 0.05,
        "partial_fraction": 0.5,
        "partial_strategy": "right_half_without_full_or_multiple_overlap",
        "seed": 7,
        "version": 1,
    }

    assert first == second
    assert first.to_dict() == expected
    assert json.loads(first.to_json_bytes()) == expected
    assert first.to_json_bytes() == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert verifier_data.verifier_generation_metadata(seed=8).to_dict()["seed"] == 8


def test_invalid_crop_generation_supports_subpixel_ground_truth_boxes():
    boxes = {1: (Box(100.1, 100.1, 0.5, 0.5),)}

    examples = build_verifier_examples(
        image_ids=frozenset({1}), ground_truth=boxes, seed=7
    )

    assert VerifierState.INVALID in {row.state for row in examples}
