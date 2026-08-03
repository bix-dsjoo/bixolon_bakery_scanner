"""Long-lived JSON Lines worker for warmed camera inference."""

from __future__ import annotations

import contextlib
import sys
import traceback
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
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
    validate_result_event,
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
_STARTUP_EVENTS = frozenset({"loading", "warming"})
_CODE_IDENTITY_FIELDS = frozenset({"code_commit", "code_identity_sha256"})
_LOWER_HEX = frozenset("0123456789abcdef")
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
    code_identity: Mapping[str, str] | None = None,
) -> int:
    """Serve requests until shutdown or EOF, keeping stdout protocol-only."""
    diagnostics = stderr or sys.stderr
    attested_identity = (
        _validated_code_identity(code_identity) if code_identity is not None else None
    )
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
        emit(_ready_event(runtime, code_identity=attested_identity))
    except Exception as exc:
        if runtime is not None:
            _close_runtime(runtime, diagnostics)
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
        _close_runtime(runtime, diagnostics)
        stopped: dict[str, object] = {"type": "stopped"}
        if stopped_request_id is not None:
            stopped["request_id"] = stopped_request_id
        if attested_identity is not None:
            stopped["code_identity"] = dict(attested_identity)
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
        if previous_phase is not WorkerPhase.AGGREGATING:
            raise ValueError("runtime result requires terminal aggregating progress")
        if not isinstance(result, Mapping):
            raise ValueError("runtime result must be a mapping")
        if result.get("type") != "result":
            raise ValueError("runtime result type must be result")
        if result.get("request_id") != request.request_id:
            raise ValueError("runtime result request_id does not match request")
        validate_result_event(result)
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


def _ready_event(
    runtime: CameraRuntime,
    *,
    code_identity: Mapping[str, str] | None = None,
) -> dict[str, object]:
    device = getattr(runtime, "device", None)
    if not isinstance(device, str) or not device:
        raise ValueError("runtime device must be a non-empty string")
    event: dict[str, object] = {"type": "ready", "device": device}
    startup_metrics = getattr(runtime, "startup_metrics", None)
    if startup_metrics is None:
        if code_identity is not None:
            event["code_identity"] = dict(code_identity)
        return event
    if is_dataclass(startup_metrics):
        startup_metrics = {
            field: (
                dict(value) if isinstance(value, Mapping) else value
            )
            for field, value in (
                (field.name, getattr(startup_metrics, field.name))
                for field in fields(startup_metrics)
            )
        }
    if not isinstance(startup_metrics, Mapping):
        raise ValueError("runtime startup_metrics must be a mapping or dataclass")
    event["startup_metrics"] = dict(startup_metrics)
    if code_identity is not None:
        event["code_identity"] = dict(code_identity)
    return event


def _validated_code_identity(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _CODE_IDENTITY_FIELDS:
        raise ValueError("worker code identity schema is invalid")
    commit = value["code_commit"]
    identity = value["code_identity_sha256"]
    if (
        not isinstance(commit, str)
        or len(commit) not in (40, 64)
        or any(character not in _LOWER_HEX for character in commit)
        or not isinstance(identity, str)
        or len(identity) != 64
        or any(character not in _LOWER_HEX for character in identity)
    ):
        raise ValueError("worker code identity hashes are invalid")
    return {"code_commit": commit, "code_identity_sha256": identity}


def _close_runtime(runtime: CameraRuntime, diagnostics: TextIO) -> None:
    try:
        with contextlib.redirect_stdout(diagnostics):
            runtime.close()
    except Exception as exc:
        _write_diagnostic(diagnostics, "runtime shutdown failed", exc)


def _write_diagnostic(stderr: TextIO, context: str, exc: Exception) -> None:
    print(f"{context}: {exc}", file=stderr)
    traceback.print_exc(file=stderr)
