"""Persistent warmed RF-DETR and fail-closed classifier runtime for camera captures."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, cast

import torch

from bakery_scanner.classification.config import (
    ClassifierConfig,
    preprocess_sha256,
)
from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    ModelProvenance,
)
from bakery_scanner.classification.fusion_policy import FusionPolicyArtifact
from bakery_scanner.classification.policy import PolicyCalibration
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.contracts import BreadProposal
from bakery_scanner.data.preprocess import CanonicalImage, load_canonical_image
from bakery_scanner.detectors.rfdetr import RFDetrRunner

from .camera_protocol import WorkerPhase
from .presentation_policy import PresentationPolicy


_DETECTOR_ID = "rfdetr_large_bakery_v1"
_REPVIT_ID = "repvit_m1_15plus5_v1"
_DINOV3_ID = "dinov3_vits16_15plus5_v1"
_FUSION_POLICY_ID = "fusion_local_or_global_consensus_margin_v1"
_MANIFEST_COMMON_KEYS = {
    "schema_version",
    "source_label",
    "checkpoint",
    "calibration",
    "score_threshold",
}
_MANIFEST_SOURCE_KEYS = {"source_path", "source_uri"}
_ARTIFACT_KEYS = {"file", "sha256"}
_SHA256_LENGTH = 64


class RuntimeBackend(Protocol):
    device: str
    detector: RFDetrRunner
    classifier: ClassifierPipeline

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class StartupMetrics:
    device: str
    load_ms: float
    warmup_ms: float
    fallback_reason: str | None
    detector_id: str
    repvit_id: str
    dinov3_id: str
    fusion_policy_id: str
    detector_threshold: float

    def __post_init__(self) -> None:
        if self.device not in {"cpu", "cuda:0"}:
            raise ValueError("startup device must be cpu or cuda:0")
        for field in ("load_ms", "warmup_ms"):
            value = getattr(self, field)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field} must be finite and non-negative")
        if not math.isfinite(self.detector_threshold) or not (
            0.0 <= self.detector_threshold <= 1.0
        ):
            raise ValueError("detector_threshold must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class _DetectorManifest:
    checkpoint: Path
    calibration: Path
    score_threshold: float
    source_label: str


class _LoadedBackend:
    """Own the model graph built for one initialization attempt."""

    def __init__(
        self,
        *,
        device: str,
        detector: RFDetrRunner,
        classifier: ClassifierPipeline,
        detector_threshold: float,
    ) -> None:
        self.device = device
        self.detector = detector
        self.classifier = classifier
        self.detector_id = detector.source
        self.repvit_id = classifier.config.repvit.artifact_id
        self.dinov3_id = classifier.config.dinov3.artifact_id
        self.fusion_policy_id = (
            classifier.fusion_policy.decision_rule
            if classifier.fusion_policy is not None
            else ""
        )
        self.detector_threshold = detector_threshold
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        classifier = self.classifier
        detector = self.detector
        self.classifier = cast(ClassifierPipeline, None)
        self.detector = cast(RFDetrRunner, None)
        for owned in (classifier, detector):
            closer = getattr(owned, "close", None)
            if callable(closer):
                closer()


class CameraInferenceRuntime:
    """Reuse one fully warmed detector/classifier graph for all camera requests."""

    def __init__(
        self,
        *,
        root: Path,
        backend: RuntimeBackend,
        startup_metrics: StartupMetrics,
        presentation_policy: PresentationPolicy,
        clock: Callable[[], float],
    ) -> None:
        self._root = root
        self._backend: RuntimeBackend | None = backend
        self._clock = clock
        self._warmed = True
        self._closed = False
        self.device = startup_metrics.device
        self.startup_metrics = startup_metrics
        self._presentation_policy = presentation_policy

    @classmethod
    def initialize(
        cls,
        root: Path,
        warmup_image: Path,
        preference: str = "auto",
        on_startup: Callable[[str, str], None] | None = None,
        *,
        cuda_probe: Callable[[], bool] | None = None,
        backend_loader: Callable[[str], RuntimeBackend] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> "CameraInferenceRuntime":
        root_path = Path(root).resolve()
        warmup_path = Path(warmup_image).resolve()
        if not root_path.is_dir():
            raise ValueError(f"repository root is missing: {root_path}")
        if not warmup_path.is_file():
            raise ValueError(f"warm-up image is missing: {warmup_path}")
        normalized_preference = _normalize_preference(preference)
        runtime_clock = clock or time.perf_counter
        probe = cuda_probe or _probe_cuda
        cuda_available = False
        if normalized_preference != "cpu":
            try:
                cuda_available = bool(probe())
            except Exception:
                cuda_available = False
        attempts = ["cuda:0", "cpu"] if cuda_available else ["cpu"]
        fallback_reason = None if cuda_available or normalized_preference == "cpu" else "cuda_unavailable"

        manifest = (
            _load_detector_manifest(root_path) if backend_loader is None else None
        )
        for device in attempts:
            backend: RuntimeBackend | None = None
            try:
                load_started = _timestamp(runtime_clock, device)
                if on_startup is not None:
                    on_startup("loading", device)
                if backend_loader is None:
                    assert manifest is not None
                    config = _validate_classifier_artifacts(root_path, device)
                    backend = _load_default_backend(
                        manifest=manifest,
                        config=config,
                        config_path=_classifier_config_path(root_path, device),
                        device=device,
                    )
                else:
                    backend = backend_loader(device)
                _validate_backend(backend, device)
                presentation_policy = PresentationPolicy.load(
                    root_path
                    / "policies"
                    / "presentation"
                    / "camera_action_state_v2.json"
                )
                load_finished = _timestamp(runtime_clock, device)
            except Exception:
                if backend is not None:
                    try:
                        backend.close()
                    except Exception:
                        pass
                backend = None
                gc.collect()
                _release_device_cache(device)
                if device == "cuda:0" and "cpu" in attempts:
                    fallback_reason = "cuda_load_failed"
                    continue
                raise

            if on_startup is not None:
                on_startup("warming", device)
            try:
                warmup_started = _timestamp(runtime_clock, device)
                _warm_backend(backend, warmup_path, device)
                warmup_finished = _timestamp(runtime_clock, device)
            except Exception:
                try:
                    backend.close()
                except Exception:
                    pass
                backend = None
                gc.collect()
                _release_device_cache(device)
                if device == "cuda:0" and "cpu" in attempts:
                    fallback_reason = "cuda_warmup_failed"
                    continue
                raise

            metadata = _backend_metadata(backend, manifest)
            metrics = StartupMetrics(
                device=device,
                load_ms=_milliseconds(load_started, load_finished),
                warmup_ms=_milliseconds(warmup_started, warmup_finished),
                fallback_reason=fallback_reason,
                detector_id=metadata["detector_id"],
                repvit_id=metadata["repvit_id"],
                dinov3_id=metadata["dinov3_id"],
                fusion_policy_id=metadata["fusion_policy_id"],
                detector_threshold=float(metadata["detector_threshold"]),
            )
            return cls(
                root=root_path,
                backend=backend,
                startup_metrics=metrics,
                presentation_policy=presentation_policy,
                clock=runtime_clock,
            )
        raise RuntimeError("runtime initialization exhausted device attempts")

    def warmup(self, warmup_image: Path) -> None:
        """Reject accidental model warm-up after initialization."""
        self._require_open()
        if self._warmed:
            raise RuntimeError("runtime is already warmed")
        assert self._backend is not None
        _warm_backend(self._backend, Path(warmup_image).resolve(), self.device)
        self._warmed = True

    def analyze(
        self,
        image_path: Path,
        request_id: str,
        on_progress: Callable[[WorkerPhase], None] | None = None,
    ) -> dict[str, object]:
        self._require_open()
        if not self._warmed:
            raise RuntimeError("runtime is not warmed")
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id must be a non-empty string")
        capture_path = Path(image_path).resolve()
        if not capture_path.is_file():
            raise ValueError(f"capture image is missing: {capture_path}")
        assert self._backend is not None
        backend = self._backend
        emitted: set[WorkerPhase] = set()

        total_started = _timestamp(self._clock, self.device)
        frame = load_canonical_image(capture_path)
        decode_finished = _timestamp(self._clock, self.device)

        _emit_progress(on_progress, WorkerPhase.DETECTING, emitted)
        detector_started = _timestamp(self._clock, self.device)
        proposals = backend.detector.predict(1, frame.image)
        detector_finished = _timestamp(self._clock, self.device)
        ordered = tuple(
            sorted(
                proposals,
                key=lambda item: (
                    item.box.y,
                    item.box.x,
                    item.box.height,
                    item.box.width,
                    -item.score,
                    item.source,
                ),
            )
        )

        _emit_progress(on_progress, WorkerPhase.CLASSIFYING, emitted)
        repvit_ms = 0.0
        dinov3_ms = 0.0
        decisions: list[tuple[BreadProposal, ClassificationDecision]] = []
        if ordered:
            if backend.classifier.config.runtime.mode == "serial_reference":

                def on_stage(stage: str) -> None:
                    if stage == "dinov3":
                        _emit_progress(on_progress, WorkerPhase.RECHECKING, emitted)
                    elif stage != "repvit":
                        raise ValueError(f"unsupported classifier stage: {stage}")

                for proposal in ordered:
                    decision = backend.classifier.infer(
                        frame,
                        proposal.box,
                        on_stage=on_stage,
                    )
                    if decision.box != proposal.box:
                        raise ValueError("classifier decision box changed detector coordinates")
                    decisions.append((proposal, decision))
                    repvit_ms += decision.timings.repvit_ms
                    dinov3_ms += decision.timings.dinov3_ms
            else:
                boxes = tuple(proposal.box for proposal in ordered)
                batch = backend.classifier.infer_many(
                    frame,
                    boxes,
                    repvit_max_objects=_batch_limit(
                        backend.classifier.config.runtime.repvit_microbatch_objects,
                        len(boxes),
                    ),
                    dino_max_objects=_batch_limit(
                        backend.classifier.config.runtime.dinov3_microbatch_objects,
                        len(boxes),
                    ),
                )
                if len(batch.decisions) != len(ordered):
                    raise ValueError("classifier batch decisions must align with detector proposals")
                if batch.dino_object_count > 0:
                    _emit_progress(on_progress, WorkerPhase.RECHECKING, emitted)
                for proposal, decision in zip(ordered, batch.decisions, strict=True):
                    if decision.box != proposal.box:
                        raise ValueError("classifier decision box changed detector coordinates")
                    decisions.append((proposal, decision))
                repvit_ms = batch.timings.repvit_ms
                dinov3_ms = batch.timings.dinov3_ms

        _emit_progress(on_progress, WorkerPhase.AGGREGATING, emitted)
        postprocess_started = _timestamp(self._clock, self.device)
        objects, counts, unknown_count = _aggregate_objects(
            decisions,
            _load_sku_names(self._root),
        )
        presentation = self._presentation_policy.evaluate(
            proposals=objects,
            decisions=objects,
        ).to_payload()
        postprocess_finished = _timestamp(self._clock, self.device)
        timings = {
            "decode_preprocess": _milliseconds(total_started, decode_finished),
            "detector": _milliseconds(detector_started, detector_finished),
            "repvit": repvit_ms,
            "dinov3": dinov3_ms,
            "postprocess": _milliseconds(postprocess_started, postprocess_finished),
            "total": _milliseconds(total_started, postprocess_finished),
        }
        return {
            "type": "result",
            "request_id": request_id,
            "image": {"width": frame.visual_size[0], "height": frame.visual_size[1]},
            "device": self.device,
            "objects": objects,
            "counts": counts,
            "unknown_count": unknown_count,
            "presentation": presentation,
            "timings_ms": timings,
        }

    def close(self) -> None:
        """Release this runtime's backend once."""
        if self._closed:
            return
        self._closed = True
        backend = self._backend
        self._backend = None
        if backend is not None:
            backend.close()
        _release_device_cache(self.device)

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("runtime is closed")


