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
    "detector_metadata": "detector metadata",
    "verifier_checkpoint": "verifier checkpoint",
    "verifier_config": "verifier config",
    "verifier_metadata": "verifier metadata",
    "verifier_training_examples": "verifier training examples",
    "final_policy": "final policy",
    "staged_annotations": "staged annotations",
    "staged_manifest": "staged manifest",
    "training_input_snapshot": "training input snapshot",
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
    _validate_bundle_training_snapshot(
        resolved_artifacts["training_input_snapshot"],
        staged_manifest_path=resolved_artifacts["staged_manifest"],
        expected_images=expected_staged_images,
    )
    _validate_final_policy(resolved_artifacts["final_policy"])
    _validate_detector_bundle_semantics(manifest, resolved_artifacts)
    _validate_verifier_bundle_semantics(manifest, resolved_artifacts)
    validate_smoke_results(
        _read_json_array(resolved_artifacts["smoke_results"], "smoke results"),
        detector_checkpoint_sha256=artifacts["detector_checkpoint"]["sha256"],
        detector_metadata_sha256=artifacts["detector_metadata"]["sha256"],
        verifier_checkpoint_sha256=artifacts["verifier_checkpoint"]["sha256"],
        verifier_metadata_sha256=artifacts["verifier_metadata"]["sha256"],
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
    output = Path(output_dir)
    if output.exists():
        raise ValueError("refusing to overwrite final verifier output")
    inputs = validate_staged_training_inputs(
        annotations=Path(annotations),
        staged_manifest=Path(staged_manifest),
        images=Path(images),
        expected_images=expected_staged_images,
        expected_boxes=expected_staged_boxes,
    )
    _require_cuda0_rtx5080()
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
    _write_canonical_json(
        output / "verifier_metadata.json",
        _verifier_metadata_payload(
            checkpoint=checkpoint,
            config=output / "verifier_config.json",
            runtime=_runtime_metadata(),
        ),
    )
    return checkpoint


def validate_staged_training_inputs(
    *,
    annotations: Path,
    staged_manifest: Path,
    images: Path,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> _FinalTrainingInputs:
    """Require the exact staged image set and source hashes before training."""
    inputs = _load_final_training_inputs(
        annotations=Path(annotations),
        staged_manifest=Path(staged_manifest),
        expected_images=expected_staged_images,
        expected_boxes=expected_staged_boxes,
    )
    image_root = Path(images)
    if not image_root.is_dir():
        raise ValueError("staged images directory is missing")
    rows = _read_json_array(Path(staged_manifest), "staged manifest")
    manifest_by_id: dict[int, tuple[str, str]] = {}
    expected_files: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("staged manifest rows must be objects")
        image_id = row.get("image_id")
        file_name = row.get("file_name")
        source_sha256 = row.get("source_sha256")
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id not in inputs.image_files
            or image_id in manifest_by_id
            or not _bundle_relative_path(file_name)
            or not isinstance(source_sha256, str)
            or not _SHA256.fullmatch(source_sha256)
        ):
            raise ValueError(
                "staged manifest requires unique image IDs, file names, and source SHA-256 hashes"
            )
        if file_name in expected_files:
            raise ValueError("staged manifest file names must be unique")
        if inputs.image_files[image_id] != file_name:
            raise ValueError("staged manifest and annotations have a file name mismatch")
        manifest_by_id[image_id] = (file_name, source_sha256)
        expected_files.add(file_name)
    if set(manifest_by_id) != set(inputs.image_files):
        raise ValueError("staged manifest and annotations image IDs must match")
    actual_files = {
        path.relative_to(image_root).as_posix()
        for path in image_root.rglob("*")
        if path.is_file()
    }
    missing = expected_files - actual_files
    if missing:
        raise ValueError(f"missing staged image: {min(missing)}")
    extra = actual_files - expected_files
    if extra:
        raise ValueError(f"extra staged image: {min(extra)}")
    # ``source_sha256`` deliberately commits to the pre-normalization source
    # bytes. Read each staged PNG now so the pre-output validation traverses
    # the actual training set; its distinct byte hashes are frozen separately.
    for image_id in sorted(manifest_by_id):
        file_name, _source_sha256 = manifest_by_id[image_id]
        _sha256_file(image_root / file_name)
    return inputs


def build_training_input_snapshot(
    *,
    annotations: Path,
    staged_manifest: Path,
    images: Path,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> dict[str, object]:
    """Freeze actual normalized training-image bytes without replacing provenance."""
    validate_staged_training_inputs(
        annotations=annotations,
        staged_manifest=staged_manifest,
        images=images,
        expected_staged_images=expected_staged_images,
        expected_staged_boxes=expected_staged_boxes,
    )
    image_root = Path(images)
    rows = _read_json_array(Path(staged_manifest), "staged manifest")
    snapshot_rows = []
    for row in sorted(rows, key=lambda item: item["image_id"]):
        assert isinstance(row, dict)
        file_name = row["file_name"]
        snapshot_rows.append(
            {
                "file_name": file_name,
                "image_id": row["image_id"],
                "source_sha256": row["source_sha256"],
                "staged_sha256": _sha256_file(image_root / file_name),
            }
        )
    return {"images": snapshot_rows, "schema_version": 1}


def validate_training_input_snapshot(
    *, snapshot: Mapping[str, object], images: Path
) -> None:
    """Reject missing, extra, renamed, or changed staged PNGs after snapshotting."""
    if set(snapshot) != {"images", "schema_version"} or snapshot.get(
        "schema_version"
    ) != 1:
        raise ValueError("training input snapshot schema is invalid")
    rows = snapshot.get("images")
    if not isinstance(rows, list) or not rows:
        raise ValueError("training input snapshot requires image rows")
    image_root = Path(images)
    if not image_root.is_dir():
        raise ValueError("staged images directory is missing")
    expected_files: set[str] = set()
    image_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "file_name",
            "image_id",
            "source_sha256",
            "staged_sha256",
        }:
            raise ValueError("training input snapshot row is invalid")
        image_id = row["image_id"]
        file_name = row["file_name"]
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id <= 0
            or image_id in image_ids
            or not _bundle_relative_path(file_name)
            or file_name in expected_files
            or not isinstance(row["source_sha256"], str)
            or not _SHA256.fullmatch(row["source_sha256"])
            or not isinstance(row["staged_sha256"], str)
            or not _SHA256.fullmatch(row["staged_sha256"])
        ):
            raise ValueError("training input snapshot identities or hashes are invalid")
        image_ids.add(image_id)
        expected_files.add(file_name)
    actual_files = {
        path.relative_to(image_root).as_posix()
        for path in image_root.rglob("*")
        if path.is_file()
    }
    missing, extra = expected_files - actual_files, actual_files - expected_files
    if missing:
        raise ValueError(f"training snapshot missing staged image: {min(missing)}")
    if extra:
        raise ValueError(f"training snapshot extra staged image: {min(extra)}")
    for row in rows:
        if _sha256_file(image_root / row["file_name"]) != row["staged_sha256"]:
            raise ValueError(
                f"training snapshot staged SHA-256 mismatch: {row['file_name']}"
            )


