"""GPU-resident, fail-closed RTX 5080 single-frame orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable, Protocol, Sequence

from bakery_scanner.classification.trt import (
    DinoBatchEvidence,
    GpuCropPair,
    RepVitBatchEvidence,
)
from bakery_scanner.contracts import BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    ForegroundEvidence,
    evaluate_completeness,
)
from bakery_scanner.detection.rfdetr_trt import CanonicalGpuFrame

from .contracts import (
    CANONICAL_SKUS,
    CandidateConfidence,
    CanonicalFrame,
    DecisionPath,
    FinalObject,
    ObjectLocation,
    ObjectProvenance,
    ScanProvenance,
    ScanResult,
    ScanState,
    SkuCandidate,
    StageTimings,
)


class RuntimeInferenceError(RuntimeError):
    """The whole scan was aborted; partial decisions are never publishable."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.partial_objects: tuple[FinalObject, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanContext:
    scan_id: str
    retake_chain_id: str
    attempt: int

    def __post_init__(self) -> None:
        if not isinstance(self.scan_id, str) or not self.scan_id:
            raise ValueError("scan_id must be non-empty")
        if not isinstance(self.retake_chain_id, str) or not self.retake_chain_id:
            raise ValueError("retake_chain_id must be non-empty")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")


Top3 = tuple[tuple[int, float], tuple[int, float], tuple[int, float]]


@dataclass(frozen=True, slots=True)
class DirectGateDecision:
    sku_id: int
    confidence: float
    top3: Top3

    def __post_init__(self) -> None:
        _registered_decision(self.sku_id, self.confidence, self.top3, "direct")


@dataclass(frozen=True, slots=True)
class FusionGateDecision:
    sku_id: int | None
    confidence: float | None
    margin: float
    top3: Top3

    def __post_init__(self) -> None:
        _top3(self.top3)
        if not _finite(self.margin) or self.margin < 0:
            raise ValueError("fusion margin must be finite and non-negative")
        if abs(self.margin - (self.top3[0][1] - self.top3[1][1])) > 1e-9:
            raise ValueError("fusion margin must equal the ranked Top-1/Top-2 gap")
        if self.sku_id is None:
            if self.confidence is not None:
                raise ValueError("Unknown fusion decision must have null confidence")
        else:
            _registered_decision(self.sku_id, self.confidence, self.top3, "fusion")


class CudaStream(Protocol):
    def synchronize(self) -> None: ...


class CudaStageTimer(Protocol):
    def measure(
        self, name: str, stream: CudaStream, action: Callable[[], object]
    ) -> object: ...
    def duration_ms(self, name: str) -> float: ...


class JpegGpuDecoder(Protocol):
    def decode(self, encoded: bytes, *, stream: CudaStream) -> CanonicalGpuFrame: ...


class Detector(Protocol):
    def detect(self, frame: CanonicalGpuFrame) -> tuple[BreadProposal, ...]: ...


class SceneEvidenceJob(Protocol):
    def resolve(
        self, proposals: tuple[BreadProposal, ...]
    ) -> tuple[ForegroundEvidence, CaptureQuality]: ...


class SceneAnalyzer(Protocol):
    def start(
        self,
        frame: CanonicalGpuFrame,
        tray_roi: tuple[float, float, float, float],
        *,
        stream: CudaStream,
    ) -> SceneEvidenceJob: ...


class GpuCropper(Protocol):
    def build_pairs(
        self,
        frame: CanonicalGpuFrame,
        proposals: tuple[BreadProposal, ...],
        *,
        stream: CudaStream,
    ) -> tuple[GpuCropPair, ...]: ...


class RepVitRunner(Protocol):
    def score_pairs(
        self, crop_pairs: Sequence[GpuCropPair]
    ) -> tuple[RepVitBatchEvidence, ...]: ...


class DinoRunner(Protocol):
    def score_rejections(
        self, crops: Sequence[object]
    ) -> tuple[DinoBatchEvidence, ...]: ...


class DirectPolicy(Protocol):
    immutable: bool

    def decide(
        self, evidence: RepVitBatchEvidence, *, object_order: int
    ) -> DirectGateDecision | None: ...


class FusionPolicy(Protocol):
    immutable: bool
    consensus_margin_floor: float

    def decide(
        self,
        repvit: RepVitBatchEvidence,
        dino: DinoBatchEvidence,
        *,
        object_order: int,
    ) -> FusionGateDecision: ...


