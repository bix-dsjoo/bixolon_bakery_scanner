from pathlib import Path

import pytest

from scripts.benchmark_cpu_rfdetr_299 import (
    BenchmarkDependencies,
    BenchmarkImageRow,
    BenchmarkOptions,
    select_benchmark_samples,
    run_benchmark,
)


def test_benchmark_report_has_299_contract_and_applied_detector_threshold(tmp_path):
    dependencies = BenchmarkDependencies(
        load_samples=lambda root: tuple(_sample(index) for index in range(299)),
        detector_metadata=lambda root: {
            "artifact_id": "rfdetr_large_bakery_v1",
            "score_threshold": 0.5691395401954651,
            "manifest_sha256": "a" * 64,
            "checkpoint_sha256": "b" * 64,
            "calibration_sha256": "c" * 64,
        },
        run_mode=lambda mode, samples, options: tuple(
            BenchmarkImageRow(
                key=sample.key,
                profile=sample.profile,
                object_count=len(sample.targets),
                total_ms=10.0 if mode == "serial_reference" else 5.0,
                records=(),
            )
            for sample in samples
        ),
    )
    report = run_benchmark(
        BenchmarkOptions(
            package_root=tmp_path,
            classifier_config=tmp_path / "policy.yaml",
            reference_mode="serial_reference",
            candidate_mode="batch_pytorch",
            sample_profile="all299",
            intra_op_threads=1,
            repvit_microbatch=1,
            dino_microbatch=1,
            cpu_affinity="all",
            compile_models=(),
            passes=3,
            first_order="AB",
            bootstrap_seed=20260729,
            output=tmp_path / "result",
        ),
        dependencies=dependencies,
    )

    assert report["schema_version"] == 2
    assert report["detector"]["score_threshold"] == 0.5691395401954651
    assert report["dataset"] == {"images": 299, "objects": 1406}
    assert tuple(report["profiles"]) == ("E", "M", "H")
    assert report["latency_gate"]["bootstrap_seed"] == 20260729


def test_benchmark_refuses_to_overwrite_existing_output(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError, match="overwrite"):
        run_benchmark(_options(tmp_path, output), dependencies=_dependencies())


def test_cli_omits_runtime_overrides_when_not_explicitly_requested(monkeypatch, tmp_path):
    from scripts.benchmark_cpu_rfdetr_299 import main

    received = []
    monkeypatch.setattr("scripts.benchmark_cpu_rfdetr_299.run_benchmark", received.append)

    assert main([
        "--package-root", str(tmp_path),
        "--classifier-config", str(tmp_path / "policy.yaml"),
        "--candidate-mode", "batch_pytorch",
        "--output", str(tmp_path / "result"),
    ]) == 0

    options = received[0]
    assert options.intra_op_threads is None
    assert options.cpu_affinity is None
    assert options.repvit_microbatch is None
    assert options.dino_microbatch is None


def test_batch2_screen_selects_the_prescribed_three_images_per_profile(tmp_path):
    from dataclasses import replace

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

    assert tuple(sample.image_path.name for sample in selected) == selected_names
    assert tuple(sample.profile for sample in selected) == ("E", "E", "E", "M", "M", "M", "H", "H", "H")


def _options(root: Path, output: Path) -> BenchmarkOptions:
    return BenchmarkOptions(root, root / "policy.yaml", "serial_reference", "batch_pytorch", "all299", 1, 1, 1, "all", (), 3, "AB", 20260729, output)


def _dependencies() -> BenchmarkDependencies:
    return BenchmarkDependencies(lambda root: (), lambda root: {}, lambda mode, samples, options: ())


def _sample(index):
    from bakery_scanner.contracts import Box
    from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample, CpuEvaluationTarget

    profile = "E" if index < 100 else "M" if index < 199 else "H"
    target_count = 5 if index < 210 else 4
    return CpuEvaluationSample(
        key=f"fixture/{profile.lower()}_{index:03d}.jpg",
        source="fixture",
        source_image_id=index + 1,
        image_path=Path("fixture.jpg"),
        profile=profile,
        targets=tuple(CpuEvaluationTarget(offset + 1, 1, Box(0, 0, 1, 1)) for offset in range(target_count)),
    )
