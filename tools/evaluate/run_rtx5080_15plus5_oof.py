"""Coordinate exact fold OOF evidence and publish only compact Git-safe results.

The model/runtime-specific scene executor is deliberately injected into
``execute_exact_folds``.  This module owns the immutable fold union, external
raw-evidence boundary, and the compact acceptance status; it does not invent a
fallback executor when the declared artifacts are unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from bakery_scanner.benchmarking.oof15plus5 import OofEvaluationRow, evaluate_oof


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SPLITS = (
    _REPOSITORY_ROOT / "data" / "splits" / "rtx5080_15plus5_oof_v1"
)
_EXPECTED_FOLDS = frozenset(range(5))
REQUIRED_FOLD_ARTIFACT_ROLES = (
    "code",
    "completeness_evidence",
    "completeness_policy",
    "detector",
    "dinov3_local_bank",
    "dinov3_support",
    "dinov3_weights",
    "fold_policy",
    "preprocess",
    "repvit_checkpoint",
    "repvit_prototype",
    "runtime",
)
_RAW_ROW_KEYS = {
    "scene_id",
    "fold_index",
    "input_sha256",
    "artifact_sha256",
    "predictions",
    "timings_ms",
    "status",
}
_QUALITY_KEYS = (
    "miss_count",
    "duplicate_count",
    "non_target_detection_count",
    "split_count",
    "merge_count",
    "detected_count_mismatch_count",
    "object_order_mismatch_count",
    "wrong_auto_approval_count",
    "accepted_scan_critical_failure_count",
    "scan_error_upper_95",
    "object_error_upper_95",
    "scan_sample_size",
    "object_sample_size",
)
_UTILITY_KEYS = (
    "normal_scan_acceptance",
    "unnecessary_retake",
    "auto_sku_approval_coverage",
    "unknown_rate",
    "unknown_top3_recall",
    "incremental_auto_sku_approval_coverage",
    "counterfactual_completeness_block_rate",
    "counterfactual_expected_case_count",
    "counterfactual_submitted_case_count",
    "missing_required_slices",
    "has_violation",
    "passes",
)
_UTILITY_FLOORS = {
    "normal_scan_acceptance": (0.80, 0.70, "minimum"),
    "unnecessary_retake": (0.20, 0.30, "maximum"),
    "auto_sku_approval_coverage": (0.70, 0.60, "minimum"),
    "unknown_rate": (0.30, 0.40, "maximum"),
}


class ArtifactAdmissionError(ValueError):
    """A declared fold artifact was not the exact admitted regular file."""


@dataclass(frozen=True, slots=True)
class FoldOofResult:
    """One fold's verified evaluator output and declared artifact identities."""

    fold_index: int
    results: tuple[OofEvaluationRow, ...]
    policy_sha256: str
    artifact_sha256: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.fold_index not in _EXPECTED_FOLDS:
            raise ValueError("fold index must be in 0..4")
        if not isinstance(self.results, tuple) or not all(
            isinstance(row, OofEvaluationRow) for row in self.results
        ):
            raise ValueError("fold results must be immutable OofEvaluationRow values")
        if not _is_sha256(self.policy_sha256):
            raise ValueError("fold policy identity must be a lowercase SHA-256")
        _verify_artifact_hashes(self.artifact_sha256)


@dataclass(frozen=True, slots=True)
class FoldExecutionSpec:
    """Exact inputs exposed to one operational fold executor."""

    fold_index: int
    evaluation_scene_ids: tuple[str, ...]
    artifact_sha256: Mapping[str, str]
    policy_sha256: str


def expected_artifact_ids() -> tuple[str, ...]:
    return tuple(
        f"fold-{fold}:{role}"
        for fold in range(5)
        for role in REQUIRED_FOLD_ARTIFACT_ROLES
    )


