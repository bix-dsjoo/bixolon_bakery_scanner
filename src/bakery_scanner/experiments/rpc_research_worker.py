"""External-only, deterministic oracle feature extraction for RPC research."""

from __future__ import annotations

import hashlib
import math
import os
import platform
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from numbers import Real
from typing import Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image, ImageOps

from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.experiments.rpc_manifest import (
    RpcImage,
    RpcIndex,
    canonical_json_bytes,
    write_new_json,
)


_DINO_SHA256 = "08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d"
_REPVIT_SHA256 = "217aca2b9a9149ebbab4faac93719036a227fd2fbde623cd51f780f49b7610a4"
_FEATURE_DIMENSION = 384
_DINO_PATCH_COUNT = 196
_CANONICAL_FRAME = "exif_visual_rgb_v1"
_RESEARCH_RUNS_ROOT = Path(r"C:\workspace\rpc_fewshot_runs")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ResearchArtifacts:
    """The two independently hash-verified research backbone artifacts."""

    repvit_path: Path
    dino_path: Path
    repvit_sha256: str
    dino_sha256: str

    @classmethod
    def from_paths(cls, repvit_path: Path, dino_path: Path) -> "ResearchArtifacts":
        repvit = Path(repvit_path)
        dino = Path(dino_path)
        # DINO first makes a missing or substituted DINO checkpoint fail closed
        # before a caller can use any partially accepted artifact bundle.
        dino_digest = _sha256_file(dino)
        if dino_digest != _DINO_SHA256:
            raise ValueError("DINOv3 SHA-256 mismatch")
        repvit_digest = _sha256_file(repvit)
        if repvit_digest != _REPVIT_SHA256:
            raise ValueError("RepViT SHA-256 mismatch")
        return cls(repvit.resolve(), dino.resolve(), repvit_digest, dino_digest)


@dataclass(frozen=True, slots=True)
class OracleFeatureRow:
    """One COCO oracle annotation whose features are source-bound."""

    source_identity: str
    annotation_id: int
    category_id: int
    bbox_xywh: tuple[float, float, float, float]
    difficulty: str
    source_byte_size: int | None = None
    source_sha256: str | None = None
    dino_global: tuple[float, ...] | None = None
    capture_stratum: str | None = None
    feature_array_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_identity, str) or not self.source_identity:
            raise ValueError("source identity must be non-empty")
        if type(self.annotation_id) is not int or self.annotation_id <= 0:
            raise ValueError("annotation ID must be positive")
        if type(self.category_id) is not int or self.category_id <= 0:
            raise ValueError("category ID must be positive")
        if not isinstance(self.difficulty, str) or len(self.difficulty) != 1:
            raise ValueError("difficulty must be one character")
        values = tuple(float(value) for value in self.bbox_xywh)
        if len(values) != 4 or not all(math.isfinite(value) for value in values):
            raise ValueError("oracle bbox must contain four finite coordinates")
        if values[2] <= 0.0 or values[3] <= 0.0:
            raise ValueError("oracle bbox must have positive width and height")
        object.__setattr__(self, "bbox_xywh", values)
        if self.source_byte_size is not None and (
            type(self.source_byte_size) is not int or self.source_byte_size <= 0
        ):
            raise ValueError("source byte size must be positive")
        if self.source_sha256 is not None and (
            not isinstance(self.source_sha256, str) or _SHA256.fullmatch(self.source_sha256) is None
        ):
            raise ValueError("source SHA-256 must be lowercase SHA-256")
        if self.capture_stratum is not None and (
            not isinstance(self.capture_stratum, str) or not self.capture_stratum
        ):
            raise ValueError("capture stratum must be non-empty")
        if self.feature_array_sha256 is not None and (
            not isinstance(self.feature_array_sha256, str)
            or _SHA256.fullmatch(self.feature_array_sha256) is None
        ):
            raise ValueError("feature-array SHA-256 must be lowercase SHA-256")
        if self.dino_global is not None:
            if isinstance(self.dino_global, (str, bytes)):
                raise ValueError("DINO global feature must be a finite numeric vector")
            values = tuple(self.dino_global)
            if (
                not values
                or any(isinstance(value, bool) or not isinstance(value, Real) for value in values)
                or not all(math.isfinite(float(value)) for value in values)
            ):
                raise ValueError("DINO global feature must be a finite numeric vector")
            object.__setattr__(self, "dino_global", tuple(float(value) for value in values))

    @property
    def identity(self) -> str:
        return f"{self.source_identity}:{self.annotation_id}"


