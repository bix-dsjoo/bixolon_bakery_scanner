import io
import importlib.util
import json
from pathlib import Path

from bakery_scanner.prototype.camera_protocol import WorkerPhase
from bakery_scanner.prototype.camera_worker import serve


class FakeRuntime:
    def __init__(self, *, fail_analyze: bool = False) -> None:
        self.fail_analyze = fail_analyze
        self.closed = False

    def analyze(self, image_path: Path, request_id: str, on_progress):
        assert image_path.is_file()
        if self.fail_analyze:
            raise RuntimeError("inference failed")
        for phase in (
            WorkerPhase.DETECTING,
            WorkerPhase.CLASSIFYING,
            WorkerPhase.AGGREGATING,
        ):
            on_progress(phase)
        return {"type": "result", "request_id": request_id, "objects": []}

    def close(self) -> None:
        self.closed = True


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
        {"type": "result", "request_id": "analysis-1", "objects": []},
    ]


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
