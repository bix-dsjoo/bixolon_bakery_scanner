"""Stable CPU benchmark reporting namespace."""

from bakery_scanner.e2e.cpu_benchmark_report import (
    build_benchmark_report as build_cpu_benchmark_report,
)
from bakery_scanner.e2e.rfdetr_cpu import (
    summarize_profile_stages,
    summarize_profiles,
)
from bakery_scanner.benchmarking.gpu_worker_receipt import (
    GROUPS as GPU_RECEIPT_GROUPS,
    MINIMUM_GROUP_OBSERVATIONS,
    STAGES as GPU_RECEIPT_STAGES,
    GpuSample,
    GpuWorkerReceipt,
    build_receipt as build_gpu_worker_receipt,
    summarize_ms as summarize_gpu_ms,
)

__all__ = [
    "build_cpu_benchmark_report",
    "GPU_RECEIPT_GROUPS",
    "GPU_RECEIPT_STAGES",
    "MINIMUM_GROUP_OBSERVATIONS",
    "GpuSample",
    "GpuWorkerReceipt",
    "build_gpu_worker_receipt",
    "summarize_gpu_ms",
    "summarize_profile_stages",
    "summarize_profiles",
]
