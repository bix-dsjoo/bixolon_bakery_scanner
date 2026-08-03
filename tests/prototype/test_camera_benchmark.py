from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

import pytest

from scripts.benchmark_camera_worker import (
    _require_stable_code_identity,
    load_benchmark_protocol,
    load_external_manifest,
    build_benchmark_report,
    resolve_code_identity,
    summarize_ms,
    validate_run_count,
)


def _gpu_receipt_artifacts() -> dict[str, str]:
    return {
        "benchmark_manifest_sha256": "a" * 64,
        "benchmark_protocol_sha256": "b" * 64,
        "code_commit": "c" * 40,
        "code_identity_sha256": "d" * 64,
    }


def _applied_hashes() -> dict[str, str]:
    names = (
        "detector_checkpoint_sha256", "detector_calibration_sha256",
        "detector_manifest_sha256", "repvit_checkpoint_sha256",
        "repvit_manifest_sha256", "repvit_prototype_sha256",
        "dinov3_weights_sha256", "dinov3_support_sha256",
        "dinov3_local_bank_sha256", "classifier_calibration_sha256",
        "preprocess_sha256", "fusion_policy_sha256", "presentation_policy_sha256",
    )
    return {name: f"{index:064x}" for index, name in enumerate(names, 1)}


def _result(run: int, total_ms: float) -> dict[str, object]:
    return {
        "type": "result",
        "request_id": f"benchmark-{run:02d}",
        "device": "cpu",
        "timings_ms": {
            "decode_preprocess": 1.0,
            "detector": total_ms - 5.0,
            "crop": 0.0,
            "repvit": 2.0,
            "dinov3": 0.0,
            "fusion": 0.0,
            "postprocess": 2.0,
            "total": total_ms,
        },
        "diagnostics": {"object_count": 1, "dino_object_count": 0},
    }


def test_summarize_twenty_warm_runs_uses_nearest_rank_p95():
    values = tuple(float(value) for value in range(1, 21))

    summary = summarize_ms(values)

    assert summary == {"count": 20, "p50": 10.0, "p95": 19.0, "max": 20.0}


def test_validate_run_count_rejects_fewer_than_twenty_measured_runs():
    with pytest.raises(ValueError, match="at least 20"):
        validate_run_count(19)


def test_report_keeps_startup_and_warmup_out_of_measured_timings():
    ready = {
        "type": "ready",
        "device": "cpu",
        "startup_metrics": {
            "device": "cpu",
            "load_ms": 1000.0,
            "warmup_ms": 500.0,
            "fallback_reason": "cuda_unavailable",
            "detector_id": "rfdetr_large_bakery_v1",
            "repvit_id": "repvit_m1_15plus5_v1",
            "dinov3_id": "dinov3_vits16_15plus5_v1",
            "fusion_policy_id": "fusion_local_or_global_consensus_margin_v1",
            "detector_threshold": 0.5691395401954651,
        },
    }
    results = tuple(_result(run, float(run)) for run in range(20, 40))

    report = build_benchmark_report(ready, results)

    assert report["run_count"] == 20
    assert report["startup"] == {
        "load_ms": 1000.0,
        "warmup_ms": 500.0,
        "fallback_reason": "cuda_unavailable",
    }
    assert report["timings_ms"]["total"] == {
        "count": 20,
        "p50": 29.0,
        "p95": 38.0,
        "max": 39.0,
    }
    assert report["timings_ms"]["total"]["max"] != ready["startup_metrics"]["load_ms"]


def test_report_rejects_a_second_startup_event_in_measured_results():
    ready = {
        "type": "ready",
        "device": "cpu",
        "startup_metrics": {
            "device": "cpu",
            "load_ms": 1.0,
            "warmup_ms": 1.0,
            "fallback_reason": None,
            "detector_id": "rfdetr_large_bakery_v1",
            "repvit_id": "repvit_m1_15plus5_v1",
            "dinov3_id": "dinov3_vits16_15plus5_v1",
            "fusion_policy_id": "fusion_local_or_global_consensus_margin_v1",
            "detector_threshold": 0.5691395401954651,
        },
    }
    events = tuple(_result(run, float(run + 10)) for run in range(20))
    events = events[:5] + ({"type": "warming"},) + events[5:]

    with pytest.raises(ValueError, match="startup event"):
        build_benchmark_report(ready, events)


def test_benchmark_rejects_cuda_fallback():
    ready = {
        "type": "ready",
        "device": "cuda:0",
        "startup_metrics": {
            "device": "cuda:0", "load_ms": 1.0, "warmup_ms": 1.0,
            "fallback_reason": "cuda_load_failed", "detector_id": "detector",
            "repvit_id": "repvit", "dinov3_id": "dinov3",
            "fusion_policy_id": "policy", "detector_threshold": 0.5,
        },
    }
    results = tuple(_result(run, 10.0) | {"device": "cuda:0"} for run in range(100))

    with pytest.raises(ValueError, match="fallback"):
        build_benchmark_report(ready, results)


def test_benchmark_preserves_group_object_and_dino_counts():
    ready = {
        "type": "ready", "device": "cuda:0",
        "startup_metrics": {
            "device": "cuda:0", "load_ms": 1.0, "warmup_ms": 1.0,
            "fallback_reason": None, "detector_id": "detector", "repvit_id": "repvit",
                "dinov3_id": "dinov3", "fusion_policy_id": "policy", "detector_threshold": 0.5,
                "applied_artifact_hashes": _applied_hashes(),
        },
    }
    results = []
    for group in ("E", "M", "H"):
        for index in range(100):
            event = _result(index, 10.0) | {
                "request_id": f"{group}-{index}", "device": "cuda:0",
                "image_id": f"{group}-{index}", "group": group,
                "image_sha256": f"{index:064x}",
                "diagnostics": {"object_count": 3, "dino_object_count": 3 if group == "H" else 0},
            }
            results.append(event)

    report = build_benchmark_report(ready, results, artifacts=_gpu_receipt_artifacts())

    assert report["groups"]["H"]["dino_execution_rate"] == 1.0
    assert report["groups"]["E"]["object_count"]["max"] == 3.0


