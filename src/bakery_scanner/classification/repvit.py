"""Strict RepViT-M1 artifact loading and three-crop probability scoring."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import timm
import torch
from PIL import Image

from .config import ClassifierConfig
from .contracts import ModelScoreVector
from .preprocess import build_transform

_SKU_IDS = tuple(range(1, 21))


@dataclass(frozen=True, slots=True)
class RepVitEvidence:
    scores: ModelScoreVector
    feature: torch.Tensor
    crop_disagreement: float


@dataclass(frozen=True, slots=True)
class TightContextRepVitEvidence:
    scores: ModelScoreVector
    tight_scores: ModelScoreVector
    context_scores: ModelScoreVector
    feature: torch.Tensor
    crop_disagreement: float


@dataclass(frozen=True, slots=True)
class RepVitPrototypeBank:
    prototypes: torch.Tensor

    @classmethod
    def load(cls, path: Path, *, checkpoint_sha256: str, expected_preprocess_sha256: str, expected_sha256: str) -> "RepVitPrototypeBank":
        _verify_sha256(path, expected_sha256, "prototype bank")
        payload = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict) or payload.get("artifact_type") != "repvit_m1_15plus5_feature_prototypes":
            raise ValueError("RepViT prototype artifact is invalid")
        if payload.get("checkpoint_sha256") != checkpoint_sha256 or payload.get("preprocess_sha256") != expected_preprocess_sha256:
            raise ValueError("RepViT prototype artifact provenance mismatch")
        value = payload.get("prototypes")
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != (20, 384) or not torch.isfinite(value).all().item():
            raise ValueError("RepViT prototypes must have shape (20, 384)")
        return cls(torch.nn.functional.normalize(value.float(), dim=1))

    def distances(self, feature: torch.Tensor) -> tuple[float, ...]:
        if tuple(feature.shape) != (384,) or not torch.isfinite(feature).all().item():
            raise ValueError("RepViT feature must have shape (384,)")
        vector = torch.nn.functional.normalize(feature.float(), dim=0)
        return tuple(float(value) for value in (1.0 - self.prototypes @ vector).tolist())


class RepVitM1Runner:
    def __init__(
        self,
        model: torch.nn.Module,
        sku_ids: tuple[int, ...],
        transform: Callable[[Image.Image], torch.Tensor],
        model_id: str,
        device: torch.device,
    ) -> None:
        if sku_ids != _SKU_IDS:
            raise ValueError("RepViT SKU IDs must be 1 through 20 in canonical order")
        self.model = model
        self.sku_ids = sku_ids
        self.transform = transform
        self.model_id = model_id
        self.device = device

    @classmethod
    def load(cls, config: ClassifierConfig, *, device: torch.device | None = None) -> "RepVitM1Runner":
        repvit = config.repvit
        _verify_sha256(repvit.checkpoint, repvit.checkpoint_sha256, "checkpoint")
        _verify_sha256(repvit.manifest, repvit.manifest_sha256, "manifest")
        checkpoint = torch.load(repvit.checkpoint, map_location="cpu", weights_only=True)
        class_index = checkpoint.get("class_index") if isinstance(checkpoint, dict) else None
        _require_class_index(class_index)
        _require_manifest_class_map(repvit.manifest)
        if device is None:
            device = torch.device(config.runtime.device.lower())
        model = timm.create_model("repvit_m1", pretrained=False, num_classes=20)
        state_dict = checkpoint.get("state_dict") if isinstance(checkpoint, dict) else None
        if not isinstance(state_dict, dict):
            raise ValueError("RepViT checkpoint must contain state_dict")
        model.load_state_dict(state_dict, strict=True)
        model.to(device).eval()
        return cls(model, _SKU_IDS, build_transform(config.preprocess.input_size), repvit.artifact_id, device)

    def score(self, crops: Sequence[Image.Image]) -> ModelScoreVector:
        if len(crops) != 3:
            raise ValueError("RepViT requires exactly three crops")
        batch = torch.stack(tuple(self.transform(crop.convert("RGB")) for crop in crops))
        with torch.inference_mode():
            logits = self.model(batch.to(self.device))
            if logits.shape != (3, 20):
                raise ValueError("RepViT logits must have shape (3, 20)")
            if not torch.isfinite(logits).all().item():
                raise ValueError("RepViT logits must be finite")
            probabilities = logits.softmax(dim=1).mean(dim=0)
        return ModelScoreVector(self.model_id, self.sku_ids, tuple(float(value) for value in probabilities.detach().cpu().tolist()), "probability")

    def score_with_evidence(self, crops: Sequence[Image.Image]) -> RepVitEvidence:
        return self.score_many_with_evidence((tuple(crops),), max_objects=1)[0]

    def score_many_with_evidence(
        self,
        crop_groups: Sequence[Sequence[Image.Image]],
        *,
        max_objects: int,
    ) -> tuple[RepVitEvidence, ...]:
        groups = _validated_crop_groups(crop_groups)
        if type(max_objects) is not int or max_objects <= 0:
            raise ValueError("max_objects must be a positive integer")
        results: list[RepVitEvidence] = []
        for start in range(0, len(groups), max_objects):
            crops = tuple(crop for group in groups[start : start + max_objects] for crop in group)
            results.extend(self._score_evidence_batch(crops))
        return tuple(results)

    def score_tight_context_chunk(
        self,
        crops: Sequence[Image.Image],
        *,
        valid_mask: Sequence[bool],
    ) -> tuple[TightContextRepVitEvidence, ...]:
        """Score one padded static chunk of seven ordered tight/context pairs."""
        rows = tuple(crops)
        mask = tuple(valid_mask)
        if len(rows) != 14 or len(mask) != 14 or any(type(value) is not bool for value in mask):
            raise ValueError("RepViT static chunk requires 14 crops and a 14-row boolean mask")
        pair_mask = tuple(mask[index] and mask[index + 1] for index in range(0, 14, 2))
        if any(mask[index] != mask[index + 1] for index in range(0, 14, 2)) or pair_mask != tuple(sorted(pair_mask, reverse=True)):
            raise ValueError("RepViT static mask must contain complete valid pairs followed by padding")
        batch = torch.stack(tuple(self.transform(crop.convert("RGB")) for crop in rows))
        with torch.inference_mode():
            features = self.model.forward_features(batch.to(self.device))
            if not isinstance(features, torch.Tensor) or features.ndim != 4 or features.shape[:2] != (14, 384):
                raise ValueError("RepViT static features must have shape (14, 384, H, W)")
            logits = self.model.forward_head(features, pre_logits=False)
            if tuple(logits.shape) != (14, 20) or not torch.isfinite(logits).all().item():
                raise ValueError("RepViT static logits must be finite with shape (14, 20)")
            crop_probabilities = logits.softmax(dim=1).reshape(7, 2, 20)
            pooled = torch.nn.functional.normalize(features.mean(dim=(2, 3)), dim=1).reshape(7, 2, 384)
            probabilities = crop_probabilities.mean(dim=1)
            object_features = pooled.mean(dim=1)
            disagreements = (probabilities[:, None, :] - crop_probabilities).abs().mean(dim=(1, 2))
        results = []
        for index, valid in enumerate(pair_mask):
            if not valid:
                continue
            vectors = tuple(
                ModelScoreVector(self.model_id, self.sku_ids, tuple(float(value) for value in values.tolist()), "probability")
                for values in (probabilities[index], crop_probabilities[index, 0], crop_probabilities[index, 1])
            )
            results.append(TightContextRepVitEvidence(
                vectors[0], vectors[1], vectors[2], object_features[index].detach().cpu(),
                float(disagreements[index].detach().cpu()),
            ))
        return tuple(results)

    def _score_evidence_batch(self, crops: Sequence[Image.Image]) -> tuple[RepVitEvidence, ...]:
        if not crops or len(crops) % 3:
            raise ValueError("RepViT evidence batches must contain exactly three crops per object")
        object_count = len(crops) // 3
        batch = torch.stack(tuple(self.transform(crop.convert("RGB")) for crop in crops))
        with torch.inference_mode():
            model_input = batch.to(self.device)
            features = self.model.forward_features(model_input)
            if features.ndim != 4 or features.shape[:2] != (3 * object_count, 384):
                raise ValueError("RepViT features must have shape (3 * objects, 384, H, W)")
            if not torch.isfinite(features).all().item():
                raise ValueError("RepViT features must be finite")
            pooled = torch.nn.functional.normalize(features.mean(dim=(2, 3)), dim=1)
            logits = self.model.forward_head(features, pre_logits=False)
            if logits.shape != (3 * object_count, 20):
                raise ValueError("RepViT logits must have shape (3 * objects, 20)")
            if not torch.isfinite(logits).all().item():
                raise ValueError("RepViT logits must be finite")
            crop_probabilities = logits.softmax(dim=1).reshape(object_count, 3, 20)
            probabilities = crop_probabilities.mean(dim=1)
            if not torch.isfinite(probabilities).all().item():
                raise ValueError("RepViT probabilities must be finite")
        object_features = pooled.reshape(object_count, 3, 384).mean(dim=1)
        disagreements = (probabilities[:, None, :] - crop_probabilities).abs().mean(dim=(1, 2))
        return tuple(
            RepVitEvidence(
                ModelScoreVector(
                    self.model_id,
                    self.sku_ids,
                    tuple(float(value) for value in score_values.tolist()),
                    "probability",
                ),
                feature.detach().cpu(),
                float(disagreement.detach().cpu()),
            )
            for score_values, feature, disagreement in zip(
                probabilities.detach().cpu(), object_features, disagreements, strict=True
            )
        )


def _validated_crop_groups(
    crop_groups: Sequence[Sequence[Image.Image]],
) -> tuple[tuple[Image.Image, Image.Image, Image.Image], ...]:
    groups = tuple(tuple(group) for group in crop_groups)
    if not groups:
        raise ValueError("RepViT crop groups must not be empty")
    if any(len(group) != 3 for group in groups):
        raise ValueError("RepViT requires exactly three crops per object")
    if any(not isinstance(crop, Image.Image) for group in groups for crop in group):
        raise ValueError("RepViT crops must be PIL images")
    return tuple((group[0], group[1], group[2]) for group in groups)


def _verify_sha256(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"RepViT {label} file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError(f"RepViT {label} SHA-256 mismatch")


def _require_class_index(value: object) -> None:
    expected = {sku: sku - 1 for sku in _SKU_IDS}
    if value != expected:
        raise ValueError("RepViT checkpoint class_index must map {1: 0, ..., 20: 19}")


def _require_manifest_class_map(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        class_map = payload["class_map"]
        sku_ids = tuple(row["id"] for row in class_map)
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("RepViT manifest class_map is invalid") from exc
    if sku_ids != _SKU_IDS:
        raise ValueError("RepViT manifest class_map must match checkpoint canonical class order")
