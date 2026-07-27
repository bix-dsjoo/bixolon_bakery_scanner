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


def source_balanced_coreset(
    source_patches: Sequence[torch.Tensor],
    *,
    cap: int,
) -> tuple[torch.Tensor, tuple[int, ...]]:
    """Select a deterministic, near-equal patch quota for every source image."""
    if type(cap) is not int or not 1 <= cap <= 1024:
        raise ValueError("local patch cap must be an integer between 1 and 1024")
    sources = tuple(source_patches)
    if not sources:
        raise ValueError("local coreset requires at least one source")
    for patches in sources:
        if not isinstance(patches, torch.Tensor) or patches.ndim != 2 or patches.shape[0] == 0 or patches.shape[1] != _DIMENSION:
            raise ValueError("local coreset source patches must have shape (N, 384)")
        if not torch.isfinite(patches).all().item():
            raise ValueError("local coreset source patches must be finite")

    total = sum(patches.shape[0] for patches in sources)
    target = min(cap, total)
    selected = [0] * len(sources)
    # Round-robin allocation prevents a capture with many images/patches from
    # dominating a SKU.  Source order is the canonical sorted source order.
    while sum(selected) < target:
        progressed = False
        for index, patches in enumerate(sources):
            if selected[index] < patches.shape[0] and sum(selected) < target:
                selected[index] += 1
                progressed = True
        if not progressed:
            raise RuntimeError("local coreset allocation stalled")

    coreset = torch.cat(
        tuple(
            patches.index_select(
                0,
                torch.linspace(0, patches.shape[0] - 1, steps=count)
                .round()
                .to(dtype=torch.long),
            )
            for patches, count in zip(sources, selected, strict=True)
            if count
        )
    ).contiguous()
    return coreset, tuple(selected)


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
        schema_version = payload.get("schema_version")
        if schema_version not in (1, 2):
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
        if schema_version == 2:
            _validate_coreset_selection(payload.get("selection"), patches)
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
            sku_id: _trimmed_topk_similarity(selected, self.patches[sku_id])
            for sku_id in candidates
        }


def _trimmed_topk_similarity(
    query_patches: torch.Tensor,
    reference_patches: torch.Tensor,
) -> float:
    """Average each query patch's top three references, then trim query outliers."""
    # Keep the complete bank on CPU and transfer only the currently selected
    # SKU reference set.  Query patches come directly from the DINO GPU
    # forward pass, so matrix multiplication otherwise crosses devices.
    reference_patches = reference_patches.to(query_patches.device, non_blocking=True)
    similarities = query_patches @ reference_patches.T
    top_count = min(3, reference_patches.shape[0])
    per_query = similarities.topk(top_count, dim=1).values.mean(dim=1)
    trim_count = int(per_query.shape[0] * 0.10)
    if trim_count and 2 * trim_count < per_query.shape[0]:
        per_query = per_query.sort().values[trim_count:-trim_count]
    return float(per_query.mean().item())


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


def _validate_coreset_selection(selection: object, patches: Mapping[int, torch.Tensor]) -> None:
    if not isinstance(selection, dict) or set(selection) != {
        "method",
        "patch_cap_per_sku",
        "source_image_sha256",
        "source_patch_counts",
        "selected_patch_counts",
    }:
        raise ValueError("local patch bank coreset selection is invalid")
    cap = selection["patch_cap_per_sku"]
    if type(cap) is not int or not 512 <= cap <= 1024:
        raise ValueError("local patch bank coreset cap is invalid")
    if selection["method"] != "round_robin_evenly_spaced_v1":
        raise ValueError("local patch bank coreset method is invalid")
    source_hashes = selection["source_image_sha256"]
    source_counts = selection["source_patch_counts"]
    selected_counts = selection["selected_patch_counts"]
    if not all(isinstance(value, dict) and tuple(sorted(value)) == _SKU_IDS for value in (source_hashes, source_counts, selected_counts)):
        raise ValueError("local patch bank coreset SKU membership is invalid")
    for sku_id in _SKU_IDS:
        hashes = source_hashes[sku_id]
        available = source_counts[sku_id]
        selected = selected_counts[sku_id]
        if (
            not isinstance(hashes, list)
            or not isinstance(available, list)
            or not isinstance(selected, list)
            or not (len(hashes) == len(available) == len(selected))
            or not hashes
            or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in hashes)
            or any(type(value) is not int or value <= 0 for value in available)
            or any(type(value) is not int or value < 0 for value in selected)
            or any(chosen > total for chosen, total in zip(selected, available, strict=True))
        ):
            raise ValueError("local patch bank coreset source metadata is invalid")
        if sum(selected) != min(cap, sum(available)) or patches[sku_id].shape[0] != sum(selected):
            raise ValueError("local patch bank coreset size is invalid")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