@dataclass(frozen=True, slots=True)
class SupportExample:
    """One selected, source- and feature-array-bound oracle support example."""

    source_identity: str
    annotation_id: int
    category_id: int
    source_byte_size: int
    source_sha256: str
    dino_global: tuple[float, ...]
    capture_stratum: str
    feature_array_sha256: str


@dataclass(frozen=True, slots=True)
class SupportBank:
    """A class-complete immutable support order with only prefix access."""

    selector: str
    seed: int
    maximum_shots: int
    class_orders: tuple[tuple[SupportExample, ...], ...]
    feature_array_sha256: str
    sha256: str

    def __post_init__(self) -> None:
        if self.selector not in {"rnd", "div"}:
            raise ValueError("unsupported support selector")
        if type(self.seed) is not int:
            raise ValueError("support seed must be an integer")
        if type(self.maximum_shots) is not int or self.maximum_shots <= 0:
            raise ValueError("maximum shots must be positive")
        if not self.class_orders:
            raise ValueError("support bank requires complete class orders")
        categories: list[int] = []
        for order in self.class_orders:
            if len(order) < self.maximum_shots:
                raise ValueError("insufficient support candidates")
            category_ids = {example.category_id for example in order}
            if len(category_ids) != 1:
                raise ValueError("support order must contain one class")
            categories.append(next(iter(category_ids)))
        if categories != sorted(categories) or len(categories) != len(set(categories)):
            raise ValueError("support bank classes must be unique and sorted")
        identities = [example.source_identity for order in self.class_orders for example in order]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate source identity")
        if not isinstance(self.feature_array_sha256, str) or _SHA256.fullmatch(self.feature_array_sha256) is None:
            raise ValueError("feature-array SHA-256 must be lowercase SHA-256")
        if self.sha256 != _support_bank_digest(
            self.selector, self.seed, self.maximum_shots, self.class_orders, self.feature_array_sha256
        ):
            raise ValueError("support bank SHA-256 mismatch")

    @property
    def ordered_support_identities(self) -> tuple[tuple[int, tuple[str, ...]], ...]:
        """Record every materialized candidate identity, not a resampled draw."""
        return tuple(
            (order[0].category_id, tuple(example.source_identity for example in order))
            for order in self.class_orders
        )

    @property
    def feature_array_digest(self) -> str:
        """Compatibility-neutral name for the bound DINO-global array SHA-256."""
        return self.feature_array_sha256

    def prefix(self, shot_count: int) -> tuple[SupportExample, ...]:
        """Return the class-complete prefix without extending or resampling the bank."""
        if type(shot_count) is not int or shot_count <= 0:
            raise ValueError("shot count must be positive")
        if shot_count > self.maximum_shots:
            raise ValueError("non-prefix support extension is not allowed")
        return tuple(example for order in self.class_orders for example in order[:shot_count])


def materialize_support_bank(
    rows: Sequence[OracleFeatureRow], *, selector: str, seed: int, maximum_shots: int
) -> SupportBank:
    """Create source/hash-bound, nested RND or DINO-global DIV support prefixes."""
    if selector not in {"rnd", "div"}:
        raise ValueError("unsupported support selector")
    if type(seed) is not int:
        raise ValueError("support seed must be an integer")
    if type(maximum_shots) is not int or maximum_shots <= 0:
        raise ValueError("maximum shots must be positive")
    if not isinstance(rows, Sequence) or not rows:
        raise ValueError("support rows must be a non-empty sequence")
    if not all(isinstance(row, OracleFeatureRow) for row in rows):
        raise ValueError("support rows must be OracleFeatureRow instances")
    source_identities = [row.source_identity for row in rows]
    if len(source_identities) != len(set(source_identities)):
        raise ValueError("duplicate source identity")
    examples = tuple(_support_example(row) for row in rows)
    feature_digests = {example.feature_array_sha256 for example in examples}
    if len(feature_digests) != 1:
        raise ValueError("support rows must bind one feature-array SHA-256")
    dimensions = {len(example.dino_global) for example in examples}
    if len(dimensions) != 1:
        raise ValueError("DINO global feature dimensions must agree")
    by_category: dict[int, list[SupportExample]] = {}
    for example in examples:
        by_category.setdefault(example.category_id, []).append(example)
    orders: list[tuple[SupportExample, ...]] = []
    for category_id, candidates in sorted(by_category.items()):
        if len(candidates) < maximum_shots:
            raise ValueError(f"insufficient support candidates for category {category_id}")
        if selector == "rnd":
            order = tuple(sorted(candidates, key=lambda item: (_seeded_digest(seed, item.source_identity), item.source_identity)))
        else:
            order = _diverse_support_order(tuple(candidates), seed)
        orders.append(order)
    feature_digest = next(iter(feature_digests))
    frozen_orders = tuple(orders)
    return SupportBank(
        selector,
        seed,
        maximum_shots,
        frozen_orders,
        feature_digest,
        _support_bank_digest(selector, seed, maximum_shots, frozen_orders, feature_digest),
    )


