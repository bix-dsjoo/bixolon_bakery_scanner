from __future__ import annotations

from pathlib import Path

import pytest
import torch

from tools.train.train_repvit_15plus5_oof import (
    CalibrationCheckpoint,
    EvidenceSource,
    FoldSources,
    balanced_epoch_rows,
    build_repvit_sources,
    configure_repvit_trainable_parameters,
    select_calibration_checkpoint,
)


def _sources() -> FoldSources:
    isolated = tuple(
        EvidenceSource(sku_id, "isolated", f"isolated-{sku_id}-{index}", Path(f"i-{sku_id}-{index}.jpg"), "a" * 64)
        for sku_id in range(1, 21)
        for index in range(2 if sku_id == 1 else 1)
    )
    scenes = (
        EvidenceSource(1, "train_scene", "train-a#000", Path("train-a.jpg"), "b" * 64, scene_id="train-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(2, "train_scene", "train-b#000", Path("train-b.jpg"), "c" * 64, scene_id="train-b", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(1, "calibration_scene", "cal-a#000", Path("cal-a.jpg"), "d" * 64, scene_id="cal-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(1, "evaluation_scene", "eval-a#000", Path("eval-a.jpg"), "e" * 64, scene_id="eval-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
    )
    return FoldSources(
        isolated=isolated,
        scenes=scenes,
        folds={0: {"train": ("train-a", "train-b"), "calibration": ("cal-a",), "evaluation": ("eval-a",)}},
        source_manifest_sha256="f" * 64,
        fold_manifest_sha256={0: "0" * 64},
    )


def test_eval_scene_crop_never_enters_repvit_training() -> None:
    fold_sources = _sources()

    rows = build_repvit_sources(fold_sources, fold_index=0)

    assert not set(rows.scene_ids) & set(fold_sources.evaluation_scene_ids(0))
    assert not set(rows.scene_ids) & set(fold_sources.calibration_scene_ids(0))
    assert set(rows.source_roles) == {"isolated", "train_scene"}


def test_balanced_epoch_equalizes_skus_and_sources_deterministically() -> None:
    rows = build_repvit_sources(_sources(), fold_index=0)

    first = balanced_epoch_rows(rows, seed=20260803)
    second = balanced_epoch_rows(rows, seed=20260803)

    assert [row.identity for row in first] == [row.identity for row in second]
    per_sku = {sku_id: [row for row in first if row.sku_id == sku_id] for sku_id in range(1, 21)}
    assert len({len(values) for values in per_sku.values()}) == 1
    for sku_id in (1, 2):
        roles = [row.source_role for row in per_sku[sku_id]]
        assert roles.count("isolated") == roles.count("train_scene")


def test_repvit_source_manifest_binds_exact_class_order_and_rows() -> None:
    rows = build_repvit_sources(_sources(), fold_index=0)

    payload = rows.manifest_payload()

    assert payload["class_order"] == list(range(1, 21))
    assert payload["class_map"][0] == {"id": 1, "name": "Walnut Donut"}
    assert payload["class_map"][-1] == {"id": 20, "name": "Plain Bread"}
    assert payload["fold_manifest_sha256"] == "0" * 64
    assert payload["source_manifest_sha256"] == "f" * 64
    assert set(payload["source_counts"]) == {str(sku_id) for sku_id in range(1, 21)}
    assert len(payload["rows_sha256"]) == 64


def test_only_final_stage_and_head_are_trainable() -> None:
    class Model(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = torch.nn.Linear(2, 2)
            self.stages = torch.nn.ModuleList((torch.nn.Linear(2, 2), torch.nn.Linear(2, 2)))
            self.head = torch.nn.Linear(2, 20)

    model = Model()

    names = configure_repvit_trainable_parameters(model)

    assert names
    assert all(name.startswith(("stages.1.", "head.")) for name in names)
    assert not any(parameter.requires_grad for parameter in model.stem.parameters())
    assert not any(parameter.requires_grad for parameter in model.stages[0].parameters())
    assert all(parameter.requires_grad for parameter in model.stages[1].parameters())
    assert all(parameter.requires_grad for parameter in model.head.parameters())


def test_checkpoint_selection_uses_only_calibration_role(tmp_path: Path) -> None:
    candidates = (
        CalibrationCheckpoint(1, tmp_path / "epoch-1.pt", "calibration", 0.4),
        CalibrationCheckpoint(2, tmp_path / "epoch-2.pt", "calibration", 0.2),
    )

    assert select_calibration_checkpoint(candidates).epoch == 2

    with pytest.raises(ValueError, match="only calibration"):
        select_calibration_checkpoint((CalibrationCheckpoint(1, tmp_path / "bad.pt", "evaluation", 0.1),))
