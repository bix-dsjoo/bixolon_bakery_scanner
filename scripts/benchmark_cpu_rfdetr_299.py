"""Reproducible AB/BA CPU benchmark report for the RF-DETR-L pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence

from bakery_scanner.e2e.cpu_benchmark_coordinator import (
    BenchmarkCoordinationError,
    BenchmarkCoordinator,
)
from bakery_scanner.e2e.cpu_benchmark_protocol import (
    ProtocolState,
    WorkerError,
    WorkerSpec,
)
from bakery_scanner.e2e.cpu_benchmark_report import (
    CoordinatorSettings,
    build_benchmark_report,
    publish_benchmark_failure,
    publish_benchmark_report,
)
from bakery_scanner.e2e.cpu_benchmark_worker import select_benchmark_samples
from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample


@dataclass(frozen=True, slots=True)
class BenchmarkOptions:
    package_root: Path
    classifier_config: Path
    reference_mode: str
    candidate_mode: str
    sample_profile: Literal["all299", "batch2_e3_m3_h3"]
    intra_op_threads: int | None
    repvit_microbatch: int | str | None
    dino_microbatch: int | str | None
    cpu_affinity: str | tuple[int, ...] | None
    compile_models: tuple[str, ...]
    passes: int
    first_order: Literal["AB", "BA"]
    bootstrap_seed: int
    output: Path
    warmup_repetitions: Literal[2] = 2
    ready_timeout_s: float = 900.0
    pass_timeout_s: float = 7200.0
    shutdown_timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.warmup_repetitions != 2:
            raise ValueError("warmup_repetitions must be exactly 2")
        if type(self.passes) is not int or self.passes < 3:
            raise ValueError("passes must be an integer of at least 3")
        for field in (
            "ready_timeout_s",
            "pass_timeout_s",
            "shutdown_timeout_s",
        ):
            object.__setattr__(
                self,
                field,
                _positive_float(getattr(self, field)),
            )


@dataclass(frozen=True, slots=True)
class BenchmarkDependencies:
    load_samples: Callable[[Path], tuple[CpuEvaluationSample, ...]]
    detector_metadata: Callable[[Path], dict[str, object]]
    artifact_hashes: Callable[
        [Path, Path, tuple[CpuEvaluationSample, ...]], dict[str, str]
    ]
    run_coordinator: Callable[..., object]
    build_report: Callable[..., dict[str, object]]
    publish_report: Callable[[Path, dict[str, object]], object]
    publish_failure: Callable[..., object] = publish_benchmark_failure


def run_benchmark(
    options: BenchmarkOptions,
    dependencies: BenchmarkDependencies | None = None,
) -> dict[str, object]:
    """Run two persistent workers and publish one schema-v3 report."""
    if options.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {options.output}")
    dependencies = dependencies or _live_dependencies()

    all_samples = tuple(dependencies.load_samples(options.package_root))
    _validate_full_dataset(all_samples)
    samples = select_benchmark_samples(
        all_samples,
        sample_profile=options.sample_profile,
        package_root=options.package_root,
    )
    detector = dict(dependencies.detector_metadata(options.package_root))
    artifacts = dict(
        dependencies.artifact_hashes(
            options.package_root,
            options.classifier_config,
            all_samples,
        )
    )
    expected_artifacts = tuple(artifacts.items())
    shared_overrides = _shared_runtime_overrides(options)
    reference_spec = WorkerSpec(
        role="reference",
        mode="serial_reference",
        package_root=options.package_root,
        classifier_config=options.classifier_config,
        sample_profile=options.sample_profile,
        runtime_overrides=(
            ("mode", options.reference_mode),
            *shared_overrides,
        ),
        expected_artifact_hashes=expected_artifacts,
        warmup_repetitions=options.warmup_repetitions,
    )
    candidate_overrides = [
        ("mode", options.candidate_mode),
        *shared_overrides,
    ]
    if options.compile_models:
        candidate_overrides.append(("compile_models", options.compile_models))
    candidate_spec = WorkerSpec(
        role="candidate",
        mode=options.candidate_mode,
        package_root=options.package_root,
        classifier_config=options.classifier_config,
        sample_profile=options.sample_profile,
        runtime_overrides=tuple(candidate_overrides),
        expected_artifact_hashes=expected_artifacts,
        warmup_repetitions=options.warmup_repetitions,
    )
    coordinator_settings = CoordinatorSettings(
        options.ready_timeout_s,
        options.pass_timeout_s,
        options.shutdown_timeout_s,
    )

    try:
        execution = dependencies.run_coordinator(
            reference_spec=reference_spec,
            candidate_spec=candidate_spec,
            image_keys=tuple(sample.key for sample in samples),
            passes=options.passes,
            first_order=options.first_order,
            ready_timeout_s=options.ready_timeout_s,
            pass_timeout_s=options.pass_timeout_s,
            shutdown_timeout_s=options.shutdown_timeout_s,
        )
        report = dependencies.build_report(
            execution=execution,
            samples=samples,
            detector=detector,
            artifacts=artifacts,
            sample_profile=options.sample_profile,
            bootstrap_seed=options.bootstrap_seed,
            coordinator_settings=coordinator_settings,
        )
        dependencies.publish_report(options.output, report)
    except Exception as exc:
        failure = (
            exc.failure
            if isinstance(exc, BenchmarkCoordinationError)
            else _parent_failure(exc)
        )
        dependencies.publish_failure(
            options.output,
            failure,
            coordinator_settings=coordinator_settings,
        )
        raise
    return report


def _validate_full_dataset(samples: tuple[CpuEvaluationSample, ...]) -> None:
    if len(samples) != 299 or sum(len(sample.targets) for sample in samples) != 1406:
        raise ValueError(
            "benchmark requires the fixed 299-image, 1,406-object dataset"
        )


def _shared_runtime_overrides(
    options: BenchmarkOptions,
) -> tuple[tuple[str, object], ...]:
    overrides: list[tuple[str, object]] = []
    if options.intra_op_threads is not None:
        overrides.append(("intra_op_threads", options.intra_op_threads))
    if options.repvit_microbatch is not None:
        overrides.append(
            ("repvit_microbatch_objects", options.repvit_microbatch)
        )
    if options.dino_microbatch is not None:
        overrides.append(
            ("dinov3_microbatch_objects", options.dino_microbatch)
        )
    if options.cpu_affinity is not None:
        overrides.append(("cpu_affinity", options.cpu_affinity))
    return tuple(overrides)


def _parent_failure(exc: Exception) -> WorkerError:
    message = " ".join(str(exc).split()) or "benchmark report operation failed"
    return WorkerError(
        exception_type=type(exc).__name__,
        message=message[:500],
        role=None,
        pid=os.getpid(),
        protocol_state=ProtocolState.ERROR,
        pass_index=None,
        stderr_path=None,
    )


def _live_dependencies() -> BenchmarkDependencies:
    return BenchmarkDependencies(
        load_samples=_live_samples,
        detector_metadata=_live_detector_metadata,
        artifact_hashes=_artifact_hashes,
        run_coordinator=_run_coordinator,
        build_report=build_benchmark_report,
        publish_report=publish_benchmark_report,
        publish_failure=publish_benchmark_failure,
    )


def _run_coordinator(
    *,
    reference_spec: WorkerSpec,
    candidate_spec: WorkerSpec,
    image_keys: tuple[str, ...],
    passes: int,
    first_order: Literal["AB", "BA"],
    ready_timeout_s: float,
    pass_timeout_s: float,
    shutdown_timeout_s: float,
) -> object:
    coordinator = BenchmarkCoordinator(
        ready_timeout_s=ready_timeout_s,
        pass_timeout_s=pass_timeout_s,
        shutdown_timeout_s=shutdown_timeout_s,
    )
    return coordinator.run(
        reference_spec=reference_spec,
        candidate_spec=candidate_spec,
        image_keys=image_keys,
        passes=passes,
        first_order=first_order,
    )


def _live_samples(root: Path) -> tuple[CpuEvaluationSample, ...]:
    from bakery_scanner.e2e.cpu_dataset import load_cpu_evaluation_samples

    return load_cpu_evaluation_samples(root)


def _live_detector_metadata(root: Path) -> dict[str, object]:
    manifest_path = (
        root / "models" / "rfdetr_large_bakery_v1" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = manifest.get("checkpoint")
    calibration = manifest.get("calibration")
    if not isinstance(checkpoint, dict) or not isinstance(calibration, dict):
        raise ValueError(
            "RF-DETR manifest must declare checkpoint and calibration"
        )
    threshold = manifest.get("score_threshold")
    if not isinstance(threshold, (int, float)):
        raise ValueError("RF-DETR manifest score_threshold is invalid")
    checkpoint_path = manifest_path.parent / str(checkpoint.get("file"))
    calibration_path = manifest_path.parent / str(calibration.get("file"))
    return {
        "artifact_id": manifest.get("source_label"),
        "score_threshold": float(threshold),
        "manifest_sha256": _sha256(manifest_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "calibration_sha256": _sha256(calibration_path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_hashes(
    root: Path,
    classifier_config: Path,
    samples: tuple[CpuEvaluationSample, ...],
) -> dict[str, str]:
    paths = {
        "classifier_config_sha256": classifier_config,
        "group_15class_annotations_sha256": (
            root
            / "datasets"
            / "detection"
            / "group_15class"
            / "annotations"
            / "instances.json"
        ),
        "group_20class_batch01_annotations_sha256": (
            root
            / "datasets"
            / "detection"
            / "group_20class_batch01"
            / "annotations"
            / "instances.json"
        ),
        "group_20class_batch02_annotations_sha256": (
            root
            / "datasets"
            / "detection"
            / "group_20class_batch02"
            / "annotations"
            / "instances.json"
        ),
    }
    result = {
        name: _sha256(path) for name, path in paths.items() if path.is_file()
    }
    result["ordered_image_list_sha256"] = hashlib.sha256(
        "\n".join(sample.key for sample in samples).encode("utf-8")
    ).hexdigest()
    return result


def _positive_float(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise ValueError("value must be a finite positive number")
    return float(value)


def _positive_timeout_argument(value: str) -> float:
    try:
        return _positive_float(float(value))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            "timeout must be a finite positive number"
        ) from exc


def _passes_argument(value: str) -> int:
    try:
        passes = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "passes must be an integer of at least 3"
        ) from exc
    if passes < 3:
        raise argparse.ArgumentTypeError(
            "passes must be an integer of at least 3"
        )
    return passes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--classifier-config", type=Path, required=True)
    parser.add_argument(
        "--reference-mode",
        choices=("serial_reference",),
        default="serial_reference",
    )
    parser.add_argument(
        "--candidate-mode",
        choices=(
            "serial_reference",
            "batch_pytorch",
            "batch_pytorch_compile",
        ),
        required=True,
    )
    parser.add_argument(
        "--sample-profile",
        choices=("all299", "batch2_e3_m3_h3"),
        default="all299",
    )
    parser.add_argument("--intra-op-threads", type=int)
    parser.add_argument("--cpu-affinity")
    parser.add_argument(
        "--repvit-microbatch",
        choices=("1", "2", "4", "8", "all"),
    )
    parser.add_argument(
        "--dino-microbatch",
        choices=("1", "2", "4", "8", "all"),
    )
    parser.add_argument(
        "--compile-model",
        choices=("repvit", "dinov3"),
        action="append",
        default=[],
    )
    parser.add_argument("--passes", type=_passes_argument, default=3)
    parser.add_argument("--first-order", choices=("AB", "BA"), default="AB")
    parser.add_argument("--bootstrap-seed", type=int, default=20260729)
    parser.add_argument(
        "--ready-timeout",
        type=_positive_timeout_argument,
        default=900.0,
    )
    parser.add_argument(
        "--pass-timeout",
        type=_positive_timeout_argument,
        default=7200.0,
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=_positive_timeout_argument,
        default=30.0,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    def microbatch(value: str | None) -> int | str | None:
        if value is None:
            return None
        return "all" if value == "all" else int(value)

    affinity = (
        None
        if args.cpu_affinity is None
        else (
            args.cpu_affinity
            if args.cpu_affinity == "all"
            else tuple(
                int(value) for value in args.cpu_affinity.split(",")
            )
        )
    )
    run_benchmark(
        BenchmarkOptions(
            args.package_root,
            args.classifier_config,
            args.reference_mode,
            args.candidate_mode,
            args.sample_profile,
            args.intra_op_threads,
            microbatch(args.repvit_microbatch),
            microbatch(args.dino_microbatch),
            affinity,
            tuple(args.compile_model),
            args.passes,
            args.first_order,
            args.bootstrap_seed,
            args.output,
            ready_timeout_s=args.ready_timeout,
            pass_timeout_s=args.pass_timeout,
            shutdown_timeout_s=args.shutdown_timeout,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
