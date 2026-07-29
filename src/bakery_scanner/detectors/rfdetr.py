"""RF-DETR-L adapter that preserves the scanner's canonical bread proposal contract."""

from __future__ import annotations

import math
from numbers import Integral
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

from bakery_scanner.contracts import Box, BreadProposal


_PRODUCT_CLASS_ID = 0
_PRODUCT_CLASS_NAME = "product"
_BACKGROUND_CLASS_ID = 1
_BACKGROUND_CLASS_NAME = "__background__"
_SOURCE = "rfdetr_large_bakery_v1"


class RFDetrRunner:
    """Normalize a loaded RF-DETR-L model into canonical bread proposals."""

    def __init__(self, model: Any, *, score_threshold: float, source: str = _SOURCE) -> None:
        if not hasattr(model, "predict"):
            raise TypeError("RF-DETR backend must provide predict()")
        if isinstance(score_threshold, bool) or not isinstance(score_threshold, (int, float)):
            raise ValueError("score_threshold must be a finite number in [0, 1]")
        if not math.isfinite(float(score_threshold)) or not 0.0 <= float(score_threshold) <= 1.0:
            raise ValueError("score_threshold must be a finite number in [0, 1]")
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a non-empty detector identifier")
        self._model = model
        self._score_threshold = float(score_threshold)
        self.source = source

    @classmethod
    def from_model(cls, model: Any, *, score_threshold: float, source: str = _SOURCE) -> "RFDetrRunner":
        return cls(model, score_threshold=score_threshold, source=source)

    @classmethod
    def load(
        cls,
        checkpoint: str | Path,
        *,
        score_threshold: float,
        source: str = _SOURCE,
        device: str = "cuda",
        model_factory: Callable[..., Any] | None = None,
    ) -> "RFDetrRunner":
        checkpoint_path = Path(checkpoint).resolve()
        if not checkpoint_path.is_file():
            raise ValueError(f"RF-DETR checkpoint is missing: {checkpoint_path}")
        if model_factory is None:
            try:
                from rfdetr import RFDETRLarge
            except ImportError as error:
                raise RuntimeError("RF-DETR is required for RFDetrRunner.load()") from error
            model_factory = RFDETRLarge
        return cls(
            model_factory(pretrain_weights=str(checkpoint_path), num_classes=1, device=device),
            score_threshold=score_threshold,
            source=source,
        )

    def predict(self, image_id: int, image: Image.Image) -> tuple[BreadProposal, ...]:
        if not isinstance(image, Image.Image) or image.mode != "RGB":
            raise ValueError("RF-DETR inputs must be canonical RGB PIL images")
        output = self._model.predict(
            image,
            threshold=self._score_threshold,
            include_source_image=False,
        )
        if isinstance(output, list):
            if len(output) != 1:
                raise ValueError("single-image RF-DETR inference must return one result")
            output = output[0]
        try:
            boxes = np.asarray(output.xyxy)
            scores = np.asarray(output.confidence)
            classes = np.asarray(output.class_id)
            names = np.asarray(output.data["class_name"])
        except (AttributeError, KeyError, TypeError) as error:
            raise ValueError("malformed RF-DETR output fields") from error
        if boxes.ndim != 2 or boxes.shape[1:] != (4,):
            raise ValueError("RF-DETR xyxy must have shape (N, 4)")
        count = boxes.shape[0]
        if scores.shape != (count,) or classes.shape != (count,) or names.shape != (count,):
            raise ValueError("RF-DETR output field length mismatch")
        if not np.issubdtype(boxes.dtype, np.number) or not np.issubdtype(scores.dtype, np.number):
            raise ValueError("RF-DETR coordinates and scores must be numeric")
        if not np.all(np.isfinite(boxes)) or not np.all(np.isfinite(scores)):
            raise ValueError("RF-DETR coordinates and scores must be finite")

        width, height = image.size
        proposals: list[BreadProposal] = []
        for xyxy, score, class_id, class_name in zip(boxes.astype(float, copy=False), scores, classes, names, strict=True):
            if isinstance(class_id, (bool, np.bool_)) or not isinstance(class_id, Integral):
                raise ValueError("RF-DETR class id must be an integer")
            score_value = float(score)
            if not 0.0 <= score_value <= 1.0:
                raise ValueError("RF-DETR score must lie in [0, 1]")
            class_value = int(class_id)
            if class_value == _BACKGROUND_CLASS_ID and str(class_name) == _BACKGROUND_CLASS_NAME:
                continue
            if class_value != _PRODUCT_CLASS_ID or str(class_name) != _PRODUCT_CLASS_NAME:
                raise ValueError(f"unknown RF-DETR class: id={class_id!r}, name={class_name!r}")
            x1, y1, x2, y2 = (float(value) for value in xyxy)
            clipped_x1 = min(max(x1, 0.0), float(width))
            clipped_y1 = min(max(y1, 0.0), float(height))
            clipped_x2 = min(max(x2, 0.0), float(width))
            clipped_y2 = min(max(y2, 0.0), float(height))
            if clipped_x2 <= clipped_x1 or clipped_y2 <= clipped_y1:
                continue
            proposals.append(
                BreadProposal(
                    image_id=image_id,
                    source=self.source,
                    score=score_value,
                    box=Box(clipped_x1, clipped_y1, clipped_x2 - clipped_x1, clipped_y2 - clipped_y1),
                    image_width=width,
                    image_height=height,
                )
            )
        return tuple(sorted(proposals, key=lambda item: (-item.score, item.box.y, item.box.x, item.box.height, item.box.width)))
