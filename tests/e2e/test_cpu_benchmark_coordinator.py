from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_benchmark_coordinator import (
    BenchmarkCoordinationError,
    BenchmarkCoordinator,
    _SpawnWorkerEndpoint,
)
from bakery_scanner.e2e.cpu_benchmark_protocol import (
    BenchmarkImageRow,
    PassResult,
    ProtocolState,
    ResolvedRuntime,
    RunPassCommand,
    WarmupEvidence,
    WarmupImageEvidence,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerError,
    WorkerMetadata,
    WorkerSpec,
)


_ROOT = Path(__file__).resolve().parents[2]
_HASH = "a" * 64
_DETECTOR_METADATA = (
    ("artifact_id", "rfdetr_large_bakery_v1"),
    ("score_threshold", 0.5),
    ("calibration_score_threshold", 0.5),
    ("checkpoint_file", "checkpoint.pth"),
    ("manifest_sha256", "b" * 64),
    ("checkpoint_sha256", "c" * 64),
    ("calibration_sha256", "d" * 64),
)


def _worker_spec(role: str, mode: str) -> WorkerSpec:
    return WorkerSpec(
        role=role,
        mode=mode,
        package_root=_ROOT,
        classifier_config=_ROOT / "configs" / "cpu_rfdetr_classifier_policy.yaml",
        sample_profile="batch2_e3_m3_h3",
        runtime_overrides=(
            ("mode", mode),
            ("intra_op_threads", 4),
            ("inter_op_threads", 1),
        ),
        expected_artifact_hashes=(("fixture_sha256", _HASH),),
    )


def _runtime(mode: str) -> ResolvedRuntime:
    return ResolvedRuntime(
        mode=mode,
        device="CPU",
        precision="FP32",
        intra_op_threads=4,
        inter_op_threads=1,
        cpu_affinity=(0, 1, 2, 3),
        repvit_microbatch_objects=1 if mode == "serial_reference" else "all",
        dinov3_microbatch_objects=1 if mode == "serial_reference" else "all",
        compile_models=(),
    )


def _environment() -> WorkerEnvironment:
    return WorkerEnvironment(
        python_version="3.12",
        pytorch_version="2.7",
        torchvision_version="0.22",
        numpy_version="2.2",
        os_name="nt",
        os_version="test",
        logical_cpu_count=4,
        inherited_affinity=(0, 1, 2, 3),
        filesystem_encoding="utf-8",
        default_encoding="utf-8",
        utf8_mode=1,
        gc_enabled=True,
    )


def _warmup() -> WarmupEvidence:
    images = []
    for repetition in (1, 2):
        for profile, key in (("E", "warmup/e"), ("M", "warmup/m"), ("H", "warmup/h")):
            images.append(
                WarmupImageEvidence(
                    key=key,
                    profile=profile,
                    repetition=repetition,
                    started_at_utc="2026-07-30T00:00:00+00:00",
                    completed_at_utc="2026-07-30T00:00:01+00:00",
                    stage_counts=WarmupStageCounts(1, 1, 1, 1, 1),
                )
            )
    return WarmupEvidence(2, tuple(images))


def _metadata(spec: WorkerSpec) -> WorkerMetadata:
    return WorkerMetadata(
        role=spec.role,
        pid=101 if spec.role == "reference" else 202,
        resolved_runtime=_runtime(spec.mode),
        environment=_environment(),
        detector_metadata=_DETECTOR_METADATA,
        artifact_hashes=spec.expected_artifact_hashes,
        warmup=_warmup(),
        stderr_path=_ROOT / f"{spec.role}.stderr.log",
    )


