from __future__ import annotations

import hashlib
import json
import weakref
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image

from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    SkuCandidate,
    StageTimings,
)
from bakery_scanner.classification.runtime import BatchInferenceResult, BatchStageTimings
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.prototype.camera_protocol import WorkerPhase
from bakery_scanner.prototype.camera_runtime import (
    CameraInferenceRuntime,
    _load_detector_manifest,
)


def _write_image(path: Path, size: tuple[int, int] = (80, 60)) -> Path:
    Image.new("RGB", size, (240, 230, 220)).save(path, format="JPEG")
    return path


def _provenance() -> ModelProvenance:
    return ModelProvenance(
        repvit_artifact_id="repvit_m1_15plus5_v1",
        repvit_sha256="1" * 64,
        dinov3_artifact_id="dinov3_vits16_15plus5_v1",
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id="fusion_policy_fusion_local_or_global_consensus_margin_v1",
        calibration_sha256="4" * 64,
        preprocess_sha256="5" * 64,
        repvit_manifest_sha256="6" * 64,
        repvit_prototype_sha256="7" * 64,
    )


def _confirmed(sku_id: int, box: Box, *, repvit_ms: float = 2.0) -> ClassificationDecision:
    return ClassificationDecision(
        decision="sku",
        sku_id=sku_id,
        confidence=0.95,
        box=box,
        decision_path=DecisionPath.REPVIT_DIRECT,
        top3=(),
        provenance=_provenance(),
        timings=StageTimings(repvit_ms=repvit_ms, dinov3_ms=0.0, total_ms=repvit_ms),
    )


def _unknown(
    box: Box,
    *,
    scores: tuple[float, float, float] = (0.61, 0.22, 0.17),
) -> ClassificationDecision:
    return ClassificationDecision(
        decision="unknown",
        sku_id=None,
        confidence=scores[0],
        box=box,
        decision_path=DecisionPath.UNKNOWN_TOP3,
        top3=(
            SkuCandidate(rank=1, sku_id=4, score=scores[0]),
            SkuCandidate(rank=2, sku_id=7, score=scores[1]),
            SkuCandidate(rank=3, sku_id=12, score=scores[2]),
        ),
        provenance=_provenance(),
        timings=StageTimings(repvit_ms=3.0, dinov3_ms=5.0, total_ms=8.0),
        unknown_reason="fusion_global_consensus_margin",
    )


def _proposal(box: Box, *, score: float = 0.9) -> BreadProposal:
    return BreadProposal(
        image_id=1,
        source="rfdetr_large_bakery_v1",
        score=score,
        box=box,
        image_width=80,
        image_height=60,
    )


class FakeDetector:
    source = "rfdetr_large_bakery_v1"

    def __init__(self, proposals: tuple[BreadProposal, ...]) -> None:
        self.proposals = proposals
        self.predict_calls = 0

    def predict(self, image_id: int, image: Image.Image) -> tuple[BreadProposal, ...]:
        self.predict_calls += 1
        return self.proposals


class FakeClassifier:
    def __init__(
        self,
        decisions: tuple[ClassificationDecision, ...],
        *,
        fail_warmup: bool = False,
        fail_analyze: bool = False,
    ) -> None:
        self.decisions = decisions
        self.fail_warmup = fail_warmup
        self.fail_analyze = fail_analyze
        self.preflight_calls = 0
        self.infer_calls = 0
        self.infer_many_calls = 0
        self.config = SimpleNamespace(
            runtime=SimpleNamespace(
                repvit_microbatch_objects="all",
                dinov3_microbatch_objects="all",
            )
        )

    def preflight_models(self, image, box: Box) -> None:
        self.preflight_calls += 1
        if self.fail_warmup:
            raise RuntimeError("warm-up failed")

    def infer(self, image, box: Box, *, on_stage=None) -> ClassificationDecision:
        if self.fail_analyze:
            raise RuntimeError("analysis failed")
        decision = self.decisions[self.infer_calls % len(self.decisions)]
        self.infer_calls += 1
        if on_stage is not None:
            on_stage("repvit")
            if decision.timings.dinov3_ms > 0:
                on_stage("dinov3")
        return decision

    def infer_many(
        self,
        image,
        boxes: tuple[Box, ...],
        *,
        repvit_max_objects: int,
        dino_max_objects: int,
    ) -> BatchInferenceResult:
        if self.fail_analyze:
            raise RuntimeError("analysis failed")
        self.infer_many_calls += 1
        decisions = tuple(
            self.decisions[index % len(self.decisions)]
            for index, _ in enumerate(boxes)
        )
        return BatchInferenceResult(
            decisions,
            BatchStageTimings(
                crop_ms=0.0,
                repvit_ms=sum(decision.timings.repvit_ms for decision in decisions),
                dinov3_ms=sum(decision.timings.dinov3_ms for decision in decisions),
                fusion_ms=0.0,
                total_ms=sum(decision.timings.total_ms for decision in decisions),
            ),
            sum(decision.timings.dinov3_ms > 0.0 for decision in decisions),
        )


