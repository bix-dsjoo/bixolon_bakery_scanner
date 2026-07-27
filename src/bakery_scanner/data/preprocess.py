"""EXIF-aware full-frame normalization with reversible box coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps

from bakery_scanner.contracts import Box


@dataclass(frozen=True, slots=True)
class CanonicalImage:
    """RGB image whose coordinates are the EXIF-corrected visual frame."""

    image: Image.Image
    visual_size: tuple[int, int]
    raw_size: tuple[int, int]
    exif_orientation: int
    frame_version: Literal["exif_visual_rgb_v1"] = "exif_visual_rgb_v1"

    def require_box(self, box: Box) -> None:
        if not isinstance(box, Box):
            raise ValueError("box must be a Box in canonical visual coordinates")
        width, height = self.visual_size
        if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
            raise ValueError("box must stay within canonical visual image bounds")


def canonicalize_image(image: Image.Image) -> CanonicalImage:
    """Transpose encoded EXIF orientation once and expose visual RGB pixels."""
    if not isinstance(image, Image.Image):
        raise ValueError("image must be a PIL Image")
    raw_size = image.size
    try:
        orientation = int(image.getexif().get(274, 1))
    except (AttributeError, TypeError, ValueError):
        orientation = 1
    if orientation < 1 or orientation > 8:
        orientation = 1
    visual = ImageOps.exif_transpose(image).convert("RGB")
    return CanonicalImage(
        image=visual,
        visual_size=visual.size,
        raw_size=raw_size,
        exif_orientation=orientation,
    )


def load_canonical_image(path: str | Path) -> CanonicalImage:
    """Load a capture and immediately establish its visual coordinate frame."""
    with Image.open(path) as encoded:
        return canonicalize_image(encoded)


@dataclass(frozen=True, slots=True)
class NormalizedCapture:
    """A letterboxed canonical image and its source/canvas coordinate mapping."""

    image: Image.Image
    source_size: tuple[int, int]
    target_size: tuple[int, int]
    scale: float
    offset: tuple[float, float]

    def source_box_to_canonical(self, box: Box) -> Box:
        return Box(
            box.x * self.scale + self.offset[0],
            box.y * self.scale + self.offset[1],
            box.width * self.scale,
            box.height * self.scale,
        )

    def canonical_box_to_source(self, box: Box) -> Box:
        return Box(
            (box.x - self.offset[0]) / self.scale,
            (box.y - self.offset[1]) / self.scale,
            box.width / self.scale,
            box.height / self.scale,
        )


def normalize_capture(image: Image.Image | CanonicalImage, target_size: tuple[int, int]) -> NormalizedCapture:
    """Apply EXIF orientation and letterbox the complete image onto a canvas.

    This deliberately performs no tray geometry, ROI, or colour calibration.
    """
    if len(target_size) != 2 or any(not isinstance(value, int) or value <= 0 for value in target_size):
        raise ValueError("target_size must contain two positive integers")
    oriented = image.image if isinstance(image, CanonicalImage) else canonicalize_image(image).image
    source_width, source_height = oriented.size
    target_width, target_height = target_size
    scale = min(target_width / source_width, target_height / source_height)
    resized_size = (round(source_width * scale), round(source_height * scale))
    resized = oriented.resize(resized_size, Image.Resampling.LANCZOS)
    offset = ((target_width - resized.width) / 2, (target_height - resized.height) / 2)
    canvas = Image.new("RGB", target_size)
    canvas.paste(resized, (round(offset[0]), round(offset[1])))
    return NormalizedCapture(canvas, (source_width, source_height), target_size, scale, offset)
