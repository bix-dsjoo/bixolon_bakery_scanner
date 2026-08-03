"""Lazy online orchestration for verified bakery product crops."""

from __future__ import annotations

import hashlib
import math
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Protocol, Sequence

import torch
from PIL import Image

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import CanonicalImage, canonicalize_image

from .config import ClassifierConfig, preprocess_sha256
from .contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
    SkuCandidate,
    StageTimings,
)
from .dinov3 import DinoV3Rechecker
from .errors import DinoInferenceError
from .full_evidence import FullEvidenceRow
from .fusion_policy import FusionPolicyArtifact
from .local_bank import LocalPatchBank
from .policy import DecisionPolicy, DirectEvidence, PolicyCalibration
from .preprocess import (
    ClassifierPreprocessDescriptor,
    build_crop_pair,
    make_padded_crops_with_product_boxes,
)
from .repvit import RepVitM1Runner, RepVitPrototypeBank


_CPU_PROCESS_CONFIGURATION: tuple[int | None, int, str | tuple[int, ...]] | None = None
_CPU_PROCESS_CONFIGURATION_LOCK = RLock()


class _ScoreRunner(Protocol):
    def score(self, crops: tuple[Image.Image, ...]): ...


class _RepVitRunner(_ScoreRunner, Protocol):
    def score_with_evidence(self, crops: tuple[Image.Image, ...]): ...


class _PrototypeBank(Protocol):
    def distances(self, feature: torch.Tensor) -> tuple[float, ...]: ...


class _Clock(Protocol):
    def __call__(self) -> float: ...

    def synchronize(self) -> None: ...


class _StageTimingSink(Protocol):
    def __call__(self, timings: SerialStageTimings) -> None: ...


class _CudaClock:
    def __init__(self, device: torch.device) -> None:
        self.device = device

    def synchronize(self) -> None:
        if self.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize(self.device)

    def __call__(self) -> float:
        return time.perf_counter()


class CudaTimingCollector:
    """Deferred CUDA-event diagnostics for one request on the active stream.

    The caller owns finalization.  This keeps classifier and detector launches
    queued together and makes exactly one request-boundary synchronization the
    point at which event elapsed times are read.
    """

    def __init__(
        self,
        device: torch.device | str = "cuda:0",
        *,
        synchronize: Callable[[], None] | None = None,
    ) -> None:
        self.device = torch.device(device)
        if self.device.type != "cuda" or not torch.cuda.is_available():
            raise ValueError("CUDA event timing requires an available CUDA device")
        try:
            self._stream = torch.cuda.current_stream(self.device)
            self._ranges: list[tuple[str, Any, Any]] = []
        except Exception as exc:
            raise ValueError("CUDA event timing could not be created") from exc
        self._synchronize = synchronize or (lambda: torch.cuda.synchronize(self.device))
        self._finalized = False

    def measure(self, stage: str, action: Callable[[], Any]) -> Any:
        if self._finalized:
            raise RuntimeError("CUDA timing collector is already finalized")
        try:
            start = torch.cuda.Event(enable_timing=True)
            end = torch.cuda.Event(enable_timing=True)
            start.record(self._stream)
        except Exception as exc:
            raise ValueError("CUDA event timing could not be created") from exc
        torch.cuda.nvtx.range_push(stage)
        try:
            value = action()
        finally:
            torch.cuda.nvtx.range_pop()
        try:
            end.record(self._stream)
        except Exception as exc:
            raise ValueError("CUDA event timing could not be created") from exc
        self._ranges.append((stage, start, end))
        return value

    def finalize(self) -> dict[str, float]:
        if self._finalized:
            raise RuntimeError("CUDA timing collector is already finalized")
        try:
            self._synchronize()
            totals: dict[str, float] = {}
            for stage, start, end in self._ranges:
                elapsed = float(start.elapsed_time(end))
                if not math.isfinite(elapsed) or elapsed < 0.0:
                    raise ValueError("CUDA event elapsed time is invalid")
                totals[stage] = totals.get(stage, 0.0) + elapsed
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError("CUDA event timing could not be finalized") from exc
        self._finalized = True
        return totals