class FakeBatchClassifier(FakeClassifier):
    def __init__(
        self,
        decisions: tuple[ClassificationDecision, ...],
        *,
        dino_object_count: int | None = None,
    ) -> None:
        super().__init__(decisions)
        self.config = SimpleNamespace(
            runtime=SimpleNamespace(
                repvit_microbatch_objects="all",
                dinov3_microbatch_objects="all",
            )
        )
        self.dino_object_count = (
            sum(decision.timings.dinov3_ms > 0.0 for decision in decisions)
            if dino_object_count is None
            else dino_object_count
        )
        self.infer_many_calls: list[tuple[Box, ...]] = []
        self.infer_many_limits: list[tuple[int, int]] = []

    def infer_many(
        self,
        image,
        boxes: tuple[Box, ...],
        *,
        repvit_max_objects: int,
        dino_max_objects: int,
    ) -> BatchInferenceResult:
        self.infer_many_calls.append(tuple(boxes))
        self.infer_many_limits.append((repvit_max_objects, dino_max_objects))
        return BatchInferenceResult(
            self.decisions,
            BatchStageTimings(
                crop_ms=1.0,
                repvit_ms=7.0,
                dinov3_ms=5.0,
                fusion_ms=1.0,
                total_ms=14.0,
            ),
            self.dino_object_count,
        )


class FailIfCalledClassifier(FakeBatchClassifier):
    def __init__(self) -> None:
        super().__init__(())

    def infer_many(self, *args, **kwargs) -> BatchInferenceResult:
        pytest.fail("classifier called for empty scene")


class FakeBackend:
    detector_id = "rfdetr_large_bakery_v1"
    repvit_id = "repvit_m1_15plus5_v1"
    dinov3_id = "dinov3_vits16_15plus5_v1"
    fusion_policy_id = "fusion_local_or_global_consensus_margin_v1"
    detector_threshold = 0.8502742052078247

    def __init__(
        self,
        device: str,
        *,
        proposals: tuple[BreadProposal, ...] | None = None,
        decisions: tuple[ClassificationDecision, ...] | None = None,
        fail_warmup: bool = False,
        fail_analyze: bool = False,
    ) -> None:
        warmup_box = Box(5, 5, 20, 20)
        self.device = device
        self.detector = FakeDetector(proposals or (_proposal(warmup_box),))
        self.classifier = FakeClassifier(
            decisions or (_confirmed(6, warmup_box),),
            fail_warmup=fail_warmup,
            fail_analyze=fail_analyze,
        )
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


@dataclass
class TickClock:
    value: float = 0.0

    def __call__(self) -> float:
        self.value += 0.001
        return self.value


@dataclass
class ManualClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _runtime(
    tmp_path: Path,
    *,
    classifier: FakeClassifier,
    proposals: tuple[BreadProposal, ...],
) -> CameraInferenceRuntime:
    warmup_image = _write_image(tmp_path / "warm.jpg")
    backend = FakeBackend("cpu", proposals=proposals)
    backend.classifier = classifier
    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=lambda device: backend,
    )
    backend.detector.proposals = proposals
    return runtime


