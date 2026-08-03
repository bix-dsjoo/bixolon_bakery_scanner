"""Materialize one external, hash-bound RPC research support-bank receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from bakery_scanner.experiments.rpc_research_worker import (
    OracleFeatureRow,
    materialize_support_bank,
    write_support_bank,
)


_RUNS_ROOT = Path(r"C:\workspace\rpc_fewshot_runs")


def _rows_from_json(path: Path) -> tuple[OracleFeatureRow, ...]:
    """Read explicit, already-verified feature rows without copying feature payloads."""
    source = Path(path).resolve()
    if not source.is_relative_to(_RUNS_ROOT.resolve()):
        raise ValueError(f"support rows must be under {_RUNS_ROOT}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read support rows") from exc
    if not isinstance(value, Mapping) or set(value) != {"rows"} or not isinstance(value["rows"], list):
        raise ValueError("support rows must be an object containing only rows")
    rows: list[OracleFeatureRow] = []
    for item in value["rows"]:
        if not isinstance(item, Mapping) or set(item) != {
            "source_identity", "annotation_id", "category_id", "bbox_xywh", "difficulty",
            "source_byte_size", "source_sha256", "dino_global", "capture_stratum",
            "feature_array_sha256",
        }:
            raise ValueError("invalid support row")
        try:
            rows.append(
                OracleFeatureRow(
                    source_identity=item["source_identity"],
                    annotation_id=item["annotation_id"],
                    category_id=item["category_id"],
                    bbox_xywh=tuple(item["bbox_xywh"]),
                    difficulty=item["difficulty"],
                    source_byte_size=item["source_byte_size"],
                    source_sha256=item["source_sha256"],
                    dino_global=tuple(item["dino_global"]),
                    capture_stratum=item["capture_stratum"],
                    feature_array_sha256=item["feature_array_sha256"],
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid support row") from exc
    return tuple(rows)


def run(rows_path: Path, output: Path, *, selector: str, seed: int, maximum_shots: int) -> Path:
    """Create one no-replace RND or DIV receipt from external feature-row evidence."""
    bank = materialize_support_bank(
        _rows_from_json(rows_path), selector=selector, seed=seed, maximum_shots=maximum_shots
    )
    return write_support_bank(output, bank)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selector", required=True, choices=("rnd", "div"))
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--maximum-shots", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        print(run(args.rows, args.output, selector=args.selector, seed=args.seed, maximum_shots=args.maximum_shots))
    except (OSError, ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
