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
from bakery_scanner.classification.preprocess import make_padded_crops
from bakery_scanner.classification.repvit import RepVitM1Runner
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Force RepViT and DINOv3 over independent classifier evidence."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dino-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
