"""Independent classifier evidence, grouped calibration, and release metrics."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence

import numpy as np
import torch
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import load_canonical_image

from .policy import (
    PolicyCalibration,
    calibrate_dinov3,
    calibrate_repvit,
    fuse_probabilities,
)
from .config import ClassifierConfig, preprocess_sha256


_SKU_IDS = tuple(range(1, 21))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPVIT_ARTIFACT_ID = "repvit_m1_15plus5_v1"
_DINOV3_ARTIFACT_ID = "dinov3_vits16_15plus5_v1"
_MANIFEST_KEYS = frozenset(
    {
        "sample_id",
        "capture_group",
        "image_path",
        "box_xyxy",
        "registered",
        "sku_id",
        "role",
        "scenario_schema_version",
        "scenarios",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "sample_id",
        "capture_group",
        "registered",
        "sku_id",
        "role",
        "image_sha256",
        "repvit_values",
        "dinov3_values",
        "repvit_artifact_id",
        "dinov3_artifact_id",
        "provenance_schema_version",
        "repvit_checkpoint_sha256",
        "repvit_manifest_sha256",
        "dinov3_weights_sha256",
        "dinov3_support_sha256",
        "preprocess_sha256",
        "scenario_schema_version",
        "scenarios",
    }
)

TEMPERATURES = (0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00, 4.00)
ALPHAS = tuple(index / 20 for index in range(21))


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _validate_label(
    *,
    registered: object,
    sku_id: object,
    role: object,
) -> tuple[bool, int | None, Literal["development", "locked_acceptance"]]:
    if type(registered) is not bool:
        raise ValueError("registered must be a boolean")
    if role not in ("development", "locked_acceptance"):
        raise ValueError("role must be development or locked_acceptance")
    if registered:
        if type(sku_id) is not int or sku_id not in _SKU_IDS:
            raise ValueError("registered rows require sku_id between 1 and 20")
        checked_sku: int | None = sku_id
    else:
        if sku_id is not None:
            raise ValueError("unregistered rows require null sku_id")
        checked_sku = None
    return registered, checked_sku, role


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    sample_id: str
    capture_group: str
    image_path: Path
    box: Box
    registered: bool
    sku_id: int | None
    role: Literal["development", "locked_acceptance"]
    image_sha256: str
    scenario_schema_version: int = 1
    scenarios: tuple[str, ...] = ("general",)

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        if not isinstance(self.capture_group, str) or not self.capture_group.strip():
            raise ValueError("capture_group must not be empty")
        if not isinstance(self.image_path, Path) or not self.image_path.is_absolute():
            raise ValueError("image_path must be an absolute Path")
        if not isinstance(self.box, Box):
            raise ValueError("box must be a Box")
        registered, sku_id, role = _validate_label(
            registered=self.registered,
            sku_id=self.sku_id,
            role=self.role,
        )
        object.__setattr__(self, "registered", registered)
        object.__setattr__(self, "sku_id", sku_id)
        object.__setattr__(self, "role", role)
        if not isinstance(self.image_sha256, str) or not _SHA256.fullmatch(
            self.image_sha256
        ):
            raise ValueError("image_sha256 must be a lowercase SHA-256 hash")
        _validate_scenarios(self.scenario_schema_version, self.scenarios)


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    sample_id: str
    capture_group: str
    registered: bool
    sku_id: int | None
    role: Literal["development", "locked_acceptance"]
    image_sha256: str
    repvit_values: tuple[float, ...]
    dinov3_values: tuple[float, ...]
    repvit_artifact_id: str
    dinov3_artifact_id: str
    provenance_schema_version: int = 1
    repvit_checkpoint_sha256: str = "0" * 64
    repvit_manifest_sha256: str = "0" * 64
    dinov3_weights_sha256: str = "0" * 64
    dinov3_support_sha256: str = "0" * 64
    preprocess_sha256: str = "0" * 64
    scenario_schema_version: int = 1
    scenarios: tuple[str, ...] = ("general",)

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        if not isinstance(self.capture_group, str) or not self.capture_group.strip():
            raise ValueError("capture_group must not be empty")
        registered, sku_id, role = _validate_label(
            registered=self.registered,
            sku_id=self.sku_id,
            role=self.role,
        )
        object.__setattr__(self, "registered", registered)
        object.__setattr__(self, "sku_id", sku_id)
        object.__setattr__(self, "role", role)
        if not isinstance(self.image_sha256, str) or not _SHA256.fullmatch(
            self.image_sha256
        ):
            raise ValueError("image_sha256 must be a lowercase SHA-256 hash")
        if self.repvit_artifact_id != _REPVIT_ARTIFACT_ID:
            raise ValueError(f"repvit_artifact_id must be {_REPVIT_ARTIFACT_ID}")
        if self.dinov3_artifact_id != _DINOV3_ARTIFACT_ID:
            raise ValueError(f"dinov3_artifact_id must be {_DINOV3_ARTIFACT_ID}")
        if self.provenance_schema_version != 1:
            raise ValueError("provenance_schema_version must be 1")
        for field in (
            "repvit_checkpoint_sha256",
            "repvit_manifest_sha256",
            "dinov3_weights_sha256",
            "dinov3_support_sha256",
            "preprocess_sha256",
        ):
            if not _SHA256.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be a lowercase SHA-256 hash")
        _validate_scenarios(self.scenario_schema_version, self.scenarios)
        object.__setattr__(
            self,
            "repvit_values",
            _validate_score_vector(
                self.repvit_values,
                "repvit_values",
            ),
        )
        object.__setattr__(
            self,
            "dinov3_values",
            _validate_score_vector(
                self.dinov3_values,
                "dinov3_values",
            ),
        )

    def to_json_bytes(self) -> bytes:
        return _canonical_json_bytes(
            {
                "capture_group": self.capture_group,
                "dinov3_artifact_id": self.dinov3_artifact_id,
                "dinov3_values": list(self.dinov3_values),
                "image_sha256": self.image_sha256,
                "registered": self.registered,
                "repvit_artifact_id": self.repvit_artifact_id,
                "repvit_values": list(self.repvit_values),
                "role": self.role,
                "provenance_schema_version": self.provenance_schema_version,
                "repvit_checkpoint_sha256": self.repvit_checkpoint_sha256,
                "repvit_manifest_sha256": self.repvit_manifest_sha256,
                "dinov3_weights_sha256": self.dinov3_weights_sha256,
                "dinov3_support_sha256": self.dinov3_support_sha256,
                "preprocess_sha256": self.preprocess_sha256,
                "scenario_schema_version": self.scenario_schema_version,
                "scenarios": list(self.scenarios),
                "sample_id": self.sample_id,
                "sku_id": self.sku_id,
            }
        )

    @classmethod
    def from_mapping(cls, value: object) -> "EvidenceRow":
        mapping = _exact_mapping(value, _EVIDENCE_KEYS, "evidence row")
        try:
            return cls(
                sample_id=mapping["sample_id"],
                capture_group=mapping["capture_group"],
                registered=mapping["registered"],
                sku_id=mapping["sku_id"],
                role=mapping["role"],
                image_sha256=mapping["image_sha256"],
                repvit_values=tuple(mapping["repvit_values"]),
                dinov3_values=tuple(mapping["dinov3_values"]),
                repvit_artifact_id=mapping["repvit_artifact_id"],
                dinov3_artifact_id=mapping["dinov3_artifact_id"],
                provenance_schema_version=mapping["provenance_schema_version"],
                repvit_checkpoint_sha256=mapping["repvit_checkpoint_sha256"],
                repvit_manifest_sha256=mapping["repvit_manifest_sha256"],
                dinov3_weights_sha256=mapping["dinov3_weights_sha256"],
                dinov3_support_sha256=mapping["dinov3_support_sha256"],
                preprocess_sha256=mapping["preprocess_sha256"],
                scenario_schema_version=mapping["scenario_schema_version"],
                scenarios=tuple(mapping["scenarios"]),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("evidence row has invalid field types") from exc


@dataclass(frozen=True, slots=True)
class EvaluatedRow:
    sample_id: str
    registered: bool
    sku_id: int | None
    decision: Literal["sku", "unknown"]
    predicted_sku_id: int | None
    top3: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must not be empty")
        registered, sku_id, _ = _validate_label(
            registered=self.registered,
            sku_id=self.sku_id,
            role="development",
        )
        object.__setattr__(self, "registered", registered)
        object.__setattr__(self, "sku_id", sku_id)
        if self.decision == "sku":
            if (
                type(self.predicted_sku_id) is not int
                or self.predicted_sku_id not in _SKU_IDS
            ):
                raise ValueError("sku decision requires predicted_sku_id")
            if self.top3:
                raise ValueError("sku decision must not include top3")
        elif self.decision == "unknown":
            if self.predicted_sku_id is not None:
                raise ValueError("unknown decision must not include predicted_sku_id")
            if (
                len(self.top3) != 3
                or len(set(self.top3)) != 3
                or any(sku not in _SKU_IDS for sku in self.top3)
            ):
                raise ValueError("unknown decision requires three unique Top-3 SKUs")
        else:
            raise ValueError("decision must be sku or unknown")


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    sample_count: int
    registered_count: int
    unregistered_count: int
    auto_count: int
    auto_correct: int
    auto_errors: int
    unknown_count: int
    fallback_top3_denominator: int
    fallback_top3_correct: int
    fallback_top3_misses: int
    assisted_correct: int
    assisted_failures: int
    auto_precision: float | None
    auto_coverage: float | None
    fallback_top3_recall: float | None
    assisted_success: float | None
    failure_sample_ids: tuple[str, ...]

    @property
    def release_passes(self) -> bool:
        return (
            self.auto_precision == 1.0
            and self.fallback_top3_recall == 1.0
            and self.assisted_success == 1.0
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LockedCoverageContract:
    """Versioned minimum coverage for a release-eligible locked evaluation."""

    schema_version: int
    required_scenarios: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_scenarios(self.schema_version, self.required_scenarios)

    @classmethod
    def load(cls, path: Path) -> "LockedCoverageContract":
        content = Path(path).read_bytes()
        try:
            payload = json.loads(
                content.decode("utf-8"), object_pairs_hook=_unique_object
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("locked coverage contract must be canonical JSON") from exc
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "required_scenarios",
        }:
            raise ValueError("locked coverage contract has missing or extra keys")
        if _canonical_json_bytes(payload) != content:
            raise ValueError("locked coverage contract must use canonical JSON")
        return cls(payload["schema_version"], tuple(payload["required_scenarios"]))

    def report(self, rows: Sequence[EvidenceRow]) -> dict[str, object]:
        present_skus = {row.sku_id for row in rows if row.registered}
        present_scenarios = {scenario for row in rows for scenario in row.scenarios}
        missing_skus = [sku for sku in _SKU_IDS if sku not in present_skus]
        missing_scenarios = [
            scenario
            for scenario in self.required_scenarios
            if scenario not in present_scenarios
        ]
        unregistered_count = sum(not row.registered for row in rows)
        return {
            "schema_version": self.schema_version,
            "required_scenarios": list(self.required_scenarios),
            "missing_registered_skus": missing_skus,
            "missing_scenarios": missing_scenarios,
            "unregistered_count": unregistered_count,
            "complete": not missing_skus
            and not missing_scenarios
            and unregistered_count > 0,
        }


def load_evidence_manifest(
    path: Path,
    *,
    training_image_hashes: frozenset[str] | None = None,
) -> tuple[EvidenceInput, ...]:
    """Load labeled inputs and reject identity or training-data leakage."""
    manifest_path = Path(path).resolve()
    if training_image_hashes is None:
        training_image_hashes = _default_training_hashes(manifest_path)
    checked_training_hashes = frozenset(training_image_hashes)
    if any(not _SHA256.fullmatch(value) for value in checked_training_hashes):
        raise ValueError("training image hashes must be lowercase SHA-256 values")

    rows: list[EvidenceInput] = []
    sample_ids: set[str] = set()
    for line_number, value in _read_jsonl(manifest_path):
        mapping = _exact_mapping(value, _MANIFEST_KEYS, "manifest row")
        sample_id = mapping["sample_id"]
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"line {line_number}: sample_id must not be empty")
        if sample_id in sample_ids:
            raise ValueError(f"line {line_number}: duplicate sample_id {sample_id}")
        sample_ids.add(sample_id)

        image_raw = mapping["image_path"]
        if not isinstance(image_raw, str) or not image_raw:
            raise ValueError(f"line {line_number}: image_path must not be empty")
        image_path = (manifest_path.parent / image_raw).resolve()
        if not image_path.is_file():
            raise ValueError(f"line {line_number}: image_path does not exist")
        image_sha256 = sha256_file(image_path)
        if image_sha256 in checked_training_hashes:
            raise ValueError(f"line {line_number}: image is present in RepViT training")

        box = _parse_box(mapping["box_xyxy"], line_number)
        try:
            with Image.open(image_path) as image:
                image.verify()
            frame = load_canonical_image(image_path)
        except Exception as exc:
            raise ValueError(f"line {line_number}: image is not readable") from exc
        try:
            frame.require_box(box)
        except ValueError as exc:
            raise ValueError(
                f"line {line_number}: box is outside canonical visual image bounds"
            ) from exc

        try:
            rows.append(
                EvidenceInput(
                    sample_id=sample_id,
                    capture_group=mapping["capture_group"],
                    image_path=image_path,
                    box=box,
                    registered=mapping["registered"],
                    sku_id=mapping["sku_id"],
                    role=mapping["role"],
                    image_sha256=image_sha256,
                    scenario_schema_version=mapping["scenario_schema_version"],
                    scenarios=tuple(mapping["scenarios"]),
                )
            )
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
    if not rows:
        raise ValueError("evidence manifest must contain at least one row")
    return tuple(rows)


def load_evidence_rows(
    path: Path,
    *,
    training_image_hashes: frozenset[str] | None = None,
) -> tuple[EvidenceRow, ...]:
    evidence_path = Path(path).resolve()
    checked_training_hashes = frozenset(training_image_hashes or ())
    if any(not _SHA256.fullmatch(value) for value in checked_training_hashes):
        raise ValueError("training image hashes must be lowercase SHA-256 values")
    rows: list[EvidenceRow] = []
    sample_ids: set[str] = set()
    for line_number, value in _read_jsonl(evidence_path):
        try:
            row = EvidenceRow.from_mapping(value)
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
        if row.sample_id in sample_ids:
            raise ValueError(f"line {line_number}: duplicate sample_id {row.sample_id}")
        if row.image_sha256 in checked_training_hashes:
            raise ValueError(f"line {line_number}: image is present in RepViT training")
        sample_ids.add(row.sample_id)
        rows.append(row)
    if not rows:
        raise ValueError("evidence file must contain at least one row")
    return tuple(rows)


def load_repvit_training_hashes(
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> frozenset[str]:
    """Load the exact training image identities from a RepViT manifest."""
    training_manifest = Path(path).resolve()
    if expected_sha256 is not None:
        if not _SHA256.fullmatch(expected_sha256):
            raise ValueError("expected RepViT manifest hash must be lowercase SHA-256")
        if sha256_file(training_manifest) != expected_sha256:
            raise ValueError("RepViT training manifest SHA-256 mismatch")
    try:
        payload = json.loads(
            training_manifest.read_text(encoding="utf-8"),
            parse_constant=lambda value: _reject_constant(value),
            object_pairs_hook=_unique_object,
        )
        sources = payload["sources"]
        hashes = frozenset(source["sha256"] for source in sources)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("RepViT training manifest has invalid sources") from exc
    if (
        not isinstance(sources, list)
        or len(hashes) != len(sources)
        or any(
            not isinstance(value, str) or not _SHA256.fullmatch(value)
            for value in hashes
        )
    ):
        raise ValueError("RepViT training manifest has invalid image hashes")
    return hashes


def load_dinov3_support_training_hashes(
    support_path: Path,
    source_manifest_path: Path,
) -> frozenset[str]:
    """Require the canonical source identities embedded by the DINO support build."""
    try:
        support = torch.load(Path(support_path), map_location="cpu", weights_only=True)
        expected = support["source_manifest_sha256"]
    except (OSError, KeyError, RuntimeError, ValueError) as exc:
        raise ValueError(
            "DINOv3 support has no valid source manifest identity"
        ) from exc
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError("DINOv3 support has invalid source_manifest_sha256")
    source_path = Path(source_manifest_path).resolve()
    try:
        content = source_path.read_bytes()
    except OSError as exc:
        raise ValueError("DINOv3 source manifest is required") from exc
    if sha256_file(source_path) != expected:
        raise ValueError("DINOv3 source manifest SHA-256 does not match support")
    try:
        payload = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("DINOv3 source manifest must be canonical JSON") from exc
    if _canonical_json_bytes(payload) != content:
        raise ValueError("DINOv3 source manifest must use canonical JSON")
    try:
        sources = payload["sources"]
        hashes = frozenset(source["sha256"] for source in sources)
    except (KeyError, TypeError) as exc:
        raise ValueError("DINOv3 source manifest has invalid sources") from exc
    if (
        not isinstance(sources, list)
        or len(sources) != len(hashes)
        or any(
            not isinstance(value, str) or not _SHA256.fullmatch(value)
            for value in hashes
        )
    ):
        raise ValueError("DINOv3 source manifest has invalid image hashes")
    return hashes


def validate_evidence_provenance(
    rows: Sequence[EvidenceRow], config: ClassifierConfig
) -> None:
    """Check vectors against both configured digest claims and the exact files."""
    expected = {
        "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
        "repvit_manifest_sha256": config.repvit.manifest_sha256,
        "dinov3_weights_sha256": config.dinov3.weights_sha256,
        "dinov3_support_sha256": config.dinov3.support_sha256,
        "preprocess_sha256": preprocess_sha256(config.preprocess),
    }
    paths = {
        "repvit_checkpoint_sha256": config.repvit.checkpoint,
        "repvit_manifest_sha256": config.repvit.manifest,
        "dinov3_weights_sha256": config.dinov3.weights,
        "dinov3_support_sha256": config.dinov3.support,
    }
    for field, artifact_path in paths.items():
        if sha256_file(artifact_path) != expected[field]:
            raise ValueError(f"configured {field} does not match its SHA-256")
    if any(
        getattr(row, field) != expected_hash
        for row in rows
        for field, expected_hash in expected.items()
    ):
        raise ValueError(
            "evidence model provenance does not match configured artifacts"
        )


def evaluate_rows(rows: Sequence[EvaluatedRow]) -> ClassificationMetrics:
    if not rows:
        raise ValueError("evaluation requires at least one row")
    sample_ids: set[str] = set()
    auto_count = auto_correct = auto_errors = registered_auto_count = 0
    fallback_denominator = fallback_correct = fallback_misses = 0
    assisted_correct = assisted_failures = 0
    registered_count = 0
    failures: list[str] = []
    for row in rows:
        if not isinstance(row, EvaluatedRow):
            raise ValueError("evaluation rows must be EvaluatedRow values")
        if row.sample_id in sample_ids:
            raise ValueError(f"duplicate sample_id {row.sample_id}")
        sample_ids.add(row.sample_id)
        registered_count += int(row.registered)
        if row.decision == "sku":
            auto_count += 1
            registered_auto_count += int(row.registered)
            correct = row.registered and row.predicted_sku_id == row.sku_id
            auto_correct += int(correct)
            auto_errors += int(not correct)
            if correct:
                assisted_correct += 1
            else:
                assisted_failures += 1
                failures.append(row.sample_id)
        elif row.registered:
            fallback_denominator += 1
            correct = row.sku_id in row.top3
            fallback_correct += int(correct)
            fallback_misses += int(not correct)
            if correct:
                assisted_correct += 1
            else:
                assisted_failures += 1
                failures.append(row.sample_id)
        else:
            assisted_correct += 1
    sample_count = len(rows)
    unknown_count = sample_count - auto_count
    return ClassificationMetrics(
        sample_count=sample_count,
        registered_count=registered_count,
        unregistered_count=sample_count - registered_count,
        auto_count=auto_count,
        auto_correct=auto_correct,
        auto_errors=auto_errors,
        unknown_count=unknown_count,
        fallback_top3_denominator=fallback_denominator,
        fallback_top3_correct=fallback_correct,
        fallback_top3_misses=fallback_misses,
        assisted_correct=assisted_correct,
        assisted_failures=assisted_failures,
        auto_precision=None if auto_count == 0 else auto_correct / auto_count,
        auto_coverage=(
            None if registered_count == 0 else registered_auto_count / registered_count
        ),
        fallback_top3_recall=(
            None
            if fallback_denominator == 0
            else fallback_correct / fallback_denominator
        ),
        assisted_success=assisted_correct / sample_count,
        failure_sample_ids=tuple(failures),
    )


def evaluate_policy(
    rows: Sequence[EvidenceRow],
    calibration: PolicyCalibration,
) -> ClassificationMetrics:
    return evaluate_rows(policy_predictions(rows, calibration))


def policy_predictions(
    rows: Sequence[EvidenceRow],
    calibration: PolicyCalibration,
) -> tuple[EvaluatedRow, ...]:
    arrays = _score_arrays(rows, calibration)
    direct = (arrays.repvit_top_probability >= calibration.direct_threshold) & (
        arrays.repvit_margin >= calibration.direct_margin
    )
    recheck_confirmed = (
        ~direct
        & (arrays.repvit_top == arrays.dino_top)
        & (arrays.dino_top_probability >= calibration.dino_threshold)
        & (arrays.fused_margin >= calibration.fused_margin)
    )
    automatic = direct | recheck_confirmed
    predictions: list[EvaluatedRow] = []
    for index, row in enumerate(rows):
        if automatic[index]:
            predicted = (
                int(arrays.repvit_top[index] + 1)
                if direct[index]
                else int(arrays.fused_top[index] + 1)
            )
            predictions.append(
                EvaluatedRow(
                    row.sample_id,
                    row.registered,
                    row.sku_id,
                    "sku",
                    predicted,
                    (),
                )
            )
        else:
            predictions.append(
                EvaluatedRow(
                    row.sample_id,
                    row.registered,
                    row.sku_id,
                    "unknown",
                    None,
                    tuple(int(value + 1) for value in arrays.fused_order[index, :3]),
                )
            )
    return tuple(predictions)


def grouped_development_splits(
    rows: Sequence[EvidenceRow],
    *,
    folds: int = 5,
    seed: int = 20260727,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    _require_development_rows(rows)
    if type(folds) is not int or folds < 2:
        raise ValueError("folds must be an integer of at least 2")
    groups = np.asarray([row.capture_group for row in rows], dtype=object)
    if np.unique(groups).size < folds:
        raise ValueError("capture_group count must be at least folds")
    labels = np.asarray(
        [f"sku:{row.sku_id:02d}" if row.registered else "unregistered" for row in rows],
        dtype=object,
    )
    splitter = StratifiedGroupKFold(
        n_splits=folds,
        shuffle=True,
        random_state=seed,
    )
    placeholder = np.zeros(len(rows), dtype=np.uint8)
    return tuple(
        (training.astype(np.int64), held_out.astype(np.int64))
        for training, held_out in splitter.split(placeholder, labels, groups)
    )


def select_policy(
    rows: Sequence[EvidenceRow],
    *,
    folds: int = 5,
    seed: int = 20260727,
    artifact_hashes: Mapping[str, str] | None = None,
) -> PolicyCalibration:
    """Cross-fit development evidence, then fit one final immutable policy."""
    checked_rows = tuple(rows)
    _validate_evidence_identity(checked_rows)
    splits = grouped_development_splits(checked_rows, folds=folds, seed=seed)
    pooled: list[EvaluatedRow] = []
    for training_indices, held_out_indices in splits:
        training = tuple(checked_rows[index] for index in training_indices)
        held_out = tuple(checked_rows[index] for index in held_out_indices)
        fold_calibration = _fit_policy(
            training, hash_evidence_rows(training), artifact_hashes
        )
        pooled.extend(policy_predictions(held_out, fold_calibration))
    cross_fit_metrics = evaluate_rows(tuple(pooled))
    undefined_metrics = tuple(
        name
        for name in (
            "auto_precision",
            "fallback_top3_recall",
            "assisted_success",
        )
        if getattr(cross_fit_metrics, name) is None
    )
    if undefined_metrics:
        raise ValueError(
            "cross-fit development has undefined applicable release metrics: "
            + ", ".join(undefined_metrics)
        )
    if (
        cross_fit_metrics.auto_errors
        or cross_fit_metrics.fallback_top3_misses
        or cross_fit_metrics.assisted_failures
    ):
        raise ValueError(
            "cross-fit development gates failed: "
            f"auto_errors={cross_fit_metrics.auto_errors}, "
            f"fallback_top3_misses={cross_fit_metrics.fallback_top3_misses}, "
            f"assisted_failures={cross_fit_metrics.assisted_failures}"
        )
    return _fit_policy(checked_rows, hash_evidence_rows(checked_rows), artifact_hashes)


def hash_evidence_rows(rows: Sequence[EvidenceRow]) -> str:
    payload = b"".join(row.to_json_bytes() + b"\n" for row in rows)
    return hashlib.sha256(payload).hexdigest()


def hash_evidence_identities(rows: Sequence[EvidenceRow]) -> str:
    payload = [
        {
            "capture_group": row.capture_group,
            "image_sha256": row.image_sha256,
            "sample_id": row.sample_id,
            "scenario_schema_version": row.scenario_schema_version,
            "scenarios": list(row.scenarios),
        }
        for row in sorted(rows, key=lambda item: item.sample_id)
    ]
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Durably replace one artifact only after its complete payload exists."""
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def canonical_json_bytes(value: object) -> bytes:
    return _canonical_json_bytes(value)


