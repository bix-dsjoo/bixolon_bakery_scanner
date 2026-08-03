"""Build leak-free RepViT 15+5 fold sources and fail-closed training receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Mapping, Protocol, Sequence

import torch
from PIL import Image

from bakery_scanner.classification.preprocess import ClassifierPreprocessDescriptor, build_crop_pair
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image
from bakery_scanner.data.oof15plus5 import build_oof_folds, write_oof_manifests
from bakery_scanner.data.sku_scene import SkuSceneInventory, load_inventory


CANONICAL_CLASS_ORDER = tuple(range(1, 21))
CANONICAL_CLASS_NAMES = (
    "Walnut Donut", "Croffle", "Waffle", "Scon", "Half-moon Croissant",
    "Croissant", "Flower Bread", "Almond Scon", "Dinner Roll", "Sugar Donut",
    "Bagel", "Egg Tart", "Muffin", "Burger", "Sandwich", "Grain Campagne",
    "Almond Campagne", "Mini Bread", "Pastry Bread", "Plain Bread",
)
CANONICAL_CLASS_MAP = tuple(
    {"id": sku_id, "name": name}
    for sku_id, name in zip(CANONICAL_CLASS_ORDER, CANONICAL_CLASS_NAMES, strict=True)
)
SourceRole = Literal["isolated", "train_scene", "calibration_scene", "evaluation_scene"]
_RECEIPT_NAME = "receipt.json"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    sku_id: int
    source_role: SourceRole
    identity: str
    path: Path | None
    image_sha256: str
    scene_id: str | None = None
    box_xywh: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.sku_id not in CANONICAL_CLASS_ORDER:
            raise ValueError("evidence source SKU must be in canonical class order")
        if self.source_role == "isolated":
            if self.scene_id is not None or self.box_xywh is not None:
                raise ValueError("isolated evidence must not carry scene coordinates")
        elif self.scene_id is None or self.box_xywh is None:
            raise ValueError("scene evidence must carry scene identity and box")
        if not self.identity or not _is_sha256(self.image_sha256):
            raise ValueError("evidence source identity and image SHA-256 are required")


@dataclass(frozen=True, slots=True)
class FoldSources:
    isolated: tuple[EvidenceSource, ...]
    scenes: tuple[EvidenceSource, ...]
    folds: Mapping[int, Mapping[str, tuple[str, ...]]]
    source_manifest_sha256: str
    fold_manifest_sha256: Mapping[int, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "isolated", tuple(self.isolated))
        object.__setattr__(self, "scenes", tuple(self.scenes))
        if not _is_sha256(self.source_manifest_sha256):
            raise ValueError("source manifest SHA-256 is invalid")
        for fold_index, roles in self.folds.items():
            if type(fold_index) is not int or set(roles) != {"train", "calibration", "evaluation"}:
                raise ValueError("each fold must define exact train/calibration/evaluation roles")
            role_sets = [set(roles[name]) for name in ("train", "calibration", "evaluation")]
            if set.union(*role_sets) and sum(len(values) for values in role_sets) != len(set.union(*role_sets)):
                raise ValueError("fold scene roles must be disjoint")
            if not _is_sha256(self.fold_manifest_sha256.get(fold_index)):
                raise ValueError("fold manifest SHA-256 is invalid")

    def evaluation_scene_ids(self, fold_index: int) -> tuple[str, ...]:
        return tuple(self.folds[fold_index]["evaluation"])

    def calibration_scene_ids(self, fold_index: int) -> tuple[str, ...]:
        return tuple(self.folds[fold_index]["calibration"])


@dataclass(frozen=True, slots=True)
class FoldEvidenceRows:
    fold_index: int
    rows: tuple[EvidenceSource, ...]
    source_manifest_sha256: str
    fold_manifest_sha256: str

    @property
    def scene_ids(self) -> tuple[str, ...]:
        return tuple(row.scene_id for row in self.rows if row.scene_id is not None)

    @property
    def source_roles(self) -> tuple[str, ...]:
        return tuple(row.source_role for row in self.rows)

    def manifest_payload(self) -> dict[str, object]:
        counts = {
            str(sku_id): {
                role: sum(row.sku_id == sku_id and row.source_role == role for row in self.rows)
                for role in ("isolated", "train_scene")
            }
            for sku_id in CANONICAL_CLASS_ORDER
        }
        row_payload = [_source_payload(row) for row in sorted(self.rows, key=lambda value: value.identity)]
        return {
            "schema_version": 1,
            "class_order": list(CANONICAL_CLASS_ORDER),
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "fold_index": self.fold_index,
            "fold_manifest_sha256": self.fold_manifest_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_counts": counts,
            "rows_sha256": _canonical_sha256(row_payload),
        }


@dataclass(frozen=True, slots=True)
class CalibrationCheckpoint:
    epoch: int
    path: Path
    selection_role: str
    loss: float

    def __post_init__(self) -> None:
        if type(self.epoch) is not int or self.epoch <= 0:
            raise ValueError("checkpoint epoch must be positive")
        if not math.isfinite(self.loss) or self.loss < 0.0:
            raise ValueError("checkpoint calibration loss must be finite and non-negative")


def configure_repvit_trainable_parameters(model: object) -> tuple[str, ...]:
    """Freeze the early backbone and expose exactly the final stage and head."""
    named_parameters = getattr(model, "named_parameters", None)
    stages = getattr(model, "stages", None)
    head = getattr(model, "head", None)
    if not callable(named_parameters) or stages is None or head is None or len(stages) < 1:
        raise ValueError("RepViT model must expose stages, head, and named parameters")
    for _, parameter in named_parameters():
        parameter.requires_grad = False
    for parameter in stages[-1].parameters():
        parameter.requires_grad = True
    for parameter in head.parameters():
        parameter.requires_grad = True
    selected = tuple(sorted(name for name, parameter in named_parameters() if parameter.requires_grad))
    final_prefix = f"stages.{len(stages) - 1}."
    if not selected or any(not name.startswith((final_prefix, "head.")) for name in selected):
        raise ValueError("RepViT trainable parameters must be limited to final stage and head")
    _set_repvit_finetune_mode(model)
    return selected


def _set_repvit_finetune_mode(model: object) -> None:
    """Keep frozen modules deterministic while enabling only the declared trainable branches."""
    stages = getattr(model, "stages", None)
    head = getattr(model, "head", None)
    if not isinstance(model, torch.nn.Module) or stages is None or head is None or len(stages) < 1:
        raise ValueError("RepViT fine-tune mode requires stages and head")
    model.eval()
    stages[-1].train()
    head.train()


def select_calibration_checkpoint(
    candidates: Sequence[CalibrationCheckpoint],
) -> CalibrationCheckpoint:
    """Select deterministically without consulting training or evaluation metrics."""
    values = tuple(candidates)
    if not values:
        raise ValueError("checkpoint selection requires calibration candidates")
    if any(candidate.selection_role != "calibration" for candidate in values):
        raise ValueError("checkpoint selection may use only calibration role evidence")
    return min(values, key=lambda candidate: (candidate.loss, candidate.epoch, candidate.path.as_posix()))


@dataclass(frozen=True, slots=True)
class LoadedExample:
    source: EvidenceSource
    crops: tuple[Image.Image, ...]
    product_boxes: tuple[Box, ...]


class RepVitTrainingBackend(Protocol):
    def load_base(self, path: Path, *, class_map: Sequence[Mapping[str, object]]) -> torch.nn.Module: ...
    def train_epoch(self, model: torch.nn.Module, examples: Sequence[LoadedExample], *, seed: int) -> Mapping[str, float]: ...
    def calibration_loss(self, model: torch.nn.Module, examples: Sequence[LoadedExample]) -> float: ...
    def save_checkpoint(self, model: torch.nn.Module, path: Path, *, class_index: Mapping[int, int]) -> None: ...
    def build_prototypes(self, model: torch.nn.Module, examples: Sequence[LoadedExample]) -> torch.Tensor: ...


class TorchRepVitTrainingBackend:
    """Provisioned torch/timm adapter; never requests pretrained downloads."""

    def __init__(self, *, device: str = "cuda:0", batch_size: int = 32, learning_rate: float = 3e-4) -> None:
        self.device = torch.device(device)
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.transform = build_transform(224)
        self._optimizer: torch.optim.Optimizer | None = None

    def load_base(self, path: Path, *, class_map: Sequence[Mapping[str, object]]) -> torch.nn.Module:
        import timm
        payload = torch.load(path, map_location="cpu", weights_only=True)
        expected_index = {sku_id: sku_id - 1 for sku_id in CANONICAL_CLASS_ORDER}
        if tuple(class_map) != CANONICAL_CLASS_MAP:
            raise ValueError("RepViT base class names do not match canonical 15+5 catalog")
        if not isinstance(payload, dict):
            raise ValueError("declared RepViT base artifact must be a state dictionary")
        if "state_dict" in payload:
            if payload.get("class_index") not in (None, expected_index) or not isinstance(payload["state_dict"], dict):
                raise ValueError("declared RepViT base artifact class mapping is invalid")
            base_state = payload["state_dict"]
        else:
            base_state = payload
        if not base_state or any(not isinstance(name, str) or not isinstance(value, torch.Tensor) for name, value in base_state.items()):
            raise ValueError("declared RepViT base state dictionary is invalid")
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(20260803)
            model = timm.create_model("repvit_m1", pretrained=False, num_classes=20)
        target_state = model.state_dict()
        backbone_state = {
            name: value for name, value in base_state.items()
            if not name.startswith("head.") and name in target_state and value.shape == target_state[name].shape
        }
        missing_backbone = tuple(name for name in target_state if not name.startswith("head.") and name not in backbone_state)
        unexpected_backbone = tuple(name for name in base_state if not name.startswith("head.") and name not in target_state)
        if missing_backbone or unexpected_backbone:
            raise ValueError("declared RepViT base artifact does not exactly cover the backbone")
        model.load_state_dict(backbone_state, strict=False)
        return model.to(self.device)

    def train_epoch(self, model: torch.nn.Module, examples: Sequence[LoadedExample], *, seed: int) -> Mapping[str, float]:
        if self._optimizer is None:
            self._optimizer = torch.optim.AdamW((parameter for parameter in model.parameters() if parameter.requires_grad), lr=self.learning_rate)
        model.train()
        _set_repvit_finetune_mode(model)
        total_loss = 0.0
        count = 0
        for start in range(0, len(examples), self.batch_size):
            chunk = examples[start : start + self.batch_size]
            images = torch.stack(tuple(self.transform(_chosen_crop(example, seed)) for example in chunk)).to(self.device)
            labels = torch.tensor([example.source.sku_id - 1 for example in chunk], dtype=torch.long, device=self.device)
            self._optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            if tuple(logits.shape) != (len(chunk), 20):
                raise ValueError("RepViT training logits must have shape (N, 20)")
            loss = torch.nn.functional.cross_entropy(logits, labels)
            loss.backward()
            self._optimizer.step()
            total_loss += float(loss.detach().cpu()) * len(chunk)
            count += len(chunk)
        return {"loss": total_loss / count, "examples": float(count)}

    def calibration_loss(self, model: torch.nn.Module, examples: Sequence[LoadedExample]) -> float:
        model.eval()
        losses = []
        with torch.inference_mode():
            for example in examples:
                batch = torch.stack(tuple(self.transform(crop) for crop in example.crops)).to(self.device)
                logits = model(batch).mean(dim=0, keepdim=True)
                label = torch.tensor([example.source.sku_id - 1], dtype=torch.long, device=self.device)
                losses.append(float(torch.nn.functional.cross_entropy(logits, label).cpu()))
        return sum(losses) / len(losses)

    def save_checkpoint(self, model: torch.nn.Module, path: Path, *, class_index: Mapping[int, int]) -> None:
        torch.save({"state_dict": model.state_dict(), "class_index": dict(class_index)}, path)

    def build_prototypes(self, model: torch.nn.Module, examples: Sequence[LoadedExample]) -> torch.Tensor:
        model.eval()
        values: dict[int, list[torch.Tensor]] = {sku_id: [] for sku_id in CANONICAL_CLASS_ORDER}
        with torch.inference_mode():
            for example in examples:
                tensor = torch.stack(tuple(self.transform(crop) for crop in example.crops)).to(self.device)
                features = model.forward_features(tensor)
                if features.ndim != 4 or features.shape[0] != len(example.crops) or features.shape[1] != 384:
                    raise ValueError("RepViT prototype features must have 384 channels")
                per_crop = torch.nn.functional.normalize(features.mean(dim=(2, 3)).float(), dim=1)
                values[example.source.sku_id].append(torch.nn.functional.normalize(per_crop.mean(dim=0), dim=0).cpu())
        return torch.stack(tuple(torch.nn.functional.normalize(torch.stack(values[sku_id]).mean(dim=0), dim=0) for sku_id in CANONICAL_CLASS_ORDER))


def _chosen_crop(example: LoadedExample, seed: int) -> Image.Image:
    index = int(hashlib.sha256(f"{seed}:{example.source.identity}".encode()).hexdigest(), 16) % len(example.crops)
    return example.crops[index]


def run_fold_training(
    sources: FoldSources,
    *,
    fold_index: int,
    base_checkpoint: Path,
    base_checkpoint_sha256: str,
    runtime_identity: Mapping[str, object],
    backend: RepVitTrainingBackend,
    output_root: Path,
    epochs: int = 10,
    base_seed: int = 20260803,
) -> dict[str, object]:
    """Train and atomically publish one fully provenance-bound RepViT fold."""
    if type(epochs) is not int or epochs <= 0:
        raise ValueError("epochs must be a positive integer")
    base_checkpoint = Path(base_checkpoint).resolve()
    if not base_checkpoint.is_file() or _file_sha256(base_checkpoint) != base_checkpoint_sha256:
        raise ValueError("RepViT base checkpoint SHA-256 mismatch")
    if not _is_sha256(runtime_identity.get("receipt_sha256")):
        raise ValueError("verified runtime identity receipt SHA-256 is required")
    training_rows = build_repvit_sources(sources, fold_index=fold_index)
    calibration_rows = _build_calibration_sources(sources, fold_index=fold_index)
    training_examples = _load_examples(training_rows.rows)
    calibration_examples = _load_examples(calibration_rows)
    if {example.source.source_role for example in calibration_examples} != {"calibration_scene"}:
        raise ValueError("checkpoint selection requires only calibration-role crops")

    output_root = Path(output_root).resolve()
    final_root = output_root / f"fold-{fold_index}"
    if final_root.exists():
        raise FileExistsError(f"refusing to overwrite fold output: {final_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".fold-{fold_index}.pending-", dir=output_root))
    try:
        model = backend.load_base(base_checkpoint, class_map=CANONICAL_CLASS_MAP)
        trainable_names = configure_repvit_trainable_parameters(model)
        candidates: list[CalibrationCheckpoint] = []
        epoch_metrics: list[dict[str, object]] = []
        examples_by_identity = {example.source.identity: example for example in training_examples}
        for epoch in range(1, epochs + 1):
            seed = base_seed + fold_index * 10_000 + epoch
            epoch_rows = balanced_epoch_rows(training_rows, seed=seed)
            epoch_examples = tuple(examples_by_identity[row.identity] for row in epoch_rows)
            train_metrics = dict(backend.train_epoch(model, epoch_examples, seed=seed))
            loss = float(backend.calibration_loss(model, calibration_examples))
            if not math.isfinite(loss) or loss < 0.0:
                raise ValueError("calibration loss must be finite and non-negative")
            checkpoint = pending / f"epoch-{epoch:03d}.pt"
            backend.save_checkpoint(model, checkpoint, class_index={sku_id: sku_id - 1 for sku_id in CANONICAL_CLASS_ORDER})
            if not checkpoint.is_file():
                raise FileNotFoundError("RepViT backend did not produce declared checkpoint")
            candidates.append(CalibrationCheckpoint(epoch, checkpoint, "calibration", loss))
            epoch_metrics.append({"epoch": epoch, "seed": seed, "train": train_metrics, "calibration_loss": loss})
        selected = select_calibration_checkpoint(tuple(candidates))
        selected_payload = torch.load(selected.path, map_location="cpu", weights_only=True)
        expected_index = {sku_id: sku_id - 1 for sku_id in CANONICAL_CLASS_ORDER}
        if (
            not isinstance(selected_payload, dict)
            or selected_payload.get("class_index") != expected_index
            or not isinstance(selected_payload.get("state_dict"), dict)
        ):
            raise ValueError("selected RepViT checkpoint does not preserve the canonical class mapping")
        model.load_state_dict(selected_payload["state_dict"], strict=True)
        checkpoint_path = pending / "checkpoint.pt"
        shutil.copy2(selected.path, checkpoint_path)
        prototype_rows = balanced_epoch_rows(training_rows, seed=base_seed + fold_index * 10_000)
        prototype_examples = tuple(examples_by_identity[row.identity] for row in prototype_rows)
        prototypes = backend.build_prototypes(model, prototype_examples)
        _validate_prototypes(prototypes)
        prototype_path = pending / "prototype_bank.pt"
        descriptor_sha256 = ClassifierPreprocessDescriptor().sha256()
        torch.save({
            "artifact_type": "repvit_m1_15plus5_feature_prototypes",
            "checkpoint_sha256": _file_sha256(checkpoint_path),
            "preprocess_sha256": descriptor_sha256,
            "preprocess_descriptor": ClassifierPreprocessDescriptor().to_payload(),
            "class_order": list(CANONICAL_CLASS_ORDER),
            "prototypes": prototypes.detach().cpu().float(),
        }, prototype_path)
        manifest_path = pending / "manifest.json"
        _write_json_new(manifest_path, {
            "schema_version": 1,
            "model_id": "repvit_m1_15plus5_v1",
            "fold_index": fold_index,
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "checkpoint_sha256": _file_sha256(checkpoint_path),
            "prototype_bank_sha256": _file_sha256(prototype_path),
            "preprocess_sha256": descriptor_sha256,
            "preprocess_descriptor": ClassifierPreprocessDescriptor().to_payload(),
            "fold_manifest_sha256": training_rows.fold_manifest_sha256,
            "source_manifest_sha256": training_rows.source_manifest_sha256,
        })
        receipt = {
            "schema_version": 1,
            "status": "verified_success",
            "fold_index": fold_index,
            "checkpoint": _file_identity(checkpoint_path, shape=None, dtype=None),
            "prototype_bank": _file_identity(prototype_path, shape=[20, 384], dtype="float32"),
            "manifest": _file_identity(manifest_path, shape=None, dtype=None),
            "selection": {"role": "calibration", "epoch": selected.epoch, "loss": selected.loss},
            "metrics": epoch_metrics,
            "provenance": {
                "model_id": "repvit_m1_15plus5_v1",
                "base_checkpoint_sha256": base_checkpoint_sha256,
                "preprocess_sha256": descriptor_sha256,
                "fold_manifest_sha256": training_rows.fold_manifest_sha256,
                "source_manifest_sha256": training_rows.source_manifest_sha256,
                "source_rows_sha256": training_rows.manifest_payload()["rows_sha256"],
                "runtime_identity": dict(runtime_identity),
                "runtime_identity_sha256": _canonical_sha256(runtime_identity),
                "class_order": list(CANONICAL_CLASS_ORDER),
                "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
                "trainable_parameter_names": list(trainable_names),
                "source_counts": training_rows.manifest_payload()["source_counts"],
                "training_source_identities": sorted(example.source.identity for example in training_examples),
                "prototype_source_identities": [example.source.identity for example in prototype_examples],
                "calibration_source_identities": sorted(example.source.identity for example in calibration_examples),
                "code_sha256": _file_sha256(Path(__file__)),
            },
        }
        _write_json_new(pending / _RECEIPT_NAME, receipt)
        os.replace(pending, final_root)
        return receipt
    except Exception:
        (pending / "failure.json").write_text(
            json.dumps({"status": "failed_incomplete_fold", "fold_index": fold_index}, sort_keys=True),
            encoding="utf-8",
        )
        raise


def _build_calibration_sources(sources: FoldSources, *, fold_index: int) -> tuple[EvidenceSource, ...]:
    calibration_ids = set(sources.folds[fold_index]["calibration"])
    selected = []
    for row in sources.scenes:
        if row.scene_id in calibration_ids:
            selected.append(EvidenceSource(
                row.sku_id, "calibration_scene", row.identity, row.path, row.image_sha256,
                scene_id=row.scene_id, box_xywh=row.box_xywh,
            ))
    if not selected:
        raise ValueError("fold calibration sources must not be empty")
    return tuple(sorted(selected, key=lambda row: (row.sku_id, row.identity)))


def _load_examples(rows: Sequence[EvidenceSource]) -> tuple[LoadedExample, ...]:
    examples = []
    for row in rows:
        if row.path is None or not row.path.is_file() or _file_sha256(row.path) != row.image_sha256:
            raise ValueError(f"admitted source image SHA-256 mismatch: {row.identity}")
        with Image.open(row.path) as handle:
            frame = canonicalize_image(handle)
        if row.source_role == "isolated":
            crops = (frame.image.copy(),)
            product_boxes = (Box(0.0, 0.0, float(frame.image.width), float(frame.image.height)),)
        else:
            assert row.box_xywh is not None
            pair = build_crop_pair(frame, Box(*row.box_xywh))
            crops = (pair.tight, pair.context)
            product_boxes = (
                Box(0.0, 0.0, float(pair.tight.width), float(pair.tight.height)),
                pair.context_product_box,
            )
        examples.append(LoadedExample(row, crops, product_boxes))
    return tuple(examples)


def _validate_prototypes(value: torch.Tensor) -> None:
    if value.dtype != torch.float32 or tuple(value.shape) != (20, 384) or not torch.isfinite(value).all().item():
        raise ValueError("RepViT prototype tensor must be finite float32 with shape (20, 384)")
    if (value.norm(dim=1) == 0).any().item():
        raise ValueError("RepViT prototype tensor must cover every SKU with non-zero vectors")


def _file_identity(path: Path, *, shape: list[int] | None, dtype: str | None) -> dict[str, object]:
    result: dict[str, object] = {"file_name": path.name, "bytes": path.stat().st_size, "sha256": _file_sha256(path)}
    if shape is not None:
        result["shape"] = shape
    if dtype is not None:
        result["dtype"] = dtype
    return result


def build_repvit_sources(sources: FoldSources, *, fold_index: int) -> FoldEvidenceRows:
    """Select isolated images and only the requested fold's training scenes."""
    roles = sources.folds.get(fold_index)
    if roles is None:
        raise ValueError("requested fold is unavailable")
    training_ids = set(roles["train"])
    selected_scenes = tuple(row for row in sources.scenes if row.scene_id in training_ids)
    if any(row.source_role != "train_scene" for row in selected_scenes):
        raise ValueError("training scene identity has a non-training source role")
    selected = tuple(sorted((*sources.isolated, *selected_scenes), key=lambda row: (row.sku_id, row.source_role, row.identity)))
    if {row.sku_id for row in selected} != set(CANONICAL_CLASS_ORDER):
        raise ValueError("fold sources must cover the exact canonical 20-class order")
    forbidden = set(roles["calibration"]) | set(roles["evaluation"])
    if any(row.scene_id in forbidden for row in selected if row.scene_id is not None):
        raise ValueError("calibration/evaluation scene leaked into training sources")
    return FoldEvidenceRows(
        fold_index,
        selected,
        sources.source_manifest_sha256,
        sources.fold_manifest_sha256[fold_index],
    )


