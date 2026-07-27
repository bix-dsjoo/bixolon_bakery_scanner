from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

import bakery_scanner.detectors.bundle as bundle
from bakery_scanner.detectors.bundle import (
    validate_final_bundle,
    validate_smoke_results,
)
from bakery_scanner.verifier.model import CLASS_ORDER, PREPROCESSING


def _write(path: Path, payload: bytes) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": path.relative_to(path.parents[1]).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _valid_bundle(root: Path) -> Path:
    annotations = {
        "annotations": [
            {"id": index + 1, "image_id": (index % 299) + 1}
            for index in range(1410)
        ],
        "images": [{"id": index + 1} for index in range(299)],
    }
    staged_manifest = [{"image_id": index + 1} for index in range(299)]
    artifacts = {
        "detector_checkpoint": _write(
            root / "detector" / "best_stg2.pth", b"detector"
        ),
        "detector_config": _write(
            root / "detector" / "dfine_n_640.yml", b"input_size: 640\n"
        ),
        "verifier_checkpoint": _write(
            root / "verifier" / "verifier.pt", b"verifier"
        ),
        "verifier_config": _write(
            root / "verifier" / "verifier_config.json", b"{}\n"
        ),
        "verifier_training_examples": _write(
            root / "verifier" / "training_examples.json", b"[]\n"
        ),
        "final_policy": _write(
            root / "policy" / "final_policy.json",
            b'{"detector_score_threshold":0.001,"minimum_exactly_one_probability":0.8}\n',
        ),
        "staged_annotations": _write(
            root / "evidence" / "annotations.json",
            json.dumps(annotations, sort_keys=True, separators=(",", ":")).encode(),
        ),
        "staged_manifest": _write(
            root / "evidence" / "staged_manifest.json",
            json.dumps(
                staged_manifest, sort_keys=True, separators=(",", ":")
            ).encode(),
        ),
        "development_report": _write(
            root / "evidence" / "development_report.json", b"{}\n"
        ),
        "smoke_results": _write(
            root / "smoke" / "results.json",
            json.dumps(
                [
                    {
                        "bbox": [1.0, 2.0, 5.0, 6.0],
                        "image_height": 20,
                        "image_id": 1,
                        "image_width": 10,
                        "outcome": "EXACTLY_ONE",
                        "probabilities": [0.01, 0.97, 0.01, 0.01],
                    }
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        ),
    }
    manifest = {
        "artifacts": artifacts,
        "detector": {
            "input_size": 640,
            "name": "dfine_n_640",
        },
        "runtime": {
            "cuda_version": "12.8",
            "device": "cuda:0",
            "gpu_name": "NVIDIA GeForce RTX 5080",
            "python_version": "3.11.9",
            "torch_version": "2.8.0",
        },
        "schema_version": 1,
        "seed": 20260724,
        "training_data": {
            "box_count": 1410,
            "image_count": 299,
        },
        "verifier": {
            "class_order": list(CLASS_ORDER),
            "model_name": "mobilenetv4_conv_small",
            "preprocessing": PREPROCESSING,
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return root


def test_bundle_requires_detector_verifier_policy_and_hashes(tmp_path):
    with pytest.raises(ValueError, match="verifier checkpoint"):
        validate_final_bundle(tmp_path)


def test_bundle_accepts_complete_hash_consistent_gpu_manifest(tmp_path):
    validate_final_bundle(_valid_bundle(tmp_path))


def test_bundle_rejects_hash_mismatched_member(tmp_path):
    root = _valid_bundle(tmp_path)
    (root / "verifier" / "verifier.pt").write_bytes(b"changed")

    with pytest.raises(ValueError, match="verifier checkpoint hash mismatch"):
        validate_final_bundle(root)


def test_bundle_rejects_unhashed_extra_member(tmp_path):
    root = _valid_bundle(tmp_path)
    (root / "untracked.bin").write_bytes(b"not committed by manifest")

    with pytest.raises(ValueError, match="unhashed bundle member"):
        validate_final_bundle(root)


def test_bundle_requires_exact_full_staged_counts(tmp_path):
    root = _valid_bundle(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["training_data"]["image_count"] = 298
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="299 images and 1410 boxes"):
        validate_final_bundle(root)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("runtime.device", "cpu", "cuda:0"),
        ("verifier.class_order", ["EXACTLY_ONE"], "class order"),
        ("verifier.preprocessing", {}, "preprocessing"),
    ],
)
def test_bundle_rejects_incomplete_gpu_or_verifier_metadata(
    tmp_path, field, value, message
):
    root = _valid_bundle(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    section, key = field.split(".")
    manifest[section][key] = value
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_final_bundle(root)


def test_smoke_requires_source_bounds_normalized_probabilities_and_outcome():
    validate_smoke_results(
        [
            {
                "bbox": [1.0, 2.0, 5.0, 6.0],
                "image_height": 20,
                "image_id": 1,
                "image_width": 10,
                "outcome": "EXACTLY_ONE",
                "probabilities": [0.01, 0.97, 0.01, 0.01],
            }
        ]
    )


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ({"bbox": [1.0, 2.0, 11.0, 6.0]}, "source image bounds"),
        (
            {"probabilities": [0.01, 0.97, 0.01, 0.010002]},
            "sum to one",
        ),
        ({"outcome": "ACCEPTED"}, "four-state outcome"),
    ],
)
def test_smoke_rejects_broken_inference_contract(replacement, message):
    result = {
        "bbox": [1.0, 2.0, 5.0, 6.0],
        "image_height": 20,
        "image_id": 1,
        "image_width": 10,
        "outcome": "EXACTLY_ONE",
        "probabilities": [0.01, 0.97, 0.01, 0.01],
    }
    result.update(replacement)

    with pytest.raises(ValueError, match=message):
        validate_smoke_results([result])


def test_smoke_outcome_must_match_probability_argmax():
    with pytest.raises(ValueError, match="probability argmax"):
        validate_smoke_results(
            [
                {
                    "bbox": [1.0, 2.0, 5.0, 6.0],
                    "image_height": 20,
                    "image_id": 1,
                    "image_width": 10,
                    "outcome": "INVALID",
                    "probabilities": [0.01, 0.97, 0.01, 0.01],
                }
            ]
        )


def test_final_policy_freezes_recall_first_minimum_cross_fit_thresholds(
    tmp_path,
):
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "operational_guarantee": False,
                "policies": {
                    str(fold): {
                        "detector_score_threshold": value,
                        "minimum_exactly_one_probability": 0.9 - value,
                    }
                    for fold, value in enumerate(
                        (0.4, 0.2, 0.3, 0.5, 0.1)
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "final-policy.json"

    bundle.write_final_policy_from_report(report=report, output=output)

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "detector_score_threshold": 0.1,
        "minimum_exactly_one_probability": 0.4,
    }


def test_final_policy_refuses_to_overwrite_immutable_output(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "operational_guarantee": False,
                "policies": {
                    str(fold): {
                        "detector_score_threshold": 0.1,
                        "minimum_exactly_one_probability": 0.8,
                    }
                    for fold in range(5)
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "final-policy.json"
    output.write_text("preserve me", encoding="utf-8")

    with pytest.raises(ValueError, match="overwrite final policy"):
        bundle.write_final_policy_from_report(report=report, output=output)

    assert output.read_text(encoding="utf-8") == "preserve me"


def test_final_verifier_training_rejects_cpu_before_reading_inputs(tmp_path):
    with pytest.raises(ValueError, match="cuda:0"):
        bundle.train_final_verifier(
            annotations=tmp_path / "missing-annotations.json",
            staged_manifest=tmp_path / "missing-staged-manifest.json",
            images=tmp_path / "missing-images",
            output_dir=tmp_path / "output",
            device="cpu",
        )


def test_final_training_script_rejects_cpu_before_creating_artifacts(tmp_path):
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/train_dfine640_verifier_final.ps1",
            "-Device",
            "cpu",
            "-BundleRoot",
            str(tmp_path / "bundle"),
        ],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "cuda:0" in completed.stderr
    assert not (tmp_path / "bundle").exists()
