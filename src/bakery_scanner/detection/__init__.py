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
from .completeness_evidence import (
    CompletenessExecutionRecord,
    CompletenessProposalEvidence,
    LoadedCompletenessEvidenceBundle,
    build_completeness_execution_record,
    load_completeness_evidence_bundle,
    write_completeness_evidence_bundle,
)

__all__ = [
    "CaptureQuality", "CompletenessDecision", "CompletenessExecutionRecord",
    "CompletenessPolicy", "CompletenessProposalEvidence", "CounterfactualCase",
    "ForegroundAnalyzer", "ForegroundEvidence", "InvalidDetectorOutput",
    "LoadedCompletenessEvidenceBundle", "ReferenceForegroundAnalyzerConfig", "RFDetrRunner",
    "build_completeness_execution_record", "build_counterfactuals", "evaluate_completeness",
    "load_completeness_evidence_bundle", "write_completeness_evidence_bundle",
]
