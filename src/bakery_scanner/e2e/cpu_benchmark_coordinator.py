"""Persistent spawn coordination for isolated CPU benchmark workers."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing import get_context
from multiprocessing.connection import Connection
from pathlib import Path
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

    def finalize(self) -> None: ...

    @property
    def pid(self) -> int: ...

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
_DETECTOR_DIRECTORY = "rfdetr_large_bakery_v1"
_SHA256_LENGTH = 64


class _SpawnWorkerEndpoint:
    """One duplex pipe and one persistent spawn-created child process."""

    def __init__(
        self,
        spec: WorkerSpec,
        context,
        *,
        process_target: Callable[[Connection], None] = worker_process_main,
    ) -> None:
        self._spec = spec
        self._connection: Connection
        parent_connection, child_connection = context.Pipe(duplex=True)
        self._connection = parent_connection
        self._process = context.Process(
            target=process_target,
            args=(child_connection,),
            name=f"cpu-benchmark-{spec.role}",
        )
        self._connection_closed = False
        self._process_closed = False
        self._finalized = False
        self._final_exit_code: int | None = None
        try:
            self._process.start()
            process_pid = self._process.pid
            if process_pid is None:
                raise RuntimeError("spawned worker did not receive a PID")
            self._pid = process_pid
        except BaseException:
            parent_connection.close()
            try:
                self._process.close()
            except ValueError:
                pass
            raise
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
        if self._finalized:
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

    def terminate(self) -> None:
        if self.is_alive:
            self._process.terminate()
            self._process.join(5.0)
            if self.is_alive:
                kill = getattr(self._process, "kill", None)
                if callable(kill):
                    kill()
                    self._process.join(5.0)

    def finalize(self) -> None:
        if self._finalized:
            return
        if self.is_alive:
            raise self._endpoint_error(
                "WorkerLifecycleError",
                "worker must stop before endpoint finalization",
                ProtocolState.STOPPING,
                None,
            )
        self._close_connection()
        try:
            self._process.join(0)
            self._final_exit_code = self._process.exitcode
            self._process.close()
            self._process_closed = True
        finally:
            self._finalized = True

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    @property
    def is_connection_closed(self) -> bool:
        return self._connection_closed

    @property
    def is_process_closed(self) -> bool:
        return self._process_closed

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def is_alive(self) -> bool:
        if self._finalized:
            return False
        return self._process.is_alive()

    @property
    def exit_code(self) -> int | None:
        if self._finalized:
            return self._final_exit_code
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
                pid=self._pid,
                protocol_state=state,
                pass_index=pass_index,
                stderr_path=None,
            )
        )

    def _close_connection(self) -> None:
        if not self._connection_closed:
            self._connection.close()
            self._connection_closed = True


class BenchmarkCoordinator:
    def __init__(
        self,
        *,
        endpoint_factory: Callable[[WorkerSpec], WorkerEndpoint] | None = None,
        ready_timeout_s: float = 900.0,
        pass_timeout_s: float = 7200.0,
        shutdown_timeout_s: float = 30.0,
        trusted_detector_metadata_loader: (
            Callable[[WorkerSpec], Mapping[str, object]] | None
        ) = None,
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
        if trusted_detector_metadata_loader is None:
            self._trusted_detector_metadata_loader = (
                _load_trusted_detector_metadata
            )
        elif callable(trusted_detector_metadata_loader):
            self._trusted_detector_metadata_loader = (
                trusted_detector_metadata_loader
            )
        else:
            raise TypeError("trusted_detector_metadata_loader must be callable")

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
        try:
            trusted_detector_metadata = _normalize_trusted_detector_metadata(
                self._trusted_detector_metadata_loader(reference_spec)
            )
        except BaseException as exc:
            failure = _as_coordination_error(
                exc,
                reference_spec,
                None,
                None,
                ProtocolState.CREATED,
                None,
            )
            raise failure from exc
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
            _validate_ready(
                reference_spec,
                reference_endpoint,
                reference_metadata,
                trusted_detector_metadata,
            )
            active_spec = candidate_spec
            candidate_metadata = candidate_endpoint.prepare(self._ready_timeout_s)
            _validate_ready(
                candidate_spec,
                candidate_endpoint,
                candidate_metadata,
                trusted_detector_metadata,
            )
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


def _load_trusted_detector_metadata(
    spec: WorkerSpec,
) -> Mapping[str, object]:
    manifest_path = (
        spec.package_root
        / "models"
        / _DETECTOR_DIRECTORY
        / "manifest.json"
    )
    try:
        encoded = manifest_path.read_bytes()
        manifest = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "trusted RF-DETR manifest must be readable UTF-8 JSON"
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("trusted RF-DETR manifest must be a schema v1 object")
    if manifest.get("source_label") != _DETECTOR_DIRECTORY:
        raise ValueError(
            "trusted RF-DETR manifest source label did not match its directory"
        )
    checkpoint = manifest.get("checkpoint")
    calibration = manifest.get("calibration")
    if not isinstance(checkpoint, dict) or not isinstance(calibration, dict):
        raise ValueError(
            "trusted RF-DETR manifest must declare checkpoint and calibration"
        )
    checkpoint_file = _manifest_file(checkpoint.get("file"), "checkpoint")
    _manifest_file(calibration.get("file"), "calibration")
    checkpoint_sha256 = _manifest_sha256(
        checkpoint.get("sha256"), "checkpoint"
    )
    calibration_sha256 = _manifest_sha256(
        calibration.get("sha256"), "calibration"
    )
    threshold = _trusted_threshold(manifest.get("score_threshold"))
    manifest_sha256 = hashlib.sha256(encoded).hexdigest()
    expected = dict(spec.expected_artifact_hashes)
    for field in (
        "rfdetr_manifest_sha256",
        "detector_manifest_sha256",
    ):
        if field in expected and expected[field] != manifest_sha256:
            raise ValueError(
                "trusted RF-DETR manifest SHA-256 did not match WorkerSpec"
            )
    return {
        "artifact_id": _DETECTOR_DIRECTORY,
        "score_threshold": threshold,
        "manifest_sha256": manifest_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "calibration_sha256": calibration_sha256,
        "checkpoint_file": checkpoint_file,
    }


def _normalize_trusted_detector_metadata(
    value: Mapping[str, object],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(
            "trusted detector metadata loader must return a mapping"
        )
    metadata = dict(value)
    artifact_id = metadata.get("artifact_id")
    checkpoint_file = metadata.get("checkpoint_file")
    if artifact_id != _DETECTOR_DIRECTORY:
        raise ValueError("trusted detector artifact identity was invalid")
    _manifest_file(checkpoint_file, "checkpoint")
    for field in (
        "manifest_sha256",
        "checkpoint_sha256",
        "calibration_sha256",
    ):
        _manifest_sha256(metadata.get(field), field)
    metadata["score_threshold"] = _trusted_threshold(
        metadata.get("score_threshold")
    )
    return metadata


def _manifest_file(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).name != value
    ):
        raise ValueError(
            f"trusted RF-DETR {field} file must be a non-empty file name"
        )
    return value


def _manifest_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(
            f"trusted RF-DETR {field} SHA-256 must be lowercase hexadecimal"
        )
    return value


def _trusted_threshold(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(
            "trusted RF-DETR manifest threshold must be finite and in [0, 1]"
        )
    return float(value)


def _validate_ready(
    spec: WorkerSpec,
    endpoint: WorkerEndpoint,
    metadata: WorkerMetadata,
    trusted_detector_metadata: Mapping[str, object],
) -> None:
    if not isinstance(metadata, WorkerMetadata):
        raise ValueError("READY payload must contain WorkerMetadata")
    if metadata.role != spec.role:
        raise ValueError("READY role did not match WorkerSpec")
    if metadata.pid != endpoint.pid:
        raise ValueError("READY PID did not match the spawned endpoint process")
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
    _validate_detector_metadata(metadata, trusted_detector_metadata)
    _validate_warmup(spec, metadata)


def _validate_detector_metadata(
    metadata: WorkerMetadata,
    trusted: Mapping[str, object],
) -> None:
    detector = dict(metadata.detector_metadata)
    score = detector.get("score_threshold")
    calibrated = detector.get("calibration_score_threshold")
    trusted_score = trusted["score_threshold"]
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(float(score))
        or not 0.0 <= float(score) <= 1.0
        or isinstance(calibrated, bool)
        or not isinstance(calibrated, (int, float))
        or not math.isfinite(float(calibrated))
        or not 0.0 <= float(calibrated) <= 1.0
        or float(score) != float(calibrated)
        or float(score) != trusted_score
    ):
        raise ValueError(
            "READY detector threshold did not match the trusted manifest"
        )
    for field in (
        "artifact_id",
        "manifest_sha256",
        "checkpoint_sha256",
        "calibration_sha256",
        "checkpoint_file",
    ):
        if detector.get(field) != trusted[field]:
            raise ValueError(
                f"READY detector {field} did not match the trusted manifest"
            )


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
    if not errors and _has_survivors(endpoints):
        errors.append(RuntimeError("worker survived graceful shutdown"))
    if errors:
        _terminate_survivors(endpoints)
    errors.extend(_finalize_all(endpoints))
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
    _finalize_all(endpoints)


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


def _has_survivors(
    endpoints: list[tuple[WorkerSpec, WorkerEndpoint]],
) -> bool:
    for _, endpoint in endpoints:
        try:
            if endpoint.is_alive:
                return True
        except BaseException:
            return True
    return False


def _finalize_all(
    endpoints: list[tuple[WorkerSpec, WorkerEndpoint]],
) -> list[BaseException]:
    errors: list[BaseException] = []
    for _, endpoint in endpoints:
        try:
            endpoint.finalize()
        except BaseException as exc:
            errors.append(exc)
    return errors


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