@dataclass(frozen=True, slots=True)
class BatchStageTimings:
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    total_ms: float

    def __post_init__(self) -> None:
        for value in (
            self.crop_ms,
            self.repvit_ms,
            self.dinov3_ms,
            self.fusion_ms,
            self.total_ms,
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError("batch stage timings must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class SerialStageTimings:
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float
    total_ms: float
    dino_executed: bool

    def __post_init__(self) -> None:
        for value in (
            self.crop_ms,
            self.repvit_ms,
            self.dinov3_ms,
            self.fusion_ms,
            self.total_ms,
        ):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0.0:
                raise ValueError("serial stage timings must be finite and non-negative")


def _combined_timing_sink(
    configured: _StageTimingSink | None,
    callback: _StageTimingSink | None,
) -> _StageTimingSink | None:
    if configured is None:
        return callback
    if callback is None:
        return configured

    def emit(timings: SerialStageTimings) -> None:
        configured(timings)
        callback(timings)

    return emit


@dataclass(frozen=True, slots=True)
class BatchInferenceResult:
    decisions: tuple[ClassificationDecision, ...]
    timings: BatchStageTimings
    dino_object_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        if any(not isinstance(decision, ClassificationDecision) for decision in self.decisions):
            raise ValueError("batch decisions must contain ClassificationDecision values")
        if type(self.dino_object_count) is not int or not 0 <= self.dino_object_count <= len(self.decisions):
            raise ValueError("dino_object_count must be within the decision count")


@dataclass(frozen=True, slots=True)
class TightContextRepVitEvidence:
    """Pair-aware RepViT evidence required by the static 15+5 direct gate."""

    scores: ModelScoreVector
    tight_scores: ModelScoreVector
    context_scores: ModelScoreVector
    feature: torch.Tensor
    crop_disagreement: float

    def __post_init__(self) -> None:
        if self.scores.sku_ids != self.tight_scores.sku_ids or self.scores.sku_ids != self.context_scores.sku_ids:
            raise ValueError("tight/context RepViT class order must align")
        if any(scores.model_id != "repvit_m1_15plus5_v1" or scores.score_kind != "probability" for scores in (self.scores, self.tight_scores, self.context_scores)):
            raise ValueError("tight/context evidence must use canonical RepViT probabilities")
        if tuple(self.feature.shape) != (384,) or not torch.isfinite(self.feature).all().item():
            raise ValueError("tight/context RepViT feature must have shape (384,)")
        if not math.isfinite(self.crop_disagreement) or self.crop_disagreement < 0.0:
            raise ValueError("tight/context crop disagreement must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class BenchmarkPreflightEvidence:
    repvit: int
    dinov3_global_local: int
    fusion: int


def configure_cpu_process(runtime: ClassifierRuntimeConfig) -> None:
    """Apply CPU-global runtime settings once in a dedicated worker process."""
    if runtime.device != "CPU":
        return
    requested = (
        runtime.intra_op_threads,
        runtime.inter_op_threads,
        runtime.cpu_affinity,
    )
    global _CPU_PROCESS_CONFIGURATION
    with _CPU_PROCESS_CONFIGURATION_LOCK:
        if _CPU_PROCESS_CONFIGURATION is not None:
            if _CPU_PROCESS_CONFIGURATION != requested:
                raise RuntimeError(
                    "CPU process settings are already configured; use a fresh worker process"
                )
            return
        if runtime.intra_op_threads is not None:
            torch.set_num_threads(runtime.intra_op_threads)
        torch.set_num_interop_threads(runtime.inter_op_threads)
        if runtime.cpu_affinity != "all":
            allowed_mask = _get_process_affinity_mask()
            requested_mask = sum(1 << cpu_id for cpu_id in runtime.cpu_affinity)
            if requested_mask & ~allowed_mask:
                raise ValueError("cpu_affinity includes logical CPUs outside the inherited process mask")
            _set_process_affinity_mask(requested_mask)
        _CPU_PROCESS_CONFIGURATION = requested


def _get_process_affinity_mask() -> int:
    if os.name != "nt":
        logical_cpus = os.cpu_count() or 1
        return (1 << logical_cpus) - 1
    import ctypes

    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    kernel32 = _windows_kernel32(ctypes)
    if not kernel32.GetProcessAffinityMask(
        kernel32.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask failed")
    return int(process_mask.value)


def _set_process_affinity_mask(mask: int) -> None:
    if os.name != "nt":
        raise RuntimeError("process affinity subsets are supported only on Windows")
    import ctypes

    kernel32 = _windows_kernel32(ctypes)
    if not kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), ctypes.c_size_t(mask)):
        raise OSError(ctypes.get_last_error(), "SetProcessAffinityMask failed")


def _windows_kernel32(ctypes: object):
    """Return kernel32 with pointer-sized affinity signatures on Windows."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    )
    kernel32.GetProcessAffinityMask.restype = ctypes.c_int
    kernel32.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    kernel32.SetProcessAffinityMask.restype = ctypes.c_int
    return kernel32


class ClassifierPipeline:
    """Run RepViT first and construct DINOv3 only when recheck is needed."""

    def __init__(
        self,
        *,
        config: ClassifierConfig,
        repvit: _RepVitRunner,
        dino_loader: Callable[[], _ScoreRunner],
        policy: DecisionPolicy,
        prototype_bank: _PrototypeBank,
        fusion_policy: FusionPolicyArtifact | None = None,
        fusion_provenance: ModelProvenance | None = None,
        local_bank: object | None = None,
        local_bank_loader: Callable[[], object] | None = None,
        clock: _Clock | None = None,
        stage_timing_sink: _StageTimingSink | None = None,
    ) -> None:
        self.config = config
        self.repvit = repvit
        self.policy = policy
        self.prototype_bank = prototype_bank
        self.fusion_policy = fusion_policy
        self.fusion_provenance = fusion_provenance
        if (fusion_policy is None) != (fusion_provenance is None):
            raise ValueError("fusion policy and provenance must be supplied together")
        self._local_bank = local_bank
        self._local_bank_loader = local_bank_loader
        self._dino_loader = dino_loader
        self._dino: _ScoreRunner | None = None
        device = torch.device(config.runtime.device.lower())
        self.clock = clock or _CudaClock(device)
        self._stage_timing_sink = stage_timing_sink

    @classmethod
    def load(
        cls,
        config_path: Path,
        *,
        calibration_path: Path | None = None,
        runtime_override: ClassifierRuntimeConfig | None = None,
        stage_timing_sink: _StageTimingSink | None = None,
        artifact_root: Path | None = None,
    ) -> "ClassifierPipeline":
        """Load strict configuration, calibration, and the primary runner."""
        config = (
            ClassifierConfig.load(config_path)
            if artifact_root is None
            else ClassifierConfig.load(config_path, artifact_root=artifact_root)
        )
        if runtime_override is not None:
            config = config.model_copy(update={"runtime": runtime_override})
        configure_cpu_process(config.runtime)
        calibration_payload = (calibration_path or config.calibration.artifact).read_bytes()
        calibration = PolicyCalibration.from_json_bytes(calibration_payload)
        fusion_policy = None
        fusion_payload = None
        if config.calibration.fusion_policy is not None:
            fusion_payload = config.calibration.fusion_policy.read_bytes()
            if hashlib.sha256(fusion_payload).hexdigest() != config.calibration.fusion_policy_sha256:
                raise ValueError("fusion policy SHA-256 does not match classifier config")
            fusion_policy = FusionPolicyArtifact.from_json_bytes(fusion_payload)
        static_policy = (
            fusion_policy is not None
            and fusion_policy.schema_version == 3
            and fusion_policy.decision_rule == "fusion_local_or_global_consensus_margin_v1"
            and fusion_policy.artifact_hashes["preprocess_sha256"] == ClassifierPreprocessDescriptor().sha256()
        )
        active_preprocess_sha256 = (
            ClassifierPreprocessDescriptor().sha256()
            if static_policy else preprocess_sha256(config.preprocess)
        )
        provenance = ModelProvenance(
            repvit_artifact_id=config.repvit.artifact_id,
            repvit_sha256=config.repvit.checkpoint_sha256,
            dinov3_artifact_id=config.dinov3.artifact_id,
            dinov3_sha256=config.dinov3.weights_sha256,
            dinov3_support_sha256=config.dinov3.support_sha256,
            calibration_id=calibration.calibration_id,
            calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
            preprocess_sha256=active_preprocess_sha256,
            repvit_manifest_sha256=config.repvit.manifest_sha256,
            repvit_prototype_sha256=config.repvit.prototype_bank_sha256 or "0" * 64,
        )
        policy = DecisionPolicy(calibration, provenance=provenance)
        fusion_provenance = None
        if fusion_policy is not None:
            assert fusion_payload is not None
            expected_hashes = {
                "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
                "repvit_manifest_sha256": config.repvit.manifest_sha256,
                "repvit_prototype_sha256": config.repvit.prototype_bank_sha256 or "0" * 64,
                "dinov3_weights_sha256": config.dinov3.weights_sha256,
                "dinov3_support_sha256": config.dinov3.support_sha256,
                "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256 or "0" * 64,
                "preprocess_sha256": active_preprocess_sha256,
            }
            if fusion_policy.artifact_hashes != expected_hashes:
                raise ValueError("fusion policy artifacts do not match classifier config")
            fusion_provenance = replace(
                provenance,
                calibration_id=f"fusion_policy_{fusion_policy.decision_rule}",
                calibration_sha256=hashlib.sha256(fusion_payload).hexdigest(),
            )
        repvit = RepVitM1Runner.load(config)
        if "repvit" in config.runtime.compile_models:
            repvit.model = torch.compile(repvit.model)
        if config.repvit.prototype_bank is None or config.repvit.prototype_bank_sha256 is None:
            raise ValueError("RepViT prototype bank is required for safe direct decisions")
        prototype_bank = RepVitPrototypeBank.load(
            config.repvit.prototype_bank,
            checkpoint_sha256=config.repvit.checkpoint_sha256,
            expected_preprocess_sha256=active_preprocess_sha256,
            expected_sha256=config.repvit.prototype_bank_sha256,
        )
        return cls(
            config=config,
            repvit=repvit,
            dino_loader=lambda: DinoV3Rechecker.load(config),
            policy=policy,
            prototype_bank=prototype_bank,
            fusion_policy=fusion_policy,
            fusion_provenance=fusion_provenance,
            local_bank_loader=lambda: _load_local_bank(config, preprocess_identity=active_preprocess_sha256),
            stage_timing_sink=stage_timing_sink,
        )

    def infer(
        self,
        image: Image.Image | CanonicalImage,
        box: Box,
        *,
        on_stage: Callable[[str], None] | None = None,
        on_timing: _StageTimingSink | None = None,
    ) -> ClassificationDecision:
        if self._uses_static_policy():
            raise ValueError("schema-3 static policy requires tight/context batch inference")
        frame = _canonical_frame(image)
        _validate_visual_box(frame, box)
        total_started = self._timestamp()
        timing_sink = _combined_timing_sink(self._stage_timing_sink, on_timing)
        serial_started = time.perf_counter() if timing_sink is not None else None
        crops, product_boxes = make_padded_crops_with_product_boxes(
            frame.image,
            box,
            self.config.preprocess.paddings,
        )
        crop_finished = time.perf_counter() if serial_started is not None else None

        if on_stage is not None:
            on_stage("repvit")
        repvit_started = self._timestamp()
        serial_repvit_started = time.perf_counter() if serial_started is not None else None
        repvit_evidence = self.repvit.score_with_evidence(crops)
        repvit_scores = repvit_evidence.scores
        serial_repvit_finished = time.perf_counter() if serial_started is not None else None
        repvit_finished = self._timestamp()
        nearest_prototype_distance = min(self.prototype_bank.distances(repvit_evidence.feature))
        direct = self.policy.direct(
            repvit_scores,
            evidence=DirectEvidence(
                crop_disagreement=repvit_evidence.crop_disagreement,
                nearest_prototype_distance=nearest_prototype_distance,
            ),
            box=box,
        )
        if direct is not None:
            total_finished = self._timestamp()
            if timing_sink is not None:
                self._observe_serial_timing(
                    sink=timing_sink,
                    total_started=serial_started,
                    crop_finished=crop_finished,
                    repvit_started=serial_repvit_started,
                    repvit_finished=serial_repvit_finished,
                    dino_executed=False,
                )
            return self._with_metadata(
                direct,
                frame=frame,
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=0.0,
                total_ms=_milliseconds(total_started, total_finished),
            )

        if on_stage is not None:
            on_stage("dinov3")
        dinov3_started = self._timestamp()
        dino = self._get_dino()
        serial_dinov3_started = time.perf_counter() if serial_started is not None else None
        serial_dinov3_finished = None
        serial_fusion_started = None
        serial_fusion_finished = None
        try:
            local_bank = self._get_local_bank()
            if self.fusion_policy is not None:
                if local_bank is None or not callable(getattr(dino, "score_global_and_local_evidence", None)):
                    raise ValueError("fusion policy requires DINO local evidence scoring")
                dino_scores, local_scores, patch_count, patch_ratio = dino.score_global_and_local_evidence(
                    crops,
                    product_boxes,
                    local_bank,
                    repvit_scores=repvit_scores,
                )
                serial_dinov3_finished = time.perf_counter() if serial_started is not None else None
                serial_fusion_started = time.perf_counter() if serial_started is not None else None
                decision = self._fusion_decision(
                    repvit_scores=repvit_scores,
                    dino_scores=dino_scores,
                    local_scores=local_scores,
                    crop_disagreement=repvit_evidence.crop_disagreement,
                    nearest_prototype_distance=nearest_prototype_distance,
                    patch_count=patch_count,
                    patch_ratio=patch_ratio,
                    box=box,
                )
                serial_fusion_finished = time.perf_counter() if serial_started is not None else None
            elif local_bank is not None and callable(getattr(dino, "score_global_and_local", None)):
                dino_scores, local_scores = dino.score_global_and_local(
                    crops,
                    product_boxes,
                    local_bank,
                    repvit_scores=repvit_scores,
                )
                serial_dinov3_finished = time.perf_counter() if serial_started is not None else None
                serial_fusion_started = time.perf_counter() if serial_started is not None else None
                decision = self.policy.after_local_recheck(
                    repvit_scores,
                    dino_scores,
                    local_scores,
                    box=box,
                )
                serial_fusion_finished = time.perf_counter() if serial_started is not None else None
            else:
                dino_scores = dino.score(crops)
                serial_dinov3_finished = time.perf_counter() if serial_started is not None else None
                serial_fusion_started = time.perf_counter() if serial_started is not None else None
                decision = self.policy.after_recheck(repvit_scores, dino_scores, box=box)
                serial_fusion_finished = time.perf_counter() if serial_started is not None else None
        except DinoInferenceError as exc:
            dinov3_finished = self._timestamp()
            serial_dinov3_finished = time.perf_counter() if serial_started is not None else None
            serial_fusion_started = time.perf_counter() if serial_started is not None else None
            decision = self._dino_failure_decision(repvit_scores, box=box)
            serial_fusion_finished = time.perf_counter() if serial_started is not None else None
            total_finished = self._timestamp()
            if timing_sink is not None:
                self._observe_serial_timing(
                    sink=timing_sink,
                    total_started=serial_started,
                    crop_finished=crop_finished,
                    repvit_started=serial_repvit_started,
                    repvit_finished=serial_repvit_finished,
                    dino_started=serial_dinov3_started,
                    dino_finished=serial_dinov3_finished,
                    fusion_started=serial_fusion_started,
                    fusion_finished=serial_fusion_finished,
                    dino_executed=True,
                )
            return self._with_metadata(
                decision,
                frame=frame,
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=_milliseconds(
                    dinov3_started,
                    dinov3_finished,
                ),
                total_ms=_milliseconds(total_started, total_finished),
                failure_code=exc.code,
            )

        dinov3_finished = self._timestamp()
        total_finished = self._timestamp()
        if timing_sink is not None:
            self._observe_serial_timing(
                sink=timing_sink,
                total_started=serial_started,
                crop_finished=crop_finished,
                repvit_started=serial_repvit_started,
                repvit_finished=serial_repvit_finished,
                dino_started=serial_dinov3_started,
                dino_finished=serial_dinov3_finished,
                fusion_started=serial_fusion_started,
                fusion_finished=serial_fusion_finished,
                dino_executed=True,
            )
        return self._with_metadata(
            decision,
            frame=frame,
            repvit_ms=_milliseconds(repvit_started, repvit_finished),
            dinov3_ms=_milliseconds(dinov3_started, dinov3_finished),
            total_ms=_milliseconds(total_started, total_finished),
        )

    def infer_many(
        self,
        image: Image.Image | CanonicalImage,
        boxes: Sequence[Box],
        *,
        repvit_max_objects: int | None = None,
        dino_max_objects: int | None = None,
        repvit_rows_per_invocation: int | None = None,
        dino_objects_per_invocation: int | None = None,
        cuda_timing: CudaTimingCollector | None = None,
    ) -> BatchInferenceResult:
        """Classify ordered detector boxes with shared batch evidence extraction."""
        if repvit_rows_per_invocation is not None or dino_objects_per_invocation is not None:
            if repvit_max_objects is not None or dino_max_objects is not None:
                raise ValueError("legacy and static classifier batch contracts cannot be mixed")
            return self._infer_many_tight_context(
                image,
                boxes,
                repvit_rows_per_invocation=repvit_rows_per_invocation,
                dino_objects_per_invocation=dino_objects_per_invocation,
                cuda_timing=cuda_timing,
            )
        if self._uses_static_policy():
            raise ValueError("schema-3 static policy requires tight/context batch inference")
        total_started = self._host_now()
        owns_cuda_timing = False
        frame = _canonical_frame(image)
        ordered_boxes = tuple(boxes)
        for box in ordered_boxes:
            _validate_visual_box(frame, box)
        if type(repvit_max_objects) is not int or repvit_max_objects <= 0:
            raise ValueError("repvit_max_objects must be a positive integer")
        if type(dino_max_objects) is not int or dino_max_objects <= 0:
            raise ValueError("dino_max_objects must be a positive integer")
        if not ordered_boxes:
            total_finished = self._host_now()
            return BatchInferenceResult(
                (),
                BatchStageTimings(0.0, 0.0, 0.0, 0.0, _milliseconds(total_started, total_finished)),
                0,
            )
        if self.config.runtime.device == "CUDA:0" and torch.cuda.is_available():
            if cuda_timing is None:
                cuda_timing = CudaTimingCollector(
                    "cuda:0", synchronize=self.clock.synchronize
                )
                owns_cuda_timing = True

        crop_started = self._host_now()
        crop_groups: list[tuple[Image.Image, ...]] = []
        product_box_groups: list[tuple[Box, ...]] = []
        for box in ordered_boxes:
            crops, product_boxes = make_padded_crops_with_product_boxes(
                frame.image, box, self.config.preprocess.paddings
            )
            crop_groups.append(crops)
            product_box_groups.append(product_boxes)
        crop_finished = self._host_now()

        if not callable(getattr(self.repvit, "score_many_with_evidence", None)):
            raise ValueError("RepViT runner does not expose batch evidence scoring")
        repvit_started = self._host_now()
        score_repvit = lambda: self.repvit.score_many_with_evidence(
            tuple(crop_groups), max_objects=repvit_max_objects
        )
        repvit_evidence = (
            cuda_timing.measure("repvit", score_repvit)
            if cuda_timing is not None
            else score_repvit()
        )
        repvit_finished = self._host_now()
        if len(repvit_evidence) != len(ordered_boxes):
            raise ValueError("RepViT batch evidence must align with input boxes")

        decisions: list[ClassificationDecision | None] = [None] * len(ordered_boxes)
        recheck_indexes: list[int] = []
        nearest_distances: list[float] = []
        for index, (box, evidence) in enumerate(zip(ordered_boxes, repvit_evidence, strict=True)):
            nearest_distance = min(self.prototype_bank.distances(evidence.feature))
            nearest_distances.append(nearest_distance)
            direct = self.policy.direct(
                evidence.scores,
                evidence=DirectEvidence(
                    crop_disagreement=evidence.crop_disagreement,
                    nearest_prototype_distance=nearest_distance,
                ),
                box=box,
            )
            if direct is None:
                recheck_indexes.append(index)
            else:
                decisions[index] = direct

        dino_started = self._host_now()
        fusion_ms = 0.0
        if recheck_indexes:
            dino = self._get_dino()
            local_bank = self._get_local_bank()
            if local_bank is None or not callable(getattr(dino, "score_many_global_and_local_evidence", None)):
                raise ValueError("batch inference requires DINO local evidence scoring")
            for start in range(0, len(recheck_indexes), dino_max_objects):
                batch_indexes = recheck_indexes[start : start + dino_max_objects]
                try:
                    score_dino = lambda: dino.score_many_global_and_local_evidence(
                        tuple(crop_groups[index] for index in batch_indexes),
                        tuple(product_box_groups[index] for index in batch_indexes),
                        local_bank,
                        repvit_scores=tuple(repvit_evidence[index].scores for index in batch_indexes),
                        max_objects=dino_max_objects,
                    )
                    dino_evidence = (
                        cuda_timing.measure("dinov3", score_dino)
                        if cuda_timing is not None
                        else score_dino()
                    )
                    if len(dino_evidence) != len(batch_indexes):
                        raise ValueError("DINO batch evidence must align with rejected objects")
                except DinoInferenceError as exc:
                    for index in batch_indexes:
                        decisions[index] = self._dino_failure_decision(
                            repvit_evidence[index].scores, box=ordered_boxes[index]
                        )
                    for index in batch_indexes:
                        decisions[index] = replace(
                            decisions[index],
                            provenance=replace(decisions[index].provenance, failure_code=exc.code),
                        )
                    continue

                fusion_started = self._host_now()
                for index, evidence in zip(batch_indexes, dino_evidence, strict=True):
                    if self.fusion_policy is not None:
                        decisions[index] = self._fusion_decision(
                            repvit_scores=repvit_evidence[index].scores,
                            dino_scores=evidence.global_scores,
                            local_scores=evidence.local_scores,
                            crop_disagreement=repvit_evidence[index].crop_disagreement,
                            nearest_prototype_distance=nearest_distances[index],
                            patch_count=evidence.product_patch_count,
                            patch_ratio=evidence.product_patch_ratio,
                            box=ordered_boxes[index],
                        )
                    else:
                        decisions[index] = self.policy.after_local_recheck(
                            repvit_evidence[index].scores,
                            evidence.global_scores,
                            evidence.local_scores,
                            box=ordered_boxes[index],
                        )
                fusion_finished = self._host_now()
                fusion_ms += _milliseconds(fusion_started, fusion_finished)
        dino_finished = self._host_now()
        total_finished = self._host_now()
        if any(decision is None for decision in decisions):
            raise RuntimeError("batch inference did not produce every decision")
        repvit_ms = _milliseconds(repvit_started, repvit_finished)
        dino_ms = _milliseconds(dino_started, dino_finished)
        if owns_cuda_timing:
            assert cuda_timing is not None
            event_timings = cuda_timing.finalize()
            repvit_ms = event_timings.get("repvit", 0.0)
            dino_ms = event_timings.get("dinov3", 0.0)
            total_finished = self._host_now()
        total_ms = _milliseconds(total_started, total_finished)
        completed = tuple(
            self._with_metadata(
                decision,
                frame=frame,
                repvit_ms=repvit_ms,
                dinov3_ms=0.0 if index not in recheck_indexes else dino_ms,
                total_ms=total_ms,
                failure_code=decision.provenance.failure_code,
            )
            for index, decision in enumerate(decisions)
            if decision is not None
        )
        return BatchInferenceResult(
            completed,
            BatchStageTimings(
                crop_ms=_milliseconds(crop_started, crop_finished),
                repvit_ms=repvit_ms,
                dinov3_ms=dino_ms,
                fusion_ms=fusion_ms,
                total_ms=total_ms,
            ),
            len(recheck_indexes),
        )

    def _infer_many_tight_context(
        self,
        image: Image.Image | CanonicalImage,
        boxes: Sequence[Box],
        *,
        repvit_rows_per_invocation: int | None,
        dino_objects_per_invocation: int | None,
        cuda_timing: CudaTimingCollector | None,
    ) -> BatchInferenceResult:
        """Run the isolated Task 5 static tight/context evidence contract."""
        if repvit_rows_per_invocation != 14:
            raise ValueError("repvit_rows_per_invocation must be the static value 14")
        if dino_objects_per_invocation != 7:
            raise ValueError("dino_objects_per_invocation must be the static value 7")
        self._require_static_admission()
        total_started = self._host_now()
        owns_cuda_timing = False
        frame = _canonical_frame(image)
        ordered_boxes = tuple(boxes)
        for box in ordered_boxes:
            _validate_visual_box(frame, box)
        if not ordered_boxes:
            total_finished = self._host_now()
            return BatchInferenceResult(
                (),
                BatchStageTimings(0.0, 0.0, 0.0, 0.0, _milliseconds(total_started, total_finished)),
                0,
            )
        if self.config.runtime.device == "CUDA:0" and torch.cuda.is_available() and cuda_timing is None:
            cuda_timing = CudaTimingCollector("cuda:0", synchronize=self.clock.synchronize)
            owns_cuda_timing = True

        crop_started = self._host_now()
        pairs = tuple(build_crop_pair(frame, box) for box in ordered_boxes)
        crop_finished = self._host_now()

        repvit_started = self._host_now()
        repvit_evidence: list[object] = []
        object_capacity = repvit_rows_per_invocation // 2
        for start in range(0, len(pairs), object_capacity):
            valid_pairs = pairs[start : start + object_capacity]
            padded_pairs = _pad_static_chunk(valid_pairs, object_capacity)
            rows = tuple(crop for pair in padded_pairs for crop in (pair.tight, pair.context))
            valid_mask = tuple(
                row_index < 2 * len(valid_pairs)
                for row_index in range(repvit_rows_per_invocation)
            )
            action = lambda rows=rows, valid_mask=valid_mask, valid_count=len(valid_pairs): self._score_tight_context_chunk(
                rows, valid_mask=valid_mask, valid_count=valid_count
            )
            chunk_evidence = cuda_timing.measure("repvit", action) if cuda_timing is not None else action()
            repvit_evidence.extend(chunk_evidence)
        repvit_finished = self._host_now()
        if len(repvit_evidence) != len(ordered_boxes):
            raise ValueError("RepViT static evidence must align with input boxes")

        decisions: list[ClassificationDecision | None] = [None] * len(ordered_boxes)
        recheck_indexes: list[int] = []
        nearest_distances: list[float] = []
        for index, (box, evidence) in enumerate(zip(ordered_boxes, repvit_evidence, strict=True)):
            _require_tight_context_evidence(evidence)
            nearest_distance = min(self.prototype_bank.distances(evidence.feature))
            nearest_distances.append(nearest_distance)
            direct = None
            if _pair_top1_agrees(evidence):
                direct = self.policy.direct(
                    evidence.scores,
                    evidence=DirectEvidence(
                        crop_disagreement=evidence.crop_disagreement,
                        nearest_prototype_distance=nearest_distance,
                    ),
                    box=box,
                )
            if direct is None:
                recheck_indexes.append(index)
            else:
                decisions[index] = direct

        dino_started = self._host_now()
        fusion_ms = 0.0
        if recheck_indexes:
            dino = self._get_dino()
            local_bank = self._get_local_bank()
            if local_bank is None:
                raise ValueError("static DINO inference requires a local support bank")
            for start in range(0, len(recheck_indexes), dino_objects_per_invocation):
                valid_indexes = recheck_indexes[start : start + dino_objects_per_invocation]
                padded_indexes = _pad_static_chunk(tuple(valid_indexes), dino_objects_per_invocation)
                context_crops = tuple(pairs[index].context for index in padded_indexes)
                product_boxes = tuple(pairs[index].context_product_box for index in padded_indexes)
                aligned_repvit = tuple(repvit_evidence[index].scores for index in padded_indexes)
                valid_mask = tuple(index < len(valid_indexes) for index in range(dino_objects_per_invocation))
                action = lambda: self._score_context_dino_chunk(
                    dino,
                    context_crops,
                    product_boxes,
                    local_bank,
                    repvit_scores=aligned_repvit,
                    valid_mask=valid_mask,
                    valid_count=len(valid_indexes),
                )
                # Do not catch chunk failures: the Task 5 contract aborts the scan.
                dino_evidence = cuda_timing.measure("dinov3", action) if cuda_timing is not None else action()
                fusion_started = self._host_now()
                for index, evidence in zip(valid_indexes, dino_evidence, strict=True):
                    decisions[index] = self._fusion_decision(
                        repvit_scores=repvit_evidence[index].scores,
                        dino_scores=evidence.global_scores,
                        local_scores=evidence.local_scores,
                        crop_disagreement=repvit_evidence[index].crop_disagreement,
                        nearest_prototype_distance=nearest_distances[index],
                        patch_count=evidence.product_patch_count,
                        patch_ratio=evidence.product_patch_ratio,
                        box=ordered_boxes[index],
                    )
                fusion_finished = self._host_now()
                fusion_ms += _milliseconds(fusion_started, fusion_finished)
        dino_finished = self._host_now()
        if any(decision is None for decision in decisions):
            raise RuntimeError("static batch inference did not produce every decision")
        total_finished = self._host_now()
        repvit_ms = _milliseconds(repvit_started, repvit_finished)
        dino_ms = _milliseconds(dino_started, dino_finished)
        if owns_cuda_timing:
            assert cuda_timing is not None
            event_timings = cuda_timing.finalize()
            repvit_ms = event_timings.get("repvit", 0.0)
            dino_ms = event_timings.get("dinov3", 0.0)
            total_finished = self._host_now()
        total_ms = _milliseconds(total_started, total_finished)
        completed = tuple(
            self._with_metadata(
                decision,
                frame=frame,
                repvit_ms=repvit_ms,
                dinov3_ms=0.0 if index not in recheck_indexes else dino_ms,
                total_ms=total_ms,
                failure_code=decision.provenance.failure_code,
            )
            for index, decision in enumerate(decisions)
            if decision is not None
        )
        return BatchInferenceResult(
            completed,
            BatchStageTimings(
                crop_ms=_milliseconds(crop_started, crop_finished),
                repvit_ms=repvit_ms,
                dinov3_ms=dino_ms,
                fusion_ms=fusion_ms,
                total_ms=total_ms,
            ),
            len(recheck_indexes),
        )

    def _require_static_admission(self) -> None:
        if self.fusion_policy is None or self.fusion_provenance is None:
            raise ValueError("static inference requires an admitted immutable fusion policy")
        if (
            self.fusion_policy.schema_version != 3
            or self.fusion_policy.decision_rule != "fusion_local_or_global_consensus_margin_v1"
            or self.fusion_policy.consensus_margin_floor != 0.85
        ):
            raise ValueError("static inference requires the immutable consensus fusion policy")
        descriptor_sha256 = ClassifierPreprocessDescriptor().sha256()
        hashes = self.fusion_policy.artifact_hashes
        if hashes["preprocess_sha256"] != descriptor_sha256:
            raise ValueError("static preprocessing SHA-256 does not match fusion policy")
        for label, provenance in (
            ("direct policy", self.policy.provenance),
            ("fusion policy", self.fusion_provenance),
        ):
            expected = {
                "repvit_checkpoint_sha256": provenance.repvit_sha256,
                "repvit_manifest_sha256": provenance.repvit_manifest_sha256,
                "repvit_prototype_sha256": provenance.repvit_prototype_sha256,
                "dinov3_weights_sha256": provenance.dinov3_sha256,
                "dinov3_support_sha256": provenance.dinov3_support_sha256,
                "preprocess_sha256": provenance.preprocess_sha256,
            }
            if any(hashes[name] != value for name, value in expected.items()):
                raise ValueError(f"static {label} artifact identity does not match fusion policy")
        local_sha256 = getattr(self._local_bank, "sha256", None)
        if local_sha256 is not None and local_sha256 != hashes["dinov3_local_bank_sha256"]:
            raise ValueError("static local support identity does not match fusion policy")

    def _uses_static_policy(self) -> bool:
        return (
            self.fusion_policy is not None
            and self.fusion_policy.schema_version == 3
            and self.fusion_policy.decision_rule == "fusion_local_or_global_consensus_margin_v1"
            and self.fusion_policy.artifact_hashes["preprocess_sha256"] == ClassifierPreprocessDescriptor().sha256()
        )

    def _score_tight_context_chunk(
        self,
        rows: tuple[Image.Image, ...],
        *,
        valid_mask: tuple[bool, ...],
        valid_count: int,
    ) -> tuple[object, ...]:
        score_static = getattr(self.repvit, "score_tight_context_chunk", None)
        if callable(score_static):
            result = tuple(score_static(rows, valid_mask=valid_mask))
        else:
            score_many = getattr(self.repvit, "score_many_with_evidence", None)
            if not callable(score_many):
                raise ValueError("RepViT runner does not expose tight/context static scoring")
            groups = tuple((rows[index], rows[index + 1]) for index in range(0, len(rows), 2))
            result = tuple(score_many(groups, max_objects=7))
        if len(result) not in {valid_count, 7}:
            raise ValueError("RepViT static chunk evidence must align with valid or padded objects")
        return result[:valid_count]

    def _score_context_dino_chunk(
        self,
        dino: object,
        crops: tuple[Image.Image, ...],
        product_boxes: tuple[Box, ...],
        local_bank: object,
        *,
        repvit_scores: tuple[ModelScoreVector, ...],
        valid_mask: tuple[bool, ...],
        valid_count: int,
    ) -> tuple[object, ...]:
        score_static = getattr(dino, "score_context_chunk_global_and_local_evidence", None)
        if callable(score_static):
            result = tuple(score_static(
                crops,
                product_boxes,
                local_bank,
                repvit_scores=repvit_scores,
                valid_mask=valid_mask,
            ))
        else:
            score_many = getattr(dino, "score_many_global_and_local_evidence", None)
            if not callable(score_many):
                raise ValueError("DINO runner does not expose context static scoring")
            result = tuple(score_many(
                tuple((crop,) for crop in crops),
                tuple((box,) for box in product_boxes),
                local_bank,
                repvit_scores=repvit_scores,
                max_objects=7,
            ))
        if len(result) not in {valid_count, 7}:
            raise ValueError("DINO static chunk evidence must align with valid or padded objects")
        return result[:valid_count]

    def preflight_benchmark(
        self,
        image: Image.Image | CanonicalImage,
        boxes: Sequence[Box],
        *,
        repvit_max_objects: int,
        dino_max_objects: int,
    ) -> BenchmarkPreflightEvidence:
        """Execute benchmark warm-up work without producing an evaluated decision."""
        if self._uses_static_policy():
            raise ValueError("schema-3 static policy requires a tight/context benchmark preflight")
        frame = _canonical_frame(image)
        ordered_boxes = tuple(boxes)
        if not ordered_boxes:
            raise ValueError("benchmark preflight requires at least one box")
        for box in ordered_boxes:
            _validate_visual_box(frame, box)
        if type(repvit_max_objects) is not int or repvit_max_objects <= 0:
            raise ValueError("repvit_max_objects must be a positive integer")
        if type(dino_max_objects) is not int or dino_max_objects <= 0:
            raise ValueError("dino_max_objects must be a positive integer")
        if self.fusion_policy is None or self.fusion_provenance is None:
            raise ValueError("benchmark preflight requires an immutable fusion policy")
        local_bank = self._get_local_bank()
        if local_bank is None:
            raise ValueError("benchmark preflight requires a DINO local bank")

        crop_groups: list[tuple[Image.Image, ...]] = []
        product_box_groups: list[tuple[Box, ...]] = []
        for box in ordered_boxes:
            crops, product_boxes = make_padded_crops_with_product_boxes(
                frame.image,
                box,
                self.config.preprocess.paddings,
            )
            crop_groups.append(crops)
            product_box_groups.append(product_boxes)

        if self.config.runtime.mode == "serial_reference":
            repvit_evidence = tuple(
                self.repvit.score_with_evidence(crops) for crops in crop_groups
            )
        else:
            score_many = getattr(self.repvit, "score_many_with_evidence", None)
            if not callable(score_many):
                raise ValueError("RepViT runner does not expose batch evidence scoring")
            repvit_evidence = tuple(
                score_many(tuple(crop_groups), max_objects=repvit_max_objects)
            )
            if len(repvit_evidence) != len(ordered_boxes):
                raise ValueError("RepViT batch evidence must align with input boxes")

        dino = self._get_dino()
        score_global_and_local = getattr(dino, "score_global_and_local_evidence", None)
        if not callable(score_global_and_local):
            raise ValueError("benchmark preflight requires DINO local evidence scoring")
        first_repvit = repvit_evidence[0]
        dino_scores, local_scores, patch_count, patch_ratio = score_global_and_local(
            crop_groups[0],
            product_box_groups[0],
            local_bank,
            repvit_scores=first_repvit.scores,
        )
        nearest_prototype_distance = min(
            self.prototype_bank.distances(first_repvit.feature)
        )
        self._fusion_decision(
            repvit_scores=first_repvit.scores,
            dino_scores=dino_scores,
            local_scores=local_scores,
            crop_disagreement=first_repvit.crop_disagreement,
            nearest_prototype_distance=nearest_prototype_distance,
            patch_count=patch_count,
            patch_ratio=patch_ratio,
            box=ordered_boxes[0],
        )
        self.clock.synchronize()
        return BenchmarkPreflightEvidence(
            repvit=len(repvit_evidence),
            dinov3_global_local=1,
            fusion=1,
        )

    def preflight_models(self, image: Image.Image | CanonicalImage, box: Box) -> None:
        """Load and execute all configured model evidence before measured inference."""
        if self._uses_static_policy():
            raise ValueError("schema-3 static policy requires a tight/context model preflight")
        frame = _canonical_frame(image)
        _validate_visual_box(frame, box)
        crops, product_boxes = make_padded_crops_with_product_boxes(
            frame.image,
            box,
            self.config.preprocess.paddings,
        )
        repvit_scores = self.repvit.score_with_evidence(crops).scores
        dino = self._get_dino()
        local_bank = self._get_local_bank()
        if local_bank is None:
            dino.score(crops)
        elif callable(getattr(dino, "score_global_and_local_evidence", None)):
            dino.score_global_and_local_evidence(
                crops,
                product_boxes,
                local_bank,
                repvit_scores=repvit_scores,
            )
        elif callable(getattr(dino, "score_global_and_local", None)):
            dino.score_global_and_local(
                crops,
                product_boxes,
                local_bank,
                repvit_scores=repvit_scores,
            )
        else:
            raise ValueError("DINO local bank preflight requires local evidence scoring")
        self.clock.synchronize()

    def _get_dino(self) -> _ScoreRunner:
        if self._dino is None:
            loaded = self._dino_loader()
            if loaded is None or not callable(getattr(loaded, "score", None)):
                raise TypeError("DINO loader must return a score runner")
            if "dinov3" in self.config.runtime.compile_models:
                if not isinstance(loaded, DinoV3Rechecker):
                    raise TypeError("DINO compile selection requires a DINOv3 rechecker")
                loaded.encoder = torch.compile(loaded.encoder)
            self._dino = loaded
        return self._dino

    def _get_local_bank(self) -> object | None:
        if self._local_bank is None and self._local_bank_loader is not None:
            self._local_bank = self._local_bank_loader()
        return self._local_bank

    def _timestamp(self) -> float:
        self.clock.synchronize()
        return self.clock()

    def _host_now(self) -> float:
        """Read the host monotonic clock without serializing queued GPU work."""
        value = float(self.clock())
        if not math.isfinite(value):
            raise ValueError("clock must return finite values")
        return value

    def _observe_serial_timing(
        self,
        *,
        sink: _StageTimingSink,
        total_started: float | None,
        crop_finished: float | None,
        repvit_started: float | None,
        repvit_finished: float | None,
        dino_executed: bool,
        dino_started: float | None = None,
        dino_finished: float | None = None,
        fusion_started: float | None = None,
        fusion_finished: float | None = None,
    ) -> None:
        if (
            total_started is None
            or crop_finished is None
            or repvit_started is None
            or repvit_finished is None
        ):
            raise RuntimeError("serial timing observation boundaries are incomplete")
        total_finished = time.perf_counter()
        if dino_executed:
            if dino_started is None:
                raise RuntimeError("DINO timing observation boundary is missing")
            dino_finished = dino_finished or total_finished
            dinov3_ms = _milliseconds(dino_started, dino_finished)
        else:
            dinov3_ms = 0.0
        if fusion_started is not None and fusion_finished is not None:
            fusion_ms = _milliseconds(fusion_started, fusion_finished)
        else:
            fusion_ms = 0.0
        sink(
            SerialStageTimings(
                crop_ms=_milliseconds(total_started, crop_finished),
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=dinov3_ms,
                fusion_ms=fusion_ms,
                total_ms=_milliseconds(total_started, total_finished),
                dino_executed=dino_executed,
            )
        )

    def _fusion_decision(
        self,
        *,
        repvit_scores,
        dino_scores,
        local_scores: dict[int, float],
        crop_disagreement: float,
        nearest_prototype_distance: float,
        patch_count: int,
        patch_ratio: float,
        box: Box,
    ) -> ClassificationDecision:
        if self.fusion_policy is None or self.fusion_provenance is None:
            raise RuntimeError("fusion decision requested without fusion policy")
        row = FullEvidenceRow(
            sample_id="runtime", capture_group="runtime", registered=False, sku_id=None,
            role="development", image_sha256="0" * 64,
            repvit_values=repvit_scores.values, dinov3_values=dino_scores.values,
            candidate_sku_ids=tuple(local_scores),
            local_values=tuple(local_scores[sku_id] for sku_id in local_scores),
            repvit_crop_disagreement=crop_disagreement,
            nearest_prototype_distance=nearest_prototype_distance,
            local_product_patch_count=patch_count, local_product_patch_ratio=patch_ratio,
            repvit_checkpoint_sha256=self.config.repvit.checkpoint_sha256,
            repvit_manifest_sha256=self.config.repvit.manifest_sha256,
            repvit_prototype_sha256=self.config.repvit.prototype_bank_sha256 or "0" * 64,
            dinov3_weights_sha256=self.config.dinov3.weights_sha256,
            dinov3_support_sha256=self.config.dinov3.support_sha256,
            dinov3_local_bank_sha256=self.config.dinov3.local_bank_sha256 or "0" * 64,
            preprocess_sha256=self.fusion_policy.artifact_hashes["preprocess_sha256"],
        )
        ranked = self.fusion_policy.ranker.rank(row)
        decision, _ = self.fusion_policy.decide(row)
        if decision.decision == "sku":
            return ClassificationDecision(
                decision="sku", sku_id=decision.predicted_sku_id,
                confidence=ranked.scores[0], box=box,
                decision_path=DecisionPath.FUSION_RANKED, top3=(),
                provenance=self.fusion_provenance, timings=StageTimings(0.0, 0.0, 0.0),
            )
        return ClassificationDecision(
            decision="unknown", sku_id=None, confidence=ranked.scores[0], box=box,
            decision_path=DecisionPath.UNKNOWN_TOP3,
            top3=tuple(
                SkuCandidate(rank=index, sku_id=sku_id, score=score)
                for index, (sku_id, score) in enumerate(zip(ranked.sku_ids[:3], ranked.scores[:3], strict=True), start=1)
            ),
            provenance=self.fusion_provenance, timings=StageTimings(0.0, 0.0, 0.0),
            unknown_reason=(
                "fusion_local_disagreement"
                if self.fusion_policy.decision_rule == "fusion_local_agree_v1"
                else (
                    "fusion_global_consensus_margin"
                    if self.fusion_policy.decision_rule == "fusion_local_or_global_consensus_margin_v1"
                    else "fusion_risk_threshold"
                )
            ),
        )

    def _dino_failure_decision(self, repvit_scores, *, box: Box) -> ClassificationDecision:
        """Preserve the configured pipeline provenance for fail-closed DINO errors."""
        decision = self.policy.dino_failure(repvit_scores, box=box)
        if self.fusion_provenance is None:
            return decision
        return replace(decision, provenance=self.fusion_provenance)

    def _with_metadata(
        self,
        decision: ClassificationDecision,
        *,
        frame: CanonicalImage,
        repvit_ms: float,
        dinov3_ms: float,
        total_ms: float,
        failure_code: str | None = None,
    ) -> ClassificationDecision:
        provenance = replace(
            decision.provenance,
            canonical_frame_version=frame.frame_version,
            exif_orientation=frame.exif_orientation,
            failure_code=failure_code,
        )
        timings = StageTimings(
            repvit_ms=repvit_ms,
            dinov3_ms=dinov3_ms,
            total_ms=total_ms,
        )
        return replace(
            decision,
            provenance=provenance,
            timings=timings,
        )


def _milliseconds(started: float, finished: float) -> float:
    return (finished - started) * 1000.0


def _pad_static_chunk(values: tuple[Any, ...], capacity: int) -> tuple[Any, ...]:
    if not values or len(values) > capacity:
        raise ValueError("static chunk must contain one through capacity valid values")
    return values + (values[-1],) * (capacity - len(values))


def _require_tight_context_evidence(evidence: object) -> None:
    required = ("scores", "tight_scores", "context_scores", "feature", "crop_disagreement")
    if any(not hasattr(evidence, name) for name in required):
        raise ValueError("RepViT static evidence must include tight and context scores")
    if not all(
        isinstance(getattr(evidence, name), ModelScoreVector)
        for name in ("scores", "tight_scores", "context_scores")
    ):
        raise ValueError("RepViT static evidence score vectors are invalid")


def _pair_top1_agrees(evidence: object) -> bool:
    tight = evidence.tight_scores
    context = evidence.context_scores
    if tight.sku_ids != context.sku_ids:
        return False
    return _score_top1(tight) == _score_top1(context)


def _score_top1(scores: ModelScoreVector) -> int:
    return min(
        scores.sku_ids,
        key=lambda sku_id: (-scores.values[scores.sku_ids.index(sku_id)], sku_id),
    )


def _canonical_frame(image: Image.Image | CanonicalImage) -> CanonicalImage:
    if isinstance(image, CanonicalImage):
        return image
    return canonicalize_image(image)


def _validate_visual_box(frame: CanonicalImage, box: Box) -> None:
    frame.require_box(box)


def _load_local_bank(config: ClassifierConfig, *, preprocess_identity: str | None = None) -> LocalPatchBank:
    if config.dinov3.local_bank is None or config.dinov3.local_bank_sha256 is None:
        raise ValueError("DINO local patch bank is required for local recheck")
    bank = LocalPatchBank.load(
        config.dinov3.local_bank,
        dino_weights_sha256=config.dinov3.weights_sha256,
        preprocess_sha256=preprocess_identity or preprocess_sha256(config.preprocess),
    )
    if bank.sha256 != config.dinov3.local_bank_sha256:
        raise ValueError("DINO local patch bank SHA-256 mismatch")
    return bank