def _support_example(row: OracleFeatureRow) -> SupportExample:
    if (
        row.source_byte_size is None
        or row.source_sha256 is None
        or row.dino_global is None
        or row.capture_stratum is None
        or row.feature_array_sha256 is None
    ):
        raise ValueError("support row lacks source/hash-bound DINO feature provenance")
    return SupportExample(
        row.source_identity,
        row.annotation_id,
        row.category_id,
        row.source_byte_size,
        row.source_sha256,
        row.dino_global,
        row.capture_stratum,
        row.feature_array_sha256,
    )


def _diverse_support_order(
    candidates: tuple[SupportExample, ...], seed: int
) -> tuple[SupportExample, ...]:
    normalized = {candidate.source_identity: _normalized_vector(candidate.dino_global) for candidate in candidates}
    dimensions = len(candidates[0].dino_global)
    centroid = tuple(
        sum(normalized[candidate.source_identity][index] for candidate in candidates) / len(candidates)
        for index in range(dimensions)
    )
    first = min(
        candidates,
        key=lambda item: (_vector_distance(normalized[item.source_identity], centroid), item.source_sha256, item.source_identity),
    )
    selected = [first]
    remaining = {candidate.source_identity: candidate for candidate in candidates if candidate != first}
    stratum_counts = {first.capture_stratum: 1}
    all_strata = {candidate.capture_stratum for candidate in candidates}
    while remaining:
        pool = tuple(remaining.values())
        unrepresented = all_strata - set(stratum_counts)
        if unrepresented:
            next_stratum = min(unrepresented, key=lambda item: (_seeded_digest(seed, item), item))
            pool = tuple(candidate for candidate in pool if candidate.capture_stratum == next_stratum)
        else:
            fewest = min(stratum_counts.get(candidate.capture_stratum, 0) for candidate in pool)
            pool = tuple(candidate for candidate in pool if stratum_counts.get(candidate.capture_stratum, 0) == fewest)
        next_candidate = min(
            pool,
            key=lambda item: (
                -min(
                    _vector_distance(normalized[item.source_identity], normalized[chosen.source_identity])
                    for chosen in selected
                ),
                item.source_sha256,
                item.source_identity,
            ),
        )
        selected.append(next_candidate)
        del remaining[next_candidate.source_identity]
        stratum_counts[next_candidate.capture_stratum] = stratum_counts.get(next_candidate.capture_stratum, 0) + 1
    return tuple(selected)


def _normalized_vector(values: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("DINO global feature must have non-zero length")
    return tuple(value / norm for value in values)


def _vector_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(sum((first - second) ** 2 for first, second in zip(left, right, strict=True)))


def _seeded_digest(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def _support_bank_digest(
    selector: str,
    seed: int,
    maximum_shots: int,
    class_orders: tuple[tuple[SupportExample, ...], ...],
    feature_array_sha256: str,
) -> str:
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "selector": selector,
                "seed": seed,
                "maximum_shots": maximum_shots,
                "feature_array_sha256": feature_array_sha256,
                "class_orders": [
                    [
                        {
                            "source_identity": example.source_identity,
                            "annotation_id": example.annotation_id,
                            "category_id": example.category_id,
                            "source_byte_size": example.source_byte_size,
                            "source_sha256": example.source_sha256,
                            "capture_stratum": example.capture_stratum,
                        }
                        for example in order
                    ]
                    for order in class_orders
                ],
            }
        )
    ).hexdigest()


