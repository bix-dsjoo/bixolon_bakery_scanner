"""Lightweight importable worker target for real ``spawn`` lifecycle tests."""

from __future__ import annotations

import multiprocessing
import os
import sys
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    ErrorMessage,
    PassResult,
    PassResultMessage,
    PrepareCommand,
    ProtocolState,
    ReadyMessage,
    ResolvedRuntime,
    RunPassCommand,
    ShutdownCommand,
    StoppedMessage,
    WarmupEvidence,
    WarmupImageEvidence,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerError,
    WorkerMetadata,
    WorkerSpec,
)


FIXTURE_ARTIFACT_HASHES = (("fixture_sha256", "a" * 64),)
FIXTURE_DETECTOR_METADATA = (
    ("artifact_id", "rfdetr_large_bakery_v1"),
    ("score_threshold", 0.5),
    ("calibration_score_threshold", 0.5),
    ("checkpoint_file", "checkpoint.pth"),
    ("manifest_sha256", "b" * 64),
    ("checkpoint_sha256", "c" * 64),
    ("calibration_sha256", "d" * 64),
)
CONTROLLED_CRASH_COMMAND = RunPassCommand(
    pass_index=0,
    image_keys=("fixture/crash",),
)
CONTROLLED_CRASH_EXIT_CODE = 23


class SpawnFixtureEndpointFactory:
    """Create real spawn endpoints while retaining lifecycle observations."""

    def __init__(self, process_target: Callable[[Connection], None]) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._process_target = process_target
        self.endpoints: dict[str, Any] = {}

    def __call__(self, spec: WorkerSpec) -> Any:
        # Keep this import out of the spawned fixture module's import path:
        # importing the production coordinator also imports the real model worker.
        from bakery_scanner.e2e.cpu_benchmark_coordinator import _SpawnWorkerEndpoint

        endpoint = _SpawnWorkerEndpoint(
            spec,
            self._context,
            process_target=self._process_target,
        )
        self.endpoints[spec.role] = endpoint
        return endpoint


def spawn_fixture_endpoint_factory(
    process_target: Callable[[Connection], None],
) -> SpawnFixtureEndpointFactory:
    return SpawnFixtureEndpointFactory(process_target)


def fake_worker_process_main(connection: Connection) -> None:
    """Implement the production protocol without importing model runtimes."""
    pid = os.getpid()
    spec: WorkerSpec | None = None
    state = ProtocolState.CREATED
    pass_index: int | None = None
    try:
        if "torch" in sys.modules:
            raise RuntimeError("lightweight spawn fixture imported torch")
        prepare = connection.recv()
        if not isinstance(prepare, PrepareCommand):
            raise TypeError("first worker command must be PrepareCommand")
        spec = prepare.spec
        state = ProtocolState.PREPARING
        connection.send(ReadyMessage(_metadata(spec, pid)))
        state = ProtocolState.READY

        while True:
            command = connection.recv()
            if isinstance(command, RunPassCommand):
                pass_index = command.pass_index
                state = ProtocolState.RUNNING_PASS
                if command == CONTROLLED_CRASH_COMMAND:
                    os._exit(CONTROLLED_CRASH_EXIT_CODE)
                result = PassResult(
                    role=spec.role,
                    worker_pid=pid,
                    pass_index=command.pass_index,
                    rows=tuple(_row(key) for key in command.image_keys),
                )
                connection.send(PassResultMessage(result))
                pass_index = None
                state = ProtocolState.READY
                continue
            if isinstance(command, ShutdownCommand):
                state = ProtocolState.STOPPING
                connection.send(StoppedMessage(role=spec.role, pid=pid))
                state = ProtocolState.STOPPED
                return
            raise TypeError("worker command type was not recognized")
    except (BrokenPipeError, EOFError, OSError):
        return
    except BaseException as exc:
        role = None if spec is None else spec.role
        try:
            connection.send(
                ErrorMessage(
                    WorkerError(
                        exception_type=type(exc).__name__,
                        message=str(exc) or "spawn fixture worker failed",
                        role=role,
                        pid=pid,
                        protocol_state=state,
                        pass_index=pass_index,
                        stderr_path=None,
                    )
                )
            )
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def _metadata(spec: WorkerSpec, pid: int) -> WorkerMetadata:
    return WorkerMetadata(
        role=spec.role,
        pid=pid,
        resolved_runtime=_runtime(spec),
        environment=WorkerEnvironment(
            python_version="spawn-fixture",
            pytorch_version="not-imported",
            torchvision_version="not-imported",
            numpy_version="not-imported",
            os_name=os.name,
            os_version="spawn-fixture",
            logical_cpu_count=1,
            inherited_affinity=(0,),
            filesystem_encoding="utf-8",
            default_encoding="utf-8",
            utf8_mode=1,
            gc_enabled=True,
        ),
        detector_metadata=FIXTURE_DETECTOR_METADATA,
        artifact_hashes=spec.expected_artifact_hashes,
        warmup=_warmup(),
        stderr_path=spec.package_root / f"{spec.role}.spawn-fixture.stderr.log",
    )


def _runtime(spec: WorkerSpec) -> ResolvedRuntime:
    overrides = dict(spec.runtime_overrides)
    serial = spec.mode == "serial_reference"
    return ResolvedRuntime(
        mode=spec.mode,
        device="CPU",
        precision="FP32",
        intra_op_threads=int(overrides.get("intra_op_threads", 1)),
        inter_op_threads=int(overrides.get("inter_op_threads", 1)),
        cpu_affinity=(0,),
        repvit_microbatch_objects=1 if serial else "all",
        dinov3_microbatch_objects=1 if serial else "all",
        compile_models=(),
    )


def _warmup() -> WarmupEvidence:
    images = tuple(
        WarmupImageEvidence(
            key=f"warmup/{profile.lower()}",
            profile=profile,
            repetition=repetition,
            started_at_utc="2026-07-30T00:00:00+00:00",
            completed_at_utc="2026-07-30T00:00:01+00:00",
            stage_counts=WarmupStageCounts(1, 1, 1, 1, 1),
        )
        for repetition in (1, 2)
        for profile in ("E", "M", "H")
    )
    return WarmupEvidence(repetitions=2, images=images)


def _row(key: str) -> BenchmarkImageRow:
    return BenchmarkImageRow(
        key=key,
        profile={"e": "E", "m": "M", "h": "H"}[key],
        object_count=0,
        total_ms=1.0,
        records=(),
        false_positive_proposal_indices=(),
        canonical_ms=0.1,
        detector_ms=0.2,
        crop_ms=0.1,
        repvit_ms=0.2,
        dinov3_ms=0.2,
        fusion_ms=0.1,
        dino_object_count=0,
        registered_count=0,
        unknown_count=0,
    )
