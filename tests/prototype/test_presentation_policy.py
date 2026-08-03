import hashlib
import json
from pathlib import Path

import pytest

from bakery_scanner.prototype.presentation_policy import PresentationPolicy


POLICY = {
    "box_overlap_iou": 0.7,
    "candidate_top12_min_margin": 0.05,
    "candidate_top1_min_score": 0.3,
    "policy_id": "camera_action_state_v1",
    "schema_version": 1,
}

V2_POLICY = {
    "box_overlap_iou": 0.7,
    "policy_id": "camera_action_state_v2",
    "schema_version": 2,
}


def _write_policy(path: Path, payload: object = POLICY) -> bytes:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def _proposal(object_id: str, bbox_xyxy: list[float]) -> dict[str, object]:
    return {"object_id": object_id, "bbox_xyxy": bbox_xyxy}


def _decision(
    object_id: str,
    *,
    sku_id: int | None,
    top3: list[tuple[int, float]] | None = None,
) -> dict[str, object]:
    return {
        "object_id": object_id,
        "sku_id": sku_id,
        "top3": [
            {"rank": rank, "sku_id": sku_id, "score": score}
            for rank, (sku_id, score) in enumerate(top3 or [], start=1)
        ],
    }


def _load_policy(tmp_path: Path) -> tuple[PresentationPolicy, bytes]:
    path = tmp_path / "camera_presentation_policy.json"
    payload = _write_policy(path)
    return PresentationPolicy.load(path), payload


def _load_v2_policy(tmp_path: Path) -> tuple[PresentationPolicy, bytes]:
    path = tmp_path / "camera_action_state_v2.json"
    payload = _write_policy(path, V2_POLICY)
    return PresentationPolicy.load(path), payload


def test_load_keeps_the_sha256_of_the_exact_policy_bytes(tmp_path):
    policy, payload = _load_policy(tmp_path)

    assert policy.policy_id == "camera_action_state_v1"
    assert policy.policy_sha256 == hashlib.sha256(payload).hexdigest()


def test_load_v2_binds_exact_bytes_without_candidate_thresholds(tmp_path):
    policy, payload = _load_v2_policy(tmp_path)

    assert policy.schema_version == 2
    assert policy.policy_id == "camera_action_state_v2"
    assert policy.policy_sha256 == hashlib.sha256(payload).hexdigest()
    assert policy.candidate_top1_min_score is None
    assert policy.candidate_top12_min_margin is None


@pytest.mark.parametrize(
    "payload",
    [
        {**V2_POLICY, "candidate_top1_min_score": 0.3},
        {**V2_POLICY, "candidate_top12_min_margin": 0.05},
        {key: value for key, value in V2_POLICY.items() if key != "box_overlap_iou"},
        {**V2_POLICY, "policy_id": "camera_action_state_v1"},
        {**V2_POLICY, "schema_version": 1},
    ],
)
def test_load_v2_rejects_mixed_or_incomplete_policy_artifacts(tmp_path, payload):
    path = tmp_path / "policy-v2.json"
    _write_policy(path, payload)

    with pytest.raises(ValueError):
        PresentationPolicy.load(path)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {**POLICY, "extra": True},
        {key: value for key, value in POLICY.items() if key != "box_overlap_iou"},
        {**POLICY, "schema_version": 2},
        {**POLICY, "policy_id": "other"},
        {**POLICY, "box_overlap_iou": -0.1},
        {**POLICY, "candidate_top1_min_score": float("inf")},
    ],
)
def test_load_rejects_malformed_policy_artifacts(tmp_path, payload):
    path = tmp_path / "policy.json"
    _write_policy(path, payload)

    with pytest.raises(ValueError):
        PresentationPolicy.load(path)


def test_changed_policy_bytes_have_a_different_verified_sha256(tmp_path):
    path = tmp_path / "policy.json"
    first = _write_policy(path)
    initial = PresentationPolicy.load(path)
    changed = b'{\n  "box_overlap_iou": 0.7,\n  "candidate_top12_min_margin": 0.05,\n  "candidate_top1_min_score": 0.3,\n  "policy_id": "camera_action_state_v1",\n  "schema_version": 1\n}\n'
    path.write_bytes(changed)
    reloaded = PresentationPolicy.load(path)

    assert initial.policy_sha256 == hashlib.sha256(first).hexdigest()
    assert reloaded.policy_sha256 == hashlib.sha256(changed).hexdigest()
    assert reloaded.policy_sha256 != initial.policy_sha256


def test_no_proposals_requests_a_full_scan_retake(tmp_path):
    policy, _ = _load_policy(tmp_path)

    payload = policy.evaluate(proposals=[], decisions=[]).to_payload()

    assert payload == {
        "state": "needs_retake",
        "final_count_usable": False,
        "retake_scope": "scan",
        "retake_object_ids": [],
        "instruction_code": "no_bread_detected",
        "candidate_object_ids": [],
        "policy_id": "camera_action_state_v1",
        "policy_sha256": policy.policy_sha256,
    }


def test_iou_at_threshold_requests_retake_for_both_objects(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [
        _proposal("object-2", [3.0, 0.0, 20.0, 17.0]),
        _proposal("object-1", [0.0, 0.0, 17.0, 17.0]),
    ]
    decisions = [_decision("object-1", sku_id=1), _decision("object-2", sku_id=2)]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "needs_retake"
    assert payload["final_count_usable"] is False
    assert payload["retake_scope"] == "object"
    assert payload["retake_object_ids"] == ["object-1", "object-2"]
    assert payload["instruction_code"] == "separate_breads"
    assert payload["candidate_object_ids"] == []


def test_iou_just_below_threshold_keeps_confirmed_objects_usable(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [
        _proposal("object-1", [0.0, 0.0, 1000.0, 1000.0]),
        _proposal("object-2", [177.0, 0.0, 1177.0, 1000.0]),
    ]
    decisions = [_decision("object-1", sku_id=1), _decision("object-2", sku_id=2)]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "normal"
    assert payload["final_count_usable"] is True
    assert payload["retake_scope"] is None
    assert payload["retake_object_ids"] == []
    assert payload["instruction_code"] is None
    assert payload["candidate_object_ids"] == []


def test_weak_unknown_requests_a_targeted_retake(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-7", [0.0, 0.0, 10.0, 10.0])]
    decisions = [_decision("object-7", sku_id=None, top3=[(1, 0.29), (2, 0.10), (3, 0.01)])]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "needs_retake"
    assert payload["final_count_usable"] is False
    assert payload["retake_scope"] == "object"
    assert payload["retake_object_ids"] == ["object-7"]
    assert payload["instruction_code"] == "candidate_evidence_weak"
    assert payload["candidate_object_ids"] == []


def test_v2_weak_unknown_routes_to_top3_review_not_retake(tmp_path):
    policy, _ = _load_v2_policy(tmp_path)
    proposals = [_proposal("object-7", [0.0, 0.0, 10.0, 10.0])]
    decisions = [
        _decision(
            "object-7",
            sku_id=None,
            top3=[(1, 0.01), (2, 0.01), (3, 0.0)],
        )
    ]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "unknown"
    assert payload["final_count_usable"] is True
    assert payload["retake_scope"] is None
    assert payload["retake_object_ids"] == []
    assert payload["instruction_code"] is None
    assert payload["candidate_object_ids"] == ["object-7"]


def test_v2_overlap_still_requires_object_retake(tmp_path):
    policy, _ = _load_v2_policy(tmp_path)
    proposals = [
        _proposal("object-2", [3.0, 0.0, 20.0, 17.0]),
        _proposal("object-1", [0.0, 0.0, 17.0, 17.0]),
    ]
    decisions = [_decision("object-1", sku_id=1), _decision("object-2", sku_id=2)]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "needs_retake"
    assert payload["instruction_code"] == "separate_breads"
    assert payload["retake_object_ids"] == ["object-1", "object-2"]
    assert payload["candidate_object_ids"] == []


def test_tied_unknown_requests_a_targeted_retake(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-7", [0.0, 0.0, 10.0, 10.0])]
    decisions = [_decision("object-7", sku_id=None, top3=[(1, 0.80), (2, 0.80), (3, 0.01)])]

    assert policy.evaluate(proposals=proposals, decisions=decisions).to_payload()[
        "retake_object_ids"
    ] == ["object-7"]


def test_unknown_at_exact_score_and_margin_boundaries_is_a_usable_candidate(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-3", [0.0, 0.0, 10.0, 10.0])]
    decisions = [_decision("object-3", sku_id=None, top3=[(1, 0.30), (2, 0.25), (3, 0.01)])]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "unknown"
    assert payload["final_count_usable"] is True
    assert payload["retake_scope"] is None
    assert payload["retake_object_ids"] == []
    assert payload["instruction_code"] is None
    assert payload["candidate_object_ids"] == ["object-3"]


def test_all_confirmed_objects_are_normal(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-1", [0.0, 0.0, 10.0, 10.0])]
    decisions = [_decision("object-1", sku_id=1)]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "normal"
    assert payload["final_count_usable"] is True
    assert payload["retake_scope"] is None
    assert payload["retake_object_ids"] == []
    assert payload["instruction_code"] is None
    assert payload["candidate_object_ids"] == []


def test_input_order_does_not_change_the_presentation_decision(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [
        _proposal("object-2", [20.0, 0.0, 30.0, 10.0]),
        _proposal("object-1", [0.0, 0.0, 10.0, 10.0]),
    ]
    decisions = [
        _decision("object-2", sku_id=None, top3=[(2, 0.75), (1, 0.60), (3, 0.1)]),
        _decision("object-1", sku_id=None, top3=[(1, 0.20), (2, 0.1), (3, 0.01)]),
    ]

    first = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()
    second = policy.evaluate(
        proposals=list(reversed(proposals)), decisions=list(reversed(decisions))
    ).to_payload()

    assert first == second
    assert first["retake_object_ids"] == ["object-1"]


def test_unmatched_proposal_ids_fail_closed_before_overlap_routing(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [
        _proposal("object-1", [0.0, 0.0, 17.0, 17.0]),
        _proposal("object-2", [3.0, 0.0, 20.0, 17.0]),
    ]
    decisions = [_decision("object-1", sku_id=1)]

    with pytest.raises(ValueError, match="bijection"):
        policy.evaluate(proposals=proposals, decisions=decisions)


def test_unmatched_decision_ids_fail_closed_before_unknown_routing(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-1", [0.0, 0.0, 10.0, 10.0])]
    decisions = [
        _decision("object-1", sku_id=1),
        _decision("object-2", sku_id=None, top3=[(2, 0.90), (1, 0.80), (3, 0.1)]),
    ]

    with pytest.raises(ValueError, match="bijection"):
        policy.evaluate(proposals=proposals, decisions=decisions)


@pytest.mark.parametrize(
    ("proposals", "decisions"),
    [
        (
            [
                _proposal("object-1", [0.0, 0.0, 10.0, 10.0]),
                _proposal("object-1", [20.0, 0.0, 30.0, 10.0]),
            ],
            [_decision("object-1", sku_id=1)],
        ),
        (
            [_proposal("object-1", [0.0, 0.0, 10.0, 10.0])],
            [_decision("object-1", sku_id=1), _decision("object-1", sku_id=1)],
        ),
    ],
)
def test_duplicate_final_object_ids_fail_closed(tmp_path, proposals, decisions):
    policy, _ = _load_policy(tmp_path)

    with pytest.raises(ValueError, match="unique"):
        policy.evaluate(proposals=proposals, decisions=decisions)


def test_unknown_score_just_below_threshold_requests_object_retake(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-3", [0.0, 0.0, 10.0, 10.0])]
    decisions = [
        _decision(
            "object-3",
            sku_id=None,
            top3=[(1, 0.2999999999995), (2, 0.10), (3, 0.01)],
        )
    ]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "needs_retake"
    assert payload["retake_object_ids"] == ["object-3"]
    assert payload["instruction_code"] == "candidate_evidence_weak"


def test_unknown_margin_just_below_threshold_requests_object_retake(tmp_path):
    policy, _ = _load_policy(tmp_path)
    proposals = [_proposal("object-3", [0.0, 0.0, 10.0, 10.0])]
    decisions = [
        _decision(
            "object-3",
            sku_id=None,
            top3=[(1, 0.80), (2, 0.7500000000005), (3, 0.01)],
        )
    ]

    payload = policy.evaluate(proposals=proposals, decisions=decisions).to_payload()

    assert payload["state"] == "needs_retake"
    assert payload["retake_object_ids"] == ["object-3"]
    assert payload["instruction_code"] == "candidate_evidence_weak"
