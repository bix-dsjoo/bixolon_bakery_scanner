"""Long-lived JSON Lines worker for warmed camera inference."""

from __future__ import annotations

import contextlib
import sys
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, TextIO

from .camera_protocol import (
    AnalyzeRequest,
    PingRequest,
    ShutdownRequest,
    WorkerPhase,
    encode_event,
    parse_request,
    progress_event,
)


class CameraRuntime(Protocol):
    """The runtime surface owned by this worker."""

    def analyze(
        self,
        image_path: Path,
        request_id: str,
        on_progress: Callable[[WorkerPhase], None] | None = None,
    ) -> dict[str, object]: ...

    def close(self) -> None: ...


RuntimeFactory = Callable[[Callable[[str, str | None], None]], CameraRuntime]
_STARTUP_EVENTS = frozenset({"loading", "warming", "ready"})
_LEGAL_NEXT_PHASES = {
    None: frozenset({WorkerPhase.DETECTING}),
    WorkerPhase.DETECTING: frozenset({WorkerPhase.CLASSIFYING}),
    WorkerPhase.CLASSIFYING: frozenset(
        {WorkerPhase.RECHECKING, WorkerPhase.AGGREGATING}
    ),
    WorkerPhase.RECHECKING: frozenset({WorkerPhase.AGGREGATING}),
    WorkerPhase.AGGREGATING: frozenset(),
}


def serve(
    stdin: TextIO,
    stdout: TextIO,
    *,
    runtime_factory: RuntimeFactory,
    stderr: TextIO | None = None,
) -> int:
    """Serve requests until shutdown or EOF, keeping stdout protocol-only."""
    diagnostics = stderr or sys.stderr
    startup_emitted: set[str] = set()

    def emit(event: Mapping[str, object]) -> None:
        stdout.write(encode_event(event))
        stdout.flush()

    def emit_startup(event_type: str, device: str | None = None) -> None:
        if event_type not in _STARTUP_EVENTS:
            raise ValueError(f"unsupported startup event: {event_type}")
        if event_type in startup_emitted:
            return
        event: dict[str, object] = {"type": event_type}
        if isinstance(device, str) and device:
            event["device"] = device
        emit(event)
        startup_emitted.add(event_type)

    runtime: CameraRuntime | None = None
    emit_startup("loading")
    try:
        with contextlib.redirect_stdout(diagnostics):
            runtime = runtime_factory(emit_startup)
        emit_startup("warming")
        emit_startup("ready")
    except Exception as exc:
        _write_diagnostic(diagnostics, "runtime initialization failed", exc)
        emit({"type": "fatal", "code": "initialization_failed", "message": str(exc)})
        return 1

    handled_request_ids: set[str] = set()
    stopped_request_id: str | None = None
    try:
        for line in stdin:
            try:
                request = parse_request(line)
            except ValueError as exc:
                _write_diagnostic(diagnostics, "invalid request", exc)
                emit({"type": "error", "code": "invalid_request", "message": str(exc)})
                continue

            request_id = request.request_id
            if request_id in handled_request_ids:
                emit(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "code": "duplicate_request_id",
                        "message": "request_id has already been handled",
                    }
                )
                continue
            handled_request_ids.add(request_id)

            if isinstance(request, PingRequest):
                emit({"type": "pong", "request_id": request_id})
                continue
            if isinstance(request, ShutdownRequest):
                stopped_request_id = request_id
                break
            assert isinstance(request, AnalyzeRequest)
            _serve_analysis(runtime, request, emit, diagnostics)
    finally:
        try:
            with contextlib.redirect_stdout(diagnostics):
                runtime.close()
        except Exception as exc:
            _write_diagnostic(diagnostics, "runtime shutdown failed", exc)
        stopped: dict[str, object] = {"type": "stopped"}
        if stopped_request_id is not None:
            stopped["request_id"] = stopped_request_id
        emit(stopped)
    return 0


def _serve_analysis(
    runtime: CameraRuntime,
    request: AnalyzeRequest,
    emit: Callable[[Mapping[str, object]], None],
    diagnostics: TextIO,
) -> None:
    previous_phase: WorkerPhase | None = None

    def on_progress(phase: WorkerPhase) -> None:
        nonlocal previous_phase
        if (
            not isinstance(phase, WorkerPhase)
            or phase not in _LEGAL_NEXT_PHASES[previous_phase]
        ):
            raise ValueError("runtime emitted progress outside the legal phase order")
        emit(progress_event(request.request_id, phase))
        previous_phase = phase

    try:
        with contextlib.redirect_stdout(diagnostics):
            result = runtime.analyze(request.image_path, request.request_id, on_progress)
        if not isinstance(result, Mapping):
            raise ValueError("runtime result must be a mapping")
        if result.get("type") != "result":
            raise ValueError("runtime result type must be result")
        if result.get("request_id") != request.request_id:
            raise ValueError("runtime result request_id does not match request")
        emit(result)
    except Exception as exc:
        _write_diagnostic(diagnostics, f"analysis failed for {request.request_id}", exc)
        emit(
            {
                "type": "error",
                "request_id": request.request_id,
                "code": "analysis_failed",
                "message": str(exc),
            }
        )


def _write_diagnostic(stderr: TextIO, context: str, exc: Exception) -> None:
    print(f"{context}: {exc}", file=stderr)
    traceback.print_exc(file=stderr)
