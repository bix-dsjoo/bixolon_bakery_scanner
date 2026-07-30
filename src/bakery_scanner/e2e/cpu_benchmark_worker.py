"""Prepared, child-local execution core for reliable CPU benchmark passes."""

from __future__ import annotations

import gc
import hashlib
import json
import locale
import math
import os
import platform
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast

from bakery_scanner.classification.config import ClassifierConfig, ClassifierRuntimeConfig
from bakery_scanner.classification.contracts import ClassificationDecision, DecisionPath
from bakery_scanner.classification.runtime import (
    BatchInferenceResult,
    ClassifierPipeline,
    SerialStageTimings,
    configure_cpu_process,
)
from bakery_scanner.contracts import BreadProposal
from bakery_scanner.data.preprocess import CanonicalImage, load_canonical_image
from bakery_scanner.detectors.rfdetr import RFDetrRunner

from .cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PassResult,
    ResolvedRuntime,
    RunPassCommand,
    WarmupEvidence,
    WarmupImageEvidence,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerMetadata,
    WorkerSpec,
)
from .cpu_dataset import CpuEvaluationSample, load_cpu_evaluation_samples
from .cpu_profile import resolve_batch2_e3_m3_h3
from .cpu_regression import (
    ImageRegressionRecord,
    build_image_regression_record,
)


_EXPECTED_IMAGES = 299
_EXPECTED_OBJECTS = 1406
_DETECTOR_DIRECTORY = "rfdetr_large_bakery_v1"


@dataclass(frozen=True, slots=True)
class WorkerDependencies:
    """Spawn-safe factories; loaded model instances remain inside the worker."""

    load_samples: Callable[[Path], tuple[CpuEvaluationSample, ...]]
    select_samples: Callable[..., tuple[CpuEvaluationSample, ...]]
    detector_metadata: Callable[[Path], dict[str, object]]
    load_detector: Callable[[Path, float], object]
    load_classifier: Callable[[Path, ClassifierRuntimeConfig, object], ClassifierPipeline]
    load_canonical_image: Callable[[Path], CanonicalImage]
    build_regression_record: Callable[..., object]
    configure_cpu_process: Callable[[ClassifierRuntimeConfig], None]
    read_environment: Callable[[], WorkerEnvironment]
    clock: Callable[[], float]


class BenchmarkWorkerFailure(RuntimeError):
    """Fail-closed worker preparation or measured-pass error."""


@dataclass(frozen=True, slots=True)
class _ClassifierTimings:
    crop_ms: float
    repvit_ms: float
    dinov3_ms: float
    fusion_ms: float