class Rtx5080Pipeline:
    """One admitted RTX 5080 path with no legacy or CPU fallback."""

    def __init__(
        self,
        *,
        decoder: JpegGpuDecoder,
        detector: Detector,
        scene_analyzer: SceneAnalyzer,
        cropper: GpuCropper,
        repvit: RepVitRunner,
        dino: DinoRunner,
        direct_policy: DirectPolicy,
        fusion_policy: FusionPolicy,
        completeness_policy: CompletenessPolicy,
        tray_roi: tuple[float, float, float, float],
        detector_stream: CudaStream,
        completeness_stream: CudaStream,
        timer: CudaStageTimer,
        object_provenance: ObjectProvenance,
        scan_provenance: ScanProvenance,
        host_now: Callable[[], float] = time.perf_counter,
    ) -> None:
        if getattr(direct_policy, "immutable", False) is not True:
            raise ValueError("direct policy must be immutable and admitted")
        if (
            getattr(fusion_policy, "immutable", False) is not True
            or getattr(fusion_policy, "consensus_margin_floor", None) != 0.85
        ):
            raise ValueError("fusion policy must be immutable with margin floor 0.85")
        if not isinstance(completeness_policy, CompletenessPolicy):
            raise ValueError("completeness policy must be calibrated")
        _tray_roi(tray_roi)
        if not isinstance(object_provenance, ObjectProvenance) or not isinstance(
            scan_provenance, ScanProvenance
        ):
            raise ValueError("admitted object and scan provenance are required")
        self.decoder, self.detector, self.scene_analyzer = (
            decoder,
            detector,
            scene_analyzer,
        )
        self.cropper, self.repvit, self.dino = cropper, repvit, dino
        self.direct_policy, self.fusion_policy = direct_policy, fusion_policy
        self.completeness_policy, self.tray_roi = completeness_policy, tray_roi
        self.detector_stream, self.completeness_stream = (
            detector_stream,
            completeness_stream,
        )
        self.timer = timer
        self.object_provenance, self.scan_provenance = (
            object_provenance,
            scan_provenance,
        )
        self._host_now = host_now

    def infer(self, encoded: bytes, context: ScanContext) -> ScanResult:
        if not isinstance(encoded, bytes) or not encoded:
            raise ValueError("encoded JPEG must be non-empty bytes")
        if not isinstance(context, ScanContext):
            raise ValueError("context must use ScanContext")
        started = self._host_now()
        try:
            frame = self.timer.measure(
                "decode_canonical",
                self.detector_stream,
                lambda: self.decoder.decode(encoded, stream=self.detector_stream),
            )
            if not isinstance(frame, CanonicalGpuFrame):
                raise ValueError("decoder did not produce a canonical GPU frame")

            # Queue independent foreground/quality work before detector execution;
            # both streams meet only at the completeness boundary.
            scene_job = self.scene_analyzer.start(
                frame, self.tray_roi, stream=self.completeness_stream
            )
            proposals = self.timer.measure(
                "detector", self.detector_stream, lambda: self.detector.detect(frame)
            )
            if not isinstance(proposals, tuple):
                raise ValueError("detector did not return an immutable proposal tuple")
            self.detector_stream.synchronize()
            self.completeness_stream.synchronize()
            foreground, quality = self.timer.measure(
                "completeness",
                self.completeness_stream,
                lambda: scene_job.resolve(proposals),
            )
            completeness = evaluate_completeness(
                (frame.width, frame.height),
                proposals,
                foreground,
                quality,
                self.completeness_policy,
            )
            canonical = CanonicalFrame(frame.width, frame.height)
            if not completeness.accepted:
                return self._retake(
                    context,
                    canonical,
                    completeness.reasons,
                    completeness.problem_regions,
                    started,
                )

            ordered = tuple(sorted(proposals, key=_proposal_order_key))
            pairs = self.timer.measure(
                "crop",
                self.detector_stream,
                lambda: self.cropper.build_pairs(
                    frame, ordered, stream=self.detector_stream
                ),
            )
            if not isinstance(pairs, tuple) or len(pairs) != len(ordered):
                raise ValueError("GPU crop pairs do not align with accepted proposals")
            if tuple(pair.object_order for pair in pairs) != tuple(
                range(1, len(pairs) + 1)
            ):
                raise ValueError(
                    "GPU crop pairs do not preserve deterministic object order"
                )
            repvit = self.timer.measure(
                "repvit", self.detector_stream, lambda: self.repvit.score_pairs(pairs)
            )
            if not isinstance(repvit, tuple) or len(repvit) != len(pairs):
                raise ValueError(
                    "RepViT evidence does not align with accepted proposals"
                )

            direct = self.timer.measure(
                "direct_gate",
                self.detector_stream,
                lambda: tuple(
                    _checked_direct(
                        evidence,
                        self.direct_policy.decide(evidence, object_order=index),
                    )
                    for index, evidence in enumerate(repvit, start=1)
                ),
            )
            rejected = tuple(
                index for index, value in enumerate(direct) if value is None
            )
            dino_by_index: dict[int, DinoBatchEvidence] = {}
            if rejected:
                rejected_crops = tuple(pairs[index].context for index in rejected)
                dino = self.timer.measure(
                    "dinov3",
                    self.detector_stream,
                    lambda: self.dino.score_rejections(rejected_crops),
                )
                if not isinstance(dino, tuple) or len(dino) != len(rejected):
                    raise ValueError(
                        "DINO evidence does not align with direct rejections"
                    )
                dino_by_index.update(zip(rejected, dino, strict=True))

            decisions = self.timer.measure(
                "fusion_payload",
                self.detector_stream,
                lambda: tuple(
                    value
                    if value is not None
                    else _checked_fusion(
                        repvit[index],
                        dino_by_index[index],
                        self.fusion_policy.decide(
                            repvit[index],
                            dino_by_index[index],
                            object_order=index + 1,
                        ),
                    )
                    for index, value in enumerate(direct)
                ),
            )
            objects = tuple(
                self._final_object(context, index, proposal, decision, canonical)
                for index, (proposal, decision) in enumerate(
                    zip(ordered, decisions, strict=True), start=1
                )
            )
            return self._accepted(context, canonical, objects, started)
        except RuntimeInferenceError:
            raise
        except Exception as exc:
            raise RuntimeInferenceError(
                "RTX 5080 scan aborted without partial result"
            ) from exc

    def _final_object(
        self,
        context: ScanContext,
        order: int,
        proposal: BreadProposal,
        decision: DirectGateDecision | FusionGateDecision,
        frame: CanonicalFrame,
    ) -> FinalObject:
        location = _location(proposal, order, frame)
        top3 = _sku_candidates(decision.top3)
        if isinstance(decision, DirectGateDecision):
            return FinalObject(
                f"{context.scan_id}#{order:04d}",
                decision.sku_id,
                CANONICAL_SKUS[decision.sku_id],
                DecisionPath.DIRECT,
                location,
                CandidateConfidence(proposal.score, decision.confidence, None),
                top3,
                self.object_provenance,
            )
        if not isinstance(decision, FusionGateDecision):
            raise ValueError("policy returned a malformed decision")
        if decision.sku_id is None:
            return FinalObject(
                f"{context.scan_id}#{order:04d}",
                None,
                "Unknown",
                DecisionPath.UNKNOWN,
                location,
                CandidateConfidence(proposal.score, None, decision.margin),
                top3,
                self.object_provenance,
            )
        return FinalObject(
            f"{context.scan_id}#{order:04d}",
            decision.sku_id,
            CANONICAL_SKUS[decision.sku_id],
            DecisionPath.CONSENSUS,
            location,
            CandidateConfidence(proposal.score, decision.confidence, decision.margin),
            top3,
            self.object_provenance,
        )

    def _accepted(
        self,
        context: ScanContext,
        frame: CanonicalFrame,
        objects: tuple[FinalObject, ...],
        started: float,
    ) -> ScanResult:
        return self._validated_result(
            lambda timings: ScanResult(
                context.scan_id,
                context.retake_chain_id,
                ScanState.ACCEPTED,
                objects,
                (),
                timings,
                self.scan_provenance,
                frame,
                False,
            ),
            started,
        )

    def _retake(
        self,
        context: ScanContext,
        frame: CanonicalFrame,
        reasons: tuple,
        regions: tuple[tuple[float, float, float, float], ...],
        started: float,
    ) -> ScanResult:
        problem_regions = tuple(
            _region_location(region, index, frame)
            for index, region in enumerate(regions, start=1)
        )
        return self._validated_result(
            lambda timings: ScanResult.needs_retake(
                scan_id=context.scan_id,
                retake_chain_id=context.retake_chain_id,
                attempt=context.attempt,
                reasons=reasons,
                problem_regions=problem_regions,
                timings_ms=timings,
                provenance=self.scan_provenance,
                canonical_frame=frame,
            ),
            started,
        )

    def _validated_result(
        self, factory: Callable[[StageTimings], ScanResult], started: float
    ) -> ScanResult:
        provisional = factory(
            self._timings(max(0.0, (self._host_now() - started) * 1000))
        )
        provisional.to_json_bytes()
        final = factory(self._timings(max(0.0, (self._host_now() - started) * 1000)))
        final.to_json_bytes()
        return final

    def _timings(self, total: float) -> StageTimings:
        return StageTimings(
            self.timer.duration_ms("decode_canonical"),
            self.timer.duration_ms("detector"),
            self.timer.duration_ms("completeness"),
            self.timer.duration_ms("crop"),
            self.timer.duration_ms("repvit"),
            self.timer.duration_ms("direct_gate"),
            self.timer.duration_ms("dinov3"),
            self.timer.duration_ms("fusion_payload"),
            total,
        )


