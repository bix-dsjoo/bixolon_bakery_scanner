"""Materialize one external, hash-bound RPC research support-bank receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from bakery_scanner.experiments.rpc_research_worker import (
    materialize_support_bank_from_feature_manifest,
    write_support_bank,
)


def run(feature_manifest: Path, output: Path, *, selector: str, seed: int, maximum_shots: int) -> Path:
    """Create one receipt directly from a verified Task 1 feature cache."""
    bank = materialize_support_bank_from_feature_manifest(
        feature_manifest, selector=selector, seed=seed, maximum_shots=maximum_shots
    )
    return write_support_bank(output, bank)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selector", required=True, choices=("rnd", "div"))
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--maximum-shots", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        print(run(args.features_manifest, args.output, selector=args.selector, seed=args.seed, maximum_shots=args.maximum_shots))
    except (OSError, ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
