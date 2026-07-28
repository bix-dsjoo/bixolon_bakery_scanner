"""Force both classifier models over independent labeled evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol, Sequence

from PIL import Image

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.contracts import ModelScoreVector
from bakery_scanner.classification.dinov3 import DinoV3Rechecker
from bakery_scanner.classification.evidence import (
    EvidenceInput,
    EvidenceRow,
    atomic_write_bytes,
    load_evidence_manifest,
    load_dinov3_support_training_hashes,
    load_repvit_training_hashes,
)
from bakery_scanner.classification.full_evidence import FullEvidenceRow
from bakery_scanner.classification.local_bank import LocalPatchBank
from bakery_scanner.classification.preprocess import make_padded_crops, make_padded_crops_with_product_boxes
from bakery_scanner.classification.repvit import RepVitM1Runner, RepVitPrototypeBank
from bakery_scanner.data.preprocess import load_canonical_image


class _Runner(Protocol):
    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector: ...


def collect_rows(
    inputs: Sequence[EvidenceInput],
    repvit: _Runner,
    dino: _Runner,
    *,
    paddings: tuple[float, ...],
    provenance: dict[str, str] | None = None,
) -> tuple[EvidenceRow, ...]:
    """Score every sample with both models, validating all rows in memory."""
    rows: list[EvidenceRow] = []
    for item in inputs:
        frame = load_canonical_image(item.image_path)
        frame.require_box(item.box)
        crops = make_padded_crops(frame.image, item.box, paddings)
        repvit_scores = repvit.score(crops)
        dino_scores = dino.score(crops)
        rows.append(
            EvidenceRow(
                sample_id=item.sample_id,
                capture_group=item.capture_group,
                registered=item.registered,
                sku_id=item.sku_id,
                role=item.role,
                image_sha256=item.image_sha256,
                repvit_values=repvit_scores.values,
                dinov3_values=dino_scores.values,
                repvit_artifact_id=repvit_scores.model_id,
                dinov3_artifact_id=dino_scores.model_id,
                repvit_checkpoint_sha256=(provenance or {}).get(
                    "repvit_checkpoint_sha256", "0" * 64
                ),
                repvit_manifest_sha256=(provenance or {}).get(
                    "repvit_manifest_sha256", "0" * 64
                ),
                dinov3_weights_sha256=(provenance or {}).get(
                    "dinov3_weights_sha256", "0" * 64
                ),
                dinov3_support_sha256=(provenance or {}).get(
                    "dinov3_support_sha256", "0" * 64
                ),
                preprocess_sha256=(provenance or {}).get("preprocess_sha256", "0" * 64),
                scenario_schema_version=item.scenario_schema_version,
                scenarios=item.scenarios,
            )
        )
    if len(rows) != len(inputs):
        raise RuntimeError("evidence collection did not produce one row per input")
    return tuple(rows)


def collect_full_rows(
    inputs: Sequence[EvidenceInput],
    repvit,
    prototype_bank,
    dino,
    local_bank,
    *,
    paddings: tuple[float, ...],
    provenance: dict[str, str] | None = None,
) -> tuple[FullEvidenceRow, ...]:
    """Collect all shared ranking evidence from the same three-view path as runtime."""
    rows: list[FullEvidenceRow] = []
    metadata = provenance or {}
    for item in inputs:
        frame = load_canonical_image(item.image_path)
        frame.require_box(item.box)
        crops, product_boxes = make_padded_crops_with_product_boxes(
            frame.image, item.box, paddings
        )
        repvit_evidence = repvit.score_with_evidence(crops)
        dino_evidence = dino.score_global_and_local_evidence(
            crops, product_boxes, local_bank, repvit_scores=repvit_evidence.scores
        )
        global_scores, local_scores, patch_count, patch_ratio = dino_evidence
        candidate_ids = tuple(local_scores)
        rows.append(
            FullEvidenceRow(
                sample_id=item.sample_id,
                capture_group=item.capture_group,
                registered=item.registered,
                sku_id=item.sku_id,
                role=item.role,
                image_sha256=item.image_sha256,
                repvit_values=repvit_evidence.scores.values,
                dinov3_values=global_scores.values,
                candidate_sku_ids=candidate_ids,
                local_values=tuple(local_scores[sku_id] for sku_id in candidate_ids),
                repvit_crop_disagreement=repvit_evidence.crop_disagreement,
                nearest_prototype_distance=min(prototype_bank.distances(repvit_evidence.feature)),
                local_product_patch_count=patch_count,
                local_product_patch_ratio=patch_ratio,
                repvit_checkpoint_sha256=metadata.get("repvit_checkpoint_sha256", "0" * 64),
                repvit_manifest_sha256=metadata.get("repvit_manifest_sha256", "0" * 64),
                repvit_prototype_sha256=metadata.get("repvit_prototype_sha256", "0" * 64),
                dinov3_weights_sha256=metadata.get("dinov3_weights_sha256", "0" * 64),
                dinov3_support_sha256=metadata.get("dinov3_support_sha256", "0" * 64),
                dinov3_local_bank_sha256=metadata.get("dinov3_local_bank_sha256", "0" * 64),
                preprocess_sha256=metadata.get("preprocess_sha256", "0" * 64),
                scenario_schema_version=item.scenario_schema_version,
                scenarios=item.scenarios,
            )
        )
    if len(rows) != len(inputs):
        raise RuntimeError("full evidence collection did not produce one row per input")
    return tuple(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Force RepViT and DINOv3 over independent classifier evidence."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dino-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--full-output",
        type=Path,
        help="Optional full runtime-ranking evidence JSONL output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ClassifierConfig.load(args.config)
    training_hashes = load_repvit_training_hashes(
        config.repvit.manifest, expected_sha256=config.repvit.manifest_sha256
    ) | load_dinov3_support_training_hashes(
        config.dinov3.support, args.dino_source_manifest
    )
    inputs = load_evidence_manifest(
        args.manifest,
        training_image_hashes=training_hashes,
    )
    repvit = RepVitM1Runner.load(config)
    dino = DinoV3Rechecker.load(config)
    rows = collect_rows(
        inputs,
        repvit,
        dino,
        paddings=config.preprocess.paddings,
        provenance={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
    )
    payload = b"".join(row.to_json_bytes() + b"\n" for row in rows)
    atomic_write_bytes(args.output, payload)
    if args.full_output is not None:
        if config.repvit.prototype_bank is None or config.repvit.prototype_bank_sha256 is None:
            raise ValueError("RepViT prototype bank is required for full evidence")
        if config.dinov3.local_bank is None or config.dinov3.local_bank_sha256 is None:
            raise ValueError("DINO local bank is required for full evidence")
        prototype_bank = RepVitPrototypeBank.load(
            config.repvit.prototype_bank,
            checkpoint_sha256=config.repvit.checkpoint_sha256,
            expected_preprocess_sha256=preprocess_sha256(config.preprocess),
            expected_sha256=config.repvit.prototype_bank_sha256,
        )
        local_bank = LocalPatchBank.load(
            config.dinov3.local_bank,
            dino_weights_sha256=config.dinov3.weights_sha256,
            preprocess_sha256=preprocess_sha256(config.preprocess),
        )
        if local_bank.sha256 != config.dinov3.local_bank_sha256:
            raise ValueError("DINO local bank SHA-256 mismatch")
        full_rows = collect_full_rows(
            inputs,
            repvit,
            prototype_bank,
            dino,
            local_bank,
            paddings=config.preprocess.paddings,
            provenance={
                "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
                "repvit_manifest_sha256": config.repvit.manifest_sha256,
                "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
                "dinov3_weights_sha256": config.dinov3.weights_sha256,
                "dinov3_support_sha256": config.dinov3.support_sha256,
                "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256,
                "preprocess_sha256": preprocess_sha256(config.preprocess),
            },
        )
        atomic_write_bytes(
            args.full_output,
            b"".join(row.to_json_bytes() + b"\n" for row in full_rows),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