def _proposal_order_key(proposal: BreadProposal) -> tuple[float, float, float, float]:
    return (
        (proposal.box.y + proposal.box.height / 2) / proposal.image_height,
        (proposal.box.x + proposal.box.width / 2) / proposal.image_width,
        proposal.box.x,
        proposal.box.y,
    )


def _location(
    proposal: BreadProposal, order: int, frame: CanonicalFrame
) -> ObjectLocation:
    x1, y1, x2, y2 = proposal.box.xyxy
    return ObjectLocation(
        (x1, y1, x2, y2),
        ((x1 + x2) / (2 * frame.width), (y1 + y2) / (2 * frame.height)),
        order,
    )


def _region_location(
    region: tuple[float, float, float, float], order: int, frame: CanonicalFrame
) -> ObjectLocation:
    x1, y1, x2, y2 = region
    return ObjectLocation(
        region, ((x1 + x2) / (2 * frame.width), (y1 + y2) / (2 * frame.height)), order
    )


def _sku_candidates(values: Top3) -> tuple[SkuCandidate, ...]:
    return tuple(
        SkuCandidate(index, sku_id, CANONICAL_SKUS[sku_id], score)
        for index, (sku_id, score) in enumerate(values, start=1)
    )


def _checked_direct(
    evidence: RepVitBatchEvidence, decision: DirectGateDecision | None
) -> DirectGateDecision | None:
    if decision is None:
        return None
    if not isinstance(decision, DirectGateDecision):
        raise ValueError("direct policy returned a malformed decision")
    if not (
        decision.sku_id
        == _score_top1(evidence.tight_scores)
        == _score_top1(evidence.context_scores)
    ):
        raise ValueError("direct approval requires agreeing tight/context Top-1")
    return decision


