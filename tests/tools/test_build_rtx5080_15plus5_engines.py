from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.package.build_rtx5080_15plus5_engines import EngineBuildError, build_engines


def _identity(path: Path, version: str | None = None) -> dict[str, object]:
    value = {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if version:
        value["version"] = version
    return value


def _runtime(tmp_path: Path) -> Path:
    paths = {}
    for name in ("trt.whl", "trtexec.exe", "onnx.whl", "driver.dll", "cuda.dll"):
        paths[name] = tmp_path / name
        paths[name].write_bytes(name.encode())
    module = tmp_path / "site-packages" / "tensorrt" / "__init__.py"
    metadata = tmp_path / "site-packages" / "tensorrt_bindings-10.14.dist-info" / "METADATA"
    module.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    module.write_bytes(b"__version__ = '10.14'\n")
    metadata.write_bytes(b"Name: tensorrt-bindings\nVersion: 10.14\n")
    payload = {
        "schema_version": 1, "runtime_id": "trt-v1",
        "build_host": {"hostname": "host", "os": "Windows", "architecture": "AMD64"},
        "gpu": {"name": "NVIDIA GeForce RTX 5080", "compute_capability": "12.0", "uuid": "GPU-X"},
        "driver": {"version": "591", **_identity(paths["driver.dll"])},
        "driver_compatibility": {"minimum_version": "590", "maximum_version": "599"},
        "cuda_runtime": {"version": "13", **_identity(paths["cuda.dll"])},
        "tensorrt_python_wheel": {
            "version": "10.14", **_identity(paths["trt.whl"]),
            "installed_distribution": {
                "name": "tensorrt-bindings", "version": "10.14",
                "module": _identity(module), "metadata": _identity(metadata),
            },
        },
        "trtexec": {"version": "10.14", **_identity(paths["trtexec.exe"])},
        "onnx_python_wheel": {"version": "1.19", **_identity(paths["onnx.whl"])},
    }
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _onnx_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "onnx"
    root.mkdir()
    artifacts = {}
    shapes = {"rfdetr": [1, 3, 640, 640], "repvit": [14, 3, 224, 224], "dinov3": [7, 3, 224, 224]}
    outputs = {
        "rfdetr": [{"name": "boxes", "shape": [1, 300, 4], "semantic": "normalized_xyxy", "dtype": "float32"}, {"name": "scores", "shape": [1, 300], "semantic": "objectness", "dtype": "float32"}],
        "repvit": [{"name": "logits", "shape": [14, 20], "semantic": "sku_logits", "dtype": "float32"}],
        "dinov3": [{"name": "global_embeddings", "shape": [7, 384], "semantic": "global_cls_embedding", "dtype": "float32"}, {"name": "local_patch_tokens", "shape": [7, 196, 384], "semantic": "local_patch_embedding", "dtype": "float32"}],
    }
    for role in ("rfdetr", "repvit", "dinov3"):
        path = root / f"{role}.onnx"
        path.write_bytes(role.encode())
        source = tmp_path / f"{role}.checkpoint"
        source.write_bytes((role + "-source").encode())
        artifacts[role] = {
            "file": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "input": {"name": "images" if role == "rfdetr" else "crops", "shape": shapes[role], "dtype": "float32"},
            "outputs": outputs[role], "dynamic_axes": None,
            "source": {"path": str(source.resolve()), "bytes": source.stat().st_size, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "preprocess_sha256": hashlib.sha256((role + "-preprocess").encode()).hexdigest()},
        }
    (root / "onnx-bundle-manifest.json").write_text(json.dumps({
        "schema_version": 1, "status": "exported_static_onnx", "opset": 17,
        "chunk_capacities_are_scan_limits": False, "models": artifacts,
    }), encoding="utf-8")
    return root


def _inspect_onnx(path: Path, role: str) -> dict[str, object]:
    manifest = json.loads((path.parent / "onnx-bundle-manifest.json").read_text())
    record = manifest["models"][role]
    return {"input": record["input"], "outputs": record["outputs"]}


def test_engine_build_refuses_unprovisioned_runtime(tmp_path: Path) -> None:
    with pytest.raises(EngineBuildError, match="runtime manifest"):
        build_engines(runtime_manifest=tmp_path / "missing.json", onnx_root=tmp_path / "onnx", output=tmp_path / "engines")


def test_build_uses_deterministic_static_command_and_receipt(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    onnx = _onnx_bundle(tmp_path)
    output = tmp_path / "engines"
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        engine_arg = next(item for item in command if item.startswith("--saveEngine="))
        Path(engine_arg.split("=", 1)[1]).write_bytes(b"engine")
        return SimpleNamespace(returncode=0, stdout="built", stderr="")

    def inspect(engine, role):
        return {
            "rfdetr": [
                {"name": "images", "mode": "input", "dtype": "float16", "shape": [1, 3, 640, 640], "semantic": "canonical_rgb"},
                {"name": "boxes", "mode": "output", "dtype": "float16", "shape": [1, 300, 4], "semantic": "normalized_xyxy"},
                {"name": "scores", "mode": "output", "dtype": "float16", "shape": [1, 300], "semantic": "objectness"},
            ],
            "repvit": [
                {"name": "crops", "mode": "input", "dtype": "float16", "shape": [14, 3, 224, 224], "semantic": "tight_context_rows"},
                {"name": "logits", "mode": "output", "dtype": "float16", "shape": [14, 20], "semantic": "sku_logits"},
            ],
            "dinov3": [
                {"name": "crops", "mode": "input", "dtype": "float16", "shape": [7, 3, 224, 224], "semantic": "context_rows"},
                {"name": "global_embeddings", "mode": "output", "dtype": "float16", "shape": [7, 384], "semantic": "global_cls_embedding"},
                {"name": "local_patch_tokens", "mode": "output", "dtype": "float16", "shape": [7, 196, 384], "semantic": "local_patch_embedding"},
            ],
        }[role]

    result = build_engines(runtime_manifest=runtime, onnx_root=onnx, output=output, run=run, inspect_engine=inspect, inspect_onnx=_inspect_onnx)
    assert result["status"] == "built_static_fp16_engines"
    assert len(commands) == 3
    forbidden = ("--minShapes", "--optShapes", "--maxShapes", "--shapes")
    for command in commands:
        assert command[-4:] == ["--useCudaGraph", "--profilingVerbosity=detailed", "--builderOptimizationLevel=5", "--tacticSources=+CUBLAS,+CUBLAS_LT,+CUDNN"]
        assert "--fp16" in command
        assert not any(item.startswith(forbidden) for item in command)
    receipt = json.loads((output / "build-receipt.json").read_text())
    assert receipt["runtime"]["gpu"]["name"] == "NVIDIA GeForce RTX 5080"
    assert receipt["chunk_capacities_are_scan_limits"] is False


def test_build_rejects_binding_mismatch_without_publishing(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    onnx = _onnx_bundle(tmp_path)
    output = tmp_path / "engines"

    def run(command, **kwargs):
        Path(next(item for item in command if item.startswith("--saveEngine=")).split("=", 1)[1]).write_bytes(b"engine")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def inspect(engine, role):
        return [{"name": "dynamic", "mode": "input", "dtype": "float16", "shape": [-1, 3, 224, 224], "semantic": "bad"}]

    with pytest.raises(EngineBuildError, match="binding"):
        build_engines(runtime_manifest=runtime, onnx_root=onnx, output=output, run=run, inspect_engine=inspect, inspect_onnx=_inspect_onnx)
    assert not output.exists()


def test_build_rejects_dynamic_shape_observed_in_onnx_graph(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    onnx = _onnx_bundle(tmp_path)

    def dynamic_graph(path, role):
        observed = _inspect_onnx(path, role)
        observed["input"] = {**observed["input"], "shape": [-1, *observed["input"]["shape"][1:]]}
        return observed

    with pytest.raises(EngineBuildError, match="observed ONNX graph"):
        build_engines(
            runtime_manifest=runtime, onnx_root=onnx, output=tmp_path / "engines",
            inspect_onnx=dynamic_graph,
        )