@dataclass(frozen=True, slots=True)
class _ScoreArrays:
    repvit: np.ndarray
    dino: np.ndarray
    fused: np.ndarray
    repvit_top: np.ndarray
    dino_top: np.ndarray
    fused_top: np.ndarray
    repvit_top_probability: np.ndarray
    dino_top_probability: np.ndarray
    repvit_margin: np.ndarray
    fused_margin: np.ndarray
    fused_order: np.ndarray


def _fit_policy(
    rows: tuple[EvidenceRow, ...],
    evidence_sha256: str,
    artifact_hashes: Mapping[str, str] | None = None,
) -> PolicyCalibration:
    registered = np.asarray([row.registered for row in rows], dtype=bool)
    if not registered.any():
        raise ValueError("policy selection requires registered development rows")
    truth = np.asarray(
        [row.sku_id - 1 if row.sku_id is not None else -1 for row in rows],
        dtype=np.int64,
    )
    repvit_raw = np.asarray([row.repvit_values for row in rows], dtype=np.float64)
    dino_raw = np.asarray([row.dinov3_values for row in rows], dtype=np.float64)

    repvit_temperature = min(
        TEMPERATURES,
        key=lambda temperature: (
            _nll(
                _calibrate_matrix(repvit_raw, temperature, repvit=True),
                truth,
                registered,
            ),
            temperature,
        ),
    )
    dinov3_temperature = min(
        TEMPERATURES,
        key=lambda temperature: (
            _nll(
                _calibrate_matrix(dino_raw, temperature, repvit=False),
                truth,
                registered,
            ),
            temperature,
        ),
    )
    repvit = _calibrate_matrix(repvit_raw, repvit_temperature, repvit=True)
    dino = _calibrate_matrix(dino_raw, dinov3_temperature, repvit=False)

    def alpha_key(alpha: float) -> tuple[int, float, float]:
        fused = _fuse_matrix(repvit, dino, alpha)
        order = _rank_matrix(fused)
        top3_misses = int(
            np.sum(registered & ~np.any(order[:, :3] == truth[:, np.newaxis], axis=1))
        )
        return top3_misses, _nll(fused, truth, registered), alpha

    alpha = min(ALPHAS, key=alpha_key)
    fused = _fuse_matrix(repvit, dino, alpha)
    repvit_order = _rank_matrix(repvit)
    dino_order = _rank_matrix(dino)
    fused_order = _rank_matrix(fused)
    repvit_top = repvit_order[:, 0]
    dino_top = dino_order[:, 0]
    fused_top = fused_order[:, 0]
    indices = np.arange(len(rows))
    repvit_top_probability = repvit[indices, repvit_top]
    dino_top_probability = dino[indices, dino_top]
    repvit_margin = (
        repvit[indices, repvit_order[:, 0]] - repvit[indices, repvit_order[:, 1]]
    )
    fused_margin = fused[indices, fused_order[:, 0]] - fused[indices, fused_order[:, 1]]
    direct_pairs = _lossless_thresholds(
        repvit_top_probability,
        repvit_margin,
    )
    # Gates require zero automatic errors.  Among safe masks, accepting more
    # correct rows is always lexicographically better; evaluating unsafe masks
    # cannot improve a valid release policy.  This avoids the former O(n^4)
    # nested threshold enumeration while retaining every safe acceptance mask.
    safe_direct: list[tuple[int, float, float, np.ndarray]] = []
    for direct_threshold, direct_margin in direct_pairs:
        direct = (repvit_top_probability >= direct_threshold) & (repvit_margin >= direct_margin)
        if not np.any(direct & (~registered | (repvit_top != truth))):
            safe_direct.append((int(direct.sum()), direct_threshold, direct_margin, direct))
    if not safe_direct:
        raise ValueError("no zero-error RepViT direct threshold exists")
    _, direct_threshold, direct_margin, direct = max(safe_direct, key=lambda row: (row[0], -row[1], -row[2]))
    recheck = ~direct
    safe_recheck: list[tuple[int, float, float, np.ndarray]] = []
    for dino_threshold, required_fused_margin in _lossless_thresholds(dino_top_probability[recheck], fused_margin[recheck]):
        confirmed = recheck & (repvit_top == dino_top) & (dino_top_probability >= dino_threshold) & (fused_margin >= required_fused_margin)
        if not np.any(confirmed & (~registered | (fused_top != truth))):
            safe_recheck.append((int(confirmed.sum()), dino_threshold, required_fused_margin, confirmed))
    if not safe_recheck:
        raise ValueError("no zero-error DINO recheck threshold exists")
    _, dino_threshold, required_fused_margin, confirmed = max(safe_recheck, key=lambda row: (row[0], -row[1], -row[2]))
    automatic = direct | confirmed
    unknown = ~automatic
    fallback_misses = unknown & registered & ~np.any(fused_order[:, :3] == truth[:, np.newaxis], axis=1)
    automatic_errors = automatic & (~registered | (np.where(direct, repvit_top, fused_top) != truth))
    best = ((int(automatic_errors.sum()), int(fallback_misses.sum()), int(unknown.sum()), direct_threshold, direct_margin, dino_threshold, required_fused_margin), (direct_threshold, direct_margin, dino_threshold, required_fused_margin))
    if best is None:  # pragma: no cover - nonempty rows always yield sentinels
        raise RuntimeError("policy candidate grid is empty")
    direct_threshold, direct_margin, dino_threshold, fused_margin_threshold = best[1]
    hashes = {
        "repvit_checkpoint_sha256": "0" * 64,
        "repvit_manifest_sha256": "0" * 64,
        "dinov3_weights_sha256": "0" * 64,
        "dinov3_support_sha256": "0" * 64,
        "preprocess_sha256": "0" * 64,
    }
    if artifact_hashes is not None:
        if set(artifact_hashes) != set(hashes) or any(
            not isinstance(value, str) or not _SHA256.fullmatch(value)
            for value in artifact_hashes.values()
        ):
            raise ValueError(
                "artifact_hashes must contain exact lowercase SHA-256 values"
            )
        hashes.update(artifact_hashes)
    return PolicyCalibration(
        schema_version=2,
        calibration_id="policy_v2",
        repvit_artifact_id=_REPVIT_ARTIFACT_ID,
        dinov3_artifact_id=_DINOV3_ARTIFACT_ID,
        repvit_temperature=repvit_temperature,
        dinov3_temperature=dinov3_temperature,
        alpha=alpha,
        direct_threshold=direct_threshold,
        direct_margin=direct_margin,
        # Legacy evidence rows do not yet contain direct OOD measurements.
        # Keep their selection semantics until Task 4 makes those fields mandatory.
        direct_max_crop_disagreement=1.0,
        direct_max_prototype_distance=2.0,
        dino_threshold=dino_threshold,
        fused_margin=fused_margin_threshold,
        evidence_sha256=evidence_sha256,
        development_identity_sha256=hash_evidence_identities(rows),
        **hashes,
    )