def balanced_epoch_rows(rows: FoldEvidenceRows, *, seed: int) -> tuple[EvidenceSource, ...]:
    """Deterministically equalize SKU and isolated/scene contribution per epoch."""
    if type(seed) is not int:
        raise ValueError("epoch seed must be an integer")
    grouped = {
        sku_id: {
            role: tuple(sorted((row for row in rows.rows if row.sku_id == sku_id and row.source_role == role), key=lambda row: row.identity))
            for role in ("isolated", "train_scene")
        }
        for sku_id in CANONICAL_CLASS_ORDER
    }
    if any(not any(groups.values()) for groups in grouped.values()):
        raise ValueError("every canonical SKU needs at least one training source")
    target = max(
        (2 * max(len(groups["isolated"]), len(groups["train_scene"])) if all(groups.values()) else len(groups["isolated"] or groups["train_scene"]))
        for groups in grouped.values()
    )
    if any(all(groups.values()) for groups in grouped.values()) and target % 2:
        target += 1
    selected: list[EvidenceSource] = []
    for sku_id, groups in grouped.items():
        active = tuple(role for role in ("isolated", "train_scene") if groups[role])
        role_target = target // len(active)
        if role_target * len(active) != target:
            raise ValueError("balanced target cannot be divided equally across active sources")
        for role in active:
            values = groups[role]
            selected.extend(values[index % len(values)] for index in range(role_target))
    return tuple(sorted(selected, key=lambda row: hashlib.sha256(f"{seed}:{row.sku_id}:{row.source_role}:{row.identity}".encode()).hexdigest()))


