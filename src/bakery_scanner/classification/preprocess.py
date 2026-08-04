"""Deterministic image preparation shared by classifier model runners."""

from __future__ import annotations

import math
import hashlib
import json
from dataclasses import asdict, dataclass

from PIL import Image
from torchvision import transforms

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import CanonicalImage


@dataclass(frozen=True, slots=True)
class ClassifierPreprocessDescriptor:
    """Immutable identity of every Task 5 tight/context pixel transform."""

    schema_version: int = 1
    canonical_frame_version: str = "exif_visual_rgb_v1"
    crop_rule: str = "total_padding_split_floor_ceil_clip_rgb"
    input_size: int = 224
    context_padding: float = 0.10
    interpolation: str = "bilinear_antialias_true"
    normalization_mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    normalization_std: tuple[float, float, float] = (0.229, 0.224, 0.225)

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.canonical_frame_version != "exif_visual_rgb_v1":
            raise ValueError("unsupported classifier preprocessing descriptor")
        if self.crop_rule != "total_padding_split_floor_ceil_clip_rgb":
            raise ValueError("classifier crop rule is not canonical")
        if self.input_size != 224 or self.context_padding != 0.10:
            raise ValueError("classifier preprocessing must use 224 and context padding 0.10")
        if self.interpolation != "bilinear_antialias_true":
            raise ValueError("classifier interpolation must be bilinear with antialiasing")
        if self.normalization_mean != (0.485, 0.456, 0.406) or self.normalization_std != (0.229, 0.224, 0.225):
            raise ValueError("classifier normalization is not canonical")

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["normalization_mean"] = list(self.normalization_mean)
        payload["normalization_std"] = list(self.normalization_std)
        return payload

    def sha256(self) -> str:
        encoded = json.dumps(
            self.to_payload(), allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CropPair:
    tight: Image.Image
    context: Image.Image
    box: Box
    context_product_box: Box


def build_crop_pair(
    frame: CanonicalImage,
    box: Box,
    context_padding: float = 0.10,
) -> CropPair:
    """Build ordered tight/context crops in the verified canonical frame."""
    if not isinstance(frame, CanonicalImage):
        raise ValueError("frame must be a CanonicalImage")
    _require_canonical_frame(frame)
    try:
        frame.require_box(box)
    except ValueError as exc:
        raise ValueError("box must stay within canonical visual image bounds") from exc
    if context_padding != 0.10:
        raise ValueError("context padding must be the immutable value 0.10")
    tight = _crop_one(frame.image, box, 0.0)
    context_bounds = _crop_bounds(frame.image, box, context_padding)
    left, top, right, bottom = context_bounds
    context = frame.image.crop((left, top, right, bottom))
    return CropPair(
        tight=tight,
        context=context,
        box=box,
        context_product_box=Box(box.x - left, box.y - top, box.width, box.height),
    )


def _require_canonical_frame(frame: CanonicalImage) -> None:
    width, height = frame.visual_size
    if (
        frame.frame_version != "exif_visual_rgb_v1"
        or frame.image.mode != "RGB"
        or type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
        or frame.image.size != frame.visual_size
    ):
        raise ValueError("canonical frame invariants are invalid")


def make_padded_crops(
    image: Image.Image,
    box: Box,
    paddings: tuple[float, ...],
) -> tuple[Image.Image, ...]:
    """Return RGB crops expanded by each total fractional padding amount."""
    rgb = image.convert("RGB")
    return tuple(_crop_one(rgb, box, padding) for padding in paddings)


def make_padded_crops_with_product_boxes(
    image: Image.Image,
    box: Box,
    paddings: tuple[float, ...],
) -> tuple[tuple[Image.Image, ...], tuple[Box, ...]]:
    """Return padded crops and the verified product box in each crop frame."""
    rgb = image.convert("RGB")
    crops: list[Image.Image] = []
    product_boxes: list[Box] = []
    for padding in paddings:
        left, top, right, bottom = _crop_bounds(rgb, box, padding)
        crops.append(rgb.crop((left, top, right, bottom)))
        product_boxes.append(Box(box.x - left, box.y - top, box.width, box.height))
    return tuple(crops), tuple(product_boxes)


def _crop_one(image: Image.Image, box: Box, padding: float) -> Image.Image:
    left, top, right, bottom = _crop_bounds(image, box, padding)
    return image.crop((left, top, right, bottom))


def _crop_bounds(image: Image.Image, box: Box, padding: float) -> tuple[int, int, int, int]:
    if not math.isfinite(padding) or padding < 0.0:
        raise ValueError("padding must be a finite non-negative value")
    horizontal = padding * box.width / 2.0
    vertical = padding * box.height / 2.0
    left = max(0, math.floor(box.x - horizontal))
    top = max(0, math.floor(box.y - vertical))
    right = min(image.width, math.ceil(box.x + box.width + horizontal))
    bottom = min(image.height, math.ceil(box.y + box.height + vertical))
    if right <= left or bottom <= top:
        raise ValueError("box must intersect the image after clipping")
    return left, top, right, bottom


def build_transform(input_size: int) -> transforms.Compose:
    """Build the fixed ImageNet normalization used by both classifier models."""
    return transforms.Compose([
        transforms.Resize((input_size, input_size), antialias=True),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
