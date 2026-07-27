"""MobileNetV4 verifier model and grouped out-of-fold training runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import torch
from PIL import Image
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms import InterpolationMode
from torchvision.transforms import v2

from bakery_scanner.contracts import Box, BreadProposal, SceneKey, VerifierState
from bakery_scanner.detectors.proposal_policy import retain_raw_proposals
from bakery_scanner.verifier.data import (
    VerifierExample,
    build_verifier_examples,
    verifier_generation_metadata,
)


MODEL_NAME = "mobilenetv4_conv_small"
CLASS_ORDER = tuple(state.name for state in VerifierState)
PREPROCESSING: dict[str, object] = {
    "color_mode": "RGB",
    "input_size": [224, 224],
    "interpolation": "bicubic",
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
}
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class VerifierPrediction:
    image_id: int
    crop_xywh: Box
    probabilities: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if (
            isinstance(self.image_id, bool)
            or not isinstance(self.image_id, int)
            or self.image_id <= 0
        ):
            raise ValueError("image_id must be a positive integer")
        if not isinstance(self.crop_xywh, Box):
            raise ValueError("crop_xywh must be a Box")
        values = tuple(float(value) for value in self.probabilities)
        if (
            len(values) != 4
            or any(not math.isfinite(value) or not 0 <= value <= 1 for value in values)
            or not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-6)
        ):
            raise ValueError("probabilities must be four finite values summing to one")
        object.__setattr__(self, "probabilities", values)


@dataclass(frozen=True, slots=True)
class VerifierTrainingConfig:
    model_name: str = MODEL_NAME
    seed: int = 20260724
    epochs: int = 20
    batch_size: int = 64
    learning_rate: float = 3e-4
    weight_decay: float = 1e-2
    num_workers: int = 0
    pretrained: bool = True

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["class_order"] = list(CLASS_ORDER)
        payload["preprocessing"] = PREPROCESSING
        return payload


@dataclass(frozen=True, slots=True)
class _FoldInputs:
    fold: int
    training_image_ids: frozenset[int]
    validation_image_ids: frozenset[int]
    image_files: Mapping[int, str]
    ground_truth: Mapping[int, tuple[Box, ...]]
    candidates: tuple[BreadProposal, ...]


def classify_verifier_batch(model: nn.Module, crops: Tensor) -> Tensor:
    """Return a ``[batch, 4]`` softmax probability tensor."""
    logits = model(crops)
    if not isinstance(logits, Tensor) or logits.ndim != 2:
        raise ValueError("verifier model must return a two-dimensional tensor")
    if logits.shape != (crops.shape[0], 4):
        raise ValueError("verifier model must return one four-logit row per crop")
    return torch.softmax(logits, dim=1)


def build_mobilenetv4_verifier(*, pretrained: bool = True) -> nn.Module:
    """Create the pinned timm MobileNetV4 classifier with exactly four logits."""
    import timm

    return timm.create_model(MODEL_NAME, pretrained=pretrained, num_classes=4)


def build_verifier_receipt(
    *,
    checkpoint: Path,
    fold_manifest: Path,
    config: Path,
    fold: int,
    seed: int,
    verifier_predictions: Path | None = None,
) -> dict[str, object]:
    """Build the immutable fold receipt, including Task 2 public metadata."""
    _require_fold(fold)
    receipt = {
        "checkpoint_sha256": _sha256_file(checkpoint),
        "class_order": list(CLASS_ORDER),
        "config_sha256": _sha256_file(config),
        "device": "cuda:0",
        "fold": fold,
        "fold_manifest_sha256": _sha256_file(fold_manifest),
        "model_name": MODEL_NAME,
        "preprocessing": PREPROCESSING,
        "seed": seed,
        "status": "completed",
        "training_examples": verifier_generation_metadata(seed=seed).to_dict(),
    }
    if verifier_predictions is not None:
        receipt["verifier_predictions_sha256"] = _sha256_file(verifier_predictions)
    return receipt


def verifier_receipt_core_sha256(receipt: Mapping[str, object]) -> str:
    """Hash the receipt portion that predates its prediction artifact.

    Prediction rows point at this core because a full receipt also commits to
    the prediction file, which would otherwise create an impossible hash cycle.
    """
    core = dict(receipt)
    core.pop("verifier_predictions_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def write_verifier_predictions(
    output: Path,
    *,
    predictions: Sequence[VerifierPrediction],
    fold: int,
    validation_image_ids: frozenset[int],
    verifier_receipt_sha256: str,
) -> None:
    """Write canonical predictions restricted to one target fold."""
    _require_fold(fold)
    if not _SHA256.fullmatch(verifier_receipt_sha256):
        raise ValueError("verifier_receipt_sha256 must be a lowercase SHA-256 digest")
    rows: list[dict[str, object]] = []
    identities: set[tuple[int, Box]] = set()
    for prediction in predictions:
        if not isinstance(prediction, VerifierPrediction):
            raise ValueError("predictions must contain VerifierPrediction values")
        if prediction.image_id not in validation_image_ids:
            raise ValueError("verifier prediction must belong to the held-out fold")
        identity = (prediction.image_id, prediction.crop_xywh)
        if identity in identities:
            raise ValueError("duplicate verifier prediction candidate")
        identities.add(identity)
        box = prediction.crop_xywh
        rows.append(
            {
                "bbox": [box.x, box.y, box.width, box.height],
                "fold": fold,
                "image_id": prediction.image_id,
                "probabilities": list(prediction.probabilities),
                "verifier_receipt_sha256": verifier_receipt_sha256,
            }
        )
    rows.sort(key=lambda row: (row["image_id"], row["bbox"][1], row["bbox"][0], row["bbox"][3], row["bbox"][2]))
    _write_canonical_json(Path(output), rows)


class VerifierOofRunner:
    """Train one verifier fold and predict only its held-out D-FINE candidates."""

    def __init__(self, config: VerifierTrainingConfig | None = None) -> None:
        self.config = config or VerifierTrainingConfig()

    def train(
        self,
        train_manifest: Path,
        output_dir: Path,
        *,
        device: str,
        annotations: Path | None = None,
        images: Path | None = None,
        detector_predictions: Path | None = None,
        fold_root: Path | None = None,
        staged_manifest: Path | None = None,
    ) -> None:
        """Train on manifest training IDs, then infer target-fold candidates."""
        if device != "cuda:0":
            raise ValueError("verifier training requires device cuda:0")
        if (
            annotations is None
            or images is None
            or detector_predictions is None
            or fold_root is None
            or staged_manifest is None
        ):
            raise ValueError(
                "annotations, images, detector_predictions, fold_root, and staged_manifest are required"
            )
        _validate_five_fold_integrity(Path(fold_root), Path(staged_manifest))
        _require_cuda0_rtx5080()

        manifest_path = Path(train_manifest)
        output_path = Path(output_dir)
        if output_path.exists():
            raise ValueError("refusing to overwrite verifier fold output")
        fold_inputs = _load_fold_inputs(
            manifest_path=manifest_path,
            annotations_path=Path(annotations),
            detector_predictions_path=Path(detector_predictions),
        )
        configured_manifest = (
            Path(fold_root) / f"fold-{fold_inputs.fold}" / "manifest.json"
        )
        if manifest_path.resolve() != configured_manifest.resolve():
            raise ValueError("training manifest must be the configured target-fold manifest")
        examples = tuple(
            build_verifier_examples(
                image_ids=fold_inputs.training_image_ids,
                ground_truth=fold_inputs.ground_truth,
                seed=self.config.seed,
            )
        )
        if not examples or {example.state for example in examples} != set(VerifierState):
            raise ValueError("training fold must produce all four verifier states")

        _seed_everything(self.config.seed)
        output_path.mkdir(parents=True)
        config_path = output_path / "verifier_config.json"
        _write_canonical_json(config_path, self.config.to_dict())
        _write_training_examples(output_path / "training_examples.json", examples)

        model = build_mobilenetv4_verifier(
            pretrained=self.config.pretrained
        ).to(device)
        train_dataset = _VerifierCropDataset(
            examples=examples,
            image_files=fold_inputs.image_files,
            images_root=Path(images),
        )
        generator = torch.Generator()
        generator.manual_seed(self.config.seed)
        loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=self.config.num_workers,
            generator=generator,
            pin_memory=True,
        )
        _fit(model, loader, config=self.config, device=device)

        checkpoint_path = output_path / "verifier.pt"
        torch.save(
            {
                "class_order": CLASS_ORDER,
                "fold": fold_inputs.fold,
                "model_name": MODEL_NAME,
                "preprocessing": PREPROCESSING,
                "seed": self.config.seed,
                "state_dict": model.state_dict(),
            },
            checkpoint_path,
        )

        # All label-derived data was frozen above.  This inference path consumes
        # only target-fold image files and detector candidates.
        predictions = _predict_candidates(
            model,
            candidates=fold_inputs.candidates,
            image_files=fold_inputs.image_files,
            images_root=Path(images),
            batch_size=self.config.batch_size,
            device=device,
        )
        receipt = build_verifier_receipt(
            checkpoint=checkpoint_path,
            fold_manifest=manifest_path,
            config=config_path,
            fold=fold_inputs.fold,
            seed=self.config.seed,
        )
        prediction_path = output_path / "verifier_predictions.json"
        write_verifier_predictions(
            prediction_path,
            predictions=predictions,
            fold=fold_inputs.fold,
            validation_image_ids=fold_inputs.validation_image_ids,
            verifier_receipt_sha256=verifier_receipt_core_sha256(receipt),
        )
        receipt_path = output_path / "receipt.json"
        _write_canonical_json(
            receipt_path,
            build_verifier_receipt(
                checkpoint=checkpoint_path,
                fold_manifest=manifest_path,
                config=config_path,
                fold=fold_inputs.fold,
                seed=self.config.seed,
                verifier_predictions=prediction_path,
            ),
        )


class _VerifierCropDataset(Dataset[tuple[Tensor, Tensor]]):
    def __init__(
        self,
        *,
        examples: Sequence[VerifierExample],
        image_files: Mapping[int, str],
        images_root: Path,
    ) -> None:
        self.examples = tuple(examples)
        self.image_files = image_files
        self.images_root = images_root

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        example = self.examples[index]
        crop = _load_crop(
            self.images_root / self.image_files[example.image_id],
            example.crop_xywh,
        )
        return crop, torch.tensor(int(example.state), dtype=torch.long)


class _CandidateCropDataset(Dataset[Tensor]):
    def __init__(
        self,
        *,
        candidates: Sequence[BreadProposal],
        image_files: Mapping[int, str],
        images_root: Path,
    ) -> None:
        self.candidates = tuple(candidates)
        self.image_files = image_files
        self.images_root = images_root

    def __len__(self) -> int:
        return len(self.candidates)

    def __getitem__(self, index: int) -> Tensor:
        candidate = self.candidates[index]
        return _load_crop(
            self.images_root / self.image_files[candidate.image_id],
            candidate.box,
        )


_TRANSFORM = v2.Compose(
    (
        v2.Resize(
            (PREPROCESSING["input_size"][0], PREPROCESSING["input_size"][1]),
            interpolation=InterpolationMode.BICUBIC,
            antialias=True,
        ),
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(
            mean=PREPROCESSING["mean"],
            std=PREPROCESSING["std"],
        ),
    )
)


def _load_crop(path: Path, box: Box) -> Tensor:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        crop = rgb.crop(box.xyxy)
        return _TRANSFORM(crop)


def _fit(
    model: nn.Module,
    loader: DataLoader[tuple[Tensor, Tensor]],
    *,
    config: VerifierTrainingConfig,
    device: str,
) -> None:
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    loss_function = nn.CrossEntropyLoss()
    model.train()
    for _ in range(config.epochs):
        for crops, labels in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(
                crops.to(device, non_blocking=True)
            )
            if logits.shape != (crops.shape[0], 4):
                raise ValueError("MobileNetV4 verifier must emit four logits")
            loss = loss_function(logits, labels.to(device, non_blocking=True))
            loss.backward()
            optimizer.step()


def _predict_candidates(
    model: nn.Module,
    *,
    candidates: Sequence[BreadProposal],
    image_files: Mapping[int, str],
    images_root: Path,
    batch_size: int,
    device: str,
) -> tuple[VerifierPrediction, ...]:
    dataset = _CandidateCropDataset(
        candidates=candidates,
        image_files=image_files,
        images_root=images_root,
    )
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )
    rows: list[VerifierPrediction] = []
    model.eval()
    offset = 0
    with torch.inference_mode():
        for crops in loader:
            probabilities = classify_verifier_batch(
                model, crops.to(device, non_blocking=True)
            ).cpu()
            for values in probabilities.tolist():
                candidate = candidates[offset]
                rows.append(
                    VerifierPrediction(
                        image_id=candidate.image_id,
                        crop_xywh=candidate.box,
                        probabilities=tuple(values),
                    )
                )
                offset += 1
    if offset != len(candidates):
        raise ValueError("verifier inference did not cover every candidate")
    return tuple(rows)


def _load_fold_inputs(
    *,
    manifest_path: Path,
    annotations_path: Path,
    detector_predictions_path: Path,
) -> _FoldInputs:
    manifest = _read_json_object(manifest_path, "fold manifest")
    fold = manifest.get("index")
    _require_fold(fold)
    training_ids = _positive_int_set(
        manifest.get("training_image_ids"), "training_image_ids"
    )
    validation_ids = _positive_int_set(
        manifest.get("validation_image_ids"), "validation_image_ids"
    )
    if not training_ids or not validation_ids or training_ids & validation_ids:
        raise ValueError("fold training and validation image IDs must be disjoint")

    coco = _read_json_object(annotations_path, "staged annotations")
    image_rows = coco.get("images")
    annotation_rows = coco.get("annotations")
    if not isinstance(image_rows, list) or not isinstance(annotation_rows, list):
        raise ValueError("staged annotations require images and annotations arrays")
    image_files: dict[int, str] = {}
    image_sizes: dict[int, tuple[int, int]] = {}
    for row in image_rows:
        if not isinstance(row, dict):
            raise ValueError("staged image must be an object")
        image_id, file_name = row.get("id"), row.get("file_name")
        width, height = row.get("width"), row.get("height")
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or image_id in image_files
            or not isinstance(file_name, str)
            or not file_name
            or isinstance(width, bool)
            or not isinstance(width, int)
            or width <= 0
            or isinstance(height, bool)
            or not isinstance(height, int)
            or height <= 0
        ):
            raise ValueError("staged images require unique IDs, paths, and sizes")
        image_files[image_id] = file_name
        image_sizes[image_id] = (width, height)
    if not training_ids | validation_ids <= image_files.keys():
        raise ValueError("fold IDs must exist in staged annotations")

    # Validation annotations are deliberately never placed in this mapping.
    ground_truth_lists: dict[int, list[Box]] = {
        image_id: [] for image_id in training_ids
    }
    for row in annotation_rows:
        if not isinstance(row, dict):
            raise ValueError("staged annotation must be an object")
        image_id = row.get("image_id")
        if image_id not in training_ids:
            continue
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("training annotation bbox must be xywh")
        ground_truth_lists[image_id].append(Box(*bbox))
    ground_truth = {
        image_id: tuple(boxes)
        for image_id, boxes in ground_truth_lists.items()
    }

    candidate_rows = _read_json_array(
        detector_predictions_path, "D-FINE validation predictions"
    )
    candidates: list[BreadProposal] = []
    for row in candidate_rows:
        if not isinstance(row, dict):
            raise ValueError("D-FINE validation prediction must be an object")
        image_id = row.get("image_id")
        if image_id not in validation_ids:
            raise ValueError("D-FINE candidate must belong to the target fold")
        if row.get("source") != "dfine_n_640":
            raise ValueError("verifier inference accepts only dfine_n_640 D-FINE candidates")
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("D-FINE candidate bbox must be xywh")
        width, height = image_sizes[image_id]
        candidates.append(
            BreadProposal(
                image_id=image_id,
                source=row.get("source"),
                score=row.get("score"),
                box=Box(*bbox),
                image_width=width,
                image_height=height,
            )
        )
    retained = tuple(retain_raw_proposals(candidates))
    return _FoldInputs(
        fold=fold,
        training_image_ids=training_ids,
        validation_image_ids=validation_ids,
        image_files=image_files,
        ground_truth=ground_truth,
        candidates=retained,
    )


def validate_completed_verifier_fold(
    *,
    run_root: Path,
    fold_manifest: Path,
    annotations: Path,
    detector_predictions: Path,
) -> None:
    """Reject any completed verifier artifact not exactly tied to its candidates."""
    run_root = Path(run_root)
    inputs = _load_fold_inputs(
        manifest_path=Path(fold_manifest),
        annotations_path=Path(annotations),
        detector_predictions_path=Path(detector_predictions),
    )
    receipt_path = run_root / "receipt.json"
    prediction_path = run_root / "verifier_predictions.json"
    checkpoint_path = run_root / "verifier.pt"
    config_path = run_root / "verifier_config.json"
    receipt = _read_json_object(receipt_path, "verifier receipt")
    required = {
        "checkpoint_sha256": _sha256_file(checkpoint_path),
        "config_sha256": _sha256_file(config_path),
        "fold_manifest_sha256": _sha256_file(Path(fold_manifest)),
        "fold": inputs.fold,
        "model_name": MODEL_NAME,
        "device": "cuda:0",
        "status": "completed",
        "verifier_predictions_sha256": _sha256_file(prediction_path),
    }
    if any(receipt.get(key) != value for key, value in required.items()):
        raise ValueError("verifier receipt identity or artifact hash mismatch")
    if receipt.get("class_order") != list(CLASS_ORDER):
        raise ValueError("verifier receipt class order is invalid")
    config = _read_json_object(config_path, "verifier config")
    if config.get("class_order") != list(CLASS_ORDER):
        raise ValueError("verifier config class order is invalid")
    _validate_prediction_rows(
        rows=_read_json_array(prediction_path, "verifier predictions"),
        candidates=inputs.candidates,
        fold=inputs.fold,
        receipt_core_sha256=verifier_receipt_core_sha256(receipt),
    )


def _validate_prediction_rows(
    *,
    rows: Sequence[object],
    candidates: Sequence[BreadProposal],
    fold: int,
    receipt_core_sha256: str,
) -> None:
    expected = {(candidate.image_id, candidate.box) for candidate in candidates}
    observed: set[tuple[int, Box]] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "bbox", "fold", "image_id", "probabilities", "verifier_receipt_sha256"
        }:
            raise ValueError("verifier prediction row has invalid fields")
        image_id, bbox = row["image_id"], row["bbox"]
        if isinstance(image_id, bool) or not isinstance(image_id, int):
            raise ValueError("verifier prediction image ID is invalid")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("verifier prediction bbox is invalid")
        try:
            prediction = VerifierPrediction(
                image_id=image_id,
                crop_xywh=Box(*bbox),
                probabilities=tuple(row["probabilities"]),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("verifier prediction probabilities or geometry are invalid") from exc
        if row["fold"] != fold or row["verifier_receipt_sha256"] != receipt_core_sha256:
            raise ValueError("verifier prediction fold or receipt reference is invalid")
        identity = (prediction.image_id, prediction.crop_xywh)
        if identity in observed:
            raise ValueError("duplicate verifier prediction candidate")
        observed.add(identity)
    if observed != expected:
        raise ValueError("verifier predictions do not exactly match the retained D-FINE candidate set")


def _validate_five_fold_integrity(fold_root: Path, staged_manifest_path: Path) -> None:
    """Require exact grouped five-fold coverage and complement training sets."""
    staged_rows = _read_json_array(Path(staged_manifest_path), "staged manifest")
    scene_by_id: dict[int, SceneKey] = {}
    ids_by_scene: dict[SceneKey, frozenset[int]] = {}
    mutable_scene_ids: dict[SceneKey, set[int]] = {}
    for row in staged_rows:
        if not isinstance(row, dict) or not isinstance(row.get("scene"), dict):
            raise ValueError("staged manifest must map every image to a capture scene")
        image_id = row.get("image_id")
        if isinstance(image_id, bool) or not isinstance(image_id, int) or image_id <= 0 or image_id in scene_by_id:
            raise ValueError("staged manifest image IDs must be unique positive integers")
        try:
            scene = SceneKey(row["scene"]["capture_batch"], row["scene"]["scene_number"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("staged manifest contains an invalid capture scene") from exc
        scene_by_id[image_id] = scene
        mutable_scene_ids.setdefault(scene, set()).add(image_id)
    if not scene_by_id:
        raise ValueError("staged manifest must not be empty")
    ids_by_scene = {scene: frozenset(ids) for scene, ids in mutable_scene_ids.items()}

    manifests: dict[int, tuple[frozenset[int], frozenset[int], frozenset[SceneKey], frozenset[SceneKey]]] = {}
    for fold in range(5):
        path = Path(fold_root) / f"fold-{fold}" / "manifest.json"
        manifest = _read_json_object(path, "fold manifest")
        if manifest.get("index") != fold:
            raise ValueError("configured fold manifest index is invalid")
        training = _positive_int_set(manifest.get("training_image_ids"), "training_image_ids")
        validation = _positive_int_set(manifest.get("validation_image_ids"), "validation_image_ids")
        training_scenes = _scene_set(manifest.get("training_scenes"), "training_scenes")
        validation_scenes = _scene_set(manifest.get("validation_scenes"), "validation_scenes")
        if not training or not validation or training & validation:
            raise ValueError("configured fold training and validation IDs must be disjoint")
        if not training | validation <= scene_by_id.keys():
            raise ValueError("configured fold IDs must exist in staged manifest")
        _require_whole_capture_scenes(validation, validation_scenes, scene_by_id, ids_by_scene, "validation")
        _require_whole_capture_scenes(training, training_scenes, scene_by_id, ids_by_scene, "training")
        manifests[fold] = (training, validation, training_scenes, validation_scenes)
    validation_union = frozenset().union(*(row[1] for row in manifests.values()))
    if validation_union != frozenset(scene_by_id) or sum(len(row[1]) for row in manifests.values()) != len(validation_union):
        raise ValueError("five configured validation folds must exactly cover each staged image once")
    for fold, (training, _, training_scenes, _) in manifests.items():
        other_validations = frozenset().union(*(row[1] for other, row in manifests.items() if other != fold))
        other_scenes = frozenset().union(*(row[3] for other, row in manifests.items() if other != fold))
        if training != other_validations or training_scenes != other_scenes:
            raise ValueError("training IDs and scenes must exactly equal the other four configured folds")


def _scene_set(value: object, label: str) -> frozenset[SceneKey]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    try:
        scenes = frozenset(
            SceneKey(row["capture_batch"], row["scene_number"])
            for row in value
            if isinstance(row, dict)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain valid capture scenes") from exc
    if len(scenes) != len(value):
        raise ValueError(f"{label} must contain unique capture scenes")
    return scenes


def _require_whole_capture_scenes(
    image_ids: frozenset[int],
    scenes: frozenset[SceneKey],
    scene_by_id: Mapping[int, SceneKey],
    ids_by_scene: Mapping[SceneKey, frozenset[int]],
    partition: str,
) -> None:
    if {scene_by_id[image_id] for image_id in image_ids} != scenes:
        raise ValueError(f"{partition} scenes do not match selected image IDs")
    for scene in scenes:
        if not ids_by_scene[scene] <= image_ids:
            raise ValueError(f"{partition} fold must contain every image from a whole capture scene")


def _write_training_examples(path: Path, examples: Sequence[VerifierExample]) -> None:
    _write_canonical_json(
        path,
        [
            {
                "bbox": [
                    row.crop_xywh.x,
                    row.crop_xywh.y,
                    row.crop_xywh.width,
                    row.crop_xywh.height,
                ],
                "image_id": row.image_id,
                "state": int(row.state),
            }
            for row in examples
        ],
    )


def _seed_everything(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def _require_cuda0_rtx5080() -> None:
    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise ValueError("verifier training requires RTX 5080 cuda:0")
    if "RTX 5080" not in torch.cuda.get_device_name(0):
        raise ValueError("verifier training requires RTX 5080 cuda:0")


def _require_fold(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value not in range(5):
        raise ValueError("fold must be an integer from 0 through 4")


def _positive_int_set(value: object, label: str) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result = frozenset(
        item
        for item in value
        if isinstance(item, int) and not isinstance(item, bool) and item > 0
    )
    if len(result) != len(value):
        raise ValueError(f"{label} must contain unique positive integers")
    return result


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON: {path}") from exc


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    value = _read_json(path, label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_json_array(path: Path, label: str) -> list[object]:
    value = _read_json(path, label)
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"required verifier artifact is missing: {path}") from exc


def _write_canonical_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(payload))


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train one grouped OOF MobileNetV4 verifier fold on cuda:0."
    )
    parser.add_argument("--fold-manifest", type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--images", type=Path)
    parser.add_argument("--detector-predictions", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--fold-root", type=Path)
    parser.add_argument("--staged-manifest", type=Path)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--validate-fold-integrity", action="store_true")
    parser.add_argument("--validate-completed-fold", action="store_true")
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.validate_fold_integrity:
        if args.fold_root is None or args.staged_manifest is None:
            raise ValueError("fold_root and staged_manifest are required for integrity validation")
        _validate_five_fold_integrity(args.fold_root, args.staged_manifest)
        return 0
    if args.validate_completed_fold:
        if None in (args.run_root, args.fold_manifest, args.annotations, args.detector_predictions):
            raise ValueError("run_root, fold_manifest, annotations, and detector_predictions are required")
        validate_completed_verifier_fold(
            run_root=args.run_root,
            fold_manifest=args.fold_manifest,
            annotations=args.annotations,
            detector_predictions=args.detector_predictions,
        )
        return 0
    if None in (
        args.fold_manifest,
        args.annotations,
        args.images,
        args.detector_predictions,
        args.output_dir,
        args.fold_root,
        args.staged_manifest,
    ):
        raise ValueError("all fold training arguments are required")
    VerifierOofRunner().train(
        args.fold_manifest,
        args.output_dir,
        device=args.device,
        annotations=args.annotations,
        images=args.images,
        detector_predictions=args.detector_predictions,
        fold_root=args.fold_root,
        staged_manifest=args.staged_manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
