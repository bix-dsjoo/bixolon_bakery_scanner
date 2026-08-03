"""Build fold-safe DINOv3 15+5 global/local support or an unverified receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol, Sequence

import torch

from bakery_scanner.classification.preprocess import ClassifierPreprocessDescriptor, build_transform

try:
    from tools.train.train_repvit_15plus5_oof import (
        CANONICAL_CLASS_ORDER,
        CANONICAL_CLASS_MAP,
        FoldEvidenceRows,
        FoldSources,
        LoadedExample,
        _file_identity,
        _file_sha256,
        _is_sha256,
        _input_context,
        _load_examples,
        build_repvit_sources,
        load_fold_sources,
        run_output_transaction,
        verify_runtime_receipt,
    )
except ModuleNotFoundError as exc:
    if exc.name != "tools":
        raise
    from train_repvit_15plus5_oof import (  # type: ignore[no-redef]
        CANONICAL_CLASS_ORDER,
        CANONICAL_CLASS_MAP,
        FoldEvidenceRows,
        FoldSources,
        LoadedExample,
        _file_identity,
        _file_sha256,
        _is_sha256,
        _input_context,
        _load_examples,
        build_repvit_sources,
        load_fold_sources,
        run_output_transaction,
        verify_runtime_receipt,
    )


@dataclass(frozen=True, slots=True)
class SupportContribution:
    sku_id: int
    source_role: str
    identity: str
    global_token: torch.Tensor
    local_tokens: torch.Tensor


@dataclass(frozen=True, slots=True)
class AggregatedSupport:
    global_prototypes: torch.Tensor
    local_patches: Mapping[int, torch.Tensor]
    source_counts: Mapping[int, Mapping[str, int]]
    patch_counts: Mapping[int, Mapping[str, int]]
    contributor_identities: Mapping[int, Mapping[str, tuple[str, ...]]]
    patch_identities: Mapping[int, Mapping[str, tuple[str, ...]]]


class DinoSupportExtractor(Protocol):
    def transform(self, image) -> torch.Tensor: ...
    def forward_global_local(self, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]: ...


class TorchDinoSupportExtractor:
    """Provisioned DINOv3 ViT-S/16 adapter with one global/local forward per batch."""

    def __init__(self, weights: Path, *, device: str = "cuda:0") -> None:
        from dinov3.models.vision_transformer import vit_small

        self.device = torch.device(device)
        payload = torch.load(weights, map_location="cpu", weights_only=True)
        if not isinstance(payload, Mapping):
            raise ValueError("DINOv3 weights must be a state dictionary")
        self.weights_key_count = len(payload)
        model = vit_small(
            patch_size=16,
            n_storage_tokens=4,
            mask_k_bias=True,
            layerscale_init=1e-5,
        )
        model.load_state_dict(payload, strict=True)
        self.encoder = model.to(self.device).eval()
        self._transform = build_transform(224)

    def transform(self, image) -> torch.Tensor:
        return self._transform(image.convert("RGB"))

    def forward_global_local(self, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        global_tokens, local_tokens = extract_global_local_tokens(self.encoder, batch.to(self.device))
        return global_tokens.float().cpu(), local_tokens.float().cpu()


def build_dino_sources(sources: FoldSources, *, fold_index: int) -> FoldEvidenceRows:
    """DINO support obeys the same isolated + train-scene isolation as RepViT."""
    return build_repvit_sources(sources, fold_index=fold_index)


def extract_global_local_tokens(encoder: torch.nn.Module, batch: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Extract both token kinds from exactly one DINO forward_features call."""
    if not callable(getattr(encoder, "forward_features", None)):
        raise ValueError("DINO encoder must expose forward_features")
    with torch.inference_mode():
        output = encoder.forward_features(batch)
    if not isinstance(output, Mapping):
        raise ValueError("DINO forward_features must return a mapping")
    global_tokens = output.get("x_norm_clstoken")
    local_tokens = output.get("x_norm_patchtokens")
    if not isinstance(global_tokens, torch.Tensor) or not isinstance(local_tokens, torch.Tensor):
        raise ValueError("DINO output must contain global and local tensors")
    if global_tokens.ndim != 2 or global_tokens.shape[1] != 384:
        raise ValueError("DINO global tokens must have shape (N, 384)")
    if local_tokens.ndim != 3 or local_tokens.shape[0] != global_tokens.shape[0] or local_tokens.shape[2] != 384:
        raise ValueError("DINO local tokens must have shape (N, patches, 384)")
    if not torch.isfinite(global_tokens).all().item() or not torch.isfinite(local_tokens).all().item():
        raise ValueError("DINO tokens must be finite")
    return global_tokens, local_tokens


