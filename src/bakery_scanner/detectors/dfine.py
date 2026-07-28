"""Command boundary and strict output parsing for the pinned D-FINE checkout."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.data.preprocess import CanonicalImage

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

    def __init__(self, command_runner: Callable[[tuple[str, ...]], dict[str, Any]] | None = None, gpu_probe: Callable[[], tuple[bool, str]] | None = None) -> None:
        self._command_runner = command_runner or _subprocess_runner
        self._gpu_probe = gpu_probe or _default_gpu_probe

    def train(self, config: str | Path, output: str | Path, *, device: str = "cuda:0") -> dict[str, Any]:
        _require_rtx_5080(device, self._gpu_probe)
        return self._command_runner(("dfine-train", "--config", str(config), "--output", str(output), "--device", device))

    def predict(
        self,
        model: str | Path,
        image: str | Path | CanonicalImage,
        *,
        image_id: int,
        image_size: tuple[int, int] | None = None,
        source: str,
    ) -> tuple[BreadProposal, ...]:
        _require_rtx_5080("cuda:0", self._gpu_probe)
        if isinstance(image, CanonicalImage):
            if image_size is not None and image_size != image.visual_size:
                raise ValueError("D-FINE image_size must match canonical visual size")
            return self._predict_canonical(model, image, image_id=image_id, source=source)
        if image_size is None:
            raise ValueError("D-FINE image_size is required for an encoded image path")
        return self._predict_path(model, image, image_id=image_id, image_size=image_size, source=source)

    def _predict_canonical(
        self,
        model: str | Path,
        frame: CanonicalImage,
        *,
        image_id: int,
        source: str,
    ) -> tuple[BreadProposal, ...]:
        with NamedTemporaryFile(suffix=".png", delete=False) as handle:
            materialized = Path(handle.name)
        try:
            frame.image.save(materialized, format="PNG")
            return self._predict_path(
                model,
                materialized,
                image_id=image_id,
                image_size=frame.visual_size,
                source=source,
            )
        finally:
            materialized.unlink(missing_ok=True)

    def _predict_path(
        self,
        model: str | Path,
        image: str | Path,
        *,
        image_id: int,
        image_size: tuple[int, int],
        source: str,
    ) -> tuple[BreadProposal, ...]:
        payload = self._command_runner(("dfine-predict", "--model", str(model), "--image", str(image), "--device", "cuda:0"))
        return parse_dfine_output(image_id, image_size, payload["labels"], payload["boxes"], payload["scores"], source)

    def export_onnx(self, model: str | Path, output: str | Path) -> dict[str, Any]:
        _require_rtx_5080("cuda:0", self._gpu_probe)
        return self._command_runner(("dfine-export-onnx", "--model", str(model), "--output", str(output), "--device", "cuda:0"))


class _PersistentTransport(Protocol):
    """One request/response exchange with a preloaded D-FINE worker."""

    def request(self, payload: dict[str, object]) -> dict[str, Any]: ...


class JsonLineDFineTransport:
    """Synchronous JSONL bridge to a preloaded D-FINE venv worker."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        process_factory: Callable[..., Any] | None = None,
    ) -> None:
        if not command or any(not isinstance(value, str) or not value for value in command):
            raise ValueError("D-FINE worker command must be a non-empty string tuple")
        factory = process_factory or subprocess.Popen
        self._process = factory(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("D-FINE worker requires stdin and stdout pipes")

    def request(self, payload: dict[str, object]) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) != {"image", "image_id"}:
            raise ValueError("D-FINE worker request requires image and image_id")
        if not isinstance(payload["image"], str) or not payload["image"] or type(payload["image_id"]) is not int or payload["image_id"] <= 0:
            raise ValueError("D-FINE worker request image fields are invalid")
        if self._process.poll() is not None:
            raise RuntimeError("D-FINE worker exited before processing a request")
        self._process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise RuntimeError("D-FINE worker returned no response")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("D-FINE worker response is not valid JSON") from exc
        if not isinstance(response, dict):
            raise RuntimeError("D-FINE worker response must be an object")
        if "error" in response:
            raise RuntimeError(f"D-FINE worker inference failed: {response['error']}")
        return response

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()


class PersistentDFineRunner:
    """Detector adapter backed by one already-warm D-FINE process.

    The transport owns process startup and its checkpoint lifetime.  This
    boundary keeps D-FINE imports in the pinned environment while ensuring an
    E2E image request does not reload model weights.
    """

    def __init__(
        self,
        transport: _PersistentTransport,
        *,
        source: str,
        gpu_probe: Callable[[], tuple[bool, str]] | None = None,
    ) -> None:
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a non-empty detector identifier")
        self._transport = transport
        self.source = source
        self._gpu_probe = gpu_probe or _default_gpu_probe

    def predict(self, image_id: int, image: CanonicalImage) -> tuple[BreadProposal, ...]:
        _require_rtx_5080("cuda:0", self._gpu_probe)
        if not isinstance(image, CanonicalImage):
            raise TypeError("persistent D-FINE inference requires a CanonicalImage")
        with NamedTemporaryFile(suffix=".png", delete=False) as handle:
            materialized = Path(handle.name)
        try:
            image.image.save(materialized, format="PNG")
            payload = self._transport.request({"image": str(materialized), "image_id": image_id})
            if not isinstance(payload, dict):
                raise TypeError("persistent D-FINE transport must return an object")
            return parse_dfine_output(
                image_id,
                image.visual_size,
                payload["labels"],
                payload["boxes"],
                payload["scores"],
                self.source,
            )
        finally:
            materialized.unlink(missing_ok=True)


def _require_rtx_5080(device: str, probe: Callable[[], tuple[bool, str]]) -> None:
    if device.lower() != "cuda:0":
        raise ValueError("GPU-only project requires RTX 5080 device cuda:0")
    available, name = probe()
    if not available or "RTX 5080" not in name:
        raise RuntimeError("RTX 5080 CUDA device 0 is required")


def _default_gpu_probe() -> tuple[bool, str]:
    import torch
    return torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""


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
