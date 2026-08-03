from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import torch

from tools.train.build_dinov3_15plus5_oof import (
    SupportContribution,
    aggregate_support,
    build_dino_sources,
    extract_global_local_tokens,
    support_metadata,
)
from tools.train.train_repvit_15plus5_oof import EvidenceSource, FoldSources


def _sources() -> FoldSources:
    isolated = tuple(
        EvidenceSource(sku_id, "isolated", f"isolated-{sku_id}", None, "a" * 64)
        for sku_id in range(1, 21)
    )
    scenes = (
        EvidenceSource(1, "train_scene", "train-a#000", None, "b" * 64, scene_id="train-a", box_xywh=(0.0, 0.0, 4.0, 4.0)),
        EvidenceSource(1, "calibration_scene", "cal-a#000", None, "c" * 64, scene_id="cal-a", box_xywh=(0.0, 0.0, 4.0, 4.0)),
        EvidenceSource(1, "evaluation_scene", "eval-a#000", None, "d" * 64, scene_id="eval-a", box_xywh=(0.0, 0.0, 4.0, 4.0)),
    )
    return FoldSources(
        isolated=isolated,
        scenes=scenes,
        folds={0: {"train": ("train-a",), "calibration": ("cal-a",), "evaluation": ("eval-a",)}},
        source_manifest_sha256="e" * 64,
        fold_manifest_sha256={0: "f" * 64},
    )


def test_support_bank_uses_only_isolated_and_training_scene_crops() -> None:
    rows = build_dino_sources(_sources(), fold_index=0)

    assert set(rows.source_roles) <= {"isolated", "train_scene"}
    assert set(rows.scene_ids) == {"train-a"}


def test_support_caps_are_applied_per_sku_and_source_before_aggregation() -> None:
    contributions = []
    for source_role, offset in (("isolated", 0.0), ("train_scene", 10.0)):
        for index in range(3):
            global_token = torch.zeros(384)
            global_token[0] = 1.0 + offset + index
            patches = torch.zeros((3, 384))
            patches[:, 0] = torch.tensor((1.0 + offset, 2.0 + offset, 3.0 + offset))
            contributions.append(SupportContribution(1, source_role, f"{source_role}-{index}", global_token, patches))

    support = aggregate_support(
        tuple(contributions),
        global_contributors_per_sku_source=2,
        local_patches_per_sku_source=4,
    )

    assert support.source_counts[1] == {"isolated": 2, "train_scene": 2}
    assert support.patch_counts[1] == {"isolated": 4, "train_scene": 4}
    assert tuple(support.global_prototypes.shape) == (20, 384)
    assert tuple(support.local_patches[1].shape) == (8, 384)


def test_support_aggregation_is_identity_order_deterministic() -> None:
    rows = tuple(
        SupportContribution(1, "isolated", identity, torch.ones(384) * value, torch.ones((1, 384)) * value)
        for identity, value in (("b", 2.0), ("a", 1.0))
    )

    first = aggregate_support(rows, global_contributors_per_sku_source=1, local_patches_per_sku_source=1)
    second = aggregate_support(tuple(reversed(rows)), global_contributors_per_sku_source=1, local_patches_per_sku_source=1)

    assert torch.equal(first.global_prototypes, second.global_prototypes)
    assert torch.equal(first.local_patches[1], second.local_patches[1])


def test_one_dino_forward_produces_global_and_local_tokens() -> None:
    class Encoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def forward_features(self, batch: torch.Tensor):
            self.calls += 1
            return {
                "x_norm_clstoken": torch.ones((len(batch), 384)),
                "x_norm_patchtokens": torch.ones((len(batch), 196, 384)),
            }

    encoder = Encoder()

    global_tokens, local_tokens = extract_global_local_tokens(
        encoder, torch.ones((2, 3, 224, 224))
    )

    assert encoder.calls == 1
    assert tuple(global_tokens.shape) == (2, 384)
    assert tuple(local_tokens.shape) == (2, 196, 384)


def test_direct_cli_execution_writes_explicit_unverified_receipt(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "support"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")

    completed = subprocess.run(
        (
            sys.executable,
            str(root / "tools" / "train" / "build_dinov3_15plus5_oof.py"),
            "--splits", str(root / "data" / "splits" / "rtx5080_15plus5_oof_v1"),
            "--fold", "0",
            "--output", str(output),
        ),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2, completed.stderr
    receipt = json.loads((output / "fold-0" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "unverified_missing_dinov3_support_inputs"
    assert "no automatic download" in receipt["detail"]


def test_support_metadata_binds_weights_preprocess_fold_sources_runtime_and_tensors() -> None:
    rows = build_dino_sources(_sources(), fold_index=0)
    support = aggregate_support(
        (SupportContribution(1, "isolated", "a", torch.ones(384), torch.ones((2, 384))),),
        global_contributors_per_sku_source=1,
        local_patches_per_sku_source=2,
    )

    metadata = support_metadata(
        support,
        rows=rows,
        weights_sha256="1" * 64,
        preprocessing_sha256="2" * 64,
        runtime_identity={"python": "provisioned"},
    )

    assert metadata["weights_sha256"] == "1" * 64
    assert metadata["preprocessing_sha256"] == "2" * 64
    assert metadata["fold_manifest_sha256"] == "f" * 64
    assert metadata["source_manifest_sha256"] == "e" * 64
    assert metadata["class_order"] == list(range(1, 21))
    assert metadata["class_map"][5] == {"id": 6, "name": "Croissant"}
    assert metadata["global_tensor"] == {"shape": [20, 384], "dtype": "float32"}
    assert metadata["local_tensors"]["1"] == {"shape": [2, 384], "dtype": "float32"}
    assert len(metadata["runtime_identity_sha256"]) == 64
