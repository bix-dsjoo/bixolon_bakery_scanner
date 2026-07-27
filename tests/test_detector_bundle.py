from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

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
    staged_manifest = [
        {
            "file_name": f"image-{index + 1}.png",
            "image_id": index + 1,
            "source_sha256": f"{index + 1:064x}",
        }
        for index in range(299)
    ]
    annotations = {
        "annotations": [
            {"id": index + 1, "image_id": (index % 299) + 1}
            for index in range(1410)
        ],
        "images": [
            {"file_name": f"image-{index + 1}.png", "id": index + 1}
            for index in range(299)
        ],
    }
    runtime = {
        "cuda_version": "12.8",
        "device": "cuda:0",
        "gpu_name": "NVIDIA GeForce RTX 5080",
        "python_version": "3.11.9",
        "torch_version": "2.8.0",
    }
    detector_checkpoint = _write(
        root / "detector" / "best_stg2.pth", b"detector"
    )
    detector_config = _write(
        root / "detector" / "dfine_n_640.yml", b"input_size: 640\n"
    )
    verifier_checkpoint = _write(
        root / "verifier" / "verifier.pt", b"verifier"
    )
    verifier_config = _write(
        root / "verifier" / "verifier_config.json",
        json.dumps(
            {
                "class_order": list(CLASS_ORDER),
                "model_name": "mobilenetv4_conv_small",
                "preprocessing": PREPROCESSING,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
    )
    detector_metadata = _write(
        root / "detector" / "detector_metadata.json",
        json.dumps(
            {
                "checkpoint_sha256": detector_checkpoint["sha256"],
                "config_sha256": detector_config["sha256"],
                "input_size": 640,
                "name": "dfine_n_640",
                "runtime": runtime,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
    )
    verifier_metadata = _write(
        root / "verifier" / "verifier_metadata.json",
        json.dumps(
            {
                "checkpoint_sha256": verifier_checkpoint["sha256"],
                "class_order": list(CLASS_ORDER),
                "config_sha256": verifier_config["sha256"],
                "model_name": "mobilenetv4_conv_small",
                "preprocessing": PREPROCESSING,
                "runtime": runtime,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
    )
    artifacts = {
        "detector_checkpoint": detector_checkpoint,
        "detector_config": detector_config,
        "detector_metadata": detector_metadata,
        "verifier_checkpoint": verifier_checkpoint,
        "verifier_config": verifier_config,
        "verifier_metadata": verifier_metadata,
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
        "training_input_snapshot": _write(
            root / "evidence" / "training_input_snapshot.json",
            json.dumps(
                {
                    "images": [
                        {
                            "file_name": row["file_name"],
                            "image_id": row["image_id"],
                            "source_sha256": row["source_sha256"],
                            "staged_sha256": hashlib.sha256(
                                f"staged-{row['image_id']}".encode()
                            ).hexdigest(),
                        }
                        for row in staged_manifest
                    ],
                    "schema_version": 1,
                },
                sort_keys=True,
                separators=(",", ":"),
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
                        "verifier_checkpoint_sha256": verifier_checkpoint[
                            "sha256"
                        ],
                        "verifier_metadata_sha256": verifier_metadata["sha256"],
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
        "runtime": runtime,
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


def _small_staged_inputs(root: Path) -> tuple[Path, Path, Path]:
    images = root / "images"
    images.mkdir()
    (images / "one.png").write_bytes(b"one")
    (images / "two.png").write_bytes(b"two")
    annotations = root / "annotations.json"
    annotations.write_text(
        json.dumps(
            {
                "annotations": [
                    {"id": 1, "image_id": 1, "bbox": [0, 0, 1, 1]},
                    {"id": 2, "image_id": 2, "bbox": [0, 0, 1, 1]},
                ],
                "images": [
                    {"file_name": "one.png", "id": 1},
                    {"file_name": "two.png", "id": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    staged_manifest = root / "staged_manifest.json"
    staged_manifest.write_text(
        json.dumps(
            [
                {
                    "file_name": name,
                    "image_id": index,
                    "source_sha256": hashlib.sha256(
                        (images / name).read_bytes()
                    ).hexdigest(),
                }
                for index, name in ((1, "one.png"), (2, "two.png"))
            ]
        ),
        encoding="utf-8",
    )
    return annotations, staged_manifest, images


def _writer_ready_bundle(root: Path) -> Path:
    bundle_root = _valid_bundle(root)
    (bundle_root / "manifest.json").unlink()
    (bundle_root / "detector" / "best_stg2.pth").rename(
        bundle_root / "detector" / "checkpoint.pth"
    )
    return bundle_root


def _patch_bundle_writer_gpu(monkeypatch) -> None:
    monkeypatch.setattr(bundle, "_require_cuda0_rtx5080", lambda: None)
    monkeypatch.setattr(
        bundle.torch.cuda,
        "get_device_name",
        lambda _: "NVIDIA GeForce RTX 5080",
    )
    monkeypatch.setattr(bundle.torch.version, "cuda", "12.8")
    monkeypatch.setattr(
        bundle,
        "_runtime_metadata",
        lambda: {
            "cuda_version": "12.8",
            "device": "cuda:0",
            "gpu_name": "NVIDIA GeForce RTX 5080",
            "python_version": "3.11.9",
            "torch_version": "2.8.0",
        },
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "missing staged image"),
        ("extra", "extra staged image"),
        ("name", "file name mismatch"),
    ],
)
def test_staged_input_validation_rejects_missing_extra_named_or_changed_images(
    tmp_path, mutation, message
):
    annotations, staged_manifest, images = _small_staged_inputs(tmp_path)
    if mutation == "missing":
        (images / "two.png").unlink()
    elif mutation == "extra":
        (images / "extra.png").write_bytes(b"extra")
    elif mutation == "name":
        payload = json.loads(annotations.read_text(encoding="utf-8"))
        payload["images"][1]["file_name"] = "renamed.png"
        annotations.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        bundle.validate_staged_training_inputs(
            annotations=annotations,
            staged_manifest=staged_manifest,
            images=images,
            expected_staged_images=2,
            expected_staged_boxes=2,
        )


def test_training_snapshot_preserves_original_hash_and_detects_staged_png_mutation(
    tmp_path,
):
    annotations, staged_manifest, images = _small_staged_inputs(tmp_path)
    manifest = json.loads(staged_manifest.read_text(encoding="utf-8"))
    manifest[0]["source_sha256"] = "0" * 64
    staged_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    bundle.validate_staged_training_inputs(
        annotations=annotations,
        staged_manifest=staged_manifest,
        images=images,
        expected_staged_images=2,
        expected_staged_boxes=2,
    )
    snapshot = {
        "images": [
            {
                "file_name": "one.png",
                "image_id": 1,
                "source_sha256": "0" * 64,
                "staged_sha256": hashlib.sha256(
                    (images / "one.png").read_bytes()
                ).hexdigest(),
            },
            {
                "file_name": "two.png",
                "image_id": 2,
                "source_sha256": manifest[1]["source_sha256"],
                "staged_sha256": hashlib.sha256(
                    (images / "two.png").read_bytes()
                ).hexdigest(),
            },
        ],
        "schema_version": 1,
    }
    (images / "two.png").write_bytes(b"changed-after-snapshot")

    with pytest.raises(ValueError, match="training snapshot staged SHA-256 mismatch"):
        bundle.validate_training_input_snapshot(snapshot=snapshot, images=images)


def test_bundle_writer_refuses_to_reapprove_tampered_artifact(monkeypatch, tmp_path):
    root = _writer_ready_bundle(tmp_path)
    _patch_bundle_writer_gpu(monkeypatch)
    bundle.write_final_bundle_manifest(root)
    original_manifest = (root / "manifest.json").read_bytes()
    (root / "verifier" / "verifier_config.json").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="overwrite final bundle manifest"):
        bundle.write_final_bundle_manifest(root)

    assert (root / "manifest.json").read_bytes() == original_manifest


def test_bundle_writer_leaves_no_manifest_when_preconditions_fail(
    monkeypatch, tmp_path
):
    root = _writer_ready_bundle(tmp_path)
    _patch_bundle_writer_gpu(monkeypatch)
    (root / "untracked.bin").write_bytes(b"unhashed")

    with pytest.raises(ValueError, match="unhashed bundle member"):
        bundle.write_final_bundle_manifest(root)

    assert not (root / "manifest.json").exists()


def test_bundle_requires_detector_verifier_policy_and_hashes(tmp_path):
    with pytest.raises(ValueError, match="verifier checkpoint"):
        validate_final_bundle(tmp_path)


def test_bundle_accepts_complete_hash_consistent_gpu_manifest(tmp_path):
    validate_final_bundle(_valid_bundle(tmp_path))


def test_bundle_requires_training_byte_snapshot(tmp_path):
    root = _valid_bundle(tmp_path)
    (root / "evidence" / "training_input_snapshot.json").unlink()
    with pytest.raises(ValueError, match="training input snapshot"):
        validate_final_bundle(root)


def test_bundle_requires_auditable_verifier_checkpoint_metadata(tmp_path):
    root = _valid_bundle(tmp_path)
    (root / "verifier" / "verifier_metadata.json").unlink()
    with pytest.raises(ValueError, match="verifier metadata"):
        validate_final_bundle(root)


def test_bundle_requires_smoke_to_link_the_verifier_checkpoint(tmp_path):
    root = _valid_bundle(tmp_path)
    smoke_path = root / "smoke" / "results.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    smoke[0]["verifier_checkpoint_sha256"] = "0" * 64
    smoke_path.write_text(json.dumps(smoke), encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["smoke_results"]["sha256"] = hashlib.sha256(
        smoke_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="smoke verifier checkpoint linkage"):
        validate_final_bundle(root)


def test_bundle_rejects_rehashed_verifier_config_without_model_metadata(tmp_path):
    root = _valid_bundle(tmp_path)
    config_path = root / "verifier" / "verifier_config.json"
    config_path.write_text("{}", encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["verifier_config"]["sha256"] = hashlib.sha256(
        config_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="verifier config metadata"):
        validate_final_bundle(root)


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


def test_smoke_runner_refuses_existing_output_before_gpu_inference(tmp_path):
    output = tmp_path / "results.json"
    output.write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="overwrite smoke results"):
        bundle.run_one_image_verifier_smoke(
            checkpoint=tmp_path / "missing-checkpoint.pt",
            detector_predictions=tmp_path / "missing-predictions.json",
            annotations=tmp_path / "missing-annotations.json",
            images=tmp_path / "missing-images",
            output=output,
            device="cuda:0",
        )

    assert output.read_text(encoding="utf-8") == "preserve"


def test_smoke_runner_writes_results_linked_to_the_verifier_metadata(
    monkeypatch, tmp_path
):
    checkpoint = tmp_path / "verifier.pt"
    checkpoint.write_bytes(b"checkpoint")
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (tmp_path / "verifier_metadata.json").write_text(
        json.dumps({"checkpoint_sha256": checkpoint_sha256}), encoding="utf-8"
    )

    class FakeModel:
        def to(self, _device):
            return self

        def load_state_dict(self, _state_dict, strict):
            assert strict is True

    monkeypatch.setattr(bundle, "_require_cuda0_rtx5080", lambda: None)
    monkeypatch.setattr(
        bundle,
        "_load_image_metadata",
        lambda _path: ({1: "one.png"}, {1: (10, 20)}),
    )
    monkeypatch.setattr(
        bundle,
        "_read_json_array",
        lambda _path, _label: [
            {
                "bbox": [1.0, 2.0, 5.0, 6.0],
                "image_id": 1,
                "score": 0.9,
                "source": "dfine_n_640",
            }
        ],
    )
    monkeypatch.setattr(
        bundle.torch,
        "load",
        lambda *_args, **_kwargs: {
            "class_order": CLASS_ORDER,
            "model_name": "mobilenetv4_conv_small",
            "preprocessing": PREPROCESSING,
            "state_dict": {},
        },
    )
    monkeypatch.setattr(
        bundle, "build_mobilenetv4_verifier", lambda **_kwargs: FakeModel()
    )
    monkeypatch.setattr(
        bundle,
        "_predict_candidates",
        lambda *_args, **_kwargs: (
            SimpleNamespace(probabilities=(0.01, 0.97, 0.01, 0.01)),
        ),
    )
    output = tmp_path / "smoke.json"

    bundle.run_one_image_verifier_smoke(
        checkpoint=checkpoint,
        detector_predictions=tmp_path / "predictions.json",
        annotations=tmp_path / "annotations.json",
        images=tmp_path / "images",
        output=output,
        device="cuda:0",
    )

    row = json.loads(output.read_text(encoding="utf-8"))[0]
    assert row["verifier_checkpoint_sha256"] == checkpoint_sha256
    assert row["verifier_metadata_sha256"] == hashlib.sha256(
        (tmp_path / "verifier_metadata.json").read_bytes()
    ).hexdigest()


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