def load_fold_sources(dataset_root: Path, split_root: Path) -> FoldSources:
    inventory = load_inventory(Path(dataset_root))
    with tempfile.TemporaryDirectory(prefix="bakery-canonical-splits-") as temporary:
        regenerated = Path(temporary) / "rtx5080_15plus5_oof_v1"
        write_oof_manifests(build_oof_folds(inventory, seed=20260803), inventory, regenerated)
        verify_canonical_split_files(
            Path(split_root),
            {path.name: path.read_bytes() for path in regenerated.iterdir() if path.is_file()},
        )
    folds: dict[int, Mapping[str, tuple[str, ...]]] = {}
    fold_hashes: dict[int, str] = {}
    for path in sorted(Path(split_root).glob("fold-*.json")):
        payload = _verified_fold_manifest(path, inventory)
        fold_index = payload["fold_index"]
        folds[fold_index] = {name: tuple(payload["scene_ids"][name]) for name in ("train", "calibration", "evaluation")}
        fold_hashes[fold_index] = payload["manifest_sha256"]
    if set(folds) != set(range(5)):
        raise ValueError("split root must contain exactly five fold manifests")
    # Rows carry their fold-neutral physical identity. build_repvit_sources selects
    # by ID, while the role label is normalized to train_scene at selection time.
    isolated = tuple(
        EvidenceSource(row.sku_id, "isolated", row.identity, row.path, row.sha256)
        for sku_id in CANONICAL_CLASS_ORDER for row in inventory.isolated_by_sku[sku_id]
    )
    scene_rows = tuple(
        EvidenceSource(
            box.sku_id,
            "train_scene",
            f"{scene.scene_id}#{index:03d}",
            Path(dataset_root) / "detection" / scene.source_name / "images" / scene.file_name,
            scene.image_sha256,
            scene_id=scene.scene_id,
            box_xywh=box.box_xywh,
        )
        for scene in inventory.scenes for index, box in enumerate(scene.boxes)
    )
    return FoldSources(isolated, scene_rows, folds, inventory.source_sha256, fold_hashes)


