"""Fail-closed static RF-DETR-L TensorRT adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from bakery_scanner.contracts import BreadProposal


_SOURCE = "rfdetr_l_bread_gpu_fp16_v1"


class DetectorTensorRtError(RuntimeError):
    """Detector output or CUDA execution cannot produce a trusted scan."""


class DeviceTensor(Protocol):
    shape: tuple[int, ...]
    dtype: str


class CudaStream(Protocol):
    def synchronize(self) -> None: ...


class EngineSession(Protocol):
    def execute(
        self, bindings: Mapping[str, DeviceTensor], stream: CudaStream
    ) -> Mapping[str, DeviceTensor]: ...


class DetectorInputBuffer(DeviceTensor, Protocol):
    def stage_frame(
        self, frame: "CanonicalGpuFrame", *, stream: CudaStream
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CanonicalGpuFrame:
    width: int
    height: int
    exif_orientation: int
    device_rgb: DeviceTensor
    canonical_frame_version: str

    def __post_init__(self) -> None:
        if (
            type(self.width) is not int
            or self.width < 1
            or type(self.height) is not int
            or self.height < 1
        ):
            raise ValueError("canonical GPU frame dimensions must be positive integers")
        if (
            type(self.exif_orientation) is not int
            or not 1 <= self.exif_orientation <= 8
        ):
            raise ValueError("canonical GPU frame requires an EXIF orientation")
        if self.canonical_frame_version != "exif_visual_rgb_v1":
            raise ValueError("canonical GPU frame version is invalid")
        if (
            getattr(self.device_rgb, "shape", None) != (self.height, self.width, 3)
            or getattr(self.device_rgb, "dtype", None) != "uint8"
        ):
            raise ValueError(
                "canonical GPU frame must be an HWC uint8 device RGB tensor"
            )


DetectorDecoder = Callable[
    [Mapping[str, DeviceTensor], CanonicalGpuFrame], tuple[BreadProposal, ...]
]


class RfDetrTensorRtRunner:
    """Execute exactly one admitted static detector engine invocation."""

    def __init__(
        self,
        session: EngineSession,
        stream: CudaStream,
        input_buffer: DetectorInputBuffer,
        decoder: DetectorDecoder,
    ) -> None:
        _tensor(input_buffer, (1, 3, 640, 640), "float16", "RF-DETR input")
        if not callable(decoder):
            raise ValueError("RF-DETR output decoder is required")
        self._session, self._stream, self._input, self._decoder = (
            session,
            stream,
            input_buffer,
            decoder,
        )

    def detect(self, frame: CanonicalGpuFrame) -> tuple[BreadProposal, ...]:
        if not isinstance(frame, CanonicalGpuFrame):
            raise DetectorTensorRtError("RF-DETR requires the canonical GPU frame")
        try:
            self._input.stage_frame(frame, stream=self._stream)
            outputs = self._session.execute({"images": self._input}, self._stream)
            if not isinstance(outputs, Mapping) or set(outputs) != {"boxes", "scores"}:
                raise ValueError("RF-DETR returned wrong output bindings")
            _tensor(outputs["boxes"], (1, 300, 4), "float16", "RF-DETR boxes")
            _tensor(outputs["scores"], (1, 300), "float16", "RF-DETR scores")
            proposals = self._decoder(outputs, frame)
            _validate_proposals(proposals, frame)
            return proposals
        except DetectorTensorRtError:
            raise
        except Exception as exc:
            raise DetectorTensorRtError("RF-DETR TensorRT inference failed") from exc


def _validate_proposals(value: object, frame: CanonicalGpuFrame) -> None:
    if not isinstance(value, tuple) or any(
        not isinstance(item, BreadProposal) for item in value
    ):
        raise DetectorTensorRtError(
            "RF-DETR decoder must return an immutable proposal tuple"
        )
    for item in value:
        if (
            item.source != _SOURCE
            or item.image_width != frame.width
            or item.image_height != frame.height
        ):
            raise DetectorTensorRtError(
                "RF-DETR proposal provenance or canonical dimensions are invalid"
            )
    keys = tuple(
        (
            item.box.y + item.box.height / 2,
            item.box.x + item.box.width / 2,
            item.box.x,
            item.box.y,
        )
        for item in value
    )
    if keys != tuple(sorted(keys)):
        raise DetectorTensorRtError(
            "RF-DETR proposals must use deterministic canonical order"
        )


def _tensor(value: object, shape: tuple[int, ...], dtype: str, label: str) -> None:
    if getattr(value, "shape", None) != shape or getattr(value, "dtype", None) != dtype:
        raise ValueError(f"{label} must have static shape {shape} and dtype {dtype}")
