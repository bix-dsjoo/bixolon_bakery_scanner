"""Static TensorRT classifier adapters for the RTX 5080 candidate.

The adapters own only static batching and device-binding validation.  Crop
creation, calibrated gates, and fusion remain separate pipeline boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping, Protocol, Sequence


_SKU_COUNT = 20


class TensorRtInferenceError(RuntimeError):
    """A static TensorRT invocation failed; callers must abort the scan."""


class DeviceTensor(Protocol):
    shape: tuple[int, ...]
    dtype: str


class CudaStream(Protocol):
    def synchronize(self) -> None: ...


class EngineSession(Protocol):
    def execute(
        self, bindings: Mapping[str, DeviceTensor], stream: CudaStream
    ) -> Mapping[str, DeviceTensor]: ...


class StaticInputBuffer(DeviceTensor, Protocol):
    def stage_rows(
        self,
        rows: Sequence["GpuCrop"],
        *,
        valid_mask: tuple[bool, ...],
        stream: CudaStream,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class GpuCrop:
    tensor: DeviceTensor
    object_order: int

    def __post_init__(self) -> None:
        _tensor(self.tensor, (3, 224, 224), "float16", "GPU crop")
        if type(self.object_order) is not int or self.object_order < 1:
            raise ValueError("GPU crop object_order must be a positive integer")


@dataclass(frozen=True, slots=True)
class GpuCropPair:
    tight: GpuCrop
    context: GpuCrop
    object_order: int

    def __post_init__(self) -> None:
        if not isinstance(self.tight, GpuCrop) or not isinstance(self.context, GpuCrop):
            raise ValueError("GPU crop pair requires tight and context GPU crops")
        if (
            self.tight.object_order != self.object_order
            or self.context.object_order != self.object_order
        ):
            raise ValueError("GPU crop pair object order must align")


@dataclass(frozen=True, slots=True)
class RepVitBatchEvidence:
    tight_scores: tuple[float, ...]
    context_scores: tuple[float, ...]

    def __post_init__(self) -> None:
        _scores(self.tight_scores, "RepViT tight scores", probabilities=True)
        _scores(self.context_scores, "RepViT context scores", probabilities=True)


@dataclass(frozen=True, slots=True)
class DinoBatchEvidence:
    global_scores: tuple[float, ...]
    candidate_sku_ids: tuple[int, ...]
    local_scores: tuple[float, ...]
    product_patch_count: int
    product_patch_ratio: float

    def __post_init__(self) -> None:
        _scores(self.global_scores, "DINO global scores", probabilities=False)
        if (
            not isinstance(self.candidate_sku_ids, tuple)
            or not 1 <= len(self.candidate_sku_ids) <= 8
            or len(set(self.candidate_sku_ids)) != len(self.candidate_sku_ids)
            or any(
                type(value) is not int or value not in range(1, 21)
                for value in self.candidate_sku_ids
            )
        ):
            raise ValueError("DINO candidate SKU IDs are invalid")
        if not isinstance(self.local_scores, tuple) or len(self.local_scores) != len(
            self.candidate_sku_ids
        ):
            raise ValueError("DINO local scores must align with candidates")
        if any(not _finite(value) for value in self.local_scores):
            raise ValueError("DINO local scores must be finite")
        if type(self.product_patch_count) is not int or self.product_patch_count < 1:
            raise ValueError("DINO product patch count must be positive")
        if (
            not _finite(self.product_patch_ratio)
            or not 0 <= self.product_patch_ratio <= 1
        ):
            raise ValueError("DINO product patch ratio must be within [0, 1]")


RepVitDecoder = Callable[
    [Mapping[str, DeviceTensor], tuple[int, ...]], tuple[RepVitBatchEvidence, ...]
]
DinoDecoder = Callable[
    [Mapping[str, DeviceTensor], tuple[int, ...]], tuple[DinoBatchEvidence, ...]
]


class RepVitTensorRtRunner:
    """Execute ordered seven-object / fourteen-row static chunks."""

    def __init__(
        self,
        session: EngineSession,
        stream: CudaStream,
        input_buffer: StaticInputBuffer,
        decoder: RepVitDecoder,
    ) -> None:
        _tensor(input_buffer, (14, 3, 224, 224), "float16", "RepViT input")
        if not callable(decoder):
            raise ValueError("RepViT output decoder is required")
        self._session = session
        self._stream = stream
        self._input = input_buffer
        self._decoder = decoder

    def score_pairs(
        self, crop_pairs: Sequence[GpuCropPair]
    ) -> tuple[RepVitBatchEvidence, ...]:
        pairs = tuple(crop_pairs)
        _ordered((pair.object_order for pair in pairs), "RepViT crop pairs")
        result: list[RepVitBatchEvidence] = []
        for chunk_index, start in enumerate(range(0, len(pairs), 7), start=1):
            valid = pairs[start : start + 7]
            padded = valid + (valid[-1],) * (7 - len(valid))
            rows = tuple(crop for pair in padded for crop in (pair.tight, pair.context))
            valid_rows = 2 * len(valid)
            mask = tuple(index < valid_rows for index in range(14))
            try:
                self._input.stage_rows(rows, valid_mask=mask, stream=self._stream)
                outputs = self._session.execute({"crops": self._input}, self._stream)
                _exact_outputs(outputs, {"logits": ((14, 20), "float16")}, "RepViT")
                decoded = self._decoder(outputs, tuple(range(valid_rows)))
                if not isinstance(decoded, tuple) or len(decoded) != len(valid):
                    raise ValueError(
                        "RepViT decoder output does not align with valid objects"
                    )
                if any(not isinstance(item, RepVitBatchEvidence) for item in decoded):
                    raise ValueError("RepViT decoder returned malformed evidence")
            except Exception as exc:
                raise TensorRtInferenceError(
                    f"RepViT static chunk {chunk_index} failed"
                ) from exc
            result.extend(decoded)
        return tuple(result)


class DinoTensorRtRunner:
    """Execute only rejected objects in ordered seven-row static chunks."""

    def __init__(
        self,
        session: EngineSession,
        stream: CudaStream,
        input_buffer: StaticInputBuffer,
        decoder: DinoDecoder,
    ) -> None:
        _tensor(input_buffer, (7, 3, 224, 224), "float16", "DINO input")
        if not callable(decoder):
            raise ValueError("DINO output decoder is required")
        self._session = session
        self._stream = stream
        self._input = input_buffer
        self._decoder = decoder

    def score_rejections(
        self, crops: Sequence[GpuCrop]
    ) -> tuple[DinoBatchEvidence, ...]:
        ordered = tuple(crops)
        _ordered((crop.object_order for crop in ordered), "DINO crops")
        result: list[DinoBatchEvidence] = []
        for chunk_index, start in enumerate(range(0, len(ordered), 7), start=1):
            valid = ordered[start : start + 7]
            padded = valid + (valid[-1],) * (7 - len(valid))
            mask = tuple(index < len(valid) for index in range(7))
            try:
                self._input.stage_rows(padded, valid_mask=mask, stream=self._stream)
                outputs = self._session.execute({"crops": self._input}, self._stream)
                _exact_outputs(
                    outputs,
                    {
                        "global_embeddings": ((7, 384), "float16"),
                        "local_patch_tokens": ((7, 196, 384), "float16"),
                    },
                    "DINO",
                )
                valid_rows = tuple(range(len(valid)))
                decoded = self._decoder(outputs, valid_rows)
                if not isinstance(decoded, tuple) or len(decoded) != len(valid):
                    raise ValueError(
                        "DINO decoder output does not align with valid objects"
                    )
                if any(not isinstance(item, DinoBatchEvidence) for item in decoded):
                    raise ValueError("DINO decoder returned malformed evidence")
            except Exception as exc:
                raise TensorRtInferenceError(
                    f"DINO static chunk {chunk_index} failed"
                ) from exc
            result.extend(decoded)
        return tuple(result)


def _exact_outputs(
    outputs: object, expected: Mapping[str, tuple[tuple[int, ...], str]], label: str
) -> None:
    if not isinstance(outputs, Mapping) or set(outputs) != set(expected):
        raise ValueError(f"{label} engine returned wrong output bindings")
    for name, (shape, dtype) in expected.items():
        _tensor(outputs[name], shape, dtype, f"{label} {name}")


def _tensor(value: object, shape: tuple[int, ...], dtype: str, label: str) -> None:
    if getattr(value, "shape", None) != shape or getattr(value, "dtype", None) != dtype:
        raise ValueError(f"{label} must have static shape {shape} and dtype {dtype}")


def _ordered(values: Sequence[int] | object, label: str) -> None:
    sequence = tuple(values)
    if sequence != tuple(sorted(sequence)) or len(set(sequence)) != len(sequence):
        raise ValueError(f"{label} must have unique ascending object order")


def _scores(values: object, label: str, *, probabilities: bool) -> None:
    if (
        not isinstance(values, tuple)
        or len(values) != _SKU_COUNT
        or any(not _finite(value) for value in values)
    ):
        raise ValueError(f"{label} must contain 20 finite values")
    if probabilities and any(not 0 <= value <= 1 for value in values):
        raise ValueError(f"{label} must contain probabilities")


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
