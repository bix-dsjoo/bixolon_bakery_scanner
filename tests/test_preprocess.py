from io import BytesIO

from PIL import Image
import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image, normalize_capture


def test_box_transform_round_trips_with_half_pixel_tolerance():
    normalized = normalize_capture(Image.new("RGB", (400, 300)), (1152, 1536))
    box = Box(100, 80, 120, 90)

    restored = normalized.canonical_box_to_source(
        normalized.source_box_to_canonical(box)
    )

    assert restored.xyxy == pytest.approx(box.xyxy, abs=0.5)
    assert normalized.image.size == (1152, 1536)


def test_canonicalize_uses_exif_visual_coordinates_for_orientation_six():
    encoded = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20), "white").save(encoded, format="JPEG", exif=exif)

    frame = canonicalize_image(Image.open(BytesIO(encoded.getvalue())))

    assert frame.raw_size == (40, 20)
    assert frame.visual_size == (20, 40)
    assert frame.image.size == (20, 40)
    assert frame.exif_orientation == 6
    frame.require_box(Box(1, 2, 10, 20))
    with pytest.raises(ValueError, match="canonical visual"):
        frame.require_box(Box(15, 2, 10, 20))