def _normalize_preference(preference: str) -> str:
    if preference == "cuda":
        return "cuda:0"
    if preference not in {"auto", "cpu", "cuda:0"}:
        raise ValueError("preference must be auto, cpu, or cuda:0")
    return preference


def _batch_limit(value: int | str, object_count: int) -> int:
    if value == "all":
        return max(1, object_count)
    if type(value) is int:
        return value
    raise ValueError("classifier microbatch object limit is invalid")


def _probe_cuda() -> bool:
    if not torch.cuda.is_available():
        return False
    try:
        probe = torch.empty(1, device="cuda:0")
        del probe
        return True
    except Exception:
        return False


def _load_detector_manifest(root: Path) -> _DetectorManifest:
    model_dir = root / "models" / _DETECTOR_ID
    manifest_path = model_dir / "manifest.json"
    try:
        payload = json.loads(
            manifest_path.read_text("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid numeric constant: {value}")
            ),
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"detector manifest is invalid: {manifest_path}") from exc
    except ValueError as exc:
        if str(exc).startswith("invalid numeric constant:"):
            raise ValueError("detector manifest threshold is invalid") from exc
        raise
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"detector manifest is invalid: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("detector manifest schema is invalid")
    source_keys = set(payload) - _MANIFEST_COMMON_KEYS
    if (
        not _MANIFEST_COMMON_KEYS.issubset(payload)
        or source_keys not in ({"source_path"}, {"source_uri"})
    ):
        raise ValueError("detector manifest schema is invalid")
    if payload["schema_version"] != 1:
        raise ValueError("detector manifest schema_version is invalid")
    if payload["source_label"] != _DETECTOR_ID:
        raise ValueError("detector manifest source label is invalid")
    source_key = next(iter(source_keys & _MANIFEST_SOURCE_KEYS))
    if not isinstance(payload[source_key], str) or not payload[source_key]:
        raise ValueError("detector manifest source reference is invalid")
    checkpoint = _manifest_artifact(model_dir, payload["checkpoint"], "checkpoint")
    calibration = _manifest_artifact(
        model_dir, payload["calibration"], "calibration"
    )
    threshold = payload["score_threshold"]
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0.0 <= float(threshold) <= 1.0
    ):
        raise ValueError("detector manifest threshold is invalid")
    return _DetectorManifest(
        checkpoint=checkpoint,
        calibration=calibration,
        score_threshold=float(threshold),
        source_label=_DETECTOR_ID,
    )


