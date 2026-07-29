import json
import math

import pytest

from bakery_scanner.prototype.camera_protocol import (
    AnalyzeRequest,
    PingRequest,
    ShutdownRequest,
    WorkerPhase,
    encode_event,
    parse_request,
    progress_event,
)


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
