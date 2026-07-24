"""EXIF-aware full-frame normalization with reversible box coordinates."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps

from bakery_scanner.contracts import Box


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


def normalize_capture(image: Image.Image, target_size: tuple[int, int]) -> NormalizedCapture:
    """Apply EXIF orientation and letterbox the complete image onto a canvas.

    This deliberately performs no tray geometry, ROI, or colour calibration.
    """
    if len(target_size) != 2 or any(not isinstance(value, int) or value <= 0 for value in target_size):
        raise ValueError("target_size must contain two positive integers")
    oriented = ImageOps.exif_transpose(image).convert("RGB")
    source_width, source_height = oriented.size
    target_width, target_height = target_size
    scale = min(target_width / source_width, target_height / source_height)
    resized_size = (round(source_width * scale), round(source_height * scale))
    resized = oriented.resize(resized_size, Image.Resampling.LANCZOS)
    offset = ((target_width - resized.width) / 2, (target_height - resized.height) / 2)
    canvas = Image.new("RGB", target_size)
    canvas.paste(resized, (round(offset[0]), round(offset[1])))
    return NormalizedCapture(canvas, (source_width, source_height), target_size, scale, offset)
