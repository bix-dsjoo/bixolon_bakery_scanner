from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from bakery_scanner.classification.evidence import (
    EvaluatedRow,
    EvidenceInput,
    EvidenceRow,
    atomic_write_bytes,
    evaluate_rows,
    load_evidence_manifest,
    load_repvit_training_hashes,
)
from bakery_scanner.classification.contracts import ModelScoreVector
from bakery_scanner.contracts import Box
from scripts.collect_classifier_evidence import collect_rows
from scripts.evaluate_classifier_policy import build_evaluation_report


def _write_image(path: Path, color: str = "red") -> str:
    Image.new("RGB", (40, 30), color).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(
    image_name: str,
    *,
    sample_id: str = "cal-000001",
    capture_group: str = "batch03:scene0042",
    registered: bool = True,
    sku_id: int | None = 6,
    role: str = "development",
) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "capture_group": capture_group,
        "image_path": image_name,
        "box_xyxy": [1, 2, 30, 25],
        "registered": registered,
        "sku_id": sku_id,
        "role": role,
    }


def test_manifest_resolves_images_validates_box_and_hash(tmp_path: Path):
    image = tmp_path / "sample.png"
    expected_hash = _write_image(image)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_manifest_row(image.name)])

    rows = load_evidence_manifest(manifest, training_image_hashes=frozenset())

    assert len(rows) == 1
    assert rows[0].image_path == image.resolve()
    assert rows[0].box.xyxy == (1.0, 2.0, 30.0, 25.0)
    assert rows[0].image_sha256 == expected_hash


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"capture_group": ""}, "capture_group"),
        ({"registered": True, "sku_id": None}, "registered"),
        ({"registered": False, "sku_id": 6}, "unregistered"),
        ({"role": "training"}, "role"),
        ({"box_xyxy": [0, 0, 41, 30]}, "bounds"),
        ({"unexpected": 1}, "exact"),
    ],
)
def test_manifest_rejects_invalid_rows(
    tmp_path: Path,
    mutation: dict[str, object],
    message: str,
):
    image = tmp_path / "sample.png"
    _write_image(image)
    row = _manifest_row(image.name)
    row.update(mutation)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [row])

    with pytest.raises(ValueError, match=message):
        load_evidence_manifest(manifest, training_image_hashes=frozenset())


def test_manifest_rejects_duplicate_ids_and_duplicate_image_content(tmp_path: Path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_image(first)
    second.write_bytes(first.read_bytes())
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        [
            _manifest_row(first.name),
            _manifest_row(second.name, sample_id="cal-000001"),
        ],
    )
    with pytest.raises(ValueError, match="duplicate sample_id"):
        load_evidence_manifest(manifest, training_image_hashes=frozenset())

    rows = [
        _manifest_row(first.name),
        _manifest_row(second.name, sample_id="cal-000002"),
    ]
    _write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="duplicate image SHA-256"):
        load_evidence_manifest(manifest, training_image_hashes=frozenset())


def test_manifest_rejects_repvit_training_image_hash(tmp_path: Path):
    image = tmp_path / "sample.png"
    image_hash = _write_image(image)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, [_manifest_row(image.name)])

    with pytest.raises(ValueError, match="RepViT training"):
        load_evidence_manifest(
            manifest,
            training_image_hashes=frozenset({image_hash}),
        )