def support_bank_manifest(bank: SupportBank) -> dict[str, object]:
    """Return the compact, canonical receipt for an immutable support bank."""
    if not isinstance(bank, SupportBank):
        raise ValueError("support bank must be a SupportBank")
    return {
        "schema_version": 1,
        "kind": "rpc-research-support-bank",
        "selector": bank.selector,
        "seed": bank.seed,
        "maximum_shots": bank.maximum_shots,
        "feature_array_sha256": bank.feature_array_sha256,
        "classes": [
            {
                "category_id": order[0].category_id,
                "ordered_support_identities": [example.source_identity for example in order],
                "examples": [
                    {
                        "identity": f"{example.source_identity}:{example.annotation_id}",
                        "source_identity": example.source_identity,
                        "annotation_id": example.annotation_id,
                        "source_byte_size": example.source_byte_size,
                        "source_sha256": example.source_sha256,
                        "capture_stratum": example.capture_stratum,
                    }
                    for example in order
                ],
            }
            for order in bank.class_orders
        ],
        "sha256": bank.sha256,
    }


def write_support_bank(path: Path, bank: SupportBank) -> Path:
    """Write a no-replace compact support receipt outside the repository."""
    destination = Path(path).resolve()
    root = _RESEARCH_RUNS_ROOT.resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"output must be under {root}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_new_json(destination, support_bank_manifest(bank))
    return destination


