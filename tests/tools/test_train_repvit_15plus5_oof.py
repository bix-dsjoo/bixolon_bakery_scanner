from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import torch
from PIL import Image

from tools.train.train_repvit_15plus5_oof import (
    CalibrationCheckpoint,
    CANONICAL_CLASS_MAP,
    EvidenceSource,
    FoldSources,
    TorchRepVitTrainingBackend,
    balanced_epoch_rows,
    build_repvit_sources,
    configure_repvit_trainable_parameters,
    select_calibration_checkpoint,
    run_fold_training,
    run_output_transaction,
    verify_runtime_receipt,
    verify_canonical_split_files,
)


def _sources() -> FoldSources:
    isolated = tuple(
        EvidenceSource(sku_id, "isolated", f"isolated-{sku_id}-{index}", Path(f"i-{sku_id}-{index}.jpg"), "a" * 64)
        for sku_id in range(1, 21)
        for index in range(2 if sku_id == 1 else 1)
    )
    scenes = (
        EvidenceSource(1, "train_scene", "train-a#000", Path("train-a.jpg"), "b" * 64, scene_id="train-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(2, "train_scene", "train-b#000", Path("train-b.jpg"), "c" * 64, scene_id="train-b", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(1, "calibration_scene", "cal-a#000", Path("cal-a.jpg"), "d" * 64, scene_id="cal-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
        EvidenceSource(1, "evaluation_scene", "eval-a#000", Path("eval-a.jpg"), "e" * 64, scene_id="eval-a", box_xywh=(0.0, 0.0, 10.0, 10.0)),
    )
    return FoldSources(
        isolated=isolated,
        scenes=scenes,
        folds={0: {"train": ("train-a", "train-b"), "calibration": ("cal-a",), "evaluation": ("eval-a",)}},
        source_manifest_sha256="f" * 64,
        fold_manifest_sha256={0: "0" * 64},
    )


def test_eval_scene_crop_never_enters_repvit_training() -> None:
    fold_sources = _sources()

    rows = build_repvit_sources(fold_sources, fold_index=0)

    assert not set(rows.scene_ids) & set(fold_sources.evaluation_scene_ids(0))
    assert not set(rows.scene_ids) & set(fold_sources.calibration_scene_ids(0))
    assert set(rows.source_roles) == {"isolated", "train_scene"}


def test_balanced_epoch_equalizes_skus_and_sources_deterministically() -> None:
    rows = build_repvit_sources(_sources(), fold_index=0)

    first = balanced_epoch_rows(rows, seed=20260803)
    second = balanced_epoch_rows(rows, seed=20260803)

    assert [row.identity for row in first] == [row.identity for row in second]
    per_sku = {sku_id: [row for row in first if row.sku_id == sku_id] for sku_id in range(1, 21)}
    assert len({len(values) for values in per_sku.values()}) == 1
    for sku_id in (1, 2):
        roles = [row.source_role for row in per_sku[sku_id]]
        assert roles.count("isolated") == roles.count("train_scene")


def test_repvit_source_manifest_binds_exact_class_order_and_rows() -> None:
    rows = build_repvit_sources(_sources(), fold_index=0)

    payload = rows.manifest_payload()

    assert payload["class_order"] == list(range(1, 21))
    assert payload["class_map"][0] == {"id": 1, "name": "Walnut Donut"}
    assert payload["class_map"][-1] == {"id": 20, "name": "Plain Bread"}
    assert payload["fold_manifest_sha256"] == "0" * 64
    assert payload["source_manifest_sha256"] == "f" * 64
    assert set(payload["source_counts"]) == {str(sku_id) for sku_id in range(1, 21)}
    assert len(payload["rows_sha256"]) == 64


def test_only_final_stage_and_head_are_trainable() -> None:
    class Model(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = torch.nn.Linear(2, 2)
            self.stages = torch.nn.ModuleList((torch.nn.Linear(2, 2), torch.nn.Linear(2, 2)))
            self.head = torch.nn.Linear(2, 20)

    model = Model()

    names = configure_repvit_trainable_parameters(model)

    assert names
    assert all(name.startswith(("stages.1.", "head.")) for name in names)
    assert not any(parameter.requires_grad for parameter in model.stem.parameters())
    assert not any(parameter.requires_grad for parameter in model.stages[0].parameters())
    assert all(parameter.requires_grad for parameter in model.stages[1].parameters())
    assert all(parameter.requires_grad for parameter in model.head.parameters())


def test_torch_backend_initializes_20_way_head_from_declared_base(monkeypatch, tmp_path: Path) -> None:
    class Model(torch.nn.Module):
        def __init__(self, classes: int) -> None:
            super().__init__()
            self.stem = torch.nn.Linear(2, 2)
            self.stages = torch.nn.ModuleList((torch.nn.Linear(2, 2), torch.nn.Linear(2, 2)))
            self.head = torch.nn.Linear(2, classes)

    base_model = Model(1000)
    with torch.no_grad():
        base_model.stem.weight.fill_(0.25)
    base = tmp_path / "imagenet-base.pt"
    torch.save(base_model.state_dict(), base)
    monkeypatch.setitem(sys.modules, "timm", type("Timm", (), {
        "create_model": staticmethod(lambda name, *, pretrained, num_classes: Model(num_classes))
    }))

    loaded = TorchRepVitTrainingBackend(device="cpu").load_base(base, class_map=CANONICAL_CLASS_MAP)

    assert loaded.head.out_features == 20
    assert torch.equal(loaded.stem.weight, base_model.stem.weight)


def test_checkpoint_selection_uses_only_calibration_role(tmp_path: Path) -> None:
    candidates = (
        CalibrationCheckpoint(1, tmp_path / "epoch-1.pt", "calibration", 0.4),
        CalibrationCheckpoint(2, tmp_path / "epoch-2.pt", "calibration", 0.2),
    )

    assert select_calibration_checkpoint(candidates).epoch == 2

    with pytest.raises(ValueError, match="only calibration"):
        select_calibration_checkpoint((CalibrationCheckpoint(1, tmp_path / "bad.pt", "evaluation", 0.1),))


def test_full_repvit_fold_trains_loaded_balanced_crops_and_selects_only_calibration(tmp_path: Path) -> None:
    sources = _sources_with_images(tmp_path)

    class Model(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = torch.nn.Linear(2, 2)
            self.stages = torch.nn.ModuleList((torch.nn.Linear(2, 2), torch.nn.Linear(2, 2)))
            self.head = torch.nn.Linear(2, 20)

    class Backend:
        def __init__(self) -> None:
            self.train_roles = []
            self.calibration_roles = []

        def load_base(self, path, *, class_map):
            assert path.read_bytes() == b"base"
            assert [row["id"] for row in class_map] == list(range(1, 21))
            return Model()

        def train_epoch(self, model, examples, *, seed):
            self.train_roles.append({example.source.source_role for example in examples})
            assert all(crop.mode == "RGB" for example in examples for crop in example.crops)
            return {"loss": 1.0 / seed}

        def calibration_loss(self, model, examples):
            self.calibration_roles.append({example.source.source_role for example in examples})
            return 0.4 if len(self.calibration_roles) == 1 else 0.2

        def save_checkpoint(self, model, path, *, class_index):
            torch.save({"state_dict": model.state_dict(), "class_index": class_index}, path)

        def build_prototypes(self, model, examples):
            return torch.eye(384, dtype=torch.float32)[:20]

    base = tmp_path / "base.pt"
    base.write_bytes(b"base")
    backend = Backend()

    receipt = run_fold_training(
        sources,
        fold_index=0,
        base_checkpoint=base,
        base_checkpoint_sha256=hashlib.sha256(b"base").hexdigest(),
        runtime_identity={"receipt_sha256": "1" * 64},
        backend=backend,
        output_root=tmp_path / "run",
        epochs=2,
    )

    assert backend.train_roles == [{"isolated", "train_scene"}] * 2
    assert backend.calibration_roles == [{"calibration_scene"}] * 2
    assert receipt["status"] == "verified_success"
    assert receipt["selection"]["role"] == "calibration"
    assert receipt["selection"]["epoch"] == 2
    assert receipt["checkpoint"]["sha256"] == _sha256(tmp_path / "run" / "fold-0" / "checkpoint.pt")
    assert receipt["prototype_bank"]["shape"] == [20, 384]
    manifest = json.loads((tmp_path / "run" / "fold-0" / "manifest.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in manifest["class_map"]] == list(range(1, 21))
    assert receipt["manifest"]["sha256"] == _sha256(tmp_path / "run" / "fold-0" / "manifest.json")
    assert not any("eval" in identity for identity in receipt["provenance"]["training_source_identities"])


def _sources_with_images(root: Path) -> FoldSources:
    isolated = []
    for sku_id in range(1, 21):
        path = root / f"isolated-{sku_id}.png"
        Image.new("RGB", (16, 16), (sku_id, 0, 0)).save(path)
        isolated.append(EvidenceSource(sku_id, "isolated", path.name, path, _sha256(path)))
    scenes = []
    for role, scene_id in (("train_scene", "train-a"), ("calibration_scene", "cal-a"), ("evaluation_scene", "eval-a")):
        path = root / f"{scene_id}.png"
        Image.new("RGB", (20, 20), "white").save(path)
        scenes.append(EvidenceSource(1, role, f"{scene_id}#000", path, _sha256(path), scene_id=scene_id, box_xywh=(2.0, 2.0, 10.0, 10.0)))
    return FoldSources(
        tuple(isolated), tuple(scenes),
        {0: {"train": ("train-a",), "calibration": ("cal-a",), "evaluation": ("eval-a",)}},
        "e" * 64, {0: "f" * 64},
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_receipt_verifies_interpreter_package_and_artifact_bytes(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_bytes(b"module")
    base = tmp_path / "base.pt"
    base.write_bytes(b"base")
    payload = {
        "schema_version": 1,
        "interpreter": {"path": str(Path(sys.executable).resolve()), "bytes": Path(sys.executable).stat().st_size, "sha256": _sha256(Path(sys.executable))},
        "packages": {"fixture": {"version": "1.0", "module_path": str(module.resolve()), "bytes": module.stat().st_size, "sha256": _sha256(module)}},
        "artifacts": {"base": {"path": str(base.resolve()), "bytes": base.stat().st_size, "sha256": _sha256(base)}},
    }
    payload["receipt_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = tmp_path / "runtime.json"
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    verified = verify_runtime_receipt(receipt, required_packages=("fixture",), required_artifacts={"base": base})

    assert verified["receipt_sha256"] == payload["receipt_sha256"]
    blank = tmp_path / "blank.json"
    blank.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime receipt"):
        verify_runtime_receipt(blank, required_packages=("fixture",), required_artifacts={"base": base})


def test_canonical_split_admission_rejects_self_hashed_reassignment(tmp_path: Path) -> None:
    expected = {"inventory.json": b'{"canonical":true}', "fold-0.json": b'{"role":"train"}'}
    for name, content in expected.items():
        (tmp_path / name).write_bytes(content)
    verify_canonical_split_files(tmp_path, expected)
    reassigned = {"role": "evaluation"}
    reassigned["manifest_sha256"] = hashlib.sha256(json.dumps(reassigned, sort_keys=True).encode()).hexdigest()
    (tmp_path / "fold-0.json").write_text(json.dumps(reassigned), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical Task 1"):
        verify_canonical_split_files(tmp_path, expected)


def test_multifold_output_is_published_only_after_every_fold_succeeds(tmp_path: Path) -> None:
    output = tmp_path / "published"

    receipts = run_output_transaction(
        output,
        (0, 1),
        producer="repvit",
        fold_action=lambda fold_index, pending: _write_fold_fixture(pending, fold_index),
    )

    assert [row["fold_index"] for row in receipts] == [0, 1]
    assert (output / "fold-0" / "receipt.json").is_file()
    assert (output / "fold-1" / "receipt.json").is_file()
    assert json.loads((output / "transaction.json").read_text(encoding="utf-8"))["status"] == "verified_success"
    assert not list(tmp_path.glob(".published.pending-*"))


def test_multifold_failure_retains_pending_evidence_without_publishing(tmp_path: Path) -> None:
    output = tmp_path / "published"

    def fail_second(fold_index: int, pending: Path):
        if fold_index == 1:
            raise RuntimeError("fold two failed")
        return _write_fold_fixture(pending, fold_index)

    with pytest.raises(RuntimeError, match="fold two"):
        run_output_transaction(output, (0, 1), producer="repvit", fold_action=fail_second)

    assert not output.exists()
    pending = list(tmp_path.glob(".published.pending-*"))
    assert len(pending) == 1
    assert (pending[0] / "fold-0" / "receipt.json").is_file()
    failure = json.loads((pending[0] / "transaction.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed_incomplete_transaction"
    assert failure["completed_folds"] == [0]


def _write_fold_fixture(root: Path, fold_index: int) -> dict[str, object]:
    fold = root / f"fold-{fold_index}"
    fold.mkdir(parents=True)
    receipt = {"status": "verified_success", "fold_index": fold_index}
    (fold / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return receipt
