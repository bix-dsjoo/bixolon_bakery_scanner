import pytest

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detectors.soft_nms import SoftNmsPolicy, final_boxes, soft_nms


def _proposal(score: float, x: float, y: float = 0, width: float = 10, height: float = 10, *, image_id: int = 1) -> BreadProposal:
    return BreadProposal(image_id, "dfine_n_640", score, Box(x, y, width, height), 100, 100)


def test_soft_nms_decays_overlapping_lower_score_without_deleting_row():
    high_score_box = _proposal(.9, 0)
    overlap_box = _proposal(.8, 1)

    result = soft_nms((high_score_box, overlap_box), SoftNmsPolicy(.1, .3, .5))

    assert len(result) == 2
    assert result[1].score < overlap_box.score
    assert result[1].box == overlap_box.box


def test_non_overlapping_candidates_keep_original_score():
    left_box = _proposal(.9, 0)
    right_box = _proposal(.8, 20)
    policy = SoftNmsPolicy(.1, .3, .5)

    assert soft_nms((left_box, right_box), policy) == (left_box, right_box)


def test_final_threshold_is_applied_after_decay():
    high_score_box = _proposal(.9, 0)
    overlap_box = _proposal(.8, 1)
    policy = SoftNmsPolicy(.5, .3, .5)

    assert final_boxes((high_score_box, overlap_box), policy) == {1: (high_score_box.box,)}


@pytest.mark.parametrize(
    "policy",
    (
        SoftNmsPolicy(-.1, .3, .5),
        SoftNmsPolicy(1.1, .3, .5),
        SoftNmsPolicy(.1, -.1, .5),
        SoftNmsPolicy(.1, 1.1, .5),
        SoftNmsPolicy(.1, .3, 0),
    ),
)
def test_soft_nms_rejects_invalid_policy_values(policy):
    with pytest.raises(ValueError):
        soft_nms((), policy)


def test_soft_nms_rejects_duplicate_coordinates_within_source_image():
    proposal = _proposal(.9, 0)

    with pytest.raises(ValueError, match="duplicate candidate coordinates"):
        soft_nms((proposal, proposal), SoftNmsPolicy(.1, .3, .5))
