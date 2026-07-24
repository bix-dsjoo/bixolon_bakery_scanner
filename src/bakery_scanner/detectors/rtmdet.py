"""Command boundary and strict output parsing for the pinned RTMDet checkout."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bakery_scanner.contracts import BreadProposal
from bakery_scanner.detectors.dfine import _parse_xyxy, _subprocess_runner


def parse_rtmdet_output(image_id: int, image_size: tuple[int, int], labels: Sequence[int], boxes: Sequence[Sequence[float]], scores: Sequence[float], source: str) -> tuple[BreadProposal, ...]:
    """Convert MMDetection xyxy results into canonical one-class proposals."""
    return _parse_xyxy(image_id, image_size, labels, boxes, scores, source)


class RTMDetRunner:
    def __init__(self, command_runner: Callable[[tuple[str, ...]], dict[str, Any]] | None = None) -> None:
        self._command_runner = command_runner or _subprocess_runner

    def train(self, config: str | Path, output: str | Path) -> dict[str, Any]:
        return self._command_runner(("rtmdet-train", "--config", str(config), "--work-dir", str(output)))

    def predict(self, model: str | Path, image: str | Path, *, image_id: int, image_size: tuple[int, int], source: str) -> tuple[BreadProposal, ...]:
        payload = self._command_runner(("rtmdet-predict", "--model", str(model), "--image", str(image)))
        return parse_rtmdet_output(image_id, image_size, payload["labels"], payload["boxes"], payload["scores"], source)

    def export_onnx(self, model: str | Path, output: str | Path) -> dict[str, Any]:
        return self._command_runner(("rtmdet-export-onnx", "--model", str(model), "--output", str(output)))