def load_fold_execution_specs(
    artifact_root: Path,
    *,
    splits: Path = _DEFAULT_SPLITS,
) -> tuple[FoldExecutionSpec, ...]:
    """Verify exact per-fold descriptors and the bytes they declare."""
    unresolved_root = Path(artifact_root)
    if unresolved_root.is_symlink():
        raise ArtifactAdmissionError("OOF artifact root must not be a symlink")
    root = unresolved_root.resolve()
    if not root.is_dir():
        raise ArtifactAdmissionError("OOF artifact root is unavailable")
    specs = []
    scene_ids_by_fold: dict[int, tuple[str, ...]] = {}
    for fold in range(5):
        hashes: dict[str, str] = {}
        fold_root = root / f"fold-{fold}"
        if not fold_root.is_dir() or fold_root.is_symlink():
            raise ArtifactAdmissionError(f"fold-{fold}: artifact directory unavailable")
        for role in REQUIRED_FOLD_ARTIFACT_ROLES:
            artifact_id = f"fold-{fold}:{role}"
            descriptor_path = fold_root / f"{role}.json"
            if descriptor_path.is_symlink():
                raise ArtifactAdmissionError(f"{artifact_id}: descriptor is a symlink")
            try:
                descriptor = _load_json(descriptor_path)
            except ValueError as exc:
                raise ArtifactAdmissionError(
                    f"{artifact_id}: descriptor unavailable or invalid"
                ) from exc
            if set(descriptor) != {
                "schema_version",
                "artifact_id",
                "role",
                "file",
                "bytes",
                "sha256",
            } or (
                descriptor.get("schema_version") != 1
                or descriptor.get("artifact_id") != artifact_id
                or descriptor.get("role") != role
                or type(descriptor.get("bytes")) is not int
                or int(descriptor["bytes"]) < 1
                or not _is_sha256(descriptor.get("sha256"))
            ):
                raise ArtifactAdmissionError(f"{artifact_id}: descriptor contract mismatch")
            relative = descriptor.get("file")
            if (
                not isinstance(relative, str)
                or not relative
                or Path(relative).is_absolute()
                or Path(relative).drive
                or ".." in Path(relative).parts
            ):
                raise ArtifactAdmissionError(f"{artifact_id}: artifact path is invalid")
            unresolved_path = fold_root / relative
            if unresolved_path.is_symlink():
                raise ArtifactAdmissionError(f"{artifact_id}: artifact is a symlink")
            path = unresolved_path.resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise ArtifactAdmissionError(
                    f"{artifact_id}: artifact escapes the declared root"
                ) from exc
            if not path.is_file() or path.is_symlink():
                raise ArtifactAdmissionError(f"{artifact_id}: artifact file unavailable")
            actual_bytes, actual_sha256 = _file_identity(path)
            if (
                descriptor["bytes"] != actual_bytes
                or descriptor["sha256"] != actual_sha256
            ):
                raise ArtifactAdmissionError(f"{artifact_id}: byte identity mismatch")
            hashes[role] = actual_sha256
        split_manifest = _load_json(Path(splits) / f"fold-{fold}.json")
        scene_roles = _mapping(split_manifest.get("scene_ids"), "scene_ids")
        evaluation = _string_tuple(
            scene_roles.get("evaluation"), f"fold-{fold} evaluation scenes"
        )
        scene_ids_by_fold[fold] = evaluation
        specs.append(
            FoldExecutionSpec(
                fold_index=fold,
                evaluation_scene_ids=evaluation,
                artifact_sha256=hashes,
                policy_sha256=hashes["fold_policy"],
            )
        )
    verify_exact_fold_union(scene_ids_by_fold, splits=splits)
    return tuple(specs)


