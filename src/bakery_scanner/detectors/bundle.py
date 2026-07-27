"""Immutable final D-FINE 640 plus four-state verifier bundle contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import torch
from torch.utils.data import DataLoader

from bakery_scanner.contracts import Box, BreadProposal, VerifierState
from bakery_scanner.verifier.data import build_verifier_examples
from bakery_scanner.verifier.model import (
    CLASS_ORDER,
    MODEL_NAME,
    PREPROCESSING,
    VerifierTrainingConfig,
    _VerifierCropDataset,
    _fit,
    _predict_candidates,
    _require_cuda0_rtx5080,
    _seed_everything,
    _write_training_examples,
    build_mobilenetv4_verifier,
)


_SHA256 = re.compile(r"[0-9a-f]{64}")
_ARTIFACT_LABELS = {
    "detector_checkpoint": "detector checkpoint",
    "detector_config": "detector config",
    "verifier_checkpoint": "verifier checkpoint",
    "verifier_config": "verifier config",
    "verifier_training_examples": "verifier training examples",
    "final_policy": "final policy",
    "staged_annotations": "staged annotations",
    "staged_manifest": "staged manifest",
    "development_report": "development report",
    "smoke_results": "smoke results",
}


@dataclass(frozen=True, slots=True)
class _FinalTrainingInputs:
    image_files: Mapping[int, str]
    ground_truth: Mapping[int, tuple[Box, ...]]


def validate_final_bundle(
    bundle_root: Path,
    *,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> None:
    """Raise unless every immutable final-bundle member and its hash is present."""
    root = Path(bundle_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            "verifier checkpoint is unavailable because bundle manifest is missing"
        )
    manifest = _read_json_object(manifest_path, "final bundle manifest")
    required_sections = {
        "artifacts",
        "detector",
        "runtime",
        "schema_version",
        "seed",
        "training_data",
        "verifier",
    }
    if set(manifest) != required_sections:
        raise ValueError("final bundle manifest fields are incomplete")
    if manifest["schema_version"] != 1:
        raise ValueError("final bundle schema version must be 1")
    if manifest["seed"] != 20260724:
        raise ValueError("final bundle seed must be 20260724")

    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACT_LABELS):
        raise ValueError(
            "detector checkpoint, verifier checkpoint, configs, policy, "
            "training-data/report hashes, and smoke results are required"
        )
    resolved_artifacts = {
        name: _validate_artifact(root, artifacts[name], label)
        for name, label in _ARTIFACT_LABELS.items()
    }
    committed_files = {
        manifest_path.resolve(),
        *(path.resolve() for path in resolved_artifacts.values()),
    }
    observed_files = {
        path.resolve() for path in root.rglob("*") if path.is_file()
    }
    if observed_files != committed_files:
        raise ValueError("final bundle contains an unhashed bundle member")

    _validate_detector_metadata(manifest["detector"])
    _validate_verifier_metadata(manifest["verifier"])
    _validate_runtime_metadata(manifest["runtime"])
    _validate_training_data(
        manifest["training_data"],
        annotations_path=resolved_artifacts["staged_annotations"],
        staged_manifest_path=resolved_artifacts["staged_manifest"],
        expected_images=expected_staged_images,
        expected_boxes=expected_staged_boxes,
    )
    _validate_final_policy(resolved_artifacts["final_policy"])
    validate_smoke_results(
        _read_json_array(resolved_artifacts["smoke_results"], "smoke results")
    )


def train_final_verifier(
    *,
    annotations: Path,
    staged_manifest: Path,
    images: Path,
    output_dir: Path,
    device: str,
    config: VerifierTrainingConfig | None = None,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> Path:
    """Train the four-state verifier once on every staged image using cuda:0."""
    if device != "cuda:0":
        raise ValueError("final verifier training requires device cuda:0")
    _require_cuda0_rtx5080()
    output = Path(output_dir)
    if output.exists():
        raise ValueError("refusing to overwrite final verifier output")
    inputs = _load_final_training_inputs(
        annotations=Path(annotations),
        staged_manifest=Path(staged_manifest),
        expected_images=expected_staged_images,
        expected_boxes=expected_staged_boxes,
    )
    examples = tuple(
        build_verifier_examples(
            image_ids=frozenset(inputs.image_files),
            ground_truth=inputs.ground_truth,
            seed=(config or VerifierTrainingConfig()).seed,
        )
    )
    if not examples or {row.state for row in examples} != set(VerifierState):
        raise ValueError("full-data verifier examples must cover all four states")
    training_config = config or VerifierTrainingConfig()
    _seed_everything(training_config.seed)
    output.mkdir(parents=True)
    _write_canonical_json(
        output / "verifier_config.json", training_config.to_dict()
    )
    _write_training_examples(output / "training_examples.json", examples)
    model = build_mobilenetv4_verifier(
        pretrained=training_config.pretrained
    ).to(device)
    dataset = _VerifierCropDataset(
        examples=examples,
        image_files=inputs.image_files,
        images_root=Path(images),
    )
    generator = torch.Generator()
    generator.manual_seed(training_config.seed)
    loader = DataLoader(
        dataset,
        batch_size=training_config.batch_size,
        shuffle=True,
        num_workers=training_config.num_workers,
        generator=generator,
        pin_memory=True,
    )
    _fit(model, loader, config=training_config, device=device)
    checkpoint = output / "verifier.pt"
    torch.save(
        {
            "class_order": CLASS_ORDER,
            "model_name": MODEL_NAME,
            "preprocessing": PREPROCESSING,
            "seed": training_config.seed,
            "state_dict": model.state_dict(),
            "training_scope": "all_staged_images",
        },
        checkpoint,
    )
    return checkpoint


def run_one_image_verifier_smoke(
    *,
    checkpoint: Path,
    detector_predictions: Path,
    annotations: Path,
    images: Path,
    output: Path,
    device: str,
) -> Path:
    """Run the final verifier over one image's GPU D-FINE smoke candidates."""
    if device != "cuda:0":
        raise ValueError("final smoke inference requires device cuda:0")
    _require_cuda0_rtx5080()
    image_files, image_sizes = _load_image_metadata(Path(annotations))
    rows = _read_json_array(Path(detector_predictions), "detector smoke predictions")
    if not rows:
        raise ValueError("detector smoke inference must retain at least one candidate")
    candidates: list[BreadProposal] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("detector smoke prediction rows must be objects")
        image_id = row.get("image_id")
        if image_id not in image_files:
            raise ValueError("detector smoke prediction image is not staged")
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("detector smoke prediction bbox must be xywh")
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
    if len({candidate.image_id for candidate in candidates}) != 1:
        raise ValueError("detector smoke predictions must cover exactly one image")

    checkpoint_payload = torch.load(
        Path(checkpoint), map_location=device, weights_only=True
    )
    if (
        not isinstance(checkpoint_payload, dict)
        or checkpoint_payload.get("class_order") != CLASS_ORDER
        or checkpoint_payload.get("model_name") != MODEL_NAME
        or checkpoint_payload.get("preprocessing") != PREPROCESSING
        or not isinstance(checkpoint_payload.get("state_dict"), dict)
    ):
        raise ValueError("final verifier checkpoint metadata is invalid")
    model = build_mobilenetv4_verifier(pretrained=False).to(device)
    model.load_state_dict(checkpoint_payload["state_dict"], strict=True)
    predictions = _predict_candidates(
        model,
        candidates=candidates,
        image_files=image_files,
        images_root=Path(images),
        batch_size=VerifierTrainingConfig().batch_size,
        device=device,
    )
    payload = []
    for candidate, prediction in zip(candidates, predictions, strict=True):
        probabilities = list(prediction.probabilities)
        payload.append(
            {
                "bbox": [
                    candidate.box.x,
                    candidate.box.y,
                    candidate.box.width,
                    candidate.box.height,
                ],
                "image_height": candidate.image_height,
                "image_id": candidate.image_id,
                "image_width": candidate.image_width,
                "outcome": CLASS_ORDER[
                    max(range(4), key=lambda index: probabilities[index])
                ],
                "probabilities": probabilities,
            }
        )
    validate_smoke_results(payload)
    return _write_canonical_json(Path(output), payload)


