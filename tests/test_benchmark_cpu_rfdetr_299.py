from pathlib import Path

import pytest

from scripts.benchmark_cpu_rfdetr_299 import (
    BenchmarkDependencies,
    BenchmarkImageRow,
    BenchmarkOptions,
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
