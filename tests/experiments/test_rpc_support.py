"""Contract tests for deterministic, immutable RPC few-shot support selection."""

from __future__ import annotations

import hashlib

import pytest

from bakery_scanner.experiments.rpc_support import (
    SupportCandidate,
    materialize_support_order,
    parse_train_capture_stratum,
    support_prefix,
)


def _candidate(
    source_identity: str,
    file_name: str,
    embedding: tuple[float, float],
    *,
    category_id: int = 7,
) -> SupportCandidate:
    return SupportCandidate(
        category_id=category_id,
        source_identity=source_identity,
        image_sha256=hashlib.sha256(source_identity.encode("utf-8")).hexdigest(),
        source_byte_size=100,
        capture_stratum=parse_train_capture_stratum(file_name, category_id),
        embedding=embedding,
    )


def _candidates() -> tuple[SupportCandidate, ...]:
    return (
        _candidate("centroid", "roll_camera1-top.jpg", (0.0, 1.0)),
        _candidate("far-a", "roll_camera2-top.jpg", (1.0, 0.0)),
        _candidate("far-b", "roll_camera1-bottom.jpg", (-0.9, 0.1)),
        _candidate("repeat-far", "roll_camera1-top.jpg", (0.3, 0.9)),
    )


def _duplicate_candidates() -> tuple[SupportCandidate, ...]:
    candidate = _candidate("same-source", "roll_camera1-top.jpg", (1.0, 0.0))
    return candidate, candidate


def test_diversity_order_selects_one_stratum_before_repeating():
    ordered = materialize_support_order(_candidates(), method="div", seed=11)
    assert [row.source_identity for row in ordered.candidates[:3]] == ["centroid", "far-a", "far-b"]
    assert support_prefix(ordered, 1) == ordered.candidates[:1]
    assert support_prefix(ordered, 3)[:1] == support_prefix(ordered, 1)


def test_diversity_second_pick_uses_unrepresented_stratum_even_if_repeat_is_farther():
    candidates = (
        _candidate("centroid", "roll_camera1-top.jpg", (0.0, 1.0)),
        _candidate("near-left", "roll_camera1-top.jpg", (-0.1, 0.99)),
        _candidate("near-right", "roll_camera1-top.jpg", (0.1, 0.99)),
        _candidate("repeat-far", "roll_camera1-top.jpg", (0.0, -1.0)),
        _candidate("other", "roll_camera2-top.jpg", (1.0, 0.0)),
    )

    ordered = materialize_support_order(candidates, method="div", seed=11)

    assert [item.source_identity for item in ordered.candidates[:2]] == ["near-right", "other"]


def test_random_order_is_seeded_sha_ranking_without_replacement():
    candidates = _candidates()
    order = materialize_support_order(candidates, method="rnd", seed=11)
    expected = sorted(
        candidates,
        key=lambda item: (
            hashlib.sha256(f"11:{item.source_identity}".encode("utf-8")).hexdigest(),
            item.source_identity,
        ),
    )

    assert order.candidates == tuple(expected)
    assert order == materialize_support_order(tuple(reversed(candidates)), method="rnd", seed=11)
    assert order.source_identities == tuple(item.source_identity for item in expected)
    assert len(order.manifest_sha256) == 64


def test_selector_rejects_duplicate_source_identity():
    with pytest.raises(ValueError, match="duplicate source identity"):
        materialize_support_order(_duplicate_candidates(), method="rnd", seed=11)


def test_selector_rejects_zero_vector():
    with pytest.raises(ValueError, match="zero-norm embedding"):
        materialize_support_order((_candidate("zero", "roll_camera1-top.jpg", (0.0, 0.0)),), method="div", seed=11)


def test_selector_rejects_inconsistent_embedding_dimensions():
    candidates = _candidates() + (
        SupportCandidate(
            category_id=7,
            source_identity="three-d",
            image_sha256="a" * 64,
            source_byte_size=100,
            capture_stratum=parse_train_capture_stratum("roll_camera3-top.jpg", 7),
            embedding=(1.0, 0.0, 0.0),
        ),
    )
    with pytest.raises(ValueError, match="embedding dimensions"):
        materialize_support_order(candidates, method="div", seed=11)


def test_parse_train_capture_stratum_rejects_invalid_filename():
    with pytest.raises(ValueError, match="invalid train capture filename"):
        parse_train_capture_stratum("roll-camera1-top.jpg", 7)


def test_selector_rejects_unsupported_method():
    with pytest.raises(ValueError, match="unsupported support selection method"):
        materialize_support_order(_candidates(), method="nearest", seed=11)


def test_support_prefix_rejects_request_above_availability():
    order = materialize_support_order(_candidates(), method="rnd", seed=11)
    with pytest.raises(ValueError, match="insufficient support candidates"):
        support_prefix(order, 5)
