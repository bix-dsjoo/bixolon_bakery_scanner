import io
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from bakery_scanner.prototype.camera_protocol import WorkerPhase, validate_result_event
from bakery_scanner.prototype.camera_runtime import StartupMetrics
from bakery_scanner.prototype.camera_worker import serve

_POLICY_SHA256 = "a" * 64


def _normal_presentation() -> dict[str, object]:
    return {
        "state": "normal",
        "final_count_usable": True,
        "retake_scope": None,
        "retake_object_ids": [],
        "instruction_code": None,
        "candidate_object_ids": [],
        "policy_id": "camera_action_state_v1",
        "policy_sha256": _POLICY_SHA256,
    }


@dataclass(frozen=True)
class FakeStartupMetrics:
    load_ms: float
    warmup_ms: float


class FakeRuntime:
    def __init__(
        self,
        *,
        fail_analyze: bool = False,
        phases: tuple[WorkerPhase, ...] = (
            WorkerPhase.DETECTING,
            WorkerPhase.CLASSIFYING,
            WorkerPhase.AGGREGATING,
        ),
        device: str = "cpu",
        startup_metrics: object | None = None,
        presentation: object | None = None,
    ) -> None:
        self.fail_analyze = fail_analyze
        self.phases = phases
        self.device = device
        self.startup_metrics = startup_metrics
        self.presentation = (
            _normal_presentation() if presentation is None else presentation
        )
        self.closed = False
        self.close_calls = 0

    def analyze(self, image_path: Path, request_id: str, on_progress):
        assert image_path.is_file()
        if self.fail_analyze:
            raise RuntimeError("inference failed")
        for phase in self.phases:
            on_progress(phase)
        return {
            "type": "result",
            "request_id": request_id,
            "image": {"width": 1, "height": 1},
            "device": self.device,
            "execution_device": self.device,
            "runtime_mode": "cpu_reference",
            "fallback_reason": "CPU reference runtime selected",
            "scan_to_result_ms": 0.0,
            "inference_ms": 0.0,
            "objects": [],
            "counts": {},
            "unknown_count": 0,
            "presentation": self.presentation,
            "timings_ms": {
                "decode_preprocess": 0.0,
                "detector": 0.0,
                "crop": 0.0,
                "repvit": 0.0,
                "dinov3": 0.0,
                "fusion": 0.0,
                "postprocess": 0.0,
                "total": 0.0,
            },
            "diagnostics": {"object_count": 0, "dino_object_count": 0},
        }

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


