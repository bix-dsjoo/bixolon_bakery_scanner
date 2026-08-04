from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from tools.package.export_rtx5080_15plus5_onnx import (
    OnnxExportError,
    export_static_onnx_bundle,
)


def _sources(tmp_path: Path) -> dict[str, dict[str, object]]:
    result = {}
    for role in ("rfdetr", "repvit", "dinov3"):
        path = tmp_path / f"{role}.checkpoint"
        path.write_bytes(role.encode())
        result[role] = {
            "path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "preprocess_sha256": hashlib.sha256((role + "-preprocess").encode()).hexdigest(),
        }
    return result


def test_static_export_uses_only_canonical_shapes_and_semantics(tmp_path: Path) -> None:
    output = tmp_path / "external" / "onnx"
    seen = {}

    def fake_exporter(request):
        seen[request.role] = request
        request.output.write_bytes(request.role.encode())

    receipt = export_static_onnx_bundle(
        output=output,
        exporters={"rfdetr": fake_exporter, "repvit": fake_exporter, "dinov3": fake_exporter},
        sources=_sources(tmp_path),
    )
    assert seen["rfdetr"].input_shape == (1, 3, 640, 640)
    assert seen["repvit"].input_shape == (14, 3, 224, 224)
    assert seen["dinov3"].input_shape == (7, 3, 224, 224)
    assert seen["dinov3"].outputs == (
        ("global_embeddings", (7, 384), "global_cls_embedding"),
        ("local_patch_tokens", (7, 196, 384), "local_patch_embedding"),
    )
    assert all(request.dynamic_axes is None for request in seen.values())
    assert receipt["status"] == "exported_static_onnx"
    assert json.loads((output / "onnx-bundle-manifest.json").read_text())["chunk_capacities_are_scan_limits"] is False


def test_static_export_refuses_partial_export_and_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "onnx"

    def exporter(request):
        request.output.write_bytes(b"onnx")

    with pytest.raises(OnnxExportError, match="exactly"):
        export_static_onnx_bundle(output=output, exporters={"repvit": exporter}, sources=_sources(tmp_path))
    sources = _sources(tmp_path)
    export_static_onnx_bundle(output=output, exporters={role: exporter for role in ("rfdetr", "repvit", "dinov3")}, sources=sources)
    with pytest.raises(OnnxExportError, match="refuse to overwrite"):
        export_static_onnx_bundle(output=output, exporters={role: exporter for role in ("rfdetr", "repvit", "dinov3")}, sources=sources)


def test_static_export_rejects_substituted_source_checkpoint(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    Path(sources["repvit"]["path"]).write_bytes(b"substituted")
    with pytest.raises(OnnxExportError, match="repvit source"):
        export_static_onnx_bundle(
            output=tmp_path / "onnx",
            exporters={role: lambda request: None for role in ("rfdetr", "repvit", "dinov3")},
            sources=sources,
        )
