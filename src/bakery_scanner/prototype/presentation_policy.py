"""Fixed, verified presentation routing for camera inference results."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal, Mapping, Sequence


_V1_POLICY_FIELDS = {
    "box_overlap_iou",
    "candidate_top12_min_margin",
    "candidate_top1_min_score",
    "policy_id",
    "schema_version",
}
_V2_POLICY_FIELDS = {
    "box_overlap_iou",
    "policy_id",
    "schema_version",
}
_V1_POLICY_ID = "camera_action_state_v1"
_V2_POLICY_ID = "camera_action_state_v2"


@dataclass(frozen=True, slots=True)
class PresentationDecision:
    """A UI-only action state that leaves inference results untouched."""

    state: str
    final_count_usable: bool
    retake_scope: str | None
    retake_object_ids: tuple[str, ...]
    instruction_code: str | None
    candidate_object_ids: tuple[str, ...]
    policy_id: str
    policy_sha256: str

    def to_payload(self) -> dict[str, object]:
        return {
            "state": self.state,
            "final_count_usable": self.final_count_usable,
            "retake_scope": self.retake_scope,
            "retake_object_ids": list(self.retake_object_ids),
            "instruction_code": self.instruction_code,
            "candidate_object_ids": list(self.candidate_object_ids),
            "policy_id": self.policy_id,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True, slots=True)
class PresentationPolicy:
    box_overlap_iou: float
    candidate_top12_min_margin: float | None
    candidate_top1_min_score: float | None
    schema_version: Literal[1, 2]
    policy_id: str
    policy_sha256: str

    @classmethod
    def load(cls, path: Path) -> "PresentationPolicy":
        """Load one exact policy artifact and bind routing to its byte hash."""
        policy_path = Path(path)
        try:
            payload_bytes = policy_path.read_bytes()
            payload = json.loads(
                payload_bytes.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonfinite_constant,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"presentation policy is invalid: {policy_path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("presentation policy schema is invalid")
        schema_version = payload.get("schema_version")
        if isinstance(schema_version, bool) or schema_version not in (1, 2):
            raise ValueError("presentation policy schema_version is invalid")
        if schema_version == 1:
            if set(payload) != _V1_POLICY_FIELDS:
                raise ValueError("presentation policy schema is invalid")
            if payload["policy_id"] != _V1_POLICY_ID:
                raise ValueError("presentation policy ID is invalid")
            candidate_top12_min_margin = _policy_probability(
                payload["candidate_top12_min_margin"],
                "candidate_top12_min_margin",
            )
            candidate_top1_min_score = _policy_probability(
                payload["candidate_top1_min_score"],
                "candidate_top1_min_score",
            )
            policy_id = _V1_POLICY_ID
        else:
            if set(payload) != _V2_POLICY_FIELDS:
                raise ValueError("presentation policy schema is invalid")
            if payload["policy_id"] != _V2_POLICY_ID:
                raise ValueError("presentation policy ID is invalid")
            candidate_top12_min_margin = None
            candidate_top1_min_score = None
            policy_id = _V2_POLICY_ID
        return cls(
            box_overlap_iou=_policy_probability(
                payload["box_overlap_iou"], "box_overlap_iou"
            ),
            candidate_top12_min_margin=candidate_top12_min_margin,
            candidate_top1_min_score=candidate_top1_min_score,
            schema_version=schema_version,
            policy_id=policy_id,
            policy_sha256=hashlib.sha256(payload_bytes).hexdigest(),
        )

    def evaluate(
        self,
        *,
        proposals: Sequence[Mapping[str, object]],
        decisions: Sequence[Mapping[str, object]],
    ) -> PresentationDecision:
        """Route presentation state without changing final inference objects."""
        normalized_proposals = tuple(_proposal(item) for item in proposals)
        if not normalized_proposals:
            return self._scan_retake("no_bread_detected")
        normalized_decisions = tuple(_decision(item) for item in decisions)
        _require_unique_bijection(normalized_proposals, normalized_decisions)
        if object_ids := _overlapping_object_ids(
            normalized_proposals, self.box_overlap_iou
        ):
            return self._object_retake("separate_breads", object_ids)
        if self.schema_version == 1:
            if (
                self.candidate_top1_min_score is None
                or self.candidate_top12_min_margin is None
            ):
                raise ValueError("v1 presentation policy thresholds are missing")
            if object_ids := _weak_unknown_ids(
                normalized_decisions,
                self.candidate_top1_min_score,
                self.candidate_top12_min_margin,
            ):
                return self._object_retake("candidate_evidence_weak", object_ids)
        if object_ids := _unknown_ids(normalized_decisions):
            return self._unknown(object_ids)
        return self._normal()

    def _normal(self) -> PresentationDecision:
        return self._result(
            state="normal",
            final_count_usable=True,
            retake_scope=None,
            retake_object_ids=(),
            instruction_code=None,
            candidate_object_ids=(),
        )

    def _unknown(self, candidate_object_ids: tuple[str, ...]) -> PresentationDecision:
        return self._result(
            state="unknown",
            final_count_usable=True,
            retake_scope=None,
            retake_object_ids=(),
            instruction_code=None,
            candidate_object_ids=candidate_object_ids,
        )

    def _scan_retake(self, instruction_code: str) -> PresentationDecision:
        return self._result(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="scan",
            retake_object_ids=(),
            instruction_code=instruction_code,
            candidate_object_ids=(),
        )

    def _object_retake(
        self, instruction_code: str, retake_object_ids: tuple[str, ...]
    ) -> PresentationDecision:
        return self._result(
            state="needs_retake",
            final_count_usable=False,
            retake_scope="object",
            retake_object_ids=retake_object_ids,
            instruction_code=instruction_code,
            candidate_object_ids=(),
        )

    def _result(
        self,
        *,
        state: str,
        final_count_usable: bool,
        retake_scope: str | None,
        retake_object_ids: tuple[str, ...],
        instruction_code: str | None,
        candidate_object_ids: tuple[str, ...],
    ) -> PresentationDecision:
        return PresentationDecision(
            state=state,
            final_count_usable=final_count_usable,
            retake_scope=retake_scope,
            retake_object_ids=retake_object_ids,
            instruction_code=instruction_code,
            candidate_object_ids=candidate_object_ids,
            policy_id=self.policy_id,
            policy_sha256=self.policy_sha256,
        )


@dataclass(frozen=True, slots=True)
class _Proposal:
    object_id: str
    box: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class _Decision:
    object_id: str
    is_unknown: bool
    top3: tuple[float, ...]


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate presentation policy field: {key}")
        payload[key] = value
    return payload


def _reject_nonfinite_constant(value: str) -> object:
    raise ValueError(f"non-finite numeric constant: {value}")


def _policy_probability(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"presentation policy {field} is invalid")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"presentation policy {field} is invalid")
    return number


def _proposal(item: Mapping[str, object]) -> _Proposal:
    object_id = _object_id(item)
    raw_box = item.get("bbox_xyxy")
    if not isinstance(raw_box, Sequence) or isinstance(raw_box, (str, bytes)) or len(raw_box) != 4:
        raise ValueError("proposal bbox_xyxy is invalid")
    coordinates = tuple(_finite_coordinate(value) for value in raw_box)
    x_min, y_min, x_max, y_max = coordinates
    if x_min >= x_max or y_min >= y_max:
        raise ValueError("proposal bbox_xyxy is invalid")
    return _Proposal(object_id, coordinates)


def _decision(item: Mapping[str, object]) -> _Decision:
    object_id = _object_id(item)
    is_unknown = item.get("sku_id") is None
    raw_top3 = item.get("top3", ())
    if not isinstance(raw_top3, Sequence) or isinstance(raw_top3, (str, bytes)):
        raise ValueError("decision top3 is invalid")
    scores: list[float] = []
    for candidate in raw_top3:
        if not isinstance(candidate, Mapping):
            raise ValueError("decision top3 is invalid")
        scores.append(_finite_coordinate(candidate.get("score")))
    if is_unknown and len(scores) < 2:
        raise ValueError("Unknown decision requires at least two candidates")
    return _Decision(object_id, is_unknown, tuple(scores))


def _object_id(item: Mapping[str, object]) -> str:
    if not isinstance(item, Mapping):
        raise ValueError("proposal or decision must be a mapping")
    object_id = item.get("object_id")
    if not isinstance(object_id, str) or not object_id:
        raise ValueError("object_id is invalid")
    return object_id


def _finite_coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("coordinate or score is invalid")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("coordinate or score is invalid")
    return number


def _overlapping_object_ids(
    proposals: tuple[_Proposal, ...], threshold: float
) -> tuple[str, ...]:
    overlapping: set[str] = set()
    for index, left in enumerate(proposals):
        for right in proposals[index + 1 :]:
            if _iou(left.box, right.box) >= threshold:
                overlapping.update((left.object_id, right.object_id))
    return tuple(sorted(overlapping))


def _require_unique_bijection(
    proposals: tuple[_Proposal, ...], decisions: tuple[_Decision, ...]
) -> None:
    proposal_ids = tuple(item.object_id for item in proposals)
    decision_ids = tuple(item.object_id for item in decisions)
    if len(set(proposal_ids)) != len(proposal_ids):
        raise ValueError("proposal object IDs must be unique")
    if len(set(decision_ids)) != len(decision_ids):
        raise ValueError("decision object IDs must be unique")
    if set(proposal_ids) != set(decision_ids):
        raise ValueError("proposal and decision object IDs must form a bijection")


def _iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    left_x_min, left_y_min, left_x_max, left_y_max = left
    right_x_min, right_y_min, right_x_max, right_y_max = right
    intersection_width = max(0.0, min(left_x_max, right_x_max) - max(left_x_min, right_x_min))
    intersection_height = max(0.0, min(left_y_max, right_y_max) - max(left_y_min, right_y_min))
    intersection = intersection_width * intersection_height
    left_area = (left_x_max - left_x_min) * (left_y_max - left_y_min)
    right_area = (right_x_max - right_x_min) * (right_y_max - right_y_min)
    return intersection / (left_area + right_area - intersection)


def _weak_unknown_ids(
    decisions: tuple[_Decision, ...], top1_min: float, top12_margin: float
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                item.object_id
                for item in decisions
                if item.is_unknown
                and (
                    _strictly_less(item.top3[0], top1_min)
                    or _decimal(item.top3[0]) - _decimal(item.top3[1])
                    < _decimal(top12_margin)
                )
            }
        )
    )


def _unknown_ids(decisions: tuple[_Decision, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.object_id for item in decisions if item.is_unknown}))


def _strictly_less(value: float, threshold: float) -> bool:
    """Compare input decimal values without widening policy boundaries."""
    return _decimal(value) < _decimal(threshold)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))
