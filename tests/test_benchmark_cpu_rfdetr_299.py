from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_benchmark_coordinator import (
    BenchmarkCoordinationError,
)
from bakery_scanner.e2e.cpu_benchmark_protocol import (
    ProtocolState,
    WorkerError,
)
from bakery_scanner.e2e.cpu_benchmark_worker import (
    select_benchmark_samples as worker_select_benchmark_samples,
)
from scripts.benchmark_cpu_rfdetr_299 import (
    BenchmarkDependencies,
    BenchmarkOptions,
    main,
    run_benchmark,
    select_benchmark_samples,
)


def test_run_benchmark_delegates_to_two_worker_specs_and_emits_v3(tmp_path):
    coordinator_calls = []
    report_calls = []
    publications = []
    execution = object()
    dependencies = BenchmarkDependencies(
        load_samples=lambda root: tuple(_sample(index) for index in range(299)),
        detector_metadata=lambda root: _detector_metadata(),
        artifact_hashes=lambda root, config, samples: _artifact_hashes(),
        run_coordinator=lambda **kwargs: (
            coordinator_calls.append(kwargs) or execution
        ),
        build_report=lambda **kwargs: (
            report_calls.append(kwargs) or {"schema_version": 3}
        ),
        publish_report=lambda output, report: publications.append(
            (output, report)
        ),
    )

    options = _options(tmp_path, tmp_path / "result")
    report = run_benchmark(options, dependencies)

    call = coordinator_calls[0]
    assert report["schema_version"] == 3
    assert call["reference_spec"].role == "reference"
    assert call["reference_spec"].mode == "serial_reference"
    assert call["candidate_spec"].role == "candidate"
    assert call["candidate_spec"].mode == "batch_pytorch"
    assert call["passes"] == 3
    assert call["image_keys"] == tuple(
        f"fixture/{_profile(index).lower()}_{index:03d}.jpg"
        for index in range(299)
    )
    assert call["reference_spec"].expected_artifact_hashes == (
        ("classifier_config_sha256", "d" * 64),
        ("ordered_image_list_sha256", "e" * 64),
    )
    assert (
        call["reference_spec"].expected_artifact_hashes
        == call["candidate_spec"].expected_artifact_hashes
    )
    assert dict(call["reference_spec"].runtime_overrides) == {
        "mode": "serial_reference",
        "intra_op_threads": 1,
        "repvit_microbatch_objects": 1,
        "dinov3_microbatch_objects": 1,
        "cpu_affinity": "all",
    }
    assert dict(call["candidate_spec"].runtime_overrides) == {
        "mode": "batch_pytorch",
        "intra_op_threads": 1,
        "repvit_microbatch_objects": 1,
        "dinov3_microbatch_objects": 1,
        "cpu_affinity": "all",
    }
    assert report_calls == [
        {
            "execution": execution,
            "samples": tuple(_sample(index) for index in range(299)),
            "detector": _detector_metadata(),
            "artifacts": _artifact_hashes(),
            "sample_profile": "all299",
            "bootstrap_seed": 20260729,
            "coordinator_settings": report_calls[0]["coordinator_settings"],
        }
    ]
    assert publications == [(options.output, report)]


def test_run_benchmark_keeps_omitted_runtime_overrides_out_of_worker_specs(
    tmp_path,
):
    coordinator_calls = []
    dependencies = _dependencies(
        run_coordinator=lambda **kwargs: coordinator_calls.append(kwargs)
        or object(),
    )
    options = replace(
        _options(tmp_path, tmp_path / "result"),
        intra_op_threads=None,
        repvit_microbatch=None,
        dino_microbatch=None,
        cpu_affinity=None,
    )

    run_benchmark(options, dependencies)

    call = coordinator_calls[0]
    assert call["reference_spec"].runtime_overrides == (
        ("mode", "serial_reference"),
    )
    assert call["candidate_spec"].runtime_overrides == (
        ("mode", "batch_pytorch"),
    )


