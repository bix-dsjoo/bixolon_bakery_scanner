"""Select a classifier policy using grouped development evidence only."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from bakery_scanner.classification.evidence import (
    atomic_write_bytes,
    load_evidence_rows,
    select_policy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-fit and select classifier abstention policy parameters."
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260727)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load_evidence_rows(args.evidence)
    calibration = select_policy(rows, folds=args.folds, seed=args.seed)
    atomic_write_bytes(args.output, calibration.to_json_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