def test_external_manifest_requires_hashed_absolute_grouped_rows(tmp_path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"image")
    import hashlib
    import json

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "image_id": f"{group.lower()}-1",
                        "group": group,
                        "image_path": str(image.resolve()),
                        "image_sha256": hashlib.sha256(b"image").hexdigest(),
                    }
                    for group in ("E", "M", "H")
                ]
            }
        ),
        encoding="utf-8",
    )

    samples, manifest_sha256 = load_external_manifest(manifest)

    assert samples[0]["image_id"] == "e-1"
    assert manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()


def test_benchmark_protocol_requires_fixed_cuda_p95_contract(tmp_path):
    import json

    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "device": "cuda:0",
                "groups": ["E", "M", "H"],
                "minimum_group_observations": 100,
                "minimum_warmups": 20,
                "overall_p95_limit_ms": 100.0,
                "per_group_p95_limit_ms": 100.0,
                "schema_version": 1,
                "worker_boundary": "file_read_to_in_memory_result_payload",
            }
        ),
        encoding="utf-8",
    )

    loaded, protocol_sha256 = load_benchmark_protocol(protocol)

    assert loaded["minimum_group_observations"] == 100
    assert len(protocol_sha256) == 64


def test_cli_help_imports_the_checked_out_source_tree():
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable, str(root / "scripts" / "benchmark_camera_worker.py"), "--help"]

    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    completed = subprocess.run(
        command, cwd=root, text=True, capture_output=True, env=environment
    )

    assert completed.returncode == 0, completed.stderr


def test_code_identity_rejects_a_repository_other_than_the_import_checkout(tmp_path):
    with pytest.raises(ValueError, match="source checkout"):
        resolve_code_identity(tmp_path)


def test_code_identity_stability_rejects_a_change_after_measurement(monkeypatch):
    expected = {"code_commit": "a" * 40, "code_identity_sha256": "b" * 64}
    changed = {"code_commit": "a" * 40, "code_identity_sha256": "c" * 64}
    monkeypatch.setattr(
        "scripts.benchmark_camera_worker.resolve_code_identity",
        lambda _root: changed,
    )

    with pytest.raises(ValueError, match="changed during the benchmark"):
        _require_stable_code_identity(Path.cwd(), expected)


def test_grouped_runner_rechecks_identity_after_worker_shutdown(tmp_path, monkeypatch):
    import hashlib
    import json

    root = Path(__file__).resolve().parents[2]
    images = []
    for group in ("E", "M", "H"):
        image = tmp_path / f"{group}.jpg"
        image.write_bytes(group.encode("utf-8"))
        images.append(
            {
                "image_id": group.lower(),
                "group": group,
                "image_path": str(image.resolve()),
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            }
        )
    manifest = tmp_path / "external.json"
    manifest.write_text(json.dumps({"samples": images}), encoding="utf-8")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "device": "cuda:0", "groups": ["E", "M", "H"],
                "minimum_group_observations": 100, "minimum_warmups": 20,
                "overall_p95_limit_ms": 100.0, "per_group_p95_limit_ms": 100.0,
                "schema_version": 1,
                "worker_boundary": "file_read_to_in_memory_result_payload",
            }
        ),
        encoding="utf-8",
    )

    class FakeWorker:
        def __init__(self, *_args):
            self._startup = iter(
                (
                    {"type": "loading"}, {"type": "warming"},
                    {
                        "type": "ready", "device": "cuda:0",
                        "startup_metrics": {"device": "cuda:0", "fallback_reason": None},
                    },
                )
            )
            self._events = None

        def send(self, event):
            if event["type"] == "analyze":
                request_id = event["request_id"]
                self._events = iter(
                    [
                        {"type": "progress", "request_id": request_id, "phase": phase}
                        for phase in ("detecting", "classifying", "aggregating")
                    ]
                    + [{"type": "result", "request_id": request_id, "device": "cuda:0"}]
                )
            elif event["type"] == "shutdown":
                self._events = iter(
                    [{"type": "stopped", "request_id": event["request_id"]}]
                )

        def receive(self, _timeout):
            if self._events is not None:
                try:
                    return next(self._events)
                except StopIteration:
                    self._events = None
            return next(self._startup)

        def wait(self, _timeout):
            return 0

        def abort(self):
            pass

    initial = {"code_commit": "a" * 40, "code_identity_sha256": "b" * 64}
    changed = {"code_commit": "a" * 40, "code_identity_sha256": "c" * 64}
    calls = 0

    def changing_identity(_root):
        nonlocal calls
        calls += 1
        return initial if calls == 1 else changed

    monkeypatch.setattr("scripts.benchmark_camera_worker._WorkerProcess", FakeWorker)
    monkeypatch.setattr(
        "scripts.benchmark_camera_worker.resolve_code_identity", changing_identity
    )

    from scripts.benchmark_camera_worker import run_grouped_benchmark

    with pytest.raises(ValueError, match="changed during the benchmark"):
        run_grouped_benchmark(
            python_executable=Path(sys.executable), repo_root=root,
            manifest_path=manifest, protocol_path=protocol,
        )
    assert calls == 2
