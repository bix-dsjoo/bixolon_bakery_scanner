"""Deterministic, fail-closed OOF quality receipts for the 15+5 pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

import yaml
from scipy.stats import beta


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HASH_FIELDS = (
    "split_sha256", "source_evidence_sha256", "detector_sha256",
    "repvit_checkpoint_sha256", "repvit_prototype_sha256", "dinov3_weights_sha256",
    "dinov3_support_sha256", "dinov3_local_bank_sha256", "preprocess_sha256",
    "fold_policy_sha256", "code_sha256",
)
_DINO_BINDING_HASH_FIELDS = (
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
_EXPECTED_FOLDS = frozenset(range(5))
_UTILITY_CONFIG = Path("configs/evaluation/rtx5080_15plus5_oof_v1.yaml")


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")
    return float(value)


def _box(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError("box must contain four finite coordinates")
    result = tuple(_finite(item, "box coordinate") for item in value)
    if result[0] < 0 or result[1] < 0 or result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("box must be finite, non-negative, and non-empty")
    return result


@dataclass(frozen=True, slots=True)
class GroundTruthObject:
    object_id: str
    sku_id: int
    box_xyxy: tuple[float, float, float, float]
    object_order: int

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("ground-truth object_id must not be empty")
        if type(self.sku_id) is not int or self.sku_id not in range(1, 21):
            raise ValueError("ground-truth SKU must be active")
        object.__setattr__(self, "box_xyxy", _box(self.box_xyxy))
        if type(self.object_order) is not int or self.object_order < 1:
            raise ValueError("object order must be positive")


@dataclass(frozen=True, slots=True)
class PredictionObject:
    object_id: str
    box_xyxy: tuple[float, float, float, float]
    object_order: int
    state: Literal["auto_approved", "unknown"]
    sku_id: int | None
    top3: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("prediction object_id must not be empty")
        object.__setattr__(self, "box_xyxy", _box(self.box_xyxy))
        if type(self.object_order) is not int or self.object_order < 1:
            raise ValueError("object order must be positive")
        if self.state == "auto_approved":
            if type(self.sku_id) is not int or self.sku_id not in range(1, 21) or self.top3:
                raise ValueError("auto-approved prediction contract is invalid")
        elif self.state == "unknown":
            if self.sku_id is not None or len(self.top3) != 3 or len(set(self.top3)) != 3 or any(type(sku) is not int or sku not in range(1, 21) for sku in self.top3):
                raise ValueError("Unknown requires exactly three unique active-catalog Top-3 candidates")
        else:
            raise ValueError("prediction state must be auto_approved or unknown")


@dataclass(frozen=True, slots=True)
class OofEvaluationRow:
    scene_id: str
    fold_index: int
    role: Literal["evaluation"]
    declared_evaluation_scene_ids: tuple[str, ...]
    state: Literal["accepted_scan", "needs_retake", "no_target_detected"]
    difficulty: Literal["E", "M", "H"]
    image_shape: str
    catalog_segment: Literal["base", "incremental"]
    evidence_kind: Literal["observed", "counterfactual"]
    ground_truth: tuple[GroundTruthObject, ...]
    predictions: tuple[PredictionObject, ...]
    seed: int
    split_sha256: str
    source_evidence_sha256: str
    detector_sha256: str
    repvit_checkpoint_sha256: str
    repvit_prototype_sha256: str
    dinov3_weights_sha256: str
    dinov3_support_sha256: str
    dinov3_local_bank_sha256: str
    preprocess_sha256: str
    fold_policy_sha256: str
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
    final_policy_sha256: str | None = None
    expected_state: Literal["accepted_scan", "needs_retake", "no_target_detected"] | None = None
    evidence_status: Literal["verified"] = "verified"
    source_scene_id: str | None = None
    variant_id: str | None = None

    def __post_init__(self) -> None:
        if self.evidence_kind not in {"observed", "counterfactual"}:
            raise ValueError("evaluation evidence kind is invalid")
        declared_identity = self.scene_id if self.evidence_kind == "observed" else self.source_scene_id
        if not self.scene_id or declared_identity not in self.declared_evaluation_scene_ids:
            raise ValueError("scene must be declared for evaluation")
        if type(self.fold_index) is not int or self.fold_index not in range(5):
            raise ValueError("evaluation fold is invalid")
        if self.role != "evaluation":
            raise ValueError("OOF row must have evaluation role")
        if self.state not in {"accepted_scan", "needs_retake", "no_target_detected"}:
            raise ValueError("scan state is invalid")
        if self.difficulty not in {"E", "M", "H"} or not self.image_shape:
            raise ValueError("reporting slice identity is invalid")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if len({item.object_id for item in self.ground_truth}) != len(self.ground_truth) or len({item.object_id for item in self.predictions}) != len(self.predictions):
            raise ValueError("duplicate scene/object row")
        for field_name in _HASH_FIELDS:
            if not isinstance(getattr(self, field_name), str) or not _SHA256.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256")
        for field_name in _DINO_BINDING_HASH_FIELDS:
            if not isinstance(getattr(self, field_name), str) or not _SHA256.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a lowercase SHA-256")
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
        if self.state == "accepted_scan" and not self.ground_truth:
            raise ValueError("accepted_scan requires at least one target; zero targets are no_target_detected")
        if self.state == "no_target_detected" and (self.ground_truth or self.predictions):
            raise ValueError("no_target_detected requires zero targets and predictions")
        if self.state == "needs_retake" and self.predictions:
            raise ValueError("needs_retake must not carry final predictions or objects")
        if self.expected_state is not None and self.expected_state not in {
            "accepted_scan",
            "needs_retake",
            "no_target_detected",
        }:
            raise ValueError("expected scan state is invalid")
        if self.evidence_status != "verified":
            raise ValueError("OOF evidence must have verified input status")
        if self.evidence_kind == "observed":
            if self.source_scene_id != self.scene_id or self.variant_id is not None:
                raise ValueError("observed evidence must bind its own source scene without a variant")
        elif self.evidence_kind == "counterfactual":
            if (
                not isinstance(self.source_scene_id, str)
                or not self.source_scene_id
                or not isinstance(self.variant_id, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.variant_id)
                or self.scene_id != f"{self.source_scene_id}::counterfactual::{self.variant_id}"
            ):
                raise ValueError("counterfactual evidence requires a distinct deterministic variant identity")
        if self.final_policy_sha256 is not None:
            raise ValueError("final policy/OOF receipt circularity is forbidden")


@dataclass(frozen=True, slots=True)
class OofQuality:
    miss_count: int
    duplicate_count: int
    non_target_detection_count: int
    split_count: int
    merge_count: int
    detected_count_mismatch_count: int
    object_order_mismatch_count: int
    wrong_auto_approval_count: int
    accepted_scan_critical_failure_count: int
    scan_error_upper_95: float
    object_error_upper_95: float
    scan_sample_size: int
    object_sample_size: int


@dataclass(frozen=True, slots=True)
class OofUtility:
    normal_scan_acceptance: Mapping[str, float | None]
    unnecessary_retake: Mapping[str, float | None]
    auto_sku_approval_coverage: Mapping[str, float | None]
    unknown_rate: Mapping[str, float | None]
    unknown_top3_recall: Mapping[str, float | None]
    incremental_auto_sku_approval_coverage: float | None
    counterfactual_completeness_block_rate: float | None
    missing_required_slices: tuple[str, ...]
    has_violation: bool
    passes: bool


@dataclass(frozen=True, slots=True)
class OofAcceptanceReceipt:
    status: Literal["quality-accepted", "quality-rejected", "utility-rejected", "unverified"]
    quality: OofQuality
    utility: OofUtility
    scene_count: int
    object_count: int
    registered_object_total: int
    unknown_count: int
    top3_rank_hits: Mapping[str, int]
    object_count_slices: Mapping[str, int]
    report_slices: Mapping[str, Mapping[str, int]]
    quality_claims_by_count: Mapping[str, str | None]
    policy_by_fold: Mapping[int, str]
    provenance_by_fold: Mapping[int, Mapping[str, Mapping[str, str]]]
    seed_by_fold: Mapping[int, int]
    unverified_reasons: tuple[str, ...] = ()
    sample_size_limit: str = "Exact one-sided 95% bounds describe only the observed OOF sample; they do not establish a 0.1% production-risk claim."
    schema_version: int = 1

    def to_json_bytes(self) -> bytes:
        payload = asdict(self)
        payload["policy_by_fold"] = {str(key): value for key, value in sorted(self.policy_by_fold.items())}
        payload["provenance_by_fold"] = {str(key): value for key, value in sorted(self.provenance_by_fold.items())}
        payload["seed_by_fold"] = {str(key): value for key, value in sorted(self.seed_by_fold.items())}
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True, slots=True)
class FrozenOofReceipt:
    payload: bytes
    sha256: str

    def __post_init__(self) -> None:
        if hashlib.sha256(self.payload).hexdigest() != self.sha256:
            raise ValueError("frozen OOF receipt hash mismatch")


def immutable_fusion_accepts(
    fusion_sku: int,
    dino_local_top1: int,
    repvit_global_top1: int,
    dino_global_top1: int,
    fusion_margin: float,
) -> bool:
    margin = _finite(fusion_margin, "fusion margin")
    return fusion_sku == dino_local_top1 or (
        repvit_global_top1 == fusion_sku
        and dino_global_top1 == fusion_sku
        and margin >= 0.85
    )


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    return intersection / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection)


def _matches(row: OofEvaluationRow) -> tuple[tuple[int, int], ...]:
    candidates = sorted(
        ((-_iou(gt.box_xyxy, pred.box_xyxy), gi, pi)
         for gi, gt in enumerate(row.ground_truth)
         for pi, pred in enumerate(row.predictions)
         if _iou(gt.box_xyxy, pred.box_xyxy) >= 0.50),
    )
    used_gt: set[int] = set()
    used_pred: set[int] = set()
    result = []
    for _, gi, pi in candidates:
        if gi not in used_gt and pi not in used_pred:
            used_gt.add(gi); used_pred.add(pi); result.append((gi, pi))
    return tuple(sorted(result))


def _upper_bound(errors: int, sample_size: int) -> float:
    if sample_size == 0:
        return 1.0
    if errors == sample_size:
        return 1.0
    return float(beta.ppf(0.95, errors + 1, sample_size - errors))


def _count_slice(count: int) -> str:
    if count <= 2:
        return "count_1_2"
    if count <= 7:
        return "count_3_7"
    return "count_8_plus"


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _load_utility_floors() -> Mapping[str, Mapping[str, float]]:
    try:
        value = yaml.safe_load(_UTILITY_CONFIG.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("OOF utility configuration is unavailable") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("OOF utility configuration is invalid")
    floors = value.get("utility_floors")
    required = {
        "normal_scan_acceptance",
        "unnecessary_retake",
        "auto_sku_approval_coverage",
        "unknown_rate",
        "unknown_top3_recall",
    }
    if not isinstance(floors, dict) or set(floors) != required:
        raise ValueError("OOF utility floors are invalid")
    result: dict[str, Mapping[str, float]] = {}
    for name in required:
        row = floors[name]
        if (
            not isinstance(row, dict)
            or set(row) != {"overall", "each"}
            or any(not isinstance(item, (int, float)) or isinstance(item, bool) or not 0.0 <= float(item) <= 1.0 for item in row.values())
        ):
            raise ValueError("OOF utility floor values are invalid")
        result[name] = {key: float(item) for key, item in row.items()}
    return result


def _manifest_missing_identities(rows: tuple[OofEvaluationRow, ...]) -> tuple[str, ...]:
    """Require the exact checked-in evaluation scene identity, not row claims."""
    missing: list[str] = []
    try:
        expected: dict[int, tuple[tuple[str, ...], str, str, int]] = {}
        for fold in range(5):
            value = json.loads((Path.cwd() / "data" / "splits" / "rtx5080_15plus5_oof_v1" / f"fold-{fold}.json").read_text(encoding="utf-8"))
            scenes = value["scene_ids"]["evaluation"]
            expected[fold] = (tuple(scenes), value["manifest_sha256"], value["source_sha256"], value["seed"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return ("canonical_split_manifest_unavailable",)
    observed_by_fold = {
        fold: tuple(sorted(row.scene_id for row in rows if row.fold_index == fold and row.evidence_kind == "observed"))
        for fold in range(5)
    }
    for fold, (scene_ids, manifest_sha, source_sha, seed) in expected.items():
        fold_rows = tuple(row for row in rows if row.fold_index == fold and row.evidence_kind == "observed")
        expected_set = set(scene_ids)
        observed_set = set(observed_by_fold[fold])
        missing.extend(f"missing_observed_scene:{fold}:{scene_id}" for scene_id in sorted(expected_set - observed_set))
        missing.extend(f"unexpected_observed_scene:{fold}:{scene_id}" for scene_id in sorted(observed_set - expected_set))
        for row in fold_rows:
            if row.declared_evaluation_scene_ids != tuple(scene_ids):
                missing.append(f"declared_evaluation_identity_mismatch:{fold}:{row.scene_id}")
            if row.split_sha256 != manifest_sha:
                missing.append(f"split_identity_mismatch:{fold}:{row.scene_id}")
            if row.source_evidence_sha256 != source_sha:
                missing.append(f"source_identity_mismatch:{fold}:{row.scene_id}")
            if row.seed != seed:
                missing.append(f"seed_identity_mismatch:{fold}:{row.scene_id}")
    return tuple(sorted(set(missing)))


def _utility_metrics(
    rows: tuple[OofEvaluationRow, ...],
    matched_by_scene: Mapping[str, tuple[tuple[int, int], ...]],
) -> OofUtility:
    floors = _load_utility_floors()
    slices = ("overall", "E", "M", "H")
    measurements: dict[str, dict[str, float | None]] = {
        name: {} for name in floors
    }
    missing: list[str] = []
    for slice_name in slices:
        subset = tuple(
            row for row in rows
            if row.evidence_kind == "observed" and (slice_name == "overall" or row.difficulty == slice_name)
        )
        expected_normal = tuple(row for row in subset if row.expected_state == "accepted_scan")
        expected_retake = tuple(row for row in subset if row.expected_state in {"needs_retake", "no_target_detected"})
        final_predictions = tuple(pred for row in expected_normal for pred in row.predictions)
        unknown_matches = tuple(
            (row, gi, pi)
            for row in expected_normal
            for gi, pi in matched_by_scene[row.scene_id]
            if row.predictions[pi].state == "unknown"
        )
        normal_acceptance = _rate(sum(row.state == "accepted_scan" for row in expected_normal), len(expected_normal))
        unnecessary_retake = _rate(sum(row.state == "needs_retake" for row in expected_normal), len(expected_normal))
        auto_coverage = _rate(sum(pred.state == "auto_approved" for pred in final_predictions), sum(len(row.ground_truth) for row in expected_normal))
        unknown_rate = _rate(sum(pred.state == "unknown" for pred in final_predictions), len(final_predictions))
        top3_recall = _rate(sum(row.ground_truth[gi].sku_id in row.predictions[pi].top3 for row, gi, pi in unknown_matches), len(unknown_matches))
        values = {
            "normal_scan_acceptance": normal_acceptance,
            "unnecessary_retake": unnecessary_retake,
            "auto_sku_approval_coverage": auto_coverage,
            "unknown_rate": unknown_rate,
            "unknown_top3_recall": top3_recall,
        }
        for name, value in values.items():
            measurements[name][slice_name] = value
            if value is None:
                missing.append(f"{name}:{slice_name}")
        if not expected_retake:
            missing.append(f"retake:{slice_name}")

    incremental = tuple(row for row in rows if row.evidence_kind == "observed" and row.expected_state == "accepted_scan" and row.catalog_segment == "incremental")
    incremental_auto = _rate(
        sum(pred.state == "auto_approved" for row in incremental for pred in row.predictions),
        sum(len(row.ground_truth) for row in incremental),
    )
    if incremental_auto is None:
        missing.append("incremental_auto_sku_approval_coverage")
    counterfactual = tuple(row for row in rows if row.evidence_kind == "counterfactual")
    counterfactual_block = _rate(sum(row.state in {"needs_retake", "no_target_detected"} for row in counterfactual), len(counterfactual))
    if counterfactual_block is None:
        missing.append("counterfactual_completeness_block_rate")

    has_violation = False
    for name, values in measurements.items():
        for slice_name, value in values.items():
            if value is None:
                continue
            floor = floors[name]["overall" if slice_name == "overall" else "each"]
            passed = value >= floor if name in {"normal_scan_acceptance", "auto_sku_approval_coverage", "unknown_top3_recall"} else value <= floor
            has_violation = has_violation or not passed
    if incremental_auto is not None:
        has_violation = has_violation or incremental_auto < 0.50
    if counterfactual_block is not None:
        has_violation = has_violation or counterfactual_block < 1.0
    return OofUtility(
        normal_scan_acceptance=measurements["normal_scan_acceptance"],
        unnecessary_retake=measurements["unnecessary_retake"],
        auto_sku_approval_coverage=measurements["auto_sku_approval_coverage"],
        unknown_rate=measurements["unknown_rate"],
        unknown_top3_recall=measurements["unknown_top3_recall"],
        incremental_auto_sku_approval_coverage=incremental_auto,
        counterfactual_completeness_block_rate=counterfactual_block,
        missing_required_slices=tuple(sorted(set(missing))),
        has_violation=has_violation,
        passes=not missing and not has_violation,
    )


def evaluate_oof(rows: Sequence[OofEvaluationRow], policy_by_fold: Mapping[int, str]) -> OofAcceptanceReceipt:
    checked = tuple(rows)
    if not checked:
        raise ValueError("OOF evaluation rows must not be empty")
    if len({row.scene_id for row in checked}) != len(checked):
        raise ValueError("duplicate evaluation scene/object rows")
    observed_sources = {
        (row.fold_index, row.scene_id)
        for row in checked
        if row.evidence_kind == "observed"
    }
    if any(
        row.evidence_kind == "counterfactual"
        and (row.fold_index, row.source_scene_id) not in observed_sources
        for row in checked
    ):
        raise ValueError("counterfactual source must reference an observed evaluation scene in the same fold")
    for fold, digest in policy_by_fold.items():
        if type(fold) is not int or fold not in range(5) or not _SHA256.fullmatch(digest):
            raise ValueError("fold policy mapping is invalid")
    if any(row.role != "evaluation" for row in checked):
        raise ValueError("OOF evaluation accepts only evaluation role")
    if any(policy_by_fold.get(row.fold_index) != row.fold_policy_sha256 for row in checked):
        raise ValueError("fold policy identity mismatch")
    provenance_by_fold: dict[int, dict[str, dict[str, str]]] = {}
    seed_by_fold: dict[int, int] = {}
    for row in checked:
        identity = {
            field: getattr(row, field)
            for field in (*_HASH_FIELDS, *_DINO_BINDING_HASH_FIELDS)
            if field != "fold_policy_sha256"
        }
        by_kind = provenance_by_fold.setdefault(row.fold_index, {})
        if row.evidence_kind in by_kind and by_kind[row.evidence_kind] != identity:
            raise ValueError("evaluation evidence identity mismatch")
        if row.fold_index in seed_by_fold and seed_by_fold[row.fold_index] != row.seed:
            raise ValueError("evaluation seed mismatch")
        by_kind[row.evidence_kind] = identity
        seed_by_fold[row.fold_index] = row.seed

    counts = {name: 0 for name in ("miss", "duplicate", "non_target", "split", "merge", "count", "order", "wrong")}
    unknown = registered = critical_scenes = 0
    top3 = {"rank_1": 0, "rank_2": 0, "rank_3": 0, "miss": 0}
    object_slices = {"count_1_2": 0, "count_3_7": 0, "count_8_plus": 0}
    report: dict[str, dict[str, int]] = {name: {} for name in ("difficulty", "sku", "object_count", "image_shape", "catalog_segment", "evidence_kind")}
    matched_by_scene: dict[str, tuple[tuple[int, int], ...]] = {}
    for row in sorted(checked, key=lambda item: (item.fold_index, item.scene_id)):
        matches = _matches(row)
        matched_by_scene[row.scene_id] = matches
        matched_gt, matched_pred = {a for a, _ in matches}, {b for _, b in matches}
        miss = len(row.ground_truth) - len(matched_gt)
        extras = [pi for pi in range(len(row.predictions)) if pi not in matched_pred]
        duplicate = sum(any(_iou(row.ground_truth[gi].box_xyxy, row.predictions[pi].box_xyxy) >= 0.5 for gi in range(len(row.ground_truth))) for pi in extras)
        non_target = len(extras) - duplicate
        relations_gt = [sum(_iou(gt.box_xyxy, pred.box_xyxy) >= 0.5 for pred in row.predictions) for gt in row.ground_truth]
        relations_pred = [sum(_iou(gt.box_xyxy, pred.box_xyxy) >= 0.5 for gt in row.ground_truth) for pred in row.predictions]
        split = sum(value > 1 for value in relations_gt)
        merge = sum(value > 1 for value in relations_pred)
        count_mismatch = int(len(row.ground_truth) != len(row.predictions))
        order_mismatch = sum(row.ground_truth[gi].object_order != row.predictions[pi].object_order for gi, pi in matches)
        wrong = sum(
            row.predictions[pi].state == "auto_approved" and row.predictions[pi].sku_id != row.ground_truth[gi].sku_id
            for gi, pi in matches
        )
        for key, value in (("miss", miss), ("duplicate", duplicate), ("non_target", non_target), ("split", split), ("merge", merge), ("count", count_mismatch), ("order", order_mismatch), ("wrong", wrong)):
            counts[key] += value
        scene_critical = miss + duplicate + non_target + split + merge + count_mismatch + order_mismatch + wrong
        if row.state == "accepted_scan" and scene_critical:
            critical_scenes += 1
        for gi, pi in matches:
            gt, pred = row.ground_truth[gi], row.predictions[pi]
            if pred.state == "unknown":
                try:
                    rank = pred.top3.index(gt.sku_id) + 1
                    top3[f"rank_{rank}"] += 1
                except ValueError:
                    top3["miss"] += 1
        # Outcome aggregation reflects every final prediction, independently of
        # matching; unmatched automatic predictions remain non-target failures.
        unknown += sum(pred.state == "unknown" for pred in row.predictions)
        registered += sum(pred.state == "auto_approved" for pred in row.predictions)
        if row.ground_truth:
            object_slices[_count_slice(len(row.ground_truth))] += 1
        values = {
            "difficulty": row.difficulty,
            "object_count": _count_slice(len(row.ground_truth)),
            "image_shape": row.image_shape,
            "catalog_segment": row.catalog_segment,
            "evidence_kind": row.evidence_kind,
        }
        for category, value in values.items():
            report[category][value] = report[category].get(value, 0) + 1
        for gt in row.ground_truth:
            key = str(gt.sku_id)
            report["sku"][key] = report["sku"].get(key, 0) + 1

    quality = OofQuality(
        miss_count=counts["miss"], duplicate_count=counts["duplicate"],
        non_target_detection_count=counts["non_target"], split_count=counts["split"],
        merge_count=counts["merge"], detected_count_mismatch_count=counts["count"],
        object_order_mismatch_count=counts["order"], wrong_auto_approval_count=counts["wrong"],
        accepted_scan_critical_failure_count=critical_scenes,
        scan_error_upper_95=_upper_bound(critical_scenes, len(checked)),
        object_error_upper_95=_upper_bound(counts["wrong"], sum(len(row.ground_truth) for row in checked)),
        scan_sample_size=len(checked), object_sample_size=sum(len(row.ground_truth) for row in checked),
    )
    utility = _utility_metrics(checked, matched_by_scene)
    manifest_missing = _manifest_missing_identities(checked)
    complete_policy_set = set(policy_by_fold) == _EXPECTED_FOLDS
    if critical_scenes or counts["wrong"]:
        status = "quality-rejected"
    elif manifest_missing or not complete_policy_set or utility.missing_required_slices:
        status = "unverified"
    elif utility.has_violation:
        status = "utility-rejected"
    else:
        status = "quality-accepted"
    return OofAcceptanceReceipt(
        status=status, quality=quality, utility=utility, scene_count=len(checked),
        object_count=sum(len(row.ground_truth) for row in checked),
        registered_object_total=registered, unknown_count=unknown,
        top3_rank_hits=top3, object_count_slices=object_slices, report_slices=report,
        quality_claims_by_count={"count_1_2": None, "count_3_7": "current_oof_evidence", "count_8_plus": None},
        policy_by_fold=dict(policy_by_fold), provenance_by_fold=provenance_by_fold, seed_by_fold=seed_by_fold,
        unverified_reasons=tuple(sorted(
            (*manifest_missing, *utility.missing_required_slices,
             *(f"missing_policy_fold:{fold}" for fold in sorted(_EXPECTED_FOLDS - set(policy_by_fold))),
             *(f"unexpected_policy_fold:{fold}" for fold in sorted(set(policy_by_fold) - _EXPECTED_FOLDS)))
        )),
    )


def freeze_oof_receipt(receipt: OofAcceptanceReceipt) -> FrozenOofReceipt:
    if not isinstance(receipt, OofAcceptanceReceipt):
        raise ValueError("only a validated OOF receipt can be frozen")
    if set(receipt.policy_by_fold) != set(range(5)) or set(receipt.provenance_by_fold) != set(range(5)):
        raise ValueError("OOF receipt must contain exactly five folds before freezing")
    if receipt.status != "quality-accepted" or not receipt.utility.passes:
        raise ValueError("only a quality-accepted utility-passing OOF receipt may be frozen")
    payload = receipt.to_json_bytes()
    _reject_private_paths(json.loads(payload.decode("utf-8")))
    return FrozenOofReceipt(payload, hashlib.sha256(payload).hexdigest())


def build_final_development_policy(frozen_receipt: FrozenOofReceipt | None, fusion_policy_bytes: bytes) -> bytes:
    if not isinstance(frozen_receipt, FrozenOofReceipt):
        raise ValueError("a frozen OOF receipt hash is required before final policy creation")
    try:
        frozen_payload = json.loads(frozen_receipt.payload.decode("utf-8"))
        base = json.loads(fusion_policy_bytes)
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("fusion policy must be valid JSON") from exc
    if (
        not isinstance(frozen_payload, dict)
        or frozen_payload.get("schema_version") != 1
        or set(frozen_payload.get("policy_by_fold", {})) != {str(index) for index in range(5)}
        or set(frozen_payload.get("provenance_by_fold", {})) != {str(index) for index in range(5)}
        or frozen_payload.get("status") != "quality-accepted"
        or not isinstance(frozen_payload.get("utility"), dict)
        or frozen_payload.get("utility", {}).get("passes") is not True
        or frozen_payload.get("utility", {}).get("missing_required_slices") != []
        or json.dumps(frozen_payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode() != frozen_receipt.payload
    ):
        raise ValueError("frozen OOF receipt must be a canonical five-fold receipt")
    if (
        not isinstance(base, dict)
        or "frozen_oof_receipt_sha256" in base
        or base.get("schema_version") != 3
        or base.get("decision_rule") != "fusion_local_or_global_consensus_margin_v1"
        or base.get("consensus_margin_floor") != 0.85
    ):
        raise ValueError("fusion policy payload is invalid or circular")
    payload = {
        "schema_version": 1,
        "artifact_type": "rtx5080_15plus5_final_development_policy",
        "frozen_oof_receipt_sha256": frozen_receipt.sha256,
        "fusion_policy": base,
    }
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    _reject_private_paths(payload)
    return encoded


def _reject_private_paths(value: object) -> None:
    if isinstance(value, str):
        if value.startswith(("/", "\\\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
            raise ValueError("receipt/policy must not contain private absolute paths")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _reject_private_paths(key)
            _reject_private_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private_paths(item)
