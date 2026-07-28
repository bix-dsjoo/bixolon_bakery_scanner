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
from .full_evidence import FullEvidenceRow
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
_V1_KEYS = frozenset({"schema_version", "ranker", "risk_calibrator", "risk_threshold", "development_evidence_sha256", "artifact_hashes"})
_V2_KEYS = _V1_KEYS | {"decision_rule"}
_V3_KEYS = _V2_KEYS | {"consensus_margin_floor"}
_DECISION_RULES = frozenset(
    {
        "risk_threshold_v1",
        "fusion_local_agree_v1",
        "fusion_local_or_global_consensus_margin_v1",
    }
)


@dataclass(frozen=True, slots=True)
class FusionPolicyArtifact:
    ranker: FusionRanker
    risk_calibrator: RiskCalibrator
    risk_threshold: float
    development_evidence_sha256: str
    artifact_hashes: Mapping[str, str]
    decision_rule: str = "risk_threshold_v1"
    schema_version: int = 2
    consensus_margin_floor: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ranker, FusionRanker) or not isinstance(self.risk_calibrator, RiskCalibrator):
            raise ValueError("fusion policy requires ranker and risk calibrator")
        if len(self.ranker.feature_mean) != len(self.risk_calibrator.feature_mean):
            raise ValueError("fusion ranker and risk feature schemas must match")
        if not isinstance(self.risk_threshold, (int, float)) or isinstance(self.risk_threshold, bool) or not math.isfinite(float(self.risk_threshold)) or not 0.0 <= float(self.risk_threshold) <= 1.0:
            raise ValueError("risk_threshold must be between 0 and 1")
        object.__setattr__(self, "risk_threshold", float(self.risk_threshold))
        if type(self.schema_version) is not int or self.schema_version not in {1, 2, 3}:
            raise ValueError("fusion policy schema_version must be 1, 2, or 3")
        if self.decision_rule not in _DECISION_RULES:
            raise ValueError("fusion policy decision_rule is invalid")
        if self.schema_version == 1 and self.decision_rule != "risk_threshold_v1":
            raise ValueError("schema version 1 only supports risk_threshold_v1")
        if self.schema_version == 2 and self.decision_rule not in {"risk_threshold_v1", "fusion_local_agree_v1"}:
            raise ValueError("schema version 2 decision_rule is invalid")
        if self.schema_version == 3 and self.decision_rule != "fusion_local_or_global_consensus_margin_v1":
            raise ValueError("schema version 3 only supports the consensus-margin decision rule")
        if self.schema_version == 3:
            if (
                not isinstance(self.consensus_margin_floor, (int, float))
                or isinstance(self.consensus_margin_floor, bool)
                or not math.isfinite(float(self.consensus_margin_floor))
                or not 0.0 <= float(self.consensus_margin_floor) <= 1.0
            ):
                raise ValueError("consensus_margin_floor must be between 0 and 1")
            object.__setattr__(self, "consensus_margin_floor", float(self.consensus_margin_floor))
        elif self.consensus_margin_floor is not None:
            raise ValueError("consensus_margin_floor requires schema version 3")
        if not isinstance(self.development_evidence_sha256, str) or not _SHA256.fullmatch(self.development_evidence_sha256):
            raise ValueError("development_evidence_sha256 must be a lowercase SHA-256 hash")
        hashes = dict(self.artifact_hashes)
        if set(hashes) != _HASH_KEYS or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in hashes.values()):
            raise ValueError("fusion policy artifact hashes are invalid")
        object.__setattr__(self, "artifact_hashes", hashes)

    def to_json_bytes(self) -> bytes:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "ranker": _model_mapping(self.ranker),
            "risk_calibrator": _model_mapping(self.risk_calibrator),
            "risk_threshold": self.risk_threshold,
            "development_evidence_sha256": self.development_evidence_sha256,
            "artifact_hashes": dict(self.artifact_hashes),
        }
        if self.schema_version == 2:
            payload["decision_rule"] = self.decision_rule
        elif self.schema_version == 3:
            payload["decision_rule"] = self.decision_rule
            payload["consensus_margin_floor"] = self.consensus_margin_floor
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def decide(self, row: "FullEvidenceRow") -> tuple[FusionDecision, float]:
        """Apply the immutable common policy without selecting any threshold."""
        ranked = self.ranker.rank(row)
        risk = self.risk_calibrator.predict_ranked_risk(RankedEvidence(row, ranked))
        if self.decision_rule == "risk_threshold_v1":
            accepted = risk <= self.risk_threshold
        else:
            local_top1 = _local_top1(row)
            accepted = ranked.sku_ids[0] == local_top1
            if self.decision_rule == "fusion_local_or_global_consensus_margin_v1":
                accepted = accepted or (
                    ranked.sku_ids[0] == _global_top1(row.repvit_values) == _global_top1(row.dinov3_values)
                    and ranked.scores[0] - ranked.scores[1] >= self.consensus_margin_floor
                )
        if accepted:
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
        if not isinstance(value, dict):
            raise ValueError("fusion policy artifact schema is invalid")
        schema_version = value.get("schema_version")
        if schema_version == 1 and set(value) == _V1_KEYS:
            decision_rule = "risk_threshold_v1"
            consensus_margin_floor = None
        elif schema_version == 2 and set(value) == _V2_KEYS:
            decision_rule = value.get("decision_rule")
            consensus_margin_floor = None
        elif schema_version == 3 and set(value) == _V3_KEYS:
            decision_rule = value.get("decision_rule")
            consensus_margin_floor = value.get("consensus_margin_floor")
        else:
            raise ValueError("fusion policy artifact schema is invalid")
        try:
            ranker = FusionRanker(**_model_arguments(value["ranker"]))
            risk = RiskCalibrator(**_model_arguments(value["risk_calibrator"]))
            result = cls(
                ranker,
                risk,
                value["risk_threshold"],
                value["development_evidence_sha256"],
                value["artifact_hashes"],
                decision_rule=decision_rule,
                schema_version=schema_version,
                consensus_margin_floor=consensus_margin_floor,
            )
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


def _global_top1(values: tuple[float, ...]) -> int:
    return min(range(1, len(values) + 1), key=lambda sku_id: (-values[sku_id - 1], sku_id))


def _local_top1(row: FullEvidenceRow) -> int:
    return min(
        zip(row.candidate_sku_ids, row.local_values, strict=True),
        key=lambda item: (-item[1], item[0]),
    )[0]


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
