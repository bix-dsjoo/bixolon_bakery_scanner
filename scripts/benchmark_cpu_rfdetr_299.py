"""Reproducible AB/BA CPU benchmark report for the RF-DETR-L pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence
from uuid import uuid4

from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample
from bakery_scanner.e2e.cpu_latency import ImageLatency, PairedPass, compare_paired_latency
from bakery_scanner.e2e.cpu_profile import resolve_batch2_e3_m3_h3
from bakery_scanner.e2e.cpu_regression import ObjectRecord, compare_run
from bakery_scanner.e2e.rfdetr_cpu import summarize_profile_stages


@dataclass(frozen=True, slots=True)
class BenchmarkOptions:
    package_root: Path
    classifier_config: Path
    reference_mode: str
    candidate_mode: str
    sample_profile: Literal["all299", "batch2_e3_m3_h3"]
    intra_op_threads: int | None
    repvit_microbatch: int | str
    dino_microbatch: int | str
    cpu_affinity: str
    compile_models: tuple[str, ...]
    passes: int
    first_order: Literal["AB", "BA"]
    bootstrap_seed: int
    output: Path


@dataclass(frozen=True, slots=True)
class BenchmarkImageRow:
    key: str
    profile: Literal["E", "M", "H"]
    object_count: int
    total_ms: float
    records: tuple[ObjectRecord, ...]
    canonical_ms: float = 0.0
    detector_ms: float = 0.0
    crop_ms: float = 0.0
    repvit_ms: float = 0.0
    dinov3_ms: float = 0.0
    fusion_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class BenchmarkDependencies:
    load_samples: Callable[[Path], tuple[CpuEvaluationSample, ...]]
    detector_metadata: Callable[[Path], dict[str, object]]
    run_mode: Callable[[str, tuple[CpuEvaluationSample, ...], BenchmarkOptions], tuple[BenchmarkImageRow, ...]]


def run_benchmark(options: BenchmarkOptions, dependencies: BenchmarkDependencies | None = None) -> dict[str, object]:
    if options.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {options.output}")
    if dependencies is None:
        dependencies = _live_dependencies()
    all_samples = dependencies.load_samples(options.package_root)
    _validate_full_dataset(all_samples)
    samples = select_benchmark_samples(
        all_samples,
        sample_profile=options.sample_profile,
        package_root=options.package_root,
    )
    metadata = dependencies.detector_metadata(options.package_root)
    staging = options.output.parent / f".{options.output.name}.staging-{uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        passes: list[PairedPass] = []
        reference_records: tuple[ObjectRecord, ...] | None = None
        candidate_records: tuple[ObjectRecord, ...] | None = None
        profile_rows: tuple[BenchmarkImageRow, ...] = ()
        for index in range(options.passes):
            order = options.first_order if index % 2 == 0 else ("BA" if options.first_order == "AB" else "AB")
            first, second = (options.reference_mode, options.candidate_mode) if order == "AB" else (options.candidate_mode, options.reference_mode)
            first_rows = dependencies.run_mode(first, samples, options)
            second_rows = dependencies.run_mode(second, samples, options)
            by_mode = {first: first_rows, second: second_rows}
            reference_rows = by_mode[options.reference_mode]
            candidate_rows = by_mode[options.candidate_mode]
            _validate_rows(reference_rows, samples)
            _validate_rows(candidate_rows, samples)
            if reference_records is None:
                reference_records = tuple(record for row in reference_rows for record in row.records)
                candidate_records = tuple(record for row in candidate_rows for record in row.records)
                profile_rows = reference_rows
            passes.append(PairedPass(index, order, tuple(ImageLatency(row.key, row.total_ms) for row in reference_rows), tuple(ImageLatency(row.key, row.total_ms) for row in candidate_rows)))
        assert reference_records is not None and candidate_records is not None
        quality = compare_run(reference_records, candidate_records)
        latency = compare_paired_latency(passes, seed=options.bootstrap_seed)
        report = {
            "schema_version": 2,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "dataset": {"images": len(samples), "objects": sum(len(sample.targets) for sample in samples)},
            "detector": metadata,
            "artifacts": _artifact_hashes(options.package_root, options.classifier_config, samples),
            "runtime": {"reference_mode": options.reference_mode, "candidate_mode": options.candidate_mode, "intra_op_threads": options.intra_op_threads, "inter_op_threads": 1, "cpu_affinity": options.cpu_affinity, "repvit_microbatch": options.repvit_microbatch, "dinov3_microbatch": options.dino_microbatch, "compile_models": list(options.compile_models)},
            "profiles": summarize_profile_stages(tuple(_summary_row(row) for row in profile_rows)),
            "quality_gate": {"scope": options.sample_profile, "reference": quality.reference.__dict__ if hasattr(quality.reference, "__dict__") else {"top1": quality.reference.top1, "top3": quality.reference.top3, "fp": quality.reference.false_positives, "fn": quality.reference.false_negatives, "unknown": quality.reference.unknown, "misclassified": quality.reference.misclassified}, "candidate": {"top1": quality.candidate.top1, "top3": quality.candidate.top3, "fp": quality.candidate.false_positives, "fn": quality.candidate.false_negatives, "unknown": quality.candidate.unknown, "misclassified": quality.candidate.misclassified}, "passed": quality.passed if options.sample_profile == "all299" else not quality.regressions},
            "latency_gate": {"bootstrap_seed": options.bootstrap_seed, "mean_delta_ms": latency.mean_delta_ms, "p95_delta_ms": latency.p95_delta_ms, "mean_ci_upper_ms": latency.mean_ci_upper_ms, "p95_ci_upper_ms": latency.p95_ci_upper_ms, "passed": latency.passed},
            "passes": [{"pass_index": item.pass_index, "order": item.order, "reference": [{"key": row.image_key, "total_ms": row.total_ms} for row in item.reference], "candidate": [{"key": row.image_key, "total_ms": row.total_ms} for row in item.candidate]} for item in passes],
        }
        (staging / "report.json").write_text(json.dumps(report, allow_nan=False, sort_keys=True), encoding="utf-8")
        staging.replace(options.output)
        return report
    except Exception as exc:
        (staging / "failure.json").write_text(json.dumps({"type": type(exc).__name__, "message": str(exc)}), encoding="utf-8")
        staging.replace(options.output.parent / f"{options.output.name}.failed.{uuid4().hex}")
        raise


def _validate_full_dataset(samples: tuple[CpuEvaluationSample, ...]) -> None:
    if len(samples) != 299 or sum(len(sample.targets) for sample in samples) != 1406:
        raise ValueError("benchmark requires the fixed 299-image, 1,406-object dataset")


def select_benchmark_samples(
    samples: tuple[CpuEvaluationSample, ...],
    *,
    sample_profile: Literal["all299", "batch2_e3_m3_h3"],
    package_root: Path,
    resolve_profile: Callable[[Path], tuple[Path, ...]] = resolve_batch2_e3_m3_h3,
    sample_for_path: Callable[[Path], CpuEvaluationSample] | None = None,
) -> tuple[CpuEvaluationSample, ...]:
    """Select either the fixed acceptance corpus or the prescribed 3/3/3 screen."""
    if sample_profile == "all299":
        return samples
    if sample_for_path is None:
        by_path = {sample.image_path.resolve(): sample for sample in samples}

        def sample_for_path(path: Path) -> CpuEvaluationSample:
            try:
                return by_path[path.resolve()]
            except KeyError as exc:
                raise ValueError(f"screen image is not in the fixed CPU dataset: {path}") from exc

    source = package_root / "datasets" / "detection" / "group_20class_batch02" / "images"
    selected = tuple(sample_for_path(path) for path in resolve_profile(source))
    if len(selected) != 9 or tuple(sample.profile for sample in selected) != ("E", "E", "E", "M", "M", "M", "H", "H", "H"):
        raise ValueError("batch2_e3_m3_h3 must contain three ordered E, M, and H images")
    return selected


def _validate_rows(rows: tuple[BenchmarkImageRow, ...], samples: tuple[CpuEvaluationSample, ...]) -> None:
    if tuple(row.key for row in rows) != tuple(sample.key for sample in samples):
        raise ValueError("benchmark rows must preserve the dataset image order")


def _summary_row(row: BenchmarkImageRow) -> dict[str, object]:
    return {"profile": row.profile, "object_count": row.object_count, "elapsed_ms": row.total_ms, "canonical_ms": row.canonical_ms, "detector_ms": row.detector_ms, "crop_ms": row.crop_ms, "repvit_ms": row.repvit_ms, "dinov3_ms": row.dinov3_ms, "fusion_ms": row.fusion_ms}


def _live_dependencies() -> BenchmarkDependencies:
    return BenchmarkDependencies(_live_samples, _live_detector_metadata, _live_run_mode)


def _live_samples(root: Path) -> tuple[CpuEvaluationSample, ...]:
    from bakery_scanner.e2e.cpu_dataset import load_cpu_evaluation_samples

    return load_cpu_evaluation_samples(root)


def _live_detector_metadata(root: Path) -> dict[str, object]:
    manifest_path = root / "models" / "rfdetr_large_bakery_v1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = manifest.get("checkpoint")
    calibration = manifest.get("calibration")
    if not isinstance(checkpoint, dict) or not isinstance(calibration, dict):
        raise ValueError("RF-DETR manifest must declare checkpoint and calibration")
    threshold = manifest.get("score_threshold")
    if not isinstance(threshold, (int, float)):
        raise ValueError("RF-DETR manifest score_threshold is invalid")
    checkpoint_path = manifest_path.parent / str(checkpoint.get("file"))
    calibration_path = manifest_path.parent / str(calibration.get("file"))
    return {"artifact_id": manifest.get("source_label"), "score_threshold": float(threshold), "manifest_sha256": _sha256(manifest_path), "checkpoint_sha256": _sha256(checkpoint_path), "calibration_sha256": _sha256(calibration_path)}


def _live_run_mode(mode: str, samples: tuple[CpuEvaluationSample, ...], options: BenchmarkOptions) -> tuple[BenchmarkImageRow, ...]:
    from bakery_scanner.classification.config import ClassifierConfig
    from bakery_scanner.classification.runtime import ClassifierPipeline
    from bakery_scanner.data.preprocess import load_canonical_image
    from bakery_scanner.detectors.rfdetr import RFDetrRunner
    from bakery_scanner.e2e.cpu_regression import build_image_regression_record

    runtime = ClassifierConfig.load(options.classifier_config).runtime.model_copy(update={
        "mode": mode,
        "intra_op_threads": options.intra_op_threads,
        "repvit_microbatch_objects": options.repvit_microbatch,
        "dinov3_microbatch_objects": options.dino_microbatch,
        "cpu_affinity": options.cpu_affinity,
        "compile_models": options.compile_models,
    })
    classifier = ClassifierPipeline.load(options.classifier_config, runtime_override=runtime)
    metadata = _live_detector_metadata(options.package_root)
    checkpoint = options.package_root / "models" / "rfdetr_large_bakery_v1" / "checkpoint.pth"
    detector = RFDetrRunner.load(checkpoint, score_threshold=float(metadata["score_threshold"]), device="cpu")
    rows: list[BenchmarkImageRow] = []
    for image_id, sample in enumerate(samples, start=1):
        canonical_started = time.perf_counter()
        frame = load_canonical_image(sample.image_path)
        canonical_ms = (time.perf_counter() - canonical_started) * 1000.0
        detector_started = time.perf_counter()
        proposals = detector.predict(image_id, frame.image)
        detector_ms = (time.perf_counter() - detector_started) * 1000.0
        if mode == "serial_reference":
            started = time.perf_counter()
            decisions = tuple(classifier.infer(frame, proposal.box) for proposal in proposals)
            total_ms = canonical_ms + detector_ms + (time.perf_counter() - started) * 1000.0
            crop_ms = repvit_ms = dinov3_ms = fusion_ms = 0.0
        else:
            batch = classifier.infer_many(frame, tuple(proposal.box for proposal in proposals), repvit_max_objects=options.repvit_microbatch if isinstance(options.repvit_microbatch, int) else len(proposals), dino_max_objects=options.dino_microbatch if isinstance(options.dino_microbatch, int) else max(1, len(proposals)))
            decisions = batch.decisions
            total_ms = canonical_ms + detector_ms + batch.timings.total_ms
            crop_ms, repvit_ms, dinov3_ms, fusion_ms = batch.timings.crop_ms, batch.timings.repvit_ms, batch.timings.dinov3_ms, batch.timings.fusion_ms
        record = build_image_regression_record(sample, proposals, decisions)
        rows.append(BenchmarkImageRow(sample.key, sample.profile, len(sample.targets), total_ms, record.objects, canonical_ms, detector_ms, crop_ms, repvit_ms, dinov3_ms, fusion_ms))
    return tuple(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_hashes(root: Path, classifier_config: Path, samples: tuple[CpuEvaluationSample, ...]) -> dict[str, str]:
    paths = {
        "classifier_config_sha256": classifier_config,
        "group_15class_annotations_sha256": root / "datasets" / "detection" / "group_15class" / "annotations" / "instances.json",
        "group_20class_batch01_annotations_sha256": root / "datasets" / "detection" / "group_20class_batch01" / "annotations" / "instances.json",
        "group_20class_batch02_annotations_sha256": root / "datasets" / "detection" / "group_20class_batch02" / "annotations" / "instances.json",
    }
    result = {name: _sha256(path) for name, path in paths.items() if path.is_file()}
    result["ordered_image_list_sha256"] = hashlib.sha256("\n".join(sample.key for sample in samples).encode("utf-8")).hexdigest()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--classifier-config", type=Path, required=True)
    parser.add_argument("--reference-mode", choices=("serial_reference",), default="serial_reference")
    parser.add_argument("--candidate-mode", choices=("serial_reference", "batch_pytorch", "batch_pytorch_compile"), required=True)
    parser.add_argument("--sample-profile", choices=("all299", "batch2_e3_m3_h3"), default="all299")
    parser.add_argument("--intra-op-threads", type=int)
    parser.add_argument("--cpu-affinity", default="all")
    parser.add_argument("--repvit-microbatch", choices=("1", "2", "4", "8", "all"), default="1")
    parser.add_argument("--dino-microbatch", choices=("1", "2", "4", "8", "all"), default="1")
    parser.add_argument("--compile-model", choices=("repvit", "dinov3"), action="append", default=[])
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--first-order", choices=("AB", "BA"), default="AB")
    parser.add_argument("--bootstrap-seed", type=int, default=20260729)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    def microbatch(value: str) -> int | str:
        return "all" if value == "all" else int(value)
    affinity = args.cpu_affinity if args.cpu_affinity == "all" else tuple(int(value) for value in args.cpu_affinity.split(","))
    run_benchmark(BenchmarkOptions(args.package_root, args.classifier_config, args.reference_mode, args.candidate_mode, args.sample_profile, args.intra_op_threads, microbatch(args.repvit_microbatch), microbatch(args.dino_microbatch), affinity, tuple(args.compile_model), args.passes, args.first_order, args.bootstrap_seed, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
