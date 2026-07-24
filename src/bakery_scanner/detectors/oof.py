"""Leakage-safe, complete OOF detector evidence and pair selection."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from bakery_scanner.contracts import Box, BreadProposal, SceneKey
from bakery_scanner.detectors.experiments import DetectorExperiment
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
    for row in artifact.predictions:
        if artifact.experiments_by_run[row.run_id].seed == seed and row.proposal.source in names and row.proposal.score >= thresholds[row.proposal.source]:
            values.setdefault(row.proposal.image_id, []).append(row.proposal.box)
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
