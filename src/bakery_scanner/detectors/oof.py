"""Leakage-safe collection and deterministic selection of detector OOF evidence."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from bakery_scanner.contracts import BreadProposal, SceneKey


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


@dataclass(frozen=True, slots=True)
class DetectorPairSelection:
    primary: str
    secondary: str
    alternatives: tuple[tuple[str, str], ...]


def collect_oof_predictions(runs: Iterable[object], runner_factory: Callable[[object], Iterable[tuple[SceneKey, BreadProposal]]], output: Path) -> OofArtifact:
    """Persist only validation-scene predictions and prove no train scene leaked."""
    rows: list[OofPrediction] = []
    training: dict[str, frozenset[SceneKey]] = {}
    observed_runs: set[str] = set()
    for run in runs:
        experiment = run.experiment  # task boundary deliberately requires a run receipt-like object
        run_id = experiment.run_id
        if run_id in observed_runs:
            raise ValueError(f"duplicate OOF run: {run_id}")
        observed_runs.add(run_id)
        validation = frozenset(run.validation_scenes)
        train = frozenset(run.training_scenes)
        if not validation or validation & train:
            raise ValueError("fold scenes must be non-empty and disjoint")
        training[run_id] = train
        emitted = runner_factory(run)
        if emitted is None:
            raise ValueError(f"missing validation prediction artifact for {run_id}")
        for scene, proposal in emitted:
            if scene in train:
                raise ValueError(f"OOF prediction belongs to training scene for {run_id}")
            if scene not in validation:
                raise ValueError(f"OOF prediction is outside validation scene for {run_id}")
            if proposal.source != experiment.name:
                raise ValueError("proposal source must match experiment name")
            rows.append(OofPrediction(run_id, scene, proposal))
    if not observed_runs:
        raise ValueError("at least one detector run is required")
    ordered = tuple(sorted(rows, key=lambda row: (row.run_id, row.scene, -row.proposal.score, row.proposal.image_id, row.proposal.box)))
    payload = [{"box": [row.proposal.box.x, row.proposal.box.y, row.proposal.box.width, row.proposal.box.height], "image_id": row.proposal.image_id, "run_id": row.run_id, "scene": [row.scene.capture_batch, row.scene.scene_number], "score": row.proposal.score, "source": row.proposal.source} for row in ordered]
    path = Path(output) / "oof_predictions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return OofArtifact(path, ordered, training)


def select_complementary_pair(reports: Iterable[Mapping[str, object]]) -> DetectorPairSelection:
    """Choose a heterogeneous pair using development metrics only, never latency first."""
    rows = tuple(reports)
    if len(rows) < 2:
        raise ValueError("at least two detector reports are required")
    names = [str(row["name"]) for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("detector report names must be unique")
    by_name = {str(row["name"]): row for row in rows}
    candidates = []
    for first, second in combinations(sorted(names), 2):
        left, right = by_name[first], by_name[second]
        if first.startswith("dfine") == second.startswith("dfine"):
            continue
        primary, secondary = (first, second) if first.startswith("dfine") else (second, first)
        score = (
            max(int(left["misses"]), int(right["misses"])),
            int(left["merge_errors"]) + int(right["merge_errors"]),
            int(left["false_proposals"]) + int(right["false_proposals"]),
            int(by_name[primary]["primary_misses"]),
            -min(float(left["sem_exact"]), float(right["sem_exact"])),
            float(left["latency_ms"]) + float(right["latency_ms"]),
            primary,
            secondary,
        )
        candidates.append((score, (primary, secondary)))
    if not candidates:
        raise ValueError("a complementary pair requires one D-FINE and one RTMDet report")
    ordered = tuple(pair for _, pair in sorted(candidates))
    return DetectorPairSelection(ordered[0][0], ordered[0][1], ordered)
