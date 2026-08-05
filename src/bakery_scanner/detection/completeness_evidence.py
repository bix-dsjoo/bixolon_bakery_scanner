"""Hash-admitted evidence for actual scene-completeness executions.

The public producer derives the decision from :func:`evaluate_completeness`.
OOF consumers must load the resulting bytes through an admitted index; an
arbitrary in-memory record is never an admission credential.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Literal, Mapping, Sequence

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    BoxXYXY,
    CaptureQuality,
    CompletenessPolicy,
    ForegroundEvidence,
    evaluate_completeness,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_CANONICAL_FRAME_VERSION = "exif_transposed_rgb_v1"
_CANONICAL_FRAME_MODE = "RGB"

REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS = (
    "acceptance_config_sha256",
    "detector_sha256",
    "dino_global_preprocess_sha256",
    "dino_global_runtime_sha256",
    "dino_global_split_sha256",
    "dino_local_model_sha256",
    "dino_local_preprocess_sha256",
    "dino_local_runtime_sha256",
    "dino_local_split_sha256",
    "dinov3_local_bank_sha256",
    "dinov3_support_sha256",
    "dinov3_weights_sha256",
    "fold_manifest_file_sha256",
    "fold_policy_sha256",
    "preprocess_sha256",
    "repvit_checkpoint_sha256",
    "repvit_prototype_sha256",
    "runtime_sha256",
    "split_sha256",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _require_exact_keys(value: object, expected: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{name} fields are invalid")
    return value


def _policy_payload(policy: CompletenessPolicy) -> dict[str, object]:
    return {
        "border_margin_ratio": policy.border_margin_ratio,
        "exposure_range": list(policy.exposure_range),
        "max_pair_iou": policy.max_pair_iou,
        "max_reflection_ratio": policy.max_reflection_ratio,
        "max_risk_score": policy.max_risk_score,
        "max_uncovered_ratio": policy.max_uncovered_ratio,
        "min_blur_score": policy.min_blur_score,
    }


def _foreground_payload(foreground: ForegroundEvidence) -> dict[str, object]:
    return {
        "covered_ratio": foreground.covered_ratio,
        "possible_merge_regions": [list(region) for region in foreground.possible_merge_regions],
        "possible_split_regions": [list(region) for region in foreground.possible_split_regions],
        "problem_regions": [list(region) for region in foreground.problem_regions],
        "risk_score": foreground.risk_score,
        "uncovered_ratio": foreground.uncovered_ratio,
    }


def _quality_payload(quality: CaptureQuality) -> dict[str, object]:
    return {
        "blur_score": quality.blur_score,
        "exposure_score": quality.exposure_score,
        "reflection_ratio": quality.reflection_ratio,
    }


@dataclass(frozen=True, slots=True)
class CompletenessProposalEvidence:
    proposal_identity_sha256: str
    image_id: int
    source_sha256: str
    score: float
    box_xyxy: BoxXYXY
    image_width: int
    image_height: int
    class_id: int
    class_name: str

    def __post_init__(self) -> None:
        _require_sha256(self.proposal_identity_sha256, "proposal_identity_sha256")
        _require_sha256(self.source_sha256, "proposal source_sha256")
        try:
            proposal = self.to_proposal()
        except (TypeError, ValueError) as exc:
            raise ValueError("completeness proposal evidence is invalid") from exc
        if self.proposal_identity_sha256 != _canonical_sha256(self.identity_payload()):
            raise ValueError("completeness proposal identity SHA-256 mismatch")
        if proposal.box.xyxy != self.box_xyxy:
            raise ValueError("completeness proposal box is not canonical")

    def identity_payload(self) -> dict[str, object]:
        return {
            "box_xyxy": list(self.box_xyxy),
            "class_id": self.class_id,
            "class_name": self.class_name,
            "image_height": self.image_height,
            "image_id": self.image_id,
            "image_width": self.image_width,
            "score": self.score,
            "source_sha256": self.source_sha256,
        }

    def canonical_payload(self) -> dict[str, object]:
        return {
            **self.identity_payload(),
            "proposal_identity_sha256": self.proposal_identity_sha256,
        }

    def to_proposal(self) -> BreadProposal:
        x_min, y_min, x_max, y_max = self.box_xyxy
        return BreadProposal(
            self.image_id,
            f"source_sha256:{self.source_sha256}",
            self.score,
            Box(x_min, y_min, x_max - x_min, y_max - y_min),
            self.image_width,
            self.image_height,
            self.class_id,
            self.class_name,
        )


@dataclass(frozen=True, slots=True)
class CompletenessExecutionRecord:
    """Canonical payload loaded from, or ready to publish into, a bundle."""

    source_scene_sha256: str
    source_image_sha256: str
    fold_index: int
    canonical_frame_version: Literal["exif_transposed_rgb_v1"]
    canonical_frame_mode: Literal["RGB"]
    frame_size: tuple[int, int]
    proposals: tuple[CompletenessProposalEvidence, ...]
    foreground: ForegroundEvidence
    quality: CaptureQuality
    policy: CompletenessPolicy
    completeness_policy_id: str
    completeness_policy_artifact_sha256: str
    decision_state: Literal["accepted_scan", "needs_retake"]
    decision_reasons: tuple[str, ...]
    problem_regions: tuple[BoxXYXY, ...]
    final_source_proposal_sha256: tuple[str, ...]
    frame_sha256: str
    proposal_set_sha256: str
    foreground_sha256: str
    quality_sha256: str
    policy_payload_sha256: str
    code_sha256: str
    input_artifact_sha256: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _require_sha256(self.source_scene_sha256, "source_scene_sha256")
        _require_sha256(self.source_image_sha256, "source_image_sha256")
        if type(self.fold_index) is not int or self.fold_index not in range(5):
            raise ValueError("completeness evidence fold is invalid")
        if self.canonical_frame_version != _CANONICAL_FRAME_VERSION:
            raise ValueError("canonical frame version is invalid")
        if self.canonical_frame_mode != _CANONICAL_FRAME_MODE:
            raise ValueError("canonical frame mode must be RGB")
        if (
            not isinstance(self.frame_size, tuple)
            or len(self.frame_size) != 2
            or any(type(value) is not int or value < 1 for value in self.frame_size)
        ):
            raise ValueError("canonical frame size is invalid")
        if not isinstance(self.proposals, tuple) or not all(
            isinstance(item, CompletenessProposalEvidence) for item in self.proposals
        ):
            raise ValueError("completeness proposals must be immutable evidence")
        if not isinstance(self.foreground, ForegroundEvidence):
            raise ValueError("foreground evidence is invalid")
        if not isinstance(self.quality, CaptureQuality):
            raise ValueError("capture quality evidence is invalid")
        if not isinstance(self.policy, CompletenessPolicy):
            raise ValueError("completeness policy is invalid")
        if not isinstance(self.completeness_policy_id, str) or not _OPAQUE_ID.fullmatch(
            self.completeness_policy_id
        ):
            raise ValueError("completeness policy identity is invalid")
        _require_sha256(
            self.completeness_policy_artifact_sha256,
            "completeness_policy_artifact_sha256",
        )
        for field_name in (
            "frame_sha256",
            "proposal_set_sha256",
            "foreground_sha256",
            "quality_sha256",
            "policy_payload_sha256",
            "code_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        if (
            not isinstance(self.input_artifact_sha256, tuple)
            or tuple(sorted(self.input_artifact_sha256)) != self.input_artifact_sha256
            or len({key for key, _ in self.input_artifact_sha256}) != len(self.input_artifact_sha256)
            or tuple(key for key, _ in self.input_artifact_sha256)
            != REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS
        ):
            raise ValueError("completeness input artifact identities are invalid")
        for key, digest in self.input_artifact_sha256:
            if not isinstance(key, str):
                raise ValueError("completeness input artifact key is invalid")
            _require_sha256(digest, f"input artifact {key}")

        frame_payload = {
            "height": self.frame_size[1],
            "mode": self.canonical_frame_mode,
            "source_image_sha256": self.source_image_sha256,
            "version": self.canonical_frame_version,
            "width": self.frame_size[0],
        }
        proposal_payload = [item.canonical_payload() for item in self.proposals]
        expected_hashes = {
            "frame_sha256": _canonical_sha256(frame_payload),
            "proposal_set_sha256": _canonical_sha256(proposal_payload),
            "foreground_sha256": _canonical_sha256(_foreground_payload(self.foreground)),
            "quality_sha256": _canonical_sha256(_quality_payload(self.quality)),
            "policy_payload_sha256": _canonical_sha256(_policy_payload(self.policy)),
        }
        for field_name, digest in expected_hashes.items():
            if getattr(self, field_name) != digest:
                raise ValueError(f"{field_name} does not match canonical evidence")

        proposals = tuple(item.to_proposal() for item in self.proposals)
        if any(
            (proposal.image_width, proposal.image_height) != self.frame_size
            for proposal in proposals
        ):
            raise ValueError("proposal canonical frame identity mismatch")
        decision = evaluate_completeness(
            self.frame_size,
            proposals,
            self.foreground,
            self.quality,
            self.policy,
        )
        expected_state = "accepted_scan" if decision.accepted else "needs_retake"
        expected_reasons = tuple(reason.value for reason in decision.reasons)
        expected_final = (
            tuple(item.proposal_identity_sha256 for item in self.proposals)
            if decision.accepted
            else ()
        )
        if self.decision_state != expected_state or self.decision_reasons != expected_reasons:
            raise ValueError("completeness execution result does not match actual decision")
        if self.problem_regions != decision.problem_regions:
            raise ValueError("completeness execution problem regions do not match actual decision")
        if self.final_source_proposal_sha256 != expected_final:
            raise ValueError("completeness final source set does not match actual decision")
        if self.decision_state == "accepted_scan" and (
            self.decision_reasons or not self.final_source_proposal_sha256
        ):
            raise ValueError("accepted_scan requires zero reasons and a non-empty final source set")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "canonical_frame": {
                "height": self.frame_size[1],
                "mode": self.canonical_frame_mode,
                "source_image_sha256": self.source_image_sha256,
                "version": self.canonical_frame_version,
                "width": self.frame_size[0],
            },
            "code_sha256": self.code_sha256,
            "completeness_policy": {
                "artifact_sha256": self.completeness_policy_artifact_sha256,
                "id": self.completeness_policy_id,
                "payload": _policy_payload(self.policy),
                "payload_sha256": self.policy_payload_sha256,
            },
            "decision": {
                "problem_regions": [list(region) for region in self.problem_regions],
                "reasons": list(self.decision_reasons),
                "state": self.decision_state,
            },
            "evidence_hashes": {
                "foreground_sha256": self.foreground_sha256,
                "frame_sha256": self.frame_sha256,
                "proposal_set_sha256": self.proposal_set_sha256,
                "quality_sha256": self.quality_sha256,
            },
            "final_source_proposal_sha256": list(self.final_source_proposal_sha256),
            "fold_index": self.fold_index,
            "foreground": _foreground_payload(self.foreground),
            "input_artifact_sha256": dict(self.input_artifact_sha256),
            "proposals": [item.canonical_payload() for item in self.proposals],
            "quality": _quality_payload(self.quality),
            "schema_version": 1,
            "source_image_sha256": self.source_image_sha256,
            "source_scene_sha256": self.source_scene_sha256,
        }

    @property
    def payload_sha256(self) -> str:
        return _canonical_sha256(self.canonical_payload())

    def to_json_bytes(self) -> bytes:
        return _canonical_json(
            {
                "payload": self.canonical_payload(),
                "payload_sha256": self.payload_sha256,
                "schema_version": 1,
            }
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_json_bytes()).hexdigest()


def _proposal_evidence(proposal: BreadProposal) -> CompletenessProposalEvidence:
    source_sha256 = hashlib.sha256(proposal.source.encode("utf-8")).hexdigest()
    identity_payload = {
        "box_xyxy": list(proposal.box.xyxy),
        "class_id": proposal.class_id,
        "class_name": proposal.class_name,
        "image_height": proposal.image_height,
        "image_id": proposal.image_id,
        "image_width": proposal.image_width,
        "score": proposal.score,
        "source_sha256": source_sha256,
    }
    return CompletenessProposalEvidence(
        proposal_identity_sha256=_canonical_sha256(identity_payload),
        image_id=proposal.image_id,
        source_sha256=source_sha256,
        score=proposal.score,
        box_xyxy=proposal.box.xyxy,
        image_width=proposal.image_width,
        image_height=proposal.image_height,
        class_id=proposal.class_id,
        class_name=proposal.class_name,
    )


def build_completeness_execution_record(
    *,
    source_scene_identity: str,
    source_image_sha256: str,
    fold_index: int,
    canonical_frame_version: str,
    canonical_frame_mode: str,
    frame_size: tuple[int, int],
    proposals: tuple[BreadProposal, ...],
    foreground: ForegroundEvidence,
    quality: CaptureQuality,
    policy: CompletenessPolicy,
    completeness_policy_id: str,
    completeness_policy_artifact_sha256: str,
    code_sha256: str,
    input_artifact_sha256: Mapping[str, str],
) -> CompletenessExecutionRecord:
    """Execute Task 3 and capture its actual decision in a canonical record."""
    if not isinstance(source_scene_identity, str) or not source_scene_identity:
        raise ValueError("source scene identity is required")
    _require_sha256(source_image_sha256, "source_image_sha256")
    if canonical_frame_version != _CANONICAL_FRAME_VERSION:
        raise ValueError("canonical frame version is invalid")
    if canonical_frame_mode != _CANONICAL_FRAME_MODE:
        raise ValueError("canonical frame mode must be RGB")
    if not isinstance(input_artifact_sha256, Mapping):
        raise ValueError("completeness input artifact identities are required")
    artifact_items = tuple(sorted(input_artifact_sha256.items()))
    if tuple(key for key, _ in artifact_items) != REQUIRED_COMPLETENESS_INPUT_ARTIFACT_KEYS:
        raise ValueError("completeness input artifact identities are invalid")
    proposal_evidence = tuple(_proposal_evidence(item) for item in proposals)
    decision = evaluate_completeness(frame_size, proposals, foreground, quality, policy)
    frame_payload = {
        "height": frame_size[1],
        "mode": canonical_frame_mode,
        "source_image_sha256": source_image_sha256,
        "version": canonical_frame_version,
        "width": frame_size[0],
    }
    proposal_payload = [item.canonical_payload() for item in proposal_evidence]
    return CompletenessExecutionRecord(
        source_scene_sha256=hashlib.sha256(source_scene_identity.encode("utf-8")).hexdigest(),
        source_image_sha256=source_image_sha256,
        fold_index=fold_index,
        canonical_frame_version=_CANONICAL_FRAME_VERSION,
        canonical_frame_mode=_CANONICAL_FRAME_MODE,
        frame_size=frame_size,
        proposals=proposal_evidence,
        foreground=foreground,
        quality=quality,
        policy=policy,
        completeness_policy_id=completeness_policy_id,
        completeness_policy_artifact_sha256=completeness_policy_artifact_sha256,
        decision_state="accepted_scan" if decision.accepted else "needs_retake",
        decision_reasons=tuple(reason.value for reason in decision.reasons),
        problem_regions=decision.problem_regions,
        final_source_proposal_sha256=(
            tuple(item.proposal_identity_sha256 for item in proposal_evidence)
            if decision.accepted
            else ()
        ),
        frame_sha256=_canonical_sha256(frame_payload),
        proposal_set_sha256=_canonical_sha256(proposal_payload),
        foreground_sha256=_canonical_sha256(_foreground_payload(foreground)),
        quality_sha256=_canonical_sha256(_quality_payload(quality)),
        policy_payload_sha256=_canonical_sha256(_policy_payload(policy)),
        code_sha256=code_sha256,
        input_artifact_sha256=artifact_items,
    )


@dataclass(frozen=True, slots=True)
class LoadedCompletenessEvidenceBundle:
    root: Path
    index_sha256: str
    records: tuple[tuple[str, CompletenessExecutionRecord], ...]

    def require_record(
        self,
        source_scene_sha256: str,
        expected_record_sha256: str,
    ) -> CompletenessExecutionRecord:
        _require_sha256(source_scene_sha256, "source_scene_sha256")
        _require_sha256(expected_record_sha256, "expected record SHA-256")
        record_by_scene = dict(self.records)
        record = record_by_scene.get(source_scene_sha256)
        if record is None:
            raise ValueError("completeness evidence record is absent from admitted index")
        if record.sha256 != expected_record_sha256:
            raise ValueError("completeness evidence record SHA-256 mismatch")
        return record


def write_completeness_evidence_bundle(
    records: Sequence[CompletenessExecutionRecord],
    output_root: Path,
) -> str:
    """Publish records and their exact immutable index without replacing bytes."""
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError("completeness evidence output root must be absolute")
    checked = tuple(records)
    if not checked or not all(isinstance(item, CompletenessExecutionRecord) for item in checked):
        raise ValueError("completeness evidence bundle requires execution records")
    if len({item.source_scene_sha256 for item in checked}) != len(checked):
        raise ValueError("completeness evidence scene identity must be unique")
    if output_root.exists():
        raise ValueError("completeness evidence output root already exists")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}-", dir=str(output_root.parent))
    )
    try:
        record_root = temporary / "records"
        record_root.mkdir()
        entries: list[dict[str, object]] = []
        for record in sorted(checked, key=lambda item: item.source_scene_sha256):
            encoded = record.to_json_bytes()
            relative_path = f"records/{record.source_scene_sha256}.json"
            (temporary / relative_path).write_bytes(encoded)
            entries.append(
                {
                    "byte_size": len(encoded),
                    "path": relative_path,
                    "record_sha256": hashlib.sha256(encoded).hexdigest(),
                    "scene_sha256": record.source_scene_sha256,
                }
            )
        index_bytes = _canonical_json({"records": entries, "schema_version": 1})
        (temporary / "index.json").write_bytes(index_bytes)
        os.replace(temporary, output_root)
        return hashlib.sha256(index_bytes).hexdigest()
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _json_no_duplicates(encoded: bytes, name: str) -> object:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{name} contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        return json.loads(encoded.decode("utf-8"), object_pairs_hook=pairs_hook)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not canonical UTF-8 JSON") from exc


def _tuple_regions(value: object, name: str) -> tuple[BoxXYXY, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return tuple(tuple(region) for region in value)  # type: ignore[arg-type, return-value]


def _record_from_bytes(encoded: bytes) -> CompletenessExecutionRecord:
    envelope = _require_exact_keys(
        _json_no_duplicates(encoded, "completeness evidence record"),
        {"payload", "payload_sha256", "schema_version"},
        "completeness evidence record",
    )
    if envelope["schema_version"] != 1:
        raise ValueError("completeness evidence record schema is invalid")
    payload = envelope["payload"]
    payload_sha256 = _require_sha256(envelope["payload_sha256"], "record payload_sha256")
    if payload_sha256 != _canonical_sha256(payload):
        raise ValueError("completeness evidence payload SHA-256 mismatch")
    if encoded != _canonical_json(envelope):
        raise ValueError("completeness evidence record is not canonical")
    data = _require_exact_keys(
        payload,
        {
            "canonical_frame",
            "code_sha256",
            "completeness_policy",
            "decision",
            "evidence_hashes",
            "final_source_proposal_sha256",
            "fold_index",
            "foreground",
            "input_artifact_sha256",
            "proposals",
            "quality",
            "schema_version",
            "source_image_sha256",
            "source_scene_sha256",
        },
        "completeness evidence payload",
    )
    if data["schema_version"] != 1:
        raise ValueError("completeness evidence payload schema is invalid")
    frame = _require_exact_keys(
        data["canonical_frame"],
        {"height", "mode", "source_image_sha256", "version", "width"},
        "canonical frame",
    )
    foreground_data = _require_exact_keys(
        data["foreground"],
        {
            "covered_ratio",
            "possible_merge_regions",
            "possible_split_regions",
            "problem_regions",
            "risk_score",
            "uncovered_ratio",
        },
        "foreground evidence",
    )
    quality_data = _require_exact_keys(
        data["quality"],
        {"blur_score", "exposure_score", "reflection_ratio"},
        "quality evidence",
    )
    policy_data = _require_exact_keys(
        data["completeness_policy"],
        {"artifact_sha256", "id", "payload", "payload_sha256"},
        "completeness policy",
    )
    policy_payload = _require_exact_keys(
        policy_data["payload"],
        {
            "border_margin_ratio",
            "exposure_range",
            "max_pair_iou",
            "max_reflection_ratio",
            "max_risk_score",
            "max_uncovered_ratio",
            "min_blur_score",
        },
        "completeness policy payload",
    )
    exposure_range = policy_payload["exposure_range"]
    if not isinstance(exposure_range, list) or len(exposure_range) != 2:
        raise ValueError("completeness policy exposure range is invalid")
    decision = _require_exact_keys(
        data["decision"],
        {"problem_regions", "reasons", "state"},
        "completeness decision",
    )
    evidence_hashes = _require_exact_keys(
        data["evidence_hashes"],
        {"foreground_sha256", "frame_sha256", "proposal_set_sha256", "quality_sha256"},
        "completeness evidence hashes",
    )
    proposal_rows = data["proposals"]
    if not isinstance(proposal_rows, list):
        raise ValueError("completeness proposals are invalid")
    proposals: list[CompletenessProposalEvidence] = []
    for row in proposal_rows:
        item = _require_exact_keys(
            row,
            {
                "box_xyxy",
                "class_id",
                "class_name",
                "image_height",
                "image_id",
                "image_width",
                "proposal_identity_sha256",
                "score",
                "source_sha256",
            },
            "completeness proposal",
        )
        box_xyxy = item["box_xyxy"]
        if not isinstance(box_xyxy, list) or len(box_xyxy) != 4:
            raise ValueError("completeness proposal box is invalid")
        proposals.append(
            CompletenessProposalEvidence(
                proposal_identity_sha256=item["proposal_identity_sha256"],  # type: ignore[arg-type]
                image_id=item["image_id"],  # type: ignore[arg-type]
                source_sha256=item["source_sha256"],  # type: ignore[arg-type]
                score=item["score"],  # type: ignore[arg-type]
                box_xyxy=tuple(box_xyxy),  # type: ignore[arg-type]
                image_width=item["image_width"],  # type: ignore[arg-type]
                image_height=item["image_height"],  # type: ignore[arg-type]
                class_id=item["class_id"],  # type: ignore[arg-type]
                class_name=item["class_name"],  # type: ignore[arg-type]
            )
        )
    artifact_map = data["input_artifact_sha256"]
    if not isinstance(artifact_map, dict):
        raise ValueError("completeness input artifacts are invalid")
    final_source = data["final_source_proposal_sha256"]
    reasons = decision["reasons"]
    if not isinstance(final_source, list) or not isinstance(reasons, list):
        raise ValueError("completeness decision collections are invalid")
    record = CompletenessExecutionRecord(
        source_scene_sha256=data["source_scene_sha256"],  # type: ignore[arg-type]
        source_image_sha256=data["source_image_sha256"],  # type: ignore[arg-type]
        fold_index=data["fold_index"],  # type: ignore[arg-type]
        canonical_frame_version=frame["version"],  # type: ignore[arg-type]
        canonical_frame_mode=frame["mode"],  # type: ignore[arg-type]
        frame_size=(frame["width"], frame["height"]),  # type: ignore[arg-type]
        proposals=tuple(proposals),
        foreground=ForegroundEvidence(
            foreground_data["uncovered_ratio"],  # type: ignore[arg-type]
            foreground_data["covered_ratio"],  # type: ignore[arg-type]
            _tuple_regions(foreground_data["problem_regions"], "problem_regions"),
            _tuple_regions(
                foreground_data["possible_split_regions"],
                "possible_split_regions",
            ),
            _tuple_regions(
                foreground_data["possible_merge_regions"],
                "possible_merge_regions",
            ),
            foreground_data["risk_score"],  # type: ignore[arg-type]
        ),
        quality=CaptureQuality(
            quality_data["blur_score"],  # type: ignore[arg-type]
            quality_data["exposure_score"],  # type: ignore[arg-type]
            quality_data["reflection_ratio"],  # type: ignore[arg-type]
        ),
        policy=CompletenessPolicy(
            policy_payload["max_uncovered_ratio"],  # type: ignore[arg-type]
            policy_payload["max_pair_iou"],  # type: ignore[arg-type]
            policy_payload["border_margin_ratio"],  # type: ignore[arg-type]
            policy_payload["min_blur_score"],  # type: ignore[arg-type]
            tuple(exposure_range),  # type: ignore[arg-type]
            policy_payload["max_reflection_ratio"],  # type: ignore[arg-type]
            policy_payload["max_risk_score"],  # type: ignore[arg-type]
        ),
        completeness_policy_id=policy_data["id"],  # type: ignore[arg-type]
        completeness_policy_artifact_sha256=policy_data["artifact_sha256"],  # type: ignore[arg-type]
        decision_state=decision["state"],  # type: ignore[arg-type]
        decision_reasons=tuple(reasons),  # type: ignore[arg-type]
        problem_regions=_tuple_regions(decision["problem_regions"], "problem_regions"),
        final_source_proposal_sha256=tuple(final_source),  # type: ignore[arg-type]
        frame_sha256=evidence_hashes["frame_sha256"],  # type: ignore[arg-type]
        proposal_set_sha256=evidence_hashes["proposal_set_sha256"],  # type: ignore[arg-type]
        foreground_sha256=evidence_hashes["foreground_sha256"],  # type: ignore[arg-type]
        quality_sha256=evidence_hashes["quality_sha256"],  # type: ignore[arg-type]
        policy_payload_sha256=policy_data["payload_sha256"],  # type: ignore[arg-type]
        code_sha256=data["code_sha256"],  # type: ignore[arg-type]
        input_artifact_sha256=tuple(sorted(artifact_map.items())),  # type: ignore[arg-type]
    )
    if record.canonical_payload() != data or record.payload_sha256 != payload_sha256:
        raise ValueError("completeness evidence record canonical payload mismatch")
    return record


def load_completeness_evidence_bundle(
    root: Path,
    *,
    expected_index_sha256: str,
) -> LoadedCompletenessEvidenceBundle:
    """Load every indexed record after exact byte and canonical checks."""
    root = Path(root)
    if not root.is_absolute():
        raise ValueError("completeness evidence root must be absolute")
    _require_sha256(expected_index_sha256, "expected index SHA-256")
    resolved_root = root.resolve(strict=True)
    index_path = resolved_root / "index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise ValueError("completeness evidence index is missing or unsafe")
    index_bytes = index_path.read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != expected_index_sha256:
        raise ValueError("completeness evidence index SHA-256 mismatch")
    index = _require_exact_keys(
        _json_no_duplicates(index_bytes, "completeness evidence index"),
        {"records", "schema_version"},
        "completeness evidence index",
    )
    if index["schema_version"] != 1 or index_bytes != _canonical_json(index):
        raise ValueError("completeness evidence index is not canonical schema 1")
    entries = index["records"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("completeness evidence index requires records")
    records: list[tuple[str, CompletenessExecutionRecord]] = []
    seen: set[str] = set()
    previous_scene = ""
    for row in entries:
        entry = _require_exact_keys(
            row,
            {"byte_size", "path", "record_sha256", "scene_sha256"},
            "completeness evidence index entry",
        )
        scene_sha256 = _require_sha256(entry["scene_sha256"], "index scene_sha256")
        record_sha256 = _require_sha256(entry["record_sha256"], "index record_sha256")
        expected_path = f"records/{scene_sha256}.json"
        if entry["path"] != expected_path or scene_sha256 in seen or scene_sha256 <= previous_scene:
            raise ValueError("completeness evidence index mapping is invalid")
        if type(entry["byte_size"]) is not int or entry["byte_size"] < 1:
            raise ValueError("completeness evidence record byte size is invalid")
        record_path = (resolved_root / expected_path).resolve(strict=True)
        try:
            record_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("completeness evidence record escapes its admitted root") from exc
        if record_path.is_symlink() or not record_path.is_file():
            raise ValueError("completeness evidence record path is missing or unsafe")
        encoded = record_path.read_bytes()
        if len(encoded) != entry["byte_size"]:
            raise ValueError("completeness evidence record byte size mismatch")
        if hashlib.sha256(encoded).hexdigest() != record_sha256:
            raise ValueError("completeness evidence record SHA-256 mismatch")
        record = _record_from_bytes(encoded)
        if record.source_scene_sha256 != scene_sha256 or record.sha256 != record_sha256:
            raise ValueError("completeness evidence record/index identity mismatch")
        records.append((scene_sha256, record))
        seen.add(scene_sha256)
        previous_scene = scene_sha256
    return LoadedCompletenessEvidenceBundle(resolved_root, expected_index_sha256, tuple(records))
