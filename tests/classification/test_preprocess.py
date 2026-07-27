from __future__ import annotations

from PIL import Image

from bakery_scanner.classification.preprocess import make_padded_crops, make_padded_crops_with_product_boxes
from bakery_scanner.contracts import Box


def test_three_padded_crops_are_ordered_and_clipped():
    image = Image.new("RGB", (100, 80))
    crops = make_padded_crops(image, Box(0, 0, 40, 20), (0.05, 0.10, 0.15))
    assert len(crops) == 3
    assert [crop.size for crop in crops] == [(41, 21), (42, 21), (43, 22)]


def test_centered_crop_expands_each_side_with_floor_and_ceil():
    image = Image.new("RGB", (100, 80))
    crops = make_padded_crops(image, Box(20, 30, 40, 20), (0.05,))
    assert crops[0].size == (42, 22)


def test_crops_clip_at_all_image_edges():
    image = Image.new("RGB", (100, 80))
    boxes = (Box(0, 0, 10, 10), Box(90, 0, 10, 10), Box(0, 70, 10, 10), Box(90, 70, 10, 10))
    assert [make_padded_crops(image, box, (0.15,))[0].size for box in boxes] == [(11, 11)] * 4


def test_crops_convert_non_rgb_input_to_rgb():
    image = Image.new("L", (20, 20), 42)
    crop = make_padded_crops(image, Box(2, 2, 10, 10), (0.05,))[0]
    assert crop.mode == "RGB"
    assert crop.getpixel((0, 0)) == (42, 42, 42)


def test_crops_are_deterministic_pixel_for_pixel():
    image = Image.effect_noise((40, 40), 50).convert("RGB")
    box = Box(5, 5, 20, 20)
    first = make_padded_crops(image, box, (0.05, 0.10, 0.15))
    second = make_padded_crops(image, box, (0.05, 0.10, 0.15))
    assert [crop.tobytes() for crop in first] == [crop.tobytes() for crop in second]


def test_padded_crops_return_the_product_box_in_each_crop_coordinate_frame():
    crops, product_boxes = make_padded_crops_with_product_boxes(
        Image.new("RGB", (100, 80)),
        Box(20, 30, 40, 20),
        (0.05, 0.10, 0.15),
    )

    assert [crop.size for crop in crops] == [(42, 22), (44, 22), (46, 24)]
    assert product_boxes == (
        Box(1, 1, 40, 20),
        Box(2, 1, 40, 20),
        Box(3, 2, 40, 20),
    )
