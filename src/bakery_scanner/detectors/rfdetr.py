"""RF-DETR-L adapter that preserves the scanner's canonical bread proposal contract."""

from __future__ import annotations

import hashlib
import math
import os
from numbers import Integral
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

from bakery_scanner.contracts import Box, BreadProposal


_PRODUCT_CLASS_ID = 0
_PRODUCT_CLASS_NAME = "product"
_BACKGROUND_CLASS_ID = 1
_BACKGROUND_CLASS_NAME = "__background__"
_SOURCE = "rfdetr_large_bakery_v1"


class RFDetrRunner:
    """Normalize a loaded RF-DETR-L model into canonical bread proposals."""

    def __init__(self, model: Any, *, score_threshold: float, source: str = _SOURCE) -> None:
        if not hasattr(model, "predict"):
            raise TypeError("RF-DETR backend must provide predict()")
        if isinstance(score_threshold, bool) or not isinstance(score_threshold, (int, float)):
            raise ValueError("score_threshold must be a finite number in [0, 1]")
        if not math.isfinite(float(score_threshold)) or not 0.0 <= float(score_threshold) <= 1.0:
            raise ValueError("score_threshold must be a finite number in [0, 1]")
        if not isinstance(source, str) or not source:
            raise ValueError("source must be a non-empty detector identifier")
        self._model = model
        self._score_threshold = float(score_threshold)
        self.source = source

    @classmethod
    def from_model(cls, model: Any, *, score_threshold: float, source: str = _SOURCE) -> "RFDetrRunner":
        return cls(model, score_threshold=score_threshold, source=source)

    @classmethod
    def load(
        cls,
        checkpoint: str | Path,
        *,
        score_threshold: float,
        source: str = _SOURCE,
        device: str = "cuda",
        model_factory: Callable[..., Any] | None = None,
        expected_sha256: str | None = None,
    ) -> "RFDetrRunner":
        checkpoint_path = Path(checkpoint).resolve()
        if not checkpoint_path.is_file():
            raise ValueError(f"RF-DETR checkpoint is missing: {checkpoint_path}")
        with _CheckpointBinding(checkpoint_path, expected_sha256, device):
            if model_factory is None:
                try:
                    from rfdetr import RFDETRLarge
                except ImportError as error:
                    raise RuntimeError("RF-DETR is required for RFDetrRunner.load()") from error
                model_factory = RFDETRLarge
            model = model_factory(
                pretrain_weights=str(checkpoint_path), num_classes=1, device=device
            )
        return cls(
            model,
            score_threshold=score_threshold,
            source=source,
        )

    def predict(self, image_id: int, image: Image.Image) -> tuple[BreadProposal, ...]:
        if not isinstance(image, Image.Image) or image.mode != "RGB":
            raise ValueError("RF-DETR inputs must be canonical RGB PIL images")
        output = self._model.predict(
            image,
            threshold=self._score_threshold,
            include_source_image=False,
        )
        if isinstance(output, list):
            if len(output) != 1:
                raise ValueError("single-image RF-DETR inference must return one result")
            output = output[0]
        try:
            boxes = np.asarray(output.xyxy)
            scores = np.asarray(output.confidence)
            classes = np.asarray(output.class_id)
            names = np.asarray(output.data["class_name"])
        except (AttributeError, KeyError, TypeError) as error:
            raise ValueError("malformed RF-DETR output fields") from error
        if boxes.ndim != 2 or boxes.shape[1:] != (4,):
            raise ValueError("RF-DETR xyxy must have shape (N, 4)")
        count = boxes.shape[0]
        if scores.shape != (count,) or classes.shape != (count,) or names.shape != (count,):
            raise ValueError("RF-DETR output field length mismatch")
        if not np.issubdtype(boxes.dtype, np.number) or not np.issubdtype(scores.dtype, np.number):
            raise ValueError("RF-DETR coordinates and scores must be numeric")
        if not np.all(np.isfinite(boxes)) or not np.all(np.isfinite(scores)):
            raise ValueError("RF-DETR coordinates and scores must be finite")

        width, height = image.size
        proposals: list[BreadProposal] = []
        for xyxy, score, class_id, class_name in zip(boxes.astype(float, copy=False), scores, classes, names, strict=True):
            if isinstance(class_id, (bool, np.bool_)) or not isinstance(class_id, Integral):
                raise ValueError("RF-DETR class id must be an integer")
            score_value = float(score)
            if not 0.0 <= score_value <= 1.0:
                raise ValueError("RF-DETR score must lie in [0, 1]")
            class_value = int(class_id)
            if class_value == _BACKGROUND_CLASS_ID and str(class_name) == _BACKGROUND_CLASS_NAME:
                continue
            if class_value != _PRODUCT_CLASS_ID or str(class_name) != _PRODUCT_CLASS_NAME:
                raise ValueError(f"unknown RF-DETR class: id={class_id!r}, name={class_name!r}")
            x1, y1, x2, y2 = (float(value) for value in xyxy)
            clipped_x1 = min(max(x1, 0.0), float(width))
            clipped_y1 = min(max(y1, 0.0), float(height))
            clipped_x2 = min(max(x2, 0.0), float(width))
            clipped_y2 = min(max(y2, 0.0), float(height))
            if clipped_x2 <= clipped_x1 or clipped_y2 <= clipped_y1:
                continue
            proposals.append(
                BreadProposal(
                    image_id=image_id,
                    source=self.source,
                    score=score_value,
                    box=Box(clipped_x1, clipped_y1, clipped_x2 - clipped_x1, clipped_y2 - clipped_y1),
                    image_width=width,
                    image_height=height,
                )
            )
        return tuple(sorted(proposals, key=lambda item: (-item.score, item.box.y, item.box.x, item.box.height, item.box.width)))