def write_final_policy_from_report(*, report: Path, output: Path) -> Path:
    """Freeze a conservative recall-first policy from five cross-fit policies."""
    if Path(output).exists():
        raise ValueError("refusing to overwrite final policy")
    payload = _read_json_object(Path(report), "development report")
    if payload.get("operational_guarantee") is not False:
        raise ValueError("final policy requires a development-only report")
    policies = payload.get("policies")
    if not isinstance(policies, dict) or set(policies) != {
        str(fold) for fold in range(5)
    }:
        raise ValueError("development report must contain five cross-fit policies")
    detector_thresholds = []
    verifier_thresholds = []
    for fold in range(5):
        row = policies[str(fold)]
        if not isinstance(row, dict):
            raise ValueError("cross-fit policy rows must be objects")
        detector_thresholds.append(row.get("detector_score_threshold"))
        verifier_thresholds.append(row.get("minimum_exactly_one_probability"))
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= 1
        for value in (*detector_thresholds, *verifier_thresholds)
    ):
        raise ValueError("cross-fit policy thresholds must be probabilities")
    return _write_canonical_json(
        Path(output),
        {
            "detector_score_threshold": min(detector_thresholds),
            "minimum_exactly_one_probability": min(verifier_thresholds),
        },
    )


def write_final_bundle_manifest(
    bundle_root: Path,
    *,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> Path:
    """Hash fixed final-bundle members and write their GPU/runtime metadata."""
    _require_cuda0_rtx5080()
    root = Path(bundle_root)
    artifact_paths = {
        "detector_checkpoint": root / "detector" / "checkpoint.pth",
        "detector_config": root / "detector" / "dfine_n_640.yml",
        "verifier_checkpoint": root / "verifier" / "verifier.pt",
        "verifier_config": root / "verifier" / "verifier_config.json",
        "verifier_training_examples": root
        / "verifier"
        / "training_examples.json",
        "final_policy": root / "policy" / "final_policy.json",
        "staged_annotations": root / "evidence" / "annotations.json",
        "staged_manifest": root / "evidence" / "staged_manifest.json",
        "development_report": root
        / "evidence"
        / "development_report.json",
        "smoke_results": root / "smoke" / "results.json",
    }
    for name, path in artifact_paths.items():
        if not path.is_file():
            raise ValueError(f"{_ARTIFACT_LABELS[name]} is missing")
    manifest = {
        "artifacts": {
            name: {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256_file(path),
            }
            for name, path in artifact_paths.items()
        },
        "detector": {"input_size": 640, "name": "dfine_n_640"},
        "runtime": {
            "cuda_version": str(torch.version.cuda or ""),
            "device": "cuda:0",
            "gpu_name": torch.cuda.get_device_name(0),
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
        },
        "schema_version": 1,
        "seed": 20260724,
        "training_data": {
            "box_count": expected_staged_boxes,
            "image_count": expected_staged_images,
        },
        "verifier": {
            "class_order": list(CLASS_ORDER),
            "model_name": MODEL_NAME,
            "preprocessing": PREPROCESSING,
        },
    }
    manifest_path = _write_canonical_json(root / "manifest.json", manifest)
    validate_final_bundle(
        root,
        expected_staged_images=expected_staged_images,
        expected_staged_boxes=expected_staged_boxes,
    )
    return manifest_path


def validate_smoke_results(results: Sequence[object]) -> None:
    """Validate one-image detector/verifier smoke output in source coordinates."""
    if (
        not isinstance(results, Sequence)
        or isinstance(results, (str, bytes))
        or not results
    ):
        raise ValueError("smoke results must contain at least one detector result")
    expected_fields = {
        "bbox",
        "image_height",
        "image_id",
        "image_width",
        "outcome",
        "probabilities",
    }
    image_ids: set[int] = set()
    for row in results:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise ValueError("smoke result fields are incomplete")
        image_id = row["image_id"]
        width = row["image_width"]
        height = row["image_height"]
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or isinstance(width, bool)
            or not isinstance(width, int)
            or width <= 0
            or isinstance(height, bool)
            or not isinstance(height, int)
            or height <= 0
        ):
            raise ValueError("smoke result image identity and dimensions are invalid")
        image_ids.add(image_id)
        _validate_source_bbox(row["bbox"], width=width, height=height)
        _validate_probabilities(row["probabilities"])
        if row["outcome"] not in CLASS_ORDER:
            raise ValueError("smoke result must declare a four-state outcome")
        probabilities = row["probabilities"]
        expected_outcome = CLASS_ORDER[
            max(range(4), key=lambda index: probabilities[index])
        ]
        if row["outcome"] != expected_outcome:
            raise ValueError(
                "smoke four-state outcome must match probability argmax"
            )
    if len(image_ids) != 1:
        raise ValueError("smoke results must cover exactly one source image")


