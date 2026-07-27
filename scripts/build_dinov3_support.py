"""Build DINOv3 global prototypes and local patch bank from the 15+5 sources."""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn.functional as functional
from dinov3.models.vision_transformer import vit_small

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.dinov3 import _ARCHITECTURE, _STORAGE_TOKEN_SHAPE, _describe_transform
from bakery_scanner.classification.evidence import atomic_write_bytes
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.data.preprocess import load_canonical_image
from build_dinov3_source_manifest import DEFAULT_ROOTS, build_manifest


def _sha(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _items(roots: tuple[Path, ...]):
    for root in roots:
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            sku_id = int(directory.name.split("_", 2)[1])
            for image in sorted(path for path in directory.rglob("*") if path.is_file()):
                yield sku_id, image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--support-output", type=Path, required=True)
    parser.add_argument("--local-bank-output", type=Path, required=True)
    parser.add_argument("--source-manifest-output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, action="append", default=None)
    args = parser.parse_args(argv)
    config = ClassifierConfig.load(args.config)
    roots = tuple(args.source_root) if args.source_root else DEFAULT_ROOTS
    source_bytes = build_manifest(roots)
    atomic_write_bytes(args.source_manifest_output, source_bytes)
    transform = build_transform(config.preprocess.input_size)
    device = torch.device(config.runtime.device.lower())
    weights = torch.load(config.dinov3.weights, map_location="cpu", weights_only=True)
    model = vit_small(patch_size=16, n_storage_tokens=4, mask_k_bias=True, layerscale_init=1e-5)
    model.load_state_dict(weights, strict=True)
    model.to(device).eval()
    globals_: dict[int, list[torch.Tensor]] = defaultdict(list)
    patches: dict[int, list[torch.Tensor]] = defaultdict(list)
    with torch.inference_mode():
        for sku_id, path in _items(roots):
            frame = load_canonical_image(path)
            features = model.forward_features(transform(frame.image).unsqueeze(0).to(device))
            globals_[sku_id].append(functional.normalize(features["x_norm_clstoken"][0], dim=0).cpu())
            patches[sku_id].append(functional.normalize(features["x_norm_patchtokens"][0], dim=1).cpu())
    if tuple(sorted(globals_)) != tuple(range(1, 21)):
        raise ValueError("source roots must contain all 20 SKU directories")
    prototypes = torch.stack([functional.normalize(torch.stack(globals_[sku]).mean(dim=0), dim=0) for sku in range(1, 21)]).float()
    class_map = [{"id": sku, "name": row["name"]} for sku, row in zip(range(1, 21), torch.load(config.dinov3.support, map_location="cpu", weights_only=True)["class_map"], strict=True)]
    weight_sha = _sha(config.dinov3.weights)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    support = {"artifact_type":"dinov3_vits16_15plus5_global_support","schema_version":1,"class_map":class_map,"prototypes":prototypes,"dino_checkpoint":{"architecture":_ARCHITECTURE,"file":config.dinov3.weights.name,"key_count":len(weights),"sha256":weight_sha,"storage_token_shape":_STORAGE_TOKEN_SHAPE},"transform":_describe_transform(transform),"source_counts":[{"sku_id":sku,"count":len(globals_[sku])} for sku in range(1,21)],"source_manifest_sha256":source_sha}
    args.support_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(support, args.support_output)
    local = {"artifact_type":"dinov3_vits16_15plus5_local_patch_bank","schema_version":1,"dino_weights_sha256":weight_sha,"preprocess_sha256":preprocess_sha256(config.preprocess),"canonical_frame_version":"exif_visual_rgb_v1","patches":{sku:torch.cat(patches[sku]).float() for sku in range(1,21)}}
    args.local_bank_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(local, args.local_bank_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
