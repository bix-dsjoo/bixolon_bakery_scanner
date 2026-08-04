"""Contract tests for RF-DETR calibration and frozen evaluation."""

from __future__ import annotations

import hashlib
import json
import sys
from importlib.metadata import distribution, version
from pathlib import Path

import pytest

from tools.evaluate import evaluate_rfdetr_bread_oof as evaluator_module
from tools.evaluate.evaluate_rfdetr_bread_oof import (
    evaluate_artifact_bound_detector,
    evaluate_bound_detector,
    evaluate_detector,
    select_detector_policy,
)


CAL_ROWS = (
    {
        "image_id": 10,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.90, "box": [0, 0, 10, 10]}],
    },
    {
        "image_id": 11,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.75, "box": [0, 0, 10, 10]}],
    },
)
EVAL_ROWS = (
    {
        "image_id": 20,
        "ground_truth": [{"box": [0, 0, 10, 10]}],
        "predictions": [{"score": 0.10, "box": [0, 0, 10, 10]}],
    },
)


def test_threshold_selection_uses_calibration_only():
    """Using evaluation scores to choose a threshold would leak held-out scenes."""
    receipt = select_detector_policy(CAL_ROWS, EVAL_ROWS)

    assert receipt.selected_from_image_ids == (10, 11)
    assert not set(receipt.selected_from_image_ids) & {20}
    assert receipt.score_threshold == 0.75


def test_detector_receipt_reports_every_primary_error():
    """Dropping any taxonomy branch would hide a detector error from the receipt."""
    ground_truth = [
        {"image_id": 1, "box": [0, 0, 10, 10]},
        {"image_id": 1, "box": [5, 0, 10, 10]},
        {"image_id": 2, "box": [0, 0, 10, 10]},
    ]
    predictions = [
        {"image_id": 1, "score": 0.9, "box": [0, 0, 10, 10]},
        {"image_id": 1, "score": 0.8, "box": [0, 0, 10, 10]},
        {"image_id": 1, "score": 0.7, "box": [0, 0, 15, 10]},
        {"image_id": 1, "score": 0.6, "box": [50, 0, 10, 10]},
    ]

    metrics = evaluate_detector(ground_truth, predictions, iou_threshold=0.50)

    assert set(metrics.error_counts) == {"miss", "duplicate", "non_target", "split", "merge"}
    assert metrics.error_counts == {"miss": 1, "duplicate": 1, "non_target": 1, "split": 1, "merge": 1}