def extract_oracle_features(
    index: RpcIndex,
    artifacts: ResearchArtifacts,
    output: Path,
) -> Path:
    """Materialize no-replace float16 oracle features and their canonical manifest.

    The output is a fresh directory containing one `manifest.json` and exactly
    three `.npy` arrays.  It intentionally does not create crops or any Git
    payload: generated data remains an external research artifact.
    """
    if not isinstance(index, RpcIndex):
        raise ValueError("index must be an RpcIndex")
    if not isinstance(artifacts, ResearchArtifacts):
        raise ValueError("artifacts must be ResearchArtifacts")
    root = _RESEARCH_RUNS_ROOT.resolve()
    destination = Path(output).resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"output must be under {root}")
    artifacts = _revalidate_artifacts(artifacts)
    if destination.exists():
        raise FileExistsError(f"output already exists: {destination}")
    rows = _oracle_rows(index)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        repvit_array = np.lib.format.open_memmap(
            temporary / "repvit_global.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _FEATURE_DIMENSION),
        )
        dino_array = np.lib.format.open_memmap(
            temporary / "dinov3_global.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _FEATURE_DIMENSION),
        )
        patch_array = np.lib.format.open_memmap(
            temporary / "dinov3_patches.float16.npy", mode="w+", dtype=np.float16,
            shape=(len(rows), _DINO_PATCH_COUNT, _FEATURE_DIMENSION),
        )
        repvit_model, dino_model = _load_feature_models(artifacts)
        transform = build_transform(224)
        device = _model_device(repvit_model)
        if _model_device(dino_model) != device:
            raise ValueError("research encoders must share one device")
        image_by_identity = {image.source_identity: image for image in index.images}
        for row_index, row in enumerate(rows):
            image = image_by_identity[row.source_identity]
            crop = _canonical_oracle_crop(image, row.bbox_xywh)
            batch = transform(crop).unsqueeze(0).to(device)
            repvit, dino, patches = _feature_vectors(repvit_model, dino_model, batch)
            repvit_array[row_index] = repvit.cpu().numpy().astype(np.float16, copy=False)
            dino_array[row_index] = dino.cpu().numpy().astype(np.float16, copy=False)
            patch_array[row_index] = patches.cpu().numpy().astype(np.float16, copy=False)
        del repvit_array, dino_array, patch_array
        manifest = _feature_manifest(rows, image_by_identity, artifacts, temporary)
        manifest_path = temporary / "manifest.json"
        write_new_json(manifest_path, manifest)
        os.rename(temporary, destination)
        return destination / "manifest.json"
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _oracle_rows(index: RpcIndex) -> tuple[OracleFeatureRow, ...]:
    image_by_coordinate = {(item.split, item.image_id): item for item in index.images}
    if len(image_by_coordinate) != len(index.images):
        raise ValueError("RPC index contains duplicate source images")
    rows: list[OracleFeatureRow] = []
    for item in index.objects:
        image = image_by_coordinate.get((item.split, item.image_id))
        if image is None:
            raise ValueError("RPC object is not bound to an indexed source image")
        difficulty = image.level[:1].upper() if image.level else "U"
        rows.append(
            OracleFeatureRow(
                image.source_identity, item.annotation_id, item.category_id,
                item.bbox_xywh, difficulty,
            )
        )
    identities = [row.identity for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("RPC index contains duplicate oracle annotation identities")
    return tuple(sorted(rows, key=lambda row: (row.source_identity, row.annotation_id)))


def _canonical_oracle_crop(
    image: RpcImage, bbox_xywh: tuple[float, float, float, float]
) -> Image.Image:
    _verify_indexed_source(image)
    try:
        with Image.open(image.source_path) as source:
            orientation = source.getexif().get(274, 1)
            if type(orientation) is not int or orientation not in range(1, 9):
                raise ValueError("RPC source image has an invalid EXIF orientation")
            _validate_bbox_bounds(bbox_xywh, source.width, source.height)
            canonical_bbox = _transpose_bbox_for_exif(
                bbox_xywh, orientation, source.width, source.height
            )
            canonical = ImageOps.exif_transpose(source).convert("RGB")
    except OSError as exc:
        raise ValueError(f"cannot decode RPC source image: {image.source_identity}") from exc
    x, y, width, height = canonical_bbox
    left, top = math.floor(x), math.floor(y)
    right, bottom = math.ceil(x + width), math.ceil(y + height)
    if left < 0 or top < 0 or right > canonical.width or bottom > canonical.height or right <= left or bottom <= top:
        raise ValueError("oracle bbox lies outside canonical RGB image")
    return canonical.crop((left, top, right, bottom))


def _transpose_bbox_for_exif(
    bbox_xywh: tuple[float, float, float, float], orientation: int, width: int, height: int
) -> tuple[float, float, float, float]:
    """Map raw-file COCO coordinates into Pillow's EXIF-transposed frame."""
    x, y, box_width, box_height = bbox_xywh
    if orientation == 1:
        return bbox_xywh
    if orientation == 2:
        return (width - x - box_width, y, box_width, box_height)
    if orientation == 3:
        return (width - x - box_width, height - y - box_height, box_width, box_height)
    if orientation == 4:
        return (x, height - y - box_height, box_width, box_height)
    if orientation == 5:
        return (y, x, box_height, box_width)
    if orientation == 6:
        return (height - y - box_height, x, box_height, box_width)
    if orientation == 7:
        return (height - y - box_height, width - x - box_width, box_height, box_width)
    return (y, width - x - box_width, box_height, box_width)


def _validate_bbox_bounds(
    bbox_xywh: tuple[float, float, float, float], width: int, height: int
) -> None:
    x, y, box_width, box_height = bbox_xywh
    if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
        raise ValueError("oracle bbox lies outside raw EXIF image")


def _feature_vectors(
    repvit_model: torch.nn.Module, dino_model: torch.nn.Module, batch: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    with torch.inference_mode():
        repvit_raw = repvit_model.forward_features(batch)
        if not isinstance(repvit_raw, torch.Tensor) or tuple(repvit_raw.shape[:2]) != (1, _FEATURE_DIMENSION):
            raise ValueError("RepViT features must have shape (1, 384, H, W)")
        if repvit_raw.ndim != 4 or not torch.isfinite(repvit_raw).all().item():
            raise ValueError("RepViT features must be finite spatial tensors")
        repvit = _l2_normalize(repvit_raw.mean(dim=(2, 3)), "RepViT global feature")[0]
        dino_raw = dino_model.forward_features(batch)
        if not isinstance(dino_raw, Mapping):
            raise ValueError("DINOv3 forward_features must return a mapping")
        dino_global = dino_raw.get("x_norm_clstoken")
        patches = dino_raw.get("x_norm_patchtokens")
        if not isinstance(dino_global, torch.Tensor) or tuple(dino_global.shape) != (1, _FEATURE_DIMENSION):
            raise ValueError("DINOv3 global features must have shape (1, 384)")
        if not isinstance(patches, torch.Tensor) or tuple(patches.shape) != (1, _DINO_PATCH_COUNT, _FEATURE_DIMENSION):
            raise ValueError("DINOv3 patch features must have shape (1, 196, 384)")
        if not torch.isfinite(dino_global).all().item() or not torch.isfinite(patches).all().item():
            raise ValueError("DINOv3 features must be finite")
        return (
            repvit,
            _l2_normalize(dino_global, "DINOv3 global feature")[0],
            _l2_normalize(patches, "DINOv3 patch feature")[0],
        )


def _l2_normalize(value: torch.Tensor, label: str) -> torch.Tensor:
    norms = value.norm(dim=-1, keepdim=True)
    if (norms == 0).any().item():
        raise ValueError(f"{label} must have non-zero length")
    return functional.normalize(value, dim=-1)


def _load_feature_models(artifacts: ResearchArtifacts) -> tuple[torch.nn.Module, torch.nn.Module]:
    """Load exact research encoders; imported lazily so contracts stay hermetic."""
    import timm
    from dinov3.models.vision_transformer import vit_small
    from safetensors.torch import load_file

    # CPU/float32 is the explicitly documented reproducibility contract for
    # this research cache.  Do not silently alter its bytes by choosing CUDA.
    device = torch.device("cpu")
    repvit = timm.create_model("repvit_m1", pretrained=False)
    repvit.load_state_dict(load_file(str(artifacts.repvit_path), device="cpu"), strict=True)
    dino = vit_small(patch_size=16, n_storage_tokens=4, mask_k_bias=True, layerscale_init=1e-5)
    weights = torch.load(artifacts.dino_path, map_location="cpu", weights_only=True)
    if not isinstance(weights, Mapping):
        raise ValueError("DINOv3 weights must be a state dictionary")
    dino.load_state_dict(weights, strict=True)
    return repvit.to(device).eval(), dino.to(device).eval()


def _revalidate_artifacts(artifacts: ResearchArtifacts) -> ResearchArtifacts:
    """Reject forged or stale dataclass values immediately before model loading."""
    verified = ResearchArtifacts.from_paths(artifacts.repvit_path, artifacts.dino_path)
    if (
        artifacts.repvit_path.resolve() != verified.repvit_path
        or artifacts.dino_path.resolve() != verified.dino_path
        or artifacts.repvit_sha256 != verified.repvit_sha256
        or artifacts.dino_sha256 != verified.dino_sha256
    ):
        raise ValueError("research artifact provenance mismatch")
    return verified


def _model_device(model: torch.nn.Module) -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def _feature_manifest(
    rows: tuple[OracleFeatureRow, ...],
    image_by_identity: dict[str, RpcImage],
    artifacts: ResearchArtifacts,
    directory: Path,
) -> dict[str, object]:
    arrays = {
        "repvit_global": _array_manifest(directory / "repvit_global.float16.npy", [len(rows), _FEATURE_DIMENSION]),
        "dinov3_global": _array_manifest(directory / "dinov3_global.float16.npy", [len(rows), _FEATURE_DIMENSION]),
        "dinov3_patches": _array_manifest(directory / "dinov3_patches.float16.npy", [len(rows), _DINO_PATCH_COUNT, _FEATURE_DIMENSION]),
    }
    return {
        "schema_version": 1,
        "kind": "rpc-research-oracle-features",
        "canonical_frame": _CANONICAL_FRAME,
        "feature_dtype": "float16",
        "execution": {
            "device": "cpu",
            "determinism": "cpu-float32-inference-mode-model-eval-v1",
        },
        "preprocessing": {
            "canonical_frame": _CANONICAL_FRAME,
            "bbox_coordinate_frame": "raw-exif-source-v1",
            "exif_bbox_transform": "raw-to-visual-v1",
            "image_mode": "RGB",
            "input_size": [224, 224],
            "resize_interpolation": "bilinear",
            "antialias": True,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "code_sha256": _sha256_file(Path(__file__)),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pillow": Image.__version__,
            "torch": torch.__version__,
        },
        "artifacts": {
            "repvit": {"path": str(artifacts.repvit_path), "sha256": artifacts.repvit_sha256},
            "dinov3": {"path": str(artifacts.dino_path), "sha256": artifacts.dino_sha256},
        },
        "arrays": arrays,
        "images": [
            {
                "source_identity": image.source_identity,
                "source_byte_size": image.byte_size,
                "source_sha256": image.sha256,
            }
            for image in sorted(image_by_identity.values(), key=lambda item: item.source_identity)
        ],
        "rows": [
            {
                "identity": row.identity,
                "source_identity": row.source_identity,
                "annotation_id": row.annotation_id,
                "category_id": row.category_id,
                "bbox_xywh": list(row.bbox_xywh),
                "difficulty": row.difficulty,
            }
            for row in rows
        ],
    }


def _array_manifest(path: Path, shape: list[int]) -> dict[str, object]:
    return {
        "file": path.name,
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "shape": shape,
    }


def _verify_indexed_source(image: RpcImage) -> None:
    if not image.source_path.is_file() or image.source_path.stat().st_size != image.byte_size:
        raise ValueError(f"RPC source image changed: {image.source_identity}")
    if _sha256_file(image.source_path) != image.sha256:
        raise ValueError(f"RPC source image changed: {image.source_identity}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    except OSError:
        return ""
    return digest.hexdigest()
