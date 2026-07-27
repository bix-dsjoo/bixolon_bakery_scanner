"""Evaluate the production classifier path on independently labeled boxes.

The manifest box is only the classifier input contract for this tool.  Detector and
Verifier quality are measured separately; this tool does not substitute a ground
truth box result for a full scan result.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.contracts import ClassificationDecision
from bakery_scanner.classification.evidence import (
    EvaluatedRow,
    atomic_write_bytes,
    canonical_json_bytes,
    evaluate_rows,
    load_dinov3_support_training_hashes,
    load_evidence_manifest,
    load_repvit_training_hashes,
)
from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.classification.config import ClassifierConfig
from bakery_scanner.data.preprocess import load_canonical_image


def evaluated_row_from_decision(
    *,
    sample_id: str,
    registered: bool,
    sku_id: int | None,
    decision: ClassificationDecision,
) -> EvaluatedRow:
    """Convert the exact runtime decision to the existing evaluation contract."""
    return EvaluatedRow(
        sample_id=sample_id,
        registered=registered,
        sku_id=sku_id,
        decision=decision.decision,
        predicted_sku_id=decision.sku_id,
        top3=tuple(candidate.sku_id for candidate in decision.top3),
    )


def evaluate_runtime_manifest(
    pipeline: ClassifierPipeline,
    inputs,
) -> tuple[tuple[EvaluatedRow, ...], tuple[ClassificationDecision, ...]]:
    evaluated: list[EvaluatedRow] = []
    decisions: list[ClassificationDecision] = []
    for item in inputs:
        decision = pipeline.infer(load_canonical_image(item.image_path), item.box)
        decisions.append(decision)
        evaluated.append(
            evaluated_row_from_decision(
                sample_id=item.sample_id,
                registered=item.registered,
                sku_id=item.sku_id,
                decision=decision,
            )
        )
    return tuple(evaluated), tuple(decisions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the complete RepViT + DINO local-recheck path on a classifier manifest."
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
    ) | load_dinov3_support_training_hashes(config.dinov3.support, args.dino_source_manifest)
    inputs = load_evidence_manifest(args.manifest, training_image_hashes=training_hashes)
    pipeline = ClassifierPipeline.load(args.config)
    evaluated, decisions = evaluate_runtime_manifest(pipeline, inputs)
    metrics = evaluate_rows(evaluated).to_dict()
    report = {
        "box_source": "manifest_classifier_box",
        "decisions": [
            {
                "decision": decision.decision,
                "decision_path": decision.decision_path.value,
                "predicted_sku_id": decision.sku_id,
                "sample_id": item.sample_id,
                "timings_ms": {
                    "dinov3": decision.timings.dinov3_ms,
                    "repvit": decision.timings.repvit_ms,
                    "total": decision.timings.total_ms,
                },
                "top3": [candidate.sku_id for candidate in decision.top3],
                "unknown_reason": decision.unknown_reason,
            }
            for item, decision in zip(inputs, decisions, strict=True)
        ],
        "metrics": metrics,
        "schema_version": 1,
    }
    atomic_write_bytes(args.output, canonical_json_bytes(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