def _score_arrays(
    rows: Sequence[EvidenceRow],
    calibration: PolicyCalibration,
) -> _ScoreArrays:
    if not rows:
        raise ValueError("policy evaluation requires at least one row")
    for row in rows:
        if row.repvit_artifact_id != calibration.repvit_artifact_id:
            raise ValueError("RepViT evidence artifact does not match calibration")
        if row.dinov3_artifact_id != calibration.dinov3_artifact_id:
            raise ValueError("DINOv3 evidence artifact does not match calibration")
    repvit = _calibrate_matrix(
        np.asarray([row.repvit_values for row in rows], dtype=np.float64),
        calibration.repvit_temperature,
        repvit=True,
    )
    dino = _calibrate_matrix(
        np.asarray([row.dinov3_values for row in rows], dtype=np.float64),
        calibration.dinov3_temperature,
        repvit=False,
    )
    fused = _fuse_matrix(repvit, dino, calibration.alpha)
    repvit_order = _rank_matrix(repvit)
    dino_order = _rank_matrix(dino)
    fused_order = _rank_matrix(fused)
    indices = np.arange(len(rows))
    return _ScoreArrays(
        repvit=repvit,
        dino=dino,
        fused=fused,
        repvit_top=repvit_order[:, 0],
        dino_top=dino_order[:, 0],
        fused_top=fused_order[:, 0],
        repvit_top_probability=repvit[indices, repvit_order[:, 0]],
        dino_top_probability=dino[indices, dino_order[:, 0]],
        repvit_margin=(
            repvit[indices, repvit_order[:, 0]] - repvit[indices, repvit_order[:, 1]]
        ),
        fused_margin=(
            fused[indices, fused_order[:, 0]] - fused[indices, fused_order[:, 1]]
        ),
        fused_order=fused_order,
    )


