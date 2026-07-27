"""Lazy online orchestration for verified bakery product crops."""

from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable, Protocol

import torch
from PIL import Image

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import CanonicalImage, canonicalize_image

from .config import ClassifierConfig, preprocess_sha256
from .contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    SkuCandidate,
    StageTimings,
)
from .dinov3 import DinoV3Rechecker
from .errors import DinoInferenceError
from .full_evidence import FullEvidenceRow
from .fusion_policy import FusionPolicyArtifact
from .local_bank import LocalPatchBank
from .policy import DecisionPolicy, DirectEvidence, PolicyCalibration
from .preprocess import make_padded_crops, make_padded_crops_with_product_boxes
from .repvit import RepVitM1Runner, RepVitPrototypeBank


class _ScoreRunner(Protocol):
    def score(self, crops: tuple[Image.Image, ...]): ...


class _RepVitRunner(_ScoreRunner, Protocol):
    def score_with_evidence(self, crops: tuple[Image.Image, ...]): ...


class _PrototypeBank(Protocol):
    def distances(self, feature: torch.Tensor) -> tuple[float, ...]: ...


class _Clock(Protocol):
    def __call__(self) -> float: ...

    def synchronize(self) -> None: ...


class _CudaClock:
    def __init__(self, device: torch.device) -> None:
        self.device = device

    def synchronize(self) -> None:
        if self.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize(self.device)

    def __call__(self) -> float:
        return time.perf_counter()


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

    @classmethod
    def load(
        cls,
        config_path: Path,
        *,
        calibration_path: Path | None = None,
    ) -> "ClassifierPipeline":
        """Load strict configuration, calibration, and the primary runner."""
        config = ClassifierConfig.load(config_path)
        calibration_payload = (calibration_path or config.calibration.artifact).read_bytes()
        calibration = PolicyCalibration.from_json_bytes(calibration_payload)
        provenance = ModelProvenance(
            repvit_artifact_id=config.repvit.artifact_id,
            repvit_sha256=config.repvit.checkpoint_sha256,
            dinov3_artifact_id=config.dinov3.artifact_id,
            dinov3_sha256=config.dinov3.weights_sha256,
            dinov3_support_sha256=config.dinov3.support_sha256,
            calibration_id=calibration.calibration_id,
            calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
            preprocess_sha256=preprocess_sha256(config.preprocess),
            repvit_manifest_sha256=config.repvit.manifest_sha256,
            repvit_prototype_sha256=config.repvit.prototype_bank_sha256 or "0" * 64,
        )
        policy = DecisionPolicy(calibration, provenance=provenance)
        fusion_policy = None
        fusion_provenance = None
        if config.calibration.fusion_policy is not None:
            fusion_payload = config.calibration.fusion_policy.read_bytes()
            if hashlib.sha256(fusion_payload).hexdigest() != config.calibration.fusion_policy_sha256:
                raise ValueError("fusion policy SHA-256 does not match classifier config")
            fusion_policy = FusionPolicyArtifact.from_json_bytes(fusion_payload)
            expected_hashes = {
                "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
                "repvit_manifest_sha256": config.repvit.manifest_sha256,
                "repvit_prototype_sha256": config.repvit.prototype_bank_sha256 or "0" * 64,
                "dinov3_weights_sha256": config.dinov3.weights_sha256,
                "dinov3_support_sha256": config.dinov3.support_sha256,
                "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256 or "0" * 64,
                "preprocess_sha256": preprocess_sha256(config.preprocess),
            }
            if fusion_policy.artifact_hashes != expected_hashes:
                raise ValueError("fusion policy artifacts do not match classifier config")
            fusion_provenance = replace(
                provenance,
                calibration_id="fusion_policy_v1",
                calibration_sha256=hashlib.sha256(fusion_payload).hexdigest(),
            )
        repvit = RepVitM1Runner.load(config)
        if config.repvit.prototype_bank is None or config.repvit.prototype_bank_sha256 is None:
            raise ValueError("RepViT prototype bank is required for safe direct decisions")
        prototype_bank = RepVitPrototypeBank.load(
            config.repvit.prototype_bank,
            checkpoint_sha256=config.repvit.checkpoint_sha256,
            expected_preprocess_sha256=preprocess_sha256(config.preprocess),
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
            local_bank_loader=lambda: _load_local_bank(config),
        )

    def infer(
        self,
        image: Image.Image | CanonicalImage,
        box: Box,
    ) -> ClassificationDecision:
        frame = _canonical_frame(image)
        _validate_visual_box(frame, box)
        total_started = self._timestamp()
        crops, product_boxes = make_padded_crops_with_product_boxes(
            frame.image,
            box,
            self.config.preprocess.paddings,
        )

        repvit_started = self._timestamp()
        repvit_evidence = self.repvit.score_with_evidence(crops)
        repvit_scores = repvit_evidence.scores
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
            return self._with_metadata(
                direct,
                frame=frame,
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=0.0,
                total_ms=_milliseconds(total_started, total_finished),
            )

        dinov3_started = self._timestamp()
        dino = self._get_dino()
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
            elif local_bank is not None and callable(getattr(dino, "score_global_and_local", None)):
                dino_scores, local_scores = dino.score_global_and_local(
                    crops,
                    product_boxes,
                    local_bank,
                    repvit_scores=repvit_scores,
                )
                decision = self.policy.after_local_recheck(
                    repvit_scores,
                    dino_scores,
                    local_scores,
                    box=box,
                )
            else:
                dino_scores = dino.score(crops)
                decision = self.policy.after_recheck(repvit_scores, dino_scores, box=box)
        except DinoInferenceError as exc:
            dinov3_finished = self._timestamp()
            decision = self.policy.dino_failure(repvit_scores, box=box)
            total_finished = self._timestamp()
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
        return self._with_metadata(
            decision,
            frame=frame,
            repvit_ms=_milliseconds(repvit_started, repvit_finished),
            dinov3_ms=_milliseconds(dinov3_started, dinov3_finished),
            total_ms=_milliseconds(total_started, total_finished),
        )

    def preflight_models(self, image: Image.Image | CanonicalImage, box: Box) -> None:
        """Load and execute both model stages before measured inference."""
        frame = _canonical_frame(image)
        _validate_visual_box(frame, box)
        crops = make_padded_crops(
            frame.image,
            box,
            self.config.preprocess.paddings,
        )
        self.repvit.score_with_evidence(crops)
        self._get_dino().score(crops)
        self.clock.synchronize()

    def _get_dino(self) -> _ScoreRunner:
        if self._dino is None:
            loaded = self._dino_loader()
            if loaded is None or not callable(getattr(loaded, "score", None)):
                raise TypeError("DINO loader must return a score runner")
            self._dino = loaded
        return self._dino

    def _get_local_bank(self) -> object | None:
        if self._local_bank is None and self._local_bank_loader is not None:
            self._local_bank = self._local_bank_loader()
        return self._local_bank

    def _timestamp(self) -> float:
        self.clock.synchronize()
        return self.clock()

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
            preprocess_sha256=preprocess_sha256(self.config.preprocess),
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
            unknown_reason="fusion_risk_threshold",
        )

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


def _canonical_frame(image: Image.Image | CanonicalImage) -> CanonicalImage:
    if isinstance(image, CanonicalImage):
        return image
    return canonicalize_image(image)


def _validate_visual_box(frame: CanonicalImage, box: Box) -> None:
    frame.require_box(box)


def _load_local_bank(config: ClassifierConfig) -> LocalPatchBank:
    if config.dinov3.local_bank is None or config.dinov3.local_bank_sha256 is None:
        raise ValueError("DINO local patch bank is required for local recheck")
    bank = LocalPatchBank.load(
        config.dinov3.local_bank,
        dino_weights_sha256=config.dinov3.weights_sha256,
        preprocess_sha256=preprocess_sha256(config.preprocess),
    )
    if bank.sha256 != config.dinov3.local_bank_sha256:
        raise ValueError("DINO local patch bank SHA-256 mismatch")
    return bank
