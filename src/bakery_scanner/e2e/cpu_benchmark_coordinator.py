"""Persistent spawn coordination for isolated CPU benchmark workers."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing import get_context
from multiprocessing.connection import Connection
from typing import Literal, Protocol, TypeVar, cast

from .cpu_benchmark_protocol import (
    ErrorMessage,
    PassResult,
    PassResultMessage,
    PrepareCommand,
    ProtocolState,
    ReadyMessage,
    RunPassCommand,
    ShutdownCommand,
    StoppedMessage,
    WorkerError,
    WorkerMetadata,
    WorkerSpec,
)
from .cpu_benchmark_worker import worker_process_main


class WorkerEndpoint(Protocol):
    def prepare(self, timeout_s: float) -> WorkerMetadata: ...

    def run_pass(self, command: RunPassCommand, timeout_s: float) -> PassResult: ...

    def shutdown(self, timeout_s: float) -> None: ...

    def terminate(self) -> None: ...

    @property
    def is_alive(self) -> bool: ...

    @property
    def exit_code(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class CoordinatedPass:
    pass_index: int
    order: Literal["AB", "BA"]
    reference: PassResult
    candidate: PassResult


@dataclass(frozen=True, slots=True)
class BenchmarkExecution:
    reference_worker: WorkerMetadata
    candidate_worker: WorkerMetadata
    passes: tuple[CoordinatedPass, ...]
    started_at_utc: str
    completed_at_utc: str


class BenchmarkCoordinationError(RuntimeError):
    """Structured, fail-closed parent-side lifecycle failure."""

    def __init__(self, failure: WorkerError) -> None:
        if not isinstance(failure, WorkerError):
            raise TypeError("failure must be WorkerError")
        self.failure = failure
        super().__init__(
            f"{failure.exception_type}: {failure.message} "
            f"(state={failure.protocol_state.value})"
        )


_MessageT = TypeVar("_MessageT")


class _SpawnWorkerEndpoint:
    """One duplex pipe and one persistent spawn-created child process."""

    def __init__(self, spec: WorkerSpec, context) -> None:
        self._spec = spec
        self._connection: Connection
        parent_connection, child_connection = context.Pipe(duplex=True)
        self._connection = parent_connection
        self._process = context.Process(
            target=worker_process_main,
            args=(child_connection,),
            name=f"cpu-benchmark-{spec.role}",
        )
        self._closed = False
        try:
            self._process.start()
        finally:
            child_connection.close()

    def prepare(self, timeout_s: float) -> WorkerMetadata:
        self._send(PrepareCommand(self._spec), ProtocolState.PREPARING, None)
        message = self._receive(
            timeout_s,
            ReadyMessage,
            ProtocolState.PREPARING,
            None,
        )
        return message.metadata

    def run_pass(self, command: RunPassCommand, timeout_s: float) -> PassResult:
        self._send(command, ProtocolState.RUNNING_PASS, command.pass_index)
        message = self._receive(
            timeout_s,
            PassResultMessage,
            ProtocolState.RUNNING_PASS,
            command.pass_index,
        )
        return message.result

    def shutdown(self, timeout_s: float) -> None:
        if self._closed:
            return
        started = time.monotonic()
        if not self.is_alive:
            raise self._endpoint_error(
                "WorkerExitError",
                "worker exited before graceful shutdown",
                ProtocolState.STOPPING,
                None,
            )
        self._send(ShutdownCommand(), ProtocolState.STOPPING, None)
        message = self._receive(
            timeout_s,
            StoppedMessage,
            ProtocolState.STOPPING,
            None,
        )
        if message.role != self._spec.role or message.pid != self._process.pid:
            raise self._endpoint_error(
                "UnexpectedWorkerMessage",
                "STOPPED identity did not match the worker",
                ProtocolState.STOPPING,
                None,
            )
        remaining = max(0.0, timeout_s - (time.monotonic() - started))
        self._process.join(remaining)
        if self.is_alive:
            raise self._endpoint_error(
                "TimeoutError",
                "worker did not exit after STOPPED",
                ProtocolState.STOPPING,
                None,
            )
        if self.exit_code != 0:
            raise self._endpoint_error(
                "WorkerExitError",
                "worker exited abnormally after STOPPED",
                ProtocolState.STOPPING,
                None,
            )
        self._close_connection()

    def terminate(self) -> None:
        if self.is_alive:
            self._process.terminate()
            self._process.join(5.0)
            if self.is_alive:
                kill = getattr(self._process, "kill", None)
                if callable(kill):
                    kill()
                    self._process.join(5.0)
        self._close_connection()

    @property
    def is_alive(self) -> bool:
        return self._process.is_alive()

    @property
    def exit_code(self) -> int | None:
        return self._process.exitcode

    def _send(
        self,
        message: object,
        state: ProtocolState,
        pass_index: int | None,
    ) -> None:
        try:
            self._connection.send(message)
        except (BrokenPipeError, EOFError, OSError) as exc:
            raise self._endpoint_error(
                type(exc).__name__,
                "worker command pipe failed",
                state,
                pass_index,
            ) from exc

    def _receive(
        self,
        timeout_s: float,
        expected_type: type[_MessageT],
        state: ProtocolState,
        pass_index: int | None,
    ) -> _MessageT:
        try:
            available = self._connection.poll(timeout_s)
        except (BrokenPipeError, EOFError, OSError) as exc:
            raise self._endpoint_error(
                type(exc).__name__,
                "worker response poll failed",
                state,
                pass_index,
            ) from exc
        if not available:
            exception_type = (
                "WorkerExitError"
                if not self.is_alive and self.exit_code not in (None, 0)
                else "TimeoutError"
            )
            raise self._endpoint_error(
                exception_type,
                "worker response was unavailable before the deadline",
                state,
                pass_index,
            )
        try:
            message = self._connection.recv()
        except (BrokenPipeError, EOFError, OSError) as exc:
            raise self._endpoint_error(
                type(exc).__name__,
                "worker response pipe closed unexpectedly",
                state,
                pass_index,
            ) from exc
        if isinstance(message, ErrorMessage):
            raise BenchmarkCoordinationError(message.error)
        if not isinstance(message, expected_type):
            raise self._endpoint_error(
                "UnexpectedWorkerMessage",
                "worker returned an unexpected message type",
                state,
                pass_index,
            )
        if not self.is_alive and self.exit_code not in (None, 0):
            raise self._endpoint_error(
                "WorkerExitError",
                "worker exited abnormally after responding",
                state,
                pass_index,
            )
        return cast(_MessageT, message)

    def _endpoint_error(
        self,
        exception_type: str,
        message: str,
        state: ProtocolState,
        pass_index: int | None,
    ) -> BenchmarkCoordinationError:
        return BenchmarkCoordinationError(
            WorkerError(
                exception_type=exception_type,
                message=message,
                role=self._spec.role,
                pid=self._process.pid or os.getpid(),
                protocol_state=state,
                pass_index=pass_index,
                stderr_path=None,
            )
        )

    def _close_connection(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True


class BenchmarkCoordinator:
    def __init__(
        self,
        *,
        endpoint_factory: Callable[[WorkerSpec], WorkerEndpoint] | None = None,
        ready_timeout_s: float = 900.0,
        pass_timeout_s: float = 7200.0,
        shutdown_timeout_s: float = 30.0,
    ) -> None:
        self._ready_timeout_s = _positive_timeout(ready_timeout_s, "ready_timeout_s")
        self._pass_timeout_s = _positive_timeout(pass_timeout_s, "pass_timeout_s")
        self._shutdown_timeout_s = _positive_timeout(
            shutdown_timeout_s, "shutdown_timeout_s"
        )
        if endpoint_factory is None:
            context = get_context("spawn")
            self._endpoint_factory = lambda spec: _SpawnWorkerEndpoint(spec, context)
        elif callable(endpoint_factory):
            self._endpoint_factory = endpoint_factory
        else:
            raise TypeError("endpoint_factory must be callable")

    def run(
        self,
        *,
        reference_spec: WorkerSpec,
        candidate_spec: WorkerSpec,
        image_keys: tuple[str, ...],
        passes: int,
        first_order: Literal["AB", "BA"],
    ) -> BenchmarkExecution:
        normalized_keys = _validate_request(
            reference_spec,
            candidate_spec,
            image_keys,
            passes,
            first_order,
        )
        started_at_utc = datetime.now(UTC).isoformat()
        endpoints: list[tuple[WorkerSpec, WorkerEndpoint]] = []
        reference_metadata: WorkerMetadata | None = None
        candidate_metadata: WorkerMetadata | None = None
        phase_state = ProtocolState.CREATED
        active_pass: int | None = None
        active_spec: WorkerSpec | None = None

        try:
            reference_endpoint = self._endpoint_factory(reference_spec)
            endpoints.append((reference_spec, reference_endpoint))
            candidate_endpoint = self._endpoint_factory(candidate_spec)
            endpoints.append((candidate_spec, candidate_endpoint))

            phase_state = ProtocolState.PREPARING
            active_spec = reference_spec
            reference_metadata = reference_endpoint.prepare(self._ready_timeout_s)
            _validate_ready(reference_spec, reference_metadata)
            active_spec = candidate_spec
            candidate_metadata = candidate_endpoint.prepare(self._ready_timeout_s)
            _validate_ready(candidate_spec, candidate_metadata)
            _validate_ready_pair(reference_metadata, candidate_metadata)
            _require_endpoint_alive(reference_spec, reference_endpoint, reference_metadata)
            _require_endpoint_alive(candidate_spec, candidate_endpoint, candidate_metadata)

            coordinated: list[CoordinatedPass] = []
            phase_state = ProtocolState.RUNNING_PASS
            for pass_index in range(passes):
                active_pass = pass_index
                order = _pass_order(first_order, pass_index)
                command = RunPassCommand(pass_index, normalized_keys)
                if order == "AB":
                    active_spec = reference_spec
                    reference_result = reference_endpoint.run_pass(
                        command, self._pass_timeout_s
                    )
                    _validate_pass_result(
                        reference_spec,
                        reference_metadata,
                        command,
                        reference_result,
                    )
                    active_spec = candidate_spec
                    candidate_result = candidate_endpoint.run_pass(
                        command, self._pass_timeout_s
                    )
                    _validate_pass_result(
                        candidate_spec,
                        candidate_metadata,
                        command,
                        candidate_result,
                    )
                else:
                    active_spec = candidate_spec
                    candidate_result = candidate_endpoint.run_pass(
                        command, self._pass_timeout_s
                    )
                    _validate_pass_result(
                        candidate_spec,
                        candidate_metadata,
                        command,
                        candidate_result,
                    )
                    active_spec = reference_spec
                    reference_result = reference_endpoint.run_pass(
                        command, self._pass_timeout_s
                    )
                    _validate_pass_result(
                        reference_spec,
                        reference_metadata,
                        command,
                        reference_result,
                    )
                coordinated.append(
                    CoordinatedPass(
                        pass_index,
                        order,
                        reference_result,
                        candidate_result,
                    )
                )
            active_pass = None
        except BaseException as exc:
            failure = _as_coordination_error(
                exc,
                active_spec,
                reference_metadata,
                candidate_metadata,
                phase_state,
                active_pass,
            )
            _stop_after_failure(endpoints, self._shutdown_timeout_s)
            raise failure from exc

        try:
            _graceful_stop(endpoints, self._shutdown_timeout_s)
        except BaseException as exc:
            failure = _as_coordination_error(
                exc,
                active_spec,
                reference_metadata,
                candidate_metadata,
                ProtocolState.STOPPING,
                None,
            )
            _terminate_survivors(endpoints)
            raise failure from exc

        return BenchmarkExecution(
            reference_worker=reference_metadata,
            candidate_worker=candidate_metadata,
            passes=tuple(coordinated),
            started_at_utc=started_at_utc,
            completed_at_utc=datetime.now(UTC).isoformat(),
        )


def _positive_timeout(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite positive number")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return timeout


def _validate_request(
    reference_spec: WorkerSpec,
    candidate_spec: WorkerSpec,
    image_keys: tuple[str, ...],
    passes: int,
    first_order: str,
) -> tuple[str, ...]:
    if not isinstance(reference_spec, WorkerSpec) or not isinstance(
        candidate_spec, WorkerSpec
    ):
        raise TypeError("reference_spec and candidate_spec must be WorkerSpec values")
    if reference_spec.role != "reference" or candidate_spec.role != "candidate":
        raise ValueError("worker specs must have reference and candidate roles")
    if type(passes) is not int or passes < 3:
        raise ValueError("passes must be an integer of at least 3")
    if first_order not in {"AB", "BA"}:
        raise ValueError("first_order must be AB or BA")
    return RunPassCommand(0, image_keys).image_keys


def _validate_ready(spec: WorkerSpec, metadata: WorkerMetadata) -> None:
    if not isinstance(metadata, WorkerMetadata):
        raise ValueError("READY payload must contain WorkerMetadata")
    if metadata.role != spec.role:
        raise ValueError("READY role did not match WorkerSpec")
    runtime = metadata.resolved_runtime
    if runtime.mode != spec.mode:
        raise ValueError("READY mode did not match WorkerSpec")
    for key, expected in spec.runtime_overrides:
        if key == "cpu_affinity" and expected == "all":
            continue
        if expected is None:
            continue
        if hasattr(runtime, key) and getattr(runtime, key) != expected:
            raise ValueError(f"READY runtime {key} did not match WorkerSpec")
    if dict(metadata.artifact_hashes) != dict(spec.expected_artifact_hashes):
        raise ValueError("READY artifact hashes did not match WorkerSpec")
    _validate_detector_threshold(metadata)
    _validate_warmup(spec, metadata)


def _validate_detector_threshold(metadata: WorkerMetadata) -> None:
    detector = dict(metadata.detector_metadata)
    score = detector.get("score_threshold")
    calibrated = detector.get("calibration_score_threshold")
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(float(score))
        or isinstance(calibrated, bool)
        or not isinstance(calibrated, (int, float))
        or not math.isfinite(float(calibrated))
        or float(score) != float(calibrated)
    ):
        raise ValueError("READY detector threshold metadata was inconsistent")


def _validate_warmup(spec: WorkerSpec, metadata: WorkerMetadata) -> None:
    warmup = metadata.warmup
    expected_shape = tuple(
        (repetition, profile)
        for repetition in range(1, spec.warmup_repetitions + 1)
        for profile in ("E", "M", "H")
    )
    actual_shape = tuple((image.repetition, image.profile) for image in warmup.images)
    if warmup.repetitions != spec.warmup_repetitions or actual_shape != expected_shape:
        raise ValueError("READY warm-up evidence did not match WorkerSpec")
    first_keys = tuple(image.key for image in warmup.images[:3])
    for offset in range(3, len(warmup.images), 3):
        if tuple(image.key for image in warmup.images[offset : offset + 3]) != first_keys:
            raise ValueError("READY warm-up image keys changed between repetitions")
    if any(
        image.stage_counts.canonical != 1
        or image.stage_counts.detector != 1
        or image.stage_counts.repvit < 1
        or image.stage_counts.dinov3_global_local != 1
        or image.stage_counts.fusion != 1
        for image in warmup.images
    ):
        raise ValueError("READY warm-up did not execute every required stage")


def _validate_ready_pair(
    reference: WorkerMetadata,
    candidate: WorkerMetadata,
) -> None:
    if reference.pid == candidate.pid:
        raise ValueError("READY workers must use two distinct processes")
    shared_runtime_fields = (
        "device",
        "precision",
        "intra_op_threads",
        "inter_op_threads",
        "cpu_affinity",
    )
    if any(
        getattr(reference.resolved_runtime, field)
        != getattr(candidate.resolved_runtime, field)
        for field in shared_runtime_fields
    ):
        raise ValueError("READY worker CPU runtimes did not match")
    if dict(reference.detector_metadata) != dict(candidate.detector_metadata):
        raise ValueError("READY worker detector metadata did not match")
    if dict(reference.artifact_hashes) != dict(candidate.artifact_hashes):
        raise ValueError("READY worker artifact hashes did not match")
    reference_warmup = tuple(
        (image.key, image.profile, image.repetition, image.stage_counts)
        for image in reference.warmup.images
    )
    candidate_warmup = tuple(
        (image.key, image.profile, image.repetition, image.stage_counts)
        for image in candidate.warmup.images
    )
    if reference_warmup != candidate_warmup:
        raise ValueError("READY worker warm-up evidence did not match")


def _require_endpoint_alive(
    spec: WorkerSpec,
    endpoint: WorkerEndpoint,
    metadata: WorkerMetadata,
) -> None:
    if endpoint.is_alive:
        return
    raise BenchmarkCoordinationError(
        WorkerError(
            exception_type="WorkerExitError",
            message="worker exited after READY and before pass 0",
            role=spec.role,
            pid=metadata.pid,
            protocol_state=ProtocolState.READY,
            pass_index=None,
            stderr_path=metadata.stderr_path,
        )
    )


def _validate_pass_result(
    spec: WorkerSpec,
    metadata: WorkerMetadata,
    command: RunPassCommand,
    result: PassResult,
) -> None:
    if not isinstance(result, PassResult):
        raise ValueError("worker pass payload must contain PassResult")
    if result.role != spec.role:
        raise ValueError("worker pass result role did not match its WorkerSpec")
    if result.worker_pid != metadata.pid:
        raise ValueError("worker pass result PID did not match READY")
    if result.pass_index != command.pass_index:
        raise ValueError("worker pass result index did not match the command")
    if tuple(row.key for row in result.rows) != command.image_keys:
        raise ValueError("worker pass result keys did not match the ordered command")


def _pass_order(first_order: str, pass_index: int) -> Literal["AB", "BA"]:
    if pass_index % 2 == 0:
        return cast(Literal["AB", "BA"], first_order)
    return "BA" if first_order == "AB" else "AB"


def _graceful_stop(
    endpoints: list[tuple[WorkerSpec, WorkerEndpoint]],
    timeout_s: float,
) -> None:
    errors: list[BaseException] = []
    for _, endpoint in endpoints:
        try:
            endpoint.shutdown(timeout_s)
        except BaseException as exc:
            errors.append(exc)
    if not errors and any(endpoint.is_alive for _, endpoint in endpoints):
        errors.append(RuntimeError("worker survived graceful shutdown"))
    if errors:
        raise errors[0]


def _stop_after_failure(
    endpoints: list[tuple[WorkerSpec, WorkerEndpoint]],
    timeout_s: float,
) -> None:
    for _, endpoint in endpoints:
        try:
            endpoint.shutdown(timeout_s)
        except BaseException:
            pass
    _terminate_survivors(endpoints)


def _terminate_survivors(
    endpoints: list[tuple[WorkerSpec, WorkerEndpoint]],
) -> None:
    for _, endpoint in endpoints:
        try:
            alive = endpoint.is_alive
        except BaseException:
            alive = True
        if alive:
            try:
                endpoint.terminate()
            except BaseException:
                pass


def _as_coordination_error(
    exc: BaseException,
    active_spec: WorkerSpec | None,
    reference_metadata: WorkerMetadata | None,
    candidate_metadata: WorkerMetadata | None,
    state: ProtocolState,
    pass_index: int | None,
) -> BenchmarkCoordinationError:
    if isinstance(exc, BenchmarkCoordinationError):
        return exc
    metadata = None
    if active_spec is not None:
        metadata = (
            reference_metadata
            if active_spec.role == "reference"
            else candidate_metadata
        )
    message = " ".join(str(exc).split())
    if not message:
        message = "coordinator operation failed"
    return BenchmarkCoordinationError(
        WorkerError(
            exception_type=type(exc).__name__,
            message=message[:500],
            role=None if active_spec is None else active_spec.role,
            pid=os.getpid() if metadata is None else metadata.pid,
            protocol_state=state,
            pass_index=pass_index,
            stderr_path=None if metadata is None else metadata.stderr_path,
        )
    )