def _validate_artifact(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{label} path and hash are required")
    relative = value["path"]
    digest = value["sha256"]
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or "\\" in relative
    ):
        raise ValueError(f"{label} path must be a bundle-relative POSIX path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} path must stay inside bundle root") from exc
    if not path.is_file():
        raise ValueError(f"{label} is missing")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError(f"{label} hash must be a lowercase SHA-256 digest")
    if _sha256_file(path) != digest:
        raise ValueError(f"{label} hash mismatch")
    return path


def _load_final_training_inputs(
    *,
    annotations: Path,
    staged_manifest: Path,
    expected_images: int,
    expected_boxes: int,
) -> _FinalTrainingInputs:
    coco = _read_json_object(annotations, "staged annotations")
    image_rows = coco.get("images")
    annotation_rows = coco.get("annotations")
    manifest_rows = _read_json_array(staged_manifest, "staged manifest")
    if (
        not isinstance(image_rows, list)
        or not isinstance(annotation_rows, list)
        or len(image_rows) != expected_images
        or len(annotation_rows) != expected_boxes
        or len(manifest_rows) != expected_images
    ):
        raise ValueError(
            f"final training requires {expected_images} images and "
            f"{expected_boxes} boxes"
        )
    image_files: dict[int, str] = {}
    for row in image_rows:
        if not isinstance(row, dict):
            raise ValueError("staged image rows must be objects")
        image_id = row.get("id")
        file_name = row.get("file_name")
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or image_id in image_files
            or not isinstance(file_name, str)
            or not file_name
        ):
            raise ValueError("staged images require unique IDs and paths")
        image_files[image_id] = file_name
    if _unique_positive_ids(manifest_rows, "staged manifest") != frozenset(
        image_files
    ):
        raise ValueError("staged annotations and manifest image IDs must match")
    ground_truth_lists = {image_id: [] for image_id in image_files}
    for row in annotation_rows:
        if not isinstance(row, dict) or row.get("image_id") not in image_files:
            raise ValueError("every staged box must reference a staged image")
        bbox = row.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("staged annotation bbox must be xywh")
        ground_truth_lists[row["image_id"]].append(Box(*bbox))
    return _FinalTrainingInputs(
        image_files=image_files,
        ground_truth={
            image_id: tuple(boxes)
            for image_id, boxes in ground_truth_lists.items()
        },
    )