def verify_exact_fold_union(
    scene_ids_by_fold: Mapping[int, Sequence[str]],
    *,
    splits: Path = _DEFAULT_SPLITS,
) -> tuple[str, ...]:
    """Require the exact canonical 299-scene evaluation partition."""
    if set(scene_ids_by_fold) != _EXPECTED_FOLDS:
        raise ValueError("OOF results must contain exactly folds 0..4")
    submitted_count = sum(len(tuple(values)) for values in scene_ids_by_fold.values())
    if submitted_count != 299:
        raise ValueError("OOF results must contain exactly 299 observed scenes")
    split_root = Path(splits)
    inventory = _load_json(split_root / "inventory.json")
    inventory_ids = _string_tuple(inventory.get("scene_ids"), "inventory scene IDs")
    if len(inventory_ids) != 299 or inventory.get("scene_count") != 299:
        raise ValueError("canonical inventory must contain exactly 299 scenes")
    seen: list[str] = []
    for fold in range(5):
        manifest = _load_json(split_root / f"fold-{fold}.json")
        if manifest.get("fold_index") != fold:
            raise ValueError(f"fold-{fold} manifest identity mismatch")
        scene_ids = manifest.get("scene_ids")
        if not isinstance(scene_ids, Mapping):
            raise ValueError(f"fold-{fold} scene roles are invalid")
        expected = _string_tuple(
            scene_ids.get("evaluation"), f"fold-{fold} declared evaluation scenes"
        )
        actual = _string_tuple(
            scene_ids_by_fold[fold], f"fold-{fold} result scene IDs"
        )
        if len(actual) != len(set(actual)):
            raise ValueError("each evaluation scene must appear exactly once")
        if set(actual) != set(expected) or len(actual) != len(expected):
            raise ValueError(
                f"fold-{fold} results do not match declared evaluation scenes"
            )
        seen.extend(actual)
    if len(seen) != 299:
        raise ValueError("OOF results must contain exactly 299 observed scenes")
    if len(set(seen)) != len(seen):
        raise ValueError("each evaluation scene must appear exactly once")
    if set(seen) != set(inventory_ids):
        raise ValueError("OOF evaluation union differs from the inventory identity")
    return inventory_ids


def execute_exact_folds(
    specs: Sequence[FoldExecutionSpec],
    infer_scene: Callable[[FoldExecutionSpec, str], Mapping[str, object]],
    *,
    splits: Path = _DEFAULT_SPLITS,
) -> tuple[Mapping[str, object], ...]:
    """Call the supplied admitted executor once for every declared scene.

    The callback receives only its fold's declared identities.  Its returned
    raw record is validated before it can cross the external evidence boundary.
    """
    by_fold = {spec.fold_index: spec for spec in specs}
    if len(by_fold) != len(specs) or set(by_fold) != _EXPECTED_FOLDS:
        raise ValueError("execution requires exactly one spec for each fold")
    verify_exact_fold_union(
        {fold: spec.evaluation_scene_ids for fold, spec in by_fold.items()},
        splits=splits,
    )
    records = []
    for fold in range(5):
        spec = by_fold[fold]
        _verify_artifact_hashes(spec.artifact_sha256)
        if spec.artifact_sha256["fold_policy"] != spec.policy_sha256:
            raise ValueError("executor policy must be the declared fold policy")
        for scene_id in spec.evaluation_scene_ids:
            record = dict(infer_scene(spec, scene_id))
            _validate_raw_row(record)
            if record["scene_id"] != scene_id or record["fold_index"] != fold:
                raise ValueError("executor returned a scene or fold identity mismatch")
            if record["artifact_sha256"] != dict(spec.artifact_sha256):
                raise ValueError("executor used artifacts other than its declared fold inputs")
            records.append(record)
    return tuple(records)


def build_oof_receipt(
    folds: Sequence[FoldOofResult],
    *,
    splits: Path = _DEFAULT_SPLITS,
    completeness_evidence_root: Path | None = None,
) -> dict[str, object]:
    """Evaluate the exact observed union with fold-specific immutable policy."""
    by_fold = {fold.fold_index: fold for fold in folds}
    if len(by_fold) != len(folds) or set(by_fold) != _EXPECTED_FOLDS:
        raise ValueError("OOF receipt requires exactly one result for each fold")
    observed_ids = {
        fold: tuple(
            row.scene_id for row in result.results if row.evidence_kind == "observed"
        )
        for fold, result in by_fold.items()
    }
    verify_exact_fold_union(observed_ids, splits=splits)
    rows: list[OofEvaluationRow] = []
    policies: dict[int, str] = {}
    for fold in range(5):
        result = by_fold[fold]
        if any(row.fold_index != fold for row in result.results):
            raise ValueError("fold result contains cross-fold evaluation evidence")
        if result.artifact_sha256["fold_policy"] != result.policy_sha256:
            raise ValueError("fold result policy differs from its declared artifact")
        if any(row.fold_policy_sha256 != result.policy_sha256 for row in result.results):
            raise ValueError("evaluation row policy differs from its fold policy")
        for row in result.results:
            verify_row_artifact_binding(row, result.artifact_sha256)
        rows.extend(result.results)
        policies[fold] = result.policy_sha256
    acceptance = evaluate_oof(
        tuple(rows),
        policies,
        completeness_evidence_root=completeness_evidence_root,
    )
    return build_compact_receipt(json.loads(acceptance.to_json_bytes()))


