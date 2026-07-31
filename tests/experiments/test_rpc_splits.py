"""Contract tests for leakage-safe RPC few-shot evaluation splits."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bakery_scanner.experiments.rpc_manifest import RpcCategory, RpcDatasetContract, RpcImage, RpcIndex
from bakery_scanner.experiments.rpc_splits import build_class_folds, build_scene_roles


def _image(split: str, image_id: int, category_id: int, stamp: datetime, suffix: str) -> RpcImage:
    name = stamp.strftime("%Y%m%d-%H-%M-%S-") + suffix + ".jpg"
    return RpcImage(split, image_id, f"{split}:{image_id}:{name}", Path(name), category_id, 1, "0" * 64)


@pytest.fixture
def index() -> RpcIndex:
    categories = tuple(
        RpcCategory(category_id, f"category-{category_id}", f"super-{(category_id - 1) % 4}")
        for category_id in range(1, 201)
    )
    images: list[RpcImage] = []
    image_id = 1
    start = datetime(2019, 1, 1, 9, 0, 0)
    for category_id in range(1, 201):
        for burst in range(2):
            stamp = start + timedelta(minutes=category_id * 3 + burst)
            suffix = f"difficulty-{category_id:03d}-{burst}"
            for offset in range(15):
                images.append(_image("val2019", image_id, category_id, stamp + timedelta(seconds=offset), suffix))
                image_id += 1
        images.append(_image("test2019", image_id, category_id, start, f"test-{category_id:03d}"))
        image_id += 1
    return RpcIndex(RpcDatasetContract.default(), tuple(images), (), categories)


def test_class_folds_make_each_category_novel_exactly_once(index: RpcIndex):
    folds = build_class_folds(index, split_version="rpc-v1", seed=7)
    assert len(folds) == 5
    assert all(len(fold.novel_category_ids) == 40 for fold in folds)
    assert sorted(category for fold in folds for category in fold.novel_category_ids) == list(range(1, 201))
    assert all(fold.base_category_ids == tuple(sorted(fold.base_category_ids)) for fold in folds)
    assert all(set(fold.base_category_ids).isdisjoint(fold.novel_category_ids) for fold in folds)
    assert all(len(fold.manifest_sha256) == 64 for fold in folds)


def test_class_folds_balance_each_supercategory_within_one(index: RpcIndex):
    folds = build_class_folds(index, split_version="rpc-v1", seed=7)
    for supercategory in {item.supercategory for item in index.categories}:
        counts = [sum(index.categories[category_id - 1].supercategory == supercategory for category_id in fold.novel_category_ids) for fold in folds]
        assert max(counts) - min(counts) <= 1


def test_scene_roles_keep_adjacent_burst_atomic(index: RpcIndex):
    roles = build_scene_roles(index, split_version="rpc-v1")
    assert len({(row.role, row.burst_id) for row in roles if row.split == "val2019"}) == len({row.burst_id for row in roles if row.split == "val2019"})


def test_scene_roles_keep_exact_120_second_gap_in_one_burst(index: RpcIndex):
    image = _image("val2019", 99999, 1, datetime(2019, 1, 4, 10, 0, 0), "boundary")
    adjacent = _image("val2019", 100000, 1, datetime(2019, 1, 4, 10, 2, 0), "boundary")
    roles = build_scene_roles(RpcIndex(index.contract, index.images + (image, adjacent), (), index.categories), split_version="rpc-v1")
    assert next(row.burst_id for row in roles if row.image_id == image.image_id) == next(row.burst_id for row in roles if row.image_id == adjacent.image_id)


def test_scene_roles_separate_gap_greater_than_120_seconds(index: RpcIndex):
    first = _image("test2019", 99999, 1, datetime(2019, 1, 5, 10, 0, 0), "gap")
    second = _image("test2019", 100000, 1, datetime(2019, 1, 5, 10, 2, 1), "gap")
    roles = build_scene_roles(RpcIndex(index.contract, index.images + (first, second), (), index.categories), split_version="rpc-v1")
    assert next(row.burst_id for row in roles if row.image_id == first.image_id) != next(row.burst_id for row in roles if row.image_id == second.image_id)


def test_scene_roles_reject_invalid_checkout_name(index: RpcIndex):
    invalid = RpcImage("val2019", 99999, "bad", Path("bad.jpg"), 1, 1, "0" * 64)
    with pytest.raises(ValueError, match="invalid checkout name"):
        build_scene_roles(RpcIndex(index.contract, index.images + (invalid,), (), index.categories), split_version="rpc-v1")


def test_scene_roles_lock_every_test_image(index: RpcIndex):
    roles = build_scene_roles(index, split_version="rpc-v1")
    assert {row.role for row in roles if row.split == "test2019"} == {"locked_acceptance"}


def test_scene_roles_reject_impossible_category_coverage(index: RpcIndex):
    images = tuple(image for image in index.images if not (image.split == "val2019" and image.category_id == 1 and image.source_path.name.endswith("-1.jpg")))
    with pytest.raises(ValueError, match="coverage"):
        build_scene_roles(RpcIndex(index.contract, images, (), index.categories), split_version="rpc-v1")


def test_split_builders_are_deterministic(index: RpcIndex):
    assert build_class_folds(index, split_version="rpc-v1", seed=7) == build_class_folds(index, split_version="rpc-v1", seed=7)
    assert build_scene_roles(index, split_version="rpc-v1") == build_scene_roles(index, split_version="rpc-v1")
