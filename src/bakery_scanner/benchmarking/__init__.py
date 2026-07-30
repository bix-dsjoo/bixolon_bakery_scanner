"""Stable CPU benchmark reporting namespace."""

from bakery_scanner.e2e.cpu_benchmark_report import build_cpu_benchmark_report
from bakery_scanner.e2e.rfdetr_cpu import (
    summarize_profile_stages,
    summarize_profiles,
)

__all__ = [
    "build_cpu_benchmark_report",
    "summarize_profile_stages",
    "summarize_profiles",
]