def verify_row_artifact_binding(
    row: object,
    artifact_sha256: Mapping[str, object],
) -> None:
    """Bind every evaluator provenance field to its declared fold artifact."""
    _verify_artifact_hashes(artifact_sha256)
    fields = {
        "code": "code_sha256",
        "detector": "detector_sha256",
        "dinov3_local_bank": "dinov3_local_bank_sha256",
        "dinov3_support": "dinov3_support_sha256",
        "dinov3_weights": "dinov3_weights_sha256",
        "fold_policy": "fold_policy_sha256",
        "preprocess": "preprocess_sha256",
        "repvit_checkpoint": "repvit_checkpoint_sha256",
        "repvit_prototype": "repvit_prototype_sha256",
        "runtime": "runtime_sha256",
        "completeness_evidence": "completeness_evidence_index_sha256",
    }
    for role, field in fields.items():
        if getattr(row, field, None) != artifact_sha256[role]:
            raise ValueError(f"evaluation row does not bind declared {role} artifact")
    if getattr(row, "evidence_kind", None) == "observed":
        source = getattr(row, "counterfactual_source_evidence", None)
        if (
            source is None
            or getattr(source, "completeness_policy_artifact_sha256", None)
            != artifact_sha256["completeness_policy"]
        ):
            raise ValueError(
                "evaluation row does not bind declared completeness_policy artifact"
            )


def select_status(
    *,
    wrong_auto_approval_count: int,
    accepted_scan_critical_failure_count: int,
    utility_passed: bool,
    top3_passed: bool,
) -> str:
    if (
        type(wrong_auto_approval_count) is not int
        or wrong_auto_approval_count < 0
        or type(accepted_scan_critical_failure_count) is not int
        or accepted_scan_critical_failure_count < 0
        or type(utility_passed) is not bool
        or type(top3_passed) is not bool
    ):
        raise ValueError("acceptance status inputs are invalid")
    if wrong_auto_approval_count or accepted_scan_critical_failure_count:
        return "quality-rejected"
    if not utility_passed:
        return "utility-rejected"
    if not top3_passed:
        return "quality-rejected"
    return "quality-passed-performance-unverified"


