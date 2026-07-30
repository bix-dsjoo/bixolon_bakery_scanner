"""Legacy detector adapters preserved without changing their behavior."""

from bakery_scanner.detectors.dfine import DFineRunner, PersistentDFineRunner
from bakery_scanner.detectors.rtmdet import RTMDetRunner

__all__ = ["DFineRunner", "PersistentDFineRunner", "RTMDetRunner"]
