"""COCO staging, full-frame normalization, and grouped split helpers."""

from .coco import CocoSource, StagedDataset, load_sources, stage_single_class_dataset
from .folds import FoldManifest, build_scene_folds
from .oof15plus5 import build_oof_folds, write_oof_manifests
from .preprocess import NormalizedCapture, normalize_capture
from .sku_scene import OofFold, SceneRecord, SkuBox, SkuSceneInventory, SourceImage, load_inventory

__all__ = [
    "CocoSource",
    "FoldManifest",
    "OofFold",
    "NormalizedCapture",
    "SceneRecord",
    "SkuBox",
    "SkuSceneInventory",
    "StagedDataset",
    "SourceImage",
    "build_oof_folds",
    "build_scene_folds",
    "load_sources",
    "load_inventory",
    "normalize_capture",
    "stage_single_class_dataset",
    "write_oof_manifests",
]