def write_training_input_snapshot(
    *,
    annotations: Path,
    staged_manifest: Path,
    images: Path,
    output: Path,
) -> Path:
    """Write one immutable snapshot of actual staged training-image bytes."""
    if Path(output).exists():
        raise ValueError("refusing to overwrite training input snapshot")
    snapshot = build_training_input_snapshot(
        annotations=annotations,
        staged_manifest=staged_manifest,
        images=images,
    )
    return _write_canonical_json(Path(output), snapshot)


def run_one_image_verifier_smoke(
    *,
    checkpoint: Path,
    detector_checkpoint: Path,
    detector_metadata: Path,
    detector_predictions: Path,
    annotations: Path,
    images: Path,
    output: Path,
    device: str,
) -> Path:
    """Run the final verifier over one image's GPU D-FINE smoke candidates."""
    if device != "cuda:0":
        raise ValueError("final smoke inference requires device cuda:0")
    if Path(output).exists():
        raise ValueError("refusing to overwrite smoke results")
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
    verifier_metadata_path = Path(checkpoint).with_name("verifier_metadata.json")
    verifier_metadata = _read_json_object(
        verifier_metadata_path, "verifier metadata"
    )
    checkpoint_sha256 = _sha256_file(Path(checkpoint))
    if verifier_metadata.get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError("verifier metadata checkpoint hash mismatch")
    verifier_metadata_sha256 = _sha256_file(verifier_metadata_path)
    detector_checkpoint_sha256 = _sha256_file(Path(detector_checkpoint))
    detector_metadata_path = Path(detector_metadata)
    detector_metadata_payload = _read_json_object(
        detector_metadata_path, "detector metadata"
    )
    if (
        detector_metadata_payload.get("checkpoint_sha256")
        != detector_checkpoint_sha256
    ):
        raise ValueError("detector metadata checkpoint hash mismatch")
    detector_metadata_sha256 = _sha256_file(detector_metadata_path)
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
                "detector_checkpoint_sha256": detector_checkpoint_sha256,
                "detector_metadata_sha256": detector_metadata_sha256,
                "verifier_checkpoint_sha256": checkpoint_sha256,
                "verifier_metadata_sha256": verifier_metadata_sha256,
            }
        )
    validate_smoke_results(
        payload,
        detector_checkpoint_sha256=detector_checkpoint_sha256,
        detector_metadata_sha256=detector_metadata_sha256,
        verifier_checkpoint_sha256=checkpoint_sha256,
        verifier_metadata_sha256=verifier_metadata_sha256,
    )
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


