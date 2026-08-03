"""Build leak-free RepViT 15+5 fold sources and fail-closed training receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

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
    return selected


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


def _unverified_receipts(output: Path, folds: Iterable[int], *, status: str, detail: str) -> int:
    for fold_index in folds:
        _write_json_new(output / f"fold-{fold_index}" / _RECEIPT_NAME, {
            "schema_version": 1,
            "fold_index": fold_index,
            "status": status,
            "detail": detail,
            "class_order": list(CANONICAL_CLASS_ORDER),
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "code_sha256": _file_sha256(Path(__file__)),
        })
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
    arguments = parser.parse_args(argv)
    selected = tuple(range(5)) if arguments.fold == "all" else (int(arguments.fold),)
    output = arguments.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to reuse output root: {output}")
    missing = []
    for label, path in (("base checkpoint", arguments.base_checkpoint), ("runtime receipt", arguments.runtime_receipt)):
        if path is None or not path.is_file():
            missing.append(label)
    if missing:
        return _unverified_receipts(output, selected, status="unverified_missing_repvit_train_inputs", detail=f"missing required local input(s): {', '.join(missing)}; no automatic download attempted")
    if not _is_sha256(arguments.base_checkpoint_sha256) or _file_sha256(arguments.base_checkpoint) != arguments.base_checkpoint_sha256:
        return _unverified_receipts(output, selected, status="unverified_repvit_base_hash_mismatch", detail="declared RepViT base checkpoint SHA-256 did not verify")
    try:
        load_fold_sources(arguments.dataset_root, arguments.splits)
    except Exception as exc:
        return _unverified_receipts(output, selected, status="unverified_repvit_sources", detail=f"verified fold sources unavailable: {type(exc).__name__}: {exc}")
    return _unverified_receipts(output, selected, status="unverified_repvit_training_not_executed", detail="validated inputs are present but this source-only producer requires the provisioned training runtime adapter")


if __name__ == "__main__":
    raise SystemExit(main())