@pytest.fixture(autouse=True)
def class_map(tmp_path: Path) -> None:
    names = (
        "Walnut Donut",
        "Croffle",
        "Waffle",
        "Scon",
        "Half-moon Croissant",
        "Croissant",
        "Flower Bread",
        "Almond Scon",
        "Dinner Roll",
        "Sugar Donut",
        "Bagel",
        "Egg Tart",
        "Muffin",
        "Burger",
        "Sandwich",
        "Grain Campagne",
        "Almond Campagne",
        "Mini Bread",
        "Pastry Bread",
        "Plain Bread",
    )
    catalog_dir = tmp_path / "data" / "catalogs"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "classes.json").write_text(
        json.dumps(
            [
                {
                    "id": sku_id,
                    "key": f"bread_{sku_id:02d}",
                    "name": name,
                    "set": "fixture",
                }
                for sku_id, name in enumerate(names, start=1)
            ]
        ),
        encoding="utf-8",
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "camera_presentation_policy.json").write_bytes(
        b'{"box_overlap_iou":0.7,"candidate_top12_min_margin":0.05,'
        b'"candidate_top1_min_score":0.3,"policy_id":"camera_action_state_v1",'
        b'"schema_version":1}'
    )
    presentation_dir = tmp_path / "policies" / "presentation"
    presentation_dir.mkdir(parents=True, exist_ok=True)
    (presentation_dir / "camera_action_state_v2.json").write_bytes(
        b'{"box_overlap_iou":0.7,"policy_id":"camera_action_state_v2",'
        b'"schema_version":2}'
    )


@pytest.fixture
def detector_repo(tmp_path: Path):
    model_dir = tmp_path / "models" / "rfdetr_large_bakery_v1"
    model_dir.mkdir(parents=True)
    checkpoint = model_dir / "checkpoint.pth"
    calibration = model_dir / "calibration.json"
    checkpoint.write_bytes(b"checkpoint")
    calibration.write_bytes(b'{"threshold":0.8502742052078247}')
    manifest = {
        "schema_version": 1,
        "source_label": "rfdetr_large_bakery_v1",
        "source_path": "fixture",
        "checkpoint": {
            "file": checkpoint.name,
            "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        },
        "calibration": {
            "file": calibration.name,
            "sha256": hashlib.sha256(calibration.read_bytes()).hexdigest(),
        },
        "score_threshold": 0.8502742052078247,
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    warmup_image = _write_image(tmp_path / "warm.jpg")
    return SimpleNamespace(
        root=tmp_path,
        model_dir=model_dir,
        detector_checkpoint=checkpoint,
        detector_calibration=calibration,
        warmup_image=warmup_image,
    )


def test_initialize_retries_cleanly_on_cpu_after_cuda_warmup_failure(tmp_path: Path):
    attempts: list[str] = []
    backends: list[FakeBackend] = []
    closed_devices: list[str] = []
    failed_backend: weakref.ReferenceType[FakeBackend] | None = None
    warmup_image = _write_image(tmp_path / "warm.jpg")

    class TrackingBackend(FakeBackend):
        def close(self) -> None:
            closed_devices.append(self.device)
            super().close()

    def loader(device: str) -> FakeBackend:
        nonlocal failed_backend
        attempts.append(device)
        if device == "cpu":
            assert failed_backend is not None
            assert failed_backend() is None
        backend = TrackingBackend(device, fail_warmup=device == "cuda:0")
        if device == "cuda:0":
            failed_backend = weakref.ref(backend)
        else:
            backends.append(backend)
        return backend

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="auto",
        cuda_probe=lambda: True,
        backend_loader=loader,
        clock=TickClock(),
    )

    assert attempts == ["cuda:0", "cpu"]
    assert closed_devices == ["cuda:0"]
    assert failed_backend is not None
    assert failed_backend() is None
    assert runtime.device == "cpu"
    assert runtime.startup_metrics.fallback_reason == "cuda_warmup_failed"
    assert runtime.startup_metrics.load_ms >= 0.0
    assert runtime.startup_metrics.warmup_ms >= 0.0


@pytest.mark.parametrize("cleanup_failure", ["availability", "empty_cache"])
def test_cuda_cleanup_failure_does_not_suppress_cpu_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_failure: str,
):
    from bakery_scanner.prototype import camera_runtime

    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")
    monkeypatch.setattr(camera_runtime.torch.cuda, "synchronize", lambda *args: None)
    if cleanup_failure == "availability":
        availability_calls = 0

        def fail_during_cleanup() -> bool:
            nonlocal availability_calls
            availability_calls += 1
            if availability_calls == 4:
                raise RuntimeError("CUDA availability cleanup failed")
            return False

        monkeypatch.setattr(
            camera_runtime.torch.cuda,
            "is_available",
            fail_during_cleanup,
        )
    else:
        monkeypatch.setattr(camera_runtime.torch.cuda, "is_available", lambda: True)

        def fail_empty_cache() -> None:
            raise RuntimeError("CUDA empty cache failed")

        monkeypatch.setattr(
            camera_runtime.torch.cuda,
            "empty_cache",
            fail_empty_cache,
        )

    def loader(device: str) -> FakeBackend:
        attempts.append(device)
        return FakeBackend(device, fail_warmup=device == "cuda:0")

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        cuda_probe=lambda: True,
        backend_loader=loader,
    )

    assert attempts == ["cuda:0", "cpu"]
    assert runtime.device == "cpu"
    assert runtime.startup_metrics.fallback_reason == "cuda_warmup_failed"