class BenchmarkWorker:
    """Prepare models once, warm them deterministically, and run ordered passes."""

    def __init__(
        self,
        spec: WorkerSpec,
        *,
        dependencies: WorkerDependencies | None = None,
    ) -> None:
        if not isinstance(spec, WorkerSpec):
            raise TypeError("spec must be a WorkerSpec")
        self._spec = spec
        self._dependencies = dependencies or _live_dependencies()
        self._metadata: WorkerMetadata | None = None
        self._preparation_attempted = False
        self._samples: tuple[CpuEvaluationSample, ...] = ()
        self._runtime: ClassifierRuntimeConfig | None = None
        self._detector: object | None = None
        self._classifier: object | None = None
        self._serial_observations: list[SerialStageTimings] = []

    def prepare(self) -> WorkerMetadata:
        """Configure and load once, then execute exactly two E/M/H warm-up rounds."""
        if self._metadata is not None:
            return self._metadata
        if self._preparation_attempted:
            raise BenchmarkWorkerFailure("worker preparation previously failed")
        self._preparation_attempted = True
        try:
            metadata = self._prepare_once()
        except BenchmarkWorkerFailure:
            raise
        except Exception as exc:
            raise BenchmarkWorkerFailure(f"worker preparation failed: {exc}") from exc
        self._metadata = metadata
        return metadata

    def run_pass(self, command: RunPassCommand) -> PassResult:
        """Run one measured pass in the immutable selected image order."""
        if self._metadata is None:
            raise BenchmarkWorkerFailure("worker must be prepared before a measured pass")
        if not isinstance(command, RunPassCommand):
            raise BenchmarkWorkerFailure("run command must be a RunPassCommand")
        expected_keys = tuple(sample.key for sample in self._samples)
        if command.image_keys != expected_keys:
            raise BenchmarkWorkerFailure(
                "measured image keys must exactly match the selected image key order"
            )
        try:
            rows = tuple(
                self._run_image(sample, sample.source_image_id) for sample in self._samples
            )
            if tuple(row.key for row in rows) != command.image_keys:
                raise BenchmarkWorkerFailure(
                    "measured rows did not preserve the requested image key order"
                )
            return PassResult(
                self._spec.role,
                os.getpid(),
                command.pass_index,
                rows,
            )
        except BenchmarkWorkerFailure:
            raise
        except Exception as exc:
            raise BenchmarkWorkerFailure(
                f"measured pass {command.pass_index} failed: {exc}"
            ) from exc

    def _prepare_once(self) -> WorkerMetadata:
        all_samples = tuple(self._dependencies.load_samples(self._spec.package_root))
        _validate_full_dataset(all_samples)
        selected = tuple(
            self._dependencies.select_samples(
                all_samples,
                sample_profile=self._spec.sample_profile,
                package_root=self._spec.package_root,
            )
        )
        _validate_selected_samples(all_samples, selected)

        raw_detector_metadata = dict(
            self._dependencies.detector_metadata(self._spec.package_root)
        )
        detector_metadata, supplied_hashes = _normalize_detector_metadata(
            raw_detector_metadata
        )
        threshold = _detector_threshold(detector_metadata)

        environment = self._dependencies.read_environment()
        if not isinstance(environment, WorkerEnvironment):
            raise BenchmarkWorkerFailure(
                "worker environment reader must return WorkerEnvironment"
            )
        runtime = _resolve_runtime(self._spec, environment)
        actual_hashes = (
            supplied_hashes
            if supplied_hashes is not None
            else _artifact_hashes(
                self._spec.package_root,
                self._spec.classifier_config,
                all_samples,
            )
        )
        verified_hashes = _verify_artifact_hashes(
            self._spec.expected_artifact_hashes, actual_hashes
        )

        self._dependencies.configure_cpu_process(runtime)
        classifier = self._dependencies.load_classifier(
            self._spec.classifier_config,
            runtime,
            self._serial_observations.append,
        )
        checkpoint_file = detector_metadata.get("checkpoint_file", "checkpoint.pth")
        if not isinstance(checkpoint_file, str) or not checkpoint_file:
            raise BenchmarkWorkerFailure(
                "RF-DETR manifest checkpoint file must be non-empty"
            )
        checkpoint = (
            self._spec.package_root
            / "models"
            / _DETECTOR_DIRECTORY
            / checkpoint_file
        )
        detector = self._dependencies.load_detector(checkpoint, threshold)
        _require_loaded_detector_threshold(detector, threshold)

        self._samples = selected
        self._runtime = runtime
        self._classifier = classifier
        self._detector = detector
        warmup_samples = _select_warmup_samples(all_samples, selected)
        warmup_images: list[WarmupImageEvidence] = []
        for repetition in range(1, self._spec.warmup_repetitions + 1):
            for sample in warmup_samples:
                warmup_images.append(self._warmup_image(sample, repetition))

        return WorkerMetadata(
            role=self._spec.role,
            pid=os.getpid(),
            resolved_runtime=_resolved_runtime(runtime),
            environment=environment,
            detector_metadata=tuple(detector_metadata.items()),
            artifact_hashes=verified_hashes,
            warmup=WarmupEvidence(
                repetitions=self._spec.warmup_repetitions,
                images=tuple(warmup_images),
            ),
            stderr_path=(
                self._spec.package_root
                / f".cpu-benchmark-{self._spec.role}-{os.getpid()}.stderr.log"
            ).resolve(),
        )

    def _warmup_image(
        self,
        sample: CpuEvaluationSample,
        repetition: int,
    ) -> WarmupImageEvidence:
        classifier, detector, runtime = self._prepared_components()
        started = datetime.now(UTC).isoformat()
        frame = self._dependencies.load_canonical_image(sample.image_path)
        _require_canonical_frame(frame)
        proposals = tuple(detector.predict(sample.source_image_id, frame.image))
        _validate_proposals(frame, proposals, sample.source_image_id)
        if not proposals:
            raise BenchmarkWorkerFailure(
                f"warm-up image {sample.key} produced no valid RF-DETR proposals"
            )
        evidence = classifier.preflight_benchmark(
            frame,
            tuple(proposal.box for proposal in proposals),
            repvit_max_objects=_microbatch_limit(
                runtime.repvit_microbatch_objects, len(proposals)
            ),
            dino_max_objects=_microbatch_limit(
                runtime.dinov3_microbatch_objects, len(proposals)
            ),
        )
        if (
            getattr(evidence, "repvit", None) != len(proposals)
            or getattr(evidence, "dinov3_global_local", None) != 1
            or getattr(evidence, "fusion", None) != 1
        ):
            raise BenchmarkWorkerFailure(
                "warm-up preflight did not execute every required classifier stage"
            )
        completed = datetime.now(UTC).isoformat()
        return WarmupImageEvidence(
            key=sample.key,
            profile=sample.profile,
            repetition=repetition,
            started_at_utc=started,
            completed_at_utc=completed,
            stage_counts=WarmupStageCounts(
                canonical=1,
                detector=1,
                repvit=len(proposals),
                dinov3_global_local=1,
                fusion=1,
            ),
        )

    def _run_image(
        self,
        sample: CpuEvaluationSample,
        image_id: int,
    ) -> BenchmarkImageRow:
        classifier, detector, runtime = self._prepared_components()
        total_started = self._dependencies.clock()
        frame = self._dependencies.load_canonical_image(sample.image_path)
        canonical_finished = self._dependencies.clock()
        _require_canonical_frame(frame)
        canonical_ms = _elapsed(total_started, canonical_finished)

        proposals = tuple(detector.predict(image_id, frame.image))
        detector_finished = self._dependencies.clock()
        detector_ms = _elapsed(canonical_finished, detector_finished)
        _validate_proposals(frame, proposals, image_id)

        if runtime.mode == "serial_reference":
            decisions, classifier_timings, dino_count = self._run_serial(
                frame, proposals
            )
        else:
            decisions, classifier_timings, dino_count = self._run_batch(
                frame, proposals
            )
        total_finished = self._dependencies.clock()
        total_ms = _elapsed(total_started, total_finished)

        record = self._dependencies.build_regression_record(
            sample, proposals, decisions
        )
        if not isinstance(record, ImageRegressionRecord):
            raise BenchmarkWorkerFailure(
                "regression builder must return ImageRegressionRecord"
            )
        return self._validated_row(
            sample=sample,
            proposals=proposals,
            decisions=decisions,
            total_ms=total_ms,
            canonical_ms=canonical_ms,
            detector_ms=detector_ms,
            classifier_timings=classifier_timings,
            dino_object_count=dino_count,
            regression_record=record,
        )

    def _run_serial(
        self,
        frame: CanonicalImage,
        proposals: tuple[BreadProposal, ...],
    ) -> tuple[
        tuple[ClassificationDecision, ...],
        _ClassifierTimings,
        int,
    ]:
        classifier, _, _ = self._prepared_components()
        self._serial_observations.clear()
        decisions = tuple(
            classifier.infer(frame, proposal.box) for proposal in proposals
        )
        observations = tuple(self._serial_observations)
        if len(observations) != len(proposals):
            raise BenchmarkWorkerFailure(
                "serial timing observations must equal the proposal count"
            )
        _validate_decisions(proposals, decisions)
        timings = _ClassifierTimings(
            crop_ms=sum(item.crop_ms for item in observations),
            repvit_ms=sum(item.repvit_ms for item in observations),
            dinov3_ms=sum(item.dinov3_ms for item in observations),
            fusion_ms=sum(item.fusion_ms for item in observations),
        )
        _validate_classifier_timings(timings)
        dino_count = sum(item.dino_executed for item in observations)
        _validate_dino_count(decisions, dino_count)
        return decisions, timings, dino_count

    def _run_batch(
        self,
        frame: CanonicalImage,
        proposals: tuple[BreadProposal, ...],
    ) -> tuple[
        tuple[ClassificationDecision, ...],
        _ClassifierTimings,
        int,
    ]:
        classifier, _, runtime = self._prepared_components()
        result = classifier.infer_many(
            frame,
            tuple(proposal.box for proposal in proposals),
            repvit_max_objects=_microbatch_limit(
                runtime.repvit_microbatch_objects, len(proposals)
            ),
            dino_max_objects=_microbatch_limit(
                runtime.dinov3_microbatch_objects, len(proposals)
            ),
        )
        if not isinstance(result, BatchInferenceResult):
            raise BenchmarkWorkerFailure(
                "batch classifier must return BatchInferenceResult"
            )
        decisions = tuple(result.decisions)
        _validate_decisions(proposals, decisions)
        timings = _ClassifierTimings(
            result.timings.crop_ms,
            result.timings.repvit_ms,
            result.timings.dinov3_ms,
            result.timings.fusion_ms,
        )
        _validate_classifier_timings(timings)
        _validate_dino_count(decisions, result.dino_object_count)
        return decisions, timings, result.dino_object_count

    def _validated_row(
        self,
        *,
        sample: CpuEvaluationSample,
        proposals: tuple[BreadProposal, ...],
        decisions: tuple[ClassificationDecision, ...],
        total_ms: float,
        canonical_ms: float,
        detector_ms: float,
        classifier_timings: _ClassifierTimings,
        dino_object_count: int,
        regression_record: ImageRegressionRecord,
    ) -> BenchmarkImageRow:
        for name, value in (
            ("total_ms", total_ms),
            ("canonical_ms", canonical_ms),
            ("detector_ms", detector_ms),
            ("crop_ms", classifier_timings.crop_ms),
            ("repvit_ms", classifier_timings.repvit_ms),
            ("dinov3_ms", classifier_timings.dinov3_ms),
            ("fusion_ms", classifier_timings.fusion_ms),
        ):
            _require_finite_non_negative(value, name)
        sequential_ms = (
            canonical_ms
            + detector_ms
            + classifier_timings.crop_ms
            + classifier_timings.repvit_ms
            + classifier_timings.dinov3_ms
            + classifier_timings.fusion_ms
        )
        if total_ms + 1e-9 < sequential_ms:
            raise BenchmarkWorkerFailure(
                "total timing must include every sequential stage timing"
            )

        ordered_records = tuple(regression_record.objects)
        false_positive_proposal_indices = tuple(
            regression_record.false_positive_proposal_indices
        )
        _validate_regression_record(
            sample,
            proposals,
            decisions,
            regression_record,
        )
        registered_count = sum(
            decision.decision == "sku" for decision in decisions
        )
        unknown_count = sum(
            decision.decision == "unknown" for decision in decisions
        )
        if registered_count + unknown_count != len(decisions):
            raise BenchmarkWorkerFailure(
                "every classifier decision must be registered or Unknown"
            )
        return BenchmarkImageRow(
            key=sample.key,
            profile=sample.profile,
            object_count=len(sample.targets),
            total_ms=total_ms,
            records=ordered_records,
            false_positive_proposal_indices=false_positive_proposal_indices,
            canonical_ms=canonical_ms,
            detector_ms=detector_ms,
            crop_ms=classifier_timings.crop_ms,
            repvit_ms=classifier_timings.repvit_ms,
            dinov3_ms=classifier_timings.dinov3_ms,
            fusion_ms=classifier_timings.fusion_ms,
            dino_object_count=dino_object_count,
            registered_count=registered_count,
            unknown_count=unknown_count,
        )

    def _prepared_components(
        self,
    ) -> tuple[object, object, ClassifierRuntimeConfig]:
        if (
            self._classifier is None
            or self._detector is None
            or self._runtime is None
        ):
            raise BenchmarkWorkerFailure("worker components are not prepared")
        return self._classifier, self._detector, self._runtime


