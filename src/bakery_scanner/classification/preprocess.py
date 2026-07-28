"""Deterministic image preparation shared by classifier model runners."""

from __future__ import annotations

import math

from PIL import Image
from torchvision import transforms

from bakery_scanner.contracts import Box


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