def _manifest_artifact(model_dir: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, dict) or set(raw) != _ARTIFACT_KEYS:
        raise ValueError(f"detector {label} manifest schema is invalid")
    filename = raw["file"]
    expected = raw["sha256"]
    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
    ):
        raise ValueError(f"detector {label} file is invalid")
    if not _is_sha256(expected):
        raise ValueError(f"detector {label} SHA-256 is invalid")
    path = model_dir / filename
    _require_file_hash(path, expected, f"detector {label}")
    return path


def _classifier_config_path(root: Path, device: str) -> Path:
    filename = (
        "gpu_rfdetr_classifier_policy.yaml"
        if device == "cuda:0"
        else "cpu_rfdetr_classifier_policy.yaml"
    )
    return root / "configs" / filename


def _validate_classifier_artifacts(root: Path, device: str) -> ClassifierConfig:
    config = ClassifierConfig.load(_classifier_config_path(root, device))
    expected_runtime = "CUDA:0" if device == "cuda:0" else "CPU"
    if config.runtime.device != expected_runtime or config.runtime.precision != "FP32":
        raise ValueError("classifier runtime must match selected device in FP32")
    if config.calibration.artifact_sha256 is None:
        raise ValueError("classifier calibration artifact SHA-256 is required")
    _require_file_hash(
        config.calibration.artifact,
        config.calibration.artifact_sha256,
        "classifier calibration artifact",
    )
    declared = (
        (config.repvit.checkpoint, config.repvit.checkpoint_sha256, "RepViT checkpoint"),
        (config.repvit.manifest, config.repvit.manifest_sha256, "RepViT manifest"),
        (config.dinov3.weights, config.dinov3.weights_sha256, "DINOv3 weights"),
        (config.dinov3.support, config.dinov3.support_sha256, "DINOv3 support"),
    )
    for path, expected, label in declared:
        _require_file_hash(path, expected, label)
    if config.repvit.prototype_bank is None or config.repvit.prototype_bank_sha256 is None:
        raise ValueError("RepViT prototype bank is required")
    _require_file_hash(
        config.repvit.prototype_bank,
        config.repvit.prototype_bank_sha256,
        "RepViT prototype bank",
    )
    if config.dinov3.local_bank is None or config.dinov3.local_bank_sha256 is None:
        raise ValueError("DINOv3 local bank is required")
    _require_file_hash(
        config.dinov3.local_bank,
        config.dinov3.local_bank_sha256,
        "DINOv3 local bank",
    )
    calibration_payload = config.calibration.artifact.read_bytes()
    calibration = PolicyCalibration.from_json_bytes(calibration_payload)
    expected_calibration = {
        "repvit_artifact_id": config.repvit.artifact_id,
        "dinov3_artifact_id": config.dinov3.artifact_id,
        "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
        "repvit_manifest_sha256": config.repvit.manifest_sha256,
        "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
        "dinov3_weights_sha256": config.dinov3.weights_sha256,
        "dinov3_support_sha256": config.dinov3.support_sha256,
        "preprocess_sha256": preprocess_sha256(config.preprocess),
    }
    for field, expected in expected_calibration.items():
        if getattr(calibration, field) != expected:
            raise ValueError(f"classifier calibration {field} mismatch")
    if (
        config.calibration.fusion_policy is None
        or config.calibration.fusion_policy_sha256 is None
    ):
        raise ValueError("immutable fusion policy is required")
    fusion_payload = config.calibration.fusion_policy.read_bytes()
    if hashlib.sha256(fusion_payload).hexdigest() != config.calibration.fusion_policy_sha256:
        raise ValueError("fusion policy SHA-256 mismatch")
    fusion = FusionPolicyArtifact.from_json_bytes(fusion_payload)
    expected_fusion_hashes = {
        "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
        "repvit_manifest_sha256": config.repvit.manifest_sha256,
        "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
        "dinov3_weights_sha256": config.dinov3.weights_sha256,
        "dinov3_support_sha256": config.dinov3.support_sha256,
        "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256,
        "preprocess_sha256": preprocess_sha256(config.preprocess),
    }
    if fusion.artifact_hashes != expected_fusion_hashes:
        raise ValueError("fusion policy artifacts do not match classifier config")
    if fusion.decision_rule != _FUSION_POLICY_ID:
        raise ValueError("fusion policy decision rule is invalid")
    return config


