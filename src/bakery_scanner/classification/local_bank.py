"""Versioned DINOv3 local-product patch support banks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import torch
import torch.nn.functional as functional


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SKU_IDS = tuple(range(1, 21))
_DIMENSION = 384


@dataclass(frozen=True, slots=True)
class LocalPatchBank:
    """Normalized per-SKU patch embeddings bound to model preprocessing."""

    patches: Mapping[int, torch.Tensor]
    sha256: str

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        dino_weights_sha256: str,
        preprocess_sha256: str,
    ) -> "LocalPatchBank":
        payload_path = Path(path)
        if not payload_path.is_file():
            raise ValueError(f"local patch bank is missing: {payload_path}")
        sha256 = _file_sha256(payload_path)
        payload = torch.load(payload_path, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            raise ValueError("local patch bank must be a mapping")
        if payload.get("artifact_type") != "dinov3_vits16_15plus5_local_patch_bank":
            raise ValueError("local patch bank artifact_type is invalid")
        if payload.get("schema_version") != 1:
            raise ValueError("local patch bank schema_version is invalid")
        if payload.get("dino_weights_sha256") != dino_weights_sha256:
            raise ValueError("local patch bank DINO weights SHA-256 mismatch")
        if payload.get("preprocess_sha256") != preprocess_sha256:
            raise ValueError("local patch bank preprocess SHA-256 mismatch")
        if payload.get("canonical_frame_version") != "exif_visual_rgb_v1":
            raise ValueError("local patch bank canonical frame is invalid")
        patches = payload.get("patches")
        if not isinstance(patches, dict) or tuple(sorted(patches)) != _SKU_IDS:
            raise ValueError("local patch bank must contain every canonical SKU")
        validated = {sku_id: _validate_patches(value, sku_id) for sku_id, value in patches.items()}
        return cls(validated, sha256)

    def score(
        self,
        candidate_sku_ids: Sequence[int],
        patch_tokens: torch.Tensor,
        patch_mask: torch.Tensor,
    ) -> dict[int, float]:
        candidates = tuple(candidate_sku_ids)
        if not candidates or len(set(candidates)) != len(candidates) or any(sku not in _SKU_IDS for sku in candidates):
            raise ValueError("local candidates must be unique canonical SKU IDs")
        if patch_tokens.ndim != 2 or patch_tokens.shape[1] != _DIMENSION:
            raise ValueError("local patch tokens must have shape (N, 384)")
        if patch_mask.dtype is not torch.bool or tuple(patch_mask.shape) != (patch_tokens.shape[0],):
            raise ValueError("local patch mask must be boolean and match tokens")
        selected = patch_tokens[patch_mask]
        if selected.shape[0] == 0 or not torch.isfinite(selected).all().item():
            raise ValueError("local patch tokens must contain finite product patches")
        selected = functional.normalize(selected.float(), dim=1)
        return {
            sku_id: float((selected @ self.patches[sku_id].T).max(dim=1).values.mean().item())
            for sku_id in candidates
        }


def _validate_patches(value: object, sku_id: int) -> torch.Tensor:
    if not isinstance(value, torch.Tensor) or value.ndim != 2 or value.shape[0] == 0 or value.shape[1] != _DIMENSION:
        raise ValueError(f"local patch bank SKU {sku_id} patches are invalid")
    value = value.float().contiguous()
    if not torch.isfinite(value).all().item() or (value.norm(dim=1) == 0).any().item():
        raise ValueError(f"local patch bank SKU {sku_id} patches must be finite non-zero")
    normalized = functional.normalize(value, dim=1)
    if not torch.allclose(value, normalized, rtol=1e-5, atol=1e-5):
        raise ValueError(f"local patch bank SKU {sku_id} patches must be normalized")
    return normalized


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
