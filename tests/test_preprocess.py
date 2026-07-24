from PIL import Image
import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import normalize_capture


def test_box_transform_round_trips_with_half_pixel_tolerance():
    normalized = normalize_capture(Image.new("RGB", (400, 300)), (1152, 1536))
    box = Box(100, 80, 120, 90)

    restored = normalized.canonical_box_to_source(
        normalized.source_box_to_canonical(box)
    )

    assert restored.xyxy == pytest.approx(box.xyxy, abs=0.5)
    assert normalized.image.size == (1152, 1536)
