"""Stable detection namespace.

New code imports canonical detection adapters from this package. The historical
``bakery_scanner.detectors`` namespace remains available for compatibility.
"""

from .rfdetr import RFDetrRunner
from .completeness import (
    CaptureQuality,
    CompletenessDecision,
    CompletenessPolicy,
    CounterfactualCase,
    ForegroundAnalyzer,
    ForegroundEvidence,
    InvalidDetectorOutput,
    ReferenceForegroundAnalyzerConfig,
    build_counterfactuals,
    evaluate_completeness,
)

__all__ = [
    "CaptureQuality", "CompletenessDecision", "CompletenessPolicy", "CounterfactualCase",
    "ForegroundAnalyzer", "ForegroundEvidence", "InvalidDetectorOutput",
    "ReferenceForegroundAnalyzerConfig", "RFDetrRunner", "build_counterfactuals",
    "evaluate_completeness",
]
