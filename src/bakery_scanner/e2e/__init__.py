"""End-to-end result contracts, source labels, evaluation, and benchmarking."""

from .contracts import FinalObject, SkuGroundTruth
from .cpu_profile import BATCH2_E3_M3_H3_NAMES, resolve_batch2_e3_m3_h3
from .cpu_smoke import run_cpu_smoke, select_smoke_images, validate_cpu_smoke_request
from .ground_truth import load_source_sku_ground_truth

__all__ = (
    "FinalObject",
    "BATCH2_E3_M3_H3_NAMES",
    "SkuGroundTruth",
    "load_source_sku_ground_truth",
    "run_cpu_smoke",
    "resolve_batch2_e3_m3_h3",
    "select_smoke_images",
    "validate_cpu_smoke_request",
)