def build_compact_receipt(acceptance: Mapping[str, object]) -> dict[str, object]:
    """Whitelist aggregate fields from a validated Task 6 acceptance receipt."""
    if not isinstance(acceptance, Mapping):
        raise ValueError("OOF acceptance payload must be a mapping")
    quality = _mapping(acceptance.get("quality"), "quality")
    utility = _mapping(acceptance.get("utility"), "utility")
    compact_quality = _whitelist(quality, _QUALITY_KEYS, "quality")
    compact_utility = _whitelist(utility, _UTILITY_KEYS, "utility")
    source_status = acceptance.get("status")
    if source_status == "unverified":
        status = "unverified_quality_evidence"
    elif source_status not in {
        "quality-accepted",
        "quality-rejected",
        "utility-rejected",
    }:
        raise ValueError("Task 6 acceptance status is invalid")
    else:
        top3_passed = _top3_passed(compact_utility["unknown_top3_recall"])
        utility_passed = _utility_without_top3_passed(compact_utility)
        status = select_status(
            wrong_auto_approval_count=int(
                compact_quality["wrong_auto_approval_count"]
            ),
            accepted_scan_critical_failure_count=int(
                compact_quality["accepted_scan_critical_failure_count"]
            ),
            utility_passed=utility_passed,
            top3_passed=top3_passed,
        )
        if source_status == "quality-rejected" and status != "quality-rejected":
            raise ValueError("compact status cannot weaken Task 6 quality rejection")
        if source_status == "utility-rejected" and status == "quality-passed-performance-unverified":
            raise ValueError("compact status cannot weaken Task 6 utility rejection")
    policies = _mapping(acceptance.get("policy_by_fold"), "policy_by_fold")
    seeds = _mapping(acceptance.get("seed_by_fold"), "seed_by_fold")
    if set(policies) != {str(fold) for fold in range(5)} or any(
        not _is_sha256(value) for value in policies.values()
    ):
        raise ValueError("compact receipt requires all five fold policy identities")
    if set(seeds) != {str(fold) for fold in range(5)} or any(
        type(value) is not int for value in seeds.values()
    ):
        raise ValueError("compact receipt requires all five fold seed identities")
    claims = _mapping(
        acceptance.get("quality_claims_by_count"), "quality_claims_by_count"
    )
    if claims != {
        "count_1_2": None,
        "count_3_7": "current_oof_evidence",
        "count_8_plus": None,
    }:
        raise ValueError("object-count quality claims differ from the approved policy")
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": status,
        "performance_status": "unverified",
        "scene_count": acceptance.get("scene_count"),
        "object_count": acceptance.get("object_count"),
        "registered_object_total": acceptance.get("registered_object_total"),
        "unknown_count": acceptance.get("unknown_count"),
        "quality": compact_quality,
        "utility": compact_utility,
        "top3": {
            "passed": _top3_passed(compact_utility["unknown_top3_recall"]),
            "rank_hits": _mapping(
                acceptance.get("top3_rank_hits"), "top3_rank_hits"
            ),
        },
        "object_count_slices": _mapping(
            acceptance.get("object_count_slices"), "object_count_slices"
        ),
        "report_slices": _mapping(
            acceptance.get("report_slices"), "report_slices"
        ),
        "quality_claims_by_count": claims,
        "policy_by_fold": dict(sorted(policies.items())),
        "seed_by_fold": dict(sorted(seeds.items())),
        "acceptance_sources": _mapping(
            acceptance.get("acceptance_sources"), "acceptance_sources"
        ),
        "evaluation_input_sha256": acceptance.get("evaluation_input_sha256"),
        "evaluation_row_count": acceptance.get("evaluation_row_count"),
        "completeness_evidence_index_sha256": acceptance.get(
            "completeness_evidence_index_sha256"
        ),
        "sample_size_limit": acceptance.get("sample_size_limit"),
        "non_target_rejection": {"status": "unverified_no_negative_scenes"},
    }
    _reject_private_or_absolute_paths(payload)
    payload["receipt_sha256"] = _canonical_sha256(payload)
    return payload


