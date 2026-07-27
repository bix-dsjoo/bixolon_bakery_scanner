from __future__ import annotations

import pytest
import numpy as np

from bakery_scanner.classification.evidence import (
    EvidenceRow,
    evaluate_policy,
    grouped_development_splits,
    select_policy,
    _lossless_thresholds,
)


def _scores(top: int, probability: float) -> tuple[float, ...]:
    rest = (1.0 - probability) / 19.0
    return tuple(probability if sku_id == top else rest for sku_id in range(1, 21))


def _similarities(top: int, high: float = 4.0) -> tuple[float, ...]:
    return tuple(high if sku_id == top else 0.0 for sku_id in range(1, 21))


def _probabilities(values: dict[int, float]) -> tuple[float, ...]:
    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values))
    return tuple(values.get(sku_id, fill) for sku_id in range(1, 21))


def _row(
    index: int,
    group: str,
    sku_id: int | None,
    *,
    repvit_top: int | None = None,
    dino_top: int | None = None,
) -> EvidenceRow:
    registered = sku_id is not None
    repvit_top = repvit_top or sku_id or 1
    dino_top = dino_top or sku_id or 1
    return EvidenceRow(
        sample_id=f"sample-{index:03d}",
        capture_group=group,
        registered=registered,
        sku_id=sku_id,
        role="development",
        image_sha256=f"{index:064x}",
        repvit_values=_scores(repvit_top, 0.8),
        dinov3_values=_similarities(dino_top),
        repvit_artifact_id="repvit_m1_15plus5_v1",
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
    )


def _grouped_rows() -> tuple[EvidenceRow, ...]:
    rows: list[EvidenceRow] = []
    index = 1
    for group_index in range(5):
        group = f"capture-{group_index}"
        for sku_id in (1, 2):
            rows.append(_row(index, group, sku_id))
            index += 1
        rows.append(_row(index, group, None, repvit_top=3, dino_top=3))
        index += 1
    return tuple(rows)


def _mixed_release_rows() -> tuple[EvidenceRow, ...]:
    rows: list[EvidenceRow] = []
    index = 1
    for group_index in range(5):
        group = f"capture-{group_index}"
        rows.append(
            EvidenceRow(
                sample_id=f"mixed-{index:03d}",
                capture_group=group,
                registered=True,
                sku_id=1,
                role="development",
                image_sha256=f"{index + 100:064x}",
                repvit_values=_probabilities({1: 0.60, 2: 0.30}),
                dinov3_values=_similarities(1),
                repvit_artifact_id="repvit_m1_15plus5_v1",
                dinov3_artifact_id="dinov3_vits16_15plus5_v1",
            )
        )
        index += 1
        dino = list(_similarities(4))
        dino[1] = 3.0
        rows.append(
            EvidenceRow(
                sample_id=f"mixed-{index:03d}",
                capture_group=group,
                registered=True,
                sku_id=2,
                role="development",
                image_sha256=f"{index + 100:064x}",
                repvit_values=_probabilities({3: 0.55, 2: 0.10}),
                dinov3_values=tuple(dino),
                repvit_artifact_id="repvit_m1_15plus5_v1",
                dinov3_artifact_id="dinov3_vits16_15plus5_v1",
            )
        )
        index += 1
    return tuple(rows)


def test_grouped_folds_never_expose_held_out_group_to_selection():
    rows = _grouped_rows()

    splits = grouped_development_splits(rows, folds=5, seed=20260727)

    assert len(splits) == 5
    for training_indices, held_out_indices in splits:
        training_groups = {rows[index].capture_group for index in training_indices}
        held_out_groups = {rows[index].capture_group for index in held_out_indices}
        assert training_groups.isdisjoint(held_out_groups)
        assert len(held_out_groups) == 1
        assert len(training_groups) == 4


def test_policy_selection_is_deterministic_and_bound_to_evidence():
    rows = _mixed_release_rows()

    first = select_policy(rows, folds=5, seed=20260727)
    second = select_policy(rows, folds=5, seed=20260727)

    assert first == second
    assert first.evidence_sha256 == second.evidence_sha256
    assert first.repvit_temperature in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
    assert 0.0 <= first.alpha <= 1.0
    metrics = evaluate_policy(rows, first)
    assert metrics.auto_errors == 0
    assert metrics.fallback_top3_misses == 0
    assert metrics.assisted_failures == 0


def test_selection_rejects_locked_acceptance_rows():
    row = _row(1, "locked-group", 1)
    locked = EvidenceRow(
        sample_id=row.sample_id,
        capture_group=row.capture_group,
        registered=row.registered,
        sku_id=row.sku_id,
        role="locked_acceptance",
        image_sha256=row.image_sha256,
        repvit_values=row.repvit_values,
        dinov3_values=row.dinov3_values,
        repvit_artifact_id=row.repvit_artifact_id,
        dinov3_artifact_id=row.dinov3_artifact_id,
    )

    with pytest.raises(ValueError, match="development"):
        select_policy((locked,), folds=2)


def test_selection_rejects_all_unknown_cross_fit_with_undefined_auto_precision():
    rows = list(_grouped_rows())

    with pytest.raises(ValueError, match="undefined applicable release metrics"):
        select_policy(tuple(rows), folds=5, seed=20260727)


def test_cross_fit_rejects_thresholds_that_fail_only_in_held_out_group():
    rows = list(_mixed_release_rows())
    for index, row in enumerate(rows):
        if row.capture_group != "capture-0" or row.sku_id != 1:
            continue
        rows[index] = EvidenceRow(
            sample_id=row.sample_id,
            capture_group=row.capture_group,
            registered=True,
            sku_id=1,
            role="development",
            image_sha256=row.image_sha256,
            repvit_values=_probabilities({2: 0.60, 1: 0.30}),
            dinov3_values=_similarities(2),
            repvit_artifact_id=row.repvit_artifact_id,
            dinov3_artifact_id=row.dinov3_artifact_id,
        )

    with pytest.raises(ValueError, match="cross-fit development gates failed"):
        select_policy(tuple(rows), folds=5, seed=20260727)


def test_lossless_threshold_candidates_keep_intermediate_safe_acceptance_mask():
    first = np.array([0.20, 0.60, 0.90])
    second = np.array([0.90, 0.60, 0.20])

    candidates = _lossless_thresholds(first, second)

    assert (0.60, 0.60) in candidates