def test_initialize_retries_on_cpu_after_cuda_load_failure(tmp_path: Path):
    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")

    def loader(device: str) -> FakeBackend:
        attempts.append(device)
        if device == "cuda:0":
            raise RuntimeError("load failed")
        return FakeBackend(device)

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        cuda_probe=lambda: True,
        backend_loader=loader,
    )

    assert attempts == ["cuda:0", "cpu"]
    assert runtime.startup_metrics.fallback_reason == "cuda_load_failed"


def test_initialize_does_not_attempt_cuda_when_torch_reports_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from bakery_scanner.prototype import camera_runtime

    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")
    monkeypatch.setattr(camera_runtime.torch.cuda, "is_available", lambda: False)

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        backend_loader=lambda device: attempts.append(device) or FakeBackend(device),
    )

    assert attempts == ["cpu"]
    assert runtime.device == "cpu"


def test_initialize_does_not_attempt_cuda_when_small_allocation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from bakery_scanner.prototype import camera_runtime

    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")
    monkeypatch.setattr(camera_runtime.torch.cuda, "is_available", lambda: True)

    def fail_allocation(*args, **kwargs):
        raise RuntimeError("CUDA allocation failed")

    monkeypatch.setattr(camera_runtime.torch, "empty", fail_allocation)

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        backend_loader=lambda device: attempts.append(device) or FakeBackend(device),
    )

    assert attempts == ["cpu"]
    assert runtime.device == "cpu"


def test_initialize_falls_back_when_cuda_timing_synchronization_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from bakery_scanner.prototype import camera_runtime

    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")
    monkeypatch.setattr(camera_runtime.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(camera_runtime.torch.cuda, "empty_cache", lambda: None)

    def fail_synchronize(*args, **kwargs):
        raise RuntimeError("CUDA context failed")

    monkeypatch.setattr(camera_runtime.torch.cuda, "synchronize", fail_synchronize)

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        cuda_probe=lambda: True,
        backend_loader=lambda device: attempts.append(device) or FakeBackend(device),
    )

    assert attempts == ["cpu"]
    assert runtime.device == "cpu"
    assert runtime.startup_metrics.fallback_reason == "cuda_load_failed"


def test_initialize_falls_back_when_cuda_warmup_timing_fails(tmp_path: Path):
    attempts: list[str] = []
    backends: list[FakeBackend] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")

    class FailingCudaWarmupClock:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self) -> float:
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("CUDA warm-up clock failed")
            return self.calls / 1000.0

    def loader(device: str) -> FakeBackend:
        attempts.append(device)
        backend = FakeBackend(device)
        backends.append(backend)
        return backend

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        cuda_probe=lambda: True,
        backend_loader=loader,
        clock=FailingCudaWarmupClock(),
    )

    assert attempts == ["cuda:0", "cpu"]
    assert backends[0].close_calls == 1
    assert runtime.device == "cpu"
    assert runtime.startup_metrics.fallback_reason == "cuda_warmup_failed"


def test_initialize_rejects_detector_checkpoint_hash_mismatch(detector_repo):
    detector_repo.detector_checkpoint.write_bytes(b"changed")

    with pytest.raises(ValueError, match="checkpoint SHA-256"):
        CameraInferenceRuntime.initialize(
            detector_repo.root,
            detector_repo.warmup_image,
            preference="cpu",
        )


def test_initialize_rejects_detector_calibration_hash_mismatch(detector_repo):
    detector_repo.detector_calibration.write_bytes(b"changed")

    with pytest.raises(ValueError, match="calibration SHA-256"):
        CameraInferenceRuntime.initialize(
            detector_repo.root,
            detector_repo.warmup_image,
            preference="cpu",
        )