def write_external_raw_rows(
    output: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    repository_root: Path = _REPOSITORY_ROOT,
) -> dict[str, object]:
    """Write private per-scene evidence outside Git, without overwriting."""
    path = Path(output).resolve()
    repository = Path(repository_root).resolve()
    try:
        path.relative_to(repository)
    except ValueError:
        pass
    else:
        raise ValueError("raw OOF evidence must stay outside the repository")
    checked = tuple(dict(row) for row in rows)
    if not checked:
        raise ValueError("raw OOF evidence must contain at least one row")
    for row in checked:
        _validate_raw_row(row)
    if len({(row["fold_index"], row["scene_id"]) for row in checked}) != len(
        checked
    ):
        raise ValueError("raw OOF evidence contains duplicate scene rows")
    payload = {
        "schema_version": 1,
        "status": "raw_external_verified",
        "rows": list(checked),
    }
    encoded = _canonical_json(payload)
    _write_new_atomic(path, encoded)
    return {
        "status": "raw_external_verified",
        "row_count": len(checked),
        "rows_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def write_unverified_checkpoint(
    compact_output: Path,
    summary: Path,
    *,
    missing_artifact_ids: Sequence[str],
) -> dict[str, object]:
    """Record missing inputs without emitting fabricated evaluation numbers."""
    missing = tuple(missing_artifact_ids)
    allowed = set(expected_artifact_ids())
    if (
        not missing
        or len(set(missing)) != len(missing)
        or any(item not in allowed for item in missing)
    ):
        raise ValueError("missing artifact IDs must be exact declared fold IDs")
    payload: dict[str, object] = {
        "schema_version": 1,
        "status": "unverified_missing_artifacts",
        "missing_artifact_ids": list(missing),
        "performance_status": "unverified",
    }
    payload["receipt_sha256"] = _canonical_sha256(payload)
    _reject_private_or_absolute_paths(payload)
    _write_new_atomic(Path(compact_output), _canonical_json(payload))
    lines = [
        "# RTX 5080 15+5 OOF checkpoint",
        "",
        "Status: `unverified_missing_artifacts`",
        "",
        "No quality metrics or acceptance receipt were produced.",
        "",
        "Missing artifact IDs:",
        "",
        *(f"- `{item}`" for item in missing),
        "",
    ]
    _write_new_atomic(Path(summary), "\n".join(lines).encode("utf-8"))
    return payload


def find_missing_artifact_ids(artifact_root: Path) -> tuple[str, ...]:
    """Return exact missing role IDs without inspecting unrelated files."""
    root = Path(artifact_root)
    missing = []
    for fold in range(5):
        fold_root = root / f"fold-{fold}"
        for role in REQUIRED_FOLD_ARTIFACT_ROLES:
            descriptor = fold_root / f"{role}.json"
            if not descriptor.is_file():
                missing.append(f"fold-{fold}:{role}")
                continue
            try:
                payload = _load_json(descriptor)
                relative = payload.get("file")
                declared = fold_root / str(relative)
            except (TypeError, ValueError):
                continue
            if not isinstance(relative, str) or not declared.is_file():
                missing.append(f"fold-{fold}:{role}")
    return tuple(missing)


def _top3_passed(value: object) -> bool:
    rates = _mapping(value, "unknown_top3_recall")
    overall = rates.get("overall")
    if not _finite_rate(overall) or float(overall) < 0.95:
        return False
    each = [item for name, item in rates.items() if name != "overall"]
    return bool(each) and all(_finite_rate(item) and float(item) >= 0.90 for item in each)


def _utility_without_top3_passed(utility: Mapping[str, object]) -> bool:
    missing = utility.get("missing_required_slices")
    if not isinstance(missing, (list, tuple)) or any(
        not isinstance(item, str) or not item.startswith("unknown_top3_recall:")
        for item in missing
    ):
        return False
    for name, (overall_floor, each_floor, direction) in _UTILITY_FLOORS.items():
        values = _mapping(utility.get(name), name)
        if not values or "overall" not in values:
            return False
        for slice_name, value in values.items():
            if not _finite_rate(value):
                return False
            floor = overall_floor if slice_name == "overall" else each_floor
            if direction == "minimum" and float(value) < floor:
                return False
            if direction == "maximum" and float(value) > floor:
                return False
    incremental = utility.get("incremental_auto_sku_approval_coverage")
    if not _finite_rate(incremental) or float(incremental) < 0.50:
        return False
    counterfactual = _mapping(
        utility.get("counterfactual_completeness_block_rate"),
        "counterfactual completeness block rate",
    )
    if set(counterfactual) != {"missing", "split", "merge", "truncation"}:
        return False
    return all(_finite_rate(value) and float(value) == 1.0 for value in counterfactual.values())