def _load_default_backend(
    *,
    manifest: _DetectorManifest,
    config: ClassifierConfig,
    config_path: Path,
    device: str,
) -> RuntimeBackend:
    detector = RFDetrRunner.load(
        manifest.checkpoint,
        score_threshold=manifest.score_threshold,
        source=manifest.source_label,
        device="cuda" if device == "cuda:0" else "cpu",
    )
    try:
        classifier = ClassifierPipeline.load(config_path)
    except Exception:
        closer = getattr(detector, "close", None)
        if callable(closer):
            closer()
        raise
    if classifier.config != config:
        raise ValueError("classifier config changed after integrity validation")
    return _LoadedBackend(
        device=device,
        detector=detector,
        classifier=classifier,
        detector_threshold=manifest.score_threshold,
    )


def _validate_backend(backend: RuntimeBackend, device: str) -> None:
    if backend is None:
        raise TypeError("backend loader must return a RuntimeBackend")
    if backend.device != device:
        raise ValueError("backend device does not match initialization attempt")
    if not callable(getattr(backend.detector, "predict", None)):
        raise TypeError("runtime detector must provide predict()")
    classifier = backend.classifier
    if (
        not callable(getattr(classifier, "infer", None))
        or not callable(getattr(classifier, "infer_many", None))
        or not callable(getattr(classifier, "preflight_models", None))
    ):
        raise TypeError(
            "runtime classifier must provide infer(), infer_many(), and preflight_models()"
        )
    if not callable(getattr(backend, "close", None)):
        raise TypeError("runtime backend must provide close()")


