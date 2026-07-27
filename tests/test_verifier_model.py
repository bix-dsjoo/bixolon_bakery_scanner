import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import torch
from torch import nn

from bakery_scanner.contracts import Box
from bakery_scanner.verifier.model import (
    CLASS_ORDER,
    VerifierOofRunner,
    VerifierPrediction,
    _load_fold_inputs,
    _validate_five_fold_integrity,
    build_mobilenetv4_verifier,
    build_verifier_receipt,
    classify_verifier_batch,
    validate_completed_verifier_fold,
    verifier_receipt_core_sha256,
    write_verifier_predictions,
)


class _TwoCropFourLogitModel(nn.Module):
    def forward(self, crops: torch.Tensor) -> torch.Tensor:
        assert crops.shape == (2, 3, 8, 8)
        return torch.tensor(
            ((1.0, 2.0, 3.0, 4.0), (4.0, 3.0, 2.0, 1.0)),
            dtype=crops.dtype,
            device=crops.device,
        )


def test_verifier_outputs_four_normalized_probabilities():
    probabilities = classify_verifier_batch(
        _TwoCropFourLogitModel(), torch.zeros(2, 3, 8, 8)
    )

    assert probabilities.shape == (2, 4)
    assert torch.allclose(probabilities.sum(dim=1), torch.ones(2))
    assert torch.all(probabilities >= 0)
    assert torch.all(probabilities <= 1)


def test_verifier_runner_rejects_cpu_device_before_writing(tmp_path: Path):
    output_dir = tmp_path / "must-not-exist"

    with pytest.raises(ValueError, match="cuda:0"):
        VerifierOofRunner().train(
            tmp_path / "missing-fold-manifest.json",
            output_dir,
            device="cpu",
        )

    assert not output_dir.exists()