def _load_image_metadata(
    annotations: Path,
) -> tuple[dict[int, str], dict[int, tuple[int, int]]]:
    coco = _read_json_object(annotations, "smoke annotations")
    rows = coco.get("images")
    if not isinstance(rows, list) or not rows:
        raise ValueError("smoke annotations require at least one image")
    files: dict[int, str] = {}
    sizes: dict[int, tuple[int, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("smoke image rows must be objects")
        image_id = row.get("id")
        file_name = row.get("file_name")
        width, height = row.get("width"), row.get("height")
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or image_id in files
            or not isinstance(file_name, str)
            or not file_name
            or isinstance(width, bool)
            or not isinstance(width, int)
            or width <= 0
            or isinstance(height, bool)
            or not isinstance(height, int)
            or height <= 0
        ):
            raise ValueError("smoke images require unique IDs, paths, and sizes")
        files[image_id] = file_name
        sizes[image_id] = (width, height)
    return files, sizes


def _validate_detector_metadata(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("detector metadata is required")
    if value.get("name") != "dfine_n_640" or value.get("input_size") != 640:
        raise ValueError("detector metadata must declare D-FINE-N at 640 pixels")


def _validate_verifier_metadata(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("verifier metadata is required")
    if value.get("model_name") != MODEL_NAME:
        raise ValueError(f"verifier model must be {MODEL_NAME}")
    if value.get("class_order") != list(CLASS_ORDER):
        raise ValueError("verifier class order is invalid")
    if value.get("preprocessing") != PREPROCESSING:
        raise ValueError("verifier preprocessing is invalid")


def _validate_runtime_metadata(value: object) -> None:
    if not isinstance(value, dict) or value.get("device") != "cuda:0":
        raise ValueError("final bundle runtime must declare device cuda:0")
    gpu_name = value.get("gpu_name")
    if not isinstance(gpu_name, str) or "RTX 5080" not in gpu_name:
        raise ValueError("final bundle runtime must record the RTX 5080 GPU")
    for name in ("cuda_version", "python_version", "torch_version"):
        version = value.get(name)
        if not isinstance(version, str) or not version:
            raise ValueError(f"final bundle runtime must record {name}")


def _validate_training_data(
    value: object,
    *,
    annotations_path: Path,
    staged_manifest_path: Path,
    expected_images: int,
    expected_boxes: int,
) -> None:
    if (
        isinstance(expected_images, bool)
        or not isinstance(expected_images, int)
        or expected_images <= 0
        or isinstance(expected_boxes, bool)
        or not isinstance(expected_boxes, int)
        or expected_boxes <= 0
    ):
        raise ValueError("expected staged counts must be positive integers")
    if not isinstance(value, dict):
        raise ValueError("training data metadata is required")
    expected_message = f"{expected_images} images and {expected_boxes} boxes"
    if value.get("image_count") != expected_images or value.get(
        "box_count"
    ) != expected_boxes:
        raise ValueError(f"final bundle must use exactly {expected_message}")
    annotations = _read_json_object(annotations_path, "staged annotations")
    image_rows = annotations.get("images")
    annotation_rows = annotations.get("annotations")
    staged_rows = _read_json_array(staged_manifest_path, "staged manifest")
    if (
        not isinstance(image_rows, list)
        or not isinstance(annotation_rows, list)
        or len(image_rows) != expected_images
        or len(annotation_rows) != expected_boxes
        or len(staged_rows) != expected_images
    ):
        raise ValueError(f"final bundle must use exactly {expected_message}")
    image_ids = _unique_positive_ids(image_rows, "staged annotations")
    manifest_ids = _unique_positive_ids(staged_rows, "staged manifest")
    if image_ids != manifest_ids:
        raise ValueError("staged annotations and manifest image IDs must match")
    for row in annotation_rows:
        if not isinstance(row, dict) or row.get("image_id") not in image_ids:
            raise ValueError("every staged box must reference a staged image")


def _validate_final_policy(path: Path) -> None:
    policy = _read_json_object(path, "final policy")
    expected = {
        "detector_score_threshold",
        "minimum_exactly_one_probability",
    }
    if set(policy) != expected:
        raise ValueError("final policy must contain both calibrated thresholds")
    for name in expected:
        value = policy[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0 <= float(value) <= 1
        ):
            raise ValueError(f"final policy {name} must be a probability")


def _validate_source_bbox(value: object, *, width: int, height: int) -> None:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("smoke result bbox must be xywh")
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(float(item))
        for item in value
    ):
        raise ValueError("smoke result bbox must contain finite coordinates")
    x, y, box_width, box_height = (float(item) for item in value)
    if (
        x < 0
        or y < 0
        or box_width <= 0
        or box_height <= 0
        or x + box_width > width
        or y + box_height > height
    ):
        raise ValueError("smoke detector box must stay within source image bounds")


def _validate_probabilities(value: object) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0 <= float(item) <= 1
            for item in value
        )
    ):
        raise ValueError("smoke verifier probabilities must be four probabilities")
    if not math.isclose(
        sum(float(item) for item in value), 1.0, rel_tol=0.0, abs_tol=1e-6
    ):
        raise ValueError("smoke verifier probabilities must sum to one within 1e-6")


