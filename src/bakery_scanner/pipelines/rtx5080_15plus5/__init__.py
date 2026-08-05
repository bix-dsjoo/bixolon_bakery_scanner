"""RTX 5080 15+5 static candidate pipeline contracts."""

from .admission import AdmissionError, AdmissionReceipt, RuntimeIdentity, admit_candidate
from .config import CandidateConfig, load_candidate_config
from .contracts import ScanResult

__all__ = [
    "AdmissionError", "AdmissionReceipt", "CandidateConfig", "RuntimeIdentity",
    "ScanResult", "admit_candidate", "load_candidate_config",
]