def write_detector_metadata(
    *, checkpoint: Path, config: Path, output: Path
) -> Path:
    """Write immutable detector provenance tied to its checkpoint and runtime."""
    if Path(output).exists():
        raise ValueError("refusing to overwrite detector metadata")
    _require_cuda0_rtx5080()
    checkpoint_path, config_path = Path(checkpoint), Path(config)
    if not checkpoint_path.is_file() or not config_path.is_file():
        raise ValueError("detector checkpoint and config are required")
    return _write_canonical_json(
        Path(output),
        {
            "checkpoint_sha256": _sha256_file(checkpoint_path),
            "config_sha256": _sha256_file(config_path),
            "input_size": 640,
            "name": "dfine_n_640",
            "runtime": _runtime_metadata(),
        },
    )


def write_final_bundle_manifest(
    bundle_root: Path,
    *,
    expected_staged_images: int = 299,
    expected_staged_boxes: int = 1410,
) -> Path:
    """Hash fixed final-bundle members and write their GPU/runtime metadata."""
    root = Path(bundle_root)
    manifest_target = root / "manifest.json"
    if manifest_target.exists():
        raise ValueError("refusing to overwrite final bundle manifest")
    _require_cuda0_rtx5080()
    artifact_paths = {
        "detector_checkpoint": root / "detector" / "checkpoint.pth",
        "detector_config": root / "detector" / "dfine_n_640.yml",
        "detector_metadata": root / "detector" / "detector_metadata.json",
        "verifier_checkpoint": root / "verifier" / "verifier.pt",
        "verifier_config": root / "verifier" / "verifier_config.json",
        "verifier_metadata": root / "verifier" / "verifier_metadata.json",
        "verifier_training_examples": root
        / "verifier"
        / "training_examples.json",
        "final_policy": root / "policy" / "final_policy.json",
        "staged_annotations": root / "evidence" / "annotations.json",
        "staged_manifest": root / "evidence" / "staged_manifest.json",
        "training_input_snapshot": root
        / "evidence"
        / "training_input_snapshot.json",
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
        "runtime": _runtime_metadata(),
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
    _validate_candidate_bundle(
        root,
        manifest,
        expected_staged_images=expected_staged_images,
        expected_staged_boxes=expected_staged_boxes,
    )
    manifest_path = _write_canonical_json(manifest_target, manifest)
    validate_final_bundle(
        root,
        expected_staged_images=expected_staged_images,
        expected_staged_boxes=expected_staged_boxes,
    )
    return manifest_path


def validate_smoke_results(
    results: Sequence[object],
    *,
    detector_checkpoint_sha256: str | None = None,
    detector_metadata_sha256: str | None = None,
    verifier_checkpoint_sha256: str | None = None,
    verifier_metadata_sha256: str | None = None,
) -> None:
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
    require_detector_linkage = (
        detector_checkpoint_sha256 is not None
        or detector_metadata_sha256 is not None
    )
    if require_detector_linkage and (
        not isinstance(detector_checkpoint_sha256, str)
        or not _SHA256.fullmatch(detector_checkpoint_sha256)
        or not isinstance(detector_metadata_sha256, str)
        or not _SHA256.fullmatch(detector_metadata_sha256)
    ):
        raise ValueError("smoke detector checkpoint linkage is invalid")
    require_verifier_linkage = (
        verifier_checkpoint_sha256 is not None
        or verifier_metadata_sha256 is not None
    )
    if require_verifier_linkage and (
        not isinstance(verifier_checkpoint_sha256, str)
        or not _SHA256.fullmatch(verifier_checkpoint_sha256)
        or not isinstance(verifier_metadata_sha256, str)
        or not _SHA256.fullmatch(verifier_metadata_sha256)
    ):
        raise ValueError("smoke verifier checkpoint linkage is invalid")
    if require_detector_linkage:
        expected_fields |= {
            "detector_checkpoint_sha256",
            "detector_metadata_sha256",
        }
    if require_verifier_linkage:
        expected_fields |= {
            "verifier_checkpoint_sha256",
            "verifier_metadata_sha256",
        }
    image_ids: set[int] = set()
    for row in results:
        if require_detector_linkage and (
            not isinstance(row, dict)
            or "detector_checkpoint_sha256" not in row
            or "detector_metadata_sha256" not in row
        ):
            raise ValueError("smoke detector checkpoint linkage is missing")
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
        if require_detector_linkage and (
            row["detector_checkpoint_sha256"] != detector_checkpoint_sha256
            or row["detector_metadata_sha256"] != detector_metadata_sha256
        ):
            raise ValueError("smoke detector checkpoint linkage is stale")
        if require_verifier_linkage and (
            row["verifier_checkpoint_sha256"] != verifier_checkpoint_sha256
            or row["verifier_metadata_sha256"] != verifier_metadata_sha256
        ):
            raise ValueError("smoke verifier checkpoint linkage is stale")
    if len(image_ids) != 1:
        raise ValueError("smoke results must cover exactly one source image")


def _validate_candidate_bundle(
    root: Path,
    manifest: Mapping[str, object],
    *,
    expected_staged_images: int,
    expected_staged_boxes: int,
) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACT_LABELS):
        raise ValueError("final bundle candidate has incomplete immutable artifacts")
    resolved_artifacts = {
        name: _validate_artifact(root, artifacts[name], label)
        for name, label in _ARTIFACT_LABELS.items()
    }
    committed_files = {path.resolve() for path in resolved_artifacts.values()}
    observed_files = {
        path.resolve() for path in root.rglob("*") if path.is_file()
    }
    if observed_files != committed_files:
        raise ValueError("final bundle contains an unhashed bundle member")
    _validate_detector_metadata(manifest.get("detector"))
    _validate_verifier_metadata(manifest.get("verifier"))
    _validate_runtime_metadata(manifest.get("runtime"))
    _validate_training_data(
        manifest.get("training_data"),
        annotations_path=resolved_artifacts["staged_annotations"],
        staged_manifest_path=resolved_artifacts["staged_manifest"],
        expected_images=expected_staged_images,
        expected_boxes=expected_staged_boxes,
    )
    _validate_bundle_training_snapshot(
        resolved_artifacts["training_input_snapshot"],
        staged_manifest_path=resolved_artifacts["staged_manifest"],
        expected_images=expected_staged_images,
    )
    _validate_final_policy(resolved_artifacts["final_policy"])
    _validate_detector_bundle_semantics(manifest, resolved_artifacts)
    _validate_verifier_bundle_semantics(manifest, resolved_artifacts)
    validate_smoke_results(
        _read_json_array(resolved_artifacts["smoke_results"], "smoke results"),
        detector_checkpoint_sha256=artifacts["detector_checkpoint"]["sha256"],
        detector_metadata_sha256=artifacts["detector_metadata"]["sha256"],
        verifier_checkpoint_sha256=artifacts["verifier_checkpoint"]["sha256"],
        verifier_metadata_sha256=artifacts["verifier_metadata"]["sha256"],
    )