def test_strict_result_validation_requires_runtime_mode(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    result = FakeRuntime().analyze(image, "request-1", lambda _phase: None)
    result.pop("runtime_mode")

    with pytest.raises(ValueError, match="envelope"):
        validate_result_event(result)


def test_strict_result_validation_requires_gpu_mode_to_use_cuda_device(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    result = FakeRuntime().analyze(image, "request-1", lambda _phase: None)
    result.update(
        {
            "device": "cpu",
            "execution_device": "cpu",
            "runtime_mode": "gpu_reference",
            "fallback_reason": "GPU reference result",
            "scan_to_result_ms": 400.0,
            "inference_ms": 80.0,
        }
    )

    with pytest.raises(ValueError, match="GPU.*device"):
        validate_result_event(result)


def _events(stdout: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def test_worker_emits_startup_once_and_keeps_request_correlation(tmp_path: Path):
    stdin = io.StringIO('{"type":"ping","request_id":"ping-1"}\n'
                        '{"type":"shutdown","request_id":"stop-1"}\n')
    stdout = io.StringIO()
    runtime = FakeRuntime()

    serve(stdin, stdout, runtime_factory=lambda emit: runtime)

    events = _events(stdout)
    assert [row["type"] for row in events] == [
        "loading",
        "warming",
        "ready",
        "pong",
        "stopped",
    ]
    assert events[3]["request_id"] == "ping-1"
    assert events[4]["request_id"] == "stop-1"
    assert runtime.closed is True


def test_ready_includes_final_runtime_device_and_startup_metrics():
    stdout = io.StringIO()
    runtime = FakeRuntime(
        device="cuda:0",
        startup_metrics=FakeStartupMetrics(load_ms=12.5, warmup_ms=7.0),
    )

    serve(
        io.StringIO('{"type":"shutdown","request_id":"stop-ready"}\n'),
        stdout,
        runtime_factory=lambda emit: runtime,
    )

    assert _events(stdout)[2] == {
        "type": "ready",
        "device": "cuda:0",
        "startup_metrics": {"load_ms": 12.5, "warmup_ms": 7.0},
    }


def test_ready_serializes_immutable_real_startup_provenance():
    hashes = {key: "a" * 64 for key in (
        "detector_checkpoint_sha256", "detector_calibration_sha256", "detector_manifest_sha256",
        "repvit_checkpoint_sha256", "repvit_manifest_sha256", "repvit_prototype_sha256",
        "dinov3_weights_sha256", "dinov3_support_sha256", "dinov3_local_bank_sha256",
        "classifier_calibration_sha256", "preprocess_sha256", "fusion_policy_sha256",
        "presentation_policy_sha256",
    )}
    metrics = StartupMetrics(
        device="cpu", load_ms=1.0, warmup_ms=1.0, fallback_reason=None,
        detector_id="detector", repvit_id="repvit", dinov3_id="dino",
        fusion_policy_id="fusion", detector_threshold=0.5, applied_artifact_hashes=hashes,
    )
    runtime = FakeRuntime(startup_metrics=metrics)
    stdout = io.StringIO()
    serve(io.StringIO('{"type":"shutdown","request_id":"stop"}\n'), stdout, runtime_factory=lambda _emit: runtime)
    assert _events(stdout)[2]["startup_metrics"]["applied_artifact_hashes"] == hashes


def test_worker_binds_child_code_identity_to_ready_and_stopped_events():
    stdout = io.StringIO()
    identity = {"code_commit": "a" * 40, "code_identity_sha256": "b" * 64}

    serve(
        io.StringIO('{"type":"shutdown","request_id":"stop-attested"}\n'),
        stdout,
        runtime_factory=lambda emit: FakeRuntime(device="cuda:0"),
        code_identity=identity,
    )

    events = _events(stdout)
    assert events[2]["code_identity"] == identity
    assert events[-1] == {
        "type": "stopped",
        "request_id": "stop-attested",
        "code_identity": identity,
    }


def test_worker_rejects_noncanonical_optional_code_identity():
    with pytest.raises(ValueError, match="code identity"):
        serve(
            io.StringIO(),
            io.StringIO(),
            runtime_factory=lambda emit: FakeRuntime(),
            code_identity={"code_commit": "A" * 40, "code_identity_sha256": "b" * 64},
        )


def test_worker_recovers_from_malformed_input_and_handles_following_request():
    stdin = io.StringIO('{"type":"ping","request_id":}\n'
                        '{"type":"ping","request_id":"ping-2"}\n'
                        '{"type":"shutdown","request_id":"stop-2"}\n')
    stdout = io.StringIO()

    serve(stdin, stdout, runtime_factory=lambda emit: FakeRuntime())

    events = _events(stdout)
    assert events[3]["type"] == "error"
    assert "request_id" not in events[3]
    assert events[4] == {"type": "pong", "request_id": "ping-2"}


def test_worker_emits_legal_correlated_progress_before_result(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    stdin = io.StringIO(
        json.dumps(
            {"type": "analyze", "request_id": "analysis-1", "image_path": str(image)}
        )
        + "\n"
        + '{"type":"shutdown","request_id":"stop-3"}\n'
    )
    stdout = io.StringIO()

    serve(stdin, stdout, runtime_factory=lambda emit: FakeRuntime())

    events = _events(stdout)
    analysis_events = [row for row in events if row.get("request_id") == "analysis-1"]
    assert analysis_events == [
        {"type": "progress", "request_id": "analysis-1", "phase": "detecting"},
        {"type": "progress", "request_id": "analysis-1", "phase": "classifying"},
        {"type": "progress", "request_id": "analysis-1", "phase": "aggregating"},
        {
            "type": "result",
            "request_id": "analysis-1",
            "image": {"width": 1, "height": 1},
            "device": "cpu",
            "execution_device": "cpu",
            "runtime_mode": "cpu_reference",
            "fallback_reason": "CPU reference runtime selected",
            "scan_to_result_ms": 0.0,
            "inference_ms": 0.0,
            "objects": [],
            "counts": {},
            "unknown_count": 0,
            "presentation": _normal_presentation(),
            "timings_ms": {
                "decode_preprocess": 0.0,
                "detector": 0.0,
                "crop": 0.0,
                "repvit": 0.0,
                "dinov3": 0.0,
                "fusion": 0.0,
                "postprocess": 0.0,
                "total": 0.0,
            },
            "diagnostics": {"object_count": 0, "dino_object_count": 0},
            },
    ]


def test_worker_converts_invalid_presentation_to_correlated_analysis_failure(
    tmp_path: Path,
):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    stdout = io.StringIO()

    serve(
        io.StringIO(
            json.dumps(
                {
                    "type": "analyze",
                    "request_id": "invalid-result",
                    "image_path": str(image),
                }
            )
            + "\n"
            + '{"type":"shutdown","request_id":"stop-invalid"}\n'
        ),
        stdout,
        runtime_factory=lambda emit: FakeRuntime(presentation={"state": "normal"}),
        stderr=io.StringIO(),
    )

    analysis_events = [
        row for row in _events(stdout) if row.get("request_id") == "invalid-result"
    ]
    assert analysis_events[-1]["type"] == "error"
    assert analysis_events[-1]["code"] == "analysis_failed"
    assert all(row["type"] != "result" for row in analysis_events)


def test_worker_accepts_rechecking_before_terminal_aggregating(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    stdout = io.StringIO()

    serve(
        io.StringIO(
            json.dumps(
                {"type": "analyze", "request_id": "rechecked", "image_path": str(image)}
            )
            + "\n"
            + '{"type":"shutdown","request_id":"stop-rechecked"}\n'
        ),
        stdout,
        runtime_factory=lambda emit: FakeRuntime(
            phases=(
                WorkerPhase.DETECTING,
                WorkerPhase.CLASSIFYING,
                WorkerPhase.RECHECKING,
                WorkerPhase.AGGREGATING,
            )
        ),
    )

    assert [
        row["type"]
        for row in _events(stdout)
        if row.get("request_id") == "rechecked"
    ] == ["progress", "progress", "progress", "progress", "result"]


@pytest.mark.parametrize(
    "phases",
    [
        (),
        (WorkerPhase.DETECTING,),
        (WorkerPhase.DETECTING, WorkerPhase.CLASSIFYING),
    ],
)
def test_worker_rejects_result_without_terminal_aggregating_phase(
    tmp_path: Path, phases: tuple[WorkerPhase, ...]
):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    stdout = io.StringIO()

    serve(
        io.StringIO(
            json.dumps(
                {"type": "analyze", "request_id": "incomplete", "image_path": str(image)}
            )
            + "\n"
            + '{"type":"shutdown","request_id":"stop-incomplete"}\n'
        ),
        stdout,
        runtime_factory=lambda emit: FakeRuntime(phases=phases),
    )

    analysis_events = [
        row for row in _events(stdout) if row.get("request_id") == "incomplete"
    ]
    assert analysis_events[-1] == {
        "type": "error",
        "request_id": "incomplete",
        "code": "analysis_failed",
        "message": "runtime result requires terminal aggregating progress",
    }
    assert all(row["type"] != "result" for row in analysis_events)


def test_worker_rejects_duplicate_request_id_without_replaying_operation():
    stdin = io.StringIO('{"type":"ping","request_id":"same"}\n'
                        '{"type":"ping","request_id":"same"}\n'
                        '{"type":"shutdown","request_id":"stop-4"}\n')
    stdout = io.StringIO()

    serve(stdin, stdout, runtime_factory=lambda emit: FakeRuntime())

    events = _events(stdout)
    assert events[3] == {"type": "pong", "request_id": "same"}
    assert events[4]["type"] == "error"
    assert events[4]["request_id"] == "same"
    assert events[4]["code"] == "duplicate_request_id"


def test_worker_emits_exactly_one_fatal_when_initialization_fails():
    stdout = io.StringIO()

    serve(
        io.StringIO('{"type":"ping","request_id":"never"}\n'),
        stdout,
        runtime_factory=lambda emit: (_ for _ in ()).throw(RuntimeError("cannot load")),
        stderr=io.StringIO(),
    )

    events = _events(stdout)
    assert [row["type"] for row in events].count("fatal") == 1
    assert all(row["type"] != "ready" for row in events)


def test_worker_closes_initialized_runtime_when_ready_event_cannot_encode():
    stdout = io.StringIO()
    runtime = FakeRuntime(startup_metrics={"unencodable": object()})

    status = serve(
        io.StringIO(),
        stdout,
        runtime_factory=lambda emit: runtime,
        stderr=io.StringIO(),
    )

    assert status == 1
    assert runtime.close_calls == 1
    assert [row["type"] for row in _events(stdout)] == [
        "loading",
        "warming",
        "fatal",
    ]


def test_cli_rejects_warmup_image_outside_repository_root(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"jpeg")
    script = Path(__file__).parents[2] / "scripts" / "run_camera_inference_worker.py"
    spec = importlib.util.spec_from_file_location("camera_worker_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        module.resolve_paths(root, outside)
    except ValueError as exc:
        assert "under the repository root" in str(exc)
    else:
        raise AssertionError("outside warm-up image must be rejected")


def test_cli_allows_verified_external_warmup_image_only_when_requested(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"jpeg")
    script = Path(__file__).parents[2] / "scripts" / "run_camera_inference_worker.py"
    spec = importlib.util.spec_from_file_location("camera_worker_cli_external", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.resolve_paths(root, outside, allow_external_warmup=True) == (
        root.resolve(), outside.resolve()
    )


def test_cli_resolves_bundled_application_and_dinov3_import_roots(
    tmp_path: Path,
):
    root = tmp_path / "pipeline"
    (root / "src").mkdir(parents=True)
    (root / "dino" / "dinov3").mkdir(parents=True)
    (root / "dino" / "dinov3" / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
    script = Path(__file__).parents[2] / "scripts" / "run_camera_inference_worker.py"
    spec = importlib.util.spec_from_file_location("camera_worker_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.resolve_import_roots(root) == (
        root.resolve() / "src",
        root.resolve() / "dino",
    )
