"""Benchmark synchronized classifier-only inference over verified bread boxes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from itertools import cycle, islice
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image

from bakery_scanner.classification.contracts import (
    DecisionPath,
    ModelProvenance,
    StageTimings,
)
from bakery_scanner.classification.evidence import atomic_write_bytes
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import Box


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_HASH_KEYS = frozenset(
    {
        "calibration_sha256",
        "dinov3_support_sha256",
        "dinov3_weights_sha256",
        "repvit_checkpoint_sha256",
        "repvit_manifest_sha256",
    }
)
_ARTIFACT_ID_KEYS = frozenset({"dinov3", "repvit"})
_MANIFEST_REQUIRED_KEYS = frozenset({"box_xyxy", "image_path", "sample_id"})
_MANIFEST_LABEL_KEYS = frozenset({"registered", "sku_id"})


@dataclass(frozen=True, slots=True)
class BenchmarkInput:
    sample_id: str
    image_path: Path
    box: Box


@dataclass(frozen=True, slots=True)
class BenchmarkAggregate:
    warmup_count: int
    image_count: int
    total_p50_ms: float
    total_p95_ms: float
    repvit_p50_ms: float
    repvit_p95_ms: float
    dinov3_p50_ms: float
    dinov3_p95_ms: float
    dino_invocation_rate: float
    direct_path_count: int
    direct_path_p50_ms: float | None
    direct_path_p95_ms: float | None
    dino_recheck_path_count: int
    dino_recheck_path_p50_ms: float | None
    dino_recheck_path_p95_ms: float | None


def aggregate_benchmark(
    timings: Sequence[StageTimings],
    *,
    warmup_count: int = 0,
    decision_paths: Sequence[DecisionPath] | None = None,
) -> BenchmarkAggregate:
    """Aggregate measured rows after discarding a leading warm-up prefix."""
    if (
        isinstance(warmup_count, bool)
        or not isinstance(warmup_count, int)
        or warmup_count < 0
    ):
        raise ValueError("warmup_count must be a non-negative integer")
    rows = tuple(timings)
    paths = tuple(decision_paths) if decision_paths is not None else None
    if paths is not None and len(paths) != len(rows):
        raise ValueError("decision_paths must align with timings")
    measured = rows[warmup_count:]
    measured_paths = None if paths is None else paths[warmup_count:]
    if not measured:
        raise ValueError("benchmark requires at least one measured timing")

    total_p50, total_p95 = _percentiles(tuple(row.total_ms for row in measured))
    repvit_p50, repvit_p95 = _percentiles(tuple(row.repvit_ms for row in measured))
    invoked = tuple(row.dinov3_ms for row in measured if row.dinov3_ms > 0.0)
    if invoked:
        dinov3_p50, dinov3_p95 = _percentiles(invoked)
    else:
        dinov3_p50 = dinov3_p95 = 0.0
    # Only legacy callers omit paths. Online benchmark calls always supply the
    # classifier decision path, including DINO failures that return Unknown.
    direct_rows = tuple(
        row.total_ms
        for index, row in enumerate(measured)
        if (
            measured_paths[index] is DecisionPath.REPVIT_DIRECT
            if measured_paths
            else row.dinov3_ms == 0.0
        )
    )
    recheck_rows = tuple(
        row.total_ms
        for index, row in enumerate(measured)
        if (
            measured_paths[index] is not DecisionPath.REPVIT_DIRECT
            if measured_paths
            else row.dinov3_ms > 0.0
        )
    )
    direct_p50, direct_p95 = _optional_percentiles(direct_rows)
    recheck_p50, recheck_p95 = _optional_percentiles(recheck_rows)

    return BenchmarkAggregate(
        warmup_count=warmup_count,
        image_count=len(measured),
        total_p50_ms=total_p50,
        total_p95_ms=total_p95,
        repvit_p50_ms=repvit_p50,
        repvit_p95_ms=repvit_p95,
        dinov3_p50_ms=dinov3_p50,
        dinov3_p95_ms=dinov3_p95,
        dino_invocation_rate=len(invoked) / len(measured),
        direct_path_count=len(direct_rows),
        direct_path_p50_ms=direct_p50,
        direct_path_p95_ms=direct_p95,
        dino_recheck_path_count=len(recheck_rows),
        dino_recheck_path_p50_ms=recheck_p50,
        dino_recheck_path_p95_ms=recheck_p95,
    )


def _percentiles(values: Sequence[float]) -> tuple[float, float]:
    result = np.percentile(
        np.asarray(values, dtype=np.float64),
        (50, 95),
        method="linear",
    )
    return (float(result[0]), float(result[1]))


def _optional_percentiles(
    values: Sequence[float],
) -> tuple[float | None, float | None]:
    if not values:
        return (None, None)
    return _percentiles(values)


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    aggregate: BenchmarkAggregate
    device: str
    precision: str
    artifact_hashes: Mapping[str, str]
    artifact_ids: Mapping[str, str]
    manifest_sha256: str

    def __post_init__(self) -> None:
        if not self.device or not self.precision:
            raise ValueError("device and precision must be non-empty")
        if set(self.artifact_hashes) != _ARTIFACT_HASH_KEYS or any(
            not isinstance(value, str) or not _SHA256.fullmatch(value)
            for value in self.artifact_hashes.values()
        ):
            raise ValueError(
                "artifact_hashes must contain exact lowercase SHA-256 values"
            )
        if set(self.artifact_ids) != _ARTIFACT_ID_KEYS or any(
            not isinstance(value, str) or not value
            for value in self.artifact_ids.values()
        ):
            raise ValueError(
                "artifact_ids must contain non-empty repvit and dinov3 IDs"
            )
        if not _SHA256.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 value")
        for value in (
            self.aggregate.total_p50_ms,
            self.aggregate.total_p95_ms,
            self.aggregate.repvit_p50_ms,
            self.aggregate.repvit_p95_ms,
            self.aggregate.dinov3_p50_ms,
            self.aggregate.dinov3_p95_ms,
            self.aggregate.dino_invocation_rate,
        ):
            if not math.isfinite(value):
                raise ValueError("benchmark values must be finite")
        for value in (
            self.aggregate.direct_path_p50_ms,
            self.aggregate.direct_path_p95_ms,
            self.aggregate.dino_recheck_path_p50_ms,
            self.aggregate.dino_recheck_path_p95_ms,
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError("path benchmark values must be finite or null")

    def to_json_bytes(self) -> bytes:
        aggregate = self.aggregate
        payload = {
            "artifacts": {
                **dict(self.artifact_hashes),
                "dinov3_artifact_id": self.artifact_ids["dinov3"],
                "repvit_artifact_id": self.artifact_ids["repvit"],
            },
            "device": self.device,
            "dino_invocation_rate": aggregate.dino_invocation_rate,
            "image_count": aggregate.image_count,
            "latency_ms": {
                "dinov3_invoked": {
                    "p50": aggregate.dinov3_p50_ms,
                    "p95": aggregate.dinov3_p95_ms,
                },
                "repvit": {
                    "p50": aggregate.repvit_p50_ms,
                    "p95": aggregate.repvit_p95_ms,
                },
                "total": {
                    "p50": aggregate.total_p50_ms,
                    "p95": aggregate.total_p95_ms,
                },
            },
            "manifest_sha256": self.manifest_sha256,
            "model_preflight_count": 1,
            "path_latency_ms": {
                "dino_recheck": {
                    "image_count": aggregate.dino_recheck_path_count,
                    "total": {
                        "p50": aggregate.dino_recheck_path_p50_ms,
                        "p95": aggregate.dino_recheck_path_p95_ms,
                    },
                },
                "repvit_direct": {
                    "image_count": aggregate.direct_path_count,
                    "total": {
                        "p50": aggregate.direct_path_p50_ms,
                        "p95": aggregate.direct_path_p95_ms,
                    },
                },
            },
            "precision": self.precision,
            "schema_version": 1,
            "scope": "classifier_only",
            "warmup_count": aggregate.warmup_count,
        }
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


def load_benchmark_manifest(path: Path) -> tuple[BenchmarkInput, ...]:
    """Load verified boxes; optional labels are validated but not scored."""
    manifest_path = Path(path).resolve()
    rows: list[BenchmarkInput] = []
    sample_ids: set[str] = set()
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"line {line_number}: benchmark manifest must be JSONL"
                ) from exc
            mapping = _benchmark_mapping(value, line_number)
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
            box = _parse_box(mapping["box_xyxy"], line_number)
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
                    image.verify()
            except Exception as exc:
                raise ValueError(f"line {line_number}: image is not readable") from exc
            if (
                box.x < 0.0
                or box.y < 0.0
                or box.x + box.width > width
                or box.y + box.height > height
            ):
                raise ValueError(f"line {line_number}: box is outside image bounds")
            rows.append(
                BenchmarkInput(
                    sample_id=sample_id,
                    image_path=image_path,
                    box=box,
                )
            )
    if not rows:
        raise ValueError("benchmark manifest must contain at least one row")
    return tuple(rows)


def _benchmark_mapping(value: Any, line_number: int) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"line {line_number}: benchmark row must be an object")
    keys = frozenset(value)
    if keys == _MANIFEST_REQUIRED_KEYS:
        return value
    if keys != _MANIFEST_REQUIRED_KEYS | _MANIFEST_LABEL_KEYS:
        raise ValueError(
            f"line {line_number}: benchmark row fields must be unlabeled or labeled"
        )
    registered = value["registered"]
    sku_id = value["sku_id"]
    if not isinstance(registered, bool):
        raise ValueError(f"line {line_number}: registered must be boolean")
    if registered:
        if (
            isinstance(sku_id, bool)
            or not isinstance(sku_id, int)
            or not 1 <= sku_id <= 20
        ):
            raise ValueError(
                f"line {line_number}: registered SKU must be between 1 and 20"
            )
    elif sku_id is not None:
        raise ValueError(
            f"line {line_number}: unregistered benchmark row requires null sku_id"
        )
    return value


def _parse_box(value: object, line_number: int) -> Box:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"line {line_number}: box_xyxy must contain four values")
    if any(
        isinstance(coordinate, bool)
        or not isinstance(coordinate, (int, float))
        or not math.isfinite(float(coordinate))
        for coordinate in value
    ):
        raise ValueError(f"line {line_number}: box_xyxy values must be finite")
    x_min, y_min, x_max, y_max = (float(coordinate) for coordinate in value)
    try:
        return Box(x_min, y_min, x_max - x_min, y_max - y_min)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: invalid box_xyxy") from exc


def _infer(pipeline: ClassifierPipeline, item: BenchmarkInput):
    with Image.open(item.image_path) as source:
        image = source.convert("RGB")
    return pipeline.infer(image, item.box)


def _preflight_models(
    pipeline: ClassifierPipeline,
    item: BenchmarkInput,
) -> None:
    with Image.open(item.image_path) as source:
        image = source.convert("RGB")
    pipeline.preflight_models(image, item.box)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_benchmark(
    *,
    config_path: Path,
    manifest_path: Path,
    warmup_count: int,
) -> BenchmarkReport:
    if (
        isinstance(warmup_count, bool)
        or not isinstance(warmup_count, int)
        or warmup_count < 0
    ):
        raise ValueError("warmup must be a non-negative integer")
    inputs = load_benchmark_manifest(manifest_path)
    pipeline = ClassifierPipeline.load(config_path)
    _preflight_models(pipeline, inputs[0])

    warmup_inputs = tuple(islice(cycle(inputs), warmup_count))
    warmup_decisions = tuple(_infer(pipeline, item) for item in warmup_inputs)
    measured_decisions = tuple(_infer(pipeline, item) for item in inputs)
    aggregate = aggregate_benchmark(
        tuple(decision.timings for decision in warmup_decisions)
        + tuple(decision.timings for decision in measured_decisions),
        warmup_count=warmup_count,
        decision_paths=(
            tuple(
                getattr(
                    decision,
                    "decision_path",
                    DecisionPath.REPVIT_DIRECT
                    if decision.timings.dinov3_ms == 0.0
                    else DecisionPath.UNKNOWN_TOP3,
                )
                for decision in warmup_decisions
            )
            + tuple(
                getattr(
                    decision,
                    "decision_path",
                    DecisionPath.REPVIT_DIRECT
                    if decision.timings.dinov3_ms == 0.0
                    else DecisionPath.UNKNOWN_TOP3,
                )
                for decision in measured_decisions
            )
        ),
    )

    provenance = measured_decisions[0].provenance
    identity = _provenance_identity(provenance)
    if any(
        _provenance_identity(decision.provenance) != identity
        for decision in measured_decisions
    ):
        raise ValueError("benchmark provenance changed between measured rows")
    config = pipeline.config
    if (
        provenance.repvit_artifact_id != config.repvit.artifact_id
        or provenance.repvit_sha256 != config.repvit.checkpoint_sha256
        or provenance.repvit_manifest_sha256 != config.repvit.manifest_sha256
        or provenance.dinov3_artifact_id != config.dinov3.artifact_id
        or provenance.dinov3_sha256 != config.dinov3.weights_sha256
        or provenance.dinov3_support_sha256 != config.dinov3.support_sha256
    ):
        raise ValueError("benchmark result provenance does not match configuration")

    return BenchmarkReport(
        aggregate=aggregate,
        device=config.runtime.device,
        precision=config.runtime.precision,
        artifact_hashes={
            "calibration_sha256": provenance.calibration_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
        },
        artifact_ids={
            "dinov3": config.dinov3.artifact_id,
            "repvit": config.repvit.artifact_id,
        },
        manifest_sha256=_sha256_file(manifest_path),
    )


def _provenance_identity(provenance: ModelProvenance) -> tuple[object, ...]:
    return (
        provenance.repvit_artifact_id,
        provenance.repvit_sha256,
        provenance.dinov3_artifact_id,
        provenance.dinov3_sha256,
        provenance.dinov3_support_sha256,
        provenance.calibration_id,
        provenance.calibration_sha256,
        provenance.preprocess_sha256,
        provenance.repvit_manifest_sha256,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark synchronized classifier-only inference; this does not "
            "measure the Detector, Verifier, or full 0.5-second pipeline target."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_benchmark(
        config_path=args.config,
        manifest_path=args.manifest,
        warmup_count=args.warmup,
    )
    atomic_write_bytes(args.output, report.to_json_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