def _calibrate_matrix(
    values: np.ndarray,
    temperature: float,
    *,
    repvit: bool,
) -> np.ndarray:
    calibrator = calibrate_repvit if repvit else calibrate_dinov3
    return np.asarray(
        [calibrator(row, temperature) for row in values],
        dtype=np.float64,
    )


def _fuse_matrix(
    repvit: np.ndarray,
    dino: np.ndarray,
    alpha: float,
) -> np.ndarray:
    return np.asarray(
        [
            fuse_probabilities(repvit_row, dino_row, alpha)
            for repvit_row, dino_row in zip(repvit, dino, strict=True)
        ],
        dtype=np.float64,
    )


def _rank_matrix(values: np.ndarray) -> np.ndarray:
    sku_order = np.arange(values.shape[1], dtype=np.int64)
    return np.asarray(
        [np.lexsort((sku_order, -row)) for row in values],
        dtype=np.int64,
    )


def _nll(
    probabilities: np.ndarray,
    truth: np.ndarray,
    mask: np.ndarray,
) -> float:
    selected = probabilities[np.flatnonzero(mask), truth[mask]]
    return float(-np.log(np.clip(selected, 1e-12, 1.0)).mean())


def _lossless_thresholds(
    first: np.ndarray,
    second: np.ndarray,
) -> tuple[tuple[float, float], ...]:
    """Retain every distinct >= acceptance mask; never Pareto-prune thresholds.

    A lower threshold is not dominated for safety gates: it may accept a correct
    intermediate point while a higher threshold only appears better geometrically.
    """
    if first.size == 0:
        return ((1.0, 1.0),)
    candidates = sorted(
        {(float(left), float(right)) for left in first for right in second}
        | {(1.0, 1.0)}
    )
    retained: list[tuple[float, float]] = []
    masks: set[bytes] = set()
    for left, right in candidates:
        mask = np.packbits((first >= left) & (second >= right)).tobytes()
        if mask not in masks:
            masks.add(mask)
            retained.append((left, right))
    return tuple(retained)