def test_verifier_receipt_hashes_model_fold_config_and_public_crop_metadata(
    tmp_path: Path,
):
    checkpoint = tmp_path / "verifier.pt"
    fold_manifest = tmp_path / "manifest.json"
    config = tmp_path / "verifier_config.json"
    checkpoint.write_bytes(b"checkpoint")
    fold_manifest.write_bytes(b'{"index":2}')
    config.write_bytes(b'{"seed":20260724}')

    receipt = build_verifier_receipt(
        checkpoint=checkpoint,
        fold_manifest=fold_manifest,
        config=config,
        fold=2,
        seed=20260724,
    )

    assert receipt == {
        "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
        "class_order": list(CLASS_ORDER),
        "config_sha256": hashlib.sha256(b'{"seed":20260724}').hexdigest(),
        "device": "cuda:0",
        "fold": 2,
        "fold_manifest_sha256": hashlib.sha256(b'{"index":2}').hexdigest(),
        "model_name": "mobilenetv4_conv_small",
        "preprocessing": {
            "color_mode": "RGB",
            "input_size": [224, 224],
            "interpolation": "bicubic",
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "seed": 20260724,
        "status": "completed",
        "training_examples": {
            "algorithm": "deterministic_four_state_verifier_crops",
            "canonical_image_height": 1536,
            "canonical_image_width": 1152,
            "exactly_one_strategy": "clamped_target_box",
            "invalid_crop_cap": 64.0,
            "invalid_grid_minimum_step": 1,
            "invalid_strategy": "seeded_grid_first_non_overlapping",
            "multiple_strategy": "clamped_pair_envelope",
            "overlap_measure": "intersection_over_ground_truth_area",
            "overlap_threshold": 0.05,
            "partial_fraction": 0.5,
            "partial_strategy": "right_half_without_full_or_multiple_overlap",
            "seed": 20260724,
            "version": 1,
        },
    }


def test_verifier_predictions_preserve_target_fold_candidate_box(tmp_path: Path):
    output = tmp_path / "verifier_predictions.json"
    receipt_hash = "a" * 64

    write_verifier_predictions(
        output,
        predictions=(
            VerifierPrediction(
                image_id=31,
                crop_xywh=Box(10.5, 20.25, 30.0, 40.0),
                probabilities=(0.1, 0.2, 0.3, 0.4),
            ),
        ),
        fold=2,
        validation_image_ids=frozenset({31}),
        verifier_receipt_sha256=receipt_hash,
    )

    assert json.loads(output.read_text(encoding="utf-8")) == [
        {
            "bbox": [10.5, 20.25, 30.0, 40.0],
            "fold": 2,
            "image_id": 31,
            "probabilities": [0.1, 0.2, 0.3, 0.4],
            "verifier_receipt_sha256": receipt_hash,
        }
    ]


def test_verifier_predictions_reject_non_target_fold_candidate(tmp_path: Path):
    with pytest.raises(ValueError, match="held-out fold"):
        write_verifier_predictions(
            tmp_path / "verifier_predictions.json",
            predictions=(
                VerifierPrediction(
                    image_id=30,
                    crop_xywh=Box(1, 2, 3, 4),
                    probabilities=(0.25, 0.25, 0.25, 0.25),
                ),
            ),
            fold=2,
            validation_image_ids=frozenset({31}),
            verifier_receipt_sha256="b" * 64,
        )


def test_timm_mobilenetv4_has_four_logit_head():
    model = build_mobilenetv4_verifier(pretrained=False).eval()

    with torch.inference_mode():
        logits = model(torch.zeros(1, 3, 64, 64))

    assert logits.shape == (1, 4)


def test_powershell_runner_rejects_cpu_before_artifact_access():
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/run_verifier_oof.ps1",
            "-Device",
            "cpu",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "cuda:0" in (result.stdout + result.stderr)


def test_fold_input_rejects_non_dfine_validation_candidate(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    annotations = tmp_path / "annotations.json"
    candidates = tmp_path / "validation_predictions.json"
    manifest.write_text(
        json.dumps(
            {
                "index": 2,
                "training_image_ids": [1],
                "validation_image_ids": [2],
            }
        ),
        encoding="utf-8",
    )
    annotations.write_text(
        json.dumps(
            {
                "images": [
                    {"file_name": "one.png", "height": 100, "id": 1, "width": 100},
                    {"file_name": "two.png", "height": 100, "id": 2, "width": 100},
                ],
                "annotations": [
                    {"bbox": [10, 10, 20, 20], "image_id": 1},
                    {"bbox": [30, 30, 20, 20], "image_id": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    candidates.write_text(
        json.dumps(
            [
                {
                    "bbox": [30, 30, 20, 20],
                    "image_id": 2,
                    "score": 0.9,
                    "source": "rtmdet_tiny_640",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="D-FINE"):
        _load_fold_inputs(
            manifest_path=manifest,
            annotations_path=annotations,
            detector_predictions_path=candidates,
        )


def _write_minimal_verifier_artifact(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a real on-disk artifact with one retained D-FINE candidate."""
    manifest = tmp_path / "manifest.json"
    annotations = tmp_path / "annotations.json"
    candidates = tmp_path / "validation_predictions.json"
    run_root = tmp_path / "verifier-run"
    manifest.write_text(
        json.dumps({"index": 2, "training_image_ids": [1], "validation_image_ids": [2]}),
        encoding="utf-8",
    )
    annotations.write_text(
        json.dumps(
            {
                "images": [
                    {"file_name": "one.png", "height": 100, "id": 1, "width": 100},
                    {"file_name": "two.png", "height": 100, "id": 2, "width": 100},
                ],
                "annotations": [{"bbox": [10, 10, 20, 20], "image_id": 1}],
            }
        ),
        encoding="utf-8",
    )
    candidates.write_text(
        json.dumps(
            [{"bbox": [30, 30, 20, 20], "image_id": 2, "score": 0.9, "source": "dfine_n_640"}]
        ),
        encoding="utf-8",
    )
    run_root.mkdir()
    checkpoint = run_root / "verifier.pt"
    config = run_root / "verifier_config.json"
    checkpoint.write_bytes(b"checkpoint")
    config.write_text(
        json.dumps({"class_order": list(CLASS_ORDER)}), encoding="utf-8"
    )
    core_receipt = build_verifier_receipt(
        checkpoint=checkpoint, fold_manifest=manifest, config=config, fold=2, seed=20260724
    )
    prediction_path = run_root / "verifier_predictions.json"
    prediction_path.write_text(
        json.dumps(
            [
                {
                    "bbox": [30, 30, 20, 20],
                    "fold": 2,
                    "image_id": 2,
                    "probabilities": [0.1, 0.2, 0.3, 0.4],
                    "verifier_receipt_sha256": verifier_receipt_core_sha256(core_receipt),
                }
            ]
        ),
        encoding="utf-8",
    )
    receipt = build_verifier_receipt(
        checkpoint=checkpoint,
        fold_manifest=manifest,
        config=config,
        fold=2,
        seed=20260724,
        verifier_predictions=prediction_path,
    )
    (run_root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return run_root, manifest, annotations, candidates


def _refresh_prediction_receipt(run_root: Path, manifest: Path) -> None:
    receipt = build_verifier_receipt(
        checkpoint=run_root / "verifier.pt",
        fold_manifest=manifest,
        config=run_root / "verifier_config.json",
        fold=2,
        seed=20260724,
        verifier_predictions=run_root / "verifier_predictions.json",
    )
    (run_root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_completed_verifier_reuse_rejects_subset_or_duplicate_predictions(tmp_path: Path):
    run_root, manifest, annotations, candidates = _write_minimal_verifier_artifact(tmp_path)
    (run_root / "verifier_predictions.json").write_text("[]", encoding="utf-8")
    _refresh_prediction_receipt(run_root, manifest)

    with pytest.raises(ValueError, match="candidate set"):
        validate_completed_verifier_fold(
            run_root=run_root,
            fold_manifest=manifest,
            annotations=annotations,
            detector_predictions=candidates,
        )


def test_completed_verifier_reuse_rejects_bad_probability(tmp_path: Path):
    run_root, manifest, annotations, candidates = _write_minimal_verifier_artifact(tmp_path)
    rows = json.loads((run_root / "verifier_predictions.json").read_text(encoding="utf-8"))
    rows[0]["probabilities"] = [0.1, 0.2, 0.3, 0.5]
    (run_root / "verifier_predictions.json").write_text(json.dumps(rows), encoding="utf-8")
    _refresh_prediction_receipt(run_root, manifest)

    with pytest.raises(ValueError, match="probabilities"):
        validate_completed_verifier_fold(
            run_root=run_root,
            fold_manifest=manifest,
            annotations=annotations,
            detector_predictions=candidates,
        )


def test_completed_verifier_reuse_rejects_fabricated_candidate_geometry(tmp_path: Path):
    run_root, manifest, annotations, candidates = _write_minimal_verifier_artifact(tmp_path)
    rows = json.loads((run_root / "verifier_predictions.json").read_text(encoding="utf-8"))
    rows[0]["bbox"] = [31, 30, 20, 20]
    (run_root / "verifier_predictions.json").write_text(json.dumps(rows), encoding="utf-8")
    _refresh_prediction_receipt(run_root, manifest)

    with pytest.raises(ValueError, match="candidate set"):
        validate_completed_verifier_fold(
            run_root=run_root,
            fold_manifest=manifest,
            annotations=annotations,
            detector_predictions=candidates,
        )


def _write_five_fold_manifests(root: Path, groups: tuple[tuple[int, ...], ...]) -> Path:
    staged_manifest = root / "staged_manifest.json"
    staged_rows = []
    for group_index, group in enumerate(groups, start=1):
        for image_id in group:
            staged_rows.append(
                {"image_id": image_id, "scene": {"capture_batch": "batch", "scene_number": group_index}}
            )
    staged_manifest.write_text(json.dumps(staged_rows), encoding="utf-8")
    for fold, validation in enumerate(groups):
        training = tuple(image_id for index, group in enumerate(groups) if index != fold for image_id in group)
        (root / f"fold-{fold}").mkdir()
        (root / f"fold-{fold}" / "manifest.json").write_text(
            json.dumps(
                {
                    "index": fold,
                    "training_image_ids": list(training),
                    "validation_image_ids": list(validation),
                    "training_scenes": [
                        {"capture_batch": "batch", "scene_number": index + 1}
                        for index in range(5) if index != fold
                    ],
                    "validation_scenes": [{"capture_batch": "batch", "scene_number": fold + 1}],
                }
            ),
            encoding="utf-8",
        )
    return staged_manifest


def test_five_fold_integrity_rejects_missing_other_fold_training_group(tmp_path: Path):
    staged_manifest = _write_five_fold_manifests(tmp_path, ((1,), (2,), (3,), (4,), (5,)))
    fold_zero = tmp_path / "fold-0" / "manifest.json"
    row = json.loads(fold_zero.read_text(encoding="utf-8"))
    row["training_image_ids"] = [2, 3, 4]
    row["training_scenes"] = [
        {"capture_batch": "batch", "scene_number": scene_number}
        for scene_number in (2, 3, 4)
    ]
    fold_zero.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(ValueError, match="other four"):
        _validate_five_fold_integrity(tmp_path, staged_manifest)


def test_five_fold_integrity_rejects_capture_scene_split(tmp_path: Path):
    staged_manifest = _write_five_fold_manifests(tmp_path, ((1, 2), (3,), (4,), (5,), (6,)))
    fold_zero = tmp_path / "fold-0" / "manifest.json"
    row = json.loads(fold_zero.read_text(encoding="utf-8"))
    row["validation_image_ids"] = [1]
    row["training_image_ids"] = [2, 3, 4, 5, 6]
    fold_zero.write_text(json.dumps(row), encoding="utf-8")

    with pytest.raises(ValueError, match="whole capture scene"):
        _validate_five_fold_integrity(tmp_path, staged_manifest)
