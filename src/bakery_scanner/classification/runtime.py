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

from .config import ClassifierConfig, preprocess_sha256
from .contracts import ClassificationDecision, ModelProvenance, StageTimings
from .dinov3 import DinoV3Rechecker
from .errors import DinoInferenceError
from .policy import DecisionPolicy, PolicyCalibration
from .preprocess import make_padded_crops
from .repvit import RepVitM1Runner


class _ScoreRunner(Protocol):
    def score(self, crops: tuple[Image.Image, ...]): ...


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
        repvit: _ScoreRunner,
        dino_loader: Callable[[], _ScoreRunner],
        policy: DecisionPolicy,
        clock: _Clock | None = None,
    ) -> None:
        self.config = config
        self.repvit = repvit
        self.policy = policy
        self._dino_loader = dino_loader
        self._dino: _ScoreRunner | None = None
        device = torch.device(config.runtime.device.lower())
        self.clock = clock or _CudaClock(device)

    @classmethod
    def load(cls, config_path: Path) -> "ClassifierPipeline":
        """Load strict configuration, calibration, and the primary runner."""
        config = ClassifierConfig.load(config_path)
        calibration_payload = config.calibration.artifact.read_bytes()
        calibration = PolicyCalibration.from_json_bytes(calibration_payload)
        provenance = ModelProvenance(
            repvit_artifact_id=config.repvit.artifact_id,
            repvit_sha256=config.repvit.checkpoint_sha256,
            dinov3_artifact_id=config.dinov3.artifact_id,
            dinov3_sha256=config.dinov3.weights_sha256,
            dinov3_support_sha256=config.dinov3.support_sha256,
            calibration_id=calibration.calibration_id,
            calibration_sha256=hashlib.sha256(calibration_payload).hexdigest(),
            preprocess_sha256=preprocess_sha256(config.preprocess),
        )
        policy = DecisionPolicy(calibration, provenance=provenance)
        repvit = RepVitM1Runner.load(config)
        return cls(
            config=config,
            repvit=repvit,
            dino_loader=lambda: DinoV3Rechecker.load(config),
            policy=policy,
        )

    def infer(
        self,
        image: Image.Image,
        box: Box,
    ) -> ClassificationDecision:
        _validate_original_box(image, box)
        total_started = self._timestamp()
        crops = make_padded_crops(
            image,
            box,
            self.config.preprocess.paddings,
        )

        repvit_started = self._timestamp()
        repvit_scores = self.repvit.score(crops)
        repvit_finished = self._timestamp()
        direct = self.policy.direct(repvit_scores, box=box)
        if direct is not None:
            total_finished = self._timestamp()
            return self._with_metadata(
                direct,
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=0.0,
                total_ms=_milliseconds(total_started, total_finished),
            )

        dinov3_started = self._timestamp()
        dino = self._get_dino()
        try:
            dino_scores = dino.score(crops)
        except DinoInferenceError as exc:
            dinov3_finished = self._timestamp()
            decision = self.policy.dino_failure(repvit_scores, box=box)
            total_finished = self._timestamp()
            return self._with_metadata(
                decision,
                repvit_ms=_milliseconds(repvit_started, repvit_finished),
                dinov3_ms=_milliseconds(
                    dinov3_started,
                    dinov3_finished,
                ),
                total_ms=_milliseconds(total_started, total_finished),
                failure_code=exc.code,
            )

        dinov3_finished = self._timestamp()
        decision = self.policy.after_recheck(
            repvit_scores,
            dino_scores,
            box=box,
        )
        total_finished = self._timestamp()
        return self._with_metadata(
            decision,
            repvit_ms=_milliseconds(repvit_started, repvit_finished),
            dinov3_ms=_milliseconds(dinov3_started, dinov3_finished),
            total_ms=_milliseconds(total_started, total_finished),
        )

    def preflight_models(self, image: Image.Image, box: Box) -> None:
        """Load and execute both model stages before measured inference."""
        _validate_original_box(image, box)
        crops = make_padded_crops(
            image,
            box,
            self.config.preprocess.paddings,
        )
        self.repvit.score(crops)
        self._get_dino().score(crops)
        self.clock.synchronize()

    def _get_dino(self) -> _ScoreRunner:
        if self._dino is None:
            loaded = self._dino_loader()
            if loaded is None or not callable(getattr(loaded, "score", None)):
                raise TypeError("DINO loader must return a score runner")
            self._dino = loaded
        return self._dino

    def _timestamp(self) -> float:
        self.clock.synchronize()
        return self.clock()

    def _with_metadata(
        self,
        decision: ClassificationDecision,
        *,
        repvit_ms: float,
        dinov3_ms: float,
        total_ms: float,
        failure_code: str | None = None,
    ) -> ClassificationDecision:
        provenance = replace(
            decision.provenance,
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


def _validate_original_box(image: Image.Image, box: Box) -> None:
    if not isinstance(box, Box):
        raise ValueError("box must be a Box in original image coordinates")
    if (
        box.x < 0.0
        or box.y < 0.0
        or box.x + box.width > image.width
        or box.y + box.height > image.height
    ):
        raise ValueError("box must stay within original image coordinates")