def _validate_score_vector(
    values: Sequence[float],
    field: str,
) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)) or len(values) != 20:
        raise ValueError(f"{field} must contain exactly 20 values")
    checked = tuple(_finite_float(value, field) for value in values)
    return checked


def _validate_scenarios(version: object, scenarios: object) -> None:
    if type(version) is not int or version != 1:
        raise ValueError("scenario_schema_version must be 1")
    if not isinstance(scenarios, tuple) or not scenarios:
        raise ValueError("scenarios must be a non-empty canonical tuple")
    if any(not isinstance(value, str) or not value.strip() for value in scenarios):
        raise ValueError("scenarios must contain non-empty labels")
    if tuple(sorted(set(scenarios))) != scenarios:
        raise ValueError("scenarios must be unique and canonically ordered")


def _require_development_rows(rows: Sequence[EvidenceRow]) -> None:
    if not rows:
        raise ValueError("development evidence must not be empty")
    if any(not isinstance(row, EvidenceRow) for row in rows):
        raise ValueError("rows must be EvidenceRow values")
    if any(row.role != "development" for row in rows):
        raise ValueError("policy selection accepts development rows only")


def _validate_evidence_identity(rows: Sequence[EvidenceRow]) -> None:
    _require_development_rows(rows)
    sample_ids = [row.sample_id for row in rows]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("duplicate sample_id in evidence")