def _validate_raw_row(row: Mapping[str, object]) -> None:
    if set(row) != _RAW_ROW_KEYS:
        raise ValueError("raw OOF row has unknown or missing fields")
    if not isinstance(row["scene_id"], str) or not row["scene_id"]:
        raise ValueError("raw OOF scene identity is invalid")
    if type(row["fold_index"]) is not int or row["fold_index"] not in _EXPECTED_FOLDS:
        raise ValueError("raw OOF fold identity is invalid")
    if not _is_sha256(row["input_sha256"]):
        raise ValueError("raw OOF input identity is invalid")
    _verify_artifact_hashes(_mapping(row["artifact_sha256"], "artifact_sha256"))
    if not isinstance(row["predictions"], list):
        raise ValueError("raw OOF predictions must be a JSON list")
    timings = _mapping(row["timings_ms"], "timings_ms")
    if not timings or any(
        not isinstance(name, str)
        or not name
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
        for name, value in timings.items()
    ):
        raise ValueError("raw OOF timings must be finite non-negative milliseconds")
    if row["status"] != "verified":
        raise ValueError("raw OOF rows must have verified status")


def _verify_artifact_hashes(value: Mapping[str, object]) -> None:
    if set(value) != set(REQUIRED_FOLD_ARTIFACT_ROLES) or any(
        not _is_sha256(item) for item in value.values()
    ):
        raise ValueError("fold artifacts must bind the exact declared SHA-256 roles")


def _whitelist(
    source: Mapping[str, object], keys: Sequence[str], field: str
) -> dict[str, object]:
    missing = set(keys) - set(source)
    if missing:
        raise ValueError(f"{field} aggregate fields are missing: {sorted(missing)}")
    return {key: source[key] for key in keys}


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed mapping")
    return value


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{field} must contain non-empty strings")
    return tuple(value)


def _load_json(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"required OOF manifest is unavailable: {Path(path).name}") from exc
    return _mapping(payload, Path(path).name)


def _reject_private_or_absolute_paths(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in {
                "path",
                "image_path",
                "dataset_path",
                "artifact_path",
                "raw_predictions",
                "raw_payload",
            }:
                raise ValueError("compact receipt contains private/raw fields")
            _reject_private_or_absolute_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_or_absolute_paths(item)
    elif isinstance(value, str):
        if re.search(r"(?:[A-Za-z]:[\\/]|^/|^\\\\)", value):
            raise ValueError("compact receipt contains an absolute/private path")


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _file_identity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _finite_rate(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _write_new_atomic(path: Path, payload: bytes) -> None:
    resolved = Path(path)
    if resolved.exists():
        raise FileExistsError(f"refusing to overwrite OOF evidence: {resolved.name}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    pending = resolved.with_name(f".{resolved.name}.{os.getpid()}.pending")
    try:
        with pending.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, resolved)
    finally:
        if pending.exists():
            pending.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--compact-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    arguments = parser.parse_args(argv)
    missing = find_missing_artifact_ids(arguments.artifact_root)
    if missing:
        payload = write_unverified_checkpoint(
            arguments.compact_output,
            arguments.summary,
            missing_artifact_ids=missing,
        )
        print(json.dumps(payload, sort_keys=True))
        return 2
    try:
        load_fold_execution_specs(arguments.artifact_root, splits=arguments.splits)
    except (ArtifactAdmissionError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "artifact-rejected",
                    "detail": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2
    # There is intentionally no generic/dynamic runtime import here.  The
    # admitted fold-specific executor must call execute_exact_folds and
    # build_oof_receipt in-process; otherwise the evidence remains unverified.
    payload = {
        "schema_version": 1,
        "status": "unverified_missing_admitted_oof_executor",
        "artifact_ids": list(expected_artifact_ids()),
    }
    print(json.dumps(payload, sort_keys=True))
    return 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ArtifactAdmissionError",
    "FoldExecutionSpec",
    "FoldOofResult",
    "REQUIRED_FOLD_ARTIFACT_ROLES",
    "build_compact_receipt",
    "build_oof_receipt",
    "execute_exact_folds",
    "expected_artifact_ids",
    "find_missing_artifact_ids",
    "load_fold_execution_specs",
    "main",
    "select_status",
    "verify_exact_fold_union",
    "verify_row_artifact_binding",
    "write_external_raw_rows",
    "write_unverified_checkpoint",
]
