"""Score existing, hash-bound RPC evidence; this library never runs a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from bakery_scanner.experiments.rpc_manifest import (
    RpcDatasetContract,
    RpcIndex,
    canonical_json_bytes,
    load_rpc_index,
    write_new_json,
)
from bakery_scanner.experiments.rpc_metrics import (
    BranchName,
    DifficultySummary,
    FullSystemSummary,
    LockedGroundTruthRow,
    PairedConditionEvidence,
    ResearchEvidenceRow,
    branch_top1_agreement,
    branch_top1_summary,
    bootstrap_paired_condition_deltas,
    bootstrap_paired_deltas,
    condition_cohort,
    condition_provenance,
    full_system_summary,
    validate_evidence_against_condition,
    validate_evidence_completeness,
    validate_paired_evidence,
)
from bakery_scanner.experiments.rpc_protocol import (
    ExperimentCondition,
    ScoringPlan,
    StageFourSelection,
    validate_stage_four_binding_for_locked_target,
    validate_stage_four_confirmation_score_receipts,
)
from bakery_scanner.experiments.rpc_splits import build_scene_roles


_SCORE_BRANCHES: tuple[BranchName, ...] = (
    "repvit_global",
    "dinov3_global",
    "dinov3_local",
)
_CANONICAL_SCENE_SPLIT_VERSION = "rpc-2019-five-fold-v1"


def load_canonical_json(path: Path) -> Mapping[str, object]:
    value, _ = _load_canonical_json_with_digest(path)
    return value


def _load_canonical_json_with_digest(path: Path) -> tuple[Mapping[str, object], str]:
    content = path.read_bytes()
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid canonical JSON: {path}") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise ValueError(f"JSON is not canonical: {path}")
    return value, hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class LoadedEvidence:
    """Rows and digest derived from one immutable read of canonical JSONL bytes."""

    rows: tuple[ResearchEvidenceRow, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class LoadedGroundTruth:
    """Validated locked object identities and the canonical file digest."""

    rows: tuple[LockedGroundTruthRow, ...]
    sha256: str
    source_manifest_sha256: str
    scene_role_manifest_sha256: str


def load_canonical_jsonl(path: Path) -> LoadedEvidence:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read evidence: {path}") from exc
    raw_lines = content.splitlines()
    if not raw_lines:
        raise ValueError("evidence must not be empty")
    rows: list[ResearchEvidenceRow] = []
    for number, line in enumerate(raw_lines, start=1):
        if not line:
            raise ValueError(f"blank evidence line {number}")
        try:
            value = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid evidence JSONL line {number}") from exc
        if not isinstance(value, dict) or canonical_json_bytes(value) != line:
            raise ValueError(f"evidence JSONL line {number} is not canonical")
        try:
            rows.append(ResearchEvidenceRow.from_dict(value))
        except ValueError as exc:
            raise ValueError(f"invalid evidence JSONL line {number}") from exc
    return LoadedEvidence(tuple(rows), hashlib.sha256(content).hexdigest())


def load_locked_ground_truth(
    path: Path,
    *,
    trusted_source_root: Path,
) -> LoadedGroundTruth:
    """Load locked truth only after independently authenticating raw RPC input."""
    index = _trusted_rpc_index(trusted_source_root)
    value, digest = _load_canonical_json_with_digest(path)
    if (
        set(value) != {
            "schema_version",
            "kind",
            "source_manifest_path",
            "source_manifest_sha256",
            "scene_role_manifest_path",
            "scene_role_manifest_sha256",
            "objects",
        }
        or value.get("schema_version") != 2
        or value.get("kind") != "rpc-fewshot-locked-ground-truth"
        or not isinstance(value.get("objects"), list)
        or not value["objects"]
    ):
        raise ValueError("invalid locked ground-truth manifest")
    try:
        rows = tuple(
            LockedGroundTruthRow.from_dict(item)
            for item in value["objects"]  # type: ignore[union-attr]
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid locked ground-truth manifest") from exc
    identities = [row.identity for row in rows]
    object_ids = [row.object_id for row in rows]
    if (
        len(identities) != len(set(identities))
        or len(object_ids) != len(set(object_ids))
    ):
        raise ValueError("locked ground-truth manifest contains duplicate objects")
    source_path = _lineage_path(path, value.get("source_manifest_path"))
    roles_path = _lineage_path(path, value.get("scene_role_manifest_path"))
    source, source_digest = _load_canonical_json_with_digest(source_path)
    roles, roles_digest = _load_canonical_json_with_digest(roles_path)
    if source_digest != value.get("source_manifest_sha256"):
        raise ValueError("locked ground-truth source manifest SHA-256 mismatch")
    if roles_digest != value.get("scene_role_manifest_sha256"):
        raise ValueError("locked ground-truth scene-role manifest SHA-256 mismatch")
    expected = _locked_test_cohort_from_lineage(
        source, source_digest, roles, trusted_index=index
    )
    if {row.identity for row in rows} != {row.identity for row in expected}:
        raise ValueError("locked ground-truth must exactly match test2019 locked cohort")
    return LoadedGroundTruth(rows, digest, source_digest, roles_digest)


def load_development_ground_truth(
    path: Path, *, trusted_source_root: Path
) -> LoadedGroundTruth:
    """Load only the authenticated development-selection cohort.

    Development is an independently derived role, not a filtered locked
    manifest.  This deliberately gives the pre-Stage-5 scorer no code path
    that can accept test2019 truth.
    """
    return _load_role_ground_truth(
        path,
        trusted_source_root=trusted_source_root,
        expected_kind="rpc-fewshot-development-ground-truth",
        split="val2019",
        role="development_selection",
    )


def load_stage_ground_truth(
    path: Path, *, stage: str, trusted_source_root: Path
) -> LoadedGroundTruth:
    """Route stage roles before any evidence is read; no pre-lock fallback exists."""
    if stage == "locked":
        return load_locked_ground_truth(path, trusted_source_root=trusted_source_root)
    if stage in {"stage1", "ascending", "confirmation"}:
        return load_development_ground_truth(path, trusted_source_root=trusted_source_root)
    raise ValueError("unsupported experiment stage for ground truth")


def materialize_locked_ground_truth(
    source_manifest_path: Path,
    scene_role_manifest_path: Path,
    output: Path,
    *,
    trusted_source_root: Path,
) -> None:
    """Derive the complete locked test2019 cohort from verified lineage artifacts."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    source_path = Path(source_manifest_path).resolve()
    roles_path = Path(scene_role_manifest_path).resolve()
    output_parent = Path(output).parent.resolve()
    try:
        source_relative = source_path.relative_to(output_parent)
        roles_relative = roles_path.relative_to(output_parent)
    except ValueError as exc:
        raise ValueError(
            "locked ground-truth lineage artifacts must be below the output directory"
        ) from exc
    source, source_digest = _load_canonical_json_with_digest(source_path)
    roles, roles_digest = _load_canonical_json_with_digest(roles_path)
    index = _trusted_rpc_index(trusted_source_root)
    rows = _locked_test_cohort_from_lineage(
        source, source_digest, roles, trusted_index=index
    )
    write_new_json(
        output,
        {
            "schema_version": 2,
            "kind": "rpc-fewshot-locked-ground-truth",
            "source_manifest_path": source_relative.as_posix(),
            "source_manifest_sha256": source_digest,
            "scene_role_manifest_path": roles_relative.as_posix(),
            "scene_role_manifest_sha256": roles_digest,
            "objects": [row.to_dict() for row in rows],
        },
    )


def materialize_development_ground_truth(
    source_manifest_path: Path,
    scene_role_manifest_path: Path,
    output: Path,
    *,
    trusted_source_root: Path,
) -> None:
    """Materialize the trusted val2019 development-selection cohort only."""
    _materialize_role_ground_truth(
        source_manifest_path,
        scene_role_manifest_path,
        output,
        trusted_source_root=trusted_source_root,
        kind="rpc-fewshot-development-ground-truth",
        split="val2019",
        role="development_selection",
    )


