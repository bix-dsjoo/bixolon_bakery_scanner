import json
import math

import pytest

from bakery_scanner.prototype import camera_protocol
from bakery_scanner.prototype.camera_protocol import (
    AnalyzeRequest,
    PingRequest,
    ShutdownRequest,
    WorkerPhase,
    encode_event,
    parse_request,
    progress_event,
)

_POLICY_SHA256 = "a" * 64


def _presentation(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "state": "normal",
        "final_count_usable": True,
        "retake_scope": None,
        "retake_object_ids": [],
        "instruction_code": None,
        "candidate_object_ids": [],
        "policy_id": "camera_action_state_v1",
        "policy_sha256": _POLICY_SHA256,
    }
    payload.update(overrides)
    return payload


def _result(presentation: dict[str, object]) -> dict[str, object]:
    return {
        "type": "result",
        "request_id": "request-1",
        "objects": [
            {"object_id": "object-1", "sku_id": 6},
            {
                "object_id": "object-2",
                "sku_id": None,
                "top3": [
                    {"rank": 1, "sku_id": 4, "score": 0.41},
                    {"rank": 2, "sku_id": 2, "score": 0.32},
                    {"rank": 3, "sku_id": 7, "score": 0.27},
                ],
            },
        ],
        "presentation": presentation,
        "timings_ms": {
            "decode_preprocess": 1.0,
            "detector": 1.0,
            "crop": 1.0,
            "repvit": 1.0,
            "dinov3": 1.0,
            "fusion": 1.0,
            "postprocess": 1.0,
            "total": 1.0,
        },
        "diagnostics": {"object_count": 2, "dino_object_count": 1},
    }


