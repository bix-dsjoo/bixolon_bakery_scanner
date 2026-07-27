"""Strict RepViT-M1 artifact loading and three-crop probability scoring."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Sequence

import timm
import torch
from PIL import Image

from .config import ClassifierConfig
from .contracts import ModelScoreVector
from .preprocess import build_transform

_SKU_IDS = tuple(range(1, 21))


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
            if not torch.isfinite(probabilities).all().item():
                raise ValueError("RepViT probabilities must be finite")
        values = tuple(float(value) for value in probabilities.detach().cpu().tolist())
        return ModelScoreVector(self.model_id, self.sku_ids, values, "probability")


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