def _write_detector_manifest(root: Path, *, threshold: float) -> str:
    manifest = {
        "schema_version": 1,
        "source_label": "rfdetr_large_bakery_v1",
        "score_threshold": threshold,
        "checkpoint": {
            "file": "checkpoint.pth",
            "sha256": "c" * 64,
        },
        "calibration": {
            "file": "calibration.json",
            "sha256": "d" * 64,
        },
    }
    encoded = json.dumps(
        manifest,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    directory = root / "models" / "rfdetr_large_bakery_v1"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


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


class FakeEndpoint:
    def __init__(
        self,
        spec: WorkerSpec,
        log: list[tuple],
        *,
        metadata: WorkerMetadata | None = None,
        tracker=None,
        failure: str | None = None,
        survive_shutdown: bool = False,
        actual_pid: int | None = None,
    ) -> None:
        self.spec = spec
        self.log = log
        self.metadata = metadata or _metadata(spec)
        self.tracker = tracker
        self.failure = failure
        self.survive_shutdown = survive_shutdown
        self._pid = actual_pid or self.metadata.pid
        self._alive = True
        self._exit_code = None
        self.finalize_calls = 0

    def prepare(self, timeout_s: float) -> WorkerMetadata:
        self.log.append(("prepare", self.spec.role, timeout_s))
        if self.failure == "ready_timeout" and self.spec.role == "reference":
            raise TimeoutError("ready timed out")
        if self.failure == "broken_pipe" and self.spec.role == "reference":
            raise BrokenPipeError("pipe closed")
        if self.failure == "bad_exit" and self.spec.role == "reference":
            self._alive = False
            self._exit_code = 7
            raise EOFError("worker exited")
        return self.metadata

    def run_pass(self, command: RunPassCommand, timeout_s: float) -> PassResult:
        self.log.append(("run", self.spec.role, command.pass_index, command.image_keys))
        if self.tracker is not None:
            self.tracker.enter()
        try:
            if self.tracker is not None:
                time.sleep(0.01)
            if (
                self.failure in {"pass_timeout", "worker_error"}
                and self.spec.role == "candidate"
                and command.pass_index == 0
            ):
                if self.failure == "pass_timeout":
                    raise TimeoutError("pass timed out")
                raise BenchmarkCoordinationError(
                    WorkerError(
                        exception_type="BenchmarkWorkerFailure",
                        message="measured pass failed",
                        role=self.spec.role,
                        pid=self.metadata.pid,
                        protocol_state=ProtocolState.RUNNING_PASS,
                        pass_index=command.pass_index,
                        stderr_path=self.metadata.stderr_path,
                    )
                )
            return PassResult(
                self.spec.role,
                self.metadata.pid,
                command.pass_index,
                tuple(_row(key) for key in command.image_keys),
            )
        finally:
            if self.tracker is not None:
                self.tracker.leave()

    def shutdown(self, timeout_s: float) -> None:
        self.log.append(("shutdown", self.spec.role, timeout_s))
        if not self.survive_shutdown:
            self._alive = False
            self._exit_code = 0

    def terminate(self) -> None:
        self.log.append(("terminate", self.spec.role))
        self._alive = False
        self._exit_code = -15

    def finalize(self) -> None:
        self.log.append(("finalize", self.spec.role))
        self.finalize_calls += 1

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def exit_code(self) -> int | None:
        return self._exit_code


class FakeEndpointFactory:
    def __init__(self, log: list[tuple]) -> None:
        self.log = log
        self.endpoints: list[FakeEndpoint] = []

    def __call__(self, spec: WorkerSpec) -> FakeEndpoint:
        endpoint = FakeEndpoint(spec, self.log)
        self.endpoints.append(endpoint)
        return endpoint


class ConcurrencyTracker:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    def enter(self) -> None:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)

    def leave(self) -> None:
        self.active -= 1


class RecordingHandle:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class DeadRecordingProcess:
    def __init__(self) -> None:
        self.pid = 707
        self.exitcode = 9
        self.start_calls = 0
        self.join_calls = []
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def is_alive(self) -> bool:
        return False

    def join(self, timeout=None) -> None:
        self.join_calls.append(timeout)

    def close(self) -> None:
        self.close_calls += 1


class DeadRecordingContext:
    def __init__(self) -> None:
        self.parent_connection = RecordingHandle()
        self.child_connection = RecordingHandle()
        self.process = DeadRecordingProcess()

    def Pipe(self, *, duplex: bool):
        assert duplex is True
        return self.parent_connection, self.child_connection

    def Process(self, **kwargs):
        return self.process