def _checked_fusion(
    repvit: RepVitBatchEvidence,
    dino: DinoBatchEvidence,
    decision: FusionGateDecision,
) -> FusionGateDecision:
    if not isinstance(decision, FusionGateDecision):
        raise ValueError("fusion policy returned a malformed decision")
    if decision.sku_id is None:
        return decision
    local_index = max(
        range(len(dino.candidate_sku_ids)),
        key=lambda index: (dino.local_scores[index], -index),
    )
    local_top1 = dino.candidate_sku_ids[local_index]
    repvit_global = tuple(
        (tight + context) / 2
        for tight, context in zip(
            repvit.tight_scores, repvit.context_scores, strict=True
        )
    )
    globally_agreed = (
        decision.sku_id == _score_top1(repvit_global) == _score_top1(dino.global_scores)
        and decision.margin >= 0.85
    )
    if decision.sku_id != local_top1 and not globally_agreed:
        raise ValueError("fusion approval lacks local or global consensus")
    return decision


def _score_top1(scores: tuple[float, ...]) -> int:
    return max(range(20), key=lambda index: (scores[index], -index)) + 1


def _registered_decision(
    sku_id: object, confidence: object, top3: object, label: str
) -> None:
    _top3(top3)
    if type(sku_id) is not int or sku_id not in CANONICAL_SKUS:
        raise ValueError(f"{label} decision SKU is invalid")
    if not _finite(confidence) or not 0 <= confidence <= 1:
        raise ValueError(f"{label} confidence must be within [0, 1]")
    if top3[0][0] != sku_id:
        raise ValueError(f"{label} decision must equal Top-1")


def _top3(value: object) -> None:
    if not isinstance(value, tuple) or len(value) != 3:
        raise ValueError("decision requires exact Top3")
    sku_ids = tuple(
        item[0] for item in value if isinstance(item, tuple) and len(item) == 2
    )
    scores = tuple(
        item[1] for item in value if isinstance(item, tuple) and len(item) == 2
    )
    if (
        len(sku_ids) != 3
        or len(set(sku_ids)) != 3
        or any(
            type(sku_id) is not int or sku_id not in CANONICAL_SKUS
            for sku_id in sku_ids
        )
        or any(not _finite(score) or not 0 <= score <= 1 for score in scores)
        or scores != tuple(sorted(scores, reverse=True))
    ):
        raise ValueError("decision Top3 is invalid")


def _tray_roi(value: object) -> None:
    if (
        not isinstance(value, tuple)
        or len(value) != 4
        or any(not _finite(item) for item in value)
    ):
        raise ValueError("tray ROI must contain four finite coordinates")
    x1, y1, x2, y2 = value
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("tray ROI must be non-negative and ordered")


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