def _runtime_metadata() -> dict[str, str]:
    return {
        "cuda_version": str(torch.version.cuda or ""),
        "device": "cuda:0",
        "gpu_name": torch.cuda.get_device_name(0),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
    }


def _verifier_metadata_payload(
    *, checkpoint: Path, config: Path, runtime: Mapping[str, object]
) -> dict[str, object]:
    return {
        "checkpoint_sha256": _sha256_file(Path(checkpoint)),
        "class_order": list(CLASS_ORDER),
        "config_sha256": _sha256_file(Path(config)),
        "model_name": MODEL_NAME,
        "preprocessing": PREPROCESSING,
        "runtime": dict(runtime),
    }


def _validate_detector_bundle_semantics(
    manifest: Mapping[str, object], artifacts: Mapping[str, Path]
) -> None:
    metadata = _read_json_object(artifacts["detector_metadata"], "detector metadata")
    expected = {
        "checkpoint_sha256": _sha256_file(artifacts["detector_checkpoint"]),
        "config_sha256": _sha256_file(artifacts["detector_config"]),
        "input_size": 640,
        "name": "dfine_n_640",
        "runtime": manifest["runtime"],
    }
    if metadata != expected:
        raise ValueError("detector metadata does not match bundle artifacts or runtime")


def _validate_verifier_bundle_semantics(
    manifest: Mapping[str, object], artifacts: Mapping[str, Path]
) -> None:
    config = _read_json_object(artifacts["verifier_config"], "verifier config")
    expected_config = {
        "class_order": list(CLASS_ORDER),
        "model_name": MODEL_NAME,
        "preprocessing": PREPROCESSING,
    }
    if any(config.get(name) != value for name, value in expected_config.items()):
        raise ValueError("verifier config metadata is invalid")
    metadata = _read_json_object(artifacts["verifier_metadata"], "verifier metadata")
    expected_metadata = {
        "checkpoint_sha256": _sha256_file(artifacts["verifier_checkpoint"]),
        "class_order": list(CLASS_ORDER),
        "config_sha256": _sha256_file(artifacts["verifier_config"]),
        "model_name": MODEL_NAME,
        "preprocessing": PREPROCESSING,
        "runtime": manifest["runtime"],
    }
    if metadata != expected_metadata:
        raise ValueError("verifier metadata does not match config, checkpoint, or runtime")


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


