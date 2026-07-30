from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_benchmark_coordinator import (
    BenchmarkCoordinationError,
    BenchmarkCoordinator,
)
from bakery_scanner.e2e.cpu_benchmark_protocol import ProtocolState, WorkerSpec
from .spawn_benchmark_fixture import (
    CONTROLLED_CRASH_COMMAND,
    CONTROLLED_CRASH_EXIT_CODE,
    FIXTURE_ARTIFACT_HASHES,
    FIXTURE_DETECTOR_METADATA,
    fake_worker_process_main,
    spawn_fixture_endpoint_factory,
)


_ROOT = Path(__file__).resolve().parents[2]


def _spec(role: str, mode: str) -> WorkerSpec:
    return WorkerSpec(
        role=role,
        mode=mode,
        package_root=_ROOT,
        classifier_config=_ROOT / "configs" / "cpu_rfdetr_classifier_policy.yaml",
        sample_profile="batch2_e3_m3_h3",
        runtime_overrides=(
            ("mode", mode),
            ("intra_op_threads", 1),
            ("inter_op_threads", 1),
        ),
        expected_artifact_hashes=FIXTURE_ARTIFACT_HASHES,
    )


def _coordinator(endpoint_factory) -> BenchmarkCoordinator:
    return BenchmarkCoordinator(
        endpoint_factory=endpoint_factory,
        ready_timeout_s=10.0,
        pass_timeout_s=10.0,
        shutdown_timeout_s=10.0,
        trusted_detector_metadata_loader=lambda spec: dict(
            FIXTURE_DETECTOR_METADATA
        ),
    )


@pytest.mark.skipif(
    multiprocessing.get_start_method(allow_none=True) == "forkserver",
    reason="test requires a spawn-capable platform",
)
def test_two_spawned_workers_remain_persistent_across_ab_ba_passes():
    factory = spawn_fixture_endpoint_factory(fake_worker_process_main)
    execution = _coordinator(factory).run(
        reference_spec=_spec("reference", "serial_reference"),
        candidate_spec=_spec("candidate", "batch_pytorch"),
        image_keys=("e", "m", "h"),
        passes=3,
        first_order="AB",
    )

    assert execution.reference_worker.pid != execution.candidate_worker.pid
    assert tuple(item.order for item in execution.passes) == ("AB", "BA", "AB")
    assert tuple(item.pass_index for item in execution.passes) == (0, 1, 2)
    assert tuple(
        item.reference.worker_pid for item in execution.passes
    ) == (execution.reference_worker.pid,) * 3
    assert tuple(
        item.candidate.worker_pid for item in execution.passes
    ) == (execution.candidate_worker.pid,) * 3
    assert tuple(
        tuple(row.key for row in item.reference.rows)
        for item in execution.passes
    ) == (("e", "m", "h"),) * 3
    assert tuple(
        tuple(row.key for row in item.candidate.rows)
        for item in execution.passes
    ) == (("e", "m", "h"),) * 3
    assert factory.endpoints["reference"].is_alive is False
    assert factory.endpoints["candidate"].is_alive is False
    assert factory.endpoints["reference"].exit_code == 0
    assert factory.endpoints["candidate"].exit_code == 0


@pytest.mark.skipif(
    multiprocessing.get_start_method(allow_none=True) == "forkserver",
    reason="test requires a spawn-capable platform",
)
def test_abnormal_spawned_worker_exit_is_structured_and_peer_is_finalized():
    factory = spawn_fixture_endpoint_factory(fake_worker_process_main)

    with pytest.raises(BenchmarkCoordinationError) as caught:
        _coordinator(factory).run(
            reference_spec=_spec("reference", "serial_reference"),
            candidate_spec=_spec("candidate", "batch_pytorch"),
            image_keys=CONTROLLED_CRASH_COMMAND.image_keys,
            passes=3,
            first_order="BA",
        )

    failure = caught.value.failure
    assert failure.exception_type in {"EOFError", "WorkerExitError"}
    assert failure.role == "candidate"
    assert failure.pid == factory.endpoints["candidate"].pid
    assert failure.protocol_state is ProtocolState.RUNNING_PASS
    assert failure.pass_index == 0
    assert factory.endpoints["candidate"].is_alive is False
    assert factory.endpoints["candidate"].exit_code == CONTROLLED_CRASH_EXIT_CODE
    assert factory.endpoints["reference"].is_alive is False
    assert factory.endpoints["reference"].exit_code == 0
