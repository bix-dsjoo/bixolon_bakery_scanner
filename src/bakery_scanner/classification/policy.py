"""Versioned calibration, score fusion, and fail-closed SKU decisions."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from bakery_scanner.contracts import Box

from .contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
    SkuCandidate,
    StageTimings,
)


_SKU_IDS = tuple(range(1, 21))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPVIT_ARTIFACT_ID = "repvit_m1_15plus5_v1"
_DINOV3_ARTIFACT_ID = "dinov3_vits16_15plus5_v1"
_CALIBRATION_KEYS = frozenset(
    {
        "schema_version",
        "calibration_id",
        "repvit_artifact_id",
        "dinov3_artifact_id",
        "repvit_temperature",
        "dinov3_temperature",
        "alpha",
        "direct_threshold",
        "direct_margin",
        "direct_max_crop_disagreement",
        "direct_max_prototype_distance",
        "dino_threshold",
        "fused_margin",
        "evidence_sha256",
        "development_identity_sha256",
        "repvit_checkpoint_sha256",
        "repvit_manifest_sha256",
        "repvit_prototype_sha256",
        "dinov3_weights_sha256",
        "dinov3_support_sha256",
        "preprocess_sha256",
    }
)


@dataclass(frozen=True, slots=True)
class PolicyCalibration:
    schema_version: int
    calibration_id: str
    repvit_artifact_id: str
    dinov3_artifact_id: str
    repvit_temperature: float
    dinov3_temperature: float
    alpha: float
    direct_threshold: float
    direct_margin: float
    direct_max_crop_disagreement: float
    direct_max_prototype_distance: float
    dino_threshold: float
    fused_margin: float
    evidence_sha256: str
    development_identity_sha256: str = "0" * 64
    repvit_checkpoint_sha256: str = "0" * 64
    repvit_manifest_sha256: str = "0" * 64
    repvit_prototype_sha256: str = "0" * 64
    dinov3_weights_sha256: str = "0" * 64
    dinov3_support_sha256: str = "0" * 64
    preprocess_sha256: str = "0" * 64

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ValueError("schema_version must be 2")
        if not isinstance(self.calibration_id, str) or not self.calibration_id:
            raise ValueError("calibration_id must not be empty")
        if self.repvit_artifact_id != _REPVIT_ARTIFACT_ID:
            raise ValueError(f"repvit_artifact_id must be {_REPVIT_ARTIFACT_ID}")
        if self.dinov3_artifact_id != _DINOV3_ARTIFACT_ID:
            raise ValueError(f"dinov3_artifact_id must be {_DINOV3_ARTIFACT_ID}")
        for field in (
            "evidence_sha256",
            "development_identity_sha256",
            "repvit_checkpoint_sha256",
            "repvit_manifest_sha256",
            "repvit_prototype_sha256",
            "dinov3_weights_sha256",
            "dinov3_support_sha256",
            "preprocess_sha256",
        ):
            if not isinstance(getattr(self, field), str) or not _SHA256.fullmatch(
                getattr(self, field)
            ):
                raise ValueError(f"{field} must be a lowercase SHA-256 hash")

        for field in ("repvit_temperature", "dinov3_temperature"):
            value = _finite_number(getattr(self, field), field)
            if value <= 0.0:
                raise ValueError(f"{field} must be greater than zero")
            object.__setattr__(self, field, value)
        for field in (
            "alpha",
            "direct_threshold",
            "direct_margin",
            "direct_max_crop_disagreement",
            "dino_threshold",
            "fused_margin",
        ):
            value = _finite_number(getattr(self, field), field)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be between 0 and 1")
            object.__setattr__(self, field, value)
        prototype_distance = _finite_number(
            self.direct_max_prototype_distance,
            "direct_max_prototype_distance",
        )
        if not 0.0 <= prototype_distance <= 2.0:
            raise ValueError("direct_max_prototype_distance must be between 0 and 2")
        object.__setattr__(self, "direct_max_prototype_distance", prototype_distance)

    def to_json_bytes(self) -> bytes:
        payload = {
            "alpha": self.alpha,
            "calibration_id": self.calibration_id,
            "dino_threshold": self.dino_threshold,
            "dinov3_artifact_id": self.dinov3_artifact_id,
            "dinov3_temperature": self.dinov3_temperature,
            "direct_margin": self.direct_margin,
            "direct_max_crop_disagreement": self.direct_max_crop_disagreement,
            "direct_max_prototype_distance": self.direct_max_prototype_distance,
            "direct_threshold": self.direct_threshold,
            "evidence_sha256": self.evidence_sha256,
            "development_identity_sha256": self.development_identity_sha256,
            "repvit_checkpoint_sha256": self.repvit_checkpoint_sha256,
            "repvit_manifest_sha256": self.repvit_manifest_sha256,
            "repvit_prototype_sha256": self.repvit_prototype_sha256,
            "dinov3_weights_sha256": self.dinov3_weights_sha256,
            "dinov3_support_sha256": self.dinov3_support_sha256,
            "preprocess_sha256": self.preprocess_sha256,
            "fused_margin": self.fused_margin,
            "repvit_artifact_id": self.repvit_artifact_id,
            "repvit_temperature": self.repvit_temperature,
            "schema_version": self.schema_version,
        }
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "PolicyCalibration":
        if not isinstance(payload, bytes):
            raise ValueError("calibration payload must be bytes")
        # Versioned artifacts are canonical JSON; repository text files may add
        # exactly one terminal newline without changing that artifact identity.
        canonical_payload = payload.removesuffix(b"\r\n").removesuffix(b"\n")
        try:
            decoded = json.loads(
                canonical_payload.decode("utf-8"),
                parse_constant=lambda value: _reject_json_constant(value),
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("calibration payload must be valid UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("calibration payload must be a JSON object")
        if set(decoded) != _CALIBRATION_KEYS:
            raise ValueError("calibration payload has missing or extra keys")
        try:
            result = cls(**decoded)
        except TypeError as exc:
            raise ValueError("calibration payload has invalid field types") from exc
        if result.to_json_bytes() != canonical_payload:
            raise ValueError("calibration payload must use canonical JSON")
        return result


@dataclass(frozen=True, slots=True)
class DirectEvidence:
    """RepViT-only safety evidence for direct SKU confirmation."""

    crop_disagreement: float
    nearest_prototype_distance: float

    def __post_init__(self) -> None:
        disagreement = _finite_number(self.crop_disagreement, "crop_disagreement")
        distance = _finite_number(
            self.nearest_prototype_distance,
            "nearest_prototype_distance",
        )
        if not 0.0 <= disagreement <= 1.0:
            raise ValueError("crop_disagreement must be between 0 and 1")
        if not 0.0 <= distance <= 2.0:
            raise ValueError("nearest_prototype_distance must be between 0 and 2")
        object.__setattr__(self, "crop_disagreement", disagreement)
        object.__setattr__(self, "nearest_prototype_distance", distance)


class DecisionPolicy:
    """Apply a validated calibration artifact to canonical model scores."""

    def __init__(
        self,
        calibration: PolicyCalibration,
        *,
        provenance: ModelProvenance,
    ) -> None:
        if provenance.repvit_artifact_id != calibration.repvit_artifact_id:
            raise ValueError("provenance RepViT artifact does not match calibration")
        if provenance.dinov3_artifact_id != calibration.dinov3_artifact_id:
            raise ValueError("provenance DINOv3 artifact does not match calibration")
        for provenance_field, calibration_field in (
            ("repvit_sha256", "repvit_checkpoint_sha256"),
            ("repvit_manifest_sha256", "repvit_manifest_sha256"),
            ("repvit_prototype_sha256", "repvit_prototype_sha256"),
            ("dinov3_sha256", "dinov3_weights_sha256"),
            ("dinov3_support_sha256", "dinov3_support_sha256"),
            ("preprocess_sha256", "preprocess_sha256"),
        ):
            if getattr(provenance, provenance_field) != getattr(
                calibration, calibration_field
            ):
                raise ValueError(
                    f"provenance {provenance_field} does not match calibration"
                )
        if provenance.calibration_id != calibration.calibration_id:
            raise ValueError("provenance calibration_id does not match calibration")
        calibration_sha256 = hashlib.sha256(calibration.to_json_bytes()).hexdigest()
        if provenance.calibration_sha256 != calibration_sha256:
            raise ValueError(
                "provenance calibration SHA-256 does not match calibration"
            )
        self.calibration = calibration
        self.provenance = provenance
        self._empty_timings = StageTimings(0.0, 0.0, 0.0)

    def direct(
        self,
        repvit_scores: ModelScoreVector,
        *,
        evidence: "DirectEvidence",
        box: Box,
    ) -> ClassificationDecision | None:
        _require_score_vector(
            repvit_scores,
            model_id=self.calibration.repvit_artifact_id,
            score_kind="probability",
        )
        repvit = calibrate_repvit(
            repvit_scores.values,
            self.calibration.repvit_temperature,
        )
        ranked = _rank(repvit, repvit_scores.sku_ids)
        best, second = ranked[:2]
        if (
            repvit[best] >= self.calibration.direct_threshold
            and repvit[best] - repvit[second] >= self.calibration.direct_margin
            and evidence.crop_disagreement
            <= self.calibration.direct_max_crop_disagreement
            and evidence.nearest_prototype_distance
            <= self.calibration.direct_max_prototype_distance
        ):
            return self._sku_decision(
                repvit_scores.sku_ids[best],
                repvit[best],
                DecisionPath.REPVIT_DIRECT,
                box,
            )
        return None


    def after_recheck(
        self,
        repvit_scores: ModelScoreVector,
        dino_scores: ModelScoreVector,
        *,
        box: Box,
    ) -> ClassificationDecision:
        _require_score_vector(
            repvit_scores,
            model_id=self.calibration.repvit_artifact_id,
            score_kind="probability",
        )
        _require_score_vector(
            dino_scores,
            model_id=self.calibration.dinov3_artifact_id,
            score_kind="similarity",
        )
        if repvit_scores.sku_ids != dino_scores.sku_ids:
            raise ValueError("RepViT and DINOv3 SKU orders must match")

        repvit = calibrate_repvit(
            repvit_scores.values,
            self.calibration.repvit_temperature,
        )
        dino = calibrate_dinov3(
            dino_scores.values,
            self.calibration.dinov3_temperature,
        )
        fused = fuse_probabilities(repvit, dino, self.calibration.alpha)
        repvit_ranked = _rank(repvit, repvit_scores.sku_ids)
        dino_ranked = _rank(dino, dino_scores.sku_ids)
        fused_ranked = _rank(fused, repvit_scores.sku_ids)
        fused_best, fused_second = fused_ranked[:2]

        if repvit_scores.sku_ids[repvit_ranked[0]] != dino_scores.sku_ids[dino_ranked[0]]:
            reason = "cross_model_disagreement"
        elif dino[dino_ranked[0]] < self.calibration.dino_threshold:
            reason = "dino_low_confidence"
        elif fused[fused_best] - fused[fused_second] < self.calibration.fused_margin:
            reason = "fused_low_margin"
        else:
            return self._sku_decision(
                repvit_scores.sku_ids[fused_best],
                fused[fused_best],
                DecisionPath.DINOV3_CONFIRMED,
                box,
            )
        return self._unknown_decision(
            fused,
            repvit_scores.sku_ids,
            fused_ranked,
            box,
            reason=reason,
        )

    def after_local_recheck(
        self,
        repvit_scores: ModelScoreVector,
        dino_global_scores: ModelScoreVector,
        local_scores: dict[int, float],
        *,
        box: Box,
    ) -> ClassificationDecision:
        """Fuse DINO global/local retrieval without treating local as a vote."""
        _require_score_vector(
            repvit_scores,
            model_id=self.calibration.repvit_artifact_id,
            score_kind="probability",
        )
        _require_score_vector(
            dino_global_scores,
            model_id=self.calibration.dinov3_artifact_id,
            score_kind="similarity",
        )
        candidate_ids = tuple(local_scores)
        if not 1 <= len(candidate_ids) <= 7 or len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("local scores must contain one to seven unique candidates")
        if any(sku_id not in _SKU_IDS for sku_id in candidate_ids):
            raise ValueError("local scores must use canonical SKU IDs")
        local_values = tuple(_finite_number(local_scores[sku_id], "local score") for sku_id in candidate_ids)
        repvit = calibrate_repvit(repvit_scores.values, self.calibration.repvit_temperature)
        dino = calibrate_dinov3(dino_global_scores.values, self.calibration.dinov3_temperature)
        local = _softmax(np.asarray(local_values, dtype=np.float64))
        candidate_indices = tuple(sku_id - 1 for sku_id in candidate_ids)
        candidate_global = np.asarray([dino[index] for index in candidate_indices], dtype=np.float64)
        candidate_family = _softmax(
            np.log(np.clip(candidate_global, 1e-12, 1.0)) + np.log(np.asarray(local))
        )
        candidate_repvit = _softmax(
            np.log(np.clip(np.asarray([repvit[index] for index in candidate_indices]), 1e-12, 1.0))
        )
        fused = _softmax(
            self.calibration.alpha * np.log(np.asarray(candidate_repvit))
            + (1.0 - self.calibration.alpha) * np.log(np.asarray(candidate_family))
        )
        ranked = tuple(sorted(range(len(candidate_ids)), key=lambda index: (-fused[index], candidate_ids[index])))
        best, second = ranked[0], ranked[1] if len(ranked) > 1 else ranked[0]
        repvit_top = _rank(repvit, repvit_scores.sku_ids)[0]
        selected_global = candidate_indices[best]
        if (
            candidate_ids[best] == repvit_scores.sku_ids[repvit_top]
            and dino[selected_global] >= self.calibration.dino_threshold
            and fused[best] - fused[second] >= self.calibration.fused_margin
        ):
            return self._sku_decision(candidate_ids[best], fused[best], DecisionPath.DINOV3_CONFIRMED, box)
        # Local matching is an additional DINO-family consistency check.  Falling
        # back to global-only confirmation here would allow a local disagreement
        # to silently turn into an automatic SKU decision.
        global_fused = fuse_probabilities(repvit, dino, self.calibration.alpha)
        return self._unknown_decision(
            global_fused,
            repvit_scores.sku_ids,
            _rank(global_fused, repvit_scores.sku_ids),
            box,
            reason="dino_local_disagreement",
        )

    def dino_failure(
        self,
        repvit_scores: ModelScoreVector,
        *,
        box: Box,
    ) -> ClassificationDecision:
        _require_score_vector(
            repvit_scores,
            model_id=self.calibration.repvit_artifact_id,
            score_kind="probability",
        )
        repvit = calibrate_repvit(
            repvit_scores.values,
            self.calibration.repvit_temperature,
        )
        return self._unknown_decision(
            repvit,
            repvit_scores.sku_ids,
            _rank(repvit, repvit_scores.sku_ids),
            box,
            reason="dino_inference_failed",
        )

    def _sku_decision(
        self,
        sku_id: int,
        confidence: float,
        path: DecisionPath,
        box: Box,
    ) -> ClassificationDecision:
        return ClassificationDecision(
            decision="sku",
            sku_id=sku_id,
            confidence=float(confidence),
            box=box,
            decision_path=path,
            top3=(),
            provenance=self.provenance,
            timings=self._empty_timings,
        )

    def _unknown_decision(
        self,
        scores: Sequence[float],
        sku_ids: tuple[int, ...],
        ranked: Sequence[int],
        box: Box,
        *,
        reason: str,
    ) -> ClassificationDecision:
        top_indices = ranked[:3]
        candidates = tuple(
            SkuCandidate(
                rank=rank,
                sku_id=sku_ids[index],
                score=float(scores[index]),
            )
            for rank, index in enumerate(top_indices, start=1)
        )
        return ClassificationDecision(
            decision="unknown",
            sku_id=None,
            confidence=candidates[0].score,
            box=box,
            decision_path=DecisionPath.UNKNOWN_TOP3,
            top3=candidates,
            provenance=self.provenance,
            timings=self._empty_timings,
            unknown_reason=reason,
        )


def calibrate_repvit(
    probabilities: Sequence[float],
    temperature: float,
) -> tuple[float, ...]:
    values = _finite_vector(probabilities, "RepViT probabilities")
    if np.any((values < 0.0) | (values > 1.0)):
        raise ValueError("RepViT probabilities must be between 0 and 1")
    if not np.any(values > 0.0):
        raise ValueError("RepViT probabilities must contain a positive value")
    checked_temperature = _positive_temperature(temperature)
    logits = np.log(np.clip(values, 1e-12, 1.0)) / checked_temperature
    return _softmax(logits)


def calibrate_dinov3(
    similarities: Sequence[float],
    temperature: float,
) -> tuple[float, ...]:
    values = _finite_vector(similarities, "DINOv3 similarities")
    checked_temperature = _positive_temperature(temperature)
    return _softmax(values / checked_temperature)


def fuse_probabilities(
    repvit: Sequence[float],
    dino: Sequence[float],
    alpha: float,
) -> tuple[float, ...]:
    repvit_values = _finite_vector(repvit, "calibrated RepViT probabilities")
    dino_values = _finite_vector(dino, "calibrated DINOv3 probabilities")
    if repvit_values.shape != dino_values.shape:
        raise ValueError("calibrated probability vectors must have equal length")
    for values, label in (
        (repvit_values, "calibrated RepViT probabilities"),
        (dino_values, "calibrated DINOv3 probabilities"),
    ):
        if np.any((values < 0.0) | (values > 1.0)):
            raise ValueError(f"{label} must be between 0 and 1")
        if not np.any(values > 0.0):
            raise ValueError(f"{label} must contain a positive value")
    checked_alpha = _finite_number(alpha, "alpha")
    if not 0.0 <= checked_alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1")
    fused_logits = checked_alpha * np.log(np.clip(repvit_values, 1e-12, 1.0))
    fused_logits += (1.0 - checked_alpha) * np.log(np.clip(dino_values, 1e-12, 1.0))
    return _softmax(fused_logits)


def _softmax(logits: np.ndarray) -> tuple[float, ...]:
    shifted = logits - np.max(logits)
    exponentials = np.exp(shifted)
    probabilities = exponentials / exponentials.sum(dtype=np.float64)
    return tuple(float(value) for value in probabilities)


def _finite_vector(values: Sequence[float], label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{label} must be a non-empty one-dimensional vector")
    if not np.isfinite(result).all():
        raise ValueError(f"{label} must be finite")
    return result


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _positive_temperature(value: object) -> float:
    result = _finite_number(value, "temperature")
    if result <= 0.0:
        raise ValueError("temperature must be greater than zero")
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _require_score_vector(
    scores: ModelScoreVector,
    *,
    model_id: str,
    score_kind: str,
) -> None:
    if scores.model_id != model_id:
        raise ValueError(f"score model_id must be {model_id}")
    if scores.sku_ids != _SKU_IDS:
        raise ValueError("score SKU IDs must be in canonical order")
    if scores.score_kind != score_kind:
        raise ValueError(f"score_kind must be {score_kind}")


def _rank(
    scores: Sequence[float],
    sku_ids: tuple[int, ...],
) -> tuple[int, ...]:
    return tuple(
        sorted(
            range(len(scores)),
            key=lambda index: (-scores[index], sku_ids[index]),
        )
    )
