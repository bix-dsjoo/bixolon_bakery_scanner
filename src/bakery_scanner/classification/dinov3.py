"""Strict DINOv3 ViT-S/16 artifact loading and prototype scoring."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import torch
import torch.nn.functional as functional
from dinov3.models.vision_transformer import vit_small
from PIL import Image
from torchvision import transforms

from bakery_scanner.contracts import Box

from .config import ClassifierConfig
from .contracts import ModelScoreVector
from .errors import DinoInferenceError
from .local_bank import LocalPatchBank
from .preprocess import ClassifierPreprocessDescriptor, build_transform

_SKU_IDS = tuple(range(1, 21))
_EMBEDDING_DIMENSION = 384
_PROTOTYPE_SHAPE = (20, _EMBEDDING_DIMENSION)
_SUPPORT_ARTIFACT_TYPE = "dinov3_vits16_15plus5_global_support"
_ARCHITECTURE = "vit_small_patch16_dinov3_storage4"
_STORAGE_TOKEN_SHAPE = [1, 4, _EMBEDDING_DIMENSION]


@dataclass(frozen=True, slots=True)
class DinoGlobalLocalEvidence:
    global_scores: ModelScoreVector
    local_scores: dict[int, float]
    product_patch_count: int
    product_patch_ratio: float


def candidate_union(
    dino_global: ModelScoreVector,
    repvit: ModelScoreVector,
) -> tuple[int, ...]:
    """Return DINO global Top-5 plus missing RepViT Top-2 candidates."""
    if (
        dino_global.model_id != "dinov3_vits16_15plus5_v1"
        or dino_global.score_kind != "similarity"
        or dino_global.sku_ids != _SKU_IDS
    ):
        raise ValueError("DINO global scores must use the canonical similarity contract")
    if (
        repvit.model_id != "repvit_m1_15plus5_v1"
        or repvit.score_kind != "probability"
        or repvit.sku_ids != _SKU_IDS
    ):
        raise ValueError("RepViT scores must use the canonical probability contract")
    dino_ranked = sorted(
        range(len(_SKU_IDS)),
        key=lambda index: (-dino_global.values[index], _SKU_IDS[index]),
    )[:5]
    repvit_ranked = sorted(
        range(len(_SKU_IDS)),
        key=lambda index: (-repvit.values[index], _SKU_IDS[index]),
    )[:2]
    candidates = [_SKU_IDS[index] for index in dino_ranked]
    candidates.extend(
        _SKU_IDS[index] for index in repvit_ranked if _SKU_IDS[index] not in candidates
    )
    return tuple(candidates)


class DinoV3Rechecker:
    def __init__(
        self,
        encoder: torch.nn.Module,
        prototypes: torch.Tensor,
        sku_ids: tuple[int, ...],
        transform: Callable[[Image.Image], torch.Tensor],
        model_id: str,
        device: torch.device,
    ) -> None:
        if sku_ids != _SKU_IDS:
            raise ValueError("DINOv3 SKU IDs must be 1 through 20 in canonical order")
        _validate_prototypes(prototypes)
        self.encoder = encoder
        self.prototypes = prototypes.detach().to(device)
        self.sku_ids = sku_ids
        self.transform = transform
        self.model_id = model_id
        self.device = device

    @classmethod
    def validate_artifacts(
        cls,
        config: ClassifierConfig,
        *,
        expected_preprocess_sha256: str,
    ) -> None:
        """Admit static DINO evidence without constructing the conditional model."""
        _load_validated_artifacts(
            config,
            expected_preprocess_sha256=expected_preprocess_sha256,
        )

    @classmethod
    def load(
        cls,
        config: ClassifierConfig,
        *,
        device: torch.device | None = None,
        expected_preprocess_sha256: str | None = None,
    ) -> "DinoV3Rechecker":
        weights, prototypes, transform = _load_validated_artifacts(
            config,
            expected_preprocess_sha256=expected_preprocess_sha256,
        )

        dinov3 = config.dinov3
        target_device = device or torch.device(config.runtime.device.lower())
        model = vit_small(
            patch_size=16,
            n_storage_tokens=4,
            mask_k_bias=True,
            layerscale_init=1e-5,
        )
        if not isinstance(weights, Mapping):
            raise ValueError("DINOv3 weights must be a state dictionary")
        model.load_state_dict(weights, strict=True)
        model.to(target_device).eval()
        return cls(
            model,
            prototypes,
            _SKU_IDS,
            transform,
            dinov3.artifact_id,
            target_device,
        )
    def score(self, crops: Sequence[Image.Image]) -> ModelScoreVector:
        if len(crops) != 3:
            raise ValueError("DINOv3 requires exactly three crops")
        try:
            batch = torch.stack(
                tuple(self.transform(crop.convert("RGB")) for crop in crops)
            )
            with torch.inference_mode():
                embeddings = self.encoder(batch.to(self.device))
                if not isinstance(embeddings, torch.Tensor) or embeddings.shape != (
                    3,
                    _EMBEDDING_DIMENSION,
                ):
                    raise ValueError("DINOv3 embeddings must have shape (3, 384)")
                if not torch.isfinite(embeddings).all().item():
                    raise ValueError("DINOv3 embeddings must be finite")
                if (embeddings.norm(dim=1) == 0).any().item():
                    raise ValueError(
                        "DINOv3 embeddings must have non-zero length"
                    )
                embeddings = functional.normalize(embeddings, dim=1)
                mean_embedding = embeddings.mean(dim=0)
                if mean_embedding.norm().item() == 0:
                    raise ValueError(
                        "DINOv3 mean embedding must have non-zero length"
                    )
                mean_embedding = functional.normalize(mean_embedding, dim=0)
                similarities = self.prototypes @ mean_embedding
                if not torch.isfinite(similarities).all().item():
                    raise ValueError("DINOv3 similarities must be finite")
        except torch.OutOfMemoryError as exc:
            raise DinoInferenceError(
                "dino_out_of_memory",
                "DINOv3 inference exhausted device memory",
            ) from exc
        values = tuple(float(value) for value in similarities.detach().cpu().tolist())
        return ModelScoreVector(self.model_id, self.sku_ids, values, "similarity")

    def score_global_and_local(
        self,
        crops: Sequence[Image.Image],
        product_boxes_in_crops: Sequence[Box],
        local_bank: LocalPatchBank,
        *,
        repvit_scores: ModelScoreVector | None = None,
    ) -> tuple[ModelScoreVector, dict[int, float]]:
        global_scores, local_scores, _, _ = self.score_global_and_local_evidence(
            crops,
            product_boxes_in_crops,
            local_bank,
            repvit_scores=repvit_scores,
        )
        return global_scores, local_scores

    def score_global_and_local_evidence(
        self,
        crops: Sequence[Image.Image],
        product_boxes_in_crops: Sequence[Box],
        local_bank: LocalPatchBank,
        *,
        repvit_scores: ModelScoreVector | None = None,
    ) -> tuple[ModelScoreVector, dict[int, float], int, float]:
        evidence = self.score_many_global_and_local_evidence(
            (tuple(crops),),
            (tuple(product_boxes_in_crops),),
            local_bank,
            repvit_scores=(repvit_scores,) if repvit_scores is not None else None,
            max_objects=1,
        )[0]
        return (
            evidence.global_scores,
            evidence.local_scores,
            evidence.product_patch_count,
            evidence.product_patch_ratio,
        )

    def score_many_global_and_local_evidence(
        self,
        crop_groups: Sequence[Sequence[Image.Image]],
        product_box_groups: Sequence[Sequence[Box]],
        local_bank: LocalPatchBank,
        *,
        repvit_scores: Sequence[ModelScoreVector] | None,
        max_objects: int,
    ) -> tuple[DinoGlobalLocalEvidence, ...]:
        groups = tuple(tuple(group) for group in crop_groups)
        boxes = tuple(tuple(group) for group in product_box_groups)
        if not groups or len(groups) != len(boxes):
            raise ValueError("DINOv3 crop and product-box groups must be non-empty and aligned")
        if any(len(group) != 3 for group in groups) or any(len(group) != 3 for group in boxes):
            raise ValueError("DINOv3 local scoring requires three crops and three product boxes")
        if any(not isinstance(crop, Image.Image) for group in groups for crop in group):
            raise ValueError("DINOv3 crops must be PIL images")
        if any(not isinstance(box, Box) for group in boxes for box in group):
            raise ValueError("DINOv3 product boxes must be Box values")
        if type(max_objects) is not int or max_objects <= 0:
            raise ValueError("max_objects must be a positive integer")
        if not callable(getattr(self.encoder, "forward_features", None)):
            raise ValueError("DINOv3 encoder does not expose forward_features")
        if repvit_scores is None:
            aligned_repvit: tuple[ModelScoreVector | None, ...] = (None,) * len(groups)
        else:
            aligned_repvit = tuple(repvit_scores)
            if len(aligned_repvit) != len(groups):
                raise ValueError("RepViT scores must align with DINOv3 crop groups")

        results: list[DinoGlobalLocalEvidence] = []
        if not callable(getattr(self.encoder, "forward_features", None)):
            raise ValueError("DINOv3 encoder does not expose forward_features")
        try:
            for start in range(0, len(groups), max_objects):
                group_slice = groups[start : start + max_objects]
                box_slice = boxes[start : start + max_objects]
                score_slice = aligned_repvit[start : start + max_objects]
                flattened = tuple(crop for group in group_slice for crop in group)
                batch = torch.stack(tuple(self.transform(crop.convert("RGB")) for crop in flattened))
                with torch.inference_mode():
                    features = self.encoder.forward_features(batch.to(self.device))
                    if not isinstance(features, Mapping):
                        raise ValueError("DINOv3 forward_features must return a mapping")
                    cls_tokens = features.get("x_norm_clstoken")
                    patch_tokens = features.get("x_norm_patchtokens")
                    count = len(group_slice)
                    if not isinstance(cls_tokens, torch.Tensor) or tuple(cls_tokens.shape) != (3 * count, _EMBEDDING_DIMENSION):
                        raise ValueError("DINOv3 class tokens must have shape (3 * objects, 384)")
                    if not isinstance(patch_tokens, torch.Tensor) or patch_tokens.ndim != 3 or patch_tokens.shape[:1] != (3 * count,) or patch_tokens.shape[2] != _EMBEDDING_DIMENSION:
                        raise ValueError("DINOv3 patch tokens must have shape (3 * objects, N, 384)")
                    if not torch.isfinite(cls_tokens).all().item() or not torch.isfinite(patch_tokens).all().item():
                        raise ValueError("DINOv3 feature tokens must be finite")
                    grouped_cls = cls_tokens.reshape(count, 3, _EMBEDDING_DIMENSION)
                    grouped_patches = patch_tokens.reshape(count, 3, patch_tokens.shape[1], _EMBEDDING_DIMENSION)
                    for crops, product_boxes, scores, object_cls, object_patches in zip(
                        group_slice, box_slice, score_slice, grouped_cls, grouped_patches, strict=True
                    ):
                        normalized_cls = functional.normalize(object_cls, dim=1)
                        mean_embedding = functional.normalize(normalized_cls.mean(dim=0), dim=0)
                        similarities = self.prototypes @ mean_embedding
                        global_scores = ModelScoreVector(
                            self.model_id,
                            self.sku_ids,
                            tuple(float(value) for value in similarities.detach().cpu().tolist()),
                            "similarity",
                        )
                        if scores is None:
                            candidate_indices = sorted(
                                range(20), key=lambda index: (-global_scores.values[index], self.sku_ids[index])
                            )[:5]
                            candidate_ids = tuple(self.sku_ids[index] for index in candidate_indices)
                        else:
                            candidate_ids = candidate_union(global_scores, scores)
                        masks = tuple(
                            _product_patch_mask(box, crop.size, object_patches.shape[1], object_patches.device)
                            for crop, box in zip(crops, product_boxes, strict=True)
                        )
                        product_mask = torch.cat(masks)
                        local_scores = local_bank.score(
                            candidate_ids,
                            object_patches.reshape(-1, _EMBEDDING_DIMENSION),
                            product_mask,
                        )
                        product_patch_count = int(product_mask.sum().item())
                        results.append(
                            DinoGlobalLocalEvidence(
                                global_scores,
                                local_scores,
                                product_patch_count,
                                product_patch_count / product_mask.numel(),
                            )
                        )
        except torch.OutOfMemoryError as exc:
            raise DinoInferenceError("dino_out_of_memory", "DINOv3 inference exhausted device memory") from exc
        return tuple(results)

    def score_context_chunk_global_and_local_evidence(
        self,
        crops: Sequence[Image.Image],
        product_boxes: Sequence[Box],
        local_bank: LocalPatchBank,
        *,
        repvit_scores: Sequence[ModelScoreVector],
        valid_mask: Sequence[bool],
    ) -> tuple[DinoGlobalLocalEvidence, ...]:
        """Score one padded static chunk with a single context crop per object."""
        rows = tuple(crops)
        boxes = tuple(product_boxes)
        scores = tuple(repvit_scores)
        mask = tuple(valid_mask)
        if len(rows) != 7 or len(boxes) != 7 or len(scores) != 7 or len(mask) != 7:
            raise ValueError("DINO static chunk requires seven aligned rows")
        if any(type(value) is not bool for value in mask) or mask != tuple(sorted(mask, reverse=True)):
            raise ValueError("DINO static mask must contain valid rows followed by padding")
        batch = torch.stack(tuple(self.transform(crop.convert("RGB")) for crop in rows))
        try:
            with torch.inference_mode():
                features = self.encoder.forward_features(batch.to(self.device))
            if not isinstance(features, Mapping):
                raise ValueError("DINOv3 forward_features must return a mapping")
            cls_tokens = features.get("x_norm_clstoken")
            patch_tokens = features.get("x_norm_patchtokens")
            if not isinstance(cls_tokens, torch.Tensor) or tuple(cls_tokens.shape) != (7, 384):
                raise ValueError("DINO static class tokens must have shape (7, 384)")
            if not isinstance(patch_tokens, torch.Tensor) or patch_tokens.ndim != 3 or patch_tokens.shape[0] != 7 or patch_tokens.shape[2] != 384:
                raise ValueError("DINO static patch tokens must have shape (7, N, 384)")
            if not torch.isfinite(cls_tokens).all().item() or not torch.isfinite(patch_tokens).all().item():
                raise ValueError("DINO static tokens must be finite")
            results = []
            for crop, box, repvit, valid, cls_token, patches in zip(
                rows, boxes, scores, mask, cls_tokens, patch_tokens, strict=True
            ):
                if not valid:
                    continue
                if cls_token.norm().item() == 0:
                    raise ValueError("DINO static class token must have non-zero norm")
                embedding = functional.normalize(cls_token, dim=0)
                similarities = self.prototypes @ embedding
                global_scores = ModelScoreVector(
                    self.model_id, self.sku_ids,
                    tuple(float(value) for value in similarities.detach().cpu().tolist()), "similarity",
                )
                candidates = candidate_union(global_scores, repvit)
                product_mask = _product_patch_mask(box, crop.size, patches.shape[0], patches.device)
                if (patches[product_mask].norm(dim=1) == 0).any().item():
                    raise ValueError("DINO static product patches must have non-zero norms")
                local_scores = local_bank.score(candidates, patches, product_mask)
                patch_count = int(product_mask.sum().item())
                results.append(DinoGlobalLocalEvidence(
                    global_scores, local_scores, patch_count, patch_count / product_mask.numel(),
                ))
            return tuple(results)
        except torch.OutOfMemoryError as exc:
            raise DinoInferenceError("dino_out_of_memory", "DINOv3 inference exhausted device memory") from exc


def _verify_sha256(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"DINOv3 {label} file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError(f"DINOv3 {label} SHA-256 mismatch")


def _load_validated_artifacts(
    config: ClassifierConfig,
    *,
    expected_preprocess_sha256: str | None,
) -> tuple[object, torch.Tensor, Callable[[Image.Image], torch.Tensor]]:
    dinov3 = config.dinov3
    _verify_sha256(dinov3.weights, dinov3.weights_sha256, "weights")
    _verify_sha256(dinov3.support, dinov3.support_sha256, "support")
    _verify_sha256(config.repvit.manifest, config.repvit.manifest_sha256, "RepViT manifest")
    weights = torch.load(dinov3.weights, map_location="cpu", weights_only=True)
    support = torch.load(dinov3.support, map_location="cpu", weights_only=True)
    transform = build_transform(config.preprocess.input_size)
    prototypes = _validate_support(
        support,
        weights=weights,
        weights_path=dinov3.weights,
        weights_sha256=dinov3.weights_sha256,
        repvit_manifest=config.repvit.manifest,
        runtime_transform=transform,
        expected_preprocess_sha256=expected_preprocess_sha256,
    )
    return weights, prototypes, transform


def _product_patch_mask(box: Box, crop_size: tuple[int, int], token_count: int, device: torch.device) -> torch.Tensor:
    width, height = crop_size
    grid = int(token_count**0.5)
    if grid * grid != token_count or width <= 0 or height <= 0:
        raise ValueError("DINOv3 patch-token grid is invalid")
    if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
        raise ValueError("product box must stay within its crop")
    # A verifier foreground mask is not available yet.  Erode the box so local
    # matching avoids the most likely tray/background boundary patches.
    inset_x = box.width * 0.05
    inset_y = box.height * 0.05
    left = box.x + inset_x
    top = box.y + inset_y
    right = box.x + box.width - inset_x
    bottom = box.y + box.height - inset_y
    centers_x = (torch.arange(grid, device=device) + 0.5) * width / grid
    centers_y = (torch.arange(grid, device=device) + 0.5) * height / grid
    xx, yy = torch.meshgrid(centers_x, centers_y, indexing="xy")
    return ((xx >= left) & (xx <= right) & (yy >= top) & (yy <= bottom)).reshape(-1)


def _validate_support(
    value: object,
    *,
    weights: object,
    weights_path: Path,
    weights_sha256: str,
    repvit_manifest: Path,
    runtime_transform: Callable[[Image.Image], torch.Tensor],
    expected_preprocess_sha256: str | None = None,
) -> torch.Tensor:
    if not isinstance(value, dict):
        raise ValueError("DINOv3 support must be a mapping")
    if value.get("artifact_type") != _SUPPORT_ARTIFACT_TYPE:
        raise ValueError("DINOv3 support artifact_type is invalid")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("DINOv3 support schema_version must be 1")

    class_map = value.get("class_map")
    repvit_class_map = _load_repvit_class_map(repvit_manifest)
    if class_map != repvit_class_map:
        raise ValueError("DINOv3 support class_map must match RepViT class_map")
    if not isinstance(class_map, list) or tuple(row.get("id") for row in class_map) != _SKU_IDS:
        raise ValueError("DINOv3 support class_map must use canonical SKU order")

    checkpoint = value.get("dino_checkpoint")
    expected_checkpoint = {
        "architecture": _ARCHITECTURE,
        "file": weights_path.name,
        "key_count": len(weights) if isinstance(weights, Mapping) else -1,
        "sha256": weights_sha256,
        "storage_token_shape": _STORAGE_TOKEN_SHAPE,
    }
    if checkpoint != expected_checkpoint:
        if isinstance(checkpoint, dict) and checkpoint.get("sha256") != weights_sha256:
            raise ValueError("DINOv3 support-declared checkpoint SHA-256 mismatch")
        raise ValueError("DINOv3 support dino_checkpoint metadata is invalid")

    runtime_metadata = _describe_transform(runtime_transform)
    if value.get("transform") != runtime_metadata:
        raise ValueError("DINOv3 support transform metadata does not match runtime transform")
    if expected_preprocess_sha256 is not None:
        descriptor = ClassifierPreprocessDescriptor()
        metadata = value.get("oof_metadata")
        if (
            expected_preprocess_sha256 != descriptor.sha256()
            or not isinstance(metadata, dict)
            or metadata.get("preprocessing_sha256") != expected_preprocess_sha256
            or metadata.get("preprocessing_descriptor") != descriptor.to_payload()
        ):
            raise ValueError("DINOv3 support OOF preprocessing descriptor or SHA-256 mismatch")

    prototypes = value.get("prototypes")
    _validate_prototypes(prototypes)
    return prototypes


def _load_repvit_class_map(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        class_map = payload["class_map"]
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("RepViT manifest class_map is invalid") from exc
    if not isinstance(class_map, list) or not all(isinstance(row, dict) for row in class_map):
        raise ValueError("RepViT manifest class_map is invalid")
    return class_map


def _validate_prototypes(value: object) -> None:
    if not isinstance(value, torch.Tensor) or tuple(value.shape) != _PROTOTYPE_SHAPE:
        raise ValueError("DINOv3 prototypes must have shape (20, 384)")
    if value.dtype != torch.float32:
        raise ValueError("DINOv3 prototypes must use float32")
    if not torch.isfinite(value).all().item():
        raise ValueError("DINOv3 prototypes must be finite")
    norms = value.norm(dim=1)
    if not torch.allclose(norms, torch.ones_like(norms), rtol=1e-5, atol=1e-5):
        raise ValueError("DINOv3 prototypes must be unit-length")


def _describe_transform(
    value: Callable[[Image.Image], torch.Tensor],
) -> dict[str, object]:
    if not isinstance(value, transforms.Compose) or len(value.transforms) != 3:
        raise ValueError("DINOv3 runtime transform structure is invalid")
    resize, to_tensor, normalize = value.transforms
    if (
        not isinstance(resize, transforms.Resize)
        or not isinstance(to_tensor, transforms.ToTensor)
        or not isinstance(normalize, transforms.Normalize)
    ):
        raise ValueError("DINOv3 runtime transform structure is invalid")
    size = [resize.size, resize.size] if isinstance(resize.size, int) else list(resize.size)
    interpolation = getattr(resize.interpolation, "value", str(resize.interpolation).lower())
    return {
        "antialias": resize.antialias,
        "image_mode": "RGB",
        "input_size": size,
        "mean": list(normalize.mean),
        "resize_interpolation": interpolation,
        "std": list(normalize.std),
    }
