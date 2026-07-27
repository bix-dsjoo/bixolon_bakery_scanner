import hashlib

import pytest
import torch

from bakery_scanner.classification.local_bank import LocalPatchBank


def _payload(*, weights_sha256: str = "a" * 64):
    patches = {
        sku_id: torch.nn.functional.normalize(torch.ones((2, 384)) * sku_id, dim=1)
        for sku_id in range(1, 21)
    }
    return {
        "artifact_type": "dinov3_vits16_15plus5_local_patch_bank",
        "schema_version": 1,
        "dino_weights_sha256": weights_sha256,
        "preprocess_sha256": "b" * 64,
        "canonical_frame_version": "exif_visual_rgb_v1",
        "patches": patches,
    }


def test_local_bank_rejects_mismatched_dino_hash_and_scores_masked_tokens(tmp_path):
    path = tmp_path / "bank.pt"
    torch.save(_payload(), path)

    with pytest.raises(ValueError, match="DINO weights"):
        LocalPatchBank.load(path, dino_weights_sha256="0" * 64, preprocess_sha256="b" * 64)

    bank = LocalPatchBank.load(path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)
    token = torch.nn.functional.normalize(torch.ones((1, 384)) * 6, dim=1)
    scores = bank.score((6,), token, torch.tensor([True]))

    assert scores == {6: pytest.approx(1.0)}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == bank.sha256