def _unique_positive_ids(rows: Sequence[object], label: str) -> frozenset[int]:
    ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} rows must be objects")
        image_id = row.get("image_id", row.get("id"))
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or image_id in ids
        ):
            raise ValueError(f"{label} image IDs must be unique positive integers")
        ids.add(image_id)
    return frozenset(ids)


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be readable UTF-8 JSON") from exc


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
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_canonical_json(path: Path, value: object) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return target


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train-verifier")
    train.add_argument("--annotations", type=Path, required=True)
    train.add_argument("--staged-manifest", type=Path, required=True)
    train.add_argument("--images", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--device", default="cuda:0")

    smoke = subparsers.add_parser("smoke-verifier")
    smoke.add_argument("--checkpoint", type=Path, required=True)
    smoke.add_argument("--detector-predictions", type=Path, required=True)
    smoke.add_argument("--annotations", type=Path, required=True)
    smoke.add_argument("--images", type=Path, required=True)
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--device", default="cuda:0")

    policy = subparsers.add_parser("write-policy")
    policy.add_argument("--report", type=Path, required=True)
    policy.add_argument("--output", type=Path, required=True)

    manifest = subparsers.add_parser("write-manifest")
    manifest.add_argument("--bundle-root", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--bundle-root", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "train-verifier":
        train_final_verifier(
            annotations=args.annotations,
            staged_manifest=args.staged_manifest,
            images=args.images,
            output_dir=args.output_dir,
            device=args.device,
        )
    elif args.command == "smoke-verifier":
        run_one_image_verifier_smoke(
            checkpoint=args.checkpoint,
            detector_predictions=args.detector_predictions,
            annotations=args.annotations,
            images=args.images,
            output=args.output,
            device=args.device,
        )
    elif args.command == "write-policy":
        write_final_policy_from_report(report=args.report, output=args.output)
    elif args.command == "write-manifest":
        write_final_bundle_manifest(args.bundle_root)
    else:
        validate_final_bundle(args.bundle_root)


if __name__ == "__main__":
    _main()