def test_initialize_rejects_threshold_only_direct_policy_mutation(detector_repo):
    config_dir = detector_repo.root / "configs"
    config_dir.mkdir(exist_ok=True)
    policy_path = detector_repo.root / "policy.json"
    original_policy = b'{"direct_threshold":0.9}'
    policy_path.write_bytes(original_policy)
    config = {
        "schema_version": 1,
        "repvit": {
            "artifact_id": "repvit_m1_15plus5_v1",
            "checkpoint": "../repvit.pt",
            "checkpoint_sha256": "1" * 64,
            "manifest": "../repvit.json",
            "manifest_sha256": "2" * 64,
            "prototype_bank": "../repvit-prototypes.pt",
            "prototype_bank_sha256": "3" * 64,
        },
        "dinov3": {
            "artifact_id": "dinov3_vits16_15plus5_v1",
            "weights": "../dino.pth",
            "weights_sha256": "4" * 64,
            "support": "../dino-support.pt",
            "support_sha256": "5" * 64,
            "local_bank": "../dino-local.pt",
            "local_bank_sha256": "6" * 64,
        },
        "preprocess": {"input_size": 224, "paddings": [0.05, 0.10, 0.15]},
        "runtime": {"device": "CPU", "precision": "FP32"},
        "calibration": {
            "artifact": "../policy.json",
            "artifact_sha256": hashlib.sha256(original_policy).hexdigest(),
            "fusion_policy": "../fusion.json",
            "fusion_policy_sha256": "7" * 64,
        },
    }
    (config_dir / "cpu_rfdetr_classifier_policy.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )
    policy_path.write_bytes(b'{"direct_threshold":0.8}')

    with pytest.raises(
        ValueError, match="classifier calibration artifact SHA-256 mismatch"
    ):
        CameraInferenceRuntime.initialize(
            detector_repo.root,
            detector_repo.warmup_image,
            preference="cpu",
        )


def test_initialize_rejects_malformed_detector_manifest(detector_repo):
    (detector_repo.model_dir / "manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="detector manifest is invalid"):
        CameraInferenceRuntime.initialize(
            detector_repo.root,
            detector_repo.warmup_image,
            preference="cpu",
        )


def test_load_detector_manifest_accepts_canonical_source_uri(detector_repo):
    manifest_path = detector_repo.model_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["source_uri"] = "artifact://rfdetr_large_bakery_v1/checkpoint.pth"
    del manifest["source_path"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = _load_detector_manifest(detector_repo.root)

    assert loaded.checkpoint == detector_repo.detector_checkpoint
    assert loaded.calibration == detector_repo.detector_calibration


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema"),
        ("source_label", "different", "source label"),
        ("score_threshold", float("nan"), "threshold"),
    ],
)
def test_initialize_rejects_invalid_detector_manifest(
    detector_repo, field: str, value: object, message: str
):
    manifest_path = detector_repo.model_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        CameraInferenceRuntime.initialize(
            detector_repo.root,
            detector_repo.warmup_image,
            preference="cpu",
        )


def test_analyze_returns_deterministic_fail_closed_result_contract(tmp_path: Path):
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")
    top = Box(40, 4, 20, 15)
    middle = Box(5, 25, 20, 15)
    bottom = Box(42, 25, 20, 15)
    backend = FakeBackend(
        "cpu",
        proposals=(
            _proposal(bottom, score=0.88),
            _proposal(middle, score=0.91),
            _proposal(top, score=0.93),
        ),
        decisions=(
            _confirmed(6, top),
            _confirmed(10, middle),
            _unknown(bottom),
        ),
    )
    phases: list[WorkerPhase] = []
    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=lambda device: backend,
        clock=TickClock(),
    )

    result = runtime.analyze(image_path, "request-7", phases.append)

    assert result["type"] == "result"
    assert result["request_id"] == "request-7"
    assert result["image"] == {"width": 80, "height": 60}
    assert result["device"] == "cpu"
    assert [row["object_id"] for row in result["objects"]] == [
        "object-1",
        "object-2",
        "object-3",
    ]
    assert [row["bbox_xyxy"] for row in result["objects"]] == [
        [40.0, 4.0, 60.0, 19.0],
        [5.0, 25.0, 25.0, 40.0],
        [42.0, 25.0, 62.0, 40.0],
    ]
    assert result["objects"][0]["sku_name"] == "Croissant"
    assert result["objects"][1]["sku_name"] == "Sugar Donut"
    assert result["objects"][0]["top3"] == []
    assert result["objects"][1]["top3"] == []
    assert len(result["objects"][2]["top3"]) == 3
    assert result["objects"][2]["sku_id"] is None
    assert result["objects"][2]["sku_name"] == "Unknown"
    assert [
        set(candidate) for candidate in result["objects"][2]["top3"]
    ] == [{"rank", "sku_id", "sku_name", "score"}] * 3
    assert [candidate["sku_name"] for candidate in result["objects"][2]["top3"]] == [
        "Scon",
        "Flower Bread",
        "Egg Tart",
    ]
    assert result["counts"] == {"6": 1, "10": 1}
    assert result["unknown_count"] == 1
    assert sum(result["counts"].values()) + result["unknown_count"] == 3
    assert set(result["timings_ms"]) == {
        "decode_preprocess",
        "detector",
        "repvit",
        "dinov3",
        "postprocess",
        "total",
    }
    assert result["timings_ms"]["repvit"] == 7.0
    assert result["timings_ms"]["dinov3"] == 5.0
    assert phases == [
        WorkerPhase.DETECTING,
        WorkerPhase.CLASSIFYING,
        WorkerPhase.RECHECKING,
        WorkerPhase.AGGREGATING,
    ]


