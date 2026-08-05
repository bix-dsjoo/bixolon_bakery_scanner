"""Export the three RTX 5080 candidate graphs with immutable static shapes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Callable, Mapping
import uuid


_ROLES = ("rfdetr", "repvit", "dinov3")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class OnnxExportError(RuntimeError):
    """Raised when a complete, immutable static export cannot be published."""


@dataclass(frozen=True, slots=True)
class StaticOnnxExportRequest:
    role: str
    output: Path
    input_name: str
    input_shape: tuple[int, ...]
    outputs: tuple[tuple[str, tuple[int, ...], str], ...]
    opset_version: int = 17
    dynamic_axes: None = None


_SPECS = {
    "rfdetr": StaticOnnxExportRequest(
        "rfdetr", Path("rfdetr.onnx"), "images", (1, 3, 640, 640),
        (("boxes", (1, 300, 4), "normalized_xyxy"), ("scores", (1, 300), "objectness")),
    ),
    "repvit": StaticOnnxExportRequest(
        "repvit", Path("repvit.onnx"), "crops", (14, 3, 224, 224),
        (("logits", (14, 20), "sku_logits"),),
    ),
    "dinov3": StaticOnnxExportRequest(
        "dinov3", Path("dinov3.onnx"), "crops", (7, 3, 224, 224),
        (("global_embeddings", (7, 384), "global_cls_embedding"),
         ("local_patch_tokens", (7, 196, 384), "local_patch_embedding")),
    ),
}

Exporter = Callable[[StaticOnnxExportRequest], None]


def export_static_onnx_bundle(
    *,
    output: Path,
    exporters: Mapping[str, Exporter],
    sources: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Export all graphs transactionally; capacities never constrain scan count."""
    if set(exporters) != set(_ROLES):
        raise OnnxExportError("exporters must contain exactly rfdetr, repvit, and dinov3")
    if set(sources) != set(_ROLES):
        raise OnnxExportError("sources must contain exactly rfdetr, repvit, and dinov3")
    verified_sources = {role: _verify_source(sources[role], role) for role in _ROLES}
    destination = Path(output).resolve()
    _require_external(destination, "ONNX output")
    if destination.exists():
        raise OnnxExportError(f"refuse to overwrite existing ONNX output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(f".{destination.name}.pending-{uuid.uuid4().hex}")
    pending.mkdir()
    try:
        models: dict[str, object] = {}
        for role in _ROLES:
            spec = _SPECS[role]
            request = StaticOnnxExportRequest(
                role, pending / spec.output, spec.input_name, spec.input_shape,
                spec.outputs, spec.opset_version, None,
            )
            try:
                exporters[role](request)
            except Exception as exc:
                raise OnnxExportError(f"{role} static ONNX export failed") from exc
            if not request.output.is_file() or request.output.is_symlink() or request.output.stat().st_size < 1:
                raise OnnxExportError(f"{role} exporter did not produce a regular non-empty ONNX file")
            models[role] = {
                "file": request.output.name,
                "bytes": request.output.stat().st_size,
                "sha256": _sha256_file(request.output),
                "input": {"name": request.input_name, "shape": list(request.input_shape), "dtype": "float32"},
                "outputs": [
                    {"name": name, "shape": list(shape), "semantic": semantic, "dtype": "float32"}
                    for name, shape, semantic in request.outputs
                ],
                "dynamic_axes": None,
                "source": verified_sources[role],
            }
        receipt: dict[str, object] = {
            "schema_version": 1,
            "status": "exported_static_onnx",
            "opset": 17,
            "chunk_capacities_are_scan_limits": False,
            "models": models,
        }
        (pending / "onnx-bundle-manifest.json").write_text(
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        pending.replace(destination)
        return receipt
    except Exception:
        if pending.exists():
            shutil.rmtree(pending)
        raise


def _verify_source(value: Mapping[str, object], role: str) -> dict[str, object]:
    required = {"path", "bytes", "sha256", "preprocess_sha256"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise OnnxExportError(f"{role} source identity has unknown or missing fields")
    path_value = value["path"]
    if not isinstance(path_value, str) or not Path(path_value).is_absolute():
        raise OnnxExportError(f"{role} source path must be absolute")
    path = Path(path_value).resolve()
    _require_external(path, f"{role} source")
    size = value["bytes"]
    digest = value["sha256"]
    preprocess = value["preprocess_sha256"]
    if type(size) is not int or size < 1 or not _is_sha(digest) or not _is_sha(preprocess):
        raise OnnxExportError(f"{role} source identity is invalid")
    try:
        if path.stat().st_size != size or _sha256_file(path) != digest:
            raise OnnxExportError(f"{role} source byte or SHA-256 mismatch")
    except OSError as exc:
        raise OnnxExportError(f"{role} source is missing") from exc
    return {"path": str(path), "bytes": size, "sha256": digest, "preprocess_sha256": preprocess}


def _require_external(path: Path, name: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(_REPOSITORY_ROOT)
    except ValueError:
        return
    raise OnnxExportError(f"{name} must stay outside Git repository")


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unverified(status: str, detail: str) -> int:
    print(json.dumps({"schema_version": 1, "status": status, "detail": detail}, sort_keys=True))
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    manifest = arguments.artifact_root / "onnx-export-input.json"
    if not manifest.is_file():
        return _unverified("unverified_missing_final_fp32_artifacts", f"missing {manifest}")
    # Concrete loaded-model exporters are supplied by the provisioned artifact
    # package. This repository intentionally owns only the verified contract.
    return _unverified(
        "unverified_missing_onnx_export_runtime",
        "provision the approved RF-DETR/PyTorch ONNX exporter adapter and runtime",
    )


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["OnnxExportError", "StaticOnnxExportRequest", "export_static_onnx_bundle", "main"]