def _bound_manifest() -> dict[str, object]:
    payload = {
        "schema_version": 1, "fold_index": 2, "seed": 20260803, "source_sha256": "b" * 64,
        "scene_ids": {"train": ["source:train.jpg"], "calibration": ["source:cal.jpg"], "evaluation": ["source:eval.jpg"]},
        "group_ids": {"train": ["source:1"], "calibration": ["source:2"], "evaluation": ["source:3"]},
        "sku_counts": {role: {str(index): 0 for index in range(1, 21)} for role in ("train", "calibration", "evaluation")},
        "difficulty_counts": {role: {difficulty: 0 for difficulty in ("E", "M", "H")} for role in ("train", "calibration", "evaluation")},
    }
    payload["manifest_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def _provenance(manifest: dict[str, object]) -> dict[str, str]:
    return {
        "fold_manifest_sha256": str(manifest["manifest_sha256"]), "source_sha256": "b" * 64,
        "staged_annotations_sha256": "c" * 64, "staged_manifest_sha256": "d" * 64,
        "detector_checkpoint_sha256": "e" * 64, "calibration_predictions_sha256": "f" * 64,
        "evaluation_predictions_sha256": "0" * 64, "config_sha256": "1" * 64,
        "code_sha256": "2" * 64, "runtime_identity_sha256": "3" * 64,
    }


def test_bound_evaluation_requires_exact_split_roles_and_receipt_provenance():
    """Missing, extra, or cross-role rows must not yield a detector receipt."""
    manifest = _bound_manifest()
    calibration = [{"image_id": 10, "scene_id": "source:cal.jpg", "ground_truth": [{"box": [0, 0, 10, 10]}], "predictions": [{"score": 0.8, "box": [0, 0, 10, 10]}]}]
    evaluation = [{"image_id": 20, "scene_id": "source:eval.jpg", "ground_truth": [{"box": [0, 0, 10, 10]}], "predictions": [{"score": 0.7, "box": [0, 0, 10, 10]}]}]

    receipt = evaluate_bound_detector(calibration, evaluation, split_manifest=manifest, provenance=_provenance(manifest))

    assert receipt["provenance"] == _provenance(manifest)
    assert receipt["role_scene_ids"] == {"calibration": ["source:cal.jpg"], "evaluation": ["source:eval.jpg"]}
    with pytest.raises(ValueError, match="exactly match"):
        evaluate_bound_detector(calibration, [{**evaluation[0], "scene_id": "source:cal.jpg"}], split_manifest=manifest, provenance=_provenance(manifest))


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def _descriptor(role: str, path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {"role": role, "path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _runtime_identity() -> dict[str, object]:
    executable = Path(sys.executable)
    package_init = Path(distribution("rfdetr").locate_file("rfdetr/__init__.py"))
    return {
        "schema_version": 1,
        "python_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "python_bytes": executable.stat().st_size,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "packages": {
            "rfdetr": {
                "version": version("rfdetr"),
                "sha256": hashlib.sha256(package_init.read_bytes()).hexdigest(),
            }
        },
    }


def _artifact_evaluation(tmp_path: Path) -> tuple[Path, dict[str, dict[str, object]], Path]:
    split_manifest = _write_json(tmp_path / "fold-2.json", _bound_manifest())
    paths = {
        "staged_manifest": _write_json(tmp_path / "staged-manifest.json", [{"image_id": 1, "file_name": "bread.png"}]),
        "staged_annotations": _write_json(
            tmp_path / "staged-annotations.json",
            {"images": [{"id": 1, "file_name": "bread.png"}], "annotations": [], "categories": [{"id": 1, "name": "bread"}]},
        ),
        "detector_checkpoint": tmp_path / "best-model.pth",
        "calibration_predictions": _write_json(
            tmp_path / "calibration-predictions.json",
            [{
                "image_id": 10,
                "scene_id": "source:cal.jpg",
                "ground_truth": [{"box": [0, 0, 10, 10]}],
                "predictions": [{"score": 0.8, "box": [0, 0, 10, 10]}],
            }],
        ),
        "evaluation_predictions": _write_json(
            tmp_path / "evaluation-predictions.json",
            [{
                "image_id": 20,
                "scene_id": "source:eval.jpg",
                "ground_truth": [{"box": [0, 0, 10, 10]}],
                "predictions": [{"score": 0.9, "box": [0, 0, 10, 10]}],
            }],
        ),
        "evaluation_config": _write_json(tmp_path / "evaluation-config.json", {"iou_threshold": 0.5}),
        "code_identity": Path(evaluator_module.__file__).resolve(),
        "runtime_identity": _write_json(tmp_path / "runtime-identity.json", _runtime_identity()),
    }
    paths["detector_checkpoint"].write_bytes(b"deterministic checkpoint bytes")
    artifacts = {role: _descriptor(role, path) for role, path in paths.items()}
    return split_manifest, artifacts, Path(tmp_path.anchor)


def test_artifact_evaluation_requires_distinct_staged_annotations_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Dropping the annotations descriptor must fail before threshold selection."""
    split_manifest, artifacts, allowed_root = _artifact_evaluation(tmp_path)
    artifacts.pop("staged_annotations")
    selection_calls = 0

    def observe_selection(*args: object, **kwargs: object):
        nonlocal selection_calls
        selection_calls += 1
        return select_detector_policy(*args, **kwargs)

    monkeypatch.setattr(evaluator_module, "select_detector_policy", observe_selection)

    with pytest.raises(ValueError, match="exact required semantic roles"):
        evaluate_artifact_bound_detector(split_manifest=split_manifest, artifacts=artifacts, allowed_root=allowed_root)

    assert selection_calls == 0


@pytest.mark.parametrize("invalidity", ("missing_file", "wrong_role", "wrong_size", "wrong_sha256", "substituted_bytes"))
def test_artifact_evaluation_rejects_invalid_staged_annotations_before_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalidity: str
):
    """A missing or byte-unbound annotations artifact must never influence policy selection."""
    split_manifest, artifacts, allowed_root = _artifact_evaluation(tmp_path)
    descriptor = artifacts["staged_annotations"]
    if invalidity == "missing_file":
        descriptor["path"] = str(tmp_path / "missing-annotations.json")
    elif invalidity == "wrong_role":
        descriptor["role"] = "staged_manifest"
    elif invalidity == "wrong_size":
        descriptor["bytes"] = int(descriptor["bytes"]) + 1
    elif invalidity == "wrong_sha256":
        descriptor["sha256"] = "0" * 64
    else:
        Path(str(descriptor["path"])).write_bytes(b'{"substituted":true}')
    selection_calls = 0

    def observe_selection(*args: object, **kwargs: object):
        nonlocal selection_calls
        selection_calls += 1
        return select_detector_policy(*args, **kwargs)

    monkeypatch.setattr(evaluator_module, "select_detector_policy", observe_selection)

    with pytest.raises(ValueError, match="staged_annotations artifact"):
        evaluate_artifact_bound_detector(split_manifest=split_manifest, artifacts=artifacts, allowed_root=allowed_root)

    assert selection_calls == 0


@pytest.mark.parametrize(
    ("prediction_role", "replacement"),
    (
        (
            "calibration_predictions",
            [{
                "image_id": 10,
                "scene_id": "source:cal.jpg",
                "ground_truth": [{"box": [0, 0, 10, 10]}],
                "predictions": [{"score": 0.2, "box": [0, 0, 10, 10]}],
            }],
        ),
        (
            "evaluation_predictions",
            [{
                "image_id": 20,
                "scene_id": "source:eval.jpg",
                "ground_truth": [{"box": [0, 0, 10, 10]}],
                "predictions": [],
            }],
        ),
    ),
)
def test_artifact_evaluation_uses_the_exact_prediction_bytes_that_were_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prediction_role: str,
    replacement: object,
):
    """Reopening a prediction path after verification would consume substituted rows."""
    split_manifest, artifacts, allowed_root = _artifact_evaluation(tmp_path)
    target = Path(str(artifacts[prediction_role]["path"])).resolve()
    replacement_bytes = json.dumps(replacement, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    original_open = Path.open
    replaced = False

    class ReplaceAfterVerifiedRead:
        def __init__(self, handle: object) -> None:
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def read(self, *args: object, **kwargs: object):
            return self.handle.read(*args, **kwargs)

        def __exit__(self, exc_type: object, exc_value: object, traceback: object):
            nonlocal replaced
            result = self.handle.__exit__(exc_type, exc_value, traceback)
            if not replaced:
                with original_open(target, "wb") as replacement_handle:
                    replacement_handle.write(replacement_bytes)
                replaced = True
            return result

    def replace_after_read(path: Path, *args: object, **kwargs: object):
        handle = original_open(path, *args, **kwargs)
        if path.resolve() == target and not replaced:
            return ReplaceAfterVerifiedRead(handle)
        return handle

    monkeypatch.setattr(Path, "open", replace_after_read)

    receipt = evaluate_artifact_bound_detector(split_manifest=split_manifest, artifacts=artifacts, allowed_root=allowed_root)

    assert replaced is True
    assert target.read_bytes() == replacement_bytes
    assert receipt["policy"]["score_threshold"] == 0.8
    assert receipt["evaluation"] == {
        "matched": 1,
        "error_counts": {"miss": 0, "duplicate": 0, "non_target": 0, "split": 0, "merge": 0},
    }


def test_artifact_evaluation_receipt_keeps_both_staging_byte_identities(tmp_path: Path):
    """Collapsing manifest and annotation evidence would make staging provenance ambiguous."""
    split_manifest, artifacts, allowed_root = _artifact_evaluation(tmp_path)

    receipt = evaluate_artifact_bound_detector(split_manifest=split_manifest, artifacts=artifacts, allowed_root=allowed_root)

    manifest_identity = receipt["verified_artifacts"]["staged_manifest"]
    annotations_identity = receipt["verified_artifacts"]["staged_annotations"]
    assert manifest_identity == {
        "bytes": artifacts["staged_manifest"]["bytes"],
        "sha256": artifacts["staged_manifest"]["sha256"],
    }
    assert annotations_identity == {
        "bytes": artifacts["staged_annotations"]["bytes"],
        "sha256": artifacts["staged_annotations"]["sha256"],
    }
    assert manifest_identity != annotations_identity
    assert receipt["provenance"]["staged_manifest_sha256"] != receipt["provenance"]["staged_annotations_sha256"]
