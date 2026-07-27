"""Classifier contracts and configuration for the bakery SKU pipeline."""

from .config import ClassifierConfig
from .contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
    SkuCandidate,
    StageTimings,
)

__all__ = [
    "ClassificationDecision",
    "ClassifierConfig",
    "DecisionPath",
    "ModelProvenance",
    "ModelScoreVector",
    "SkuCandidate",
    "StageTimings",
]
