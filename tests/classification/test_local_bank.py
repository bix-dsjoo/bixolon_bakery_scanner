import hashlib

import pytest
import torch

from bakery_scanner.classification.local_bank import LocalPatchBank, source_balanced_coreset


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


def test_local_bank_averages_each_query_patch_top_three_reference_matches(tmp_path):
    payload = _payload()
    e0 = torch.zeros(384)
    e0[0] = 1.0
    e1 = torch.zeros(384)
    e1[1] = 1.0
    payload["patches"][6] = torch.stack(
        (
            e0,
            0.8 * e0 + 0.6 * e1,
            0.6 * e0 + 0.8 * e1,
            e1,
        )
    )
    path = tmp_path / "bank.pt"
    torch.save(payload, path)
    bank = LocalPatchBank.load(path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)

    scores = bank.score((6,), torch.stack((e0, e1)), torch.tensor([True, True]))

    assert scores == {6: pytest.approx(0.8)}


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA local matching")
def test_local_bank_moves_requested_reference_patches_to_query_device(tmp_path):
    path = tmp_path / "bank.pt"
    torch.save(_payload(), path)
    bank = LocalPatchBank.load(path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)
    query = torch.nn.functional.normalize(torch.ones((2, 384), device="cuda"), dim=1)

    scores = bank.score((1, 2), query, torch.tensor([True, True], device="cuda"))

    assert set(scores) == {1, 2}


def test_source_balanced_coreset_has_fixed_cap_and_is_deterministic():
    sources = (
        torch.arange(6 * 384, dtype=torch.float32).reshape(6, 384) + 1,
        torch.arange(2 * 384, dtype=torch.float32).reshape(2, 384) + 10_000,
        torch.arange(6 * 384, dtype=torch.float32).reshape(6, 384) + 20_000,
    )

    first, selected = source_balanced_coreset(sources, cap=8)
    second, repeated = source_balanced_coreset(sources, cap=8)

    assert first.shape == (8, 384)
    assert torch.equal(first, second)
    assert selected == repeated == (3, 2, 3)
    assert sum(selected) == 8


def test_local_bank_schema_two_requires_matching_coreset_metadata(tmp_path):
    payload = _payload()
    payload["schema_version"] = 2
    payload["selection"] = {
        "method": "round_robin_evenly_spaced_v1",
        "patch_cap_per_sku": 512,
        "source_image_sha256": {sku_id: ["0" * 64] for sku_id in range(1, 21)},
        "source_patch_counts": {sku_id: [2] for sku_id in range(1, 21)},
        "selected_patch_counts": {sku_id: [2] for sku_id in range(1, 21)},
    }
    path = tmp_path / "bank.pt"
    torch.save(payload, path)

    bank = LocalPatchBank.load(path, dino_weights_sha256="a" * 64, preprocess_sha256="b" * 64)

    assert bank.patches[1].shape == (2, 384)
