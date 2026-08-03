"""Contract tests for the fold-safe RF-DETR bread training producer."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

from PIL import Image

from tools.train.train_rfdetr_bread_oof import main, run_fold_training


SPLIT_SHA = "a" * 64


class _FakeModel:
    def train(self, **kwargs: object) -> None:
        self.train_kwargs = kwargs


def _write_staged_dataset(root: Path) -> Path:
    images = root / "images"
    images.mkdir(parents=True)
    names = {
        1: "group_15class__g15_e_0001.png",
        2: "group_15class__g15_e_0002.png",
        3: "group_15class__g15_e_0003.png",
    }
    for image_id in (1, 2, 3):
        Image.new("RGB", (12, 8)).save(images / names[image_id])
    (root / "annotations.json").write_text(
        json.dumps(
            {
                "images": [
                    {"id": 1, "file_name": names[1], "width": 12, "height": 8},
                    {"id": 2, "file_name": names[2], "width": 12, "height": 8},
                    {"id": 3, "file_name": names[3], "width": 12, "height": 8},
                ],
                "annotations": [
                    {"id": 1, "image_id": 1, "category_id": 1, "bbox": [1, 1, 4, 3]},
                    {"id": 2, "image_id": 2, "category_id": 1, "bbox": [2, 1, 3, 4]},
                    {"id": 3, "image_id": 3, "category_id": 1, "bbox": [1, 2, 5, 2]},
                ],
                "categories": [{"id": 1, "name": "bread", "supercategory": "object"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "staged_manifest.json").write_text(
        json.dumps(
            [
                {"image_id": 1, "file_name": names[1], "source_sha256": "1" * 64, "box_count": 1, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 1}},
                {"image_id": 2, "file_name": names[2], "source_sha256": "2" * 64, "box_count": 1, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 2}},
                {"image_id": 3, "file_name": names[3], "source_sha256": "3" * 64, "box_count": 1, "overlap_proxy": False, "scene": {"capture_batch": "g15", "scene_number": 3}},
            ]
        ),
        encoding="utf-8",
    )
    return root


def _split_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "fold_index": 2,
        "seed": 20260803,
        "source_sha256": "b" * 64,
        "manifest_sha256": SPLIT_SHA,
        "scene_ids": {
            "train": ["group_15class:g15_e_0001.jpg"],
            "calibration": ["group_15class:g15_e_0002.jpg"],
            "evaluation": ["group_15class:g15_e_0003.jpg"],
        },
    }


def test_fold_training_uses_only_train_role(tmp_path: Path):
    """Changing the selected role to calibration/evaluation must fail this contract."""
    fake_model = _FakeModel()
    run_fold_training(
        _split_manifest(),
        fold_index=2,
        model_factory=lambda: fake_model,
        staged_root=_write_staged_dataset(tmp_path / "staged"),
        output_root=tmp_path / "runs",
    )

    assert str(fake_model.train_kwargs["dataset_dir"]).endswith("fold-2\\train")
    assert fake_model.train_kwargs["device"] == "cuda:0"
    assert fake_model.train_kwargs["num_classes"] == 1
    assert fake_model.train_kwargs["dataset_file"] == "coco"
    assert fake_model.train_kwargs["class_names"] == ["bread"]
    assert fake_model.train_kwargs["amp_dtype"] == "fp16"
    staged_annotations = json.loads((tmp_path / "runs" / "fold-2" / "train" / "annotations.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in staged_annotations["images"]] == [1]
    assert (tmp_path / "runs" / "fold-2" / "train" / "train2017" / "group_15class__g15_e_0001.png").is_file()
    assert (tmp_path / "runs" / "fold-2" / "train" / "annotations" / "instances_train2017.json").is_file()
    assert (tmp_path / "runs" / "fold-2" / "train" / "annotations" / "instances_val2017.json").is_file()


def test_training_notes_bind_split_seed_and_source_hash(tmp_path: Path):
    """Removing any reproducibility binding from a training call must fail this contract."""
    fake_model = _FakeModel()
    staged_root = _write_staged_dataset(tmp_path / "staged")
    run_fold_training(
        _split_manifest(),
        fold_index=2,
        model_factory=lambda: fake_model,
        staged_root=staged_root,
        output_root=tmp_path / "runs",
    )

    notes = fake_model.train_kwargs["notes"]
    assert notes["fold_manifest_sha256"] == SPLIT_SHA
    assert notes["seed"] == 20260803
    assert notes["base_seed"] == 20260803
    assert notes["training_seed"] == 20260805
    assert notes["source_sha256"] == "b" * 64
    assert notes["category_map"] == {"1": "bread"}
    assert notes["staged_annotations_sha256"] == hashlib.sha256((staged_root / "annotations.json").read_bytes()).hexdigest()


def test_existing_receipt_is_never_overwritten(tmp_path: Path):
    """Deleting or reusing a receipt would destroy the only record of a run."""
    run_root = tmp_path / "runs" / "fold-2"
    run_root.mkdir(parents=True)
    receipt = run_root / "receipt.json"
    receipt.write_text('{"status":"unverified"}', encoding="utf-8")

    import pytest

    with pytest.raises(FileExistsError, match="receipt"):
        run_fold_training(
            _split_manifest(),
            fold_index=2,
            model_factory=lambda: _FakeModel(),
            staged_root=_write_staged_dataset(tmp_path / "staged"),
            output_root=tmp_path / "runs",
        )


def test_cli_marks_missing_staged_coco_unverified_without_downloading(tmp_path: Path, monkeypatch):
    """A missing external staged dataset must not start a model download or fake a fold."""
    output = tmp_path / "runs"
    monkeypatch.delenv("BIXOLON_RFDETR_STAGED_ROOT", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["train_rfdetr_bread_oof.py", "--splits", str(tmp_path / "splits"), "--fold", "all", "--output", str(output)],
    )

    assert main() == 2
    assert [json.loads((output / f"fold-{index}" / "receipt.json").read_text(encoding="utf-8"))["status"] for index in range(5)] == ["unverified_missing_staged_coco"] * 5


def test_cli_marks_missing_train_extra_unverified_after_safe_staging(tmp_path: Path, monkeypatch):
    """A train()-time optional-dependency failure must not become a completed fold."""
    class MissingTrainExtra:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def train(self, **_kwargs: object) -> None:
            raise ImportError("RF-DETR training dependencies are missing")

    staged = _write_staged_dataset(tmp_path / "staged")
    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "fold-2.json").write_text(json.dumps(_split_manifest()), encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.pth"
    checkpoint.write_bytes(b"checkpoint")
    output = tmp_path / "runs"
    monkeypatch.setitem(sys.modules, "rfdetr", types.SimpleNamespace(RFDETRLarge=MissingTrainExtra))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_rfdetr_bread_oof.py", "--splits", str(splits), "--fold", "2", "--output", str(output),
            "--staged-root", str(staged), "--pretrain-weights", str(checkpoint),
            "--pretrain-sha256", hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        ],
    )

    assert main() == 2
    assert json.loads((output / "fold-2" / "receipt.json").read_text(encoding="utf-8"))["status"] == "unverified_missing_rfdetr_train_runtime"
