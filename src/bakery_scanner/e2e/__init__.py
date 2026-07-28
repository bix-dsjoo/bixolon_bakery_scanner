"""End-to-end result contracts, source labels, evaluation, and benchmarking."""

from .contracts import FinalObject, SkuGroundTruth
from .cpu_smoke import run_cpu_smoke, select_smoke_images, validate_cpu_smoke_request
from .ground_truth import load_source_sku_ground_truth

__all__ = (
    "FinalObject",
    "SkuGroundTruth",
    "load_source_sku_ground_truth",
    "run_cpu_smoke",
    "select_smoke_images",
    "validate_cpu_smoke_request",
)