class TrackingFactory(FakeEndpointFactory):
    def __init__(self, tracker: ConcurrencyTracker) -> None:
        super().__init__([])
        self.tracker = tracker

    def __call__(self, spec: WorkerSpec) -> FakeEndpoint:
        endpoint = FakeEndpoint(spec, self.log, tracker=self.tracker)
        self.endpoints.append(endpoint)
        return endpoint


class FailingFactory(FakeEndpointFactory):
    def __init__(self, failure: str) -> None:
        super().__init__([])
        self.failure = failure

    def __call__(self, spec: WorkerSpec) -> FakeEndpoint:
        endpoint = FakeEndpoint(spec, self.log, failure=self.failure)
        self.endpoints.append(endpoint)
        return endpoint


def _coordinator(**kwargs) -> BenchmarkCoordinator:
    return BenchmarkCoordinator(
        trusted_detector_metadata_loader=lambda spec: dict(
            _DETECTOR_METADATA
        ),
        **kwargs,
    )


def _run(
    coordinator: BenchmarkCoordinator,
    *,
    reference_spec: WorkerSpec | None = None,
    candidate_spec: WorkerSpec | None = None,
):
    return coordinator.run(
        reference_spec=reference_spec
        or _worker_spec("reference", "serial_reference"),
        candidate_spec=candidate_spec
        or _worker_spec("candidate", "batch_pytorch"),
        image_keys=("e", "m", "h"),
        passes=3,
        first_order="AB",
    )


def test_coordinator_prepares_once_and_dispatches_three_alternating_passes():
    log: list[tuple] = []
    coordinator = _coordinator(
        endpoint_factory=FakeEndpointFactory(log),
        ready_timeout_s=900.0,
        pass_timeout_s=7200.0,
        shutdown_timeout_s=30.0,
    )

    execution = _run(coordinator)

    assert [entry for entry in log if entry[0] == "prepare"] == [
        ("prepare", "reference", 900.0),
        ("prepare", "candidate", 900.0),
    ]
    assert [entry[:3] for entry in log if entry[0] == "run"] == [
        ("run", "reference", 0),
        ("run", "candidate", 0),
        ("run", "candidate", 1),
        ("run", "reference", 1),
        ("run", "reference", 2),
        ("run", "candidate", 2),
    ]
    assert tuple(item.order for item in execution.passes) == ("AB", "BA", "AB")


def test_coordinator_never_has_two_measured_requests_in_flight():
    tracker = ConcurrencyTracker()
    coordinator = _coordinator(endpoint_factory=TrackingFactory(tracker))

    _run(coordinator)

    assert tracker.maximum_active == 1


def test_coordinator_rejects_reusing_one_process_for_both_worker_roles():
    log: list[tuple] = []

    def factory(spec: WorkerSpec) -> FakeEndpoint:
        return FakeEndpoint(
            spec,
            log,
            metadata=replace(_metadata(spec), pid=303),
        )

    coordinator = _coordinator(endpoint_factory=factory)

    with pytest.raises(BenchmarkCoordinationError):
        _run(coordinator)

    assert not [entry for entry in log if entry[0] == "run"]


def test_coordinator_binds_each_ready_pid_to_its_actual_endpoint_process():
    log: list[tuple] = []

    def factory(spec: WorkerSpec) -> FakeEndpoint:
        return FakeEndpoint(spec, log, actual_pid=303)

    coordinator = _coordinator(endpoint_factory=factory)

    with pytest.raises(BenchmarkCoordinationError):
        _run(coordinator)

    assert not [entry for entry in log if entry[0] == "run"]


@pytest.mark.parametrize(
    "failure",
    ["ready_timeout", "pass_timeout", "worker_error", "broken_pipe", "bad_exit"],
)
def test_coordinator_converts_worker_failure_to_structured_failure(failure):
    coordinator = _coordinator(endpoint_factory=FailingFactory(failure))

    with pytest.raises(BenchmarkCoordinationError) as raised:
        _run(coordinator)

    assert raised.value.failure.protocol_state is not None
    assert raised.value.failure.exception_type