def test_camera_runtime_batches_all_ordered_objects_once(tmp_path: Path):
    image_path = _write_image(tmp_path / "capture.jpg")
    top = Box(40, 4, 20, 15)
    middle = Box(5, 25, 20, 15)
    bottom = Box(42, 25, 20, 15)
    classifier = FakeBatchClassifier(
        (
            _confirmed(6, top),
            _confirmed(10, middle),
            _unknown(bottom),
        )
    )
    classifier.infer = lambda *args, **kwargs: pytest.fail("serial infer used")
    runtime = _runtime(
        tmp_path,
        classifier=classifier,
        proposals=(
            _proposal(bottom, score=0.88),
            _proposal(middle, score=0.91),
            _proposal(top, score=0.93),
        ),
    )

    result = runtime.analyze(image_path, "batch-objects")

    assert classifier.infer_many_calls == [(top, middle, bottom)]
    assert classifier.infer_many_limits == [(3, 3)]
    assert [row["object_id"] for row in result["objects"]] == [
        "object-1",
        "object-2",
        "object-3",
    ]
    assert [row["decision_path"] for row in result["objects"]] == [
        DecisionPath.REPVIT_DIRECT.value,
        DecisionPath.REPVIT_DIRECT.value,
        DecisionPath.UNKNOWN_TOP3.value,
    ]
    assert result["timings_ms"]["repvit"] == 7.0
    assert result["timings_ms"]["dinov3"] == 5.0


def test_camera_runtime_rejects_misaligned_batch_decisions(tmp_path: Path):
    image_path = _write_image(tmp_path / "capture.jpg")
    first = Box(5, 5, 20, 20)
    second = Box(35, 5, 20, 20)
    runtime = _runtime(
        tmp_path,
        classifier=FakeBatchClassifier((_confirmed(6, first),)),
        proposals=(_proposal(first), _proposal(second)),
    )

    with pytest.raises(ValueError, match="align"):
        runtime.analyze(image_path, "misaligned")


def test_empty_scene_never_calls_classifier(tmp_path: Path):
    image_path = _write_image(tmp_path / "capture.jpg")
    runtime = _runtime(
        tmp_path,
        classifier=FailIfCalledClassifier(),
        proposals=(),
    )

    result = runtime.analyze(image_path, "empty")

    assert result["objects"] == []
    assert result["presentation"]["instruction_code"] == "no_bread_detected"


def test_analyze_routes_weak_unknown_to_top3_without_changing_counts(
    tmp_path: Path,
):
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")
    registered_box = Box(5, 5, 20, 20)
    weak_unknown_box = Box(40, 5, 20, 20)
    backend = FakeBackend(
        "cpu",
        proposals=(
            _proposal(weak_unknown_box, score=0.88),
            _proposal(registered_box, score=0.93),
        ),
        decisions=(
            _confirmed(6, registered_box),
            _unknown(weak_unknown_box, scores=(0.32, 0.29, 0.20)),
        ),
    )
    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=lambda device: backend,
    )

    result = runtime.analyze(image_path, "weak-unknown")

    assert [row["object_id"] for row in result["objects"]] == [
        "object-1",
        "object-2",
    ]
    assert result["counts"] == {"6": 1}
    assert result["unknown_count"] == 1
    assert result["presentation"] == {
        "state": "unknown",
        "final_count_usable": True,
        "retake_scope": None,
        "retake_object_ids": [],
        "instruction_code": None,
        "candidate_object_ids": ["object-2"],
        "policy_id": "camera_action_state_v2",
        "policy_sha256": (
            "d668324f7743096e83d59b64040335aa8f6bb974ba95d768915f4b39b2178b7c"
        ),
    }


