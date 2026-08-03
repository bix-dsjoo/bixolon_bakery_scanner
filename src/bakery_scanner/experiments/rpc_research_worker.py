"""External-only, deterministic oracle feature extraction for RPC research."""

from __future__ import annotations

import hashlib
import math
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image, ImageOps

from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.experiments.rpc_manifest import RpcImage, RpcIndex, write_new_json


_DINO_SHA256 = "08c60483bc63c04f533611e34bf70b120eedb7240f469bc16e9e20bf344b941d"
_REPVIT_SHA256 = "217aca2b9a9149ebbab4faac93719036a227fd2fbde623cd51f780f49b7610a4"
_FEATURE_DIMENSION = 384
_DINO_PATCH_COUNT = 196
_CANONICAL_FRAME = "exif_visual_rgb_v1"
_RESEARCH_RUNS_ROOT = Path(r"C:\workspace\rpc_fewshot_runs")


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

    @property
    def identity(self) -> str:
        return f"{self.source_identity}:{self.annotation_id}"


def extract_oracle_features(
    index: RpcIndex,
    artifacts: ResearchArtifacts,
    output: Path,
    *,
    allowed_output_root: Path | None = None,
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
    root = Path(allowed_output_root or _RESEARCH_RUNS_ROOT).resolve()
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
