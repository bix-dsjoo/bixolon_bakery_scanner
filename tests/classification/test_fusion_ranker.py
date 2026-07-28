from __future__ import annotations

import pytest

from bakery_scanner.classification.full_evidence import FullEvidenceRow
from bakery_scanner.classification.fusion_ranker import fit_oof_ranker, fit_ranker


def _row(sample_id: str, capture_group: str, sku_id: int) -> FullEvidenceRow:
    other = 2 if sku_id == 1 else 1
    repvit = [0.01] * 20
    repvit[sku_id - 1] = 0.70
    repvit[other - 1] = 0.20
    dino = [0.0] * 20
    dino[sku_id - 1] = 0.80
    dino[other - 1] = 0.50
    return FullEvidenceRow(
        sample_id=sample_id,
        capture_group=capture_group,
        registered=True,
        sku_id=sku_id,
        role="development",
        image_sha256=f"{int(sample_id[-1]):064x}",
        repvit_values=tuple(repvit),
        dinov3_values=tuple(dino),
        candidate_sku_ids=(sku_id, other),
        local_values=(0.90, 0.20),
        repvit_crop_disagreement=0.02,
        nearest_prototype_distance=0.10,
        local_product_patch_count=420,
        local_product_patch_ratio=0.71,
        repvit_checkpoint_sha256="1" * 64,
        repvit_manifest_sha256="2" * 64,
        repvit_prototype_sha256="3" * 64,
        dinov3_weights_sha256="4" * 64,
        dinov3_support_sha256="5" * 64,
        dinov3_local_bank_sha256="6" * 64,
        preprocess_sha256="7" * 64,
    )


def test_oof_ranker_excludes_held_out_capture_groups_from_each_fold():
    rows = (
        _row("sample-1", "capture-a", 1),
        _row("sample-2", "capture-b", 1),
        _row("sample-3", "capture-c", 2),
        _row("sample-4", "capture-d", 2),
    )

    result = fit_oof_ranker(rows, folds=2, seed=7)

    assert len(result.ranked_rows) == len(rows)
    assert all(
        fold.training_capture_groups.isdisjoint(fold.held_out_capture_groups)
        for fold in result.folds
    )


def test_ranker_places_the_candidate_with_shared_evidence_first():
    rows = (
        _row("sample-1", "capture-a", 1),
        _row("sample-2", "capture-b", 1),
        _row("sample-3", "capture-c", 2),
        _row("sample-4", "capture-d", 2),
    )

    ranker = fit_ranker(rows, seed=7)

    assert ranker.rank(_row("sample-5", "capture-e", 2)).sku_ids[0] == 2
