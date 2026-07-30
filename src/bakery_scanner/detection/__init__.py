"""Stable detection namespace.

New code imports canonical detection adapters from this package. The historical
``bakery_scanner.detectors`` namespace remains available for compatibility.
"""

from .rfdetr import RFDetrRunner

__all__ = ["RFDetrRunner"]
