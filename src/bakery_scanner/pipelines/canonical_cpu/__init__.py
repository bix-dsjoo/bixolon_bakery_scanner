"""Canonical deterministic CPU pipeline contract.

The runtime remains composed from the tested RF-DETR and classification
adapters. This namespace is the stable import boundary for future orchestration
without moving the established compatibility modules.
"""

CANONICAL_PIPELINE_ID = "rfdetr_l_repvit_m1_dinov3_vits16_cpu"
CANONICAL_CONFIG = "configs/pipelines/canonical_cpu.yaml"

__all__ = ["CANONICAL_CONFIG", "CANONICAL_PIPELINE_ID"]