def select_benchmark_samples(
    samples: tuple[CpuEvaluationSample, ...],
    *,
    sample_profile: str,
    package_root: Path,
) -> tuple[CpuEvaluationSample, ...]:
    """Worker-local live adapter for the existing immutable selection rules."""
    if sample_profile == "all299":
        return samples
    if sample_profile != "batch2_e3_m3_h3":
        raise ValueError("sample profile is not recognized")
    by_path = {sample.image_path.resolve(): sample for sample in samples}
    source = (
        package_root
        / "datasets"
        / "detection"
        / "group_20class_batch02"
        / "images"
    )
    selected: list[CpuEvaluationSample] = []
    for path in resolve_batch2_e3_m3_h3(source):
        try:
            selected.append(by_path[path.resolve()])
        except KeyError as exc:
            raise ValueError(
                f"screen image is not in the fixed CPU dataset: {path}"
            ) from exc
    result = tuple(selected)
    if (
        len(result) != 9
        or tuple(sample.profile for sample in result)
        != ("E", "E", "E", "M", "M", "M", "H", "H", "H")
    ):
        raise ValueError(
            "batch2_e3_m3_h3 must contain three ordered E, M, and H images"
        )
    return result


def _live_dependencies() -> WorkerDependencies:
    return WorkerDependencies(
        load_samples=load_cpu_evaluation_samples,
        select_samples=select_benchmark_samples,
        detector_metadata=_live_detector_metadata,
        load_detector=_live_load_detector,
        load_classifier=_live_load_classifier,
        load_canonical_image=load_canonical_image,
        build_regression_record=build_image_regression_record,
        configure_cpu_process=configure_cpu_process,
        read_environment=_read_environment,
        clock=time.perf_counter,
    )