def aggregate_support(
    contributions: Sequence[SupportContribution],
    *,
    global_contributors_per_sku_source: int,
    local_patches_per_sku_source: int,
) -> AggregatedSupport:
    """Apply contributor and patch caps before deterministic source aggregation."""
    if type(global_contributors_per_sku_source) is not int or global_contributors_per_sku_source <= 0:
        raise ValueError("global contributor cap must be positive")
    if type(local_patches_per_sku_source) is not int or local_patches_per_sku_source <= 0:
        raise ValueError("local patch cap must be positive")
    allowed_roles = ("isolated", "train_scene")
    rows = tuple(contributions)
    if any(row.sku_id not in CANONICAL_CLASS_ORDER or row.source_role not in allowed_roles for row in rows):
        raise ValueError("support contributions must use canonical SKUs and training sources")
    identities = [row.identity for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate contributor identity")
    if {row.sku_id for row in rows} != set(CANONICAL_CLASS_ORDER):
        raise ValueError("support contributions must cover every canonical SKU")
    global_rows: list[torch.Tensor] = []
    local_by_sku: dict[int, torch.Tensor] = {}
    source_counts: dict[int, dict[str, int]] = {}
    patch_counts: dict[int, dict[str, int]] = {}
    contributor_identities: dict[int, dict[str, tuple[str, ...]]] = {}
    patch_identities: dict[int, dict[str, tuple[str, ...]]] = {}
    for sku_id in CANONICAL_CLASS_ORDER:
        source_prototypes: list[torch.Tensor] = []
        selected_patches: list[torch.Tensor] = []
        source_counts[sku_id] = {}
        patch_counts[sku_id] = {}
        contributor_identities[sku_id] = {}
        patch_identities[sku_id] = {}
        for role in allowed_roles:
            candidates = sorted((row for row in rows if row.sku_id == sku_id and row.source_role == role), key=lambda row: row.identity)
            selected = candidates[:global_contributors_per_sku_source]
            valid_globals = []
            for row in selected:
                _validate_token_shapes(row)
                valid_globals.append(torch.nn.functional.normalize(row.global_token.float(), dim=0))
            source_counts[sku_id][role] = len(valid_globals)
            contributor_identities[sku_id][role] = tuple(row.identity for row in selected)
            if valid_globals:
                source_prototypes.append(torch.nn.functional.normalize(torch.stack(valid_globals).mean(dim=0), dim=0))
            role_patches = []
            role_patch_identities = []
            for row in candidates:
                _validate_token_shapes(row)
                role_patches.extend(torch.nn.functional.normalize(row.local_tokens.float(), dim=1))
                role_patch_identities.extend([row.identity] * len(row.local_tokens))
                if len(role_patches) >= local_patches_per_sku_source:
                    break
            role_patches = role_patches[:local_patches_per_sku_source]
            role_patch_identities = role_patch_identities[:local_patches_per_sku_source]
            patch_counts[sku_id][role] = len(role_patches)
            patch_identities[sku_id][role] = tuple(role_patch_identities)
            selected_patches.extend(role_patches)
        if source_prototypes:
            global_rows.append(torch.nn.functional.normalize(torch.stack(source_prototypes).mean(dim=0), dim=0))
        else:
            global_rows.append(torch.zeros(384, dtype=torch.float32))
        local_by_sku[sku_id] = torch.stack(selected_patches) if selected_patches else torch.empty((0, 384), dtype=torch.float32)
    return AggregatedSupport(
        torch.stack(global_rows), local_by_sku, source_counts, patch_counts,
        contributor_identities, patch_identities,
    )


def support_metadata(
    support: AggregatedSupport,
    *,
    rows: FoldEvidenceRows,
    weights_sha256: str,
    preprocessing_sha256: str,
    runtime_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind every source, runtime, class, tensor, and preprocessing identity."""
    if not _is_sha256(weights_sha256) or not _is_sha256(preprocessing_sha256):
        raise ValueError("support weights and preprocessing SHA-256 values are required")
    if tuple(support.global_prototypes.shape) != (20, 384):
        raise ValueError("global support tensor must have shape (20, 384)")
    if support.global_prototypes.dtype != torch.float32:
        raise ValueError("global support tensor must be float32")
    if set(support.local_patches) != set(CANONICAL_CLASS_ORDER):
        raise ValueError("local support must preserve the canonical class order")
    local_tensors: dict[str, dict[str, object]] = {}
    for sku_id in CANONICAL_CLASS_ORDER:
        tensor = support.local_patches[sku_id]
        if tensor.ndim != 2 or tensor.shape[1] != 384 or tensor.dtype != torch.float32:
            raise ValueError("local support tensors must have shape (patches, 384) and float32")
        local_tensors[str(sku_id)] = {
            "shape": list(tensor.shape),
            "dtype": str(tensor.dtype).removeprefix("torch."),
            "sha256": _tensor_sha256(tensor),
        }
    encoded_runtime = json.dumps(
        runtime_identity, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "artifact_type": "dinov3_vits16_15plus5_global_local_support_oof",
        "model_id": "dinov3_vits16_15plus5_v1",
        "weights_sha256": weights_sha256,
        "preprocessing_sha256": preprocessing_sha256,
        "preprocessing_descriptor": ClassifierPreprocessDescriptor().to_payload(),
        "fold_index": rows.fold_index,
        "fold_manifest_sha256": rows.fold_manifest_sha256,
        "source_manifest_sha256": rows.source_manifest_sha256,
        "source_rows_sha256": rows.manifest_payload()["rows_sha256"],
        "source_counts": {str(sku_id): dict(support.source_counts[sku_id]) for sku_id in CANONICAL_CLASS_ORDER},
        "patch_counts": {str(sku_id): dict(support.patch_counts[sku_id]) for sku_id in CANONICAL_CLASS_ORDER},
        "class_order": list(CANONICAL_CLASS_ORDER),
        "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
        "global_tensor": {
            "shape": list(support.global_prototypes.shape),
            "dtype": str(support.global_prototypes.dtype).removeprefix("torch."),
            "sha256": _tensor_sha256(support.global_prototypes),
        },
        "local_tensors": local_tensors,
        "selected_contributor_identities_sha256": hashlib.sha256(json.dumps(
            {str(sku_id): {role: list(values) for role, values in support.contributor_identities[sku_id].items()} for sku_id in CANONICAL_CLASS_ORDER},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "selected_patch_identities_sha256": hashlib.sha256(json.dumps(
            {str(sku_id): {role: list(values) for role, values in support.patch_identities[sku_id].items()} for sku_id in CANONICAL_CLASS_ORDER},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "runtime_identity": dict(runtime_identity),
        "runtime_identity_sha256": hashlib.sha256(encoded_runtime).hexdigest(),
        "code_sha256": _file_sha256(Path(__file__)),
    }


def _validate_token_shapes(row: SupportContribution) -> None:
    if (
        row.global_token.dtype != torch.float32
        or row.local_tokens.dtype != torch.float32
        or tuple(row.global_token.shape) != (384,)
        or row.local_tokens.ndim != 2
        or row.local_tokens.shape[1] != 384
        or len(row.local_tokens) == 0
    ):
        raise ValueError("support contribution token shapes are invalid")
    if not torch.isfinite(row.global_token).all().item() or not torch.isfinite(row.local_tokens).all().item():
        raise ValueError("support contribution tokens must be finite")
    if row.global_token.norm().item() == 0 or (row.local_tokens.norm(dim=1) == 0).any().item():
        raise ValueError("support contribution tokens must have non-zero norms")


def _tensor_sha256(value: torch.Tensor) -> str:
    tensor = value.detach().cpu().contiguous()
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def run_fold_support(
    sources: FoldSources,
    *,
    fold_index: int,
    weights: Path,
    weights_sha256: str,
    runtime_identity: Mapping[str, object],
    extractor: DinoSupportExtractor,
    output_root: Path,
    batch_size: int = 7,
    global_contributors_per_sku_source: int = 32,
    local_patches_per_sku_source: int = 512,
) -> dict[str, object]:
    """Extract, aggregate, and atomically publish one complete DINO fold."""
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("DINO support batch size must be positive")
    weights = Path(weights).resolve()
    if not weights.is_file() or _file_sha256(weights) != weights_sha256:
        raise ValueError("DINO weights SHA-256 mismatch")
    try:
        weights_payload = torch.load(weights, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ValueError("DINO weights must be a readable state dictionary") from exc
    if not isinstance(weights_payload, Mapping) or not weights_payload or any(
        not isinstance(name, str) or not isinstance(value, torch.Tensor)
        for name, value in weights_payload.items()
    ):
        raise ValueError("DINO weights must be a readable state dictionary")
    if not _is_sha256(runtime_identity.get("receipt_sha256")):
        raise ValueError("verified runtime identity receipt SHA-256 is required")
    rows = build_dino_sources(sources, fold_index=fold_index)
    examples = tuple(sorted(_load_examples(rows.rows), key=lambda example: example.source.identity))
    contributions: list[SupportContribution] = []
    for start in range(0, len(examples), batch_size):
        chunk = examples[start : start + batch_size]
        batch = torch.stack(tuple(extractor.transform(example.crops[-1]) for example in chunk))
        global_tokens, local_tokens = extractor.forward_global_local(batch)
        if global_tokens.dtype != torch.float32 or local_tokens.dtype != torch.float32:
            raise ValueError("DINO extractor token dtype must be float32")
        if tuple(global_tokens.shape) != (len(chunk), 384) or local_tokens.ndim != 3 or local_tokens.shape[0] != len(chunk) or local_tokens.shape[2] != 384:
            raise ValueError("DINO extractor token shapes do not align with admitted batch")
        for index, example in enumerate(chunk):
            patches = local_tokens[index].detach().cpu()
            product_mask = _support_product_patch_mask(
                example.product_boxes[-1], example.crops[-1].size, patches.shape[0]
            )
            selected_patches = patches[product_mask]
            if len(selected_patches) == 0:
                raise ValueError("DINO support crop contains no product patch tokens")
            contributions.append(SupportContribution(
                example.source.sku_id, example.source.source_role, example.source.identity,
                global_tokens[index].detach().cpu(), selected_patches,
            ))
    admitted = {example.source.identity for example in examples}
    actual = [row.identity for row in contributions]
    if set(actual) != admitted or len(actual) != len(admitted):
        raise ValueError("DINO contributions must map one-to-one to admitted fold rows")
    support = aggregate_support(
        tuple(contributions),
        global_contributors_per_sku_source=global_contributors_per_sku_source,
        local_patches_per_sku_source=local_patches_per_sku_source,
    )
    descriptor_sha256 = ClassifierPreprocessDescriptor().sha256()
    metadata = support_metadata(
        support, rows=rows, weights_sha256=weights_sha256,
        preprocessing_sha256=descriptor_sha256, runtime_identity=runtime_identity,
    )
    output_root = Path(output_root).resolve()
    final_root = output_root / f"fold-{fold_index}"
    if final_root.exists():
        raise FileExistsError(f"refusing to overwrite fold output: {final_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".fold-{fold_index}.pending-", dir=output_root))
    try:
        support_path = pending / "support.pt"
        local_path = pending / "local_bank.pt"
        torch.save({
            "artifact_type": "dinov3_vits16_15plus5_global_support",
            "schema_version": 1,
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "dino_checkpoint": {
                "architecture": "vit_small_patch16_dinov3_storage4",
                "file": weights.name,
                "key_count": len(weights_payload),
                "sha256": weights_sha256,
                "storage_token_shape": [1, 4, 384],
            },
            "transform": {
                "antialias": True,
                "image_mode": "RGB",
                "input_size": [224, 224],
                "mean": [0.485, 0.456, 0.406],
                "resize_interpolation": "bilinear",
                "std": [0.229, 0.224, 0.225],
            },
            "prototypes": support.global_prototypes,
            "oof_metadata": metadata,
        }, support_path)
        torch.save({
            "artifact_type": "dinov3_vits16_15plus5_local_patch_bank",
            "schema_version": 1,
            "dino_weights_sha256": weights_sha256,
            "preprocess_sha256": descriptor_sha256,
            "canonical_frame_version": "exif_visual_rgb_v1",
            "patches": dict(support.local_patches),
            "oof_metadata": metadata,
        }, local_path)
        (pending / "metadata.json").write_text(json.dumps(metadata, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        receipt = {
            "schema_version": 1, "status": "verified_success", "fold_index": fold_index,
            "support": _file_identity(support_path, shape=[20, 384], dtype="float32"),
            "local_bank": _file_identity(local_path, shape=None, dtype="float32"),
            "metadata": metadata,
        }
        _write_json_new(pending / "receipt.json", receipt)
        os.replace(pending, final_root)
        return receipt
    except Exception:
        (pending / "failure.json").write_text(json.dumps({"status": "failed_incomplete_fold", "fold_index": fold_index}, sort_keys=True), encoding="utf-8")
        raise


def _support_product_patch_mask(
    box,
    crop_size: tuple[int, int],
    token_count: int,
) -> torch.Tensor:
    width, height = crop_size
    grid = int(token_count**0.5)
    if grid * grid != token_count or width <= 0 or height <= 0:
        raise ValueError("DINO support patch-token grid is invalid")
    if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
        raise ValueError("DINO support product box must stay within its crop")
    inset_x = box.width * 0.05
    inset_y = box.height * 0.05
    centers_x = (torch.arange(grid) + 0.5) * width / grid
    centers_y = (torch.arange(grid) + 0.5) * height / grid
    xx, yy = torch.meshgrid(centers_x, centers_y, indexing="xy")
    return (
        (xx >= box.x + inset_x)
        & (xx <= box.x + box.width - inset_x)
        & (yy >= box.y + inset_y)
        & (yy <= box.y + box.height - inset_y)
    ).reshape(-1)


def _write_json_new(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {path}")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def _unverified(
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
        _write_json_new(pending / f"fold-{fold_index}" / "receipt.json", receipt)
        return receipt

    run_output_transaction(
        output, folds, producer="dinov3_vits16_15plus5_oof", fold_action=write_fold,
        transaction_status=status,
    )
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", type=Path, required=True)
    parser.add_argument("--fold", choices=("0", "1", "2", "3", "4", "all"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, default=Path(r"C:\workspace\bixolon_bakery_scanner\datasets"))
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--weights-sha256")
    parser.add_argument("--runtime-receipt", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=7)
    parser.add_argument("--global-contributors-per-sku-source", type=int, default=32)
    parser.add_argument("--local-patches-per-sku-source", type=int, default=512)
    arguments = parser.parse_args(argv)
    selected = tuple(range(5)) if arguments.fold == "all" else (int(arguments.fold),)
    output = arguments.output.resolve()
    context = _input_context(arguments.splits, code_path=Path(__file__))
    missing = []
    for label, path in (("DINO weights", arguments.weights), ("runtime receipt", arguments.runtime_receipt)):
        if path is None or not path.is_file():
            missing.append(label)
    if missing:
        return _unverified(
            output, selected, status="unverified_missing_dinov3_support_inputs",
            detail=f"missing required local input(s): {', '.join(missing)}; no automatic download attempted",
            context=context, unresolved_roles=tuple(label.lower().replace(" ", "_") for label in missing),
        )
    if not _is_sha256(arguments.weights_sha256) or _file_sha256(arguments.weights) != arguments.weights_sha256:
        return _unverified(output, selected, status="unverified_dinov3_weights_hash_mismatch", detail="declared DINOv3 weights SHA-256 did not verify", context=context, unresolved_roles=("dinov3_weights_identity",))
    resolved_files = {"dinov3_weights": arguments.weights}
    context = _input_context(arguments.splits, resolved_files=resolved_files, code_path=Path(__file__))
    try:
        sources = load_fold_sources(arguments.dataset_root, arguments.splits)
    except Exception as exc:
        return _unverified(output, selected, status="unverified_dinov3_sources", detail=f"verified fold sources unavailable: {type(exc).__name__}: {exc}", context=context, unresolved_roles=("canonical_sources",))
    context = _input_context(
        arguments.splits,
        sources=sources,
        resolved_files={**resolved_files, "runtime_receipt_candidate": arguments.runtime_receipt},
        code_path=Path(__file__),
    )
    try:
        runtime_identity = verify_runtime_receipt(
            arguments.runtime_receipt,
            required_packages=("torch", "dinov3"),
            required_artifacts={"dinov3_weights": arguments.weights},
        )
    except Exception as exc:
        return _unverified(output, selected, status="unverified_dinov3_runtime", detail=f"runtime receipt verification failed: {type(exc).__name__}: {exc}", context=context, unresolved_roles=("runtime_identity",))
    context = _input_context(
        arguments.splits,
        sources=sources,
        runtime_identity=runtime_identity,
        resolved_files={**resolved_files, "runtime_receipt": arguments.runtime_receipt},
        code_path=Path(__file__),
    )
    extractor_holder: dict[str, TorchDinoSupportExtractor] = {}

    def build_fold(fold_index: int, pending: Path) -> dict[str, object]:
        if "extractor" not in extractor_holder:
            extractor_holder["extractor"] = TorchDinoSupportExtractor(arguments.weights, device=arguments.device)
        return run_fold_support(
            sources,
            fold_index=fold_index,
            weights=arguments.weights,
            weights_sha256=arguments.weights_sha256,
            runtime_identity=runtime_identity,
            extractor=extractor_holder["extractor"],
            output_root=pending,
            batch_size=arguments.batch_size,
            global_contributors_per_sku_source=arguments.global_contributors_per_sku_source,
            local_patches_per_sku_source=arguments.local_patches_per_sku_source,
        )

    run_output_transaction(
        output,
        selected,
        producer="dinov3_vits16_15plus5_oof",
        fold_action=build_fold,
        failure_context=context,
        failure_unresolved_roles=("dinov3_fold_artifacts",),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
