from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from bakery_scanner.pipelines.rtx5080_15plus5.admission import AdmissionError, RuntimeIdentity, admit_candidate
from bakery_scanner.pipelines.rtx5080_15plus5.config import load_candidate_config


def _write(root: Path, artifact_id: str, kind: str, relative: str, content: bytes) -> dict[str, object]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "artifact_id": artifact_id, "kind": kind, "local_path": relative,
        "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "storage": "external",
    }


@pytest.fixture
def runtime_identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        device="cuda:0", gpu_name="NVIDIA GeForce RTX 5080", compute_capability="12.0",
        driver_version="576.52", cuda_version="13.0", tensorrt_version="10.12.0",
    )


@pytest.fixture
def candidate_root(tmp_path: Path, runtime_identity: RuntimeIdentity) -> Path:
    artifacts = (
        _write(tmp_path, "rfdetr_engine", "engine", "engines/rfdetr.engine", b"rfdetr"),
        _write(tmp_path, "repvit_engine", "engine", "engines/repvit.engine", b"repvit"),
        _write(tmp_path, "dinov3_engine", "engine", "engines/dinov3.engine", b"dinov3"),
        _write(tmp_path, "detector_onnx", "onnx", "models/detector.onnx", b"detector onnx"),
        _write(tmp_path, "detector_model", "model", "models/detector.pth", b"detector model"),
        _write(tmp_path, "preprocess", "preprocessing", "policies/preprocess.json", b"preprocess"),
        _write(tmp_path, "support", "support", "models/support.bin", b"support"),
        _write(tmp_path, "calibration", "calibration", "policies/calibration.json", b"calibration"),
        _write(tmp_path, "fusion_policy", "policy", "policies/fusion.json", b"fusion policy"),
        _write(tmp_path, "catalog", "catalog", "data/catalog.json", b"catalog"),
    )
    manifest = {
        "schema_version": 1,
        "pipeline_id": "rtx5080_15plus5_single_frame_v1",
        "artifacts": artifacts,
        "runtime": runtime_identity.__dict__ if hasattr(runtime_identity, "__dict__") else {
            "device": runtime_identity.device, "gpu_name": runtime_identity.gpu_name,
            "compute_capability": runtime_identity.compute_capability, "driver_version": runtime_identity.driver_version,
            "cuda_version": runtime_identity.cuda_version, "tensorrt_version": runtime_identity.tensorrt_version,
        },
        "engines": {
            "rfdetr_engine": [{"name": "images", "mode": "input", "dtype": "float16", "shape": [1, 3, 640, 640], "semantic": "canonical_rgb"}],
            "repvit_engine": [{"name": "crops", "mode": "input", "dtype": "float16", "shape": [14, 3, 224, 224], "semantic": "repvit_crops"}],
            "dinov3_engine": [{"name": "crops", "mode": "input", "dtype": "float16", "shape": [7, 3, 224, 224], "semantic": "dinov3_crops"}],
        },
    }
    (tmp_path / "admission.json").write_text(json.dumps(manifest), encoding="utf-8")
    config = {
        "schema_version": 1, "pipeline_id": manifest["pipeline_id"],
        "admission_manifest": "admission.json", "evaluation_config": "evaluation.yaml",
        "runtime": {"device": "CUDA:0", "precision": "FP16", "min_objects": 3, "max_objects": 7, "p95_limit_ms": 100.0,
                    "stage_budgets_ms": {"decode_canonical": 10, "detector": 36, "completeness": 6, "crop": 4, "repvit": 12, "direct_gate": 2, "dinov3": 18, "fusion_payload": 6, "headroom": 8}},
        "repvit_batch_size": 14, "dinov3_batch_size": 7, "fusion_margin": 0.85,
    }
    evaluation = {"schema_version": 1, "iou_threshold": 0.5, "seed": 20260803, "fold_count": 5,
                  "role_counts": {"train": 3, "calibration": 1, "evaluation": 1},
                  "utility_floors": {"normal_scan_acceptance": {"overall": .8, "each": .7}, "unnecessary_retake": {"overall": .2, "each": .3}, "auto_sku_approval_coverage": {"overall": .7, "each": .6}, "unknown_rate": {"overall": .3, "each": .4}, "unknown_top3_recall": {"overall": .95, "each": .9}},
                  "incremental_auto_sku_approval_coverage_floor": .5, "counterfactual_completeness_block_rate": 1.0,
                  "latency_paths": ["E", "M", "H", "overall", "dinov3", "needs_retake", "unknown"]}
    (tmp_path / "candidate.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (tmp_path / "evaluation.yaml").write_text(yaml.safe_dump(evaluation), encoding="utf-8")
    return tmp_path


def _inspect_expected_engine_bindings(_: RuntimeIdentity) -> dict[str, tuple[dict[str, object], ...]]:
    return {
        "rfdetr_engine": ({"name": "images", "mode": "input", "dtype": "float16", "shape": (1, 3, 640, 640), "semantic": "canonical_rgb"},),
        "repvit_engine": ({"name": "crops", "mode": "input", "dtype": "float16", "shape": (14, 3, 224, 224), "semantic": "repvit_crops"},),
        "dinov3_engine": ({"name": "crops", "mode": "input", "dtype": "float16", "shape": (7, 3, 224, 224), "semantic": "dinov3_crops"},),
    }


def test_admission_rejects_engine_hash_mismatch(candidate_root: Path, runtime_identity: RuntimeIdentity) -> None:
    (candidate_root / "engines" / "rfdetr.engine").write_bytes(b"wrong!")

    with pytest.raises(AdmissionError, match="SHA-256 mismatch"):
        admit_candidate(load_candidate_config(candidate_root / "candidate.yaml"), candidate_root, runtime_identity, inspect_bindings=_inspect_expected_engine_bindings)


def test_admission_accepts_only_exact_runtime_and_bindings(candidate_root: Path, runtime_identity: RuntimeIdentity) -> None:
    receipt = admit_candidate(load_candidate_config(candidate_root / "candidate.yaml"), candidate_root, runtime_identity, inspect_bindings=_inspect_expected_engine_bindings)

    assert receipt.admitted is True
    assert tuple(item.artifact_id for item in receipt.artifacts) == tuple(sorted(item.artifact_id for item in receipt.artifacts))