def _parse_box(value: object, line_number: int) -> Box:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"line {line_number}: box_xyxy must contain four values")
    x_min, y_min, x_max, y_max = (_finite_float(item, "box_xyxy") for item in value)
    try:
        return Box(x_min, y_min, x_max - x_min, y_max - y_min)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: invalid box_xyxy: {exc}") from exc


def _read_jsonl(path: Path) -> Iterable[tuple[int, object]]:
    try:
        handle = Path(path).open("r", encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read JSONL file: {path}") from exc
    with handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"line {line_number}: blank JSONL rows are invalid")
            try:
                yield (
                    line_number,
                    json.loads(
                        line,
                        parse_constant=lambda value: _reject_constant(value),
                        object_pairs_hook=_unique_object,
                    ),
                )
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key}")
        result[key] = value
    return result


def _exact_mapping(
    value: object,
    keys: frozenset[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} keys must be exact")
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is invalid: {value}")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _default_training_hashes(manifest_path: Path) -> frozenset[str]:
    candidates = (
        Path.cwd()
        / "models"
        / "repvit_m1_15plus5_v1"
        / "repvit_m1_15plus5_v1.manifest.json",
        manifest_path.parents[2]
        / "models"
        / "repvit_m1_15plus5_v1"
        / "repvit_m1_15plus5_v1.manifest.json"
        if len(manifest_path.parents) >= 3
        else Path("__missing__"),
    )
    training_manifest = next((path for path in candidates if path.is_file()), None)
    if training_manifest is None:
        raise ValueError(
            "RepViT training manifest is required to check evidence leakage"
        )
    return load_repvit_training_hashes(training_manifest)