@pytest.mark.parametrize(
    "target, mutation",
    [
        ("reference", lambda metadata: replace(metadata, role="candidate")),
        (
            "candidate",
            lambda metadata: replace(
                metadata,
                resolved_runtime=replace(
                    metadata.resolved_runtime, mode="serial_reference"
                ),
            ),
        ),
        (
            "candidate",
            lambda metadata: replace(
                metadata,
                resolved_runtime=replace(
                    metadata.resolved_runtime, intra_op_threads=2
                ),
            ),
        ),
        (
            "candidate",
            lambda metadata: replace(
                metadata,
                detector_metadata=tuple(
                    (key, 0.4 if key == "score_threshold" else value)
                    for key, value in metadata.detector_metadata
                ),
            ),
        ),
        (
            "candidate",
            lambda metadata: replace(
                metadata, artifact_hashes=(("fixture_sha256", "f" * 64),)
            ),
        ),
        (
            "candidate",
            lambda metadata: replace(
                metadata,
                warmup=replace(metadata.warmup, images=metadata.warmup.images[:-1]),
            ),
        ),
    ],
    ids=("role", "mode", "runtime", "threshold", "hash", "warmup"),
)
def test_coordinator_rejects_ready_mismatch_before_pass_zero(target, mutation):
    log: list[tuple] = []

    def factory(spec: WorkerSpec) -> FakeEndpoint:
        metadata = _metadata(spec)
        if spec.role == target:
            metadata = mutation(metadata)
        return FakeEndpoint(spec, log, metadata=metadata)

    coordinator = _coordinator(endpoint_factory=factory)

    with pytest.raises(BenchmarkCoordinationError):
        _run(coordinator)

    assert not [entry for entry in log if entry[0] == "run"]


@pytest.mark.parametrize("mutation", ["role", "pass", "keys"])
def test_coordinator_rejects_role_pass_or_key_mismatch(mutation):
    log: list[tuple] = []

    class MismatchingEndpoint(FakeEndpoint):
        def run_pass(
            self, command: RunPassCommand, timeout_s: float
        ) -> PassResult:
            result = super().run_pass(command, timeout_s)
            if self.spec.role != "reference" or command.pass_index != 0:
                return result
            if mutation == "role":
                return replace(result, role="candidate")
            if mutation == "pass":
                return replace(result, pass_index=1)
            return replace(result, rows=tuple(reversed(result.rows)))

    coordinator = _coordinator(
        endpoint_factory=lambda spec: MismatchingEndpoint(spec, log)
    )

    with pytest.raises(BenchmarkCoordinationError):
        _run(coordinator)


def test_coordinator_sends_identical_ordered_keys_and_gracefully_stops_both():
    log: list[tuple] = []
    factory = FakeEndpointFactory(log)

    execution = _run(_coordinator(endpoint_factory=factory))

    assert {
        entry[3] for entry in log if entry[0] == "run"
    } == {("e", "m", "h")}
    assert [entry[:2] for entry in log if entry[0] == "shutdown"] == [
        ("shutdown", "reference"),
        ("shutdown", "candidate"),
    ]
    assert not [entry for entry in log if entry[0] == "terminate"]
    assert [entry for entry in log if entry[0] == "finalize"] == [
        ("finalize", "reference"),
        ("finalize", "candidate"),
    ]
    assert all(endpoint.finalize_calls == 1 for endpoint in factory.endpoints)
    assert execution.reference_worker.role == "reference"
    assert execution.candidate_worker.role == "candidate"


def test_failure_stops_both_and_terminates_only_surviving_endpoint():
    log: list[tuple] = []

    def factory(spec: WorkerSpec) -> FakeEndpoint:
        return FakeEndpoint(
            spec,
            log,
            failure="pass_timeout",
            survive_shutdown=spec.role == "reference",
        )

    with pytest.raises(BenchmarkCoordinationError):
        _run(_coordinator(endpoint_factory=factory))

    assert [entry[:2] for entry in log if entry[0] == "shutdown"] == [
        ("shutdown", "reference"),
        ("shutdown", "candidate"),
    ]
    assert [entry for entry in log if entry[0] == "terminate"] == [
        ("terminate", "reference")
    ]


