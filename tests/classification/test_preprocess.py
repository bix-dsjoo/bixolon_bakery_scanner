from __future__ import annotations

import pytest
from PIL import Image

from bakery_scanner.classification.preprocess import (
    ClassifierPreprocessDescriptor,
    build_crop_pair,
    make_padded_crops,
    make_padded_crops_with_product_boxes,
)
from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image


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


def test_tight_context_pair_uses_canonical_frame_and_exact_order():
    frame = canonicalize_image(Image.new("L", (100, 80), 42))

    pair = build_crop_pair(frame, Box(20, 30, 40, 20))

    assert pair.box == Box(20, 30, 40, 20)
    assert pair.tight.mode == pair.context.mode == "RGB"
    assert pair.tight.size == (40, 20)
    assert pair.context.size == (44, 22)
    assert pair.context_product_box == Box(2, 1, 40, 20)


def test_classifier_preprocess_descriptor_is_hashable_and_complete():
    descriptor = ClassifierPreprocessDescriptor()

    assert descriptor.input_size == 224
    assert descriptor.context_padding == 0.10
    assert descriptor.interpolation == "bilinear_antialias_true"
    assert descriptor.canonical_frame_version == "exif_visual_rgb_v1"
    assert descriptor.normalization_mean == (0.485, 0.456, 0.406)
    assert descriptor.normalization_std == (0.229, 0.224, 0.225)
    assert hash(descriptor) == hash(ClassifierPreprocessDescriptor())
    assert len(descriptor.sha256()) == 64


def test_crop_pair_rejects_noncanonical_or_out_of_bounds_input():
    with pytest.raises(ValueError, match="CanonicalImage"):
        build_crop_pair(Image.new("RGB", (10, 10)), Box(0, 0, 5, 5))

    with pytest.raises(ValueError, match="canonical visual"):
        build_crop_pair(canonicalize_image(Image.new("RGB", (10, 10))), Box(8, 8, 5, 5))
