from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bakery_scanner.pipelines.rtx5080_15plus5.engine_manifest import (
    EngineAdmissionError,
    compare_fp32_fp16_evidence,
    load_engine_runtime_manifest,
    require_engine_manifest,
    verify_active_tensorrt_python,
)


def _identity(path: Path, *, version: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if version is not None:
        payload["version"] = version
    return payload


def _runtime_manifest(tmp_path: Path) -> Path:
    files = {}
    for name in ("tensorrt.whl", "trtexec.exe", "onnx.whl", "nvcuda.dll", "cudart64_13.dll"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        files[name] = path
    module = tmp_path / "site-packages" / "tensorrt" / "__init__.py"
    metadata = tmp_path / "site-packages" / "tensorrt_bindings-10.14.1.dist-info" / "METADATA"
    module.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    module.write_bytes(b"__version__ = '10.14.1'\n")
    metadata.write_bytes(b"Name: tensorrt-bindings\nVersion: 10.14.1\n")
    payload = {
        "schema_version": 1,
        "runtime_id": "tensorrt_rtx5080_v1",
        "build_host": {"hostname": "builder-01", "os": "Windows-11", "architecture": "AMD64"},
        "gpu": {"name": "NVIDIA GeForce RTX 5080", "compute_capability": "12.0", "uuid": "GPU-1234"},
        "driver": {"version": "591.12", **_identity(files["nvcuda.dll"])},
        "driver_compatibility": {"minimum_version": "590.0", "maximum_version": "599.99"},
        "cuda_runtime": {"version": "13.0", **_identity(files["cudart64_13.dll"])},
        "tensorrt_python_wheel": {
            "version": "10.14.1", **_identity(files["tensorrt.whl"]),
            "installed_distribution": {
                "name": "tensorrt-bindings", "version": "10.14.1",
                "module": _identity(module), "metadata": _identity(metadata),
            },
        },
        "trtexec": {"version": "10.14.1", **_identity(files["trtexec.exe"])},
        "onnx_python_wheel": {"version": "1.19.0", **_identity(files["onnx.whl"])},
    }
    path = tmp_path / "runtime-manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_runtime_manifest_verifies_every_runtime_file_identity(tmp_path: Path) -> None:
    path = _runtime_manifest(tmp_path)
    runtime = load_engine_runtime_manifest(path)
    assert runtime.gpu_name == "NVIDIA GeForce RTX 5080"
    runtime.trtexec.write_bytes(b"substituted")
    with pytest.raises(EngineAdmissionError, match="trtexec.*SHA-256|trtexec.*byte"):
        load_engine_runtime_manifest(path)


def test_runtime_manifest_requires_exact_fields_and_external_paths(tmp_path: Path) -> None:
    path = _runtime_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["trtexec"]["sha256"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EngineAdmissionError, match="trtexec.*fields"):
        load_engine_runtime_manifest(path)


def test_runtime_manifest_rejects_driver_outside_compatibility_range(tmp_path: Path) -> None:
    path = _runtime_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["driver_compatibility"]["minimum_version"] = "592.0"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EngineAdmissionError, match="driver.*compatibility range"):
        load_engine_runtime_manifest(path)


def _active_distribution(runtime):
    identity = runtime.tensorrt_distribution
    root = identity.module.path.parents[2]
    relative_module = identity.module.path.relative_to(root)
    relative_metadata = identity.metadata.path.relative_to(root)
    return SimpleNamespace(
        version=identity.version,
        metadata={"Name": identity.name},
        files=(relative_module, relative_metadata),
        locate_file=lambda item: root / item,
    )


def test_active_tensorrt_python_matches_declared_module_owner_version_and_bytes(tmp_path: Path) -> None:
    runtime = load_engine_runtime_manifest(_runtime_manifest(tmp_path))
    module = SimpleNamespace(
        __name__="tensorrt", __package__="tensorrt",
        __file__=str(runtime.tensorrt_distribution.module.path),
        __path__=[str(runtime.tensorrt_distribution.module.path.parent)],
        __spec__=SimpleNamespace(origin=str(runtime.tensorrt_distribution.module.path)),
        __version__=runtime.tensorrt_distribution.version,
    )
    verified = verify_active_tensorrt_python(runtime, module=module, distribution=_active_distribution(runtime))
    assert verified["distribution"] == "tensorrt-bindings"
    assert verified["module_sha256"] == runtime.tensorrt_distribution.module.sha256


@pytest.mark.parametrize("mutation", ["shadow", "module_version", "owner", "bytes"])
def test_active_tensorrt_python_rejects_unrelated_or_substituted_import(tmp_path: Path, mutation: str) -> None:
    runtime = load_engine_runtime_manifest(_runtime_manifest(tmp_path))
    module = SimpleNamespace(
        __name__="tensorrt", __package__="tensorrt",
        __file__=str(runtime.tensorrt_distribution.module.path),
        __path__=[str(runtime.tensorrt_distribution.module.path.parent)],
        __spec__=SimpleNamespace(origin=str(runtime.tensorrt_distribution.module.path)),
        __version__=runtime.tensorrt_distribution.version,
    )
    distribution = _active_distribution(runtime)
    if mutation == "shadow":
        shadow = tmp_path / "shadow" / "tensorrt.py"
        shadow.parent.mkdir()
        shadow.write_bytes(b"shadow")
        module.__file__ = str(shadow)
        module.__spec__ = SimpleNamespace(origin=str(shadow))
    elif mutation == "module_version":
        module.__version__ = "10.99.0"
    elif mutation == "owner":
        distribution.metadata = {"Name": "unrelated-package"}
    else:
        runtime.tensorrt_distribution.module.path.write_bytes(b"substituted after admission")
    with pytest.raises(EngineAdmissionError, match="TensorRT Python"):
        verify_active_tensorrt_python(runtime, module=module, distribution=distribution)


def test_engine_manifest_rejects_dynamic_or_wrong_bindings(tmp_path: Path) -> None:
    onnx = tmp_path / "repvit.onnx"
    engine = tmp_path / "repvit.engine"
    calibration = tmp_path / "repvit-fp16-calibration.json"
    receipt = tmp_path / "build-receipt.json"
    for path in (onnx, engine, calibration, receipt):
        path.write_bytes(path.name.encode())
    payload = {
        "schema_version": 1,
        "model_id": "repvit_m1_15plus5_gpu_fp16_v1",
        "precision": "fp16",
        "onnx": _identity(onnx),
        "engine": _identity(engine),
        "runtime_manifest_sha256": "a" * 64,
        "build_receipt": _identity(receipt),
        "fp16_calibration": {"calibration_id": "repvit_fp16_v1", **_identity(calibration)},
        "bindings": [
            {"name": "crops", "mode": "input", "dtype": "float16", "shape": [-1, 3, 224, 224], "semantic": "tight_context_rows"},
            {"name": "logits", "mode": "output", "dtype": "float16", "shape": [14, 20], "semantic": "sku_logits"},
        ],
    }
    manifest = tmp_path / "engine-manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EngineAdmissionError, match="static|binding"):
        require_engine_manifest(manifest, model_role="repvit")


def _evidence(*, candidate: bool = False, wrong: bool = False) -> dict[str, object]:
    scores = [0.9, 0.08, 0.02] + [0.0] * 17
    return {
        "schema_version": 1,
        "precision": "fp16" if candidate else "fp32",
        "calibration": {
            "calibration_id": "fp16-own-v1" if candidate else "fp32-v1",
            "sha256": ("b" if candidate else "a") * 64,
        },
        "bindings_sha256": "c" * 64,
        "scenes": [{
            "scene_id": "scene-001",
            "provenance": {"catalog_sha256": "d" * 64, "preprocess_sha256": "e" * 64},
            "objects": [{
                "object_id": "scene-001#0", "ground_truth_sku": 1,
                "box": [1.0, 2.0, 10.0, 12.0], "raw_scores": scores,
                "top3": [1, 2, 3], "decision": 2 if wrong else 1,
                "auto_approved": True,
            }],
        }],
    }


def test_fp16_parity_requires_own_calibration_and_rejects_wrong_auto_approval(tmp_path: Path) -> None:
    fp32 = _evidence()
    fp16 = _evidence(candidate=True, wrong=True)
    with pytest.raises(EngineAdmissionError, match="wrong auto approval"):
        compare_fp32_fp16_evidence(fp32, fp16, expected_scene_count=1)
    fp16 = _evidence(candidate=True)
    fp16["calibration"] = fp32["calibration"]
    with pytest.raises(EngineAdmissionError, match="own calibration"):
        compare_fp32_fp16_evidence(fp32, fp16, expected_scene_count=1)


@pytest.mark.parametrize("mutation", ["loss", "nonfinite", "binding", "top3"])
def test_fp16_parity_rejects_unsafe_candidate_evidence(mutation: str) -> None:
    fp32 = _evidence()
    fp16 = _evidence(candidate=True)
    if mutation == "loss":
        fp16["scenes"][0]["objects"] = []
    elif mutation == "nonfinite":
        fp16["scenes"][0]["objects"][0]["raw_scores"][0] = float("nan")
    elif mutation == "binding":
        fp16["bindings_sha256"] = "f" * 64
    else:
        fp16["scenes"][0]["objects"][0]["top3"] = [2, 1, 3]
    with pytest.raises(EngineAdmissionError):
        compare_fp32_fp16_evidence(fp32, fp16, expected_scene_count=1)


def test_fp16_parity_accepts_finite_aligned_evidence() -> None:
    result = compare_fp32_fp16_evidence(_evidence(), _evidence(candidate=True), expected_scene_count=1)
    assert result["status"] == "admitted_fp16_parity"
    assert result["scene_count"] == 1
    assert result["object_count"] == 1