def test_progress_observer_time_is_excluded_from_detector_and_postprocess(
    tmp_path: Path,
):
    clock = ManualClock()
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")
    box = Box(5, 5, 20, 20)

    class TimedDetector(FakeDetector):
        def predict(
            self, image_id: int, image: Image.Image
        ) -> tuple[BreadProposal, ...]:
            clock.advance(0.010)
            return super().predict(image_id, image)

    backend = FakeBackend("cpu")
    backend.detector = TimedDetector((_proposal(box),))
    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=lambda device: backend,
        clock=clock,
    )

    result = runtime.analyze(
        image_path,
        "timed",
        on_progress=lambda phase: clock.advance(1.0),
    )

    assert result["timings_ms"]["detector"] == pytest.approx(10.0)
    assert result["timings_ms"]["postprocess"] == pytest.approx(0.0)
    assert result["timings_ms"]["total"] == pytest.approx(3010.0)


def test_analyze_emits_each_progress_phase_at_most_once(tmp_path: Path):
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")
    first = Box(5, 5, 20, 20)
    second = Box(35, 5, 20, 20)
    backend = FakeBackend(
        "cpu",
        proposals=(_proposal(first), _proposal(second)),
        decisions=(_unknown(first), _unknown(second)),
    )
    phases: list[WorkerPhase] = []
    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=lambda device: backend,
    )

    runtime.analyze(image_path, "one", phases.append)

    assert phases == [
        WorkerPhase.DETECTING,
        WorkerPhase.CLASSIFYING,
        WorkerPhase.RECHECKING,
        WorkerPhase.AGGREGATING,
    ]


def test_analyze_never_falls_back_after_initialization(tmp_path: Path):
    attempts: list[str] = []
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")

    def loader(device: str) -> FakeBackend:
        attempts.append(device)
        return FakeBackend(device, fail_analyze=True)

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="auto",
        cuda_probe=lambda: True,
        backend_loader=loader,
    )

    with pytest.raises(RuntimeError, match="analysis failed"):
        runtime.analyze(image_path, "one")
    assert attempts == ["cuda:0"]
    assert runtime.device == "cuda:0"


def test_runtime_warms_once_reuses_models_and_closes_idempotently(tmp_path: Path):
    warmup_image = _write_image(tmp_path / "warm.jpg")
    image_path = _write_image(tmp_path / "capture.jpg")
    backend = FakeBackend("cpu")
    loader_calls = 0

    def loader(device: str) -> FakeBackend:
        nonlocal loader_calls
        loader_calls += 1
        return backend

    runtime = CameraInferenceRuntime.initialize(
        tmp_path,
        warmup_image,
        preference="cpu",
        backend_loader=loader,
    )
    runtime.analyze(image_path, "one")
    runtime.analyze(image_path, "two")

    assert loader_calls == 1
    assert backend.detector.predict_calls == 3
    assert backend.classifier.preflight_calls == 1
    assert backend.classifier.infer_calls == 0
    assert backend.classifier.infer_many_calls == 2
    with pytest.raises(RuntimeError, match="runtime is already warmed"):
        runtime.warmup(warmup_image)

    runtime.close()
    runtime.close()
    assert backend.close_calls == 1
    with pytest.raises(RuntimeError, match="runtime is closed"):
        runtime.analyze(image_path, "three")


def test_warmup_requires_at_least_one_detector_proposal(tmp_path: Path):
    warmup_image = _write_image(tmp_path / "warm.jpg")
    backend = FakeBackend("cpu", proposals=())
    backend.detector.proposals = ()

    with pytest.raises(RuntimeError, match="at least one proposal"):
        CameraInferenceRuntime.initialize(
            tmp_path,
            warmup_image,
            preference="cpu",
            backend_loader=lambda device: backend,
        )
    assert backend.close_calls == 1
