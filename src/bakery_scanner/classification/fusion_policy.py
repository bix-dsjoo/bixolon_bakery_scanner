"""Immutable common ranker/risk policy artifacts."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Mapping

from .fusion_ranker import FusionRanker
from .fusion_ranker import RankedEvidence
from .fusion_evaluation import FusionDecision, evaluate_fusion_decisions
from .risk_calibrator import RiskCalibrator


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HASH_KEYS = frozenset(
    {
        "repvit_checkpoint_sha256",
        "repvit_manifest_sha256",
        "repvit_prototype_sha256",
        "dinov3_weights_sha256",
        "dinov3_support_sha256",
        "dinov3_local_bank_sha256",
        "preprocess_sha256",
    }
)
_KEYS = frozenset({"schema_version", "ranker", "risk_calibrator", "risk_threshold", "development_evidence_sha256", "artifact_hashes"})


@dataclass(frozen=True, slots=True)
class FusionPolicyArtifact:
    ranker: FusionRanker
    risk_calibrator: RiskCalibrator
    risk_threshold: float
    development_evidence_sha256: str
    artifact_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.ranker, FusionRanker) or not isinstance(self.risk_calibrator, RiskCalibrator):
            raise ValueError("fusion policy requires ranker and risk calibrator")
        if len(self.ranker.feature_mean) != len(self.risk_calibrator.feature_mean):
            raise ValueError("fusion ranker and risk feature schemas must match")
        if not isinstance(self.risk_threshold, (int, float)) or isinstance(self.risk_threshold, bool) or not math.isfinite(float(self.risk_threshold)) or not 0.0 <= float(self.risk_threshold) <= 1.0:
            raise ValueError("risk_threshold must be between 0 and 1")
        object.__setattr__(self, "risk_threshold", float(self.risk_threshold))
        if not isinstance(self.development_evidence_sha256, str) or not _SHA256.fullmatch(self.development_evidence_sha256):
            raise ValueError("development_evidence_sha256 must be a lowercase SHA-256 hash")
        hashes = dict(self.artifact_hashes)
        if set(hashes) != _HASH_KEYS or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in hashes.values()):
            raise ValueError("fusion policy artifact hashes are invalid")
        object.__setattr__(self, "artifact_hashes", hashes)

    def to_json_bytes(self) -> bytes:
        payload = {
            "schema_version": 1,
            "ranker": _model_mapping(self.ranker),
            "risk_calibrator": _model_mapping(self.risk_calibrator),
            "risk_threshold": self.risk_threshold,
            "development_evidence_sha256": self.development_evidence_sha256,
            "artifact_hashes": dict(self.artifact_hashes),
        }
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def decide(self, row: "FullEvidenceRow") -> tuple[FusionDecision, float]:
        """Apply the immutable common policy without selecting any threshold."""
        ranked = self.ranker.rank(row)
        risk = self.risk_calibrator.predict_ranked_risk(RankedEvidence(row, ranked))
        if risk <= self.risk_threshold:
            return (
                FusionDecision(
                    row.sample_id,
                    row.registered,
                    row.sku_id,
                    "sku",
                    ranked.sku_ids[0],
                    (),
                ),
                risk,
            )
        return (
            FusionDecision(
                row.sample_id,
                row.registered,
                row.sku_id,
                "unknown",
                None,
                ranked.sku_ids[:3],
            ),
            risk,
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "FusionPolicyArtifact":
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("fusion policy artifact must be valid JSON") from exc
        if not isinstance(value, dict) or set(value) != _KEYS or value.get("schema_version") != 1:
            raise ValueError("fusion policy artifact schema is invalid")
        try:
            ranker = FusionRanker(**_model_arguments(value["ranker"]))
            risk = RiskCalibrator(**_model_arguments(value["risk_calibrator"]))
            result = cls(ranker, risk, value["risk_threshold"], value["development_evidence_sha256"], value["artifact_hashes"])
        except (KeyError, TypeError) as exc:
            raise ValueError("fusion policy artifact fields are invalid") from exc
        if result.to_json_bytes() != payload:
            raise ValueError("fusion policy artifact must use canonical JSON")
        return result


def _model_mapping(model: FusionRanker | RiskCalibrator) -> dict[str, object]:
    return {
        "feature_mean": list(model.feature_mean),
        "feature_scale": list(model.feature_scale),
        "coefficients": list(model.coefficients),
        "intercept": model.intercept,
    }


def _model_arguments(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"feature_mean", "feature_scale", "coefficients", "intercept"}:
        raise ValueError("fusion policy model fields are invalid")
    return {
        "feature_mean": tuple(value["feature_mean"]),
        "feature_scale": tuple(value["feature_scale"]),
        "coefficients": tuple(value["coefficients"]),
        "intercept": value["intercept"],
    }


def validate_evidence_hashes(rows: tuple["FullEvidenceRow", ...], expected_hashes: Mapping[str, str]) -> None:
    """Reject evidence that does not originate from this exact model contract."""
    if set(expected_hashes) != _HASH_KEYS:
        raise ValueError("expected artifact hash keys are invalid")
    if not rows:
        raise ValueError("evidence rows must not be empty")
    for row in rows:
        observed = {
            "repvit_checkpoint_sha256": row.repvit_checkpoint_sha256,
            "repvit_manifest_sha256": row.repvit_manifest_sha256,
            "repvit_prototype_sha256": row.repvit_prototype_sha256,
            "dinov3_weights_sha256": row.dinov3_weights_sha256,
            "dinov3_support_sha256": row.dinov3_support_sha256,
            "dinov3_local_bank_sha256": row.dinov3_local_bank_sha256,
            "preprocess_sha256": row.preprocess_sha256,
        }
        if observed != dict(expected_hashes):
            raise ValueError(f"evidence artifact hash mismatch for {row.sample_id}")


def select_fusion_threshold(
    ranked_rows: tuple[RankedEvidence, ...],
    risk_calibrator: RiskCalibrator,
) -> float | None:
    """Choose the most conservative common threshold meeting all B1 targets."""
    if not ranked_rows:
        raise ValueError("fusion threshold selection requires ranked rows")
    risks = tuple(risk_calibrator.predict_ranked_risk(item) for item in ranked_rows)
    for threshold in sorted(set(risks)):
        decisions = tuple(
            FusionDecision(
                item.row.sample_id,
                item.row.registered,
                item.row.sku_id,
                "sku" if risk <= threshold else "unknown",
                item.ranked.sku_ids[0] if risk <= threshold else None,
                () if risk <= threshold else item.ranked.sku_ids[:3],
            )
            for item, risk in zip(ranked_rows, risks, strict=True)
        )
        if evaluate_fusion_decisions(decisions).target_passes:
            return threshold
    return None
