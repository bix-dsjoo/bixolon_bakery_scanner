"""Focused contracts for the external-only RPC oracle feature worker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

import bakery_scanner.experiments.rpc_research_worker as worker
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


def _fixture_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ResearchArtifacts:
    repvit = tmp_path / "repvit.safetensors"
    dino = tmp_path / "dino.pth"
    repvit.write_bytes(b"repvit-fixture")
    dino.write_bytes(b"dino-fixture")
    monkeypatch.setattr(worker, "_REPVIT_SHA256", hashlib.sha256(repvit.read_bytes()).hexdigest())
    monkeypatch.setattr(worker, "_DINO_SHA256", hashlib.sha256(dino.read_bytes()).hexdigest())
    return ResearchArtifacts.from_paths(repvit, dino)


def test_extract_oracle_features_records_two_globals_and_196_patches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Removing a global branch or any patch row leaves an incomplete research cache."""
    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: (_RepVitFeatureFixture(), _DinoFeatureFixture()))
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    output = tmp_path / "features"

    manifest_path = extract_oracle_features(
        _one_image_index(tmp_path), artifacts, output, allowed_output_root=tmp_path
    )

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
    assert manifest["execution"] == {
        "determinism": "cpu-float32-inference-mode-model-eval-v1",
        "device": "cpu",
    }
    assert manifest["preprocessing"]["input_size"] == [224, 224]
    assert len(manifest["code_sha256"]) == 64
    assert manifest["runtime"]["torch"] == torch.__version__
    with pytest.raises(FileExistsError):
        extract_oracle_features(
            _one_image_index(tmp_path), artifacts, output, allowed_output_root=tmp_path
        )


def test_extract_revalidates_artifacts_before_loading_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A checkpoint replaced after construction must fail before any encoder loads."""
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    artifacts.repvit_path.write_bytes(b"substituted")
    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: pytest.fail("loaded stale model"))

    with pytest.raises(ValueError, match="RepViT SHA-256 mismatch"):
        extract_oracle_features(
            _one_image_index(tmp_path), artifacts, tmp_path / "features", allowed_output_root=tmp_path
        )


def test_canonical_oracle_crop_transforms_orientation_six_bbox(tmp_path: Path):
    """A raw top-left COCO box becomes the top-right pixel after EXIF rotation 6."""
    source = tmp_path / "oriented.png"
    raw = Image.new("RGB", (3, 2))
    raw.putdata([
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (0, 255, 255), (255, 0, 255), (255, 255, 0),
    ])
    exif = Image.Exif()
    exif[274] = 6
    raw.save(source, exif=exif)
    content = source.read_bytes()
    image = RpcImage(
        split="val2019", image_id=7, source_identity="val2019:7:oriented.png",
        source_path=source, byte_size=len(content), sha256=hashlib.sha256(content).hexdigest(), level="easy",
    )

    crop = worker._canonical_oracle_crop(image, (0.0, 0.0, 1.0, 1.0))

    assert crop.size == (1, 1)
    assert crop.getpixel((0, 0)) == (255, 0, 0)


def test_extract_rejects_output_outside_research_runs_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """The producer itself prevents a caller from writing generated payloads into Git."""
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="output must be under"):
        extract_oracle_features(
            _one_image_index(tmp_path), artifacts, tmp_path / "outside", allowed_output_root=tmp_path / "allowed"
        )