def _live_detector_metadata(root: Path) -> dict[str, object]:
    manifest_path = (
        root / "models" / _DETECTOR_DIRECTORY / "manifest.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("RF-DETR manifest must be readable UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("RF-DETR manifest must be an object")
    checkpoint = manifest.get("checkpoint")
    calibration = manifest.get("calibration")
    if not isinstance(checkpoint, dict) or not isinstance(calibration, dict):
        raise ValueError("RF-DETR manifest must declare checkpoint and calibration")
    checkpoint_file = checkpoint.get("file")
    calibration_file = calibration.get("file")
    if (
        not isinstance(checkpoint_file, str)
        or not checkpoint_file
        or not isinstance(calibration_file, str)
        or not calibration_file
    ):
        raise ValueError("RF-DETR artifact file names must be non-empty")
    checkpoint_path = manifest_path.parent / checkpoint_file
    calibration_path = manifest_path.parent / calibration_file
    manifest_threshold = _finite_threshold(
        manifest.get("score_threshold"), "RF-DETR manifest score threshold"
    )
    try:
        calibration_payload = json.loads(
            calibration_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("RF-DETR calibration must be readable UTF-8 JSON") from exc
    if not isinstance(calibration_payload, dict):
        raise ValueError("RF-DETR calibration must be an object")
    calibration_threshold = _finite_threshold(
        calibration_payload.get("selected_threshold"),
        "RF-DETR calibration threshold",
    )
    _require_declared_hash(checkpoint_path, checkpoint.get("sha256"), "checkpoint")
    _require_declared_hash(
        calibration_path, calibration.get("sha256"), "calibration"
    )
    return {
        "artifact_id": manifest.get("source_label"),
        "score_threshold": manifest_threshold,
        "calibration_score_threshold": calibration_threshold,
        "checkpoint_file": checkpoint_file,
        "manifest_sha256": _sha256(manifest_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "calibration_sha256": _sha256(calibration_path),
    }


def _live_load_detector(checkpoint: Path, threshold: float) -> object:
    return RFDetrRunner.load(
        checkpoint,
        score_threshold=threshold,
        device="cpu",
    )


def _live_load_classifier(
    config: Path,
    runtime: ClassifierRuntimeConfig,
    timing_sink: object,
) -> ClassifierPipeline:
    if not callable(timing_sink):
        raise TypeError("classifier timing sink must be callable")
    return ClassifierPipeline.load(
        config,
        runtime_override=runtime,
        stage_timing_sink=timing_sink,
    )


def _validate_full_dataset(samples: tuple[CpuEvaluationSample, ...]) -> None:
    if (
        len(samples) != _EXPECTED_IMAGES
        or sum(len(sample.targets) for sample in samples) != _EXPECTED_OBJECTS
    ):
        raise BenchmarkWorkerFailure(
            "benchmark requires the fixed 299-image, 1,406-object dataset"
        )
    if any(not isinstance(sample, CpuEvaluationSample) for sample in samples):
        raise BenchmarkWorkerFailure(
            "benchmark dataset must contain CpuEvaluationSample values"
        )
    keys = tuple(sample.key for sample in samples)
    if len(set(keys)) != len(keys):
        raise BenchmarkWorkerFailure("benchmark dataset image keys must be unique")


def _validate_selected_samples(
    all_samples: tuple[CpuEvaluationSample, ...],
    selected: tuple[CpuEvaluationSample, ...],
) -> None:
    if not selected:
        raise BenchmarkWorkerFailure("selected benchmark samples must not be empty")
    by_key = {sample.key: sample for sample in all_samples}
    selected_keys = tuple(sample.key for sample in selected)
    if len(set(selected_keys)) != len(selected_keys):
        raise BenchmarkWorkerFailure("selected image keys must be unique")
    for sample in selected:
        if (
            not isinstance(sample, CpuEvaluationSample)
            or by_key.get(sample.key) != sample
        ):
            raise BenchmarkWorkerFailure(
                "selected samples must come from the fixed benchmark dataset"
            )


def _select_warmup_samples(
    all_samples: tuple[CpuEvaluationSample, ...],
    measured: tuple[CpuEvaluationSample, ...],
) -> tuple[CpuEvaluationSample, CpuEvaluationSample, CpuEvaluationSample]:
    measured_keys = {sample.key for sample in measured}
    selected: list[CpuEvaluationSample] = []
    for profile in ("E", "M", "H"):
        sample = next(
            (
                item
                for item in all_samples
                if item.profile == profile and item.key not in measured_keys
            ),
            None,
        )
        if sample is None:
            sample = next(
                (item for item in all_samples if item.profile == profile),
                None,
            )
        if sample is None:
            raise BenchmarkWorkerFailure(
                f"fixed benchmark dataset has no {profile} warm-up sample"
            )
        selected.append(sample)
    return cast(
        tuple[CpuEvaluationSample, CpuEvaluationSample, CpuEvaluationSample],
        tuple(selected),
    )


def _normalize_detector_metadata(
    metadata: dict[str, object],
) -> tuple[dict[str, object], dict[str, str] | None]:
    supplied = metadata.pop("artifact_hashes", None)
    artifact_hashes: dict[str, str] | None = None
    if supplied is not None:
        if not isinstance(supplied, Mapping):
            raise BenchmarkWorkerFailure(
                "detector artifact hashes must be a mapping"
            )
        artifact_hashes = {}
        for name, digest in supplied.items():
            if not isinstance(name, str) or not isinstance(digest, str):
                raise BenchmarkWorkerFailure(
                    "detector artifact hashes must contain string pairs"
                )
            artifact_hashes[name] = digest
    return metadata, artifact_hashes


def _detector_threshold(metadata: Mapping[str, object]) -> float:
    threshold = _finite_threshold(
        metadata.get("score_threshold"), "RF-DETR manifest threshold"
    )
    calibration_threshold = metadata.get("calibration_score_threshold")
    if calibration_threshold is not None:
        calibrated = _finite_threshold(
            calibration_threshold, "RF-DETR calibration threshold"
        )
        if calibrated != threshold:
            raise BenchmarkWorkerFailure(
                "RF-DETR manifest threshold does not match calibration threshold"
            )
    return threshold


def _finite_threshold(value: object, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise BenchmarkWorkerFailure(f"{field} must be finite and in [0, 1]")
    return float(value)


def _require_loaded_detector_threshold(detector: object, expected: float) -> None:
    missing = object()
    applied = getattr(detector, "_score_threshold", missing)
    if applied is missing:
        applied = getattr(detector, "score_threshold", missing)
    if applied is missing:
        raise BenchmarkWorkerFailure(
            "loaded detector must expose its applied threshold"
        )
    if (
        isinstance(applied, bool)
        or not isinstance(applied, (int, float))
        or float(applied) != expected
    ):
        raise BenchmarkWorkerFailure(
            "loaded detector threshold does not match the RF-DETR manifest threshold"
        )


def _resolve_runtime(
    spec: WorkerSpec,
    environment: WorkerEnvironment,
) -> ClassifierRuntimeConfig:
    config = ClassifierConfig.load(spec.classifier_config)
    payload = config.runtime.model_dump()
    payload.update(dict(spec.runtime_overrides))
    try:
        requested = ClassifierRuntimeConfig.model_validate(payload)
    except Exception as exc:
        raise BenchmarkWorkerFailure(f"runtime overrides are invalid: {exc}") from exc
    if (
        requested.mode != spec.mode
        or requested.device != "CPU"
        or requested.precision != "FP32"
    ):
        raise BenchmarkWorkerFailure(
            "resolved runtime must match the requested mode and use CPU/FP32"
        )
    affinity = (
        tuple(environment.inherited_affinity)
        if requested.cpu_affinity == "all"
        else tuple(requested.cpu_affinity)
    )
    if not affinity:
        affinity = tuple(range(environment.logical_cpu_count))
    inherited = set(environment.inherited_affinity)
    if inherited and not set(affinity).issubset(inherited):
        raise BenchmarkWorkerFailure(
            "resolved CPU affinity must stay within inherited affinity"
        )
    intra_op_threads = requested.intra_op_threads or len(affinity)
    try:
        return ClassifierRuntimeConfig.model_validate(
            {
                **requested.model_dump(),
                "intra_op_threads": intra_op_threads,
                "cpu_affinity": affinity,
            }
        )
    except Exception as exc:
        raise BenchmarkWorkerFailure(
            f"effective CPU runtime is invalid: {exc}"
        ) from exc


def _resolved_runtime(runtime: ClassifierRuntimeConfig) -> ResolvedRuntime:
    if (
        runtime.device != "CPU"
        or runtime.precision != "FP32"
        or runtime.intra_op_threads is None
        or runtime.cpu_affinity == "all"
    ):
        raise BenchmarkWorkerFailure(
            "effective runtime fields must be non-null CPU/FP32 values"
        )
    return ResolvedRuntime(
        mode=runtime.mode,
        device=runtime.device,
        precision=runtime.precision,
        intra_op_threads=runtime.intra_op_threads,
        inter_op_threads=runtime.inter_op_threads,
        cpu_affinity=tuple(runtime.cpu_affinity),
        repvit_microbatch_objects=runtime.repvit_microbatch_objects,
        dinov3_microbatch_objects=runtime.dinov3_microbatch_objects,
        compile_models=runtime.compile_models,
    )


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
    result = {name: _sha256(path) for name, path in paths.items()}
    result["ordered_image_list_sha256"] = hashlib.sha256(
        "\n".join(sample.key for sample in samples).encode("utf-8")
    ).hexdigest()
    return result


def _verify_artifact_hashes(
    expected_pairs: tuple[tuple[str, str], ...],
    actual: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    expected = dict(expected_pairs)
    if expected != dict(actual):
        raise BenchmarkWorkerFailure(
            "worker artifact hashes do not match expected artifact hashes"
        )
    return tuple((name, actual[name]) for name, _ in expected_pairs)


def _validate_proposals(
    frame: CanonicalImage,
    proposals: tuple[object, ...],
    image_id: int,
) -> None:
    width, height = frame.visual_size
    for proposal in proposals:
        if not isinstance(proposal, BreadProposal):
            raise BenchmarkWorkerFailure(
                "detector proposals must contain BreadProposal values"
            )
        if (
            proposal.image_id != image_id
            or proposal.image_width != width
            or proposal.image_height != height
        ):
            raise BenchmarkWorkerFailure(
                "proposal boxes must use the canonical image frame"
            )
        try:
            frame.require_box(proposal.box)
        except ValueError as exc:
            raise BenchmarkWorkerFailure(
                "proposal box is outside the canonical image frame"
            ) from exc


def _require_canonical_frame(frame: object) -> None:
    if (
        not isinstance(frame, CanonicalImage)
        or frame.image.mode != "RGB"
        or frame.image.size != frame.visual_size
        or frame.frame_version != "exif_visual_rgb_v1"
    ):
        raise BenchmarkWorkerFailure(
            "image loader must return an EXIF-transposed canonical RGB frame"
        )


def _validate_decisions(
    proposals: tuple[BreadProposal, ...],
    decisions: tuple[object, ...],
) -> None:
    if len(decisions) != len(proposals):
        raise BenchmarkWorkerFailure(
            "classifier decisions must align with the detector proposal count"
        )
    for proposal, decision in zip(proposals, decisions, strict=True):
        if (
            not isinstance(decision, ClassificationDecision)
            or decision.box != proposal.box
        ):
            raise BenchmarkWorkerFailure(
                "classifier decisions must retain detector box ordering"
            )


def _validate_dino_count(
    decisions: tuple[ClassificationDecision, ...],
    dino_count: int,
) -> None:
    if type(dino_count) is not int or not 0 <= dino_count <= len(decisions):
        raise BenchmarkWorkerFailure(
            "DINO object count must be within the decision count"
        )
    decision_dino_count = sum(
        decision.decision_path is not DecisionPath.REPVIT_DIRECT
        for decision in decisions
    )
    if decision_dino_count != dino_count:
        raise BenchmarkWorkerFailure(
            "DINO object count must agree with classifier decision paths"
        )


def _validate_regression_record(
    sample: CpuEvaluationSample,
    proposals: tuple[BreadProposal, ...],
    decisions: tuple[ClassificationDecision, ...],
    regression_record: ImageRegressionRecord,
) -> None:
    try:
        expected = build_image_regression_record(
            sample, proposals, decisions
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkWorkerFailure(
            "regression record inputs are invalid"
        ) from exc
    if regression_record != expected:
        raise BenchmarkWorkerFailure(
            "regression record must preserve deterministic matching, "
            "misses, decisions, and false-positive proposal indexes"
        )


def _validate_classifier_timings(timings: _ClassifierTimings) -> None:
    for field in ("crop_ms", "repvit_ms", "dinov3_ms", "fusion_ms"):
        _require_finite_non_negative(getattr(timings, field), field)


def _require_finite_non_negative(value: object, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise BenchmarkWorkerFailure(
            f"{field} must be finite and non-negative"
        )
    return float(value)


def _elapsed(started: float, finished: float) -> float:
    if (
        isinstance(started, bool)
        or isinstance(finished, bool)
        or not isinstance(started, (int, float))
        or not isinstance(finished, (int, float))
        or not math.isfinite(float(started))
        or not math.isfinite(float(finished))
        or finished < started
    ):
        raise BenchmarkWorkerFailure(
            "benchmark clock must be finite and monotonic"
        )
    return (float(finished) - float(started)) * 1000.0


def _microbatch_limit(value: int | str, object_count: int) -> int:
    if type(object_count) is not int or object_count < 0:
        raise BenchmarkWorkerFailure("object count must be non-negative")
    if value == "all":
        return max(1, object_count)
    if type(value) is not int or value <= 0:
        raise BenchmarkWorkerFailure(
            "microbatch object limit must be positive or all"
        )
    return value


def _read_environment() -> WorkerEnvironment:
    logical_cpu_count = os.cpu_count() or 1
    affinity = _inherited_affinity(logical_cpu_count)
    return WorkerEnvironment(
        python_version=platform.python_version(),
        pytorch_version=_package_version("torch"),
        torchvision_version=_package_version("torchvision"),
        numpy_version=_package_version("numpy"),
        os_name=os.name,
        os_version=platform.platform(),
        logical_cpu_count=logical_cpu_count,
        inherited_affinity=affinity,
        filesystem_encoding=sys.getfilesystemencoding(),
        default_encoding=locale.getpreferredencoding(False),
        utf8_mode=sys.flags.utf8_mode,
        gc_enabled=gc.isenabled(),
    )


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unavailable"


def _inherited_affinity(logical_cpu_count: int) -> tuple[int, ...]:
    get_affinity = getattr(os, "sched_getaffinity", None)
    if callable(get_affinity):
        return tuple(sorted(get_affinity(0)))
    if os.name != "nt":
        return tuple(range(logical_cpu_count))
    try:
        import ctypes

        process_mask = ctypes.c_size_t()
        system_mask = ctypes.c_size_t()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        success = kernel32.GetProcessAffinityMask(
            kernel32.GetCurrentProcess(),
            ctypes.byref(process_mask),
            ctypes.byref(system_mask),
        )
        if success:
            mask = int(process_mask.value)
            return tuple(
                cpu for cpu in range(logical_cpu_count) if mask & (1 << cpu)
            )
    except (AttributeError, OSError):
        pass
    return tuple(range(logical_cpu_count))


def _require_declared_hash(path: Path, expected: object, name: str) -> None:
    if not isinstance(expected, str) or _sha256(path) != expected:
        raise BenchmarkWorkerFailure(
            f"RF-DETR {name} SHA-256 does not match its manifest"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BenchmarkWorkerFailure(
            f"required benchmark artifact is unreadable: {path}"
        ) from exc
    return digest.hexdigest()
