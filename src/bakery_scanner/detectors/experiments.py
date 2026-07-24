"""Immutable detector experiment definitions and reproducibility receipts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping

from bakery_scanner.config import ScannerConfig


class ExperimentIntegrationUnavailable(RuntimeError):
    """Raised instead of downloading or silently substituting a trainer."""


@dataclass(frozen=True, slots=True)
class DetectorExperiment:
    name: str
    backend: Literal["dfine", "rtmdet"]
    input_size: Literal[640, 768]
    seed: int
    fold: int

    @property
    def run_id(self) -> str:
        return f"{self.name}-seed{self.seed}-fold{self.fold}"

    def require_training_integration(self) -> None:
        title = "D-FINE-N" if self.backend == "dfine" else "RTMDet-Tiny"
        raise ExperimentIntegrationUnavailable(
            f"{title} training integration is not bundled. Install and pin its upstream trainer, "
            "then record the commit and command in an experiment receipt."
        )


@dataclass(frozen=True, slots=True)
class ExperimentReceipt:
    experiment: DetectorExperiment
    config_hash: str
    fold_hash: str
    upstream_commit: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    checkpoint_hash: str
    prediction_hash: str
    started_at: str
    ended_at: str
    status: Literal["completed", "failed", "unavailable"]

    def to_json_bytes(self) -> bytes:
        payload = asdict(self)
        payload["environment"] = dict(self.environment)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def experiment_matrix(config: ScannerConfig) -> tuple[DetectorExperiment, ...]:
    """Return every required backend/size/seed/fold combination deterministically."""
    variants = tuple(config.detectors.variants)
    required = {("dfine", 640), ("dfine", 768), ("rtmdet", 640), ("rtmdet", 768)}
    actual = {(variant.backend, variant.input_size) for variant in variants}
    if actual != required or len(variants) != 4:
        raise ValueError("detector variants must be exactly D-FINE-N/RTMDet-Tiny at 640 and 768")
    return tuple(
        DetectorExperiment(variant.name, variant.backend, variant.input_size, seed, fold)
        for variant in sorted(variants, key=lambda row: row.name)
        for seed in config.detectors.seeds
        for fold in range(config.dataset.folds)
    )


def write_experiment_receipt(
    experiment: DetectorExperiment,
    *,
    config_bytes: bytes,
    fold_hash: str,
    upstream_commit: str,
    command: tuple[str, ...],
    environment: Mapping[str, str],
    checkpoint_hash: str,
    prediction_hash: str,
    started_at: str,
    ended_at: str,
    status: Literal["completed", "failed", "unavailable"],
    output: Path,
) -> ExperimentReceipt:
    """Persist a canonical receipt atomically; all provenance fields are required."""
    _digest(fold_hash, "fold_hash")
    _digest(checkpoint_hash, "checkpoint_hash")
    _digest(prediction_hash, "prediction_hash")
    if len(upstream_commit) != 40 or any(character not in "0123456789abcdef" for character in upstream_commit):
        raise ValueError("upstream_commit must be a lowercase 40-character git SHA")
    if not command or any(not part for part in command):
        raise ValueError("command must contain non-empty arguments")
    receipt = ExperimentReceipt(
        experiment=experiment,
        config_hash=hashlib.sha256(config_bytes).hexdigest(),
        fold_hash=fold_hash,
        upstream_commit=upstream_commit,
        command=tuple(command),
        environment=tuple(sorted((str(key), str(value)) for key, value in environment.items())),
        checkpoint_hash=checkpoint_hash,
        prediction_hash=prediction_hash,
        started_at=started_at,
        ended_at=ended_at,
        status=status,
    )
    _atomic_write(Path(output), receipt.to_json_bytes())
    return receipt


def _digest(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