def test_analyze_requires_unique_fields_absolute_existing_image(tmp_path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")

    request = parse_request(
        json.dumps(
            {
                "type": "analyze",
                "request_id": "7",
                "image_path": str(image.resolve()),
            }
        )
    )

    assert request == AnalyzeRequest("7", image.resolve())


@pytest.mark.parametrize(
    "line",
    [
        '{"type":"analyze","request_id":"1","image_path":"capture.jpg"}',
        '{"type":"ping","type":"shutdown"}',
        '{"type":"ping","extra":true}',
    ],
)
def test_protocol_rejects_ambiguous_input(line):
    with pytest.raises(ValueError):
        parse_request(line)


@pytest.mark.parametrize(
    ("line", "request_type"),
    [
        ('{"type":"ping","request_id":"p1"}', PingRequest),
        ('{"type":"shutdown","request_id":"s1"}', ShutdownRequest),
    ],
)
def test_control_requests_accept_only_their_required_fields(line, request_type):
    assert parse_request(line) == request_type(request_type.__name__[0].lower() + "1")


@pytest.mark.parametrize(
    "line",
    [
        "",
        "[]",
        '{"type":"unsupported","request_id":"1"}',
        '{"type":"ping","request_id":""}',
        '{"type":"ping","request_id":1}',
        '{"type":"ping"}',
        '{"type":"analyze","request_id":"1"}',
        '{"type":"analyze","request_id":"1","image_path":1}',
        '{"type":"analyze","request_id":"1","image_path":"C:/missing.jpg"}',
    ],
)
def test_protocol_rejects_malformed_or_invalid_requests(line):
    with pytest.raises(ValueError):
        parse_request(line)


def test_requests_are_immutable(tmp_path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    request = parse_request(
        json.dumps(
            {
                "type": "analyze",
                "request_id": "7",
                "image_path": str(image.resolve()),
            }
        )
    )

    with pytest.raises((AttributeError, TypeError)):
        request.request_id = "changed"


def test_progress_event_is_correlated_and_canonical():
    event = progress_event("7", WorkerPhase.DETECTING)

    assert event == {"type": "progress", "request_id": "7", "phase": "detecting"}
    assert encode_event(event) == (
        '{"phase":"detecting","request_id":"7","type":"progress"}\n'
    )


def test_encode_event_appends_exactly_one_newline():
    assert encode_event({"message": "line one\nline two"}).endswith("}\n")
    assert not encode_event({"message": "line one\nline two"}).endswith("}\n\n")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_encode_event_rejects_non_finite_numbers(value):
    with pytest.raises(ValueError):
        encode_event({"value": value})


@pytest.mark.parametrize(
    "presentation",
    [
        _presentation(),
        _presentation(
            state="unknown",
            candidate_object_ids=["object-2"],
        ),
        _presentation(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="scan",
            instruction_code="no_bread_detected",
        ),
        _presentation(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="object",
            retake_object_ids=["object-1"],
            instruction_code="separate_breads",
        ),
    ],
)
def test_validate_result_event_accepts_each_consistent_presentation_state(
    presentation,
):
    camera_protocol.validate_result_event(_result(presentation))


def test_validate_result_event_accepts_v2_unknown_with_exact_top3():
    camera_protocol.validate_result_event(
        _result(
            _presentation(
                state="unknown",
                candidate_object_ids=["object-2"],
                policy_id="camera_action_state_v2",
            )
        )
    )


def test_validate_result_event_rejects_v2_candidate_evidence_retake():
    with pytest.raises(ValueError, match="inconsistent"):
        camera_protocol.validate_result_event(
            _result(
                _presentation(
                    state="needs_retake",
                    final_count_usable=False,
                    retake_scope="object",
                    retake_object_ids=["object-2"],
                    instruction_code="candidate_evidence_weak",
                    policy_id="camera_action_state_v2",
                )
            )
        )


@pytest.mark.parametrize(
    "top3",
    [
        [],
        [
            {"rank": 1, "sku_id": 4, "score": 0.41},
            {"rank": 2, "sku_id": 2, "score": 0.32},
        ],
        [
            {"rank": 1, "sku_id": 4, "score": 0.41},
            {"rank": 1, "sku_id": 2, "score": 0.32},
            {"rank": 3, "sku_id": 7, "score": 0.27},
        ],
    ],
)
def test_validate_result_event_requires_exact_ranked_top3_for_v2_candidate(top3):
    result = _result(
        _presentation(
            state="unknown",
            candidate_object_ids=["object-2"],
            policy_id="camera_action_state_v2",
        )
    )
    result["objects"][1]["top3"] = top3

    with pytest.raises(ValueError, match="Top3"):
        camera_protocol.validate_result_event(result)


@pytest.mark.parametrize(
    "presentation",
    [
        _presentation(final_count_usable=False),
        _presentation(policy_sha256="A" * 64),
        _presentation(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="scan",
            retake_object_ids=["object-1"],
            instruction_code="no_bread_detected",
        ),
        _presentation(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="object",
            instruction_code="separate_breads",
        ),
        _presentation(instruction_code="candidate_evidence_weak"),
        _presentation(
            state="unknown",
            instruction_code="candidate_evidence_weak",
            candidate_object_ids=["object-2"],
        ),
        _presentation(
            state="unknown",
            candidate_object_ids=["object-1"],
        ),
    ],
)
def test_validate_result_event_rejects_inconsistent_presentation(presentation):
    with pytest.raises(ValueError):
        camera_protocol.validate_result_event(_result(presentation))


@pytest.mark.parametrize(
    "diagnostics",
    [
        {},
        {"object_count": 1, "dino_object_count": 1},
        {"object_count": 2, "dino_object_count": 3},
        {"object_count": True, "dino_object_count": 1},
    ],
)
def test_validate_result_event_rejects_invalid_diagnostics(diagnostics):
    result = _result(_presentation())
    result["diagnostics"] = diagnostics

    with pytest.raises(ValueError, match="diagnostics"):
        camera_protocol.validate_result_event(result)


def test_validate_result_event_requires_exact_eight_stage_timings():
    result = _result(_presentation())
    result["timings_ms"].pop("fusion")

    with pytest.raises(ValueError, match="timings_ms"):
        camera_protocol.validate_result_event(result)
