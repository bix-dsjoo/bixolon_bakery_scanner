"""Build fold-safe DINOv3 15+5 global/local support or an unverified receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import torch

try:
    from tools.train.train_repvit_15plus5_oof import (
        CANONICAL_CLASS_ORDER,
        CANONICAL_CLASS_MAP,
        FoldEvidenceRows,
        FoldSources,
        _file_sha256,
        _is_sha256,
        build_repvit_sources,
        load_fold_sources,
    )
except ModuleNotFoundError as exc:
    if exc.name != "tools":
        raise
    from train_repvit_15plus5_oof import (  # type: ignore[no-redef]
        CANONICAL_CLASS_ORDER,
        CANONICAL_CLASS_MAP,
        FoldEvidenceRows,
        FoldSources,
        _file_sha256,
        _is_sha256,
        build_repvit_sources,
        load_fold_sources,
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
    global_rows: list[torch.Tensor] = []
    local_by_sku: dict[int, torch.Tensor] = {}
    source_counts: dict[int, dict[str, int]] = {}
    patch_counts: dict[int, dict[str, int]] = {}
    for sku_id in CANONICAL_CLASS_ORDER:
        source_prototypes: list[torch.Tensor] = []
        selected_patches: list[torch.Tensor] = []
        source_counts[sku_id] = {}
        patch_counts[sku_id] = {}
        for role in allowed_roles:
            candidates = sorted((row for row in rows if row.sku_id == sku_id and row.source_role == role), key=lambda row: row.identity)
            selected = candidates[:global_contributors_per_sku_source]
            valid_globals = []
            for row in selected:
                _validate_token_shapes(row)
                valid_globals.append(torch.nn.functional.normalize(row.global_token.float(), dim=0))
            source_counts[sku_id][role] = len(valid_globals)
            if valid_globals:
                source_prototypes.append(torch.nn.functional.normalize(torch.stack(valid_globals).mean(dim=0), dim=0))
            role_patches = []
            for row in candidates:
                _validate_token_shapes(row)
                role_patches.extend(torch.nn.functional.normalize(row.local_tokens.float(), dim=1))
                if len(role_patches) >= local_patches_per_sku_source:
                    break
            role_patches = role_patches[:local_patches_per_sku_source]
            patch_counts[sku_id][role] = len(role_patches)
            selected_patches.extend(role_patches)
        if source_prototypes:
            global_rows.append(torch.nn.functional.normalize(torch.stack(source_prototypes).mean(dim=0), dim=0))
        else:
            global_rows.append(torch.zeros(384, dtype=torch.float32))
        local_by_sku[sku_id] = torch.stack(selected_patches) if selected_patches else torch.empty((0, 384), dtype=torch.float32)
    return AggregatedSupport(torch.stack(global_rows), local_by_sku, source_counts, patch_counts)


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
        },
        "local_tensors": local_tensors,
        "runtime_identity": dict(runtime_identity),
        "runtime_identity_sha256": hashlib.sha256(encoded_runtime).hexdigest(),
        "code_sha256": _file_sha256(Path(__file__)),
    }


def _validate_token_shapes(row: SupportContribution) -> None:
    if tuple(row.global_token.shape) != (384,) or row.local_tokens.ndim != 2 or row.local_tokens.shape[1] != 384:
        raise ValueError("support contribution token shapes are invalid")
    if not torch.isfinite(row.global_token).all().item() or not torch.isfinite(row.local_tokens).all().item():
        raise ValueError("support contribution tokens must be finite")


def _write_json_new(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {path}")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def _unverified(output: Path, folds: Iterable[int], *, status: str, detail: str) -> int:
    for fold_index in folds:
        _write_json_new(output / f"fold-{fold_index}" / "receipt.json", {
            "schema_version": 1,
            "fold_index": fold_index,
            "status": status,
            "detail": detail,
            "class_order": list(CANONICAL_CLASS_ORDER),
            "class_map": [dict(row) for row in CANONICAL_CLASS_MAP],
            "code_sha256": _file_sha256(Path(__file__)),
        })
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
    arguments = parser.parse_args(argv)
    selected = tuple(range(5)) if arguments.fold == "all" else (int(arguments.fold),)
    output = arguments.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to reuse output root: {output}")
    missing = []
    for label, path in (("DINO weights", arguments.weights), ("runtime receipt", arguments.runtime_receipt)):
        if path is None or not path.is_file():
            missing.append(label)
    if missing:
        return _unverified(output, selected, status="unverified_missing_dinov3_support_inputs", detail=f"missing required local input(s): {', '.join(missing)}; no automatic download attempted")
    if not _is_sha256(arguments.weights_sha256) or _file_sha256(arguments.weights) != arguments.weights_sha256:
        return _unverified(output, selected, status="unverified_dinov3_weights_hash_mismatch", detail="declared DINOv3 weights SHA-256 did not verify")
    try:
        load_fold_sources(arguments.dataset_root, arguments.splits)
    except Exception as exc:
        return _unverified(output, selected, status="unverified_dinov3_sources", detail=f"verified fold sources unavailable: {type(exc).__name__}: {exc}")
    return _unverified(output, selected, status="unverified_dinov3_support_not_executed", detail="validated inputs are present but this source-only producer requires the provisioned DINO runtime adapter")


if __name__ == "__main__":
    raise SystemExit(main())