def _warm_backend(backend: RuntimeBackend, image_path: Path, device: str) -> None:
    frame = load_canonical_image(image_path)
    proposals = backend.detector.predict(1, frame.image)
    if not proposals:
        raise RuntimeError("warm-up image must produce at least one proposal")
    backend.classifier.preflight_models(frame, proposals[0].box)
    _synchronize(device)


def _backend_metadata(
    backend: RuntimeBackend,
    manifest: _DetectorManifest | None,
) -> dict[str, str | float]:
    detector = backend.detector
    classifier = backend.classifier
    config = getattr(classifier, "config", None)
    fusion = getattr(classifier, "fusion_policy", None)
    values: dict[str, str | float] = {
        "detector_id": getattr(
            backend,
            "detector_id",
            getattr(detector, "source", manifest.source_label if manifest else _DETECTOR_ID),
        ),
        "repvit_id": getattr(
            backend,
            "repvit_id",
            getattr(getattr(config, "repvit", None), "artifact_id", _REPVIT_ID),
        ),
        "dinov3_id": getattr(
            backend,
            "dinov3_id",
            getattr(getattr(config, "dinov3", None), "artifact_id", _DINOV3_ID),
        ),
        "fusion_policy_id": getattr(
            backend,
            "fusion_policy_id",
            getattr(fusion, "decision_rule", _FUSION_POLICY_ID),
        ),
        "detector_threshold": getattr(
            backend,
            "detector_threshold",
            getattr(
                detector,
                "_score_threshold",
                manifest.score_threshold if manifest else 0.0,
            ),
        ),
    }
    for field in ("detector_id", "repvit_id", "dinov3_id", "fusion_policy_id"):
        if not isinstance(values[field], str) or not values[field]:
            raise ValueError(f"backend {field} is invalid")
    return values