def test_run_benchmark_publishes_sanitized_coordination_failure_and_reraises(
    tmp_path,
):
    failure = WorkerError(
        exception_type="RuntimeError",
        message="worker failed with private detail",
        role="candidate",
        pid=123,
        protocol_state=ProtocolState.RUNNING_PASS,
        pass_index=1,
        stderr_path=None,
    )
    raised = BenchmarkCoordinationError(failure)
    publications = []

    def fail_coordination(**kwargs):
        raise raised

    dependencies = _dependencies(
        run_coordinator=fail_coordination,
        publish_failure=lambda output, error, **kwargs: publications.append(
            (output, error, kwargs)
        ),
    )
    options = _options(tmp_path, tmp_path / "result")

    with pytest.raises(BenchmarkCoordinationError) as caught:
        run_benchmark(options, dependencies)

    assert caught.value is raised
    assert publications[0][0] == options.output
    assert publications[0][1] is failure
    assert publications[0][2]["coordinator_settings"].pass_timeout_s == 7200.0


def test_run_benchmark_publishes_sanitized_report_failure_and_reraises(
    tmp_path,
):
    raised = ValueError("report failed\nwith private detail")
    publications = []

    def fail_report(**kwargs):
        raise raised

    dependencies = _dependencies(
        build_report=fail_report,
        publish_failure=lambda output, error, **kwargs: publications.append(
            (output, error, kwargs)
        ),
    )
    options = _options(tmp_path, tmp_path / "result")

    with pytest.raises(ValueError) as caught:
        run_benchmark(options, dependencies)

    assert caught.value is raised
    error = publications[0][1]
    assert error.exception_type == "ValueError"
    assert error.message == "report failed with private detail"
    assert error.role is None
    assert error.protocol_state is ProtocolState.ERROR


