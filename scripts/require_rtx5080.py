"""Fail fast unless this process is bound to CUDA device 0 on an RTX 5080."""

from __future__ import annotations

import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
import torch

if os.environ.get("CUDA_VISIBLE_DEVICES") != "0":
    raise SystemExit("GPU-only contract requires CUDA_VISIBLE_DEVICES=0")
if not torch.cuda.is_available() or torch.cuda.current_device() != 0:
    raise SystemExit("GPU-only contract requires available CUDA device 0")
if "RTX 5080" not in torch.cuda.get_device_name(0):
    raise SystemExit("GPU-only contract requires an RTX 5080 on device 0")