def verify_canonical_split_files(split_root: Path, expected: Mapping[str, bytes]) -> None:
    split_root = Path(split_root)
    if (
        not split_root.is_dir()
        or {path.name for path in split_root.iterdir() if path.is_file()} != set(expected)
        or any((split_root / name).read_bytes() != content for name, content in expected.items())
    ):
        raise ValueError("split root does not byte-match canonical Task 1 manifests")


def verify_runtime_receipt(
    path: Path,
    *,
    required_packages: Sequence[str],
    required_artifacts: Mapping[str, Path],
) -> dict[str, object]:
    """Verify the receipt itself and every declared executable/module/artifact byte."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("runtime receipt is unreadable") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "interpreter", "packages", "artifacts", "receipt_sha256"} or payload.get("schema_version") != 1:
        raise ValueError("runtime receipt schema is invalid")
    declared = payload["receipt_sha256"]
    canonical = dict(payload)
    canonical.pop("receipt_sha256")
    if not _is_sha256(declared) or _canonical_sha256(canonical) != declared:
        raise ValueError("runtime receipt SHA-256 is invalid")
    interpreter = payload["interpreter"]
    if not isinstance(interpreter, dict):
        raise ValueError("runtime receipt interpreter is invalid")
    _verify_declared_file(interpreter, Path(sys.executable).resolve(), label="interpreter")
    packages = payload["packages"]
    if not isinstance(packages, dict) or not set(required_packages) <= set(packages):
        raise ValueError("runtime receipt required packages are missing")
    for name, record in packages.items():
        if not isinstance(record, dict):
            raise ValueError(f"runtime receipt package {name} is invalid")
        try:
            module = importlib.import_module(name)
            module_file = getattr(module, "__file__", None)
            distribution = importlib.metadata.distribution(name)
            actual_version = distribution.version
        except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
            raise ValueError(f"runtime receipt package {name} is not installed") from exc
        if (
            not isinstance(module_file, str)
            or not module_file
            or record.get("distribution") != name
            or record.get("version") != actual_version
        ):
            raise ValueError(f"runtime receipt package {name} version is invalid")
        resolved_module = Path(module_file).resolve()
        installed_files = distribution.files
        if installed_files is None or not any(
            Path(distribution.locate_file(entry)).resolve() == resolved_module
            for entry in installed_files
        ):
            raise ValueError(f"runtime receipt package {name} distribution does not own imported module")
        _verify_declared_file(record, resolved_module, label=f"package {name}", path_key="module_path")
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, dict) or not set(required_artifacts) <= set(artifacts):
        raise ValueError("runtime receipt required artifacts are missing")
    for name, record in artifacts.items():
        expected = Path(required_artifacts.get(name, Path(str(record.get("path", ""))))).resolve()
        _verify_declared_file(record, expected, label=f"artifact {name}")
    return payload


def _verify_declared_file(record: Mapping[str, object], expected: Path, *, label: str, path_key: str = "path") -> None:
    if set(record) - {path_key, "bytes", "sha256", "version", "distribution"} or Path(str(record.get(path_key, ""))).resolve() != expected:
        raise ValueError(f"runtime receipt {label} path is invalid")
    if not expected.is_file() or record.get("bytes") != expected.stat().st_size or not _is_sha256(record.get("sha256")) or _file_sha256(expected) != record["sha256"]:
        raise ValueError(f"runtime receipt {label} bytes are invalid")


def _verified_fold_manifest(path: Path, inventory: SkuSceneInventory) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source_sha256") != inventory.source_sha256:
        raise ValueError("fold manifest does not bind the verified source inventory")
    declared = payload.get("manifest_sha256")
    canonical = dict(payload)
    canonical.pop("manifest_sha256", None)
    if not _is_sha256(declared) or _canonical_sha256(canonical) != declared:
        raise ValueError("fold manifest SHA-256 mismatch")
    if payload.get("fold_index") not in range(5):
        raise ValueError("fold index must be 0 through 4")
    roles = payload.get("scene_ids")
    if not isinstance(roles, dict) or set(roles) != {"train", "calibration", "evaluation"}:
        raise ValueError("fold roles are invalid")
    known = {scene.scene_id for scene in inventory.scenes}
    if set().union(*(set(roles[name]) for name in roles)) != known:
        raise ValueError("fold scene identities do not exactly cover inventory")
    return payload


def _source_payload(row: EvidenceSource) -> dict[str, object]:
    return {
        "sku_id": row.sku_id,
        "source_role": row.source_role,
        "identity": row.identity,
        "image_sha256": row.image_sha256,
        "scene_id": row.scene_id,
        "box_xywh": list(row.box_xywh) if row.box_xywh is not None else None,
    }


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _write_json_new(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {path}")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def run_output_transaction(
    output: Path,
    folds: Iterable[int],
    *,
    producer: str,
    fold_action: Callable[[int, Path], dict[str, object]],
    transaction_status: str = "verified_success",
    failure_context: Mapping[str, object] | None = None,
    failure_unresolved_roles: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Publish a requested fold set only after every fold reaches a terminal receipt."""
    output = Path(output).resolve()
    selected = tuple(folds)
    if not selected or len(selected) != len(set(selected)) or any(fold not in range(5) for fold in selected):
        raise ValueError("transaction folds must be unique values from 0 through 4")
    if output.exists():
        raise FileExistsError(f"refusing to reuse output root: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".{output.name}.pending-", dir=output.parent))
    completed: list[int] = []
    receipts: list[dict[str, object]] = []
    try:
        for fold_index in selected:
            receipts.append(fold_action(fold_index, pending))
            completed.append(fold_index)
        _write_json_new(pending / "transaction.json", {
            "schema_version": 1,
            "producer": producer,
            "status": transaction_status,
            "requested_folds": list(selected),
            "completed_folds": completed,
            "fold_receipts_sha256": _canonical_sha256(receipts),
        })
        os.replace(pending, output)
        return tuple(receipts)
    except Exception as exc:
        resolved_context = dict(failure_context or {})
        for fold_index in selected:
            receipt_path = pending / f"fold-{fold_index}" / _RECEIPT_NAME
            if not receipt_path.exists():
                _write_json_new(receipt_path, {
                    "schema_version": 1,
                    "producer": producer,
                    "fold_index": fold_index,
                    "status": "unverified_failed_transaction",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "resolved_context": resolved_context,
                    "unresolved_roles": list(failure_unresolved_roles),
                })
        _write_json_new(pending / "transaction.json", {
            "schema_version": 1,
            "producer": producer,
            "status": "failed_incomplete_transaction",
            "requested_folds": list(selected),
            "completed_folds": completed,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "resolved_context": resolved_context,
            "unresolved_roles": list(failure_unresolved_roles),
        })
        raise


def _input_context(
    split_root: Path,
    *,
    sources: FoldSources | None = None,
    runtime_identity: Mapping[str, object] | None = None,
    resolved_files: Mapping[str, Path] | None = None,
    code_path: Path | None = None,
) -> dict[str, object]:
    split_root = Path(split_root).resolve()
    resolved_code = Path(code_path or __file__).resolve()
    split_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": _file_sha256(path)}
        for path in sorted(split_root.glob("*.json")) if path.is_file()
    }
    context: dict[str, object] = {
        "preprocess_sha256": ClassifierPreprocessDescriptor().sha256(),
        "split_root": str(split_root),
        "split_files": split_files,
        "code": {
            "path": str(resolved_code),
            "bytes": resolved_code.stat().st_size,
            "sha256": _file_sha256(resolved_code),
        },
    }
    if sources is not None:
        context["source_manifest_sha256"] = sources.source_manifest_sha256
        context["fold_manifest_sha256"] = {str(key): value for key, value in sources.fold_manifest_sha256.items()}
    if runtime_identity is not None:
        context["runtime_identity"] = dict(runtime_identity)
    if resolved_files is not None:
        context["resolved_files"] = {
            role: {
                "path": str(Path(path).resolve()),
                "bytes": Path(path).stat().st_size,
                "sha256": _file_sha256(Path(path)),
            }
            for role, path in resolved_files.items()
        }
    return context


