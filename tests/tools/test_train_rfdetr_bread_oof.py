"""Contract tests for the fold-safe RF-DETR bread training producer."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from importlib.metadata import distribution, version
from pathlib import Path

from PIL import Image
import pytest

from tools.train.train_rfdetr_bread_oof import main, run_fold_training


SPLIT_SHA = "a" * 64


class _FakeModel:
    def train(self, **kwargs: object) -> None:
        self.train_kwargs = kwargs
        checkpoint = Path(str(kwargs["output_dir"])) / "best_model.pth"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_bytes(b"trained checkpoint")


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
    payload = {
        "schema_version": 1,
        "fold_index": 2,
        "seed": 20260803,
        "source_sha256": "b" * 64,
        "scene_ids": {
            "train": ["group_15class:g15_e_0001.jpg"],
            "calibration": ["group_15class:g15_e_0002.jpg"],
            "evaluation": ["group_15class:g15_e_0003.jpg"],
        },
        "group_ids": {"train": ["group_15class:1"], "calibration": ["group_15class:2"], "evaluation": ["group_15class:3"]},
        "sku_counts": {role: {str(index): 0 for index in range(1, 21)} for role in ("train", "calibration", "evaluation")},
        "difficulty_counts": {role: {difficulty: 0 for difficulty in ("E", "M", "H")} for role in ("train", "calibration", "evaluation")},
    }
    payload["manifest_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return payload


def _write_runtime_identity(path: Path) -> Path:
    executable = Path(sys.executable)
    package_init = Path(distribution("rfdetr").locate_file("rfdetr/__init__.py"))
    path.write_text(json.dumps({"schema_version": 1, "python_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "python_bytes": executable.stat().st_size, "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "packages": {"rfdetr": {"version": version("rfdetr"), "sha256": hashlib.sha256(package_init.read_bytes()).hexdigest()}}}), encoding="utf-8")
    return path


def _runtime_identity(tmp_path: Path) -> dict[str, object]:
    return json.loads(_write_runtime_identity(tmp_path / "runtime-direct.json").read_text(encoding="utf-8"))


def test_fold_training_uses_only_train_role(tmp_path: Path):
    """Changing the selected role to calibration/evaluation must fail this contract."""
    fake_model = _FakeModel()
    run_fold_training(
        _split_manifest(),
        fold_index=2,
        model_factory=lambda: fake_model,
        staged_root=_write_staged_dataset(tmp_path / "staged"),
        output_root=tmp_path / "runs",
        runtime_identity=_runtime_identity(tmp_path),
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
        runtime_identity=_runtime_identity(tmp_path),
    )

    notes = fake_model.train_kwargs["notes"]
    assert notes["fold_manifest_sha256"] == _split_manifest()["manifest_sha256"]
    assert notes["seed"] == 20260803
    assert notes["base_seed"] == 20260803
    assert notes["training_seed"] == 20260805
    assert notes["source_sha256"] == "b" * 64
    assert notes["category_map"] == {"1": "bread"}
    assert notes["staged_annotations_sha256"] == hashlib.sha256((staged_root / "annotations.json").read_bytes()).hexdigest()


def test_tampered_fold_roles_are_rejected_before_any_staging_write(tmp_path: Path):
    """Moving a held-out scene into train without its canonical hash must fail closed."""
    manifest = _split_manifest()
    manifest["scene_ids"]["train"].append("group_15class:g15_e_0003.jpg")
    output = tmp_path / "runs"

    import pytest

    with pytest.raises(ValueError, match="manifest SHA-256"):
        run_fold_training(
            manifest,
            fold_index=2,
            model_factory=_FakeModel,
            staged_root=_write_staged_dataset(tmp_path / "staged"),
            output_root=output,
            runtime_identity=_runtime_identity(tmp_path),
        )
    assert not output.exists()


def test_successful_training_writes_checkpoint_bound_immutable_receipt(tmp_path: Path):
    """A train return without a hashed checkpoint receipt would be a false success claim."""
    output = tmp_path / "runs"
    receipt = run_fold_training(
        _split_manifest(),
        fold_index=2,
        model_factory=_FakeModel,
        staged_root=_write_staged_dataset(tmp_path / "staged"),
        output_root=output,
        runtime_identity=_runtime_identity(tmp_path),
    )

    stored = json.loads((output / "fold-2" / "receipt.json").read_text(encoding="utf-8"))
    assert stored["status"] == "verified_success"
    assert stored["checkpoint"]["sha256"] == hashlib.sha256((output / "fold-2" / "checkpoint" / "best_model.pth").read_bytes()).hexdigest()
    assert stored["provenance"] == receipt["provenance"]


def test_direct_training_requires_runtime_before_model_factory(tmp_path: Path):
    """A caller cannot bypass runtime verification to obtain a success receipt."""
    invoked = False

    def factory():
        nonlocal invoked
        invoked = True
        return _FakeModel()

    import pytest

    with pytest.raises(TypeError):
        run_fold_training(_split_manifest(), fold_index=2, model_factory=factory, staged_root=_write_staged_dataset(tmp_path / "staged"), output_root=tmp_path / "runs")
    assert invoked is False


@pytest.mark.parametrize(
    "mismatch",
    ("schema", "python_sha256", "python_bytes", "python_version", "package_version", "package_module_sha256"),
)
def test_direct_training_rejects_runtime_mismatch_before_factory_or_output(tmp_path: Path, mismatch: str):
    """A direct caller with the wrong interpreter or package identity cannot publish a fold."""
    runtime_identity = _runtime_identity(tmp_path)
    if mismatch == "schema":
        runtime_identity["schema_version"] = 2
    elif mismatch == "python_sha256":
        runtime_identity["python_sha256"] = "0" * 64
    elif mismatch == "python_bytes":
        runtime_identity["python_bytes"] = int(runtime_identity["python_bytes"]) + 1
    elif mismatch == "python_version":
        runtime_identity["python_version"] = "0.0.0"
    elif mismatch == "package_version":
        runtime_identity["packages"]["rfdetr"]["version"] = "0.0.0"
    else:
        runtime_identity["packages"]["rfdetr"]["sha256"] = "0" * 64
    factory_calls = 0
    train_calls = 0

    class ObservedModel:
        def train(self, **_kwargs: object) -> None:
            nonlocal train_calls
            train_calls += 1

    def factory() -> ObservedModel:
        nonlocal factory_calls
        factory_calls += 1
        return ObservedModel()

    output = tmp_path / "runs"
    with pytest.raises(ValueError, match="runtime identity"):
        run_fold_training(
            _split_manifest(),
            fold_index=2,
            model_factory=factory,
            staged_root=tmp_path / "unused-staged-data",
            output_root=output,
            runtime_identity=runtime_identity,
        )

    assert not output.exists()
    assert not list(tmp_path.rglob("receipt.json"))
    assert factory_calls == 0
    assert train_calls == 0


def test_missing_declared_checkpoint_never_writes_success_receipt(tmp_path: Path):
    """A backend returning without best_model.pth is not a completed fold."""
    class NoCheckpoint:
        def train(self, **_kwargs: object) -> None:
            return None

    import pytest

    output = tmp_path / "runs"
    with pytest.raises(FileNotFoundError, match="checkpoint"):
        run_fold_training(_split_manifest(), fold_index=2, model_factory=NoCheckpoint, staged_root=_write_staged_dataset(tmp_path / "staged"), output_root=output, runtime_identity=_runtime_identity(tmp_path))
    assert not (output / "fold-2" / "receipt.json").exists()


def test_staged_file_name_escape_is_rejected_before_copying(tmp_path: Path):
    """A staged filename containing a separator must not escape either copy root."""
    staged = _write_staged_dataset(tmp_path / "staged")
    manifest = _split_manifest()
    payload = json.loads((staged / "staged_manifest.json").read_text(encoding="utf-8"))
    payload[0]["file_name"] = "group_15class__g15_e_0001/escape.png"
    (staged / "images" / "group_15class__g15_e_0001").mkdir()
    Image.new("RGB", (12, 8)).save(staged / "images" / "group_15class__g15_e_0001" / "escape.png")
    annotations = json.loads((staged / "annotations.json").read_text(encoding="utf-8"))
    annotations["images"][0]["file_name"] = payload[0]["file_name"]
    (staged / "annotations.json").write_text(json.dumps(annotations), encoding="utf-8")
    (staged / "staged_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="basename"):
        run_fold_training(manifest, fold_index=2, model_factory=_FakeModel, staged_root=staged, output_root=tmp_path / "runs", runtime_identity=_runtime_identity(tmp_path))
    assert not (tmp_path / "runs" / "fold-2" / "train2017" / "escape.png").exists()


def test_all_fold_preflight_rejects_later_empty_directory_without_partial_receipts(tmp_path: Path, monkeypatch):
    """An empty later fold directory must block --fold all before fold zero writes."""
    output = tmp_path / "runs"
    (output / "fold-4").mkdir(parents=True)
    monkeypatch.delenv("BIXOLON_RFDETR_STAGED_ROOT", raising=False)
    monkeypatch.setattr(sys, "argv", ["train_rfdetr_bread_oof.py", "--splits", str(tmp_path / "splits"), "--fold", "all", "--output", str(output)])

    import pytest

    with pytest.raises(FileExistsError, match="fold output directory"):
        main()
    assert not (output / "fold-0").exists()


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
            runtime_identity=_runtime_identity(tmp_path),
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
    runtime_identity = _write_runtime_identity(tmp_path / "runtime.json")
    monkeypatch.setitem(sys.modules, "rfdetr", types.SimpleNamespace(RFDETRLarge=MissingTrainExtra))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_rfdetr_bread_oof.py", "--splits", str(splits), "--fold", "2", "--output", str(output),
            "--staged-root", str(staged), "--pretrain-weights", str(checkpoint),
            "--pretrain-sha256", hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "--runtime-identity", str(runtime_identity),
        ],
    )

    assert main() == 2
    assert json.loads((output / "fold-2" / "receipt.json").read_text(encoding="utf-8"))["status"] == "unverified_missing_rfdetr_train_runtime"


def test_cli_runtime_identity_mismatch_is_unverified_before_training(tmp_path: Path, monkeypatch):
    """A runtime manifest for another executable must prevent RF-DETR construction."""
    staged = _write_staged_dataset(tmp_path / "staged")
    identity = _write_runtime_identity(tmp_path / "runtime.json")
    payload = json.loads(identity.read_text(encoding="utf-8"))
    payload["python_sha256"] = "0" * 64
    identity.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "runs"
    monkeypatch.setattr(sys, "argv", ["train_rfdetr_bread_oof.py", "--splits", str(tmp_path / "splits"), "--fold", "2", "--output", str(output), "--staged-root", str(staged), "--runtime-identity", str(identity)])

    assert main() == 2
    assert json.loads((output / "fold-2" / "receipt.json").read_text(encoding="utf-8"))["status"] == "unverified_runtime_identity_mismatch"


def _write_all_fold_manifests(root: Path) -> Path:
    root.mkdir()
    for fold_index in range(5):
        payload = _split_manifest()
        payload["fold_index"] = fold_index
        payload.pop("manifest_sha256")
        payload["manifest_sha256"] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        (root / f"fold-{fold_index}.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def _all_fold_cli_arguments(tmp_path: Path) -> tuple[list[str], Path]:
    staged = _write_staged_dataset(tmp_path / "staged")
    splits = _write_all_fold_manifests(tmp_path / "splits")
    checkpoint = tmp_path / "pretrain.pth"
    checkpoint.write_bytes(b"pretrained checkpoint")
    runtime_identity = _write_runtime_identity(tmp_path / "runtime.json")
    output = tmp_path / "runs"
    return (
        [
            "train_rfdetr_bread_oof.py",
            "--splits",
            str(splits),
            "--fold",
            "all",
            "--output",
            str(output),
            "--staged-root",
            str(staged),
            "--pretrain-weights",
            str(checkpoint),
            "--pretrain-sha256",
            hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "--runtime-identity",
            str(runtime_identity),
        ],
        output,
    )


def test_all_fold_transaction_retains_failure_evidence_without_publishing_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An unexpected later-fold failure must retain pending evidence and expose no final run."""
    constructed = 0

    class FailOnFoldOne:
        def __init__(self, **_kwargs: object) -> None:
            nonlocal constructed
            self.fold_position = constructed
            constructed += 1

        def train(self, **kwargs: object) -> None:
            if self.fold_position == 1:
                raise RuntimeError("deterministic fold-1 failure")
            checkpoint = Path(str(kwargs["output_dir"])) / "best_model.pth"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_bytes(f"fold-{self.fold_position}".encode("utf-8"))

    arguments, output = _all_fold_cli_arguments(tmp_path)
    monkeypatch.setitem(sys.modules, "rfdetr", types.SimpleNamespace(RFDETRLarge=FailOnFoldOne))
    monkeypatch.setattr(sys, "argv", arguments)

    status = main()

    pending = list(tmp_path.glob(".runs.pending-*"))
    assert status == 1
    assert not output.exists()
    assert len(pending) == 1
    assert json.loads((pending[0] / "fold-0" / "receipt.json").read_text(encoding="utf-8"))["status"] == "verified_success"
    assert json.loads((pending[0] / "transaction_receipt.json").read_text(encoding="utf-8")) == {
        "status": "failed_unexpected",
        "failed_fold": 1,
        "detail": "deterministic fold-1 failure",
    }


def test_all_fold_transaction_publishes_every_terminal_fold_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A successful all-fold run must appear only as one complete final publication."""
    constructed = 0

    class SuccessfulFold:
        def __init__(self, **_kwargs: object) -> None:
            nonlocal constructed
            self.fold_position = constructed
            constructed += 1

        def train(self, **kwargs: object) -> None:
            checkpoint = Path(str(kwargs["output_dir"])) / "best_model.pth"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_bytes(f"fold-{self.fold_position}".encode("utf-8"))

    arguments, output = _all_fold_cli_arguments(tmp_path)
    monkeypatch.setitem(sys.modules, "rfdetr", types.SimpleNamespace(RFDETRLarge=SuccessfulFold))
    monkeypatch.setattr(sys, "argv", arguments)

    status = main()

    assert status == 0
    assert output.is_dir()
    assert constructed == 5
    assert sorted(path.name for path in output.iterdir()) == [f"fold-{index}" for index in range(5)]
    assert [
        json.loads((output / f"fold-{index}" / "receipt.json").read_text(encoding="utf-8"))["status"]
        for index in range(5)
    ] == ["verified_success"] * 5
    assert not list(tmp_path.glob(".runs.pending-*"))