def test_dead_worker_and_peer_are_each_finalized_once_after_shutdown_attempts():
    factory = FailingFactory("bad_exit")

    with pytest.raises(BenchmarkCoordinationError):
        _run(_coordinator(endpoint_factory=factory))

    assert [entry[:2] for entry in factory.log if entry[0] == "shutdown"] == [
        ("shutdown", "reference"),
        ("shutdown", "candidate"),
    ]
    assert [entry for entry in factory.log if entry[0] == "finalize"] == [
        ("finalize", "reference"),
        ("finalize", "candidate"),
    ]
    assert all(endpoint.finalize_calls == 1 for endpoint in factory.endpoints)


def test_spawn_endpoint_finalizes_dead_pipe_and_process_handles_idempotently():
    context = DeadRecordingContext()
    endpoint = _SpawnWorkerEndpoint(
        _worker_spec("reference", "serial_reference"),
        context,
    )

    with pytest.raises(BenchmarkCoordinationError):
        endpoint.shutdown(1.0)
    endpoint.finalize()
    endpoint.finalize()

    assert endpoint.pid == 707
    assert endpoint.exit_code == 9
    assert context.parent_connection.close_calls == 1
    assert context.child_connection.close_calls == 1
    assert context.process.join_calls == [0]
    assert context.process.close_calls == 1


def test_coordinator_rejects_shared_wrong_threshold_against_parent_manifest(
    tmp_path,
):
    log: list[tuple] = []
    manifest_sha256 = _write_detector_manifest(tmp_path, threshold=0.5)
    reference_spec = replace(
        _worker_spec("reference", "serial_reference"),
        package_root=tmp_path,
    )
    candidate_spec = replace(
        _worker_spec("candidate", "batch_pytorch"),
        package_root=tmp_path,
    )

    def factory(spec: WorkerSpec) -> FakeEndpoint:
        wrong = replace(
            _metadata(spec),
            detector_metadata=tuple(
                (
                    key,
                    0.4
                    if key in {"score_threshold", "calibration_score_threshold"}
                    else manifest_sha256
                    if key == "manifest_sha256"
                    else value,
                )
                for key, value in _DETECTOR_METADATA
            ),
        )
        return FakeEndpoint(spec, log, metadata=wrong)

    with pytest.raises(BenchmarkCoordinationError):
        _run(
            BenchmarkCoordinator(endpoint_factory=factory),
            reference_spec=reference_spec,
            candidate_spec=candidate_spec,
        )

    assert not [entry for entry in log if entry[0] == "run"]


def test_coordinator_rejects_ready_hash_not_computed_from_parent_manifest(
    tmp_path,
):
    log: list[tuple] = []
    _write_detector_manifest(tmp_path, threshold=0.5)
    reference_spec = replace(
        _worker_spec("reference", "serial_reference"),
        package_root=tmp_path,
    )
    candidate_spec = replace(
        _worker_spec("candidate", "batch_pytorch"),
        package_root=tmp_path,
    )

    with pytest.raises(BenchmarkCoordinationError):
        _run(
            BenchmarkCoordinator(
                endpoint_factory=lambda spec: FakeEndpoint(spec, log)
            ),
            reference_spec=reference_spec,
            candidate_spec=candidate_spec,
        )

    assert not [entry for entry in log if entry[0] == "run"]


def test_coordinator_rejects_fewer_than_three_passes_before_spawning():
    calls: list[WorkerSpec] = []
    coordinator = _coordinator(
        endpoint_factory=lambda spec: calls.append(spec)  # type: ignore[arg-type,return-value]
    )

    with pytest.raises(ValueError, match="at least 3"):
        coordinator.run(
            reference_spec=_worker_spec("reference", "serial_reference"),
            candidate_spec=_worker_spec("candidate", "batch_pytorch"),
            image_keys=("e", "m", "h"),
            passes=2,
            first_order="AB",
        )

    assert calls == []