def _aggregate_objects(
    decisions: list[tuple[BreadProposal, ClassificationDecision]],
    sku_names: Mapping[int, str],
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    objects: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    unknown_count = 0
    for index, (proposal, decision) in enumerate(decisions, start=1):
        if decision.decision == "sku":
            assert decision.sku_id is not None
            sku_name = sku_names[decision.sku_id]
            counts[str(decision.sku_id)] = counts.get(str(decision.sku_id), 0) + 1
            top3: list[dict[str, object]] = []
        else:
            sku_name = "Unknown"
            unknown_count += 1
            top3 = [
                {
                    "rank": candidate.rank,
                    "sku_id": candidate.sku_id,
                    "sku_name": sku_names[candidate.sku_id],
                    "score": candidate.score,
                }
                for candidate in decision.top3
            ]
            if len(top3) != 3:
                raise ValueError("Unknown decisions must preserve exactly three candidates")
        objects.append(
            {
                "object_id": f"object-{index}",
                "sku_id": decision.sku_id,
                "sku_name": sku_name,
                "bbox_xyxy": list(proposal.box.xyxy),
                "confidence": decision.confidence,
                "decision_path": decision.decision_path.value,
                "top3": top3,
                "unknown_reason": decision.unknown_reason,
                "detector": {
                    "source": proposal.source,
                    "score": proposal.score,
                },
                "provenance": _provenance_payload(decision.provenance),
            }
        )
    if sum(counts.values()) + unknown_count != len(objects):
        raise RuntimeError("result aggregation invariant failed")
    return objects, counts, unknown_count


def _provenance_payload(provenance: ModelProvenance) -> dict[str, object]:
    return {
        "detector_id": _DETECTOR_ID,
        "repvit_artifact_id": provenance.repvit_artifact_id,
        "repvit_sha256": provenance.repvit_sha256,
        "repvit_manifest_sha256": provenance.repvit_manifest_sha256,
        "repvit_prototype_sha256": provenance.repvit_prototype_sha256,
        "dinov3_artifact_id": provenance.dinov3_artifact_id,
        "dinov3_sha256": provenance.dinov3_sha256,
        "dinov3_support_sha256": provenance.dinov3_support_sha256,
        "calibration_id": provenance.calibration_id,
        "calibration_sha256": provenance.calibration_sha256,
        "preprocess_sha256": provenance.preprocess_sha256,
        "canonical_frame_version": provenance.canonical_frame_version,
        "exif_orientation": provenance.exif_orientation,
        "failure_code": provenance.failure_code,
    }


def _load_sku_names(root: Path) -> dict[int, str]:
    path = root / "data" / "catalogs" / "classes.json"
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"SKU class map is invalid: {path}") from exc
    if not isinstance(payload, list) or len(payload) != 20:
        raise ValueError("SKU class map must contain exactly 20 rows")
    names: dict[int, str] = {}
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("SKU class map rows must be mappings")
        sku_id = row.get("id")
        name = row.get("name")
        if (
            isinstance(sku_id, bool)
            or not isinstance(sku_id, int)
            or sku_id not in range(1, 21)
            or not isinstance(name, str)
            or not name
            or sku_id in names
        ):
            raise ValueError("SKU class map row is invalid")
        names[sku_id] = name
    if tuple(sorted(names)) != tuple(range(1, 21)):
        raise ValueError("SKU class map IDs must be 1 through 20")
    return names


def _emit_progress(
    callback: Callable[[WorkerPhase], None] | None,
    phase: WorkerPhase,
    emitted: set[WorkerPhase],
) -> None:
    if phase in emitted:
        return
    emitted.add(phase)
    if callback is not None:
        callback(phase)


def _release_device_cache(device: str) -> None:
    if device != "cuda:0":
        return
    try:
        available = torch.cuda.is_available()
    except Exception:
        return
    if available:
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


def _timestamp(clock: Callable[[], float], device: str) -> float:
    _synchronize(device)
    value = float(clock())
    if not math.isfinite(value):
        raise ValueError("clock must return finite values")
    return value


def _synchronize(device: str) -> None:
    if device == "cuda:0" and torch.cuda.is_available():
        torch.cuda.synchronize(torch.device("cuda:0"))


def _milliseconds(started: float, finished: float) -> float:
    value = (finished - started) * 1000.0
    if value < 0.0:
        raise ValueError("clock must be monotonic")
    return value


def _require_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError(f"{label} SHA-256 mismatch")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )
