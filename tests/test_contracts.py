import json

import pytest

from bakery_scanner.contracts import (
    Box,
    BoxSystemResult,
    BreadProposal,
    DetectorKind,
    SceneKey,
    VerifiedBreadBox,
    VerifierState,
)


def test_bread_proposal_rejects_nonfinite_or_out_of_bounds_box():
    with pytest.raises(ValueError):
        BreadProposal(
            image_id=1,
            source="dfine_n_768",
            score=float("nan"),
            box=Box(0, 0, 10, 10),
            image_width=100,
            image_height=100,
        )

    with pytest.raises(ValueError):
        BreadProposal(
            image_id=1,
            source="dfine_n_768",
            score=0.5,
            box=Box(91, 0, 10, 10),
            image_width=100,
            image_height=100,
        )


def test_contracts_are_immutable_and_enums_have_stable_identities():
    box = Box(1, 2, 3, 4)
    assert box.xyxy == (1.0, 2.0, 4.0, 6.0)
    assert [int(state) for state in VerifierState] == [0, 1, 2, 3]
    assert DetectorKind.DFINE.value == "dfine"
    assert SceneKey("batch01", 12) < SceneKey("batch02", 1)
    with pytest.raises(AttributeError):
        box.x = 5


def test_result_json_is_canonical_and_rejects_extra_fields():
    result = BoxSystemResult(
        source_id="scan-1",
        source_sha256="a" * 64,
        boxes=(
            VerifiedBreadBox(
                object_id="bread-0001",
                box=Box(1, 2, 30, 40),
                score=0.99,
                verifier_state=VerifierState.EXACTLY_ONE,
                sources=("dfine_n_768", "rtmdet_tiny_768"),
            ),
        ),
        audit_hashes=("b" * 64,),
    )

    payload = result.to_json_bytes()

    assert payload == BoxSystemResult.from_json_bytes(payload).to_json_bytes()
    decoded = json.loads(payload)
    decoded["unexpected"] = True
    with pytest.raises(ValueError):
        BoxSystemResult.from_json_bytes(json.dumps(decoded).encode("utf-8"))


def test_result_requires_canonical_box_and_source_ordering():
    with pytest.raises(ValueError):
        VerifiedBreadBox(
            object_id="bread-0002",
            box=Box(1, 2, 3, 4),
            score=0.9,
            verifier_state=VerifierState.EXACTLY_ONE,
            sources=("rtmdet_tiny_768", "dfine_n_768"),
        )