def test_training_hashes_are_loaded_from_configured_repvit_manifest(tmp_path: Path):
    training_manifest = tmp_path / "repvit.manifest.json"
    training_manifest.write_text(
        json.dumps(
            {
                "sources": [
                    {"identity": "one.png", "sha256": "a" * 64, "sku_id": 1},
                    {"identity": "two.png", "sha256": "b" * 64, "sku_id": 2},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_repvit_training_hashes(training_manifest) == frozenset(
        {"a" * 64, "b" * 64}
    )


def test_evidence_row_requires_exact_twenty_finite_scores():
    values = tuple(index / 20 for index in range(20))
    row = EvidenceRow(
        sample_id="cal-000001",
        capture_group="batch03:scene0042",
        registered=True,
        sku_id=6,
        role="development",
        image_sha256="0" * 64,
        repvit_values=values,
        dinov3_values=values,
        repvit_artifact_id="repvit_m1_15plus5_v1",
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
    )
    assert json.loads(row.to_json_bytes())["sku_id"] == 6

    with pytest.raises(ValueError, match="20"):
        EvidenceRow(
            sample_id="cal-000002",
            capture_group="group",
            registered=True,
            sku_id=6,
            role="development",
            image_sha256="1" * 64,
            repvit_values=values[:-1],
            dinov3_values=values,
            repvit_artifact_id="repvit_m1_15plus5_v1",
            dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        )


def test_metrics_separate_precision_coverage_top3_and_assisted_success():
    metrics = evaluate_rows(
        (
            EvaluatedRow("one", True, 6, "sku", 6, ()),
            EvaluatedRow("two", True, 5, "unknown", None, (6, 5, 19)),
            EvaluatedRow("three", True, 19, "unknown", None, (6, 5, 19)),
        )
    )

    assert metrics.auto_precision == 1.0
    assert metrics.auto_coverage == pytest.approx(1 / 3)
    assert metrics.fallback_top3_recall == 1.0
    assert metrics.assisted_success == 1.0
    assert metrics.release_passes


def test_metrics_define_zero_denominators_and_none_never_passes_release():
    no_auto = evaluate_rows(
        (EvaluatedRow("one", True, 6, "unknown", None, (6, 5, 19)),)
    )
    assert no_auto.auto_precision is None
    assert not no_auto.release_passes

    no_registered_unknown = evaluate_rows((EvaluatedRow("one", True, 6, "sku", 6, ()),))
    assert no_registered_unknown.fallback_top3_recall is None
    assert not no_registered_unknown.release_passes


def test_unregistered_auto_is_error_but_not_top3_denominator():
    metrics = evaluate_rows(
        (
            EvaluatedRow("registered", True, 6, "unknown", None, (6, 5, 19)),
            EvaluatedRow("foreign", False, None, "sku", 6, ()),
        )
    )

    assert metrics.auto_errors == 1
    assert metrics.auto_precision == 0.0
    assert metrics.fallback_top3_denominator == 1
    assert metrics.fallback_top3_recall == 1.0
    assert metrics.assisted_failures == 1


class _FixedRunner:
    def __init__(self, model_id: str, kind: str):
        self.model_id = model_id
        self.kind = kind
        self.calls = 0

    def score(self, crops):
        self.calls += 1
        assert len(crops) == 3
        values = (
            tuple([1.0 / 20.0] * 20) if self.kind == "probability" else tuple(range(20))
        )
        return ModelScoreVector(
            self.model_id,
            tuple(range(1, 21)),
            values,
            self.kind,
        )


def test_collection_forces_both_models_for_every_input(tmp_path: Path):
    image_path = tmp_path / "sample.png"
    image_hash = _write_image(image_path)
    inputs = (
        EvidenceInput(
            sample_id="sample-1",
            capture_group="capture-1",
            image_path=image_path.resolve(),
            box=Box(0, 0, 20, 20),
            registered=True,
            sku_id=1,
            role="development",
            image_sha256=image_hash,
        ),
    )
    repvit = _FixedRunner("repvit_m1_15plus5_v1", "probability")
    dino = _FixedRunner("dinov3_vits16_15plus5_v1", "similarity")

    rows = collect_rows(inputs, repvit, dino, paddings=(0.05, 0.10, 0.15))

    assert repvit.calls == 1
    assert dino.calls == 1
    assert rows[0].image_sha256 == image_hash


def test_atomic_write_does_not_leave_partial_payload(tmp_path: Path):
    output = tmp_path / "artifact.json"
    output.write_bytes(b"old")

    atomic_write_bytes(output, b'{"new":true}')

    assert output.read_bytes() == b'{"new":true}'
    assert not tuple(tmp_path.glob(f".{output.name}.*.tmp"))


def test_locked_report_contains_requested_slices_and_exact_failures():
    rows = (
        EvidenceRow(
            sample_id="locked-1",
            capture_group="capture-1",
            registered=True,
            sku_id=1,
            role="locked_acceptance",
            image_sha256="a" * 64,
            repvit_values=tuple([0.8] + [0.2 / 19] * 19),
            dinov3_values=tuple([4.0] + [0.0] * 19),
            repvit_artifact_id="repvit_m1_15plus5_v1",
            dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        ),
    )
    evaluated = (EvaluatedRow("locked-1", True, 1, "sku", 2, ()),)

    report = build_evaluation_report(
        rows,
        evaluated,
        calibration_sha256="b" * 64,
        evidence_sha256="c" * 64,
    )

    assert set(report["metrics"]) == {
        "overall",
        "per_sku",
        "base_15",
        "incremental_5",
        "registered",
        "unregistered",
    }
    assert report["failures"]["automatic_errors"] == ["locked-1"]
    assert report["release_passes"] is False
