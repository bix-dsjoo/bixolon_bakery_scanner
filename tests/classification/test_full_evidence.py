from __future__ import annotations

import pytest
import torch
from PIL import Image

from bakery_scanner.classification.contracts import ModelScoreVector
from bakery_scanner.classification.evidence import EvidenceInput
from bakery_scanner.classification.full_evidence import FullEvidenceRow
from bakery_scanner.classification.repvit import RepVitEvidence
from bakery_scanner.contracts import Box
from scripts.collect_classifier_evidence import collect_full_rows


def _row(**overrides: object) -> FullEvidenceRow:
    values: dict[str, object] = {
        "sample_id": "development-001",
        "capture_group": "capture-a",
        "registered": True,
        "sku_id": 6,
        "role": "development",
        "image_sha256": "0" * 64,
        "repvit_values": (0.05,) * 20,
        "dinov3_values": tuple(float(index) for index in range(20)),
        "candidate_sku_ids": (6, 5, 19),
        "local_values": (0.8, 0.7, 0.2),
        "repvit_crop_disagreement": 0.02,
        "nearest_prototype_distance": 0.11,
        "local_product_patch_count": 420,
        "local_product_patch_ratio": 0.71,
        "repvit_checkpoint_sha256": "1" * 64,
        "repvit_manifest_sha256": "2" * 64,
        "repvit_prototype_sha256": "3" * 64,
        "dinov3_weights_sha256": "4" * 64,
        "dinov3_support_sha256": "5" * 64,
        "dinov3_local_bank_sha256": "6" * 64,
        "preprocess_sha256": "7" * 64,
    }
    values.update(overrides)
    return FullEvidenceRow(**values)


def test_full_evidence_row_round_trips_canonical_candidate_evidence():
    row = _row()

    restored = FullEvidenceRow.from_json_bytes(row.to_json_bytes())

    assert restored == row
    assert restored.candidate_sku_ids == (6, 5, 19)
    assert restored.local_product_patch_count == 420


def test_full_evidence_row_rejects_misaligned_candidate_scores():
    with pytest.raises(ValueError, match="local_values"):
        _row(local_values=(0.8, 0.7))


def test_full_evidence_row_rejects_duplicate_candidates():
    with pytest.raises(ValueError, match="candidate_sku_ids"):
        _row(candidate_sku_ids=(6, 6, 19))


class _RepVit:
    def score_with_evidence(self, crops):
        return RepVitEvidence(
            ModelScoreVector("repvit_m1_15plus5_v1", tuple(range(1, 21)), (0.05,) * 20, "probability"),
            torch.ones(384),
            0.02,
        )


class _PrototypeBank:
    def distances(self, feature):
        return (0.11,) + (0.9,) * 19


class _Dino:
    def score_global_and_local_evidence(self, crops, product_boxes, local_bank, *, repvit_scores):
        return (
            ModelScoreVector("dinov3_vits16_15plus5_v1", tuple(range(1, 21)), tuple(float(index) for index in range(20)), "similarity"),
            {20: 0.8, 6: 0.7, 19: 0.2},
            420,
            0.71,
        )


def test_full_collector_records_runtime_ood_and_local_metadata(tmp_path):
    image_path = tmp_path / "crop.png"
    Image.new("RGB", (40, 30), "white").save(image_path)
    item = EvidenceInput(
        sample_id="development-001",
        capture_group="capture-a",
        image_path=image_path.resolve(),
        box=Box(1, 1, 20, 20),
        registered=True,
        sku_id=6,
        role="development",
        image_sha256="0" * 64,
    )

    row = collect_full_rows(
        (item,), _RepVit(), _PrototypeBank(), _Dino(), object(),
        paddings=(0.05, 0.10, 0.15),
    )[0]

    assert row.nearest_prototype_distance == pytest.approx(0.11)
    assert row.local_product_patch_count == 420
    assert row.candidate_sku_ids == (20, 6, 19)