def test_benchmark_refuses_to_overwrite_existing_output(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(FileExistsError, match="overwrite"):
        run_benchmark(_options(tmp_path, output), dependencies=_dependencies())


def test_cli_omits_runtime_overrides_when_not_explicitly_requested(
    monkeypatch,
    tmp_path,
):
    received = []
    monkeypatch.setattr(
        "scripts.benchmark_cpu_rfdetr_299.run_benchmark",
        lambda options, dependencies=None: received.append(options) or {},
    )

    assert main(_required_cli_args(tmp_path)) == 0

    options = received[0]
    assert options.intra_op_threads is None
    assert options.cpu_affinity is None
    assert options.repvit_microbatch is None
    assert options.dino_microbatch is None


def test_cli_defaults_record_fixed_warmup_and_timeouts(monkeypatch, tmp_path):
    received = []
    monkeypatch.setattr(
        "scripts.benchmark_cpu_rfdetr_299.run_benchmark",
        lambda options, dependencies=None: received.append(options) or {},
    )

    assert main(_required_cli_args(tmp_path)) == 0

    assert received[0].warmup_repetitions == 2
    assert received[0].ready_timeout_s == 900.0
    assert received[0].pass_timeout_s == 7200.0
    assert received[0].shutdown_timeout_s == 30.0


def test_cli_accepts_positive_timeout_overrides(monkeypatch, tmp_path):
    received = []
    monkeypatch.setattr(
        "scripts.benchmark_cpu_rfdetr_299.run_benchmark",
        lambda options, dependencies=None: received.append(options) or {},
    )

    assert main(
        _required_cli_args(tmp_path)
        + [
            "--ready-timeout",
            "10",
            "--pass-timeout",
            "20.5",
            "--shutdown-timeout",
            "3",
        ]
    ) == 0

    assert received[0].ready_timeout_s == 10.0
    assert received[0].pass_timeout_s == 20.5
    assert received[0].shutdown_timeout_s == 3.0


@pytest.mark.parametrize(
    "flag",
    ("--ready-timeout", "--pass-timeout", "--shutdown-timeout"),
)
@pytest.mark.parametrize("value", ("0", "-1"))
def test_cli_rejects_non_positive_timeouts(flag, value, tmp_path):
    with pytest.raises(SystemExit):
        main(_required_cli_args(tmp_path) + [flag, value])


@pytest.mark.parametrize("passes", ("0", "1", "2"))
def test_cli_rejects_fewer_than_three_passes(passes, tmp_path):
    with pytest.raises(SystemExit):
        main(_required_cli_args(tmp_path) + ["--passes", passes])


@pytest.mark.parametrize(
    "changes",
    (
        {"warmup_repetitions": 1},
        {"ready_timeout_s": 0.0},
        {"pass_timeout_s": -1.0},
        {"shutdown_timeout_s": float("nan")},
        {"passes": 2},
    ),
)
def test_benchmark_options_reject_invalid_fixed_execution_settings(
    changes,
    tmp_path,
):
    with pytest.raises(ValueError):
        replace(_options(tmp_path, tmp_path / "result"), **changes)


def test_batch2_screen_selects_the_prescribed_three_images_per_profile(tmp_path):
    from bakery_scanner.e2e.cpu_profile import BATCH2_E3_M3_H3_NAMES

    samples = tuple(_sample(index) for index in range(299))
    selected_names = BATCH2_E3_M3_H3_NAMES
    selected_paths = tuple(tmp_path / name for name in selected_names)
    samples_by_name = {
        path.name: replace(sample, image_path=path, profile=profile)
        for path, sample, profile in zip(
            selected_paths,
            samples[-9:],
            ("E", "E", "E", "M", "M", "M", "H", "H", "H"),
            strict=True,
        )
    }

    selected = select_benchmark_samples(
        samples,
        sample_profile="batch2_e3_m3_h3",
        resolve_profile=lambda _: selected_paths,
        sample_for_path=lambda path: samples_by_name[path.name],
        package_root=tmp_path,
    )

    assert select_benchmark_samples is worker_select_benchmark_samples
    assert tuple(sample.image_path.name for sample in selected) == selected_names
    assert tuple(sample.profile for sample in selected) == (
        "E",
        "E",
        "E",
        "M",
        "M",
        "M",
        "H",
        "H",
        "H",
    )


def _options(root: Path, output: Path) -> BenchmarkOptions:
    return BenchmarkOptions(
        root,
        root / "policy.yaml",
        "serial_reference",
        "batch_pytorch",
        "all299",
        1,
        1,
        1,
        "all",
        (),
        3,
        "AB",
        20260729,
        output,
    )


def _dependencies(**overrides) -> BenchmarkDependencies:
    values = {
        "load_samples": lambda root: tuple(
            _sample(index) for index in range(299)
        ),
        "detector_metadata": lambda root: _detector_metadata(),
        "artifact_hashes": lambda root, config, samples: _artifact_hashes(),
        "run_coordinator": lambda **kwargs: object(),
        "build_report": lambda **kwargs: {"schema_version": 3},
        "publish_report": lambda output, report: None,
        "publish_failure": lambda output, failure, **kwargs: None,
    }
    values.update(overrides)
    return BenchmarkDependencies(**values)


def _required_cli_args(root: Path) -> list[str]:
    return [
        "--package-root",
        str(root),
        "--classifier-config",
        str(root / "policy.yaml"),
        "--candidate-mode",
        "batch_pytorch",
        "--output",
        str(root / "result"),
    ]


def _detector_metadata() -> dict[str, object]:
    return {
        "artifact_id": "rfdetr_large_bakery_v1",
        "score_threshold": 0.5691395401954651,
        "manifest_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "calibration_sha256": "c" * 64,
    }


def _artifact_hashes() -> dict[str, str]:
    return {
        "classifier_config_sha256": "d" * 64,
        "ordered_image_list_sha256": "e" * 64,
    }


def _profile(index: int) -> str:
    return "E" if index < 100 else "M" if index < 199 else "H"


def _sample(index):
    from bakery_scanner.contracts import Box
    from bakery_scanner.e2e.cpu_dataset import (
        CpuEvaluationSample,
        CpuEvaluationTarget,
    )

    profile = _profile(index)
    target_count = 5 if index < 210 else 4
    return CpuEvaluationSample(
        key=f"fixture/{profile.lower()}_{index:03d}.jpg",
        source="fixture",
        source_image_id=index + 1,
        image_path=Path("fixture.jpg"),
        profile=profile,
        targets=tuple(
            CpuEvaluationTarget(offset + 1, 1, Box(0, 0, 1, 1))
            for offset in range(target_count)
        ),
    )