def _lineage_path(ground_truth_path: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("locked ground-truth lineage path is invalid")
    candidate = (ground_truth_path.parent / value).resolve()
    try:
        candidate.relative_to(ground_truth_path.parent.resolve())
    except ValueError as exc:
        raise ValueError("locked ground-truth lineage path escapes manifest directory") from exc
    return candidate


def _load_role_ground_truth(
    path: Path,
    *,
    trusted_source_root: Path,
    expected_kind: str,
    split: str,
    role: str,
) -> LoadedGroundTruth:
    content = Path(path).read_bytes()
    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid role ground-truth manifest") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise ValueError("role ground-truth manifest is not canonical")
    digest = hashlib.sha256(content).hexdigest()
    if (
        value.get("schema_version") != 2
        or value.get("kind") != expected_kind
        or not isinstance(value.get("objects"), list)
        or not value["objects"]
    ):
        raise ValueError("invalid role ground-truth manifest")
    try:
        rows = tuple(LockedGroundTruthRow.from_dict(item) for item in value["objects"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid role ground-truth manifest") from exc
    source_path = _lineage_path(Path(path), value.get("source_manifest_path"))
    roles_path = _lineage_path(Path(path), value.get("scene_role_manifest_path"))
    source, source_digest = _load_canonical_json_with_digest(source_path)
    roles, roles_digest = _load_canonical_json_with_digest(roles_path)
    if source_digest != value.get("source_manifest_sha256") or roles_digest != value.get("scene_role_manifest_sha256"):
        raise ValueError("role ground-truth lineage SHA-256 mismatch")
    expected = _checkout_cohort_from_lineage(
        source, source_digest, roles, trusted_index=_trusted_rpc_index(trusted_source_root), split=split, role=role
    )
    if len(rows) != len(expected) or {row.identity for row in rows} != {row.identity for row in expected}:
        raise ValueError("role ground-truth must exactly match trusted cohort")
    return LoadedGroundTruth(rows, digest, source_digest, roles_digest)


def _materialize_role_ground_truth(
    source_manifest_path: Path,
    scene_role_manifest_path: Path,
    output: Path,
    *,
    trusted_source_root: Path,
    kind: str,
    split: str,
    role: str,
) -> None:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    source_path, roles_path, output_parent = Path(source_manifest_path).resolve(), Path(scene_role_manifest_path).resolve(), Path(output).parent.resolve()
    try:
        source_relative, roles_relative = source_path.relative_to(output_parent), roles_path.relative_to(output_parent)
    except ValueError as exc:
        raise ValueError("role ground-truth lineage artifacts must be below the output directory") from exc
    source, source_digest = _load_canonical_json_with_digest(source_path)
    roles, roles_digest = _load_canonical_json_with_digest(roles_path)
    rows = _checkout_cohort_from_lineage(
        source, source_digest, roles, trusted_index=_trusted_rpc_index(trusted_source_root), split=split, role=role
    )
    write_new_json(output, {
        "schema_version": 2, "kind": kind,
        "source_manifest_path": source_relative.as_posix(), "source_manifest_sha256": source_digest,
        "scene_role_manifest_path": roles_relative.as_posix(), "scene_role_manifest_sha256": roles_digest,
        "objects": [row.to_dict() for row in rows],
    })


def _trusted_rpc_index(trusted_source_root: Path) -> RpcIndex:
    """Return a raw index verified against the immutable default RPC contract.

    This private seam is patched only by hermetic tests. Public entry points
    accept a source root, never a caller-built index or contract.
    """
    if not isinstance(trusted_source_root, Path):
        raise ValueError("trusted RPC source root is required")
    return _load_verified_default_rpc_index(trusted_source_root)


def _load_verified_default_rpc_index(trusted_source_root: Path) -> RpcIndex:
    return load_rpc_index(RpcDatasetContract.default(), trusted_source_root)


def _locked_test_cohort_from_lineage(
    source: Mapping[str, object],
    source_digest: str,
    roles: Mapping[str, object],
    *,
    trusted_index: RpcIndex,
) -> tuple[LockedGroundTruthRow, ...]:
    if (
        source.get("schema_version") != 1
        or source.get("kind") != "rpc-fewshot-resolved-inputs"
        or source.get("source") != "RPC 2019"
        or not isinstance(source.get("images"), list)
        or not isinstance(source.get("objects"), list)
    ):
        raise ValueError("invalid locked ground-truth source manifest")
    contract = trusted_index.contract
    if (
        source.get("annotation_sha256") != dict(contract.annotation_sha256)
        or source.get("image_counts") != dict(contract.image_counts)
        or not isinstance(source.get("categories"), list)
    ):
        raise ValueError("locked ground-truth source does not match RPC 2019 contract")
    _validate_resolved_source_against_trusted(source, trusted_index)
    if (
        roles.get("schema_version") != 1
        or roles.get("kind") != "rpc-fewshot-scene-roles"
        or roles.get("source_manifest_sha256") != source_digest
        or not isinstance(roles.get("assignments"), list)
    ):
        raise ValueError("invalid locked ground-truth scene-role manifest")
    images: dict[int, tuple[str, str]] = {}
    for image in source["images"]:
        if not isinstance(image, Mapping) or image.get("split") != "test2019":
            continue
        image_id, sample_id, level = (
            image.get("image_id"), image.get("source_identity"), image.get("level")
        )
        if type(image_id) is not int or image_id <= 0 or not isinstance(sample_id, str) or not sample_id:
            raise ValueError("invalid test2019 source image identity")
        if level not in {"easy", "medium", "hard"} or image_id in images:
            raise ValueError("invalid test2019 source image level")
        images[image_id] = (sample_id, level)
    if not images:
        raise ValueError("locked ground-truth source lacks test2019 images")
    expected_roles = {
        (row.split, row.image_id, row.role, row.burst_id, row.difficulty)
        for row in _build_canonical_scene_roles(trusted_index)
    }
    assignments: set[tuple[str, int, str, str, str]] = set()
    for assignment in roles["assignments"]:
        if not isinstance(assignment, Mapping):
            raise ValueError("invalid locked ground-truth scene-role assignment")
        image_id, role, burst_id, difficulty = (
            assignment.get("image_id"), assignment.get("role"), assignment.get("burst_id"), assignment.get("difficulty")
        )
        split = assignment.get("split")
        if (
            split not in {"val2019", "test2019"}
            or type(image_id) is not int
            or not isinstance(burst_id, str)
            or not burst_id
            or difficulty not in {"easy", "medium", "hard"}
            or role not in {"calibration", "development_selection", "locked_acceptance"}
        ):
            raise ValueError("invalid locked ground-truth scene-role assignment")
        assignments.add((split, image_id, role, burst_id, difficulty))
    if len(assignments) != len(roles["assignments"]) or assignments != expected_roles:
        raise ValueError(
            "scene-role manifest does not exactly equal canonical trusted val/test roles"
        )
    assignments_by_image = {
        (split, image_id): (burst_id, difficulty)
        for split, image_id, _role, burst_id, difficulty in assignments
    }
    difficulty_code = {"easy": "E", "medium": "M", "hard": "H"}
    expected: list[LockedGroundTruthRow] = []
    object_ids: set[int] = set()
    for item in trusted_index.objects:
        if item.split != "test2019":
            continue
        object_id, image_id, category_id = item.annotation_id, item.image_id, item.category_id
        if (
            type(object_id) is not int or object_id <= 0 or object_id in object_ids
            or type(image_id) is not int or image_id not in images
            or type(category_id) is not int or category_id <= 0
        ):
            raise ValueError("invalid test2019 source object")
        object_ids.add(object_id)
        sample_id, _ = images[image_id]
        burst_id, difficulty = assignments_by_image[("test2019", image_id)]
        expected.append(LockedGroundTruthRow(sample_id, object_id, burst_id, difficulty_code[difficulty], category_id))
    if not expected:
        raise ValueError("locked ground-truth source lacks test2019 objects")
    return tuple(sorted(expected, key=lambda row: row.object_id))


def _checkout_cohort_from_lineage(
    source: Mapping[str, object], source_digest: str, roles: Mapping[str, object], *,
    trusted_index: RpcIndex, split: str, role: str,
) -> tuple[LockedGroundTruthRow, ...]:
    """Derive a complete, role-specific checkout cohort from authenticated RPC lineage."""
    if (split, role) == ("test2019", "locked_acceptance"):
        return _locked_test_cohort_from_lineage(source, source_digest, roles, trusted_index=trusted_index)
    if (split, role) != ("val2019", "development_selection"):
        raise ValueError("unsupported trusted checkout cohort")
    if (
        source.get("schema_version") != 1 or source.get("kind") != "rpc-fewshot-resolved-inputs"
        or source.get("source") != "RPC 2019" or not isinstance(source.get("images"), list)
        or not isinstance(source.get("objects"), list)
    ):
        raise ValueError("invalid development ground-truth source manifest")
    contract = trusted_index.contract
    if source.get("annotation_sha256") != dict(contract.annotation_sha256) or source.get("image_counts") != dict(contract.image_counts):
        raise ValueError("development ground-truth source does not match RPC 2019 contract")
    _validate_resolved_source_against_trusted_split(source, trusted_index, split)
    if (
        roles.get("schema_version") != 1 or roles.get("kind") != "rpc-fewshot-scene-roles"
        or roles.get("source_manifest_sha256") != source_digest or not isinstance(roles.get("assignments"), list)
    ):
        raise ValueError("invalid development ground-truth scene-role manifest")
    expected_roles = {(row.split, row.image_id, row.role, row.burst_id, row.difficulty) for row in _build_canonical_scene_roles(trusted_index)}
    assignments: set[tuple[str, int, str, str, str]] = set()
    for item in roles["assignments"]:
        if not isinstance(item, Mapping):
            raise ValueError("invalid development ground-truth scene-role assignment")
        row = (item.get("split"), item.get("image_id"), item.get("role"), item.get("burst_id"), item.get("difficulty"))
        if not isinstance(row[0], str) or type(row[1]) is not int or not isinstance(row[2], str) or not isinstance(row[3], str) or not isinstance(row[4], str):
            raise ValueError("invalid development ground-truth scene-role assignment")
        assignments.add(row)  # type: ignore[arg-type]
    if len(assignments) != len(roles["assignments"]) or assignments != expected_roles:
        raise ValueError("scene-role manifest does not exactly equal canonical trusted val/test roles")
    image_rows = {
        item["image_id"]: (item["source_identity"], item["level"])
        for item in source["images"]
        if isinstance(item, Mapping) and item.get("split") == split
    }
    role_by_image = {image_id: (burst_id, difficulty) for assigned_split, image_id, assigned_role, burst_id, difficulty in assignments if assigned_split == split and assigned_role == role}
    expected: list[LockedGroundTruthRow] = []
    for item in trusted_index.objects:
        if item.split != split:
            continue
        if item.image_id not in image_rows or item.image_id not in role_by_image:
            continue
        sample_id, _ = image_rows[item.image_id]
        burst_id, difficulty = role_by_image[item.image_id]
        if not isinstance(sample_id, str) or difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("invalid trusted development source identity")
        expected.append(LockedGroundTruthRow(sample_id, item.annotation_id, burst_id, {"easy":"E", "medium":"M", "hard":"H"}[difficulty], item.category_id))
    if not expected:
        raise ValueError("development role has no trusted objects")
    return tuple(sorted(expected, key=lambda row: row.object_id))


def _build_canonical_scene_roles(index: RpcIndex):
    """Private test seam around the canonical raw-index role builder."""
    return build_scene_roles(index, split_version=_CANONICAL_SCENE_SPLIT_VERSION)


def _validate_resolved_source_against_trusted(
    source: Mapping[str, object], trusted_index: RpcIndex
) -> None:
    """Check resolved source identities against independently parsed raw RPC data."""
    trusted_test_images = {
        (item.image_id, item.source_identity, item.level)
        for item in trusted_index.images
        if item.split == "test2019"
    }
    declared_test_images: set[tuple[int, str, str]] = set()
    declared_test_image_count = 0
    for item in source["images"]:  # validated list shape by caller
        if not isinstance(item, Mapping) or item.get("split") != "test2019":
            continue
        declared_test_image_count += 1
        image_id, identity, level = (
            item.get("image_id"), item.get("source_identity"), item.get("level")
        )
        if (
            type(image_id) is not int
            or image_id <= 0
            or not isinstance(identity, str)
            or not identity
            or level not in {"easy", "medium", "hard"}
        ):
            raise ValueError("invalid trusted RPC source image identity")
        declared_test_images.add((image_id, identity, level))
    if (
        declared_test_image_count != len(declared_test_images)
        or declared_test_images != trusted_test_images
    ):
        raise ValueError("resolved source does not exactly match trusted RPC source images")
    trusted_test_objects = {
        (item.annotation_id, item.image_id, item.category_id)
        for item in trusted_index.objects
        if item.split == "test2019"
    }
    declared_test_objects: set[tuple[int, int, int]] = set()
    declared_test_object_count = 0
    for item in source["objects"]:  # validated list shape by caller
        if not isinstance(item, Mapping) or item.get("split") != "test2019":
            continue
        declared_test_object_count += 1
        object_id, image_id, category_id = (
            item.get("annotation_id"), item.get("image_id"), item.get("category_id")
        )
        if any(type(value) is not int or value <= 0 for value in (object_id, image_id, category_id)):
            raise ValueError("invalid trusted RPC source object identity")
        declared_test_objects.add((object_id, image_id, category_id))
    if (
        declared_test_object_count != len(declared_test_objects)
        or declared_test_objects != trusted_test_objects
    ):
        raise ValueError("resolved source does not exactly match trusted RPC source objects")


def _validate_resolved_source_against_trusted_split(
    source: Mapping[str, object], trusted_index: RpcIndex, split: str
) -> None:
    """Exact raw-source comparison for the requested non-locked role split."""
    if split == "test2019":
        _validate_resolved_source_against_trusted(source, trusted_index)
        return
    trusted_images = {(item.image_id, item.source_identity, item.level) for item in trusted_index.images if item.split == split}
    declared_images = {
        (item.get("image_id"), item.get("source_identity"), item.get("level"))
        for item in source.get("images", [])
        if isinstance(item, Mapping) and item.get("split") == split
    }
    trusted_objects = {(item.annotation_id, item.image_id, item.category_id) for item in trusted_index.objects if item.split == split}
    declared_objects = {
        (item.get("annotation_id"), item.get("image_id"), item.get("category_id"))
        for item in source.get("objects", [])
        if isinstance(item, Mapping) and item.get("split") == split
    }
    if declared_images != trusted_images or declared_objects != trusted_objects:
        raise ValueError("resolved source does not exactly match trusted RPC source split")


def score(
    evidence_path: Path,
    reference_path: Path,
    condition_path: Path,
    reference_condition_path: Path,
    ground_truth_manifest_path: Path,
    base_checkpoint_evidence_path: Path,
    output: Path,
    *,
    trusted_source_root: Path,
) -> None:
    """Write one non-final condition score; only complete aggregation can pass."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    condition = load_canonical_json(condition_path)
    reference_condition = load_canonical_json(reference_condition_path)
    candidate_plan = _condition_scoring_plan(
        condition,
        trusted_source_root=trusted_source_root,
    )
    reference_plan = _condition_scoring_plan(
        reference_condition,
        trusted_source_root=trusted_source_root,
    )
    _validate_comparable_scoring_plans(candidate_plan, reference_plan)
    _validate_paired_condition_axes(
        (_score_receipt_condition(condition, "condition"),),
        (_score_receipt_condition(reference_condition, "condition"),),
    )
    paired_stage = _paired_condition_stage(condition, reference_condition)
    stage_four_selection = None
    if paired_stage == "locked":
        stage_four_selection = _validate_locked_condition_receipt_pair(
            condition,
            reference_condition,
            trusted_source_root=trusted_source_root,
        )
    candidate_id, _ = condition_provenance(condition)
    reference_id, _ = condition_provenance(reference_condition)
    candidate_novel, candidate_base = condition_cohort(condition)
    reference_novel, reference_base = condition_cohort(reference_condition)
    if candidate_novel != reference_novel or candidate_base != reference_base:
        raise ValueError("candidate/reference condition cohort mismatch")
    if _cohort_manifest_sha256(condition) != _cohort_manifest_sha256(reference_condition):
        raise ValueError("candidate/reference cohort manifest mismatch")
    ground_truth = load_stage_ground_truth(
        ground_truth_manifest_path, stage=paired_stage,
        trusted_source_root=trusted_source_root,
    )
    if ground_truth.sha256 != _cohort_manifest_sha256(condition):
        raise ValueError("ground-truth manifest SHA-256 mismatch")
    statuses = (condition.get("status"), reference_condition.get("status"))
    if statuses != ("completed", "completed"):
        write_new_json(output, {
            "schema_version": 2,
            "kind": "rpc-fewshot-score-receipt",
            "status": "unavailable",
            "decision_status": "unavailable",
            "reason": "candidate or reference condition is unavailable",
            "candidate_condition_id": candidate_id,
            "reference_condition_id": reference_id,
        })
        return
    base_checkpoint_evidence, base_evidence_sha256 = _load_canonical_json_with_digest(
        base_checkpoint_evidence_path
    )
    base_checkpoint_recall = validate_fold_base_checkpoint_evidence(
        condition,
        base_checkpoint_evidence,
        evidence_sha256=base_evidence_sha256,
    )
    reference_base_recall = validate_fold_base_checkpoint_evidence(
        reference_condition,
        base_checkpoint_evidence,
        evidence_sha256=base_evidence_sha256,
    )
    if reference_base_recall != base_checkpoint_recall:
        raise ValueError("candidate/reference fold base checkpoint evidence mismatch")
    candidate_evidence = load_canonical_jsonl(evidence_path)
    reference_evidence = load_canonical_jsonl(reference_path)
    candidate_rows = validate_evidence_completeness(
        candidate_evidence.rows, ground_truth.rows
    )
    reference_rows = validate_evidence_completeness(
        reference_evidence.rows, ground_truth.rows
    )
    candidate_rows = validate_evidence_against_condition(candidate_rows, condition)
    reference_rows = validate_evidence_against_condition(
        reference_rows, reference_condition
    )
    candidate_rows, reference_rows = validate_paired_evidence(candidate_rows, reference_rows)
    novel = candidate_novel
    candidate_summary = full_system_summary(candidate_rows, novel_category_ids=novel, reference_rows=reference_rows)
    reference_summary = full_system_summary(reference_rows, novel_category_ids=novel)
    candidate_branches = _branch_top1_summaries(candidate_rows, novel)
    reference_branches = _branch_top1_summaries(reference_rows, novel)
    interval = bootstrap_paired_deltas(
        candidate_rows,
        reference_rows,
        novel_category_ids=novel,
        seed=candidate_plan.bootstrap_seed,
        replicates=candidate_plan.bootstrap_replicates,
    )
    score_receipt: dict[str, object] = {
        "schema_version": 2,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "decision_status": "non_final",
        "candidate_condition_id": candidate_id,
        "reference_condition_id": reference_id,
        "candidate_condition": condition["condition"],
        "reference_condition": reference_condition["condition"],
        "candidate_scoring_plan": candidate_plan.to_dict(),
        "reference_scoring_plan": reference_plan.to_dict(),
        "cohort": {
            "base_category_ids": sorted(candidate_base),
            "novel_category_ids": sorted(novel),
        },
        "candidate_provenance": _provenance(condition, candidate_evidence.sha256),
        "reference_provenance": _provenance(reference_condition, reference_evidence.sha256),
        "candidate_branch_top1": candidate_branches,
        "reference_branch_top1": reference_branches,
        "candidate_full_system": asdict(candidate_summary),
        "reference_full_system": asdict(reference_summary),
        "paired_bootstrap_95": asdict(interval),
        "fold_base_checkpoint": {
            "base_macro_final_correct_recall": base_checkpoint_recall,
            "evidence_sha256": base_evidence_sha256,
            "evidence_path": str(base_checkpoint_evidence_path),
            "checkpoint_sha256": base_checkpoint_evidence["checkpoint_sha256"],
            "fold": base_checkpoint_evidence["fold"],
        },
        "locked_ground_truth": _locked_ground_truth_summary(ground_truth),
        "minimum_rule_inputs": {
            "registered_coverage": candidate_summary.registered_coverage,
            "novel_macro_recall_lower_delta": interval.novel_macro_recall_lower_delta,
            "novel_wrong_registered_sku_rate_upper_delta": (
                interval.novel_wrong_registered_sku_rate_upper_delta
            ),
            "novel_loss_over_10pp_fraction": candidate_summary.novel_loss_over_10pp_fraction,
            "candidate_base_macro_final_correct_recall": (
                candidate_summary.base_macro_final_correct_recall
            ),
            "fold_base_checkpoint_macro_final_correct_recall": base_checkpoint_recall,
        },
    }
    if stage_four_selection is not None:
        score_receipt["stage_four_selection"] = stage_four_selection.to_dict()
        score_receipt["stage_four_confirmation_score_receipt_paths"] = list(
            str(path) for path in _stage_four_receipt_paths(condition)
        )
    stage = paired_stage
    if stage == "stage1":
        score_receipt["stage1_global_top1_agreement"] = {
            "candidate": branch_top1_agreement(
                candidate_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
            "reference": branch_top1_agreement(
                reference_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
        }
    write_new_json(output, score_receipt)


def _branch_top1_summaries(
    rows: tuple[ResearchEvidenceRow, ...],
    novel_category_ids: set[int],
) -> dict[str, object]:
    return {
        branch: asdict(
            branch_top1_summary(
                rows,
                branch=branch,
                novel_category_ids=novel_category_ids,
            )
        )
        for branch in _SCORE_BRANCHES
    }


def _locked_ground_truth_summary(
    ground_truth: LoadedGroundTruth,
) -> dict[str, object]:
    return {
        "burst_count": len({row.burst_id for row in ground_truth.rows}),
        "manifest_sha256": ground_truth.sha256,
        "object_count": len(ground_truth.rows),
        "sample_count": len({row.sample_id for row in ground_truth.rows}),
        "scene_role_manifest_sha256": ground_truth.scene_role_manifest_sha256,
        "source_manifest_sha256": ground_truth.source_manifest_sha256,
    }


def _paired_condition_stage(
    candidate: Mapping[str, object],
    reference: Mapping[str, object],
) -> str:
    candidate_condition = candidate.get("condition")
    reference_condition = reference.get("condition")
    candidate_stage = (
        candidate_condition.get("stage")
        if isinstance(candidate_condition, Mapping)
        else None
    )
    reference_stage = (
        reference_condition.get("stage")
        if isinstance(reference_condition, Mapping)
        else None
    )
    return _paired_nested_condition_stage(
        candidate_stage,
        reference_stage,
    )


def _paired_nested_condition_stage(
    candidate_stage: object,
    reference_stage: object,
) -> str:
    if candidate_stage not in {"stage1", "ascending", "confirmation", "locked"} or (
        reference_stage != candidate_stage
    ):
        raise ValueError("candidate/reference condition stage mismatch")
    return candidate_stage


def validate_fold_base_checkpoint_evidence(
    condition: Mapping[str, object],
    evidence: Mapping[str, object],
    *,
    evidence_sha256: str,
) -> float:
    """Validate the immutable fold-base score evidence bound by a condition."""
    if not isinstance(evidence, Mapping):
        raise ValueError("fold base checkpoint evidence must be an object")
    expected_fields = {
        "schema_version",
        "kind",
        "fold",
        "checkpoint_sha256",
        "cohort_manifest_sha256",
        "base_category_ids",
        "sample_count",
        "base_macro_final_correct_recall",
    }
    if set(evidence) != expected_fields:
        raise ValueError("fold base checkpoint evidence has missing or unrecognized fields")
    nested = condition.get("condition")
    cohort = condition.get("cohort")
    binding = condition.get("fold_base_checkpoint")
    if not isinstance(nested, Mapping) or not isinstance(cohort, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("condition lacks fold base checkpoint binding")
    if evidence.get("schema_version") != 1 or evidence.get("kind") != "rpc-fewshot-fold-base-checkpoint-evidence":
        raise ValueError("invalid fold base checkpoint evidence schema")
    if evidence.get("fold") != nested.get("fold") or binding.get("fold") != nested.get("fold"):
        raise ValueError("fold base checkpoint evidence fold mismatch")
    if evidence.get("checkpoint_sha256") != binding.get("checkpoint_sha256"):
        raise ValueError("base checkpoint SHA-256 mismatch")
    if evidence_sha256 != binding.get("evidence_sha256"):
        raise ValueError("base checkpoint evidence SHA-256 mismatch")
    if evidence.get("cohort_manifest_sha256") != cohort.get("manifest_sha256"):
        raise ValueError("base checkpoint cohort manifest mismatch")
    base_category_ids = evidence.get("base_category_ids")
    if (
        not isinstance(base_category_ids, list)
        or base_category_ids != cohort.get("base_category_ids")
    ):
        raise ValueError("base checkpoint category cohort mismatch")
    sample_count = evidence.get("sample_count")
    if type(sample_count) is not int or sample_count <= 0:
        raise ValueError("base checkpoint sample_count must be a positive integer")
    recall = evidence.get("base_macro_final_correct_recall")
    if (
        not isinstance(recall, (int, float))
        or isinstance(recall, bool)
        or not math.isfinite(float(recall))
        or not 0.0 <= float(recall) <= 1.0
    ):
        raise ValueError("base checkpoint recall must be finite and in [0, 1]")
    return float(recall)


def aggregate_score_receipts(
    score_paths: Iterable[Path],
    output: Path,
    *,
    evidence_paths: Iterable[Path],
    reference_evidence_paths: Iterable[Path],
    ground_truth_manifest_path: Path,
    trusted_source_root: Path,
) -> None:
    """Recompute one final decision from every declared raw evidence pair."""
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    score_receipt_paths = tuple(Path(path) for path in score_paths)
    candidate_evidence_paths = tuple(Path(path) for path in evidence_paths)
    frozen_reference_paths = tuple(Path(path) for path in reference_evidence_paths)
    loaded_receipts = tuple(
        _load_canonical_json_with_digest(path) for path in score_receipt_paths
    )
    receipts = tuple(item[0] for item in loaded_receipts)
    if not receipts:
        raise ValueError("aggregate requires score receipts")
    if (
        len(candidate_evidence_paths) != len(receipts)
        or len(frozen_reference_paths) != len(receipts)
    ):
        raise ValueError(
            "aggregate requires one candidate/reference evidence file per score receipt"
        )
    ground_truth = load_locked_ground_truth(
        ground_truth_manifest_path,
        trusted_source_root=trusted_source_root,
    )
    candidate_plan = _score_receipt_plan(receipts[0], "candidate_scoring_plan")
    reference_plan = _score_receipt_plan(receipts[0], "reference_scoring_plan")
    _validate_comparable_scoring_plans(candidate_plan, reference_plan)
    for receipt in receipts:
        if (
            receipt.get("schema_version") != 2
            or receipt.get("kind") != "rpc-fewshot-score-receipt"
            or receipt.get("status") != "completed"
            or receipt.get("decision_status") != "non_final"
        ):
            raise ValueError("aggregate accepts only completed non-final score receipts")
        if _score_receipt_plan(receipt, "candidate_scoring_plan") != candidate_plan:
            raise ValueError("candidate scoring plan mismatch")
        if _score_receipt_plan(receipt, "reference_scoring_plan") != reference_plan:
            raise ValueError("reference scoring plan mismatch")
    candidate_conditions = tuple(
        _score_receipt_condition(receipt, "candidate_condition") for receipt in receipts
    )
    reference_conditions = tuple(
        _score_receipt_condition(receipt, "reference_condition") for receipt in receipts
    )
    _validate_paired_condition_axes(candidate_conditions, reference_conditions)
    aggregate_stage = _validated_aggregate_stage(
        candidate_conditions, reference_conditions
    )
    if aggregate_stage == "locked" and len(candidate_plan.expected_condition_ids) < 2:
        raise ValueError("a single condition is non-final; no final pass is available")
    _validate_complete_condition_set(candidate_conditions, candidate_plan)
    _validate_complete_condition_set(reference_conditions, reference_plan)
    locked_selections: tuple[StageFourSelection, ...] = ()
    if aggregate_stage == "locked":
        locked_selections = tuple(
            _validate_locked_score_receipt_pair(
                receipt,
                trusted_source_root=trusted_source_root,
            )
            for receipt in receipts
        )
        _validate_comparable_locked_selections(locked_selections, candidate_plan)
    aggregate_conditions: list[PairedConditionEvidence] = []
    candidate_summaries = []
    reference_summaries = []
    base_checkpoints: dict[int, tuple[str, str, float]] = {}
    evidence_receipts: list[dict[str, object]] = []
    branch_reports: list[dict[str, object]] = []
    for receipt, candidate_evidence_path, reference_evidence_path in zip(
        receipts,
        candidate_evidence_paths,
        frozen_reference_paths,
        strict=True,
    ):
        (
            paired,
            candidate_summary,
            reference_summary,
            base_checkpoint,
            evidence_record,
            branch_report,
        ) = _load_aggregate_evidence(
            receipt,
            candidate_plan,
            reference_plan,
            candidate_evidence_path,
            reference_evidence_path,
            ground_truth,
        )
        existing_base = base_checkpoints.setdefault(paired.fold, base_checkpoint)
        if existing_base != base_checkpoint:
            raise ValueError(
                "score receipts in one fold have inconsistent fold base checkpoint evidence"
            )
        aggregate_conditions.append(paired)
        candidate_summaries.append(candidate_summary)
        reference_summaries.append(reference_summary)
        evidence_receipts.append(evidence_record)
        branch_reports.append(branch_report)
    if set(base_checkpoints) != set(candidate_plan.folds):
        raise ValueError("aggregate lacks fold base checkpoint evidence")
    interval = bootstrap_paired_condition_deltas(
        aggregate_conditions,
        seed=candidate_plan.bootstrap_seed,
        replicates=candidate_plan.bootstrap_replicates,
    )
    minimum_rule_inputs = {
        "registered_coverage": _average(
            summary.registered_coverage for summary in candidate_summaries
        ),
        "novel_macro_recall_lower_delta": interval.novel_macro_recall_lower_delta,
        "novel_wrong_registered_sku_rate_upper_delta": (
            interval.novel_wrong_registered_sku_rate_upper_delta
        ),
        "novel_loss_over_10pp_fraction": _aggregate_novel_loss_fraction(
            aggregate_conditions,
            candidate_summaries,
            reference_summaries,
        ),
        "candidate_base_macro_final_correct_recall": _average(
            summary.base_macro_final_correct_recall for summary in candidate_summaries
        ),
        "fold_base_checkpoint_macro_final_correct_recall": _average(
            value[2] for value in base_checkpoints.values()
        ),
    }
    passes = _minimum_rule_inputs_pass(minimum_rule_inputs)
    aggregate_candidate_summary = _aggregate_full_system_summary(candidate_summaries)
    aggregate_reference_summary = _aggregate_full_system_summary(reference_summaries)
    decision_scope = (
        "complete_locked_fold_seed_aggregate"
        if aggregate_stage == "locked"
        else "complete_confirmation_fold_seed_aggregate"
    )
    decision: dict[str, object] = (
        {"decision_status": "final", "final_pass": passes}
        if aggregate_stage == "locked"
        else {"decision_status": "provisional", "provisional_pass": passes}
    )
    output_receipt: dict[str, object] = {
            "schema_version": 2,
            "kind": (
                "rpc-fewshot-final-score-receipt"
                if aggregate_stage == "locked"
                else "rpc-fewshot-confirmation-score-receipt"
            ),
            "status": "completed",
            "decision_scope": decision_scope,
            "aggregate_stage": aggregate_stage,
            "candidate_scoring_plan": candidate_plan.to_dict(),
            "reference_scoring_plan": reference_plan.to_dict(),
            "candidate_scoring_plan_sha256": candidate_plan.sha256,
            "reference_scoring_plan_sha256": reference_plan.sha256,
            "condition_count": len(receipts),
            "candidate_condition_ids": sorted(candidate_plan.expected_condition_ids),
            "reference_condition_ids": sorted(reference_plan.expected_condition_ids),
            "score_receipts": sorted(
                (
                    {
                        "candidate_condition_id": condition["condition_id"],
                        "sha256": digest,
                    }
                    for condition, (_, digest) in zip(
                        candidate_conditions, loaded_receipts, strict=True
                    )
                ),
                key=lambda item: item["candidate_condition_id"],
            ),
            "raw_evidence": sorted(
                evidence_receipts,
                key=lambda item: item["candidate_condition_id"],
            ),
            "condition_branch_top1": sorted(
                branch_reports,
                key=lambda item: item["candidate_condition_id"],
            ),
            "candidate_full_system": asdict(aggregate_candidate_summary),
            "reference_full_system": asdict(aggregate_reference_summary),
            "locked_ground_truth": _locked_ground_truth_summary(ground_truth),
            "paired_bootstrap_95": asdict(interval),
            "minimum_rule_inputs": minimum_rule_inputs,
            "upstream_artifacts": [
                _aggregate_upstream_artifact(
                    receipt,
                    score_path=score_path,
                    candidate_path=candidate_path,
                    reference_path=reference_path,
                    ground_truth_path=ground_truth_manifest_path,
                )
                for receipt, score_path, candidate_path, reference_path in zip(
                    receipts,
                    score_receipt_paths,
                    candidate_evidence_paths,
                    frozen_reference_paths,
                    strict=True,
                )
            ],
            **decision,
        }
    if aggregate_stage == "confirmation" and len(receipts) == 1:
        aggregate_novel, aggregate_base = _score_receipt_cohort(
            receipts[0], candidate_plan
        )
        condition = candidate_conditions[0]
        checkpoint_sha256, evidence_sha256, base_recall = base_checkpoints[
            condition["fold"]
        ]
        output_receipt.update(
            {
                "candidate_conditions": list(candidate_conditions),
                "reference_conditions": list(reference_conditions),
                "cohort": {
                    "base_category_ids": sorted(aggregate_base),
                    "novel_category_ids": sorted(aggregate_novel),
                },
                "fold_base_checkpoint": {
                    "base_macro_final_correct_recall": base_recall,
                    "checkpoint_sha256": checkpoint_sha256,
                    "evidence_sha256": evidence_sha256,
                    "fold": condition["fold"],
                },
            }
        )
    if locked_selections:
        output_receipt["stage_four_selections"] = [
            selection.to_dict()
            for selection in sorted(
                locked_selections, key=lambda item: (item.fold, item.support_seed)
            )
        ]
    write_new_json(output, output_receipt)


def _aggregate_full_system_summary(
    summaries: Iterable[FullSystemSummary],
) -> FullSystemSummary:
    """Recompute one report across complete fold/seed raw-evidence cells.

    Individual condition summaries are already rebuilt from immutable JSONL in
    `_load_aggregate_evidence`.  Weighting each scalar by its observed object
    count preserves the exact all-cell rate while retaining per-category and
    difficulty reporting without pretending duplicated support-seed objects are
    one physical evaluation row.
    """
    rows = tuple(summaries)
    if not rows:
        raise ValueError("aggregate full-system report requires summaries")
    total = sum(row.sample_count for row in rows)
    if total <= 0:
        raise ValueError("aggregate full-system report has no observations")

    def weighted(name: str) -> float:
        return sum(getattr(row, name) * row.sample_count for row in rows) / total

    categories = set().union(*(row.per_category_final_correct_recall for row in rows))
    if not categories or any(
        category not in row.per_category_final_correct_recall
        for category in categories
        for row in rows
    ):
        raise ValueError("aggregate full-system report lacks per-category evidence")
    per_category = {
        category: _average(
            row.per_category_final_correct_recall[category] for row in rows
        )
        for category in sorted(categories)
    }
    difficulties = {"E", "M", "H"}
    if any(set(row.by_difficulty) != difficulties for row in rows):
        raise ValueError("aggregate full-system report lacks E/M/H evidence")
    by_difficulty: dict[str, object] = {}
    for difficulty in sorted(difficulties):
        pieces = tuple(row.by_difficulty[difficulty] for row in rows)
        count = sum(piece.sample_count for piece in pieces)

        def difficulty_weighted(name: str) -> float:
            if count == 0:
                return 0.0
            return sum(getattr(piece, name) * piece.sample_count for piece in pieces) / count

        by_difficulty[difficulty] = DifficultySummary(
            sample_count=count,
            unknown_rate=difficulty_weighted("unknown_rate"),
            registered_coverage=difficulty_weighted("registered_coverage"),
            wrong_registered_sku_rate=difficulty_weighted("wrong_registered_sku_rate"),
            novel_macro_final_correct_recall=difficulty_weighted(
                "novel_macro_final_correct_recall"
            ),
            base_macro_final_correct_recall=difficulty_weighted(
                "base_macro_final_correct_recall"
            ),
            conditional_dino_execution_rate=difficulty_weighted(
                "conditional_dino_execution_rate"
            ),
        )
    return FullSystemSummary(
        sample_count=total,
        wrong_registered_sku_rate=weighted("wrong_registered_sku_rate"),
        novel_wrong_registered_sku_rate=weighted("novel_wrong_registered_sku_rate"),
        base_wrong_registered_sku_rate=weighted("base_wrong_registered_sku_rate"),
        unknown_rate=weighted("unknown_rate"),
        registered_coverage=weighted("registered_coverage"),
        novel_macro_final_correct_recall=weighted("novel_macro_final_correct_recall"),
        base_macro_final_correct_recall=weighted("base_macro_final_correct_recall"),
        per_category_final_correct_recall=per_category,
        novel_loss_over_10pp_fraction=weighted("novel_loss_over_10pp_fraction"),
        conditional_dino_execution_rate=weighted("conditional_dino_execution_rate"),
        by_difficulty=by_difficulty,  # type: ignore[arg-type]
    )


def _aggregate_upstream_artifact(
    receipt: Mapping[str, object],
    *,
    score_path: Path,
    candidate_path: Path,
    reference_path: Path,
    ground_truth_path: Path,
) -> dict[str, object]:
    artifact: dict[str, object] = {
        "candidate_evidence_path": str(candidate_path),
        "candidate_score_receipt_path": str(score_path),
        "ground_truth_manifest_path": str(ground_truth_path),
        "reference_evidence_path": str(reference_path),
    }
    base = receipt.get("fold_base_checkpoint")
    if isinstance(base, Mapping) and isinstance(base.get("evidence_path"), str):
        artifact["fold_base_checkpoint_evidence_path"] = base["evidence_path"]
    return artifact


def validate_stage_four_confirmation_derivation(
    receipt: Mapping[str, object],
    *,
    trusted_source_root: Path,
) -> None:
    """Rebuild a Stage-4 aggregate from its declared immutable upstream files.

    Stage-4 JSON is a compact conclusion, not an authority in its own right.
    The confirmation artifact must therefore reproduce byte-for-byte from the
    declared candidate/reference score receipts, raw evidence, and locked
    ground-truth manifest before it can schedule a locked Stage-5 run.
    """
    artifacts = receipt.get("upstream_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], Mapping):
        raise ValueError("Stage-4 confirmation score receipt lacks derivation artifacts")
    artifact = artifacts[0]
    required = {
        "candidate_evidence_path",
        "candidate_score_receipt_path",
        "fold_base_checkpoint_evidence_path",
        "ground_truth_manifest_path",
        "reference_evidence_path",
    }
    if set(artifact) != required or any(
        not isinstance(artifact.get(name), str) or not artifact[name]
        for name in required
    ):
        raise ValueError("Stage-4 confirmation score receipt has invalid derivation artifacts")
    score_path = Path(artifact["candidate_score_receipt_path"])
    candidate_path = Path(artifact["candidate_evidence_path"])
    reference_path = Path(artifact["reference_evidence_path"])
    ground_truth_path = Path(artifact["ground_truth_manifest_path"])
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rpc-stage-four-derivation-") as directory:
        rebuilt_path = Path(directory) / "rebuilt-confirmation.json"
        try:
            aggregate_score_receipts(
                (score_path,),
                rebuilt_path,
                evidence_paths=(candidate_path,),
                reference_evidence_paths=(reference_path,),
                ground_truth_manifest_path=ground_truth_path,
                trusted_source_root=trusted_source_root,
            )
            rebuilt = load_canonical_json(rebuilt_path)
        except (OSError, ValueError) as exc:
            raise ValueError("Stage-4 confirmation score receipt derivation failed") from exc
    if dict(rebuilt) != dict(receipt):
        raise ValueError("Stage-4 confirmation score receipt is not derivable from upstream artifacts")


def _load_aggregate_evidence(
    receipt: Mapping[str, object],
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
    candidate_path: Path,
    reference_path: Path,
    ground_truth: LoadedGroundTruth,
) -> tuple[
    PairedConditionEvidence,
    FullSystemSummary,
    FullSystemSummary,
    tuple[str, str, float],
    dict[str, object],
    dict[str, object],
]:
    candidate_condition = _score_receipt_condition(receipt, "candidate_condition")
    reference_condition = _score_receipt_condition(receipt, "reference_condition")
    fold = candidate_condition.get("fold")
    support_seed = candidate_condition.get("support_seed")
    if type(fold) is not int or type(support_seed) is not int:
        raise ValueError("score receipt has invalid fold/support-seed axes")
    if (
        receipt.get("candidate_condition_id") != candidate_condition.get("condition_id")
        or receipt.get("reference_condition_id")
        != reference_condition.get("condition_id")
    ):
        raise ValueError("score receipt top-level condition ID mismatch")
    _validate_score_receipt_locked_ground_truth(receipt, ground_truth)
    novel, base = _score_receipt_cohort(receipt, candidate_plan)
    candidate_provenance = _score_receipt_provenance(
        receipt,
        "candidate_provenance",
        candidate_condition,
        candidate_plan,
    )
    reference_provenance = _score_receipt_provenance(
        receipt,
        "reference_provenance",
        reference_condition,
        reference_plan,
    )
    if (
        candidate_provenance["cohort_manifest_sha256"]
        != reference_provenance["cohort_manifest_sha256"]
    ):
        raise ValueError("candidate/reference cohort manifest mismatch")
    if candidate_provenance["cohort_manifest_sha256"] != ground_truth.sha256:
        raise ValueError("locked ground-truth manifest SHA-256 mismatch")
    base_checkpoint = _score_receipt_base_checkpoint(
        receipt,
        fold,
        candidate_plan,
        reference_plan,
        candidate_provenance,
        reference_provenance,
    )
    loaded_candidate = load_canonical_jsonl(candidate_path)
    loaded_reference = load_canonical_jsonl(reference_path)
    if loaded_candidate.sha256 != candidate_provenance["evidence_sha256"]:
        raise ValueError("candidate evidence SHA-256 mismatch")
    if loaded_reference.sha256 != reference_provenance["evidence_sha256"]:
        raise ValueError("reference evidence SHA-256 mismatch")
    candidate_receipt = _reconstructed_condition_receipt(
        candidate_condition,
        candidate_plan,
        candidate_provenance,
        novel,
        base,
    )
    reference_receipt = _reconstructed_condition_receipt(
        reference_condition,
        reference_plan,
        reference_provenance,
        novel,
        base,
    )
    candidate_rows = validate_evidence_completeness(
        loaded_candidate.rows, ground_truth.rows
    )
    reference_rows = validate_evidence_completeness(
        loaded_reference.rows, ground_truth.rows
    )
    candidate_rows = validate_evidence_against_condition(
        candidate_rows, candidate_receipt
    )
    reference_rows = validate_evidence_against_condition(
        reference_rows, reference_receipt
    )
    candidate_rows, reference_rows = validate_paired_evidence(
        candidate_rows, reference_rows
    )
    candidate_summary = full_system_summary(
        candidate_rows,
        novel_category_ids=novel,
        reference_rows=reference_rows,
    )
    reference_summary = full_system_summary(
        reference_rows,
        novel_category_ids=novel,
    )
    branch_report: dict[str, object] = {
        "candidate_condition_id": candidate_condition["condition_id"],
        "reference_condition_id": reference_condition["condition_id"],
        "candidate": _branch_top1_summaries(candidate_rows, novel),
        "reference": _branch_top1_summaries(reference_rows, novel),
    }
    stage = _paired_nested_condition_stage(
        candidate_condition.get("stage"),
        reference_condition.get("stage"),
    )
    if stage == "stage1":
        branch_report["stage1_global_top1_agreement"] = {
            "candidate": branch_top1_agreement(
                candidate_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
            "reference": branch_top1_agreement(
                reference_rows,
                first="repvit_global",
                second="dinov3_global",
            ),
        }
    return (
        PairedConditionEvidence(
            fold=fold,
            support_seed=support_seed,
            novel_category_ids=frozenset(novel),
            candidate=candidate_rows,
            reference=reference_rows,
        ),
        candidate_summary,
        reference_summary,
        base_checkpoint,
        {
            "candidate_condition_id": candidate_condition["condition_id"],
            "candidate_evidence_sha256": loaded_candidate.sha256,
            "reference_condition_id": reference_condition["condition_id"],
            "reference_evidence_sha256": loaded_reference.sha256,
        },
        branch_report,
    )


def _validate_score_receipt_locked_ground_truth(
    receipt: Mapping[str, object],
    ground_truth: LoadedGroundTruth,
) -> None:
    value = receipt.get("locked_ground_truth")
    expected = _locked_ground_truth_summary(ground_truth)
    count_names = ("burst_count", "object_count", "sample_count")
    if (
        not isinstance(value, Mapping)
        or set(value) != set(expected)
        or value.get("manifest_sha256") != expected["manifest_sha256"]
        or value.get("source_manifest_sha256")
        != expected["source_manifest_sha256"]
        or value.get("scene_role_manifest_sha256")
        != expected["scene_role_manifest_sha256"]
        or any(
            type(value.get(name)) is not int
            or value.get(name) != expected[name]
            for name in count_names
        )
    ):
        raise ValueError("score receipt lacks valid locked ground-truth provenance")


def _score_receipt_cohort(
    receipt: Mapping[str, object], plan: ScoringPlan
) -> tuple[set[int], set[int]]:
    raw = receipt.get("cohort")
    if not isinstance(raw, Mapping) or set(raw) != {
        "base_category_ids",
        "novel_category_ids",
    }:
        raise ValueError("score receipt lacks an immutable cohort")
    novel = _category_ids(raw.get("novel_category_ids"), "novel cohort")
    base = _category_ids(raw.get("base_category_ids"), "base cohort")
    if novel & base or novel | base != set(plan.registered_category_ids):
        raise ValueError("score receipt cohort does not match the scoring plan")
    return novel, base


def _score_receipt_provenance(
    receipt: Mapping[str, object],
    name: str,
    condition: Mapping[str, object],
    plan: ScoringPlan,
) -> Mapping[str, str]:
    value = receipt.get(name)
    expected = {
        "condition_id",
        "evidence_sha256",
        "cohort_manifest_sha256",
        "base_checkpoint_sha256",
        "base_checkpoint_evidence_sha256",
        "scoring_plan_sha256",
        "condition_manifest_sha256",
        "model_sha256",
        "support_sha256",
        "calibration_sha256",
        "policy_sha256",
        "preprocessing_sha256",
        "code_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"score receipt lacks complete {name}")
    condition_id = condition.get("condition_id")
    if value.get("condition_id") != condition_id:
        raise ValueError(f"{name} condition ID mismatch")
    for field in expected - {"condition_id"}:
        _require_sha256(field, value.get(field))
    if value.get("scoring_plan_sha256") != plan.sha256:
        raise ValueError(f"{name} scoring plan SHA-256 mismatch")
    return value  # type: ignore[return-value]


def _score_receipt_base_checkpoint(
    receipt: Mapping[str, object],
    fold: int,
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
    candidate_provenance: Mapping[str, str],
    reference_provenance: Mapping[str, str],
) -> tuple[str, str, float]:
    value = receipt.get("fold_base_checkpoint")
    required = {
        "base_macro_final_correct_recall",
        "checkpoint_sha256",
        "evidence_sha256",
        "fold",
    }
    if isinstance(value, Mapping) and "evidence_path" in value:
        required.add("evidence_path")
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("score receipt lacks fold base checkpoint evidence")
    if value.get("fold") != fold:
        raise ValueError("score receipt fold base checkpoint fold mismatch")
    checkpoint_sha256 = value.get("checkpoint_sha256")
    evidence_sha256 = value.get("evidence_sha256")
    _require_sha256("fold base checkpoint_sha256", checkpoint_sha256)
    _require_sha256("fold base evidence_sha256", evidence_sha256)
    candidate_artifact = next(
        item for item in candidate_plan.fold_base_artifacts if item.fold == fold
    )
    reference_artifact = next(
        item for item in reference_plan.fold_base_artifacts if item.fold == fold
    )
    expected = (
        candidate_artifact.checkpoint_sha256,
        candidate_artifact.evidence_sha256,
    )
    if (
        expected
        != (
            reference_artifact.checkpoint_sha256,
            reference_artifact.evidence_sha256,
        )
        or expected != (checkpoint_sha256, evidence_sha256)
        or expected
        != (
            candidate_provenance["base_checkpoint_sha256"],
            candidate_provenance["base_checkpoint_evidence_sha256"],
        )
        or expected
        != (
            reference_provenance["base_checkpoint_sha256"],
            reference_provenance["base_checkpoint_evidence_sha256"],
        )
    ):
        raise ValueError(
            "score receipt fold base checkpoint does not match the scoring plan"
        )
    recall = value.get("base_macro_final_correct_recall")
    if (
        not isinstance(recall, (int, float))
        or isinstance(recall, bool)
        or not math.isfinite(float(recall))
        or not 0.0 <= float(recall) <= 1.0
    ):
        raise ValueError("fold base checkpoint recall must be finite and in [0, 1]")
    if "evidence_path" in required:
        evidence_path = value.get("evidence_path")
        if not isinstance(evidence_path, str) or not evidence_path:
            raise ValueError("score receipt lacks fold base checkpoint evidence path")
        try:
            base_evidence, digest = _load_canonical_json_with_digest(Path(evidence_path))
        except (OSError, ValueError) as exc:
            raise ValueError("cannot resolve fold base checkpoint evidence") from exc
        if digest != evidence_sha256:
            raise ValueError("fold base checkpoint evidence SHA-256 mismatch")
        cohort = receipt.get("cohort")
        expected_fields = {
            "schema_version",
            "kind",
            "fold",
            "checkpoint_sha256",
            "cohort_manifest_sha256",
            "base_category_ids",
            "sample_count",
            "base_macro_final_correct_recall",
        }
        if (
            set(base_evidence) != expected_fields
            or base_evidence.get("schema_version") != 1
            or base_evidence.get("kind") != "rpc-fewshot-fold-base-checkpoint-evidence"
            or base_evidence.get("fold") != fold
            or base_evidence.get("checkpoint_sha256") != checkpoint_sha256
            or not isinstance(cohort, Mapping)
            or base_evidence.get("cohort_manifest_sha256")
            != candidate_provenance["cohort_manifest_sha256"]
            or base_evidence.get("base_category_ids") != cohort.get("base_category_ids")
            or type(base_evidence.get("sample_count")) is not int
            or base_evidence["sample_count"] <= 0
            or base_evidence.get("base_macro_final_correct_recall") != recall
        ):
            raise ValueError("fold base checkpoint evidence does not reproduce score receipt")
    return str(checkpoint_sha256), str(evidence_sha256), float(recall)


def _reconstructed_condition_receipt(
    condition: Mapping[str, object],
    plan: ScoringPlan,
    provenance: Mapping[str, str],
    novel: set[int],
    base: set[int],
) -> Mapping[str, object]:
    return {
        "condition": dict(condition),
        "cohort": {
            "base_category_ids": sorted(base),
            "fold": condition["fold"],
            "manifest_sha256": provenance["cohort_manifest_sha256"],
            "novel_category_ids": sorted(novel),
        },
        "scoring": {
            "registered_category_ids": list(plan.registered_category_ids),
        },
        **{
            name: provenance[name]
            for name in (
                "condition_manifest_sha256",
                "model_sha256",
                "support_sha256",
                "calibration_sha256",
                "policy_sha256",
                "preprocessing_sha256",
                "code_sha256",
            )
        },
    }


def _provenance(condition: Mapping[str, object], evidence_sha256: str) -> dict[str, str]:
    condition_id, hashes = condition_provenance(condition)
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    binding = condition.get("fold_base_checkpoint")
    plan_sha256 = condition.get("scoring_plan_sha256")
    if not isinstance(binding, Mapping) or not isinstance(plan_sha256, str):
        raise ValueError("condition receipt lacks scoring/base-checkpoint provenance")
    return {
        "condition_id": condition_id,
        "evidence_sha256": evidence_sha256,
        "cohort_manifest_sha256": cohort["manifest_sha256"],
        "base_checkpoint_sha256": binding["checkpoint_sha256"],  # type: ignore[dict-item]
        "base_checkpoint_evidence_sha256": binding["evidence_sha256"],  # type: ignore[dict-item]
        "scoring_plan_sha256": plan_sha256,
        **dict(hashes),
    }


def _cohort_manifest_sha256(condition: Mapping[str, object]) -> str:
    cohort = condition.get("cohort")
    if not isinstance(cohort, Mapping) or not isinstance(cohort.get("manifest_sha256"), str):
        raise ValueError("condition receipt lacks cohort provenance")
    return cohort["manifest_sha256"]


def _condition_scoring_plan(
    condition: Mapping[str, object],
    *,
    trusted_source_root: Path,
) -> ScoringPlan:
    if (
        condition.get("schema_version") != 2
        or condition.get("kind") != "rpc-fewshot-experiment-receipt"
    ):
        raise ValueError("unsupported RPC experiment receipt schema")
    raw = condition.get("scoring_plan")
    if not isinstance(raw, Mapping):
        raise ValueError("condition receipt lacks immutable scoring plan")
    plan = ScoringPlan.from_dict(raw)
    if condition.get("scoring_plan_sha256") != plan.sha256:
        raise ValueError("condition scoring plan SHA-256 mismatch")
    parsed = _parse_nested_condition(condition, "condition")
    if parsed.condition_id not in plan.expected_condition_ids:
        raise ValueError("condition ID is not declared by the scoring plan")
    if parsed.fold not in plan.folds or parsed.support_seed not in plan.support_seeds:
        raise ValueError("condition fold/seed is not declared by the scoring plan")
    scoring = condition.get("scoring")
    if not isinstance(scoring, Mapping) or scoring.get("registered_category_ids") != list(
        plan.registered_category_ids
    ):
        raise ValueError("condition scoring cohort does not match the scoring plan")
    binding = condition.get("fold_base_checkpoint")
    artifact = next(item for item in plan.fold_base_artifacts if item.fold == parsed.fold)
    if (
        not isinstance(binding, Mapping)
        or set(binding) != {"checkpoint_sha256", "evidence_sha256", "fold"}
        or binding.get("fold") != parsed.fold
        or binding.get("checkpoint_sha256") != artifact.checkpoint_sha256
        or binding.get("evidence_sha256") != artifact.evidence_sha256
    ):
        raise ValueError("condition fold base checkpoint does not match the scoring plan")
    _validate_condition_stage_four_selection(
        condition,
        parsed,
        plan,
        trusted_source_root=trusted_source_root,
    )
    return plan


def _parse_nested_condition(
    receipt: Mapping[str, object], name: str
) -> ExperimentCondition:
    """Treat a condition ID as a digest of every declared condition field."""
    nested = receipt.get(name)
    if not isinstance(nested, Mapping):
        raise ValueError(f"receipt lacks {name}")
    parsed = ExperimentCondition.from_dict(nested)
    if dict(nested) != parsed.to_dict():
        raise ValueError("receipt condition is not canonical")
    return parsed


def _validate_condition_stage_four_selection(
    receipt: Mapping[str, object],
    condition: ExperimentCondition,
    plan: ScoringPlan,
    *,
    trusted_source_root: Path,
) -> None:
    selection_value = receipt.get("stage_four_selection")
    if condition.stage != "locked":
        if selection_value is not None:
            raise ValueError("only locked conditions may bind a Stage-4 selection")
        return
    if not isinstance(selection_value, Mapping):
        raise ValueError("locked condition lacks Stage-4 selection")
    selection = StageFourSelection.from_dict(selection_value)
    cohort = receipt.get("cohort")
    binding = receipt.get("fold_base_checkpoint")
    novel, base = condition_cohort(receipt)
    if (
        not isinstance(cohort, Mapping)
        or not isinstance(cohort.get("manifest_sha256"), str)
        or not isinstance(binding, Mapping)
        or not isinstance(binding.get("checkpoint_sha256"), str)
        or not isinstance(binding.get("evidence_sha256"), str)
    ):
        raise ValueError("locked condition lacks Stage-4 target provenance")
    validate_stage_four_binding_for_locked_target(
        selection,
        _stage_four_receipt_paths(receipt),
        condition=condition,
        cohort_manifest_sha256=cohort["manifest_sha256"],
        novel_category_ids=tuple(sorted(novel)),
        base_category_ids=tuple(sorted(base)),
        scoring_plan=plan,
        base_checkpoint_sha256=binding["checkpoint_sha256"],
        base_checkpoint_evidence_sha256=binding["evidence_sha256"],
        trusted_source_root=trusted_source_root,
    )
    _validate_locked_condition_against_selection(condition, selection)


def _validate_locked_condition_against_selection(
    condition: ExperimentCondition, selection: StageFourSelection
) -> None:
    if (condition.method, condition.selector, condition.fold, condition.support_seed) != (
        selection.method,
        selection.selector,
        selection.fold,
        selection.support_seed,
    ):
        raise ValueError("locked condition does not match its Stage-4 selection")
    if condition.shot_count not in {selection.provisional_minimum_shot_count, 150}:
        raise ValueError("locked condition is not the selected provisional minimum or 150-shot reference")


def _validate_comparable_scoring_plans(candidate: ScoringPlan, reference: ScoringPlan) -> None:
    if (
        candidate.bootstrap_seed != reference.bootstrap_seed
        or candidate.bootstrap_replicates != reference.bootstrap_replicates
        or candidate.folds != reference.folds
        or candidate.support_seeds != reference.support_seeds
        or candidate.cohort_id != reference.cohort_id
        or candidate.registered_category_ids != reference.registered_category_ids
        or candidate.fold_base_artifacts != reference.fold_base_artifacts
    ):
        raise ValueError("candidate/reference scoring plan mismatch")


def _score_receipt_plan(receipt: Mapping[str, object], name: str) -> ScoringPlan:
    value = receipt.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"score receipt lacks {name}")
    return ScoringPlan.from_dict(value)


def _score_receipt_condition(receipt: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = receipt.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"score receipt lacks {name}")
    parsed = ExperimentCondition.from_dict(value)
    if dict(value) != parsed.to_dict():
        raise ValueError("score receipt condition is not canonical")
    return parsed.to_dict()


def _validate_complete_condition_set(
    conditions: tuple[Mapping[str, object], ...], plan: ScoringPlan
) -> None:
    condition_ids = tuple(condition.get("condition_id") for condition in conditions)
    if (
        len(condition_ids) != len(set(condition_ids))
        or set(condition_ids) != set(plan.expected_condition_ids)
    ):
        raise ValueError("aggregate requires the complete declared fold/seed condition IDs")
    coordinates = {
        (condition.get("fold"), condition.get("support_seed")) for condition in conditions
    }
    declared = {(fold, seed) for fold in plan.folds for seed in plan.support_seeds}
    if coordinates != declared:
        raise ValueError("aggregate requires the complete declared fold/seed matrix")


def _validate_paired_condition_axes(
    candidate_conditions: tuple[Mapping[str, object], ...],
    reference_conditions: tuple[Mapping[str, object], ...],
) -> None:
    if len(candidate_conditions) != len(reference_conditions) or any(
        (
            candidate.get("fold"),
            candidate.get("support_seed"),
        )
        != (
            reference.get("fold"),
            reference.get("support_seed"),
        )
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    ):
        raise ValueError("candidate/reference score receipts must have paired fold/seed axes")
    if any(
        (candidate.get("method"), candidate.get("selector"))
        != (reference.get("method"), reference.get("selector"))
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    ):
        raise ValueError("candidate/reference conditions must share method and selector")


def _validated_aggregate_stage(
    candidate_conditions: tuple[Mapping[str, object], ...],
    reference_conditions: tuple[Mapping[str, object], ...],
) -> str:
    """Allow a decision only after the frozen full-system funnel stages."""
    stages = {
        _paired_nested_condition_stage(
            candidate.get("stage"), reference.get("stage")
        )
        for candidate, reference in zip(
            candidate_conditions, reference_conditions, strict=True
        )
    }
    if len(stages) != 1 or not stages <= {"confirmation", "locked"}:
        raise ValueError(
            "aggregate requires candidate/reference conditions in one confirmation or locked stage"
        )
    if any(reference.get("shot_count") != 150 for reference in reference_conditions):
        raise ValueError("aggregate requires an exact 150-shot reference condition")
    return stages.pop()


def _locked_selection_from_value(value: object) -> StageFourSelection:
    if not isinstance(value, Mapping):
        raise ValueError("locked score receipt lacks Stage-4 selection")
    return StageFourSelection.from_dict(value)


def _stage_four_receipt_paths(receipt: Mapping[str, object]) -> tuple[Path, ...]:
    value = receipt.get("stage_four_confirmation_score_receipt_paths")
    if isinstance(value, (str, bytes)):
        raise ValueError("locked condition lacks Stage-4 confirmation score receipt paths")
    try:
        paths = tuple(Path(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("locked condition lacks Stage-4 confirmation score receipt paths") from exc
    if len(paths) not in {3, 4} or any(not str(path) for path in paths):
        raise ValueError("locked condition requires three or four Stage-4 confirmation score receipt paths")
    return paths


def _validate_locked_pair_against_selection(
    candidate_value: Mapping[str, object],
    reference_value: Mapping[str, object],
    selection: StageFourSelection,
) -> None:
    candidate = ExperimentCondition.from_dict(candidate_value)
    reference = ExperimentCondition.from_dict(reference_value)
    _validate_locked_condition_against_selection(candidate, selection)
    _validate_locked_condition_against_selection(reference, selection)
    if candidate.shot_count != selection.provisional_minimum_shot_count:
        raise ValueError("locked candidate is not the Stage-4 provisional minimum")
    if reference.shot_count != 150:
        raise ValueError("locked reference is not the balanced 150-shot condition")


def _validate_locked_condition_receipt_pair(
    candidate_receipt: Mapping[str, object],
    reference_receipt: Mapping[str, object],
    *,
    trusted_source_root: Path,
) -> StageFourSelection:
    candidate = _score_receipt_condition(candidate_receipt, "condition")
    reference = _score_receipt_condition(reference_receipt, "condition")
    candidate_selection = _locked_selection_from_value(
        candidate_receipt.get("stage_four_selection")
    )
    reference_selection = _locked_selection_from_value(
        reference_receipt.get("stage_four_selection")
    )
    if candidate_selection != reference_selection:
        raise ValueError("candidate/reference locked conditions bind different Stage-4 selections")
    candidate_paths = _stage_four_receipt_paths(candidate_receipt)
    reference_paths = _stage_four_receipt_paths(reference_receipt)
    if candidate_paths != reference_paths:
        raise ValueError("candidate/reference locked conditions bind different Stage-4 receipt paths")
    validate_stage_four_confirmation_score_receipts(
        candidate_selection,
        candidate_paths,
        trusted_source_root=trusted_source_root,
    )
    _validate_locked_pair_against_selection(candidate, reference, candidate_selection)
    return candidate_selection


def _validate_locked_score_receipt_pair(
    receipt: Mapping[str, object],
    *,
    trusted_source_root: Path,
) -> StageFourSelection:
    candidate = _score_receipt_condition(receipt, "candidate_condition")
    reference = _score_receipt_condition(receipt, "reference_condition")
    selection = _locked_selection_from_value(receipt.get("stage_four_selection"))
    candidate_plan = _score_receipt_plan(receipt, "candidate_scoring_plan")
    reference_plan = _score_receipt_plan(receipt, "reference_scoring_plan")
    candidate_novel, candidate_base = _score_receipt_cohort(receipt, candidate_plan)
    reference_novel, reference_base = _score_receipt_cohort(receipt, reference_plan)
    if candidate_novel != reference_novel or candidate_base != reference_base:
        raise ValueError("locked score receipt candidate/reference cohort mismatch")
    parsed_candidate = ExperimentCondition.from_dict(candidate)
    parsed_reference = ExperimentCondition.from_dict(reference)
    candidate_provenance = _score_receipt_provenance(
        receipt, "candidate_provenance", candidate, candidate_plan
    )
    reference_provenance = _score_receipt_provenance(
        receipt, "reference_provenance", reference, reference_plan
    )
    if (
        candidate_provenance["cohort_manifest_sha256"]
        != reference_provenance["cohort_manifest_sha256"]
    ):
        raise ValueError("locked score receipt candidate/reference cohort manifest mismatch")
    candidate_checkpoint, candidate_evidence, _ = _score_receipt_base_checkpoint(
        receipt,
        parsed_candidate.fold,
        candidate_plan,
        reference_plan,
        candidate_provenance,
        reference_provenance,
    )
    reference_checkpoint, reference_evidence, _ = _score_receipt_base_checkpoint(
        receipt,
        parsed_reference.fold,
        candidate_plan,
        reference_plan,
        candidate_provenance,
        reference_provenance,
    )
    validate_stage_four_binding_for_locked_target(
        selection,
        _stage_four_receipt_paths(receipt),
        condition=parsed_candidate,
        cohort_manifest_sha256=candidate_provenance["cohort_manifest_sha256"],
        novel_category_ids=tuple(sorted(candidate_novel)),
        base_category_ids=tuple(sorted(candidate_base)),
        scoring_plan=candidate_plan,
        base_checkpoint_sha256=candidate_checkpoint,
        base_checkpoint_evidence_sha256=candidate_evidence,
        trusted_source_root=trusted_source_root,
    )
    validate_stage_four_binding_for_locked_target(
        selection,
        _stage_four_receipt_paths(receipt),
        condition=parsed_reference,
        cohort_manifest_sha256=reference_provenance["cohort_manifest_sha256"],
        novel_category_ids=tuple(sorted(reference_novel)),
        base_category_ids=tuple(sorted(reference_base)),
        scoring_plan=reference_plan,
        base_checkpoint_sha256=reference_checkpoint,
        base_checkpoint_evidence_sha256=reference_evidence,
        trusted_source_root=trusted_source_root,
    )
    _validate_locked_pair_against_selection(candidate, reference, selection)
    return selection


def _validate_comparable_locked_selections(
    selections: tuple[StageFourSelection, ...], plan: ScoringPlan
) -> None:
    """All fold/seed certificates must select the same frozen method and minimum."""
    if not selections:
        raise ValueError("locked aggregate lacks Stage-4 selections")
    coordinates = {(selection.fold, selection.support_seed) for selection in selections}
    if len(coordinates) != len(selections):
        raise ValueError("locked aggregate repeats a Stage-4 selection coordinate")
    if coordinates != {
        (fold, seed) for fold in plan.folds for seed in plan.support_seeds
    }:
        raise ValueError("locked Stage-4 selections do not cover the scoring plan matrix")
    first = selections[0]
    signature = (
        first.method,
        first.selector,
        first.provisional_minimum_shot_count,
        tuple(sorted(item.condition.shot_count for item in first.confirmation_receipts)),
    )
    if any(
        (
            selection.method,
            selection.selector,
            selection.provisional_minimum_shot_count,
            tuple(sorted(item.condition.shot_count for item in selection.confirmation_receipts)),
        )
        != signature
        for selection in selections[1:]
    ):
        raise ValueError("locked aggregate mixes incompatible Stage-4 selections")


def _minimum_rule_inputs_pass(value: object) -> bool:
    if not isinstance(value, Mapping):
        raise ValueError("score receipt lacks minimum-rule inputs")
    required = {
        "registered_coverage",
        "novel_macro_recall_lower_delta",
        "novel_wrong_registered_sku_rate_upper_delta",
        "novel_loss_over_10pp_fraction",
        "candidate_base_macro_final_correct_recall",
        "fold_base_checkpoint_macro_final_correct_recall",
    }
    if set(value) != required:
        raise ValueError("minimum-rule inputs have missing or unrecognized fields")
    numeric: dict[str, float] = {}
    for name in required:
        item = value[name]
        if (
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
        ):
            raise ValueError(f"{name} must be finite")
        numeric[name] = float(item)
    tolerance = 1e-12
    return (
        numeric["registered_coverage"] > 0.0
        and numeric["novel_macro_recall_lower_delta"] >= -0.02 - tolerance
        and numeric["novel_wrong_registered_sku_rate_upper_delta"] <= 0.005 + tolerance
        and numeric["novel_loss_over_10pp_fraction"] <= 0.05 + tolerance
        and (
            numeric["candidate_base_macro_final_correct_recall"]
            - numeric["fold_base_checkpoint_macro_final_correct_recall"]
        )
        >= -0.01 - tolerance
    )


def _category_ids(value: object, name: str) -> set[int]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a nonempty category ID sequence")
    try:
        frozen = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(f"{name} must be a nonempty category ID sequence") from exc
    if (
        not frozen
        or len(set(frozen)) != len(frozen)
        or any(type(item) is not int or item <= 0 for item in frozen)
    ):
        raise ValueError(f"{name} must be a nonempty unique category ID sequence")
    return set(frozen)


def _require_sha256(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _average(values: Iterable[float]) -> float:
    frozen = tuple(float(value) for value in values)
    if not frozen or not all(math.isfinite(value) for value in frozen):
        raise ValueError("aggregate metric inputs must be nonempty and finite")
    return sum(frozen) / len(frozen)


def _aggregate_novel_loss_fraction(
    conditions: Iterable[PairedConditionEvidence],
    candidate_summaries: Iterable[FullSystemSummary],
    reference_summaries: Iterable[FullSystemSummary],
) -> float:
    losses: dict[tuple[int, int], list[float]] = {}
    for condition, candidate, reference in zip(
        conditions,
        candidate_summaries,
        reference_summaries,
        strict=True,
    ):
        for category in condition.novel_category_ids:
            if (
                category not in candidate.per_category_final_correct_recall
                or category not in reference.per_category_final_correct_recall
            ):
                raise ValueError("aggregate summary lacks a declared novel category")
            losses.setdefault((condition.fold, category), []).append(
                reference.per_category_final_correct_recall[category]
                - candidate.per_category_final_correct_recall[category]
            )
    if not losses:
        raise ValueError("aggregate summary lacks novel categories")
    return (
        sum(sum(values) / len(values) > 0.10 for values in losses.values())
        / len(losses)
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--reference-evidence", type=Path)
    parser.add_argument("--condition", type=Path)
    parser.add_argument("--reference-condition", type=Path)
    parser.add_argument("--ground-truth-manifest", type=Path)
    parser.add_argument("--base-checkpoint-evidence", type=Path)
    parser.add_argument("--aggregate-score-receipt", action="append", type=Path)
    parser.add_argument("--aggregate-evidence", action="append", type=Path)
    parser.add_argument("--aggregate-reference-evidence", action="append", type=Path)
    parser.add_argument(
        "--trusted-rpc-root",
        type=Path,
        help="verified RPC 2019 root; required to authenticate locked truth",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise FileExistsError(f"output already exists: {args.output}")
        if args.aggregate_score_receipt:
            if any(
                value is not None
                for value in (
                    args.evidence,
                    args.reference_evidence,
                    args.condition,
                    args.reference_condition,
                    args.base_checkpoint_evidence,
                )
            ):
                raise ValueError("aggregate mode cannot accept single-condition inputs")
            if not args.aggregate_evidence or not args.aggregate_reference_evidence:
                raise ValueError(
                    "aggregate mode requires candidate and reference raw evidence"
                )
            if args.ground_truth_manifest is None:
                raise ValueError("aggregate mode requires locked ground truth")
            if args.trusted_rpc_root is None:
                raise ValueError("aggregate mode requires --trusted-rpc-root")
            aggregate_score_receipts(
                tuple(args.aggregate_score_receipt),
                args.output,
                evidence_paths=tuple(args.aggregate_evidence),
                reference_evidence_paths=tuple(args.aggregate_reference_evidence),
                ground_truth_manifest_path=args.ground_truth_manifest,
                trusted_source_root=args.trusted_rpc_root,
            )
        else:
            if args.aggregate_evidence or args.aggregate_reference_evidence:
                raise ValueError(
                    "aggregate evidence inputs require aggregate score receipts"
                )
            single = (
                args.evidence,
                args.reference_evidence,
                args.condition,
                args.reference_condition,
                args.ground_truth_manifest,
                args.base_checkpoint_evidence,
            )
            if any(value is None for value in single):
                raise ValueError(
                    "single-condition scoring requires evidence, reference evidence, "
                    "condition, reference condition, locked ground truth, and fold "
                    "base checkpoint evidence"
                )
            if args.trusted_rpc_root is None:
                raise ValueError("single-condition scoring requires --trusted-rpc-root")
            score(  # type: ignore[arg-type]
                *single,
                args.output,
                trusted_source_root=args.trusted_rpc_root,
            )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
