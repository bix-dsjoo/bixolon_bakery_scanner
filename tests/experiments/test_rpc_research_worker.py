"""Focused contracts for the external-only RPC oracle feature worker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from bakery_scanner.experiments.rpc_manifest import (
    RpcDatasetContract,
    RpcImage,
    RpcIndex,
    RpcObject,
)
from bakery_scanner.experiments.rpc_research_worker import (
    OracleFeatureRow,
    ResearchArtifacts,
    extract_oracle_features,
)


def test_research_artifacts_reject_wrong_dino_digest(tmp_path: Path):
    """Changing the DINO file must prevent its features from being materialized."""
    with pytest.raises(ValueError, match="DINOv3 SHA-256 mismatch"):
        ResearchArtifacts.from_paths(tmp_path / "repvit.safetensors", tmp_path / "dino.pth")


def test_oracle_feature_row_is_bound_to_source_and_box():
    """An annotation ID distinguishes separate oracle boxes in one source image."""
    row = OracleFeatureRow("val2019:7:item.jpg", 11, 7, (1.0, 2.0, 3.0, 4.0), "E")

    assert row.identity == "val2019:7:item.jpg:11"


class _RepVitFeatureFixture(torch.nn.Module):
    def forward_features(self, batch: torch.Tensor) -> torch.Tensor:
        values = torch.arange(1, 385, dtype=torch.float32, device=batch.device)
        return values.reshape(1, 384, 1, 1).expand(batch.shape[0], -1, -1, -1)


class _DinoFeatureFixture(torch.nn.Module):
    def forward_features(self, batch: torch.Tensor) -> dict[str, torch.Tensor]:
        global_values = torch.arange(384, 0, -1, dtype=torch.float32, device=batch.device)
        patch_values = torch.arange(1, 385, dtype=torch.float32, device=batch.device)
        return {
            "x_norm_clstoken": global_values.reshape(1, 384).expand(batch.shape[0], -1),
            "x_norm_patchtokens": patch_values.reshape(1, 1, 384).expand(batch.shape[0], 196, -1),
        }


def _one_image_index(tmp_path: Path) -> RpcIndex:
    source = tmp_path / "item.jpg"
    Image.new("RGB", (12, 9), (20, 30, 40)).save(source)
    source_bytes = source.read_bytes()
    contract = RpcDatasetContract(
        annotation_sha256={split: hashlib.sha256(split.encode()).hexdigest() for split in ("train2019", "val2019", "test2019")},
        image_counts={split: 1 for split in ("train2019", "val2019", "test2019")},
    )
    image = RpcImage(
        split="val2019",
        image_id=7,
        source_identity="val2019:7:item.jpg",
        source_path=source,
        byte_size=len(source_bytes),
        sha256=hashlib.sha256(source_bytes).hexdigest(),
        level="easy",
    )
    return RpcIndex(contract, (image,), (RpcObject("val2019", 11, 7, 7, (1.0, 2.0, 3.0, 4.0)),))


def test_extract_oracle_features_records_two_globals_and_196_patches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Removing a global branch or any patch row leaves an incomplete research cache."""
    import bakery_scanner.experiments.rpc_research_worker as worker

    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: (_RepVitFeatureFixture(), _DinoFeatureFixture()))
    artifacts = ResearchArtifacts(Path("repvit.safetensors"), Path("dino.pth"), "r" * 64, "d" * 64)
    output = tmp_path / "features"

    manifest_path = extract_oracle_features(_one_image_index(tmp_path), artifacts, output)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows"] == [{
        "annotation_id": 11,
        "bbox_xywh": [1.0, 2.0, 3.0, 4.0],
        "category_id": 7,
        "difficulty": "E",
        "identity": "val2019:7:item.jpg:11",
        "source_identity": "val2019:7:item.jpg",
    }]
    repvit = np.load(output / "repvit_global.float16.npy")
    dino = np.load(output / "dinov3_global.float16.npy")
    patches = np.load(output / "dinov3_patches.float16.npy")
    assert repvit.dtype == dino.dtype == patches.dtype == np.float16
    assert repvit.shape == dino.shape == (1, 384)
    assert patches.shape == (1, 196, 384)
    assert np.linalg.norm(repvit.astype(np.float32), axis=1) == pytest.approx([1.0], abs=2e-3)
    assert np.linalg.norm(dino.astype(np.float32), axis=1) == pytest.approx([1.0], abs=2e-3)
    with pytest.raises(FileExistsError):
        extract_oracle_features(_one_image_index(tmp_path), artifacts, output)