def _bundle_relative_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not Path(value).is_absolute()
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


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


def _validate_bundle_training_snapshot(
    path: Path, *, staged_manifest_path: Path, expected_images: int
) -> None:
    snapshot = _read_json_object(path, "training input snapshot")
    rows = snapshot.get("images")
    if snapshot.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("training input snapshot schema is invalid")
    manifest_rows = _read_json_array(staged_manifest_path, "staged manifest")
    if len(rows) != expected_images or len(manifest_rows) != expected_images:
        raise ValueError("training input snapshot must cover every staged image")
    manifest_by_id: dict[int, tuple[object, object]] = {}
    for row in manifest_rows:
        if not isinstance(row, dict):
            raise ValueError("staged manifest rows must be objects")
        image_id = row.get("image_id")
        if isinstance(image_id, bool) or not isinstance(image_id, int):
            raise ValueError("staged manifest image ID is invalid")
        manifest_by_id[image_id] = (row.get("file_name"), row.get("source_sha256"))
    snapshot_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "file_name",
            "image_id",
            "source_sha256",
            "staged_sha256",
        }:
            raise ValueError("training input snapshot row is invalid")
        image_id = row["image_id"]
        if (
            isinstance(image_id, bool)
            or not isinstance(image_id, int)
            or image_id in snapshot_ids
            or manifest_by_id.get(image_id)
            != (row["file_name"], row["source_sha256"])
            or not isinstance(row["staged_sha256"], str)
            or not _SHA256.fullmatch(row["staged_sha256"])
        ):
            raise ValueError("training input snapshot does not match staged provenance")
        snapshot_ids.add(image_id)
    if snapshot_ids != set(manifest_by_id):
        raise ValueError("training input snapshot must cover every staged image")


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

    staged = subparsers.add_parser("validate-staged-inputs")
    staged.add_argument("--annotations", type=Path, required=True)
    staged.add_argument("--staged-manifest", type=Path, required=True)
    staged.add_argument("--images", type=Path, required=True)

    snapshot = subparsers.add_parser("write-training-snapshot")
    snapshot.add_argument("--annotations", type=Path, required=True)
    snapshot.add_argument("--staged-manifest", type=Path, required=True)
    snapshot.add_argument("--images", type=Path, required=True)
    snapshot.add_argument("--output", type=Path, required=True)

    snapshot_validate = subparsers.add_parser("validate-training-snapshot")
    snapshot_validate.add_argument("--snapshot", type=Path, required=True)
    snapshot_validate.add_argument("--images", type=Path, required=True)

    smoke = subparsers.add_parser("smoke-verifier")
    smoke.add_argument("--checkpoint", type=Path, required=True)
    smoke.add_argument("--detector-checkpoint", type=Path, required=True)
    smoke.add_argument("--detector-metadata", type=Path, required=True)
    smoke.add_argument("--detector-predictions", type=Path, required=True)
    smoke.add_argument("--annotations", type=Path, required=True)
    smoke.add_argument("--images", type=Path, required=True)
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--device", default="cuda:0")

    policy = subparsers.add_parser("write-policy")
    policy.add_argument("--report", type=Path, required=True)
    policy.add_argument("--output", type=Path, required=True)

    detector_metadata = subparsers.add_parser("write-detector-metadata")
    detector_metadata.add_argument("--checkpoint", type=Path, required=True)
    detector_metadata.add_argument("--config", type=Path, required=True)
    detector_metadata.add_argument("--output", type=Path, required=True)

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
    elif args.command == "validate-staged-inputs":
        validate_staged_training_inputs(
            annotations=args.annotations,
            staged_manifest=args.staged_manifest,
            images=args.images,
        )
    elif args.command == "write-training-snapshot":
        write_training_input_snapshot(
            annotations=args.annotations,
            staged_manifest=args.staged_manifest,
            images=args.images,
            output=args.output,
        )
    elif args.command == "validate-training-snapshot":
        validate_training_input_snapshot(
            snapshot=_read_json_object(args.snapshot, "training input snapshot"),
            images=args.images,
        )
    elif args.command == "smoke-verifier":
        run_one_image_verifier_smoke(
            checkpoint=args.checkpoint,
            detector_checkpoint=args.detector_checkpoint,
            detector_metadata=args.detector_metadata,
            detector_predictions=args.detector_predictions,
            annotations=args.annotations,
            images=args.images,
            output=args.output,
            device=args.device,
        )
    elif args.command == "write-policy":
        write_final_policy_from_report(report=args.report, output=args.output)
    elif args.command == "write-detector-metadata":
        write_detector_metadata(
            checkpoint=args.checkpoint,
            config=args.config,
            output=args.output,
        )
    elif args.command == "write-manifest":
        write_final_bundle_manifest(args.bundle_root)
    else:
        validate_final_bundle(args.bundle_root)


if __name__ == "__main__":
    _main()
