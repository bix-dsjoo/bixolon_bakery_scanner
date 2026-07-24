"""Command boundary and strict output parsing for the pinned D-FINE checkout."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bakery_scanner.contracts import Box, BreadProposal

_SCORE_FLOOR = 0.001
_PROPOSAL_LIMIT = 30


def parse_dfine_output(
    image_id: int,
    image_size: tuple[int, int],
    labels: Sequence[int],
    boxes: Sequence[Sequence[float]],
    scores: Sequence[float],
    source: str,
) -> tuple[BreadProposal, ...]:
    """Convert D-FINE COCO-style xyxy output into bounded bread proposals."""
    return _parse_xyxy(image_id, image_size, labels, boxes, scores, source)


class DFineRunner:
    """Thin command-backed adapter; importing D-FINE remains isolated to its venv."""

    def __init__(self, command_runner: Callable[[tuple[str, ...]], dict[str, Any]] | None = None) -> None:
        self._command_runner = command_runner or _subprocess_runner

    def train(self, config: str | Path, output: str | Path) -> dict[str, Any]:
        return self._command_runner(("dfine-train", "--config", str(config), "--output", str(output)))

    def predict(self, model: str | Path, image: str | Path, *, image_id: int, image_size: tuple[int, int], source: str) -> tuple[BreadProposal, ...]:
        payload = self._command_runner(("dfine-predict", "--model", str(model), "--image", str(image)))
        return parse_dfine_output(image_id, image_size, payload["labels"], payload["boxes"], payload["scores"], source)

    def export_onnx(self, model: str | Path, output: str | Path) -> dict[str, Any]:
        return self._command_runner(("dfine-export-onnx", "--model", str(model), "--output", str(output)))


def _parse_xyxy(image_id: int, image_size: tuple[int, int], labels: Sequence[int], boxes: Sequence[Sequence[float]], scores: Sequence[float], source: str) -> tuple[BreadProposal, ...]:
    width, height = image_size
    if width <= 0 or height <= 0 or not (len(labels) == len(boxes) == len(scores)):
        raise ValueError("prediction arrays and image dimensions must be valid")
    candidates: list[BreadProposal] = []
    seen: set[tuple[float, float, float, float]] = set()
    for label, xyxy, score in zip(labels, boxes, scores, strict=True):
        if label != 0:
            raise ValueError("prediction class must be D-FINE class 0/bread")
        if len(xyxy) != 4:
            raise ValueError("prediction coordinates must contain four values")
        x1, y1, x2, y2 = (float(value) for value in xyxy)
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("prediction coordinates must be valid xyxy within image bounds")
        if score < _SCORE_FLOOR:
            continue
        identity = (x1, y1, x2, y2)
        if identity in seen:
            raise ValueError("duplicate prediction coordinates")
        seen.add(identity)
        candidates.append(BreadProposal(image_id, source, float(score), Box(x1, y1, x2 - x1, y2 - y1), width, height))
    return tuple(sorted(candidates, key=lambda row: (-row.score, row.box.y, row.box.x, row.box.height, row.box.width))[:_PROPOSAL_LIMIT])


def _subprocess_runner(command: tuple[str, ...]) -> dict[str, Any]:
    raise RuntimeError(f"D-FINE command runner is not configured: {' '.join(command)}")
