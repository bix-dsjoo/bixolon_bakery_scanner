"""Leakage-safe, complete OOF detector evidence and pair selection."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
from bakery_scanner.detectors.proposal_policy import RAW_SCORE_FLOOR, retain_raw_proposals
from bakery_scanner.evaluation import evaluate_scans


@dataclass(frozen=True, slots=True)
class OofPrediction:
    run_id: str
    scene: SceneKey
    proposal: BreadProposal


@dataclass(frozen=True, slots=True)
class OofArtifact:
    path: Path
    predictions: tuple[OofPrediction, ...]
    training_scenes_by_run: Mapping[str, frozenset[SceneKey]]
    experiments_by_run: Mapping[str, DetectorExperiment]
    run_receipt_hashes: Mapping[str, str]
    prediction_artifact_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PairEvidence:
    primary: str
    secondary: str
    union_misses: int
    union_merge_errors: int
    false_proposals: int
    primary_misses: int
    sem_exact: float
    seed_count: int
    receipt_hashes: tuple[str, ...]
    prediction_artifact_hashes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DetectorPairSelection:
    primary: str
    secondary: str
    evidence: tuple[PairEvidence, ...]

    @property
    def alternatives(self) -> tuple[tuple[str, str], ...]:
        return tuple((row.primary, row.secondary) for row in self.evidence)


def load_complete_oof_artifact(
    *,
    detector_root: Path,
    fold_root: Path,
    staged_root: Path,
    expected_experiments: Iterable[DetectorExperiment],
    config_root: Path | None = None,
) -> OofArtifact:
    """Load only receipts whose held-out predictions are complete and hash-consistent.

    This is deliberately a disk boundary: training writes JSON receipts, while
    selection operates only on revalidated immutable proposal records.  Empty
    prediction arrays are valid; ``processed_validation_image_ids.json`` proves
    that they mean no candidates rather than a skipped image.
    """
    expected_rows = tuple(expected_experiments)
    expected = {row.run_id: row for row in expected_rows}
    if not expected or len(expected) != len(expected_rows):
        raise ValueError("expected detector matrix must be non-empty and unique")
    detector_root, fold_root, staged_root = Path(detector_root), Path(fold_root), Path(staged_root)
    config_root = Path(config_root) if config_root is not None else None
    image_sizes, scenes_by_image = _load_staged_images(staged_root)
    rows: list[OofPrediction] = []
    training: dict[str, frozenset[SceneKey]] = {}
    validation_ids_by_run: dict[str, frozenset[int]] = {}
    receipts: dict[str, str] = {}
    artifacts: dict[str, str] = {}

    for run_id, experiment in sorted(expected.items()):
        run_root = detector_root / run_id
        receipt_path = run_root / "receipt.json"
        prediction_path = run_root / "validation_predictions.json"
        processed_path = run_root / "processed_validation_image_ids.json"
        manifest_path = fold_root / f"fold-{experiment.fold}" / "manifest.json"
        receipt = _read_json_object(receipt_path, "receipt")
        _require_receipt_identity(receipt, experiment)
        _require_file_hash(receipt, "fold_manifest_sha256", manifest_path)
        _require_file_hash(receipt, "prediction_sha256", prediction_path)
        _require_file_hash(receipt, "processed_images_sha256", processed_path)
        if config_root is not None:
            _require_file_hash(receipt, "config_sha256", config_root / f"{run_id}.{_config_extension(experiment)}")

        manifest = _read_json_object(manifest_path, "fold manifest")
        validation_ids = _positive_int_set(manifest.get("validation_image_ids"), "validation_image_ids")
        training_ids = _positive_int_set(manifest.get("training_image_ids"), "training_image_ids")
        if not validation_ids or not training_ids or validation_ids & training_ids:
            raise ValueError("fold image ids must be non-empty and disjoint")
        if not validation_ids <= image_sizes.keys() or not training_ids <= image_sizes.keys():
            raise ValueError("fold image ids must exist in staged annotations")
        validation_scenes = _scene_set(manifest.get("validation_scenes"), "validation_scenes")
        train_scenes = _scene_set(manifest.get("training_scenes"), "training_scenes")
        if not validation_scenes or not train_scenes or validation_scenes & train_scenes:
            raise ValueError("fold scenes must be non-empty and disjoint")
        if {scenes_by_image[item] for item in validation_ids} != validation_scenes:
            raise ValueError("fold validation scenes do not match staged manifest")
        if {scenes_by_image[item] for item in training_ids} != train_scenes:
            raise ValueError("fold training scenes do not match staged manifest")
        processed = _positive_int_set(_read_json_array(processed_path, "processed validation image ids"), "processed validation image ids")
        if processed != validation_ids:
            raise ValueError("processed validation image ids do not exactly match the fold")

        predictions = _read_json_array(prediction_path, "validation predictions")
        training[run_id] = frozenset(train_scenes)
        validation_ids_by_run[run_id] = validation_ids
        receipts[run_id] = _sha256_file(receipt_path)
        artifacts[run_id] = _sha256_file(prediction_path)
        retained_coordinate_identities: set[tuple[int, str, Box]] = set()
        for value in predictions:
            if not isinstance(value, dict):
                raise ValueError("validation prediction must be an object")
            image_id = value.get("image_id")
            if isinstance(image_id, bool) or not isinstance(image_id, int) or image_id not in validation_ids:
                raise ValueError("validation prediction image must belong to the held-out fold")
            bbox = value.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError("validation prediction bbox must be an xywh array")
            width, height = image_sizes[image_id]
            proposal = BreadProposal(
                image_id=image_id,
                source=value.get("source"),
                score=value.get("score"),
                box=Box(*bbox),
                image_width=width,
                image_height=height,
            )
            if proposal.source != experiment.name:
                raise ValueError("proposal source must match experiment name")
            if proposal.score >= RAW_SCORE_FLOOR:
                identity = (proposal.image_id, proposal.source, proposal.box)
                if identity in retained_coordinate_identities:
                    raise ValueError("duplicate canonical prediction coordinates")
                retained_coordinate_identities.add(identity)
            rows.append(OofPrediction(run_id, scenes_by_image[image_id], proposal))

    ordered = tuple(sorted(rows, key=lambda row: (row.run_id, row.scene, -row.proposal.score, row.proposal.image_id, row.proposal.box)))
    _require_global_fold_coverage(expected, validation_ids_by_run, frozenset(image_sizes))
    return OofArtifact(detector_root / "oof_predictions.json", ordered, training, expected, receipts, artifacts)


def collect_oof_predictions(
    runs: Iterable[object],
    runner_factory: Callable[[object], Iterable[tuple[SceneKey, BreadProposal]] | None],
    output: Path,
    *,
    expected_experiments: Iterable[DetectorExperiment],
) -> OofArtifact:
    """Persist a complete expected matrix, rejecting missing, duplicate, or leaked runs."""
    expected = {row.run_id: row for row in expected_experiments}
    if not expected:
        raise ValueError("expected detector matrix must not be empty")
    observed: dict[str, object] = {}
    for run in runs:
        experiment = run.experiment
        if experiment.run_id in observed or experiment.run_id not in expected or expected[experiment.run_id] != experiment:
            raise ValueError("observed runs do not match expected detector matrix")
        observed[experiment.run_id] = run
    if set(observed) != set(expected):
        raise ValueError("observed runs do not match expected detector matrix")

    rows: list[OofPrediction] = []
    training: dict[str, frozenset[SceneKey]] = {}
    experiments: dict[str, DetectorExperiment] = {}
    receipts: dict[str, str] = {}
    artifacts: dict[str, str] = {}
    for run_id, run in sorted(observed.items()):
        experiment = run.experiment
        validation = frozenset(run.validation_scenes)
        train = frozenset(run.training_scenes)
        receipt_hash = _hash(run.receipt_hash, "receipt_hash")
        prediction_hash = _hash(run.prediction_artifact_hash, "prediction_artifact_hash")
        if not validation or validation & train:
            raise ValueError("fold scenes must be non-empty and disjoint")
        emitted = runner_factory(run)
        if emitted is None:
            raise ValueError(f"missing validation prediction artifact for {run_id}")
        training[run_id], experiments[run_id] = train, experiment
        receipts[run_id], artifacts[run_id] = receipt_hash, prediction_hash
        for scene, proposal in emitted:
            if scene in train:
                raise ValueError(f"OOF prediction belongs to training scene for {run_id}")
            if scene not in validation:
                raise ValueError(f"OOF prediction is outside validation scene for {run_id}")
            if proposal.source != experiment.name:
                raise ValueError("proposal source must match experiment name")
            rows.append(OofPrediction(run_id, scene, proposal))
    ordered = tuple(sorted(rows, key=lambda row: (row.run_id, row.scene, -row.proposal.score, row.proposal.image_id, row.proposal.box)))
    payload = {
        "prediction_artifact_hashes": artifacts,
        "predictions": [_prediction_payload(row) for row in ordered],
        "receipt_hashes": receipts,
        "run_ids": sorted(expected),
    }
    path = Path(output) / "oof_predictions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return OofArtifact(path, ordered, training, experiments, receipts, artifacts)


def select_complementary_pair(
    artifact: OofArtifact,
    *,
    ground_truth: Mapping[int, tuple[Box, ...]],
    scenarios: Mapping[int, frozenset[str]],
    score_thresholds: Mapping[str, float],
    latency_ms: Mapping[str, float],
) -> DetectorPairSelection:
    """Rank heterogeneous pairs from their calibrated union OOF predictions."""
    variants = tuple(sorted({row.name for row in artifact.experiments_by_run.values()}))
    evidence: list[tuple[tuple[object, ...], PairEvidence]] = []
    for first, second in combinations(variants, 2):
        if first.startswith("dfine") == second.startswith("dfine"):
            continue
        primary, secondary = (first, second) if first.startswith("dfine") else (second, first)
        _require_variant_settings(primary, score_thresholds, latency_ms)
        _require_variant_settings(secondary, score_thresholds, latency_ms)
        seeds = tuple(sorted({experiment.seed for experiment in artifact.experiments_by_run.values() if experiment.name in {primary, secondary}}))
        if not seeds:
            continue
        # Never pool predictions from independently trained seeds: that would
        # manufacture duplicate boxes and bias the pair toward seed count.
        reports = tuple(
            (evaluate_scans(ground_truth, _predictions_for(artifact, (primary,), score_thresholds, seed), scenarios),
             evaluate_scans(ground_truth, _predictions_for(artifact, (primary, secondary), score_thresholds, seed), scenarios))
            for seed in seeds
        )
        used_runs = tuple(sorted(run_id for run_id, experiment in artifact.experiments_by_run.items() if experiment.name in {primary, secondary}))
        row = PairEvidence(
            primary, secondary, sum(union.misses for _, union in reports), sum(union.merge_errors for _, union in reports),
            sum(union.false_positives + union.duplicates for _, union in reports), sum(primary_report.misses for primary_report, _ in reports),
            sum(union.sem_exact for _, union in reports) / len(reports), len(seeds), tuple(sorted(artifact.run_receipt_hashes[run_id] for run_id in used_runs)),
            tuple(sorted(artifact.prediction_artifact_hashes[run_id] for run_id in used_runs)),
        )
        rank = (row.union_misses, row.union_merge_errors, row.false_proposals, row.primary_misses, -row.sem_exact, latency_ms[primary] + latency_ms[secondary], primary, secondary)
        evidence.append((rank, row))
    if not evidence:
        raise ValueError("a complementary pair requires one D-FINE and one RTMDet artifact")
    ordered = tuple(row for _, row in sorted(evidence, key=lambda row: row[0]))
    return DetectorPairSelection(ordered[0].primary, ordered[0].secondary, ordered)


def _predictions_for(artifact: OofArtifact, names: tuple[str, ...], thresholds: Mapping[str, float], seed: int) -> dict[int, tuple[Box, ...]]:
    values: dict[int, list[Box]] = {}
    raw = retain_raw_proposals(
        row.proposal
        for row in artifact.predictions
        if artifact.experiments_by_run[row.run_id].seed == seed and row.proposal.source in names
    )
    for proposal in raw:
        if proposal.score >= thresholds[proposal.source]:
            values.setdefault(proposal.image_id, []).append(proposal.box)
    return {image_id: tuple(boxes) for image_id, boxes in values.items()}


def _require_variant_settings(name: str, thresholds: Mapping[str, float], latency: Mapping[str, float]) -> None:
    if name not in thresholds or not 0 <= thresholds[name] <= 1 or name not in latency or latency[name] < 0:
        raise ValueError(f"missing calibrated settings for {name}")


def _hash(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _prediction_payload(row: OofPrediction) -> dict[str, object]:
    return {"box": [row.proposal.box.x, row.proposal.box.y, row.proposal.box.width, row.proposal.box.height], "image_id": row.proposal.image_id, "run_id": row.run_id, "scene": [row.scene.capture_batch, row.scene.scene_number], "score": row.proposal.score, "source": row.proposal.source}


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON: {path}") from exc


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_json_array(path: Path, label: str) -> list[object]:
    value = _read_json(path, label)
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"required OOF artifact is missing: {path}") from exc


def _require_file_hash(receipt: Mapping[str, object], field: str, path: Path) -> None:
    expected = _hash(receipt.get(field), field)
    if expected != _sha256_file(path):
        raise ValueError(f"{field} does not match {path.name}")


def _require_receipt_identity(receipt: Mapping[str, object], experiment: DetectorExperiment) -> None:
    required = {"run_id": experiment.run_id, "variant": experiment.name, "seed": experiment.seed, "fold": experiment.fold, "status": "completed"}
    if any(receipt.get(key) != value for key, value in required.items()):
        raise ValueError("receipt identity or completion status does not match expected experiment")


def _positive_int_set(value: object, label: str) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = frozenset(item for item in value if isinstance(item, int) and not isinstance(item, bool) and item > 0)
    if len(result) != len(value):
        raise ValueError(f"{label} must contain unique positive integers")
    return result


def _scene_set(value: object, label: str) -> frozenset[SceneKey]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    try:
        result = frozenset(SceneKey(item["capture_batch"], item["scene_number"]) for item in value if isinstance(item, dict))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain valid scenes") from exc
    if len(result) != len(value):
        raise ValueError(f"{label} must contain unique valid scenes")
    return result


def _load_staged_images(staged_root: Path) -> tuple[dict[int, tuple[int, int]], dict[int, SceneKey]]:
    annotations = _read_json_object(staged_root / "annotations.json", "staged annotations")
    images = annotations.get("images")
    if not isinstance(images, list):
        raise ValueError("staged annotations images must be an array")
    sizes: dict[int, tuple[int, int]] = {}
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("staged image must be an object")
        image_id, width, height = image.get("id"), image.get("width"), image.get("height")
        if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in (image_id, width, height)) or image_id in sizes:
            raise ValueError("staged images must have unique positive ids and sizes")
        sizes[image_id] = (width, height)
    entries = _read_json_array(staged_root / "staged_manifest.json", "staged manifest")
    scenes: dict[int, SceneKey] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("staged manifest entry must be an object")
        image_id, scene = entry.get("image_id"), entry.get("scene")
        if isinstance(image_id, bool) or not isinstance(image_id, int) or image_id not in sizes or not isinstance(scene, dict) or image_id in scenes:
            raise ValueError("staged manifest must map each image to one scene")
        try:
            scenes[image_id] = SceneKey(scene["capture_batch"], scene["scene_number"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("staged manifest contains an invalid scene") from exc
    if set(sizes) != set(scenes):
        raise ValueError("staged annotations and manifest image ids must match")
    return sizes, scenes


def _require_global_fold_coverage(
    experiments: Mapping[str, DetectorExperiment],
    validation_ids_by_run: Mapping[str, frozenset[int]],
    staged_image_ids: frozenset[int],
) -> None:
    groups: dict[tuple[str, int], list[DetectorExperiment]] = {}
    for experiment in experiments.values():
        groups.setdefault((experiment.name, experiment.seed), []).append(experiment)
    for group in groups.values():
        if len(group) == 1:
            continue  # Small unit-test or targeted diagnostic artifact.
        if len(group) != 5 or {row.fold for row in group} != set(range(5)):
            raise ValueError("a multi-fold OOF artifact requires folds 0 through 4")
        folds = tuple(validation_ids_by_run[row.run_id] for row in group)
        if set().union(*folds) != staged_image_ids or sum(len(row) for row in folds) != len(staged_image_ids):
            raise ValueError("five OOF folds must cover each staged image exactly once")


def _config_extension(experiment: DetectorExperiment) -> str:
    if experiment.backend == "dfine":
        return "yml"
    if experiment.backend == "rtmdet":
        return "py"
    raise ValueError(f"unsupported detector backend for OOF config: {experiment.backend}")
