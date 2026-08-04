"""Build an all-or-nothing static FP16 TensorRT engine bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable, Mapping, Sequence
import uuid

from bakery_scanner.pipelines.rtx5080_15plus5.engine_manifest import (
    EngineAdmissionError,
    EngineRuntimeManifest,
    canonical_engine_bindings,
    load_engine_runtime_manifest,
    require_canonical_bindings,
    verify_active_tensorrt_python,
)


_ROLES = ("rfdetr", "repvit", "dinov3")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_STATIC_INPUTS = {
    "rfdetr": {"name": "images", "shape": [1, 3, 640, 640], "dtype": "float32"},
    "repvit": {"name": "crops", "shape": [14, 3, 224, 224], "dtype": "float32"},
    "dinov3": {"name": "crops", "shape": [7, 3, 224, 224], "dtype": "float32"},
}
_STATIC_OUTPUTS = {
    role: [
        {"name": item["name"], "shape": item["shape"], "semantic": item["semantic"], "dtype": "float32"}
        for item in canonical_engine_bindings(role) if item["mode"] == "output"
    ]
    for role in _ROLES
}


class EngineBuildError(RuntimeError):
    """Raised when no complete verified engine bundle can be published."""


RunCommand = Callable[..., object]
BindingInspector = Callable[[Path, str], Sequence[Mapping[str, object]]]
OnnxInspector = Callable[[Path, str], Mapping[str, object]]
RuntimeVerifier = Callable[[EngineRuntimeManifest], Mapping[str, str]]


def build_engines(
    *,
    runtime_manifest: Path,
    onnx_root: Path,
    output: Path,
    run: RunCommand = subprocess.run,
    inspect_engine: BindingInspector | None = None,
    inspect_onnx: OnnxInspector | None = None,
    verify_runtime: RuntimeVerifier | None = None,
) -> dict[str, object]:
    """Build all three engines with no profiles and publish only after admission."""
    try:
        runtime = load_engine_runtime_manifest(runtime_manifest)
    except EngineAdmissionError as exc:
        raise EngineBuildError(str(exc)) from exc
    try:
        active_tensorrt = dict(verify_active_tensorrt_python(runtime))
    except EngineAdmissionError as exc:
        raise EngineBuildError(str(exc)) from exc
    except Exception as exc:
        raise EngineBuildError("active TensorRT Python verification failed") from exc
    if verify_runtime is not None:
        try:
            asserted_tensorrt = dict(verify_runtime(runtime))
        except EngineAdmissionError as exc:
            raise EngineBuildError(str(exc)) from exc
        except Exception as exc:
            raise EngineBuildError("active TensorRT Python assertion failed") from exc
        if asserted_tensorrt != active_tensorrt:
            raise EngineBuildError("active TensorRT Python assertion receipt mismatch")
    expected_active_tensorrt = {
        "distribution": runtime.tensorrt_distribution.name,
        "version": runtime.tensorrt_distribution.version,
        "module_path": str(runtime.tensorrt_distribution.module.path),
        "module_sha256": runtime.tensorrt_distribution.module.sha256,
        "metadata_path": str(runtime.tensorrt_distribution.metadata.path),
        "metadata_sha256": runtime.tensorrt_distribution.metadata.sha256,
        "wheel_sha256": runtime.tensorrt_python_wheel.sha256,
    }
    if active_tensorrt != expected_active_tensorrt:
        raise EngineBuildError("active TensorRT Python verification receipt mismatch")
    bundle_root = Path(onnx_root).resolve()
    graph_inspector = inspect_onnx or (
        lambda path, role: _inspect_onnx_graph(
            path, role, expected_version=runtime.onnx_python_wheel.version
        )
    )
    try:
        bundle = _load_onnx_bundle(bundle_root, graph_inspector)
    except (EngineBuildError, OSError) as exc:
        raise EngineBuildError(str(exc)) from exc
    destination = Path(output).resolve()
    _require_external(destination, "engine output")
    if destination.exists():
        raise EngineBuildError(f"refuse to overwrite existing engine output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(f".{destination.name}.pending-{uuid.uuid4().hex}")
    pending.mkdir()
    inspector = inspect_engine or (
        lambda engine, role: _inspect_engine_with_tensorrt(
            engine, role, runtime_manifest=runtime
        )
    )
    builds: dict[str, object] = {}
    try:
        for role in _ROLES:
            onnx = bundle_root / bundle["models"][role]["file"]
            engine = pending / f"{role}.engine"
            command = _trtexec_command(runtime, onnx, engine)
            started = time.perf_counter()
            try:
                completed = run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=clean_runtime_env(runtime),
                )
            except Exception as exc:
                raise EngineBuildError(f"{role} trtexec invocation failed") from exc
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if getattr(completed, "returncode", None) != 0:
                raise EngineBuildError(f"{role} trtexec failed with exit code {getattr(completed, 'returncode', None)}")
            if not engine.is_file() or engine.is_symlink() or engine.stat().st_size < 1:
                raise EngineBuildError(f"{role} trtexec produced no regular non-empty engine")
            before = _file_identity(engine)
            try:
                bindings = [dict(item) for item in inspector(engine, role)]
                require_canonical_bindings(role, bindings)
            except (EngineAdmissionError, Exception) as exc:
                if isinstance(exc, EngineBuildError):
                    raise
                raise EngineBuildError(f"{role} engine binding admission failed") from exc
            after = _file_identity(engine)
            if before != after:
                raise EngineBuildError(f"{role} engine bytes changed during binding inspection")
            builds[role] = {
                "onnx": _file_identity(onnx),
                "engine": before,
                "command": command,
                "elapsed_ms": elapsed_ms,
                "stdout": getattr(completed, "stdout", ""),
                "stderr": getattr(completed, "stderr", ""),
                "bindings": bindings,
                "workspace_mib": 4096,
                "tactic_sources": ["CUBLAS", "CUBLAS_LT", "CUDNN"],
            }
        receipt: dict[str, object] = {
            "schema_version": 1,
            "status": "built_static_fp16_engines",
            "precision": "fp16",
            "dynamic_profiles": False,
            "chunk_capacities_are_scan_limits": False,
            "runtime": runtime.receipt_payload(),
            "active_tensorrt_python": active_tensorrt,
            "onnx_bundle_manifest": _file_identity(bundle_root / "onnx-bundle-manifest.json"),
            "builds": builds,
        }
        receipt["receipt_sha256"] = _canonical_sha256(receipt)
        (pending / "build-receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        pending.replace(destination)
        return receipt
    except Exception:
        if pending.exists():
            shutil.rmtree(pending)
        raise


def _load_onnx_bundle(root: Path, inspect_onnx: OnnxInspector) -> dict[str, object]:
    manifest = root / "onnx-bundle-manifest.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineBuildError("static ONNX bundle manifest is missing or invalid") from exc
    required = {"schema_version", "status", "opset", "chunk_capacities_are_scan_limits", "models"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise EngineBuildError("static ONNX bundle manifest fields mismatch")
    if payload["schema_version"] != 1 or payload["status"] != "exported_static_onnx" or payload["opset"] != 17 or payload["chunk_capacities_are_scan_limits"] is not False:
        raise EngineBuildError("static ONNX bundle contract mismatch")
    models = payload["models"]
    if not isinstance(models, dict) or set(models) != set(_ROLES):
        raise EngineBuildError("static ONNX bundle must contain exactly three model roles")
    for role in _ROLES:
        record = models[role]
        required_model = {"file", "bytes", "sha256", "input", "outputs", "dynamic_axes", "source"}
        if not isinstance(record, dict) or set(record) != required_model or record["dynamic_axes"] is not None:
            raise EngineBuildError(f"{role} ONNX manifest permits dynamic axes or has invalid fields")
        if record["input"] != _STATIC_INPUTS[role] or record["outputs"] != _STATIC_OUTPUTS[role]:
            raise EngineBuildError(f"{role} ONNX static shape/output semantics mismatch")
        file_name = record["file"]
        if not isinstance(file_name, str) or not file_name or Path(file_name).name != file_name:
            raise EngineBuildError(f"{role} ONNX file must be root-relative")
        path = (root / file_name).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise EngineBuildError(f"{role} ONNX path escapes bundle") from exc
        actual = _file_identity(path)
        if record["bytes"] != actual["bytes"] or record["sha256"] != actual["sha256"]:
            raise EngineBuildError(f"{role} ONNX byte or SHA-256 mismatch")
        try:
            observed_graph = dict(inspect_onnx(path, role))
        except EngineBuildError:
            raise
        except Exception as exc:
            raise EngineBuildError(f"{role} observed ONNX graph inspection failed") from exc
        expected_graph = {"input": _STATIC_INPUTS[role], "outputs": _STATIC_OUTPUTS[role]}
        if observed_graph != expected_graph:
            raise EngineBuildError(f"{role} observed ONNX graph is dynamic or has a binding mismatch")
        source = record["source"]
        if not isinstance(source, dict) or set(source) != {"path", "bytes", "sha256", "preprocess_sha256"}:
            raise EngineBuildError(f"{role} ONNX source provenance mismatch")
        source_path = Path(str(source["path"])).resolve()
        source_actual = _file_identity(source_path)
        if source["bytes"] != source_actual["bytes"] or source["sha256"] != source_actual["sha256"] or not _is_sha(source["preprocess_sha256"]):
            raise EngineBuildError(f"{role} ONNX source byte or SHA-256 mismatch")
    return payload


def _inspect_onnx_graph(path: Path, role: str, *, expected_version: str) -> Mapping[str, object]:
    try:
        import onnx
    except ImportError as exc:
        raise EngineBuildError("ONNX Python runtime is unavailable; no fallback") from exc
    if getattr(onnx, "__version__", None) != expected_version:
        raise EngineBuildError("active ONNX Python version differs from runtime manifest")
    try:
        model = onnx.load_model(path, load_external_data=False)
        onnx.checker.check_model(model)
    except Exception as exc:
        raise EngineBuildError(f"{role} ONNX graph is invalid") from exc
    initializers = {item.name for item in model.graph.initializer}
    inputs = [item for item in model.graph.input if item.name not in initializers]
    if len(inputs) != 1:
        raise EngineBuildError(f"{role} ONNX graph must have exactly one data input")
    semantics = {item["name"]: item["semantic"] for item in _STATIC_OUTPUTS[role]}
    return {
        "input": _onnx_value_info(inputs[0], semantic=None),
        "outputs": [
            _onnx_value_info(item, semantic=semantics.get(item.name))
            for item in model.graph.output
        ],
    }


def _onnx_value_info(value: object, *, semantic: str | None) -> dict[str, object]:
    try:
        tensor = value.type.tensor_type
        dimensions = tensor.shape.dim
        shape = [dimension.dim_value if dimension.HasField("dim_value") and dimension.dim_value > 0 else -1 for dimension in dimensions]
        element_type = tensor.elem_type
        name = value.name
    except (AttributeError, TypeError) as exc:
        raise EngineBuildError("ONNX tensor metadata is malformed") from exc
    # ONNX TensorProto.FLOAT is numeric enum 1. Avoid importing a second symbol
    # so the active package/version check stays in one place.
    result: dict[str, object] = {"name": name, "shape": shape, "dtype": "float32" if element_type == 1 else f"onnx:{element_type}"}
    if semantic is not None:
        result["semantic"] = semantic
    return result


def _trtexec_command(runtime: EngineRuntimeManifest, onnx: Path, engine: Path) -> list[str]:
    return [
        str(runtime.trtexec),
        f"--onnx={onnx}",
        f"--saveEngine={engine}",
        "--fp16",
        "--memPoolSize=workspace:4096",
        "--useCudaGraph",
        "--profilingVerbosity=detailed",
        "--builderOptimizationLevel=5",
        "--tacticSources=+CUBLAS,+CUBLAS_LT,+CUDNN",
    ]


def clean_runtime_env(runtime: EngineRuntimeManifest) -> dict[str, str]:
    """Expose only stable OS essentials and the verified trtexec directory."""
    allowed = ("SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment["PATH"] = str(runtime.trtexec.parent)
    environment["CUDA_MODULE_LOADING"] = "EAGER"
    return environment


def _inspect_engine_with_tensorrt(
    engine: Path,
    role: str,
    *,
    runtime_manifest: EngineRuntimeManifest,
) -> Sequence[Mapping[str, object]]:
    try:
        import importlib

        trt = importlib.import_module("tensorrt")
    except ImportError as exc:
        raise EngineBuildError("TensorRT Python binding is unavailable; no fallback") from exc
    try:
        verify_active_tensorrt_python(runtime_manifest, module=trt)
    except EngineAdmissionError as exc:
        raise EngineBuildError(str(exc)) from exc
    logger = trt.Logger(trt.Logger.ERROR)
    runtime = trt.Runtime(logger)
    value = runtime.deserialize_cuda_engine(engine.read_bytes())
    if value is None:
        raise EngineBuildError(f"{role} TensorRT engine deserialization failed")
    expected = canonical_engine_bindings(role)
    semantics = {item["name"]: item["semantic"] for item in expected}
    rows = []
    for index in range(value.num_io_tensors):
        name = value.get_tensor_name(index)
        rows.append({
            "name": name,
            "mode": "input" if value.get_tensor_mode(name) == trt.TensorIOMode.INPUT else "output",
            "dtype": str(value.get_tensor_dtype(name)).lower(),
            "shape": list(value.get_tensor_shape(name)),
            "semantic": semantics.get(name, "unknown"),
        })
    return rows


def _file_identity(path: Path) -> dict[str, object]:
    resolved = Path(path).resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise EngineBuildError(f"artifact is missing or not a regular file: {resolved}")
    return {"path": str(resolved), "bytes": resolved.stat().st_size, "sha256": _sha256_file(resolved)}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _require_external(path: Path, name: str) -> None:
    try:
        path.resolve().relative_to(_REPOSITORY_ROOT)
    except ValueError:
        return
    raise EngineBuildError(f"{name} must stay outside Git repository")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--onnx-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        receipt = build_engines(
            runtime_manifest=arguments.runtime_manifest,
            onnx_root=arguments.onnx_root,
            output=arguments.output,
        )
    except EngineBuildError as exc:
        status = "unverified_missing_tensorrt_runtime" if "runtime manifest" in str(exc) or "TensorRT Python" in str(exc) else "engine_build_rejected"
        print(json.dumps({"schema_version": 1, "status": status, "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"status": receipt["status"], "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["EngineBuildError", "build_engines", "clean_runtime_env", "main"]