def _require_checkpoint_sha256(path: Path, expected: str) -> None:
    _validate_checkpoint_sha256(expected)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    except OSError as exc:
        raise ValueError(f"RF-DETR checkpoint is unavailable: {path}") from exc
    if digest.hexdigest() != expected:
        raise ValueError("RF-DETR checkpoint SHA-256 mismatch")


def _validate_checkpoint_sha256(expected: str) -> None:
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise ValueError("RF-DETR checkpoint SHA-256 is invalid")


class _CheckpointBinding:
    """Keep a verified path-based checkpoint immutable while a backend opens it.

    Windows uses a kernel handle that permits concurrent reads but denies writes
    and deletion.  POSIX cannot apply that share mode to a pathname; CPU loads
    retain the adjacent pre/post digest check, while CUDA evidence loads fail
    closed there rather than imply an OS-enforced binding that does not exist.
    """

    def __init__(self, path: Path, expected_sha256: str | None, device: str) -> None:
        self.path = path
        self.expected_sha256 = expected_sha256
        self.device = device
        self._handle: int | None = None

    def __enter__(self) -> "_CheckpointBinding":
        if str(self.device).lower().startswith("cuda") and self.expected_sha256 is None:
            raise ValueError("CUDA evidence checkpoint requires SHA-256")
        if self.expected_sha256 is None:
            return self
        _validate_checkpoint_sha256(self.expected_sha256)
        if os.name == "nt":
            self._handle = _open_windows_read_binding(self.path)
        elif str(self.device).lower().startswith("cuda"):
            raise ValueError("CUDA evidence checkpoint binding requires Windows share-deny locking")
        _require_checkpoint_sha256(self.path, self.expected_sha256)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if self.expected_sha256 is not None and exc_type is None:
                _require_checkpoint_sha256(self.path, self.expected_sha256)
        finally:
            if self._handle is not None:
                _close_windows_handle(self._handle)
                self._handle = None


class VerifiedPathBindings:
    """Bind a declared artifact set through a path-based backend construction."""

    def __init__(
        self,
        entries: tuple[tuple[Path, str, str], ...],
        *,
        device: str,
    ) -> None:
        normalized: dict[Path, tuple[str, str]] = {}
        for raw_path, expected, label in entries:
            path = Path(raw_path).resolve()
            _validate_checkpoint_sha256(expected)
            if path in normalized and normalized[path][0] != expected:
                raise ValueError("artifact binding path-set has conflicting digests")
            normalized[path] = (expected, label)
        if not normalized:
            raise ValueError("artifact binding path-set is empty")
        self._entries = tuple(
            (path, expected, label)
            for path, (expected, label) in sorted(normalized.items(), key=lambda item: str(item[0]))
        )
        self.device = device
        self._handles: list[int] = []

    def __enter__(self) -> "VerifiedPathBindings":
        cuda = str(self.device).lower().startswith("cuda")
        if cuda and os.name != "nt":
            raise ValueError("CUDA evidence artifact binding requires Windows share-deny locking")
        try:
            if os.name == "nt":
                self._handles = [_open_windows_read_binding(path) for path, _, _ in self._entries]
            for path, expected, label in self._entries:
                _require_checkpoint_sha256(path, expected)
        except Exception:
            self._close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None:
                for path, expected, _label in self._entries:
                    _require_checkpoint_sha256(path, expected)
        finally:
            self._close()

    def _close(self) -> None:
        while self._handles:
            _close_windows_handle(self._handles.pop())


def _open_windows_read_binding(path: Path) -> int:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    )
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ: explicitly deny write and delete
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle is None or handle == invalid:
        raise ValueError("RF-DETR checkpoint share-deny binding could not be acquired")
    return int(handle)


def _close_windows_handle(handle: int) -> None:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.CloseHandle(ctypes.c_void_p(handle)):
        raise OSError(ctypes.get_last_error(), "CloseHandle failed for RF-DETR checkpoint")
