"""Fold-isolated calibration for the RTX 5080 15+5 classifier pipeline.

The operational command intentionally stops as unverified when the complete,
hash-admitted five-fold evidence set is not present.  The pure calibration
contract is exposed for hermetic tests and for a later admitted producer.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_FIELDS = (
    "split_sha256",
    "source_evidence_sha256",
    "repvit_checkpoint_sha256",
    "repvit_prototype_sha256",
    "dinov3_weights_sha256",
    "dinov3_support_sha256",
    "dinov3_local_bank_sha256",
    "preprocess_sha256",
    "code_sha256",
    "runtime_sha256",
    "dino_global_split_sha256",
    "dino_local_split_sha256",
    "dino_global_source_evidence_sha256",
    "dino_local_source_evidence_sha256",
    "dino_global_runtime_sha256",
    "dino_local_runtime_sha256",
    "dino_local_model_sha256",
    "dino_global_preprocess_sha256",
    "dino_local_preprocess_sha256",
)


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class CalibrationRow:
    identity: str
    scene_id: str
    object_id: str
    fold_index: int
    role: Literal["calibration"]
    declared_calibration_scene_ids: tuple[str, ...]
    declared_evaluation_scene_ids: tuple[str, ...]
    expected_sku_id: int
    predicted_sku_id: int
    confidence: float
    margin: float
    prototype_distance: float
    crop_disagreement: float
    ranked_sku_ids: tuple[int, int, int]
    ranked_scores: tuple[float, float, float]
    split_sha256: str
    source_evidence_sha256: str
    repvit_checkpoint_sha256: str
    repvit_prototype_sha256: str
    dinov3_weights_sha256: str
    dinov3_support_sha256: str
    dinov3_local_bank_sha256: str
    preprocess_sha256: str
    code_sha256: str
    runtime_sha256: str
    dino_global_fold_index: int
    dino_local_fold_index: int
    dino_global_split_sha256: str
    dino_local_split_sha256: str
    dino_global_source_evidence_sha256: str
    dino_local_source_evidence_sha256: str
    dino_global_runtime_sha256: str
    dino_local_runtime_sha256: str
    dino_local_model_sha256: str
    dino_global_preprocess_sha256: str
    dino_local_preprocess_sha256: str
    evidence_status: Literal["verified"] = "verified"

    def __post_init__(self) -> None:
        for field in ("identity", "scene_id", "object_id"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field):
                raise ValueError(f"{field} must not be empty")
        if type(self.fold_index) is not int or self.fold_index not in range(5):
            raise ValueError("fold index must be between 0 and 4")
        if self.role != "calibration":
            raise ValueError("calibration row must have calibration role")
        declared = self.declared_calibration_scene_ids
        evaluated = self.declared_evaluation_scene_ids
        if (
            not declared
            or len(declared) != len(set(declared))
            or len(evaluated) != len(set(evaluated))
            or set(declared) & set(evaluated)
        ):
            raise ValueError("declared calibration/evaluation scenes are invalid")
        if self.scene_id not in declared:
            raise ValueError("scene is not in the declared calibration role")
        for field in ("expected_sku_id", "predicted_sku_id"):
            if type(getattr(self, field)) is not int or getattr(self, field) not in range(1, 21):
                raise ValueError(f"{field} must be an active catalog SKU")
        for field in ("confidence", "margin", "prototype_distance", "crop_disagreement"):
            value = _finite(getattr(self, field), field)
            if value < 0.0 or (field in {"confidence", "margin", "crop_disagreement"} and value > 1.0):
                raise ValueError(f"{field} is outside its calibrated range")
            object.__setattr__(self, field, value)
        if (
            len(self.ranked_sku_ids) != 3
            or len(set(self.ranked_sku_ids)) != 3
            or any(type(item) is not int or item not in range(1, 21) for item in self.ranked_sku_ids)
            or self.ranked_sku_ids[0] != self.predicted_sku_id
        ):
            raise ValueError("candidate ranking must contain three unique active SKUs led by predicted_sku_id")
        scores = tuple(_finite(value, "ranking score") for value in self.ranked_scores)
        if any(not 0.0 <= value <= 1.0 for value in scores) or not (scores[0] >= scores[1] >= scores[2]):
            raise ValueError("candidate ranking scores must be finite and descending")
        object.__setattr__(self, "ranked_scores", scores)
        for field in _PROVENANCE_FIELDS:
            if not isinstance(getattr(self, field), str) or not _SHA256.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be a lowercase SHA-256")
        if self.dino_global_fold_index != self.fold_index or self.dino_local_fold_index != self.fold_index:
            raise ValueError("DINO evidence identity fold mismatch")
        if (
            self.dino_global_split_sha256 != self.split_sha256
            or self.dino_local_split_sha256 != self.split_sha256
            or self.dino_global_source_evidence_sha256 != self.source_evidence_sha256
            or self.dino_local_source_evidence_sha256 != self.source_evidence_sha256
            or self.dino_global_runtime_sha256 != self.runtime_sha256
            or self.dino_local_runtime_sha256 != self.runtime_sha256
            or self.dino_local_model_sha256 != self.dinov3_weights_sha256
            or self.dino_global_preprocess_sha256 != self.preprocess_sha256
            or self.dino_local_preprocess_sha256 != self.preprocess_sha256
        ):
            raise ValueError("DINO evidence identity mismatch")
        if self.evidence_status != "verified":
            raise ValueError("calibration evidence must have verified input status")


@dataclass(frozen=True, slots=True)
class DirectGate:
    enabled: bool
    confidence_min: float | None = None
    margin_min: float | None = None
    prototype_distance_max: float | None = None
    crop_disagreement_max: float | None = None
    accepted_count: int = 0
    wrong_accepted_count: int = 0


@dataclass(frozen=True, slots=True)
class CalibrationBundle:
    fold_index: int
    source_scene_ids: tuple[str, ...]
    evaluation_scene_ids: tuple[str, ...]
    direct_gates: Mapping[int, DirectGate]
    fusion_decision_rule: str
    consensus_margin_floor: float
    provenance: Mapping[str, str]

    def to_json_bytes(self) -> bytes:
        source_identities = tuple(sorted(_safe_scene_identity(value) for value in self.source_scene_ids))
        evaluation_identities = tuple(sorted(_safe_scene_identity(value) for value in self.evaluation_scene_ids))
        payload = {
            "schema_version": 1,
            "fold_index": self.fold_index,
            "source_scene_count": len(source_identities),
            "source_scene_identities": list(source_identities),
            "source_scene_identity_set_sha256": _canonical_sha256(source_identities),
            "evaluation_scene_count": len(evaluation_identities),
            "evaluation_scene_identities": list(evaluation_identities),
            "evaluation_scene_identity_set_sha256": _canonical_sha256(evaluation_identities),
            "direct_gates": {str(sku): asdict(self.direct_gates[sku]) for sku in range(1, 21)},
            "fusion_decision_rule": self.fusion_decision_rule,
            "consensus_margin_floor": self.consensus_margin_floor,
            "provenance": dict(self.provenance),
        }
        _reject_private_paths(payload)
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_json_bytes()).hexdigest()


def calibrate_fold(calibration_rows: Sequence[CalibrationRow], fold_index: int) -> CalibrationBundle:
    """Calibrate one fold without accepting data from any other role or fold."""
    rows = tuple(calibration_rows)
    if type(fold_index) is not int or fold_index not in range(5) or not rows:
        raise ValueError("fold calibration requires a non-empty valid fold")
    if any(not isinstance(row, CalibrationRow) for row in rows):
        raise ValueError("fold calibration rows must use CalibrationRow")
    identities = [row.identity for row in rows]
    object_ids = [row.object_id for row in rows]
    if len(identities) != len(set(identities)) or len(object_ids) != len(set(object_ids)):
        raise ValueError("duplicate calibration scene/object identity")
    if any(row.fold_index != fold_index for row in rows):
        raise ValueError("calibration row fold mismatch")
    if any(row.role != "calibration" for row in rows):
        raise ValueError("fold calibration accepts only calibration role")
    declared = rows[0].declared_calibration_scene_ids
    evaluated = rows[0].declared_evaluation_scene_ids
    if any(
        row.declared_calibration_scene_ids != declared
        or row.declared_evaluation_scene_ids != evaluated
        for row in rows
    ):
        raise ValueError("fold rows disagree on declared calibration/evaluation scenes")
    source_ids = tuple(sorted({row.scene_id for row in rows}))
    if source_ids != tuple(sorted(declared)) or set(source_ids) & set(evaluated):
        raise ValueError("source IDs must exactly equal the declared calibration role")
    provenance = {field: getattr(rows[0], field) for field in _PROVENANCE_FIELDS}
    if any(any(getattr(row, field) != value for field, value in provenance.items()) for row in rows[1:]):
        raise ValueError("calibration evidence identity mismatch")
    gates = {sku_id: _select_direct_gate(tuple(row for row in rows if row.predicted_sku_id == sku_id)) for sku_id in range(1, 21)}
    return CalibrationBundle(
        fold_index=fold_index,
        source_scene_ids=source_ids,
        evaluation_scene_ids=tuple(sorted(evaluated)),
        direct_gates=gates,
        fusion_decision_rule="fusion_local_or_global_consensus_margin_v1",
        consensus_margin_floor=0.85,
        provenance=provenance,
    )


def _select_direct_gate(rows: tuple[CalibrationRow, ...]) -> DirectGate:
    correct = tuple(row for row in rows if row.predicted_sku_id == row.expected_sku_id)
    if not correct:
        return DirectGate(False)
    candidates: list[tuple[tuple[float, ...], DirectGate]] = []
    for confidence, margin, distance, disagreement in itertools.product(
        sorted({row.confidence for row in rows}),
        sorted({row.margin for row in rows}),
        sorted({row.prototype_distance for row in rows}),
        sorted({row.crop_disagreement for row in rows}),
    ):
        accepted = tuple(
            row for row in rows
            if row.confidence >= confidence
            and row.margin >= margin
            and row.prototype_distance <= distance
            and row.crop_disagreement <= disagreement
        )
        wrong = sum(row.expected_sku_id != row.predicted_sku_id for row in accepted)
        if accepted and wrong == 0:
            gate = DirectGate(True, confidence, margin, distance, disagreement, len(accepted), 0)
            # max coverage, then stricter confidence/margin and lower distance/disagreement.
            key = (float(len(accepted)), confidence, margin, -distance, -disagreement)
            candidates.append((key, gate))
    return max(candidates, key=lambda item: item[0])[1] if candidates else DirectGate(False)


def _safe_scene_identity(value: str) -> str:
    return "scene_sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reject_private_paths(value: object) -> None:
    if isinstance(value, str):
        if value.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
            raise ValueError("calibration bundle must not contain private absolute paths")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _reject_private_paths(key)
            _reject_private_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_paths(item)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args(argv)
    required = tuple(
        args.evidence_root / f"fold-{fold}" / name
        for fold in range(5)
        for name in ("calibration.json", "evaluation.json")
    )
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        print(json.dumps({
            "schema_version": 1,
            "status": "unverified_missing_fold_evidence",
            "missing_input_count": len(missing),
            "policy_created": False,
        }, sort_keys=True, separators=(",", ":")))
        return 2
    raise RuntimeError("operational evidence loader is not admitted until its producer schema is frozen")


if __name__ == "__main__":
    raise SystemExit(_main())