def _unverified_receipts(
    output: Path,
    folds: Iterable[int],
    *,
    status: str,
    detail: str,
    context: Mapping[str, object],
    unresolved_roles: Sequence[str],
) -> int:
    def write_fold(fold_index: int, pending: Path) -> dict[str, object]:
        receipt = {
            "schema_version": 1,
            "fold_index": fold_index,
            "status": status,
            "detail": detail,
            "unresolved_roles": list(unresolved_roles),
            "resolved_context": dict(context),
            "class_order": list(CANONICAL_CLASS_ORDER),
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "code_sha256": _file_sha256(Path(__file__)),
        }
        _write_json_new(pending / f"fold-{fold_index}" / _RECEIPT_NAME, receipt)
        return receipt

    run_output_transaction(
        output, folds, producer="repvit_m1_15plus5_oof", fold_action=write_fold,
        transaction_status=status,
    )
    return 2


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--fold", choices=("0", "1", "2", "3", "4", "all"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, default=Path(r"C:\workspace\bixolon_bakery_scanner\datasets"))
    parser.add_argument("--base-checkpoint", type=Path)
    parser.add_argument("--base-checkpoint-sha256")
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--device", default="cuda:0")
    arguments = parser.parse_args(argv)
    selected = tuple(range(5)) if arguments.fold == "all" else (int(arguments.fold),)
    output = arguments.output.resolve()
    context = _input_context(arguments.splits)
    missing = []
    for label, path in (("base checkpoint", arguments.base_checkpoint), ("runtime receipt", arguments.runtime_receipt)):
        if path is None or not path.is_file():
            missing.append(label)
    if missing:
        return _unverified_receipts(
            output, selected, status="unverified_missing_repvit_train_inputs",
            detail=f"missing required local input(s): {', '.join(missing)}; no automatic download attempted",
            context=context, unresolved_roles=tuple(label.replace(" ", "_") for label in missing),
        )
    if not _is_sha256(arguments.base_checkpoint_sha256) or _file_sha256(arguments.base_checkpoint) != arguments.base_checkpoint_sha256:
        return _unverified_receipts(output, selected, status="unverified_repvit_base_hash_mismatch", detail="declared RepViT base checkpoint SHA-256 did not verify", context=context, unresolved_roles=("base_checkpoint_identity",))
    resolved_files = {"base_checkpoint": arguments.base_checkpoint}
    context = _input_context(arguments.splits, resolved_files=resolved_files)
    try:
        sources = load_fold_sources(arguments.dataset_root, arguments.splits)
    except Exception as exc:
        return _unverified_receipts(output, selected, status="unverified_repvit_sources", detail=f"verified fold sources unavailable: {type(exc).__name__}: {exc}", context=context, unresolved_roles=("canonical_sources",))
    context = _input_context(
        arguments.splits,
        sources=sources,
        resolved_files={**resolved_files, "runtime_receipt_candidate": arguments.runtime_receipt},
    )
    try:
        runtime_identity = verify_runtime_receipt(
            arguments.runtime_receipt,
            required_packages=("torch", "timm"),
            required_artifacts={"base_checkpoint": arguments.base_checkpoint},
        )
    except Exception as exc:
        return _unverified_receipts(output, selected, status="unverified_repvit_runtime", detail=f"runtime receipt verification failed: {type(exc).__name__}: {exc}", context=context, unresolved_roles=("runtime_identity",))
    context = _input_context(
        arguments.splits,
        sources=sources,
        runtime_identity=runtime_identity,
        resolved_files={**resolved_files, "runtime_receipt": arguments.runtime_receipt},
    )
    run_output_transaction(
        output,
        selected,
        producer="repvit_m1_15plus5_oof",
        fold_action=lambda fold_index, pending: run_fold_training(
            sources,
            fold_index=fold_index,
            base_checkpoint=arguments.base_checkpoint,
            base_checkpoint_sha256=arguments.base_checkpoint_sha256,
            runtime_identity=runtime_identity,
            backend=TorchRepVitTrainingBackend(device=arguments.device),
            output_root=pending,
            epochs=arguments.epochs,
        ),
        failure_context=context,
        failure_unresolved_roles=("repvit_fold_artifacts",),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
