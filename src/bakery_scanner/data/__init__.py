"""COCO staging, full-frame normalization, and grouped split helpers."""

from .coco import CocoSource, StagedDataset, load_sources, stage_single_class_dataset
from .folds import FoldManifest, build_scene_folds
from .preprocess import NormalizedCapture, normalize_capture

__all__ = [
    "CocoSource",
    "FoldManifest",
    "NormalizedCapture",
    "StagedDataset",
    "build_scene_folds",
    "load_sources",
    "normalize_capture",
    "stage_single_class_dataset",
]
