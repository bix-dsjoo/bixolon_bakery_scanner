from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    ForegroundEvidence,
)
from bakery_scanner.detection.completeness_evidence import (
    REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS,
    build_completeness_execution_record,
    load_completeness_evidence_bundle,
    write_completeness_evidence_bundle,
)


FRAME = (1000, 800)
IMAGE_SHA256 = "d" * 64


def _proposals(count: int) -> tuple[BreadProposal, ...]:
    return tuple(
        BreadProposal(
            index + 1,
            r"C:\private\detector\predictions.json",
            0.99 - index * 0.01,
            Box(100.0 + index * 90.0, 120.0, 60.0, 60.0),
            *FRAME,
        )
        for index in range(count)
    )


def _foreground() -> ForegroundEvidence:
    return ForegroundEvidence(0.0, 1.0, (), (), (), 0.0)


def _quality() -> CaptureQuality:
    return CaptureQuality(100.0, 0.5, 0.0)


def _policy() -> CompletenessPolicy:
    return CompletenessPolicy(0.1, 0.6, 0.01, 10.0, (0.2, 0.8), 0.1, 0.5)


def _artifacts() -> dict[str, str]:
    return {
        key: hashlib.sha256(key.encode("utf-8")).hexdigest()
        for key in REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS
    }


def _record(*, count: int = 2):
    return build_completeness_execution_record(
        source_scene_identity=r"C:\private\scans\scene-0001.jpg",
        source_image_sha256=IMAGE_SHA256,
        fold_index=0,
        canonical_frame_version="exif_transposed_rgb_v1",
        canonical_frame_mode="RGB",
        frame_size=FRAME,
        proposals=_proposals(count),
        foreground=_foreground(),
        quality=_quality(),
        policy=_policy(),
        completeness_policy_id="completeness_15plus5_oof_fold_0_v1",
        completeness_policy_artifact_sha256="e" * 64,
        code_sha256="f" * 64,
        input_artifact_sha256=_artifacts(),
    )


@pytest.mark.parametrize("count", (1, 2, 8))
def test_actual_execution_record_accepts_every_positive_count_without_a_scan_limit(count: int) -> None:
    record = _record(count=count)

    assert record.decision_state == "accepted_scan"
    assert record.decision_reasons == ()
    assert len(record.final_source_proposal_sha256) == count


def test_actual_execution_record_derives_zero_target_retake_and_no_final_source_set() -> None:
    record = _record(count=0)

    assert record.decision_state == "needs_retake"
    assert record.decision_reasons == ("no_target_detected",)
    assert record.final_source_proposal_sha256 == ()


def test_bundle_is_canonical_hash_admitted_and_path_private(tmp_path) -> None:
    record = _record()
    root = tmp_path / "completeness-evidence"

    index_sha256 = write_completeness_evidence_bundle((record,), root)
    bundle = load_completeness_evidence_bundle(root, expected_index_sha256=index_sha256)
    loaded = bundle.require_record(record.source_scene_sha256, record.sha256)

    assert loaded == record
    assert bundle.index_sha256 == index_sha256
    serialized = (root / "records" / f"{record.source_scene_sha256}.json").read_text(encoding="utf-8")
    assert r"C:\private" not in serialized
    assert "scene-0001.jpg" not in serialized
    assert "predictions.json" not in serialized
    assert json.loads(serialized)["payload_sha256"] == record.payload_sha256


def test_direct_replacement_cannot_satisfy_the_loaded_record_binding(tmp_path) -> None:
    record = _record()
    root = tmp_path / "completeness-evidence"
    index_sha256 = write_completeness_evidence_bundle((record,), root)
    forged = replace(record, code_sha256="a" * 64)

    bundle = load_completeness_evidence_bundle(root, expected_index_sha256=index_sha256)

    with pytest.raises(ValueError, match="record SHA-256"):
        bundle.require_record(record.source_scene_sha256, forged.sha256)


def test_record_and_index_byte_mutation_are_detected(tmp_path) -> None:
    record = _record()
    record_root = tmp_path / "record-mutation"
    index_sha256 = write_completeness_evidence_bundle((record,), record_root)
    record_path = record_root / "records" / f"{record.source_scene_sha256}.json"
    record_path.write_bytes(record_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="record (byte size|SHA-256|canonical)"):
        load_completeness_evidence_bundle(record_root, expected_index_sha256=index_sha256)

    index_root = tmp_path / "index-mutation"
    index_sha256 = write_completeness_evidence_bundle((record,), index_root)
    index_path = index_root / "index.json"
    index_path.write_bytes(index_path.read_bytes().replace(b'"schema_version":1', b'"schema_version":2'))

    with pytest.raises(ValueError, match="index SHA-256"):
        load_completeness_evidence_bundle(index_root, expected_index_sha256=index_sha256)


def test_relative_or_cwd_shadow_root_is_never_admitted(tmp_path, monkeypatch) -> None:
    record = _record()
    canonical_root = tmp_path / "canonical" / "evidence"
    index_sha256 = write_completeness_evidence_bundle((record,), canonical_root)
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    monkeypatch.chdir(shadow)

    with pytest.raises(ValueError, match="absolute"):
        load_completeness_evidence_bundle(
            canonical_root.relative_to(tmp_path),
            expected_index_sha256=index_sha256,
        )

    assert load_completeness_evidence_bundle(
        canonical_root,
        expected_index_sha256=index_sha256,
    ).require_record(record.source_scene_sha256, record.sha256) == record
